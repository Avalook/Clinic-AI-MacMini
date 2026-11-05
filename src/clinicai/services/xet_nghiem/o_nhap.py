"""Đọc ô nhập bàn xét nghiệm đối tác — thuần, rác → 422 (luật backend)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from clinicai.api.exceptions import ValidationError
from clinicai.services.doi_tac_service import doc_so_tien

_DRIVE_RE = re.compile(r"(?:folders/|id=)([A-Za-z0-9_-]{10,200})")


def _chu(raw: object, ten: str, toi_da: int, *, bat_buoc: bool = True) -> str | None:
    s = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not s:
        if bat_buoc:
            raise ValidationError(f"{ten}: bắt buộc.")
        return None
    if len(s) > toi_da:
        raise ValidationError(f"{ten}: tối đa {toi_da} ký tự.")
    return s


def doc_so_ngay(raw: object, ten: str = "Số ngày hẹn trả") -> int | None:
    """Rỗng → None. Số nguyên 0–90. Rác → 422 (không 500)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        n = int(str(raw).strip())
    except ValueError:
        raise ValidationError(f"{ten}: nhập số ngày 0–90.") from None
    if not 0 <= n <= 90:
        raise ValidationError(f"{ten}: nhập số ngày 0–90.")
    return n


def doc_tien(raw: object, ten: str = "Giá gợi ý") -> int | None:
    """Rỗng → None. Có chữ mà không đọc được → 422. Luật đọc số: `doc_so_tien`."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    so = doc_so_tien(raw)
    if so is None:
        raise ValidationError(f"{ten}: nhập số tiền (VND), không âm.")
    return so


def doc_drive(raw: object) -> str | None:
    """Link thư mục Drive hoặc id → id. Không nhận link công khai dạng khác."""
    s = raw.strip() if isinstance(raw, str) else ""
    if not s:
        return None
    m = _DRIVE_RE.search(s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{10,200}", s):
        return s
    raise ValidationError(
        "Thư mục Drive: dán link thư mục (…/folders/…) hoặc mã thư mục."
    )


def doc_form_doi_tac(raw: Mapping[str, Any]) -> dict[str, Any]:
    ma = raw.get("ma_ngan")
    ma_s = ma.strip().upper() if isinstance(ma, str) else ""
    if not re.fullmatch(r"[A-Z0-9]{2,10}", ma_s):
        raise ValidationError("Mã ngắn: 2–10 chữ hoặc số, không dấu (ví dụ MED).")
    return {
        "ten": _chu(raw.get("ten"), "Tên đối tác", 120),
        "ma_ngan": ma_s,
        "sdt": _chu(raw.get("sdt"), "Số điện thoại", 30, bat_buoc=False),
        "ghi_chu": _chu(raw.get("ghi_chu"), "Ghi chú", 2000, bat_buoc=False),
        "drive_folder_id": doc_drive(raw.get("drive_folder")),
        "hen_tra": doc_so_ngay(raw.get("hen_tra_so_ngay_mac_dinh")),
    }


def doc_ly_do(raw: object) -> str:
    s = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not 3 <= len(s) <= 2000:
        raise ValidationError("Nhập lý do (ít nhất 3 ký tự).")
    return s
