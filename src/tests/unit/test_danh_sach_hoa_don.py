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
    assert data["tong"]["thu_rong"] == 150
    assert data["tong"]["gia_tri_huy"] == 100


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
    assert book["Theo khách"]["J2"].value == 100
    assert all(
        not sheet.protection.sheet and not sheet.merged_cells.ranges
        for sheet in book.worksheets
    )
