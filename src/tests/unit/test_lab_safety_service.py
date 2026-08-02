"""Safety regressions for durable lab triage and doctor finalisation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.lab_safety_service import (
    SEND_BACK_TASK_TYPE,
    LabSafetyService,
    PersistClassificationOutcome,
)

CLINIC_ID = UUID("a0000000-0000-4000-8000-000000000001")
PATIENT_ID = uuid4()
LAB_RESULT_ID = uuid4()
STAFF_ID = uuid4()
TASK_ID = uuid4()
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


# --- Trả lại chỉnh sửa (B.4) -------------------------------------------------
#
# Đường này nguy hiểm đúng ở chỗ nó trông vô hại: nó "chỉ mở một việc". Nhưng nó
# đứng ngay cạnh cổng an toàn của kết quả, nên bốn thứ phải giữ nguyên: hàng
# lab_result không đổi, kết quả đã ký không rút lại được bằng đường này, bấm hai
# lần không mở hai việc, và event_log không mang theo nội dung lâm sàng.


def _open_result() -> dict[str, object]:
    return {"lab_result_id": LAB_RESULT_ID, "is_finalized": False}


@pytest.mark.asyncio
async def test_send_back_rejects_wrong_patient_or_tenant_without_leaking_row() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = None

    with pytest.raises(NotFoundError):
        await LabSafetyService(pool).send_back_for_correction(
            lab_result_id=LAB_RESULT_ID,
            clinic_patient_id=PATIENT_ID,
            reason="Sai đơn vị đo",
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
    conn.fetchval.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_back_refuses_to_reopen_a_signed_result() -> None:
    # Rút lại chữ ký là một hành động khác, với luật khác. 409 chứ không phải
    # 404: kết quả có thật, chỉ là không đi cửa này.
    pool, conn = _pool()
    conn.fetchrow.return_value = {
        "lab_result_id": LAB_RESULT_ID,
        "is_finalized": True,
    }

    with pytest.raises(ConflictError):
        await LabSafetyService(pool).send_back_for_correction(
            lab_result_id=LAB_RESULT_ID,
            clinic_patient_id=PATIENT_ID,
            reason="Sai đơn vị đo",
            identity=_doctor(),
        )

    conn.fetchval.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_back_requires_a_reason_worth_reading() -> None:
    pool, conn = _pool()

    with pytest.raises(ValidationError):
        await LabSafetyService(pool).send_back_for_correction(
            lab_result_id=LAB_RESULT_ID,
            clinic_patient_id=PATIENT_ID,
            reason="sai",
            identity=_doctor(),
        )

    # Lý do được kiểm trước khi mở kết nối: một chuỗi rỗng không đáng khoá hàng.
    conn.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_back_opens_one_task_and_leaves_the_result_untouched() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = _open_result()
    conn.fetchval.side_effect = [None, TASK_ID]

    outcome = await LabSafetyService(pool).send_back_for_correction(
        lab_result_id=LAB_RESULT_ID,
        clinic_patient_id=PATIENT_ID,
        reason="Đơn vị đo ghi mg/L, phiếu gốc là mmol/L",
        identity=_doctor(),
    )

    assert outcome.task_id == TASK_ID
    assert outcome.already_open is False

    # Không một câu lệnh nào trong cả giao dịch được ghi vào lab_result. Nếu có,
    # "trả lại" đã trở thành một đường phát hành kết quả chưa ai duyệt.
    statements = [call.args[0] for call in conn.fetchval.await_args_list] + [
        call.args[0] for call in conn.execute.await_args_list
    ]
    assert all("UPDATE lab_result" not in sql for sql in statements)
    assert all("requires_doctor_review" not in sql for sql in statements)

    insert_sql, *insert_args = conn.fetchval.await_args_list[1].args
    assert "INSERT INTO staff_task" in insert_sql
    assert insert_args[0] == CLINIC_ID
    assert insert_args[1] == SEND_BACK_TASK_TYPE
    # Lý do đi vào staff_task, nơi người phải sửa sẽ đọc nó.
    assert "mmol/L" in insert_args[-1]


@pytest.mark.asyncio
async def test_send_back_twice_reuses_the_open_task() -> None:
    # Hai bác sĩ cùng mở hàng đợi, hoặc một người bấm đúp: phòng xét nghiệm nhận
    # đúng một việc, không phải hai dòng giống hệt nhau.
    pool, conn = _pool()
    conn.fetchrow.return_value = _open_result()
    conn.fetchval.return_value = TASK_ID

    outcome = await LabSafetyService(pool).send_back_for_correction(
        lab_result_id=LAB_RESULT_ID,
        clinic_patient_id=PATIENT_ID,
        reason="Đơn vị đo ghi sai",
        identity=_doctor(),
    )

    assert outcome.already_open is True
    assert outcome.task_id == TASK_ID
    assert conn.fetchval.await_count == 1
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_back_audit_event_carries_no_clinical_text() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = _open_result()
    conn.fetchval.side_effect = [None, TASK_ID]
    reason = "Kết quả Hb 4.1 g/dL không khớp phiếu gốc"

    await LabSafetyService(pool).send_back_for_correction(
        lab_result_id=LAB_RESULT_ID,
        clinic_patient_id=PATIENT_ID,
        reason=reason,
        identity=_doctor(),
    )

    audit_sql, *audit_args = conn.execute.await_args.args
    assert "INSERT INTO event_log" in audit_sql
    assert "'lab_result.sent_back'" in audit_sql
    payload = json.loads(audit_args[2])
    assert payload == {
        "lab_result_id": str(LAB_RESULT_ID),
        "task_id": str(TASK_ID),
    }
    # event_log là sổ vận hành, không phải bản sao hồ sơ bệnh án: nó ghi lại
    # việc đã xảy ra và trỏ tới nơi giữ chi tiết.
    assert reason not in audit_args[2]
    assert audit_args[-1] == str(STAFF_ID)
