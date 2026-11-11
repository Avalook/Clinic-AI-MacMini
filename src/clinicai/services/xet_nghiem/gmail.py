"""Kết quả đối tác về Gmail phòng khám — vòng quét G2.

Kế hoạch: `docs/KE-HOACH-KET-QUA-QUA-GMAIL.md`. Chạy chung tiến trình `drive-xn`
(`worker --drive`, gắn ổ VPS, khoá một tiến trình có sẵn), mỗi `drive.NHIP_GIAY`.

MỘT KHOÁ = MỘT HỘP THƯ = MỘT PHÒNG KHÁM: khoá OAuth là hộp thư của một phòng khám, nên
vòng chỉ quét đối tác của `GMAIL_CLINIC_ID` (thiếu ⇒ bỏ qua). Không thế thì phòng khám
khác đặt trùng email đối tác là đọc được kết quả trong hộp thư này.

Mỗi đối tác có `email_gui_ket_qua` (còn hoạt động):
1. **Thư mới**: thư từ địa chỉ đó sau lần quét OK cuối − 2 ngày (thư trễ, đồng hồ lệch).
   Quá `TRAN_TRANG_MOI` trang (máy chết lâu) ⇒ quét lại lịch sử từ đầu để không sót.
2. **Lịch sử**: tối đa `TRAN_LICH_SU` thư cũ mỗi vòng, mới về cũ, theo con trỏ trang
   Gmail lưu ở `drive_nhip.con_tro_lich_su` (nguồn GMAIL); hết ⇒ `so_lich_su_con = 0`.
   Gmail từ chối con trỏ (400, hết hạn) ⇒ đọc lại từ trang đầu (thư đã có bỏ qua nhanh).

Mỗi thư: header From thật phải đúng địa chỉ đối tác (`from:` của Gmail chỉ để lọc tìm;
thư Spam không đọc). Tải HẾT các PDF rồi `gmail_luu.luu_thu` ghi cả thư một giao dịch.
Lỗi riêng của một thư (quá trần, dữ liệu hỏng, CHECK từ chối) ⇒ bỏ thư đó, không chặn
thư khác. Dòng mới nguồn GMAIL, lý do `LUU_TRU` — G2 chưa ghép gì (G3 bật ghép cho thư
sau mốc `gmail_tu_ngay`). `day_tep` đẩy byte lên CFS.

Vòng không bao giờ ném (mỗi đối tác bọc riêng); lỗi ghi `drive_nhip.loi_cuoi`. Log chỉ
id thư + mã lý do — không tiêu đề, không tên khách, không chuỗi lỗi của DB (có dòng).
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

import asyncpg
import httpx
import structlog

from clinicai.core.kho_tep import KHO_VPS, chay_tren_kho
from clinicai.services import media_service
from clinicai.services.xet_nghiem import (
    ghep_khach,
    gmail_api,
    gmail_cai_dat,
    gmail_doc,
    gmail_ghep,
    gmail_luu,
)

logger = structlog.get_logger()

BIEN_PHONG_KHAM: Final = "GMAIL_CLINIC_ID"
TRAN_DOI_TAC: Final = 50
TRAN_LICH_SU: Final = 100
#: Trang thư mới tối đa mỗi vòng (100 thư/trang) — chặn vòng vô hạn.
TRAN_TRANG_MOI: Final = 5
LUI_THU_MOI: Final = timedelta(days=2)
_VN: Final = ZoneInfo("Asia/Ho_Chi_Minh")
_UUID_RE: Final = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")


def phong_kham_cua_khoa() -> str | None:
    """Phòng khám sở hữu hộp thư (env `GMAIL_CLINIC_ID`). Thiếu / rác ⇒ None."""
    v = os.environ.get(BIEN_PHONG_KHAM, "").strip()
    return v.lower() if _UUID_RE.fullmatch(v) else None


def q_thu(email: str, sau: datetime | None = None) -> str:
    """Câu tìm Gmail: thư có PDF đính kèm từ `email`, KHÔNG trong Spam (thư giả mạo
    người gửi bị Gmail xếp vào đó); `sau` ⇒ chỉ thư sau mốc (giây)."""
    q = f"from:{email} has:attachment filename:pdf -in:spam"
    return f"{q} after:{int(sau.timestamp())}" if sau is not None else q


async def _da_co(pool: asyncpg.Pool, cid: str, mids: list[str]) -> set[str]:
    """Thư đã có dòng — ghi cả thư trong một giao dịch nên có dòng = đã đủ."""
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
    dt: str,
    email: str,
    mid: str,
) -> int:
    """Một thư: đọc, kiểm người gửi, tải HẾT PDF, rồi mới ghi. Trả số dòng mới.
    `GmailError` (tạm) ⇒ ném để lượt sau làm lại; lỗi riêng của thư ⇒ bỏ thư, trả 0."""
    from clinicai.services.tep_ket_qua_service import MEDIA_LOCAL_MIN_FREE_BYTES

    thu = await gmail_api.doc_thu(kh, mid)
    if thu is None or not thu.pdf:
        return 0
    if thu.tu != email:
        logger.warning("gmail_nguoi_gui_khac", message_id=mid)
        return 0
    try:
        if sum(p.so_byte for p in thu.pdf) > gmail_api.TRAN_THU:
            raise gmail_api.ThuBoQua("thu_qua_lon")
        tai = [(p, await gmail_api.tai_phan(kh, mid, p)) for p in thu.pdf]
    except gmail_api.ThuBoQua as e:
        logger.warning("gmail_bo_thu", message_id=mid, ly_do=str(e))
        return 0
    for p, d in tai:
        if not d.startswith(b"%PDF"):
            logger.warning("gmail_khong_phai_pdf", message_id=mid, part_id=p.part_id)
    tai = [(p, d) for p, d in tai if d.startswith(b"%PDF")]
    if not tai:
        return 0
    goc = media_service.goc_vps()
    trong = await chay_tren_kho(partial(_con_cho, goc), kho=KHO_VPS)
    if trong - sum(len(d) for _, d in tai) < MEDIA_LOCAL_MIN_FREE_BYTES:
        raise gmail_api.GmailError("Ổ máy chủ gần đầy — chưa lưu thư kết quả.")
    muc = await _muc_ca_thu(pool, cid, dt, thu, tai)
    try:
        ids = await gmail_luu.luu_thu(pool, cid, dt, thu, muc)
    except asyncpg.IntegrityConstraintViolationError as e:
        # CHECK / khoá ngoại từ chối dữ liệu của RIÊNG thư này — vĩnh viễn, bỏ thư.
        # Không log chuỗi lỗi: DETAIL của Postgres chứa cả dòng (tên khách).
        logger.error("gmail_bo_thu", message_id=mid, ly_do=type(e).__name__)
        return 0
    # Gắn tờ kết quả SAU khi cả thư đã lưu (tai_len tự mở giao dịch riêng). Lỗi của
    # MỘT PDF không bỏ các PDF sau; dòng đó sang LOI_TEP (lượt sau không quét lại thư).
    for m, dong_id in zip(muc, ids, strict=True):
        if dong_id is None or m.q.ly_do is not None:
            continue
        try:
            await gmail_ghep.gan_tu_dong(pool, cid, dong_id, m.q, m.data, m.p.ten)
        except Exception as e:  # noqa: BLE001 — không log chuỗi lỗi (có thể chứa tên)
            logger.error(
                "gmail_tu_ghep_loi", drive_tep_id=dong_id, loai=type(e).__name__
            )
            await gmail_ghep.danh_loi_tep(pool, cid, dong_id)
    return sum(i is not None for i in ids)


async def _muc_ca_thu(
    pool: asyncpg.Pool,
    cid: str,
    dt: str,
    thu: gmail_api.ThuGmail,
    tai: list[tuple[gmail_api.PhanPdf, bytes]],
) -> list[gmail_luu.Muc]:
    """Đọc chữ PDF MỘT lần; quyết từng PDF. Chỉ thư từ mốc tự ghép trở đi VÀ xác thực
    đúng miền người gửi mới được xét ghép — còn lại Lưu trữ (Kho) như G2."""
    chu = [(p, d, ghep_khach.chu_pdf(d)) for p, d in tai]
    async with pool.acquire() as conn:
        moc = await gmail_cai_dat.doc_moc(conn, cid)
        xet = gmail_ghep.trong_moc(thu.nhan_luc, moc) and gmail_doc.xac_thuc_ok(
            thu.xac_thuc, thu.tu
        )
        if not xet:
            return [gmail_luu.Muc(p, d, c, gmail_ghep.LUU_TRU) for p, d, c in chu]
        viec = await ghep_khach.doc_viec(conn, cid, dt)
    nam_nay = thu.nhan_luc.astimezone(_VN).year
    return [
        gmail_luu.Muc(
            p,
            d,
            c,
            gmail_ghep.quyet(
                gmail_doc.doc_thu(thu.tieu_de, thu.than, p.ten, c, nam_nay),
                viec,
                bool(c.strip()),
            ),
        )
        for p, d, c in chu
    ]


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


async def _quet_moi(
    pool: asyncpg.Pool,
    kh: httpx.AsyncClient,
    cid: str,
    dt: str,
    email: str,
    tu: datetime,
) -> tuple[int, bool]:
    """Thư mới sau `tu`. Trả (số dòng mới, đã đọc HẾT khung chưa)."""
    so = 0
    trang: str | None = None
    for _ in range(TRAN_TRANG_MOI):
        ids, trang, _uoc = await gmail_api.liet_ke(kh, q_thu(email, tu), trang)
        so += await _nhan_ca_trang(pool, kh, cid, dt, email, ids)
        if not trang:
            return so, True
    return so, False


async def _lich_su(
    kh: httpx.AsyncClient, email: str, con_tro: str | None
) -> tuple[list[str], str | None, int]:
    """Một trang lịch sử; Gmail từ chối con trỏ (400, hết hạn) ⇒ đọc lại từ đầu."""
    try:
        return await gmail_api.liet_ke(kh, q_thu(email), con_tro, TRAN_LICH_SU)
    except gmail_api.GmailError as e:
        if con_tro is None or e.ma_http != 400:
            raise
        logger.warning("gmail_con_tro_hong_doc_lai_tu_dau")
        return await gmail_api.liet_ke(kh, q_thu(email), None, TRAN_LICH_SU)


_NHIP_SQL = """
SELECT ok_cuoi, con_tro_lich_su, so_lich_su_con FROM drive_nhip
 WHERE clinic_id = $1::uuid AND doi_tac_id = $2::uuid AND nguon = 'GMAIL'
