"""Lọc Tiền mặt / Chuyển khoản ở Danh sách hoá đơn phải khớp Báo cáo cuối ngày.

Lỗi đã gặp: phiếu trả cả hai hình thức bị xếp nguyên vào Chuyển khoản, nên ô
Thực thu lệch Báo cáo đúng bằng phần tiền mặt của phiếu đó. Số ở đây là số mẫu.
"""

from datetime import date
from typing import Any

import pytest

from clinicai.services.bao_cao_cuoi_ngay_service import gom_bao_cao
from clinicai.services.hoa_don_projection import gom_hoa_don


def _row(
    i: str, amount: int, method: str, phan: list[Any] | None, **kw: Any
) -> dict[str, Any]:
    return {
        "id": i,
        "visit_id": f"v-{i}",
        "kind": "dich_vu",
        "amount": amount,
        "status": "PAID",
        "method": method,
        "phan": phan,
        "patient_id": f"k-{i}",
        "ten": "Khách",
        "ma_bn": i,
        "so_dien_thoai": None,
        "can_doi_soat": False,
        "doi_soat_ly_do": [],
        "so_tien_thuc_nhan": None,
        "trong_ky": True,
        "huy_trong_ky": False,
        **kw,
    }


def _hai_phan(tm: int, ck: int) -> list[dict[str, Any]]:
    return [
        {"hinh_thuc": "CASH", "so_tien": tm, "khach_dua": None},
        {"hinh_thuc": "TRANSFER", "so_tien": ck, "khach_dua": None},
    ]


def _hoan(cycle: str, so: int, method: str) -> dict[str, Any]:
    return {
        "id": f"h-{cycle}-{method}",
        "cycle_id": cycle,
        "amount": so,
        "status": "COMPLETED",
        "created_at": None,
        "completed_at": None,
        "closed_at": None,
        "nguoi_lap": None,
        "nguoi_hoan": None,
        "nguoi_huy": None,
        "closed_reason": None,
        "reason": None,
        "method": method,
        "trong_ky": True,
    }


def _tong(
    rows: list[dict[str, Any]], hoan: list[dict[str, Any]], ht: str | None
) -> dict[str, Any]:
    return gom_hoa_don(rows, hoan, [], [], tim=None, trang_thai=None, hinh_thuc=ht)


def _ngay_mau() -> list[dict[str, Any]]:
    """Một ngày mẫu: 1 phiếu huỷ + 1 phiếu thu lại, cùng chia hai hình thức."""
    giam = {"original_amount": 900_000, "discount_amount": 153_000}
    return [
        _row("thuong-ck", 2_605_000, "TRANSFER", None),
        _row("thuong-tm", 895_000, "CASH", None),
        _row(
            "huy",
            747_000,
            "TRANSFER",
            _hai_phan(220_000, 527_000),
            status="VOIDED",
            huy_trong_ky=True,
            **giam,
        ),
        _row("lan", 747_000, "TRANSFER", _hai_phan(220_000, 527_000), **giam),
    ]


def test_mot_ngay_loc_tien_mat_ra_dung_so_bao_cao() -> None:
    t = _tong(_ngay_mau(), [], "CASH")["tong"]
    assert t["thu_rong"] == 1_115_000
    assert t["da_thu"] == 1_335_000
    assert t["gia_tri_huy"] == 220_000


def test_mot_ngay_loc_chuyen_khoan_ra_dung_so_bao_cao() -> None:
    t = _tong(_ngay_mau(), [], "TRANSFER")["tong"]
    assert t["thu_rong"] == 3_132_000
    assert t["da_thu"] == 3_659_000
    assert t["gia_tri_huy"] == 527_000


def test_phieu_hai_hinh_thuc_hien_o_ca_hai_bo_loc() -> None:
    rows = [_row("lan", 1_750_000, "TRANSFER", _hai_phan(300_000, 1_450_000))]
    tm = _tong(rows, [], "CASH")
    ck = _tong(rows, [], "TRANSFER")
    assert tm["tong"]["so_phieu"] == ck["tong"]["so_phieu"] == 1
    assert tm["khach"][0]["phieu"][0]["so_tien"] == 300_000
    assert ck["khach"][0]["phieu"][0]["so_tien"] == 1_450_000


def test_khong_loc_giu_nguyen_ca_phieu() -> None:
    rows = [_row("lan", 1_750_000, "TRANSFER", _hai_phan(300_000, 1_450_000))]
    p = _tong(rows, [], None)["khach"][0]["phieu"][0]
    assert p["so_tien"] == 1_750_000
    assert "phan_ca_phieu" not in p


def test_ghi_ro_dang_xem_mot_phan_cua_phieu() -> None:
    rows = [_row("lan", 1_750_000, "TRANSFER", _hai_phan(300_000, 1_450_000))]
    p = _tong(rows, [], "CASH")["khach"][0]["phieu"][0]
    assert p["phan_ca_phieu"]["so_tien"] == 1_750_000
    assert p["nhan_hinh_thuc"] == "Tiền mặt 300.000đ + Chuyển khoản 1.450.000đ"


