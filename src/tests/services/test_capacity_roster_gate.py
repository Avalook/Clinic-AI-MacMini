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

    def __init__(
        self,
        *,
        roster_known: bool,
        shifts: list[str],
        ca_lam_viec: dict[str, Any] | None = None,
    ) -> None:
        self._duty = {
            "roster_known": roster_known,
            "shifts": shifts,
            "open_minute": OPEN,
            "close_minute": CLOSE,
            # `settings` đi cùng giờ mở cửa từ 21/08/2026 — giờ của từng ca là
            # cấu hình của phòng khám. None ⇒ dùng mặc định (sáng 08:00–13:00 ·
            # chiều 14:00–17:30 · tối 17:30–21:30).
            # Bài nào cần giờ ca cụ thể thì tự khai, thay vì phụ thuộc mặc
            # định — mặc định là con số của MỘT phòng khám và sẽ đổi.
            "settings": ({"ca_lam_viec": ca_lam_viec} if ca_lam_viec else None),
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


async def _quote(conn: _Conn, doctor_id: str | None = DOCTOR) -> dict[str, Any]:
    return await CapacityService(_Pool(conn)).quote(
        date="2026-08-04",
        location_id=LOCATION,
        doctor_id=doctor_id,
        clinic_id=CLINIC,
    )


def _cac_gio(out: dict[str, Any]) -> list[str]:
    return [o["time"] for o in out["slots"]]


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


class TestCaSangKhongPhaiCaNgay:
    """Ca sáng không phải cả ngày — canh HÀNH VI, không canh con số.

    VIẾT LẠI 21/08/2026 (Luật 12.5). Bản cũ khoá cứng mốc 12:00 vì hồi ấy ca
    được suy từ một mốc chia duy nhất. Nay giờ từng ca là CẤU HÌNH của phòng
    khám, nên khoá con số ở đây là khoá lựa chọn của một phòng khám cụ thể vào
    bài kiểm của cả hệ. Các bài dưới tự khai giờ ca rồi kiểm quan hệ giữa đầu
    vào và đầu ra.

    Điều được canh vẫn y nguyên: bản đầu của luật lịch trực chỉ dừng ở mức
    NGÀY, nên BS Thành chỉ trực ca sáng ngày 08/08 vẫn được mời đặt lúc 18:00.
    Một luật đúng nửa vời khó chịu hơn không có: nó tạo cảm giác đã được kiểm.
    """

    #: Ba ca LIỀN NHAU, không nghỉ trưa — để "cả ngày = mọi khung" vẫn đúng và
    #: bài kiểm nói được về một chuyện tại một thời điểm.
    CA_LIEN = {
        "SANG": {"bat_dau": "08:00", "ket_thuc": "12:00"},
        "CHIEU": {"bat_dau": "12:00", "ket_thuc": "18:00"},
        "TOI": {"bat_dau": "18:00", "ket_thuc": "23:00"},
    }

    @pytest.mark.asyncio
    async def test_khung_buoi_chieu_bien_mat_voi_bac_si_chi_truc_sang(self) -> None:
        conn = _Conn(roster_known=True, shifts=["SANG"], ca_lam_viec=self.CA_LIEN)
        out = await _quote(conn)

        times = [s["minute_of_day"] for s in out["slots"]]
        assert times, "ca sáng vẫn phải còn khung buổi sáng"
        assert max(times) < 12 * 60, "hết ca sáng thì không được mời đặt nữa"
        assert out["off_duty"] is False, "có đi làm, chỉ là không cả ngày"
        assert out["partial_shift"] is True, "màn hình phải nói được 'chỉ trực…'"

    @pytest.mark.asyncio
    async def test_ca_toi_chi_con_khung_buoi_toi(self) -> None:
        """Ca thứ ba (21/08/2026) — chiều ngược của bài trên."""
        conn = _Conn(roster_known=True, shifts=["TOI"], ca_lam_viec=self.CA_LIEN)
        out = await _quote(conn)

        times = [s["minute_of_day"] for s in out["slots"]]
        assert times, "ca tối phải còn khung buổi tối"
        assert min(times) >= 18 * 60, "chưa tới ca tối thì chưa được mời đặt"
        assert out["partial_shift"] is True

    @pytest.mark.asyncio
    async def test_bac_si_ca_ngay_giu_moi_khung(self) -> None:
        conn = _Conn(roster_known=True, shifts=["FULL"], ca_lam_viec=self.CA_LIEN)
        out = await _quote(conn)

        assert len(out["slots"]) == (CLOSE - OPEN) // 60
        # Trực cả ngày là chuyện thường — dán nhãn "chỉ trực…" cho mọi cột chỉ
        # làm loãng đúng cái nhãn cần đọc.
        assert out["partial_shift"] is False

    @pytest.mark.asyncio
    async def test_ca_ngay_co_nghi_trua_thi_khung_gio_nghi_bien_mat(self) -> None:
        """Giờ ca thật của Dr4Women: cả ngày KHÔNG phủ 13:00–14:00.

        Đây là thứ mô hình cũ không diễn tả nổi, và là lý do hàm khung ca đổi
        chữ ký. Nếu ai đó "sửa cho gọn" thành một khoảng liền, bài này đỏ.
        """
        conn = _Conn(
            roster_known=True,
            shifts=["FULL"],
            ca_lam_viec={
                "SANG": {"bat_dau": "08:00", "ket_thuc": "13:00"},
                "CHIEU": {"bat_dau": "14:00", "ket_thuc": "17:30"},
                "TOI": {"bat_dau": "17:30", "ket_thuc": "21:30"},
            },
        )
        out = await _quote(conn)
        times = {s["minute_of_day"] for s in out["slots"]}

        assert 12 * 60 in times, "12:00 vẫn trong ca sáng"
        assert 13 * 60 not in times, "13:00 là giờ nghỉ trưa"
        assert 14 * 60 in times, "14:00 vào ca chiều"
        assert 21 * 60 in times, "21:00 vẫn trong ca tối (tới 21:30)"
        assert 22 * 60 not in times, "sau 21:30 thì hết ca, dù cửa còn mở"

    @pytest.mark.asyncio
    async def test_sang_o_tram_nay_chieu_o_tram_kia_la_ca_ngay(self) -> None:
        """Có thật trong dữ liệu: BS Thành 09/08 có cả SANG lẫn CHIEU."""
        conn = _Conn(
            roster_known=True, shifts=["SANG", "CHIEU"], ca_lam_viec=self.CA_LIEN
        )
        out = await _quote(conn)

        assert len(out["slots"]) == (18 * 60 - OPEN) // 60
        assert out["partial_shift"] is True, "sáng+chiều vẫn thiếu ca tối"


class TestLuoiKhongMoiGioNgoaiCa:
    """Lưới không được mời khung mà chốt đặt lịch sẽ từ chối (21/08/2026).

    Giờ mở cửa rộng hơn tổng ba ca, nên lưới dựng theo giờ mở cửa có cả nghỉ
    trưa và phần sau ca tối. Từ khi `booking_service._chan_dat_ngoai_khung_ca`
    từ chối đúng những khung ấy, mời rồi mới mắng là cách chắc chắn nhất khiến
    người trực mất niềm tin vào lưới.

    CHƯA CHỌN BÁC SĨ là đường phải canh: khi đã chọn, ca trực của người ấy vốn
    đã hẹp hơn; khi chưa chọn thì trước đây `windows` rỗng và lưới mở toang.
    """

    @pytest.mark.asyncio
    async def test_chua_chon_bac_si_van_bo_nghi_trua_va_sau_ca_toi(self) -> None:
        conn = _Conn(roster_known=False, shifts=[])
        gio = _cac_gio(await _quote(conn, doctor_id=None))

        assert "10:00" in gio, "giữa ca sáng phải còn"
        assert "18:00" in gio, "giữa ca tối phải còn"
        assert "13:00" not in gio, "13:00 là nghỉ trưa — không thuộc ca nào"
        assert "22:00" not in gio, "22:00 đã hết ca tối (21:30)"

    @pytest.mark.asyncio
    async def test_gio_ca_cua_phong_kham_quyet_dinh_luoi(self) -> None:
        """Đổi giờ ca thì lưới đổi theo — không viết cứng con số nào."""
        conn = _Conn(
            roster_known=False,
            shifts=[],
            ca_lam_viec={
                "SANG": {"bat_dau": "09:00", "ket_thuc": "12:00"},
                "CHIEU": {"bat_dau": "13:00", "ket_thuc": "17:00"},
                "TOI": {"bat_dau": "19:00", "ket_thuc": "22:00"},
            },
        )
        gio = _cac_gio(await _quote(conn, doctor_id=None))

        assert "08:00" not in gio, "ca sáng của phòng này bắt đầu 09:00"
        assert "09:00" in gio
        assert "13:00" in gio, "phòng này không nghỉ 13:00"
        assert "18:00" not in gio, "18:00 rơi vào khoảng nghỉ 17:00–19:00"
        assert "21:00" in gio, "ca tối của phòng này tới 22:00"

    @pytest.mark.asyncio
    async def test_ca_truc_bac_si_van_thang_khung_phong_kham(self) -> None:
        """Chọn bác sĩ chỉ trực ca sáng thì lưới vẫn chỉ có ca sáng."""
        conn = _Conn(roster_known=True, shifts=["SANG"])
        gio = _cac_gio(await _quote(conn))

        assert "10:00" in gio
        assert "18:00" not in gio, "bác sĩ này không trực ca tối"
