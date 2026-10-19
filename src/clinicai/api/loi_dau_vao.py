"""Câu tiếng Việt cho lỗi "dữ liệu gửi lên không hợp lệ" của pydantic (HTTP 422).

Mặc định FastAPI trả `{"detail": [{"type": "greater_than", "loc": [...]}]}` — giao
diện đọc `message` trước, không thấy thì rơi về "Máy chủ từ chối." nên người dùng
gõ số lượng âm cũng chỉ nhận câu ấy, không biết ô nào sai. Hàm thuần dưới đây dựng
một câu từ danh sách lỗi: tên ô + lý do ngắn, tối đa vài lỗi.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

#: Tên ô thường gặp ở màn kho → nhãn người dùng thấy. Ô lạ giữ nguyên tên.
NHAN_O: dict[str, str] = {
    "so_luong": "Số lượng",
    "batch_code": "Số lô",
    "unit": "Đơn vị",
    "ly_do": "Lý do",
    "expiry_date": "Hạn dùng",
    "cost_price": "Giá nhập",
    "gia_nhap": "Giá nhập",
    "thuc_te": "Số đếm thực tế",
    "drug_batch_id": "Lô thuốc",
    "drug_catalog_id": "Thuốc",
    "vat_tu_id": "Vật tư",
    "dong": "Danh sách dòng",
    "ten": "Tên",
    "gia": "Giá",
    "loai": "Loại",
    "huong": "Chiều chuyển",
}

#: Tối đa bao nhiêu lỗi đưa vào một câu (còn lại gom "và N lỗi khác").
TOI_DA_LOI = 3


def _gon(so: Any) -> str:
    """0.0 → '0' (pydantic đưa mốc dạng float)."""
    if isinstance(so, (int, float)) and float(so).is_integer():
        return str(int(so))
    return str(so)


def _ly_do(loi: Mapping[str, Any]) -> str:
    kieu = str(loi.get("type") or "")
    ngu_canh = loi.get("ctx")
    ctx: Mapping[str, Any] = ngu_canh if isinstance(ngu_canh, Mapping) else {}
    if kieu == "greater_than":
        return f"phải lớn hơn {_gon(ctx.get('gt', 0))}"
    if kieu == "greater_than_equal":
        return f"phải từ {_gon(ctx.get('ge', 0))} trở lên"
    if kieu == "less_than_equal":
        return f"không được lớn hơn {_gon(ctx.get('le'))}"
    if kieu == "string_too_short":
        return "không được để trống"
    if kieu == "string_too_long":
        return f"quá dài (tối đa {ctx.get('max_length')} ký tự)"
    if kieu in ("too_short", "list_too_short"):
        return "cần có ít nhất một mục"
    if kieu == "too_long":
        return f"quá nhiều mục (tối đa {ctx.get('max_length')})"
    if kieu == "missing":
        return "chưa nhập"
    if kieu.endswith("_parsing") and "uuid" in kieu:
        return "không hợp lệ"
    if kieu.endswith(("_parsing", "_type")):
        la_so = "int" in kieu or "float" in kieu
        return "phải là một con số" if la_so else "không hợp lệ"
    return "chưa hợp lệ"


def _vi_tri(loc: Sequence[Any]) -> str:
    """('body','dong',0,'so_luong') → 'Dòng 1 · Số lượng'."""
    dong: str | None = None
    ten: str | None = None
    for phan in loc:
        if isinstance(phan, int):
            dong = f"Dòng {phan + 1}"
        elif phan not in ("body", "query", "path", "header") and isinstance(phan, str):
            ten = NHAN_O.get(phan, phan)
    return " · ".join(x for x in (dong, ten) if x) or "Dữ liệu"


def cau_loi_dau_vao(loi: Sequence[Mapping[str, Any]]) -> str:
    """Câu cho người dùng từ `exc.errors()` của pydantic (rỗng → câu chung)."""
    if not loi:
        return "Dữ liệu gửi lên chưa hợp lệ — kiểm tra lại các ô vừa nhập."
    cau: list[str] = []
    for e in loi[:TOI_DA_LOI]:
        loc = e.get("loc")
        vi_tri = _vi_tri(loc if isinstance(loc, Sequence) else ())
        cau.append(f"{vi_tri}: {_ly_do(e)}")
    con_lai = len(loi) - TOI_DA_LOI
    ket = "; ".join(cau) + (f"; và {con_lai} lỗi khác" if con_lai > 0 else "")
    return ket + "."
