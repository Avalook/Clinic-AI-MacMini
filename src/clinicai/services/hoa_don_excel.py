"""Editable invoice export using the same authorized dataset."""

from typing import Any


def xlsx_hoa_don(data: dict[str, Any]) -> bytes:
    """Editable tables; period totals and lifetime bill amounts are labelled."""
    from clinicai.services.excel_export import excel_date, excel_datetime, excel_table

    customers = []
    bills = []
    lines = []
    refunds = []
    for g in data["khach"]:
        customers.append(
            [
                g["id"],
                g["ma_bn"],
                g["ten"],
                g["so_dien_thoai"],
                g["so_phieu"],
                g["trang_thai"],
                g["da_thu"],
                g["da_hoan"],
                g["cho_hoan"],
                g["thu_rong"],
            ]
        )
        for p in g["phieu"]:
            bills.append(
                [
                    g["ma_bn"],
                    g["ten"],
                    p["ma"],
                    p["visit_id"],
                    p["kind"],
                    p["trang_thai"],
                    p["so_tien"],
                    p["da_hoan"],
                    p["cho_hoan"],
                    p["thu_rong"],
                    p["thu_trong_ky"],
                    p["hinh_thuc"],
                    excel_datetime(p["lap_luc"]),
                    p["nguoi_lap"],
                    excel_datetime(p["thu_luc"]),
                    p["nguoi_thu"],
                    excel_datetime(p["huy_luc"]),
                    p["nguoi_huy"],
                    p["ly_do_huy"],
                ]
            )
            for d in p["dong"]:
                lines.append(
                    [
                        g["ma_bn"],
                        p["ma"],
                        d["id"],
                        d["ten"],
                        d["so_luong"],
                        d["thanh_tien"],
                        d["da_bo"],
                    ]
                )
            for r in p["hoan"]:
                refunds.append(
                    [
                        g["ma_bn"],
                        p["ma"],
                        r["ma"],
                        r["trang_thai"],
                        r["so_tien"],
                        r["trong_ky"],
                        r["hinh_thuc"],
                        excel_datetime(r["lap_luc"]),
                        r["nguoi_lap"],
                        excel_datetime(r["hoan_luc"]),
                        r["nguoi_hoan"],
                        r["ly_do"],
                        excel_datetime(r["huy_luc"]),
                        r["nguoi_huy"],
                        r["ly_do_huy"],
                    ]
                )
                for d in r["dong"]:
                    lines.append(
                        [
                            g["ma_bn"],
                            r["ma"],
                            d["id"],
                            d["ten"],
                            d["so_luong"],
                            d["thanh_tien"],
                            None,
                        ]
                    )
    totals = data["tong"]
    return excel_table(
        [
            (
                "Trong kỳ",
                [
                    "Từ ngày",
                    "Đến ngày",
                    "Đã thu",
                    "Đã hoàn",
                    "Chờ hoàn",
                    "Thu ròng",
                    "Số phiếu huỷ",
                    "Giá trị phiếu huỷ",
                ],
                [
                    [
                        excel_date(data["tu"]),
                        excel_date(data["den"]),
                        totals["da_thu"],
                        totals["da_hoan"],
                        totals["cho_hoan"],
                        totals["thu_rong"],
                        totals["so_huy"],
                        totals["gia_tri_huy"],
                    ]
                ],
            ),
            (
                "Theo khách",
                [
                    "Mã khách nội bộ",
                    "Mã khách",
                    "Khách",
                    "Điện thoại",
                    "Số phiếu",
                    "Trạng thái",
                    "Đã thu toàn chứng từ",
                    "Đã hoàn toàn chứng từ",
                    "Chờ hoàn",
                    "Thu ròng toàn chứng từ",
                ],
                customers,
            ),
            (
                "Chứng từ",
                [
                    "Mã khách",
                    "Khách",
                    "Mã phiếu",
                    "Mã lượt",
                    "Loại",
                    "Trạng thái",
                    "Đã thu toàn phiếu",
                    "Đã hoàn toàn phiếu",
                    "Chờ hoàn",
                    "Thu ròng toàn phiếu",
                    "Thu trong kỳ",
                    "Hình thức",
                    "Lập lúc",
                    "Người lập",
                    "Thu lúc",
                    "Người thu",
                    "Huỷ lúc",
                    "Người huỷ",
                    "Lý do huỷ",
                ],
                bills,
            ),
            (
                "Chi tiết",
                [
                    "Mã khách",
                    "Mã chứng từ",
                    "Mã dòng",
                    "Dịch vụ hoặc thuốc",
                    "Số lượng",
                    "Thành tiền",
                    "Đã bỏ",
                ],
                lines,
            ),
            (
                "Hoàn tiền",
                [
                    "Mã khách",
                    "Phiếu gốc",
                    "Mã phiếu hoàn",
                    "Trạng thái",
                    "Số tiền",
                    "Sự kiện trong kỳ",
                    "Hình thức",
                    "Lập lúc",
                    "Người lập",
                    "Hoàn lúc",
                    "Người hoàn",
                    "Lý do",
                    "Đóng lúc",
                    "Người đóng",
                    "Lý do đóng",
                ],
                refunds,
            ),
        ]
    )
