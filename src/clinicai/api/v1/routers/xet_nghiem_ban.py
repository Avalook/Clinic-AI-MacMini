"""Bàn xét nghiệm đối tác — cửa của NHÂN VIÊN bàn XN (ADR-0015, chặng 2–3).

Router mỏng: mọi luật ở `services/xet_nghiem/`. Mọi cửa có `response_model`.
Mở cho mọi nhân sự nội bộ đăng nhập (mục 2.I, "mở full lego" 30/09) — vai PARTNER bị
`get_current_identity` từ chối. RIÊNG "cho lấy mẫu khi chưa thu" và gỡ nó: chỉ Quản lý.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.clock import hom_nay_vn
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.xet_nghiem import ket_qua, mau, thu_ho
from clinicai.services.xet_nghiem.doi_tac import QUYEN_QUAN_LY
from clinicai.services.xet_nghiem.lenh import chay, chay_khong_ngay
from clinicai.services.xet_nghiem.mau import doc_ngay

router = APIRouter()
_QUAN_LY = cua_quyen(QUYEN_QUAN_LY)
P = "/xet-nghiem/ban"


class TrangThaiOut(BaseModel):
    ma: str
    nhan: str
    qua_hen: bool
    so_ngay_qua_hen: int
    qua_han_lay_mau: bool
    co_ban_moi_chua_gui: bool
    da_hoan_tien: bool
    co_the_lay_mau: bool
    ly_do_khong_lay_mau: str | None


class HoanTacOut(BaseModel):
    lenh: str
    nhan: str


class NutOut(BaseModel):
    ghi_thu: bool
    huy_thu: bool
    hoan_tien: bool
    con_hoan_duoc: int
    cho_qua: bool
    lay_mau: bool
    huy_mau: bool
    tai_ket_qua: bool
    gui: bool
    thu_hoi: bool
    dong: bool
    mo_lai: bool
    hoan_tac: HoanTacOut | None


class ViecOut(BaseModel):
    order_id: str
    visit_id: str | None
    ten_dich_vu: str | None
    doi_tac_id: str
    ten_doi_tac: str
    clinic_patient_id: str | None
    ten_khach: str | None
    ma_bn: str | None
    mau_id: str | None
    ma_mau: str | None
    hen_tra_ngay: date | None
    tep_id: str | None
    ten_tep: str | None
    ma_giao_dich: str | None
    gia_goi_y: int | None
    da_thu: int | None
    tien_mat: int | None
    chuyen_khoan: int | None
    da_hoan: int | None
    tao_luc: datetime
    trang_thai: TrangThaiOut
    nut: NutOut


class BanOut(BaseModel):
    viec: list[ViecOut]


class OkOut(BaseModel):
    ok: bool = True
    id: str | None = None
    ma_mau: str | None = None
    hen_tra_ngay: date | None = None


@router.get(P, response_model=BanOut)
async def doc_ban(
    tu_ngay: str | None = Query(default=None, max_length=10),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    """Việc chỉ định từ `tu_ngay` (mặc định 30 ngày qua; ngày rác ⇒ mặc định)."""
    hom_nay = hom_nay_vn()
    tu = doc_ngay(tu_ngay) or date.fromordinal(hom_nay.toordinal() - 30)
    return {"viec": await ket_qua.ban(pool, identity, hom_nay, tu)}


class DongTienOut(BaseModel):
    id: str
    loai: str
    so_tien: int
    tien_mat: int
    chuyen_khoan: int
    hinh_thuc: str
    ma_giao_dich: str | None
    gia_goi_y: int | None
    ghi_luc: datetime
    ten: str | None
    ten_khach: str | None
    ma_bn: str | None
    nguoi: str | None


class TienOut(BaseModel):
    ngay: date
    tong: int
    tien_mat: int
    chuyen_khoan: int
    dong: list[DongTienOut]


@router.get(f"{P}/tien", response_model=TienOut)
async def tien_thu_ho(
    ngay: str | None = Query(default=None, max_length=10),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    """Tab "Tiền thu hộ": theo NGÀY GHI NHẬN / ngày hoàn (giờ VN). Rác ⇒ hôm nay."""
    d = doc_ngay(ngay) or hom_nay_vn()
    return await thu_ho.so_ngay(pool, identity.clinic_id, d)


async def _than(request: Request) -> dict[str, Any]:
    try:
        d = await request.json()
    except ValueError:
        d = None
    return d if isinstance(d, dict) else {}


def _ok(kq: object) -> dict[str, Any]:
    if isinstance(kq, dict):
        return {"ok": True, **kq}
    return {"ok": True, "id": kq if isinstance(kq, str) else None}


_NV = Depends(get_current_identity)
_QL = Depends(_QUAN_LY)
_DB = Depends(get_db_pool)


@router.post(f"{P}/ghi-thu", response_model=OkOut)
async def ghi_thu(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    return _ok(await chay_khong_ngay(p, i, thu_ho.ghi_nhan, await _than(r)))


@router.post(f"{P}/huy-thu", response_model=OkOut)
async def huy_thu(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    return _ok(await chay_khong_ngay(p, i, thu_ho.huy, await _than(r)))


@router.post(f"{P}/hoan-tien", response_model=OkOut)
async def hoan_tien(
    r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB
) -> object:
    return _ok(await chay_khong_ngay(p, i, thu_ho.hoan, await _than(r)))


@router.post(f"{P}/lay-mau", response_model=OkOut)
async def lay_mau(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    return _ok(await chay(p, i, mau.lay_mau, await _than(r)))


@router.post(f"{P}/huy-mau", response_model=OkOut)
async def huy_mau(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    return _ok(await chay_khong_ngay(p, i, mau.huy_mau, await _than(r)))


@router.post(f"{P}/sua-hen-tra", response_model=OkOut)
async def sua_hen(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    return _ok(await chay_khong_ngay(p, i, mau.sua_hen_tra, await _than(r)))


@router.post(f"{P}/cho-qua", response_model=OkOut)
async def cho_qua(r: Request, i: StaffIdentity = _QL, p: asyncpg.Pool = _DB) -> object:
    """Chỉ Quản lý (câu 2): cho lấy mẫu khi chưa ghi nhận thu, bắt lý do."""
    return _ok(await chay(p, i, mau.cho_qua, await _than(r)))


@router.post(f"{P}/go-cho-qua", response_model=OkOut)
async def go_qua(r: Request, i: StaffIdentity = _QL, p: asyncpg.Pool = _DB) -> object:
    return _ok(await chay(p, i, mau.go_cho_qua, await _than(r)))


@router.post(f"{P}/dong", response_model=OkOut)
async def dong(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    """ "Đối tác đã tự trả khách" — đóng việc, bắt lý do."""
    return _ok(await chay(p, i, mau.dong, await _than(r)))


@router.post(f"{P}/mo-lai", response_model=OkOut)
async def mo_lai(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    return _ok(await chay(p, i, mau.mo_lai, await _than(r)))


@router.post(f"{P}/gui", response_model=OkOut)
async def gui(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    """ "Đúng người, gửi" — chỉ ghi nhận đã gửi, kênh bắt buộc."""
    await ket_qua.dung_nguoi_gui(p, i, await _than(r), hom_nay_vn())
    return _ok(None)


@router.post(f"{P}/thu-hoi", response_model=OkOut)
async def thu_hoi(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    await ket_qua.thu_hoi(p, i, await _than(r), hom_nay_vn())
    return _ok(None)


@router.post(f"{P}/tai-ket-qua", response_model=OkOut, status_code=201)
async def tai_ket_qua(
    request: Request,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    """Multipart: file + order_id. Thân chảy thẳng vào kho (như CSKH tải kết quả)."""
    from clinicai.services.nhan_tep_luong import don_tep_tam, nhan_multipart

    truong, tep = await nhan_multipart(request)
    try:
        kq = await ket_qua.tai_tay(
            pool, identity, truong.get("order_id"), hom_nay_vn(), tep=tep
        )
    finally:
        await don_tep_tam(tep)
    return {"ok": True, "id": str(kq.get("id") or "") or None}
