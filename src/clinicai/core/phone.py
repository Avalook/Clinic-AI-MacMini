"""Vietnamese phone normalization shared by validation and MPI deduplication."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import phonenumbers

LOI_SDT = "Số này không phải số VN — chọn nước khác hoặc bắt đầu bằng +."


@dataclass(frozen=True)
class SoDienThoai:
    so: str
    loai: Literal["DI_DONG", "CO_DINH", "QUOC_TE"]


def chuan_hoa_sdt(raw: object, quoc_gia: str = "VN") -> SoDienThoai | None:
    """Invalid user input returns None; only foreign numbers use the library."""
    if not isinstance(raw, str) or not raw or len(raw) > 100:
        return None
    if re.search(r"[^0-9\s()+.\-]", raw):
        return None
    text = re.sub(r"[\s().\-]", "", raw)
    if text.startswith("00"):
        text = "+" + text[2:]
    if "+" in text[1:] or not text:
        return None
    vn = text.startswith("+84") or (not text.startswith("+") and quoc_gia == "VN")
    if vn:
        digits = text.removeprefix("+")
        if digits.startswith("84"):
            digits = "0" + digits[2:]
        elif len(digits) == 9 and not digits.startswith("0"):
            digits = "0" + digits
        if re.fullmatch(r"0[0-9]{9}", digits) is None:
            return None
        if digits[:2] in _VN_MOBILE_PREFIXES:
            return SoDienThoai(digits, "DI_DONG")
        if digits.startswith("02"):
            return SoDienThoai(digits, "CO_DINH")
        return None
    try:
        number = phonenumbers.parse(text, quoc_gia)
        if number.country_code == 84:
            return chuan_hoa_sdt("+84" + str(number.national_number))
        if not phonenumbers.is_valid_number(number):
            return None
        so = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
        if re.fullmatch(r"\+[1-9][0-9]{7,14}", so) is None:
            return None
        return SoDienThoai(so, "QUOC_TE")
    except (phonenumbers.NumberParseException, TypeError, ValueError):
        return None


def mau_tim_sdt(q: object) -> str | None:
    """Phone-only search fragment; callers decide how to apply it."""
    if not isinstance(q, str) or len(q) > 100 or re.search(r"[^0-9\s()+.\-]", q):
        return None
    digits = re.sub(r"[^0-9]", "", q)
    if digits.startswith("0084"):
        digits = "0" + digits[4:]
    elif digits.startswith("84"):
        digits = "0" + digits[2:]
    elif q.strip().startswith("00"):
        digits = digits[2:]
    return digits or None


def sang_e164(so: object) -> str | None:
    phone = chuan_hoa_sdt(so)
    if phone is None:
        return None
    return phone.so if phone.loai == "QUOC_TE" else "+84" + phone.so[1:]


def dinh_dang_hien_thi(so: str) -> str:
    phone = chuan_hoa_sdt(so)
    if phone is None:
        return so
    if phone.loai != "QUOC_TE":
        return f"{phone.so[:4]} {phone.so[4:7]} {phone.so[7:]}"
    number = phonenumbers.parse(phone.so, None)
    return phonenumbers.format_number(
        number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
    ).replace("-", " ")


def che_sdt(sdt: str | None) -> str:
    """Keep the cleanup screen's historical masking contract."""
    s = (sdt or "").strip()
    if len(s) < 7:
        return s
    return f"{s[:-6]}***{s[-3:]}"


_VN_MOBILE_PREFIXES = frozenset({"03", "05", "07", "08", "09"})


def normalize_vn_phone(value: object) -> str | None:
    """Compatibility wrapper: Vietnamese mobile numbers only."""
    phone = chuan_hoa_sdt(value)
    return phone.so if phone is not None and phone.loai == "DI_DONG" else None


def phone_variants(value: object) -> list[str]:
    """Historical VN spellings, or one canonical foreign spelling."""
    phone = chuan_hoa_sdt(value)
    if phone is None:
        return []
    if phone.loai == "QUOC_TE":
        return [phone.so]
    subscriber = phone.so[1:]
    return [phone.so, f"84{subscriber}", f"+84{subscriber}"]
