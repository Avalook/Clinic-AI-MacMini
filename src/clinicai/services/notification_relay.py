"""Notification relay — polls event_log and delivers via Telegram/Zalo.

Phase 3 of the System Design completion plan (Bài 9 + Bài 23).

This is a lightweight outbox relay that does NOT require RabbitMQ:
  1. Poll event_log for rows where event_published = FALSE
  2. Render the event into a notification message (templates)
  3. Send via Telegram (and/or Zalo when configured)
  4. Mark event_published = TRUE

Designed to run in a loop from worker.py (--relay mode) or as a
standalone script.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import structlog

from clinicai.core.clock import CLINIC_TZ
from clinicai.services import notification_templates
from clinicai.services.providers import telegram

logger = structlog.get_logger()

# How many unpublished events to process per poll cycle.
BATCH_SIZE = 50
# Max send attempts per poll; failures remain unpublished for a later poll.
MAX_RETRIES = 3
# Chờ giữa hai lần thử, nhân đôi mỗi lần: 0.5s rồi 1.0s.
#
# BA LẦN THỬ LIÊN TIẾP KHÔNG NGHỈ LÀ MỘT LẦN THỬ.
# Vòng cũ gọi send_telegram() ba lần sát nhau trong vài mili-giây. Thứ làm hỏng
# lần một — mạng chớp, Telegram trả 429, provider đang khởi động lại — vẫn còn
# nguyên ở lần hai và lần ba, nên hai lần sau chỉ tốn thời gian và đẩy thêm
# request vào đúng chỗ đang quá tải. Với SEND_TIMEOUT = 10s ở providers/telegram,
# một sự cố kéo dài làm mỗi sự kiện ngốn tới 30 giây của vòng poll.
#
# Cố ý để ngắn: đây là lưới cho trục trặc thoáng qua. Hỏng lâu thì sự kiện nằm
# lại chờ vòng poll sau — đó mới là chỗ retry thuộc về.
RETRY_BACKOFF_SECONDS = 0.5


async def _lam_giau(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    aggregate_type: str | None,
    aggregate_id: str | None,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Đắp tên/giờ/dịch vụ vào payload TRƯỚC khi soạn tin.

    ``event_log.payload`` cố ý chỉ mang ID (nó là sổ sự kiện, không phải bản
    sao hồ sơ) — nhưng một tin nhắn toàn UUID thì không ai đọc được. Tra
    database NGAY LÚC GỬI thay vì lúc ghi: tin kể trạng thái mới nhất, và
    người ghi sự kiện không phải gánh thêm nghĩa vụ "nhớ đủ cột cho Telegram".

    Chỉ đắp cho sự kiện CÓ template và có lịch hẹn để tra; còn lại trả
    nguyên — render sẽ tự trả None và relay đánh dấu bỏ qua như cũ.
    KHÔNG đắp số điện thoại — xem đầu notification_templates.
    """
    if (
        aggregate_type != "appointment"
        or not aggregate_id
        or event_type not in notification_templates.TEMPLATES
    ):
        return payload
    row = await conn.fetchrow(
        """
        SELECT a.slot_start,
               p.full_name  AS ten_khach,
               p.patient_code,
               bs.full_name AS ten_bac_si,
               bs_go.full_name AS bac_si_da_go,
               st.name      AS dich_vu,
               a.ly_do_huy_ma
          FROM appointment a
          LEFT JOIN patient p       ON p.clinic_patient_id = a.clinic_patient_id
          LEFT JOIN staff bs        ON bs.id = a.doctor_id
          LEFT JOIN staff bs_go     ON bs_go.id = a.bac_si_da_go_id
          LEFT JOIN service_type st ON st.id = a.service_type_id
         WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
        """,
        aggregate_id,
        clinic_id,
    )
    if row is None:
        return payload
    gio = (
        row["slot_start"].astimezone(CLINIC_TZ).strftime("%H:%M %d/%m")
        if row["slot_start"]
        else None
    )
    # Sự kiện nói gì thì giữ nguyên (payload thắng) — chỉ đắp chỗ trống.
    dap = {
        "gio_kham": gio,
        "ten_khach": row["ten_khach"],
        "patient_code": row["patient_code"],
        "ten_bac_si": row["ten_bac_si"],
        "bac_si_da_go": row["bac_si_da_go"],
        "dich_vu": row["dich_vu"],
        "ly_do_huy_ma": row["ly_do_huy_ma"],
    }
    return {**{k: v for k, v in dap.items() if v is not None}, **payload}


