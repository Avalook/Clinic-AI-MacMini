"""Report settings and roster scopes; never trust client-selected shifts."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.core.ma_vi_tri import ma_mau
from clinicai.permissions.can import can

DEFAULT_SETTINGS = {
    "nhan_vien_theo_ca": False,
    "truong_ca_theo_ngay": False,
    "tai_chinh_day_du": False,
}
SHIFTS = ("SANG", "CHIEU", "TOI", "FULL")


def doc_thiet_lap(settings: Any) -> dict[str, bool]:
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except (ValueError, TypeError):
            settings = {}
    raw = settings.get("bao_cao_theo_ca", {}) if isinstance(settings, dict) else {}
    return {
        k: raw.get(k) is True if isinstance(raw, dict) else False
        for k in DEFAULT_SETTINGS
    }


def ngay_hop_le(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value or "")
    except (ValueError, TypeError):
        return None


def pham_vi_lich(rows: list[dict[str, Any]], *, head: bool) -> dict[str, list[str]]:
    scopes: dict[str, set[str]] = {}
    for row in rows:
        if row.get("status") != "APPROVED" or row.get("shift") not in SHIFTS:
            continue
        is_head = ma_mau(str(row.get("station") or "")) == "DIEU_PHOI"
        location = row.get("location_id")
        if head and not is_head or not location:
            continue
        shift = str(row["shift"])
        allowed = SHIFTS if shift == "FULL" or head else (shift,)
        for ca in allowed:
            scopes.setdefault(ca, set()).add(str(location))
    return {ca: sorted(scopes[ca]) for ca in SHIFTS if ca in scopes}


def gioi_han_ban_hang(bc: dict[str, Any]) -> dict[str, Any]:
    """Allowlist: no customer names, outstanding money or finance breakdown."""
    keys = ("tu", "den", "loai", "ca", "co_so", "ten_co_so", "hang_hoa")
    return {k: bc[k] for k in keys if k in bc}


def gioi_han_tai_chinh_ca(bc: dict[str, Any]) -> dict[str, Any]:
    """Assigned-day finance excludes outstanding balances outside that day."""
    blocked = {"khach_con_no", "can_xu_ly", "tien_thua", "thuoc_theo_khach"}
    return {key: value for key, value in bc.items() if key not in blocked}


class ReportAccessService:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @staticmethod
    def quan_ly(identity: StaffIdentity) -> bool:
        return identity.co_vai((ClinicRole.MANAGEMENT,))

    async def settings(self, identity: StaffIdentity) -> dict[str, bool]:
        if not self.quan_ly(identity):
            raise SafetyGateError("Chỉ quản lý được thiết lập báo cáo.")
        value = await self.pool.fetchval(
            "SELECT settings FROM clinic WHERE id=$1::uuid", identity.clinic_id
        )
        return doc_thiet_lap(value)

    async def save(
        self, identity: StaffIdentity, value: dict[str, bool]
    ) -> dict[str, bool]:
        if not self.quan_ly(identity):
            raise SafetyGateError("Chỉ quản lý được thiết lập báo cáo.")
        if set(value) != set(DEFAULT_SETTINGS) or any(
            type(v) is not bool for v in value.values()
        ):
            raise ValidationError("Thiết lập báo cáo không hợp lệ.")
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                """UPDATE clinic SET settings=jsonb_set(
                        COALESCE(settings,'{}'::jsonb),
                        '{bao_cao_theo_ca}',$2::jsonb,true),updated_at=now()
                        WHERE id=$1::uuid""",
                identity.clinic_id,
                json.dumps(value),
            )
            await conn.execute(
                """INSERT INTO event_log
                    (clinic_id,event_type,aggregate_type,aggregate_id,
                     payload,metadata,source,event_published)
                VALUES ($1::uuid,'clinic_settings.report_access_updated',
                    'clinic',$1::uuid,$2::jsonb,$3::jsonb,
                    'api:report-settings',FALSE)""",
                identity.clinic_id,
                json.dumps(value),
                json.dumps(
                    {
                        "clinic_staff_id": identity.staff_id,
                        "actor_auth_user_id": identity.auth_user_id,
                        "vai_tai_khoan": identity.vai_goc.value,
                    }
                ),
            )
        return dict(value)

    async def access(self, identity: StaffIdentity, ngay: str | None) -> dict[str, Any]:
        manager = self.quan_ly(identity)
        async with self.pool.acquire() as conn:
            settings = doc_thiet_lap(
                await conn.fetchval(
                    "SELECT settings FROM clinic WHERE id=$1::uuid", identity.clinic_id
                )
            )
            legacy = await can(conn, identity, "report.view")
            day = ngay_hop_le(ngay) if ngay is not None else now_vn().date()
            rows = (
                await conn.fetch(
                    """SELECT w.shift,w.station,w.status,
                    COALESCE(r.location_id, l.id)::text location_id
                FROM work_roster w
                JOIN staff s ON s.id=w.staff_id AND s.is_active
                JOIN clinic_location l ON l.id=s.primary_location_id
                    AND l.clinic_id=w.clinic_id
                LEFT JOIN vi_tri_lam_viec v ON v.clinic_id=w.clinic_id
                    AND v.code=w.station
                LEFT JOIN clinic_room r ON r.id=v.room_id AND r.clinic_id=w.clinic_id
                WHERE w.clinic_id=$1::uuid AND w.staff_id=$2::uuid
                    AND w.work_date=$3::date AND w.status='APPROVED'""",
                    identity.clinic_id,
                    identity.staff_id,
                    day,
                )
                if day
                else []
            )
        head = pham_vi_lich([dict(r) for r in rows], head=True)
        staff = pham_vi_lich([dict(r) for r in rows], head=False)
        # Current operational head role selects the restrictive policy; it
        # never grants access to an unassigned historical day.
        is_head = identity.co_vai((ClinicRole.TRUONG_CA,)) or bool(head)
        restricted = (
            settings["truong_ca_theo_ngay"]
            if is_head
            else settings["nhan_vien_theo_ca"]
        )
        unrestricted = manager or legacy and not restricted
        scopes = (
            head
            if settings["truong_ca_theo_ngay"] and head
            else staff
            if settings["nhan_vien_theo_ca"]
            else {}
        )
        financial = unrestricted or bool(head and settings["truong_ca_theo_ngay"])
        return {
            "quan_ly": manager,
            "ban_hang": unrestricted or bool(scopes),
            "tai_chinh": financial,
            "legacy": unrestricted,
            "tai_chinh_day_du": financial and settings["tai_chinh_day_du"],
            "cac_ca": list(SHIFTS) if unrestricted else list(scopes),
            "co_so_ids": sorted(
                {loc for locations in scopes.values() for loc in locations}
            ),
            "co_so_theo_ca": scopes,
        }

    async def authorize(
        self,
        identity: StaffIdentity,
        *,
        tu: str | None,
        den: str | None,
        ca: str | None,
        co_so: str | None,
    ) -> tuple[dict[str, Any], str | None]:
        access = await self.access(identity, tu)
        if access["legacy"]:
            return access, co_so
        day = ngay_hop_le(tu)
        shift = ca if ca in SHIFTS else "FULL" if ca in (None, "") else "INVALID"
        if not day or ngay_hop_le(den) != day or shift not in access["cac_ca"]:
            raise SafetyGateError(
                "Bạn chỉ được xem báo cáo ngày và ca đã được phân công."
            )
        locations = access["co_so_theo_ca"].get(shift, [])
        selected = co_so or (locations[0] if len(locations) == 1 else None)
        if selected not in locations:
            raise SafetyGateError("Hãy chọn cơ sở được phân công trong ca này.")
        return access, selected
