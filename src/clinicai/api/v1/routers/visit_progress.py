"""Progress flags for the day board (ROLE-02, ADR-0012)."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.visit_progress_service import VisitProgressService

router = APIRouter()


class VisitProgressRead(BaseModel):
    appointment_id: str
    visit_id: str | None
    vitals_recorded: bool
    has_clinical_record: bool
    has_prescription: bool
    paid_kinds: list[str]


@router.get("/visits/progress", response_model=list[VisitProgressRead])
async def read_visit_progress(
    date_from: date = Query(..., alias="from", description="Từ ngày (giờ VN)"),
    date_to: date = Query(
        ..., alias="to", description="Đến ngày (giờ VN), gồm cả ngày này"
    ),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[VisitProgressRead]:
    """How far each of today's patients has got: vitals, exam, prescription, fees.

    Open to any signed-in staff member on purpose — it is the progress bar the
    front desk has always seen. What changed is that it returns flags instead of
    the doctor's note, which is what let the note's read policy be closed to
    non-clinical roles.
    """
    rows = await VisitProgressService(pool).for_range(
        date_from=date_from, date_to=date_to, clinic_id=identity.clinic_id
    )
    return [VisitProgressRead(**vars(r)) for r in rows]


# ── Visit workflow progress (C.5) ─────────────────────────────────────


@router.get("/visits/{visit_id}/workflow")
async def visit_workflow_progress(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Full workflow status of a visit: work items + blockers (C.5).

    Returns the visit's current node, all work items with their status,
    and any blockers preventing a work item from starting.
    """
    async with pool.acquire() as conn:
        # Visit header with current_node_code.
        visit = await conn.fetchrow(
            """
            SELECT v.visit_id::text,
                   v.status,
                   v.current_node_code,
                   v.current_node_since,
                   v.previous_node_code,
                   v.checked_in_at,
                   p.full_name AS patient_name,
                   p.patient_code,
                   s.full_name AS doctor_name
              FROM visit v
              JOIN patient p
                ON p.clinic_patient_id = v.clinic_patient_id
              LEFT JOIN staff s
                ON s.id = v.attending_doctor_id
             WHERE v.visit_id = $1::uuid
               AND v.clinic_id = $2::uuid
            """,
            str(visit_id),
            identity.clinic_id,
        )
        if visit is None:
            from clinicai.api.exceptions import NotFoundError

            raise NotFoundError("Lượt khám không tồn tại.")

        # Work items with node name + blockers.
        items = await conn.fetch(
            """
            SELECT w.id::text AS work_item_id,
                   w.node_code,
                   nd.name AS node_name,
                   w.status,
                   w.assigned_role,
                   s.full_name AS assigned_to_name,
                   w.started_at,
                   w.finished_at,
                   w.priority,
                   COALESCE(
                       array_agg(
                           DISTINCT b.blocker_label
                       ) FILTER (
                           WHERE b.blocker_label IS NOT NULL
                       ),
                       '{}'::text[]
                   ) AS blockers
              FROM work_item w
              JOIN node_definition nd
                ON nd.code = w.node_code
               AND nd.clinic_id = w.clinic_id
               AND nd.is_active
              LEFT JOIN staff s
                ON s.id = w.assigned_to
              LEFT JOIN LATERAL (
                  SELECT
                      pre_nd.name || ' chưa '
                      || CASE WHEN dep.dependency_type = 'FS'
                              THEN 'hoàn thành'
                              ELSE 'bắt đầu' END
                      AS blocker_label
                    FROM work_item_dependency dep
                    JOIN work_item pre_w
                      ON pre_w.id
                         = dep.predecessor_work_item_id
                    JOIN node_definition pre_nd
                      ON pre_nd.code = pre_w.node_code
                     AND pre_nd.clinic_id
                         = pre_w.clinic_id
                   WHERE dep.successor_work_item_id = w.id
                     AND dep.is_blocking
                     AND pre_w.status NOT IN (
                         'COMPLETED', 'SKIPPED'
                     )
              ) b ON w.status = 'PENDING'
             WHERE w.visit_id = $1::uuid
               AND w.clinic_id = $2::uuid
               AND w.status <> 'CANCELLED'
             GROUP BY w.id, w.node_code, nd.name,
                      w.status, w.assigned_role,
                      s.full_name, w.started_at,
                      w.finished_at, w.priority,
                      w.created_at
             ORDER BY
                CASE w.status
                    WHEN 'IN_PROGRESS' THEN 0
                    WHEN 'PENDING' THEN 1
                    WHEN 'COMPLETED' THEN 2
                    WHEN 'SKIPPED' THEN 3
                    ELSE 4
                END,
                w.created_at
            """,
            str(visit_id),
            identity.clinic_id,
        )

    return {
        "ok": True,
        "visit": {
            "visit_id": visit["visit_id"],
            "status": visit["status"],
            "current_node_code": visit["current_node_code"],
            "current_node_since": (
                visit["current_node_since"].isoformat()
                if visit["current_node_since"]
                else None
            ),
            "previous_node_code": visit["previous_node_code"],
            "checked_in_at": (
                visit["checked_in_at"].isoformat() if visit["checked_in_at"] else None
            ),
            "patient_name": visit["patient_name"],
            "patient_code": visit["patient_code"],
            "doctor_name": visit["doctor_name"],
        },
        "work_items": [
            {
                "id": r["work_item_id"],
                "node_code": r["node_code"],
                "node_name": r["node_name"],
                "status": r["status"],
                "assigned_role": r["assigned_role"],
                "assigned_to_name": r["assigned_to_name"],
                "started_at": (
                    r["started_at"].isoformat() if r["started_at"] else None
                ),
                "finished_at": (
                    r["finished_at"].isoformat() if r["finished_at"] else None
                ),
                "priority": r["priority"],
                "blockers": list(r["blockers"] or []),
            }
            for r in items
        ],
    }


