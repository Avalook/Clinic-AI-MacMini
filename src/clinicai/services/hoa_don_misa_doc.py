"""Dấu vân tay của một hoá đơn lúc xuất MISA (G5c). Hàm thuần, không đụng DB.

"Đã xuất sang MISA" chỉ có ích nếu kế toán biết hoá đơn nào ĐỔI SAU KHI XUẤT (hoàn
tiền, sửa dòng, đổi người mua / công ty) để vào MISA sửa lại. Lúc đánh dấu ta lưu
hai dấu vân tay của MỖI hoá đơn; sau này tính lại từ dữ liệu hiện tại và so.

Hai dấu riêng để nói được LÝ DO:
* `nguoi_mua` — công ty (tên, địa chỉ, MST, email, người mua) với hoá đơn công ty;
  tên, địa chỉ, email, SĐT, CCCD của khách với hoá đơn cá nhân.
* `noi_dung` — ngày, tổng tiền, từng dòng hàng (tên, ĐVT, số lượng, đơn giá,
  thành tiền).

KHÔNG tính thuế suất: kế toán đặt / sửa thuế ở màn xuất là việc của chính họ lúc
tải file, không phải thay đổi của hoá đơn. Thuế suất không nằm trong dấu vân tay
nên một hoá đơn đã xuất mà sau đó kế toán đổi thuế suất sẽ KHÔNG hiện "có thay đổi".
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

#: Lý do một hoá đơn đã xuất mà nay khác (hiện cho người đọc).
LY_DO_NGUOI_MUA = "Thông tin người mua / công ty đã đổi"
LY_DO_NOI_DUNG = "Số tiền hoặc dòng hàng đã đổi"
LY_DO_KHONG_CON = "Không còn trong danh sách hoá đơn của kỳ (đã huỷ hoặc hoàn hết)"


def _bam(x: object) -> str:
    raw = json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode()).hexdigest()


def dau_van_tay(hd: Mapping[str, Any]) -> tuple[str, str]:
    """(dấu người mua, dấu nội dung) của MỘT hoá đơn gốc (chưa tách thuế)."""
    if hd.get("la_hd_cong_ty"):
        nguoi_mua: dict[str, Any] = {
            "ct": True,
            "ten": hd.get("ten_cong_ty") or "",
            "dia_chi": hd.get("dia_chi") or "",
            "mst": hd.get("ma_so_thue") or "",
            "email": hd.get("email") or "",
            "nguoi_mua": hd.get("nguoi_mua") or "",
        }
    else:
        nguoi_mua = {
            "ct": False,
            "ten": hd.get("ten_khach") or "",
            "dia_chi": hd.get("dia_chi") or "",
            "email": hd.get("email") or "",
            "sdt": hd.get("so_dien_thoai") or "",
            "cccd": hd.get("cccd") or "",
        }
    noi_dung = {
        "ngay": hd.get("ngay") or "",
        "tong": int(hd.get("tong") or 0),
        "dong": [
            [
                d.get("ten") or "",
                d.get("dvt") or "",
                d.get("so_luong"),
                d.get("don_gia"),
                int(d.get("thanh_tien") or 0),
            ]
            for d in hd.get("dong") or []
        ],
    }
    return _bam(nguoi_mua), _bam(noi_dung)


def so_sanh(
    da_xuat: Mapping[str, Any] | None, hien_tai: tuple[str, str] | None
) -> list[str]:
    """Các lý do hoá đơn đã xuất khác hiện tại. Rỗng = không đổi (hoặc chưa xuất).

    `da_xuat` có `dau_nguoi_mua`, `dau_noi_dung` lúc xuất; `hien_tai` là cặp dấu
    tính lại, hoặc None khi hoá đơn không còn trong kỳ.
    """
    if da_xuat is None:
        return []
    if hien_tai is None:
        return [LY_DO_KHONG_CON]
    ly_do = []
    if da_xuat["dau_nguoi_mua"] != hien_tai[0]:
        ly_do.append(LY_DO_NGUOI_MUA)
    if da_xuat["dau_noi_dung"] != hien_tai[1]:
        ly_do.append(LY_DO_NOI_DUNG)
    return ly_do
