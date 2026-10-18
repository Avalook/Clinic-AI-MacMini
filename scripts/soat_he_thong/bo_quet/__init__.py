"""Các bộ quét tĩnh (tầng 0 — không gọi model, không tốn token, không chạm prod).

Mỗi bộ quét là một module có `TEN` và `quet(nguon) -> (list[PhatHien], DoPhu)`.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from ..khuon import DoPhu, PhatHien
from ..nguon import Nguon

#: Thứ tự chạy = thứ tự hiện trên báo cáo.
DANH_SACH = (
    "quyen_lego",
    "cua_route",
    "ghi_khong_dau_vet",
    "su_kien",
    "day_fe_be",
)

BoQuet = Callable[[Nguon], tuple[list[PhatHien], DoPhu]]


def nap(ten: str) -> BoQuet:
    return import_module(f"{__name__}.{ten}").quet  # type: ignore[no-any-return]
