"""The workspace worklist — the query behind a front desk's board.

The bug worth guarding here is the one that shipped and was caught by the clock
rolling over during development: the queue filtered on created_at::date = today,
so at midnight the board emptied itself while people were still sitting in the
waiting room. Open work does not stop being open because a calendar day ended.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.work_item_service import WorkItemService

IDENTITY = StaffIdentity(
    staff_id="11111111-1111-4111-8111-111111111111",
    auth_user_id="22222222-2222-4222-8222-222222222222",
    full_name="Lễ tân test",
    department="RECEPTION",
    role=ClinicRole.RECEPTION,
    clinic_id="a0000000-0000-4000-8000-000000000001",
)


def _pool(rows: list[dict[str, Any]] | None = None) -> MagicMock:
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=rows or [])
    return pool


async def _call(pool: MagicMock, **kw: Any) -> None:
    await WorkItemService(pool).list_worklist(
        workspace="bang_dieu_phoi", identity=IDENTITY, **kw
    )


@pytest.mark.asyncio
async def test_queue_does_not_empty_itself_at_midnight() -> None:
    """With no date, the board shows every open item, whenever it was created.

    A patient who arrives at 23:50 and is still waiting at 00:10 must stay on
    the desk's screen. She is the one person the queue cannot afford to lose.
    """
    pool = _pool()
    await _call(pool)

    sql, *params = pool.fetch.call_args.args
    assert "$2::date IS NULL" in sql, "the date filter must be optional"
    assert params[1] is None


@pytest.mark.asyncio
async def test_an_explicit_date_still_narrows_to_that_day() -> None:
    """Looking back at a particular day stays possible."""
    pool = _pool()
    await _call(pool, day=date(2026, 7, 31))

    sql, *params = pool.fetch.call_args.args
    assert "Asia/Ho_Chi_Minh" in sql, "the clinic's day, not the server's"
    assert params[1] == date(2026, 7, 31)


@pytest.mark.asyncio
async def test_only_open_work_is_queued() -> None:
    """A queue is what is left to do; finished steps are history."""
    pool = _pool()
    await _call(pool)

    sql, *_ = pool.fetch.call_args.args
    assert "w.status IN ('PENDING', 'IN_PROGRESS')" in sql


@pytest.mark.asyncio
async def test_the_board_is_defined_by_the_catalogue_not_by_python() -> None:
    """Filtering on node_definition.workspace keeps boards data-driven.

    A clinic that moves a step onto its reception desk edits a row, not this
    service — the same reason instantiation walks node_dependency instead of
    carrying a hard-coded spine.
    """
    pool = _pool()
    await _call(pool)

    sql, *params = pool.fetch.call_args.args
    assert "n.workspace = $1" in sql
    assert params[0] == "bang_dieu_phoi"


@pytest.mark.asyncio
async def test_scoped_to_the_callers_clinic_and_active_membership() -> None:
    """The backend bypasses RLS, so this join is the only tenant boundary."""
    pool = _pool()
    await _call(pool)

    sql, *params = pool.fetch.call_args.args
    assert "clinic_membership" in sql
    assert "m.is_active" in sql
    assert "w.clinic_id = $3::uuid" in sql
    assert params[2] == IDENTITY.clinic_id
    assert params[3] == IDENTITY.staff_id
    assert params[4] == IDENTITY.role.value


@pytest.mark.asyncio
async def test_actionability_reads_the_live_definition() -> None:
    """Same rule as the visit board: issue() authorises from node_definition.

    Deciding "yours to do" from anything else would light up a button the gate
    then refuses.
    """
    pool = _pool()
    await _call(pool)

    sql, *_ = pool.fetch.call_args.args
    assert "node_definition n" in sql
    assert "snapshot" not in sql
