"""Gói dữ liệu Trang chủ — một vòng thay 6 PostgREST + 3 endpoint (Lát 3).

Bốn thứ phải đúng:

* **Khoá phòng khám** trong mọi câu SQL riêng của service.
* **Khối theo vai do BACKEND quyết** — bảng trạng thái buổi khám chỉ đổ cho
  RECEPTION, ô check-in chỉ đổ cho MANAGEMENT (gương với page.tsx:
  `showCheckin = canCheckin && role !== "RECEPTION"` = MANAGEMENT). Nhận cờ
  từ client là cho phép vai khác tự cấp thêm dữ liệu.
* **Hình lồng như PostgREST** ở bảng trạng thái — VisitStatusBoard đọc
  `patient?.full_name`, `appointment?.status`.
* **Một kết nối** cho các câu riêng (pool trần 10 — xem Lát 2).
"""

from __future__ import annotations

import inspect
import re
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services import man_trang_chu_service as mtc
from clinicai.services.man_trang_chu_service import ManTrangChuService, _luot_kham


class TestKhoaPhongKham:
    def test_moi_cau_sql_rieng_deu_khoa_clinic_id(self) -> None:
        nguon = inspect.getsource(ManTrangChuService.goi_du_lieu)
        cau = re.findall(r'"""\s*(SELECT[\s\S]*?)"""', nguon)
        assert len(cau) == 6, f"phải đúng 6 câu riêng, thấy {len(cau)}"
        for c in cau:
            assert "clinic_id = $1::uuid" in c, f"câu thiếu khoá:\n{c[:90]}"


# ── Chạy thật với pool giả + service con giả ───────────────────────────────


class _Conn:
    def __init__(self) -> None:
        self.cac_cau: list[str] = []

    async def fetchval(self, sql: str, *a: object) -> int:
        self.cac_cau.append(sql)
        return 7

    async def fetch(self, sql: str, *a: object) -> list[dict[str, Any]]:
        self.cac_cau.append(sql)
        if "FROM visit" in sql:
            return [
                {
                    "visit_id": "v1",
                    "status": "OPEN",
                    "checked_in_at": None,
                    "created_at": "x",
                    "finalized_at": None,
                    "ten_khach": "Chị Mai",
                    "patient_code": "BN001",
                    "ten_bac_si": "BS Thành",
                    "ten_dich_vu": "Khám phụ khoa",
                    "trang_thai_lich": "CHECKED_IN",
                }
            ]
        return []


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield self._conn


class _WeekGia:
    def __init__(self, pool: object) -> None:
        pass

    async def week(self, **kw: object) -> list[dict[str, Any]]:
        return [{"id": "a1", "slot_start": "s", "phan_loai": "Tái khám"}]


class _BoardGia:
    goi: list[dict[str, object]] = []

    def __init__(self, pool: object) -> None:
        pass

    async def board(self, **kw: object) -> list[dict[str, Any]]:
        _BoardGia.goi.append(dict(kw))
        return [{"id": "a1"}]


class _ProgressGia:
    def __init__(self, pool: object) -> None:
        pass

    async def for_range(self, **kw: object) -> list[Any]:
        return []


CLINIC = "a0000000-0000-4000-8000-000000000001"


