"""Luật thuần thêm / bớt người ở một phòng (nhan_su_phong_service, 27/09/2026)."""

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.nhan_su_phong_service import khoi_phong, phong_sau_khi_doi


def test_khoi_theo_phong_la_thuc_hien() -> None:
    assert khoi_phong() == "thuc_hien"


def test_them_phong_moi_cho_nguoi_theo_phong() -> None:
    assert phong_sau_khi_doi(
        moi_phong=False, dang_co={"a"}, room_id="b", them=True
    ) == (
        "doi",
        ["a", "b"],
    )


def test_them_phong_da_co_la_giu() -> None:
    assert (
        phong_sau_khi_doi(moi_phong=False, dang_co={"a"}, room_id="a", them=True)[0]
        == "giu"
    )


def test_nguoi_moi_phong_them_la_thua_khong_thu_hep() -> None:
    # Gửi phong_ids=[b] cho người đang làm MỌI phòng sẽ THU HẸP quyền — cấm.
    assert phong_sau_khi_doi(moi_phong=True, dang_co=set(), room_id="b", them=True) == (
        "giu",
        [],
    )


def test_nguoi_moi_phong_bot_bi_chan() -> None:
    with pytest.raises(ValidationError):
        phong_sau_khi_doi(moi_phong=True, dang_co=set(), room_id="b", them=False)


def test_bot_phong_cuoi_la_tat_lego_khong_gui_rong() -> None:
    # Rỗng ở doi_lego = MỌI phòng; bớt phòng cuối phải là TẮT.
    assert phong_sau_khi_doi(
        moi_phong=False, dang_co={"a"}, room_id="a", them=False
    ) == (
        "tat",
        [],
    )
