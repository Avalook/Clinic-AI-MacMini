"""Cross-resource integrity gates for clinical and financial writes.

Foreign keys prove that an id exists. They do not prove that a client-supplied
patient, appointment, visit, location, service and doctor all describe the
same clinic encounter. These tests pin that stronger invariant at the service
boundary, where the backend is operating with owner privileges.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.booking_service import BookingService
from clinicai.services.clinical_record_service import ClinicalRecordService
from clinicai.services.lab_order_service import LabOrderService
from clinicai.services.payment_service import PaymentService
from clinicai.services.ultrasound_service import UltrasoundService

CLINIC_ID = "a0000000-0000-4000-8000-000000000001"
PATIENT_ID = "a2000000-0000-4000-8000-000000000001"
OTHER_PATIENT_ID = "a2000000-0000-4000-8000-000000000002"
APPOINTMENT_ID = "a3000000-0000-4000-8000-000000000001"
VISIT_ID = "a4000000-0000-4000-8000-000000000001"
STAFF_ID = "a5000000-0000-4000-8000-000000000001"
LOCATION_ID = "a6000000-0000-4000-8000-000000000001"
SERVICE_ID = "a7000000-0000-4000-8000-000000000001"


class _AsyncContext:
    def __init__(self, value: Any) -> None:
        self.value = value
        self.entered = 0

    async def __aenter__(self) -> Any:
        self.entered += 1
        return self.value

    async def __aexit__(self, *_: object) -> None:
        return None


def _pool_and_conn() -> tuple[MagicMock, AsyncMock, _AsyncContext]:
    pool = MagicMock()
    conn = AsyncMock()
    transaction = _AsyncContext(conn)
    conn.transaction = MagicMock(return_value=transaction)
    pool.acquire.return_value = _AsyncContext(conn)
    return pool, conn, transaction


def _identity(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id=STAFF_ID,
        auth_user_id="a1000000-0000-4000-8000-000000000001",
        full_name="Nhân viên thử",
        department=role.value,
        role=role,
        clinic_id=CLINIC_ID,
    )


@pytest.mark.asyncio
async def test_clinical_record_rejects_patient_not_owned_by_appointment() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.side_effect = [
        {
            "status": "CHECKED_IN",
            "doctor_id": STAFF_ID,
            "clinic_patient_id": OTHER_PATIENT_ID,
            "patient_in_clinic": True,
            "doctor_in_clinic": True,
        },
        None,
    ]
    conn.fetchval.side_effect = [VISIT_ID, None]

    with pytest.raises(ValidationError, match="bệnh nhân"):
        await ClinicalRecordService(pool).save(
            appointment_id=APPOINTMENT_ID,
            clinic_patient_id=PATIENT_ID,
            identity=_identity(ClinicRole.DOCTOR),
        )

    assert not any(
        "INSERT INTO clinical_record" in str(call) for call in conn.execute.calls
    )
    appointment_sql = conn.fetchrow.await_args_list[0].args[0]
    assert "st.is_active" in appointment_sql
    assert "m.is_active" in appointment_sql
    assert "'DOCTOR', 'ULTRASOUND_DOCTOR'" in appointment_sql


@pytest.mark.asyncio
async def test_clinical_record_rejects_visit_owned_by_another_patient() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.side_effect = [
        {
            "status": "CHECKED_IN",
            "doctor_id": STAFF_ID,
            "clinic_patient_id": PATIENT_ID,
            "patient_in_clinic": True,
            "doctor_in_clinic": True,
        },
        {
            "visit_id": VISIT_ID,
            "status": "IN_PROGRESS",
            "created_at": datetime.now(timezone.utc),
            "clinic_patient_id": OTHER_PATIENT_ID,
        },
    ]

    with pytest.raises(ValidationError, match="bệnh nhân"):
        await ClinicalRecordService(pool).save(
            appointment_id=APPOINTMENT_ID,
            clinic_patient_id=PATIENT_ID,
            identity=_identity(ClinicRole.DOCTOR),
        )


@pytest.mark.asyncio
async def test_concurrent_visit_create_joins_and_locks_the_winner() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.side_effect = [
        None,
        {
            "visit_id": VISIT_ID,
            "status": "IN_PROGRESS",
            "clinic_patient_id": PATIENT_ID,
        },
    ]
    conn.fetchval.return_value = None
    service = ClinicalRecordService(pool)

    result = await service._writable_visit(
        conn,
        appointment_id=APPOINTMENT_ID,
        clinic_patient_id=PATIENT_ID,
        appointment_doctor_id=STAFF_ID,
        identity=_identity(ClinicRole.DOCTOR),
        vitals_only=False,
    )

    assert result == VISIT_ID
    assert "FOR UPDATE" in conn.fetchrow.await_args_list[0].args[0]
    insert_sql = conn.fetchval.await_args.args[0]
    assert "ON CONFLICT (appointment_id)" in insert_sql
    assert "DO NOTHING" in insert_sql
    assert "FOR UPDATE" in conn.fetchrow.await_args_list[1].args[0]


@pytest.mark.asyncio
async def test_clinical_record_save_locks_visit_and_record_before_merge() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.side_effect = [
        {
            "status": "CHECKED_IN",
            "doctor_id": STAFF_ID,
            "clinic_patient_id": PATIENT_ID,
            "patient_in_clinic": True,
            "doctor_in_clinic": True,
        },
        {
            "visit_id": VISIT_ID,
            "status": "IN_PROGRESS",
            "created_at": datetime.now(timezone.utc),
            "clinic_patient_id": PATIENT_ID,
        },
    ]
    conn.fetchval.return_value = {"vitals": {"bp": "120/80"}}

    await ClinicalRecordService(pool).save(
        appointment_id=APPOINTMENT_ID,
        clinic_patient_id=PATIENT_ID,
        identity=_identity(ClinicRole.DOCTOR),
        objective={"vitals": {"pulse": 72}},
        objective_sent=True,
    )

    assert "FOR UPDATE" in conn.fetchrow.await_args_list[1].args[0]
    assert "FOR UPDATE" in conn.fetchval.await_args.args[0]


@pytest.mark.asyncio
async def test_ultrasound_rejects_patient_not_owned_by_appointment() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.side_effect = [
        {
            "clinic_patient_id": OTHER_PATIENT_ID,
            "patient_in_clinic": True,
            "performer_in_clinic": True,
        },
        None,
    ]
    conn.fetchval.return_value = VISIT_ID

    with pytest.raises(ValidationError, match="bệnh nhân"):
        await UltrasoundService(pool).save_measurements(
            appointment_id=APPOINTMENT_ID,
            clinic_patient_id=PATIENT_ID,
            measurements={"bpd": 42},
            is_abnormal=False,
            status=None,
            identity=_identity(ClinicRole.ULTRASOUND_DOCTOR),
        )

    assert not any(
        "INSERT INTO ultrasound_record" in str(call) for call in conn.execute.calls
    )


@pytest.mark.asyncio
async def test_ultrasound_rejects_visit_owned_by_another_patient() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.side_effect = [
        {
            "clinic_patient_id": PATIENT_ID,
            "patient_in_clinic": True,
            "performer_in_clinic": True,
        },
        {
            "visit_id": VISIT_ID,
            "status": "IN_PROGRESS",
            "clinic_patient_id": OTHER_PATIENT_ID,
        },
    ]

    with pytest.raises(ValidationError, match="bệnh nhân"):
        await UltrasoundService(pool).save_measurements(
            appointment_id=APPOINTMENT_ID,
            clinic_patient_id=PATIENT_ID,
            measurements={"bpd": 42},
            is_abnormal=False,
            status=None,
            identity=_identity(ClinicRole.ULTRASOUND_DOCTOR),
        )


@pytest.mark.asyncio
async def test_ultrasound_rejects_existing_record_for_another_patient() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.side_effect = [
        {
            "clinic_patient_id": PATIENT_ID,
            "patient_in_clinic": True,
            "performer_in_clinic": True,
        },
        {
            "visit_id": VISIT_ID,
            "status": "IN_PROGRESS",
            "clinic_patient_id": PATIENT_ID,
        },
        {
            "ultrasound_id": "ab000000-0000-4000-8000-000000000001",
            "findings": {},
            "clinic_patient_id": OTHER_PATIENT_ID,
        },
    ]

    with pytest.raises(ValidationError, match="Phiếu siêu âm"):
        await UltrasoundService(pool).save_measurements(
            appointment_id=APPOINTMENT_ID,
            clinic_patient_id=PATIENT_ID,
            measurements={"bpd": 42},
            is_abnormal=False,
            status=None,
            identity=_identity(ClinicRole.ULTRASOUND_DOCTOR),
        )

    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_lab_order_rejects_appointment_for_another_patient() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.return_value = {
        "patient_in_clinic": True,
        "appointment_patient_id": OTHER_PATIENT_ID,
    }
    conn.fetchval.return_value = "a8000000-0000-4000-8000-000000000001"

    with pytest.raises(ValidationError, match="bệnh nhân"):
        await LabOrderService(pool).order_test(
            clinic_patient_id=PATIENT_ID,
            test_name="Công thức máu",
            appointment_id=APPOINTMENT_ID,
            identity=_identity(ClinicRole.DOCTOR),
        )

    assert not any(
        "INSERT INTO lab_result" in str(call) for call in conn.fetchval.calls
    )


@pytest.mark.asyncio
async def test_lab_order_rejects_patient_outside_clinic_without_appointment() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.return_value = {
        "patient_in_clinic": False,
        "appointment_patient_id": None,
    }
    conn.fetchval.return_value = "a8000000-0000-4000-8000-000000000001"

    with pytest.raises(ValidationError, match="bệnh nhân"):
        await LabOrderService(pool).order_test(
            clinic_patient_id=PATIENT_ID,
            test_name="Công thức máu",
            appointment_id=None,
            identity=_identity(ClinicRole.DOCTOR),
        )


@pytest.mark.asyncio
async def test_finalized_lab_result_cannot_be_changed() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchval.return_value = None

    with pytest.raises(NotFoundError, match="đã chốt"):
        await LabOrderService(pool).enter_result(
            lab_result_id="a8000000-0000-4000-8000-000000000001",
            result_value="Âm tính",
            result_link=None,
            lab_provider=None,
            identity=_identity(ClinicRole.DOCTOR),
        )

    update_sql = conn.fetchval.await_args.args[0]
    assert "is_finalized = FALSE" in update_sql
    assert not conn.execute.await_args_list


@pytest.mark.asyncio
async def test_payment_rejects_patient_not_owned_by_visit() -> None:
    pool, conn, _ = _pool_and_conn()
    relation = {
        "appt_status": "COMPLETED",
        "clinic_patient_id": OTHER_PATIENT_ID,
        "staff_in_clinic": True,
    }
    pool.fetchrow = AsyncMock(return_value=relation)
    conn.fetchrow.return_value = relation
    conn.fetchval.return_value = "a9000000-0000-4000-8000-000000000001"

    with pytest.raises(ValidationError, match="bệnh nhân"):
        await PaymentService(pool).record_payment(
            visit_id=VISIT_ID,
            kind="dich_vu",
            amount=100_000,
            clinic_patient_id=PATIENT_ID,
            identity=_identity(ClinicRole.CASHIER),
        )

    assert not any(
        "INSERT INTO payment" in str(call) for call in conn.fetchrow.await_args_list
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [None, 0, -1, float("nan"), float("inf")])
async def test_payment_rejects_invalid_amount_before_touching_db(
    amount: object,
) -> None:
    pool = MagicMock()

    with pytest.raises(ValidationError, match="lớn hơn 0"):
        await PaymentService(pool).record_payment(
            visit_id=VISIT_ID,
            kind="dich_vu",
            amount=amount,
            clinic_patient_id=PATIENT_ID,
            identity=_identity(ClinicRole.CASHIER),
        )

    pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_payment_derives_patient_from_locked_visit() -> None:
    pool, conn, _ = _pool_and_conn()
    payment_id = "a9000000-0000-4000-8000-000000000001"
    cycle_id = "aa000000-0000-4000-8000-000000000001"
    conn.fetchrow.side_effect = [
        {
            "appt_status": "COMPLETED",
            "clinic_patient_id": PATIENT_ID,
            "staff_in_clinic": True,
        },
        None,
        {"id": payment_id, "payment_cycle_id": cycle_id},
    ]
    enqueue = AsyncMock()

    with patch(
        "clinicai.services.payment_service.pos_outbox.enqueue",
        new=enqueue,
    ):
        await PaymentService(pool).record_payment(
            visit_id=VISIT_ID,
            kind="dich_vu",
            amount=100_000,
            clinic_patient_id=None,
            identity=_identity(ClinicRole.CASHIER),
        )

    payment_write = conn.fetchrow.await_args_list[2]
    assert payment_write.args[2] == PATIENT_ID
    assert "payment_cycle_id  = gen_random_uuid()" in payment_write.args[0]
    assert "WHERE payment.status = 'VOIDED'" in payment_write.args[0]
    enqueue_call = enqueue.await_args
    assert enqueue_call is not None
    assert enqueue_call.kwargs["subject_id"] == cycle_id
    assert enqueue_call.kwargs["payload"]["clinic_reference"] == cycle_id
    assert enqueue_call.kwargs["payload"]["payment_id"] == payment_id
    assert any(
        call.args[1] == "payment.recorded" for call in conn.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_paid_amount_change_requires_void_first() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.side_effect = [
        {
            "appt_status": "COMPLETED",
            "clinic_patient_id": PATIENT_ID,
            "staff_in_clinic": True,
        },
        {
            "id": "a9000000-0000-4000-8000-000000000001",
            "status": "PAID",
            "amount": 100_000,
            "payment_cycle_id": "aa000000-0000-4000-8000-000000000001",
            "clinic_patient_id": PATIENT_ID,
        },
    ]

    with pytest.raises(ConflictError, match="hoàn tác"):
        await PaymentService(pool).record_payment(
            visit_id=VISIT_ID,
            kind="dich_vu",
            amount=120_000,
            clinic_patient_id=PATIENT_ID,
            identity=_identity(ClinicRole.CASHIER),
        )

    assert len(conn.fetchrow.await_args_list) == 2
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_paid_row_for_wrong_patient_requires_void_first() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.side_effect = [
        {
            "appt_status": "COMPLETED",
            "clinic_patient_id": PATIENT_ID,
            "staff_in_clinic": True,
        },
        {
            "id": "a9000000-0000-4000-8000-000000000001",
            "status": "PAID",
            "amount": 100_000,
            "payment_cycle_id": "aa000000-0000-4000-8000-000000000001",
            "clinic_patient_id": OTHER_PATIENT_ID,
        },
    ]

    with pytest.raises(ConflictError, match="sai bệnh nhân"):
        await PaymentService(pool).record_payment(
            visit_id=VISIT_ID,
            kind="dich_vu",
            amount=100_000,
            clinic_patient_id=PATIENT_ID,
            identity=_identity(ClinicRole.CASHIER),
        )

    assert len(conn.fetchrow.await_args_list) == 2
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("missing", "expected_message"),
    [
        ("patient_ok", "bệnh nhân"),
        ("location_ok", "cơ sở"),
        ("service_ok", "dịch vụ"),
        ("doctor_ok", "bác sĩ"),
    ],
)
async def test_booking_rejects_reference_outside_clinic(
    missing: str, expected_message: str
) -> None:
    pool, conn, _ = _pool_and_conn()
    refs = {
        "patient_ok": True,
        "location_ok": True,
        "service_ok": True,
        "doctor_ok": True,
    }
    refs[missing] = False
    conn.fetchrow.return_value = refs
    conn.fetch.return_value = []
    conn.fetchval.side_effect = [
        "a3000000-0000-4000-8000-000000000099",
        "aa000000-0000-4000-8000-000000000001",
    ]

    service = BookingService(pool)
    with (
        patch.object(service, "_doctor_conflict", AsyncMock(return_value=None)),
        patch.object(service, "_slot_full", AsyncMock(return_value=None)),
        patch.object(service, "_attach_episode", AsyncMock(return_value=None)),
        pytest.raises(ValidationError, match=expected_message),
    ):
        await service.create(
            clinic_patient_id=PATIENT_ID,
            service_type_id=SERVICE_ID,
            location_id=LOCATION_ID,
            slot_start=datetime.now(timezone.utc) + timedelta(days=1),
            slot_end=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
            identity=_identity(ClinicRole.CSKH),
            doctor_id=STAFF_ID,
        )

    assert not any(
        "INSERT INTO appointment" in str(call) for call in conn.fetchval.calls
    )


@pytest.mark.asyncio
async def test_booking_action_rejects_corrupt_cross_clinic_patient_link() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.return_value = {
        "id": APPOINTMENT_ID,
        "doctor_id": None,
        "status": "SCHEDULED",
        "clinic_patient_id": PATIENT_ID,
        "slot_start": datetime.now(timezone.utc),
        "slot_end": datetime.now(timezone.utc) + timedelta(minutes=30),
        "queue_number": None,
        "booking_channel": "PHONE",
        "patient_in_clinic": False,
        "location_in_clinic": True,
        "service_in_clinic": True,
        "doctor_in_clinic": True,
    }

    with pytest.raises(ValidationError, match="nhân"):
        await BookingService(pool).apply_action(
            appointment_id=APPOINTMENT_ID,
            action="cskh_confirm",
            identity=_identity(ClinicRole.CSKH),
        )

    assert not conn.fetchval.await_args_list
    assert not conn.execute.await_args_list


@pytest.mark.asyncio
async def test_cancel_can_repair_appointment_with_stale_doctor() -> None:
    pool, conn, _ = _pool_and_conn()
    conn.fetchrow.return_value = {
        "id": APPOINTMENT_ID,
        "doctor_id": STAFF_ID,
        "status": "SCHEDULED",
        "clinic_patient_id": PATIENT_ID,
        "slot_start": datetime.now(timezone.utc),
        "slot_end": datetime.now(timezone.utc) + timedelta(minutes=30),
        "queue_number": None,
        "booking_channel": "PHONE",
        "patient_in_clinic": True,
        "location_in_clinic": True,
        "service_in_clinic": True,
        "doctor_in_clinic": False,
    }
    conn.fetchval.return_value = APPOINTMENT_ID

    result = await BookingService(pool).apply_action(
        appointment_id=APPOINTMENT_ID,
        action="cancel",
        identity=_identity(ClinicRole.CSKH),
        cancellation_reason="Bác sĩ không còn làm tại cơ sở",
    )

    assert result == {"status": "CANCELLED"}


@pytest.mark.asyncio
async def test_void_is_auditable_soft_reversal_not_a_delete() -> None:
    pool, conn, _ = _pool_and_conn()
    payment_id = "a9000000-0000-4000-8000-000000000001"
    cycle_id = "aa000000-0000-4000-8000-000000000001"
    conn.fetchrow.return_value = {
        "id": payment_id,
        "amount": 150_000,
        "payment_cycle_id": cycle_id,
        "paid_by_staff_id": STAFF_ID,
        "paid_at": datetime(2026, 7, 30, tzinfo=timezone.utc),
    }
    enqueue = AsyncMock()

    with patch(
        "clinicai.services.payment_service.pos_outbox.enqueue",
        new=enqueue,
    ):
        await PaymentService(pool).void_payment(
            visit_id=VISIT_ID,
            kind="dich_vu",
            reason="Khách đổi phương thức thanh toán",
            identity=_identity(ClinicRole.CASHIER),
        )

    mutation_sql = conn.fetchrow.await_args.args[0]
    assert "UPDATE payment" in mutation_sql
    assert "status = 'VOIDED'" in mutation_sql
    assert "void_reason" in mutation_sql
    assert "DELETE FROM payment" not in mutation_sql
    statements = " ".join(str(call.args[0]) for call in conn.execute.await_args_list)
    assert "pg_advisory_xact_lock" in statements
    assert "UPDATE pos_outbox" in statements
    assert "kind = 'invoice'" in statements
    assert "status = 'DEAD'" in statements
    assert any(
        call.args[1] == "payment.voided" for call in conn.execute.await_args_list
    )
    enqueue_call = enqueue.await_args
    assert enqueue_call is not None
    assert enqueue_call.kwargs["subject_id"] == cycle_id
    assert enqueue_call.kwargs["payload"]["clinic_reference"] == cycle_id
    void_event = next(
        call
        for call in conn.execute.await_args_list
        if call.args[1] == "payment.voided"
    )
    void_payload = json.loads(void_event.args[3])
    assert void_payload["amount"] == 150_000
    assert void_payload["void_reason"] == "Khách đổi phương thức thanh toán"