def _ai(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Người trực",
        department="X",
        role=role,
        clinic_id=CLINIC,
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


@pytest.fixture(autouse=True)
def _thay_service_con(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mtc, "WeekAppointmentsService", _WeekGia)
    monkeypatch.setattr(mtc, "DoctorBoardService", _BoardGia)
    monkeypatch.setattr(mtc, "VisitProgressService", _ProgressGia)
    _BoardGia.goi = []


async def _goi(role: ClinicRole) -> tuple[dict[str, Any], _Conn]:
    conn = _Conn()
    ra = await ManTrangChuService(_Pool(conn)).goi_du_lieu(
        identity=_ai(role),
        week_appt=date(2026, 8, 18),
        week_roster=date(2026, 8, 18),
    )
    return ra, conn


@pytest.mark.asyncio
async def test_le_tan_co_bang_trang_thai_vai_khac_khong() -> None:
    ra_lt, conn_lt = await _goi(ClinicRole.RECEPTION)
    assert ra_lt["trang_thai_kham"], "Lễ tân phải có bảng trạng thái"
    assert any("FROM visit" in c for c in conn_lt.cac_cau)

    ra_cskh, conn_cskh = await _goi(ClinicRole.CSKH)
    assert ra_cskh["trang_thai_kham"] == []
    assert not any("FROM visit" in c for c in conn_cskh.cac_cau), (
        "vai khác Lễ tân thì đừng tốn cả câu SQL bảng trạng thái"
    )


@pytest.mark.asyncio
async def test_o_checkin_chi_do_cho_quan_ly() -> None:
    """Gương với page.tsx: showCheckin = canCheckin && !RECEPTION = MANAGEMENT.

    Lễ tân check-in qua cột trong bảng lịch tuần; ô riêng chỉ gây trùng."""
    ra_ql, _ = await _goi(ClinicRole.MANAGEMENT)
    assert ra_ql["checkin"] == [{"id": "a1"}]
    assert len(_BoardGia.goi) == 1

    ra_lt, _ = await _goi(ClinicRole.RECEPTION)
    assert ra_lt["checkin"] == []
    ra_cskh, _ = await _goi(ClinicRole.CSKH)
    assert ra_cskh["checkin"] == []
    assert len(_BoardGia.goi) == 1, "vai khác Quản lý thì đừng gọi cả board"


@pytest.mark.asyncio
async def test_cac_cau_rieng_chay_tren_mot_ket_noi() -> None:
    _, conn = await _goi(ClinicRole.RECEPTION)
    # 3 đếm + roster + trực ca + bảng trạng thái = 6, cùng một _Conn.
    assert len(conn.cac_cau) == 6


@pytest.mark.asyncio
async def test_du_bay_khoi_ke_ca_khi_rong() -> None:
    ra, _ = await _goi(ClinicRole.CSKH)
    assert sorted(ra) == sorted(
        [
            "so_lieu",
            "roster",
            "truc_ca",
            "trang_thai_kham",
            "tuan_hen",
            "checkin",
            "tien_trinh",
        ]
    )
    assert ra["so_lieu"] == {
        "viec_dang_cho": 7,
        "khach_moi_hom_nay": 7,
        "lich_cho_xac_nhan": 7,
    }


class TestHinhDangLuotKham:
    def test_long_patient_doctor_service_appointment_nhu_postgrest(self) -> None:
        """VisitStatusBoard đọc `patient?.full_name`, `appointment?.status` —
        hình đổi là cả bảng của Lễ tân đổi."""

        class _R(dict[str, Any]):  # Record đọc như mapping — dict đủ cho hình
            pass

        d = _luot_kham(
            _R(
                visit_id="v1",
                status="OPEN",
                ten_khach="Chị Mai",
                patient_code="BN001",
                ten_bac_si="BS Thành",
                ten_dich_vu="Khám phụ khoa",
                trang_thai_lich="CHECKED_IN",
            )
        )
        assert d["patient"] == {"full_name": "Chị Mai", "patient_code": "BN001"}
        assert d["doctor"] == {"full_name": "BS Thành"}
        assert d["service"] == {"name": "Khám phụ khoa"}
        assert d["appointment"] == {"status": "CHECKED_IN"}
        assert "ten_khach" not in d, "cột phẳng phải được gỡ sau khi lồng"

    def test_khong_lich_thi_appointment_none(self) -> None:
        d = _luot_kham(dict(visit_id="v1", ten_khach="A", trang_thai_lich=None))
        # page lọc theo appointment?.status — None phải giữ nguyên None,
        # không thành {"status": None} kẻo phép lọc CANCELLED đổi nghĩa.
        assert d["appointment"] is None
