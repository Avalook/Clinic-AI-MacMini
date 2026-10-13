"""Money history must distinguish actual refunds from voids."""

from datetime import datetime, timezone

from clinicai.services.danh_sach_hoa_don_service import gom_hoa_don


def test_void_does_not_invent_refund_and_groups_by_patient() -> None:
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    receipts = [
        dict(
            id="a",
            patient_id="p",
            ten="Khách",
            ma_bn="P1",
            amount=100,
            status="VOIDED",
            paid_at=now,
            trong_ky=True,
            huy_trong_ky=True,
        ),
        dict(
            id="b",
            patient_id="p",
            ten="Khách",
            ma_bn="P1",
            amount=50,
            status="PAID",
            paid_at=now,
            trong_ky=True,
            huy_trong_ky=False,
        ),
    ]
    data = gom_hoa_don(receipts, [], [], [], tim=None, trang_thai=None)
    assert len(data["khach"]) == 1
    assert data["tong"]["da_thu"] == 150
    assert data["tong"]["da_hoan"] == 0
    # Huỷ không phải hoàn (không bịa khoản hoàn) nhưng cũng không còn là tiền
    # của phòng khám: thu ròng = thu − hoàn − huỷ, đúng định nghĩa "thực thu"
    # của báo cáo cuối ngày (staging 12/10 từng lệch 3.255.000đ vì thiếu huỷ).
    assert data["tong"]["gia_tri_huy"] == 100
    assert data["tong"]["thu_rong"] == 50
    t = data["tong"]
    assert t["thu_rong"] == t["da_thu"] - t["da_hoan"] - t["gia_tri_huy"]
    huy = next(p for p in data["khach"][0]["phieu"] if p["trang_thai"] == "DA_HUY")
    assert huy["thu_rong"] == 0 and huy["so_tien"] == 100


def test_completed_date_controls_period_totals_pending_is_separate() -> None:
    receipts = [
        dict(
            id="a",
            patient_id="p",
            amount=100,
            status="PAID",
            trong_ky=False,
            huy_trong_ky=False,
        )
    ]
    refunds = [
        dict(id="r", cycle_id="a", amount=30, status="COMPLETED", trong_ky=True),
        dict(id="s", cycle_id="a", amount=20, status="PENDING", trong_ky=True),
    ]
    data = gom_hoa_don(receipts, refunds, [], [], tim=None, trang_thai=None)
    assert data["tong"]["da_thu"] == 0
    assert data["tong"]["da_hoan"] == 30
    assert data["tong"]["cho_hoan"] == 20
    assert data["tong"]["thu_rong"] == -30
    bill = data["khach"][0]["phieu"][0]
    assert bill["thu_rong"] == 70
    assert bill["trang_thai"] == "CHO_HOAN"
    assert receipts[0] == dict(
        id="a",
        patient_id="p",
        amount=100,
        status="PAID",
        trong_ky=False,
        huy_trong_ky=False,
    )


def test_filter_search_receipt_and_full_customer_totals() -> None:
    receipts = [
        dict(
            id="abcdef1234",
            patient_id="p",
            amount=100,
            status="PAID",
            trong_ky=True,
            huy_trong_ky=False,
            ten="An",
        )
    ]
    assert gom_hoa_don(receipts, [], [], [], tim="PT-ABCDEF12", trang_thai=None)[
        "khach"
    ]
    assert not gom_hoa_don(receipts, [], [], [], tim=None, trang_thai="DA_HUY")["khach"]


def test_zero_bill_is_paid_failed_refund_is_not_money_returned() -> None:
    receipts = [
        dict(
            id="a",
            patient_id="p",
            amount=0,
            status="PAID",
            trong_ky=True,
            huy_trong_ky=False,
        )
    ]
    refunds = [
        dict(
            id="r",
            cycle_id="a",
            amount=20,
            status="FAILED",
            trong_ky=True,
            nguoi_huy="Người đóng",
            closed_reason="Ngân hàng từ chối",
        )
    ]
    data = gom_hoa_don(receipts, refunds, [], [], tim=None, trang_thai=None)
    bill = data["khach"][0]["phieu"][0]
    assert bill["trang_thai"] == "DA_THU"
    assert data["tong"]["da_hoan"] == 0
    assert bill["hoan"][0]["nguoi_huy"] == "Người đóng"


