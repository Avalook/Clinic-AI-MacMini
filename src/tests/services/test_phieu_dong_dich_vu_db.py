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
from clinicai.core.exceptions import ValidationError
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.hoan_tat_dong_dich_vu import CAU_THIEU_QUYEN
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


async def _dung_chi_dinh_dang_lam(
    pool: asyncpg.Pool,
    bs: StaffIdentity,
    *,
    bat_dau: bool = True,
    da_thu: bool = True,
    xep_phong: bool = True,
) -> KB:
    """Một chỉ định đã trả tiền, đã xếp phòng, và ĐANG được làm (mặc định).

    ``xep_phong=False``: chỉ định chưa xếp phòng, khách ngồi ở bàn khám có phòng
    (chỗ chờ hàng BÁC SĨ) — đường "làm tại bàn khám".
    """
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
            " 'DICHVU-SIEUAM', $7, $4::uuid, $4::uuid, now(), 'SELECTED',"
            " $8, $6::uuid, $9, 'PENDING') RETURNING id::text",
            CLINIC,
            vid,
            ma_dv,
            bs.staff_id,
            con_id,
            room if xep_phong else None,
            "assigned" if xep_phong else "authorized",
            "ASSIGNED" if xep_phong else "UNASSIGNED",
            1 if xep_phong else 0,
        )
        if xep_phong:
            await conn.execute(
                "INSERT INTO queue_entry (clinic_id, visit_id, lane, room_id, reason,"
                " ref_id, status, eligible_at) VALUES ($1::uuid, $2::uuid, 'ROOM',"
                " $3::uuid, 'SERVICE', $4::uuid, 'waiting', now())",
                CLINIC,
                vid,
                room,
                order_id,
            )
        else:
            await conn.execute(
                "INSERT INTO queue_entry (clinic_id, visit_id, lane, room_id, reason,"
                " ref_id, status, eligible_at, doctor_staff_id)"
                " VALUES ($1::uuid, $2::uuid, 'DOCTOR', $3::uuid, 'PRIMARY',"
                " $4::uuid, 'serving', now(), $5::uuid)",
                CLINIC,
                vid,
                room,
                con_id,
                bs.staff_id,
            )
        if not da_thu:
            return KB(pool, vid, order_id, bs)
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

    if not bat_dau:
        return KB(pool, vid, order_id, bs)
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


async def test_khong_du_quyen_dong_thi_khong_chot_phieu(pool: asyncpg.Pool) -> None:
    """Điều dưỡng nhập hộ mà không có quyền đóng dịch vụ: KHÔNG chốt phiếu (luật
    29/10/2026 — không còn "phiếu đã chốt, dịch vụ chưa xong"). Nháp giữ nguyên,
    bác sĩ bấm Hoàn tất là xong cả hai."""
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
    await PermissionService(pool).thu_khoi(
        staff_id=dd.staff_id, khoi="thuc_hien", identity=quan_ly
    )

    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=kb.order_id, form_id="KQ_SA_VU", identity=dd
    )
    with pytest.raises(ValidationError) as loi:
        await svc.hoan_tat(
            phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=dd
        )
    assert loi.value.message == CAU_THIEU_QUYEN
    assert (
        await pool.fetchval(
            "SELECT trang_thai FROM form_instance WHERE id = $1::uuid", phieu["id"]
        )
        == "DRAFT"
    )
    assert (
        await pool.fetchval(
            "SELECT execution_status FROM service_order WHERE id = $1::uuid",
            kb.order_id,
        )
        == "IN_PROGRESS"
    )

    kq = await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    assert kq["da_hoan_tat"] is True and kq["dich_vu"]["da_dong"] is True


async def test_phieu_cu_da_chot_dich_vu_dang_lam_bam_lai_thi_dong(
    pool: asyncpg.Pool,
) -> None:
    """Dữ liệu cũ (trước 29/10) đã kẹt "phiếu chốt, dịch vụ đang làm": màn phòng
    hiện [Xong] (`phieu_da_chot_cho_dong`), bấm Hoàn tất lại thì đóng."""
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
    # Dựng đúng trạng thái kẹt của dữ liệu cũ (đường mới không còn sinh ra nó).
    await pool.execute(
        "UPDATE form_instance SET trang_thai = 'READY', hoan_tat_luc = now(),"
        " hoan_tat_boi = $2::uuid WHERE id = $1::uuid",
        phieu["id"],
        dd.staff_id,
    )
    xem = await ServiceExecutionService(pool).xem(order_id=kb.order_id, identity=bs)
    assert xem["phieu_da_chot_cho_dong"] is True
    lai = await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    assert lai["da_hoan_tat"] is True and lai["dich_vu"]["da_dong"] is True
    assert (
        await pool.fetchval(
            "SELECT execution_status FROM service_order WHERE id = $1::uuid",
            kb.order_id,
        )
        == "COMPLETED"
    )
    assert (
        await pool.fetchval(
            "SELECT status FROM queue_entry WHERE ref_id = $1::uuid", kb.order_id
        )
        == "done"
    )
    xem = await ServiceExecutionService(pool).xem(order_id=kb.order_id, identity=bs)
    assert xem["phieu_da_chot_cho_dong"] is False


