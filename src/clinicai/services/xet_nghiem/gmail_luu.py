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
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final

import asyncpg

from clinicai.core.kho_tep import KHO_VPS, chay_tren_kho, don_tren_kho
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services import media_service

# `_tim_ban` = đường đọc DUY NHẤT "ổ VPS rồi CFS" (luật 1; tệp kia quá trần).
from clinicai.services.tep_ket_qua_service import TepMoDoc, _tim_ban, doc_dan
from clinicai.services.xet_nghiem import ghep_khach, gmail_api
from clinicai.services.xet_nghiem.gmail_ghep import QuyetGmail

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


#: Khách có SĐT (chính / phụ / SĐT thêm) nằm trong danh sách — mọi số của khách gộp
#: ` ; ` cho `ghep_khach.khop_ds` (11/11: SĐT phụ bị bỏ sót).
_KHACH_THEO_SDT_SQL = """
SELECT p.clinic_patient_id::text AS id, p.full_name,
       concat_ws(' ; ', p.phone_primary, p.phone_secondary,
                 (SELECT string_agg(s.so_dien_thoai, ' ; ') FROM patient_sdt_them s
                   WHERE s.clinic_id = p.clinic_id
                     AND s.clinic_patient_id = p.clinic_patient_id)) AS sdt
  FROM patient p
 WHERE p.clinic_id = $1::uuid
   AND (regexp_replace(coalesce(p.phone_primary, ''), '\\D', '', 'g') = ANY($2::text[])
        OR regexp_replace(coalesce(p.phone_secondary, ''), '\\D', '', 'g')
           = ANY($2::text[])
        OR EXISTS (SELECT 1 FROM patient_sdt_them s
                    WHERE s.clinic_id = p.clinic_id
                      AND s.clinic_patient_id = p.clinic_patient_id
                      AND regexp_replace(s.so_dien_thoai, '\\D', '', 'g')
                          = ANY($2::text[])))
 LIMIT 20
"""


async def dem_khach_cung_ten(conn: asyncpg.Connection, cid: str, ten: object) -> int:
    """Số hồ sơ ĐANG DÙNG của phòng khám mang đúng tên này (bỏ dấu, chỉ chữ/số — cùng
    `ghep_khach.chuan`) — G14 chỉ tự gán theo tên + năm sinh khi tên là DUY NHẤT."""
    t = ghep_khach.chuan(ten)
    if not t:
        return 0
    n = await conn.fetchval(
        "SELECT count(*) FROM patient p WHERE p.clinic_id = $1::uuid AND p.is_active"
        "   AND btrim(regexp_replace(p.full_name_unaccent, '[^0-9a-z]+', ' ', 'g'))"
        "       = $2",
        cid,
        t,
    )
    return int(n or 0)


async def khach_theo_sdt(
    conn: asyncpg.Connection, cid: str, sdts: set[str]
) -> list[ghep_khach.UngVien]:
    """MỌI hồ sơ khách của phòng khám mang một trong các SĐT (chính / phụ / thêm) —
    dạng ứng viên không chỉ định (`order_id` rỗng) cho luật khớp tên."""
    if not sdts:
        return []
    dang = sorted(sdts | {"84" + s[1:] for s in sdts})
    rows = await conn.fetch(_KHACH_THEO_SDT_SQL, cid, dang)
    # Chạm trần ⇒ có thể sót đúng người: báo, và gợi ý vẫn chỉ ra khi khớp đúng một.
    canh_bao_neu_day("patient", len(rows), 20, clinic_id=cid)
    return [
        ghep_khach.UngVien(
            order_id="",
            clinic_patient_id=r["id"],
            visit_id=None,
            ten=r["full_name"],
            sdt=r["sdt"],
        )
        for r in rows
    ]


async def goi_y_khach(conn: asyncpg.Connection, cid: str, van_ban: str) -> str | None:
    """Tên + SĐT trong chữ khớp đúng MỘT khách của phòng khám ⇒ id khách; không ⇒ None.
    Dùng lại luật khớp của Drive (`ghep_khach.khop_khach`) — một câu hỏi một hàm."""
    ung_vien = await khach_theo_sdt(conn, cid, ghep_khach.sdt_trong(van_ban))
    if not ung_vien:
        return None
    u, _ = ghep_khach.khop_khach(van_ban, ung_vien)
    return u.clinic_patient_id if u else None


