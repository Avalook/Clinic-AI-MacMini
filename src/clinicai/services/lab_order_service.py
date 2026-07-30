"""Ordering a lab test and entering its result (W5, ADR-0012).

Ported from ``src/dashboard/app/api/lab-result/route.ts`` so the rule stops
living in a Next route holding a service-role key. Rules preserved 1:1:

* **Ordering is a doctor's decision.** Only DOCTOR and ULTRASOUND_DOCTOR may
  create a lab_result; it starts at ``triage_group='PENDING'`` with no result.
* **Entering a result is clinical work**, so it is open to the clinical writers
  (doctors, nurses, medical secretary) but NOT to reception or management — the
  clinic decided that on 2026-06-17 and the frontend enforced it.
* A result needs either a summary or a link to the provider's PDF; an empty
  update is rejected rather than silently stamping ``result_received_at``.
* ``is_finalized`` is never set here. Finalising is a separate safety gate.

Two improvements over the route it replaces: the write and its audit event share
a transaction, and the pasted link is normalised in one place that is unit
tested, because a link saved without a scheme resolves against our own domain
and 404s for whoever opens the result.
"""

from __future__ import annotations

import json
import re
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

# Already absolute, or a scheme we should not touch.
_ABSOLUTE = re.compile(r"^(https?://|mailto:|tel:|//)", re.IGNORECASE)


def normalize_link(raw: str | None) -> str | None:
    """Turn a pasted link into something an ``href`` can actually open.

    Staff paste ``drive.google.com/...`` without a scheme; stored as-is the
    browser reads it as a path on our own host and the result 404s. Mirrors
    ``toHref`` in the dashboard so both sides agree while the cutover flag is
    still switchable.
    """
    value = (raw or "").strip()
    if not value:
        return None
    if _ABSOLUTE.match(value) or value.startswith("/"):
        return value
    return f"https://{value}"


class LabOrderService:
    """Create lab orders and attach their results."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def order_test(
        self,
        *,
        clinic_patient_id: str,
        test_name: str,
        appointment_id: str | None,
        identity: StaffIdentity,
    ) -> str:
        """Create a PENDING lab_result. Returns its id."""
        name = (test_name or "").strip()
        if not name:
            raise ValidationError("Thiếu tên xét nghiệm")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                lab_result_id = await conn.fetchval(
                    """
                    INSERT INTO lab_result (
                        clinic_patient_id, appointment_id, test_code, test_name,
                        triage_group
                    )
                    VALUES ($1::uuid, $2::uuid, 'MANUAL', $3, 'PENDING')
                    RETURNING lab_result_id
                    """,
                    clinic_patient_id,
                    appointment_id,
                    name,
                )
                await _log(
                    conn,
                    event_type="lab_result.ordered",
                    aggregate_id=str(lab_result_id),
                    payload={
                        "lab_result_id": str(lab_result_id),
                        "clinic_patient_id": clinic_patient_id,
                        "test_name": name,
                    },
                    identity=identity,
                    origin="api:lab-order",
                )

        logger.info(
            "lab_test_ordered",
            lab_result_id=str(lab_result_id),
            by_staff_id=identity.staff_id,
        )
        return str(lab_result_id)

    async def enter_result(
        self,
        *,
        lab_result_id: str,
        result_value: str | None,
        result_link: str | None,
        lab_provider: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Attach a summary and/or the provider's document to a lab result."""
        value = (result_value or "").strip() or None
        link = normalize_link(result_link)
        provider = (lab_provider or "").strip() or None

        if not value and not link:
            raise ValidationError("Nhập tóm tắt kết quả hoặc dán link phiếu")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                updated = await conn.fetchval(
                    """
                    UPDATE lab_result
                       SET result_value       = $2,
                           external_ref       = $3,
                           lab_provider       = $4,
                           result_received_at = now(),
                           updated_at         = now()
                     WHERE lab_result_id = $1::uuid
                    RETURNING lab_result_id
                    """,
                    lab_result_id,
                    value,
                    link,
                    provider,
                )
                if updated is None:
                    raise NotFoundError("Không tìm thấy kết quả xét nghiệm")

                await _log(
                    conn,
                    event_type="lab_result.entered",
                    aggregate_id=lab_result_id,
                    # The result itself is clinical data and does not belong in
                    # an audit payload; whether a document was attached does.
                    payload={"lab_result_id": lab_result_id, "has_link": bool(link)},
                    identity=identity,
                    origin="api:lab-entry",
                )

        logger.info(
            "lab_result_entered",
            lab_result_id=lab_result_id,
            by_staff_id=identity.staff_id,
        )


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
            (event_type, aggregate_type, aggregate_id, payload, metadata,
             source, event_published)
        VALUES ($1, 'lab_result', $2, $3, $4, $5, FALSE)
        """,
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
