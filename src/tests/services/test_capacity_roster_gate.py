"""Lịch làm việc của bác sĩ là luật CAO NHẤT — cao hơn cả ba tầng sức chứa.

Quyết định của Quang (2026-08-04): *"lịch của bác sĩ là luật cao nhất, dù đặt
thiết lập 18:00–18:15 8 slot nhưng vào ngày không có lịch của bác sĩ thì chỉ
hiện là hôm nay không có lịch của bác sĩ."*

Trước đây lưới đặt lịch KHÔNG hỏi lịch trực lần nào: nó mời CSKH đặt vào một
buổi chiều mà bác sĩ không đi làm, và sai đó chỉ vỡ ra lúc bệnh nhân đã tới nơi.

Nhưng luật này chỉ có hiệu lực KHI NGÀY ĐÓ ĐÃ XẾP CA. CSKH đặt lịch trước cả
tháng, lúc ấy lịch trực chưa có — coi "chưa xếp ca" là "không đi làm" sẽ khoá
sạch mọi ngày trong tương lai. Hai test dưới đây khoá cả hai chiều đó, vì sai
theo chiều nào cũng hỏng một luồng làm việc thật.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from clinicai.services.capacity_service import CapacityService

CLINIC = "a0000000-0000-4000-8000-000000000001"
LOCATION = "b0000000-0000-4000-8000-000000000001"
DOCTOR = "a33a95b4-b43f-479f-8b01-f1003436d85d"


OPEN, CLOSE = 8 * 60, 23 * 60


class _Conn:
    """Trả lời câu hỏi lịch trực theo kịch bản, và ghi lại có truy vấn khung giờ
    hay không — vì "không hỏi tới khung giờ" chính là điều cần chứng minh."""

    def __init__(self, *, roster_known: bool, shifts: list[str]) -> None:
        self._duty = {
            "roster_known": roster_known,
            "shifts": shifts,
            "open_minute": OPEN,
            "close_minute": CLOSE,
        }
        self.fetched_slots = False

    async def fetchrow(self, _query: str, *_args: Any) -> dict[str, Any]:
        return self._duty

    async def fetch(self, _query: str, *_args: Any) -> list[Any]:
        self.fetched_slots = True
        # Mỗi khung 60 phút suốt giờ mở cửa, để kiểm phần LỌC theo ca trực.
        return [
            {
                "minute_of_day": m,
                "slot_minutes": 60,
                "regular_cap": 3,
                "walkin_cap": 1,
                "regular_used": 0,
                "walkin_used": 0,
            }
            for m in range(OPEN, CLOSE, 60)
        ]


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield self._conn


async def _quote(conn: _Conn) -> dict[str, Any]:
    return await CapacityService(_Pool(conn)).quote(  # type: ignore[arg-type]
        date="2026-08-04",
        location_id=LOCATION,
        doctor_id=DOCTOR,
        clinic_id=CLINIC,
    )


@pytest.mark.asyncio
async def test_a_rostered_day_without_this_doctor_offers_nothing() -> None:
    """Ngày đã xếp ca mà bác sĩ không có tên: không một khung nào được mời."""
    conn = _Conn(roster_known=True, shifts=[])
    out = await _quote(conn)

    assert out["off_duty"] is True
    assert out["slots"] == []
    # Không phải "hết chỗ" — là "không có mặt". Giao diện phải nói hai câu khác
    # nhau, vì cách xử lý khác nhau: một bên đổi giờ, một bên đổi ngày/bác sĩ.
    assert out["roster_known"] is True
    assert not conn.fetched_slots, (
        "đã biết bác sĩ không đi làm thì không cần hỏi sức chứa từng khung"
    )


@pytest.mark.asyncio
async def test_a_rostered_day_with_this_doctor_behaves_normally() -> None:
    conn = _Conn(roster_known=True, shifts=["FULL"])
    out = await _quote(conn)

    assert out["off_duty"] is False
    assert conn.fetched_slots, "bác sĩ có ca trực thì phải đọc sức chứa như thường"


@pytest.mark.asyncio
async def test_a_day_with_no_roster_yet_stays_open() -> None:
    """CSKH đặt trước cả tháng, lúc đó chưa ai xếp ca.

    Đây là nửa dễ làm sai nhất: coi "chưa xếp ca" là "không đi làm" sẽ khoá
    sạch tương lai, và triệu chứng — mọi ngày xa đều trống trơn — trông y hệt
    một lỗi tải dữ liệu, nên rất khó lần ra.
    """
    conn = _Conn(roster_known=False, shifts=[])
    out = await _quote(conn)

    assert out["off_duty"] is False
    assert out["roster_known"] is False
    assert conn.fetched_slots, "ngày chưa xếp ca vẫn phải mời đặt như bình thường"


class TestAMorningShiftIsNotAWholeDay:
    """Ca sáng kết thúc 12:00 (quyết định của Quang, 2026-08-04).

    Bản đầu của luật lịch trực chỉ dừng ở mức NGÀY, nên BS Thành chỉ trực ca
    sáng ngày 08/08 vẫn được mời đặt lúc 18:00. Một luật đúng nửa vời khó chịu
    hơn không có: nó tạo cảm giác đã được kiểm.
    """

    @pytest.mark.asyncio
    async def test_afternoon_slots_disappear_for_a_morning_only_doctor(self) -> None:
        conn = _Conn(roster_known=True, shifts=["SANG"])
        out = await _quote(conn)

        times = [s["minute_of_day"] for s in out["slots"]]
        assert times, "ca sáng vẫn phải còn khung buổi sáng"
        assert max(times) < 12 * 60, "không được mời đặt sau 12:00"
        assert out["off_duty"] is False, "có đi làm, chỉ là không cả ngày"
        assert out["partial_shift"] is True, "màn hình phải nói được 'chỉ trực…'"

    @pytest.mark.asyncio
    async def test_a_full_day_doctor_keeps_every_slot(self) -> None:
        conn = _Conn(roster_known=True, shifts=["FULL"])
        out = await _quote(conn)

        assert len(out["slots"]) == (CLOSE - OPEN) // 60
        # Trực cả ngày là chuyện thường — dán nhãn "chỉ trực…" cho mọi cột chỉ
        # làm loãng đúng cái nhãn cần đọc.
        assert out["partial_shift"] is False

    @pytest.mark.asyncio
    async def test_morning_at_one_station_plus_afternoon_at_another_is_full(
        self,
    ) -> None:
        """Có thật trong dữ liệu: BS Thành 09/08 có cả SANG lẫn CHIEU."""
        conn = _Conn(roster_known=True, shifts=["SANG", "CHIEU"])
        out = await _quote(conn)

        assert len(out["slots"]) == (CLOSE - OPEN) // 60
        assert out["partial_shift"] is False
