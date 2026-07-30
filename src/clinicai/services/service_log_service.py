"""Service and procedure tracking on ``service_log`` (W5, ADR-0012).

Ports two routes that write the same table from different screens:

* ``app/api/service-log`` — the general services/procedures worklist. Clinical
  writers create an item and move it Chờ làm → Đang làm → Hoàn tất.
* ``app/api/sono`` — the ultrasound nurse's queue. Ultrasound rows move
  WAITING → IN_PROGRESS → DONE (or CANCELLED); lab rows instead toggle three
  independent milestones (sample taken, sent to the lab, result back), because
  a sample can come back before another is even sent and a single status could
  not express that.

TWO VOCABULARIES ON ONE TABLE, deliberately preserved. One screen writes
Vietnamese statuses and the other writes English ones, and each reads back only
its own rows. Unifying them is a data migration plus two screen changes, not a
detail to fix quietly underneath a port — doing it here would silently empty
whichever worklist was not updated. Worth doing; not worth doing by accident.

Both routes also let a caller pass a patient code. If one is given and matches
nothing, the call fails: an unattached service row is work nobody can find.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from typing import Any, Literal

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity

logger = structlog.get_logger()

# The general worklist (Vietnamese vocabulary).
TASK_WAITING = "Chờ làm"
TASK_IN_PROGRESS = "Đang làm"
TASK_DONE = "Hoàn tất"

# The ultrasound nurse's queue (English vocabulary).
QUEUE_WAITING = "WAITING"
QUEUE_IN_PROGRESS = "IN_PROGRESS"
QUEUE_DONE = "DONE"
QUEUE_CANCELLED = "CANCELLED"

TaskAction = Literal["start", "finish"]
QueueAction = Literal["start", "finish", "cancel"]
Milestone = Literal["sample", "sendlab", "result"]

# A lab row's three milestones are independent timestamps, not a status.
MILESTONE_COLUMN: dict[str, str] = {
    "sample": "started_at",
    "sendlab": "sent_to_lab_at",
    "result": "finished_at",
}

# The sono screen is the ultrasound nurse's own queue.
SONO_ROLES: frozenset[ClinicRole] = frozenset(
    {ClinicRole.NURSE_ULTRASOUND, ClinicRole.MANAGEMENT}
)


def source_ref(prefix: str) -> str:
    """``service_log.source_ref`` is UNIQUE and shared with the import pipeline."""
    return f"{prefix}-{int(datetime.now().timestamp() * 1000)}-{secrets.token_hex(4)}"


def task_patch(action: str, result_text: str | None) -> dict[str, Any]:
    """Columns to set for a worklist transition. Pure, so it is testable."""
    if action == "start":
        return {"started_at": "now", "status": TASK_IN_PROGRESS}
    if action == "finish":
        return {
            "finished_at": "now",
            "status": TASK_DONE,
            "result_text": (result_text or "").strip() or None,
        }
    raise ValidationError(f"Hành động không hợp lệ: {action!r}")


def queue_patch(action: str) -> dict[str, Any]:
    """Columns to set for an ultrasound-queue transition."""
    if action == "start":
        return {"started_at": "now", "status": QUEUE_IN_PROGRESS}
    if action == "finish":
        return {"finished_at": "now", "status": QUEUE_DONE}
    if action == "cancel":
        # Cancelling leaves the timestamps alone: what did happen still happened.
        return {"status": QUEUE_CANCELLED}
    raise ValidationError(f"Hành động không hợp lệ: {action!r}")


class ServiceLogService:
    """Create and progress rows on the services worklist."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(
        self,
        *,
        service_name: str,
        patient_code: str | None,
        identity: StaffIdentity,
        kind: str | None = None,
        performer: str | None = None,
        status: str = TASK_WAITING,
        ref_prefix: str = "api-svc",
        origin: str = "api:service-create",
    ) -> str:
        """Add one row to the worklist. Returns its id."""
        name = (service_name or "").strip()
        if not name:
            raise ValidationError("Thiếu tên dịch vụ")

        code = (patient_code or "").strip()

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                clinic_patient_id = await self._resolve_patient(conn, code, identity)

                row_id = await conn.fetchval(
                    """
                    INSERT INTO service_log (
                        clinic_id, source_ref, kind, clinic_patient_id,
                        service_name_raw, performer_text, status, ordered_at,
                        created_by_text, patient_link_raw
                    )
                    VALUES ($1::uuid, $2, $3, $4::uuid, $5, $6, $7, now(), $8, $9)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    source_ref(ref_prefix),
                    kind,
                    clinic_patient_id,
                    name,
                    (performer or "").strip() or None,
                    status,
                    f"{identity.full_name} · {identity.role.value}",
                    code or None,
                )

                await _log(
                    conn,
                    event_type="service_log.created",
                    aggregate_id=str(row_id),
                    payload={
                        "id": str(row_id),
                        "service_name": name,
                        "kind": kind,
                        "clinic_patient_id": (
                            str(clinic_patient_id) if clinic_patient_id else None
                        ),
                    },
                    identity=identity,
                    origin=origin,
                )

        logger.info(
            "service_log_created", id=str(row_id), by_staff_id=identity.staff_id
        )
        return str(row_id)

    async def apply_patch(
        self,
        *,
        row_id: str,
        patch: dict[str, Any],
        identity: StaffIdentity,
        event_type: str,
        origin: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Apply a column patch to one row of the caller's clinic."""
        # "now" is a sentinel, not a client-supplied timestamp: the database
        # clock decides when something happened, never a browser's.
        parts: list[str] = []
        values: list[Any] = []
        for column in patch:
            if patch[column] == "now":
                parts.append(f"{column} = now()")
            else:
                values.append(patch[column])
                parts.append(f"{column} = ${len(values) + 2}")
        assignments = ", ".join(parts)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                updated = await conn.fetchval(
                    f"""
                    UPDATE service_log
                       SET {assignments}, updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    RETURNING id
                    """,
                    row_id,
                    identity.clinic_id,
                    *values,
                )
                if updated is None:
                    raise NotFoundError("Không tìm thấy dịch vụ")

                await _log(
                    conn,
                    event_type=event_type,
                    aggregate_id=row_id,
                    payload=payload or {"id": row_id},
                    identity=identity,
                    origin=origin,
                )

    async def remove(self, *, row_id: str, identity: StaffIdentity) -> None:
        """Drop a row from the queue. service_log is not append-only."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                deleted = await conn.fetchval(
                    "DELETE FROM service_log "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid RETURNING id",
                    row_id,
                    identity.clinic_id,
                )
                if deleted is None:
                    raise NotFoundError("Không tìm thấy dòng")

                await _log(
                    conn,
                    event_type="service_log.removed",
                    aggregate_id=row_id,
                    payload={"id": row_id},
                    identity=identity,
                    origin="api:sono-remove",
                )

    async def _resolve_patient(
        self, conn: asyncpg.Connection, code: str, identity: StaffIdentity
    ) -> Any:
        if not code:
            return None
        found = await conn.fetchval(
            "SELECT clinic_patient_id FROM patient "
            "WHERE patient_code = $1 AND clinic_id = $2::uuid",
            code,
            identity.clinic_id,
        )
        if found is None:
            raise NotFoundError(f"Không tìm thấy bệnh nhân mã {code}")
        return found


async def _log(
    conn: asyncpg.Connection,
    *,
    event_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    identity: StaffIdentity,
    origin: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, event_published)
        VALUES ($1::uuid, $2, 'service_log', $3, $4, $5, $6, FALSE)
        """,
        identity.clinic_id,
        event_type,
        aggregate_id,
        json.dumps(payload),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "clinic_staff_id": identity.staff_id,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": origin,
            }
        ),
        origin,
    )
