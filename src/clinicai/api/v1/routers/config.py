"""Roster and price-list endpoints (W5, ADR-0012)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.core.shifts import (
    CAC_CA,
    NHAN_CA,
    ca_tu_settings,
    kiem_cau_hinh_ca,
    phut_tu_gio,
)
from clinicai.services.clinic_settings_service import ClinicSettingsService
from clinicai.services.config_service import (
    PRICE_ROLES,
    ROSTER_ROLES,
    PriceGroup,
    PriceListService,
    RosterDecision,
    RosterService,
    Shift,
)

router = APIRouter()

# Everyone works a shift, so everyone may sign up for one; the service decides
# who may schedule somebody else.
_ROSTER_GUARD = require_role(*ROSTER_ROLES)
_PRICE_GUARD = require_role(*PRICE_ROLES)
# Chỉ Trưởng ca + Quản lý được đổi luật đặt lịch (khung giờ / số chỗ) của
# phòng khám. Bác sĩ/CSKH/Lễ tân thấy luật nhưng không sửa được — sửa luật
# đang chạy khi đang có lịch đặt là một quyết định vận hành.
_BOOKING_POLICY_GUARD = require_role(ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT)


class ShiftRequest(BaseModel):
    work_date: date
    station: str = Field(min_length=1, max_length=64)
    shift: Shift = "FULL"
    # Ignored unless the caller is management — see the service.
    staff_id: UUID | None = None
    staff_name: str | None = Field(default=None, max_length=200)
    sort: int = 0


class RosterDecisionRequest(BaseModel):
    decision: RosterDecision
    reason: str | None = Field(default=None, max_length=500)


class PriceCreateRequest(BaseModel):
    service_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    group: PriceGroup
    unit_price: float | str | None = None


class PriceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    unit_price: float | str | None = None
    active: bool | None = None


class DisplayZoneToggle(BaseModel):
    """Một khu trên bảng gọi số: bật hay tắt."""

    key: str = Field(min_length=1, max_length=32)
    an: bool = False


class DisplaySettingsRequest(BaseModel):
    """Cấu hình MÀN HÌNH PHÒNG CHỜ của phòng khám đang đăng nhập."""

    zones: list[DisplayZoneToggle] = Field(default_factory=list)
    # Hiện TÊN người bệnh trên bảng gọi số. Bật theo yêu cầu vận hành; tắt thì
    # bảng rơi về số thứ tự.
    hien_ten: bool = True
    # Che phần giữa của tên ("Nguyễn Thị Lan" → "Nguyễn T. L.") cho phòng khám
    # muốn gọi tên mà không đọc trọn cho cả phòng chờ.
    che_ten: bool = False


class BookingPolicyUpdateRequest(BaseModel):
    """Ba con số của luật đặt lịch (C.3). CHECK constraint ở DB chặn lần cuối."""

    slot_minutes: int = Field(ge=1, le=60)
    regular_cap: int = Field(ge=1, le=100)
    walkin_cap: int = Field(ge=0, le=100)


@router.post("/roster/shifts", status_code=201)
async def add_shift(
    body: ShiftRequest,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Sign up for a shift, or — as management — schedule somebody."""
    roster_id = await RosterService(pool).add_shift(
        work_date=body.work_date,
        station=body.station,
        shift=body.shift,
        identity=identity,
        staff_id=str(body.staff_id) if body.staff_id else None,
        staff_name=body.staff_name,
        sort=body.sort,
    )
    return {"ok": True, "id": roster_id}


