"""Đọc ô nhập bàn xét nghiệm đối tác — thuần, rác → 422 (luật backend)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from typing import Any

from clinicai.api.exceptions import ValidationError

_DRIVE_RE = re.compile(r"(?:folders/|id=)([A-Za-z0-9_-]{10,200})")

#: Trần một khoản thu hộ — chặn gõ thừa số 0 (100.000.000 đồng / một việc).
SO_TIEN_TOI_DA = 100_000_000


def doc_so_tien(value: Any) -> int | None:
    """Số tiền thu hộ. Rác / âm / quá trần → None, không ném. Nhận số nguyên, chuỗi
    có dấu chấm / phẩy / khoảng trắng / "đ" ("900.000đ"). Chuyển từ
    `doi_tac_service.py` (đóng băng) sang đây 05/11/2026 — bàn cũ import lại."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        so = value
    elif isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        if value != int(value):
            return None
        so = int(value)
    elif isinstance(value, str):
        chu = value.strip().lower().replace("đ", "").replace("vnd", "")
        for k in (".", ",", " ", "\u00a0", "_"):  # \u00a0 = khoảng trắng không ngắt
            chu = chu.replace(k, "")
        if not chu.isdigit():
            return None
        so = int(chu)
    else:
        return None
    if so < 0 or so > SO_TIEN_TOI_DA:
        return None
    return so


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


_EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")
_MA_BEN_DT_RE = re.compile(r"[A-Z0-9][A-Z0-9_.-]{0,39}")


def doc_email(raw: object) -> str | None:
    """Email phòng xét nghiệm gửi kết quả (Gmail G4). Rỗng → None; chữ thường; sai
    dạng → 422 (CHECK của DB chỉ là chốt cuối, không để lọt thành 500)."""
    s = raw.strip().lower() if isinstance(raw, str) else ""
    if not s:
        return None
    if not (6 <= len(s) <= 254 and _EMAIL_RE.fullmatch(s)):
        raise ValidationError("Email gửi kết quả: nhập đúng dạng ten@mien.vn.")
    return s


def doc_ma_ben_doi_tac(raw: object) -> str | None:
    """Mã xét nghiệm phía đối tác (vd HPV, THINPREP) — chữ hoa, không khoảng trắng.
    Rỗng → None; sai dạng → 422."""
    s = raw.strip().upper() if isinstance(raw, str) else ""
    if not s:
        return None
    if not _MA_BEN_DT_RE.fullmatch(s):
        raise ValidationError(
            "Mã bên đối tác: chữ hoa / số / . _ - , tối đa 40 ký tự (vd HPV)."
        )
    return s


def doc_ngay_moc(raw: object, hom_nay: date) -> date | None:
    """Mốc "tự ghép kết quả email từ ngày". Rỗng → None (chưa tự ghép); rác hoặc
    ngày tương lai → 422 (không 500)."""
    s = raw.strip() if isinstance(raw, str) else ""
    if not s:
        return None
    try:
        d = date.fromisoformat(s)
    except ValueError:
        raise ValidationError("Ngày tự ghép: chọn một ngày (YYYY-MM-DD).") from None
    if d > hom_nay:
        raise ValidationError("Ngày tự ghép không được ở tương lai.")
    return d


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
        # Chữ tự do (ngân hàng · số · tên) — chỉ để bàn XN hiện "Chuyển khoản vào: …".
        "tai_khoan_nhan_ck": _chu(
            raw.get("tai_khoan_nhan_ck"),
            "Tài khoản nhận chuyển khoản",
            200,
            bat_buoc=False,
        ),
        "drive_folder_id": doc_drive(raw.get("drive_folder")),
        "hen_tra": doc_so_ngay(raw.get("hen_tra_so_ngay_mac_dinh")),
        "email_gui_ket_qua": doc_email(raw.get("email_gui_ket_qua")),
    }


def doc_ly_do(raw: object) -> str:
    s = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not 3 <= len(s) <= 2000:
        raise ValidationError("Nhập lý do (ít nhất 3 ký tự).")
    return s
