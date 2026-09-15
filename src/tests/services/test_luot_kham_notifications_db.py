"""Workflow invalidation commits contain only table and tenant identifiers."""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from clinicai.core.change_broker import CHANNEL, ChangeBroker
from tests.services.test_luot_kham_service_db import KichBan, _vao_kham

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

TABLES = {
    "encounter_flow",
    "vital_measurement",
    "consultation",
    "consultation_note",
    "service_order",
    "queue_entry",
    "review_round",
    "round_requirement",
}


async def test_workflow_triggers_notify_after_commit_without_content(
    kb: KichBan,
) -> None:
    consultation = await _vao_kham(kb)
    migration = (
        Path(__file__).resolve().parents[3]
        / "supabase/migrations/20260915000006_luot_kham_notifications.sql"
    )
    await kb.pool.execute(migration.read_text())
    triggers = await kb.pool.fetch(
        "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid"
        " JOIN pg_proc p ON p.oid = t.tgfoid"
        " WHERE p.proname = 'notify_row_change' AND t.tgtype = 29"
        " AND c.relname = ANY($1::text[]) AND NOT t.tgisinternal",
        list(TABLES),
    )
    assert {row["relname"] for row in triggers} == TABLES
    broker = ChangeBroker("postgresql://unused")
    own = broker.subscribe(kb.bac_si.clinic_id)
    other = broker.subscribe(str(uuid4()))
    async with kb.pool.acquire() as listener:
        await listener.add_listener(CHANNEL, broker._on_notify)
        try:
            async with kb.pool.acquire() as writer, writer.transaction():
                await writer.execute(
                    "INSERT INTO consultation_note (clinic_id, consultation_id,"
                    " body, recorded_by) VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
                    kb.bac_si.clinic_id,
                    consultation,
                    "Confidential dictated clinical text",
                    kb.thu_ky.staff_id,
                )
                assert own.empty()
            payload = json.loads(await asyncio.wait_for(own.get(), timeout=2))
            assert payload == {"t": "consultation_note", "c": kb.bac_si.clinic_id}
            assert other.empty()
        finally:
            await listener.remove_listener(CHANNEL, broker._on_notify)