async def poll_and_deliver(pool: asyncpg.Pool, *, clinic_id: str) -> int:
    """Poll unpublished events and deliver notifications.

    Returns the number of events successfully processed.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_id, event_type, payload, metadata,
                   aggregate_type, aggregate_id
            FROM event_log
            WHERE clinic_id = $1::uuid
              AND event_published = FALSE
            ORDER BY occurred_at ASC
            LIMIT $2
            """,
            clinic_id,
            BATCH_SIZE,
        )

        if not rows:
            return 0

        delivered = 0

        for row in rows:
            # ÉP VỀ CHUỖI MỘT LẦN Ở ĐÂY. Cột event_id là uuid; asyncpg trả
            # UUID object, mà cả ba câu bên dưới đều bind nó vào $1::text
            # (khoá advisory băm theo chuỗi) — đưa UUID thẳng vào là DataError
            # "expected str, got UUID". Lỗi nằm sẵn từ Bài 23 và chỉ lộ ra ở
            # lần chạy THẬT đầu tiên (15/08/2026) — mọi test trước đó mock
            # fetchval nên không con đường nào chạm tới encoder của asyncpg.
            event_id = str(row["event_id"])
            claimed = await conn.fetchval(
                """
                SELECT pg_try_advisory_lock(
                    hashtextextended($1::text, 0)
                )
                """,
                event_id,
            )
            if not claimed:
                continue

            try:
                # Another relay may have completed after this batch SELECT but
                # before we acquired the session-level advisory lock.
                still_unpublished = await conn.fetchval(
                    """
                    SELECT NOT event_published
                    FROM event_log
                    WHERE event_id = $1
                      AND clinic_id = $2::uuid
                    """,
                    event_id,
                    clinic_id,
                )
                if not still_unpublished:
                    continue

                event_type = row["event_type"]
                payload: dict[str, Any] = (
                    json.loads(row["payload"])
                    if isinstance(row["payload"], str)
                    else (row["payload"] or {})
                )

                payload = await _lam_giau(
                    conn,
                    clinic_id=clinic_id,
                    aggregate_type=row["aggregate_type"],
                    aggregate_id=(
                        str(row["aggregate_id"]) if row["aggregate_id"] else None
                    ),
                    event_type=event_type,
                    payload=payload,
                )
                message = notification_templates.render(event_type, payload)
                if message is None:
                    await _mark_published(conn, event_id, clinic_id)
                    logger.debug(
                        "relay_no_template",
                        event_type=event_type,
                        event_id=str(event_id),
                    )
                    delivered += 1
                    continue

                success = False
                for attempt in range(1, MAX_RETRIES + 1):
                    result = await telegram.send_telegram(message)
                    if result.get("ok") is True:
                        success = True
                        break
                    if result.get("skipped"):
                        # Missing provider config cannot recover within this
                        # poll. Leave the event pending for a later fixed run.
                        break
                    logger.warning(
                        "relay_telegram_retry",
                        event_id=str(event_id),
                        attempt=attempt,
                    )
                    # Không ngủ sau lần cuối: lúc đó không còn lần thử nào để chờ.
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(
                            RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                        )

                if success:
                    await _mark_published(conn, event_id, clinic_id)
                    delivered += 1
                else:
                    logger.error(
                        "relay_delivery_failed",
                        event_id=str(event_id),
                        event_type=event_type,
                    )
            finally:
                await conn.execute(
                    """
                    SELECT pg_advisory_unlock(
                        hashtextextended($1::text, 0)
                    )
                    """,
                    event_id,
                )

    logger.info("relay_poll_complete", processed=delivered, total=len(rows))
    return delivered


async def _mark_published(
    conn: asyncpg.Connection, event_id: Any, clinic_id: str
) -> None:
    """Mark an event as published in the outbox."""
    await conn.execute(
        "UPDATE event_log SET event_published = TRUE "
        "WHERE event_id = $1 AND clinic_id = $2::uuid",
        event_id,
        clinic_id,
    )
