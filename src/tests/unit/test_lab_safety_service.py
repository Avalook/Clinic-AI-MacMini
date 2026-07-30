"""Safety regressions for durable lab triage and doctor finalisation."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.lab_safety_service import (
    LabSafetyService,
    PersistClassificationOutcome,
)

CLINIC_ID = UUID("a0000000-0000-4000-8000-000000000001")
PATIENT_ID = uuid4()
LAB_RESULT_ID = uuid4()
STAFF_ID = uuid4()
NOW = datetime(2026, 7, 30, 16, 0, tzinfo=timezone.utc)


def _doctor() -> StaffIdentity:
    return StaffIdentity(
        staff_id=str(STAFF_ID),
        auth_user_id=str(uuid4()),
        full_name="Bác sĩ Test",
        department="DOCTOR",
        role=ClinicRole.DOCTOR,
        clinic_id=str(CLINIC_ID),
    )


def _pool() -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    transaction_ctx = AsyncMock()
    conn.transaction = MagicMock(return_value=transaction_ctx)
    return pool, conn


@pytest.mark.asyncio
async def test_persist_is_tenant_scoped_and_preserves_finalized() -> None:
    pool, conn = _pool()
    conn.fetchrow.side_effect = [
        {
            "lab_result_id": LAB_RESULT_ID,
            "triage_group": "PENDING",
            "triage_reason": None,
            "triage_model": None,
            "triage_classified_at": None,
            "requires_doctor_review": False,
            "is_finalized": False,
        },
        {"lab_result_id": LAB_RESULT_ID},
    ]

    persisted = await LabSafetyService(pool).persist_classification(
        lab_result_id=LAB_RESULT_ID,
        clinic_id=CLINIC_ID,
        triage_group="GROUP_C",
        triage_reason="Cần bác sĩ xem ngay",
        requires_doctor_review=True,
        triage_model="RULE",
    )

    assert persisted == PersistClassificationOutcome(
        triage_group="GROUP_C",
        triage_reason="Cần bác sĩ xem ngay",
        requires_doctor_review=True,
        triage_model="RULE",
        is_finalized=False,
        changed=True,
    )
    assert "FOR UPDATE" in conn.fetchrow.await_args_list[0].args[0]
    sql, *args = conn.fetchrow.await_args_list[1].args
    assert "clinic_id = $2::uuid" in sql
    assert "is_finalized = FALSE" in sql
    assert "triage_classified_at" in sql
    assert args[:2] == [LAB_RESULT_ID, CLINIC_ID]


@pytest.mark.asyncio
async def test_persist_classification_reports_finalization_race_without_overwrite() -> (
    None
):
    pool, conn = _pool()
    conn.fetchrow.return_value = None

    persisted = await LabSafetyService(pool).persist_classification(
        lab_result_id=LAB_RESULT_ID,
        clinic_id=CLINIC_ID,
        triage_group="GROUP_A",
        triage_reason="Bình thường",
        requires_doctor_review=False,
        triage_model="RULE",
    )

    assert persisted is None


@pytest.mark.asyncio
async def test_persist_never_downgrades_group_c_on_retry() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = {
        "lab_result_id": LAB_RESULT_ID,
        "triage_group": "GROUP_C",
        "triage_reason": "Nguy cơ cao",
        "triage_model": "RULE",
        "triage_classified_at": NOW,
        "requires_doctor_review": True,
        "is_finalized": False,
    }

    outcome = await LabSafetyService(pool).persist_classification(
        lab_result_id=LAB_RESULT_ID,
        clinic_id=CLINIC_ID,
        triage_group="GROUP_A",
        triage_reason="Retry cho kết quả thấp hơn",
        requires_doctor_review=False,
        triage_model="LLM_HAIKU",
    )

    assert outcome is not None
    assert outcome.triage_group == "GROUP_C"
    assert outcome.triage_reason == "Nguy cơ cao"
    assert outcome.requires_doctor_review is True
    assert outcome.changed is False
    assert conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_persist_exact_retry_is_idempotent() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = {
        "lab_result_id": LAB_RESULT_ID,
        "triage_group": "GROUP_B",
        "triage_reason": "Cần bác sĩ xem",
        "triage_model": "RULE",
        "triage_classified_at": NOW,
        "requires_doctor_review": True,
        "is_finalized": False,
    }

    outcome = await LabSafetyService(pool).persist_classification(
        lab_result_id=LAB_RESULT_ID,
        clinic_id=CLINIC_ID,
        triage_group="GROUP_B",
        triage_reason="Cần bác sĩ xem",
        requires_doctor_review=True,
        triage_model="RULE",
    )

    assert outcome is not None
    assert outcome.changed is False
    assert conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_persist_can_only_raise_severity() -> None:
    pool, conn = _pool()
    conn.fetchrow.side_effect = [
        {
            "lab_result_id": LAB_RESULT_ID,
            "triage_group": "GROUP_A",
            "triage_reason": "Bình thường",
            "triage_model": "RULE",
            "triage_classified_at": NOW,
            "requires_doctor_review": False,
            "is_finalized": False,
        },
        {"lab_result_id": LAB_RESULT_ID},
    ]

    outcome = await LabSafetyService(pool).persist_classification(
        lab_result_id=LAB_RESULT_ID,
        clinic_id=CLINIC_ID,
        triage_group="GROUP_C",
        triage_reason="Phát hiện nguy cơ cao",
        requires_doctor_review=True,
        triage_model="RULE",
    )

    assert outcome is not None
    assert outcome.triage_group == "GROUP_C"
    assert outcome.changed is True


@pytest.mark.asyncio
async def test_finalize_rejects_wrong_patient_or_tenant_without_leaking_row() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = None

    with pytest.raises(NotFoundError):
        await LabSafetyService(pool).finalize_review(
            lab_result_id=LAB_RESULT_ID,
            clinic_patient_id=PATIENT_ID,
            identity=_doctor(),
        )

    sql, lab_result_id, clinic_id, patient_id = conn.fetchrow.await_args.args
    assert "clinic_id = $2::uuid" in sql
    assert "clinic_patient_id = $3::uuid" in sql
    assert (lab_result_id, clinic_id, patient_id) == (
        LAB_RESULT_ID,
        CLINIC_ID,
        PATIENT_ID,
    )
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_fails_closed_while_triage_is_pending() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = {
        "lab_result_id": LAB_RESULT_ID,
        "clinic_patient_id": PATIENT_ID,
        "triage_group": "PENDING",
        "requires_doctor_review": True,
        "is_finalized": False,
        "reviewed_by_staff_id": None,
        "reviewed_at": None,
        "has_result": True,
    }

    with pytest.raises(ValidationError, match="phân loại"):
        await LabSafetyService(pool).finalize_review(
            lab_result_id=LAB_RESULT_ID,
            clinic_patient_id=PATIENT_ID,
            identity=_doctor(),
        )

    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_is_idempotent_after_first_success() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = {
        "lab_result_id": LAB_RESULT_ID,
        "clinic_patient_id": PATIENT_ID,
        "triage_group": "GROUP_C",
        "requires_doctor_review": True,
        "is_finalized": True,
        "reviewed_by_staff_id": STAFF_ID,
        "reviewed_at": NOW,
        "has_result": True,
    }

    outcome = await LabSafetyService(pool).finalize_review(
        lab_result_id=LAB_RESULT_ID,
        clinic_patient_id=PATIENT_ID,
        identity=_doctor(),
    )

    assert outcome.already_finalized is True
    assert outcome.reviewed_at == NOW
    assert conn.fetchrow.await_count == 1
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_updates_result_closes_review_task_and_writes_audit_event() -> (
    None
):
    pool, conn = _pool()
    pending = {
        "lab_result_id": LAB_RESULT_ID,
        "clinic_patient_id": PATIENT_ID,
        "triage_group": "GROUP_C",
        "requires_doctor_review": True,
        "is_finalized": False,
        "reviewed_by_staff_id": None,
        "reviewed_at": None,
        "has_result": True,
    }
    finalized = {
        **pending,
        "is_finalized": True,
        "reviewed_by_staff_id": STAFF_ID,
        "reviewed_at": NOW,
    }
    conn.fetchrow.side_effect = [pending, finalized]

    outcome = await LabSafetyService(pool).finalize_review(
        lab_result_id=LAB_RESULT_ID,
        clinic_patient_id=PATIENT_ID,
        identity=_doctor(),
    )

    assert outcome.already_finalized is False
    assert outcome.triage_group == "GROUP_C"
    update_sql, *update_args = conn.fetchrow.await_args_list[1].args
    assert "is_finalized = TRUE" in update_sql
    assert "clinic_id = $2::uuid" in update_sql
    assert "clinic_patient_id = $3::uuid" in update_sql
    assert update_args[:4] == [LAB_RESULT_ID, CLINIC_ID, PATIENT_ID, STAFF_ID]

    assert conn.execute.await_count == 2
    close_task_sql = conn.execute.await_args_list[0].args[0]
    assert "UPDATE staff_task" in close_task_sql
    assert "task_type = 'LAB_REVIEW'" in close_task_sql
    assert "clinic_id = $1::uuid" in close_task_sql
    audit_sql = conn.execute.await_args_list[1].args[0]
    assert "INSERT INTO event_log" in audit_sql
    assert "clinic_id" in audit_sql
