"""File Excel của Danh sách hoá đơn — cùng dữ liệu đã cấp quyền với màn.

Tên sheet và tên cột dùng ĐÚNG chữ trên màn (Tuyền 13/10: file từng dùng chữ kỹ
thuật "Trong kỳ", "toàn chứng từ", mã thô DA_THU / dich_vu / CASH — người đối
soát không đối chiếu được với màn). Không đưa mã nội bộ (uuid) ra file.
"""

from datetime import datetime, timezone
from typing import Any

TRANG_THAI = {
    "DA_THU": "Đã thu",
    "CHO_HOAN": "Chờ hoàn",
    "HOAN_MOT_PHAN": "Hoàn một phần",
    "HOAN_TOAN_BO": "Hoàn toàn bộ",
    "DA_HUY": "Đã hủy",
    "HON_HOP": "Nhiều trạng thái",
}
LOAI_HOA_DON = {"dich_vu": "Dịch vụ", "thuoc": "Thuốc"}
HINH_THUC = {"CASH": "Tiền mặt", "TRANSFER": "Chuyển khoản", "QR": "Chuyển khoản"}
KIEU_GIAM = {"AMOUNT": "Số tiền", "PERCENT": "%"}
TRANG_THAI_HOAN = {
    "PENDING": "Chờ trả lại",
    "COMPLETED": "Đã trả lại",
    "FAILED": "Hoàn thất bại",
    "CANCELLED": "Đã hủy yêu cầu hoàn",
}
TEN_SU_KIEN = {
    "DOI_HINH_THUC": "Đổi hình thức",
    "BO_DICH_VU": "Bỏ dịch vụ sau thu",
    "HOAN_TIEN": "Hoàn tiền",
    "HUY_PHIEU": "Huỷ phiếu",
}


def _ten(bang: dict[str, str], ma: Any) -> str | None:
    return bang.get(str(ma), str(ma)) if ma else None


def _co(x: Any) -> str:
    return "Có" if x else ""


def _so_ngay_ton(luc: Any, bay_gio: datetime) -> int | None:
    from clinicai.services.excel_export import excel_datetime

    t = excel_datetime(luc)
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max(0, (bay_gio - t).days)


