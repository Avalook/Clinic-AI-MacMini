"""R-042: vai PARTNER/DISPLAY không đọc được dữ liệu khách qua PostgREST.

Đọc với đúng vai `authenticated` + `request.jwt.claim.sub` như PostgREST làm.
Mọi thứ trong một giao dịch rồi ROLLBACK — không để lại gì trong DB tạm.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg
import pytest

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

BANG = ("patient", "appointment", "lab_result", "staff")


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL trỏ tới database dùng một lần")
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _dem_nhu(conn: Any, auth_id: str, clinic_id: str) -> dict[str, int]:
    """Đếm dòng của phòng khám thử mà người dùng `auth_id` thấy qua RLS."""
    await conn.execute("SELECT set_config('request.jwt.claim.sub', $1, true)", auth_id)
    await conn.execute("SET LOCAL ROLE authenticated")
    try:
        dem = {
            t: await conn.fetchval(
                f"SELECT count(*) FROM public.{t} WHERE clinic_id = $1::uuid",  # noqa: S608
                clinic_id,
            )
            for t in BANG[:3]
        }
        # staff không có clinic_id: đếm trong nhóm nhân viên thử vừa tạo.
        dem["staff"] = await conn.fetchval(
            "SELECT count(*) FROM public.staff WHERE full_name LIKE 'R042-%'"
        )
        return dem
    finally:
        await conn.execute("RESET ROLE")


async def _nguoi(
    conn: Any, ten: str, vai: list[str], clinic_id: str, loc_id: str
) -> str:
    auth_id, staff_id = str(uuid.uuid4()), str(uuid.uuid4())
    await conn.execute("INSERT INTO auth.users (id) VALUES ($1::uuid)", auth_id)
    await conn.execute(
        "INSERT INTO public.staff (id, auth_user_id, full_name, primary_department,"
        " primary_location_id, is_active) VALUES ($1::uuid, $2::uuid, $3, $4,"
        " $5::uuid, true)",
        staff_id,
        auth_id,
        f"R042-{ten}",
        vai[0],
        loc_id,
    )
    for v in vai:
        await conn.execute(
            "INSERT INTO public.clinic_membership (clinic_id, staff_id, role,"
            " is_active) VALUES ($1::uuid, $2::uuid, $3, true)",
            clinic_id,
            staff_id,
            v,
        )
    return auth_id


async def test_vai_ngoai_khong_doc_duoc_du_lieu_khach() -> None:
    conn = await asyncpg.connect(_dsn())
    tx = conn.transaction()
    await tx.start()
    try:
        clinic_id, loc_id = str(uuid.uuid4()), str(uuid.uuid4())
        cp_id, st_id = str(uuid.uuid4()), str(uuid.uuid4())
        # Hạt giống tối thiểu cho ba bảng khách; bỏ qua khoá ngoài/trigger ở bước
        # GIEO (replica) — test này chỉ đo RLS lúc ĐỌC.
        await conn.execute("SET LOCAL session_replication_role = replica")
        await conn.execute(
            "INSERT INTO public.clinic (id, code, name) VALUES ($1::uuid, $2, 'R042')",
            clinic_id,
            f"R042-{clinic_id[:8]}",
        )
        await conn.execute(
            "INSERT INTO public.patient (clinic_id, patient_code, full_name,"
            " location_id) VALUES ($1::uuid, 'R042-BN', 'R042 Khach Thu', $2::uuid)",
            clinic_id,
            loc_id,
        )
        await conn.execute(
            "INSERT INTO public.appointment (clinic_id, clinic_patient_id,"
            " location_id, service_type_id, slot_start, slot_end) VALUES"
            " ($1::uuid, $2::uuid, $3::uuid, $4::uuid,"
            " now(), now() + interval '15 min')",
            clinic_id,
            cp_id,
            loc_id,
            st_id,
        )
        await conn.execute(
            "INSERT INTO public.lab_result (clinic_id, clinic_patient_id, test_code,"
            " test_name) VALUES ($1::uuid, $2::uuid, 'R042', 'R042 xet nghiem')",
            clinic_id,
            cp_id,
        )
        le_tan = await _nguoi(conn, "le-tan", ["RECEPTION"], clinic_id, loc_id)
        doi_tac = await _nguoi(conn, "doi-tac", ["PARTNER"], clinic_id, loc_id)
        man_hinh = await _nguoi(conn, "man-hinh", ["DISPLAY"], clinic_id, loc_id)
        hai_vai = await _nguoi(
            conn, "hai-vai", ["PARTNER", "RECEPTION"], clinic_id, loc_id
        )
        await conn.execute("SET LOCAL session_replication_role = origin")

        trong_nha = {"patient": 1, "appointment": 1, "lab_result": 1, "staff": 4}
        # Vai ngoài: không thấy khách, chỉ thấy đúng dòng staff của chính mình
        # (proxy.ts cần dòng đó để giữ phiên).
        vai_ngoai = {"patient": 0, "appointment": 0, "lab_result": 0, "staff": 1}

        assert await _dem_nhu(conn, le_tan, clinic_id) == trong_nha
        assert await _dem_nhu(conn, hai_vai, clinic_id) == trong_nha
        assert await _dem_nhu(conn, doi_tac, clinic_id) == vai_ngoai
        assert await _dem_nhu(conn, man_hinh, clinic_id) == vai_ngoai
    finally:
        await tx.rollback()
        await conn.close()


async def test_bon_bang_deu_co_policy_restrictive() -> None:
    """Canh: ai xoá/đổi policy chặn thành permissive thì đỏ."""
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            "SELECT tablename, permissive FROM pg_policies WHERE schemaname = 'public'"
            " AND policyname = tablename || '_chan_vai_ngoai'"
        )
    finally:
        await conn.close()
    assert {r["tablename"]: r["permissive"] for r in rows} == {
        t: "RESTRICTIVE" for t in BANG
    }