def test_giam_gia_chia_theo_ty_le_giu_chuoi_tinh() -> None:
    """Tổng tiền hàng − Giảm giá = Tiền đã thu ở từng bộ lọc, hai bộ lọc cộng đủ."""
    rows = [
        _row(
            "lan",
            747_000,
            "TRANSFER",
            _hai_phan(220_000, 527_000),
            original_amount=900_000,
            discount_amount=153_000,
        ),
    ]
    a, b = _tong(rows, [], "CASH")["tong"], _tong(rows, [], "TRANSFER")["tong"]
    for t in (a, b):
        assert t["tong_truoc_giam"] - t["giam_gia"] == t["da_thu"]
    assert a["giam_gia"] + b["giam_gia"] == 153_000
    assert a["tong_truoc_giam"] + b["tong_truoc_giam"] == 900_000


def test_hoan_tien_mat_tren_phieu_chuyen_khoan_tinh_vao_tien_mat() -> None:
    """Báo cáo trừ theo hình thức của KHOẢN HOÀN."""
    rows = [_row("ck", 1_000_000, "TRANSFER", None)]
    hoan = [_hoan("ck", 200_000, "CASH")]
    tm = _tong(rows, hoan, "CASH")["tong"]
    ck = _tong(rows, hoan, "TRANSFER")["tong"]
    assert (tm["da_thu"], tm["da_hoan"], tm["thu_rong"]) == (0, 200_000, -200_000)
    assert (ck["da_thu"], ck["da_hoan"], ck["thu_rong"]) == (1_000_000, 0, 1_000_000)


def test_huy_sau_hoan_mot_phan_khong_tru_hai_lan() -> None:
    rows = [
        _row(
            "h",
            700_000,
            "TRANSFER",
            _hai_phan(500_000, 200_000),
            status="VOIDED",
            huy_trong_ky=True,
        ),
    ]
    hoan = [_hoan("h", 100_000, "CASH")]
    tm = _tong(rows, hoan, "CASH")["tong"]
    ck = _tong(rows, hoan, "TRANSFER")["tong"]
    assert tm["gia_tri_huy"] + ck["gia_tri_huy"] == 600_000
    assert tm["thu_rong"] + ck["thu_rong"] == 0


def test_tai_khoan_nhan_khong_hien_o_bo_loc_tien_mat() -> None:
    rows = [
        _row(
            "lan",
            1_750_000,
            "TRANSFER",
            _hai_phan(300_000, 1_450_000),
            tai_khoan_id="tk",
            ten_tai_khoan="VCB",
        )
    ]
    assert _tong(rows, [], "CASH")["theo_tai_khoan"] == []
    ck = _tong(rows, [], "TRANSFER")["theo_tai_khoan"]
    assert ck[0]["thuc_thu"] == 1_450_000


@pytest.mark.parametrize(
    ("rows", "hoan"),
    [
        (_ngay_mau(), []),
        ([_row("ck", 1_000_000, "TRANSFER", None)], [_hoan("ck", 200_000, "CASH")]),
        (
            [
                _row(
                    "h",
                    700_000,
                    "TRANSFER",
                    _hai_phan(500_000, 200_000),
                    status="VOIDED",
                    huy_trong_ky=True,
                )
            ],
            [_hoan("h", 100_000, "CASH")],
        ),
        ([_row("t", 500_000, "CASH", None), _row("mien", 0, "CASH", None)], []),
    ],
)
def test_hai_bo_loc_cong_lai_bang_khong_loc_va_khop_bao_cao(
    rows: list[dict[str, Any]], hoan: list[dict[str, Any]]
) -> None:
    ca, tm, ck = (
        _tong(rows, hoan, None)["tong"],
        _tong(rows, hoan, "CASH")["tong"],
        _tong(rows, hoan, "TRANSFER")["tong"],
    )
    for k in (
        "da_thu",
        "da_hoan",
        "thu_rong",
        "gia_tri_huy",
        "giam_gia",
        "tong_truoc_giam",
    ):
        assert tm[k] + ck[k] == ca[k], k

    lan_thu = [
        {
            "id": r["id"],
            "amount": r["amount"],
            "status": r["status"],
            "method": r["method"],
            "phan": r["phan"] or [{"hinh_thuc": r["method"], "so_tien": r["amount"]}],
            "paid_at": None,
            "da_hoan": sum(h["amount"] for h in hoan if h["cycle_id"] == r["id"]),
            "da_hoan_tm": sum(
                h["amount"]
                for h in hoan
                if h["cycle_id"] == r["id"] and h["method"] == "CASH"
            ),
        }
        for r in rows
    ]
    bc = gom_bao_cao(
        tu=date(2026, 10, 22),
        den=date(2026, 10, 22),
        lan_thu=lan_thu,
        hoan=[
            {"amount": h["amount"], "status": "COMPLETED", "method": h["method"]}
            for h in hoan
        ],
        dong=[],
        doi_tac=[],
        so_luot_kham=0,
    )
    theo = {r["ma"]: r["thuc_thu"] for r in bc["theo_hinh_thuc"]}
    assert theo.get("CASH", 0) == tm["thu_rong"]
    assert theo.get("TRANSFER", 0) == ck["thu_rong"]
