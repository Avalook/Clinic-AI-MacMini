"""Bàn xét nghiệm đối tác — cửa của NHÂN VIÊN bàn XN (ADR-0015, chặng 2–3).

Router mỏng: mọi luật ở `services/xet_nghiem/`. Mọi cửa có `response_model`.
Mở cho mọi nhân sự nội bộ đăng nhập (mục 2.I, "mở full lego" 30/09) — vai PARTNER bị
`get_current_identity` từ chối. RIÊNG tab Tiền thu hộ: chỉ Quản lý.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.clock import hom_nay_vn
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.xet_nghiem import anh_ck, ket_qua, mau, qua_trinh, thu_ho
from clinicai.services.xet_nghiem.doi_tac import QUYEN_QUAN_LY
from clinicai.services.xet_nghiem.lenh import chay, chay_khong_ngay
from clinicai.services.xet_nghiem.mau import doc_ngay
from clinicai.services.xet_nghiem.thu_ho import doc_doi_tac

router = APIRouter()
_QUAN_LY = cua_quyen(QUYEN_QUAN_LY)
P = "/xet-nghiem/ban"


#: Khoá màu chip — khớp `ChipTone` của `components/ui/Chip.tsx`.
MauChip = Literal["info", "neutral", "success", "brand", "warning", "danger"]


class TrangThaiOut(BaseModel):
    ma: str
    nhan: str
    qua_hen: bool
    so_ngay_qua_hen: int
    muc_qua_hen: str | None
    qua_han_lay_mau: bool
    co_ban_moi_chua_gui: bool
    da_hoan_tien: bool
    co_the_lay_mau: bool
    ly_do_khong_lay_mau: str | None
    mau: MauChip
    con_ton: bool
    vi_sao: str
    chip_nhan: str
    chip_mau: MauChip
    mau_qua_hen: MauChip | None


class AnhCkOut(BaseModel):
    id: str
    luc: datetime
    boi: str | None


class MocOut(BaseModel):
    ten: str
    luc: datetime | None
    trang_thai: Literal["done", "current", "upcoming"]


class HoanTacOut(BaseModel):
    lenh: str
    nhan: str


class NutOut(BaseModel):
    ghi_thu: bool
    huy_thu: bool
    hoan_tien: bool
    con_hoan_duoc: int
    lay_mau: bool
    hien_lay_mau: bool
    huy_mau: bool
    tai_ket_qua: bool
    gui: bool
    thu_hoi: bool
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
    #: Loại + mime tờ kết quả mới nhất — hộp xem (Lightbox) chọn cách vẽ ảnh/PDF.
    loai_tep: str | None
    mime_tep: str | None
    ma_giao_dich: str | None
    gia_goi_y: int | None
    da_thu: int | None
    tien_mat: int | None
    chuyen_khoan: int | None
    da_hoan: int | None
    thu_id: str | None
    sdt: str | None
    so_tiep_don: int | None
    so_booking: int | None
    tai_khoan_nhan_ck: str | None
    nguon_tep: str | None
    #: Số tờ kết quả còn hiệu lực của việc (1 = bản đầu; > 1 ⇒ màn ghi "Bản n").
    so_ban: int
    anh_ck: list[AnhCkOut]
    tao_luc: datetime
    ngay_chi_dinh: date
    tep_luc: datetime | None
    so_ngay_cho: int
    hanh_trinh: list[MocOut]
    buoc_dang: Literal["thu", "mau", "ket_qua"] | None
    trang_thai: TrangThaiOut
    nut: NutOut


class KhachOut(BaseModel):
    khoa: str
    ngay: date
    ten: str
    ma_bn: str | None
    sdt: str | None
    so_tiep_don: int | None
    so_booking: int | None
    order_ids: list[str]
    nhan: str
    mau: MauChip


class LocOut(BaseModel):
    ma: str
    nhan: str
    ton: bool


class DoiTacLocOut(BaseModel):
    id: str
    ten: str


class BanOut(BaseModel):
    viec: list[ViecOut]
    khach: list[KhachOut]
    loc: list[LocOut]
    quan_ly: bool
    #: Ô lọc đối tác: mọi đối tác còn hoạt động + đối tác ngưng còn việc trên bàn.
    doi_tac: list[DoiTacLocOut]
    #: Công tắc "Hiện mã ống" (Cài đặt). Tắt ⇒ mọi `ma_mau` của bàn là null.
    hien_ma_ong: bool


class QuaTrinhDongOut(BaseModel):
    luc: datetime
    viec: str
    ai: str | None


class QuaTrinhOut(BaseModel):
    dong: list[QuaTrinhDongOut]


class OkOut(BaseModel):
    ok: bool = True
    id: str | None = None
    ma_mau: str | None = None
    hen_tra_ngay: date | None = None


@router.get(P, response_model=BanOut)
async def doc_ban(
    tu_ngay: str | None = Query(default=None, max_length=10),
    ngay: str | None = Query(default=None, max_length=10),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    """Việc chỉ định từ `tu_ngay` (mặc định 30 ngày qua; ngày rác ⇒ mặc định), cộng
    đúng ngày `ngay` màn đang xem (ngày cũ hơn cửa sổ vẫn đủ việc; rác ⇒ bỏ qua)."""
    hom_nay = hom_nay_vn()
    tu = doc_ngay(tu_ngay) or date.fromordinal(hom_nay.toordinal() - 30)
    return await ket_qua.ban(pool, identity, hom_nay, tu, ngay_xem=doc_ngay(ngay))


@router.get(f"{P}/qua-trinh", response_model=QuaTrinhOut)
async def qua_trinh_viec(
    order_id: str = Query(default="", max_length=64),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    """Xem quá trình của một việc: việc · lúc · ai (mã rác ⇒ rỗng)."""
    async with pool.acquire() as conn:
        return {"dong": await qua_trinh.doc(conn, identity.clinic_id, order_id)}


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
    sdt: str | None
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
    doi_tac: str | None = Query(default=None, max_length=40),
    identity: StaffIdentity = Depends(_QUAN_LY),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    """Tab "Tiền thu hộ": theo NGÀY GHI NHẬN / ngày hoàn (giờ VN). Rác ⇒ hôm nay.
    `doi_tac` = ô lọc đối tác (rỗng/rác ⇒ mọi đối tác). CHỈ quản lý."""
    d = doc_ngay(ngay) or hom_nay_vn()
    return await thu_ho.so_ngay(pool, identity.clinic_id, d, doc_doi_tac(doi_tac))


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


@router.post(f"{P}/anh-ck", response_model=OkOut, status_code=201)
async def tai_anh_ck(
    request: Request,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    """Ảnh chuyển khoản của một khoản thu hộ (multipart: file + thanh_toan_id)."""
    from clinicai.services.nhan_tep_luong import don_tep_tam, nhan_multipart

    truong, tep = await nhan_multipart(request)
    try:
        kq = await anh_ck.tai_len(pool, identity, truong.get("thanh_toan_id"), tep)
    finally:
        await don_tep_tam(tep)
    return {"ok": True, "id": kq["id"]}


@router.get(f"{P}/anh-ck/{{anh_id}}")
async def xem_anh_ck(
    anh_id: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """Nội dung ảnh (ảnh nhỏ — đọc trọn). Không lưu đệm, không cho đoán kiểu."""
    noi_dung, mime = await anh_ck.doc(pool, identity, anh_id)
    return Response(
        content=noi_dung,
        media_type=mime,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post(f"{P}/anh-ck/{{anh_id}}/go", response_model=OkOut)
async def go_anh_ck(
    anh_id: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> object:
    await anh_ck.go(pool, identity, anh_id)
    return {"ok": True, "id": anh_id}
