"""Quyền khởi động + bất biến "luôn còn người cấp quyền" (CORE-B, 23/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_quyen_khoi_dong_db.py

Audit 23/09 gọi `can()` thật trên stack local: 12/12 tài khoản thử có 0 quyền,
quản lý không có `permission.manage` → không ai cấp quyền được cho ai.

Mỗi bài dựng MỘT PHÒNG KHÁM RIÊNG: đếm "còn bao nhiêu người cấp quyền" trên phòng
khám dùng chung thì nhân sự của bài khác làm lệch kết quả.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any
from uuid import UUID

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.permissions import cache
from clinicai.permissions.can import can
from clinicai.services.permission_service import PermissionService, cap_preset_mac_dinh
from clinicai.services.staff_service import StaffService

CLINIC_MAU = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=6)
    yield p
    await p.close()


@pytest_asyncio.fixture
async def pk(pool: asyncpg.Pool) -> str:
    """Phòng khám mới tinh, chép nhóm quyền mẫu của phòng khám mẫu."""
    async with pool.acquire() as conn:
        cid = await conn.fetchval(
            "INSERT INTO clinic (code, name, timezone) VALUES ($1, 'PK quyền (test)',"
            " 'Asia/Ho_Chi_Minh') RETURNING id::text",
            f"Q{uuid.uuid4().hex[:8]}",
        )
        await conn.execute(
            "INSERT INTO quyen_preset (clinic_id, ma, ten, khoi, he_thong, mo_ta)"
            " SELECT $1::uuid, ma, ten, khoi, he_thong, mo_ta FROM quyen_preset"
            "  WHERE clinic_id = $2::uuid",
            cid,
            CLINIC_MAU,
        )
    return str(cid)


async def _nguoi(
    conn: asyncpg.Connection, clinic_id: str, role: str, *, cap: bool = True
) -> StaffIdentity:
    ten = f"Test {role} {uuid.uuid4().hex[:6]}"
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC_MAU,
    )
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
        clinic_id,
        sid,
        role,
    )
    if cap:
        await cap_preset_mac_dinh(conn, clinic_id=clinic_id, staff_id=sid, vai=role)
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=role,
        role=ClinicRole(role),
        clinic_id=clinic_id,
        location_id=None,
        location_name="",
    )


async def _co(pool: asyncpg.Pool, ai: StaffIdentity, quyen: str) -> bool:
    cache.quen(ai.clinic_id, ai.staff_id)
    async with pool.acquire() as conn:
        return await can(conn, ai, quyen)


# ── Cấp theo preset ────────────────────────────────────────────────────────


async def test_thanh_vien_chua_co_quyen_duoc_cap_bu(
    pool: asyncpg.Pool, pk: str
) -> None:
    """Đúng lỗi audit 23/09: người được chèn thẳng vào membership có 0 quyền."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, pk, "DOCTOR", cap=False)
    assert not await _co(pool, bs, "clinical.order.place")

    async with pool.acquire() as conn:
        await conn.fetchval("SELECT public.cap_quyen_cho_moi_thanh_vien()")
    assert await _co(pool, bs, "clinical.order.place")


async def test_cap_lai_khong_bat_lai_quyen_quan_ly_da_thu(
    pool: asyncpg.Pool, pk: str
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, pk, "MANAGEMENT")
        dd = await _nguoi(conn, pk, "NURSE_ULTRASOUND")
    assert await _co(pool, dd, "vitals.measure")

    await PermissionService(pool).thu_khoi(
        staff_id=dd.staff_id, khoi="sinh_hieu", identity=ql
    )
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT public.cap_quyen_cho_moi_thanh_vien()")
        await cap_preset_mac_dinh(
            conn, clinic_id=pk, staff_id=dd.staff_id, vai="NURSE_ULTRASOUND"
        )
    assert not await _co(pool, dd, "vitals.measure")


# ── Bất biến: luôn còn người cấp quyền ─────────────────────────────────────


async def test_khong_tu_thu_duoc_quyen_cap_quyen_cua_nguoi_cuoi(
    pool: asyncpg.Pool, pk: str
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, pk, "MANAGEMENT")

    with pytest.raises(ConflictError):
        await PermissionService(pool).thu_khoi(
            staff_id=ql.staff_id, khoi="quan_tri_quyen", identity=ql
        )
    assert await _co(pool, ql, "permission.manage")