async def _dem_su_kien(pool: asyncpg.Pool, order_id: str, loai: str) -> int:
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE aggregate_id = $1::uuid"
            "   AND event_type = $2",
            order_id,
            loai,
        )
    )


async def test_hoan_tat_khi_chua_bat_dau_thi_bat_dau_va_xong(
    pool: asyncpg.Pool,
) -> None:
    """Ca HPV 28/10: điền phiếu + Hoàn tất khi chưa ai bấm Bắt đầu. Trước đây
    phiếu chốt mà dịch vụ nằm "chờ làm" (rồi kẹt); nay một lần bấm là xong."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    kb = await _dung_chi_dinh_dang_lam(pool, bs, bat_dau=False)

    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=kb.order_id, form_id="KQ_SA_VU", identity=bs
    )
    kq = await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    assert kq["dich_vu"]["da_dong"] is True
    assert (
        await pool.fetchval(
            "SELECT execution_status FROM service_order WHERE id = $1::uuid",
            kb.order_id,
        )
        == "COMPLETED"
    )
    # Bằng LỆNH: đủ cặp sự kiện → dịch vụ thu hộ tự lên bàn đối tác.
    assert await _dem_su_kien(pool, kb.order_id, "service.started") == 1
    assert await _dem_su_kien(pool, kb.order_id, "service.completed") == 1
    assert (
        await pool.fetchval(
            "SELECT status FROM queue_entry WHERE ref_id = $1::uuid", kb.order_id
        )
        == "done"
    )


async def test_chua_thu_tien_thi_khong_chot_phieu(pool: asyncpg.Pool) -> None:
    """Chưa thu (dây thu trước khi làm BẬT, không tick Làm trước – thu sau): phiếu
    giữ nháp, dịch vụ không động tới, câu nói đúng việc cần làm."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    kb = await _dung_chi_dinh_dang_lam(pool, bs, bat_dau=False, da_thu=False)

    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=kb.order_id, form_id="KQ_SA_VU", identity=bs
    )
    with pytest.raises(ValidationError) as loi:
        await svc.hoan_tat(
            phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
        )
    assert "Nội dung phiếu vẫn giữ" in loi.value.message
    assert (
        await pool.fetchval(
            "SELECT trang_thai FROM form_instance WHERE id = $1::uuid", phieu["id"]
        )
        == "DRAFT"
    )
    assert await _dem_su_kien(pool, kb.order_id, "service.started") == 0


async def test_chua_xep_phong_thi_lam_tai_ban_kham(pool: asyncpg.Pool) -> None:
    """Chỉ định chưa xếp phòng, bác sĩ điền ở bàn khám: Hoàn tất = làm tại bàn
    khám (xếp vào phòng bàn khám, lần làm ghi nơi làm BAN_KHAM) rồi xong."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    kb = await _dung_chi_dinh_dang_lam(pool, bs, bat_dau=False, xep_phong=False)

    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=kb.order_id, form_id="KQ_SA_VU", identity=bs
    )
    kq = await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    assert kq["dich_vu"]["da_dong"] is True
    don = await pool.fetchrow(
        "SELECT execution_status, room_id IS NOT NULL AS co_phong"
        "  FROM service_order WHERE id = $1::uuid",
        kb.order_id,
    )
    assert don["execution_status"] == "COMPLETED" and don["co_phong"]
    assert (
        await pool.fetchval(
            "SELECT noi_lam FROM service_execution_attempt"
            " WHERE service_order_id = $1::uuid",
            kb.order_id,
        )
        == "BAN_KHAM"
    )


async def test_dich_vu_khong_dang_lam_thi_khong_dong_gi(pool: asyncpg.Pool) -> None:
    """Điền phiếu cho dịch vụ đã xong: không mở lại, không đóng thêm lần nào."""
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
