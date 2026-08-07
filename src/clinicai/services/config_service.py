"""Clinic configuration: the staff roster and the price list (W5, ADR-0012).

Ports the last two routes that built a service-role client inline:
``app/api/roster`` and ``app/api/service-price``.

ROSTER. Management schedules anybody; everyone else may only sign themselves up
and may only remove their own shift. That is enforced by ignoring the client's
``staff_id`` unless the caller is management, rather than by validating it —
there is nothing to spoof if the value is never read.

Self-registered shifts land PENDING and do not appear on the shared rota until
management approves them. Management's own entries are APPROVED immediately,
because the approval exists to stop staff writing themselves onto the schedule,
not to make managers approve themselves.

``week_start`` is computed from ``work_date`` and never taken from the client.
The form keeps the previously viewed week in state, so a client-supplied value
silently filed shifts under the wrong week.

PRICES. Cashiers, the shift lead and management maintain the list. Prices are
whole dong — no fractional currency — and a duplicate service code is a 409
rather than a second row nobody notices.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Literal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError

logger = structlog.get_logger()

ROSTER_ADMIN_ROLES: frozenset[ClinicRole] = frozenset({ClinicRole.MANAGEMENT})

# LUỒNG TỰ ĐĂNG KÝ CA ĐANG ĐÓNG (Quang, 07/08/2026): quản lý tự xếp lịch cho
# mọi người rồi bấm áp dụng; nhân viên chỉ xem. Đây là ĐÓNG chứ không phải bỏ —
# bảng đăng ký và luồng duyệt vẫn còn nguyên để mở lại khi cần đường xin đổi ca.
#
# Phải siết ở ĐÂY chứ không chỉ ẩn bảng ngoài giao diện. Ẩn nút mà để nguyên
# đường ghi thì bất kỳ ai cũng còn POST thẳng vào /api/v1/roster/shifts được, và
# ca họ ghi rơi vào PENDING — vô hình với cả người xếp lịch (lưới sửa chỉ đọc
# APPROVED) lẫn màn chính thức. Treo vĩnh viễn, không ai thấy.
ROSTER_ROLES: frozenset[ClinicRole] = ROSTER_ADMIN_ROLES
PRICE_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.CASHIER,
        ClinicRole.CASHIER_THUOC,
        ClinicRole.CASHIER_DV,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
    }
)

Shift = Literal["SANG", "CHIEU", "FULL"]
RosterDecision = Literal["approve", "reject"]
PriceGroup = Literal["thuoc", "dich_vu"]


def week_start_of(work_date: date) -> date:
    """The Monday of that date's week.

    Derived, never accepted from the client: the schedule form keeps the week
    the user was last looking at, so a posted week_start filed shifts under a
    week they were not editing.
    """
    return work_date - timedelta(days=work_date.weekday())


def parse_price(raw: Any) -> int | None:
    """A whole number of dong, or None for blank. Raises on nonsense.

    Returning None for "not set" and raising for "-5" keeps the two apart; the
    route conflated them behind a single undefined.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        raise ValidationError("Đơn giá không hợp lệ")
    try:
        number = float(raw)
    except (TypeError, ValueError):
        raise ValidationError("Đơn giá không hợp lệ") from None
    if not math.isfinite(number) or number < 0:
        raise ValidationError("Đơn giá không hợp lệ")
    return round(number)


