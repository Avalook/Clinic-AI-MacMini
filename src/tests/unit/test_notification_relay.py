"""Unit tests for the event_log notification outbox relay."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from clinicai.services import notification_relay as relay
from clinicai.services.notification_relay import poll_and_deliver

CLINIC_ID = "a0000000-0000-4000-8000-000000000001"


def _relay_db(
    rows: list[dict[str, Any]], *fetchvals: object
) -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()
    acquire = AsyncMock()
    acquire.__aenter__.return_value = conn
    pool.acquire.return_value = acquire
    # 15/08/2026: relay đọc thêm aggregate_* để làm giàu tin — fixture cũ
    # không có hai khoá ấy thì đắp None (None = không làm giàu, đường cũ).
    conn.fetch.return_value = [
        {"aggregate_type": None, "aggregate_id": None, **r} for r in rows
    ]
    conn.fetchval.side_effect = fetchvals
    conn.execute.return_value = "UPDATE 1"
    return pool, conn


@pytest.mark.asyncio
async def test_relay_claims_and_marks_canonical_event_log_row() -> None:
    event_id = uuid4()
    pool, conn = _relay_db(
        [
            {
                "event_id": event_id,
                "event_type": "appointment.created",
                "payload": {"patient_name": "Lan"},
                "metadata": {},
            }
        ],
        True,  # advisory lock acquired
        True,  # event still unpublished after acquiring the lock
    )

    with (
        patch(
            "clinicai.services.notification_relay.notification_templates.render",
            return_value="Có lịch hẹn mới",
        ),
        patch(
            "clinicai.services.notification_relay.telegram.send_telegram",
            new=AsyncMock(return_value={"ok": True}),
        ),
    ):
        assert await poll_and_deliver(pool, clinic_id=CLINIC_ID) == 1

    select_sql = conn.fetch.await_args.args[0]
    assert "SELECT event_id" in select_sql
    assert "ORDER BY occurred_at" in select_sql
    assert "clinic_id = $1::uuid" in select_sql
    assert conn.fetch.await_args.args[1] == CLINIC_ID
    assert "SELECT id" not in select_sql
    assert "created_at" not in select_sql

    claim_sql = conn.fetchval.await_args_list[0].args[0]
    assert "pg_try_advisory_lock" in claim_sql
    update_calls = [
        call.args
        for call in conn.execute.await_args_list
        if "UPDATE event_log" in call.args[0]
    ]
    assert len(update_calls) == 1
    assert "WHERE event_id = $1 AND clinic_id = $2::uuid" in update_calls[0][0]
    # PHẢI LÀ CHUỖI, không phải UUID object: ba câu SQL của vòng khoá bind
    # event_id vào $1::text, và asyncpg từ chối UUID ở đó bằng DataError —
    # đo trên prod ngay lần poll THẬT đầu tiên (15/08/2026).
    assert update_calls[0][1] == str(event_id)
    assert update_calls[0][2] == CLINIC_ID

    claim_args = conn.fetchval.await_args_list[0].args
    assert claim_args[1] == str(event_id), (
        "khoá advisory băm chuỗi — đưa UUID object vào là DataError giữa vòng poll"
    )


@pytest.mark.asyncio
async def test_relay_does_not_send_event_claimed_by_another_worker() -> None:
    pool, conn = _relay_db(
        [
            {
                "event_id": uuid4(),
                "event_type": "appointment.created",
                "payload": {},
                "metadata": {},
            }
        ],
        False,
    )
    send = AsyncMock(return_value={"ok": True})

    with (
        patch(
            "clinicai.services.notification_relay.notification_templates.render",
            return_value="Có lịch hẹn mới",
        ),
        patch(
            "clinicai.services.notification_relay.telegram.send_telegram",
            new=send,
        ),
    ):
        assert await poll_and_deliver(pool, clinic_id=CLINIC_ID) == 0

    send.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_result", "expected_attempts"),
    [
        ({"ok": False}, 3),
        ({"ok": False, "skipped": True}, 1),
    ],
)
async def test_relay_does_not_publish_unaccepted_delivery(
    provider_result: dict[str, object], expected_attempts: int
) -> None:
    pool, conn = _relay_db(
        [
            {
                "event_id": uuid4(),
                "event_type": "appointment.created",
                "payload": {},
                "metadata": {},
            }
        ],
        True,
        True,
    )

    with (
        patch(
            "clinicai.services.notification_relay.notification_templates.render",
            return_value="Có lịch hẹn mới",
        ),
        patch(
            "clinicai.services.notification_relay.telegram.send_telegram",
            new=AsyncMock(return_value=provider_result),
        ) as send,
    ):
        assert await poll_and_deliver(pool, clinic_id=CLINIC_ID) == 0

    assert send.await_count == expected_attempts
    assert not any(
        "UPDATE event_log" in call.args[0] for call in conn.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_failed_sends_wait_between_attempts() -> None:
    """Ba lần thử liên tiếp không nghỉ chỉ là một lần thử.

    Vòng cũ gọi ``send_telegram`` ba lần trong vài mili-giây. Nguyên nhân hỏng
    lần một — mạng chớp, 429, provider đang khởi động lại — vẫn còn nguyên ở lần
    hai và ba, nên chúng chỉ tốn thời gian và đẩy thêm request vào chỗ đang quá
    tải. Bài kiểm này ghim: có nghỉ, nghỉ tăng dần, và KHÔNG nghỉ sau lần cuối
    (lúc đó chẳng còn gì để chờ).
    """
    pool, _conn = _relay_db(
        [
            {
                "event_id": uuid4(),
                "event_type": "appointment.created",
                "payload": {},
                "metadata": {},
            }
        ],
        True,  # advisory lock acquired
        True,  # event still unpublished
    )

    with (
        patch(
            "clinicai.services.notification_relay.notification_templates.render",
            return_value="Có lịch hẹn mới",
        ),
        patch(
            "clinicai.services.notification_relay.telegram.send_telegram",
            new=AsyncMock(return_value={"ok": False}),
        ) as send,
        patch(
            "clinicai.services.notification_relay.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep,
    ):
        assert await poll_and_deliver(pool, clinic_id=CLINIC_ID) == 0

    assert send.await_count == relay.MAX_RETRIES
    # Nghỉ giữa các lần thử, tức là ít hơn số lần thử đúng một.
    waited = [call.args[0] for call in sleep.await_args_list]
    assert waited == [
        relay.RETRY_BACKOFF_SECONDS * (2**i) for i in range(relay.MAX_RETRIES - 1)
    ], f"chờ sai nhịp: {waited}"


@pytest.mark.asyncio
async def test_a_successful_send_never_waits() -> None:
    """Đường thuận lợi không được chậm đi vì cơ chế thử lại."""
    pool, _conn = _relay_db(
        [
            {
                "event_id": uuid4(),
                "event_type": "appointment.created",
                "payload": {},
                "metadata": {},
            }
        ],
        True,
        True,
    )

    with (
        patch(
            "clinicai.services.notification_relay.notification_templates.render",
            return_value="Có lịch hẹn mới",
        ),
        patch(
            "clinicai.services.notification_relay.telegram.send_telegram",
            new=AsyncMock(return_value={"ok": True}),
        ),
        patch(
            "clinicai.services.notification_relay.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep,
    ):
        assert await poll_and_deliver(pool, clinic_id=CLINIC_ID) == 1

    sleep.assert_not_awaited()


def test_bo_loc_danh_thuc_chi_nghe_event_log_cua_dung_phong_kham() -> None:
    """Kênh 'clinicai_changes' chở MỌI bảng live — relay chỉ thức vì
    event_log của chính mình; tin méo thì thức cho chắc (quét thừa rẻ hơn
    một sự kiện nằm chờ 30 giây)."""
    from clinicai.services.notification_relay import nen_danh_thuc

    cua_minh = '{"t": "event_log", "c": "' + CLINIC_ID + '"}'
    assert nen_danh_thuc(cua_minh, CLINIC_ID) is True
    assert (
        nen_danh_thuc('{"t": "appointment", "c": "' + CLINIC_ID + '"}', CLINIC_ID)
        is False
    )
    assert nen_danh_thuc('{"t": "event_log", "c": "khac"}', CLINIC_ID) is False
    assert nen_danh_thuc("tin méo không phải json", CLINIC_ID) is True


def test_trigger_event_log_chi_insert() -> None:
    """Relay đánh dấu đã-gửi bằng UPDATE lên chính event_log — trigger notify
    mà nghe cả UPDATE là relay tự đánh thức mình thành vòng lặp vô tận."""
    from pathlib import Path

    sql = Path(
        "supabase/migrations/20260815000003_notify_event_log_cho_relay.sql"
    ).read_text(encoding="utf-8")
    assert "AFTER INSERT ON public.event_log" in sql
    assert "UPDATE" not in sql.split("CREATE TRIGGER")[1], (
        "trigger nghe UPDATE là vòng lặp tự đánh thức"
    )
