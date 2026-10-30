"""Số liệu báo cáo — CHỈ QUẢN LÝ (Quang chốt 2026-08-06).

Màn /reports vốn đã chỉ mở cho MANAGEMENT trên menu, nhưng endpoint phía sau
không gác vai nào: bất kỳ ai đăng nhập cũng gọi thẳng được và lấy số liệu vận
hành của cả phòng khám. Cửa phòng có khoá, cái tủ bên trong thì không.

Chốt phải đặt ở đây chứ không ở màn hình: màn hình chỉ quyết định người ta THẤY
gì, nó không ngăn được ai gõ thẳng đường dẫn.
"""

from __future__ import annotations

from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, StrictBool

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.bao_cao_cuoi_ngay_service import (
    BaoCaoCuoiNgayService,
    csv_bao_cao,
    csv_hang_hoa,
)
from clinicai.services.excel_export import XLSX_MEDIA_TYPE
from clinicai.services.excel_report_export import (
    xlsx_bao_cao,
    xlsx_hang_hoa,
    xlsx_tom_tat,
)
from clinicai.services.report_access_service import (
    ReportAccessService,
    gioi_han_ban_hang,
    gioi_han_tai_chinh_ca,
)
from clinicai.services.reports_service import (
    ReportsService,
    toan_canh,
    tong_quan,
)

router = APIRouter()


class ReportSettingsRequest(BaseModel):
    nhan_vien_theo_ca: StrictBool
    truong_ca_theo_ngay: StrictBool
    tai_chinh_day_du: StrictBool


@router.get("/reports/settings")
async def report_settings(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, bool]:
    return await ReportAccessService(pool).settings(identity)


@router.patch("/reports/settings")
async def save_report_settings(
    body: ReportSettingsRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, bool]:
    return await ReportAccessService(pool).save(identity, body.model_dump())


