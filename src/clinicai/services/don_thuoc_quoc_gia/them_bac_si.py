"""Lệnh một lần: thêm bác sĩ vào cơ sở trên Hệ thống đơn thuốc quốc gia.

    python -m clinicai.services.don_thuoc_quoc_gia.them_bac_si <staff_id>

Đọc cấu hình như worker (`DTQG_*`, phải là `DTQG_NHA_CUNG_CAP=that`), lấy mã liên
thông của bác sĩ từ `DTQG_BAC_SI`, mật khẩu CƠ SỞ từ `DTQG_MAT_KHAU_CO_SO` (chỉ
lệnh này cần — không nằm trong cấu hình worker). Gửi ra ngoài: người chạy là
người vận hành, theo docs/LIEN-THONG-DON-THUOC.md bước 4.
"""

from __future__ import annotations

import asyncio
import os
import sys

from clinicai.adapters.don_thuoc_quoc_gia.that import ProviderThat
from clinicai.ports.don_thuoc_quoc_gia import GuiDonError
from clinicai.services.don_thuoc_quoc_gia.cau_hinh import THAT, CauHinh, doc_cau_hinh


def chuan_bi(argv: list[str], env: dict[str, str]) -> tuple[CauHinh, str, str] | str:
    """HÀM THUẦN: (cấu hình, mã bác sĩ, mật khẩu cơ sở) hoặc câu lỗi."""
    if len(argv) != 1:
        return "Cách dùng: python -m " + __name__ + " <staff_id>"
    ch = doc_cau_hinh(env)
    if isinstance(ch, list):
        return "Cấu hình sai: " + "; ".join(ch)
    if ch.nha_cung_cap != THAT:
        return "Chỉ dùng với DTQG_NHA_CUNG_CAP=that"
    tk = ch.bac_si.get(argv[0].lower())
    if tk is None:
        return "staff_id này chưa có trong DTQG_BAC_SI"
    mk = env.get("DTQG_MAT_KHAU_CO_SO", "").strip()
    if not mk:
        return "Thiếu DTQG_MAT_KHAU_CO_SO"
    return ch, tk.ma_lien_thong, mk


async def _chay(ch: CauHinh, ma_bs: str, mk: str) -> str:
    p = ProviderThat(
        url=ch.url, ma_lien_thong_co_so=ch.ma_lien_thong_co_so or "", mat_khau_bac_si={}
    )
    return await p.them_bac_si(ma_bs, mk)


def main() -> int:
    kq = chuan_bi(sys.argv[1:], dict(os.environ))
    if isinstance(kq, str):
        print(kq, file=sys.stderr)
        return 2
    try:
        print(asyncio.run(_chay(*kq)))
    except GuiDonError as e:
        print(f"Không thêm được: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
