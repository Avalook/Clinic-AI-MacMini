"""Hồ sơ lâm sàng đọc ở backend (24/09/2026) — trang bệnh án thôi đọc thẳng DB."""

from __future__ import annotations

import dataclasses

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.ho_so_lam_sang_doc import doc_ho_so, phieu_in_theo_lich
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_doc_ho_so_theo_luot_va_so_do_moi_nhat(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    await pool.execute(
        "INSERT INTO vital_measurement (clinic_id, visit_id, systolic, diastolic,"
        " recorded_by)"
        " SELECT clinic_id, visit_id, 118, 76, $2::uuid"
        " FROM visit WHERE visit_id = $1::uuid",
        visit,
        ca.dd.staff_id,
    )
    hs = await doc_ho_so(pool, identity=ca.bac_si, patient_id=pid, visit_id=visit)
    assert hs["visit"]["visit_id"] == visit
    assert hs["vital_latest"]["systolic"] == 118
    assert [h["visit_id"] for h in hs["history_raw"]] == [visit]
    assert hs["prescriptions"] == []


async def test_ma_rac_bao_loi_ro_rang(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    with pytest.raises(ValidationError):
        await doc_ho_so(pool, identity=ca.bac_si, patient_id="không-phải-mã")


async def _lich_cua_luot(pool: asyncpg.Pool, visit: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT appointment_id::text FROM visit WHERE visit_id = $1::uuid", visit
        )
    )


async def test_lich_cua_khach_khac_khong_lo_luot(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Mở khách A kèm mã lịch của B (cùng phòng khám) không được ra lượt của B."""
    ca = await _dung(pool)
    khach_a = await _benh_nhan(pool, ca)
    khach_b = await _benh_nhan(pool, ca)
    luot_b = await _check_in(pool, ca, khach_b, ca.loai_kham)
    lich_b = await _lich_cua_luot(pool, luot_b)

    hs = await doc_ho_so(
        pool, identity=ca.bac_si, patient_id=khach_a, appointment_id=lich_b
    )
    assert hs["visit"] is None

    dung_chu = await doc_ho_so(
        pool, identity=ca.bac_si, patient_id=khach_b, appointment_id=lich_b
    )
    assert dung_chu["visit"]["visit_id"] == luot_b


async def test_thu_ky_khong_in_phieu_khach_bac_si_khac(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    khach = await _benh_nhan(pool, ca)
    lich = await _lich_cua_luot(pool, await _check_in(pool, ca, khach, ca.loai_kham))
    thu_ky = dataclasses.replace(ca.le_tan, role=ClinicRole.TKYK)
    # Thư ký đi cùng một người KHÁC bác sĩ của lịch này.
    await pool.execute(
        "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid)",
        thu_ky.clinic_id,
        thu_ky.staff_id,
        ca.thu_ngan.staff_id,
    )
    with pytest.raises(SafetyGateError):
        await phieu_in_theo_lich(pool, identity=thu_ky, appointment_id=lich)

    phieu = await phieu_in_theo_lich(pool, identity=ca.bac_si, appointment_id=lich)
    assert phieu is not None
    assert phieu["appointment"]["clinic_patient_id"] == khach
