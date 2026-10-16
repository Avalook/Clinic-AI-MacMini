"""Typed Excel exports for end-of-day reports."""

from collections.abc import Mapping
from typing import Any

from clinicai.services.bao_cao_cuoi_ngay_service import (
    TEN_HINH_THUC,
    TEN_LOAI,
    TEN_TRANG_THAI_THUOC,
    TIEU_DE_CO_TON,
    dong_co_ton,
)


def xlsx_hang_hoa(bc: Mapping[str, Any], loai: Any) -> bytes:
    """Export individual goods as a sortable table, without totals mixed into data."""
    from clinicai.services.excel_export import excel_table

    hh = (bc.get("hang_hoa") or {}).get(loai if loai in TEN_LOAI else "thuoc") or {
        "dong": []
    }
    if hh.get("co_ton"):
        # Khuôn có tồn kho: đúng thứ tự cột như màn (không "Đơn vị" riêng — đơn vị
        # nằm trong tên hàng, mỗi đơn vị lô một dòng).
        return excel_table([("Hàng hóa", TIEU_DE_CO_TON, dong_co_ton(hh))])
    keys = ("sl_ban", "doanh_thu", "sl_tra", "gia_tri_tra", "doanh_thu_thuan")
    rows = [
        [m.get("ma"), m["ten"], m.get("don_vi"), *[m[k] for k in keys]]
        for m in hh["dong"]
    ]
    return excel_table(
        [
            (
                "Hàng hóa",
                [
                    "Mã hàng",
                    "Tên hàng",
                    "Đơn vị",
                    "SL bán",
                    "Doanh thu",
                    "SL trả",
                    "Giá trị trả",
                    "Doanh thu thuần",
                ],
                rows,
            )
        ]
    )


def dong_tien_rows(dt: Mapping[str, Any]) -> list[list[Any]]:
    """Các dòng khối Dòng tiền (14/10/2026) — đúng chữ khách đưa, TM / CK từng
    mục có tiền đi qua. Thuần; khối rỗng → không dòng nào."""
    if not dt:
        return []

    def tm_ck(nhan: str, o: Mapping[str, Any]) -> list[list[Any]]:
        return [
            [nhan, o.get("tong")],
            [f"  {nhan} — tiền mặt", o.get("tien_mat")],
            [f"  {nhan} — chuyển khoản", o.get("chuyen_khoan")],
        ]

    return [
        ["Dòng tiền vào", dt.get("dong_tien_vao")],
        ["  Tiền thu — tiền mặt", (dt.get("tien_thu") or {}).get("tien_mat")],
        ["  Tiền thu — chuyển khoản", (dt.get("tien_thu") or {}).get("chuyen_khoan")],
        *tm_ck("Trả lại tiền khách hàng", dt.get("tra_lai") or {}),
        ["Nợ", dt.get("no")],
        ["Giảm giá", dt.get("giam_gia")],
        *tm_ck("Nợ thu được", dt.get("no_thu_duoc") or {}),
        *tm_ck("Thực thu", dt.get("thuc_thu") or {}),
        ["Doanh thu thuần", dt.get("doanh_thu_thuan")],
    ]


def xlsx_tom_tat(bc: Mapping[str, Any], day_du: bool = False) -> bytes:
    """Match the summary displayed on screen; never include hidden detail rows."""
    from clinicai.services.excel_export import excel_table

    rows = [
        ["Tổng thu", bc["tong"]["thuc_thu"]],
        [
            "Dịch vụ",
            next((r["thuc_thu"] for r in bc["theo_loai"] if r["ma"] == "dich_vu"), 0),
        ],
        [
            "Thuốc / vật tư",
            next((r["thuc_thu"] for r in bc["theo_loai"] if r["ma"] == "thuoc"), 0),
        ],
        *[[r["ten"], r["thuc_thu"]] for r in bc["theo_hinh_thuc"]],
    ]
    if day_du and bc.get("tai_chinh"):
        rows.extend(dong_tien_rows(bc["tai_chinh"].get("dong_tien") or {}))
    rows.append(["Phiếu thu", bc["tong"]["so_phieu_thu"]])
    return excel_table([("Tóm tắt", ["Mục", "Giá trị"], rows)])


