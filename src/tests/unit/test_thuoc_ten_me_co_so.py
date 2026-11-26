"""Tên đơn vị cũ kèm số: "hộp 60 viên" = mẹ "hộp" + 60 con "viên" (Tuyền 26/11)."""

from __future__ import annotations

from clinicai.services.thuoc.me_con import la_doi_ten_cung_nghia, tach_ten_me_co_so


def test_tach_ten() -> None:
    assert tach_ten_me_co_so("hộp 60 viên") == ("hộp", 60, "viên")
    assert tach_ten_me_co_so(" hộp  25 que ") == ("hộp", 25, "que")
    assert tach_ten_me_co_so("hộp") is None
    assert tach_ten_me_co_so("hộp 0 viên") is None


def test_doi_ten_cung_nghia() -> None:
    assert la_doi_ten_cung_nghia("hộp 15 viên", "Hộp")
    assert not la_doi_ten_cung_nghia("hộp 15 viên", "viên")
    assert not la_doi_ten_cung_nghia("hộp", "hộp")