async def test_con_nguoi_khac_thi_thu_duoc(pool: asyncpg.Pool, pk: str) -> None:
    async with pool.acquire() as conn:
        a = await _nguoi(conn, pk, "MANAGEMENT")
        b = await _nguoi(conn, pk, "MANAGEMENT")

    await PermissionService(pool).thu_khoi(
        staff_id=b.staff_id, khoi="quan_tri_quyen", identity=a
    )
    assert not await _co(pool, b, "permission.manage")
    # A giờ là người cuối cùng.
    with pytest.raises(ConflictError):
        await PermissionService(pool).thu_khoi(
            staff_id=a.staff_id, khoi="quan_tri_quyen", identity=a
        )


async def test_cho_nguoi_cuoi_nghi_viec_bi_chan(pool: asyncpg.Pool, pk: str) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, pk, "MANAGEMENT")

    with pytest.raises(ConflictError):
        await StaffService(pool, pk).deactivate(UUID(ql.staff_id))
    assert await pool.fetchval(
        "SELECT is_active FROM clinic_membership WHERE clinic_id = $1::uuid"
        " AND staff_id = $2::uuid",
        pk,
        ql.staff_id,
    )


async def test_postgres_chan_ca_khi_di_vong_qua_service(
    pool: asyncpg.Pool, pk: str
) -> None:
    """Luật nằm ở database: ghi thẳng SQL cũng không lọt."""
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, pk, "MANAGEMENT")

    for cau in (
        "UPDATE capability_grant SET revoked_at = now(), revoked_by = staff_id"
        " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
        "   AND capability = 'permission.manage'",
        "UPDATE clinic_membership SET is_active = false"
        " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid",
        "UPDATE staff SET is_active = false"
        " WHERE id = $2::uuid AND $1::uuid IS NOT NULL",
    ):
        async with pool.acquire() as conn:
            with pytest.raises(asyncpg.CheckViolationError):
                async with conn.transaction():
                    await conn.execute(cau, pk, ql.staff_id)
    assert await _co(pool, ql, "permission.manage")


async def test_hai_nguoi_thu_cung_luc_thi_mot_nguoi_that_bai(
    pool: asyncpg.Pool, pk: str
) -> None:
    """Hai quản lý, hai giao dịch song song, mỗi bên thu quyền một người.

    Kiểm ở Python thì cả hai cùng thấy "còn người kia" và cùng commit → 0 người.
    Trigger khoá dòng phòng khám lúc COMMIT nên bên sau đếm lại và bị chặn.
    """
    async with pool.acquire() as conn:
        a = await _nguoi(conn, pk, "MANAGEMENT")
        b = await _nguoi(conn, pk, "MANAGEMENT")

    c1 = await pool.acquire()
    c2 = await pool.acquire()
    try:
        t1 = c1.transaction()
        t2 = c2.transaction()
        await t1.start()
        await t2.start()
        for c, ai in ((c1, a), (c2, b)):
            await c.execute(
                "UPDATE capability_grant SET revoked_at = now(), revoked_by = staff_id"
                " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
                "   AND capability = 'permission.manage'",
                pk,
                ai.staff_id,
            )
        ket_qua = await asyncio.gather(t1.commit(), t2.commit(), return_exceptions=True)
        loi = [k for k in ket_qua if isinstance(k, BaseException)]
        assert len(loi) == 1 and isinstance(loi[0], asyncpg.CheckViolationError)
    finally:
        await pool.release(c1)
        await pool.release(c2)

    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT public.con_nguoi_cap_quyen($1::uuid)", pk)


async def test_phong_kham_chua_co_ai_van_sua_viec_khac_duoc(
    pool: asyncpg.Pool, pk: str
) -> None:
    """Không bắn nhầm: chỉ chặn khi thay đổi thật sự BỚT một người cấp quyền."""
    async with pool.acquire() as conn:
        lt = await _nguoi(conn, pk, "RECEPTION")
        async with conn.transaction():
            await conn.execute(
                "UPDATE clinic_membership SET is_active = false"
                " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid",
                pk,
                lt.staff_id,
            )


async def test_quyen_cap_quyen_khong_duoc_co_han(pool: asyncpg.Pool, pk: str) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, pk, "MANAGEMENT")
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "UPDATE capability_grant SET valid_until = now() + interval '1 day'"
                " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
                "   AND capability = 'permission.manage'",
                pk,
                ql.staff_id,
            )
