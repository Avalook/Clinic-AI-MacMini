"""Phần THUẦN của sổ sửa chỉ định (Khối 2, 06/10/2026) — không cần DB."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from clinicai.services.so_sua_chi_dinh_service import cau_so, dong_so, so_sanh_don


def _d(id_: str | None, ten: str, **k: Any) -> dict[str, Any]:
    return {"id": id_, "drug_name_raw": ten, **k}


def test_so_sanh_don_them_bo_doi() -> None:
    truoc = [
        _d("1", "Paracetamol", quantity="1 hộp", dosage_instructions="Sáng 1"),
        _d("2", "Vitamin C", quantity="2 hộp"),
    ]
    sau = [
        _d("1", "Paracetamol", quantity="1 hộp", dosage_instructions="Sáng 2"),
        _d("3", "Kẽm", quantity="1 hộp"),
    ]
    kq = {(t.hanh_dong, t.ten) for t in so_sanh_don(truoc, sau)}
    assert kq == {("DOI", "Paracetamol"), ("BO", "Vitamin C"), ("THEM", "Kẽm")}
    [doi] = [t for t in so_sanh_don(truoc, sau) if t.hanh_dong == "DOI"]
    assert (doi.truoc, doi.sau) == ({"cach_dung": "Sáng 1"}, {"cach_dung": "Sáng 2"})


def test_dinh_chinh_thay_dong_moi_cung_thuoc_la_doi_khong_phai_bo_them() -> None:
    truoc = [_d("1", "Paracetamol", drug_catalog_id="k1", quantity="1 hộp")]
    sau = [_d("9", "Paracetamol", drug_catalog_id="k1", quantity="2 hộp")]
    [t] = so_sanh_don(truoc, sau)
    assert (t.hanh_dong, t.dong_id, t.sau) == ("DOI", "9", {"so_luong": "2 hộp"})


def test_luu_y_nguyen_va_so_le_khong_doi() -> None:
    a = [_d("1", "A", quantity=2.0)]
    b = [_d("1", " A ", quantity="2")]
    assert so_sanh_don(a, b) == []


def test_dau_vao_rac_khong_nem() -> None:
    rac: list[Any] = [None, 1, "x", {"id": None}, {"drug_name_raw": ""}, []]
    assert so_sanh_don(rac, rac) == []
    assert so_sanh_don(rac, []) == []
    assert so_sanh_don([], rac) == []
    # Dòng không tên bị bỏ, dòng có tên vẫn ghi.
    kq = so_sanh_don([], [*rac, _d(None, "Kẽm")])
    assert [(t.hanh_dong, t.ten) for t in kq] == [("THEM", "Kẽm")]


def test_cau_so() -> None:
    assert (
        cau_so(
            {
                "hanh_dong": "BO",
                "nhom": "CLS",
                "ten_muc": "Siêu âm",
                "da_thu": 300000,
                "tien_thua": 300000,
            }
        )
        == "Bỏ cận lâm sàng “Siêu âm” · đã thu 300.000đ → tiền thừa 300.000đ"
    )
    assert cau_so(
        {
            "hanh_dong": "DOI",
            "nhom": "THUOC",
            "ten_muc": "Para",
            "chi_tiet": {"truoc": {"so_luong": "1"}, "sau": {"so_luong": "2"}},
        }
    ).endswith("Số lượng: 1 → 2")
    # Rác: không ném.
    assert cau_so({})
    assert cau_so({"hanh_dong": "XYZ", "nhom": None, "da_thu": None, "chi_tiet": None})


def test_dong_so_co_hoan_tac() -> None:
    goc = {
        "id": "a",
        "hanh_dong": "BO",
        "nhom": "CLS",
        "ten_muc": "X",
        "chi_tiet": "khong-phai-json",
        "luc": datetime.now(UTC),
        "con_bo": True,
        "hoan_tac_luc": None,
        "boi_vai": "TRUONG_CA",
    }
    d = dong_so(goc)
    assert d["hoan_tac_duoc"] is True and d["luc"] and d["boi_vai"]
    assert dong_so(goc, chi_xem=True)["hoan_tac_duoc"] is False
    assert dong_so({**goc, "nhom": "THUOC"})["hoan_tac_duoc"] is False
    assert dong_so({**goc, "con_bo": False})["hoan_tac_duoc"] is False
    assert dong_so({**goc, "hanh_dong": "THEM"})["hoan_tac_duoc"] is False


def test_cau_xoa_ai_vai_lam_thay_va_rac() -> None:
    from clinicai.services.so_sua_chi_dinh_service import cau_xoa

    assert cau_xoa(
        {
            "boi_ten": "Nguyễn A",
            "boi_vai": "MANAGEMENT",
            "boi_staff_id": "1",
            "bac_si_chinh_id": "2",
            "bac_si_chinh_ten": "Hùng",
        }
    ).endswith("Nguyễn A (thay BS Hùng) đã xoá chỉ định này")
    # Chính bác sĩ chính xoá: không ghi "thay".
    assert "thay" not in cau_xoa(
        {
            "boi_ten": "Hùng",
            "boi_staff_id": "2",
            "bac_si_chinh_id": "2",
            "bac_si_chinh_ten": "Hùng",
        }
    )
    # Rác / thiếu dữ liệu: không ném.
    assert cau_xoa({}) == "Không rõ ai đã xoá chỉ định này"
    assert cau_xoa({"boi_vai": 123, "boi_ten": None}).endswith("đã xoá chỉ định này")
