"""Cửa Kho email kết quả (tạm) — Gmail G2b. Router mỏng: luật ở
`services/xet_nghiem/kho_email`. Thiếu quyền `xet_nghiem.kho_email` ⇒ 404 ở service
(không lộ Kho / thư có hay không). Lớp gác `_GUARDED` ở `main.py` như các cửa XN khác.
"""

from __future__ import annotations

from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.tep_ket_qua_service import doc_dan
from clinicai.services.xet_nghiem import kho_email

router = APIRouter()
P = "/xet-nghiem/kho-email"
_NV = Depends(get_current_identity)
_DB = Depends(get_db_pool)


class DenOut(BaseModel):
    nhan: str
    #: success | danger | neutral — màu chip, máy chủ tính.
    mau: str


class ThuOut(BaseModel):
    id: str
    doi_tac_id: str
    ten_doi_tac: str
    ten: str
    tieu_de: str | None
    nhan_luc: datetime
    ma_tep: str | None
    #: LUU_TRU | CHO_GHEP | DA_GHEP | TU_CHOI (tính từ sự việc, một biểu thức SQL).
    trang_thai: str
    nhan_trang_thai: str
    #: Màu chip (neutral | warning | success | danger) — máy chủ tính.
    mau: str
    #: Thư chưa ghép (Lưu trữ / Chờ ghép tay): vì sao — máy chủ tính (G5). Còn lại None.
    vi_sao: str | None = None
    goi_y_id: str | None
    goi_y_ten: str | None
    goi_y_ma: str | None


class LocOut(BaseModel):
    ma: str
    nhan: str


class KhoOut(BaseModel):
    thu: list[ThuOut]
    #: Tổng thư khớp bộ lọc — màn biết còn trang, không cắt im lặng.
    tong: int
    trang: int
    co: int
    thanh_tren: DenOut
    #: Các lựa chọn bộ lọc trạng thái (nhãn một nơi: services/.../kho_email.NHAN).
    loc: list[LocOut]


class ThuChiTietOut(BaseModel):
    id: str
    doi_tac_id: str
    ten_doi_tac: str
    ten: str
    tieu_de: str | None
    than: str | None
    nhan_luc: datetime
    ma_tep: str | None
    trang_thai: str
    nhan_trang_thai: str
    vi_sao: str | None = None


@router.get(P, response_model=KhoOut)
async def danh_sach(
    request: Request, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB
) -> object:
    """Lọc: tu_ngay, den_ngay (YYYY-MM-DD), trang_thai, q (tên bỏ dấu / SĐT), trang,
    co. Tham số rác ⇒ bỏ lọc đó (không 422)."""
    async with p.acquire() as conn:
        return await kho_email.danh_sach(conn, i, dict(request.query_params))


@router.get(f"{P}/{{thu_id}}", response_model=ThuChiTietOut)
async def chi_tiet(
    thu_id: str, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB
) -> object:
    async with p.acquire() as conn:
        return await kho_email.chi_tiet(conn, i, thu_id)


@router.get(f"{P}/{{thu_id}}/pdf")
async def pdf(
    thu_id: str, i: StaffIdentity = _NV, p: asyncpg.Pool = _DB
) -> StreamingResponse:
    """PDF đã lưu (ổ VPS / CFS) — mỗi lần mở có vết `lab.archive_viewed`. Không đặt
    CSP sandbox: Chrome không vẽ PDF trong khung bị sandbox (như xem tệp Drive)."""
    tep = await kho_email.mo_pdf(p, i, thu_id)
    return StreamingResponse(
        doc_dan(tep, 0, max(tep.so_byte - 1, 0)),
        media_type=tep.mime,
        headers={
            "Content-Length": str(tep.so_byte),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
