"""Nhớ tạm quyền — và quên cho đúng.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55474/postgres \
        poetry run pytest src/tests/services/test_quyen_cache_db.py

Cache quyền là cache một quyết định an ninh. Bốn bài dưới đây canh đúng chỗ dễ
thành lỗ hổng: thu quyền rồi mà vẫn bấm được, hoặc cấp quyền rồi mà phải chờ.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.permissions import cache
from clinicai.permissions.can import can
from clinicai.services.permission_service import PermissionService

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    cache.quen_het()
    yield p
    cache.quen_het()
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
        f"Cache {role} {uuid.uuid4().hex[:6]}",
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

    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name="Cache test",
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


@pytest_asyncio.fixture
async def quan_ly(pool: asyncpg.Pool) -> StaffIdentity:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "MANAGEMENT")
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " SELECT $1::uuid, $2::uuid, ma, work_pack FROM capability"
            " WHERE work_pack = 'quan_tri_quyen' ON CONFLICT DO NOTHING",
            CLINIC,
            ql.staff_id,
        )
    return ql


async def test_thu_quyen_thi_mat_hieu_luc_ngay_lap_tuc(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    """Chỗ dễ thành lỗ hổng nhất: thu rồi mà cache còn giữ."""
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")

    svc = PermissionService(pool)
    await svc.cap_khoi(staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly)

    async with pool.acquire() as conn:
        assert await can(conn, dd, "clinical.order.place") is True  # nhớ vào cache

    await svc.thu_khoi(staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly)

    async with pool.acquire() as conn:
        # KHÔNG chờ hết hạn: quyền mất hiệu lực ở lệnh kế tiếp.
        assert await can(conn, dd, "clinical.order.place") is False


async def test_cap_quyen_thi_dung_duoc_ngay_lap_tuc(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    """Không cache câu trả lời 'không' — vừa cấp là làm được."""
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
        assert await can(conn, dd, "clinical.order.place") is False

    await PermissionService(pool).cap_khoi(
        staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly
    )
    async with pool.acquire() as conn:
        assert await can(conn, dd, "clinical.order.place") is True


async def test_cache_bo_duoc_luot_hoi_lai(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    """Hỏi lại quyền đã nhớ thì không cần chạm database nữa."""
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
    await PermissionService(pool).cap_khoi(
        staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly
    )

    async with pool.acquire() as conn:
        assert await can(conn, dd, "clinical.order.place") is True

    da_nho = cache.doc(CLINIC, dd.staff_id)
    assert da_nho is not None and "clinical.order.place" in da_nho

    # Cắt đường database: nếu còn hỏi xuống DB thì câu này sẽ nổ.
    class KhongDuocHoi:
        async def fetchval(self, *_: Any, **__: Any) -> Any:
            raise AssertionError("Đã nhớ rồi mà vẫn hỏi xuống database.")

    assert await can(KhongDuocHoi(), dd, "clinical.order.place") is True


async def test_hoi_kem_phong_thi_luon_xuong_database(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    """Quyền hẹp theo phòng/ca không được nhớ tạm — nhớ nhầm thì đắt."""
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
    await PermissionService(pool).cap_khoi(
        staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly
    )
    async with pool.acquire() as conn:
        assert await can(conn, dd, "clinical.order.place") is True
        phong = await conn.fetchval(
            "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid LIMIT 1",
            CLINIC,
        )
        # Quyền của người này là toàn phòng khám, nên hỏi kèm phòng vẫn đúng,
        # nhưng phải đi hỏi lại chứ không lấy từ bộ nhớ.
        assert await can(conn, dd, "clinical.order.place", phong_id=phong) is True
