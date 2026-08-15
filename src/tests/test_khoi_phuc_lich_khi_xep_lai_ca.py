"""Đường về của một cú xoá ca nhầm (15/08/2026).

`RosterService.remove` gỡ bác sĩ khỏi lịch hẹn khi ca khám cuối trong ngày bị
xoá. `_khoi_phuc_lich_bi_go` là chiều ngược: xếp lại ca thì những lịch ấy quay
về với đúng bác sĩ ấy — nhưng CHỈ những lịch mà giờ hẹn nằm trong ca mới, và
CHỈ khi ghế còn trống. Các bài ở đây chạy qua CHÍNH hàm đó với một connection
giả có savepoint: luật lọc theo ca, luật bỏ-qua-khi-hết-ghế, và luật "PENDING
không kéo lịch" đều là hành vi, không phải chuỗi ký tự trong mã nguồn.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import date
from typing import Any
from unittest.mock import MagicMock

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.config_service import RosterService


def _identity(role: ClinicRole = ClinicRole.MANAGEMENT) -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Quản lý A",
        department="Điều hành",
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class _GiaoDich:
    """Savepoint giả — chỉ cần vào/ra được; rollback là việc của Postgres."""

    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False  # không nuốt exception — để chỗ gọi tự xử


class _Conn:
    """Connection giả trả lời theo KỊCH BẢN: mỗi câu SQL khớp một mẩu khoá.

    Khác `_Conn` của test_booking_service (trả theo thứ tự): khối khôi phục
    chạy vòng lặp với số câu lệnh thay đổi theo dữ liệu, đếm thứ tự sẽ gãy
    ngay khi thêm một ứng viên. Khớp theo mẩu chuỗi thì kịch bản đọc được.
    """

    def __init__(
        self,
        *,
        ung_vien: list[dict[str, Any]],
        ca: dict[str, Any] | None,
        ghe_day_cho: set[str] = frozenset(),  # type: ignore[assignment]
    ) -> None:
        self._ung_vien = ung_vien
        self._ca = ca
        self._ghe_day_cho = set(ghe_day_cho)
        self.da_gan: list[str] = []
        self.event_cho: list[str] = []

    def transaction(self) -> _GiaoDich:
        return _GiaoDich(self)

    async def fetch(self, sql: str, *args: object) -> list[dict[str, Any]]:
        assert "bac_si_da_go_id = $2::uuid" in sql, "truy vấn ứng viên đổi dạng?"
        return self._ung_vien

    async def fetchrow(self, sql: str, *args: object) -> dict[str, Any] | None:
        assert "clinic_hours_for_date" in sql, "truy vấn ca trực đổi dạng?"
        return self._ca

    async def fetchval(self, sql: str, *args: object) -> object:
        assert "SET doctor_id = $2::uuid" in sql, "câu UPDATE khôi phục đổi dạng?"
        appt_id = str(args[0])
        # Trigger sức chứa từ chối bằng RAISE — mô phỏng đúng đường ấy.
        if appt_id in self._ghe_day_cho:
            raise asyncpg.PostgresError("Khung giờ đã đầy")
        self.da_gan.append(appt_id)
        return appt_id

    async def execute(self, sql: str, *args: object) -> None:
        assert "appointment.doctor_restored" in sql, "event_log đổi dạng?"
        self.event_cho.append(str(args[1]))


_CA_SANG = {"shifts": ["SANG"], "open_minute": 7 * 60, "close_minute": 20 * 60}


def _chay(conn: _Conn) -> list[str]:
    service = RosterService(MagicMock())
    return asyncio.run(
        service._khoi_phuc_lich_bi_go(
            conn,
            doctor_id="bs000000-0000-4000-8000-000000000001",
            work_date=date(2026, 8, 20),
            identity=_identity(),
        )
    )


class TestKhoiPhucLichBiGo:
    def test_lich_trong_ca_duoc_gan_lai_kem_event(self) -> None:
        conn = _Conn(
            ung_vien=[{"id": "a1", "phut": 8 * 60}, {"id": "a2", "phut": 9 * 60}],
            ca=_CA_SANG,
        )
        assert _chay(conn) == ["a1", "a2"]
        assert conn.event_cho == ["a1", "a2"]

    def test_them_ca_sang_khong_keo_lich_buoi_chieu(self) -> None:
        """15:00 nằm ngoài ca SÁNG — người đó chiều nay vẫn nghỉ."""
        conn = _Conn(
            ung_vien=[{"id": "sang", "phut": 8 * 60}, {"id": "chieu", "phut": 15 * 60}],
            ca=_CA_SANG,
        )
        assert _chay(conn) == ["sang"]

    def test_ghe_da_bi_chiem_thi_lich_ay_o_lai_hang_cho(self) -> None:
        """Trigger sức chứa RAISE → bỏ qua đúng MỘT lịch, các lịch sau vẫn gắn."""
        conn = _Conn(
            ung_vien=[
                {"id": "a1", "phut": 8 * 60},
                {"id": "day", "phut": 9 * 60},
                {"id": "a3", "phut": 10 * 60},
            ],
            ca=_CA_SANG,
            ghe_day_cho={"day"},
        )
        assert _chay(conn) == ["a1", "a3"]
        assert conn.event_cho == ["a1", "a3"]

    def test_khong_ung_vien_thi_khong_dung_toi_gi_khac(self) -> None:
        conn = _Conn(ung_vien=[], ca=None)
        assert _chay(conn) == []

    def test_khong_gio_mo_cua_thi_khong_gan(self) -> None:
        conn = _Conn(
            ung_vien=[{"id": "a1", "phut": 8 * 60}],
            ca={"shifts": ["SANG"], "open_minute": None, "close_minute": None},
        )
        assert _chay(conn) == []


class TestLuatGoiKhoiPhuc:
    """Hai luật nằm ở CHỖ GỌI trong add_shift, khoá bằng đọc mã nguồn."""

    def test_chi_ca_kham_duoc_duyet_moi_keo_lich(self) -> None:
        """PENDING chưa phải ca trực; ca trạm khác không liên quan lịch khám."""
        ma = inspect.getsource(RosterService.add_shift)
        assert 'if station == "LICH_KHAM" and is_admin:' in ma
        goi = ma.index("_khoi_phuc_lich_bi_go")
        assert ma.index('if station == "LICH_KHAM" and is_admin:') < goi

    def test_chen_ca_va_khoi_phuc_cung_mot_giao_dich(self) -> None:
        """Đối xứng với remove(): không có khoảnh khắc ca đã có mà lịch lơ lửng."""
        ma = inspect.getsource(RosterService.add_shift)
        assert ma.index("conn.transaction()") < ma.index("INSERT INTO work_roster")
        assert ma.index("INSERT INTO work_roster") < ma.index("_khoi_phuc_lich_bi_go")
