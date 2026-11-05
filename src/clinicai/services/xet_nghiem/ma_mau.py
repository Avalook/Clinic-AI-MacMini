"""Mã ống mẫu: `M` + số thứ tự (đệm 5) + 1 chữ số kiểm Damm (kế hoạch 2.B, 4.5).

Cấp số ở Postgres (`cap_ma_mau()` — cùng bảng Damm, test chéo 1.000 số). Python chỉ
ĐỌC/KIỂM mã (tên tệp Drive, ô quét), không cấp. Damm bắt mọi lỗi gõ sai một chữ số và
mọi lỗi đảo hai chữ số liền nhau — đúng hai lỗi hay gặp khi chép mã từ ống.
"""

from __future__ import annotations

import re
from typing import Final

#: Bảng tựa nhóm cấp 10 của Damm (bản chuẩn, Damm 2004).
_DAMM: Final[tuple[tuple[int, ...], ...]] = (
    (0, 3, 1, 7, 5, 9, 8, 6, 4, 2),
    (7, 0, 9, 2, 1, 5, 4, 8, 6, 3),
    (4, 2, 0, 6, 8, 7, 1, 3, 5, 9),
    (1, 7, 5, 0, 9, 8, 3, 4, 2, 6),
    (6, 1, 2, 3, 0, 4, 5, 9, 7, 8),
    (3, 6, 7, 4, 2, 0, 9, 5, 8, 1),
    (5, 8, 6, 9, 7, 2, 0, 1, 3, 4),
    (8, 9, 4, 5, 3, 6, 2, 0, 1, 7),
    (9, 4, 3, 8, 6, 1, 7, 2, 0, 5),
    (2, 5, 8, 1, 4, 3, 6, 7, 9, 0),
)

_MA_RE: Final = re.compile(r"M(\d{6,})")


def chu_so_kiem(so: str) -> int:
    """Chữ số kiểm Damm của chuỗi chữ số `so`."""
    tg = 0
    for c in so:
        tg = _DAMM[tg][int(c)]
    return tg


def tao_ma(so_thu_tu: int) -> str:
    """Số thứ tự → mã đầy đủ. `572 → 'M005724'` (vectơ kiểm của kế hoạch)."""
    than = f"{so_thu_tu:05d}"
    return f"M{than}{chu_so_kiem(than)}"


def ma_hop_le(ma: str) -> bool:
    """Mã đúng dạng và đúng chữ số kiểm. Rác → False, không ném."""
    if not isinstance(ma, str):
        return False
    m = _MA_RE.fullmatch(ma.strip().upper())
    return m is not None and chu_so_kiem(m.group(1)) == 0


def tim_ma_trong_ten(ten: str) -> list[str]:
    """Mọi mã hợp lệ trong một tên tệp (chặng 4 dùng; sai số kiểm bị bỏ)."""
    if not isinstance(ten, str):
        return []
    return [f"M{s}" for s in _MA_RE.findall(ten.upper()) if chu_so_kiem(s) == 0]
