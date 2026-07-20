"""Vietnamese phone normalization shared by validation and MPI deduplication."""

from __future__ import annotations

import re

_VN_MOBILE_PREFIXES = frozenset({"03", "05", "07", "08", "09"})


def normalize_vn_phone(value: str) -> str | None:
    """Return canonical 10-digit VN mobile form, or ``None`` when invalid.

    Accepted equivalent inputs include ``090...``, ``8490...``, ``+8490...``
    and the nine-digit subscriber form. Formatting punctuation is ignored.
    """
    text = value.strip()
    if not text or re.search(r"[^\d\s()+.\-]", text):
        return None
    digits = re.sub(r"\D", "", text)
    if digits.startswith("0084"):
        subscriber = digits[4:]
    elif digits.startswith("84"):
        subscriber = digits[2:]
    elif digits.startswith("0"):
        subscriber = digits[1:]
    else:
        subscriber = digits

    national = f"0{subscriber}"
    if (
        len(national) != 10
        or not national.isdigit()
        or national[:2] not in _VN_MOBILE_PREFIXES
    ):
        return None
    return national


def phone_variants(value: str) -> list[str]:
    """Return national, country-code and E.164 spellings for one VN mobile."""
    national = normalize_vn_phone(value)
    if national is None:
        return []
    subscriber = national[1:]
    return [national, f"84{subscriber}", f"+84{subscriber}"]
