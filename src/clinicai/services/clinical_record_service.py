"""Writing the clinical record for a visit (W5, ADR-0012).

Ported from ``src/dashboard/app/api/clinical-record/route.ts``, the largest
piece of clinical logic that was still living in the frontend. Every rule is
preserved, and each one exists because of something that went wrong or could:

* **Two write modes.** ``vitals_only`` is the nurse/reception path — vitals plus
  the chief complaint, nothing else. The full path is doctors, the medical
  secretary entering on their behalf, and nurses (widened 2026-06-29).
  Reception may only ever write vitals.
* **Vitals need the patient to have arrived.** Reception must have checked them
  in (CHECKED_IN, or COMPLETED so a correction is still possible), otherwise
  vitals could be recorded for somebody who never turned up.
* **A doctor writes on their own appointments** or unassigned walk-ins, never on
  another doctor's. TKYK and nurses are exempt because entering on behalf of a
  doctor is their job.
* **48-hour lock.** After roughly two shifts the record is closed; corrections
  go through the shift lead.
* **Chỉ trạng thái ĐANG SỐNG mới ghi được** — OPEN, IN_PROGRESS và INCOMPLETE
  (khách về giữa chừng). FINALIZED *và* AMENDED bất biến theo Thông tư 13. Đây
  là danh sách TRẮNG chứ không phải phép kiểm `!= FINALIZED`, nên một trạng thái
  CUỐI thêm sau này không lọt qua được.

  INCOMPLETE ghi được vì khách CÒN QUAY LẠI: khoá bút lúc đó là bắt bác sĩ phải
  đính chính một hồ sơ chưa ai ký.
* **Merging, not overwriting.** A doctor may have opened the form before the
  nurse entered vitals; saving blind would wipe them. Existing values are kept
  and only non-empty incoming fields override.

The whole write is one transaction. In the route it was five sequential
statements, so a failure part-way through could leave a visit with a record but
no prescriptions, or a record saved and the medical history lost.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event

logger = structlog.get_logger()

PROFILE_COLUMNS: frozenset[str] = frozenset(
    {
        "blood_type",
        "allergies",
        "chronic_diseases",
        "current_medications",
        "surgical_history",
        "family_history",
        "notes",
    }
)


def validated_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Copy only the versioned medical-profile contract; reject unknown keys."""
    unknown = set(profile) - PROFILE_COLUMNS
    if unknown:
        raise ValidationError(
            "Trường tiền sử không hợp lệ: " + ", ".join(sorted(unknown))
        )
    return {key: profile[key] for key in profile if key in PROFILE_COLUMNS}


# Trạng thái lượt khám còn GHI ĐƯỢC hồ sơ.
#
# Danh sách TRẮNG, không phải kiểm `!= FINALIZED`. Cố ý: một trạng thái CUỐI
# thêm sau này sẽ không lọt qua được, còn danh sách đen thì lọt.
#
# INCOMPLETE (khách về giữa chừng) nằm TRONG danh sách này. Nó là trạng thái
# KHÔNG-CUỐI: khách còn quay lại, và khoá bút lúc này là bắt bác sĩ phải đính
# chính một hồ sơ chưa ai ký. FINALIZED và AMENDED thì bất biến theo Thông tư 13.
WRITABLE_VISIT_STATUSES: frozenset[str] = frozenset(
    {"OPEN", "IN_PROGRESS", "INCOMPLETE"}
)
ARRIVED_APPOINTMENT_STATUSES: frozenset[str] = frozenset({"CHECKED_IN", "COMPLETED"})
RECORD_LOCK = timedelta(hours=48)

# Full-record writers. Reception is absent on purpose; it appears only in the
# vitals-only path.
FULL_RECORD_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.NURSE_ULTRASOUND,
    }
)
VITALS_ONLY_EXTRA_ROLES: frozenset[ClinicRole] = frozenset({ClinicRole.RECEPTION})
# Roles that enter on behalf of a doctor, so the ownership check does not apply.
ON_BEHALF_ROLES: frozenset[ClinicRole] = frozenset(
    {ClinicRole.TKYK, ClinicRole.NURSE_ULTRASOUND}
)


