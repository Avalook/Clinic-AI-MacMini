"""Gõ tên thuốc không có trong danh mục → thuốc gần giống (tên VÀ biệt dược).

Ca thật (kế hoạch mục 7): bác sĩ gõ "Indurate" (danh mục là "Idurat 5mg", biệt
dược "Indurat 5mg / Tadalafil"), "AktiveMeno" (→ "Aktiv isoflavon"), "vicofol"
(→ "Vitcofol"), "gynoflor" (→ "Eulac" vì biệt dược ghi "Gynoflor"). Trước đây máy
tự thêm tên lạ vào danh mục, không giá → cả hoá đơn thuốc của lượt không thu được.

Chỉ gợi ý thuốc CHỌN ĐƯỢC (đang dùng, có giá) — thuốc rác không giá ("Indurate 5
(D/U)") khớp chữ rất sát nhưng gợi ý nó là đẻ thêm lượt kẹt quầy.

Luật so khớp, từ chắc tới yếu (điểm 0–1, lấy điểm cao nhất của mọi chữ của thuốc):
1. Trùng khít sau khi bỏ dấu, hoa/thường, dấu cách, ký tự lạ → 1.
2. Một bên chứa trọn bên kia (từ ≥ 4 chữ: "aktiv" nằm đầu "aktivemeno") → 0,9.
3. Giống chữ (difflib) giữa chữ gõ và từng từ / cả tên ≥ 0,75.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from difflib import SequenceMatcher
from typing import Any

import asyncpg

#: Gõ dài hơn thế là rác (dán nhầm cả đoạn) — cắt, không ném.
TEN_TOI_DA = 200
NGUONG_GIONG = 0.75
GOI_Y_TOI_DA = 5
#: Chữ chung của tên thuốc ("Thuốc …", "… viên", "… gói") và hàm lượng ("5mg",
#: "500") — trùng chúng không có nghĩa là cùng thuốc.
_TU_CHUNG = frozenset(
    {"thuoc", "vien", "goi", "hop", "ong", "lo", "tuyp", "but", "dang", "nang", "sui"}
)
_HAM_LUONG = re.compile(r"^\d+([.,]\d+)?(mg|mcg|g|ml|iu|ui|v)?$")


def chu_so_khop(chu: Any) -> str:
    """Bỏ dấu, chữ thường, ký tự lạ thành cách: “Vitcofol® 5mg” → “vitcofol 5mg”."""
    s = unicodedata.normalize("NFD", str(chu or "")[:TEN_TOI_DA])
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "d").lower()
    return " ".join(re.sub(r"[^0-9a-z]+", " ", s).split())


def _diem(go: str, chu: str) -> float:
    """Điểm giống giữa chữ gõ (đã chuẩn) và một chữ của thuốc (đã chuẩn)."""
    if not go or not chu:
        return 0.0
    go_lien, chu_lien = go.replace(" ", ""), chu.replace(" ", "")
    if go_lien == chu_lien:
        return 1.0
    tu = [t for t in chu.split() if t not in _TU_CHUNG and not _HAM_LUONG.match(t)]
    if any(len(t) >= 4 and (t in go_lien or go_lien in t) for t in tu):
        return 0.9
    if len(go_lien) >= 4 and go_lien in chu_lien:
        return 0.9
    return max(
        [SequenceMatcher(None, go_lien, t).ratio() for t in tu]
        + [SequenceMatcher(None, go_lien, chu_lien).ratio()]
    )


def xep_goi_y(
    ten_go: Any, ung_vien: Iterable[Mapping[str, Any]], toi_da: int = GOI_Y_TOI_DA
) -> list[dict[str, Any]]:
    """Thuốc gần giống `ten_go`, giống nhất trước. Hàm thuần — test không cần DB.

    `ung_vien`: mỗi dòng có `id`, `ten`, `biet_duoc` (biệt dược có thể nhiều tên
    ngăn bằng "/" hoặc ","). Đầu vào rác (rỗng, toàn ký tự lạ) → danh sách rỗng."""
    go = chu_so_khop(ten_go)
    if len(go.replace(" ", "")) < 3:
        return []
    ra: list[tuple[float, str, dict[str, Any]]] = []
    for u in ung_vien:
        biet_duoc = re.split(r"[/,;]", str(u.get("biet_duoc") or ""))
        chu = [str(u.get("ten") or ""), *biet_duoc]
        diem = max(_diem(go, chu_so_khop(c)) for c in chu)
        if diem >= NGUONG_GIONG:
            ten = str(u.get("ten") or "")
            dong = {
                "drug_catalog_id": str(u["id"]),
                "ten": ten,
                "biet_duoc": u.get("biet_duoc"),
                "diem": round(diem, 2),
            }
            ra.append((diem, ten.lower(), dong))
    ra.sort(key=lambda x: (-x[0], x[1]))
    return [x[2] for x in ra[: max(toi_da, 0)]]


async def goi_y_thuoc(
    conn: asyncpg.Connection, clinic_id: str, ten_go: Any
) -> list[dict[str, Any]]:
    """Thuốc chọn được (đang dùng, có giá) gần giống tên gõ, của phòng khám này."""
    if not chu_so_khop(ten_go):
        return []
    rows = await conn.fetch(
        "SELECT id::text AS id, name_raw AS ten, biet_duoc FROM public.drug_catalog"
        " WHERE clinic_id = $1::uuid AND is_active AND unit_price IS NOT NULL",
        clinic_id,
    )
    return xep_goi_y(ten_go, [dict(r) for r in rows])


def cau_khong_co_thuoc(ten_go: str, goi_y: list[dict[str, Any]]) -> str:
    """Câu 422 khi lưu đơn có tên thuốc ngoài danh mục."""
    ten = " ".join(str(ten_go or "").split())[:80]
    cau = f"“{ten}” không có trong danh mục thuốc."
    if goi_y:
        cau += " Có phải: " + ", ".join(f"“{g['ten']}”" for g in goi_y) + "?"
    return cau + " Chọn thuốc trong danh mục, hoặc bấm “Nhờ kho thêm thuốc”."


__all__ = ["chu_so_khop", "cau_khong_co_thuoc", "goi_y_thuoc", "xep_goi_y"]