@router.get("/roster/stations")
async def roster_stations(
    staff_id: UUID,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Nhân viên này được xếp vào những vị trí nào.

    Cùng nguồn với chỗ thi hành trong `add_shift`, nên ô chọn trên màn không
    thể mời một vị trí rồi backend từ chối.
    """
    return await RosterService(pool).tram_cho_nhan_vien(
        identity=identity, staff_id=str(staff_id)
    )


@router.get("/roster/station-scope")
async def station_scope(
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Cả ma trận vai × vị trí — màn cấu hình của quản lý."""
    return {"items": await RosterService(pool).ma_tran_vi_tri(identity=identity)}


class StationScopeRequest(BaseModel):
    tram_ma: str = Field(min_length=1, max_length=64)
    vai: str = Field(min_length=1, max_length=32)
    cho_phep: bool


@router.put("/roster/station-scope")
async def set_station_scope(
    body: StationScopeRequest,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Bật/tắt một ô của ma trận. Chỉ Quản lý (kiểm lại trong service)."""
    return await RosterService(pool).dat_vi_tri_cho_vai(
        identity=identity,
        tram_ma=body.tram_ma,
        vai=body.vai,
        cho_phep=body.cho_phep,
    )


@router.patch("/roster/shifts/{roster_id}")
async def decide_shift(
    roster_id: UUID,
    body: RosterDecisionRequest,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Approve or reject a self-registered shift. Management only."""
    await RosterService(pool).decide(
        roster_id=str(roster_id),
        decision=body.decision,
        reason=body.reason,
        identity=identity,
    )
    return {"ok": True}


class ApplyWeekRequest(BaseModel):
    week_start: date


@router.post("/roster/weeks/apply", status_code=201)
async def apply_week(
    body: ApplyWeekRequest,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Chốt lịch trực một tuần. Chỉ Quản lý.

    Trước khi có việc này, một tuần vừa xếp nháp và một tuần đã chốt trông hệt
    nhau với mọi thứ đọc lịch trực. Xem migration 20260808000001.
    """
    return await RosterService(pool).apply_week(
        week_start=body.week_start, identity=identity
    )


@router.get("/roster/weeks/applied")
async def applied_weeks(
    tu: date,
    den: date,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Tuần nào trong khoảng đã áp dụng — phần còn lại là dự kiến."""
    return {
        "weeks": await RosterService(pool).applied_weeks(
            identity=identity, tu=tu, den=den
        )
    }


@router.delete("/roster/shifts/{roster_id}")
async def remove_shift(
    roster_id: UUID,
    dry_run: bool = False,
    identity: StaffIdentity = Depends(_ROSTER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Remove a shift. Non-managers may only remove their own.

    ``dry_run=true``: đo mà không cắt — trả số lịch hẹn SẼ bị huỷ (kèm giờ)
    để màn hình hỏi lại trước khi xoá thật. Xem RosterService.remove.
    """
    ket = await RosterService(pool).remove(
        roster_id=str(roster_id), identity=identity, dry_run=dry_run
    )
    return {"ok": True, **ket}


class PriceRow(BaseModel):
    """Một dòng bảng giá — đúng những gì hai màn giá vẽ."""

    id: UUID
    service_code: str
    name: str
    group: str
    #: Có thể NULL: 29 dịch vụ hiện chưa điền giá, và điền một con số bịa vào
    #: đó thì thu ngân sẽ thu đúng con số bịa ấy.
    unit_price: Decimal | None
    active: bool


@router.get("/service-prices", response_model=list[PriceRow])
async def list_prices(
    group: PriceGroup = Query(..., description="thuoc | dich_vu"),
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[PriceRow]:
    """Bảng giá thuốc hoặc dịch vụ.

    Ba endpoint ghi (POST/PATCH/DELETE) đã có từ trước, phần ĐỌC thì chưa —
    nên hai màn giá vẫn đọc thẳng `service_price` qua PostgREST. Đây là nửa
    còn thiếu.
    """
    rows = await PriceListService(pool).list(group=group, identity=identity)
    return [PriceRow(**r) for r in rows]


@router.post("/service-prices", status_code=201)
async def add_price(
    body: PriceCreateRequest,
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Add a line to the price list."""
    price_id = await PriceListService(pool).add(
        service_code=body.service_code,
        name=body.name,
        group=body.group,
        unit_price=body.unit_price,
        identity=identity,
    )
    return {"ok": True, "id": price_id}


@router.patch("/service-prices/{price_id}")
async def update_price(
    price_id: UUID,
    body: PriceUpdateRequest,
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Change a price, rename a line, or switch it off."""
    await PriceListService(pool).update(
        price_id=str(price_id),
        identity=identity,
        name=body.name,
        unit_price=body.unit_price,
        # Absent means "leave the price"; explicit null means "clear it".
        unit_price_provided="unit_price" in body.model_fields_set,
        active=body.active,
    )
    return {"ok": True}


@router.delete("/service-prices/{price_id}")
async def remove_price(
    price_id: UUID,
    identity: StaffIdentity = Depends(_PRICE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Remove a price-list line."""
    await PriceListService(pool).remove(price_id=str(price_id), identity=identity)
    return {"ok": True}


@router.patch("/booking-policy")
async def update_booking_policy(
    body: BookingPolicyUpdateRequest,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Thay luật đặt lịch của CHÍNH phòng khám đang đăng nhập (C.3 write path).

    Chỉ Trưởng ca + Quản lý. ``identity.clinic_id`` luôn suy từ membership —
    KHÔNG nhận clinic_id từ body, nên phòng khám A sửa không thể chạm phòng
    khám B. CHECK constraint ``clinic_booking_policy_valid`` là lưới cuối.
    """
    saved = await ClinicSettingsService(pool).update_booking_policy(
        identity=identity,
        slot_minutes=body.slot_minutes,
        regular_cap=body.regular_cap,
        walkin_cap=body.walkin_cap,
    )
    return {"ok": True, **saved}


# ── Booking capacity overrides (C.4) ──────────────────────────────────


class BookingRuleRequest(BaseModel):
    """MỘT luật số chỗ: ai — thứ mấy — khung giờ nào — mấy chỗ — tới bao giờ.

    Người dùng không chọn "tầng"; service chọn hộ theo việc có khoảng ngày hay
    không (xem ``save_rule``). Trước đây chỗ này là hai request khác nhau trên
    hai tab, và câu hỏi đầu tiên của người vận hành là *"tại sao không gộp một
    khung thiết lập chung?"* — đúng, ba tầng là cách LƯU chứ không phải cách
    NGHĨ.

    ``doctor_ids`` rỗng = mọi bác sĩ. ``weekday`` để trống = mọi thứ.
    ``date_start``/``date_end`` để trống = áp dụng mãi mãi.
    """

    doctor_ids: list[UUID] = Field(default_factory=list, max_length=50)
    weekday: int | None = Field(default=None, ge=0, le=6)
    # PHÚT-trong-ngày, không phải giờ tròn (20260803000009). Luật của phòng
    # khám khác nhau giữa 18:00 và 18:15, nên độ mịn theo giờ không ghi lại
    # được điều Trưởng ca muốn nói.
    minute_start: int = Field(ge=0, le=1439)
    minute_end: int = Field(ge=1, le=1440)
    regular_cap: int = Field(ge=1, le=100)
    walkin_cap: int = Field(ge=0, le=100)
    date_start: date | None = None
    date_end: date | None = None
    reason: str | None = Field(default=None, max_length=500)


@router.post("/booking-rules", status_code=201)
async def save_booking_rule(
    body: BookingRuleRequest,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Ghi một luật số chỗ (C.4).

    Luật mới thắng: luật cũ cùng bác sĩ + cùng thứ phủ chung khung sẽ bị cắt
    quanh nó, không phải báo lỗi bắt người dùng đi dọn trước.
    """
    from clinicai.services.booking_override_service import BookingOverrideService

    result: dict[str, object] = await BookingOverrideService(pool).save_rule(
        identity=identity,
        doctor_ids=[str(d) for d in body.doctor_ids],
        weekday=body.weekday,
        minute_start=body.minute_start,
        minute_end=body.minute_end,
        regular_cap=body.regular_cap,
        walkin_cap=body.walkin_cap,
        date_start=body.date_start,
        date_end=body.date_end,
        reason=body.reason,
    )
    return result


@router.get("/booking-rules")
async def list_booking_rules(
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Mọi luật còn hiệu lực, hai tầng gộp làm một danh sách."""
    from clinicai.services.booking_override_service import BookingOverrideService

    items = await BookingOverrideService(pool).list_rules(identity=identity)
    return {"ok": True, "items": items}


@router.delete("/booking-overrides/doctor/{override_id}")
async def delete_doctor_override(
    override_id: UUID,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Xóa override per-doctor."""
    from clinicai.services.booking_override_service import BookingOverrideService

    await BookingOverrideService(pool).delete_doctor_override(
        identity=identity, override_id=str(override_id)
    )
    return {"ok": True}


@router.delete("/booking-overrides/slot/{override_id}")
async def delete_slot_override(
    override_id: UUID,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Xóa slot override."""
    from clinicai.services.booking_override_service import BookingOverrideService

    await BookingOverrideService(pool).delete_slot_override(
        identity=identity, override_id=str(override_id)
    )
    return {"ok": True}


# ── Feature Mode (Phase 1 onboarding) ─────────────────────────────────

_FEATURE_MODE_READ = require_role(
    ClinicRole.MANAGEMENT,
    ClinicRole.TRUONG_CA,
    ClinicRole.CSKH,
    ClinicRole.RECEPTION,
    ClinicRole.DOCTOR,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.TKYK,
    ClinicRole.NURSE_ULTRASOUND,
    ClinicRole.CASHIER,
    ClinicRole.CASHIER_THUOC,
    ClinicRole.CASHIER_DV,
    ClinicRole.PHARMACIST,
)
_FEATURE_MODE_WRITE = require_role(ClinicRole.MANAGEMENT)


class FeatureModeUpdateRequest(BaseModel):
    mode: str = Field(min_length=1, max_length=20)


@router.get("/feature-mode")
async def get_feature_mode(
    identity: StaffIdentity = Depends(_FEATURE_MODE_READ),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Trả chế độ phòng khám hiện tại (CSKH_ONLY hoặc FULL_CLINIC)."""
    mode = await ClinicSettingsService(pool).get_feature_mode(
        clinic_id=identity.clinic_id,
    )
    return {"ok": True, "mode": mode}


@router.put("/feature-mode")
async def update_feature_mode(
    body: FeatureModeUpdateRequest,
    identity: StaffIdentity = Depends(_FEATURE_MODE_WRITE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Đổi chế độ phòng khám. Chỉ MANAGEMENT."""
    result = await ClinicSettingsService(pool).update_feature_mode(
        identity=identity,
        mode=body.mode,
    )
    return {"ok": True, **result}


@router.patch("/display-settings")
async def update_display_settings(
    body: DisplaySettingsRequest,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Bật/tắt từng khu trên bảng gọi số, và cách hiện tên người bệnh.

    Chỉ Trưởng ca + Quản lý (cùng gác với luật đặt lịch). `clinic_id` suy từ
    membership, KHÔNG nhận từ body — phòng khám A sửa không chạm được phòng
    khám B.

    Giữ nguyên `label` và `prefix` của từng khu: đây là công tắc bật/tắt, không
    phải chỗ đổi tên khu. Khoá nào không có trong bảng cấu hình thì bỏ qua —
    gửi một khu không tồn tại không tạo ra khu mới.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT settings -> 'display' AS display FROM clinic WHERE id = $1::uuid",
            identity.clinic_id,
        )
        hien_tai = row["display"] if row else None
        if isinstance(hien_tai, str):
            hien_tai = json.loads(hien_tai)
        hien_tai = dict(hien_tai or {})

        muon_an = {z.key: z.an for z in body.zones}
        zones = [
            {**z, "an": muon_an.get(str(z.get("key")), bool(z.get("an")))}
            for z in (hien_tai.get("zones") or [])
            if isinstance(z, dict)
        ]
        hien_tai.update(
            {"zones": zones, "hien_ten": body.hien_ten, "che_ten": body.che_ten}
        )

        await conn.execute(
            """
            UPDATE public.clinic
               SET settings = jsonb_set(
                       coalesce(settings, '{}'::jsonb),
                       '{display}',
                       $2::jsonb,
                       true
                   ),
                   updated_at = now()
             WHERE id = $1::uuid
            """,
            identity.clinic_id,
            json.dumps(hien_tai, ensure_ascii=False),
        )

    return {"ok": True, "display": hien_tai}


# ── Giờ ca làm việc ─────────────────────────────────────────────────────────
#
# Cùng gác với luật đặt lịch: người sửa được "phòng khám nhận đặt lịch theo luật
# gì" thì sửa được "một ngày chia làm mấy ca".
#
# TRƯỚC ĐÂY CHỈ ĐỔI ĐƯỢC BẰNG LỆNH SQL. Giờ ca đã ra khỏi mã nguồn từ 21/08 để
# mỗi phòng khám khai riêng, nhưng không có màn nào để khai — nghĩa là vẫn phải
# gọi người viết code, đúng thứ việc đưa cấu hình ra khỏi mã sinh ra để tránh.


class KhungCaRequest(BaseModel):
    bat_dau: str = Field(pattern=r"^\d{2}:\d{2}$")
    ket_thuc: str = Field(pattern=r"^\d{2}:\d{2}$")


class CaLamViecRequest(BaseModel):
    ca_lam_viec: dict[str, KhungCaRequest]


@router.get("/ca-lam-viec")
async def doc_ca_lam_viec(
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Giờ từng ca + giờ mở cửa từng thứ, cho màn cấu hình.

    Trả kèm giờ mở cửa vì màn hình phải nói được "ca tối tràn ra ngoài giờ đóng
    cửa thứ Bảy" ngay lúc gõ, chứ không đợi bấm Lưu mới biết.
    """
    async with pool.acquire() as conn:
        raw = await conn.fetchval(
            "SELECT settings FROM clinic WHERE id = $1::uuid", identity.clinic_id
        )
        gio_rows = await conn.fetch(
            """
            SELECT key::int AS thu, value ->> 'open' AS mo, value ->> 'close' AS dong
              FROM clinic c, jsonb_each(c.settings -> 'hours')
             WHERE c.id = $1::uuid
            """,
            identity.clinic_id,
        )
    ca = ca_tu_settings(raw)
    return {
        "ca_lam_viec": {
            ma: {
                "bat_dau": f"{ca[ma][0] // 60:02d}:{ca[ma][0] % 60:02d}",
                "ket_thuc": f"{ca[ma][1] // 60:02d}:{ca[ma][1] % 60:02d}",
                "nhan": NHAN_CA.get(ma, ma),
            }
            for ma in CAC_CA
            if ma in ca
        },
        "gio_mo_cua": {
            str(r["thu"]): {"mo": r["mo"], "dong": r["dong"]} for r in gio_rows
        },
    }


@router.patch("/ca-lam-viec")
async def sua_ca_lam_viec(
    body: CaLamViecRequest,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Đổi giờ ba ca. `clinic_id` suy từ membership, KHÔNG nhận từ body.

    GHI ĐÈ CẢ CỤM, không vá từng ca: gửi thiếu một ca rồi ghi đè từng khoá sẽ
    để lại ca cũ nằm im trong cấu hình, và bản đọc vẫn dùng nó — người sửa
    tưởng đã bỏ ca tối, hệ vẫn xếp ca tối. `kiem_cau_hinh_ca` bắt buộc đủ ba ca
    nên "ghi đè cả cụm" là an toàn.

    KHÔNG đụng tới lịch hẹn đã có. Thu ca lại thì những lịch cũ nằm ngoài ca vẫn
    còn nguyên — phạt người dùng vì dữ liệu có trước luật là cách chắc nhất để
    họ không dám sửa cấu hình nữa. Chốt đặt lịch chỉ áp cho lịch ĐẶT MỚI và
    ĐỔI GIỜ; màn Lịch hẹn vẫn hiện lịch cũ như thường.
    """
    ca: dict[str, tuple[int, int]] = {}
    xau_gio: list[str] = []
    for ma, khung in body.ca_lam_viec.items():
        if ma not in CAC_CA:
            raise ValidationError(f"Không có ca {ma!r}.")
        lo, hi = phut_tu_gio(khung.bat_dau), phut_tu_gio(khung.ket_thuc)
        if lo is None or hi is None:
            xau_gio.append(f"Ca {NHAN_CA.get(ma, ma)}: giờ không đọc được.")
            continue
        ca[ma] = (lo, hi)

    async with pool.acquire() as conn:
        gio_rows = await conn.fetch(
            """
            SELECT key::int AS thu, value ->> 'open' AS mo, value ->> 'close' AS dong
              FROM clinic c, jsonb_each(c.settings -> 'hours')
             WHERE c.id = $1::uuid
            """,
            identity.clinic_id,
        )
        loi = xau_gio + kiem_cau_hinh_ca(
            ca, {str(r["thu"]): (r["mo"], r["dong"]) for r in gio_rows}
        )
        if loi:
            # GỘP MỌI LỖI vào một câu, ngăn bằng xuống dòng: người nhập sai hai
            # ô phải thấy cả hai, chứ không phải sửa một ô rồi bấm Lưu để biết
            # ô thứ hai. Handler chung của app trả 422 kèm nguyên câu này.
            raise ValidationError("\n".join(loi))

        moi = {
            ma: {"bat_dau": khung.bat_dau, "ket_thuc": khung.ket_thuc}
            for ma, khung in body.ca_lam_viec.items()
        }
        await conn.execute(
            """
            UPDATE public.clinic
               SET settings = jsonb_set(
                       coalesce(settings, '{}'::jsonb),
                       '{ca_lam_viec}', $2::jsonb, true),
                   updated_at = now()
             WHERE id = $1::uuid
            """,
            identity.clinic_id,
            json.dumps(moi, ensure_ascii=False),
        )
    return {"ok": True, "ca_lam_viec": moi}


# ── Luật bắt buộc bác sĩ ────────────────────────────────────────────────────
#
# Cùng gác với luật số chỗ (_BOOKING_POLICY_GUARD): cả hai đều là "phòng khám
# nhận đặt lịch theo luật gì", và người sửa được cái này thì sửa được cái kia.


class LuatBacSiRequest(BaseModel):
    service_type_id: UUID
    required_staff_id: UUID
    cach_tinh: Literal["CHUA_TUNG", "DOT_MOI", "QUA_N_THANG"] = "DOT_MOI"
    so_thang: int | None = Field(default=None, ge=1, le=120)
    chan_han: bool = True
    is_active: bool = True
    ghi_chu: str | None = Field(default=None, max_length=500)


@router.get("/booking-rules/doctor")
async def list_doctor_rules(
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mọi luật bắt buộc bác sĩ của phòng khám."""
    from clinicai.services.luat_bac_si_service import LuatBacSiService

    return {"items": await LuatBacSiService(pool).danh_sach(identity=identity)}


@router.put("/booking-rules/doctor", status_code=201)
async def save_doctor_rule(
    body: LuatBacSiRequest,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đặt hoặc sửa luật của một dịch vụ. PUT vì mỗi dịch vụ chỉ có một luật."""
    from clinicai.services.luat_bac_si_service import LuatBacSiService

    return await LuatBacSiService(pool).luu(
        identity=identity,
        service_type_id=str(body.service_type_id),
        required_staff_id=str(body.required_staff_id),
        cach_tinh=body.cach_tinh,
        so_thang=body.so_thang,
        chan_han=body.chan_han,
        is_active=body.is_active,
        ghi_chu=body.ghi_chu,
    )


@router.get("/booking-rules/doctor/xem-thu")
async def preview_doctor_rule(
    service_type_id: UUID,
    cach_tinh: Literal["CHUA_TUNG", "DOT_MOI", "QUA_N_THANG"],
    so_thang: int | None = None,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Cách tính này coi bao nhiêu khách hiện có là "mới"."""
    from clinicai.services.luat_bac_si_service import LuatBacSiService

    return await LuatBacSiService(pool).xem_thu(
        identity=identity,
        service_type_id=str(service_type_id),
        cach_tinh=cach_tinh,
        so_thang=so_thang,
    )


@router.delete("/booking-rules/doctor/{luat_id}")
async def delete_doctor_rule(
    luat_id: UUID,
    identity: StaffIdentity = Depends(_BOOKING_POLICY_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gỡ hẳn một luật."""
    from clinicai.services.luat_bac_si_service import LuatBacSiService

    return await LuatBacSiService(pool).xoa(identity=identity, luat_id=str(luat_id))
