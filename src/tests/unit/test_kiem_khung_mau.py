"""Kiểm khung mẫu kết quả trước khi xuất bản (27/09/2026 — màn sửa mẫu)."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from clinicai.core.exceptions import ValidationError
from clinicai.phieu_kham.kiem_khung_mau import kiem_khung_mau
from clinicai.services.mau_ket_qua_service import _ma_tu_ten

MAU: list[dict[str, Any]] = [
    {
        "ma": "mo_ta",
        "ten": "Mô tả",
        "cot": [{"ma": "thai_a", "ten": "Thai A"}, {"ma": "thai_b", "ten": "Thai B"}],
        "block": [
            {
                "ma": "tim_thai",
                "ten": "Tim thai",
                "kieu": "text",
                "mac_dinh": {"thai_a": "dương tính", "thai_b": ""},
            },
            {"ma": "crl", "ten": "CRL", "kieu": "so", "goi_y": "mm"},
        ],
    },
    {
        "ma": "hpv",
        "ten": "HPV",
        "block": [
            {
                "ma": "hpv_16",
                "ten": "HPV 16",
                "kieu": "chon",
                "chon": ["Âm tính", "Dương tính"],
                "mac_dinh": "Âm tính",
            }
        ],
    },
    {
        "ma": "ket_luan",
        "ten": "Kết luận",
        "block": [{"ma": "ket_luan", "ten": "Kết luận", "kieu": "doan_van"}],
    },
]


def _sua(**thay: Any) -> list[dict[str, Any]]:
    k = copy.deepcopy(MAU)
    for duong, v in thay.items():
        muc, o, truong = duong.split("__")
        k[int(muc)]["block"][int(o)][truong] = v
    return k


def test_mau_hop_le_duoc_chuan_hoa() -> None:
    ra = kiem_khung_mau(MAU)
    # Ô mặc định theo cột: cột rỗng bị bỏ, cột có chữ giữ.
    assert ra[0]["block"][0]["mac_dinh"] == {"thai_a": "dương tính"}
    assert ra[1]["block"][0]["chon"] == ["Âm tính", "Dương tính"]


@pytest.mark.parametrize(
    ("khung", "cau"),
    [
        (_sua(**{"0__0__kieu": "bang_tinh"}), "kiểu ô"),
        (_sua(**{"1__0__chon": []}), "phải có lựa chọn"),
        (_sua(**{"1__0__mac_dinh": "Không rõ"}), "một trong các lựa chọn"),
        (_sua(**{"0__1__ma": "tim_thai"}), "trùng mã"),
        (_sua(**{"0__1__ma": "CRL mm"}), "mã ô không hợp lệ"),
        (_sua(**{"0__0__ten": "  "}), "chưa có tên"),
        (_sua(**{"0__1__chon": ["a"]}), "chỉ ô kiểu chọn"),
        (_sua(**{"2__0__mac_dinh": {"thai_a": "x"}}), "mục dạng bảng"),
        (_sua(**{"0__0__la": 1}), "trường lạ"),
        (_sua(**{"0__0__hien_thi": "o_tick"}), "chỉ ô kiểu chọn mới có cách hiển thị"),
        (_sua(**{"1__0__hien_thi": "nut_to"}), "cách hiển thị"),
    ],
)
def test_khung_sai_bi_chan_voi_cau_ro_rang(khung: Any, cau: str) -> None:
    with pytest.raises(ValidationError, match=cau):
        kiem_khung_mau(khung)


def test_o_chon_hien_dang_o_tick_duoc_giu() -> None:
    """ "Kết luận nhanh" DXA (29/09/2026): ô chọn một vẽ thành ô tích nhanh —
    khoá `hien_thi` phải đi qua kiểm khung, không thì xuất bản lại mẫu là mất."""
    ra = kiem_khung_mau(_sua(**{"1__0__hien_thi": "o_tick"}))
    assert ra[1]["block"][0]["hien_thi"] == "o_tick"
    # Không khai thì không tự thêm: ô chọn cũ vẫn là hộp thả xuống.
    assert "hien_thi" not in kiem_khung_mau(MAU)[1]["block"][0]


def test_o_tuy_chon_va_don_vi_duoc_giu_va_chuan_hoa() -> None:
    """09/10/2026: `tuy_chon` (không nhắc còn trống) + `don_vi` (in sau giá trị)."""
    k = _sua(**{"0__1__don_vi": "  mm ", "2__0__tuy_chon": True})
    ra = kiem_khung_mau(k)
    assert ra[0]["block"][1]["don_vi"] == "mm"
    assert ra[2]["block"][0]["tuy_chon"] is True
    # false / rỗng = như không khai: không mang khoá thừa vào khung.
    ra = kiem_khung_mau(_sua(**{"0__1__don_vi": " ", "2__0__tuy_chon": False}))
    assert "don_vi" not in ra[0]["block"][1]
    assert "tuy_chon" not in ra[2]["block"][0]
    # Ô chữ ngắn có đơn vị được (mẫu siêu âm gõ "12 x 8").
    assert kiem_khung_mau(_sua(**{"0__0__don_vi": "mm"}))[0]["block"][0]["don_vi"]


@pytest.mark.parametrize(
    ("thay", "cau"),
    [
        ({"2__0__tuy_chon": "có"}, "tuỳ chọn"),
        ({"2__0__tuy_chon": 1}, "tuỳ chọn"),
        ({"0__1__don_vi": 5}, "phải là chữ"),
        ({"0__1__don_vi": ["mm"]}, "phải là chữ"),
        ({"0__1__don_vi": "m" * 21}, "dài quá 20"),
        ({"2__0__don_vi": "mm"}, "chỉ ô chữ ngắn hoặc ô số"),
        ({"1__0__don_vi": "mm"}, "chỉ ô chữ ngắn hoặc ô số"),
    ],
)
def test_tuy_chon_don_vi_rac_bi_chan_gon(thay: dict[str, Any], cau: str) -> None:
    """Đầu vào rác → ValidationError (400 có câu), không bao giờ 500."""
    with pytest.raises(ValidationError, match=cau):
        kiem_khung_mau(_sua(**thay))


def test_trung_ma_o_giua_hai_muc_cung_bi_chan() -> None:
    """Dữ liệu điền khoá theo `ma` ô trên CẢ phiếu — trùng ở hai mục vẫn ghi đè."""
    k = copy.deepcopy(MAU)
    k[2]["block"][0]["ma"] = "hpv_16"
    with pytest.raises(ValidationError, match="ghi đè"):
        kiem_khung_mau(k)


def test_bang_qua_tam_cot_bi_chan() -> None:
    k = copy.deepcopy(MAU)
    k[0]["cot"] = [{"ma": f"c{i}", "ten": f"C{i}"} for i in range(9)]
    with pytest.raises(ValidationError, match="1–8 cột"):
        kiem_khung_mau(k)


def test_mau_khong_co_ket_luan_van_duoc_theo_nguon_chuan() -> None:
    """5 mẫu theo PDF không có mục Kết luận — không chặn."""
    assert kiem_khung_mau(MAU[:2])


def test_khung_rong_bi_chan() -> None:
    with pytest.raises(ValidationError):
        kiem_khung_mau([])


def test_ma_mau_sinh_tu_ten() -> None:
    assert _ma_tu_ten("Siêu âm tuyến vú (2 bên)") == "SIEU_AM_TUYEN_VU_2_BEN"
    assert _ma_tu_ten("Đo độ đặc xương") == "DO_DO_DAC_XUONG"
    assert _ma_tu_ten("!!!") == "MAU_MOI"
