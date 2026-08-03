"""Booking override CRUD (C.4 — per-doctor / per-slot capacity overrides).

Same shape as ``clinic_settings_service.py``: thin Python over a well-
constrained schema. Every write is tenant-scoped (from ``identity.clinic_id``)
and audit-logged via ``event_log``. The DB CHECK constraints are the real
guards; Python validates early so a bad number becomes a 422 instead of an
opaque constraint error.

Override layers (resolve order):
  Tầng 3  slot_booking_override   — date range × MINUTE range × doctor
  Tầng 2  doctor_booking_override — per doctor, optionally per weekday
  Tầng 1  clinic.settings.booking — clinic default (C.3)

SQL function ``resolve_effective_cap()`` does the merge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

# Safety ceiling: overrides cannot exceed these (mirrors DB CHECK).
MAX_CAP = 100
# Max date range for slot overrides (mirrors DB CHECK).
MAX_SLOT_RANGE_DAYS = 90


# ── Cắt khoảng phút ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WindowTrim:
    """Chuyện gì xảy ra với MỘT luật cũ khi một luật mới phủ lên nó."""

    action: str  # "deleted" | "trimmed" | "split"
    keep: tuple[int, int] | None
    keep_extra: tuple[int, int] | None = None


def plan_window_trim(
    old_start: int, old_end: int, new_start: int, new_end: int
) -> WindowTrim:
    """Phần nào của luật cũ sống sót khi khung ``[new_start, new_end)`` chiếm chỗ.

    Tách khỏi phần chạy SQL vì đây là chỗ dễ sai nhất và cũng dễ kiểm nhất:
    bốn nhánh, toàn số nguyên, không cần database. Ghép chung với INSERT/UPDATE
    thì muốn thử một trường hợp biên phải dựng cả một phòng khám.

    Mọi khoảng đều NỬA MỞ ``[start, end)`` — cùng quy ước với int4range trong
    ràng buộc EXCLUDE và với ``resolve_effective_cap`` (``>= start AND < end``).
    Nhờ vậy hai khung liền kề (18:00–18:15 và 18:15–18:30) KHÔNG coi là chồng
    lấn, và luật cũ bị cắt tới đúng mốc của luật mới không để lại phút hở.
    """
    if old_start >= new_start and old_end <= new_end:
        # Nằm trọn bên trong — không còn gì để giữ.
        return WindowTrim(action="deleted", keep=None)
    if old_start < new_start and old_end > new_end:
        # Khung mới nằm giữa: cắt đôi.
        return WindowTrim(
            action="split",
            keep=(old_start, new_start),
            keep_extra=(new_end, old_end),
        )
    if old_start < new_start:
        # Thò đầu bên trái.
        return WindowTrim(action="trimmed", keep=(old_start, new_start))
    # Thò đuôi bên phải.
    return WindowTrim(action="trimmed", keep=(new_end, old_end))


# ── DTOs ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DoctorOverrideDTO:
    """One doctor_booking_override row."""

    id: str
    doctor_id: str | None
    weekday: int | None
    # Phút-trong-ngày, nửa mở [start, end). NULL/NULL = cả ngày.
    minute_start: int | None
    minute_end: int | None
    slot_minutes: int | None
    regular_cap: int | None
    walkin_cap: int | None
    effective_from: date
    effective_to: date | None
    reason: str | None
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class SlotOverrideDTO:
    """One slot_booking_override row."""

    id: str
    doctor_id: str | None
    date_start: date
    date_end: date
    # PHÚT-trong-ngày, không phải giờ. Luật phòng khám khác nhau giữa 18:00 và
    # 18:15 (BS Thành: 10 ca rồi 4 ca), nên độ mịn theo giờ không ghi lại được
    # điều khách hàng thật sự nói. Xem 20260803000009.
    minute_start: int
    minute_end: int
    regular_cap: int | None
    walkin_cap: int | None
    reason: str
    created_by: str
    created_at: datetime


# ── Service ────────────────────────────────────────────────────────────────

class BookingOverrideService:
    """CRUD for booking capacity overrides."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Doctor overrides (Tầng 2) ──────────────────────────────────────

    async def create_doctor_override(
        self,
        *,
        identity: StaffIdentity,
        doctor_id: str | None,
        weekday: int | None = None,
        minute_start: int | None = None,
        minute_end: int | None = None,
        slot_minutes: int | None = None,
        regular_cap: int | None = None,
        walkin_cap: int | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Ghi luật thường trực cho một khung giờ — LUẬT MỚI THẮNG.

        KHÔNG phải "create". Trưởng ca nói *"BS Thành, 18:00–18:15, 9 ca"* và
        điều đó phải trở thành sự thật, kể cả khi đã có luật khác phủ khung ấy.
        Bản trước chỉ INSERT, nên lần lưu thứ hai đụng ràng buộc
        ``doctor_override_no_overlap`` và trả về — qua handler toàn cục —
        *"Lịch hẹn xung đột khung giờ với appointment khác"*: một câu nói về
        LỊCH HẸN cho người đang sửa LUẬT, và không có lịch hẹn nào để đi tìm.

        Ràng buộc EXCLUDE vẫn đúng và vẫn còn: hai luật cùng phủ một khung thì
        không phải "luật nào thắng" mà là không có luật nào. Chỗ sai là bắt
        người dùng tự dọn. Ở đây luật cũ bị CẮT quanh khung mới — phần không
        chồng lấn giữ nguyên hiệu lực:

            cũ  18:00 ─────────────── 19:00   (4 ca)
            mới        18:15 ─ 18:30          (9 ca)
            ⇒   18:00 ─ 18:15 (4)  18:15 ─ 18:30 (9)  18:30 ─ 19:00 (4)

        Ba trường hợp còn lại — cũ nằm trọn trong mới, cũ thò một đầu — cũng
        cùng một phép cắt. Mọi lần cắt đều ghi vào ``event_log`` kèm id, vì đây
        là lần duy nhất một luật biến mất mà không ai bấm nút xoá.

        ``doctor_id=None`` = luật cho MỌI bác sĩ; luật riêng của một bác sĩ đè
        lên nó (thứ tự ưu tiên nằm trong ``resolve_effective_cap``).

        Returns ``{"ok": True, "id": "<uuid>", "replaced": [...]}``.
        """
        self._validate_doctor_fields(
            weekday=weekday,
            minute_start=minute_start,
            minute_end=minute_end,
            slot_minutes=slot_minutes,
            regular_cap=regular_cap,
            walkin_cap=walkin_cap,
            effective_from=effective_from,
            effective_to=effective_to,
        )

        eff_from = effective_from or date.today()

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                if doctor_id:
                    # Verify doctor belongs to this clinic.
                    exists = await conn.fetchval(
                        """
                        SELECT 1 FROM clinic_membership
                         WHERE clinic_id = $1::uuid
                           AND staff_id  = $2::uuid
                           AND is_active = true
                        """,
                        identity.clinic_id,
                        doctor_id,
                    )
                    if not exists:
                        raise ValidationError(
                            "Bác sĩ không thuộc phòng khám này hoặc đã bị vô hiệu."
                        )

                replaced = await self._clear_minute_window(
                    conn,
                    clinic_id=identity.clinic_id,
                    doctor_id=doctor_id,
                    weekday=weekday,
                    effective_from=eff_from,
                    effective_to=effective_to,
                    minute_start=minute_start,
                    minute_end=minute_end,
                )

                override_id = await conn.fetchval(
                    """
                    INSERT INTO doctor_booking_override
                        (clinic_id, doctor_id, weekday, minute_start, minute_end,
                         slot_minutes, regular_cap, walkin_cap,
                         effective_from, effective_to, created_by, reason)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11::uuid, $12)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    doctor_id,
                    weekday,
                    minute_start,
                    minute_end,
                    slot_minutes,
                    regular_cap,
                    walkin_cap,
                    eff_from,
                    effective_to,
                    identity.auth_user_id,
                    reason,
                )

                # MỘT LUẬT ĐÚNG VẪN CÓ THỂ KHÔNG CÓ TÁC DỤNG HÔM NAY.
                #
                # Tầng 3 (ngoại lệ tạm thời) đè lên tầng 2. Nên nếu còn một
                # ngoại lệ cũ phủ đúng khung vừa lưu, Trưởng ca sẽ lưu thành
                # công, quay ra lưới, và KHÔNG THẤY GÌ ĐỔI — rồi kết luận là
                # chức năng hỏng. Prod đang có đúng một dòng như thế cho BS
                # Thành (18:00–19:00, hết hạn 09/08), và nó là thứ đầu tiên sẽ
                # gây hiểu lầm sau khi phần lưu này chạy được.
                #
                # Không tự xoá nó: một ngoại lệ tạm thời có lý do bắt buộc và
                # có người chịu trách nhiệm. Chỉ nói ra.
                shadowed = await self._find_shadowing_exceptions(
                    conn,
                    clinic_id=identity.clinic_id,
                    doctor_id=doctor_id,
                    minute_start=minute_start,
                    minute_end=minute_end,
                )

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.doctor_created",
                    payload={
                        "override_id": str(override_id),
                        "doctor_id": doctor_id,
                        "weekday": weekday,
                        "minute_start": minute_start,
                        "minute_end": minute_end,
                        "slot_minutes": slot_minutes,
                        "regular_cap": regular_cap,
                        "walkin_cap": walkin_cap,
                        "effective_from": str(eff_from),
                        "effective_to": str(effective_to) if effective_to else None,
                        "reason": reason,
                        # Luật cũ nào bị cắt/xoá để chỗ cho luật này. Không có
                        # nút nào tạo ra dòng này, nên nếu không ghi ở đây thì
                        # nó biến mất không dấu vết.
                        "replaced": replaced,
                    },
                )

        logger.info(
            "doctor_override_created",
            override_id=str(override_id),
            doctor_id=doctor_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
            replaced_count=len(replaced),
            shadowed_count=len(shadowed),
        )
        return {
            "ok": True,
            "id": str(override_id),
            "replaced": replaced,
            "shadowed_by": shadowed,
        }

    async def list_doctor_overrides(
        self,
        *,
        identity: StaffIdentity,
        doctor_id: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """List doctor overrides for this clinic."""
        async with self._pool.acquire() as conn:
            if doctor_id:
                rows = await conn.fetch(
                    """
                    SELECT id, doctor_id, weekday,
                           minute_start, minute_end, slot_minutes,
                           regular_cap, walkin_cap,
                           effective_from, effective_to, reason,
                           created_by, created_at
                      FROM doctor_booking_override
                     WHERE clinic_id = $1::uuid
                       AND doctor_id = $2::uuid
                       AND ($3::boolean IS FALSE
                            OR (effective_to IS NULL OR effective_to >= current_date))
                     ORDER BY effective_from DESC
                    """,
                    identity.clinic_id,
                    doctor_id,
                    active_only,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, doctor_id, weekday,
                           minute_start, minute_end, slot_minutes,
                           regular_cap, walkin_cap,
                           effective_from, effective_to, reason,
                           created_by, created_at
                      FROM doctor_booking_override
                     WHERE clinic_id = $1::uuid
                       AND ($2::boolean IS FALSE
                            OR (effective_to IS NULL OR effective_to >= current_date))
                     ORDER BY effective_from DESC
                    """,
                    identity.clinic_id,
                    active_only,
                )

        return [_doctor_row_to_dict(r) for r in rows]

    async def delete_doctor_override(
        self,
        *,
        identity: StaffIdentity,
        override_id: str,
    ) -> None:
        """Delete a doctor override by id."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                deleted = await conn.fetchval(
                    """
                    DELETE FROM doctor_booking_override
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    RETURNING id
                    """,
                    override_id,
                    identity.clinic_id,
                )
                if deleted is None:
                    raise NotFoundError("Override không tồn tại.")

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.doctor_deleted",
                    payload={"override_id": override_id},
                )

        logger.info(
            "doctor_override_deleted",
            override_id=override_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
        )

    # ── Slot overrides (Tầng 3) ────────────────────────────────────────

    async def create_slot_override(
        self,
        *,
        identity: StaffIdentity,
        doctor_id: str | None = None,
        date_start: date,
        date_end: date,
        minute_start: int,
        minute_end: int,
        regular_cap: int | None = None,
        walkin_cap: int | None = None,
        reason: str,
    ) -> dict[str, Any]:
        """Create a per-slot booking capacity override (date × minute range)."""
        self._validate_slot_fields(
            date_start=date_start,
            date_end=date_end,
            minute_start=minute_start,
            minute_end=minute_end,
            regular_cap=regular_cap,
            walkin_cap=walkin_cap,
            reason=reason,
        )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Verify doctor if specified.
                if doctor_id:
                    exists = await conn.fetchval(
                        """
                        SELECT 1 FROM clinic_membership
                         WHERE clinic_id = $1::uuid
                           AND staff_id  = $2::uuid
                           AND is_active = true
                        """,
                        identity.clinic_id,
                        doctor_id,
                    )
                    if not exists:
                        raise ValidationError(
                            "Bác sĩ không thuộc phòng khám này hoặc đã bị vô hiệu."
                        )

                try:
                    override_id = await conn.fetchval(
                        """
                        INSERT INTO slot_booking_override
                            (clinic_id, doctor_id, date_start, date_end,
                             minute_start, minute_end, regular_cap, walkin_cap,
                             reason, created_by)
                        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9,
                                $10::uuid)
                        RETURNING id
                        """,
                        identity.clinic_id,
                        doctor_id,
                        date_start,
                        date_end,
                        minute_start,
                        minute_end,
                        regular_cap,
                        walkin_cap,
                        reason,
                        identity.auth_user_id,
                    )
                except asyncpg.ExclusionViolationError as exc:
                    # PHẢI BẮT Ở ĐÂY. main.py có handler toàn cục cho
                    # ExclusionViolationError, và nó trả về "Lịch hẹn xung đột
                    # khung giờ với appointment khác" — đúng cho ràng buộc
                    # appointment_no_doctor_overlap, hoàn toàn sai cho ràng buộc
                    # này. Trưởng ca đang sửa LUẬT sẽ nhận một câu nói về LỊCH
                    # HẸN và đi tìm một lịch hẹn không tồn tại.
                    #
                    # Đây cũng là lúc duy nhất nói được điều hữu ích: đã có một
                    # luật phủ khung này rồi, hãy sửa hoặc xoá nó — chứ không
                    # phải thêm một luật thứ hai mà database sẽ phải chọn bừa.
                    overlapping = await self._find_overlap(
                        conn,
                        clinic_id=identity.clinic_id,
                        doctor_id=doctor_id,
                        date_start=date_start,
                        date_end=date_end,
                        minute_start=minute_start,
                        minute_end=minute_end,
                    )
                    raise ValidationError(
                        "Đã có một luật khác phủ khung giờ này"
                        + (f" ({overlapping})" if overlapping else "")
                        + ". Sửa hoặc xoá luật đó trước — hai luật cho cùng một "
                        "khung thì không có cách nào biết luật nào đúng."
                    ) from exc

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.slot_created",
                    payload={
                        "override_id": str(override_id),
                        "doctor_id": doctor_id,
                        "date_start": str(date_start),
                        "date_end": str(date_end),
                        "minute_start": minute_start,
                        "minute_end": minute_end,
                        "regular_cap": regular_cap,
                        "walkin_cap": walkin_cap,
                        "reason": reason,
                    },
                )

        logger.info(
            "slot_override_created",
            override_id=str(override_id),
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
            date_range=f"{date_start}..{date_end}",
        )
        return {"ok": True, "id": str(override_id)}

    async def list_slot_overrides(
        self,
        *,
        identity: StaffIdentity,
        date_from: date | None = None,
        date_to: date | None = None,
        doctor_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List slot overrides, optionally filtered by date range and doctor."""
        query_date = date_from or date.today()
        query_end = date_to or query_date

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, doctor_id, date_start, date_end,
                       minute_start, minute_end, regular_cap, walkin_cap,
                       reason, created_by, created_at
                  FROM slot_booking_override
                 WHERE clinic_id = $1::uuid
                   AND date_end >= $2
                   AND date_start <= $3
                   AND ($4::uuid IS NULL OR doctor_id = $4::uuid
                        OR doctor_id IS NULL)
                 ORDER BY date_start, minute_start
                """,
                identity.clinic_id,
                query_date,
                query_end,
                doctor_id,
            )

        return [_slot_row_to_dict(r) for r in rows]

    async def delete_slot_override(
        self,
        *,
        identity: StaffIdentity,
        override_id: str,
    ) -> None:
        """Delete a slot override by id."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                deleted = await conn.fetchval(
                    """
                    DELETE FROM slot_booking_override
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    RETURNING id
                    """,
                    override_id,
                    identity.clinic_id,
                )
                if deleted is None:
                    raise NotFoundError("Override không tồn tại.")

                await self._log_event(
                    conn,
                    identity=identity,
                    event_type="booking_override.slot_deleted",
                    payload={"override_id": override_id},
                )

        logger.info(
            "slot_override_deleted",
            override_id=override_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
        )

    # ── Internals ──────────────────────────────────────────────────────

    @staticmethod
    async def _clear_minute_window(
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        doctor_id: str | None,
        weekday: int | None,
        effective_from: date,
        effective_to: date | None,
        minute_start: int | None,
        minute_end: int | None,
    ) -> list[dict[str, Any]]:
        """Dọn đúng khoảng phút mà luật mới sắp chiếm, giữ nguyên phần còn lại.

        Chỉ đụng những luật mà ràng buộc EXCLUDE coi là chồng lấn — cùng phòng
        khám, cùng bác sĩ (NULL = mọi bác sĩ, và NULL chỉ chồng với NULL), cùng
        thứ, khoảng NGÀY giao nhau. Luật của bác sĩ khác, thứ khác hay đợt hiệu
        lực khác không bị chạm tới.

        Cắt theo TRỤC PHÚT, không theo trục ngày. Giao diện luôn ghi luật thường
        trực từ hôm nay và không có ngày kết thúc, nên trục ngày không có gì để
        cắt; làm cả hai trục sẽ sinh ra tới chín mảnh cho một thao tác và không
        ai đọc nổi bảng luật sau đó.
        """
        # NULL = cả ngày. Quy về [0, 1440) một lần ở đây để bốn nhánh bên dưới
        # chỉ phải nghĩ về số, giống hệt cách EXCLUDE coalesce trong chỉ mục.
        new_start = 0 if minute_start is None else minute_start
        new_end = 1440 if minute_end is None else minute_end

        rows = await conn.fetch(
            """
            SELECT id, minute_start, minute_end, regular_cap, walkin_cap,
                   slot_minutes, effective_from, effective_to, reason
              FROM doctor_booking_override
             WHERE clinic_id = $1::uuid
               AND coalesce(doctor_id, '00000000-0000-0000-0000-000000000000')
                 = coalesce($2::uuid, '00000000-0000-0000-0000-000000000000')
               AND coalesce(weekday, -1) = coalesce($3::int, -1)
               AND daterange(effective_from, effective_to, '[]')
                && daterange($4::date, $5::date, '[]')
               AND int4range(coalesce(minute_start, 0), coalesce(minute_end, 1440))
                && int4range($6, $7)
             FOR UPDATE
            """,
            clinic_id,
            doctor_id,
            weekday,
            effective_from,
            effective_to,
            new_start,
            new_end,
        )

        replaced: list[dict[str, Any]] = []
        for r in rows:
            old_start = 0 if r["minute_start"] is None else r["minute_start"]
            old_end = 1440 if r["minute_end"] is None else r["minute_end"]
            plan = plan_window_trim(old_start, old_end, new_start, new_end)

            if plan.action == "deleted":
                await conn.execute(
                    "DELETE FROM doctor_booking_override WHERE id = $1", r["id"]
                )
            else:
                assert plan.keep is not None  # noqa: S101 — plan_window_trim đảm bảo
                await conn.execute(
                    "UPDATE doctor_booking_override SET minute_start = $2,"
                    " minute_end = $3 WHERE id = $1",
                    r["id"],
                    plan.keep[0],
                    plan.keep[1],
                )
            if plan.keep_extra is not None:
                # Mảnh thứ hai của một luật bị cắt đôi. Copy từ chính dòng vừa
                # thu hẹp nên mọi trường khác (số chỗ, hiệu lực, lý do, người
                # tạo) đi theo — liệt kê tay ở đây là chỗ để quên một cột.
                await conn.execute(
                    """
                    INSERT INTO doctor_booking_override
                        (clinic_id, doctor_id, weekday, minute_start, minute_end,
                         slot_minutes, regular_cap, walkin_cap,
                         effective_from, effective_to, created_by, reason)
                    SELECT clinic_id, doctor_id, weekday, $2, $3,
                           slot_minutes, regular_cap, walkin_cap,
                           effective_from, effective_to, created_by, reason
                      FROM doctor_booking_override WHERE id = $1
                    """,
                    r["id"],
                    plan.keep_extra[0],
                    plan.keep_extra[1],
                )

            replaced.append(
                {
                    "id": str(r["id"]),
                    "action": plan.action,
                    "was": [old_start, old_end],
                    "kept": [
                        list(w)
                        for w in (plan.keep, plan.keep_extra)
                        if w is not None
                    ],
                    "regular_cap": r["regular_cap"],
                    "walkin_cap": r["walkin_cap"],
                    "reason": r["reason"],
                }
            )

        return replaced

    @staticmethod
    async def _find_shadowing_exceptions(
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        doctor_id: str | None,
        minute_start: int | None,
        minute_end: int | None,
    ) -> list[dict[str, Any]]:
        """Ngoại lệ tạm thời (tầng 3) còn hiệu lực đang phủ khung này.

        Chỉ đọc, không sửa. Câu trả lời đi thẳng lên màn hình để "đã lưu" không
        bị hiểu thành "đã có tác dụng ngay".
        """
        start = 0 if minute_start is None else minute_start
        end = 1440 if minute_end is None else minute_end
        rows = await conn.fetch(
            """
            SELECT date_start, date_end, minute_start, minute_end,
                   regular_cap, walkin_cap, reason
              FROM slot_booking_override
             WHERE clinic_id = $1::uuid
               AND (doctor_id = $2::uuid OR doctor_id IS NULL)
               AND date_end >= current_date
               AND int4range(minute_start, minute_end) && int4range($3, $4)
             ORDER BY date_start, minute_start
            """,
            clinic_id,
            doctor_id,
            start,
            end,
        )
        return [
            {
                "date_start": r["date_start"].isoformat(),
                "date_end": r["date_end"].isoformat(),
                "minute_start": r["minute_start"],
                "minute_end": r["minute_end"],
                "regular_cap": r["regular_cap"],
                "walkin_cap": r["walkin_cap"],
                "reason": r["reason"],
            }
            for r in rows
        ]

    @staticmethod
    def _validate_doctor_fields(
        *,
        weekday: int | None,
        minute_start: int | None,
        minute_end: int | None,
        slot_minutes: int | None,
        regular_cap: int | None,
        walkin_cap: int | None,
        effective_from: date | None,
        effective_to: date | None,
    ) -> None:
        if weekday is not None and not 0 <= weekday <= 6:
            raise ValidationError("weekday phải từ 0 (CN) đến 6 (T7)")
        # Cùng luật với CHECK doctor_override_minute_range (20260803000011) —
        # kiểm ở đây để người dùng nhận một câu tiếng Việt thay vì tên ràng buộc.
        if (minute_start is None) != (minute_end is None):
            raise ValidationError(
                "Khung giờ phải có cả giờ bắt đầu và giờ kết thúc"
                " (để trống cả hai = áp cho cả ngày)."
            )
        if minute_start is not None and minute_end is not None:
            if not 0 <= minute_start <= 1439:
                raise ValidationError("Giờ bắt đầu không hợp lệ")
            if not 1 <= minute_end <= 1440:
                raise ValidationError("Giờ kết thúc không hợp lệ")
            if minute_end <= minute_start:
                raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu")
            if minute_start % 5 or minute_end % 5:
                raise ValidationError("Mốc giờ phải theo bội số 5 phút")
        if slot_minutes is not None:
            if not 1 <= slot_minutes <= 60:
                raise ValidationError("slot_minutes phải từ 1 đến 60")
            if 60 % slot_minutes != 0:
                raise ValidationError("slot_minutes phải chia hết 60")
        if regular_cap is not None and not 1 <= regular_cap <= MAX_CAP:
            raise ValidationError(f"regular_cap phải từ 1 đến {MAX_CAP}")
        if walkin_cap is not None and not 0 <= walkin_cap <= MAX_CAP:
            raise ValidationError(f"walkin_cap phải từ 0 đến {MAX_CAP}")
        if (
            slot_minutes is None
            and regular_cap is None
            and walkin_cap is None
        ):
            raise ValidationError(
                "Ít nhất một trường (slot_minutes, regular_cap,"
                " walkin_cap) phải có giá trị."
            )
        if effective_from and effective_to and effective_to < effective_from:
            raise ValidationError("effective_to phải sau effective_from")

    @staticmethod
    def _validate_slot_fields(
        *,
        date_start: date,
        date_end: date,
        minute_start: int,
        minute_end: int,
        regular_cap: int | None,
        walkin_cap: int | None,
        reason: str,
    ) -> None:
        if date_end < date_start:
            raise ValidationError("date_end phải sau hoặc bằng date_start")
        if (date_end - date_start).days > MAX_SLOT_RANGE_DAYS:
            raise ValidationError(
                f"Khoảng thời gian tối đa {MAX_SLOT_RANGE_DAYS} ngày"
            )
        if not 0 <= minute_start <= 1439:
            raise ValidationError("Giờ bắt đầu không hợp lệ")
        if not 1 <= minute_end <= 1440:
            raise ValidationError("Giờ kết thúc không hợp lệ")
        if minute_end <= minute_start:
            raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu")
        # Bội số 5 — mọi độ dài khung hợp lệ (chia hết 60) là bội số của 5, nên
        # một mốc lẻ chắc chắn cắt ngang một khung và để lại vùng không luật nào
        # phủ. Chặn ở đây để người dùng nhận một câu tiếng Việt, thay vì nhận
        # tên ràng buộc CHECK từ database.
        if minute_start % 5 or minute_end % 5:
            raise ValidationError("Mốc giờ phải theo bội số 5 phút")
        if regular_cap is None and walkin_cap is None:
            raise ValidationError(
                "Ít nhất một trường (regular_cap, walkin_cap) phải có giá trị."
            )
        if regular_cap is not None and not 1 <= regular_cap <= MAX_CAP:
            raise ValidationError(f"regular_cap phải từ 1 đến {MAX_CAP}")
        if walkin_cap is not None and not 0 <= walkin_cap <= MAX_CAP:
            raise ValidationError(f"walkin_cap phải từ 0 đến {MAX_CAP}")
        if not reason or not reason.strip():
            raise ValidationError("Lý do thay đổi không được để trống.")

    @staticmethod
    async def _find_overlap(
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        doctor_id: str | None,
        date_start: date,
        date_end: date,
        minute_start: int,
        minute_end: int,
    ) -> str | None:
        """Describe the rule that already covers this window, for the error text.

        The EXCLUDE constraint names itself, not the row it collided with. A
        person who has to go and fix the other rule needs to know which one it
        is; "slot_override_no_overlap" tells them nothing.
        """
        row = await conn.fetchrow(
            """
            SELECT date_start, date_end, minute_start, minute_end, reason
              FROM slot_booking_override
             WHERE clinic_id = $1::uuid
               AND coalesce(doctor_id, '00000000-0000-0000-0000-000000000000')
                 = coalesce($2::uuid, '00000000-0000-0000-0000-000000000000')
               AND daterange(date_start, date_end, '[]')
                && daterange($3::date, $4::date, '[]')
               AND int4range(minute_start, minute_end) && int4range($5, $6)
             LIMIT 1
            """,
            clinic_id,
            doctor_id,
            date_start,
            date_end,
            minute_start,
            minute_end,
        )
        if row is None:
            return None

        def hhmm(minutes: int) -> str:
            return f"{minutes // 60:02d}:{minutes % 60:02d}"

        return (
            f"{row['date_start']:%d/%m} – {row['date_end']:%d/%m}, "
            f"{hhmm(row['minute_start'])}–{hhmm(row['minute_end'])}"
            + (f", lý do: {row['reason']}" if row["reason"] else "")
        )

    @staticmethod
    async def _log_event(
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        await conn.execute(
            """
            INSERT INTO event_log
                (clinic_id, event_type, aggregate_type, aggregate_id,
                 payload, metadata, source, event_published)
            VALUES ($1::uuid, $2, 'booking_override', $3,
                    $4, $5, 'api:booking-override', FALSE)
            """,
            identity.clinic_id,
            event_type,
            payload.get("override_id", identity.clinic_id),
            json.dumps(payload),
            json.dumps(
                {
                    "clinic_role": identity.role.value,
                    "clinic_staff_id": identity.staff_id,
                    "actor_auth_user_id": identity.auth_user_id,
                    "origin": "api:booking-override",
                }
            ),
        )


# ── Row mappers ────────────────────────────────────────────────────────────


def _doctor_row_to_dict(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        # NULL = luật cho mọi bác sĩ (20260803000011) — không ép sang chuỗi
        # "None", vì giao diện phân biệt hai trường hợp này.
        "doctor_id": str(r["doctor_id"]) if r["doctor_id"] else None,
        "weekday": r["weekday"],
        "minute_start": r["minute_start"],
        "minute_end": r["minute_end"],
        "slot_minutes": r["slot_minutes"],
        "regular_cap": r["regular_cap"],
        "walkin_cap": r["walkin_cap"],
        "effective_from": r["effective_from"].isoformat(),
        "effective_to": r["effective_to"].isoformat() if r["effective_to"] else None,
        "reason": r["reason"],
        "created_by": str(r["created_by"]),
        "created_at": r["created_at"].isoformat(),
    }


def _slot_row_to_dict(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "doctor_id": str(r["doctor_id"]) if r["doctor_id"] else None,
        "date_start": r["date_start"].isoformat(),
        "date_end": r["date_end"].isoformat(),
        "minute_start": r["minute_start"],
        "minute_end": r["minute_end"],
        "regular_cap": r["regular_cap"],
        "walkin_cap": r["walkin_cap"],
        "reason": r["reason"],
        "created_by": str(r["created_by"]),
        "created_at": r["created_at"].isoformat(),
    }
