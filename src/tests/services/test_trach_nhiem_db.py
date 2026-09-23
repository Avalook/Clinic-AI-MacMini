"""Trách nhiệm không được rơi — khách trả tiền mà không được làm dịch vụ.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55474/postgres \
        poetry run pytest src/tests/services/test_trach_nhiem_db.py

Đây cũng là bài chứng minh LEGO: module Thực hiện KHÔNG biết module Trách nhiệm
tồn tại. Nó chỉ phát sự kiện; việc mở ra là do bên nghe.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.events.catalogue import (
    TRACH_NHIEM_DICH_VU,
    DichVuGianDoan,
    DichVuKhongLam,
)
from clinicai.events.emit import HE_THONG, emit_event
from clinicai.events.worker import lam_mot_dong

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


async def _visit(conn: asyncpg.Connection) -> str:
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN test trách nhiệm', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"TN-{uuid.uuid4().hex[:10]}",
        loc,
    )
    return str(
        await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', now())"
            " RETURNING visit_id::text",
            CLINIC,
            pid,
        )
    )


async def _lam_het(pool: asyncpg.Pool, gioi_han: int = 50_000) -> None:
    for _ in range(gioi_han):
        if not await lam_mot_dong(pool, TRACH_NHIEM_DICH_VU):
            return


async def _viec(pool: asyncpg.Pool, order_id: str) -> list[asyncpg.Record]:
    return list(
        await pool.fetch(
            "SELECT node_code, status, payload FROM work_item"
            " WHERE service_order_id = $1::uuid",
            order_id,
        )
    )


async def test_da_thu_tien_ma_khong_lam_thi_mo_viec_doi_soat(
    pool: asyncpg.Pool,
) -> None:
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        vid = await _visit(conn)
        async with conn.transaction():
            await emit_event(
                conn,
                ten="service.not_performed",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=DichVuKhongLam(
                    visit_id=vid,
                    service_order_id=order_id,
                    ly_do="EQUIPMENT_UNAVAILABLE_BEFORE_START",
                    execution_revision=1,
                    da_thu_tien=True,
                ),
                boi=HE_THONG,
            )

    await _lam_het(pool)
    viec = await _viec(pool, order_id)
    assert [v["node_code"] for v in viec] == ["OPS-FINANCIAL-RESOLUTION"]
    assert viec[0]["status"] == "PENDING"
    assert json.loads(viec[0]["payload"])["vi"] == "service.not_performed"


async def test_chua_thu_tien_thi_khong_mo_viec(pool: asyncpg.Pool) -> None:
    """Mở việc cho mọi trường hợp là cách nhanh nhất để người trực học cách lờ đi."""
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        vid = await _visit(conn)
        async with conn.transaction():
            await emit_event(
                conn,
                ten="service.not_performed",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=DichVuKhongLam(
                    visit_id=vid,
                    service_order_id=order_id,
                    ly_do="PATIENT_DECLINED_AT_ROOM",
                    execution_revision=1,
                    da_thu_tien=False,
                ),
                boi=HE_THONG,
            )
    await _lam_het(pool)
    assert await _viec(pool, order_id) == []


async def test_dung_giua_chung_thi_mo_viec_quyet_lam_lai(pool: asyncpg.Pool) -> None:
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        vid = await _visit(conn)
        async with conn.transaction():
            await emit_event(
                conn,
                ten="service.interrupted",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=DichVuGianDoan(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=str(uuid.uuid4()),
                    attempt_no=1,
                    ly_do="EQUIPMENT_FAILURE",
                    execution_revision=1,
                ),
                boi=HE_THONG,
            )
    await _lam_het(pool)
    viec = await _viec(pool, order_id)
    assert [v["node_code"] for v in viec] == ["OPS-SERVICE-INTERRUPTED"]


async def test_giao_lai_su_kien_khong_mo_hai_viec(pool: asyncpg.Pool) -> None:
    """Giao tin là 'ít nhất một lần' — hai lần tới không được thành hai việc."""
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        vid = await _visit(conn)
        async with conn.transaction():
            event_id = await emit_event(
                conn,
                ten="service.interrupted",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=DichVuGianDoan(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=str(uuid.uuid4()),
                    attempt_no=1,
                    ly_do="TECHNICAL_FAILURE",
                    execution_revision=1,
                ),
                boi=HE_THONG,
            )
    await _lam_het(pool)
    # Giả lập giao lại.
    await pool.execute(
        "UPDATE event_delivery SET status = 'PENDING', processed_at = NULL"
        " WHERE event_id = $1::uuid AND consumer = $2",
        event_id,
        TRACH_NHIEM_DICH_VU,
    )
    await _lam_het(pool)
    assert len(await _viec(pool, order_id)) == 1


async def test_phat_lai_lich_su_khong_mo_lai_viec_cu(pool: asyncpg.Pool) -> None:
    """Chạy lại sổ sự kiện không được dựng lại việc mà người ta đã xử lý xong."""
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        vid = await _visit(conn)
        async with conn.transaction():
            await emit_event(
                conn,
                ten="service.interrupted",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=DichVuGianDoan(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=str(uuid.uuid4()),
                    attempt_no=1,
                    ly_do="PATIENT_REQUEST",
                    execution_revision=1,
                ),
                boi=HE_THONG,
                replay_id=str(uuid.uuid4()),
            )
    await _lam_het(pool)
    assert await _viec(pool, order_id) == []


async def test_viec_hien_len_bang_viec_cua_khu_van_hanh(pool: asyncpg.Pool) -> None:
    """Mở việc mà không ai nhìn thấy thì vẫn là rơi.

    Bảng việc đã có sẵn (`list_worklist` theo khu làm việc). Bài này canh đúng
    chỗ nối: việc mới mở phải hiện ở khu vận hành, kèm mã chỉ định để người xử lý
    biết nó về chuyện gì.
    """
    from clinicai.api.identity import ClinicRole, StaffIdentity
    from clinicai.services.work_item_service import WorkItemService

    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        vid = await _visit(conn)
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        sid = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id,"
            " is_active) VALUES ('Quản lý test việc', 'MANAGEMENT', $1::uuid, true)"
            " RETURNING id::text",
            loc,
        )
        await conn.execute(
            "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
            " VALUES ($1::uuid, $2::uuid, 'MANAGEMENT', true)"
            " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
            CLINIC,
            sid,
        )
        async with conn.transaction():
            await emit_event(
                conn,
                ten="service.not_performed",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=DichVuKhongLam(
                    visit_id=vid,
                    service_order_id=order_id,
                    ly_do="STAFF_UNAVAILABLE",
                    execution_revision=1,
                    da_thu_tien=True,
                ),
                boi=HE_THONG,
            )
    await _lam_het(pool)

    quan_ly = StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name="Quản lý test việc",
        department="MANAGEMENT",
        role=ClinicRole.MANAGEMENT,
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )
    bang = await WorkItemService(pool).list_worklist(
        workspace="khu_van_hanh", identity=quan_ly
    )
    cua_ta = [v for v in bang if v.get("node_code") == "OPS-FINANCIAL-RESOLUTION"]
    assert cua_ta, "Việc đối soát tiền không hiện ở bảng việc khu vận hành"
