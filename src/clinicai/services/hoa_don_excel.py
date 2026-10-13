"""Editable invoice export using the same authorized dataset."""

from typing import Any


def xlsx_hoa_don(data: dict[str, Any]) -> bytes:
    """Editable tables; period totals and lifetime bill amounts are labelled."""
    from clinicai.services.excel_export import excel_date, excel_datetime, excel_table

    customers = []
    bills = []
    lines = []
    refunds = []
    events = []
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
                g["tong_truoc_giam"],
                g["giam_gia"],
                g.get("da_thu_dich_vu", 0),
                g.get("da_thu_thuoc", 0),
                g.get("chua_tra_lai", 0),
                len(g.get("viec_ton") or []),
            ]
        )
        for p in g["phieu"]:
            for e in p.get("su_kien") or []:
                events.append(
                    [
                        g["ma_bn"],
                        g["ten"],
                        p["ma"],
                        excel_datetime(e["luc"]),
                        TEN_SU_KIEN.get(e["loai"], e["loai"]),
                        e.get("nguoi"),
                        e.get("mo_ta"),
                        e.get("ly_do"),
                        e["so_tien"],
                    ]
                )
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
                    p["tong_truoc_giam"],
                    p["giam_gia"],
                    p["kieu_giam"],
                    p["gia_tri_giam"],
                    p["ly_do_giam"],
                    p["nguoi_giam"],
                    excel_datetime(p["giam_luc"]),
                ]
            )
            for d in p["dong"]:
                lines.append(
                    [
                        g["ma_bn"],
                        g["ten"],
                        p["ma"],
                        d["id"],
                        d["ten"],
                        d["so_luong"],
                        d["thanh_tien"],
                        d["da_bo"],
                        d["thanh_tien_truoc_giam"],
                        d["giam_gia"],
                    ]
                )
            for r in p["hoan"]:
                refunds.append(
                    [
                        g["ma_bn"],
                        g["ten"],
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
                            g["ten"],
                            r["ma"],
                            d["id"],
                            d["ten"],
                            d["so_luong"],
                            d["thanh_tien"],
                            None,
                            None,
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
                    "Thực thu",
                    "Số phiếu huỷ",
                    "Giá trị phiếu huỷ",
                    "Trước giảm trong kỳ",
                    "Giảm giá trong kỳ",
                    "Chưa trả lại khách",
                    "Việc còn tồn (mọi ngày)",
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
                        totals["tong_truoc_giam"],
                        totals["giam_gia"],
                        totals.get("chua_tra_lai", 0),
                        totals.get("so_viec_ton", 0),
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
                    "Thực thu toàn chứng từ",
                    "Trước giảm toàn chứng từ",
                    "Giảm giá toàn chứng từ",
                    "Đã thu dịch vụ",
                    "Đã thu thuốc",
                    "Chưa trả lại khách",
                    "Số việc tồn",
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
                    "Thực thu toàn phiếu",
                    "Thu trong kỳ",
                    "Hình thức",
                    "Lập lúc",
                    "Người lập",
                    "Thu lúc",
                    "Người thu",
                    "Huỷ lúc",
                    "Người huỷ",
                    "Lý do huỷ",
                    "Trước giảm",
                    "Giảm giá",
                    "Kiểu giảm",
                    "Giá trị nhập",
                    "Lý do giảm",
                    "Người giảm",
                    "Giảm lúc",
                ],
                bills,
            ),
            (
                "Chi tiết",
                [
                    "Mã khách",
                    "Khách",
                    "Mã chứng từ",
                    "Mã dòng",
                    "Dịch vụ hoặc thuốc",
                    "Số lượng",
                    "Thành tiền",
                    "Đã bỏ",
                    "Thành tiền trước giảm",
                    "Giảm giá phân bổ",
                ],
                lines,
            ),
            (
                "Hoàn tiền",
                [
                    "Mã khách",
                    "Khách",
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
            (
                "Sau khi thu",
                [
                    "Mã khách",
                    "Khách",
                    "Mã phiếu",
                    "Lúc",
                    "Việc",
                    "Người làm",
                    "Mô tả",
                    "Lý do",
                    "Số tiền",
                ],
                events,
            ),
            (
                "Việc còn tồn",
                [
                    "Phát sinh",
                    "Mã khách",
                    "Khách",
                    "Việc",
                    "Số tiền",
                    "Mô tả",
                    "Mã phiếu",
                    "Loại",
                    "Người",
                ],
                [
                    [
                        excel_datetime(v["luc"]),
                        v["ma_bn"],
                        v["ten"],
                        v["ten_loai"],
                        v["so_tien"],
                        v.get("mo_ta"),
                        v.get("ma"),
                        {"thuoc": "Thuốc", "dich_vu": "Dịch vụ"}.get(
                            v.get("kind") or ""
                        ),
                        v.get("nguoi"),
                    ]
                    for v in data.get("viec_ton") or []
                ],
            ),
        ]
    )


TEN_SU_KIEN = {
    "DOI_HINH_THUC": "Đổi hình thức",
    "BO_DICH_VU": "Bỏ dịch vụ sau thu",
    "HOAN_TIEN": "Hoàn tiền",
    "HUY_PHIEU": "Huỷ phiếu",
}
