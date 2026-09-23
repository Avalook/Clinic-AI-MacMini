"""Phát lại sổ sự kiện dựng lại projection (docs/CHUAN-CAM-LEGO.md mục 3).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_phat_lai_projection_db.py

Bằng chứng #3 của thesis ("xoá dashboard dựng lại được không"): dòng thời gian
một lượt khám xoá đi, dựng lại từ `domain_event`, phải ra đúng như cũ.
"""

from __future__ import annotations

import asyncpg
import pytest

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.events import worker as nguoi_dua_tin
from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT
from clinicai.events.consumers.trach_nhiem import TRACH_NHIEM
from clinicai.events.phat_lai import dung_lai
from clinicai.services.booking_service import BookingService
from clinicai.services.luot_kham_service import LuotKhamService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_sinh_hieu_khong_chan_db import _lich_hom_nay

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _chup(pool: asyncpg.Pool, visit_id: str) -> list[tuple[object, ...]]:  # noqa: F811
    rows = await pool.fetch(
        "SELECT event_id::text, event_type, nhan, chi_tiet::text, thu_tu,"
        " occurred_at, actor_type FROM luot_dong_thoi_gian"
        " WHERE visit_id = $1::uuid ORDER BY thu_tu",
        visit_id,
    )
    return [tuple(r) for r in rows]


async def test_xoa_roi_dung_lai_dong_thoi_gian_ra_y_het(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    appt, le_tan, _, loc = await _lich_hom_nay(pool)
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=le_tan
    )
    vid = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, loc, "NURSE_ULTRASOUND")
    svc = LuotKhamService(pool)
    await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=dd)
    await svc.record_vitals(
        visit_id=vid, raw={"systolic": 120, "diastolic": 80}, identity=dd
    )
    while await nguoi_dua_tin.lam_mot_dong(pool, DONG_THOI_GIAN_LUOT):
        pass

    truoc = await _chup(pool, vid)
    assert [r[1] for r in truoc] == [
        "visit.checked_in",
        "vitals.started",
        "vitals.recorded",
    ]

    # Làm hỏng màn: xoá một dòng — rồi dựng lại từ sổ.
    await pool.execute(
        "DELETE FROM luot_dong_thoi_gian WHERE visit_id = $1::uuid"
        " AND event_type = 'vitals.started'",
        vid,
    )
    n = await dung_lai(pool, DONG_THOI_GIAN_LUOT, clinic_id=CLINIC, visit_id=vid)
    assert n == 3
    assert await _chup(pool, vid) == truoc


async def test_node_tac_vu_khong_duoc_phat_lai(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Node trách nhiệm MỞ VIỆC — phát lại là mở lại việc. Phải từ chối."""
    with pytest.raises(ValueError, match="không khai là projection"):
        await dung_lai(pool, TRACH_NHIEM, clinic_id=CLINIC)
