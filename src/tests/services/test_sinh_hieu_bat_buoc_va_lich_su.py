"""Sinh hiệu: 100% đo huyết áp, có thai thêm chiều cao + cân nặng, mỗi lần đo một dòng.

Luật PM (CONTEXT v1.0), sửa 15/09/2026. Trước đó hồ sơ khám cũ chỉ bắt buộc ở
giao diện (D26: huyết áp + cân nặng + chiều cao cho MỌI khách) và ghi đè JSON —
đo lại là mất số cũ, không biết ai đo. Nay cả hai đường ghi (hồ sơ khám cũ và
màn luồng khám) dùng CÙNG luật `luot_kham_rules` và cùng bảng `vital_measurement`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole
from clinicai.services.clinical_record_service import sinh_hieu_tu_ho_so
from clinicai.services.luot_kham_rules import Vitals, thieu_sinh_hieu_khi_co_thai
from tests.services.test_clinical_record_revision import (
    PATIENT,
    VISIT,
    identity,
    setup_service,
)


def test_huyet_ap_chuoi_tach_thanh_hai_so() -> None:
    so = sinh_hieu_tu_ho_so(
        {"huyet_ap": " 120 / 80 ", "mach": "72", "nhiet_do": "36,8"}, co_thai=False
    )
    assert (so.systolic, so.diastolic, so.pulse) == (120, 80, 72)
    assert so.temperature == Decimal("36.8")


@pytest.mark.parametrize("vitals", [{}, {"mach": "80"}, {"huyet_ap": "  "}])
def test_thieu_huyet_ap_bi_tu_choi(vitals: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="huyết áp"):
        sinh_hieu_tu_ho_so(vitals, co_thai=False)


@pytest.mark.parametrize("huyet_ap", ["120", "120-80", "abc/80", "80/120", "120/80/60"])
def test_huyet_ap_sai_dang_khong_doan(huyet_ap: str) -> None:
    with pytest.raises(ValidationError):
        sinh_hieu_tu_ho_so({"huyet_ap": huyet_ap}, co_thai=False)


def test_khong_thai_khong_bat_can_nang_chieu_cao() -> None:
    # D26 cũ bắt cân nặng + chiều cao cho MỌI khách; luật PM chỉ bắt khi có thai.
    assert sinh_hieu_tu_ho_so({"huyet_ap": "110/70"}, co_thai=False).weight_kg is None


def test_co_thai_thieu_chieu_cao_can_nang_bi_tu_choi() -> None:
    with pytest.raises(ValidationError, match="chiều cao và cân nặng"):
        sinh_hieu_tu_ho_so({"huyet_ap": "110/70"}, co_thai=True)
    with pytest.raises(ValidationError, match="cân nặng"):
        sinh_hieu_tu_ho_so({"huyet_ap": "110/70", "chieu_cao": "158"}, co_thai=True)
    so = sinh_hieu_tu_ho_so(
        {"huyet_ap": "110/70", "chieu_cao": "158", "can_nang": "55"}, co_thai=True
    )
    assert (so.height_cm, so.weight_kg) == (Decimal(158), Decimal(55))


def test_luat_co_thai_dung_chung_cho_luong_kham() -> None:
    v = Vitals(systolic=110, diastolic=70)
    assert thieu_sinh_hieu_khi_co_thai(v, co_thai=False) is None
    assert "chiều cao" in (thieu_sinh_hieu_khi_co_thai(v, co_thai=True) or "")


def _service(*, co_thai: bool, stored_vitals: dict[str, Any] | None) -> Any:
    service, conn = setup_service(2)
    appointment, stored = list(conn.fetchrow.side_effect)
    conn.fetchrow.side_effect = [
        appointment,
        {**stored, "soap_objective": {"vitals": stored_vitals or {}}},
    ]

    async def fetchval(sql: str, *_: Any) -> Any:
        return co_thai if "pregnancy" in sql else 3

    conn.fetchval.side_effect = fetchval
    return service, conn


def _vital_inserts(conn: Any) -> list[tuple[Any, ...]]:
    return [
        c.args
        for c in conn.execute.await_args_list
        if "INSERT INTO vital_measurement" in c.args[0]
    ]


async def _save(service: Any, **kwargs: Any) -> dict[str, Any]:
    with patch(
        "clinicai.services.clinical_record_service.record_event", new=AsyncMock()
    ):
        out: dict[str, Any] = await service.save(
            appointment_id="40000000-0000-0000-0000-000000000001",
            clinic_patient_id=PATIENT,
            identity=kwargs.pop("identity", identity()),
            **kwargs,
        )
    return out


@pytest.mark.asyncio
async def test_don_kham_khong_huyet_ap_bi_chan_truoc_moi_lenh_ghi() -> None:
    service, conn = _service(co_thai=False, stored_vitals=None)
    with pytest.raises(ValidationError, match="huyết áp"):
        await _save(
            service,
            identity=identity(ClinicRole.NURSE_ULTRASOUND),
            vitals_only=True,
            objective={"vitals": {"mach": "80"}},
        )
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_moi_lan_do_them_mot_dong_lich_su() -> None:
    service, conn = _service(co_thai=False, stored_vitals={"huyet_ap": "120/80"})
    await _save(
        service,
        identity=identity(ClinicRole.NURSE_ULTRASOUND),
        vitals_only=True,
        objective={"vitals": {"huyet_ap": "135/85", "mach": "90"}},
    )
    (args,) = _vital_inserts(conn)
    assert args[2] == VISIT
    assert (args[3], args[4], args[5]) == (135, 85, 90)


@pytest.mark.asyncio
async def test_bac_si_luu_ho_so_khong_doi_sinh_hieu_thi_khong_them_dong() -> None:
    service, conn = _service(co_thai=False, stored_vitals={"huyet_ap": "120/80"})
    await _save(
        service,
        expected_revision=2,
        objective={"vitals": {"huyet_ap": ""}},
        objective_sent=True,
        assessment={"diagnosis": "x"},
    )
    assert _vital_inserts(conn) == []


@pytest.mark.asyncio
async def test_bac_si_bo_sung_sinh_hieu_kiem_bo_sau_gop() -> None:
    # Số cũ có huyết áp; bác sĩ chỉ thêm mạch → bộ sau gộp đủ luật, ghi một dòng.
    service, conn = _service(co_thai=False, stored_vitals={"huyet_ap": "120/80"})
    await _save(
        service,
        expected_revision=2,
        objective={"vitals": {"mach": "76"}},
        objective_sent=True,
    )
    (args,) = _vital_inserts(conn)
    assert (args[3], args[4], args[5]) == (120, 80, 76)


@pytest.mark.asyncio
async def test_khach_co_thai_don_kham_thieu_can_nang_bi_chan() -> None:
    service, conn = _service(co_thai=True, stored_vitals=None)
    with pytest.raises(ValidationError, match="có thai"):
        await _save(
            service,
            identity=identity(ClinicRole.NURSE_ULTRASOUND),
            vitals_only=True,
            objective={"vitals": {"huyet_ap": "110/70", "chieu_cao": "160"}},
        )
    assert _vital_inserts(conn) == []
