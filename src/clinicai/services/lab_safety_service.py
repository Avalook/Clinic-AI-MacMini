"""Durable lab triage and the doctor-only finalisation safety gate.

The triage graph is deliberately separated from this persistence boundary:
classification may use rules/LLM, while this service owns the transactional
facts that other processes rely on.  In particular, a classifier must never
overwrite a result that a doctor finalised between fetch and persist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

_TRIAGE_SEVERITY = {
    "PENDING": 0,
    "GROUP_A": 1,
    "GROUP_B": 2,
    "GROUP_C": 3,
}


@dataclass(frozen=True)
class PersistClassificationOutcome:
    """The effective durable triage state after a monotonic write attempt."""

    triage_group: str
    triage_reason: str | None
    requires_doctor_review: bool
    triage_model: str | None
    is_finalized: bool
    changed: bool


@dataclass(frozen=True)
class LabReviewOutcome:
    """Immutable result returned by a doctor review/finalisation."""

    lab_result_id: UUID
    clinic_patient_id: UUID
    triage_group: str
    is_finalized: bool
    reviewed_by_staff_id: UUID
    reviewed_at: datetime
    already_finalized: bool


@dataclass(frozen=True)
class LabSendBackOutcome:
    """What a doctor's "send back for correction" left behind."""

    lab_result_id: UUID
    task_id: UUID
    already_open: bool


# Free text, not an enum: staff_task.task_type has no CHECK constraint, and
# finalize_review already closes 'LAB_REVIEW' the same way.
SEND_BACK_TASK_TYPE = "LAB_RESULT_FIX"
SEND_BACK_TASK_PRIORITY = "HIGH"
# A reason is what the lab has to act on. "sai" tells nobody what to redo.
MIN_SEND_BACK_REASON = 5
MAX_SEND_BACK_REASON = 500


def normalize_send_back_reason(raw: str | None) -> str:
    """Trim and bound the doctor's reason, or refuse the send-back."""
    reason = (raw or "").strip()
    if len(reason) < MIN_SEND_BACK_REASON:
        raise ValidationError(f"Lý do trả lại phải từ {MIN_SEND_BACK_REASON} ký tự")
    return reason[:MAX_SEND_BACK_REASON]