@router.get("/visits/active")
async def active_visits(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dispatch board: all active visits with patient location (C.5).

    Returns visits that are OPEN or IN_PROGRESS today, showing where
    each patient currently is (current_node_code) and how many work
    items remain.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT v.visit_id::text,
                   v.status,
                   v.current_node_code,
                   v.current_node_since,
                   v.checked_in_at,
                   p.full_name AS patient_name,
                   p.patient_code,
                   a.queue_number,
                   s.full_name AS doctor_name,
                   nd.name AS current_node_name,
                   (SELECT count(*)
                      FROM work_item w
                     WHERE w.visit_id = v.visit_id
                       AND w.status IN (
                           'PENDING', 'IN_PROGRESS'
                       )
                   ) AS remaining_items,
                   (SELECT count(*)
                      FROM work_item w
                     WHERE w.visit_id = v.visit_id
                       AND w.status = 'COMPLETED'
                   ) AS completed_items
              FROM visit v
              JOIN patient p
                ON p.clinic_patient_id
                   = v.clinic_patient_id
              LEFT JOIN appointment a
                ON a.id = v.appointment_id
              LEFT JOIN staff s
                ON s.id = v.attending_doctor_id
              LEFT JOIN node_definition nd
                ON nd.code = v.current_node_code
               AND nd.clinic_id = v.clinic_id
               AND nd.is_active
             WHERE v.clinic_id = $1::uuid
               AND v.status IN ('OPEN', 'IN_PROGRESS')
               AND v.checked_in_at >= (
                   now() AT TIME ZONE
                   'Asia/Ho_Chi_Minh'
               )::date::timestamptz
             ORDER BY v.checked_in_at
            """,
            identity.clinic_id,
        )

    return {
        "ok": True,
        "visits": [
            {
                "visit_id": r["visit_id"],
                "status": r["status"],
                "current_node_code": r["current_node_code"],
                "current_node_name": r["current_node_name"],
                "current_node_since": (
                    r["current_node_since"].isoformat()
                    if r["current_node_since"]
                    else None
                ),
                "checked_in_at": (
                    r["checked_in_at"].isoformat() if r["checked_in_at"] else None
                ),
                "patient_name": r["patient_name"],
                "patient_code": r["patient_code"],
                "queue_number": r["queue_number"],
                "doctor_name": r["doctor_name"],
                "remaining_items": r["remaining_items"],
                "completed_items": r["completed_items"],
            }
            for r in rows
        ],
    }
