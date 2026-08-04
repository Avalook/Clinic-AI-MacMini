"""Bảng khám bác sĩ: hình dạng trả về và tham số gửi xuống driver.

Hai LUẬT của service này (phân loại khám, cờ chờ đọc KQ) nằm trong SQL nên
không kiểm được ở đây. Chúng đã được đối chiếu trực tiếp với đường cũ trên
prod, và vì dữ liệu thật chỉ có 2 phiếu xét nghiệm — tức là luật B3 gần như
không được chạm tới — bảy tình huống của nó được dựng riêng trong một giao
dịch rồi rollback:

    không có phiếu nào · một phiếu đã có KQ · chỉ có external_ref ·
    hai phiếu còn một chờ · hai phiếu đều có KQ · toàn khoảng trắng · chờ hết

Test dưới đây khoá phần còn lại: hình dạng mà TSX đọc, và kiểu tham số — hai
thứ mà mọi kiểm tra tĩnh đều bỏ lọt.
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from typing import Any

import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.doctor_board_service import DoctorBoardService, _row_to_dict

CLINIC = "a0000000-0000-4000-8000-000000000001"
DOCTOR = "a33a95b4-b43f-479f-8b01-f1003436d85d"


def _record(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "11111111-1111-4111-8111-111111111111",
        "slot_start": datetime.datetime(2026, 8, 7, 18, 0, tzinfo=CLINIC_TZ),
        "status": "CHECKED_IN",
        "queue_number": "3",
        "booking_channel": "WALK_IN",
        "phan_loai": "Tái khám",
        "b3_ready": True,
        "checked_in_at": datetime.datetime(2026, 8, 7, 17, 55, tzinfo=CLINIC_TZ),
        "clinic_patient_id": "33333333-3333-4333-8333-333333333333",
        "patient_code": "BN-2026-000001",
        "full_name": "Nguyễn Thị A",
        "date_of_birth": datetime.date(1990, 5, 2),
        "phone_primary": "0900000000",
        "phone_secondary": None,
        "gender": "Nữ",
        "ethnicity": "Kinh",
        "nationality": "Việt Nam",
        "occupation": None,
        "patient_objection": None,
        "address": "Hà Nội",
        "guardian_name": None,
        "service_name": "Khám phụ khoa",
    }
    base.update(over)
    return base


class TestTheShapeTheBoardReads:
    def test_checked_in_at_comes_back_flat_not_wrapped_in_an_array(self) -> None:
        """Bản cũ nhận mảng ``visit`` từ PostgREST rồi tự lấy phần tử [0].

        "Phần tử đầu của một mảng không có thứ tự" là một phép chọn ngẫu nhiên.
        Ở đây việc chọn đã xong, có thứ tự, trong database — nên trường này
        phẳng, và TSX không phải tự làm phẳng nữa.
        """
        out = _row_to_dict(_record())
        assert out["checked_in_at"].startswith("2026-08-07T17:55")
        assert "visit" not in out

    def test_a_patient_who_never_checked_in_has_null(self) -> None:
        out = _row_to_dict(_record(checked_in_at=None))
        assert out["checked_in_at"] is None

    def test_service_is_nested_and_absent_becomes_null(self) -> None:
        assert _row_to_dict(_record())["service"] == {"name": "Khám phụ khoa"}
        assert _row_to_dict(_record(service_name=None))["service"] is None

    def test_the_two_computed_flags_survive_the_mapping(self) -> None:
        """Cả hai đều quyết định THỨ TỰ GỌI BỆNH NHÂN trên bảng khám."""
        out = _row_to_dict(_record())
        assert out["phan_loai"] == "Tái khám"
        assert out["b3_ready"] is True

    def test_an_appointment_without_a_patient_still_maps(self) -> None:
        out = _row_to_dict(_record(clinic_patient_id=None, phan_loai=""))
        assert out["patient"] is None
        assert out["phan_loai"] == ""


class _Conn:
    def __init__(self) -> None:
        self.args: tuple[Any, ...] = ()

    async def fetch(self, _q: str, *args: Any) -> list[Any]:
        self.args = args
        return []


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield self._conn


@pytest.mark.asyncio
async def test_no_doctor_means_every_doctor_not_zero_rows() -> None:
    """``doctor_id=None`` là "mọi bác sĩ" (Lễ tân, TKYK), không phải "không ai".

    SQL dùng ``$4 IS NULL OR doctor_id = $4``; nếu ai đó đổi thành so sánh
    thẳng thì bảng của Lễ tân sẽ trống trơn mà không có lỗi nào.
    """
    conn = _Conn()
    await DoctorBoardService(_Pool(conn)).board(
        clinic_id=CLINIC,
        start=datetime.datetime(2026, 8, 1, tzinfo=CLINIC_TZ),
        end=datetime.datetime(2026, 9, 1, tzinfo=CLINIC_TZ),
        doctor_id=None,
    )
    assert conn.args[3] is None


@pytest.mark.asyncio
async def test_the_window_reaches_the_driver_as_datetimes() -> None:
    """Chuỗi ở đây là 500, không phải một kết quả sai — xem capacity_service."""
    conn = _Conn()
    await DoctorBoardService(_Pool(conn)).board(
        clinic_id=CLINIC,
        start=datetime.datetime(2026, 8, 1, tzinfo=CLINIC_TZ),
        end=datetime.datetime(2026, 9, 1, tzinfo=CLINIC_TZ),
        doctor_id=DOCTOR,
    )
    _clinic, start, end, doctor = conn.args
    assert isinstance(start, datetime.datetime)
    assert isinstance(end, datetime.datetime)
    assert start.tzinfo is not None and end.tzinfo is not None
    assert doctor == DOCTOR
