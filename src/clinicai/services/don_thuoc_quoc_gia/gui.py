"""Hàng chờ đơn thuốc quốc gia — GỬI (rút hàng).

Chạy ngoài giao dịch đã sinh ra việc, nên quầy / bàn khám không bao giờ chờ hệ
thống quốc gia. Mỗi lượt chỉ PHIÊN BẢN MỚI NHẤT được gửi (bản cũ chưa gửi = bị
thay). Mỗi phiên bản là một đơn với mã riêng; phiên bản sau một bản đã gửi là đơn
thay thế (QĐ 425 Điều 9: đơn đã gửi không sửa được).

Đơn GỠ HẾT sau khi đã gửi: API không có lệnh huỷ (QĐ 808) — dòng dừng ở LOI với
câu giải thích, canh gác mở cảnh báo để người xử lý ngoài hệ thống. Không giả vờ
đã huỷ.

Dòng được giữ bằng ``FOR UPDATE SKIP LOCKED`` trong giao dịch của lần gửi — hai
worker không gửi trùng. Lỗi thử lại được thì lùi theo cấp số (1′, 5′, 25′, ~2 giờ,
~10 giờ…) tới `so_lan_thu`; lỗi nội dung (thiếu trường, hệ thống từ chối) dừng
ngay — kết cục LOI là thật thà: có người phải xem.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import asyncpg
import structlog

from clinicai.ports.don_thuoc_quoc_gia import (
    DonThuocQuocGiaProvider,
    GuiDonError,
    KetQuaGui,
    KySoDonThuoc,
)
from clinicai.services.don_thuoc_quoc_gia.anh_xa import goi_tu_json, thieu_truong
from clinicai.services.don_thuoc_quoc_gia.cau_hinh import CauHinh

logger = structlog.get_logger()

LO_GUI = 50
TRE_GOC_GIAY = 60
HE_SO_TRE = 5
#: Lỗi lưu lại cắt ở chừng này ký tự (cột giới hạn 500).
DAI_LOI = 400
GO_HET_SAU_KHI_GUI = (
    "DON_DA_GUI_BI_GO_HET: đơn đã lên hệ thống quốc gia mà bác sĩ gỡ hết thuốc —"
    " API không có lệnh huỷ; báo người bệnh / xử lý trên donthuocquocgia.vn"
)


def tre_lan_sau(so_lan_da_thu: int) -> timedelta:
    """HÀM THUẦN: chờ bao lâu trước lần thử kế tiếp (sau `so_lan_da_thu` lần hỏng)."""
    mu = max(so_lan_da_thu - 1, 0)
    return timedelta(seconds=TRE_GOC_GIAY * HE_SO_TRE**mu)


# Dòng tới hạn: phiên bản mới nhất của lượt, chưa gửi, chưa dừng, tới giờ thử, và
# không phải "đơn gỡ hết của lượt chưa từng gửi" (KHONG_CAN — không có gì để làm).
_DEN_HAN_SQL = """
SELECT g.id, g.goi, g.la_huy, g.so_lan_thu
  FROM public.dtqg_gui g
 WHERE g.clinic_id = $1::uuid
   AND g.da_gui_luc IS NULL AND g.het_luot_luc IS NULL
   AND g.thu_lai_luc <= now()
   AND NOT EXISTS (SELECT 1 FROM public.dtqg_gui m
                    WHERE m.clinic_id = g.clinic_id AND m.visit_id = g.visit_id
                      AND m.phien_ban > g.phien_ban)
   AND (NOT g.la_huy OR EXISTS (
            SELECT 1 FROM public.dtqg_gui s
             WHERE s.clinic_id = g.clinic_id AND s.visit_id = g.visit_id
               AND s.phien_ban < g.phien_ban AND s.da_gui_luc IS NOT NULL))
 ORDER BY g.thu_lai_luc, g.tao_luc
 LIMIT 1
 FOR UPDATE OF g SKIP LOCKED
"""


async def _goi_api(
    provider: DonThuocQuocGiaProvider,
    ky_so: KySoDonThuoc,
    row: asyncpg.Record,
) -> KetQuaGui:
    if row["la_huy"]:
        raise GuiDonError(GO_HET_SAU_KHI_GUI, thu_lai=False)
    tho: dict[str, Any] = (
        json.loads(row["goi"]) if isinstance(row["goi"], str) else row["goi"]
    )
    goi = goi_tu_json(tho)
    thieu = thieu_truong(goi) + provider.thieu(goi)
    if thieu:
        raise GuiDonError("THIEU_DU_LIEU: " + ", ".join(thieu), thu_lai=False)
    chu_ky = await ky_so.ky(
        json.dumps(tho, ensure_ascii=False, sort_keys=True).encode()
    )
    return await provider.gui(goi, chu_ky)


async def _ghi_ket_qua(
    conn: asyncpg.Connection,
    ch: CauHinh,
    row: asyncpg.Record,
    provider: DonThuocQuocGiaProvider,
    ket_qua: KetQuaGui | GuiDonError,
) -> bool:
    if isinstance(ket_qua, GuiDonError):
        lan = row["so_lan_thu"] + 1
        het = (not ket_qua.thu_lai) or lan >= ch.so_lan_thu
        await conn.execute(
            "UPDATE public.dtqg_gui SET so_lan_thu = $3, loi_cuoi = $4,"
            " thu_lai_luc = now() + $5::interval,"
            " het_luot_luc = CASE WHEN $6 THEN now() END"
            " WHERE clinic_id = $1::uuid AND id = $2",
            ch.clinic_id,
            row["id"],
            lan,
            str(ket_qua)[:DAI_LOI],
            tre_lan_sau(lan),
            het,
        )
        # Log chỉ MÃ lỗi (phần trước dấu ":") — câu hệ thống ngoài trả về có thể
        # chép dữ liệu khách; câu đủ nằm ở `loi_cuoi` (che trên staging).
        ma_loi = str(ket_qua).split(":", 1)[0][:60]
        logger.warning("dtqg_gui_loi", lan=lan, het_luot=het, ma_loi=ma_loi)
        return False
    await conn.execute(
        "UPDATE public.dtqg_gui SET so_lan_thu = so_lan_thu + 1, da_gui_luc = now(),"
        " ma_tra_ve = $3, nha_cung_cap = $4, loi_cuoi = NULL"
        " WHERE clinic_id = $1::uuid AND id = $2",
        ch.clinic_id,
        row["id"],
        (ket_qua.ma_tra_ve or "")[:200] or None,
        provider.ten,
    )
    return True


async def gui_den_han(
    pool: asyncpg.Pool,
    ch: CauHinh,
    provider: DonThuocQuocGiaProvider,
    ky_so: KySoDonThuoc,
) -> int:
    """Gửi các dòng tới hạn (tối đa `LO_GUI`). Trả số dòng gửi thành công."""
    da_gui = 0
    async with pool.acquire() as conn:
        for _ in range(LO_GUI):
            async with conn.transaction():
                row = await conn.fetchrow(_DEN_HAN_SQL, ch.clinic_id)
                if row is None:
                    break
                try:
                    kq: KetQuaGui | GuiDonError = await _goi_api(provider, ky_so, row)
                except GuiDonError as e:
                    kq = e
                except Exception as e:  # noqa: BLE001 — lỗi lạ = lỗi mạng, thử lại
                    kq = GuiDonError(f"{type(e).__name__}: {e}")
                da_gui += await _ghi_ket_qua(conn, ch, row, provider, kq)
    return da_gui


__all__ = ["GO_HET_SAU_KHI_GUI", "gui_den_han", "tre_lan_sau"]
