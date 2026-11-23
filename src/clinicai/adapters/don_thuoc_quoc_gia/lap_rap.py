"""Chỗ LẮP RÁP liên thông đơn thuốc quốc gia: chọn adapter theo cấu hình rồi cắm
vào hàng chờ.

Service (`services/don_thuoc_quoc_gia`) chỉ biết CỔNG (`ports/don_thuoc_quoc_gia`),
không nhắc tên adapter nào — `test_pos_port.TestBoundary` canh điều đó. Worker
`su-kien` gọi `nhip_worker` ở đây; công tắc `DTQG_BAT` tắt thì không chạy một câu
SQL nào (kiểm trong `vong.nhip_trong_worker`).
"""

from __future__ import annotations

import asyncpg

from clinicai.adapters.don_thuoc_quoc_gia.gia_lap import KhongKy, ProviderGiaLap
from clinicai.services.don_thuoc_quoc_gia.cau_hinh import GIA_LAP, CauHinh
from clinicai.services.don_thuoc_quoc_gia.vong import NhaCungCap, nhip_trong_worker

# Dùng chung một bản trong tiến trình (giả lập nhớ đơn đã nhận giữa các vòng).
_GIA_LAP = ProviderGiaLap()


def dung_nha_cung_cap(ch: CauHinh) -> NhaCungCap | None:
    """Nhà cung cấp + bộ ký số theo cấu hình (đã kiểm ở `doc_cau_hinh_dtqg`);
    None = chưa có adapter cho lựa chọn ấy (hệ thống thật: PR kế tiếp)."""
    if ch.nha_cung_cap == GIA_LAP:
        return _GIA_LAP, KhongKy()
    return None


async def nhip_worker(pool: asyncpg.Pool, *, canh: bool) -> None:
    """Worker `su-kien` gọi mỗi vòng — xem `vong.nhip_trong_worker`."""
    await nhip_trong_worker(pool, canh=canh, dung=dung_nha_cung_cap)


__all__ = ["dung_nha_cung_cap", "nhip_worker"]
