"""Các chỉ số tài chính từ nguồn báo cáo đã lọc quyền, ngày và ca.

Không suy giảm giá từ chênh lệch bảng giá: hệ thống chưa có sổ giảm giá.
Không thay đổi tập ngày của báo cáo cũ; đây là số hiệu lực hiện tại của tập ấy.

Không có dòng "nợ chưa thu trong kỳ": nó là số trôi (khoản thu sau thì biến
khỏi kỳ cũ, ghi nợ lại thì nhảy sang kỳ mới) chứ không phải dòng tiền đã ghi.
Nợ còn treo xem ở "Khách còn nợ" (`khach_con_no`).
"""

from collections.abc import Mapping
from typing import Any


def tom_tat_tai_chinh(bao_cao: Mapping[str, Any]) -> dict[str, Any]:
    """Doanh thu lấy dòng hàng của phiếu PAID, không lấy số lần thu làm doanh thu.

    Hoàn tiền chỉ COMPLETED; ngày thuộc tập khoản hoàn tạo trong khoảng đã chọn.
    """
    tong = bao_cao.get("tong") or {}
    hang_hoa = bao_cao.get("hang_hoa") or {}
    doanh_thu = sum(int(v["tong"]["doanh_thu"]) for v in hang_hoa.values())
    doanh_thu_thuan = sum(int(v["tong"]["doanh_thu_thuan"]) for v in hang_hoa.values())
    hoan = {r["ma"]: int(r.get("hoan") or 0) for r in bao_cao.get("theo_hinh_thuc", ())}
    return {
        "so_phieu_thu": int(tong.get("so_phieu_thu") or 0),
        "doanh_thu": doanh_thu,
        "hoan_tien_mat": hoan.get("CASH", 0),
        "hoan_chuyen_khoan": hoan.get("TRANSFER", 0) + hoan.get("QR", 0),
        "giam_gia": None,
        "doanh_thu_thuan": doanh_thu_thuan,
        "thuc_thu": int(tong.get("thuc_thu") or 0),
        "chua_co_du_lieu": ["giam_gia"],
        "pham_vi": {
            "so_phieu_thu": "Phiếu có ngày thu trong khoảng, gồm phiếu đã huỷ.",
            "doanh_thu": "Dòng hàng của phiếu còn hiệu lực, theo ngày thu.",
            "hoan": "Khoản đã hoàn, theo ngày lập khoản hoàn trong khoảng.",
            "doanh_thu_thuan": (
                "Doanh thu trừ giá trị dòng hàng đã hoàn trong tập báo cáo."
            ),
            "thuc_thu": "Tiền thu trừ phiếu huỷ và khoản đã hoàn trong tập báo cáo.",
        },
    }