_GHI_SQL = """
INSERT INTO drive_tep (clinic_id, doi_tac_id, nguon, file_id, md5, ten, mime, so_byte,
                       email_message_id, email_tieu_de, email_than, email_nhan_luc,
                       ma_ben_doi_tac_tep, khoa, sha256, vi_tri, tai_len_luc, ly_do_cho,
                       goi_y_clinic_patient_id, goi_y_order_id, luu_tru_vi_sao)
VALUES ($1::uuid, $2::uuid, 'GMAIL', $3, $4, $5, 'application/pdf', $6, $7, $8, $9, $10,
        $11, $12, $13, 'vps', now(), $15, $14::uuid, $16::uuid, $17)
ON CONFLICT DO NOTHING
RETURNING id::text
"""


@dataclass(frozen=True)
class Muc:
    """Một PDF của thư: byte, chữ PDF (đã đọc một lần), quyết ghép (G3)."""

    p: gmail_api.PhanPdf
    data: bytes
    chu: str
    q: QuyetGmail


async def _goi_y(
    conn: asyncpg.Connection, cid: str, thu: gmail_api.ThuGmail, m: Muc
) -> str | None:
    """Khách gợi ý của một PDF: khách G3 đã khớp, không thì đoán theo SĐT (G2)."""
    return (
        m.q.goi_y_clinic_patient_id
        or m.q.clinic_patient_id
        or await goi_y_khach(
            conn, cid, "\n".join((thu.tieu_de, thu.than, m.p.ten, m.chu))
        )
    )


async def _ghi_dong(
    conn: asyncpg.Connection,
    cid: str,
    dt: str,
    thu: gmail_api.ThuGmail,
    m: Muc,
    khoa: str,
    goi_y: str | None,
) -> str | None:
    """Một dòng `drive_tep` của một PDF; đã có (quét lại) ⇒ None."""
    v: str | None = await conn.fetchval(
        _GHI_SQL,
        cid,
        dt,
        f"gmail:{thu.id}:{m.p.part_id}",
        hashlib.md5(m.data, usedforsecurity=False).hexdigest(),
        m.p.ten or "(không tên).pdf",
        len(m.data),
        thu.id,
        thu.tieu_de or None,
        thu.than or None,
        thu.nhan_luc,
        ma_tep(m.p.ten),
        khoa,
        hashlib.sha256(m.data).hexdigest(),
        goi_y,
        m.q.ly_do,
        m.q.goi_y_order_id,
        m.q.luu_tru_vi_sao,
    )
    return v


async def luu_thu(
    pool: asyncpg.Pool,
    cid: str,
    dt: str,
    thu: gmail_api.ThuGmail,
    muc: list[Muc],
) -> list[str | None]:
    """Ghi hết byte rồi MỌI dòng của thư trong một giao dịch. Lỗi ⇒ dọn mọi tệp vừa
    ghi rồi ném (không dòng nào). Dòng đã có (quét lại) ⇒ None + xoá tệp thừa.
    Trả id dòng theo đúng thứ tự `muc` (để gắn tờ cho PDF tự ghép)."""
    goc = media_service.goc_vps()
    khoa: list[str] = []
    # Đã commit ⇒ dòng trỏ vào tệp: lỗi sau đó (trả kết nối) KHÔNG được xoá tệp.
    da_commit = False
    try:
        for m in muc:
            k = f"{cid}/gmail/{thu.id}/{uuid.uuid4().hex}.pdf"
            khoa.append(k)
            await chay_tren_kho(partial(_ghi_o, goc, k, m.data), kho=KHO_VPS, han=30)
        async with pool.acquire() as conn:
            goi_y = [await _goi_y(conn, cid, thu, m) for m in muc]
            async with conn.transaction():
                moi: list[str | None] = [
                    await _ghi_dong(conn, cid, dt, thu, m, k, g)
                    for m, k, g in zip(muc, khoa, goi_y, strict=True)
                ]
            da_commit = True
    except BaseException:
        if not da_commit:
            for k in khoa:
                await don_tren_kho(
                    partial(_xoa_o, goc, k), viec=f"xoa:{k}", kho=KHO_VPS
                )
        raise
    for k, v in zip(khoa, moi, strict=True):
        if v is None:
            await don_tren_kho(partial(_xoa_o, goc, k), viec=f"xoa:{k}", kho=KHO_VPS)
    return moi


async def doc_het(khoa: str, vi_tri: str) -> bytes:
    """Byte một PDF Gmail đã lưu (ổ VPS trước, rồi CFS) — MỘT đường đọc cho hàng ghép
    tay (xem trước / Gán) và Kho. Trần ở `gmail_api.TRAN_BYTE` từ lúc nhận."""
    duong, kho, f = await _tim_ban(khoa, vi_tri, mo=True)
    assert f is not None
    so = await chay_tren_kho(lambda: duong.stat().st_size, kho=kho)
    tep = TepMoDoc(
        f=f, kho=kho, duong=duong, mime="application/pdf", so_byte=so, ten=""
    )
    return b"".join([m async for m in doc_dan(tep, 0, max(so - 1, 0))])
