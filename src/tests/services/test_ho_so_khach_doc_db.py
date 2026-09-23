"""Hồ sơ khách đọc ở backend + luật được mở hồ sơ (24/09/2026)."""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.services import ho_so_khach_doc
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_bac_si_chi_mo_khach_co_lich_voi_minh(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    # Chưa có lịch với bác sĩ này → không mở được.
    assert not await ho_so_khach_doc.duoc_mo(pool, ca.bac_si, pid)
    with pytest.raises(SafetyGateError):
        await ho_so_khach_doc.hanh_chinh(pool, identity=ca.bac_si, khach=pid)
    await _check_in(pool, ca, pid, ca.loai_kham)
    assert await ho_so_khach_doc.duoc_mo(pool, ca.bac_si, pid)
    hs = await ho_so_khach_doc.hanh_chinh(pool, identity=ca.bac_si, khach=pid)
    assert hs["patient"]["clinic_patient_id"] == pid
    assert len(hs["appointments"]) == 1
    assert hs["appointments"][0]["doctor"] is not None


async def test_le_tan_mo_duoc_va_doc_lich_su(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    await _check_in(pool, ca, pid, ca.loai_kham)
    assert await ho_so_khach_doc.duoc_mo(pool, ca.le_tan, pid)
    ls = await ho_so_khach_doc.lich_su_lam_sang(pool, identity=ca.bac_si, khach=pid)
    assert len(ls["visits"]) == 1
    assert await ho_so_khach_doc.nhat_ky_cskh(pool, identity=ca.le_tan, khach=pid) == []