class LabSafetyService:
    """Persist triage and atomically finalise a reviewed lab result."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def persist_classification(
        self,
        *,
        lab_result_id: UUID,
        clinic_id: UUID,
        triage_group: str,
        triage_reason: str | None,
        requires_doctor_review: bool,
        triage_model: str | None,
    ) -> PersistClassificationOutcome | None:
        """Persist only severity-preserving classifier output.

        Replays are true no-ops. A later classifier may raise A → B → C, but
        may never lower an existing result. Doctor-review requirements are
        monotonic too: once raised they cannot be cleared by an AI retry.
        ``None`` means the tenant-bound row no longer exists.
        """
        if triage_group not in _TRIAGE_SEVERITY:
            raise ValidationError("Nhóm phân loại xét nghiệm không hợp lệ")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """
                    SELECT lab_result_id, triage_group, triage_reason,
                           triage_model, triage_classified_at,
                           requires_doctor_review, is_finalized
                      FROM lab_result
                     WHERE lab_result_id = $1
                       AND clinic_id = $2::uuid
                     FOR UPDATE
                    """,
                    lab_result_id,
                    clinic_id,
                )
                if current is None:
                    return None

                current_group = str(current["triage_group"])
                if current_group not in _TRIAGE_SEVERITY:
                    raise ConflictError("Nhóm phân loại đã lưu không hợp lệ")
                if bool(current["is_finalized"]):
                    return _classification_outcome(current, changed=False)

                severity_increases = (
                    _TRIAGE_SEVERITY[triage_group] > _TRIAGE_SEVERITY[current_group]
                )
                initial_pending_classification = (
                    current_group == "PENDING"
                    and triage_group == "PENDING"
                    and current["triage_classified_at"] is None
                )
                replace_classification = (
                    severity_increases or initial_pending_classification
                )
                review_escalates = requires_doctor_review and not bool(
                    current["requires_doctor_review"]
                )
                if not replace_classification and not review_escalates:
                    return _classification_outcome(current, changed=False)

                effective_group = (
                    triage_group if replace_classification else current_group
                )
                effective_reason = (
                    triage_reason
                    if replace_classification
                    else current["triage_reason"]
                )
                effective_model = (
                    triage_model if replace_classification else current["triage_model"]
                )
                effective_review = bool(
                    current["requires_doctor_review"] or requires_doctor_review
                )
                updated = await conn.fetchrow(
                    """
                    UPDATE lab_result
                       SET triage_group = $3,
                           triage_reason = $4,
                           requires_doctor_review = $5,
                           triage_classified_at = CASE
                               WHEN $7 THEN now()
                               ELSE triage_classified_at
                           END,
                           triage_model = $6,
                           updated_at = now()
                     WHERE lab_result_id = $1
                       AND clinic_id = $2::uuid
                       AND is_finalized = FALSE
                    RETURNING lab_result_id
                    """,
                    lab_result_id,
                    clinic_id,
                    effective_group,
                    effective_reason,
                    effective_review,
                    effective_model,
                    replace_classification,
                )
                if updated is None:
                    raise ConflictError(
                        "Kết quả xét nghiệm đã thay đổi khi đang phân loại"
                    )

        return PersistClassificationOutcome(
            triage_group=effective_group,
            triage_reason=effective_reason,
            requires_doctor_review=effective_review,
            triage_model=effective_model,
            is_finalized=False,
            changed=True,
        )

    async def finalize_review(
        self,
        *,
        lab_result_id: UUID,
        clinic_patient_id: UUID,
        identity: StaffIdentity,
    ) -> LabReviewOutcome:
        """Doctor review + finalisation in one tenant/patient-bound transaction.

        Repeating an already-successful request is idempotent and does not
        append another audit event. A PENDING classifier state or an empty
        provider result is rejected so a click cannot manufacture a clinically
        final result from an unfinished order.
        """
        clinic_id = UUID(identity.clinic_id)
        reviewer_id = UUID(identity.staff_id)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """
                    SELECT lab_result_id, clinic_patient_id, triage_group,
                           requires_doctor_review, is_finalized,
                           reviewed_by_staff_id, reviewed_at,
                           (
                               NULLIF(btrim(result_value), '') IS NOT NULL
                               OR result_numeric IS NOT NULL
                               OR NULLIF(btrim(external_ref), '') IS NOT NULL
                               OR raw_payload IS NOT NULL
                           ) AS has_result
                      FROM lab_result
                     WHERE lab_result_id = $1
                       AND clinic_id = $2::uuid
                       AND clinic_patient_id = $3::uuid
                     FOR UPDATE
                    """,
                    lab_result_id,
                    clinic_id,
                    clinic_patient_id,
                )
                if current is None:
                    # One response for absent, cross-tenant and wrong-patient
                    # targets avoids turning the endpoint into an ID oracle.
                    raise NotFoundError("Không tìm thấy kết quả xét nghiệm")

                if bool(current["is_finalized"]):
                    return _review_outcome(current, already_finalized=True)

                if current["triage_group"] == "PENDING":
                    raise ValidationError(
                        "Kết quả chưa được phân loại; không thể hoàn tất duyệt"
                    )
                if not bool(current["has_result"]):
                    raise ValidationError(
                        "Chưa có dữ liệu kết quả xét nghiệm để hoàn tất duyệt"
                    )

                finalized = await conn.fetchrow(
                    """
                    UPDATE lab_result
                       SET reviewed_by_staff_id = $4::uuid,
                           reviewed_at = now(),
                           is_finalized = TRUE,
                           updated_at = now()
                     WHERE lab_result_id = $1
                       AND clinic_id = $2::uuid
                       AND clinic_patient_id = $3::uuid
                       AND is_finalized = FALSE
                    RETURNING lab_result_id, clinic_patient_id, triage_group,
                              requires_doctor_review, is_finalized,
                              reviewed_by_staff_id, reviewed_at
                    """,
                    lab_result_id,
                    clinic_id,
                    clinic_patient_id,
                    reviewer_id,
                )
                if finalized is None:
                    # The row is locked, so this indicates an invariant breach
                    # rather than a normal concurrent retry.
                    raise ConflictError("Kết quả xét nghiệm đã thay đổi khi đang duyệt")

                await conn.execute(
                    """
                    UPDATE staff_task
                       SET status = 'DONE',
                           completed_at = COALESCE(completed_at, now()),
                           updated_at = now()
                     WHERE clinic_id = $1::uuid
                       AND task_type = 'LAB_REVIEW'
                       AND source_type = 'LAB_RESULT'
                       AND source_id = $2::uuid
                       AND status IN ('PENDING', 'IN_PROGRESS')
                    """,
                    clinic_id,
                    lab_result_id,
                )
                await _append_finalized_event(
                    conn,
                    lab_result_id=lab_result_id,
                    triage_group=str(finalized["triage_group"]),
                    identity=identity,
                )

        logger.info(
            "lab_result_finalized",
            lab_result_id=str(lab_result_id),
            clinic_id=str(clinic_id),
            reviewed_by_staff_id=str(reviewer_id),
        )
        return _review_outcome(finalized, already_finalized=False)

    async def send_back_for_correction(
        self,
        *,
        lab_result_id: UUID,
        clinic_patient_id: UUID,
        reason: str,
        identity: StaffIdentity,
    ) -> LabSendBackOutcome:
        """Refuse a result and put the correction back on somebody's list.

        Deliberately touches nothing on the result row. The value stays exactly
        as the lab sent it — that is the evidence of what was rejected — and
        the safety gate stays closed, because ``requires_doctor_review`` and
        ``is_finalized`` are left alone. What changes is that the fix now has
        an owner instead of living in a doctor's head.

        Clicking twice does not file two tasks: an open one is reused.
        """
        clinic_id = UUID(identity.clinic_id)
        text = normalize_send_back_reason(reason)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """
                    SELECT lab_result_id, is_finalized
                    FROM lab_result
                    WHERE lab_result_id = $1
                      AND clinic_id = $2::uuid
                      AND clinic_patient_id = $3::uuid
                    FOR UPDATE
                    """,
                    lab_result_id,
                    clinic_id,
                    clinic_patient_id,
                )
                if current is None:
                    # One answer for absent, cross-tenant and wrong-patient,
                    # exactly as finalize_review: not an ID oracle.
                    raise NotFoundError("Không tìm thấy kết quả xét nghiệm")
                if bool(current["is_finalized"]):
                    # Finalising is the doctor's signature. Taking it back is a
                    # different act with different rules, not this endpoint.
                    raise ConflictError(
                        "Kết quả đã được duyệt; không trả lại chỉnh sửa được"
                    )

                open_task = await conn.fetchval(
                    """
                    SELECT task_id
                    FROM staff_task
                    WHERE clinic_id = $1::uuid
                      AND task_type = $2
                      AND source_type = 'LAB_RESULT'
                      AND source_id = $3::uuid
                      AND status IN ('PENDING', 'IN_PROGRESS')
                    ORDER BY created_at
                    LIMIT 1
                    """,
                    clinic_id,
                    SEND_BACK_TASK_TYPE,
                    lab_result_id,
                )
                if open_task is not None:
                    return LabSendBackOutcome(
                        lab_result_id=lab_result_id,
                        task_id=UUID(str(open_task)),
                        already_open=True,
                    )

                task_id = await conn.fetchval(
                    """
                    INSERT INTO staff_task
                        (clinic_id, task_type, priority, status, source_type,
                         source_id, title, description)
                    VALUES ($1::uuid, $2, $3, 'PENDING', 'LAB_RESULT',
                            $4::uuid, $5, $6)
                    RETURNING task_id
                    """,
                    clinic_id,
                    SEND_BACK_TASK_TYPE,
                    SEND_BACK_TASK_PRIORITY,
                    lab_result_id,
                    "Kết quả XN bị trả lại chỉnh sửa",
                    text,
                )
                await _append_send_back_event(
                    conn,
                    lab_result_id=lab_result_id,
                    task_id=UUID(str(task_id)),
                    identity=identity,
                )

        logger.info(
            "lab_result_sent_back",
            lab_result_id=str(lab_result_id),
            clinic_id=str(clinic_id),
            by_staff_id=identity.staff_id,
        )
        return LabSendBackOutcome(
            lab_result_id=lab_result_id,
            task_id=UUID(str(task_id)),
            already_open=False,
        )


def _review_outcome(row: Any, *, already_finalized: bool) -> LabReviewOutcome:
    reviewed_by = row["reviewed_by_staff_id"]
    reviewed_at = row["reviewed_at"]
    if reviewed_by is None or reviewed_at is None:
        raise ConflictError("Kết quả hoàn tất thiếu thông tin bác sĩ duyệt")
    return LabReviewOutcome(
        lab_result_id=UUID(str(row["lab_result_id"])),
        clinic_patient_id=UUID(str(row["clinic_patient_id"])),
        triage_group=str(row["triage_group"]),
        is_finalized=bool(row["is_finalized"]),
        reviewed_by_staff_id=UUID(str(reviewed_by)),
        reviewed_at=reviewed_at,
        already_finalized=already_finalized,
    )


async def _append_send_back_event(
    conn: asyncpg.Connection,
    *,
    lab_result_id: UUID,
    task_id: UUID,
    identity: StaffIdentity,
) -> None:
    """Record that a result was refused — without copying the result into it.

    The doctor's reason lives in ``staff_task.description``, where the person
    who has to redo the work will read it. ``event_log`` keeps the pointer.
    """
    await conn.execute(
        """
        INSERT INTO event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, actor_staff_id, event_published)
        VALUES ($1::uuid, 'lab_result.sent_back', 'lab_result', $2::uuid,
                $3::jsonb, $4::jsonb, 'api:lab-send-back', $5::uuid, FALSE)
        """,
        identity.clinic_id,
        str(lab_result_id),
        json.dumps(
            {
                "lab_result_id": str(lab_result_id),
                "task_id": str(task_id),
            }
        ),
        json.dumps(
            {
                "actor_role": identity.role.value,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": "api:lab-send-back",
            }
        ),
        identity.staff_id,
    )


def _classification_outcome(
    row: Any,
    *,
    changed: bool,
) -> PersistClassificationOutcome:
    return PersistClassificationOutcome(
        triage_group=str(row["triage_group"]),
        triage_reason=row["triage_reason"],
        requires_doctor_review=bool(row["requires_doctor_review"]),
        triage_model=row["triage_model"],
        is_finalized=bool(row["is_finalized"]),
        changed=changed,
    )


async def _append_finalized_event(
    conn: asyncpg.Connection,
    *,
    lab_result_id: UUID,
    triage_group: str,
    identity: StaffIdentity,
) -> None:
    await conn.execute(
        """
        INSERT INTO event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, actor_staff_id, event_published)
        VALUES ($1::uuid, 'lab_result.finalized', 'lab_result', $2::uuid,
                $3::jsonb, $4::jsonb, 'api:lab-review', $5::uuid, FALSE)
        """,
        identity.clinic_id,
        lab_result_id,
        json.dumps(
            {
                "lab_result_id": str(lab_result_id),
                "triage_group": triage_group,
            }
        ),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": "api:lab-review",
            }
        ),
        identity.staff_id,
    )
