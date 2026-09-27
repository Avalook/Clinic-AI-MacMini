"""Ngày tuần từ người dùng: rác không được ném (lich_phong_service.doc_tuan)."""

from datetime import date

import pytest

from clinicai.services.lich_phong_service import doc_tuan


def test_ngay_giua_tuan_ve_thu_hai() -> None:
    assert doc_tuan("2026-09-24") == date(2026, 9, 21)


@pytest.mark.parametrize("rac", [None, "", "abc", "2026-13-40", 123, "2026-09"])
def test_rac_ve_tuan_nay_khong_nem(rac: object) -> None:
    d = doc_tuan(rac)
    assert d.weekday() == 0
