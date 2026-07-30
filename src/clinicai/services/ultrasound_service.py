"""Foetal ultrasound measurements attached to a visit (W5, ADR-0012).

Ported from ``src/dashboard/app/api/ultrasound/route.ts``. Rules preserved 1:1,
including the ones that are deliberate clinical restraint rather than missing
features:

* **ULTRASOUND_DOCTOR only.** Not widened to doctors in general.
* **EFW is typed in, never computed.** Hadlock and friends would be easy to add
  and are exactly the kind of "helpful" inference that puts a number nobody
  chose onto a pregnancy record. It stays manual until the clinic's doctor
  signs off on a formula.
* **Abnormality is a doctor pressing a button**, never derived from the
  measurements.
* A visit that is no longer OPEN or IN_PROGRESS is closed to edits: measurements
  cannot be changed after the record is finalised.
* One ultrasound_record per visit; measurements merge into the existing
  ``findings`` JSONB rather than replacing it, so saving just BPD does not wipe
  the rest of the exam.

The visit find-or-create and the record write now share a transaction. In the
route they did not, so a crash in between left an empty visit attached to the
appointment.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

MEASURE_KEYS: tuple[str, ...] = ("crl", "nt", "bpd", "hc", "ac", "fl", "efw")
WRITABLE_VISIT_STATUSES: frozenset[str] = frozenset({"OPEN", "IN_PROGRESS"})


def num_or_none(value: Any) -> float | None:
    """A measurement, or None for anything that is not a finite number.

    An empty field means "not measured", which is different from zero, so a
    blank must never become 0.0 on a pregnancy record.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return number


def merge_findings(
    previous: dict[str, Any] | None,
    *,
    measurements: dict[str, Any] | None,
    is_abnormal: bool | None,
    status: str | None,
) -> dict[str, Any]:
    """Merge an update into the findings already recorded.

    Pure, so the merge — the part that could quietly lose a measurement — is
    testable without a database.
    """
    merged: dict[str, Any] = dict(previous or {})
    if measurements:
        for key in MEASURE_KEYS:
            if key in measurements:
                merged[key] = num_or_none(measurements[key])
    if is_abnormal is not None:
        merged["is_abnormal"] = is_abnormal
    if status:
        merged["status"] = status
    return merged


class UltrasoundService:
    """Record foetal measurements against a visit."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_measurements(
        self,
        *,
        appointment_id: str,
        clinic_patient_id: str,
        measurements: dict[str, Any] | None,
        is_abnormal: bool | None,
        status: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Upsert the visit's ultrasound record. Returns the merged findings."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                visit = await conn.fetchrow(
                    """
                    SELECT visit_id, status
                      FROM visit
                     WHERE appointment_id = $1::uuid
                     ORDER BY created_at DESC
                     LIMIT 1
                    """,
                    appointment_id,
                )

                if visit is not None:
                    if visit["status"] not in WRITABLE_VISIT_STATUSES:
                        raise ConflictError(
                            f"Hồ sơ đã chốt ({visit['status']}) — không sửa số đo."
                        )
                    visit_id = visit["visit_id"]
                else:
                    # The sonographer is the attending doctor for their own scan.
                    visit_id = await conn.fetchval(
                        """
                        INSERT INTO visit (
                            clinic_patient_id, appointment_id, attending_doctor_id,
                            status, checked_in_at
                        )
                        VALUES ($1::uuid, $2::uuid, $3::uuid, 'IN_PROGRESS', now())
                        RETURNING visit_id
                        """,
                        clinic_patient_id,
                        appointment_id,
                        identity.staff_id,
                    )

                record = await conn.fetchrow(
                    """
                    SELECT ultrasound_id, findings
                      FROM ultrasound_record
                     WHERE visit_id = $1::uuid
                     ORDER BY created_at DESC
                     LIMIT 1
                    """,
                    visit_id,
                )

                findings = merge_findings(
                    _as_dict(record["findings"]) if record else None,
                    measurements=measurements,
                    is_abnormal=is_abnormal,
                    status=status,
                )

                if record is not None:
                    await conn.execute(
                        """
                        UPDATE ultrasound_record
                           SET findings = $2, performed_by = $3::uuid,
                               performed_at = now()
                         WHERE ultrasound_id = $1
                        """,
                        record["ultrasound_id"],
                        _json(findings),
                        identity.staff_id,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO ultrasound_record (
                            visit_id, clinic_patient_id, performed_by,
                            ultrasound_type, findings, performed_at
                        )
                        VALUES ($1::uuid, $2::uuid, $3::uuid, 'Thai', $4, now())
                        """,
                        visit_id,
                        clinic_patient_id,
                        identity.staff_id,
                        _json(findings),
                    )

        logger.info(
            "ultrasound_measurements_saved",
            visit_id=str(visit_id),
            by_staff_id=identity.staff_id,
        )
        return findings


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        import json

        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return value or {}


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value)
