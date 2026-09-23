"""Màn ĐỌC lịch hẹn đi qua backend (24/09/2026) — trước là Next.js đọc thẳng DB."""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.core.clock import now_vn
from clinicai.services import lich_hen_doc
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_doc_lich_theo_ngay_sap_toi_va_lich_su(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    await _check_in(pool, ca, pid, ca.loai_kham)

    hom_nay = now_vn().date().isoformat()
    ngay = await lich_hen_doc.lich_trong_ngay(
        pool, identity=ca.le_tan, ngay=hom_nay, doctor_id=ca.bac_si.staff_id
    )
    assert ngay and all(d["doctor_id"] == ca.bac_si.staff_id for d in ngay)

    sap = await lich_hen_doc.lich_sap_toi(
        pool, identity=ca.le_tan, clinic_patient_id=pid
    )
    assert len(sap) == 1

    su = await lich_hen_doc.lich_su_dich_vu(
        pool, identity=ca.le_tan, clinic_patient_id=pid, service_type_id=ca.loai_kham
    )
    assert su["serviceVisitCount"] == 1


@pytest.mark.parametrize("rac", ["", "99-99-9999", "2026-02-30", "hôm nay", None])
async def test_ngay_rac_tra_rong_khong_nem(pool: asyncpg.Pool, rac: str | None) -> None:  # noqa: F811
    ca = await _dung(pool)
    assert await lich_hen_doc.lich_trong_ngay(pool, identity=ca.le_tan, ngay=rac) == []
