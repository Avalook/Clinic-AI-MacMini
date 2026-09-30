"""Dọn ổ tệp kết quả HẰNG NGÀY (V9, 30/09/2026) — chạy trong vòng `su-kien`.

Hai việc, cả hai chỉ làm khi CHẮC CHẮN đang nhìn đúng kho:

  1. Tệp kết quả đã XOÁ MỀM quá 30 ngày VÀ chưa từng được xem / duyệt / gửi
     khách / đính chính → xoá tệp vật lý, ghi `da_don_tep_luc` (từ đây không
     khôi phục được). Tệp đã vào hồ sơ (có người xem, bác sĩ duyệt, đã gửi
     khách) thì CHỈ ẨN, không bao giờ dọn — khách có thể đang cầm bản in.
  2. Tệp tạm sót `MEDIA_ROOT/.tam/*.part` cũ hơn 1 ngày — ổ treo giữa lúc tải
     lên để lại (log `kho_tep_bo_qua_don`).

MỌI thao tác chạm ổ đi qua `chay_tren_kho` (luồng phụ, có hạn giờ, ngắt mạch —
sự cố treo API 29/09). Ổ chậm / lỗi: dừng lượt này, lần sau làm tiếp; không
bao giờ ném ra ngoài làm chết vòng giao tin.

KHO CHƯA GẮN THÌ KHÔNG LÀM GÌ. Service `su-kien` hiện KHÔNG gắn ổ media
(docker-compose.yml). Chạy ở đó mà không kiểm, tiến trình sẽ thấy "tệp không
còn" ở mọi dòng và ghi nhầm "đã dọn" cho tệp vẫn nằm trên ổ thật. Nên chỉ chạy
khi: biến `MEDIA_ROOT` được ĐẶT, thư mục tồn tại, và (nếu có `MEDIA_MARKER`)
tệp đánh dấu có mặt.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import asyncpg
import structlog

from clinicai.core.exceptions import ExternalServiceError
from clinicai.core.kho_tep import chay_tren_kho
from clinicai.services.media_service import MEDIA_ROOT

logger = structlog.get_logger()

#: Một lượt mỗi ngày (tính từ lúc tiến trình khởi động; khởi động lại thì chạy
#: lại — lượt nào cũng làm lại được, không hại).
NHIP_GIAY = 24 * 3600
#: Tệp đã xoá bao lâu mới dọn — trùng hạn khôi phục.
SO_NGAY_DON = 30
#: Tệp tạm `.part` cũ hơn bấy nhiêu giây là tệp sót.
TAM_CU_GIAY = 24 * 3600
#: Mỗi lượt dọn tối đa bấy nhiêu tệp — lượt sau làm tiếp.
MOI_LUOT = 200
#: Hạn cho một lần quét thư mục tạm (có thể nhiều tệp).
HAN_QUET_TAM_GIAY = 30.0


def kho_san_sang(
    goc: Path | None = None, env: dict[str, str] | None = None
) -> tuple[bool, str]:
    """(được làm, lý do không). Đồng bộ — CHẠY QUA `chay_tren_kho`."""
    moi_truong = os.environ if env is None else env
    if not str(moi_truong.get("MEDIA_ROOT", "")).strip():
        return False, "chua_dat_MEDIA_ROOT"
    goc = goc or MEDIA_ROOT
    if not goc.is_dir():
        return False, "khong_co_thu_muc_MEDIA_ROOT"
    dau = str(moi_truong.get("MEDIA_MARKER", "")).strip()
    if dau and not (goc / dau).is_file():
        return False, "thieu_MEDIA_MARKER"
    return True, ""


def duong_an_toan(goc: Path, clinic_id: str, khoa: str) -> Path | None:
    """Khoá tệp → đường tuyệt đối TRONG kho, đúng phòng khám; sai → None.

    Hàm thuần về chuỗi + `resolve()` (chạm ổ nhẹ) — gọi trong `chay_tren_kho`.
    """
    if not khoa or not khoa.startswith(f"{clinic_id}/"):
        return None
    p = (goc / khoa).resolve()
    if not p.is_relative_to(goc.resolve()):
        return None
    return p


def don_tep_tam(goc: Path, bay_gio: float | None = None) -> int:
    """Xoá `goc/.tam/*.part` cũ hơn 1 ngày. Trả số tệp đã xoá. Đồng bộ."""
    tam = goc / ".tam"
    if not tam.is_dir():
        return 0
    moc = (bay_gio if bay_gio is not None else time.time()) - TAM_CU_GIAY
    so = 0
    for p in tam.glob("*.part"):
        try:
            if p.is_file() and p.stat().st_mtime < moc:
                p.unlink(missing_ok=True)
                so += 1
        except OSError as loi:
            logger.warning("don_tep_tam_loi", tep=p.name, loi=str(loi))
    return so


#: Tệp đủ điều kiện dọn: xoá > 30 ngày, chưa dọn, xoá thường (không phải đính
#: chính), CHƯA từng xem / duyệt cho gửi / gửi khách. Tệp đối tác tự hợp lệ lúc
#: tải lên (người tải = người xác nhận) không tính là "đã duyệt".
_SQL_UNG_VIEN = """
SELECT t.id::text AS id, t.clinic_id::text AS clinic_id, t.khoa
  FROM tep_ket_qua t
 WHERE t.da_xoa_luc IS NOT NULL
   AND t.da_don_tep_luc IS NULL
   AND t.da_xoa_luc < now() - make_interval(days => $1)
   AND t.da_xoa_loai = 'XOA'
   AND t.da_xem_luc IS NULL
   AND t.cho_phep_gui_luc IS NULL
   AND t.gui_luc IS NULL
 ORDER BY t.da_xoa_luc
 LIMIT $2
