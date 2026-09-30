"""Lệnh `PlaceServiceOrders` trên Postgres thật — lát CD-01.

Năm kịch bản G1–G5 lấy thẳng từ `docs/slices/CD-01-bac-si-chi-dinh-dich-vu.md`,
cộng hai kịch bản về quyền. Chạy:

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55471/postgres \\
        poetry run pytest src/tests/services/test_chi_dinh_db.py
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT
from clinicai.events.worker import lam_mot_dong
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.permission_service import cap_preset_mac_dinh
from tests.goi_mau_cu import ve_goi_mau_cu

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield p
    await p.close()


async def _nguoi(conn: asyncpg.Connection, loc: str, role: str) -> StaffIdentity:
    ten = f"Test {role} {uuid.uuid4().hex[:6]}"
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        ten,
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
    # Người mới vào làm được cấp quyền theo preset của vai — đúng đường mà
    # staff_service đi khi quản lý thêm nhân sự thật.
    await cap_preset_mac_dinh(conn, clinic_id=CLINIC, staff_id=sid, vai=role)
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


class KB:
    """Một lượt khám đang mở, có bác sĩ, thư ký y khoa và một mã siêu âm."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        visit_id: str,
        consultation_id: str,
        bac_si: StaffIdentity,
        thu_ky: StaffIdentity,
        le_tan: StaffIdentity,
        ma_sa: str,
    ) -> None:
        self.pool = pool
        self.svc = ChiDinhService(pool)
        self.visit_id = visit_id
        self.consultation_id = consultation_id
        self.bac_si = bac_si
        self.thu_ky = thu_ky
        self.le_tan = le_tan
        self.ma_sa = ma_sa


@pytest_asyncio.fixture
async def kb(pool: asyncpg.Pool) -> KB:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        bac_si = await _nguoi(conn, loc, "DOCTOR")
        thu_ky = await _nguoi(conn, loc, "TKYK")
        le_tan = await _nguoi(conn, loc, "RECEPTION")
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN test chỉ định', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"CD-{uuid.uuid4().hex[:10]}",
            loc,
        )
        vid = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
            " attending_doctor_id, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', $3::uuid, now())"
            " RETURNING visit_id::text",
            CLINIC,
            pid,
            bac_si.staff_id,
        )
        con = await conn.fetchval(
            "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
            " doctor_staff_id, started_by, started_at)"
            " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'in_progress', $3::uuid,"
            " $3::uuid, now()) RETURNING id::text",
            CLINIC,
            vid,
            bac_si.staff_id,
        )
        ma_sa = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND active AND node_code = 'DICHVU-SIEUAM'"
            " ORDER BY service_code LIMIT 1",
            CLINIC,
        )
        return KB(pool, str(vid), str(con), bac_si, thu_ky, le_tan, ma_sa)


async def _su_kien(kb: KB, order_id: str) -> asyncpg.Record | None:
    return await kb.pool.fetchrow(
        "SELECT * FROM domain_event WHERE aggregate_id = $1::uuid"
        " AND event_type = 'service_order.placed'",
        order_id,
    )


async def test_g1_bac_si_chi_dinh_thi_co_don_va_co_su_kien(kb: KB) -> None:
    ket_qua = await kb.svc.dat_chi_dinh(
        consultation_id=kb.consultation_id,
        service_codes=[kb.ma_sa],
        identity=kb.bac_si,
        idempotency_key=str(uuid.uuid4()),
    )
    assert ket_qua["ok"] is True
    (order_id,) = ket_qua["order_ids"]

    don = await kb.pool.fetchrow(
        "SELECT exec_status, selection_status, routing_status, service_code"
        " FROM service_order WHERE id = $1::uuid",
        order_id,
    )
    assert don is not None
    # Chỉ định là chính thức NGAY, không qua bước duyệt (tin #149).
    assert don["exec_status"] == "authorized"
    assert don["selection_status"] == "PENDING"

    su_kien = await _su_kien(kb, order_id)
    assert su_kien is not None
    assert su_kien["aggregate_version"] == 1
    assert str(su_kien["correlation_id"]) == kb.visit_id
    assert su_kien["actor_type"] == "HUMAN"
    assert str(su_kien["actor_staff_id"]) == kb.bac_si.staff_id

    cho_giao = await kb.pool.fetchval(
        "SELECT count(*) FROM event_delivery WHERE event_id = $1::uuid",
        su_kien["event_id"],
    )
    assert cho_giao == 1