@router.get("/reports/access")
async def report_access(
    ngay: str | None = Query(None, max_length=40),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await ReportAccessService(pool).access(identity, ngay)


# Lego 17 "Báo cáo" (25/09/2026): hỏi quyền, không hỏi vai.
_READ_GUARD = cua_quyen("report.view")
#: Các ô đếm tổng (không tên khách, không so người với người) — cùng tập vai
#: trang /reports đang mở (`isOpsAdmin` = quản lý + trưởng ca).
# Toàn cảnh: tab của Vận hành (/ops) và báo cáo.
_TONG_QUAN_GUARD = cua_quyen("report.view", "ops.view")

# Lọc theo cơ sở (08/10/2026 — mở cơ sở Hào Nam). Rỗng = tất cả cơ sở; mã rác
# KHÔNG 422/500 mà ra số 0 (`co_so_bao_cao.doc_co_so`), cùng lối "rác không làm
# sập báo cáo" với ngày rác ở dưới.
_CO_SO = Query(None, max_length=64, description="uuid cơ sở; rỗng = tất cả; rác = số 0")


@router.get("/reports/booking-channels")
async def booking_channels(
    days: int = Query(30, ge=1, le=365),
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lịch hẹn theo nguồn đặt — MỘT truy vấn thay cho 8 lượt đếm rời."""
    return await ReportsService(pool).booking_channels(
        identity=identity, days=days, location_id=co_so
    )


@router.get("/reports/kpi-dat-lich")
async def kpi_dat_lich(
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(_READ_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mỗi nhân viên đặt được bao nhiêu lịch — hôm nay, tuần này, tháng này.

    CHỈ QUẢN LÝ ĐỌC ĐƯỢC, cùng cửa với các số liệu báo cáo khác. Đây là bảng so
    sánh giữa người với người; mở cho chính những người bị so sánh là một quyết
    định về quản trị con người, không phải một quyết định kỹ thuật, nên nó phải
    được nói ra chứ không rơi vào mặc định.
    """
    return await ReportsService(pool).kpi_dat_lich_theo_nhan_vien(
        identity=identity, location_id=co_so
    )


@router.get("/reports/tong-quan")
async def bao_cao_tong_quan(
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(_TONG_QUAN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ô số trang /reports: hôm nay · ngày mai · theo bác sĩ · 30 ngày · 7 ngày."""
    return await tong_quan(pool, identity=identity, location_id=co_so)


@router.get("/reports/toan-canh")
async def bao_cao_toan_canh(
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(_TONG_QUAN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tab "Toàn cảnh" của /ops: nhân sự · bốn con số hôm nay · 10 sự kiện."""
    return await toan_canh(pool, identity=identity, location_id=co_so)


# ── Báo cáo cuối ngày (29/09/2026) — tài chính kiểu KiotViet, CHỈ ĐỌC ──────
# Ngày rác / rỗng → hôm nay, không 422: người xem gõ sai ngày vẫn thấy số hôm
# nay chứ không thấy trang lỗi.


@router.get("/reports/cuoi-ngay")
async def bao_cao_cuoi_ngay(
    tu: str | None = Query(
        None, max_length=40, description="YYYY-MM-DD; rác = hôm nay"
    ),
    den: str | None = Query(
        None, max_length=40, description="YYYY-MM-DD; rác = hôm nay"
    ),
    loai: str | None = Query(
        None,
        max_length=20,
        description="dich_vu | thuoc — xem riêng một loại tiền; rỗng/rác = cả hai",
    ),
    co_so: str | None = _CO_SO,
    ca: str | None = Query(
        None,
        max_length=10,
        description="SANG | CHIEU | TOI — cuối ca (một ngày); rác = cả ngày",
    ),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thu gốc · huỷ · hoàn · thực thu; theo hình thức / loại / người thu / ngày;
    thuốc kê vs thực bán theo khách. ``ca`` → chỉ khung giờ một ca (cuối ca).

    Không chọn cơ sở → thêm ``theo_co_so`` (từng cơ sở, tiền cộng lại = tổng)."""
    access, location = await ReportAccessService(pool).authorize(
        identity, tu=tu, den=den, ca=ca, co_so=co_so
    )
    bc = await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=identity,
        tu=tu,
        den=den,
        loai=loai,
        co_so=location,
        ca=None if ca == "FULL" else ca,
    )
    data = (
        (bc if access["legacy"] else gioi_han_tai_chinh_ca(bc))
        if access["tai_chinh"]
        else gioi_han_ban_hang(bc)
    )
    return {**data, "access": access}


class ChotCaRequest(BaseModel):
    ngay: str = Field(max_length=40)
    ca: str = Field(max_length=10)
    co_so: str = Field(max_length=40)
    ghi_chu: str | None = Field(default=None, max_length=500)


class MoKhoaCaRequest(BaseModel):
    id: str = Field(max_length=40)
    ly_do: str = Field(max_length=500)


class KetTienMatRequest(BaseModel):
    """Kiểu lỏng: luật (mệnh giá, số tờ, lý do) ở ``ket_tien_mat_service``."""

    hanh_dong: Literal["quy_dau", "dem_cuoi", "mo_lai"]
    ngay: str = Field(max_length=40)
    ca: str = Field(max_length=10)
    co_so: str = Field(max_length=40)
    tong: Any = None
    dem: dict[str, Any] | None = None
    ly_do: str | None = Field(default=None, max_length=500)
    ly_do_lech: str | None = Field(default=None, max_length=500)
    nguoi_nhan: str | None = Field(default=None, max_length=200)


@router.get("/reports/ket-tien-mat")
async def xem_ket_tien_mat(
    ngay: str | None = Query(None, max_length=40),
    ca: str | None = Query(None, max_length=10),
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Két tiền mặt của đúng một ca: quỹ đầu, tiền mặt trong ca, dự kiến, đếm."""
    from clinicai.services.ket_tien_mat_service import KetTienMatService

    return await KetTienMatService(pool).xem(
        identity=identity, ngay=ngay, ca=ca, co_so=co_so
    )


@router.post("/reports/ket-tien-mat")
async def ghi_ket_tien_mat(
    body: KetTienMatRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Quỹ đầu ca / kiểm kê cuối ca / mở lại (bắt lý do) — có vết."""
    from clinicai.services.ket_tien_mat_service import KetTienMatService

    svc = KetTienMatService(pool)
    if body.hanh_dong == "quy_dau":
        return await svc.quy_dau(
            identity=identity,
            ngay=body.ngay,
            ca=body.ca,
            co_so=body.co_so,
            tong=body.tong,
            dem=body.dem,
            ly_do=body.ly_do,
        )
    if body.hanh_dong == "dem_cuoi":
        return await svc.dem_cuoi(
            identity=identity,
            ngay=body.ngay,
            ca=body.ca,
            co_so=body.co_so,
            tong=body.tong,
            dem=body.dem,
            ly_do_lech=body.ly_do_lech,
            nguoi_nhan=body.nguoi_nhan,
        )
    return await svc.mo_lai(
        identity=identity,
        ngay=body.ngay,
        ca=body.ca,
        co_so=body.co_so,
        ly_do=body.ly_do,
    )


@router.get("/reports/chot-ca")
async def trang_thai_chot_ca(
    ngay: str | None = Query(None, max_length=40),
    ca: str | None = Query(None, max_length=10),
    co_so: str | None = _CO_SO,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ca (một ngày, một ca, một cơ sở) đã chốt chưa — G4c khoá sổ theo ca."""
    from clinicai.services.chot_so_ca_service import ChotSoCaService

    return await ChotSoCaService(pool).trang_thai(
        identity=identity, ngay=ngay, ca=ca, co_so=co_so
    )


@router.post("/reports/chot-ca")
async def chot_ca(
    body: ChotCaRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chốt ca: chụp lại báo cáo cuối ca; sau đó huỷ / hoàn tác của ca này tính
    vào ca đang làm. Ai xem được tài chính của ca thì chốt được (máy chủ kiểm)."""
    from clinicai.services.chot_so_ca_service import ChotSoCaService

    return await ChotSoCaService(pool).chot(
        identity=identity,
        ngay=body.ngay,
        ca=body.ca,
        co_so=body.co_so,
        ghi_chu=body.ghi_chu,
    )


@router.post("/reports/chot-ca/mo-khoa")
async def mo_khoa_ca(
    body: MoKhoaCaRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mở khoá ca đã chốt — Quản lý, bắt lý do, giữ dấu (không sửa số chụp)."""
    from clinicai.services.chot_so_ca_service import ChotSoCaService

    return await ChotSoCaService(pool).mo_khoa(
        identity=identity, chot_id=body.id, ly_do=body.ly_do
    )


@router.get("/reports/cuoi-ngay.csv")
async def bao_cao_cuoi_ngay_csv(
    tu: str | None = Query(None, max_length=40),
    den: str | None = Query(None, max_length=40),
    loai: str | None = Query(None, max_length=20),
    co_so: str | None = _CO_SO,
    ca: str | None = Query(None, max_length=10),
    mau: str | None = Query(
        None, max_length=20, description="hang_hoa = khuôn KiotViet hàng hoá"
    ),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """[Xuất Excel]: CSV UTF-8 có BOM. ``mau=hang_hoa`` → "Báo cáo cuối ngày về
    hàng hóa" (khuôn KiotViet) của loại đang xem (rỗng = thuốc)."""
    access, location = await ReportAccessService(pool).authorize(
        identity, tu=tu, den=den, ca=ca, co_so=co_so
    )
    if not access["tai_chinh"] and mau != "hang_hoa":
        raise SafetyGateError(
            "Bạn chỉ được xuất báo cáo bán hàng của ca được phân công."
        )
    bc = await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=identity,
        tu=tu,
        den=den,
        loai=loai,
        co_so=location,
        ca=None if ca == "FULL" else ca,
    )
    if not access["tai_chinh"]:
        bc = gioi_han_ban_hang(bc)
    elif not access["legacy"]:
        bc = gioi_han_tai_chinh_ca(bc)
    hang_hoa = mau == "hang_hoa"
    ten = (
        f"bao-cao-hang-hoa-{bc['tu']}_{bc['den']}.csv"
        if hang_hoa
        else f"bao-cao-cuoi-ngay-{bc['tu']}_{bc['den']}.csv"
    )
    noi_dung = csv_hang_hoa(bc, loai) if hang_hoa else csv_bao_cao(bc)
    return Response(
        content=noi_dung.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{ten}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/reports/cuoi-ngay.xlsx")
async def bao_cao_cuoi_ngay_xlsx(
    tu: str | None = Query(None, max_length=40),
    den: str | None = Query(None, max_length=40),
    loai: str | None = Query(None, max_length=20),
    co_so: str | None = _CO_SO,
    ca: str | None = Query(None, max_length=10),
    mau: str | None = Query(
        None, max_length=20, description="hang_hoa = khuôn KiotViet hàng hoá"
    ),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """Editable Excel tables with exactly the same access scope as the report."""
    access, location = await ReportAccessService(pool).authorize(
        identity, tu=tu, den=den, ca=ca, co_so=co_so
    )
    if not access["tai_chinh"] and mau != "hang_hoa":
        raise SafetyGateError(
            "Bạn chỉ được xuất báo cáo bán hàng của ca được phân công."
        )
    bc = await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=identity,
        tu=tu,
        den=den,
        loai=loai,
        co_so=location,
        ca=None if ca == "FULL" else ca,
    )
    if not access["tai_chinh"]:
        bc = gioi_han_ban_hang(bc)
    elif not access["legacy"]:
        bc = gioi_han_tai_chinh_ca(bc)
    if not access.get("tai_chinh_day_du", False):
        bc = {key: value for key, value in bc.items() if key != "tai_chinh"}
    hang_hoa = mau == "hang_hoa"
    ten = (
        f"bao-cao-hang-hoa-{bc['tu']}_{bc['den']}.xlsx"
        if hang_hoa
        else f"bao-cao-cuoi-ngay-{bc['tu']}_{bc['den']}.xlsx"
    )
    noi_dung = (
        xlsx_hang_hoa(bc, loai)
        if hang_hoa
        else xlsx_tom_tat(bc, day_du=mau == "tom_tat_day_du")
        if mau in ("tom_tat", "tom_tat_day_du")
        else xlsx_bao_cao(bc)
    )
    return Response(
        content=noi_dung,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{ten}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
