"""DB-004: a shared historical catalogue function changes unrelated clinics.

Synthetic data, wrapper-created database only. This deliberately RED invariant
does not claim normal migration runners replay already-recorded migrations.
"""

from __future__ import annotations

import json
import os
import uuid
from urllib.parse import urlsplit

import asyncpg
import pytest

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_catalogue_bootstrap_preserves_independent_clinic_items() -> None:
    """Both independently configured clinics should keep their own items."""
    dsn = os.environ["DATABASE_URL_TEST"]
    assert urlsplit(dsn).path.removeprefix("/").startswith("tam_")
    conn = await asyncpg.connect(dsn)
    outer = conn.transaction()
    await outer.start()
    try:
        clinics = [uuid.uuid4(), uuid.uuid4()]
        drugs = [uuid.uuid4(), uuid.uuid4()]
        for clinic, drug in zip(clinics, drugs, strict=True):
            await conn.execute(
                "INSERT INTO clinic(id,code,name) VALUES($1,$2,'AUDIT clinic')",
                clinic,
                "AUD" + clinic.hex[:12],
            )
            await conn.execute(
                "INSERT INTO drug_catalog"
                " (id,clinic_id,name_raw,name_base,unit_price,is_active)"
                " VALUES($1,$2,'AUDIT independent item','AUDIT independent item',"
                "12345,true)",
                drug,
                clinic,
            )
        await conn.execute("SELECT public.chuan_hoa_danh_muc_thuoc_kiotviet()")
        states = []
        for clinic, drug in zip(clinics, drugs, strict=True):
            states.append(
                {
                    "original_active": await conn.fetchval(
                        "SELECT is_active FROM drug_catalog WHERE id=$1", drug
                    ),
                    "rows_after": await conn.fetchval(
                        "SELECT count(*) FROM drug_catalog WHERE clinic_id=$1",
                        clinic,
                    ),
                }
            )
        print(json.dumps({"finding": "DB-004", "synthetic_clinics": states}))
        assert all(s["original_active"] and s["rows_after"] == 1 for s in states)
    finally:
        await outer.rollback()
        await conn.close()