def test_needs_review_filter_and_xlsx_lifetime_period_parity() -> None:
    from io import BytesIO

    from openpyxl import load_workbook

    from clinicai.services.danh_sach_hoa_don_service import xlsx_hoa_don

    receipts = [
        dict(
            id="a",
            patient_id="p",
            amount=100,
            status="VOIDED",
            trong_ky=False,
            huy_trong_ky=True,
        ),
        dict(
            id="b",
            patient_id="q",
            amount=50,
            status="PAID",
            trong_ky=True,
            huy_trong_ky=False,
        ),
    ]
    data = gom_hoa_don(
        receipts, [], [], [], tim=None, trang_thai=None, can_kiem_tra=True
    )
    assert len(data["khach"]) == 1
    assert data["khach"][0]["can_doi_soat"] is True
    assert data["khach"][0]["canh_bao"] == ["Phiếu huỷ cần xác minh tiền trả lại"]
    data.update(tu="2026-10-13", den="2026-10-13")
    book = load_workbook(BytesIO(xlsx_hoa_don(data)))
    assert book["Trong kỳ"]["C2"].value == data["tong"]["da_thu"] == 0
    assert book["Chứng từ"]["G2"].value == 100
    # Khách chỉ có một phiếu đã huỷ: thu ròng 0 (tiền không còn ở phòng khám).
    assert book["Theo khách"]["J2"].value == 0
    assert all(
        not sheet.protection.sheet and not sheet.merged_cells.ranges
        for sheet in book.worksheets
    )


def test_discount_original_actual_and_allocated_are_immutable() -> None:
    from copy import deepcopy
    from decimal import Decimal

    variants = (
        (100, None, 0, None, None),
        (70, 100, 30, "AMOUNT", Decimal("30")),
        (75, 100, 25, "PERCENT", Decimal("25")),
        (0, 100, 100, "PERCENT", Decimal("100")),
    )
    for amount, original, discount, kind, value in variants:
        row = dict(
            id="a",
            patient_id="p",
            amount=amount,
            status="PAID",
            trong_ky=True,
            huy_trong_ky=False,
            original_amount=original,
            discount_amount=discount,
            discount_type=kind,
            discount_value=value,
            discount_reason="Chăm sóc khách" if discount else None,
            nguoi_giam="Thu ngân" if discount else None,
        )
        line = dict(
            id="l",
            cycle_id="a",
            so_luong=1,
            thanh_tien=amount,
            discount_allocated=discount,
        )
        saved = deepcopy((row, line))
        data = gom_hoa_don([row], [], [line], [], tim=None, trang_thai=None)
        bill = data["khach"][0]["phieu"][0]
        assert bill["tong_truoc_giam"] == 100
        assert bill["giam_gia"] == discount
        assert bill["so_tien"] == bill["thu_rong"] == amount
        assert bill["trang_thai"] == "DA_THU"
        assert bill["kieu_giam"] == kind
        assert bill["gia_tri_giam"] == (float(value) if value is not None else None)
        assert bill["nguoi_giam"] == row["nguoi_giam"]
        assert bill["dong"][0]["thanh_tien_truoc_giam"] == 100
        assert bill["dong"][0]["giam_gia"] == discount
        assert data["tong"]["giam_gia"] == data["khach"][0]["giam_gia"] == discount
        assert data["tong"]["tong_truoc_giam"] == 100
        assert (row, line) == saved


def test_discount_excel_columns_and_cross_day_refund_do_not_double_count() -> None:
    from io import BytesIO

    from openpyxl import load_workbook

    from clinicai.services.danh_sach_hoa_don_service import xlsx_hoa_don

    row = dict(
        id="a",
        patient_id="p",
        amount=70,
        status="PAID",
        trong_ky=False,
        huy_trong_ky=False,
        original_amount=100,
        discount_amount=30,
        discount_type="AMOUNT",
        discount_value=30,
        discount_reason="Ưu đãi",
        nguoi_giam="Thu ngân",
    )
    line = dict(
        id="l",
        cycle_id="a",
        so_luong=1,
        thanh_tien=70,
        discount_allocated=30,
        ten="Dịch vụ",
        da_bo=False,
    )
    refund = dict(id="r", cycle_id="a", amount=20, status="COMPLETED", trong_ky=True)
    data = gom_hoa_don([row], [refund], [line], [], tim=None, trang_thai=None)
    assert data["tong"]["giam_gia"] == data["tong"]["tong_truoc_giam"] == 0
    assert data["tong"]["thu_rong"] == -20
    assert data["khach"][0]["thu_rong"] == 50
    data.update(tu="2026-10-13", den="2026-10-13")
    book = load_workbook(BytesIO(xlsx_hoa_don(data)))
    for sheet, expected in (
        (
            "Chứng từ",
            {
                "Tổng tiền hàng": 100,
                "Giảm giá": 30,
                "Lý do giảm": "Ưu đãi",
                "Người giảm": "Thu ngân",
                "Tiền đã thu toàn phiếu": 70,
            },
        ),
        (
            "Chi tiết",
            {"Thành tiền": 70, "Thành tiền trước giảm": 100, "Giảm giá phân bổ": 30},
        ),
        ("Theo khách", {"Giảm giá toàn chứng từ": 30, "Thực thu toàn chứng từ": 50}),
        ("Trong kỳ", {"Giảm giá trong kỳ": 0, "Thực thu": -20}),
    ):
        ws = book[sheet]
        cells = {cell.value: ws.cell(2, cell.column) for cell in ws[1]}
        for label, value in expected.items():
            assert cells[label].value == value
            if isinstance(value, int):
                assert cells[label].data_type == "n"


