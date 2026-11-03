"""Trợ lý AI trả lời khách — màn thử `/tro-ly-thu` (docs/KE-HOACH-TRO-LY-AI-KHACH.md).

Router mỏng: luật nằm ở `services/tro_ly_khach/`. Gác bằng quyền `ops.view`.

BẬT/TẮT: `TRO_LY_BAT=true` + `TRO_LY_MO_HINH` (danh sách "hãng:model" cách nhau
bởi dấu phẩy, model đầu là mặc định). Tắt thì `/trang-thai` vẫn trả lời (màn nói
"chưa bật"), mọi route khác 503. Màn chỉ được chọn model TRONG danh sách — không
để client đưa hãng/URL tuỳ ý cho server gọi.
"""

from __future__ import annotations

import os
from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from clinicai.adapters.mo_hinh import tao_mo_hinh
from clinicai.api.identity import StaffIdentity
from clinicai.api.rate_limit import InMemoryRateLimiter
from clinicai.core.clock import now_vn
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.ports.mo_hinh import MoHinhError
from clinicai.services.tro_ly_khach import hoi_thoai
from clinicai.services.tro_ly_khach.cong_cu import CongCuPhongKham

router = APIRouter(prefix="/tro-ly", tags=["tro-ly"])
_GUARD = cua_quyen("ops.view")
# Mỗi tin là vài lượt gọi model trả tiền.
TRO_LY_RATE_LIMIT = InMemoryRateLimiter(scope="tro-ly", limit=20, window_seconds=60)


def danh_sach_mo_hinh() -> list[str]:
    return [
        m.strip() for m in os.environ.get("TRO_LY_MO_HINH", "").split(",") if m.strip()
    ]


def da_bat() -> bool:
    return os.environ.get("TRO_LY_BAT", "").strip().lower() == "true" and bool(
        danh_sach_mo_hinh()
    )


def require_bat() -> None:
    if not da_bat():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Trợ lý AI chưa bật")


def _loi(e: hoi_thoai.TroLyError) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class TaoHoiThoai(BaseModel):
    tieu_de: str | None = Field(default=None, max_length=120)


class GuiTin(BaseModel):
    noi_dung: str = Field(min_length=1, max_length=hoi_thoai.DAI_TOI_DA)
    mo_hinh: str | None = None


class Duyet(BaseModel):
    hanh_dong: str
    noi_dung: str | None = Field(default=None, max_length=hoi_thoai.DAI_TOI_DA)


@router.get("/trang-thai")
async def trang_thai(
    _identity: Annotated[StaffIdentity, Depends(_GUARD)],
) -> dict[str, Any]:
    return {"bat": da_bat(), "mo_hinh": danh_sach_mo_hinh() if da_bat() else []}


@router.get("/hoi-thoai", dependencies=[Depends(require_bat)])
async def danh_sach_hoi_thoai(
    identity: Annotated[StaffIdentity, Depends(_GUARD)],
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[dict[str, Any]]:
    return await hoi_thoai.danh_sach(pool, clinic_id=identity.clinic_id)


@router.post("/hoi-thoai", dependencies=[Depends(require_bat)])
async def tao_hoi_thoai(
    body: TaoHoiThoai,
    identity: Annotated[StaffIdentity, Depends(_GUARD)],
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await hoi_thoai.tao(
        pool,
        clinic_id=identity.clinic_id,
        staff_id=identity.staff_id,
        tieu_de=body.tieu_de,
    )


@router.get("/hoi-thoai/{hoi_thoai_id}", dependencies=[Depends(require_bat)])
async def doc_hoi_thoai(
    hoi_thoai_id: str,
    identity: Annotated[StaffIdentity, Depends(_GUARD)],
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    ht = await hoi_thoai.doc(
        pool, clinic_id=identity.clinic_id, hoi_thoai_id=_uuid(hoi_thoai_id)
    )
    if ht is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không có hội thoại này")
    return ht


@router.post(
    "/hoi-thoai/{hoi_thoai_id}/tin",
    dependencies=[Depends(require_bat), Depends(TRO_LY_RATE_LIMIT)],
)
async def gui_tin(
    hoi_thoai_id: str,
    body: GuiTin,
    identity: Annotated[StaffIdentity, Depends(_GUARD)],
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    ds = danh_sach_mo_hinh()
    cau_hinh = body.mo_hinh or ds[0]
    if cau_hinh not in ds:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Model không có trong danh sách"
        )
    try:
        mo_hinh = tao_mo_hinh(cau_hinh, pool=pool)
    except MoHinhError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    try:
        return await hoi_thoai.gui_tin(
            pool,
            mo_hinh,
            CongCuPhongKham(
                pool,
                clinic_id=identity.clinic_id,
                location_id=identity.location_id or None,
            ),
            clinic_id=identity.clinic_id,
            hoi_thoai_id=_uuid(hoi_thoai_id),
            noi_dung=body.noi_dung,
            luc=now_vn(),
        )
    except hoi_thoai.TroLyError as e:
        raise _loi(e) from e
    finally:
        await mo_hinh.dong()


@router.post("/tin/{tin_id}/duyet", dependencies=[Depends(require_bat)])
async def duyet_nhap(
    tin_id: str,
    body: Duyet,
    identity: Annotated[StaffIdentity, Depends(_GUARD)],
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    try:
        return await hoi_thoai.duyet(
            pool,
            clinic_id=identity.clinic_id,
            tin_id=_uuid(tin_id),
            staff_id=identity.staff_id,
            hanh_dong=body.hanh_dong,
            noi_dung=body.noi_dung,
        )
    except hoi_thoai.TroLyError as e:
        raise _loi(e) from e


def _uuid(s: str) -> str:
    """Mã trên URL do client gửi — rác thì 404, không để Postgres ném 500."""
    try:
        return str(UUID(s))
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy") from e
