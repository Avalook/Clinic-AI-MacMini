"""Tài khoản nhận chuyển khoản (31/10/2026) — hàm thuần, không cần DB.

Bất biến chính: tổng các dòng ``theo_tai_khoan`` của báo cáo cuối ngày = đúng
dòng Chuyển khoản của ``theo_hinh_thuc`` (thu / huỷ / hoàn / thực thu), kể cả
lần thu chia TM + CK, lần thu cũ không có tài khoản ("Chưa phân loại") và hoàn.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.bao_cao_cuoi_ngay_service import csv_bao_cao, gom_bao_cao
from clinicai.services.hoa_don_projection import tach_tai_khoan
from clinicai.services.phan_thu import doc_phan, tai_khoan_chon
from clinicai.services.tai_khoan_nhan_service import (
    CHUA_PHAN_LOAI,
    chon_mac_dinh,
    chuan_so_tai_khoan,
    doc_form,
    doc_id,
    dung_duoc,
)

VN = timezone(timedelta(hours=7))
LUC = datetime(2026, 10, 31, 9, 0, tzinfo=VN)
HN = "11111111-1111-1111-1111-111111111111"
KN = "22222222-2222-2222-2222-222222222222"
A = "aaaaaaaa-0000-0000-0000-000000000001"
B = "aaaaaaaa-0000-0000-0000-000000000002"
C = "aaaaaaaa-0000-0000-0000-000000000003"


def _tk(
    id_: str, loc: str | None, *, md: bool = False, dung: bool = True
) -> dict[str, Any]:
    return {"id": id_, "location_id": loc, "mac_dinh": md, "dang_dung": dung}


# ── chọn mặc định ───────────────────────────────────────────────────────────


def test_mot_tai_khoan_dung_duoc_thi_tu_chon() -> None:
    assert chon_mac_dinh([_tk(A, HN)], HN) == A
    # Tài khoản của cơ sở khác không tính; dùng chung thì tính.
    assert chon_mac_dinh([_tk(A, KN), _tk(B, None)], HN) == B


def test_mac_dinh_co_so_thang_mac_dinh_dung_chung() -> None:
    ds = [_tk(A, None, md=True), _tk(B, HN, md=True), _tk(C, HN)]
    assert chon_mac_dinh(ds, HN) == B
    assert chon_mac_dinh(ds, KN) == A


def test_nhieu_tai_khoan_khong_mac_dinh_thi_de_trong() -> None:
    assert chon_mac_dinh([_tk(A, HN), _tk(B, HN)], HN) is None


def test_tat_tai_khoan_mac_dinh_thi_roi_ve_tai_khoan_con_lai() -> None:
    # Tắt = dang_dung false (mặc định cũng bỏ): còn MỘT tài khoản → tự chọn.
    ds = [_tk(A, HN, md=False, dung=False), _tk(B, HN)]
    assert chon_mac_dinh(ds, HN) == B
    assert not dung_duoc(ds[0], HN)


def test_khong_co_tai_khoan_nao() -> None:
    assert chon_mac_dinh([], HN) is None


# ── đầu vào rác ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("rac", ["x", "123", "'; DROP TABLE x; --", 12, "aaaa-bbbb"])
def test_ma_tai_khoan_rac_thi_422(rac: Any) -> None:
    with pytest.raises(ValidationError):
        doc_id(rac)


def test_ma_rong_la_none() -> None:
    assert doc_id(None) is None
    assert doc_id("  ") is None
    assert doc_id(A.upper()) == A


@pytest.mark.parametrize("rac", [None, "", "12", "abc-!@#", 123, "1" * 31])
def test_so_tai_khoan_rac(rac: Any) -> None:
    with pytest.raises(ValidationError):
        chuan_so_tai_khoan(rac)


def test_so_tai_khoan_bo_dau_cach() -> None:
    assert chuan_so_tai_khoan(" 0123 456.789-0 ") == "01234567890"


def test_form_mac_dinh_phai_dang_dung() -> None:
    f = doc_form(
        {
            "ten_goi": " VCB  Hào Nam ",
            "ngan_hang": "Vietcombank",
            "so_tai_khoan": "0123456789",
            "chu_tai_khoan": "CONG TY DR4WOMEN",
            "mac_dinh": True,
            "dang_dung": False,
        }
    )
    assert f["ten_goi"] == "VCB Hào Nam"
    assert (f["mac_dinh"], f["dang_dung"], f["location_id"]) == (False, False, None)
    with pytest.raises(ValidationError, match="Tên gọi"):
        doc_form({"ten_goi": "", "ngan_hang": "x", "so_tai_khoan": "1234"})


def test_phan_mang_tai_khoan_chi_cho_chuyen_khoan() -> None:
    phan = doc_phan(
        [
            {"hinh_thuc": "CASH", "so_tien": 100, "tai_khoan_id": A},
            {"hinh_thuc": "TRANSFER", "so_tien": 50, "tai_khoan_id": B},
        ]
    )
    assert phan is not None
    assert [p.tai_khoan_id for p in phan] == [None, B]
    assert tai_khoan_chon(phan) == B
    # Không chọn tài khoản → dấu băm của lần thu giữ nguyên dạng cũ.
    cu = doc_phan([{"hinh_thuc": "TRANSFER", "so_tien": 50}])
    assert cu is not None and "tai_khoan_id" not in cu[0].ra_dict()
    with pytest.raises(ValidationError, match="Tài khoản nhận"):
        doc_phan([{"hinh_thuc": "TRANSFER", "so_tien": 50, "tai_khoan_id": "rac"}])


# ── báo cáo: tổng theo tài khoản = dòng Chuyển khoản ───────────────────────


def _lan(
    i: int, phan: list[tuple[str, int]], tk: str | None, *, huy: bool = False
) -> dict[str, Any]:
    return {
        "id": f"c{i}",
        "visit_id": f"v{i}",
        "kind": "dich_vu",
        "status": "VOIDED" if huy else "PAID",
        "amount": sum(s for _, s in phan),
        "method": "TRANSFER" if any(h == "TRANSFER" for h, _ in phan) else "CASH",
        "phan": [{"hinh_thuc": h, "so_tien": s} for h, s in phan],
        "tai_khoan_id": tk,
        "paid_at": LUC,
        "closed_at": LUC if huy else None,
        "nguoi_thu": "Thu A",
    }


def _hoan(i: int, so: int, method: str, tk: str | None) -> dict[str, Any]:
    return {
        "refund_id": f"r{i}",
        "visit_id": f"v{i}",
        "kind": "dich_vu",
        "amount": so,
        "status": "COMPLETED",
        "method": method,
        "tai_khoan_id": tk,
        "created_at": LUC,
    }


def _bc(lan: list[dict[str, Any]], hoan: list[dict[str, Any]]) -> dict[str, Any]:
    return gom_bao_cao(
        tu=date(2026, 10, 31),
        den=date(2026, 10, 31),
        lan_thu=lan,
        hoan=hoan,
        dong=[],
        doi_tac=[],
        so_luot_kham=0,
        ten_tai_khoan={A: "VCB · 01", B: "TCB · 02"},
    )


def _kiem_bat_bien(bc: dict[str, Any]) -> None:
    ck = next(r for r in bc["theo_hinh_thuc"] if r["ma"] == "TRANSFER")
    for k in ("thu", "huy", "hoan", "thuc_thu"):
        assert sum(r[k] for r in bc["theo_tai_khoan"]) == ck[k], k


def test_tach_dung_tung_tai_khoan_va_chua_phan_loai() -> None:
    bc = _bc(
        [
            _lan(1, [("CASH", 500_000), ("TRANSFER", 200_000)], A),
            _lan(2, [("TRANSFER", 300_000)], B),
            _lan(3, [("TRANSFER", 100_000)], None),  # lần thu cũ
            _lan(4, [("TRANSFER", 50_000)], A, huy=True),
            _lan(5, [("CASH", 70_000)], None),
        ],
        [_hoan(2, 40_000, "TRANSFER", B), _hoan(5, 10_000, "CASH", None)],
    )
    tk = {r["ten"]: r for r in bc["theo_tai_khoan"]}
    assert tk["VCB · 01"]["thu"] == 250_000 and tk["VCB · 01"]["huy"] == 50_000
    assert tk["VCB · 01"]["thuc_thu"] == 200_000
    assert tk["TCB · 02"]["hoan"] == 40_000 and tk["TCB · 02"]["thuc_thu"] == 260_000
    assert tk[CHUA_PHAN_LOAI]["thuc_thu"] == 100_000
    # "Chưa phân loại" đứng cuối.
    assert bc["theo_tai_khoan"][-1]["id"] is None
    _kiem_bat_bien(bc)
    csv = csv_bao_cao(bc)
    assert "Chuyển khoản theo tài khoản" in csv and "TCB · 02" in csv


def test_bat_bien_bam_ngau_nhien() -> None:
    rnd = random.Random(31102026)
    for _ in range(200):
        lan, hoan = [], []
        for i in range(rnd.randint(0, 12)):
            kieu = rnd.choice(["tm", "ck", "chia"])
            so = rnd.randint(1, 50) * 10_000
            phan = (
                [("CASH", so)]
                if kieu == "tm"
                else [("TRANSFER", so)]
                if kieu == "ck"
                else [("CASH", so), ("TRANSFER", rnd.randint(1, 9) * 10_000)]
            )
            lan.append(_lan(i, phan, rnd.choice([A, B, None]), huy=rnd.random() < 0.2))
            if rnd.random() < 0.3:
                hoan.append(
                    _hoan(
                        i,
                        rnd.randint(1, 5) * 1_000,
                        rnd.choice(["CASH", "TRANSFER", "QR"]),
                        rnd.choice([A, B, None]),
                    )
                )
        _kiem_bat_bien(_bc(lan, hoan))


def test_danh_sach_hoa_don_tach_tai_khoan() -> None:
    bills: list[dict[str, Any]] = [
        {
            "chuyen_khoan": 200_000,
            "tai_khoan_id": A,
            "ten_tai_khoan": "VCB · 01",
            "trang_thai_goc": "PAID",
            "thu_trong_ky": True,
            "huy_trong_ky": False,
            "hoan": [
                {
                    "trong_ky": True,
                    "trang_thai": "COMPLETED",
                    "hinh_thuc": "TRANSFER",
                    "tai_khoan_id": A,
                    "ten_tai_khoan": "VCB · 01",
                    "so_tien": 20_000,
                }
            ],
        },
        {
            "chuyen_khoan": 90_000,
            "tai_khoan_id": None,
            "trang_thai_goc": "PAID",
            "thu_trong_ky": True,
            "huy_trong_ky": False,
            "hoan": [],
        },
        # Lần chờ CK đã huỷ: không phải tiền đã thu.
        {
            "chuyen_khoan": 70_000,
            "tai_khoan_id": B,
            "trang_thai_goc": "CANCELLED",
            "thu_trong_ky": False,
            "huy_trong_ky": False,
            "hoan": [],
        },
    ]
    ra = tach_tai_khoan(bills)
    assert [(r["ten"], r["thuc_thu"]) for r in ra] == [
        ("VCB · 01", 180_000),
        (CHUA_PHAN_LOAI, 90_000),
    ]
