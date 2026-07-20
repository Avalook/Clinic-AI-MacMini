"""Unit tests for staff_capability service helpers (P9.6).

Pattern: mock-pool — no live DB. Each test programs `pool.acquire()` to
return a connection whose `fetchrow` / `fetch` side_effect drives the
service behaviour. Mirrors the project's existing scheduling /
patient-context test patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from clinicai.schemas.staff import (
    Capability,
    ProficiencyLevel,
    StaffCapabilityDTO,
)
from clinicai.services.staff_service import (
    add_capability,
    get_staff_by_capability,
)

_NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def _mock_pool_with_fetchrow(row: dict[str, Any]) -> MagicMock:
    pool = MagicMock()
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool


def _mock_pool_with_fetch(rows: list[dict[str, Any]]) -> MagicMock:
    pool = MagicMock()
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows)
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool


def _capability_row(
    *,
    staff_id: UUID,
    capability: str = Capability.PHLEBOTOMY.value,
    proficiency_level: str = ProficiencyLevel.COMPETENT.value,
) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "staff_id": staff_id,
        "capability": capability,
        "proficiency_level": proficiency_level,
        "created_at": _NOW,
    }


# ---- add_capability ---------------------------------------------------------


@pytest.mark.asyncio
async def test_add_capability__ok() -> None:
    """Insert a new (staff_id, capability) row → service returns the DTO."""
    staff_id = uuid4()
    expected = _capability_row(staff_id=staff_id)
    pool = _mock_pool_with_fetchrow(expected)

    dto = await add_capability(
        pool,
        staff_id=staff_id,
        capability=Capability.PHLEBOTOMY.value,
        proficiency_level=ProficiencyLevel.COMPETENT.value,
    )

    assert isinstance(dto, StaffCapabilityDTO)
    assert dto.staff_id == staff_id
    assert dto.capability == "PHLEBOTOMY"
    assert dto.proficiency_level == "COMPETENT"
    # The query argument list is positional: (staff_id, capability, level)
    conn_mock = pool.acquire.return_value.__aenter__.return_value
    args = conn_mock.fetchrow.await_args.args
    assert args[1] == staff_id
    assert args[2] == "PHLEBOTOMY"
    assert args[3] == "COMPETENT"


@pytest.mark.asyncio
async def test_add_capability__upsert() -> None:
    """Insert with conflict → ON CONFLICT updates proficiency_level, returns row.

    We don't replay the DB constraint here (mock-pool); instead we verify
    the SQL pinned by the service contains the upsert clause and that the
    service surfaces the row asyncpg returns.
    """
    from clinicai.services import staff_service as _svc

    sql = _svc._ADD_CAPABILITY_SQL
    assert "ON CONFLICT (staff_id, capability) DO UPDATE" in sql
    assert "SET proficiency_level = EXCLUDED.proficiency_level" in sql

    staff_id = uuid4()
    upgraded = _capability_row(
        staff_id=staff_id, proficiency_level=ProficiencyLevel.EXPERT.value
    )
    pool = _mock_pool_with_fetchrow(upgraded)

    # Call twice with the same (staff_id, capability) but escalating
    # proficiency — second call should not raise (upsert semantics) and
    # must return the updated proficiency.
    await add_capability(
        pool,
        staff_id=staff_id,
        capability=Capability.PHLEBOTOMY.value,
        proficiency_level=ProficiencyLevel.COMPETENT.value,
    )
    dto = await add_capability(
        pool,
        staff_id=staff_id,
        capability=Capability.PHLEBOTOMY.value,
        proficiency_level=ProficiencyLevel.EXPERT.value,
    )

    assert dto.proficiency_level == "EXPERT"


# ---- get_staff_by_capability ------------------------------------------------


def _on_duty_row(
    *,
    full_name: str,
    capability: str = Capability.PHLEBOTOMY.value,
    proficiency_level: str = ProficiencyLevel.COMPETENT.value,
) -> dict[str, Any]:
    return {
        "staff_id": uuid4(),
        "full_name": full_name,
        "short_name": full_name.split()[-1],
        "primary_department": "NURSE_ULTRASOUND",
        "capability": capability,
        "proficiency_level": proficiency_level,
    }


@pytest.mark.asyncio
async def test_get_staff_by_capability__filters_training() -> None:
    """exclude_training=True → SQL excludes is_training=TRUE rows.

    Trainee rows never come back from the mocked fetch (we model the SQL
    filter at the mock layer). The assertion verifies the service forwards
    `exclude_training=True` as a query parameter so the SQL filter fires.
    """
    location_id = uuid4()
    # Mock returns only non-trainees — simulating the SQL filter result.
    pool = _mock_pool_with_fetch([_on_duty_row(full_name="Y tá A")])

    rows = await get_staff_by_capability(
        pool,
        capability=Capability.PHLEBOTOMY.value,
        location_id=location_id,
        exclude_training=True,
    )

    assert len(rows) == 1
    assert rows[0]["full_name"] == "Y tá A"

    conn_mock = pool.acquire.return_value.__aenter__.return_value
    args = conn_mock.fetch.await_args.args
    # Args: (sql, capability, location_id, exclude_training)
    assert args[1] == "PHLEBOTOMY"
    assert args[2] == location_id
    assert args[3] is True
    # And the SQL must include the trainee guard so the flag actually does work.
    from clinicai.services import staff_service as _svc

    assert "s.is_training = FALSE" in _svc._GET_BY_CAPABILITY_SQL


@pytest.mark.asyncio
async def test_get_staff_by_capability__filters_inactive() -> None:
    """SQL hard-filters is_active=TRUE; inactive staff never come back.

    Verified by (a) asserting the SQL contains the `is_active = TRUE` clause
    and (b) the mock returning only active staff yields exactly those rows.
    """
    from clinicai.services import staff_service as _svc

    assert "s.is_active = TRUE" in _svc._GET_BY_CAPABILITY_SQL

    location_id = uuid4()
    # Mock returns two active staff; the inactive ones were already filtered
    # by the SQL clause that the service pinned.
    pool = _mock_pool_with_fetch(
        [
            _on_duty_row(full_name="Y tá A"),
            _on_duty_row(full_name="Y tá B"),
        ]
    )

    rows = await get_staff_by_capability(
        pool,
        capability=Capability.PHLEBOTOMY.value,
        location_id=location_id,
        exclude_training=True,
    )

    assert len(rows) == 2
    assert {r["full_name"] for r in rows} == {"Y tá A", "Y tá B"}
