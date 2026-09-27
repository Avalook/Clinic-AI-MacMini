"""KHO LỖI tự dựng trong Postgres (27/09/2026 — theo dõi lỗi Pha 1).

Mỗi lỗi chưa lường trước (500 ở API, bên nhận sự kiện hỏng ở worker, lỗi trình
duyệt) ghi thành MỘT dòng `loi_nhom` theo KIỂU: cùng nguồn + vị trí + loại lỗi +
khung code thì cộng dồn `so_lan`, không đẻ dòng mới. Màn /ops tab "Lỗi & cảnh
báo" đọc ở đây; bộ canh gác (`canh_gac.py`) báo khi có kiểu lỗi MỚI.

Ba luật không được phá:
  1. GHI LỖI KHÔNG ĐƯỢC LÀM HỎNG THÊM: trần 0,5 giây, nuốt mọi lỗi của chính nó.
     Đang 500 vì DB chậm mà ghi lỗi lại chờ DB thì người dùng chờ gấp đôi.
  2. KHÔNG DỮ LIỆU KHÁCH: thông điệp qua bộ che (SĐT, email, token) + cắt phần
     giá trị Postgres kèm theo (`Key (full_name)=(Nguyễn Văn A)` → `=(…)`), tối
     đa 200 ký tự. Vị trí là route TEMPLATE, không phải đường dẫn đã điền.
  3. DẤU VÂN KHÔNG CÓ SỐ DÒNG: sửa code thêm một dòng phía trên không được biến
     một lỗi cũ thành "lỗi mới".
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import traceback
from typing import Any

import asyncpg
import structlog

from clinicai.core.logging import _redact_text

logger = structlog.get_logger()

TRAN_GIAY = 0.5
DAI_TOI_DA = 200
_GIA_TRI_PG = re.compile(r"=\([^)]*\)")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)


def thong_diep_sach(exc: BaseException) -> str:
    """Thông điệp lỗi đã che dữ liệu khách, gọn ≤ 200 ký tự."""
    chu = _redact_text(str(exc))
    chu = _GIA_TRI_PG.sub("=(…)", chu)
    chu = _UUID.sub(":id", chu)
    chu = " ".join(chu.split())
    return chu[:DAI_TOI_DA]


def khung_code(exc: BaseException) -> str:
    """Khung SÂU NHẤT trong code của mình (`clinicai/…:hàm`), không số dòng."""
    khung = ""
    for f in traceback.extract_tb(exc.__traceback__):
        ten = f.filename.replace("\\", "/")
        if "/clinicai/" in ten:
            khung = f"{ten.split('/clinicai/', 1)[1]}:{f.name}"
    return khung


def dau_van(nguon: str, vi_tri: str, exc: BaseException) -> str:
    """Dấu vân của một KIỂU lỗi — cùng kiểu thì cộng dồn."""
    goc = f"{nguon}|{vi_tri}|{type(exc).__name__}|{khung_code(exc)}"
    return hashlib.sha1(goc.encode()).hexdigest()[:20]


async def _ghi(
    pool: asyncpg.Pool,
    *,
    nguon: str,
    vi_tri: str,
    kieu: str,
    dv: str,
    thong_diep: str,
    ma_yeu_cau: str | None,
) -> None:
    await pool.execute(
        """
        INSERT INTO loi_nhom (nguon, dau_van, vi_tri, kieu, thong_diep, ma_yeu_cau)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (nguon, dau_van) DO UPDATE
           SET so_lan = loi_nhom.so_lan + 1,
               lan_cuoi = now(),
               thong_diep = EXCLUDED.thong_diep,
               ma_yeu_cau = coalesce(EXCLUDED.ma_yeu_cau, loi_nhom.ma_yeu_cau),
               -- Đã sửa mà còn tái diễn = lỗi quay lại: mở lại cho người trực thấy.
               trang_thai = CASE WHEN loi_nhom.trang_thai = 'DA_SUA'
                                 THEN 'MOI' ELSE loi_nhom.trang_thai END
        """,
        nguon,
        dv,
        vi_tri[:200],
        kieu[:100],
        thong_diep,
        ma_yeu_cau,
    )


async def ghi_loi(
    pool: asyncpg.Pool | None,
    *,
    nguon: str,
    vi_tri: str,
    exc: BaseException,
    ma_yeu_cau: str | None = None,
) -> None:
    """Ghi một lỗi vào kho. KHÔNG BAO GIỜ ném, trần 0,5 giây."""
    if pool is None:
        return
    try:
        await asyncio.wait_for(
            _ghi(
                pool,
                nguon=nguon,
                vi_tri=vi_tri,
                kieu=type(exc).__name__,
                dv=dau_van(nguon, vi_tri, exc),
                thong_diep=thong_diep_sach(exc),
                ma_yeu_cau=ma_yeu_cau,
            ),
            timeout=TRAN_GIAY,
        )
    except Exception as loi:  # noqa: BLE001 — ghi lỗi không được sinh lỗi mới
        logger.warning("kho_loi_ghi_hong", ly_do=type(loi).__name__)


async def ghi_loi_web(
    pool: asyncpg.Pool,
    *,
    vi_tri: str,
    kieu: str,
    thong_diep: str,
) -> None:
    """Lỗi trình duyệt / server Next gửi về (đã qua proxy). Cùng luật che."""
    sach = _GIA_TRI_PG.sub("=(…)", _redact_text(thong_diep))
    sach = _UUID.sub(":id", " ".join(sach.split()))[:DAI_TOI_DA]
    vi = _UUID.sub(":id", vi_tri.split("?", 1)[0])[:200]
    dv = hashlib.sha1(f"web|{vi}|{kieu}|{sach[:80]}".encode()).hexdigest()[:20]
    try:
        await asyncio.wait_for(
            _ghi(
                pool,
                nguon="web",
                vi_tri=vi,
                kieu=kieu[:100] or "Error",
                dv=dv,
                thong_diep=sach,
                ma_yeu_cau=None,
            ),
            timeout=TRAN_GIAY,
        )
    except Exception as loi:  # noqa: BLE001
        logger.warning("kho_loi_ghi_hong", ly_do=type(loi).__name__)


async def danh_sach(
    pool: asyncpg.Pool, *, chi_mo: bool = False, gioi_han: int = 100
) -> list[dict[str, Any]]:
    """Các kiểu lỗi, mới nhất trước (cho /ops)."""
    rows = await pool.fetch(
        """
        SELECT l.id::text, l.nguon, l.vi_tri, l.kieu, l.thong_diep, l.so_lan,
               l.lan_dau, l.lan_cuoi, l.ma_yeu_cau, l.trang_thai, l.doi_luc,
               s.full_name AS doi_boi
          FROM loi_nhom l LEFT JOIN staff s ON s.id = l.doi_boi
         WHERE NOT $1::boolean OR l.trang_thai IN ('MOI', 'DA_BIET')
         ORDER BY l.lan_cuoi DESC
         LIMIT $2
        """,
        chi_mo,
        gioi_han,
    )
    return [
        {
            **dict(r),
            "lan_dau": r["lan_dau"].isoformat(),
            "lan_cuoi": r["lan_cuoi"].isoformat(),
            "doi_luc": r["doi_luc"].isoformat() if r["doi_luc"] else None,
        }
        for r in rows
    ]


TRANG_THAI = ("MOI", "DA_BIET", "DA_SUA", "BO_QUA")


async def doi_trang_thai(
    pool: asyncpg.Pool, *, loi_id: str, trang_thai: str, staff_id: str
) -> bool:
    if trang_thai not in TRANG_THAI:
        return False
    kq = await pool.execute(
        "UPDATE loi_nhom SET trang_thai = $2, doi_luc = now(), doi_boi = $3::uuid"
        " WHERE id = $1::uuid",
        loi_id,
        trang_thai,
        staff_id,
    )
    return str(kq).endswith(" 1")
