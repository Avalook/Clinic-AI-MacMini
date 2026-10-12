"""Quyết định phạm vi ca từ lịch đã duyệt; không tin ca do client tự chọn."""

from collections.abc import Iterable, Mapping
from typing import Any

CAC_CA = frozenset({"SANG", "CHIEU", "TOI"})


def ca_duoc_xem(
    lich: Iterable[Mapping[str, Any]], *, truong_ca_ca_ngay: bool
) -> frozenset[str]:
    """Đầu vào phải là lịch đúng tenant/nhân viên/ngày đã khóa tại truy vấn.

    FULL cho phép cả ngày và từng ca con. Trưởng ca được cả ngày chỉ khi
    có lịch trưởng ca đã duyệt trong chính ngày đang hỏi.
    """
    rows = tuple(r for r in lich if r.get("status") == "APPROVED")
    full = any(
        r.get("shift") == "FULL"
        or (truong_ca_ca_ngay and r.get("la_truong_ca") is True)
        for r in rows
    )
    if full:
        return CAC_CA | {"FULL"}
    return frozenset(str(r["shift"]) for r in rows if r.get("shift") in CAC_CA)


def cho_phep_ca(ca: str | None, duoc_xem: frozenset[str]) -> bool:
    """Rỗng là cả ngày; mã ca không hợp lệ luôn từ chối, không fallback."""
    return (ca or "FULL") in duoc_xem