"""


async def quet_doi_tac(
    pool: asyncpg.Pool, kh: httpx.AsyncClient, cid: str, dt: str, email: str
) -> tuple[int, str | None, int | None]:
    """Một đối tác: thư mới rồi một trang lịch sử. Trả (số dòng mới, con trỏ, còn ~)."""
    n = await pool.fetchrow(_NHIP_SQL, cid, dt)
    con_tro = n["con_tro_lich_su"] if n is not None else None
    con = n["so_lich_su_con"] if n is not None else None
    so = 0
    if n is not None and n["ok_cuoi"] is not None:
        so, het = await _quet_moi(pool, kh, cid, dt, email, n["ok_cuoi"] - LUI_THU_MOI)
        if not het:
            # Khung "mới" quá dài (máy chết lâu) ⇒ quét lại lịch sử từ đầu, không sót.
            logger.warning("gmail_qua_tran_thu_moi_quet_lai_lich_su", doi_tac_id=dt)
            con_tro, con = None, None
    if con == 0:
        return so, None, 0
    ids, sau, uoc = await _lich_su(kh, email, con_tro)
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
    email: str | None = None,
) -> None:
    """Nhịp nguồn GMAIL. Lỗi ⇒ giữ nguyên con trỏ lịch sử (lượt sau đọc lại trang).
    Con trỏ CHỈ ghi khi email lúc quét vẫn là email hiện tại của đối tác: Quản lý đổi
    email giữa lượt quét (G4 đặt con trỏ về NULL) thì lượt đang chạy bằng email cũ
    KHÔNG được ghi đè "lịch sử đã hết" — không thì thư cũ của địa chỉ mới không bao
    giờ được nạp, mà không gì báo."""
    async with pool.acquire() as conn, conn.transaction():
        # FOR SHARE: lệnh đổi email (gmail_cai_dat.email_cu ... FOR UPDATE) chờ tới khi
        # nhịp này ghi xong rồi mới đặt lại con trỏ ⇒ thứ tự luôn đúng, cả khi chưa có
        # dòng nhịp (nhánh INSERT).
        hien = await conn.fetchval(
            "SELECT email_gui_ket_qua FROM doi_tac"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR SHARE",
            cid,
            dt,
        )
        ghi_con_tro = loi is None and email is not None and email == hien
        await conn.execute(
            """
            INSERT INTO drive_nhip (clinic_id, doi_tac_id, nguon, lan_quet_cuoi,
                                    ok_cuoi, loi_cuoi, so_tep_cuoi, con_tro_lich_su,
                                    so_lich_su_con)
            VALUES ($1::uuid, $2::uuid, 'GMAIL', now(),
                    CASE WHEN $3::text IS NULL THEN now() END, $3, $4,
                    CASE WHEN $7 THEN $5 END, CASE WHEN $7 THEN $6::int END)
            ON CONFLICT (clinic_id, doi_tac_id, nguon) DO UPDATE
               SET lan_quet_cuoi = now(),
                   ok_cuoi = CASE WHEN $3::text IS NULL THEN now()
                                  ELSE drive_nhip.ok_cuoi END,
                   loi_cuoi = $3, so_tep_cuoi = $4,
                   con_tro_lich_su = CASE WHEN $7 THEN $5
                                          ELSE drive_nhip.con_tro_lich_su END,
                   so_lich_su_con = CASE WHEN $7 THEN $6::int
                                         ELSE drive_nhip.so_lich_su_con END
            """,
            cid,
            dt,
            loi,
            so,
            con_tro,
            con,
            ghi_con_tro,
        )


async def mot_vong(pool: asyncpg.Pool) -> dict[str, int]:
    """Một lượt mọi đối tác (của phòng khám chủ hộp thư) có email gửi kết quả. Không
    khoá / chưa gắn phòng khám ⇒ bỏ qua, không ném."""
    if not gmail_api.co_cau_hinh():
        return {"bo_qua": 1}
    cid = phong_kham_cua_khoa()
    if cid is None:
        logger.warning("gmail_chua_gan_phong_kham", bien=BIEN_PHONG_KHAM)
        return {"bo_qua": 1}
    rows = await pool.fetch(
        "SELECT id::text AS id, email_gui_ket_qua AS email FROM doi_tac"
        " WHERE clinic_id = $1::uuid AND email_gui_ket_qua IS NOT NULL"
        "   AND ngung_luc IS NULL ORDER BY id LIMIT $2",
        cid,
        TRAN_DOI_TAC,
    )
    tong = loi = 0
    async with httpx.AsyncClient(timeout=60) as kh:
        for r in rows:
            try:
                so, con_tro, con = await quet_doi_tac(
                    pool, kh, cid, r["id"], r["email"]
                )
                tong += so
                await _nhip(pool, cid, r["id"], None, so, con_tro, con, r["email"])
            except Exception as e:  # noqa: BLE001 — đối tác lỗi không chặn đối tác khác
                loi += 1
                if isinstance(e, gmail_api.GmailError):
                    cau = str(e)[:300]
                    logger.warning("gmail_quet_loi", doi_tac_id=r["id"], cau=cau)
                else:
                    # Chỉ tên kiểu lỗi: chuỗi lỗi DB có thể chứa dữ liệu thư.
                    cau = "Lỗi quét Gmail."
                    logger.error(
                        "gmail_quet_loi", doi_tac_id=r["id"], loai=type(e).__name__
                    )
                try:
                    await _nhip(pool, cid, r["id"], cau, 0)
                except Exception:  # noqa: BLE001
                    logger.exception("gmail_ghi_nhip_loi", doi_tac_id=r["id"])
    return {"doi_tac": len(rows), "tep_moi": tong, "loi": loi}
