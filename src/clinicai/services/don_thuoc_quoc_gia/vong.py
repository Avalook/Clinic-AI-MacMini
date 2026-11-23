"""Một vòng liên thông đơn thuốc quốc gia trong worker `su-kien`.

Worker gọi `nhip_trong_worker` mỗi vòng; nó chỉ chạy `mot_vong_dtqg` khi
`cau_hinh.da_bat()` và tới nhịp — công tắc tắt thì không chạy một câu SQL nào.
Bật mà cấu hình sai → không gửi gì, mở cảnh báo `DTQG_CAU_HINH_SAI` để người
trực thấy ở /ops thay vì im lặng.

Canh gác (cùng bảng `canh_bao`, cùng kênh Telegram ops — chỉ SỐ ĐẾM, không tên
khách):
  · DTQG_TON_DONG  đơn chờ gửi quá `TON_DONG_PHUT` phút (mạng / hệ thống quốc gia hỏng)
  · DTQG_LOI       đơn dừng hẳn (thiếu dữ liệu, bị từ chối, hết lượt thử)
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import asyncpg
import structlog

from clinicai.ports.don_thuoc_quoc_gia import DonThuocQuocGiaProvider, KySoDonThuoc
from clinicai.services import canh_gac
from clinicai.services.canh_gac import KetQuaKiem
from clinicai.services.don_thuoc_quoc_gia.cau_hinh import (
    CauHinh,
    da_bat,
    doc_cau_hinh_dtqg,
)
from clinicai.services.don_thuoc_quoc_gia.gui import gui_den_han
from clinicai.services.don_thuoc_quoc_gia.hang_cho import vao_hang_don_thuoc

logger = structlog.get_logger()

#: Nhịp trong vòng su-kien (giây).
NHIP_GIAY = 60
TON_DONG_PHUT = 30

_SO_SQL = """
SELECT
  count(*) FILTER (WHERE public.dtqg_trang_thai(g) = 'CHO_GUI'
                     AND g.tao_luc < now() - make_interval(mins => $2::int))
    AS ton_dong,
  count(*) FILTER (WHERE public.dtqg_trang_thai(g) = 'LOI') AS loi
  FROM public.dtqg_gui g
 WHERE g.clinic_id = $1::uuid
   AND g.da_gui_luc IS NULL
   AND g.tao_luc > now() - make_interval(days => $3::int)
"""
#: Đơn LOI chỉ giữ cảnh báo mở chừng này ngày — không có màn "đã xử lý", nên
#: không giới hạn thì một đơn gỡ hết sau khi gửi giữ cảnh báo mở mãi mãi.
LOI_TRONG_NGAY = 7


def danh_gia_canh_bao_dtqg(so: Mapping[str, Any]) -> list[KetQuaKiem]:
    """HÀM THUẦN: số đếm → cảnh báo."""
    loi_cau_hinh: list[str] = list(so.get("loi_cau_hinh") or [])
    ra = [
        KetQuaKiem(
            "DTQG_CAU_HINH_SAI",
            "critical",
            bool(loi_cau_hinh),
            "Liên thông đơn thuốc quốc gia BẬT nhưng cấu hình sai — chưa gửi đơn"
            " nào: " + "; ".join(loi_cau_hinh),
        )
    ]
    if loi_cau_hinh:
        return ra
    ton, loi = int(so.get("ton_dong", 0)), int(so.get("loi", 0))
    ra += [
        KetQuaKiem(
            "DTQG_TON_DONG",
            "warning",
            ton > 0,
            f"{ton} đơn thuốc chờ gửi Hệ thống đơn thuốc quốc gia quá"
            f" {TON_DONG_PHUT} phút.",
        ),
        KetQuaKiem(
            "DTQG_LOI",
            "warning",
            loi > 0,
            f"{loi} đơn thuốc KHÔNG gửi được lên Hệ thống đơn thuốc quốc gia"
            " (thiếu dữ liệu / bị từ chối) — xem docs/LIEN-THONG-DON-THUOC.md.",
        ),
    ]
    return ra


#: Nhà cung cấp + bộ ký số. Service chỉ biết CỔNG; adapter cụ thể do chỗ lắp
#: ráp (`adapters/don_thuoc_quoc_gia/lap_rap.py`) chọn theo cấu hình và truyền vào.
NhaCungCap = tuple[DonThuocQuocGiaProvider, KySoDonThuoc]
DungNhaCungCap = Callable[[CauHinh], "NhaCungCap | None"]


async def mot_vong_dtqg(
    pool: asyncpg.Pool,
    *,
    env: Mapping[str, str] | None = None,
    nha_cung_cap: NhaCungCap | DungNhaCungCap | None = None,
) -> dict[str, Any]:
    """Soát → vào hàng → gửi → canh gác. Không bao giờ ném. Công tắc tắt → về
    ngay, không một câu SQL (worker cũng kiểm trước khi gọi — hai lớp).
    `nha_cung_cap`: một cặp có sẵn, hoặc hàm dựng theo cấu hình (trả None =
    chưa có adapter cho lựa chọn ấy → cảnh báo cấu hình)."""
    if not da_bat(env):
        return {"tat": True}
    ket: dict[str, Any] = {"vao_hang": 0, "da_gui": 0}
    try:
        ch = doc_cau_hinh_dtqg(env)
        if isinstance(ch, list):
            ket["loi_cau_hinh"] = ch
            await canh_gac.ap_dung(pool, danh_gia_canh_bao_dtqg(ket))
            return ket
        ncc = nha_cung_cap(ch) if callable(nha_cung_cap) else nha_cung_cap
        if ncc is None:
            ket["loi_cau_hinh"] = [f"chưa có adapter cho '{ch.nha_cung_cap}'"]
            await canh_gac.ap_dung(pool, danh_gia_canh_bao_dtqg(ket))
            return ket
        provider, ky_so = ncc
        ket["vao_hang"] = await vao_hang_don_thuoc(pool, ch)
        ket["da_gui"] = await gui_den_han(pool, ch, provider, ky_so)
        r = await pool.fetchrow(_SO_SQL, ch.clinic_id, TON_DONG_PHUT, LOI_TRONG_NGAY)
        ket.update(dict(r) if r else {})
        await canh_gac.ap_dung(pool, danh_gia_canh_bao_dtqg(ket))
    except Exception:  # noqa: BLE001 — một vòng hỏng không được làm chết su-kien
        logger.exception("dtqg_vong_hong")
    return ket


#: Lần cuối `nhip_trong_worker` chạy một vòng (giây đơn điệu, trong tiến trình).
_lan_chay = 0.0


async def nhip_trong_worker(
    pool: asyncpg.Pool, *, canh: bool, dung: DungNhaCungCap
) -> None:
    """Worker `su-kien` gọi mỗi vòng (qua chỗ lắp ráp). Chỉ tiến trình giao MỌI
    bên nhận (`canh`) mới chạy; công tắc `DTQG_BAT` tắt → về ngay, không một câu
    SQL; chưa tới `NHIP_GIAY` → về ngay. Không bao giờ ném."""
    global _lan_chay
    if not canh or not da_bat() or time.monotonic() - _lan_chay < NHIP_GIAY:
        return
    _lan_chay = time.monotonic()
    await mot_vong_dtqg(pool, nha_cung_cap=dung)


__all__ = [
    "NHIP_GIAY",
    "DungNhaCungCap",
    "NhaCungCap",
    "danh_gia_canh_bao_dtqg",
    "mot_vong_dtqg",
    "nhip_trong_worker",
]
