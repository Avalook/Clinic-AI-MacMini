"""Gom dịch vụ đặt lịch theo nhóm (T0, 07/10/2026) — hàm thuần."""

from __future__ import annotations

from clinicai.services.dich_vu_dat_lich import gom_nhom, ten_sach


def _dong(id_: str, ten: str, nhom: str, form: str | None = None) -> dict[str, object]:
    return {"id": id_, "name": ten, "nhom": nhom, "form_code": form}


def test_gom_theo_thu_tu_nhom_an_thuoc_bo_free() -> None:
    nhom = gom_nhom(
        [
            _dong("k", "Khác", "KHAC"),
            _dong("t", "Thuốc A", "THUOC"),
            _dong("b", "Tập máy Bio", "DIEU_TRI"),
            _dong("p", "Phụ khoa", "KHAM", "PK"),
            _dong("f", "FREE", "KHAM"),
            _dong("s", "Sàn chậu", "KHAM", "SAN_CHAU"),
        ]
    )
    assert [n["ma"] for n in nhom] == ["KHAM", "DIEU_TRI", "KHAC"]
    kham = nhom[0]["dich_vu"]
    assert [d["id"] for d in kham] == ["p", "s"]
    # Lĩnh vực hồ sơ chỉ cho 5 loại lõi — Sàn chậu không có.
    assert [d["linh_vuc"] for d in kham] == ["PK", None]
    assert nhom[2]["goi_y_ghi_chu"]
    assert nhom[0]["goi_y_ghi_chu"] is None


def test_nhom_rong_khong_tra_va_khoa_phu_di_theo() -> None:
    nhom = gom_nhom(
        [
            {
                "id": "x",
                "ten": "Nam khoa",
                "nhom": "KHAM",
                "form_code": "NK",
                "hien_tai": True,
                "chan": False,
                "ghi_chu": None,
            }
        ]
    )
    assert len(nhom) == 1
    muc = nhom[0]["dich_vu"][0]
    assert muc["hien_tai"] is True and muc["linh_vuc"] == "NK"
    assert "ghi_chu" in muc


def test_nhom_la_hoac_trong_coi_nhu_kham_hoac_bo() -> None:
    nhom = gom_nhom(
        [_dong("a", "Phụ khoa", None), _dong("z", "Lạ", "LA")]  # type: ignore[arg-type]
    )
    assert [n["ma"] for n in nhom] == ["KHAM"]
    assert [d["id"] for d in nhom[0]["dich_vu"]] == ["a"]


def test_ten_sach() -> None:
    assert ten_sach("** Phụ khoa ") == "Phụ khoa"
    assert ten_sach(None) == ""
