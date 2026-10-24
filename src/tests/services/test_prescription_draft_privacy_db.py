"""Draft privacy holds at the database, not just behind the Next proxy.

Since 20261022900000 (khoá /rest/v1) `authenticated` reads nothing from
clinical_record and cannot call read_prescription_draft over /rpc either:
FastAPI reads drafts as the database owner.
"""

from __future__ import annotations

import os

import asyncpg
import pytest

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_draft_not_readable_through_postgrest() -> None:
    url = os.environ.get("DATABASE_URL_TEST")
    if not url:
        pytest.skip("requires explicitly disposable, migrated DATABASE_URL_TEST")
    conn = await asyncpg.connect(url)
    try:
        allowed = await conn.fetchrow(
            """SELECT
                 has_table_privilege('authenticated',
                                     'public.clinical_record', 'SELECT') AS whole,
                 has_column_privilege('authenticated', 'public.clinical_record',
                                      'soap_assessment', 'SELECT') AS chart,
                 has_column_privilege('authenticated', 'public.clinical_record',
                                      'prescription_draft', 'SELECT') AS draft,
                 has_function_privilege('authenticated',
                                        'public.read_prescription_draft(uuid)',
                                        'EXECUTE') AS checked,
                 has_function_privilege('anon',
                                        'public.read_prescription_draft(uuid)',
                                        'EXECUTE') AS anonymous
            """
        )
        assert allowed == (False, False, False, False, False)
        # The database, not just the Next proxy, refuses the direct read.
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE authenticated")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetch(
                    "SELECT prescription_draft FROM public.clinical_record"
                )
    finally:
        await conn.close()
