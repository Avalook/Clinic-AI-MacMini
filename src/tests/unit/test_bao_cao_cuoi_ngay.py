"""Báo cáo cuối ngày (29/09/2026) — hàm thuần, không cần DB."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.bao_cao_cuoi_ngay_service import (
    csv_bao_cao,
    doc_khoang,
    gom_bao_cao,
)


def _hom_nay() -> date:
    return datetime.now(CLINIC_TZ).date()


@pytest.mark.parametrize(
    ("tu", "den"),
    [
        (None, None),
        ("", ""),
        ("rác", "2026-13-45"),
        (123, ["x"]),
        ("'; DROP TABLE visit; --", None),
    ],
)
def test_ngay_rac_ve_hom_nay_khong_nem(tu: Any, den: Any) -> None:
    assert doc_khoang(tu, den) == (_hom_nay(), _hom_nay())


def test_ngay_dao_chieu_thi_doi_cho_va_toi_da_92_ngay() -> None:
    assert doc_khoang("2026-09-20", "2026-09-10") == (
        date(2026, 9, 10),
        date(2026, 9, 20),
    )
    a, b = doc_khoang("2025-01-01", "2026-09-29")
    assert b == date(2026, 9, 29) and (b - a).days == 92


VN = timezone(timedelta(hours=7))
LUC = datetime(2026, 9, 29, 9, 0, tzinfo=VN)
LUC2 = datetime(2026, 9, 30, 23, 30, tzinfo=VN)  # 23:30 giờ VN vẫn là ngày 30


def _thu(
    id_: str,
    kind: str,
    so: int,
    ht: str | None,
    *,
    huy: bool = False,
    nguoi: str = "Thu A",
    luc: datetime = LUC,
    visit: str = "v1",
    khach: str = "k1",
) -> dict[str, Any]:
    return {
        "id": id_,
        "visit_id": visit,
        "khach_id": khach,
        "kind": kind,
        "status": "VOIDED" if huy else "PAID",
        "amount": so,
        "method": ht,
        "paid_at": luc,
        "closed_at": luc if huy else None,
        "close_reason": "Thu nhầm khách" if huy else None,
        "nguoi_thu": nguoi,
        "nguoi_huy": "QL" if huy else None,
        "ten_khach": "BN",
        "ma_bn": "BN-1",
    }


def _bc(**kw: Any) -> dict[str, Any]:
    tu = date(2026, 9, 29)
    goc: dict[str, Any] = {
        "tu": tu,
        "den": tu,
        "lan_thu": [],
        "hoan": [],
        "dong": [],
        "doi_tac": [],
        "so_luot_kham": 0,
        "so_luot_khong_chon_dich_vu_kham": 0,
    }
    goc.update(kw)
    return gom_bao_cao(**goc)


def test_dem_luot_khong_chon_dich_vu_kham() -> None:
    bc = _bc(so_luot_kham=9, so_luot_khong_chon_dich_vu_kham=4)
    assert bc["khach"]["so_luot_kham"] == 9
    assert bc["khach"]["so_luot_khong_chon_dich_vu_kham"] == 4


def test_gom_so_tm_ck_hoan_huy_thuoc() -> None:
    bc = _bc(
        lan_thu=[
            _thu("c1", "dich_vu", 700_000, "CASH"),
            _thu(
                "c2",
                "dich_vu",
                150_000,
                "TRANSFER",
                nguoi="Thu B",
                visit="v2",
                khach="k2",
            ),
            _thu("c3", "dich_vu", 150_000, "CASH", huy=True, visit="v3", khach="k3"),
            _thu("c4", "thuoc", 80_000, "QR", visit="v1"),
        ],
        hoan=[
            {
                "refund_id": "r1",
                "visit_id": "v1",
                "kind": "dich_vu",
                "amount": 300_000,
                "status": "COMPLETED",
                "method": "CASH",
                "reason": "khách không làm soi",
                "created_at": LUC,
                "nguoi": "QL",
                "ten_khach": "BN",
                "ma_bn": "BN-1",
            },
            {
                "refund_id": "r2",
                "visit_id": "v2",
                "kind": "dich_vu",
                "amount": 50_000,
                "status": "PENDING",
                "method": "TRANSFER",
                "reason": "chờ chuyển lại",
                "created_at": LUC,
                "nguoi": "QL",
                "ten_khach": "BN",
                "ma_bn": "BN-2",
            },
        ],
        dong=[
            {
                "cycle_id": "c1",
                "source_type": "exam",
                "ten": "Khám",
                "so_luong": 1,
                "thanh_tien": 150_000,
            },
            {
                "cycle_id": "c1",
                "source_type": "service_order",
                "ten": "Soi",
                "so_luong": 1,
                "thanh_tien": 300_000,
            },
            {
                "cycle_id": "c1",
                "source_type": "service_order",
                "ten": "SA",
                "so_luong": 1,
                "thanh_tien": 250_000,
            },
            {
                "cycle_id": "c2",
                "source_type": "exam",
                "ten": "Khám",
                "so_luong": 1,
                "thanh_tien": 150_000,
            },
            # phiếu huỷ + thuốc: không vào top dịch vụ
            {
                "cycle_id": "c3",
                "source_type": "exam",
                "ten": "Khám",
                "so_luong": 1,
                "thanh_tien": 150_000,
            },
            {
                "cycle_id": "c4",
                "source_type": "prescription",
                "ten": "Thuốc X",
                "so_luong": 2,
                "thanh_tien": 80_000,
            },
        ],
        doi_tac=[
            {
                "id": "d1",
                "so_tien": 900_000,
                "hinh_thuc": "CASH",
                "ghi_luc": LUC,
                "ten": "HPV",
                "nguoi": "ĐT",
                "ten_khach": "BN",
                "ma_bn": "BN-1",
            }
        ],
        so_luot_kham=5,
    )
    t = bc["tong"]
    assert (t["thu"], t["huy"], t["hoan"], t["thuc_thu"], t["hoan_cho"]) == (
        1_080_000,
        150_000,
        300_000,
        630_000,
        50_000,
    )
    assert (t["so_phieu_thu"], t["so_phieu_huy"], t["so_phieu_hoan"]) == (4, 1, 1)
    ht = {o["ma"]: o for o in bc["theo_hinh_thuc"]}
    assert (
        ht["CASH"]["thu"],
        ht["CASH"]["huy"],
        ht["CASH"]["hoan"],
        ht["CASH"]["thuc_thu"],
    ) == (
        850_000,
        150_000,
        300_000,
        400_000,
    )
    assert ht["TRANSFER"]["thuc_thu"] == 150_000 and ht["QR"]["thuc_thu"] == 80_000
    assert "KHAC" not in ht
    # Tổng theo hình thức = tổng chung (không suy đoán, không rơi đồng nào).
    assert sum(o["thuc_thu"] for o in bc["theo_hinh_thuc"]) == t["thuc_thu"]
    loai = {o["ma"]: o["thuc_thu"] for o in bc["theo_loai"]}
    assert loai == {"dich_vu": 550_000, "thuoc": 80_000}
    nguoi = {o["ten"]: o for o in bc["theo_nguoi_thu"]}
    assert nguoi["Thu A"]["thu"] == 930_000 and nguoi["Thu A"]["huy"] == 150_000
    assert nguoi["Thu B"]["thuc_thu"] == 150_000
    assert [(o["loai"], o["cho"]) for o in bc["hoan_huy"]] == [
        ("huy", False),
        ("hoan", False),
        ("hoan", True),
    ]
    assert bc["hoan_huy"][0]["ly_do"] == "Thu nhầm khách"
    # Khách: v3 chỉ có phiếu huỷ → không tính "đã thu".
    assert bc["khach"] == {
        "so_luot_kham": 5,
        "so_luot_khong_chon_dich_vu_kham": 0,
        "so_luot_da_thu": 2,
        "so_khach_da_thu": 2,
        "so_luot_ban_le": 0,
    }
    assert bc["doi_tac"]["tong"] == 900_000
    assert [(o["ten"], o["doanh_thu"]) for o in bc["top_dich_vu"]] == [
        ("Khám", 300_000),
        ("Soi", 300_000),
        ("SA", 250_000),
    ]
    assert bc["theo_ngay"] == []  # một ngày → không bảng theo ngày


def test_theo_ngay_khi_chon_khoang_du_moi_ngay_va_gio_vn() -> None:
    bc = _bc(
        tu=date(2026, 9, 29),
        den=date(2026, 10, 1),
        lan_thu=[
            _thu("c1", "dich_vu", 100_000, "CASH"),
            _thu(
                "c2", "dich_vu", 200_000, None, luc=LUC2
            ),  # dữ liệu cũ: không phương thức
        ],
    )
    assert [(o["ngay"], o["thuc_thu"], o["so_phieu"]) for o in bc["theo_ngay"]] == [
        ("2026-09-29", 100_000, 1),
        ("2026-09-30", 200_000, 1),
        ("2026-10-01", 0, 0),
    ]
    ht = {o["ma"]: o["thu"] for o in bc["theo_hinh_thuc"]}
    assert ht["KHAC"] == 200_000


def test_rong_khong_nem_va_csv_co_bom_chong_cong_thuc() -> None:
    bc = _bc()
    assert bc["tong"]["thuc_thu"] == 0 and bc["top_dich_vu"] == []
    bc = _bc(
        lan_thu=[_thu("c1", "dich_vu", 100_000, "CASH", huy=True, nguoi="=HACK()")]
    )
    out = csv_bao_cao(bc)
    assert out.startswith("﻿")
    assert "'=HACK()" in out and "Huỷ phiếu" in out
