"""Ba lỗi màn Điều phối ca (Tuyền 29/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55710/postgres \\
        pytest src/tests/services/test_truong_ca_3_loi_db.py

1. Khách đã check-out / lượt ngày cũ KHÔNG tính vào "đang trong phòng khám".
2. Lịch sử điều phối trả nhãn tiếng Việt + tên bước, không mã thô.
3. Migration gỡ DXA khỏi phòng Đo sinh hiệu — chạy lại được, không gỡ nếu
   không còn phòng nào khác làm DXA.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.services import dispatch_service as ds
from clinicai.services.dispatch_service import DispatchService

CLINIC = "a0000000-0000-4000-8000-000000000001"
MIGRATION = (
    Path(__file__).parents[3]
    / "supabase/migrations/20260929970000_go_dxa_khoi_phong_do_sinh_hieu.sql"
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    p = await asyncpg.create_pool(
        dsn=url.replace("postgresql+asyncpg://", "postgresql://", 1),
        min_size=1,
        max_size=4,
    )
    yield p
    await p.close()


async def _loc(conn: asyncpg.Connection) -> str:
    return str(
        await conn.fetchval(
            "SELECT location_id::text FROM clinic_room WHERE clinic_id = $1::uuid"
            " LIMIT 1",
            CLINIC,
        )
    )


async def _benh_nhan(conn: asyncpg.Connection, loc: str, ten: str) -> Any:
    return await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, $3, $4::uuid) RETURNING clinic_patient_id",
        CLINIC,
        f"T3L-{uuid.uuid4().hex[:8]}",
        ten,
        loc,
    )


async def _luot(
    conn: asyncpg.Connection,
    loc: str,
    *,
    ten: str,
    node: str,
    ngay_truoc: int = 0,
    dong: bool = False,
) -> str:
    pid = await _benh_nhan(conn, loc, ten)
    return str(
        await conn.fetchval(
            """
            INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at,
                               current_node_code, current_node_since, closed_at)
            VALUES ($1::uuid, $2, 'OPEN',
                    now() - make_interval(days => $3::int, mins => 30), $4,
                    now() - make_interval(days => $3::int, mins => 30),
                    CASE WHEN $5::boolean THEN now() END)
            RETURNING visit_id::text
            """,
            CLINIC,
            pid,
            ngay_truoc,
            node,
            dong,
        )
    )


async def test_tong_quan_chi_tinh_luot_con_mo_hom_nay(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            loc = await _loc(conn)
            con_mo = await _luot(conn, loc, ten="Khách còn mở", node="LUOTKHAM-03")
            da_ve = await _luot(
                conn, loc, ten="Khách đã về", node="LUOTKHAM-15", dong=True
            )
            node15 = await _luot(conn, loc, ten="Ở bước đóng", node="LUOTKHAM-15")
            cu = await _luot(
                conn, loc, ten="Lượt hôm qua", node="LUOTKHAM-03", ngay_truoc=2
            )
            rows = await conn.fetch(
                # None = mọi cơ sở (lọc cơ sở 08/10/2026).
                ds._OVERVIEW_SQL,
                CLINIC,
                list(ds.LIVE_VISIT_STATUSES),
                None,
            )
            ids = {str(r["visit_id"]) for r in rows}
            assert con_mo in ids
            assert da_ve not in ids
            assert node15 not in ids
            assert cu not in ids
        finally:
            await tx.rollback()


async def test_lich_su_co_nhan_tieng_viet(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        loc = await _loc(conn)
        visit = await _luot(conn, loc, ten="Khách lịch sử", node="LUOTKHAM-15")
    # DB dùng một lần: visit / event_log là append-only nên không dọn tay.
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO event_log (clinic_id, source, aggregate_type, aggregate_id,
                                   event_type, payload, metadata)
            VALUES ($1::uuid, 'test', 'visit', $2::uuid, 'dispatch.checkout',
                    $3::jsonb, '{}'::jsonb)
            """,
            CLINIC,
            visit,
            json.dumps({"to_node": "LUOTKHAM-15"}),
        )
    rows = await DispatchService(pool).history(clinic_id=CLINIC, limit=50)
    [r] = [x for x in rows if x["visit_id"] == visit]
    assert r["event_label"] == "Cho khách về (check-out)"
    assert r["to_node_name"] == "Đóng lượt khám"
    assert r["event_type"] == "dispatch.checkout"


async def _mot_phong(
    conn: asyncpg.Connection, loc: str, ten: str, nodes: list[str]
) -> str:
    rid = await conn.fetchval(
        "INSERT INTO clinic_room (clinic_id, code, name, node_code, location_id)"
        " VALUES ($1::uuid, $2, $3, $4, $5::uuid) RETURNING id::text",
        CLINIC,
        f"T3-{uuid.uuid4().hex[:6]}",
        ten,
        nodes[0],
        loc,
    )
    for n in nodes:
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3)",
            CLINIC,
            rid,
            n,
        )
    return str(rid)


async def _dxa(conn: asyncpg.Connection, rid: str) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM clinic_room_node WHERE room_id = $1::uuid"
            " AND node_code = 'DICHVU-DXA')",
            rid,
        )
    )


async def test_migration_go_dxa_khoi_phong_do_sinh_hieu(pool: asyncpg.Pool) -> None:
    sql = MIGRATION.read_text()
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            loc = await _loc(conn)
            # Cô lập: chỉ các phòng của bài thử làm DXA.
            await conn.execute(
                "DELETE FROM clinic_room_node WHERE node_code = 'DICHVU-DXA'"
            )
            await conn.execute(
                "UPDATE clinic_room SET node_code = 'LUOTKHAM-03'"
                " WHERE node_code = 'DICHVU-DXA'"
            )
            sinh_hieu = await _mot_phong(
                conn, loc, "Đo sinh hiệu", ["LUOTKHAM-03", "DICHVU-DXA"]
            )
            # Chưa có phòng nào khác → KHÔNG gỡ.
            await conn.execute(sql)
            assert await _dxa(conn, sinh_hieu)

            doi_tac = await _mot_phong(conn, loc, "Phòng đối tác", ["DICHVU-DXA"])
            await conn.execute(sql)
            assert not await _dxa(conn, sinh_hieu)
            assert await _dxa(conn, doi_tac)
            n_chinh = await conn.fetchval(
                "SELECT count(*) FROM clinic_room_node WHERE room_id = $1::uuid"
                " AND node_code = 'LUOTKHAM-03'",
                sinh_hieu,
            )
            assert n_chinh == 1
            # Chạy lần hai: không đổi gì.
            await conn.execute(sql)
            assert await _dxa(conn, doi_tac)
            assert not await _dxa(conn, sinh_hieu)
        finally:
            await tx.rollback()
