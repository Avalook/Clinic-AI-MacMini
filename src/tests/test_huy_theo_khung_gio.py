"""Gỡ ca huỷ theo KHUNG GIỜ, không theo ngày (Tuyền 17/08/2026).

"Xoá ca sáng để thêm cả ngày thì sao — về bản chất bác sĩ vẫn khám." Bản cũ
hỏi thô "còn ca nào trong ngày không" nên sai cả hai chiều: xoá SÁNG còn
CHIỀU thì lịch sáng sống sót mồ côi; xoá SÁNG rồi thêm CẢ NGÀY thì lịch
sáng bị huỷ oan. Các bài dưới chạy qua CHÍNH RosterService.remove với
connection giả — luật lọc theo hợp-các-ca-còn-lại là hành vi, không phải
chuỗi ký tự.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.config_service import RosterService


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Quản lý A",
        department="Điều hành",
        role=ClinicRole.MANAGEMENT,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class _GiaoDich:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> bool:
        return False


_CA = {
    "staff_id": "bs000000-0000-4000-8000-000000000001",
    "work_date": date(2026, 8, 20),
    "station": "LICH_KHAM",
}

# Giờ mở cửa 07:00–20:00; hai lịch: 08:00 (sáng) và 15:00 (chiều).
_UNG_VIEN = [
    {"id": "sang8h", "phut": 8 * 60, "gio": "08:00"},
    {"id": "chieu15h", "phut": 15 * 60, "gio": "15:00"},
]


def _ca_con_lai(shift: str) -> dict[str, Any]:
    return {"shift": shift, "open_minute": 7 * 60, "close_minute": 20 * 60}


class _Conn:
    """Định tuyến theo nội dung SQL — vòng gọi thay đổi theo dry_run/dữ liệu."""

    def __init__(self, *, con_lai: list[dict[str, Any]]) -> None:
        self._con_lai = con_lai
        self.da_xoa_ca = False
        self.ids_huy: list[str] | None = None
        self.so_event = 0

    def transaction(self) -> _GiaoDich:
        return _GiaoDich()

    async def fetchrow(self, sql: str, *args: object) -> dict[str, Any]:
        assert "FROM work_roster" in sql
        return dict(_CA)

    async def fetch(self, sql: str, *args: object) -> list[dict[str, Any]]:
        if "clinic_hours_for_date" in sql:
            assert "coalesce(w.status, 'APPROVED') = 'APPROVED'" in sql, (
                "PENDING chưa phải ca trực — không được tính là phủ"
            )
            return self._con_lai
        assert "FROM public.appointment" in sql
        return list(_UNG_VIEN)

    async def execute(self, sql: str, *args: object) -> None:
        if "DELETE FROM work_roster" in sql:
            self.da_xoa_ca = True
        elif "UPDATE public.appointment" in sql:
            gia_tri = args[1]
            assert isinstance(gia_tri, list)
            self.ids_huy = [str(x) for x in gia_tri]
        elif "appointment.doctor_removed" in sql:
            self.so_event += 1


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    def acquire(self) -> "_Pool":
        return self

    async def __aenter__(self) -> _Conn:
        return self._conn

    async def __aexit__(self, *_: object) -> None:
        return None


def _go(conn: _Conn, *, dry_run: bool = False) -> dict[str, Any]:
    service = RosterService(_Pool(conn))
    return asyncio.run(
        service.remove(
            roster_id="ca000000-0000-4000-8000-000000000001",
            identity=_identity(),
            dry_run=dry_run,
        )
    )


class TestHuyTheoKhungGio:
    def test_xoa_sang_con_chieu_thi_chi_lich_sang_bi_huy(self) -> None:
        """Chiều bác sĩ vẫn ngồi bàn khám — lịch 15:00 phải ở yên."""
        conn = _Conn(con_lai=[_ca_con_lai("CHIEU")])
        ket = _go(conn)
        assert ket["so_lich_huy"] == 1 and ket["gio"] == ["08:00"]
        assert conn.ids_huy == ["sang8h"]
        assert conn.so_event == 1

    def test_them_ca_ngay_truoc_roi_xoa_sang_thi_khong_huy_gi(self) -> None:
        """Đường đổi ca an toàn: THÊM cả-ngày trước, xoá sáng sau — mọi giờ
        vẫn được phủ, không lịch nào chết oan."""
        conn = _Conn(con_lai=[_ca_con_lai("FULL")])
        ket = _go(conn)
        assert ket["so_lich_huy"] == 0
        assert conn.ids_huy is None and conn.so_event == 0

    def test_het_ca_thi_huy_ca_ngay_nhu_cu(self) -> None:
        conn = _Conn(con_lai=[])
        ket = _go(conn)
        assert ket["so_lich_huy"] == 2
        assert conn.ids_huy == ["sang8h", "chieu15h"]

    def test_dry_run_do_ma_khong_cat(self) -> None:
        """Hộp xác nhận cần con số TRƯỚC khi xoá — và đo thì không được để
        lại vết gì: không xoá ca, không huỷ lịch, không event."""
        conn = _Conn(con_lai=[_ca_con_lai("CHIEU")])
        ket = _go(conn, dry_run=True)
        assert ket == {"so_lich_huy": 1, "gio": ["08:00"]}
        assert conn.da_xoa_ca is False
        assert conn.ids_huy is None and conn.so_event == 0
