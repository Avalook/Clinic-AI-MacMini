"""Bài canh /rest/v1 (20261022900000, kế hoạch docs/ke-hoach/khoa-rest-v1-2210.md).

PostgREST mở thẳng ra Internet qua Caddy. Trước 22/10/2026 tài khoản ĐỐI TÁC đọc
được 70 khách, 51 lịch hẹn vì chính sách chỉ hỏi "thuộc phòng khám không".
Nay `anon`/`authenticated` chỉ được đúng danh sách dưới đây. Thêm bảng/cột/hàm
mà tự mở cho hai vai này → bài này đỏ. Muốn mở thật thì sửa danh sách ở đây
CÙNG migration, và nói rõ trong PR vì sao giao diện cần đọc thẳng Postgres
thay vì qua FastAPI.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

VAI_REST = ("anon", "authenticated")

#: Đúng các cột màn đăng nhập (login/actions.ts) và proxy.ts đọc.
COT_DUOC_DOC = {
    ("authenticated", "clinic_membership", "clinic_id"),
    ("authenticated", "clinic_membership", "is_active"),
    ("authenticated", "clinic_membership", "role"),
    ("authenticated", "clinic_membership", "staff_id"),
    ("authenticated", "staff", "auth_user_id"),
    ("authenticated", "staff", "id"),
    ("authenticated", "staff", "is_active"),
    ("authenticated", "staff", "primary_department"),
}

#: Hàm mà policy RLS còn gọi (lý do từng hàm: comment trong migration).
HAM_DUOC_GOI = {
    ("authenticated", "current_clinic_ids"),
    ("authenticated", "current_clinic_ids_for_roles"),
    ("authenticated", "current_clinical_clinic_ids"),
    ("authenticated", "current_staff_id"),
    ("authenticated", "thu_ky_duoc_xem_khach"),
}

BANG_NHAY_CAM = (
    "patient",
    "appointment",
    "payment",
    "visit",
    "prescription",
    "lab_result",
    "capability_grant",
    "payment_cycle",
    "clinic",
)

#: Cột staff không bao giờ được ra Internet.
COT_STAFF_NHAY_CAM = (
    "full_name",
    "national_id_number",
    "phone",
    "date_of_birth",
    "license_number",
    "email",
)


@pytest_asyncio.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    url = os.environ.get("DATABASE_URL_TEST")
    if not url:
        pytest.skip("requires explicitly disposable, migrated DATABASE_URL_TEST")
    c = await asyncpg.connect(url)
    try:
        yield c
    finally:
        await c.close()


# ── Quyền: so với danh sách cho phép cố định ──────────────────────────────


async def test_khong_con_quyen_ca_bang_nao(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        "SELECT grantee, table_name, privilege_type"
        " FROM information_schema.role_table_grants"
        " WHERE table_schema = 'public' AND grantee = ANY($1::text[])",
        [*VAI_REST, "PUBLIC"],
    )
    assert [tuple(r) for r in rows] == []


async def test_chi_doc_dung_cac_cot_cho_phep(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        "SELECT grantee, table_name, column_name, privilege_type"
        " FROM information_schema.column_privileges"
        " WHERE table_schema = 'public' AND grantee = ANY($1::text[])",
        [*VAI_REST, "PUBLIC"],
    )
    assert {r["privilege_type"] for r in rows} <= {"SELECT"}
    assert {(r["grantee"], r["table_name"], r["column_name"]) for r in rows} == (
        COT_DUOC_DOC
    )


async def test_chi_goi_dung_cac_ham_cho_phep(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        "SELECT grantee, routine_name FROM information_schema.routine_privileges"
        " WHERE routine_schema = 'public' AND grantee = ANY($1::text[])",
        [*VAI_REST, "PUBLIC"],
    )
    assert {(r["grantee"], r["routine_name"]) for r in rows} == HAM_DUOC_GOI


async def test_khong_sequence_nao_mo(conn: asyncpg.Connection) -> None:
    mo = await conn.fetch(
        "SELECT c.relname, v.vai FROM pg_class c"
        " JOIN pg_namespace n ON n.oid = c.relnamespace"
        " CROSS JOIN unnest($1::text[]) AS v(vai)"
        " WHERE n.nspname = 'public' AND c.relkind = 'S'"
        "   AND has_sequence_privilege(v.vai, c.oid, 'USAGE, SELECT, UPDATE')",
        list(VAI_REST),
    )
    assert [tuple(r) for r in mo] == []


async def test_bang_va_ham_moi_khong_tu_mo(conn: asyncpg.Connection) -> None:
    # Quyền mặc định: migration chạy bằng `postgres`; thời Supabase cloud có
    # `supabase_admin` cấp ALL mặc định cho anon/authenticated.
    mac_dinh = await conn.fetch(
        "SELECT d.defaclrole::regrole::text AS chu, d.defaclobjtype"
        " FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a"
        " WHERE a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)"
        "   AND (d.defaclnamespace = 0 OR d.defaclnamespace = 'public'::regnamespace)"
        "   AND NOT (d.defaclnamespace = 0 AND d.defaclobjtype IN ('T', 'n'))"
    )
    assert [tuple(r) for r in mac_dinh] == []
    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute("CREATE TABLE public.canh_rest_v1_bang_moi (id int)")
        await conn.execute(
            "CREATE FUNCTION public.canh_rest_v1_ham_moi() RETURNS int"
            " LANGUAGE sql AS 'SELECT 1'"
        )
        for vai in VAI_REST:
            assert not await conn.fetchval(
                "SELECT has_table_privilege($1, 'public.canh_rest_v1_bang_moi',"
                " 'SELECT, INSERT, UPDATE, DELETE')",
                vai,
            )
            assert not await conn.fetchval(
                "SELECT has_function_privilege($1,"
                " 'public.canh_rest_v1_ham_moi()', 'EXECUTE')",
                vai,
            )
    finally:
        await tr.rollback()


async def test_policy_hai_bang_chi_hang_cua_minh(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        "SELECT tablename, policyname, cmd, roles::text[] AS roles, qual"
        " FROM pg_policies WHERE schemaname = 'public'"
        "   AND tablename IN ('staff', 'clinic_membership')"
        "   AND permissive = 'PERMISSIVE'"
        " ORDER BY tablename"
    )
    assert [(r["tablename"], r["policyname"], r["cmd"], r["roles"]) for r in rows] == [
        (
            "clinic_membership",
            "clinic_membership_select_chinh_minh",
            "SELECT",
            ["authenticated"],
        ),
        ("staff", "staff_select_chinh_minh", "SELECT", ["authenticated"]),
    ]
    assert all("auth.uid()" in r["qual"] for r in rows)


# ── Hành vi thật dưới vai authenticated ──────────────────────────────────


async def _tao_nguoi(conn: asyncpg.Connection, vai: str) -> tuple[str, str]:
    """Một nhân viên + tài khoản đăng nhập + membership `vai`. Trả (auth, staff)."""
    auth_id, staff_id = str(uuid.uuid4()), str(uuid.uuid4())
    clinic_id = await conn.fetchval(
        "SELECT id FROM clinic ORDER BY created_at, id LIMIT 1"
    )
    location_id = await conn.fetchval(
        "SELECT id FROM clinic_location WHERE clinic_id = $1 AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        clinic_id,
    )
    await conn.execute("INSERT INTO auth.users (id) VALUES ($1::uuid)", auth_id)
    await conn.execute(
        "INSERT INTO staff (id, full_name, primary_department, auth_user_id,"
        " primary_location_id, national_id_number, phone)"
        " VALUES ($1::uuid, $2, $3, $4::uuid, $5, $6, '0900000000')",
        staff_id,
        f"Canh REST {vai}",
        vai,
        auth_id,
        location_id,
        f"{uuid.uuid4().int % 10**12:012d}",  # CCCD là duy nhất (uq_staff_cccd)
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role)"
        " VALUES ($1, $2::uuid, $3)"
        " ON CONFLICT ON CONSTRAINT uq_clinic_membership DO NOTHING",
        clinic_id,
        staff_id,
        vai,
    )
    return auth_id, staff_id


async def _dong_vai(conn: asyncpg.Connection, auth_id: str) -> None:
    await conn.execute("SET LOCAL ROLE authenticated")
    await conn.execute(
        "SELECT set_config('request.jwt.claims', $1, true)",
        f'{{"sub": "{auth_id}", "role": "authenticated"}}',
    )


async def _bi_tu_choi(conn: asyncpg.Connection, sql: str) -> bool:
    try:
        async with conn.transaction():  # savepoint: lỗi không làm hỏng giao dịch ngoài
            await conn.fetch(sql)
    except asyncpg.InsufficientPrivilegeError:
        return True
    return False


@pytest.mark.parametrize("vai", ["PARTNER", "DISPLAY"])
async def test_doi_tac_va_tivi_khong_doc_duoc_du_lieu_khach(
    conn: asyncpg.Connection, vai: str
) -> None:
    tr = conn.transaction()
    await tr.start()
    try:
        auth_id, staff_id = await _tao_nguoi(conn, vai)
        await _tao_nguoi(conn, "RECEPTION")  # một đồng nghiệp để thử đọc chéo
        await _dong_vai(conn, auth_id)
        for bang in BANG_NHAY_CAM:
            assert await _bi_tu_choi(conn, f"SELECT * FROM public.{bang} LIMIT 1"), bang
        assert await _bi_tu_choi(conn, "SELECT * FROM public.staff")
        for cot in COT_STAFF_NHAY_CAM:
            assert await _bi_tu_choi(conn, f"SELECT {cot} FROM public.staff"), cot
        ids = await conn.fetch("SELECT id::text FROM public.staff")
        assert [r["id"] for r in ids] == [staff_id]
        mem = await conn.fetch(
            "SELECT staff_id::text, role FROM public.clinic_membership"
        )
        assert {r["staff_id"] for r in mem} == {staff_id}
    finally:
        await tr.rollback()


async def test_nhan_vien_thuong_chi_thay_hang_cua_minh(
    conn: asyncpg.Connection,
) -> None:
    tr = conn.transaction()
    await tr.start()
    try:
        auth_id, staff_id = await _tao_nguoi(conn, "CASHIER")
        await _tao_nguoi(conn, "DOCTOR")
        await _dong_vai(conn, auth_id)
        # Đúng câu của login/actions.ts và proxy.ts.
        rows = await conn.fetch(
            "SELECT id::text, primary_department, is_active, auth_user_id::text"
            " FROM public.staff WHERE auth_user_id = $1::uuid",
            auth_id,
        )
        assert [tuple(r) for r in rows] == [(staff_id, "CASHIER", True, auth_id)]
        assert [
            r["id"] for r in await conn.fetch("SELECT id::text FROM public.staff")
        ] == [staff_id]
        mem = await conn.fetch(
            "SELECT clinic_id, role, is_active FROM public.clinic_membership"
            " WHERE staff_id = $1::uuid AND is_active",
            staff_id,
        )
        assert [r["role"] for r in mem] == ["CASHIER"]
        assert await _bi_tu_choi(conn, "SELECT national_id_number FROM public.staff")
        assert await _bi_tu_choi(conn, "SELECT * FROM public.patient LIMIT 1")
        assert await _bi_tu_choi(
            conn, "SELECT public.read_prescription_draft(gen_random_uuid())"
        )
    finally:
        await tr.rollback()


async def test_nhan_vien_da_nghi_van_thay_hang_cua_minh(
    conn: asyncpg.Connection,
) -> None:
    # Màn đăng nhập cần thấy is_active = false để báo đúng câu, không lọc ở policy.
    tr = conn.transaction()
    await tr.start()
    try:
        auth_id, staff_id = await _tao_nguoi(conn, "RECEPTION")
        await conn.execute(
            "UPDATE clinic_membership SET is_active = false WHERE staff_id = $1::uuid",
            staff_id,
        )
        await conn.execute(
            "UPDATE staff SET is_active = false WHERE id = $1::uuid", staff_id
        )
        await _dong_vai(conn, auth_id)
        rows = await conn.fetch("SELECT id::text, is_active FROM public.staff")
        assert [tuple(r) for r in rows] == [(staff_id, False)]
    finally:
        await tr.rollback()


async def test_anon_khong_doc_duoc_gi(conn: asyncpg.Connection) -> None:
    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute("SET LOCAL ROLE anon")
        for bang in ("staff", "clinic_membership", *BANG_NHAY_CAM):
            assert await _bi_tu_choi(conn, f"SELECT 1 FROM public.{bang} LIMIT 1"), bang
        assert await _bi_tu_choi(conn, "SELECT public.current_clinic_ids()")
    finally:
        await tr.rollback()
