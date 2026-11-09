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
from clinicai.services.xet_nghiem import ghep_tay

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
