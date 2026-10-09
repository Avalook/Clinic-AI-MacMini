"""Hoàn tác check-in: luật "đã làm rồi thì không hoàn tác" (Tuyền 09/10/2026)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.hoan_tac_check_in import (
    CUOI_CAU,
    VIEC_DA_LAM,
    ly_do_khong_hoan_tac,
)
from clinicai.services.tiep_don_service import dung_dong


def test_chua_lam_gi_thi_hoan_tac_duoc() -> None:
    assert ly_do_khong_hoan_tac(None) is None
    assert ly_do_khong_hoan_tac({}) is None
    assert ly_do_khong_hoan_tac({co: False for co, _ in VIEC_DA_LAM}) is None


@pytest.mark.parametrize(("co", "nhan"), VIEC_DA_LAM)
def test_moi_viec_da_lam_deu_chan_kem_cau_ro(co: str, nhan: str) -> None:
    cau = ly_do_khong_hoan_tac({co: True})
    assert cau == f"Khách đã {nhan} — {CUOI_CAU}"
    assert "Nhờ trưởng ca điều phối" in cau


def test_nhieu_viec_ke_het() -> None:
    cau = ly_do_khong_hoan_tac({"da_do_sinh_hieu": True, "nop_tien": True})
    assert cau is not None
    assert cau.startswith("Khách đã được đo sinh hiệu, nộp tiền — ")


def test_co_rac_coi_nhu_chua_lam() -> None:
    # Chỉ True thật mới tính — None/"t"/1 từ dữ liệu lạ không được chặn nhầm.
    assert ly_do_khong_hoan_tac({"nop_tien": None, "vao_phong": "t", "x": True}) is None


def _luc(h: int, m: int = 0) -> datetime:
    return datetime(2026, 10, 9, h, m, tzinfo=CLINIC_TZ)


def _dong(viec: dict[str, Any] | None, **kw: Any) -> dict[str, Any]:
    r: dict[str, Any] = {
        "appointment_id": "a",
        "status": "CHECKED_IN",
        "visit_id": "v",
        "checked_in_at": _luc(8, 31),
        "booking_channel": "HOTLINE",
        "slot_start": _luc(8, 30),
        "slot_minutes": 15,
    }
    r.update(kw)
    return dung_dong(r, [], _luc(8, 40), viec)


def test_dong_tiep_don_co_co_hoan_tac() -> None:
    d = _dong({"da_do_sinh_hieu": False})
    assert d["hoan_tac_duoc"] is True and d["ly_do_khong_hoan_tac"] is None

    d = _dong({"da_do_sinh_hieu": True})
    assert d["hoan_tac_duoc"] is False
    assert "đo sinh hiệu" in d["ly_do_khong_hoan_tac"]

    # Chưa check-in / đã về: không có nút, không có câu.
    d = _dong(None, status="CONFIRMED", visit_id=None, checked_in_at=None)
    assert d["hoan_tac_duoc"] is False and d["ly_do_khong_hoan_tac"] is None
    d = _dong({"nop_tien": True}, ve_luc=_luc(9))
    assert d["hoan_tac_duoc"] is False and d["ly_do_khong_hoan_tac"] is None
