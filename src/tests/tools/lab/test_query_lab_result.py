"""Unit tests for lab.query_lab_result (mocked asyncpg pool).

Tests follow the repo's established tool-test pattern (see
`src/tests/tools/scheduling/test_find_work_sessions.py`): the asyncpg pool is
mocked, and assertions exercise the SQL composition (WHERE clauses, params,
ORDER BY whitelist) plus Pydantic validation. The DB-level filter behaviour
is exercised indirectly — parameterized SQL is trusted to filter correctly
once the params are right.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from clinicai.tools._common.context import new_trace
from clinicai.tools.lab.query_lab_result import (
    LabResultRow,
    QueryLabResultFilter,
    query_lab_result,
)

_NOW = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)


def _make_row(
    *,
    patient_id: UUID,
    test_code: str = "HBV",
    test_name: str = "Hepatitis B surface Ag",
    triage_group: str = "GROUP_A",
    received_at: datetime | None = None,
    is_finalized: bool = False,
) -> dict:
    return {
        "lab_result_id": uuid4(),
        "clinic_patient_id": patient_id,
        "visit_id": None,
        "appointment_id": None,
        "test_code": test_code,
        "test_name": test_name,
        "panel_code": None,
        "result_value": "Negative",
        "result_numeric": None,
        "result_unit": None,
        "reference_range_low": None,
        "reference_range_high": None,
        "flag": "NORMAL",
        "triage_group": triage_group,
        "triage_reason": None,
        "requires_doctor_review": False,
        "reviewed_by_staff_id": None,
        "reviewed_at": None,
        "is_finalized": is_finalized,
        "lab_provider": None,
        "sample_collected_at": None,
        "result_received_at": received_at or _NOW,
    }


def _mock_pool(rows: list[dict]) -> tuple[MagicMock, AsyncMock]:
    """Build a MagicMock pool whose `pool.acquire()` async-context yields a
    connection whose `.fetch(...)` returns the given rows.
    """
    pool = MagicMock()
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows)
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    return pool, conn


@pytest.mark.asyncio
async def test_query_lab_result__only_patient_id__returns_all_for_patient() -> None:
    """No optional filters → SQL has only the patient_id where-clause."""
    patient_a = uuid4()
    rows = [_make_row(patient_id=patient_a) for _ in range(3)]
    pool, conn = _mock_pool(rows)

    out = await query_lab_result(
        pool,
        QueryLabResultFilter(clinic_patient_id=patient_a),
        new_trace(),
    )

    assert len(out) == 3
    assert all(isinstance(r, LabResultRow) for r in out)
    assert all(r.clinic_patient_id == patient_a for r in out)

    sql, *params = conn.fetch.call_args.args
    assert "WHERE clinic_patient_id = $1" in sql
    # Only patient_id + limit → 2 params total
    assert len(params) == 2
    assert params[0] == patient_a
    assert params[1] == 50  # default limit


@pytest.mark.asyncio
async def test_query_lab_result__filter_by_group_c__only_group_c_rows() -> None:
    """`group=GROUP_C` adds the triage_group filter clause + param."""
    patient = uuid4()
    rows = [_make_row(patient_id=patient, triage_group="GROUP_C")]
    pool, conn = _mock_pool(rows)

    out = await query_lab_result(
        pool,
        QueryLabResultFilter(clinic_patient_id=patient, group="GROUP_C"),
        new_trace(),
    )

    assert len(out) == 1
    assert out[0].triage_group == "GROUP_C"

    sql, *params = conn.fetch.call_args.args
    assert "triage_group = $2" in sql
    assert "GROUP_C" in params


@pytest.mark.asyncio
async def test_query_lab_result__filter_by_test_code__exact_match() -> None:
    """`test_code=HBV` adds the test_code filter clause + param."""
    patient = uuid4()
    rows = [_make_row(patient_id=patient, test_code="HBV")]
    pool, conn = _mock_pool(rows)

    out = await query_lab_result(
        pool,
        QueryLabResultFilter(clinic_patient_id=patient, test_code="HBV"),
        new_trace(),
    )

    assert len(out) == 1
    assert out[0].test_code == "HBV"

    sql, *params = conn.fetch.call_args.args
    assert "test_code = $2" in sql
    assert "HBV" in params


@pytest.mark.asyncio
async def test_query_lab_result__date_range__within_range_only() -> None:
    """`date_from` + `date_to` add two filter clauses bound to result_received_at."""
    patient = uuid4()
    d_from = _NOW - timedelta(days=7)
    d_to = _NOW
    rows = [
        _make_row(patient_id=patient, received_at=_NOW - timedelta(days=5)),
        _make_row(patient_id=patient, received_at=_NOW - timedelta(days=1)),
    ]
    pool, conn = _mock_pool(rows)

    out = await query_lab_result(
        pool,
        QueryLabResultFilter(
            clinic_patient_id=patient,
            date_from=d_from,
            date_to=d_to,
        ),
        new_trace(),
    )

    assert len(out) == 2

    sql, *params = conn.fetch.call_args.args
    assert "result_received_at >= $2" in sql
    assert "result_received_at <= $3" in sql
    assert d_from in params
    assert d_to in params


@pytest.mark.asyncio
async def test_query_lab_result__limit_respected() -> None:
    """Custom `limit` propagates as the last bound parameter and into LIMIT $N."""
    patient = uuid4()
    rows = [_make_row(patient_id=patient) for _ in range(2)]
    pool, conn = _mock_pool(rows)

    out = await query_lab_result(
        pool,
        QueryLabResultFilter(clinic_patient_id=patient, limit=2),
        new_trace(),
    )

    assert len(out) == 2

    sql, *params = conn.fetch.call_args.args
    # limit is always the last param
    assert params[-1] == 2
    assert "LIMIT $2" in sql


@pytest.mark.asyncio
async def test_query_lab_result__order_desc_default__newest_first() -> None:
    """Default order_by emits `result_received_at DESC`; rows are returned in
    whatever order the DB yields — caller assertion is that the SQL is correct.
    """
    patient = uuid4()
    newer = _make_row(patient_id=patient, received_at=_NOW)
    older = _make_row(patient_id=patient, received_at=_NOW - timedelta(days=3))
    pool, conn = _mock_pool([newer, older])

    out = await query_lab_result(
        pool,
        QueryLabResultFilter(clinic_patient_id=patient),
        new_trace(),
    )

    sql = conn.fetch.call_args.args[0]
    assert "ORDER BY result_received_at DESC" in sql
    # DB-returned order is preserved by the tool.
    assert out[0].result_received_at >= out[-1].result_received_at


@pytest.mark.asyncio
async def test_query_lab_result__no_results__returns_empty_list() -> None:
    """Empty fetch result → empty list, no exception."""
    patient = uuid4()
    pool, conn = _mock_pool([])

    out = await query_lab_result(
        pool,
        QueryLabResultFilter(clinic_patient_id=patient),
        new_trace(),
    )

    assert out == []
    assert conn.fetch.await_count == 1


def test_query_lab_result__invalid_limit__pydantic_validation_error() -> None:
    """`limit=0` violates the ge=1 constraint and must fail validation."""
    with pytest.raises(ValidationError):
        QueryLabResultFilter(clinic_patient_id=uuid4(), limit=0)


# ---------------------------------------------------------------------------
# Extra defence-in-depth: ORDER BY whitelist is the only injection vector,
# so make sure the Literal type rejects arbitrary strings at the schema layer.
# ---------------------------------------------------------------------------


def test_query_lab_result__invalid_order_by__pydantic_validation_error() -> None:
    """ORDER BY whitelist enforced by the Literal type — non-listed value fails."""
    with pytest.raises(ValidationError):
        QueryLabResultFilter(
            clinic_patient_id=uuid4(),
            order_by="received_at_desc; DROP TABLE lab_result --",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_query_lab_result__row_decimal_fields_roundtrip() -> None:
    """Decimal columns round-trip through Pydantic without coercion errors."""
    patient = uuid4()
    row = _make_row(patient_id=patient)
    row["result_numeric"] = Decimal("4.2")
    row["reference_range_low"] = Decimal("1.0")
    row["reference_range_high"] = Decimal("5.0")
    pool, _ = _mock_pool([row])

    out = await query_lab_result(
        pool,
        QueryLabResultFilter(clinic_patient_id=patient),
        new_trace(),
    )

    assert out[0].result_numeric == Decimal("4.2")
    assert out[0].reference_range_low == Decimal("1.0")
    assert out[0].reference_range_high == Decimal("5.0")