def xlsx_hoa_don(data: dict[str, Any], *, bay_gio: datetime | None = None) -> bytes:
    """Bảng sửa / lọc được; mỗi sheet là một Excel Table."""
    from clinicai.services.excel_export import excel_date, excel_datetime, excel_table

    bay_gio = bay_gio or datetime.now(timezone.utc)
    customers: list[list[Any]] = []
    bills: list[list[Any]] = []
    lines: list[list[Any]] = []
    refunds: list[list[Any]] = []
    events: list[list[Any]] = []
    for g in data["khach"]:
        customers.append(
            [
                g["ten"],
                g["ma_bn"],
                g["so_dien_thoai"],
                g["so_phieu"],
                g["tong_truoc_giam"],
                g["giam_gia"],
                g["da_thu"],
                g.get("da_thu_dich_vu", 0),
                g.get("da_thu_thuoc", 0),
                g["da_hoan"],
                g.get("chua_tra_lai", 0),
                g["thu_rong"],
                _ten(TRANG_THAI, g["trang_thai"]),
                len(g.get("viec_ton") or []),
            ]
        )
        for p in g["phieu"]:
            bills.append(
                [
                    g["ten"],
                    g["ma_bn"],
                    p["ma"],
                    _ten(LOAI_HOA_DON, p["kind"]),
                    _ten(TRANG_THAI, p["trang_thai"]),
                    excel_datetime(p["thu_luc"]),
                    p["nguoi_thu"],
                    _ten(HINH_THUC, p["hinh_thuc"]),
                    p["tong_truoc_giam"],
                    p["giam_gia"],
                    _ten(KIEU_GIAM, p["kieu_giam"]),
                    p["gia_tri_giam"],
                    p["ly_do_giam"],
                    p["nguoi_giam"],
                    p["so_tien"],
                    p["da_hoan"],
                    p["cho_hoan"],
                    p["thu_rong"],
                    excel_datetime(p["huy_luc"]),
                    p["nguoi_huy"],
                    p["ly_do_huy"],
                    excel_datetime(p["lap_luc"]),
                    p["nguoi_lap"],
                ]
            )
            for d in p["dong"]:
                lines.append(
                    [
                        g["ten"],
                        g["ma_bn"],
                        "Thu",
                        p["ma"],
                        d["ten"],
                        d["so_luong"],
                        d["thanh_tien_truoc_giam"],
                        d["giam_gia"],
                        d["thanh_tien"],
                        _co(d["da_bo"]),
                    ]
                )
            for e in p.get("su_kien") or []:
                events.append(
                    [
                        g["ten"],
                        g["ma_bn"],
                        p["ma"],
                        excel_datetime(e["luc"]),
                        TEN_SU_KIEN.get(e["loai"], e["loai"]),
                        e.get("nguoi"),
                        e.get("mo_ta"),
                        e.get("ly_do"),
                        e["so_tien"],
                    ]
                )
            for r in p["hoan"]:
                refunds.append(
                    [
                        g["ten"],
                        g["ma_bn"],
                        p["ma"],
                        r["ma"],
                        _ten(TRANG_THAI_HOAN, r["trang_thai"]),
                        r["so_tien"],
                        _ten(HINH_THUC, r["hinh_thuc"]),
                        r["ly_do"],
                        excel_datetime(r["lap_luc"]),
                        r["nguoi_lap"],
                        excel_datetime(r["hoan_luc"]),
                        r["nguoi_hoan"],
                        excel_datetime(r["huy_luc"]),
                        r["nguoi_huy"],
                        r["ly_do_huy"],
                    ]
                )
                for d in r["dong"]:
                    lines.append(
                        [
                            g["ten"],
                            g["ma_bn"],
                            "Hoàn",
                            r["ma"],
                            d["ten"],
                            d["so_luong"],
                            None,
                            None,
                            d["thanh_tien"],
                            "",
                        ]
                    )
    t = data["tong"]
    return excel_table(
        [
            (
                # = hàng tổng trên màn (dòng tiền trong khoảng ngày đang xem).
                "Tổng hợp",
                [
                    "Từ ngày",
                    "Đến ngày",
                    "Tổng tiền hàng",
                    "Giảm giá",
                    "Tiền đã thu",
                    "Phiếu huỷ",
                    "Số phiếu huỷ",
                    "Đã trả lại khách",
                    "Thực thu",
                    "Chưa trả lại khách",
                    "Việc còn tồn",
                ],
                [
                    [
                        excel_date(data["tu"]),
                        excel_date(data["den"]),
                        t["tong_truoc_giam"],
                        t["giam_gia"],
                        t["da_thu"],
                        t.get("gia_tri_huy", 0),
                        t.get("so_huy", 0),
                        t["da_hoan"],
                        t["thu_rong"],
                        t.get("chua_tra_lai", 0),
                        t.get("so_viec_ton", 0),
                    ]
                ],
            ),
            (
                # = bảng "Theo khách" trên màn.
                "Theo khách",
                [
                    "Khách",
                    "Mã khách",
                    "Điện thoại",
                    "Số phiếu",
                    "Tổng tiền hàng",
                    "Giảm giá",
                    "Tiền đã thu",
                    "Tiền đã thu dịch vụ",
                    "Tiền đã thu thuốc",
                    "Đã trả lại",
                    "Chưa trả lại",
                    "Thực thu",
                    "Trạng thái",
                    "Số việc tồn",
                ],
                customers,
            ),
            (
                "Phiếu thu",
                [
                    "Khách",
                    "Mã khách",
                    "Mã phiếu",
                    "Loại hoá đơn",
                    "Trạng thái",
                    "Thu lúc",
                    "Người thu",
                    "Hình thức",
                    "Tổng tiền hàng",
                    "Giảm giá",
                    "Kiểu giảm",
                    "Giá trị giảm",
                    "Lý do giảm",
                    "Người giảm",
                    "Tiền đã thu",
                    "Đã trả lại",
                    "Chờ trả lại",
                    "Thực thu",
                    "Huỷ lúc",
                    "Người huỷ",
                    "Lý do huỷ",
                    "Lập lúc",
                    "Người lập",
                ],
                bills,
            ),
            (
                "Dòng phiếu",
                [
                    "Khách",
                    "Mã khách",
                    "Phiếu",
                    "Mã phiếu",
                    "Dịch vụ / thuốc",
                    "Số lượng",
                    "Tổng tiền hàng",
                    "Giảm giá",
                    "Thành tiền",
                    "Bỏ sau thu",
                ],
                lines,
            ),
            (
                "Hoàn tiền",
                [
                    "Khách",
                    "Mã khách",
                    "Phiếu thu gốc",
                    "Mã phiếu hoàn",
                    "Trạng thái",
                    "Số tiền",
                    "Hình thức",
                    "Lý do",
                    "Lập lúc",
                    "Người lập",
                    "Trả lúc",
                    "Người trả",
                    "Đóng lúc",
                    "Người đóng",
                    "Lý do đóng",
                ],
                refunds,
            ),
            (
                "Sau khi thu",
                [
                    "Khách",
                    "Mã khách",
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
                    "Khách",
                    "Mã khách",
                    "Việc",
                    "Số tiền",
                    "Đã tồn (ngày)",
                    "Mô tả",
                    "Mã phiếu",
                    "Loại hoá đơn",
                    "Người",
                ],
                [
                    [
                        excel_datetime(v["luc"]),
                        v["ten"],
                        v["ma_bn"],
                        v["ten_loai"],
                        v["so_tien"],
                        _so_ngay_ton(v["luc"], bay_gio),
                        v.get("mo_ta"),
                        v.get("ma"),
                        _ten(LOAI_HOA_DON, v.get("kind")),
                        v.get("nguoi"),
                    ]
                    for v in data.get("viec_ton") or []
                ],
            ),
        ]
    )
