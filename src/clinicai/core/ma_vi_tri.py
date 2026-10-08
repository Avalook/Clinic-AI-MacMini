"""Mã vị trí làm việc của cơ sở thứ hai trở đi → "mã mẫu" Kim Ngưu.

Vài bảng tra viết cứng theo mã vị trí Kim Ngưu (`VAI_THEO_VI_TRI`,
`MA_CA_KHAM_BAC_SI`, `NHOM_THEO_VI_TRI` ở nav-items.ts). `vi_tri_lam_viec.code`
và `work_roster.station` là duy nhất TOÀN phòng khám và không có cột cơ sở, nên
cơ sở mới (Hào Nam, 08/10/2026) mang mã có tiền tố cơ sở:

    HN__T1_LETAN        → T1_LETAN
    HN__T1_THUNGAN__2   → T1_THUNGAN   (bản thứ hai của cùng vị trí mẫu)

Tra bảng nào theo mã thì tra qua `ma_mau()`. Bản TS y hệt: `lib/ma-vi-tri.ts`.
"""

from __future__ import annotations

import re

_TIEN_TO = re.compile(r"^[A-Z0-9]+__")
_HAU_TO = re.compile(r"__\d+$")


def ma_mau(ma: str) -> str:
    """Bỏ tiền tố cơ sở `XX__` và hậu tố bản sao `__n`; mã Kim Ngưu giữ nguyên."""
    return _HAU_TO.sub("", _TIEN_TO.sub("", ma))