"""


async def _don_mot_tep(pool: asyncpg.Pool, goc: Path, ung_vien: asyncpg.Record) -> bool:
    """Xoá tệp vật lý + ghi `da_don_tep_luc` trong MỘT giao dịch giữ khoá dòng:
    ai bấm Khôi phục cùng lúc thì chờ, rồi trigger từ chối (đã dọn). Trả True
    nếu đã dọn. Ổ chậm → ExternalServiceError (nơi gọi dừng lượt)."""
    clinic_id = str(ung_vien["clinic_id"])
    async with pool.acquire() as conn, conn.transaction():
        con = await conn.fetchval(
            "SELECT t.khoa FROM tep_ket_qua t"
            " WHERE t.id = $1::uuid AND t.clinic_id = $2::uuid"
            "   AND t.da_xoa_luc IS NOT NULL AND t.da_don_tep_luc IS NULL"
            "   AND t.da_xoa_loai = 'XOA' AND t.da_xem_luc IS NULL"
            "   AND t.cho_phep_gui_luc IS NULL AND t.gui_luc IS NULL"
            "   AND t.da_xoa_luc < now() - make_interval(days => $3)"
            " FOR UPDATE",
            ung_vien["id"],
            clinic_id,
            SO_NGAY_DON,
        )
        if con is None:
            return False  # vừa được khôi phục / đổi trạng thái
        khoa = str(con)

        def _xoa() -> bool:
            p = duong_an_toan(goc, clinic_id, khoa)
            if p is None:
                return False
            p.unlink(missing_ok=True)
            return True

        if not await chay_tren_kho(_xoa):
            logger.error("don_tep_khoa_la", tep_id=ung_vien["id"])
            return False
        await conn.execute(
            "UPDATE tep_ket_qua SET da_don_tep_luc = now()"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            ung_vien["id"],
            clinic_id,
        )
    return True


async def mot_luot(
    pool: asyncpg.Pool,
    *,
    goc: Path | None = None,
    kiem_kho: Callable[[], tuple[bool, str]] | None = None,
) -> dict[str, Any]:
    """Một lượt dọn. KHÔNG BAO GIỜ ném — trả số đếm để ghi log / test."""
    goc = goc or MEDIA_ROOT
    ket_qua: dict[str, Any] = {"da_don": 0, "tam": 0, "bo_qua": None}
    try:
        duoc, vi_sao = await chay_tren_kho(kiem_kho or kho_san_sang)
        if not duoc:
            ket_qua["bo_qua"] = vi_sao
            logger.warning("don_tep_bo_qua_kho_chua_gan", ly_do=vi_sao)
            return ket_qua
        for uv in await pool.fetch(_SQL_UNG_VIEN, SO_NGAY_DON, MOI_LUOT):
            try:
                if await _don_mot_tep(pool, goc, uv):
                    ket_qua["da_don"] += 1
            except ExternalServiceError:
                # Ổ chậm / ngắt mạch: dừng lượt, lần sau làm tiếp.
                ket_qua["bo_qua"] = "kho_cham"
                logger.warning("don_tep_dung_vi_kho_cham", da_don=ket_qua["da_don"])
                break
            except OSError as loi:
                logger.warning("don_tep_loi_o", tep_id=uv["id"], loi=str(loi))
        if ket_qua["bo_qua"] is None:
            ket_qua["tam"] = await chay_tren_kho(
                lambda: don_tep_tam(goc), han=HAN_QUET_TAM_GIAY
            )
    except ExternalServiceError:
        ket_qua["bo_qua"] = "kho_cham"
        logger.warning("don_tep_dung_vi_kho_cham")
    except Exception:  # noqa: BLE001 — không được làm chết vòng giao tin
        ket_qua["bo_qua"] = "loi"
        logger.exception("don_tep_loi")
    logger.info("don_tep_ket_qua_xong", **ket_qua)
    return ket_qua


__all__ = [
    "NHIP_GIAY",
    "SO_NGAY_DON",
    "don_tep_tam",
    "duong_an_toan",
    "kho_san_sang",
    "mot_luot",
]
