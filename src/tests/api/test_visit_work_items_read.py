"""The visit work-item board: what it shows, in what order, to whom.

The read path has to agree with the write path. `issue()` authorises against the
LIVE node_definition, so if this endpoint decided "actionable" from the pinned
node_definition_version.snapshot instead, an item could look actionable to a
role the gate then refuses — a button that is enabled and always errors.
"""

from __future__ import annotations

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
    location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
    location_name="Kim Ngưu",
)


def _row(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "33333333-3333-4333-8333-333333333333",
        "node_code": "LUOTKHAM-02",
        "status": "PENDING",
        "priority": "P0",
        "version": 1,
        "assigned_role": None,
        "assigned_to": None,
        "started_at": None,
        "finished_at": None,
        "node_name": "Xác minh người bệnh",
        "flow_group": "tiep_nhan",
        "workspace": "bang_dieu_phoi",
        "actor_roles": ["RECEPTION"],
        "actionable_by_me": True,
        "blocked": False,
        "clinic_patient_id": "55555555-5555-4555-8555-555555555555",
        "patient_code": "BN-000123",
        "full_name": "Trần Hồng Dung",
        "date_of_birth": None,
        "gender": "Nữ",
        "phone_primary": "0900016081",
    }
    base.update(over)
    return base


def _pool(rows: list[dict[str, Any]]) -> MagicMock:
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=rows)
    return pool


@pytest.mark.asyncio
async def test_returns_the_board_fields_a_client_needs() -> None:
    pool = _pool([_row()])
    out = await WorkItemService(pool).list_for_visit(
        visit_id="44444444-4444-4444-8444-444444444444", identity=IDENTITY
    )

    assert len(out) == 1
    item = out[0]
    # actionable_by_me and blocked are the difference between a button that is
    # hidden, greyed out, or live. Computed here so every client draws it the
    # same way instead of each re-implementing the rule.
    assert item["actionable_by_me"] is True
    assert item["blocked"] is False
    assert item["node_name"] == "Xác minh người bệnh"
    assert item["actor_roles"] == ["RECEPTION"]


@pytest.mark.asyncio
async def test_each_step_names_the_patient_it_is_about() -> None:
    """A screen that acts on a visit has to be able to name the patient.

    The order composer read this endpoint and had nothing to show, so a doctor
    could pick an ultrasound for an unnamed visit — a wrong-patient risk, not a
    blank field. Same shape as list_worklist so no client learns two of them.
    """
    pool = _pool([_row()])
    out = await WorkItemService(pool).list_for_visit(
        visit_id="44444444-4444-4444-8444-444444444444", identity=IDENTITY
    )

    patient = out[0]["patient"]
    assert isinstance(patient, dict)
    assert patient["full_name"] == "Trần Hồng Dung"
    assert patient["patient_code"] == "BN-000123"

    # The join must be tenant-scoped like every other one here: the backend
    # bypasses RLS, so an unqualified patient join would reach across clinics.
    sql, *_ = pool.fetch.call_args.args
    assert "LEFT JOIN patient p" in sql
    assert "p.clinic_id = w.clinic_id" in sql


@pytest.mark.asyncio
async def test_query_is_scoped_to_the_callers_clinic_and_membership() -> None:
    """The backend bypasses RLS; this join is the only tenant boundary."""
    pool = _pool([])
    await WorkItemService(pool).list_for_visit(
        visit_id="44444444-4444-4444-8444-444444444444", identity=IDENTITY
    )

    sql, *params = pool.fetch.call_args.args
    assert "clinic_membership" in sql
    assert "w.clinic_id = $2::uuid" in sql
    assert params[1] == IDENTITY.clinic_id
    assert params[2] == IDENTITY.staff_id
    assert params[3] == IDENTITY.role.value


@pytest.mark.asyncio
async def test_authorisation_reads_the_live_definition_not_the_pinned_snapshot() -> (
    None
):
    """Pinning is for history; authorisation is live.

    issue() resolves actor_roles from node_definition. Showing the snapshot's
    roles here would let the board offer a step the gate then rejects.
    """
    pool = _pool([])
    await WorkItemService(pool).list_for_visit(
        visit_id="44444444-4444-4444-8444-444444444444", identity=IDENTITY
    )

    sql, *_ = pool.fetch.call_args.args
    assert "node_definition n" in sql
    assert "snapshot" not in sql


@pytest.mark.asyncio
async def test_normal_roles_only_receive_their_own_visit_nodes() -> None:
    """A visit UUID must not turn one active task into cross-station PII.

    The route guard establishes there is an active role-owned task.  This query
    remains row-scoped afterwards, so a receptionist cannot receive doctor or
    cashier work just because they legitimately own a reception step.
    """
    pool = _pool([])
    await WorkItemService(pool).list_for_visit(
        visit_id="44444444-4444-4444-8444-444444444444", identity=IDENTITY
    )

    sql, *_ = pool.fetch.call_args.args
    assert "AND (m.role IN ('MANAGEMENT', 'TRUONG_CA')" in sql
    assert "OR m.role = ANY(n.actor_roles))" in sql
    assert "cardinality(n.actor_roles) = 0" not in sql
    assert "n.actor_roles IS NULL" not in sql


@pytest.mark.asyncio
async def test_board_is_ordered_by_flow_not_alphabetically() -> None:
    """Ordering by flow_group put "tạo chỉ định" above the check-in.

    The groups sort kham < sinh_hieu < thu_ngan < tiep_nhan, which is the day
    backwards. Depth from a node nothing depends on gives the real order for
    any catalogue, so the assertion is on the mechanism, not on a code list.
    """
    pool = _pool([])
    await WorkItemService(pool).list_for_visit(
        visit_id="44444444-4444-4444-8444-444444444444", identity=IDENTITY
    )

    sql, *_ = pool.fetch.call_args.args
    assert "ORDER BY f.level" in sql
    assert "ORDER BY n.flow_group" not in sql


@pytest.mark.asyncio
async def test_cancelled_items_are_not_on_the_board() -> None:
    """An undone arrival leaves cancelled rows as history.

    Showing them would put work on the board that nobody is expected to do.
    """
    pool = _pool([])
    await WorkItemService(pool).list_for_visit(
        visit_id="44444444-4444-4444-8444-444444444444", identity=IDENTITY
    )

    sql, *_ = pool.fetch.call_args.args
    assert "w.status <> 'CANCELLED'" in sql
