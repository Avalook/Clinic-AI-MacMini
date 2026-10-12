"""Read/export cashier scopes from approved roster; payment writes unchanged."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.ma_vi_tri import ma_mau
from clinicai.core.shifts import ca_tu_settings, shift_windows
from clinicai.permissions.can import can
from clinicai.services.report_access_service import (
    ROSTER_LOCATION_JOIN,
    SHIFTS,
    ngay_hop_le,
)

STATIONS = {
    "dich_vu": {"T1_THUNGAN", "T1_LETAN", "LE_TAN", "T2_THUNGAN", "T3_THUNGAN"},
    "thuoc": {"T2_XEPTHUOC", "T2_TAODON"},
}


@dataclass(frozen=True)
class CashierScope:
    identity: StaffIdentity
    starts: list[datetime] | None
    ends: list[datetime] | None
    actor_id: str | None = None


def visible_refunds(
    value: dict[str, Any] | None,
    starts: list[datetime] | None,
    ends: list[datetime] | None,
) -> dict[str, Any] | None:
    if value is None or starts is None or ends is None:
        return value
    return {
        **value,
        "khoan_hoan": [
            r
            for r in value.get("khoan_hoan", [])
            if isinstance(r.get("created_at"), datetime)
            and any(
                lo <= r["created_at"] < hi for lo, hi in zip(starts, ends, strict=True)
            )
        ],
    }


def scope_intervals(
    day: date, shifts: list[str], settings: Any
) -> tuple[list[datetime], list[datetime]]:
    """Cashier access follows actual working windows, including midday gaps."""
    midnight = datetime.combine(day, time.min, tzinfo=CLINIC_TZ)
    windows = sorted(
        {
            window
            for shift in shifts
            for window in shift_windows(shift, 0, 1440, ca_tu_settings(settings))
        }
    )
    return (
        [midnight + timedelta(minutes=w[0]) for w in windows],
        [midnight + timedelta(minutes=w[1]) for w in windows],
    )


def allowed_roster(rows: list[dict[str, Any]], kind: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in rows:
        station = ma_mau(str(row["station"]))
        if row["status"] != "APPROVED" or row["shift"] not in SHIFTS:
            continue
        if station not in STATIONS[kind] and station != "DIEU_PHOI":
            continue
        loc = row.get("location_id")
        if not loc:
            continue
        shifts = (
            SHIFTS
            if station == "DIEU_PHOI" or row["shift"] == "FULL"
            else [row["shift"]]
        )
        for shift in shifts:
            result.setdefault(str(loc), set()).add(shift)
    return result


_ROSTER = f"""SELECT w.work_date,w.shift,w.station,w.status,
    l.id::text location_id,
    l.name location_name
    FROM work_roster w
    JOIN staff s ON s.id=w.staff_id AND s.is_active
    LEFT JOIN vi_tri_lam_viec v ON v.clinic_id=w.clinic_id AND v.code=w.station
    LEFT JOIN clinic_room r ON r.id=v.room_id AND r.clinic_id=w.clinic_id
    {ROSTER_LOCATION_JOIN}
    WHERE w.clinic_id=$1::uuid AND w.staff_id=$2::uuid AND w.status='APPROVED'
