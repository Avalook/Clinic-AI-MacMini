"""Tham số gửi xuống database phải đúng KIỂU, không chỉ đúng giá trị.

CHUYỆN ĐÃ XẢY RA. ``CapacityService.quote()`` nhận ``date: str`` rồi đưa thẳng
chuỗi đó vào một tham số khai ``$2::date``. Postgres khai kiểu là date, asyncpg
gọi ``.toordinal()`` trên chuỗi, và cả endpoint trả 500:

    AttributeError: 'str' object has no attribute 'toordinal'

Nó nằm im rất lâu vì hai lớp che nhau:

  * ``GET /appointments/quote`` bị route ``/appointments/{id}`` nuốt, nên chưa
    bao giờ chạy tới dòng này;
  * và mọi test về sức chứa đều gọi ``cell_state()`` — một hàm thuần, không đi
    qua asyncpg — nên 841 test xanh trong khi endpoint hỏng.

Chỉ tới khi lưới đặt lịch bắt đầu đọc số chỗ thật thì nó mới lộ, và triệu chứng
người dùng thấy là *"sao chưa áp số lượng của bác sĩ Thành"*: lưới lặng lẽ rơi
về số mặc định của phòng khám vì lời gọi 500.

Test này không kiểm SQL trả về gì. Nó kiểm điều mà không test hành vi nào bắt
được: cái gì thật sự được gửi xuống driver.
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.capacity_service import CapacityService

CLINIC = "a0000000-0000-4000-8000-000000000001"
LOCATION = "b0000000-0000-4000-8000-000000000001"


class _RecordingConn:
    """Ghi lại tham số của lần fetch, trả về không dòng nào."""

    def __init__(self) -> None:
        self.args: tuple[Any, ...] = ()

    async def fetchrow(self, _query: str, *_args: Any) -> dict[str, Any]:
        # Câu hỏi lịch trực chạy TRƯỚC (xem test_capacity_roster_gate). Ở đây
        # trả "ngày chưa xếp ca" để nó không chặn, vì file này kiểm chuyện khác.
        return {
            "roster_known": False,
            "shifts": [],
            "open_minute": 17 * 60,
            "close_minute": 23 * 60,
        }

    async def fetch(self, _query: str, *args: Any) -> list[Any]:
        self.args = args
        return []


class _RecordingPool:
    def __init__(self, conn: _RecordingConn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield self._conn


@pytest.mark.asyncio
async def test_the_day_reaches_the_driver_as_a_date_not_a_string() -> None:
    conn = _RecordingConn()
    await CapacityService(_RecordingPool(conn)).quote(  # type: ignore[arg-type]
        date="2026-08-07",
        location_id=LOCATION,
        doctor_id=None,
        clinic_id=CLINIC,
    )
    day = conn.args[1]
    # `isinstance(str)` không đủ: một chuỗi KHÔNG phải date, và đó chính là lỗi.
    assert isinstance(day, datetime.date), (
        f"tham số ngày gửi xuống asyncpg là {type(day).__name__}, phải là date"
    )
    assert day == datetime.date(2026, 8, 7)


@pytest.mark.asyncio
async def test_a_junk_date_is_a_clear_refusal_not_a_500() -> None:
    """Ngày hỏng phải thành câu tiếng Việt, không thành traceback của driver."""
    conn = _RecordingConn()
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        await CapacityService(_RecordingPool(conn)).quote(  # type: ignore[arg-type]
            date="07/08/2026",
            location_id=LOCATION,
            doctor_id=None,
            clinic_id=CLINIC,
        )
    assert conn.args == (), "không được chạm database khi tham số đã sai"


@pytest.mark.asyncio
async def test_an_empty_day_means_closed_not_an_error() -> None:
    """Không dòng nào = phòng khám đóng cửa hôm đó, khác hẳn "hết chỗ"."""
    conn = _RecordingConn()
    out = await CapacityService(_RecordingPool(conn)).quote(  # type: ignore[arg-type]
        date="2026-08-07",
        location_id=LOCATION,
        doctor_id=None,
        clinic_id=CLINIC,
    )
    assert out["closed"] is True
    assert out["slots"] == []
