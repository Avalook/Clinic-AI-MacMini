"""Audit: a capped observation must not resolve an unobserved overdue task."""

# ruff: noqa: F811 -- imported fixture follows the repository convention.

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.services import agent_giam_sat as ag
from tests.services.test_phieu_kham_db import CLINIC, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_capped_detection_keeps_unobserved_overdue_incident_open(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = [str(uuid.uuid4()) for _ in range(ag.TRAN + 1)]
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            node = await conn.fetchrow(
                "SELECT n.code, nv.id FROM node_definition n"
                " JOIN node_definition_version nv ON nv.node_definition_id=n.id"
                " AND nv.clinic_id=n.clinic_id AND nv.version=n.current_version"
                " WHERE n.clinic_id=$1::uuid LIMIT 1",
                CLINIC,
            )
            assert node is not None
            await conn.executemany(
                "INSERT INTO work_item(id,clinic_id,node_code,node_version_id,due_at)"
                " VALUES($1::uuid,$2::uuid,$3,$4,now()-interval '5 hours')",
                [(key, CLINIC, node["code"], node["id"]) for key in ids],
            )
            observations = [
                ag.NhanDinh(
                    "viec_qua_han",
                    key,
                    "critical",
                    "Synthetic audit",
                    "quan_sat",
                    {"work_item_id": key},
                )
                for key in ids
            ]
            await ag.ap_dung(conn, CLINIC, {"viec_qua_han": observations}, set())
            # Scope the actual detector to our synthetic rows; preserve its real LIMIT.
            safe_ids = ",".join("'" + str(uuid.UUID(key)) + "'" for key in ids)
            monkeypatch.setattr(
                ag,
                "_QUA_HAN_SQL",
                ag._QUA_HAN_SQL.replace(
                    f"  LIMIT {ag.TRAN}",
                    f" AND w.id IN ({safe_ids})\n  LIMIT {ag.TRAN}",
                ),
            )
            now = await conn.fetchval("SELECT now()")
            observed = await ag.phat_hien_sql(conn, CLINIC, now)
            assert len(observed["viec_qua_han"]) == ag.TRAN
            await ag.ap_dung(
                conn, CLINIC, {"viec_qua_han": observed["viec_qua_han"]}, set()
            )
            falsely_closed = await conn.fetchval(
                "SELECT count(*) FROM agent_nhan_dinh a JOIN work_item w"
                " ON a.khoa=w.id::text AND a.clinic_id=w.clinic_id"
                " WHERE w.id=ANY($1::uuid[]) AND w.status='PENDING'"
                " AND w.due_at<now() AND a.ly_do_dong='HET'",
                ids,
            )
            assert falsely_closed == 0, "Unobserved overdue work was declared resolved"
        finally:
            await tx.rollback()
