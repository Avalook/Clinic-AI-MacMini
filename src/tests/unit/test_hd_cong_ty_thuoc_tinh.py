"""Thuộc tính (property-based, sinh ca ngẫu nhiên có seed) — cột công ty trong file
Excel hoá đơn, theo luật Tuyền 16/10/2026. Không thêm thư viện: `random.Random(seed)`.

Mỗi hoá đơn là một phiếu thu; "tick" = phiếu được ghi "xuất về công ty".
  L1  KHÔNG tick → C "Tên khách hàng" TRỐNG; D/G cá nhân; F = tên khách.
  L2  CÓ tick    → C = tên công ty, D = địa chỉ công ty, E = MST, F = tên KHÁCH THẬT,
                   G = email công ty (không bao giờ là email cá nhân).
  L3  Cờ tick KHÔNG đổi tiền: số hoá đơn, số dòng, tổng, thứ tự, các cột hàng hoá.
  L4  Thông tin người mua chỉ ở dòng đầu của hoá đơn; số thứ tự lặp mọi dòng.
  L5  Dấu vân tay "đã xuất MISA" của hoá đơn cá nhân KHÔNG đổi khi chỉ khác cờ in.
"""

from __future__ import annotations

import io
import random
import warnings
from typing import Any

from openpyxl import load_workbook

from clinicai.services.hoa_don_misa_doc import dau_van_tay
from clinicai.services.thue_gtgt import ap_thue_hoa_don
from clinicai.services.xuat_hoa_don_service import dung_hoa_don, xlsx_misa

SO_CA = 40
# Chữ khó: "=" đầu ô, dấu cách đầu/cuối, tiếng Việt, ký tự đặc biệt.
_CHU = ["A", "=1+1", "Nguyễn Thị Ánh", " cách ", "Cty & Con", "0123", "ñ", "x" * 60]


def _chu(rng: random.Random) -> str:
    return rng.choice(_CHU) + (str(rng.randrange(1000)) if rng.random() < 0.5 else "")


def _co(rng: random.Random, p: float = 0.7) -> str | None:
    return _chu(rng) if rng.random() < p else None


def _ca(rng: random.Random) -> dict[str, Any]:
    dong = [
        {
            "id": f"l{i}",
            "ten": _chu(rng),
            "so_luong": rng.randint(1, 5),
            "thanh_tien": rng.randint(1, 5000) * 1000,
        }
        for i in range(rng.randint(1, 4))
    ]
    khach = {
        "ten": _chu(rng),
        "ma_bn": "BN1",
        "so_dien_thoai": _co(rng),
        "phieu": [
            {
                "id": "p1",
                "ma": "PT-P1",
                "kind": "dich_vu",
                "thu_luc": "2026-10-16T09:00:00+07:00",
                "thu_trong_ky": True,
                "trang_thai": "DA_THU",
                "hinh_thuc": rng.choice(["CASH", "TRANSFER"]),
                "dong": dong,
                "hoan": [],
            }
        ],
    }
    cong_ty = {
        "ten_cong_ty": _chu(rng),
        "dia_chi_cong_ty": _co(rng),
        "ma_so_thue": _co(rng),
        "email_nhan_hd": _co(rng),
        # Ô của G5c; luật mới KHÔNG dùng nó cho cột F.
        "nguoi_mua": _co(rng),
    }
    return {
        "khach": khach,
        "ca_nhan": {"dia_chi": _co(rng), "cccd": _co(rng), "email": _co(rng)},
        "cong_ty": cong_ty,
    }


def _chay(ca: dict[str, Any], tick: bool) -> tuple[dict[str, Any], list[list[str]]]:
    them_ct = {"p1": ca["cong_ty"]} if tick else {}
    goc = dung_hoa_don([ca["khach"]], {}, {"p1": ca["ca_nhan"]}, None, None, them_ct)
    hoa_don = [hd for h in goc for hd in ap_thue_hoa_don(h)]
    for i, hd in enumerate(hoa_don, 1):
        hd["stt"] = i
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ws = load_workbook(io.BytesIO(xlsx_misa(hoa_don))).active
    assert ws is not None
    hang = [
        [str(c.value) if c.value is not None else "" for c in row]
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row)
        if any(c.value is not None for c in row)
    ]
    return goc[0], hang


def _cac_ca() -> list[dict[str, Any]]:
    rng = random.Random(1610)
    return [_ca(rng) for _ in range(SO_CA)]


def test_l1_khong_tick_ten_khach_hang_trong_thong_tin_ca_nhan() -> None:
    for ca in _cac_ca():
        _, hang = _chay(ca, tick=False)
        dau = hang[0]
        assert dau[2] == "", "C 'Tên khách hàng' phải trống khi không xuất về công ty"
        assert dau[4] == "", "không có MST"
        assert dau[5] == ca["khach"]["ten"].strip() or dau[5] == ca["khach"]["ten"]
        assert dau[3] == (ca["ca_nhan"]["dia_chi"] or "")
        assert dau[6] == (ca["ca_nhan"]["email"] or "")


def test_l2_tick_dien_dung_cot_sdt_khach_khong_lo_cccd() -> None:
    for ca in _cac_ca():
        ct = ca["cong_ty"]
        _, hang = _chay(ca, tick=True)
        dau = hang[0]
        assert dau[2] == ct["ten_cong_ty"]
        assert dau[3] == (ct["dia_chi_cong_ty"] or "")
        assert dau[4] == (ct["ma_so_thue"] or "")
        assert dau[5] == ca["khach"]["ten"]  # khách THẬT, không theo ô của công ty
        # Email công ty; công ty chưa có thì email cá nhân của khách (Tuyền 16/10).
        assert dau[6] == (ct["email_nhan_hd"] or ca["ca_nhan"]["email"] or "")
        # SĐT khách ghi ở cột H; CCCD cá nhân KHÔNG lọt vào hoá đơn công ty.
        assert dau[7] == (ca["khach"]["so_dien_thoai"] or "") and dau[8] == ""


def test_l3_tick_khong_doi_tien() -> None:
    for ca in _cac_ca():
        co, hang_co = _chay(ca, tick=True)
        khong, hang_khong = _chay(ca, tick=False)
        assert co["tong"] == khong["tong"]
        assert [d["thanh_tien"] for d in co["dong"]] == [
            d["thanh_tien"] for d in khong["dong"]
        ]
        assert len(hang_co) == len(hang_khong)
        assert [r[12:] for r in hang_co] == [r[12:] for r in hang_khong]


def test_l4_thong_tin_chi_o_dong_dau_stt_lap_moi_dong() -> None:
    for ca in _cac_ca():
        for tick in (False, True):
            _, hang = _chay(ca, tick)
            assert all(r[0] == "1" for r in hang)
            for r in hang[1:]:
                assert all(r[c] == "" for c in range(1, 12))


def test_l5_dau_van_tay_ca_nhan_khong_doi_theo_cach_in_cot_c() -> None:
    """Cách in cột C đổi (trống thay vì tên khách) KHÔNG làm mọi hoá đơn đã đánh dấu
    "đã xuất MISA" báo "có thay đổi sau khi xuất" — dấu vân tay dựa vào `ten_khach`."""
    for ca in _cac_ca():
        hd, _ = _chay(ca, tick=False)
        assert hd["ten_khach"] == ca["khach"]["ten"]
        assert dau_van_tay(hd) == dau_van_tay({**hd, "nguoi_mua": "khác"})
