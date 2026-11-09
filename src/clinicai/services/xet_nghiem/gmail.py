"""Kết quả đối tác về Gmail phòng khám — vòng quét G2.

Kế hoạch: `docs/KE-HOACH-KET-QUA-QUA-GMAIL.md`. Chạy chung tiến trình `drive-xn`
(`worker --drive`, gắn ổ VPS, khoá một tiến trình có sẵn), mỗi `drive.NHIP_GIAY`.
Mỗi đối tác có `email_gui_ket_qua` (còn hoạt động):

1. **Thư mới**: thư từ địa chỉ đó sau lần quét OK cuối − 2 ngày (thư trễ, đồng hồ lệch).
2. **Lịch sử**: tối đa `TRAN_LICH_SU` thư cũ mỗi vòng, mới về cũ, theo con trỏ trang
   Gmail lưu ở `drive_nhip.con_tro_lich_su` (nguồn GMAIL); hết ⇒ `so_lich_su_con = 0`.

Mỗi thư: header From thật phải đúng địa chỉ đối tác (`from:` của Gmail chỉ để lọc tìm).
Tải HẾT các PDF của thư trước khi ghi — một phần lỗi ⇒ cả thư để lượt sau (không có
thư lưu dở mà lượt sau tưởng xong). Mỗi PDF: byte vào ổ VPS
(`<clinic>/gmail/<thư>/<uuid>.pdf`, 0600) rồi một dòng `drive_tep` nguồn GMAIL, lý do
`LUU_TRU` — G2 chưa ghép gì (G3 bật ghép cho thư sau mốc `gmail_tu_ngay`). `day_tep`
đẩy byte lên CFS như tệp kết quả.

Gợi ý khách (kế hoạch 1.10): tên + SĐT khớp đúng MỘT khách ⇒ `goi_y_clinic_patient_id`.
Chỉ là chữ gợi ý ở Kho — không gắn, không báo ai.

Vòng không bao giờ ném (mỗi đối tác bọc riêng); lỗi ghi `drive_nhip.loi_cuoi`. Log chỉ
id thư + lý do — không tiêu đề, không tên khách.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Final

import asyncpg
import httpx
import structlog

from clinicai.core.kho_tep import KHO_VPS, chay_tren_kho, don_tren_kho
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services import media_service
from clinicai.services.xet_nghiem import ghep_khach, gmail_api

logger = structlog.get_logger()

TRAN_DOI_TAC: Final = 50
TRAN_LICH_SU: Final = 100
#: Trang thư mới tối đa mỗi vòng (100 thư/trang) — chặn vòng vô hạn.
TRAN_TRANG_MOI: Final = 5
LUI_THU_MOI: Final = timedelta(days=2)
_MA_TEP_RE: Final = re.compile(r"(?<!\d)(\d{6}-\d{6})(?!\d)")


def ma_tep(ten: object) -> str | None:
    """Mã `081126-501726` trong tên tệp (kế hoạch 1.13: lưu để tra, KHÔNG dùng ghép).
    Không có / nhiều mã khác nhau / rác ⇒ None."""
    if not isinstance(ten, str):
        return None
    ma = set(_MA_TEP_RE.findall(ten))
    return ma.pop() if len(ma) == 1 else None


def q_thu(email: str, sau: datetime | None = None) -> str:
    """Câu tìm Gmail: thư CÓ đính kèm từ `email`; `sau` ⇒ chỉ thư sau mốc (giây)."""
    q = f"from:{email} has:attachment"
    return f"{q} after:{int(sau.timestamp())}" if sau is not None else q


def _ghi_o(goc: Path, khoa: str, data: bytes) -> None:
    """Đồng bộ (chạy trong `chay_tren_kho`): ghi tạm rồi đổi tên, quyền 0600."""
    p = media_service.giai_trong(goc, khoa)
    if p is None:
        raise ValueError("khoá tệp không hợp lệ")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(p)


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


async def _luu_pdf(
    pool: asyncpg.Pool,
    cid: str,
    doi_tac_id: str,
    thu: gmail_api.ThuGmail,
    p: gmail_api.PhanPdf,
    data: bytes,
) -> bool:
    """Byte vào ổ VPS rồi một dòng sự việc. Dòng đã có (quét lại) ⇒ xoá tệp vừa ghi."""
    goc = media_service.goc_vps()
    khoa = f"{cid}/gmail/{thu.id}/{uuid.uuid4().hex}.pdf"
    await chay_tren_kho(partial(_ghi_o, goc, khoa, data), kho=KHO_VPS, han=30)
    van_ban = "\n".join((thu.tieu_de, thu.than, p.ten, ghep_khach.chu_pdf(data)))
    try:
        async with pool.acquire() as conn:
            goi_y = await goi_y_khach(conn, cid, van_ban)
            moi = await conn.fetchval(
                _GHI_SQL,
                cid,
                doi_tac_id,
                f"gmail:{thu.id}:{p.part_id}",
                hashlib.md5(data, usedforsecurity=False).hexdigest(),
                p.ten or "(không tên).pdf",
                len(data),
                thu.id,
                thu.tieu_de or None,
                thu.than or None,
                thu.nhan_luc,
                ma_tep(p.ten),
                khoa,
                hashlib.sha256(data).hexdigest(),
                goi_y,
            )
    except BaseException:
        await don_tren_kho(partial(_xoa_o, goc, khoa), viec=f"xoa:{khoa}", kho=KHO_VPS)
        raise
    if moi is None:
        await don_tren_kho(partial(_xoa_o, goc, khoa), viec=f"xoa:{khoa}", kho=KHO_VPS)
    return moi is not None


async def _da_co(pool: asyncpg.Pool, cid: str, mids: list[str]) -> set[str]:
    rows = await pool.fetch(
        "SELECT DISTINCT email_message_id FROM drive_tep WHERE clinic_id = $1::uuid"
        " AND nguon = 'GMAIL' AND email_message_id = ANY($2::text[])",
        cid,
        mids,
    )
    return {r["email_message_id"] for r in rows}


def _con_cho(goc: Path) -> int:
    goc.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(goc).free


async def nhan_thu(
    pool: asyncpg.Pool,
    kh: httpx.AsyncClient,
    cid: str,
    doi_tac_id: str,
    email: str,
    mid: str,
) -> int:
    """Một thư: đọc, kiểm người gửi, tải HẾT PDF, rồi mới ghi. Trả số dòng mới."""
    from clinicai.services.tep_ket_qua_service import MEDIA_LOCAL_MIN_FREE_BYTES

    thu = await gmail_api.doc_thu(kh, mid)
    if thu is None or not thu.pdf:
        return 0
    if thu.tu != email:
        logger.warning("gmail_nguoi_gui_khac", message_id=mid)
        return 0
    tai: list[tuple[gmail_api.PhanPdf, bytes]] = []
    for p in thu.pdf:
        data = await gmail_api.tai_phan(kh, mid, p)
        if not data.startswith(b"%PDF"):
            logger.warning("gmail_khong_phai_pdf", message_id=mid, part_id=p.part_id)
            continue
        tai.append((p, data))
    can = sum(len(d) for _, d in tai)
    goc = media_service.goc_vps()
    if tai and await chay_tren_kho(partial(_con_cho, goc), kho=KHO_VPS) - can < (
        MEDIA_LOCAL_MIN_FREE_BYTES
    ):
        raise gmail_api.GmailError("Ổ máy chủ gần đầy — chưa lưu thư kết quả.")
    so = 0
    for p, data in tai:
        so += await _luu_pdf(pool, cid, doi_tac_id, thu, p, data)
    return so


async def _nhan_ca_trang(
    pool: asyncpg.Pool,
    kh: httpx.AsyncClient,
    cid: str,
    dt: str,
    email: str,
    ids: list[str],
) -> int:
    da_co = await _da_co(pool, cid, ids) if ids else set()
    so = 0
    for mid in ids:
        if mid not in da_co:
            so += await nhan_thu(pool, kh, cid, dt, email, mid)
    return so


_NHIP_SQL = """
SELECT ok_cuoi, con_tro_lich_su, so_lich_su_con FROM drive_nhip
 WHERE clinic_id = $1::uuid AND doi_tac_id = $2::uuid AND nguon = 'GMAIL'
