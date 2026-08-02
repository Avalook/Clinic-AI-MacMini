"""Customer-care records: manual actions and follow-up calls (W5, ADR-0012).

Ported from ``app/api/cskh-action/route.ts`` and ``app/api/cskh-followup/route.ts``.
Both tables are read-only to clients, which is why the routes held a service-role
key; the rules now live here and the write shares a transaction with its audit
event.

Rules preserved 1:1:

* Both are intake work — CSKH, reception, the shift lead and management. Not
  clinical staff, who have their own screens.
* An action needs a category and a description. A blank note is not a record of
  anything, and ``cskh_action`` is what the clinic reads back to answer "what did
  we do for this patient".
* The patient code is optional, but if one is given and does not match, the call
  fails rather than filing the work against nobody.
* A follow-up call is stamped with the date in Asia/Ho_Chi_Minh, not UTC. A call
  made at 8pm in Hanoi belongs to that working day; UTC would file it as
  tomorrow and the overdue list would be wrong every evening.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity

logger = structlog.get_logger()

CLINIC_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Mirrors canWriteIntake in src/dashboard/lib/roles.ts.
INTAKE_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.CSKH,
        ClinicRole.RECEPTION,
        ClinicRole.MANAGEMENT,
        ClinicRole.TRUONG_CA,
    }
)

# What a CSKH staffer can say about a piece of work when they close it (B.4).
# A closed vocabulary rather than free text: the board filters on these, and
# "Đã gọi " with a trailing space would quietly become a fourth state.
RESOLUTIONS: dict[str, str] = {
    "called": "Đã gọi",
    "closed": "Đã đóng",
}
MAX_RESULT_TEXT = 2000

FOLLOWUP_STATUS = "Đã gọi nhắc tái khám"
FOLLOWUP_KIND = "Nhắc gọi tái khám"


def clinic_today(now: datetime | None = None) -> str:
    """Today's date in the clinic's timezone, as YYYY-MM-DD.

    Deliberately not UTC: an evening call in Hanoi is UTC-tomorrow, which would
    put it on the wrong working day and skew the overdue-recall list nightly.
    """
    moment = now or datetime.now(CLINIC_TZ)
    return moment.astimezone(CLINIC_TZ).date().isoformat()


def manual_source_ref() -> str:
    """``cskh_action.source_ref`` is UNIQUE NOT NULL and imports own the space.

    Hand-entered work needs its own collision-free key. Uses secrets rather than
    the route's Math.random so two clicks in the same millisecond cannot clash.
    """
    return (
        f"dash-manual-{int(datetime.now().timestamp() * 1000)}-{secrets.token_hex(4)}"
    )


@dataclass(frozen=True)
class CskhActionOutcome:
    """State of one care action after somebody closed it."""

    action_id: str
    status: str
    changed: bool


class CskhService:
    """Record customer-care work."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def record_action(
        self,
        *,
        category: str,
        description: str,
        status: str | None,
        patient_code: str | None,
        identity: StaffIdentity,
    ) -> str:
        """Log one manually entered care action. Returns its id."""
        category = (category or "").strip()
        description = (description or "").strip()
        if not category:
            raise ValidationError("Thiếu loại việc")
        if not description:
            raise ValidationError("Phải nhập nội dung việc")

        code = (patient_code or "").strip()
        status = (status or "").strip() or None

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                clinic_patient_id = None
                if code:
                    clinic_patient_id = await conn.fetchval(
                        "SELECT clinic_patient_id FROM patient "
                        "WHERE patient_code = $1 AND clinic_id = $2::uuid",
                        code,
                        identity.clinic_id,
                    )
                    if clinic_patient_id is None:
                        raise NotFoundError(f"Không tìm thấy bệnh nhân mã {code}")

                action_id = await conn.fetchval(
                    """
                    INSERT INTO cskh_action (
                        clinic_id, source_ref, clinic_patient_id, category, status,
                        description, source_created_at, created_by_text,
                        patient_link_raw
                    )
                    VALUES ($1::uuid, $2, $3::uuid, $4, $5, $6, now(), $7, $8)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    manual_source_ref(),
                    clinic_patient_id,
                    category,
                    status,
                    description,
                    f"{identity.full_name} · {identity.role.value}",
                    code or None,
                )

                await _log(
                    conn,
                    aggregate_type="cskh_action",
                    event_type="cskh_action.created",
                    aggregate_id=str(action_id),
                    payload={
                        "id": str(action_id),
                        "category": category,
                        "status": status,
                        "clinic_patient_id": (
                            str(clinic_patient_id) if clinic_patient_id else None
                        ),
                    },
                    identity=identity,
                    origin="api:cskh-action-manual",
                )

        logger.info(
            "cskh_action_recorded",
            action_id=str(action_id),
            by_staff_id=identity.staff_id,
        )
        return str(action_id)

    async def record_followup_call(
        self,
        *,
        clinic_patient_id: str,
        note: str | None,
        identity: StaffIdentity,
    ) -> str:
        """Log a recall reminder call against a patient. Returns the log id."""
        today = clinic_today()

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                exists = await conn.fetchval(
                    "SELECT 1 FROM patient "
                    "WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
                    clinic_patient_id,
                    identity.clinic_id,
                )
                if not exists:
                    raise NotFoundError("Không tìm thấy bệnh nhân")

                log_id = await conn.fetchval(
                    """
                    INSERT INTO cskh_log (
                        clinic_id, clinic_patient_id, work_date, cskh_status,
                        cskh_followup, last_cskh_date, cskh_by, note
                    )
                    VALUES ($1::uuid, $2::uuid, $3::date, $4, $5, $3::date, $6, $7)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    today,
                    FOLLOWUP_STATUS,
                    FOLLOWUP_KIND,
                    f"{identity.full_name} · {identity.role.value}",
                    (note or "").strip() or None,
                )

                await _log(
                    conn,
                    aggregate_type="cskh_log",
                    event_type="cskh_log.followup_call",
                    aggregate_id=str(log_id),
                    payload={
                        "id": str(log_id),
                        "clinic_patient_id": clinic_patient_id,
                        "kind": "nhac_goi",
                    },
                    identity=identity,
                    origin="api:cskh-followup",
                )

        logger.info(
            "cskh_followup_logged", log_id=str(log_id), by_staff_id=identity.staff_id
        )
        return str(log_id)

    async def resolve_action(
        self,
        *,
        action_id: str,
        outcome: str,
        note: str | None,
        identity: StaffIdentity,
    ) -> CskhActionOutcome:
        """Close one care action: called back, or done with entirely.

        Until now the CSKH board's buttons only hid the row in the browser, so
        a refresh brought the work back and two people could call the same
        patient. Writing the outcome down is the whole point of the screen.

        Repeating the same outcome with no new note changes nothing and says
        so, but "called" followed by "closed" is a real progression, not a
        double-click, so it is allowed through.
        """
        status = RESOLUTIONS.get(outcome)
        if status is None:
            raise ValidationError("Kết quả xử lý không hợp lệ")
        text = (note or "").strip()[:MAX_RESULT_TEXT] or None

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """
                    SELECT id, status
                    FROM cskh_action
                    WHERE id = $1::uuid
                      AND clinic_id = $2::uuid
                    FOR UPDATE
                    """,
                    action_id,
                    identity.clinic_id,
                )
                if current is None:
                    raise NotFoundError("Không tìm thấy việc CSKH")

                if str(current["status"] or "") == status and text is None:
                    return CskhActionOutcome(
                        action_id=action_id, status=status, changed=False
                    )

                await conn.execute(
                    """
                    UPDATE cskh_action
                       SET status = $2,
                           result_text = COALESCE($3, result_text),
                           last_edited_by_text = $4,
                           source_updated_at = now(),
                           updated_at = now()
                     WHERE id = $1::uuid
                       AND clinic_id = $5::uuid
                    """,
                    action_id,
                    status,
                    text,
                    f"{identity.full_name} · {identity.role.value}",
                    identity.clinic_id,
                )

                await _log(
                    conn,
                    aggregate_type="cskh_action",
                    event_type="cskh_action.resolved",
                    aggregate_id=action_id,
                    # The note may quote what the patient said, so it stays in
                    # the row the clinic reads, not in the audit trail.
                    payload={"id": action_id, "status": status},
                    identity=identity,
                    origin="api:cskh-action-resolve",
                )

        logger.info(
            "cskh_action_resolved",
            action_id=action_id,
            status=status,
            by_staff_id=identity.staff_id,
        )
        return CskhActionOutcome(action_id=action_id, status=status, changed=True)


async def _log(
    conn: asyncpg.Connection,
    *,
    aggregate_type: str,
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
             metadata, source, actor_staff_id, event_published)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::uuid, FALSE)
        """,
        identity.clinic_id,
        event_type,
        aggregate_type,
        aggregate_id,
        json.dumps(payload),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": origin,
            }
        ),
        origin,
        identity.staff_id,
    )
