"""Cửa làm thay bác sĩ: người đứng ô phụ tá của ô bác sĩ (Tuyền 04/11/2026)."""

from __future__ import annotations

from clinicai.api.identity import ClinicRole
from clinicai.permissions.ca_truc import CaLam, duoc_lam_thay


def _ca(
    ai: str,
    vi_tri: str,
    *,
    bac_si: bool = False,
    ho_tro: str | None = None,
    ca: str = "TOI",
    phong: str = "p",
) -> CaLam:
    return CaLam(
        staff_id=ai,
        room_id=phong,
        ca=ca,
        lan=None,
        bac_si=bac_si,
        vi_tri=vi_tri,
        ho_tro=ho_tro,
    )


LICH = [
    _ca("bs1", "BS1", bac_si=True),
    _ca("bs2", "BS2", bac_si=True),
    _ca("bs3", "BS3", bac_si=True),
    _ca("dd3", "DD3", ho_tro="BS3"),
    # Bác sĩ khác / trưởng ca đứng ô phụ tá cũng được làm phụ tá.
    _ca("bs_khac", "DD1", ho_tro="BS1"),
]


def test_phu_ta_lam_thay_bac_si_cua_o_minh_bat_ke_vai() -> None:
    assert duoc_lam_thay(
        nguoi_bam="dd3", bac_si_id="bs3", vai_goc=ClinicRole.NURSE_ULTRASOUND, lich=LICH
    )
    assert duoc_lam_thay(
        nguoi_bam="bs_khac",
        bac_si_id="bs1",
        vai_goc=ClinicRole.ULTRASOUND_DOCTOR,
        lich=LICH,
    )


def test_phu_ta_khac_ca_khong_ghep_theo_o() -> None:
    lich = [_ca("bs1", "BS1", bac_si=True, ca="SANG"), _ca("x", "DD1", ho_tro="BS1")]
    assert not duoc_lam_thay(
        nguoi_bam="x", bac_si_id="bs1", vai_goc=ClinicRole.TRUONG_CA, lich=lich
    )


def test_luat_cu_van_mo_trong_pr_nay() -> None:
    """Chưa chặn thêm ai: ĐD cùng phòng cùng ca phòng nhiều bác sĩ không làn
    vẫn làm thay được bác sĩ khác (luật cũ) — siết sau khi chạy bóng."""
    assert duoc_lam_thay(
        nguoi_bam="dd3", bac_si_id="bs2", vai_goc=ClinicRole.NURSE_ULTRASOUND, lich=LICH
    )
    # Vai không phải TKYK/ĐD, không đứng ô phụ tá của BS2 → không.
    assert not duoc_lam_thay(
        nguoi_bam="bs_khac", bac_si_id="bs2", vai_goc=ClinicRole.TRUONG_CA, lich=LICH
    )
