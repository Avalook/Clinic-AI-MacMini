"""`queue_entry.vao_hang_luc` — giờ vào hàng LẦN ĐẦU (Tuyền 09/10/2026, 7b).

    scripts/test-nhanh.sh src/tests/services/test_queue_entry_vao_hang_luc_db.py

Kịch bản: khách vào hàng khám (T−37′), bác sĩ khám (T−13′, tức chờ 24′), khách
đi làm dịch vụ — chỗ chờ khám bị khoá — rồi quay lại: `mo_cho_bi_chan` đặt lại
`eligible_at = now()` (luật xếp sau người đang chờ, GIỮ NGUYÊN). Trigger giữ
`vao_hang_luc`; Hành trình khách đọc đúng câu `_SQL_HANG` ra "vào T−37′ · chờ
24′ · quay lại T". Thứ tự hàng vẫn theo `eligible_at`.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.services import hanh_trinh_khach_service as htk
from clinicai.services.hang_cho import chan_cho_khac, mo_cho_bi_chan
from tests.services.test_truong_ca_3_loi_db import (  # noqa: F401
    CLINIC,
    _loc,
    _luot,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _vao_hang(
    conn: asyncpg.Connection, vid: str, status: str, phut_truoc: int | None
) -> str:
    return str(
        await conn.fetchval(
            """
            INSERT INTO queue_entry (clinic_id, visit_id, lane, reason, ref_id,
                                     status, eligible_at)
            VALUES ($1::uuid, $2::uuid, 'DOCTOR', 'PRIMARY', $3::uuid, $4,
                    CASE WHEN $5::int IS NOT NULL
                         THEN now() - make_interval(mins => $5::int) END)
            RETURNING id::text
            """,
            CLINIC,
            vid,
            str(uuid.uuid4()),
            status,
            phut_truoc,
        )
    )


async def _cot(conn: asyncpg.Connection, qid: str) -> Any:
    return await conn.fetchrow(
        "SELECT status, eligible_at, vao_hang_luc, now() AS bay_gio"
        " FROM queue_entry WHERE id = $1::uuid",
        qid,
    )


async def test_vao_hang_luc_giu_lan_dau_thu_tu_hang_van_theo_eligible(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            loc = await _loc(conn)
            a = await _luot(conn, loc, ten="Khách quay lại", node="LUOTKHAM-03")
            b = await _luot(conn, loc, ten="Khách vào sau", node="LUOTKHAM-03")
            qa = await _vao_hang(conn, a, "waiting", 37)
            qb = await _vao_hang(conn, b, "waiting", 30)
            r = await _cot(conn, qa)
            vao = r["eligible_at"]
            assert r["vao_hang_luc"] == vao, "tạo ở waiting: vào hàng = eligible_at"

            # Khách sang phòng khác: chỗ chờ khám khoá; về: mở lại, eligible = now.
            await chan_cho_khac(conn, CLINIC, a, str(uuid.uuid4()))
            assert (await _cot(conn, qa))["status"] == "blocked"
            await mo_cho_bi_chan(conn, CLINIC, a)
            r = await _cot(conn, qa)
            assert r["status"] == "waiting"
            assert r["eligible_at"] == r["bay_gio"], "luật xếp hàng giữ nguyên"
            assert r["vao_hang_luc"] == vao, "lần đầu vào hàng không bị ghi đè"

            # Thứ tự hàng KHÔNG đổi luật: quay lại thì đứng sau người đang chờ.
            thu_tu = await conn.fetch(
                "SELECT id::text FROM queue_entry WHERE id = ANY($1::uuid[])"
                " ORDER BY coalesce(eligible_at, created_at), id",
                [qa, qb],
            )
            assert [x["id"] for x in thu_tu] == [qb, qa]

            # Ghi thẳng cột cũng không đè được.
            await conn.execute(
                "UPDATE queue_entry SET vao_hang_luc = now() WHERE id = $1::uuid", qa
            )
            assert (await _cot(conn, qa))["vao_hang_luc"] == vao

            # Hành trình đọc đúng câu thật → vào T−37′, chờ 24′, quay lại bây giờ.
            hang = [dict(x) for x in await conn.fetch(htk._SQL_HANG, CLINIC, [a])]
            bat_kham = vao + timedelta(minutes=24)
            vao_kham, quay = htk.vao_hang_that(hang[0], bat_kham)
            assert vao_kham == vao
            assert bat_kham - vao_kham == timedelta(minutes=24)
            assert quay == r["bay_gio"]
        finally:
            await tx.rollback()


async def test_tao_o_blocked_thi_vao_hang_luc_la_luc_mo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            loc = await _loc(conn)
            a = await _luot(conn, loc, ten="Khách đang bận", node="LUOTKHAM-03")
            qa = await _vao_hang(conn, a, "blocked", None)
            assert (await _cot(conn, qa))["vao_hang_luc"] is None, (
                "đang bận ở phòng khác: chưa bắt đầu chờ"
            )
            await mo_cho_bi_chan(conn, CLINIC, a)
            r = await _cot(conn, qa)
            assert r["vao_hang_luc"] == r["eligible_at"] == r["bay_gio"]
        finally:
            await tx.rollback()
