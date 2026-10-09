"""Hoàn tác check-in — "đã làm rồi thì không hoàn tác được nữa" (Tuyền 09/10/2026).

    scripts/test-nhanh.sh src/tests/services/test_hoan_tac_check_in_db.py

Lễ tân bấm nhầm check-in → Hoàn tác được, kể cả khi hệ thống đã tự xếp hàng
(khối Hành trình chạy xong). Khách đã được đo, đã vào phòng, đã nộp tiền →
máy chủ từ chối, câu nói rõ việc gì, lịch + lượt giữ nguyên.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.services.booking_service import BookingService
from clinicai.services.hoan_tac_check_in import doc_viec_da_lam
from clinicai.services.luot_kham_service import LuotKhamService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _dung,
    _kham_va_chi_dinh,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _lich(pool: asyncpg.Pool, visit: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT appointment_id::text FROM visit WHERE visit_id = $1::uuid", visit
        )
    )


async def _vao(pool: asyncpg.Pool) -> tuple[Ca, str, str]:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)  # đã chạy Hành trình
    return ca, visit, await _lich(pool, visit)


async def _hoan_tac(pool: asyncpg.Pool, ca: Ca, appt: str) -> None:  # noqa: F811
    await BookingService(pool).apply_action(
        appointment_id=appt, action="undo_checkin", identity=ca.le_tan
    )


async def _bi_tu_choi(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    appt: str,
    visit: str,
    chu: str,
) -> None:
    with pytest.raises(ConflictError) as loi:
        await _hoan_tac(pool, ca, appt)
    cau = str(loi.value.detail if hasattr(loi.value, "detail") else loi.value)
    assert "Khách đã" in cau and chu in cau, cau
    assert "không hoàn tác check-in được" in cau
    assert (
        await pool.fetchval("SELECT status FROM appointment WHERE id = $1::uuid", appt)
        == "CHECKED_IN"
    )
    assert await pool.fetchval(
        "SELECT status FROM visit WHERE visit_id = $1::uuid", visit
    ) in ("OPEN", "IN_PROGRESS")


async def test_chua_lam_gi_thi_hoan_tac_duoc(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, visit, appt = await _vao(pool)
    # Hệ thống đã tự làm: mở lượt, trạm đầu, hàng chờ, quyết đường đi.
    assert await pool.fetchval(
        "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid", visit
    )
    async with pool.acquire() as conn:
        viec = (await doc_viec_da_lam(conn, CLINIC, [visit]))[visit]
    assert not any(v for k, v in viec.items() if k != "visit_id"), viec

    await _hoan_tac(pool, ca, appt)

    assert (
        await pool.fetchval("SELECT status FROM appointment WHERE id = $1::uuid", appt)
        == "CONFIRMED"
    )
    assert (
        await pool.fetchval("SELECT status FROM visit WHERE visit_id = $1::uuid", visit)
        == "INCOMPLETE"
    )


async def test_da_do_sinh_hieu_thi_tu_choi(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, visit, appt = await _vao(pool)
    svc = LuotKhamService(pool)
    await svc.bat_dau_do_sinh_hieu(visit_id=visit, identity=ca.dd)
    # Mới bấm Bắt đầu đo đã là việc thật.
    await _bi_tu_choi(pool, ca, appt, visit, "bắt đầu đo sinh hiệu")
    await svc.record_vitals(
        visit_id=visit, raw={"systolic": 118, "diastolic": 76}, identity=ca.dd
    )
    await _bi_tu_choi(pool, ca, appt, visit, "được đo sinh hiệu")


async def test_dang_o_phong_bac_si_thi_tu_choi(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, visit, appt = await _vao(pool)
    con = await pool.fetchval(
        "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
        " AND kind = 'PRIMARY'",
        visit,
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    await _bi_tu_choi(pool, ca, appt, visit, "tư vấn/khám")


async def test_da_nop_tien_thi_tu_choi(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Chỉ cờ tiền: đường thu thật đòi có chỉ định trước (cờ khác cũng bật),
    nên ghi thẳng một lần thu đã nhận (dạng `legacy`, hợp lệ ở DB)."""
    ca, visit, appt = await _vao(pool)
    await pool.execute(
        "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
        " amount, status, legacy, paid_at)"
        " VALUES (gen_random_uuid(), $1::uuid, $2::uuid, 'dich_vu', 150000,"
        " 'PAID', true, now())",
        CLINIC,
        visit,
    )
    await _bi_tu_choi(pool, ca, appt, visit, "nộp tiền")


async def test_chi_dinh_roi_thu_tien_thi_tu_choi(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Đường thật: bác sĩ chỉ định → lễ tân chọn → thu tiền dịch vụ."""
    ca, visit, appt = await _vao(pool)
    _, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await _bi_tu_choi(pool, ca, appt, visit, "nộp tiền")
