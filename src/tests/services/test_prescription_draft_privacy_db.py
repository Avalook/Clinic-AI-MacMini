"""Column grants enforce draft privacy even through direct PostgREST SELECT."""

from __future__ import annotations

import os

import asyncpg
import pytest

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_draft_column_needs_checked_rpc_not_raw_table_read() -> None:
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
        assert allowed == (False, True, False, True, False)
        # The database, not just the Next proxy, refuses the direct read.
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE authenticated")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetch(
                    "SELECT prescription_draft FROM public.clinical_record"
                )
    finally:
        await conn.close()
