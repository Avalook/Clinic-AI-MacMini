"""Lưu một thư kết quả Gmail vào Kho — byte ổ VPS + dòng `drive_tep` (Gmail G2).

Tách khỏi vòng quét `gmail.py` (trần 400 dòng). Một thư = một giao dịch: ghi hết byte
(`<clinic>/gmail/<thư>/<uuid>.pdf`, 0600) rồi MỌI dòng trong một giao dịch; lỗi ⇒ dọn
mọi tệp vừa ghi, không dòng nào (lượt sau làm lại cả thư — `gmail._da_co` coi "có dòng"
là đủ thư, nên KHÔNG được có thư lưu dở).
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from functools import partial
from pathlib import Path
from typing import Final

import asyncpg

from clinicai.core.kho_tep import KHO_VPS, chay_tren_kho, don_tren_kho
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services import media_service
from clinicai.services.xet_nghiem import ghep_khach, gmail_api

_MA_TEP_RE: Final = re.compile(r"(?<!\d)(\d{6}-\d{6})(?!\d)")


def ma_tep(ten: object) -> str | None:
    """Mã `081126-501726` trong tên tệp (kế hoạch 1.13: lưu để tra, KHÔNG dùng ghép).
    Không có / nhiều mã khác nhau / rác ⇒ None."""
    if not isinstance(ten, str):
        return None
    ma = set(_MA_TEP_RE.findall(ten))
    return ma.pop() if len(ma) == 1 else None


def _ghi_o(goc: Path, khoa: str, data: bytes) -> None:
    """Đồng bộ (chạy trong `chay_tren_kho`): ghi tạm rồi đổi tên, quyền 0600."""
    p = media_service.giai_trong(goc, khoa)
    if p is None:
        raise ValueError("khoá tệp không hợp lệ")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(p)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _xoa_o(goc: Path, khoa: str) -> None:
    p = media_service.giai_trong(goc, khoa)
    if p is not None:
        p.unlink(missing_ok=True)


async def goi_y_khach(conn: asyncpg.Connection, cid: str, van_ban: str) -> str | None:
    """Tên + SĐT trong chữ khớp đúng MỘT khách của phòng khám ⇒ id khách; không ⇒ None.
    Dùng lại luật khớp của Drive (`ghep_khach.khop_khach`) — một câu hỏi một hàm."""
    sdts = ghep_khach.sdt_trong(van_ban)
    if not sdts:
        return None
    dang = sorted(sdts | {"84" + s[1:] for s in sdts})
    rows = await conn.fetch(
        "SELECT clinic_patient_id::text AS id, full_name, phone_primary FROM patient"
        " WHERE clinic_id = $1::uuid"
        "   AND regexp_replace(coalesce(phone_primary, ''), '\\D', '', 'g')"
        "       = ANY($2::text[])"
        " LIMIT 20",
        cid,
        dang,
    )
    # Chạm trần ⇒ có thể sót đúng người: báo, và gợi ý vẫn chỉ ra khi khớp đúng một.
    canh_bao_neu_day("patient", len(rows), 20, clinic_id=cid)
    ung_vien = [
        ghep_khach.UngVien(
            order_id="",
            clinic_patient_id=r["id"],
            visit_id=None,
            ten=r["full_name"],
            sdt=r["phone_primary"],
        )
        for r in rows
    ]
    u, _ = ghep_khach.khop_khach(van_ban, ung_vien)
    return u.clinic_patient_id if u else None


_GHI_SQL = """
INSERT INTO drive_tep (clinic_id, doi_tac_id, nguon, file_id, md5, ten, mime, so_byte,
                       email_message_id, email_tieu_de, email_than, email_nhan_luc,
                       ma_ben_doi_tac_tep, khoa, sha256, vi_tri, tai_len_luc, ly_do_cho,
                       goi_y_clinic_patient_id)
VALUES ($1::uuid, $2::uuid, 'GMAIL', $3, $4, $5, 'application/pdf', $6, $7, $8, $9, $10,
        $11, $12, $13, 'vps', now(), 'LUU_TRU', $14::uuid)
ON CONFLICT DO NOTHING
RETURNING id
"""


async def luu_thu(
    pool: asyncpg.Pool,
    cid: str,
    dt: str,
    thu: gmail_api.ThuGmail,
    tai: list[tuple[gmail_api.PhanPdf, bytes]],
) -> int:
    """Ghi hết byte rồi MỌI dòng của thư trong một giao dịch. Lỗi ⇒ dọn mọi tệp vừa
    ghi rồi ném (không dòng nào). Dòng đã có (quét lại) ⇒ xoá tệp thừa của nó."""
    goc = media_service.goc_vps()
    khoa: list[str] = []
    try:
        for _p, data in tai:
            k = f"{cid}/gmail/{thu.id}/{uuid.uuid4().hex}.pdf"
            khoa.append(k)
            await chay_tren_kho(partial(_ghi_o, goc, k, data), kho=KHO_VPS, han=30)
        async with pool.acquire() as conn:
            goi_y = [
                await goi_y_khach(
                    conn,
                    cid,
                    "\n".join((thu.tieu_de, thu.than, p.ten, ghep_khach.chu_pdf(d))),
                )
                for p, d in tai
            ]
            async with conn.transaction():
                moi = [
                    await conn.fetchval(
                        _GHI_SQL,
                        cid,
                        dt,
                        f"gmail:{thu.id}:{p.part_id}",
                        hashlib.md5(d, usedforsecurity=False).hexdigest(),
                        p.ten or "(không tên).pdf",
                        len(d),
                        thu.id,
                        thu.tieu_de or None,
                        thu.than or None,
                        thu.nhan_luc,
                        ma_tep(p.ten),
                        k,
                        hashlib.sha256(d).hexdigest(),
                        g,
                    )
                    for (p, d), k, g in zip(tai, khoa, goi_y, strict=True)
                ]
    except BaseException:
        for k in khoa:
            await don_tren_kho(partial(_xoa_o, goc, k), viec=f"xoa:{k}", kho=KHO_VPS)
        raise
    for k, m in zip(khoa, moi, strict=True):
        if m is None:
            await don_tren_kho(partial(_xoa_o, goc, k), viec=f"xoa:{k}", kho=KHO_VPS)
    return sum(m is not None for m in moi)
