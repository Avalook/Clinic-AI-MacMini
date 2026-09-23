"""Điền xong phiếu kết quả thì dịch vụ đóng theo — hoặc nói rõ vì sao chưa.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55476/postgres \
        poetry run pytest src/tests/services/test_phieu_dong_dich_vu_db.py

Người làm siêu âm điền xong phiếu rồi đứng dậy gọi khách tiếp theo. Nếu hệ thống
bắt họ nhớ bấm thêm nút "Xong" thì sẽ có ngày không ai bấm, và khách còn tên
trong hàng chờ sau khi đã khám xong.

Nhưng đóng hộ phải đi bằng LỆNH của module Thực hiện — nó tự kiểm quyền, tự khoá
lượt, tự phát sự kiện. Và khi không đóng được thì phải NÓI RA.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.permission_service import PermissionService, cap_preset_mac_dinh
from clinicai.services.service_execution_service import ServiceExecutionService

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=6)
    yield p
    await p.close()


async def _nguoi(conn: asyncpg.Connection, role: str) -> StaffIdentity:
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        f"Test {role} {uuid.uuid4().hex[:6]}",
        role,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        CLINIC,
        sid,
        role,
    )
    await cap_preset_mac_dinh(conn, clinic_id=CLINIC, staff_id=sid, vai=role)
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name="Test",
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


@dataclass
class KB:
    pool: asyncpg.Pool
    visit_id: str
    order_id: str
    bs: StaffIdentity


async def _dung_chi_dinh_dang_lam(pool: asyncpg.Pool, bs: StaffIdentity) -> KB:
    """Một chỉ định đã trả tiền, đã xếp phòng, và ĐANG được làm."""
    async with pool.acquire() as conn:
        loc = bs.location_id
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN test phiếu', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"PH-{uuid.uuid4().hex[:10]}",
            loc,
        )
        vid = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
            " attending_doctor_id, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', $3::uuid, now())"
            " RETURNING visit_id::text",
            CLINIC,
            pid,
            bs.staff_id,
        )
        con_id = await conn.fetchval(
            "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
            " doctor_staff_id, started_by, started_at)"
            " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'in_progress', $3::uuid,"
            " $3::uuid, now()) RETURNING id::text",
            CLINIC,
            vid,
            bs.staff_id,
        )
        room = await conn.fetchval(
            "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid"
            " ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        ma_dv = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND active ORDER BY service_code LIMIT 1",
            CLINIC,
        )
        order_id = await conn.fetchval(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by,"
            " authorized_by, authorized_at, selection_status, routing_status,"
            " room_id, routing_revision, execution_status)"
            " VALUES ($1::uuid, $2::uuid, $5::uuid, $3, 'Dịch vụ test',"
            " 'DICHVU-SIEUAM', 'assigned', $4::uuid, $4::uuid, now(), 'SELECTED',"
            " 'ASSIGNED', $6::uuid, 1, 'PENDING') RETURNING id::text",
            CLINIC,
            vid,
            ma_dv,
            bs.staff_id,
            con_id,
            room,
        )
        await conn.execute(
            "INSERT INTO queue_entry (clinic_id, visit_id, lane, room_id, reason,"
            " ref_id, status, eligible_at) VALUES ($1::uuid, $2::uuid, 'ROOM',"
            " $3::uuid, 'SERVICE', $4::uuid, 'waiting', now())",
            CLINIC,
            vid,
            room,
            order_id,
        )
        cycle = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
            " amount, bill_revision, method, status, legacy, created_by, paid_at,"
            " confirmed_by) VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 300000,"
            " 'rev-test', 'CASH', 'PAID', false, $4::uuid, now(), $4::uuid)",
            cycle,
            CLINIC,
            vid,
            bs.staff_id,
        )
        await conn.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'dich_vu', 'service_order', $4::uuid, 'Dịch vụ test', 1, 300000,"
            " 300000, 'CLINIC')",
            CLINIC,
            cycle,
            vid,
            order_id,
        )

    await ServiceExecutionService(pool).bat_dau(
        order_id=order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=bs,
        idempotency_key=str(uuid.uuid4()),
    )
    return KB(pool, vid, order_id, bs)


async def test_hoan_tat_phieu_thi_dong_luon_dich_vu(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    kb = await _dung_chi_dinh_dang_lam(pool, bs)

    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=kb.order_id, form_id="KQ_SA_VU", identity=bs
    )
    kq = await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    assert kq["dich_vu"]["da_dong"] is True

    trang_thai = await pool.fetchval(
        "SELECT execution_status FROM service_order WHERE id = $1::uuid", kb.order_id
    )
    assert trang_thai == "COMPLETED"
    # Đi bằng LỆNH nên sự kiện của module Thực hiện vẫn được phát.
    so = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE aggregate_id = $1::uuid"
        "   AND event_type = 'service.completed'",
        kb.order_id,
    )
    assert so == 1
    # Hàng chờ của phòng cũng đóng theo.
    assert (
        await pool.fetchval(
            "SELECT status FROM queue_entry WHERE ref_id = $1::uuid", kb.order_id
        )
        == "done"
    )


async def test_khong_du_quyen_dong_thi_phieu_van_xong_va_noi_ro(
    pool: asyncpg.Pool,
) -> None:
    """Điều dưỡng nhập hộ: phiếu xong, dịch vụ chưa đóng, và màn phải biết."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
        quan_ly = await _nguoi(conn, "MANAGEMENT")
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " SELECT $1::uuid, $2::uuid, ma, work_pack FROM capability"
            " WHERE work_pack = 'quan_tri_quyen' ON CONFLICT DO NOTHING",
            CLINIC,
            quan_ly.staff_id,
        )
    kb = await _dung_chi_dinh_dang_lam(pool, bs)

    # Thu đúng khối "Thực hiện dịch vụ" của điều dưỡng — vẫn còn khối Kết quả.
    await PermissionService(pool).thu_khoi(
        staff_id=dd.staff_id, khoi="thuc_hien", identity=quan_ly
    )

    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=kb.order_id, form_id="KQ_SA_VU", identity=dd
    )
    kq = await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=dd
    )

    assert kq["da_hoan_tat"] is True
    assert kq["dich_vu"]["da_dong"] is False
    assert kq["dich_vu"]["vi_sao"] == "khong_du_quyen"
    # Dịch vụ vẫn đang làm — không ai âm thầm đóng hộ.
    assert (
        await pool.fetchval(
            "SELECT execution_status FROM service_order WHERE id = $1::uuid",
            kb.order_id,
        )
        == "IN_PROGRESS"
    )


async def test_dich_vu_khong_dang_lam_thi_khong_dong_gi(pool: asyncpg.Pool) -> None:
    """Điền phiếu cho dịch vụ chưa bắt đầu: không tự bắt đầu, không tự đóng."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    kb = await _dung_chi_dinh_dang_lam(pool, bs)
    # Đóng trước bằng lệnh thật, rồi mới điền phiếu.
    lan = await pool.fetchval(
        "SELECT id::text FROM service_execution_attempt"
        " WHERE service_order_id = $1::uuid AND status = 'IN_PROGRESS'",
        kb.order_id,
    )
    rev = await pool.fetchval(
        "SELECT execution_revision FROM service_order WHERE id = $1::uuid", kb.order_id
    )
    await ServiceExecutionService(pool).xong(
        order_id=kb.order_id,
        attempt_id=lan,
        expected_execution_revision=int(rev),
        identity=bs,
        idempotency_key=str(uuid.uuid4()),
    )

    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=kb.order_id, form_id="KQ_SA_VU", identity=bs
    )
    kq = await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    assert kq["dich_vu"] == {"da_dong": False, "vi_sao": "khong_dang_lam"}