class RosterService:
    """Sign up for shifts, approve them, remove them."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add_shift(
        self,
        *,
        work_date: date,
        station: str,
        shift: str,
        identity: StaffIdentity,
        staff_id: str | None = None,
        staff_name: str | None = None,
        sort: int = 0,
    ) -> str:
        """Add one roster cell. Returns its id."""
        station = (station or "").strip()
        if not station:
            raise ValidationError("Thiếu vị trí")

        is_admin = identity.role in ROSTER_ADMIN_ROLES
        # Only management may name somebody else. For everyone else the client's
        # value is ignored entirely rather than checked.
        assigning_other = is_admin and bool(staff_id)
        target_id = staff_id if assigning_other else identity.staff_id
        target_name = (
            (staff_name or "").strip() if assigning_other else identity.full_name
        )
        if not target_name:
            raise ValidationError("Thiếu nhân viên")

        async with self._pool.acquire() as conn:
            row_id = await conn.fetchval(
                """
                INSERT INTO work_roster (
                    clinic_id, week_start, work_date, shift, station,
                    staff_id, staff_name, sort, status
                )
                VALUES ($1::uuid, $2, $3, $4, $5, $6::uuid, $7, $8, $9)
                RETURNING id
                """,
                identity.clinic_id,
                week_start_of(work_date),
                work_date,
                shift if shift in ("SANG", "CHIEU") else "FULL",
                station,
                target_id,
                target_name,
                sort,
                "APPROVED" if is_admin else "PENDING",
            )

        logger.info(
            "roster_shift_added",
            roster_id=str(row_id),
            self_service=not assigning_other,
            by_staff_id=identity.staff_id,
        )
        return str(row_id)

    async def decide(
        self,
        *,
        roster_id: str,
        decision: RosterDecision,
        reason: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Approve or reject a self-registered shift. Management only."""
        if identity.role not in ROSTER_ADMIN_ROLES:
            raise SafetyGateError("Chỉ quản lý được duyệt ca")

        status = "APPROVED" if decision == "approve" else "REJECTED"
        # Approving clears any earlier rejection reason, in case a manager
        # changed their mind about a shift they had turned down.
        reject_reason = (reason or "").strip() or None if status == "REJECTED" else None

        async with self._pool.acquire() as conn:
            updated = await conn.fetchval(
                """
                UPDATE work_roster
                   SET status = $3, reject_reason = $4, updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                RETURNING id
                """,
                roster_id,
                identity.clinic_id,
                status,
                reject_reason,
            )
        if updated is None:
            raise NotFoundError("Không tìm thấy ca trực")

    async def remove(self, *, roster_id: str, identity: StaffIdentity) -> None:
        """Remove a shift. Non-managers may only remove their own."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT staff_id FROM work_roster "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    roster_id,
                    identity.clinic_id,
                )
                if row is None:
                    raise NotFoundError("Không tìm thấy ca trực")

                if identity.role not in ROSTER_ADMIN_ROLES and (
                    str(row["staff_id"] or "") != identity.staff_id
                ):
                    raise SafetyGateError("Chỉ được xoá ca của chính mình")

                await conn.execute(
                    "DELETE FROM work_roster "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    roster_id,
                    identity.clinic_id,
                )

    async def apply_week(
        self, *, week_start: date, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Quản lý chốt lịch trực của một tuần.

        Trước khi có việc này, "tuần đã xếp" và "tuần đã chốt" là một — nên một
        bản nháp trải sẵn từ mẫu tuần cũng khoá được ô đặt lịch và cũng sinh
        được cảnh báo "bác sĩ không trực hôm đó". Xem 20260808000001.

        Áp dụng lại một tuần đã áp dụng KHÔNG phải lỗi: quản lý sửa thêm vài ca
        rồi bấm lại là chuyện thường. Chỉ cập nhật lại dấu thời gian và người bấm.
        """
        mon = week_start_of(week_start)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                so_ca = await conn.fetchval(
                    "SELECT count(*) FROM work_roster "
                    "WHERE clinic_id = $1::uuid AND week_start = $2",
                    identity.clinic_id,
                    mon,
                )
                if not so_ca:
                    # Áp dụng một tuần trống nghĩa là tuyên bố "tuần này không
                    # ai đi làm" — và vì lịch trực là luật cao nhất, nó sẽ TỪ
                    # CHỐI mọi lượt đặt của cả tuần. Không để việc đó xảy ra do
                    # bấm nhầm.
                    raise ValidationError(
                        "Tuần này chưa xếp ca nào. Xếp lịch trước rồi mới áp dụng."
                    )

                await conn.execute(
                    """
                    INSERT INTO roster_week
                        (clinic_id, week_start, applied_by_staff_id)
                    VALUES ($1::uuid, $2, $3::uuid)
                    ON CONFLICT (clinic_id, week_start) DO UPDATE
                        SET applied_at = now(),
                            applied_by_staff_id = EXCLUDED.applied_by_staff_id
                    """,
                    identity.clinic_id,
                    mon,
                    identity.staff_id,
                )
                await conn.execute(
                    """
                    INSERT INTO event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, source, occurred_at)
                    VALUES ($1::uuid, 'roster.week_applied', 'roster_week',
                            gen_random_uuid(),
                            jsonb_build_object('week_start', $2::text,
                                               'so_ca', $3::int,
                                               'by_staff_id', $4::text),
                            'config.roster', now())
                    """,
                    identity.clinic_id,
                    mon.isoformat(),
                    so_ca,
                    identity.staff_id,
                )

        logger.info(
            "roster_week_applied",
            week_start=mon.isoformat(),
            so_ca=so_ca,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "week_start": mon.isoformat(), "so_ca": so_ca}

    async def applied_weeks(
        self, *, identity: StaffIdentity, tu: date, den: date
    ) -> list[str]:
        """Những tuần đã áp dụng trong khoảng — để giao diện biết tuần nào dự kiến."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT week_start FROM roster_week "
                " WHERE clinic_id = $1::uuid AND week_start BETWEEN $2 AND $3"
                " ORDER BY week_start",
                identity.clinic_id,
                week_start_of(tu),
                week_start_of(den),
            )
        return [r["week_start"].isoformat() for r in rows]


class PriceListService:
    """Maintain the service and medicine price list."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list(
        self, *, group: PriceGroup, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        """Bảng giá của một nhóm (thuốc hoặc dịch vụ), sắp theo mã.

        TRẢ CẢ DÒNG ĐÃ TẮT (`active = false`). Thu ngân cần thấy chúng để biết
        một mã cũ đã ngừng dùng, chứ không phải để tưởng nó chưa từng tồn tại
        rồi đi tạo lại trùng mã. Màn hình tự làm mờ dòng đã tắt.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, service_code, name, "group", unit_price, active
                  FROM service_price
                 WHERE clinic_id = $1::uuid AND "group" = $2
                 ORDER BY service_code
                 LIMIT 1000
                """,
                identity.clinic_id,
                group,
            )
            return [dict(r) for r in rows]

    async def add(
        self,
        *,
        service_code: str,
        name: str,
        group: PriceGroup,
        unit_price: Any,
        identity: StaffIdentity,
    ) -> str:
        code = (service_code or "").strip()
        label = (name or "").strip()
        if not code or not label:
            raise ValidationError("Thiếu mã hoặc tên dịch vụ")

        price = parse_price(unit_price)
        async with self._pool.acquire() as conn:
            try:
                row_id = await conn.fetchval(
                    """
                    INSERT INTO service_price
                        (clinic_id, service_code, name, "group", unit_price)
                    VALUES ($1::uuid, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    code,
                    label,
                    group,
                    price,
                )
            except asyncpg.UniqueViolationError as exc:
                raise ConflictError(f"Mã {code} đã có trong nhóm {group}.") from exc
        return str(row_id)

    async def update(
        self,
        *,
        price_id: str,
        identity: StaffIdentity,
        name: str | None = None,
        unit_price: Any = None,
        unit_price_provided: bool = False,
        active: bool | None = None,
    ) -> None:
        patch: dict[str, Any] = {}
        if name is not None and name.strip():
            patch["name"] = name.strip()
        if unit_price_provided:
            patch["unit_price"] = parse_price(unit_price)
        if active is not None:
            patch["active"] = active
        if not patch:
            raise ValidationError("Không có gì để sửa")

        columns = list(patch)
        assignments = ", ".join(f"{c} = ${i + 3}" for i, c in enumerate(columns))
        async with self._pool.acquire() as conn:
            updated = await conn.fetchval(
                f"""
                UPDATE service_price SET {assignments}, updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                RETURNING id
                """,
                price_id,
                identity.clinic_id,
                *[patch[c] for c in columns],
            )
        if updated is None:
            raise NotFoundError("Không tìm thấy dòng giá")

    async def remove(self, *, price_id: str, identity: StaffIdentity) -> None:
        async with self._pool.acquire() as conn:
            deleted = await conn.fetchval(
                "DELETE FROM service_price "
                "WHERE id = $1::uuid AND clinic_id = $2::uuid RETURNING id",
                price_id,
                identity.clinic_id,
            )
        if deleted is None:
            raise NotFoundError("Không tìm thấy dòng giá")
