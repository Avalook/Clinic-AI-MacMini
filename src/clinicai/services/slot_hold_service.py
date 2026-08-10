"""Giữ chỗ trong lúc CSKH đang chọn khung giờ.

Quyết định của Quang (2026-08-04): *"cái đếm 10' chỉ sinh event khi mà CSKH
đang chọn khung giờ khám để CSKH khác được hiện là khung này đang được giữ để
đặt để tránh đặt trùng, chứ không phải đã ấn đặt lịch rồi lại còn giữ 10' làm
gì"*.

CÁI ĐANG CHẠY LÀM SAI CHỖ NÀY. Màn đặt lịch dán nhãn "Đang giữ" lên ô nào có
lịch hẹn ở trạng thái WAITING/CSKH_CONFIRMED — tức là nó gọi một LỊCH ĐÃ ĐẶT
XONG là "đang giữ". Ghế đã bán và ghế đang có người đứng cạnh là hai thứ khác
nhau, và gộp lại thì CSKH thứ hai không biết khung nào thật sự còn chỗ.

GIỮ CHỖ LÀ TƯ VẤN, KHÔNG PHẢI KHOÁ. Chốt chặn thật vẫn là trigger sức chứa lúc
INSERT lịch hẹn. Một dòng giữ chỗ bị rò (đóng trình duyệt giữa chừng) làm phiền
người khác trong tối đa 10 phút chứ không chặn được ai — và không bao giờ làm
một lịch hẹn hợp lệ bị từ chối.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity

logger = structlog.get_logger()

HOLD_MINUTES = 10

# Ai đặt lịch được thì giữ chỗ được — cùng danh sách với INTAKE_ROLES bên
# booking_service, và policy RLS của bảng cũng chép đúng danh sách này.
HOLD_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.CSKH,
        ClinicRole.RECEPTION,
        ClinicRole.MANAGEMENT,
        ClinicRole.TRUONG_CA,
    }
)


def _assert_may_hold(identity: StaffIdentity) -> None:
    if identity.role not in HOLD_ROLES:
        raise ValidationError(
            f"Vai trò {identity.role.value} không giữ chỗ đặt lịch được."
        )


class SlotHoldService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def hold(
        self,
        *,
        identity: StaffIdentity,
        slot_start: datetime,
        slot_end: datetime,
        doctor_id: str | None,
        clinic_patient_id: str | None = None,
    ) -> dict[str, Any]:
        """Giữ khung giờ này cho tới khi đặt xong, hoặc 10 phút.

        Chọn lại khung khác thì lần giữ trước được thả — nếu không, một CSKH
        bấm lướt qua năm khung sẽ để lại năm chỗ "đang giữ" mà họ không hề định
        đặt, và màn hình của người bên cạnh đầy cảnh báo giả.
        """
        _assert_may_hold(identity)
        if slot_end <= slot_start:
            raise ValidationError("Khung giờ không hợp lệ.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                released = await self._release_mine(
                    conn, identity=identity, reason="cancelled", keep=slot_start
                )
                row = await conn.fetchrow(
                    """
                    INSERT INTO public.slot_hold
                        (clinic_id, doctor_id, slot_start, slot_end, held_by,
                         expires_at)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid,
                            now() + ($6 || ' minutes')::interval)
                    ON CONFLICT (clinic_id, held_by, slot_start,
                                 coalesce(doctor_id,
                                          '00000000-0000-0000-0000-000000000000'::uuid))
                      WHERE released_at IS NULL
                    DO UPDATE SET expires_at =
                                    now() + ($6 || ' minutes')::interval,
                                  held_at = now()
                    RETURNING id, expires_at
                    """,
                    identity.clinic_id,
                    doctor_id,
                    slot_start,
                    slot_end,
                    identity.staff_id,
                    str(HOLD_MINUTES),
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="slot_hold.created",
                    aggregate_id=str(row["id"]),
                    payload={
                        "slot_start": slot_start.isoformat(),
                        "slot_end": slot_end.isoformat(),
                        "doctor_id": doctor_id,
                        "expires_at": row["expires_at"].isoformat(),
                        "released_others": released,
                        # Không lưu vào `slot_hold` — chỉ đi vào nhật ký, nơi
                        # v_audit_log đọc `payload->>'clinic_patient_id'` ĐẦU
                        # TIÊN trong chuỗi tra tên. Thiếu nó thì màn Lịch sử
                        # thao tác in "slot_hold · 938d4f94" thay cho tên khách.
                        "clinic_patient_id": clinic_patient_id,
                    },
                )

        logger.info(
            "slot_held",
            slot_start=slot_start.isoformat(),
            doctor_id=doctor_id,
            by_staff_id=identity.staff_id,
        )
        return {"id": str(row["id"]), "expires_at": row["expires_at"].isoformat()}

    async def release(
        self, *, identity: StaffIdentity, reason: str = "cancelled"
    ) -> dict[str, Any]:
        """Thả mọi chỗ người này đang giữ. Bỏ chọn, hoặc rời màn hình."""
        _assert_may_hold(identity)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                n = await self._release_mine(conn, identity=identity, reason=reason)
        return {"released": n}

    async def active(
        self, *, identity: StaffIdentity, date: str
    ) -> list[dict[str, Any]]:
        """Chỗ đang được giữ trong ngày — để lưới đặt lịch tô đúng ô.

        Bỏ chỗ do CHÍNH người đang xem giữ: hiện "đang giữ" trên ô mình vừa bấm
        là tự nói với mình rằng có người khác đang tranh chỗ đó.
        """
        try:
            day = datetime.fromisoformat(date).date()
        except ValueError as exc:
            raise ValidationError(
                f"Ngày không hợp lệ: {date!r}. Định dạng đúng là YYYY-MM-DD."
            ) from exc

        rows = await self._pool.fetch(
            """
            SELECT id, doctor_id, slot_start, slot_end, held_by, held_by_name,
                   expires_at
              FROM public.v_slot_hold_active
             WHERE clinic_id = $1::uuid
               AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $2::date
               AND held_by <> $3::uuid
             ORDER BY slot_start
            """,
            identity.clinic_id,
            day,
            identity.staff_id,
        )
        return [
            {
                "id": str(r["id"]),
                "doctor_id": str(r["doctor_id"]) if r["doctor_id"] else None,
                "slot_start": r["slot_start"].isoformat(),
                "slot_end": r["slot_end"].isoformat(),
                "held_by_name": r["held_by_name"],
                "expires_at": r["expires_at"].isoformat(),
            }
            for r in rows
        ]

    async def _release_mine(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        reason: str,
        keep: datetime | None = None,
    ) -> int:
        rows = await conn.fetch(
            """
            UPDATE public.slot_hold
               SET released_at = now(), release_reason = $3
             WHERE clinic_id = $1::uuid AND held_by = $2::uuid
               AND released_at IS NULL
               AND ($4::timestamptz IS NULL OR slot_start <> $4)
            RETURNING id, slot_start
            """,
            identity.clinic_id,
            identity.staff_id,
            reason,
            keep,
        )
        for r in rows:
            await _log(
                conn,
                identity=identity,
                event_type="slot_hold.released",
                aggregate_id=str(r["id"]),
                payload={
                    "slot_start": r["slot_start"].isoformat(),
                    "reason": reason,
                },
            )
        return len(rows)


async def release_on_booking(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    appointment_id: str,
    slot_start: datetime,
) -> None:
    """Đặt xong thì thả chỗ giữ — chạy trong CÙNG transaction với lịch hẹn.

    Quang: *"chứ không phải đã ấn đặt lịch rồi lại còn giữ 10' làm gì"*. Ghế đã
    thành lịch hẹn thật rồi; để dòng giữ chỗ sống tiếp là đếm cùng một ghế hai
    lần trên màn hình người khác.

    Cùng transaction, chứ không phải một lệnh gọi riêng sau đó: đặt lịch thành
    công mà thả chỗ thất bại sẽ để lại một chỗ "đang giữ" vĩnh viễn ở đúng khung
    vừa đặt.
    """
    rows = await conn.fetch(
        """
        UPDATE public.slot_hold
           SET released_at = now(), release_reason = 'booked',
               appointment_id = $3::uuid
         WHERE clinic_id = $1::uuid AND held_by = $2::uuid
           AND released_at IS NULL AND slot_start = $4
        RETURNING id
        """,
        identity.clinic_id,
        identity.staff_id,
        appointment_id,
        slot_start,
    )
    for r in rows:
        await _log(
            conn,
            identity=identity,
            event_type="slot_hold.released",
            aggregate_id=str(r["id"]),
            payload={
                "slot_start": slot_start.isoformat(),
                "reason": "booked",
                "appointment_id": appointment_id,
            },
        )


async def _log(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    event_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
) -> None:
    """Mọi thao tác sinh event: ai, vai gì, đường nào, lúc nào.

    Quang: *"quy tắc làm gì cũng sinh ra event có route này kia"*. `metadata`
    mang người làm và vai, `source` mang đường vào — đọc lại một sự việc là đọc
    được ai chịu trách nhiệm.
    """
    await conn.execute(
        """
        INSERT INTO public.event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, event_published)
        VALUES ($1::uuid, $2, 'slot_hold', $3, $4::jsonb, $5::jsonb,
                'api:booking', FALSE)
        """,
        identity.clinic_id,
        event_type,
        aggregate_id,
        json.dumps(payload),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "clinic_staff_id": identity.staff_id,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": "api:booking",
            }
        ),
    )


def hold_expiry(now: datetime) -> datetime:
    """Khi nào một lần giữ hết hạn. Tách ra để kiểm được mà không cần DB."""
    return now + timedelta(minutes=HOLD_MINUTES)
