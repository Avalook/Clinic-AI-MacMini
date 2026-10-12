"""Navigation reflects roster scope; command authorization remains server-side.

History flags are derived navigation tags, not grantable Lego capabilities.
They deliberately stay outside QUYEN/database: roster authorization is mandatory.
"""

from datetime import datetime, time, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.core.ma_vi_tri import ma_mau
from clinicai.core.shifts import ca_tu_settings, shift_windows
from clinicai.services.cashier_scope_service import STATIONS, CashierScopeService


def scoped_navigation(
    capabilities: list[str], scopes: dict[str, dict[str, Any]]
) -> list[str]:
    cashier_caps = {
        "payment.service.collect",
        "payment.medicine.collect",
        "payment.service.history",
        "payment.medicine.history",
    }
    result = set(capabilities) - cashier_caps
    for kind, scope in scopes.items():
        prefix = "payment.service" if kind == "dich_vu" else "payment.medicine"
        if scope.get("quan_ly") or scope.get("items"):
            result.add(f"{prefix}.history")
        if scope.get("thao_tac"):
            result.add(f"{prefix}.collect")
    return sorted(result)


async def cashier_navigation(
    pool: asyncpg.Pool, identity: StaffIdentity, capabilities: list[str]
) -> list[str]:
    service = CashierScopeService(pool)
    scopes = {
        kind: await service.days(identity, kind=kind, limit=1)
        for kind in ["dich_vu", "thuoc"]
    }
    return scoped_navigation(capabilities, scopes)


def next_navigation_boundary(
    when: datetime, rows: list[dict[str, Any]], settings: Any
) -> datetime:
    # Midnight refreshes a newly scheduled day even if nobody is on duty now.
    midnight = datetime.combine(when.date(), time.min, tzinfo=when.tzinfo)
    candidates = [midnight + timedelta(days=1)]
    stations = STATIONS["dich_vu"] | STATIONS["thuoc"]
    for row in rows:
        station = ma_mau(str(row["station"]))
        if station not in stations or row["shift"] not in [
            "SANG",
            "CHIEU",
            "TOI",
            "FULL",
        ]:
            continue
        windows = shift_windows(row["shift"], 0, 24 * 60, ca_tu_settings(settings))
        candidates.extend(
            point
            for window in windows
            for minutes in window
            if (point := midnight + timedelta(minutes=minutes)) > when
        )
    return min(candidates)


async def navigation_deadline(pool: asyncpg.Pool, identity: StaffIdentity) -> str:
    when = now_vn()
    rows = await pool.fetch(
        "SELECT w.station,w.shift FROM work_roster w "
        "JOIN staff s ON s.id=w.staff_id AND s.is_active "
        "WHERE w.clinic_id=$1::uuid AND w.staff_id=$2::uuid "
        "AND w.status='APPROVED' AND w.work_date=$3::date",
        identity.clinic_id,
        identity.staff_id,
        when.date(),
    )
    settings = await pool.fetchval(
        "SELECT settings FROM clinic WHERE id=$1::uuid", identity.clinic_id
    )
    return next_navigation_boundary(
        when, [dict(row) for row in rows], settings
    ).isoformat()
