"""MANAGEMENT-only, read-only operations endpoints: service status and telemetry."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.core.telemetry import SLOW_REQUEST_MS, telemetry
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.schemas.ops import OpsStatusResponse
from clinicai.services import (
    agent_giam_sat,
    canh_gac,
    canh_gac_kho_tep,
    day_tep,
    kho_loi,
    nhat_ky_van_hanh,
    traffic_service,
)
from clinicai.services.ops_status import OpsStatusService

router = APIRouter()
# Lego 20 "Vận hành hệ thống" (25/09/2026): hỏi quyền, không hỏi vai.
_MANAGEMENT_GUARD = cua_quyen("ops.view")


@router.get("/ops/status", response_model=OpsStatusResponse)
async def get_ops_status(
    response: Response,
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> OpsStatusResponse:
    response.headers["Cache-Control"] = "private, no-store"
    return await OpsStatusService(pool).collect()


@router.get("/ops/telemetry")
async def get_telemetry(
    response: Response,
    window_s: float | None = Query(default=900, ge=0, le=86400),
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
) -> dict[str, object]:
    """Response times and recent failures, from the API process's ring buffer.

    Behind the MANAGEMENT guard like the rest of /ops. It carries no patient
    data by construction (route templates only — see core/telemetry), but it
    does describe the shape of the system, and that is not something to hand to
    every logged-in staff member.

    Defaults to the last 15 minutes: the question at a front desk is "is it slow
    right now", and an average over a whole uptime hides the answer.
    """
    response.headers["Cache-Control"] = "no-store"
    snapshot = telemetry.snapshot(window_s=window_s or None)
    snapshot["slow_threshold_ms"] = SLOW_REQUEST_MS
    return snapshot


@router.get("/ops/su-kien")
async def suc_khoe_su_kien(
    response: Response,
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Sức khoẻ đường đưa tin — bốn số, không hơn.

    Google SRE: số đo nào không có người nhìn hoặc không gắn với cảnh báo thì bỏ.
    Bốn số ở đây là bốn kiểu hỏng khác nhau, không phải bốn cách nói một chuyện:

        cho_lam   tin chưa giao được — tắc ở đâu đó
        chet      đã thử hết lượt, có người phải xử lý tay
        dang_lam  đang giao; số này treo cao nghĩa là worker chết giữa chừng
        cho_lau_giay  tin cũ nhất đã chờ bao lâu — thứ nói "có đang tắc không"

    Hai số đầu đáng bắn Telegram. Hai số sau để nhìn trên bảng.
    """
    response.headers["Cache-Control"] = "no-store"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT consumer, cho_lam, chet, dang_lam,"
            " EXTRACT(EPOCH FROM tuoi_dong_cu_nhat)::int AS cho_lau_giay"
            "  FROM v_event_delivery_suc_khoe ORDER BY consumer"
        )
        tong_su_kien = await conn.fetchval("SELECT count(*) FROM domain_event")
    ben_nhan = [dict(r) for r in rows]
    return {
        "ben_nhan": ben_nhan,
        "tong_su_kien": tong_su_kien,
        # Một cờ để Uptime Kuma hỏi mà không phải hiểu từng con số.
        "on": all(
            (b["chet"] or 0) == 0 and (b["cho_lau_giay"] or 0) < 300 for b in ben_nhan
        ),
    }


# ── Theo dõi lỗi Pha 1 (27/09/2026): kho lỗi · cảnh báo · nhật ký vận hành ──────


