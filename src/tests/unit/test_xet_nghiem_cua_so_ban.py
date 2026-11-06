"""Bàn XN chọn ngày: `tu_ngay` chỉ mở rộng cửa sổ về quá khứ, rác ⇒ mặc định."""

from __future__ import annotations

from datetime import date

import pytest

from clinicai.services.xet_nghiem.ket_qua import cua_so_ban

HOM_NAY = date(2026, 11, 6)
MAC_DINH = date(2026, 10, 7)


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        (None, MAC_DINH),
        ("", MAC_DINH),
        ("rác", MAC_DINH),
        ("2026-13-45", MAC_DINH),
        (12345, MAC_DINH),
        # Ngày trong 30 ngày qua / hôm nay / tương lai: không thu hẹp cửa sổ.
        ("2026-11-06", MAC_DINH),
        ("2026-11-01", MAC_DINH),
        ("2027-01-01", MAC_DINH),
        # Ngày cũ hơn: mở rộng tới đúng ngày đó.
        ("2026-06-15", date(2026, 6, 15)),
        ("2026-10-06", date(2026, 10, 6)),
    ],
)
def test_cua_so_ban(vao: object, ra: date) -> None:
    assert cua_so_ban(vao, HOM_NAY) == ra
