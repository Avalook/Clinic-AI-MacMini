"""Thu hồi / cấp lại tài khoản (06/10/2026) — qua HTTP thật (router + service +
database), chỉ thay bước JWT.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_tai_khoan_db.py

Kẽ hở được vá: "Gỡ tài khoản" gỡ nối + xoá GoTrue nhưng để nguyên app_credential,
nên nối lại (bằng bất kỳ đường nào) là chuỗi băm cũ mở lại /api/v1/auth/login.
Giờ thu hồi khoá app_credential trong CÙNG giao dịch với gỡ nối; "Tạo tài khoản"
(nối) là đường mở lại. Đăng nhập đọc dấu khoá — bài kiểm ở test_auth_service.py
(database thử không có schema `extensions` để chạy crypt() như prod).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import asyncpg
import httpx
import pytest
import pytest_asyncio

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    _resolve_identity,
    doc_vai_theo_lego,
)
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.permissions import cache
from clinicai.permissions.catalogue import quyen_cua_khoi

CLINIC = "a0000000-0000-4000-8000-000000000001"
HASH = "$2a$06$" + "y" * 53  # đúng dạng bcrypt; database thử không băm thật

HIEN_TAI: dict[str, StaffIdentity] = {}


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    app.dependency_overrides[get_db_pool] = lambda: p
    app.dependency_overrides[_resolve_identity] = lambda: HIEN_TAI["ai"]
    try:
        yield p
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)
        await p.close()


@pytest_asyncio.fixture
async def http(pool: asyncpg.Pool) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://tk"
    ) as c:
        yield c


async def _nhan_vien(
    conn: asyncpg.Connection, *, clinic: str = CLINIC, noi: bool = True
) -> tuple[str, str | None]:
    """Nhân viên có membership ở `clinic`, (tuỳ) đã nối + có app_credential."""
    # Cơ sở lấy của phòng khám chính (cột bắt buộc); phạm vi đi theo membership.
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    uid = str(uuid.uuid4()) if noi else None
    if uid:
        await conn.execute("INSERT INTO auth.users (id) VALUES ($1::uuid)", uid)
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active, auth_user_id) VALUES ($1, 'RECEPTION', $2::uuid, true, $3::uuid)"
        " RETURNING id::text",
        f"TK thử {uuid.uuid4().hex[:6]}",
        loc,
        uid,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, 'RECEPTION', true)",
        clinic,
        sid,
    )
    if uid:
        await conn.execute(
            "INSERT INTO app_credential (staff_id, email, password_hash)"
            " VALUES ($1::uuid, $2, $3)",
            sid,
            f"tk-{sid[:8]}@dr4women.local",
            HASH,
        )
    return sid, uid


async def _quan_ly(pool: asyncpg.Pool, khoi: list[str]) -> StaffIdentity:
    async with pool.acquire() as conn:
        sid, _ = await _nhan_vien(conn, noi=False)
        for k in khoi:
            for q in quyen_cua_khoi(k):
                await conn.execute(
                    "INSERT INTO capability_grant (clinic_id, staff_id, capability,"
                    " tu_khoi) VALUES ($1::uuid, $2::uuid, $3, $4)"
                    " ON CONFLICT DO NOTHING",
                    CLINIC,
                    sid,
                    q,
                    k,
                )
        loc = await conn.fetchval(
            "SELECT primary_location_id::text FROM staff WHERE id = $1::uuid", sid
        )
    cache.quen(CLINIC, sid)
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name="QL thử",
        department="RECEPTION",
        role=ClinicRole("RECEPTION"),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
        vai_theo_lego=await doc_vai_theo_lego(
            pool, CLINIC, sid, ClinicRole("RECEPTION")
        ),
    )


async def _khoa(pool: asyncpg.Pool, sid: str) -> asyncpg.Record:
    row = await pool.fetchrow(
        "SELECT c.thu_hoi_luc, c.thu_hoi_boi::text AS thu_hoi_boi, s.auth_user_id::text"
        "  AS auth_user_id FROM app_credential c JOIN staff s ON s.id = c.staff_id"
        " WHERE c.staff_id = $1::uuid",
        sid,
    )
    assert row is not None
    return row


@pytest.mark.asyncio
async def test_thu_hoi_khoa_app_credential_roi_cap_lai_mo_ra(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    HIEN_TAI["ai"] = ql = await _quan_ly(pool, ["nhan_su"])
    async with pool.acquire() as conn:
        sid, uid = await _nhan_vien(conn)

    r = await http.get(f"/api/v1/staff/{sid}/tai-khoan")
    assert r.status_code == 200 and r.json()["auth_user_id"] == uid

    # Màn cũ (tab khác vừa đổi tài khoản) → 409, KHÔNG gỡ nhầm.
    r = await http.post(
        f"/api/v1/staff/{sid}/tai-khoan/thu-hoi",
        json={"auth_user_id": str(uuid.uuid4())},
    )
    assert r.status_code == 409
    assert (await _khoa(pool, sid))["thu_hoi_luc"] is None

    r = await http.post(
        f"/api/v1/staff/{sid}/tai-khoan/thu-hoi", json={"auth_user_id": uid}
    )
    assert r.status_code == 200, r.text
    assert r.json()["khoa_ung_dung"] is True
    k = await _khoa(pool, sid)
    assert k["auth_user_id"] is None
    assert k["thu_hoi_luc"] is not None and k["thu_hoi_boi"] == ql.staff_id
    su_kien = await pool.fetchval(
        "SELECT payload->>'auth_user_id_cu' FROM event_log"
        " WHERE clinic_id = $1::uuid AND event_type = 'staff.account_thu_hoi'"
        "   AND aggregate_id = $2 ORDER BY recorded_at DESC LIMIT 1",
        CLINIC,
        sid,
    )
    assert su_kien == uid

    # Thu hồi lần hai: chưa có tài khoản → 409.
    r = await http.post(
        f"/api/v1/staff/{sid}/tai-khoan/thu-hoi", json={"auth_user_id": uid}
    )
    assert r.status_code == 409

    # Cấp lại = "Tạo tài khoản": người dùng GoTrue mới → nối → khoá mở ra.
    moi = str(uuid.uuid4())
    await pool.execute("INSERT INTO auth.users (id) VALUES ($1::uuid)", moi)
    r = await http.post(
        f"/api/v1/staff/{sid}/tai-khoan/noi", json={"auth_user_id": moi}
    )
    assert r.status_code == 200, r.text
    assert r.json()["mo_lai_khoa_ung_dung"] is True
    k = await _khoa(pool, sid)
    assert k["auth_user_id"] == moi
    assert k["thu_hoi_luc"] is None and k["thu_hoi_boi"] is None

    # Đã nối rồi thì không nối đè.
    khac = str(uuid.uuid4())
    await pool.execute("INSERT INTO auth.users (id) VALUES ($1::uuid)", khac)
    r = await http.post(
        f"/api/v1/staff/{sid}/tai-khoan/noi", json={"auth_user_id": khac}
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_nhan_vien_phong_kham_khac_la_404(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    HIEN_TAI["ai"] = await _quan_ly(pool, ["nhan_su"])
    async with pool.acquire() as conn:
        khac = await conn.fetchval(
            "SELECT id::text FROM clinic WHERE id <> $1::uuid LIMIT 1",
            CLINIC,
        )
        if khac is None:
            pytest.skip("database thử chỉ có một phòng khám")
        sid, uid = await _nhan_vien(conn, clinic=khac)

    assert (await http.get(f"/api/v1/staff/{sid}/tai-khoan")).status_code == 404
    r = await http.post(
        f"/api/v1/staff/{sid}/tai-khoan/thu-hoi", json={"auth_user_id": uid}
    )
    assert r.status_code == 404
    k = await _khoa(pool, sid)
    assert k["auth_user_id"] == uid and k["thu_hoi_luc"] is None


@pytest.mark.asyncio
async def test_khong_co_quyen_account_manage_thi_403(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    HIEN_TAI["ai"] = await _quan_ly(pool, [])
    async with pool.acquire() as conn:
        sid, uid = await _nhan_vien(conn)

    r = await http.post(
        f"/api/v1/staff/{sid}/tai-khoan/thu-hoi", json={"auth_user_id": uid}
    )
    assert r.status_code == 403
    assert (await _khoa(pool, sid))["auth_user_id"] == uid
