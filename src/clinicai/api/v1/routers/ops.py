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
from clinicai.services import canh_gac, canh_gac_kho_tep, kho_loi, nhat_ky_van_hanh
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
    ``kho_tep``: số đo tốc độ ổ Viettel CFS mới nhất (None = chưa đo / tắt)."""
    response.headers["Cache-Control"] = "no-store"
    return {
        "canh_bao": await canh_gac.danh_sach(pool),
        "kho_tep": canh_gac_kho_tep.MOI_NHAT,
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
