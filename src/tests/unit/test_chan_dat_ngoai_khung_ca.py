"""Chỉ đặt lịch được trong ca làm việc — chốt `_chan_dat_ngoai_khung_ca`.

Vì sao có luật này: giờ mở cửa (07:00–22:00) rộng hơn tổng ba ca
(08:00–13:00 · 14:00–17:30 · 17:30–21:30), nên còn ba khoảng trống đặt được mà
không thuộc ca nào — sớm hơn ca sáng, nghỉ trưa, và sau khi hết ca tối. Đo trên
staging 21/08/2026 có đúng 3 lịch rơi vào đó. Chúng không lỗi ở đâu cả, chỉ làm
KPI theo ca của CSKH đếm thiếu.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.booking_service import BookingService

# Giờ mở cửa rộng hơn ba ca — chính khoảng chênh này sinh ra lỗ hổng.
MO_CUA, DONG_CUA = 7 * 60, 22 * 60


class _Conn:
    """Trả một câu trả lời duy nhất cho câu hỏi giờ mở cửa + giờ ca."""

    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row
        self.so_lan_hoi = 0

    async def fetchrow(self, sql: str, *args: object) -> Any:
        self.so_lan_hoi += 1
        return self._row


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="CSKH A",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def _luc(gio: int, phut: int = 0) -> datetime:
    """Một mốc giờ NGÀY MAI theo giờ phòng khám.

    Ngày mai chứ không phải một ngày viết cứng: bài kiểm ghim ngày sẽ đỏ vào
    một hôm không ai đoán trước, đúng cái bẫy đã ghi ở `_MAI` trong
    test_booking_service.py.
    """
    mai = datetime.now(CLINIC_TZ) + timedelta(days=1)
    return mai.replace(hour=gio, minute=phut, second=0, microsecond=0)


def _chan(gio: int, phut: int = 0, *, settings: Any = None) -> str | None:
    """Chạy chốt. Trả None nếu cho qua, hoặc câu từ chối."""
    service = BookingService(MagicMock())
    conn = _Conn(
        {"open_minute": MO_CUA, "close_minute": DONG_CUA, "settings": settings}
    )
    try:
        asyncio.run(
            service._chan_dat_ngoai_khung_ca(
                conn,
                slot_start=_luc(gio, phut),
                identity=_identity(),
            )
        )
    except ValidationError as loi:
        return str(loi)
    return None


class TestBaKhoangTrong:
    """Ba khoảng đặt được nhưng không thuộc ca nào — nay bị chặn."""

    @pytest.mark.parametrize(
        ("gio", "phut", "ten"),
        [
            (7, 15, "sớm hơn ca sáng"),
            (7, 30, "sớm hơn ca sáng"),
            (13, 30, "nghỉ trưa"),
            (21, 30, "vừa hết ca tối"),
            (21, 45, "sau ca tối"),
        ],
    )
    def test_gio_ngoai_ca_bi_tu_choi(self, gio: int, phut: int, ten: str) -> None:
        loi = _chan(gio, phut)
        assert loi is not None, f"{gio:02d}:{phut:02d} ({ten}) phải bị chặn"
        assert f"{gio:02d}:{phut:02d}" in loi, "câu từ chối phải nhắc đúng giờ bị chặn"

    def test_cau_tu_choi_noi_ro_duoc_dat_vao_khung_nao(self) -> None:
        """Từ chối mà không chỉ đường thì người trực phải đoán."""
        loi = _chan(13, 30)
        assert loi is not None
        assert "08:00" in loi and "13:00" in loi, "phải liệt kê khung nhận lịch"
        assert "21:30" in loi

    def test_cau_tu_choi_chi_dung_cai_cua_co_that(self) -> None:
        """Bản đầu bảo "sửa ở màn Lịch làm việc" — màn ấy KHÔNG sửa giờ ca.

        Chỉ sai một cái cửa không tồn tại còn tệ hơn không chỉ gì: người trực đi
        tìm, không thấy, rồi thôi không tin câu báo lỗi nào nữa. Màn sửa giờ ca
        nằm ở Cài đặt (`PATCH /api/v1/ca-lam-viec`).
        """
        loi = _chan(7, 15)
        assert loi is not None
        assert "Cài đặt" in loi, loi
        assert "Lịch làm việc" not in loi, "màn đó xếp AI trực, không định nghĩa ca"


class TestGioTrongCaThiQua:
    @pytest.mark.parametrize(
        ("gio", "phut", "ten"),
        [
            (8, 0, "đầu ca sáng"),
            (10, 0, "giữa ca sáng"),
            (12, 59, "sát cuối ca sáng"),
            (14, 0, "đầu ca chiều"),
            (17, 30, "giao chiều sang tối, không có kẽ hở"),
            (18, 20, "giữa ca tối"),
            (21, 29, "sát cuối ca tối"),
        ],
    )
    def test_gio_trong_ca_van_dat_duoc(self, gio: int, phut: int, ten: str) -> None:
        assert _chan(gio, phut) is None, f"{gio:02d}:{phut:02d} ({ten}) phải đặt được"


class TestDocGioCaTuPhongKham:
    """Giờ ca do phòng khám khai, không viết cứng trong code."""

    def test_doi_gio_ca_thi_luat_doi_theo(self) -> None:
        # Phòng khám khác: sáng muộn hơn, tối kéo tới 22:00.
        rieng = {
            "ca_lam_viec": {
                "SANG": {"bat_dau": "09:00", "ket_thuc": "12:30"},
                "CHIEU": {"bat_dau": "13:30", "ket_thuc": "17:00"},
                "TOI": {"bat_dau": "18:00", "ket_thuc": "22:00"},
            }
        }
        # 08:30 nằm trong ca sáng MẶC ĐỊNH nhưng ngoài ca sáng của phòng này.
        assert _chan(8, 30, settings=rieng) is not None
        # 21:45 ngoài ca tối mặc định nhưng trong ca tối của phòng này.
        assert _chan(21, 45, settings=rieng) is None
        # 13:00 là nghỉ trưa của phòng này (12:30–13:30).
        assert _chan(13, 0, settings=rieng) is not None

    def test_settings_hong_thi_dung_ca_mac_dinh_chu_khong_mo_toang(self) -> None:
        """Cấu hình hỏng không được biến thành "cho đặt mọi giờ"."""
        for rac in (None, "khong-phai-json", {"ca_lam_viec": "hong"}, {}):
            assert _chan(7, 15, settings=rac) is not None, f"hỏng ở {rac!r}"
            assert _chan(10, 0, settings=rac) is None, f"hỏng ở {rac!r}"


class TestNgayKhongCoGioMoCua:
    def test_ngay_dong_cua_thi_chot_nay_im_lang(self) -> None:
        """Hai luật cùng hét một lỗi thì người dùng đọc được một nửa sự thật.

        Ngày phòng khám đóng cửa đã có luật giờ mở cửa lo; chốt này nói thêm
        chỉ làm câu báo lỗi mâu thuẫn nhau.
        """
        service = BookingService(MagicMock())
        conn = _Conn({"open_minute": None, "close_minute": None, "settings": None})
        asyncio.run(
            service._chan_dat_ngoai_khung_ca(
                conn,
                slot_start=_luc(7, 15),
                identity=_identity(),
            )
        )

    def test_khong_co_dong_nao_cung_im_lang(self) -> None:
        service = BookingService(MagicMock())
        conn = _Conn(None)
        asyncio.run(
            service._chan_dat_ngoai_khung_ca(
                conn,
                slot_start=_luc(7, 15),
                identity=_identity(),
            )
        )


class TestGanDuHaiDuongChonGio:
    """Luật 12.2 — ĐẾM số nơi gọi, đừng tin là đã gắn đủ.

    Chốt "không đặt vào quá khứ" từng chỉ gắn ở `create`: cửa trước khoá còn
    cửa sau mở, đặt lịch tương lai rồi dời về hôm qua thì lọt. Luật này có đúng
    hai đường chọn giờ — tạo mới và đổi lịch — nên phải gắn ở cả hai.
    """

    def test_create_co_goi_chot(self) -> None:
        nguon = inspect.getsource(BookingService.create)
        assert "_chan_dat_ngoai_khung_ca" in nguon

    def test_doi_lich_co_goi_chot(self) -> None:
        nguon = inspect.getsource(BookingService._build_patch)
        assert "_chan_dat_ngoai_khung_ca" in nguon

    def test_hai_duong_va_chi_hai_duong(self) -> None:
        """Gắn thêm vào `_guard_slot` sẽ khoá luôn dữ liệu CŨ.

        `reassign` và `assign_doctor` đi qua `_guard_slot` nhưng dùng lại giờ
        của lịch đã có. Gắn chốt ở đó nghĩa là một lịch cũ nằm ngoài ca sẽ
        không gán được bác sĩ nữa — phạt người dùng vì dữ liệu có trước luật.
        """
        nguon = inspect.getsource(BookingService._guard_slot)
        assert "_chan_dat_ngoai_khung_ca" not in nguon

        ca_file = inspect.getsource(BookingService)
        assert ca_file.count("await self._chan_dat_ngoai_khung_ca(") == 2