async def test_g2_gui_lai_cung_khoa_thi_khong_nhan_doi(kb: KB) -> None:
    khoa = str(uuid.uuid4())
    lan_1 = await kb.svc.dat_chi_dinh(
        consultation_id=kb.consultation_id,
        service_codes=[kb.ma_sa],
        identity=kb.bac_si,
        idempotency_key=khoa,
    )
    lan_2 = await kb.svc.dat_chi_dinh(
        consultation_id=kb.consultation_id,
        service_codes=[kb.ma_sa],
        identity=kb.bac_si,
        idempotency_key=khoa,
    )
    assert lan_1 == lan_2

    so_don = await kb.pool.fetchval(
        "SELECT count(*) FROM service_order WHERE visit_id = $1::uuid", kb.visit_id
    )
    assert so_don == 1
    so_su_kien = await kb.pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE correlation_id = $1::uuid", kb.visit_id
    )
    assert so_su_kien == 1


async def test_g3_thu_ky_y_khoa_chi_dinh_duoc_khong_can_ai_duyet(kb: KB) -> None:
    ket_qua = await kb.svc.dat_chi_dinh(
        consultation_id=kb.consultation_id,
        service_codes=[kb.ma_sa],
        identity=kb.thu_ky,
        idempotency_key=str(uuid.uuid4()),
    )
    (order_id,) = ket_qua["order_ids"]
    don = await kb.pool.fetchrow(
        "SELECT exec_status, authorized_by::text AS ai FROM service_order"
        " WHERE id = $1::uuid",
        order_id,
    )
    assert don is not None
    assert don["exec_status"] == "authorized"
    assert don["ai"] == kb.thu_ky.staff_id


async def test_g4_luot_da_dong_thi_bi_tu_choi_va_khong_de_lai_gi(kb: KB) -> None:
    await kb.pool.execute(
        "UPDATE consultation SET status = 'completed', completed_at = now(),"
        " completed_by = doctor_staff_id, outcome = 'NO_SERVICES' WHERE id = $1::uuid",
        kb.consultation_id,
    )
    with pytest.raises(Exception):  # noqa: B017 — chỉ cần: bị chặn
        await kb.svc.dat_chi_dinh(
            consultation_id=kb.consultation_id,
            service_codes=[kb.ma_sa],
            identity=kb.bac_si,
            idempotency_key=str(uuid.uuid4()),
        )

    assert (
        await kb.pool.fetchval(
            "SELECT count(*) FROM service_order WHERE visit_id = $1::uuid", kb.visit_id
        )
        == 0
    )
    assert (
        await kb.pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE correlation_id = $1::uuid",
            kb.visit_id,
        )
        == 0
    )


async def test_g5_vai_khong_duoc_chi_dinh_thi_chan(kb: KB) -> None:
    await ve_goi_mau_cu(kb.pool, kb.le_tan)  # gói lego cũ (mở full 30/09)
    with pytest.raises(SafetyGateError):
        await kb.svc.dat_chi_dinh(
            consultation_id=kb.consultation_id,
            service_codes=[kb.ma_sa],
            identity=kb.le_tan,
            idempotency_key=str(uuid.uuid4()),
        )


async def test_chi_dinh_hien_len_dong_thoi_gian(kb: KB) -> None:
    """Đi hết đường: lệnh → sự kiện → người đưa tin → màn hành trình."""
    ket_qua = await kb.svc.dat_chi_dinh(
        consultation_id=kb.consultation_id,
        service_codes=[kb.ma_sa],
        identity=kb.bac_si,
        idempotency_key=str(uuid.uuid4()),
    )
    (order_id,) = ket_qua["order_ids"]

    for _ in range(50_000):
        if not await lam_mot_dong(kb.pool, DONG_THOI_GIAN_LUOT):
            break

    dong = await kb.pool.fetchrow(
        "SELECT nhan, chi_tiet, actor_type FROM luot_dong_thoi_gian"
        " WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    assert dong is not None
    assert dong["nhan"] == "Đã chỉ định dịch vụ"
    assert dong["actor_type"] == "HUMAN"
    assert order_id  # chỉ định thật sự tồn tại


async def test_hai_dich_vu_thi_hai_su_kien_chung_mot_chuoi(kb: KB) -> None:
    ma_2 = await kb.pool.fetchval(
        "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid AND active"
        " AND service_code <> $2 ORDER BY service_code LIMIT 1",
        CLINIC,
        kb.ma_sa,
    )
    ket_qua = await kb.svc.dat_chi_dinh(
        consultation_id=kb.consultation_id,
        service_codes=[kb.ma_sa, ma_2],
        identity=kb.bac_si,
        idempotency_key=str(uuid.uuid4()),
    )
    assert len(ket_qua["order_ids"]) == 2

    su_kien = await kb.pool.fetch(
        "SELECT aggregate_id::text AS aggregate_id, correlation_id::text AS chuoi"
        " FROM domain_event WHERE correlation_id = $1::uuid",
        kb.visit_id,
    )
    assert len(su_kien) == 2
    assert {r["chuoi"] for r in su_kien} == {kb.visit_id}
    assert {r["aggregate_id"] for r in su_kien} == set(ket_qua["order_ids"])
