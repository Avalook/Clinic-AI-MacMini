"""DB-002 observational probe on full exact-main schema, synthetic data only.

Passing means the before/after exposure was reproduced, not that ACL is safe.
Run via scripts/test-nhanh.sh; every insert and grant is rolled back.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
import pytest

pytestmark = [pytest.mark.db, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[3]
CLINIC = uuid.UUID("a0000000-0000-4000-8000-000000000001")


async def _as_nurse(conn: asyncpg.Connection, user: uuid.UUID) -> None:
    """Use the actual PostgREST database role and synthetic JWT subject."""
    await conn.execute("SET LOCAL ROLE authenticated")
    await conn.execute(
        "SELECT set_config('request.jwt.claim.sub', $1, true)", str(user)
    )
    await conn.execute(
        "SELECT set_config('request.jwt.claims', $1, true)",
        json.dumps({"sub": str(user), "role": "authenticated"}),
    )


async def _denied(conn: asyncpg.Connection, query: str, *args: object) -> None:
    """Assert an actual query is denied, isolated by a savepoint."""
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with conn.transaction():
            await conn.fetchval(query, *args)


async def test_restore_grants_expose_draft_and_settings_after_main_hardening() -> None:
    """Observe both sensitive columns before and after exact restore ACL steps."""
    dsn = os.environ["DATABASE_URL_TEST"]
    assert urlsplit(dsn).path.removeprefix("/").startswith("tam_")
    conn = await asyncpg.connect(dsn)
    outer = conn.transaction()
    await outer.start()
    try:
        stock = [
            "drug_batch",
            "inventory_txn",
            "drug_return",
            "phieu_kho",
            "phieu_kho_dong",
            "kiem_ke_ca",
            "kiem_ke_ca_dong",
            "vat_tu_phieu",
            "vat_tu_ton",
            "vat_tu_txn",
            "vat_tu_nhap_cho_duyet",
        ]
        for table in stock:
            assert await conn.fetchval(
                "SELECT to_regclass($1) IS NOT NULL", "public." + table
            )
        user, staff, patient, visit = (uuid.uuid4() for _ in range(4))
        location = await conn.fetchval(
            "SELECT id FROM clinic_location WHERE clinic_id=$1 AND is_active LIMIT 1",
            CLINIC,
        )
        await conn.execute("INSERT INTO auth.users(id) VALUES($1)", user)
        await conn.execute(
            "INSERT INTO staff (id,full_name,primary_department,primary_location_id,"
            "is_active,auth_user_id) VALUES ($1,'AUDIT synthetic nurse',"
            "'NURSE_ULTRASOUND',$2,true,$3)",
            staff,
            location,
            user,
        )
        await conn.execute(
            "INSERT INTO clinic_membership (clinic_id,staff_id,role,is_active) "
            "VALUES ($1,$2,'NURSE_ULTRASOUND',true) ON CONFLICT DO NOTHING",
            CLINIC,
            staff,
        )
        await conn.execute(
            "INSERT INTO patient"
            " (clinic_patient_id,clinic_id,patient_code,full_name,location_id) "
            "VALUES ($1,$2,$3,'AUDIT synthetic patient',$4)",
            patient,
            CLINIC,
            "AUDIT-ACL-" + uuid.uuid4().hex[:12],
            location,
        )
        await conn.execute(
            "INSERT INTO visit (visit_id,clinic_id,clinic_patient_id,status) "
            "VALUES ($1,$2,$3,'OPEN')",
            visit,
            CLINIC,
            patient,
        )
        await conn.execute(
            "INSERT INTO clinical_record"
            " (visit_id,clinic_id,prescription_draft,soap_subjective) "
            "VALUES ($1,$2,$3::jsonb,$4::jsonb)",
            visit,
            CLINIC,
            '{"audit_sentinel":"synthetic_draft"}',
            '{"audit_sentinel":"synthetic_chart"}',
        )
        await conn.execute(
            "UPDATE clinic SET settings = settings || $2::jsonb WHERE id=$1",
            CLINIC,
            '{"audit_sentinel":"synthetic_settings"}',
        )
        await _as_nurse(conn, user)
        assert await conn.fetchval("SELECT current_user") == "authenticated"
        assert await conn.fetchval("SELECT current_staff_id()") == staff
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM clinic_membership WHERE staff_id=$1"
                " AND role <> 'NURSE_ULTRASOUND'",
                staff,
            )
            == 0
        )
        assert (
            await conn.fetchval(
                "SELECT soap_subjective->>'audit_sentinel' FROM clinical_record"
                " WHERE visit_id=$1",
                visit,
            )
            == "synthetic_chart"
        )
        await _denied(
            conn,
            "SELECT prescription_draft FROM clinical_record WHERE visit_id=$1",
            visit,
        )
        await _denied(conn, "SELECT settings FROM clinic WHERE id=$1", CLINIC)
        await conn.execute("RESET ROLE")

        # Exact blanket table/sequence grants in restore scripts at pinned main.
        await conn.execute(
            "GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated, service_role"
        )
        await conn.execute(
            "GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated, service_role"
        )
        for filename in [
            "20261019100000_harden_public_function_acl.sql",
            "20261019120000_restrict_stock_postgrest_reads.sql",
        ]:
            text = (ROOT / "supabase/migrations" / filename).read_text()
            await conn.execute(re.sub(r"(?m)^\s*(BEGIN|COMMIT);\s*$", "", text))
        await _as_nurse(conn, user)
        draft = await conn.fetchval(
            "SELECT prescription_draft->>'audit_sentinel' FROM clinical_record"
            " WHERE visit_id=$1",
            visit,
        )
        settings = await conn.fetchval(
            "SELECT settings->>'audit_sentinel' FROM clinic WHERE id=$1",
            CLINIC,
        )
        assert draft == "synthetic_draft"
        assert settings == "synthetic_settings"
        print(
            json.dumps(
                {
                    "finding": "DB-002",
                    "schema": "full exact main; no placeholder tables",
                    "role": "authenticated",
                    "membership": "NURSE_ULTRASOUND only",
                    "actual_rls_chart_read_before": True,
                    "draft_query_denied_before": True,
                    "settings_query_denied_before": True,
                    "draft_read_after_restore_and_two_acl_migrations": True,
                    "settings_read_after_restore_and_two_acl_migrations": True,
                    "data": "synthetic sentinels only",
                    "cleanup": "outer transaction rollback",
                }
            )
        )
    finally:
        await outer.rollback()
        await conn.close()
