"""Mã vị trí cơ sở thứ hai → mã mẫu Kim Ngưu (08/10/2026, Hào Nam)."""

from __future__ import annotations

import pytest

from clinicai.api.identity import ClinicRole, vai_tu_vi_tri
from clinicai.core.ma_vi_tri import ma_mau
from clinicai.services.config_service import la_ca_kham_bac_si


@pytest.mark.parametrize(
    ("ma", "mau"),
    [
        ("T1_LETAN", "T1_LETAN"),
        ("HN__T1_LETAN", "T1_LETAN"),
        ("HN__T1_THUNGAN__2", "T1_THUNGAN"),
        ("DIEU_PHOI", "DIEU_PHOI"),
        ("VT-1a2b3c4d", "VT-1a2b3c4d"),
        ("", ""),
    ],
)
def test_ma_mau(ma: str, mau: str) -> None:
    assert ma_mau(ma) == mau


def test_vi_tri_hao_nam_cap_vai_nhu_kim_nguu() -> None:
    assert vai_tu_vi_tri(["HN__T1_LETAN"], ClinicRole.CSKH) == vai_tu_vi_tri(
        ["T1_LETAN"], ClinicRole.CSKH
    )
    assert vai_tu_vi_tri(["HN__T1_LETAN"], ClinicRole.CSKH)


def test_ca_kham_bac_si_hao_nam() -> None:
    assert la_ca_kham_bac_si("HN__T1_SA_BS")
    assert la_ca_kham_bac_si("T4_SAN_BS")
    assert not la_ca_kham_bac_si("HN__T1_LETAN")


# ── Công tắc chọn cơ sở (08/10/2026) — đầu vào rác trả giá trị an toàn ──────
@pytest.mark.parametrize(
    ("settings", "ket_qua"),
    [
        (None, (True, None)),
        ({}, (True, None)),
        ({"hoi_chon_co_so": False}, (False, None)),
        (
            {
                "hoi_chon_co_so": False,
                "co_so_mac_dinh": "b0000000-0000-4000-8000-0000000000aa",
            },
            (False, "b0000000-0000-4000-8000-0000000000aa"),
        ),
        ({"co_so_mac_dinh": "rac"}, (True, None)),
        ('{"hoi_chon_co_so": false}', (False, None)),
        ("{hỏng", (True, None)),
        ([1, 2], (True, None)),
    ],
)
def test_doc_chon_co_so(settings: object, ket_qua: tuple[bool, str | None]) -> None:
    from clinicai.core.chon_co_so import doc_chon_co_so

    assert doc_chon_co_so(settings) == ket_qua
