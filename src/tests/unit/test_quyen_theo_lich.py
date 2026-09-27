"""Luật thuần của quyền theo lịch (permissions/lich.py)."""

from clinicai.permissions.lich import co_ca_o_phong
from clinicai.services.day_noi import DAY


def test_co_ca_khi_mot_vi_tri_dang_dung_thuoc_phong() -> None:
    assert co_ca_o_phong(["T1_LETAN", "T1_SA_DD"], {"T1_SA_BS", "T1_SA_DD"})


def test_khong_ca_hoac_vi_tri_phong_khac() -> None:
    assert not co_ca_o_phong([], {"T1_SA_DD"})
    assert not co_ca_o_phong(["T1_LETAN"], {"T1_SA_DD"})
    assert not co_ca_o_phong(["T1_SA_DD"], [])


def test_day_quyen_theo_lich_mac_dinh_tat() -> None:
    assert DAY["quyen_theo_lich"].mac_dinh is False
    assert DAY["quyen_theo_lich"].kieu == "bat_tat"
