"""Hồ sơ lâm sàng đọc ở backend (24/09/2026) — trang bệnh án thôi đọc thẳng DB."""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.ho_so_lam_sang_doc import doc_ho_so
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