def may_write(role: ClinicRole, *, vitals_only: bool) -> bool:
    """Whether this role may write in this mode."""
    if role in FULL_RECORD_ROLES:
        return True
    return vitals_only and role in VITALS_ONLY_EXTRA_ROLES


def as_obj(value: Any) -> dict[str, Any]:
    """A JSON object, or an empty one. Lists and scalars are not partial records."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def non_empty(values: dict[str, Any]) -> dict[str, Any]:
    """Drop keys the user left blank, so a merge only overrides with real input."""
    return {
        key: value
        for key, value in values.items()
        if value is not None and not (isinstance(value, str) and value.strip() == "")
    }


def merge_objective(
    previous: Any, incoming: Any, *, incoming_was_sent: bool
) -> dict[str, Any] | None:
    """Merge the doctor's SOAP-objective over what is already recorded.

    The nurse's vitals must survive a doctor saving a form they opened earlier,
    so previous vitals are kept and only non-blank incoming ones override. When
    nothing was sent and nothing is stored, the column stays NULL rather than
    becoming an empty object.
    """
    prev = as_obj(previous)
    incoming_obj = as_obj(incoming)

    if not incoming_was_sent and not prev:
        return None

    merged: dict[str, Any] = {**prev, **incoming_obj}
    merged["vitals"] = {
        **as_obj(prev.get("vitals")),
        **non_empty(as_obj(incoming_obj.get("vitals"))),
    }
    return merged


def merge_vitals_only(previous: Any, incoming: Any) -> dict[str, Any]:
    """The nurse path: replace vitals, leave every other section alone.

    Diagnosis, plan and history belong to the doctor and are not touched.
    """
    return {**as_obj(previous), "vitals": as_obj(incoming).get("vitals") or {}}


class ClinicalRecordService:
    """Create or update the clinical record attached to an appointment's visit."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(
        self,
        *,
        appointment_id: str,
        clinic_patient_id: str,
        identity: StaffIdentity,
        vitals_only: bool = False,
        chief_complaint: str | None = None,
        subjective: Any = None,
        objective: Any = None,
        objective_sent: bool = False,
        assessment: Any = None,
        plan: Any = None,
        profile: dict[str, Any] | None = None,
        prescriptions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Write the record. Returns the visit id it was written to."""
        if not may_write(identity.role, vitals_only=vitals_only):
            raise SafetyGateError(
                "Chỉ bác sĩ / điều dưỡng / lễ tân mới ghi sinh hiệu + lý do khám."
                if vitals_only
                else "Chỉ bác sĩ mới ghi hồ sơ khám."
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                appointment = await conn.fetchrow(
                    """
                    SELECT
                        a.status,
                        a.doctor_id,
                        a.clinic_patient_id,
                        p.clinic_patient_id IS NOT NULL AS patient_in_clinic,
                        (
                            a.doctor_id IS NULL
                            OR EXISTS (
                                SELECT 1
                                  FROM staff st
                                  JOIN clinic_membership m
                                    ON m.staff_id = st.id
                                 WHERE st.id = a.doctor_id
                                   AND st.is_active
                                   AND m.clinic_id = a.clinic_id
                                   AND m.is_active
                                   AND m.role IN (
                                       'DOCTOR', 'ULTRASOUND_DOCTOR'
                                   )
                            )
                        ) AS doctor_in_clinic
                      FROM appointment a
                      LEFT JOIN patient p
                        ON p.clinic_patient_id = a.clinic_patient_id
                       AND p.clinic_id = a.clinic_id
                     WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
                    """,
                    appointment_id,
                    identity.clinic_id,
                )
                if appointment is None:
                    raise ValidationError("Không tìm thấy lịch hẹn")
                if (
                    not appointment["patient_in_clinic"]
                    or str(appointment["clinic_patient_id"]) != clinic_patient_id
                ):
                    raise ValidationError(
                        "Lịch hẹn không thuộc bệnh nhân này trong phòng khám"
                    )
                if not appointment["doctor_in_clinic"]:
                    raise ValidationError(
                        "Bác sĩ của lịch hẹn không thuộc phòng khám này"
                    )

                if vitals_only and appointment["status"] not in (
                    ARRIVED_APPOINTMENT_STATUSES
                ):
                    raise ConflictError(
                        "Chờ lễ tân check-in bệnh nhân (đã đến) "
                        "trước khi điền sinh hiệu."
                    )

                if (
                    not vitals_only
                    and identity.role not in ON_BEHALF_ROLES
                    and appointment["doctor_id"] is not None
                    and str(appointment["doctor_id"]) != identity.staff_id
                ):
                    raise SafetyGateError(
                        "Lịch hẹn này thuộc bác sĩ khác — không thể ghi hồ sơ khám."
                    )

                visit_id = await self._writable_visit(
                    conn,
                    appointment_id=appointment_id,
                    clinic_patient_id=clinic_patient_id,
                    appointment_doctor_id=appointment["doctor_id"],
                    identity=identity,
                    vitals_only=vitals_only,
                )

                stored = await conn.fetchval(
                    "SELECT soap_objective FROM clinical_record "
                    "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid "
                    "FOR UPDATE",
                    visit_id,
                    identity.clinic_id,
                )

                if vitals_only:
                    await self._save_vitals(
                        conn,
                        visit_id=visit_id,
                        stored_objective=stored,
                        objective=objective,
                        chief_complaint=chief_complaint,
                        clinic_id=identity.clinic_id,
                    )
                    # Sinh hiệu là ghi chép lâm sàng, chỉ hẹp hơn về nội dung —
                    # nó vẫn phải để lại dấu vết như phần còn lại của bệnh án.
                    await record_event(
                        conn,
                        event_type="clinical_record.vitals_saved",
                        aggregate_type="visit",
                        aggregate_id=str(visit_id),
                        identity=identity,
                        origin="api:clinical-record",
                        payload={
                            "visit_id": str(visit_id),
                            "appointment_id": appointment_id,
                            "vitals_only": True,
                        },
                    )
                    return {"visit_id": str(visit_id), "vitals_only": True}

                await conn.execute(
                    """
                    INSERT INTO clinical_record (
                        clinic_id, visit_id, chief_complaint_at_visit,
                        soap_subjective, soap_objective, soap_assessment, soap_plan
                    )
                    VALUES ($7::uuid, $1::uuid, $2, $3, $4, $5, $6)
                    ON CONFLICT (visit_id) DO UPDATE SET
                        chief_complaint_at_visit = EXCLUDED.chief_complaint_at_visit,
                        soap_subjective          = EXCLUDED.soap_subjective,
                        soap_objective           = EXCLUDED.soap_objective,
                        soap_assessment          = EXCLUDED.soap_assessment,
                        soap_plan                = EXCLUDED.soap_plan
                    """,
                    visit_id,
                    (chief_complaint or "").strip() or None,
                    _json_or_none(subjective),
                    _json_or_none(
                        merge_objective(
                            stored, objective, incoming_was_sent=objective_sent
                        )
                    ),
                    _json_or_none(assessment),
                    _json_or_none(plan),
                    identity.clinic_id,
                )

                if profile:
                    await self._save_profile(
                        conn, clinic_patient_id, profile, identity.clinic_id
                    )

                if prescriptions is not None:
                    await self._replace_prescriptions(
                        conn,
                        visit_id=visit_id,
                        clinic_patient_id=clinic_patient_id,
                        prescriptions=prescriptions,
                        clinic_id=identity.clinic_id,
                    )

                # TÊN PHẦN ĐÃ GHI, KHÔNG PHẢI NỘI DUNG. "Ai sửa bệnh án nào,
                # lúc nào, đụng những mục nào" trả lời được câu hỏi của quản lý
                # và của thanh tra; nội dung bệnh án thì thuộc màn khác, RLS
                # khác, và một nhóm người khác được đọc (xem services/audit.py).
                await record_event(
                    conn,
                    event_type="clinical_record.saved",
                    aggregate_type="visit",
                    aggregate_id=str(visit_id),
                    identity=identity,
                    origin="api:clinical-record",
                    payload={
                        "visit_id": str(visit_id),
                        "appointment_id": appointment_id,
                        "sections": sorted(
                            name
                            for name, value in (
                                ("chief_complaint", chief_complaint),
                                ("subjective", subjective),
                                ("objective", objective),
                                ("assessment", assessment),
                                ("plan", plan),
                                ("profile", profile),
                            )
                            if value
                        ),
                        "prescription_count": (
                            len(prescriptions) if prescriptions is not None else None
                        ),
                    },
                )

        logger.info(
            "clinical_record_saved",
            visit_id=str(visit_id),
            vitals_only=vitals_only,
            by_staff_id=identity.staff_id,
        )
        return {"visit_id": str(visit_id), "vitals_only": False}

    async def _writable_visit(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: str,
        clinic_patient_id: str,
        appointment_doctor_id: Any,
        identity: StaffIdentity,
        vitals_only: bool,
    ) -> Any:
        """Find the appointment's visit or create a draft, refusing closed ones."""
        existing = await conn.fetchrow(
            """
            SELECT visit_id, status, created_at, clinic_patient_id
              FROM visit
             WHERE appointment_id = $1::uuid AND clinic_id = $2::uuid
             ORDER BY created_at DESC
             LIMIT 1
             FOR UPDATE
            """,
            appointment_id,
            identity.clinic_id,
        )

        if existing is not None:
            if str(existing["clinic_patient_id"]) != clinic_patient_id:
                raise ValidationError(
                    "Lượt khám không thuộc bệnh nhân của lịch hẹn này"
                )
            created_at = existing["created_at"]
            if created_at is not None:
                age = datetime.now(timezone.utc) - created_at
                if age > RECORD_LOCK:
                    raise SafetyGateError(
                        "Hồ sơ đã khóa sau 48h — không thể chỉnh sửa. "
                        "Liên hệ Trưởng ca nếu cần đính chính."
                    )
            if existing["status"] not in WRITABLE_VISIT_STATUSES:
                raise ConflictError(
                    f"Hồ sơ đã chốt ({existing['status']}) — luật cấm sửa, "
                    "phải đính chính."
                )
            return existing["visit_id"]

        # A nurse or secretary opening the visit does not become the attending
        # doctor — the appointment's doctor does.
        attending = (
            appointment_doctor_id
            if (vitals_only or identity.role in ON_BEHALF_ROLES)
            else identity.staff_id
        )

        visit_id = await conn.fetchval(
            """
            INSERT INTO visit (
                clinic_id, clinic_patient_id, appointment_id,
                attending_doctor_id, status, checked_in_at
            )
            VALUES ($4::uuid, $1::uuid, $2::uuid, $3::uuid,
                    'IN_PROGRESS', now())
            ON CONFLICT (appointment_id) WHERE appointment_id IS NOT NULL
            DO NOTHING
            RETURNING visit_id
            """,
            clinic_patient_id,
            appointment_id,
            str(attending) if attending else None,
            identity.clinic_id,
        )
        if visit_id is not None:
            return visit_id

        # A nurse and doctor can both observe no visit. ON CONFLICT keeps the
        # transaction usable (unlike catching a UniqueViolation after it has
        # aborted PostgreSQL's transaction), then this row lock serializes the
        # objective merge with the winner.
        again = await conn.fetchrow(
            """
            SELECT visit_id, status, clinic_patient_id FROM visit
             WHERE appointment_id = $1::uuid AND clinic_id = $2::uuid
             ORDER BY created_at DESC LIMIT 1
             FOR UPDATE
            """,
            appointment_id,
            identity.clinic_id,
        )
        if again is None:
            raise ConflictError(
                "Lượt khám vừa được tạo nhưng chưa thể đọc lại, hãy thử lại"
            )
        if str(again["clinic_patient_id"]) != clinic_patient_id:
            raise ValidationError("Lượt khám không thuộc bệnh nhân của lịch hẹn này")
        if again["status"] not in WRITABLE_VISIT_STATUSES:
            raise ConflictError(f"Hồ sơ đã chốt ({again['status']}) — luật cấm sửa.")
        return again["visit_id"]

    async def _save_vitals(
        self,
        conn: asyncpg.Connection,
        *,
        visit_id: Any,
        stored_objective: Any,
        objective: Any,
        chief_complaint: str | None,
        clinic_id: str | None,
    ) -> None:
        merged = merge_vitals_only(stored_objective, objective)
        complaint = (chief_complaint or "").strip()

        # The complaint is only written when the nurse typed one; an empty save
        # must not erase what the doctor already recorded.
        await conn.execute(
            """
            INSERT INTO clinical_record
                (clinic_id, visit_id, soap_objective, chief_complaint_at_visit)
            VALUES ($4::uuid, $1::uuid, $2, $3)
            ON CONFLICT (visit_id) DO UPDATE SET
                soap_objective = EXCLUDED.soap_objective,
                chief_complaint_at_visit = COALESCE(
                    EXCLUDED.chief_complaint_at_visit,
                    clinical_record.chief_complaint_at_visit
                )
            """,
            visit_id,
            json.dumps(merged),
            complaint or None,
            clinic_id,
        )

    async def _save_profile(
        self,
        conn: asyncpg.Connection,
        clinic_patient_id: str,
        profile: dict[str, Any],
        clinic_id: str | None,
    ) -> None:
        safe_profile = validated_profile(profile)
        columns = list(safe_profile)
        if not columns:
            return
        assignments = ", ".join(f"{col} = ${i + 2}" for i, col in enumerate(columns))
        placeholders = ", ".join(f"${i + 2}" for i in range(len(columns)))
        await conn.execute(
            f"""
            INSERT INTO patient_medical_profile
                (clinic_id, clinic_patient_id, {", ".join(columns)})
            VALUES (${len(columns) + 2}::uuid, $1::uuid, {placeholders})
            ON CONFLICT (clinic_patient_id) DO UPDATE SET {assignments}
            """,
            clinic_patient_id,
            *[safe_profile[col] for col in columns],
            clinic_id,
        )

    async def _replace_prescriptions(
        self,
        conn: asyncpg.Connection,
        *,
        visit_id: Any,
        clinic_patient_id: str,
        prescriptions: list[dict[str, Any]],
        clinic_id: str | None,
    ) -> None:
        """The visit's prescription is replaced wholesale, as the route did."""
        await conn.execute(
            "DELETE FROM prescription "
            "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
            visit_id,
            clinic_id,
        )
        rows = [
            (
                f"dash-rx-{visit_id}-{index}",
                clinic_patient_id,
                str(visit_id),
                (item.get("drug_name") or "").strip(),
                (item.get("quantity") or "").strip() or None,
                (item.get("dosage") or "").strip() or None,
                (item.get("caution") or "").strip() or None,
                clinic_id,
            )
            for index, item in enumerate(prescriptions)
            if (item.get("drug_name") or "").strip()
        ]
        if not rows:
            return
        await conn.executemany(
            """
            INSERT INTO prescription (
                source_ref, clinic_patient_id, visit_id, drug_name_raw,
                quantity, dosage_instructions, caution, clinic_id
            )
            VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6, $7, $8::uuid)
            """,
            rows,
        )


def _json_or_none(value: Any) -> str | None:
    return None if value is None else json.dumps(value)