def test_su_kien_sau_thu_theo_gio_va_huy_sau_bao_lau() -> None:
    from datetime import timedelta

    from clinicai.services.hoa_don_projection import gom_hoa_don

    thu = datetime(2026, 10, 13, 6, 0, tzinfo=timezone.utc)
    receipts = [
        dict(
            id="c1",
            patient_id="p",
            visit_id="v",
            kind="dich_vu",
            amount=700,
            status="VOIDED",
            paid_at=thu,
            closed_at=thu + timedelta(seconds=52),
            close_reason="thao tác nhầm",
            nguoi_huy="Lan",
            trong_ky=True,
            huy_trong_ky=True,
        )
    ]
    doi = [
        dict(
            cycle_id="c1",
            method_cu="CASH",
            method_moi="TRANSFER",
            luc=thu + timedelta(seconds=10),
            nguoi="Lan",
            ly_do=None,
        )
    ]
    [khach] = gom_hoa_don(
        receipts, [], [], [], tim=None, trang_thai=None, doi_hinh_thuc=doi
    )["khach"]
    ev = khach["phieu"][0]["su_kien"]
    assert [e["loai"] for e in ev] == ["DOI_HINH_THUC", "HUY_PHIEU"]
    assert ev[0]["mo_ta"] == "Tiền mặt → Chuyển khoản"
    assert ev[1]["sau_giay"] == 52 and ev[1]["so_tien"] == -700
    assert khach["co_phieu_huy"] is True
    assert (khach["da_thu_dich_vu"], khach["da_thu_thuoc"]) == (700, 0)


def test_viec_ton_cu_nhat_truoc_va_khach_con_viec_len_dau() -> None:
    from clinicai.services.hoa_don_projection import gom_hoa_don, gom_viec_ton

    k = dict(patient_id="p2", ten="B", ma_bn="B2")
    ton = gom_viec_ton(
        hoan=[],
        ck=[
            dict(
                k,
                payment_cycle_id="c9",
                visit_id="v2",
                kind="dich_vu",
                amount=150,
                created_at=datetime(2026, 10, 13, 7, tzinfo=timezone.utc),
            )
        ],
        no=[
            dict(
                k,
                visit_id="v3",
                so_tien=400,
                ly_do="quên ví",
                ghi_luc=datetime(2026, 10, 11, 9, tzinfo=timezone.utc),
            )
        ],
        tien_thua={},
        luot={},
    )
    assert [v["loai"] for v in ton] == ["GHI_NO", "CK_CHUA_VE"]
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    receipts = [
        dict(
            id=i,
            patient_id=p,
            visit_id=v,
            kind="thuoc",
            amount=10,
            status="PAID",
            paid_at=now,
            trong_ky=True,
            huy_trong_ky=False,
        )
        for i, p, v in (("a", "p1", "v1"), ("b", "p2", "v2"))
    ]
    data = gom_hoa_don(receipts, [], [], [], tim=None, trang_thai=None, viec_ton=ton)
    assert [g["id"] for g in data["khach"]] == ["p2", "p1"]
    assert data["tong"]["so_viec_ton"] == 2
    assert len(data["khach"][0]["viec_ton"]) == 2
    only = gom_hoa_don(
        receipts, [], [], [], tim=None, trang_thai="CON_VIEC_TON", viec_ton=ton
    )
    assert [g["id"] for g in only["khach"]] == ["p2"]


def test_moi_sheet_co_ma_khach_deu_co_ten_khach() -> None:
    """Người đối soát đọc theo TÊN khách — sheet chỉ có mã thì phải tra ngược."""
    from io import BytesIO

    from openpyxl import load_workbook

    from clinicai.services.danh_sach_hoa_don_service import xlsx_hoa_don
    from clinicai.services.hoa_don_projection import gom_hoa_don

    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    receipts = [
        dict(
            id="c1",
            patient_id="p",
            ten="Nguyễn Thị A",
            ma_bn="BN1",
            visit_id="v",
            kind="dich_vu",
            amount=100,
            status="PAID",
            paid_at=now,
            trong_ky=True,
            huy_trong_ky=False,
        )
    ]
    lines = [
        dict(
            id="l1",
            cycle_id="c1",
            ten="Siêu âm",
            so_luong=1,
            thanh_tien=100,
            da_bo=False,
        )
    ]
    refunds = [
        dict(
            id="r1",
            cycle_id="c1",
            amount=30,
            status="COMPLETED",
            completed_at=now,
            trong_ky=True,
        )
    ]
    data = gom_hoa_don(receipts, refunds, lines, [], tim=None, trang_thai=None)
    data.update(tu="2026-10-13", den="2026-10-13")
    book = load_workbook(BytesIO(xlsx_hoa_don(data)))
    thieu = []
    for ws in book.worksheets:
        dau = [c.value for c in ws[1]]
        if "Mã khách" in dau and "Khách" not in dau:
            thieu.append(ws.title)
    assert not thieu, f"Sheet thiếu tên khách: {thieu}"
    assert book["Chi tiết"]["B2"].value == "Nguyễn Thị A"
    assert book["Hoàn tiền"]["B2"].value == "Nguyễn Thị A"