@router.get("/ops/loi")
async def ds_loi(
    response: Response,
    chi_mo: bool = Query(default=False),
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Các KIỂU lỗi đã gom (api / worker / web), mới nhất trước. Không dữ liệu
    khách — thông điệp đã qua bộ che (services/kho_loi.py)."""
    response.headers["Cache-Control"] = "no-store"
    return {"loi": await kho_loi.danh_sach(pool, chi_mo=chi_mo)}


class DoiTrangThaiLoi(BaseModel):
    trang_thai: str


@router.post("/ops/loi/{loi_id}/trang-thai")
async def doi_trang_thai_loi(
    loi_id: UUID,
    body: DoiTrangThaiLoi,
    identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Đánh dấu MOI → DA_BIET / DA_SUA / BO_QUA (đã sửa mà tái diễn thì tự mở lại)."""
    if body.trang_thai not in kho_loi.TRANG_THAI:
        raise ValidationError("Trạng thái lỗi không hợp lệ.")
    ok = await kho_loi.doi_trang_thai(
        pool,
        loi_id=str(loi_id),
        trang_thai=body.trang_thai,
        staff_id=identity.staff_id,
    )
    if not ok:
        raise NotFoundError("Không tìm thấy lỗi này.")
    return {"ok": True}


@router.get("/ops/canh-bao")
async def ds_canh_bao(
    response: Response,
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Cảnh báo của bộ canh gác: đang mở trước, rồi mới đóng gần đây.
    ``kho_tep``: số đo tốc độ ổ Viettel CFS mới nhất (None = chưa đo / tắt).
    ``day_tep``: tệp chờ đẩy ổ VPS → CFS / đã đẩy hôm nay / đang lỗi (01/10)."""
    response.headers["Cache-Control"] = "no-store"
    async with pool.acquire() as conn:
        so_day = await day_tep.so_lieu(conn)
    return {
        "canh_bao": await canh_gac.danh_sach(pool),
        "kho_tep": canh_gac_kho_tep.MOI_NHAT,
        "day_tep": so_day,
    }


@router.get("/ops/nhat-ky")
async def nhat_ky(
    response: Response,
    ngay: str | None = None,
    tim: str | None = None,
    identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Nhật ký vận hành một ngày: ai làm gì, lúc nào, cách bước trước bao lâu;
    chỉ số chờ theo lượt + trung vị cả ngày. Ngày rác → hôm nay."""
    response.headers["Cache-Control"] = "no-store"
    return await nhat_ky_van_hanh.doc_nhat_ky(
        pool, clinic_id=identity.clinic_id, ngay=ngay, tim=tim
    )


# ── Agent giám sát (09/10/2026, shadow) — services/agent_giam_sat.py ─────────


@router.get("/ops/agent")
async def agent_nhan_dinh(
    response: Response,
    chi_mo: bool = Query(default=False),
    identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Nhận định của agent (đang mở trước), độ đúng 14 ngày theo loại, công tắc.
    Shadow: chỉ quản lý thấy ở đây — chưa réo chuông ai."""
    response.headers["Cache-Control"] = "no-store"
    return await agent_giam_sat.danh_sach(
        pool, clinic_id=identity.clinic_id, chi_dang_mo=chi_mo
    )


class DanhGiaNhanDinh(BaseModel):
    #: None = bỏ chấm (hoàn tác).
    danh_gia: str | None = None
    ghi_chu: str | None = Field(default=None, max_length=500)


@router.post("/ops/agent/{nhan_dinh_id}/danh-gia")
async def danh_gia_nhan_dinh(
    nhan_dinh_id: UUID,
    body: DanhGiaNhanDinh,
    identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Quản lý chấm ĐÚNG / SAI / KHÔNG RÕ — số đo để quyết lên giai đoạn sau."""
    if body.danh_gia is not None and body.danh_gia not in agent_giam_sat.DANH_GIA:
        raise ValidationError("Đánh giá không hợp lệ.")
    ok = await agent_giam_sat.danh_gia(
        pool,
        clinic_id=identity.clinic_id,
        nhan_dinh_id=str(nhan_dinh_id),
        gia_tri=body.danh_gia,
        ghi_chu=body.ghi_chu,
        staff_id=identity.staff_id,
    )
    if not ok:
        raise NotFoundError("Không tìm thấy nhận định này.")
    return {"ok": True}


class CheDoAgent(BaseModel):
    loai: str = Field(max_length=60)
    che_do: str


@router.post("/ops/agent/che-do")
async def dat_che_do_agent(
    body: CheDoAgent,
    identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Bật/tắt một loại nhận định, hoặc `loai='*'` = mọi loại (công tắc khẩn).
    Có hiệu lực ở vòng kế (≤ 1 phút), không cần deploy."""
    if body.loai != "*" and body.loai not in agent_giam_sat.LOAI:
        raise ValidationError("Loại nhận định không có.")
    if body.che_do not in agent_giam_sat.CHE_DO:
        raise ValidationError("Chế độ không hợp lệ.")
    await agent_giam_sat.dat_che_do(
        pool,
        clinic_id=identity.clinic_id,
        loai=body.loai,
        che_do=body.che_do,
        staff_id=identity.staff_id,
    )
    return {"ok": True}


class LoiTrinhDuyet(BaseModel):
    vi_tri: str = Field(default="", max_length=300)
    kieu: str = Field(default="Error", max_length=100)
    thong_diep: str = Field(default="", max_length=1000)


@router.post("/loi-trinh-duyet")
async def loi_trinh_duyet(
    body: LoiTrinhDuyet,
    _identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Lỗi giao diện (trang lỗi React, lỗi server Next) gửi về kho lỗi.

    Ai đăng nhập cũng gửi được — lỗi xảy ra ở mọi vai. Thân ≤ 1KB, qua bộ che.
    """
    await kho_loi.ghi_loi_web(
        pool, vi_tri=body.vi_tri, kieu=body.kieu, thong_diep=body.thong_diep
    )
    return {"ok": True}


class TrafficLoginPayload(BaseModel):
    username: str = Field(default="admin", max_length=50)
    password: str = Field(default="", max_length=100)
    pin: str = Field(default="", max_length=100)


@router.post("/ops/traffic")
async def lay_bao_cao_traffic(
    body: TrafficLoginPayload,
    _identity: StaffIdentity = Depends(_MANAGEMENT_GUARD),
) -> dict[str, object]:
    """Báo cáo lưu lượng truy cập. Hai lớp (30/09/2026): đăng nhập ClinicAI có
    quyền Vận hành (ops.view) VÀ mật khẩu riêng đặt trong .env.prod. Trang từng mở
    cho cả Internet với admin/12345678 — IP + đường dẫn là dữ liệu cá nhân."""
    pwd = body.password or body.pin
    user = body.username or "admin"
    if not (
        traffic_service.xac_thuc_admin(user, pwd)
        or traffic_service.xac_thuc_ma_pin(pwd)
    ):
        raise ValidationError("Tài khoản hoặc mật khẩu không chính xác.")

    data = traffic_service.doc_du_lieu_traffic()
    if data is None:
        raise NotFoundError(
            "Dữ liệu lưu lượng chưa sẵn sàng. Vui lòng thử lại sau ít phút."
        )

    return {"ok": True, "data": data}
