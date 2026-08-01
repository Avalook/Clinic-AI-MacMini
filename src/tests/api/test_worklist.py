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
from fastapi import HTTPException

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.work_items import (
    require_visit_work_items_read_access,
    require_workspace_read_access,
)
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


@pytest.mark.asyncio
async def test_a_role_cannot_read_an_unrelated_workspace_by_typing_its_name() -> None:
    """The board's query parameter is not an authorization boundary.

    A CSKH login is allowed to authenticate to the general work-item API, but
    it cannot use ``workspace=khu_bac_si`` to obtain another station's patient
    queue.  This check must happen before the service reads the worklist.
    """
    pool = _pool()
    pool.fetchval = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as excinfo:
        await require_workspace_read_access(
            workspace="khu_bac_si", identity=IDENTITY, pool=pool
        )

    assert getattr(excinfo.value, "status_code", None) == 403


@pytest.mark.asyncio
async def test_an_unassigned_workspace_node_does_not_authorize_every_role() -> None:
    """An empty actor list is deliberately *not* a public queue.

    ``node_definition.actor_roles`` defaults to ``{}``, whose schema contract is
    "nobody yet."  Model the dangerous database result here: a query that
    contains the old empty-list bypass would find such a node and return true;
    the fail-closed query must instead receive false and return 403.
    """
    pool = _pool()

    async def _empty_role_node_matches_only_an_unsafe_query(
        sql: str, *_: object
    ) -> bool:
        return "cardinality(n.actor_roles) = 0" in " ".join(sql.split())

    pool.fetchval = AsyncMock(side_effect=_empty_role_node_matches_only_an_unsafe_query)

    with pytest.raises(HTTPException) as excinfo:
        await require_workspace_read_access(
            workspace="bang_dieu_phoi", identity=IDENTITY, pool=pool
        )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_management_can_read_any_configured_workspace_for_coordination() -> None:
    """Management and the shift lead retain the read-only operational view."""
    pool = _pool()
    management = StaffIdentity(**{**IDENTITY.__dict__, "role": ClinicRole.MANAGEMENT})

    await require_workspace_read_access(
        workspace="khu_bac_si", identity=management, pool=pool
    )
    pool.fetchval.assert_not_called()


@pytest.mark.asyncio
async def test_a_workspace_reader_only_receives_nodes_for_its_role() -> None:
    """Opening checkout must not leak reconciliation and payment rows to reception.

    Reception is an actor on LUOTKHAM-15, so it may eventually receive a
    redacted checkout view. It is not an actor on LUOTKHAM-13/14, therefore the
    generic worklist query must scope normal users to their own node rows.
    """
    pool = _pool()
    reception = StaffIdentity(**{**IDENTITY.__dict__, "role": ClinicRole.RECEPTION})
    await WorkItemService(pool).list_worklist(
        workspace="thu_ngan_dong_luot", identity=reception
    )

    sql, *_ = pool.fetch.call_args.args
    assert "AND (m.role IN ('MANAGEMENT', 'TRUONG_CA')" in sql
    assert "OR m.role = ANY(n.actor_roles))" in sql
    assert "cardinality(n.actor_roles) = 0" not in sql
    assert "n.actor_roles IS NULL" not in sql


@pytest.mark.asyncio
async def test_visit_work_items_do_not_become_a_cross_station_patient_lookup() -> None:
    """A raw visit UUID must not bypass the workspace read policy."""
    pool = _pool()
    pool.fetchval = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as excinfo:
        await require_visit_work_items_read_access(
            visit_id="33333333-3333-4333-8333-333333333333",
            identity=IDENTITY,
            pool=pool,
        )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_a_future_or_terminal_role_step_cannot_authorize_visit_pii() -> None:
    """An active reception task must exist before its visit projection opens.

    A routine workflow already has future RECEPTION nodes.  The old ``EXISTS``
    query treated one as enough authorization and then returned clinical and
    cashier rows for the whole visit.  This fake models precisely that positive
    database match: only a query missing the live-status predicate gets true.
    """
    pool = _pool()

    async def _future_or_terminal_step_matches_only_an_unsafe_query(
        sql: str, *_: object
    ) -> bool:
        normalized = " ".join(sql.split())
        return (
            "$3 = ANY(n.actor_roles)" in normalized
            and "w.status = 'IN_PROGRESS'" not in normalized
            and "w.status = 'PENDING'" not in normalized
        )

    pool.fetchval = AsyncMock(
        side_effect=_future_or_terminal_step_matches_only_an_unsafe_query
    )

    with pytest.raises(HTTPException) as excinfo:
        await require_visit_work_items_read_access(
            visit_id="33333333-3333-4333-8333-333333333333",
            identity=IDENTITY,
            pool=pool,
        )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_a_future_pending_but_blocked_step_cannot_authorize_visit_pii() -> None:
    """Instantiated downstream rows are PENDING before they are ready to work.

    A status check alone is not enough: the workflow creates future nodes as
    PENDING, then its dependency gate keeps them blocked.  Model that exact
    positive result so a regression to status-only authorization grants no
    access in this test.
    """
    pool = _pool()

    async def _blocked_pending_step_matches_only_an_unsafe_query(
        sql: str, *_: object
    ) -> bool:
        normalized = " ".join(sql.split())
        return (
            "w.status IN ('PENDING', 'IN_PROGRESS')" in normalized
            and "work_item_gate_blockers(w.id, 'start')" not in normalized
        )

    pool.fetchval = AsyncMock(
        side_effect=_blocked_pending_step_matches_only_an_unsafe_query
    )

    with pytest.raises(HTTPException) as excinfo:
        await require_visit_work_items_read_access(
            visit_id="33333333-3333-4333-8333-333333333333",
            identity=IDENTITY,
            pool=pool,
        )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_active_owned_step_is_the_only_normal_visit_read_grant() -> None:
    """The visit guard asks SQL for an active step owned by the caller."""
    pool = _pool()
    pool.fetchval = AsyncMock(return_value=True)

    await require_visit_work_items_read_access(
        visit_id="33333333-3333-4333-8333-333333333333",
        identity=IDENTITY,
        pool=pool,
    )

    # await_args is None until the guard actually queries. Asserting that first
    # keeps a guard that never ran from failing as an attribute error.
    awaited = pool.fetchval.await_args
    assert awaited is not None
    normalized = " ".join(awaited.args[0].split())
    assert "w.status = 'IN_PROGRESS'" in normalized
    assert "w.status = 'PENDING'" in normalized
    assert "work_item_gate_blockers(w.id, 'start')" in normalized
    assert "$3 = ANY(n.actor_roles)" in normalized
    assert "cardinality(n.actor_roles) = 0" not in normalized
    assert "n.actor_roles IS NULL" not in normalized
