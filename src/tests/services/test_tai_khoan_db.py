"""Thu hồi / cấp lại tài khoản (06/10/2026) — qua HTTP thật (router + service +
database), chỉ thay bước JWT.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_tai_khoan_db.py

Kẽ hở được vá: "Gỡ tài khoản" gỡ nối + xoá GoTrue nhưng để nguyên app_credential,
nên nối lại (bằng bất kỳ đường nào) là chuỗi băm cũ mở lại /api/v1/auth/login.
Giờ thu hồi khoá app_credential trong CÙNG giao dịch với gỡ nối; "Tạo tài khoản"
(nối) là đường mở lại. Đăng nhập đọc dấu khoá — bài kiểm ở test_auth_service.py
(database thử không có schema `extensions` để chạy crypt() như prod).

Đồng bộ mật khẩu GoTrue → app_credential (20261006420000): database thử chỉ có
`auth.users(id)` rút gọn, nên `_cot_gotrue` thêm hai cột GoTrue thật dùng
(`email`, `encrypted_password`, cho phép NULL — bài kiểm khác không đổi gì).
"Đăng nhập được" kiểm đúng phép so của auth_service.py: hash = crypt(mk, hash)
(pgcrypto ở schema public trên database thử).
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
from clinicai.services.dong_bo_mat_khau import dong_bo

CLINIC = "a0000000-0000-4000-8000-000000000001"
MK_CU = "mat-khau-cu-123"

HIEN_TAI: dict[str, StaffIdentity] = {}


async def _cot_gotrue(conn: asyncpg.Connection) -> None:
    """Hai cột GoTrue mà hàm đồng bộ đọc — chỉ thêm khi bảng rút gọn thiếu."""
    co = await conn.fetchval(
        "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'auth'"
        " AND table_name = 'users' AND column_name IN ('email', 'encrypted_password')"
    )
    if co < 2:
        await conn.execute(
            "ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email varchar(255),"
            " ADD COLUMN IF NOT EXISTS encrypted_password varchar(255)"
        )


async def _gotrue(conn: asyncpg.Connection, mat_khau: str = MK_CU) -> str:
    """Người dùng GoTrue có email + bcrypt thật (như API quản trị tạo)."""
    uid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO auth.users (id, email, encrypted_password) VALUES ($1::uuid,"
        " $2, public.crypt($3, public.gen_salt('bf', 4)))",
        uid,
        f"tk-{uid[:8]}@dr4women.local",
        mat_khau,
    )
    return uid


async def _dat_mk_gotrue(pool: asyncpg.Pool, uid: str, mat_khau: str) -> None:
    await pool.execute(
        "UPDATE auth.users SET encrypted_password ="
        " public.crypt($2, public.gen_salt('bf', 4)) WHERE id = $1::uuid",
        uid,
        mat_khau,
    )


async def _khop(pool: asyncpg.Pool, sid: str, mat_khau: str) -> bool:
    """Đúng phép so của auth_service.py (crypt ở public trên database thử)."""
    return bool(
        await pool.fetchval(
            "SELECT password_hash = public.crypt($2, password_hash)"
            "  FROM app_credential WHERE staff_id = $1::uuid",
            sid,
            mat_khau,
        )
    )


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    async with p.acquire() as conn:
        await _cot_gotrue(conn)
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
    """Nhân viên có membership ở `clinic`, (tuỳ) đã nối + app_credential chép
    đúng chuỗi băm GoTrue (mật khẩu MK_CU)."""
    # Cơ sở lấy của phòng khám chính (cột bắt buộc); phạm vi đi theo membership.
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    uid = await _gotrue(conn) if noi else None
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
            " SELECT $1::uuid, email, encrypted_password FROM auth.users"
            " WHERE id = $2::uuid",
            sid,
            uid,
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

    # Cấp lại = "Tạo tài khoản": người dùng GoTrue mới (mật khẩu MỚI) → nối →
    # khoá mở ra VỚI MẬT KHẨU MỚI; mật khẩu cũ hết vào được.
    async with pool.acquire() as conn:
        moi = await _gotrue(conn, "mat-khau-moi-456")
    r = await http.post(
        f"/api/v1/staff/{sid}/tai-khoan/noi", json={"auth_user_id": moi}
    )
    assert r.status_code == 200, r.text
    assert r.json()["mo_lai_khoa_ung_dung"] is True
    k = await _khoa(pool, sid)
    assert k["auth_user_id"] == moi
    assert k["thu_hoi_luc"] is None and k["thu_hoi_boi"] is None
    assert await _khop(pool, sid, "mat-khau-moi-456")
    assert not await _khop(pool, sid, MK_CU)

    # Đã nối rồi thì không nối đè.
    async with pool.acquire() as conn:
        khac = await _gotrue(conn)
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


# ── Đồng bộ mật khẩu GoTrue → app_credential (20261006420000) ──────────────────

KHONG_DOI = {"them": 0, "sua": 0, "mo_lai": 0, "trung_email": 0}


async def _dem(pool: asyncpg.Pool, sid: str) -> asyncpg.Record:
    row = await pool.fetchrow(
        "SELECT email, password_hash, failed_attempts, locked_until, thu_hoi_luc"
        "  FROM app_credential WHERE staff_id = $1::uuid",
        sid,
    )
    assert row is not None
    return row


@pytest.mark.asyncio
async def test_dat_lai_mat_khau_va_doi_ten_chep_sang_app_credential(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    HIEN_TAI["ai"] = await _quan_ly(pool, ["nhan_su"])
    async with pool.acquire() as conn:
        sid, uid = await _nhan_vien(conn)
        # Đúng ca thật: người đã nối nhưng app_credential CHƯA có dòng.
        await conn.execute("DELETE FROM app_credential WHERE staff_id = $1::uuid", sid)
    assert uid is not None
    url = f"/api/v1/staff/{sid}/nhat-ky-tai-khoan"

    # Lần đầu: tạo dòng với mật khẩu hiện có ở GoTrue.
    r = await http.post(url, json={"hanh_dong": "doi_mat_khau"})
    assert r.status_code == 201, r.text
    assert r.json()["dong_bo"] == {**KHONG_DOI, "them": 1}
    assert await _khop(pool, sid, MK_CU)

    # Đặt lại mật khẩu ở GoTrue; đếm sai của mật khẩu cũ phải về 0.
    await pool.execute(
        "UPDATE app_credential SET failed_attempts = 4,"
        " locked_until = now() + interval '10 minutes' WHERE staff_id = $1::uuid",
        sid,
    )
    await _dat_mk_gotrue(pool, uid, "mat-khau-moi-789")
    r = await http.post(url, json={"hanh_dong": "doi_mat_khau"})
    assert r.json()["dong_bo"] == {**KHONG_DOI, "sua": 1}
    assert await _khop(pool, sid, "mat-khau-moi-789")
    assert not await _khop(pool, sid, MK_CU)
    d = await _dem(pool, sid)
    assert d["failed_attempts"] == 0 and d["locked_until"] is None

    # Idempotent: gọi lại hai lần liền không đổi gì.
    truoc = await _dem(pool, sid)
    for _ in range(2):
        r = await http.post(url, json={"hanh_dong": "doi_mat_khau"})
        assert r.json()["dong_bo"] == KHONG_DOI
    assert await _dem(pool, sid) == truoc

    # Đổi tên đăng nhập ở GoTrue → email đi theo, nhật ký ghi số dòng sửa.
    moi = f"ten-moi-{uid[:8]}@dr4women.local"
    await pool.execute("UPDATE auth.users SET email = $2 WHERE id = $1::uuid", uid, moi)
    r = await http.post(url, json={"hanh_dong": "doi_ten_dang_nhap"})
    assert r.json()["dong_bo"] == {**KHONG_DOI, "sua": 1}
    assert (await _dem(pool, sid))["email"] == moi
    sua = await pool.fetchval(
        "SELECT payload->'dong_bo'->>'sua' FROM event_log WHERE clinic_id = $1::uuid"
        "   AND event_type = 'staff.account_doi_ten_dang_nhap' AND aggregate_id = $2"
        " ORDER BY recorded_at DESC LIMIT 1",
        CLINIC,
        sid,
    )
    assert sua == "1"


@pytest.mark.asyncio
async def test_dong_thu_hoi_khong_bi_dong_bo_mo_lai(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    HIEN_TAI["ai"] = await _quan_ly(pool, ["nhan_su"])
    async with pool.acquire() as conn:
        sid, uid = await _nhan_vien(conn)
    r = await http.post(
        f"/api/v1/staff/{sid}/tai-khoan/thu-hoi", json={"auth_user_id": uid}
    )
    assert r.status_code == 200, r.text
    truoc = await _dem(pool, sid)

    # Nối lại bằng lối KHÁC "Tạo tài khoản" (script nhân sự ghi thẳng) với mật
    # khẩu mới: không lối đồng bộ nào được mở dòng thu hồi.
    async with pool.acquire() as conn:
        uid2 = await _gotrue(conn, "mat-khau-script-1")
        await conn.execute(
            "UPDATE staff SET auth_user_id = $2::uuid WHERE id = $1::uuid", sid, uid2
        )
        assert await dong_bo(conn, sid) == KHONG_DOI
        # mo_lai cho MỘT NGƯỜI KHÁC không lan sang người này.
        khac, _ = await _nhan_vien(conn)
        await dong_bo(conn, khac, mo_lai=True)
    await dong_bo(pool)  # lượt định kỳ: mọi nhân viên
    r = await http.post(
        f"/api/v1/staff/{sid}/nhat-ky-tai-khoan", json={"hanh_dong": "doi_mat_khau"}
    )
    assert r.json()["dong_bo"] == KHONG_DOI
    assert await _dem(pool, sid) == truoc
    assert not await _khop(pool, sid, "mat-khau-script-1")


@pytest.mark.asyncio
async def test_email_cua_dong_thu_hoi_duoc_cap_cho_nguoi_moi(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    """Gỡ "letan1" của A rồi đặt "letan1" cho B: B có dòng. Trùng dòng CÒN DÙNG
    của người khác thì bỏ qua + đếm, không làm hỏng cả lượt."""
    HIEN_TAI["ai"] = await _quan_ly(pool, ["nhan_su"])
    async with pool.acquire() as conn:
        a, uid_a = await _nhan_vien(conn)
    email_a = (await _dem(pool, a))["email"]
    r = await http.post(
        f"/api/v1/staff/{a}/tai-khoan/thu-hoi", json={"auth_user_id": uid_a}
    )
    assert r.status_code == 200, r.text
    async with pool.acquire() as conn:
        b, uid_b = await _nhan_vien(conn)
        await conn.execute("DELETE FROM app_credential WHERE staff_id = $1::uuid", b)
        await conn.execute("DELETE FROM auth.users WHERE id = $1::uuid", uid_a)
        await conn.execute(
            "UPDATE auth.users SET email = $2 WHERE id = $1::uuid", uid_b, email_a
        )
        assert await dong_bo(conn, b) == {**KHONG_DOI, "them": 1}
        assert (await _dem(pool, b))["email"] == email_a

        # C trỏ người dùng GoTrue có email trùng dòng CÒN DÙNG của B (dữ liệu lệch).
        c, uid_c = await _nhan_vien(conn)
        await conn.execute("DELETE FROM app_credential WHERE staff_id = $1::uuid", c)
        await conn.execute(
            "UPDATE auth.users SET email = upper($2) WHERE id = $1::uuid",
            uid_c,
            email_a,
        )
        assert await dong_bo(conn, c) == {**KHONG_DOI, "trung_email": 1}
    con = await pool.fetchval(
        "SELECT count(*) FROM app_credential WHERE staff_id = $1::uuid", c
    )
    assert con == 0


@pytest.mark.asyncio
async def test_dong_bo_nhan_vien_chua_noi_va_phong_kham_khac(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    HIEN_TAI["ai"] = await _quan_ly(pool, ["nhan_su"])
    async with pool.acquire() as conn:
        chua, _ = await _nhan_vien(conn, noi=False)
        assert await dong_bo(conn, chua) == KHONG_DOI
        khac = await conn.fetchval(
            "SELECT id::text FROM clinic WHERE id <> $1::uuid LIMIT 1", CLINIC
        )
        if khac is None:
            pytest.skip("database thử chỉ có một phòng khám")
        sid, uid = await _nhan_vien(conn, clinic=khac)
    assert uid is not None
    truoc = await _dem(pool, sid)
    await _dat_mk_gotrue(pool, uid, "mat-khau-pk-khac")
    r = await http.post(
        f"/api/v1/staff/{sid}/nhat-ky-tai-khoan", json={"hanh_dong": "doi_mat_khau"}
    )
    assert r.status_code == 404
    assert await _dem(pool, sid) == truoc