def xlsx_bao_cao(bc: Mapping[str, Any]) -> bytes:
    """Export each report section in its own editable table, retaining raw types."""
    from clinicai.services.excel_export import excel_date, excel_datetime, excel_table

    tong = bc["tong"]
    sheets = [
        (
            "Tổng quan",
            ["Mục", "Giá trị"],
            [
                ["Từ ngày", excel_date(bc["tu"])],
                ["Đến ngày", excel_date(bc["den"])],
                ["Cơ sở", bc.get("ten_co_so") or "Tất cả cơ sở"],
                ["Ca", (bc.get("ca") or {}).get("ten") or "Cả ngày"],
                *[
                    [label, tong[key]]
                    for label, key in (
                        ("Thu gốc", "thu"),
                        ("Hủy phiếu", "huy"),
                        ("Hoàn", "hoan"),
                        ("Thực thu", "thuc_thu"),
                        ("Hoàn chờ chuyển", "hoan_cho"),
                        ("Phiếu thu", "so_phieu_thu"),
                    )
                ],
                ["Lượt khám", bc["khach"]["so_luot_kham"]],
                [
                    "Lượt không chọn dịch vụ khám",
                    bc["khach"]["so_luot_khong_chon_dich_vu_kham"],
                ],
            ],
        )
    ]
    keys = ("thu", "huy", "hoan", "thuc_thu")
    for title, key in (
        ("Hình thức", "theo_hinh_thuc"),
        ("Loại", "theo_loai"),
        ("Người thu", "theo_nguoi_thu"),
    ):
        sheets.append(
            (
                title,
                [title, "Thu gốc", "Hủy phiếu", "Hoàn", "Thực thu"],
                [[r["ten"], *[r[k] for k in keys]] for r in bc[key]],
            )
        )
    sheets.append(
        (
            "Theo ngày",
            ["Ngày", "Số phiếu", "Thu gốc", "Hủy phiếu", "Hoàn", "Thực thu"],
            [
                [excel_date(r["ngay"]), r["so_phieu"], *[r[k] for k in keys]]
                for r in bc["theo_ngay"]
            ],
        )
    )
    sheets.append(
        (
            "Top dịch vụ",
            ["Dịch vụ", "Số lượng", "Doanh thu gộp"],
            [[r["ten"], r["so_luong"], r["doanh_thu"]] for r in bc["top_dich_vu"]],
        )
    )
    sheets.append(
        (
            "Hoàn hủy",
            [
                "Loại",
                "Lúc",
                "Khách",
                "Mã khách",
                "Hình thức",
                "Số tiền",
                "Người",
                "Lý do",
            ],
            [
                [
                    "Hủy phiếu"
                    if r["loai"] == "huy"
                    else "Hoàn (chờ chuyển)"
                    if r["cho"]
                    else "Hoàn",
                    excel_datetime(r["luc"]),
                    r["khach"],
                    r["ma_bn"],
                    r.get("nhan_hinh_thuc")
                    or TEN_HINH_THUC.get(str(r["hinh_thuc"]), ""),
                    r["so_tien"],
                    r["nguoi"],
                    r["ly_do"],
                ]
                for r in bc["hoan_huy"]
            ],
        )
    )
    sheets.append(
        (
            "Đổi hình thức",
            [
                "Loại",
                "Lúc",
                "Khách",
                "Mã khách",
                "Từ",
                "Sang",
                "Số tiền",
                "Người",
                "Lý do",
            ],
            [
                [
                    TEN_LOAI.get(str(r["loai_tien"]), ""),
                    excel_datetime(r["luc"]),
                    r["khach"],
                    r["ma_bn"],
                    TEN_HINH_THUC.get(str(r["tu"]), "Không rõ"),
                    r.get("nhan_sang") or TEN_HINH_THUC.get(str(r["sang"]), ""),
                    r["so_tien"],
                    r["nguoi"],
                    r["ly_do"],
                ]
                for r in bc.get("doi_hinh_thuc") or []
            ],
        )
    )
    sheets.append(
        (
            "Đối tác thu hộ",
            ["Dịch vụ", "Lúc", "Khách", "Số tiền", "Hình thức"],
            [
                [
                    r["dich_vu"],
                    excel_datetime(r["luc"]),
                    r["khach"],
                    r["so_tien"],
                    TEN_HINH_THUC.get(str(r["hinh_thuc"]), ""),
                ]
                for r in bc["doi_tac"]["dong"]
            ],
        )
    )
    if bc.get("theo_co_so"):
        sheets.append(
            (
                "Theo cơ sở",
                [
                    "Cơ sở",
                    "Lượt khám",
                    "Phiếu thu",
                    "Thu gốc",
                    "Hủy phiếu",
                    "Hoàn",
                    "Thực thu",
                ],
                [
                    [
                        r["ten"],
                        r["khach"]["so_luot_kham"],
                        r["tong"]["so_phieu_thu"],
                        *[r["tong"][k] for k in keys],
                    ]
                    for r in bc["theo_co_so"]
                ],
            )
        )
    if bc.get("tai_chinh"):
        sheets.append(
            (
                "Dòng tiền",
                ["Mục", "Giá trị"],
                dong_tien_rows(bc["tai_chinh"].get("dong_tien") or {}),
            )
        )
    tt = bc.get("thuoc_theo_khach")
    if tt:
        sheets.append(
            (
                "Thuốc theo khách",
                [
                    "Khách",
                    "Mã khách",
                    "Thuốc",
                    "Bác sĩ ghi",
                    "Kê",
                    "Thực bán",
                    "Chênh",
                    "Đơn vị",
                    "Đơn giá",
                    "Thành tiền",
                    "Trạng thái",
                    "Người thu",
                ],
                [
                    [
                        k["khach"],
                        k["ma_bn"],
                        d["ten"],
                        d["ten_bac_si"],
                        d["so_ke"],
                        d["thuc_ban"],
                        d["chenh"],
                        d["don_vi"],
                        d["don_gia"],
                        d["thanh_tien"],
                        TEN_TRANG_THAI_THUOC.get(d["trang_thai"], ""),
                        ", ".join(k["nguoi_thu"]),
                    ]
                    for k in tt["khach"]
                    for d in k["dong"]
                ],
            )
        )
        sheets.append(
            (
                "Tiêu hao thuốc",
                ["Thuốc", "Đơn vị", "Kê", "Thực bán", "Khách trả", "Tiền"],
                [
                    [
                        r["ten"],
                        r["don_vi"],
                        r["so_ke"],
                        r["thuc_ban"],
                        r["so_tra"],
                        r["tien"],
                    ]
                    for r in tt["tieu_hao"]
                ],
            )
        )
    sheets.append(
        (
            "Giảm giá",
            [
                "Mã lần thu",
                "Lúc thu",
                "Khách",
                "Mã khách",
                "Trạng thái",
                "Trước giảm giá",
                "Giảm giá",
                "Sau giảm giá",
                "Lý do giảm giá",
                "Người giảm giá",
                "Kiểu giảm giá",
                "Giá trị giảm giá",
            ],
            [
                [
                    r["id"],
                    excel_datetime(r["luc"]),
                    r["khach"],
                    r["ma_bn"],
                    r["trang_thai"],
                    r["truoc_giam"],
                    r["giam_gia"],
                    r["sau_giam"],
                    r["ly_do"],
                    r["nguoi"],
                    r["kieu"],
                    r["gia_tri"],
                ]
                for r in bc.get("chi_tiet_giam_gia") or []
            ],
        )
    )
    return excel_table(sheets)
