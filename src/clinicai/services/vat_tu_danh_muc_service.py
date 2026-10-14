"""Whitelist riêng cho thuộc tính vật tư; không thay điều kiện bán hiện tại."""

from decimal import Decimal, DecimalException
from typing import Any

from clinicai.api.exceptions import ValidationError

COT_VAT_TU = {
    "loai_vat_tu": "loai_vat_tu",
    "gia_nhap": "gia_nhap_vat_tu",
    "ma_vach": "ma_vach_vat_tu",
    "don_vi": "don_vi",
    "kinh_doanh": "kinh_doanh_vat_tu",
    "can_duyet_nhap": "can_duyet_nhap_vat_tu",
    "can_ql_duyet": "can_ql_duyet",
    "chon_nhanh": "chon_nhanh",
}


def patch_vat_tu(raw: dict[str, Any]) -> dict[str, Any]:
    """Giữ null để xoá ô tuỳ chọn; số rác/âm/phần lẻ không ghi dữ liệu."""
    if set(raw) - set(COT_VAT_TU):
        raise ValidationError("Thuộc tính vật tư không hợp lệ.")
    patch: dict[str, Any] = {}
    for ten, v in raw.items():
        if ten in {"kinh_doanh", "can_duyet_nhap", "can_ql_duyet", "chon_nhanh"}:
            if not isinstance(v, bool):
                raise ValidationError("Cờ vật tư phải là bật hoặc tắt.")
        elif ten == "gia_nhap":
            if v is None or v == "":
                v = None
            else:
                try:
                    so = Decimal(str(v))
                    if (
                        not so.is_finite()
                        or so < 0
                        or so >= Decimal("1e12")
                        or so != so.to_integral_value()
                    ):
                        raise ValidationError(
                            "Giá nhập phải là số đồng nguyên không âm."
                        )
                    v = int(so)
                except (DecimalException, ValueError, TypeError) as exc:
                    raise ValidationError("Giá nhập không hợp lệ.") from exc
        else:
            if v is not None and not isinstance(v, str):
                raise ValidationError("Thuộc tính vật tư phải là chữ.")
            v = v.strip() or None if isinstance(v, str) else None
            if ten == "loai_vat_tu" and v not in {None, "VPP", "VTYT"}:
                raise ValidationError("Chọn Văn phòng phẩm hoặc Vật tư y tế.")
            if v is not None and len(v) > (40 if ten == "don_vi" else 120):
                raise ValidationError("Thuộc tính vật tư quá dài.")
        patch = {**patch, COT_VAT_TU[ten]: v}
    return patch