"""


async def quet_doi_tac(
    pool: asyncpg.Pool, kh: httpx.AsyncClient, cid: str, dt: str, email: str
) -> tuple[int, str | None, int | None]:
    """Một đối tác: thư mới rồi một trang lịch sử. Trả (số dòng mới, con trỏ, còn ~)."""
    n = await pool.fetchrow(_NHIP_SQL, cid, dt)
    so = 0
    if n is not None and n["ok_cuoi"] is not None:
        trang: str | None = None
        for _ in range(TRAN_TRANG_MOI):
            ids, trang, _uoc = await gmail_api.liet_ke(
                kh, q_thu(email, n["ok_cuoi"] - LUI_THU_MOI), trang
            )
            so += await _nhan_ca_trang(pool, kh, cid, dt, email, ids)
            if not trang:
                break
    con_tro = n["con_tro_lich_su"] if n is not None else None
    con = n["so_lich_su_con"] if n is not None else None
    if con == 0:
        return so, None, 0
    ids, sau, uoc = await gmail_api.liet_ke(kh, q_thu(email), con_tro, TRAN_LICH_SU)
    so += await _nhan_ca_trang(pool, kh, cid, dt, email, ids)
    if sau is None:
        return so, None, 0
    da = await pool.fetchval(
        "SELECT count(DISTINCT email_message_id) FROM drive_tep WHERE clinic_id ="
        " $1::uuid AND doi_tac_id = $2::uuid AND nguon = 'GMAIL'",
        cid,
        dt,
    )
    return so, sau, max(uoc - int(da or 0), 1)


async def _nhip(
    pool: asyncpg.Pool,
    cid: str,
    dt: str,
    loi: str | None,
    so: int,
    con_tro: str | None = None,
    con: int | None = None,
) -> None:
    """Nhịp nguồn GMAIL. Lỗi ⇒ giữ nguyên con trỏ lịch sử (lượt sau đọc lại trang)."""
    await pool.execute(
        """
        INSERT INTO drive_nhip (clinic_id, doi_tac_id, nguon, lan_quet_cuoi, ok_cuoi,
                                loi_cuoi, so_tep_cuoi, con_tro_lich_su, so_lich_su_con)
        VALUES ($1::uuid, $2::uuid, 'GMAIL', now(),
                CASE WHEN $3::text IS NULL THEN now() END, $3, $4, $5, $6)
        ON CONFLICT (clinic_id, doi_tac_id, nguon) DO UPDATE
           SET lan_quet_cuoi = now(),
               ok_cuoi = CASE WHEN $3::text IS NULL THEN now()
                              ELSE drive_nhip.ok_cuoi END,
               loi_cuoi = $3, so_tep_cuoi = $4,
               con_tro_lich_su = CASE WHEN $3::text IS NULL THEN $5
                                      ELSE drive_nhip.con_tro_lich_su END,
               so_lich_su_con = CASE WHEN $3::text IS NULL THEN $6
                                     ELSE drive_nhip.so_lich_su_con END
        """,
        cid,
        dt,
        loi,
        so,
        con_tro,
        con,
    )


async def mot_vong(pool: asyncpg.Pool) -> dict[str, int]:
    """Một lượt mọi đối tác có email gửi kết quả. Không khoá ⇒ bỏ qua, không ném."""
    if not gmail_api.co_cau_hinh():
        return {"bo_qua": 1}
    rows = await pool.fetch(
        "SELECT clinic_id::text AS cid, id::text AS id, email_gui_ket_qua AS email"
        " FROM doi_tac WHERE email_gui_ket_qua IS NOT NULL AND ngung_luc IS NULL"
        " ORDER BY clinic_id, id LIMIT $1",
        TRAN_DOI_TAC,
    )
    tong = loi = 0
    async with httpx.AsyncClient(timeout=60) as kh:
        for r in rows:
            try:
                so, con_tro, con = await quet_doi_tac(
                    pool, kh, r["cid"], r["id"], r["email"]
                )
                tong += so
                await _nhip(pool, r["cid"], r["id"], None, so, con_tro, con)
            except Exception as e:  # noqa: BLE001 — đối tác lỗi không chặn đối tác khác
                loi += 1
                cau = (
                    str(e)[:300]
                    if isinstance(e, gmail_api.GmailError)
                    else "Lỗi quét Gmail."
                )
                logger.exception("gmail_quet_loi", doi_tac_id=r["id"])
                try:
                    await _nhip(pool, r["cid"], r["id"], cau, 0)
                except Exception:  # noqa: BLE001
                    logger.exception("gmail_ghi_nhip_loi", doi_tac_id=r["id"])
    return {"doi_tac": len(rows), "tep_moi": tong, "loi": loi}
