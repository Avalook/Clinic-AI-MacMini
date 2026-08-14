"""Lịch hẹn tuần: hình dạng trả về và mốc biên tuần.

Phần LUẬT (Tái khám / Khám lần đầu) nằm trong SQL nên không kiểm được ở đây —
nó được đối chiếu trực tiếp với đường cũ trên dữ liệu prod: 46 dòng qua 13
tuần, mọi trường giống hệt. Test này khoá hai thứ còn lại, và cả hai đều đã
từng gây lỗi thật:

  * kiểu tham số gửi xuống driver (chuỗi thay vì datetime → 500);
  * hình dạng lồng nhau mà TSX đang đọc (sai một khoá → màn hình trắng).
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from typing import Any

import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.week_appointments_service import (
    WeekAppointmentsService,
    _row_to_dict,
    _vn_midnight,
)

CLINIC = "a0000000-0000-4000-8000-000000000001"


class TestTheWeekBoundary:
    def test_midnight_is_a_datetime_not_a_string(self) -> None:
        """asyncpg gọi thẳng phương thức của datetime lên tham số timestamptz.

        Một chuỗi ở đây là AttributeError và cả endpoint thành 500 — đúng lỗi
        đã làm /appointments/quote chết lặng rất lâu.
        """
        m = _vn_midnight(datetime.date(2026, 8, 3))
        assert isinstance(m, datetime.datetime)

    def test_midnight_carries_the_clinic_timezone(self) -> None:
        """Không mang múi giờ thì biên tuần lệch 7 tiếng tuỳ môi trường."""
        m = _vn_midnight(datetime.date(2026, 8, 3))
        assert m.tzinfo is not None
        assert m.utcoffset() == datetime.timedelta(hours=7)

    def test_midnight_is_the_start_of_that_local_day(self) -> None:
        m = _vn_midnight(datetime.date(2026, 8, 3))
        assert (m.year, m.month, m.day) == (2026, 8, 3)
        assert (m.hour, m.minute, m.second) == (0, 0, 0)
        # Nửa đêm 03/08 giờ VN = 17:00 ngày 02/08 UTC.
        utc = m.astimezone(datetime.timezone.utc)
        assert (utc.day, utc.hour) == (2, 17)


class _Row(dict[str, Any]):
    """asyncpg.Record đọc bằng [] — dict đủ để kiểm phần ánh xạ."""


def _record(**over: Any) -> _Row:
    base = {
        "id": "11111111-1111-4111-8111-111111111111",
        "slot_start": datetime.datetime(2026, 8, 3, 11, 0, tzinfo=CLINIC_TZ),
        "status": "SCHEDULED",
        "queue_number": "2",
        "doctor_id": "22222222-2222-4222-8222-222222222222",
        "booking_channel": "HOTLINE",
        "phan_loai": "Tái khám",
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
        "doctor_name": "TS.BS. Phan Chí Thành",
        "service_name": "Khám phụ khoa",
        # Hai cột nuôi luật thứ tự gọi. `checked_in_at` là chỗ endpoint này
        # trước đây KHÔNG trả, nên luật "có hẹn và đến đúng giờ" chưa từng chạy
        # ở lưới trang chủ.
        "checked_in_at": None,
        "slot_minutes": 15,
    }
    base.update(over)
    return _Row(base)


class TestTheShapeTheScreenReads:
    def test_relations_come_back_nested_like_postgrest(self) -> None:
        """TSX đọc `r.patient.full_name`, `r.doctor.full_name`, `r.service.name`.

        Trả phẳng (`doctor_name`) sẽ không lỗi biên dịch ở đâu cả — nó chỉ làm
        cột bác sĩ trống trơn trên lưới.
        """
        out = _row_to_dict(_record())
        assert out["doctor"] == {"full_name": "TS.BS. Phan Chí Thành"}
        assert out["service"] == {"name": "Khám phụ khoa"}
        assert out["patient"]["full_name"] == "Nguyễn Thị A"
        assert out["patient"]["clinic_patient_id"].startswith("33333333")

    def test_missing_relations_are_null_not_empty_objects(self) -> None:
        """`{full_name: null}` sẽ hiện ra một dòng trống thay vì bị bỏ qua."""
        out = _row_to_dict(_record(doctor_name=None, service_name=None))
        assert out["doctor"] is None
        assert out["service"] is None

    def test_dates_are_iso_strings(self) -> None:
        out = _row_to_dict(_record())
        assert out["patient"]["date_of_birth"] == "1990-05-02"
        assert out["slot_start"].startswith("2026-08-03T11:00")

    def test_a_null_birthday_stays_null(self) -> None:
        out = _row_to_dict(_record(date_of_birth=None))
        assert out["patient"]["date_of_birth"] is None

    def test_an_appointment_without_a_patient_has_no_classification(self) -> None:
        """SQL trả '' cho dòng mất bệnh nhân; phần ánh xạ phải để patient = None."""
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
async def test_the_range_sent_down_is_exactly_seven_local_days() -> None:
    conn = _Conn()
    await WeekAppointmentsService(_Pool(conn)).week(
        clinic_id=CLINIC, week_start=datetime.date(2026, 8, 3)
    )
    _clinic, start, end, hidden = conn.args
    assert isinstance(start, datetime.datetime)
    assert isinstance(end, datetime.datetime)
    assert end - start == datetime.timedelta(days=7)
    # Nửa mở: lịch đúng nửa đêm ngày thứ tám thuộc TUẦN SAU, không phải tuần này.
    assert start.date() == datetime.date(2026, 8, 3)
    assert end.date() == datetime.date(2026, 8, 10)
    assert set(hidden) == {"CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"}


def test_lich_da_huy_khong_duoc_tinh_la_lan_kham_truoc() -> None:
    """Khách đặt rồi huỷ, đặt lại → lịch mới vẫn là LẦN ĐẦU của họ.

    Bản cũ tính mốc sớm nhất trên MỌI trạng thái, nên một lịch đã huỷ vẫn kéo
    lịch sau thành "Tái khám" — trong khi màn Quản lý khách hàng gọi đúng người
    ấy là "Khách mới" (nó đếm lượt khám XONG). Hai màn nói ngược nhau về cùng
    một người trong cùng một ca trực.

    Kiểm bằng cách đọc SQL: nhánh `som_nhat` phải lọc trạng thái chết. Không có
    cách nào khác ở tầng này — luật nằm trong một chuỗi SQL, và cả mypy lẫn
    ruff đều không đọc được bên trong nó (đã có một lỗi kiểu uuid lọt qua đúng
    vì thế, 14/08/2026).
    """
    from clinicai.services.week_appointments_service import _SQL

    dau = _SQL.index("som_nhat AS (")
    khoi = _SQL[dau : _SQL.index(")", _SQL.index("GROUP BY", dau))]
    assert "$4::text[]" in khoi, (
        "som_nhat phải bỏ lịch huỷ/không đến/bác sĩ từ chối — nếu không, một "
        "lịch đã huỷ biến khách chưa từng tới thành 'khám cũ'"
    )
