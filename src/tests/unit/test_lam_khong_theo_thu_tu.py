"""V4 (30/09/2026) — luật thuần của "làm không theo thứ tự": phiếu nào tính là
đã điền, khi nào màn phòng được hiện nút "Huỷ bắt đầu nhầm", và 409
PATIENT_BUSY mang `chi_tiet` (tên phòng đang giữ khách) tới tận thân trả về."""

from __future__ import annotations

import json

from clinicai.main import clinicai_exception_handler
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.service_execution_service import (
    huy_bat_dau_duoc,
    phieu_da_dien,
)


def test_phieu_da_dien() -> None:
    assert phieu_da_dien("DRAFT", 0) is False
    assert phieu_da_dien("DRAFT", None) is False
    assert phieu_da_dien("DRAFT", 1) is True
    assert phieu_da_dien("READY", 0) is True


def test_huy_bat_dau_duoc() -> None:
    assert huy_bat_dau_duoc("IN_PROGRESS", True, []) is True
    assert huy_bat_dau_duoc("IN_PROGRESS", True, [("DRAFT", 0)]) is True
    assert huy_bat_dau_duoc("IN_PROGRESS", True, [("DRAFT", 3)]) is False
    assert huy_bat_dau_duoc("IN_PROGRESS", False, []) is False
    assert huy_bat_dau_duoc("PENDING", True, []) is False
    assert huy_bat_dau_duoc(None, False, []) is False


async def test_409_patient_busy_mang_chi_tiet_toi_than_tra_ve() -> None:
    """Màn phòng hỏi "chuyển sang đây?" theo `chi_tiet` máy chủ trả."""
    r = await clinicai_exception_handler(
        None,  # type: ignore[arg-type]
        LuotKhamConflictError(
            "PATIENT_BUSY",
            "Khách đang làm dịch vụ ở phòng SA1.",
            {"ma": "PATIENT_BUSY", "phong": "SA1", "chuyen_duoc": True},
        ),
    )
    assert r.status_code == 409
    assert json.loads(bytes(r.body)) == {
        "error": "PATIENT_BUSY",
        "message": "Khách đang làm dịch vụ ở phòng SA1.",
        "chi_tiet": {"ma": "PATIENT_BUSY", "phong": "SA1", "chuyen_duoc": True},
    }


async def test_loi_khong_chi_tiet_giu_dang_cu() -> None:
    r = await clinicai_exception_handler(
        None,  # type: ignore[arg-type]
        LuotKhamConflictError("VERSION_CONFLICT", "Màn hình đã cũ."),
    )
    assert json.loads(bytes(r.body)) == {
        "error": "VERSION_CONFLICT",
        "message": "Màn hình đã cũ.",
    }
