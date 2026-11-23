"""Quản lý đọc được nội dung y khoa theo QUYỀN + nhật ký mở hồ sơ (24/09/2026).

Tuyền chốt: "quản lý quyền cao nhất — có module đó thì mọi quyền của nó có cả".
Chạy trên Postgres thật (nhóm mẫu theo migration 20260924000014 → 15), không giả `can`.

Nhật ký mở hồ sơ từ 24/11/2026 ghi vào `nhat_ky_xem_ho_so` cho MỌI vai (trước đó
`event_log` và bỏ qua bác sĩ) — chi tiết ở `test_nhat_ky_xem_ho_so_db.py`.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.v1.routers.clinical_records import doc_ho_so_lam_sang
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.permissions.y_khoa import cua_y_khoa
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)
from tests.xem_thu import xem_that

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _so_lan_mo(pool: asyncpg.Pool, khach: str, staff_id: str) -> int:  # noqa: F811
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM nhat_ky_xem_ho_so"
            " WHERE clinic_patient_id = $1::uuid AND staff_id = $2::uuid",
            khach,
            staff_id,
        )
    )


async def test_quan_ly_mo_duoc_ho_so_va_de_lai_dau_vet(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, ca.loc, "MANAGEMENT")
        # Mọi khối — không còn hàng rào chứng chỉ (migration 20260924000015).
        for q in (
            "clinical.record.write",
            "clinical.consult.perform",
            "clinical.consult.finalize",
            "result.review.approve",
            "permission.manage",
        ):
            assert await can(conn, ql, q), q
    pid = await _benh_nhan(pool, ca)
    await _check_in(pool, ca, pid, ca.loai_kham)

    assert await cua_y_khoa(identity=ql, pool=pool) is ql
    hs = await doc_ho_so_lam_sang(
        patient_id=pid, identity=ql, pool=pool, xem=xem_that(pool, ql)
    )
    assert "draft" in hs
    assert await _so_lan_mo(pool, pid, ql.staff_id) == 1


async def test_le_tan_van_bi_chan_va_bac_si_cung_de_lai_dau_vet(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    await _check_in(pool, ca, pid, ca.loai_kham)
    await ve_goi_mau_cu(pool, ca.le_tan)  # gói lego cũ (mở full lego 30/09)
    with pytest.raises(SafetyGateError):
        await cua_y_khoa(identity=ca.le_tan, pool=pool)
    # NĐ 356/2025: hỏi "ai đã truy cập", kể cả bác sĩ (đổi 24/11/2026).
    await doc_ho_so_lam_sang(
        patient_id=pid, identity=ca.bac_si, pool=pool, xem=xem_that(pool, ca.bac_si)
    )
    assert await _so_lan_mo(pool, pid, ca.bac_si.staff_id) == 1
