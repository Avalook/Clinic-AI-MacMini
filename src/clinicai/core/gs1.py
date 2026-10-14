"""Tách chuỗi GS1 (mã vuông DataMatrix / GS1-128 trên hộp thuốc).

Máy quét và camera trả ba dạng: có tiền tố ký hiệu `]d2`/`]C1`/`]Q3`, phân
cách trường bằng ký tự GS (0x1D, FNC1), hoặc dạng người đọc
`(01)…(17)…(10)…`. Chỉ đọc bốn AI hộp thuốc cần: 01 mã SP (GTIN-14),
10 số lô, 17 hạn dùng, 21 số sê-ri. Gặp AI lạ thì dừng ở đó — phần đã đọc
được vẫn trả.

Luật repo: đầu vào rác → None, không ném. Không có AI 01 → None (mã không
phải GS1 thì tra như mã vạch thường).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

GS = "\x1d"
_TIEN_TO = ("]d2", "]C1", "]Q3", "]e0")
# AI → (độ dài cố định | None = độ dài thay đổi, tối đa)
_AI: dict[str, tuple[int | None, int]] = {
    "01": (14, 14),
    "10": (None, 20),
    "11": (6, 6),
    "15": (6, 6),
    "17": (6, 6),
    "21": (None, 20),
}
_NGOAC = re.compile(r"\((\d{2,4})\)([^(]*)")


@dataclass(frozen=True)
class Gs1:
    gtin: str
    so_lo: str | None
    han: date | None
    serial: str | None


def doc_han_gs1(yymmdd: str) -> date | None:
    """YYMMDD của GS1. Ngày "00" = ngày cuối tháng (chuẩn GS1). Rác → None."""
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
    if not 1 <= mm <= 12:
        return None
    nam = 2000 + yy
    if dd == 0:
        dd = calendar.monthrange(nam, mm)[1]
    try:
        return date(nam, mm, dd)
    except ValueError:
        return None


def _gtin_hop_le(gtin: str) -> bool:
    if len(gtin) != 14 or not gtin.isdigit():
        return False
    tong = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(gtin[:13]))
    return (10 - tong % 10) % 10 == int(gtin[13])


def _truong_ngoac(chuoi: str) -> dict[str, str] | None:
    truong: dict[str, str] = {}
    for ai, gia in _NGOAC.findall(chuoi):
        if ai not in _AI:
            break
        truong[ai] = gia.strip()
    return truong or None


def _truong_tho(chuoi: str) -> dict[str, str]:
    truong: dict[str, str] = {}
    i = 0
    while i < len(chuoi):
        if chuoi[i] == GS:
            i += 1
            continue
        ai = chuoi[i : i + 2]
        if ai not in _AI:
            break
        co_dinh, toi_da = _AI[ai]
        i += 2
        if co_dinh is not None:
            gia = chuoi[i : i + co_dinh]
            if len(gia) != co_dinh:
                break
            i += co_dinh
        else:
            het = chuoi.find(GS, i)
            het = len(chuoi) if het < 0 else het
            gia = chuoi[i:het][:toi_da]
            i = het
        truong[ai] = gia
    return truong


def tach_gs1(chuoi: object) -> Gs1 | None:
    if not isinstance(chuoi, str):
        return None
    s = chuoi.strip()
    for tt in _TIEN_TO:
        if s.startswith(tt):
            s = s[len(tt) :]
            break
    s = s.lstrip(GS)
    truong = _truong_ngoac(s) if s.startswith("(") else _truong_tho(s)
    if not truong:
        return None
    gtin = truong.get("01", "")
    if not _gtin_hop_le(gtin):
        return None
    han_tho = truong.get("17")
    return Gs1(
        gtin=gtin,
        so_lo=truong.get("10") or None,
        han=doc_han_gs1(han_tho) if han_tho else None,
        serial=truong.get("21") or None,
    )


def chuan_ma(ma: str) -> str:
    """Dạng so khớp của một mã vạch: dãy 8–14 chữ số được đệm 0 đầu cho đủ 14
    (EAN-8, UPC-A, EAN-13 và GTIN-14 của cùng một hộp là CÙNG một mã — mã vuông
    GS1 chứa GTIN-14, mã vạch in trên hộp là EAN-13). Mã chữ-số khác giữ nguyên."""
    chu = ma.strip()
    if chu.isascii() and chu.isdigit() and 8 <= len(chu) <= 14:
        return chu.zfill(14)
    return chu
