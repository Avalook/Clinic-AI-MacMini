"""Tool: lab.query_lab_result — filtered read of the lab_result table.

Pure read-only query helper used by the lab_triage sub-graph (P9.2) and other
callers that need a thin view over `lab_result`. The function is parameterized
end-to-end (no f-string SQL value interpolation) and uses a whitelist for the
ORDER BY clause to keep the query injection-safe.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from clinicai.tools._common.context import TraceContext

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

TriageGroup = Literal["GROUP_A", "GROUP_B", "GROUP_C", "PENDING"]
OrderBy = Literal["received_at_desc", "received_at_asc"]

_ORDER_BY_MAP: dict[str, str] = {
    "received_at_desc": "result_received_at DESC",
    "received_at_asc": "result_received_at ASC",
}

_SELECT_COLUMNS = (
    "lab_result_id, clinic_patient_id, visit_id, appointment_id, "
    "test_code, test_name, panel_code, "
    "result_value, result_numeric, result_unit, "
    "reference_range_low, reference_range_high, flag, "
    "triage_group, triage_reason, "
    "requires_doctor_review, reviewed_by_staff_id, reviewed_at, is_finalized, "
    "lab_provider, sample_collected_at, result_received_at"
)


class LabResultRow(BaseModel):
    """Thin projection of a `lab_result` row.

    Mirrors the columns declared in migration 015 (see
    `src/migrations/20260521_015_create_lab_result.sql`).
    """

    model_config = ConfigDict(from_attributes=True)

    lab_result_id: UUID
    clinic_patient_id: UUID
    visit_id: UUID | None
    appointment_id: UUID | None
    test_code: str
    test_name: str
    panel_code: str | None
    result_value: str | None
    result_numeric: Decimal | None
    result_unit: str | None
    reference_range_low: Decimal | None
    reference_range_high: Decimal | None
    flag: str | None
    triage_group: TriageGroup
    triage_reason: str | None
    requires_doctor_review: bool
    reviewed_by_staff_id: UUID | None
    reviewed_at: datetime | None
    is_finalized: bool
    lab_provider: str | None
    sample_collected_at: datetime | None
    result_received_at: datetime


class QueryLabResultFilter(BaseModel):
    """Filter set for `query_lab_result`.

    `group` maps to the `triage_group` column. `is_finalized` replaces the
    original spec's free-form `status` field — the schema only exposes a
    boolean finalization flag, not a status string.
    """

    clinic_patient_id: UUID
    test_code: str | None = None
    group: TriageGroup | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    is_finalized: bool | None = None
    limit: int = Field(default=50, ge=1, le=500)
    order_by: OrderBy = "received_at_desc"


async def query_lab_result(
    pool: asyncpg.Pool,
    filters: QueryLabResultFilter,
    trace: TraceContext,
) -> list[LabResultRow]:
    """Query `lab_result` with optional filters.

    Pure read-only. No side effects, no LLM, no event writes. Callers are
    expected to inject the asyncpg pool and a trace context.

    Args:
        pool: asyncpg connection pool (caller-managed lifecycle).
        filters: validated filter set; `clinic_patient_id` is mandatory.
        trace: per-invocation TraceContext for observability.

    Returns:
        List of `LabResultRow` matching the filters, possibly empty.

    Raises:
        asyncpg errors propagate unchanged — no domain wrapping.
    """
    where_clauses: list[str] = ["clinic_patient_id = $1"]
    params: list[object] = [filters.clinic_patient_id]
    idx = 2

    if filters.test_code is not None:
        where_clauses.append(f"test_code = ${idx}")
        params.append(filters.test_code)
        idx += 1

    if filters.group is not None:
        where_clauses.append(f"triage_group = ${idx}")
        params.append(filters.group)
        idx += 1

    if filters.date_from is not None:
        where_clauses.append(f"result_received_at >= ${idx}")
        params.append(filters.date_from)
        idx += 1

    if filters.date_to is not None:
        where_clauses.append(f"result_received_at <= ${idx}")
        params.append(filters.date_to)
        idx += 1

    if filters.is_finalized is not None:
        where_clauses.append(f"is_finalized = ${idx}")
        params.append(filters.is_finalized)
        idx += 1

    order_by_sql = _ORDER_BY_MAP[filters.order_by]
    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM lab_result "
        f"WHERE {' AND '.join(where_clauses)} "
        f"ORDER BY {order_by_sql} "
        f"LIMIT ${idx}"
    )
    params.append(filters.limit)

    logger.debug(
        "tool.lab.query_lab_result",
        extra={
            "trace_id": str(trace.trace_id),
            "clinic_patient_id": str(filters.clinic_patient_id),
            "filter_count": len(where_clauses),
            "limit": filters.limit,
        },
    )

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [LabResultRow.model_validate(dict(row)) for row in rows]
