"""Cửa chặng 4 bàn XN — tệp Drive chờ ghép, ghép tay, từ chối, gán sang (05/11/2026).

Tách khỏi `xet_nghiem_ban.py` (đã gần trần 400 dòng); cùng tiền tố `/xet-nghiem/ban`,
cùng lớp gác `_GUARDED` ở `main.py`. Router mỏng: luật ở `services/xet_nghiem/ghep_tay`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.clock import hom_nay_vn
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.xet_nghiem import ghep_tay, gmail_gan_lai, gmail_goi_y

router = APIRouter()
P = "/xet-nghiem/ban"
_NV = Depends(get_current_identity)
_DB = Depends(get_db_pool)


class OkOut(BaseModel):
    ok: bool
    tep_id: str | None = None


class DriveChoOut(BaseModel):
    id: str
    doi_tac_id: str
    ten_doi_tac: str
    ten: str
    mime: str | None
    #: Cách hộp xem vẽ: ANH | PDF | TAI_LIEU (máy chủ suy từ mime).
    loai: str
    drive_tao_luc: datetime | None
    drive_nguoi_tai: str | None
    nhan_luc: datetime
    ly_do_cho: str | None
    vi_sao: str
    #: DRIVE | GMAIL (Gmail G3 — thư sau mốc tự ghép đã xét mà chưa chắc).
    nguon: str = "DRIVE"
    email_tieu_de: str | None = None
    email_nhan_luc: datetime | None = None
    #: Việc máy chủ gợi ý gán (khớp khách, chưa lấy mẫu / đã có tờ) — nút "Gán theo
    #: gợi ý" chỉ gửi id này; máy chủ vẫn kiểm như Gán tay.
    goi_y_order_id: str | None = None
    #: Khách khớp tên + SĐT (cả Drive) — màn đưa việc của khách này lên đầu ô chọn.
    goi_y_clinic_patient_id: str | None = None
    goi_y_ten: str | None = None
    goi_y_ma: str | None = None
    #: Thư email có khách gợi ý ⇒ nút "Gán cho khách này" (G9, không cần Bàn XN).
    gan_goi_y_duoc: bool = False
    #: Thư email ⇒ ô "tìm khách rồi gán" (G10).
    gan_khach_duoc: bool = False


class DriveNhipOut(BaseModel):
    doi_tac_id: str
    lan_quet_cuoi: datetime
    ok_cuoi: datetime | None
    loi_cuoi: str | None
    #: Quá 1 giờ không có lượt quét thành công (máy chủ tính) ⇒ đèn đỏ.
    tre: bool


class DriveChoListOut(BaseModel):
    tep: list[DriveChoOut]
    nhip: list[DriveNhipOut]


async def _than(request: Request) -> dict[str, Any]:
    try:
        d = await request.json()
    except ValueError:
        d = None
    return d if isinstance(d, dict) else {}


@router.get(f"{P}/drive-cho", response_model=DriveChoListOut)
async def drive_cho(i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    async with p.acquire() as conn:
        return {
            "tep": await ghep_tay.ds_cho(conn, i.clinic_id),
            "nhip": await ghep_tay.ds_nhip(conn, i.clinic_id),
        }


@router.get(f"{P}/drive-tep/{{drive_tep_id}}")
async def drive_tep(
    drive_tep_id: str, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB
) -> Response:
    """Xem trước tệp CHƯA ghép — máy chủ đọc Drive, trình duyệt không gọi Drive.
    Kiểu trả về là kiểu đã sniff từ byte (chỉ ảnh/PDF), không phải mime Drive báo.
    Không đặt CSP sandbox: Chrome không vẽ PDF trong khung bị sandbox."""
    noi, mime = await ghep_tay.noi_dung_cho(p, i, drive_tep_id)
    return Response(
        noi,
        media_type=mime,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(f"{P}/drive-ghep", response_model=OkOut)
async def drive_ghep(
    r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB
) -> object:
    kq = await ghep_tay.ghep(p, i, await _than(r), hom_nay_vn())
    return {"ok": True, "tep_id": kq["tep_id"]}


#: Gán thư email cho khách BẤT KỲ + dò hồ sơ khách (tên, SĐT) ⇒ gác đúng quyền màn
#: Việc của đối tác (`lib/roles.ts` NAV_QUYEN), không chỉ "đã đăng nhập" (soát G10).
_BAN_XN = Depends(cua_quyen("partner.work"))


@router.post(f"{P}/drive-gan-khach", response_model=OkOut)
async def drive_gan_khach(
    r: Request, i: StaffIdentity = _BAN_XN, p: asyncpg.Pool = _DB
) -> object:
    """Thư email ⇒ khách người bấm chọn (gợi ý G9 / ô tìm G10): vào chỉ định đúng loại
    hoặc hồ sơ theo lượt khám."""
    kq = await gmail_goi_y.gan_cho_khach(p, i, await _than(r))
    return {"ok": True, "tep_id": kq["tep_id"]}


class KhachTimOut(BaseModel):
    clinic_patient_id: str
    full_name: str
    patient_code: str | None
    phone_primary: str | None
    birth_year: int | None
    gender: str | None


class KhachTimListOut(BaseModel):
    items: list[KhachTimOut]


@router.get(f"{P}/tim-khach", response_model=KhachTimListOut)
async def tim_khach(
    q: str = "", i: StaffIdentity = _BAN_XN, p: asyncpg.Pool = _DB
) -> object:
    """Ô tìm khách của thư email chờ (G10) — câu tìm khách dùng chung."""
    return {"items": await gmail_goi_y.tim_khach(p, i, q)}


class EmailDaGanOut(BaseModel):
    id: str
    ten: str
    email_tieu_de: str | None
    email_nhan_luc: datetime | None
    ghep_luc: datetime | None
    ten_doi_tac: str
    ghep_boi: str
    tep_id: str
    loai_tep: str
    #: Chữ trạng thái tờ (máy chủ tính): Chờ xác nhận / Hợp lệ / Tờ đã thu hồi…
    nhan_to: str
    #: Tờ đã gửi khách mà gắn nhầm ⇒ câu nhắc báo khách (máy chủ tính).
    canh_bao: str | None
    da_gui: bool
    vao_chi_dinh: bool
    #: Tên dịch vụ của chỉ định, hoặc "Hồ sơ theo lượt khám".
    gan_vao: str
    clinic_patient_id: str
    ten_khach: str
    patient_code: str | None
    phone_primary: str | None


class EmailDaGanListOut(BaseModel):
    thu: list[EmailDaGanOut]
    #: Người xem có quyền Xác nhận kết quả (thu hồi tờ cũ cần quyền đó).
    co_quyen_gan_lai: bool


@router.get(f"{P}/email-da-gan", response_model=EmailDaGanListOut)
async def email_da_gan(
    q: str = "", i: StaffIdentity = _BAN_XN, p: asyncpg.Pool = _DB
) -> object:
    """Thư email ĐÃ gắn khách (G11) — chỗ sửa khi gắn nhầm."""
    return await gmail_gan_lai.da_gan(p, i, q)


@router.post(f"{P}/drive-gan-lai", response_model=OkOut)
async def drive_gan_lai(
    r: Request, i: StaffIdentity = _BAN_XN, p: asyncpg.Pool = _DB
) -> object:
    """Thư email gắn nhầm ⇒ thu hồi / từ chối tờ cũ, gán cho khách đúng (G11)."""
    kq = await gmail_gan_lai.gan_lai(p, i, await _than(r))
    return {"ok": True, "tep_id": kq["tep_id"]}


@router.post(f"{P}/drive-tu-choi", response_model=OkOut)
async def drive_tu_choi(
    r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB
) -> object:
    await ghep_tay.tu_choi(p, i, await _than(r))
    return {"ok": True}


@router.post(f"{P}/gan-sang", response_model=OkOut)
async def gan_sang(r: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB) -> object:
    kq = await ghep_tay.gan_sang(p, i, await _than(r), hom_nay_vn())
    return {"ok": True, "tep_id": kq["tep_id"]}
