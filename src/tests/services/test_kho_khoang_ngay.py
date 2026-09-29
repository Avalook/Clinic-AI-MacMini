"""Khoảng ngày xuất–nhập–tồn: đầu vào rác → hôm nay, không ném (CLAUDE.md)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from clinicai.services.kho_thuoc_service import XNT_TOI_DA_NGAY, khoang_xnt

HOM_NAY = date(2026, 9, 29)


@pytest.mark.parametrize(
    "rac", [None, "", "abc", "2026-13-01", "20260929", 12, [], {}, "1999-01-01", " "]
)
def test_rac_thanh_hom_nay(rac: Any) -> None:
    assert khoang_xnt(rac, rac, HOM_NAY) == (HOM_NAY, HOM_NAY)


def test_dao_nguoc_thi_doi_cho() -> None:
    assert khoang_xnt("2026-09-20", "2026-09-01", HOM_NAY) == (
        date(2026, 9, 1),
        date(2026, 9, 20),
    )


def test_khoang_qua_dai_bi_cat() -> None:
    a, b = khoang_xnt("2020-01-01", "2026-09-29", HOM_NAY)
    assert b == HOM_NAY and (b - a).days == XNT_TOI_DA_NGAY - 1
