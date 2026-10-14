"""Tách thuế GTGT ngược (K1) — bảng số tính tay, không đọc code để lấy đáp án."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.services.thue_gtgt import (
    CHE_DO_MOT,
    CHE_DO_TACH,
    GHI_CHU_NHIEU_THUE,
    ap_thue_hoa_don,
    chon_thue_suat,
    chuan_hoa_thue_suat,
    dem_dong_chua_thue,
    ma_cot_k,
    nhom_theo_thue_suat,
    tach_thue,
    tach_thue_cac_dong,
)


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ("8", "8"),
        (8, "8"),
        (" 8% ", "8"),
        ("8,5", "8.5"),
        ("10.0", "10"),
        ("0", "0"),
        ("kct", "KCT"),
        (" KKKNT ", "KKKNT"),
        # rác → rỗng, không ném
        ("", None),
        (None, None),
        ("abc", None),
        ("-5", None),
        ("101", None),
        ("nan", None),
        ("inf", None),
        (True, None),
        ("8%%", None),
    ],
)
def test_chuan_hoa_thue_suat(vao: object, ra: str | None) -> None:
    assert chuan_hoa_thue_suat(vao) == ra


def test_tach_mot_dong_bang_so_tay() -> None:
    # 1.000.000 × 1,08 = 1.080.000 → hàng 1.000.000 + thuế 80.000
    assert tach_thue(1_080_000, "8") == (1_000_000, 80_000)
    assert tach_thue(1_100_000, "10") == (1_000_000, 100_000)
    assert tach_thue(1_050_000, "5") == (1_000_000, 50_000)
    # 0%, KCT, KKKNT, chưa đặt: không tách
    assert tach_thue(1_000_000, "0") == (1_000_000, 0)
    assert tach_thue(1_000_000, "KCT") == (1_000_000, 0)
    assert tach_thue(1_000_000, "KKKNT") == (1_000_000, 0)
    assert tach_thue(1_000_000, None) == (1_000_000, 0)
    # tiền 0 / âm không sinh thuế
    assert tach_thue(0, "8") == (0, 0)
    # làm tròn nửa lên: 100 × 8/108 = 7,407 → 7
    assert tach_thue(100, "8") == (93, 7)
    # 5% tự nhập có phần lẻ: 105.000 × 8,5/108,5 = 8.226,27 → 8.226
    assert tach_thue(105_000, "8.5") == (96_774, 8_226)


@pytest.mark.parametrize("ma", ["5", "8", "8.5", "10", "KCT", None])
@pytest.mark.parametrize("tien", [1, 7, 99, 100, 12_345, 1_080_000, 9_999_999])
def test_tach_luon_khop_tong(tien: int, ma: str | None) -> None:
    hang, thue = tach_thue(tien, ma)
    assert hang + thue == tien
    assert hang >= 0
    assert thue >= 0


def test_ba_dong_lam_tron_don_dong_cuoi() -> None:
    # 3 dòng 100đ, thuế 8%: mỗi dòng 100/1,08 = 92,59 → 93 (nửa lên) → Σ 279.
    # Tổng 300 → thuế 300×8/108 = 22,22 → 22; hàng 278 → dòng cuối bù -1 = 92.
    hang, thue = tach_thue_cac_dong([100, 100, 100], "8")
    assert thue == 22
    assert hang == [93, 93, 92]
    assert sum(hang) + thue == 300


def test_nhieu_dong_tong_dung_so_khach_tra() -> None:
    gom = [333_333, 777, 1_080_000, 5]
    hang, thue = tach_thue_cac_dong(gom, "8")
    assert sum(hang) + thue == sum(gom)
    assert all(h >= 0 for h in hang)


def test_khong_thue_giu_nguyen_dong() -> None:
    assert tach_thue_cac_dong([100, 250], None) == ([100, 250], 0)
    assert tach_thue_cac_dong([100, 250], "KCT") == ([100, 250], 0)
    assert tach_thue_cac_dong([], "8") == ([], 0)


def test_uu_tien_dong_mat_hang_nhom() -> None:
    assert chon_thue_suat(dong="5", mat_hang="8", nhom="10") == "5"
    assert chon_thue_suat(dong=None, mat_hang="8", nhom="10") == "8"
    assert chon_thue_suat(dong="", mat_hang=None, nhom="10") == "10"
    assert chon_thue_suat() is None
    # ô gõ hỏng ở tầng trên không che thuế suất đúng ở tầng dưới
    assert chon_thue_suat(dong="xyz", mat_hang="8", nhom="10") == "8"
    # 0 là một thuế suất thật, thắng nhóm 10
    assert chon_thue_suat(dong="0", nhom="10") == "0"


def test_gom_theo_thue_suat_va_dem_dong_chua_dat() -> None:
    dong: list[dict[str, Any]] = [
        {"id": "a", "thue_suat": "8"},
        {"id": "b", "thue_suat": None},
        {"id": "c", "thue_suat": "8%"},
        {"id": "d", "thue_suat": "rác"},
        {"id": "e"},
    ]
    nhom = nhom_theo_thue_suat(dong)
    assert [d["id"] for d in nhom["8"]] == ["a", "c"]
    assert [d["id"] for d in nhom[None]] == ["b", "d", "e"]
    assert dem_dong_chua_thue(dong) == 3


# ── Áp thuế lên hoá đơn ──────────────────────────────────────────────────────
def _hd(*dong: tuple[str, int, str | None], giam: int = 0) -> dict[str, object]:
    return {
        "stt": 1,
        "ma_phieu": "PT-1",
        "ghi_chu": [],
        "tong": sum(t for _, t, _ in dong),
        "dong": [
            {
                "id": f"l{i}",
                "ten": ten,
                "dvt": "Lần",
                "so_luong": 1,
                "don_gia": tien,
                "thanh_tien": tien,
                "giam_gia": giam if i == 0 else 0,
                "truoc_giam": tien + (giam if i == 0 else 0),
                "thue_suat": thue,
            }
            for i, (ten, tien, thue) in enumerate(dong)
        ],
    }


def test_chua_dat_thue_xuat_y_nhu_cu() -> None:
    hd = _hd(("A", 1_080_000, None), ("B", 50_000, "rác"))
    (r,) = ap_thue_hoa_don(hd)
    assert r["thue_suat_ma"] == "" and r["tien_thue"] is None
    assert [d["thanh_tien"] for d in r["dong"]] == [1_080_000, 50_000]
    assert r["tong"] == 1_130_000


def test_mot_thue_suat_bang_so_tay() -> None:
    hd = _hd(("A", 108_000, "8"), ("B", 540_000, "8"))
    for che_do in (CHE_DO_TACH, CHE_DO_MOT):
        (r,) = ap_thue_hoa_don(hd, che_do=che_do)
        # 648.000 × 8/108 = 48.000 thuế; hàng 100.000 + 500.000.
        assert [d["thanh_tien"] for d in r["dong"]] == [100_000, 500_000]
        assert (r["thue_suat_ma"], r["tien_thue"], r["tien_hang"]) == (
            "8",
            48_000,
            600_000,
        )
        assert r["tong"] == 648_000


def test_tach_theo_thue_suat_ba_hoa_don() -> None:
    hd = _hd(("A", 1_080_000, "8"), ("B", 105_000, "5"), ("C", 50_000, None))
    ra = ap_thue_hoa_don(hd, che_do=CHE_DO_TACH)
    assert [(r["thue_suat_ma"], r["tien_hang"], r["tien_thue"]) for r in ra] == [
        ("8", 1_000_000, 80_000),
        ("5", 100_000, 5_000),
        ("", None, None),
    ]
    assert sum(r["tong"] for r in ra) == 1_235_000
    assert any("1 dòng chưa có thuế suất" in g for g in ra[2]["ghi_chu"])
    assert any("Tách theo thuế suất 8%" in g for g in ra[0]["ghi_chu"])


def test_mot_hoa_don_nhieu_thue_suat_khung() -> None:
    hd = _hd(("A", 1_080_000, "8"), ("B", 105_000, "5"), ("C", 50_000, None))
    (r,) = ap_thue_hoa_don(hd, che_do=CHE_DO_MOT)
    assert r["thue_suat_ma"] == ""  # nhiều thuế suất: K trống
    assert [d["thanh_tien"] for d in r["dong"]] == [1_000_000, 100_000, 50_000]
    assert r["tien_thue"] == 85_000 and r["tien_hang"] == 1_150_000
    assert r["tien_hang"] + r["tien_thue"] == r["tong"] == 1_235_000
    assert GHI_CHU_NHIEU_THUE in r["ghi_chu"]
    assert "1 dòng chưa có thuế suất" in r["ghi_chu"]


def test_ghi_giam_gia_k2_dong_goc_va_chiet_khau() -> None:
    # Dòng 270.000 sau giảm = 300.000 gốc − 30.000 giảm; thuế 8%.
    hd = _hd(("Siêu âm", 270_000, "8"), giam=30_000)
    (r,) = ap_thue_hoa_don(hd, ghi_giam_gia=True)
    goc, ck = r["dong"]
    assert goc["ten"] == "Siêu âm" and ck["ten"] == "Chiết khấu — Siêu âm"
    assert (ck["so_luong"], ck["dvt"]) == (1, "")
    # 270.000 × 8/108 = 20.000 thuế; hàng 250.000 = 277.778 − 27.778.
    assert (goc["thanh_tien"], ck["thanh_tien"]) == (277_778, -27_778)
    assert r["tien_thue"] == 20_000 and r["tien_hang"] == 250_000
    assert r["tong"] == 270_000
    # Không thuế: vẫn hai dòng, tổng = số khách trả.
    (k,) = ap_thue_hoa_don(
        _hd(("Siêu âm", 270_000, None), giam=30_000), ghi_giam_gia=True
    )
    assert [d["thanh_tien"] for d in k["dong"]] == [300_000, -30_000]
    assert k["tong"] == 270_000
    # Tắt công tắc: một dòng sau giảm như cũ.
    (t,) = ap_thue_hoa_don(_hd(("Siêu âm", 270_000, None), giam=30_000))
    assert [d["thanh_tien"] for d in t["dong"]] == [270_000]


def test_ma_cot_k_misa() -> None:
    assert [ma_cot_k(m) for m in ("0", "5", "8", "10", "KCT", "KKKNT")] == [
        "0",
        "5",
        "8",
        "10",
        "KCT",
        "KKKNT",
    ]
    assert ma_cot_k("8.5") == "KHAC" and ma_cot_k(None) == ""
    (r,) = ap_thue_hoa_don(_hd(("A", 108_500, "8.5")))
    assert r["thue_suat_ma"] == "KHAC" and r["tien_thue"] == 8_500
    assert any("KHAC" in g for g in r["ghi_chu"])