"""


class CashierScopeService:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def receipt_exempt(self, identity: StaffIdentity) -> bool:
        if identity.co_vai([ClinicRole.MANAGEMENT]):
            return True
        if identity.vai_goc != ClinicRole.CSKH:
            return False
        async with self.pool.acquire() as conn:
            # Existing CSKH invoice-to-customer workflow is a separate grant.
            return await can(conn, identity, "crm.manage")

    async def receipt(self, identity: StaffIdentity, *, id_: str, loai: str) -> None:
        if await self.receipt_exempt(identity):
            return
        if loai == "huong_dan":
            active = await self.authorize_active(identity, kind="dich_vu")
            row = await self.pool.fetchrow(
                """SELECT 'dich_vu' AS kind,created_at AS luc,
                    co_so_cua_luot(clinic_id,visit_id)::text AS location_id
                    FROM visit WHERE clinic_id=$1::uuid AND visit_id=$2::uuid""",
                identity.clinic_id,
                id_,
            )
        elif loai == "hoan":
            row = await self.pool.fetchrow(
                """SELECT kind,created_at AS luc,
                    created_by::text AS actor_id,completed_by::text AS confirmer_id,
                    completed_at,
                    payment_cycle_id::text AS cycle_id,
                    co_so_cua_luot(clinic_id,visit_id)::text AS location_id
                    FROM payment_refund
                    WHERE clinic_id=$1::uuid AND refund_id=$2::uuid""",
                identity.clinic_id,
                id_,
            )
        else:
            row = await self.pool.fetchrow(
                """SELECT kind,coalesce(paid_at,created_at) AS luc,
                    created_by::text AS actor_id,confirmed_by::text AS confirmer_id,
                    created_at,
                    co_so_cua_luot(clinic_id,visit_id)::text AS location_id
                    FROM payment_cycle
                    WHERE clinic_id=$1::uuid AND payment_cycle_id=$2::uuid""",
                identity.clinic_id,
                id_,
            )
        if not row or not row["location_id"]:
            raise SafetyGateError("Phiếu không thuộc phạm vi ca trực của bạn.")
        if loai == "huong_dan":
            if row["location_id"] != active.identity.location_id:
                raise SafetyGateError("Lượt không thuộc cơ sở đang trực.")
            return
        if loai == "hoan" and row["confirmer_id"] == identity.staff_id:
            row = {**dict(row), "luc": row["completed_at"] or row["luc"]}
        if (
            loai == "hoan"
            and row["cycle_id"]
            and identity.staff_id not in [row["actor_id"], row["confirmer_id"]]
        ):
            parent = await self.pool.fetchrow(
                "SELECT created_by::text AS actor_id, "
                "confirmed_by::text AS confirmer_id, "
                "coalesce(paid_at,created_at) AS luc, created_at "
                "FROM payment_cycle WHERE clinic_id=$1::uuid "
                "AND payment_cycle_id=$2::uuid",
                identity.clinic_id,
                row["cycle_id"],
            )
            if parent and identity.staff_id in [
                parent["actor_id"],
                parent["confirmer_id"],
            ]:
                row = {
                    **dict(row),
                    "actor_id": parent["actor_id"],
                    "confirmer_id": parent["confirmer_id"],
                    "luc": (
                        parent["created_at"]
                        if parent["actor_id"] == identity.staff_id
                        else parent["luc"]
                    ),
                }
        if loai == "thu" and row["actor_id"] == identity.staff_id:
            row = {**dict(row), "luc": row["created_at"]}
        when = row["luc"].astimezone(CLINIC_TZ)
        scope = await self.authorize(
            identity,
            tu=when.date().isoformat(),
            den=when.date().isoformat(),
            kind=row["kind"],
            ca=None,
            co_so=row["location_id"],
        )
        if scope.actor_id and scope.actor_id not in [
            row.get("actor_id"),
            row.get("confirmer_id"),
        ]:
            raise SafetyGateError("Phiếu không thuộc giao dịch của bạn.")
        if (
            scope.starts is not None
            and scope.ends is not None
            and not any(
                lo <= when < hi for lo, hi in zip(scope.starts, scope.ends, strict=True)
            )
        ):
            raise SafetyGateError("Phiếu không thuộc phạm vi ca trực của bạn.")

    async def days(
        self,
        identity: StaffIdentity,
        *,
        kind: str,
        cursor: str | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        if kind not in STATIONS:
            raise SafetyGateError("Hãy chọn đúng quầy dịch vụ hoặc thuốc.")
        manager = identity.co_vai([ClinicRole.MANAGEMENT])
        if manager:
            return {
                "quan_ly": True,
                "items": [],
                "next_cursor": None,
                "thao_tac": True,
                "dang_truc": [],
            }
        before = ngay_hop_le(cursor)
        if cursor and before is None:
            raise SafetyGateError("Mốc ngày không hợp lệ.")
        # Fetch DISTINCT dates first: number of positions cannot truncate a day.
        settings = await self.pool.fetchval(
            "SELECT settings FROM clinic WHERE id=$1::uuid", identity.clinic_id
        )
        dates = await self.pool.fetch(
            "SELECT DISTINCT work_date FROM work_roster "
            "WHERE clinic_id=$1::uuid AND staff_id=$2::uuid "
            "AND status='APPROVED' AND work_date <= $4::date "
            "AND ($3::date IS NULL OR work_date<$3) "
            "ORDER BY work_date DESC",
            identity.clinic_id,
            identity.staff_id,
            before,
            now_vn().date(),
        )
        items: list[dict[str, Any]] = []
        for d in dates:
            rows = await self.pool.fetch(
                _ROSTER + " AND w.work_date=$3::date",
                identity.clinic_id,
                identity.staff_id,
                d["work_date"],
            )
            scopes = allowed_roster([dict(r) for r in rows], kind)
            head_locations = {
                str(r["location_id"])
                for r in rows
                if ma_mau(str(r["station"])) == "DIEU_PHOI"
            }
            if d["work_date"] == now_vn().date():
                scopes = {
                    loc: {
                        shift
                        for shift in shifts
                        if loc in head_locations
                        or (
                            scope_intervals(d["work_date"], [shift], settings)[0]
                            and scope_intervals(d["work_date"], [shift], settings)[0][0]
                            <= now_vn()
                        )
                    }
                    for loc, shifts in scopes.items()
                }
                scopes = {loc: shifts for loc, shifts in scopes.items() if shifts}
            if not scopes:
                continue
            items.append(
                {
                    "ngay": d["work_date"].isoformat(),
                    "cac_ca": [
                        ca for ca in SHIFTS if any(ca in x for x in scopes.values())
                    ],
                    "co_so_ids": sorted(scopes),
                    "co_so_theo_ca": {
                        ca: sorted(
                            loc for loc, shifts in scopes.items() if ca in shifts
                        )
                        for ca in SHIFTS
                        if any(ca in shifts for shifts in scopes.values())
                    },
                    "co_so": [
                        {
                            "id": loc,
                            "ten": next(
                                str(r["location_name"])
                                for r in rows
                                if r["location_id"] == loc
                            ),
                        }
                        for loc in sorted(scopes)
                    ],
                }
            )
            if len(items) > limit:
                break
        active_rows = await self.pool.fetch(
            _ROSTER + " AND w.work_date=$3::date",
            identity.clinic_id,
            identity.staff_id,
            now_vn().date(),
        )
        active_scopes = allowed_roster([dict(r) for r in active_rows], kind)
        settings = await self.pool.fetchval(
            "SELECT settings FROM clinic WHERE id=$1::uuid", identity.clinic_id
        )
        when = now_vn()
        active = []
        active_heads = {
            str(r["location_id"])
            for r in active_rows
            if ma_mau(str(r["station"])) == "DIEU_PHOI"
        }
        for loc, shifts in active_scopes.items():
            if loc in active_heads:
                active.append({"ca": "FULL", "co_so_id": loc})
                continue
            for shift in SHIFTS:
                if shift not in shifts:
                    continue
                starts, ends = scope_intervals(when.date(), [shift], settings)
                if any(lo <= when < hi for lo, hi in zip(starts, ends, strict=True)):
                    active.append({"ca": shift, "co_so_id": loc})
        return {
            "thao_tac": bool(active),
            "dang_truc": active,
            "quan_ly": False,
            "items": items[:limit],
            "next_cursor": items[limit - 1]["ngay"] if len(items) > limit else None,
        }

    async def authorize(
        self,
        identity: StaffIdentity,
        *,
        tu: str | None,
        den: str | None,
        kind: str,
        ca: str | None,
        co_so: str | None,
    ) -> CashierScope:
        if identity.co_vai([ClinicRole.MANAGEMENT]):
            return CashierScope(identity, None, None)
        day = ngay_hop_le(tu) if tu is not None else now_vn().date()
        end_day = ngay_hop_le(den) if den is not None else day
        if (
            day is None
            or day != end_day
            or day > now_vn().date()
            or kind not in STATIONS
            or ca not in (*SHIFTS, None, "")
        ):
            raise SafetyGateError("Chỉ xem một ngày và ca trực được phân công.")
        rows = await self.pool.fetch(
            _ROSTER + " AND w.work_date=$3::date",
            identity.clinic_id,
            identity.staff_id,
            day,
        )
        scopes = allowed_roster([dict(r) for r in rows], kind)
        location = co_so or identity.location_id
        shifts = scopes.get(location, set())
        selected = [ca] if ca else [s for s in SHIFTS if s in shifts]
        if not selected or any(s not in shifts for s in selected):
            raise SafetyGateError("Bạn không được phân công ở quầy, cơ sở và ca này.")
        settings = await self.pool.fetchval(
            "SELECT settings FROM clinic WHERE id=$1::uuid", identity.clinic_id
        )
        head = any(
            ma_mau(str(r["station"])) == "DIEU_PHOI"
            and str(r["location_id"]) == location
            for r in rows
        )
        if head:
            midnight = datetime.combine(day, time.min, tzinfo=CLINIC_TZ)
            return CashierScope(
                replace(identity, location_id=location),
                [midnight],
                [midnight + timedelta(days=1)],
                None,
            )
        starts, ends = scope_intervals(day, selected, settings)
        if not starts:
            raise SafetyGateError("Ca trực chưa có khung giờ hợp lệ.")
        if day == now_vn().date():
            if ca and any(start > now_vn() for start in starts):
                raise SafetyGateError("Ca trực này chưa bắt đầu.")
            intervals = [
                (lo, hi) for lo, hi in zip(starts, ends, strict=True) if lo <= now_vn()
            ]
            starts = [lo for lo, _ in intervals]
            ends = [hi for _, hi in intervals]
            if not starts:
                raise SafetyGateError("Ca trực này chưa bắt đầu.")
        head = any(
            ma_mau(str(r["station"])) == "DIEU_PHOI"
            and str(r["location_id"]) == location
            for r in rows
        )
        return CashierScope(
            replace(identity, location_id=location),
            starts,
            ends,
            None if head else identity.staff_id,
        )

    async def authorize_active(
        self,
        identity: StaffIdentity,
        *,
        kind: str,
        co_so: str | None = None,
    ) -> CashierScope:
        """Use a counter now; history selection cannot grant write permission."""
        scope = await self.authorize(
            identity,
            tu=None,
            den=None,
            kind=kind,
            ca=None,
            co_so=co_so,
        )
        when = now_vn()
        if (
            scope.starts is not None
            and scope.ends is not None
            and not any(
                lo <= when < hi for lo, hi in zip(scope.starts, scope.ends, strict=True)
            )
        ):
            raise SafetyGateError("Bạn không đang trực quầy này.")
        return scope

    async def authorize_any_active(self, identity: StaffIdentity) -> CashierScope:
        for kind in STATIONS:
            try:
                return await self.authorize_active(identity, kind=kind)
            except SafetyGateError:
                continue
        raise SafetyGateError("Bạn không đang trực quầy thu tiền.")

    async def active_visit(
        self, identity: StaffIdentity, *, visit_id: str
    ) -> StaffIdentity:
        if identity.co_vai([ClinicRole.MANAGEMENT]):
            return identity
        location = await self.pool.fetchval(
            "SELECT co_so_cua_luot(clinic_id,visit_id)::text FROM visit "
            "WHERE clinic_id=$1::uuid AND visit_id=$2::uuid",
            identity.clinic_id,
            visit_id,
        )
        if not location:
            raise SafetyGateError("Lượt không thuộc cơ sở đang trực.")
        for kind in STATIONS:
            try:
                return (
                    await self.authorize_active(
                        identity,
                        kind=kind,
                        co_so=location,
                    )
                ).identity
            except SafetyGateError:
                continue
        raise SafetyGateError("Bạn không đang trực quầy của lượt này.")
