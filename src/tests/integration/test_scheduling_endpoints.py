"""Integration tests for Scheduling (WorkSession and Appointment) FastAPI endpoints."""

from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_create_and_get_work_session_success(
    async_client, clean_db, location_id
) -> None:
    """POST /api/v1/work-sessions creates a session, GET retrieves it."""
    payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-01",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
        "max_patients": 20,
    }

    # 1. Create work session
    res_create = await async_client.post("/api/v1/work-sessions", json=payload)
    assert res_create.status_code == 201
    created = res_create.json()
    assert created["session_type"] == "EVENING"
    ws_id = created["id"]

    # 2. Get work session details (should include empty staff list)
    res_get = await async_client.get(f"/api/v1/work-sessions/{ws_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["session"]["id"] == ws_id
    assert isinstance(data["staff"], list)
    assert len(data["staff"]) == 0


@pytest.mark.asyncio
async def test_create_work_session_duplicate_409(
    async_client, clean_db, location_id
) -> None:
    """Creating duplicate work sessions (same location, date, type) returns 409."""
    payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-01",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
        "max_patients": 20,
    }

    # First succeeds
    res1 = await async_client.post("/api/v1/work-sessions", json=payload)
    assert res1.status_code == 201

    # Second fails with 409
    res2 = await async_client.post("/api/v1/work-sessions", json=payload)
    assert res2.status_code == 409
    assert res2.json()["error"] == "CONFLICT_ERROR"


@pytest.mark.asyncio
async def test_assign_staff_to_session_success(
    async_client, clean_db, location_id
) -> None:
    """POST /api/v1/work-sessions/{id}/staff assigns a staff member to the session."""
    # 1. Create staff member
    staff_payload = {
        "full_name": "Dr. House",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
        "is_training": True,  # Let's set True to verify the snapshot works
        "is_active": True,
    }
    staff_res = await async_client.post("/api/v1/staff", json=staff_payload)
    staff_id = staff_res.json()["id"]

    # 2. Create work session
    ws_payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-01",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
        "max_patients": 20,
    }
    ws_res = await async_client.post("/api/v1/work-sessions", json=ws_payload)
    ws_id = ws_res.json()["id"]

    # 3. Assign staff
    assign_payload = {
        "staff_id": staff_id,
        "role": "DOCTOR",
        "station": "Station A",
        "on_call_flag": False,
    }
    assign_res = await async_client.post(
        f"/api/v1/work-sessions/{ws_id}/staff", json=assign_payload
    )
    assert assign_res.status_code == 201

    # Response should contain the session details and the assigned staff member
    data = assign_res.json()
    assert data["session"]["id"] == ws_id
    assert len(data["staff"]) == 1
    assigned = data["staff"][0]
    assert assigned["staff_id"] == staff_id
    assert assigned["role"] == "DOCTOR"
    assert assigned["station"] == "Station A"
    assert assigned["is_training"] is True  # Snapshot verified!


@pytest.mark.asyncio
async def test_assign_staff_duplicate_409(async_client, clean_db, location_id) -> None:
    """Assigning the same staff member to the same session/station/role again
    returns 409.
    """
    # 1. Create staff
    staff_payload = {
        "full_name": "Dr. Watson",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    staff_res = await async_client.post("/api/v1/staff", json=staff_payload)
    staff_id = staff_res.json()["id"]

    # 2. Create work session
    ws_payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-01",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
    }
    ws_res = await async_client.post("/api/v1/work-sessions", json=ws_payload)
    ws_id = ws_res.json()["id"]

    # 3. Assign staff
    assign_payload = {
        "staff_id": staff_id,
        "role": "DOCTOR",
        "station": "Room 101",
    }
    res1 = await async_client.post(
        f"/api/v1/work-sessions/{ws_id}/staff", json=assign_payload
    )
    assert res1.status_code == 201

    # 4. Duplicate assignment to the same session/station/role -> 409
    res2 = await async_client.post(
        f"/api/v1/work-sessions/{ws_id}/staff", json=assign_payload
    )
    assert res2.status_code == 409
    assert res2.json()["error"] == "CONFLICT_ERROR"


@pytest.mark.asyncio
async def test_create_and_get_appointment_success(
    async_client, clean_db, location_id, service_type_id
) -> None:
    """POST /api/v1/appointments books an appointment; GET retrieves it."""
    # 1. Create patient
    patient_payload = {
        "full_name": "Jane Doe",
        "date_of_birth": "1995-05-15",
        "phone_primary": "+84988776655",
        "national_id_number": "123456789012",
        "location_id": str(location_id),
        "is_active": True,
    }
    patient_res = await async_client.post("/api/v1/patients", json=patient_payload)
    assert patient_res.status_code == 201
    patient_id = patient_res.json()["clinic_patient_id"]

    # 2. Create staff doctor
    staff_payload = {
        "full_name": "Doctor Strange",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    staff_res = await async_client.post("/api/v1/staff", json=staff_payload)
    doctor_id = staff_res.json()["id"]

    # 3. Create work session
    ws_payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-01",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
    }
    ws_res = await async_client.post("/api/v1/work-sessions", json=ws_payload)
    ws_id = ws_res.json()["id"]

    # 4. Assign doctor to work session
    assign_payload = {
        "staff_id": doctor_id,
        "role": "DOCTOR",
        "station": "Sanctum A",
    }
    await async_client.post(f"/api/v1/work-sessions/{ws_id}/staff", json=assign_payload)

    # 5. Book Appointment
    apt_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-01T09:00:00Z",
        "slot_end": "2026-06-01T09:30:00Z",
        "assigned_station": "Sanctum A",
        "queue_number": "1",
    }
    apt_res = await async_client.post("/api/v1/appointments", json=apt_payload)
    assert apt_res.status_code == 201
    apt = apt_res.json()
    assert apt["status"] == "SCHEDULED"
    apt_id = apt["id"]

    # 6. Retrieve appointment
    get_res = await async_client.get(f"/api/v1/appointments/{apt_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == apt_id
    assert get_res.json()["status"] == "SCHEDULED"


@pytest.mark.asyncio
async def test_create_appointment_doctor_not_on_duty_409(
    async_client, clean_db, location_id, service_type_id
) -> None:
    """Booking an appointment with a doctor who is not assigned to the session
    returns 409.
    """
    # 1. Create patient
    patient_payload = {
        "full_name": "Jane Doe",
        "date_of_birth": "1995-05-15",
        "phone_primary": "+84988776655",
        "location_id": str(location_id),
    }
    patient_res = await async_client.post("/api/v1/patients", json=patient_payload)
    patient_id = patient_res.json()["clinic_patient_id"]

    # 2. Create staff doctor (not assigned to session)
    staff_payload = {
        "full_name": "Doctor Strange",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    staff_res = await async_client.post("/api/v1/staff", json=staff_payload)
    doctor_id = staff_res.json()["id"]

    # 3. Create work session
    ws_payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-01",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
    }
    ws_res = await async_client.post("/api/v1/work-sessions", json=ws_payload)
    ws_id = ws_res.json()["id"]

    # 4. Book Appointment without assigning doctor to the session first
    apt_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-01T09:00:00Z",
        "slot_end": "2026-06-01T09:30:00Z",
    }
    apt_res = await async_client.post("/api/v1/appointments", json=apt_payload)
    assert apt_res.status_code == 409
    assert "Doctor is not assigned" in apt_res.json()["message"]


@pytest.mark.asyncio
async def test_confirm_appointment_workflow(
    async_client, clean_db, location_id, service_type_id
) -> None:
    """PATCH /api/v1/appointments/{id}/confirm updates state to CONFIRMED.
    Subsequent tries fail (422).
    """
    # 1. Create Patient
    patient_payload = {
        "full_name": "Jane Doe",
        "date_of_birth": "1995-05-15",
        "phone_primary": "+84988776655",
        "location_id": str(location_id),
    }
    patient_res = await async_client.post("/api/v1/patients", json=patient_payload)
    patient_id = patient_res.json()["clinic_patient_id"]

    # 2. Book appointment
    apt_payload = {
        "clinic_patient_id": patient_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-01T09:00:00Z",
        "slot_end": "2026-06-01T09:30:00Z",
    }
    apt_res = await async_client.post("/api/v1/appointments", json=apt_payload)
    apt_id = apt_res.json()["id"]

    # 3. Confirm appointment -> returns 200
    confirm_res = await async_client.patch(f"/api/v1/appointments/{apt_id}/confirm")
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "CONFIRMED"
    assert confirm_res.json()["confirmed_at"] is not None

    # 4. Confirm again -> returns 422 (since status is not SCHEDULED)
    confirm_res_2 = await async_client.patch(f"/api/v1/appointments/{apt_id}/confirm")
    assert confirm_res_2.status_code == 422
    assert "Cannot confirm" in confirm_res_2.json()["message"]


@pytest.mark.asyncio
async def test_cancel_appointment_workflow(
    async_client, clean_db, location_id, service_type_id
) -> None:
    """PATCH /api/v1/appointments/{id}/cancel updates state to CANCELLED.
    Subsequent tries fail (422).
    """
    # 1. Create Patient
    patient_payload = {
        "full_name": "Jane Doe",
        "date_of_birth": "1995-05-15",
        "phone_primary": "+84988776655",
        "location_id": str(location_id),
    }
    patient_res = await async_client.post("/api/v1/patients", json=patient_payload)
    patient_id = patient_res.json()["clinic_patient_id"]

    # 2. Book appointment
    apt_payload = {
        "clinic_patient_id": patient_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-01T09:00:00Z",
        "slot_end": "2026-06-01T09:30:00Z",
    }
    apt_res = await async_client.post("/api/v1/appointments", json=apt_payload)
    apt_id = apt_res.json()["id"]

    # 3. Cancel appointment -> returns 200
    cancel_res = await async_client.patch(
        f"/api/v1/appointments/{apt_id}/cancel",
        json={"reason": "Patient requested cancellation"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"
    assert cancel_res.json()["cancellation_reason"] == "Patient requested cancellation"

    # 4. Cancel again -> returns 422
    cancel_res_2 = await async_client.patch(
        f"/api/v1/appointments/{apt_id}/cancel",
        json={"reason": "Change my mind"},
    )
    assert cancel_res_2.status_code == 422
    assert "Cannot cancel" in cancel_res_2.json()["message"]


@pytest.mark.asyncio
async def test_get_appointment_not_found(async_client, clean_db) -> None:
    """GET /api/v1/appointments/{id} with missing ID returns 404."""
    res = await async_client.get(f"/api/v1/appointments/{uuid4()}")
    assert res.status_code == 404
    assert res.json()["error"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_appointment_slot_overlap_same_doctor_blocked(
    async_client, clean_db, location_id, service_type_id
) -> None:
    """Booking overlapping appointments for the same doctor should be blocked."""
    # 1. Create Patient
    patient_payload = {
        "full_name": "Patient A",
        "date_of_birth": "1995-05-15",
        "phone_primary": "+84988776651",
        "location_id": str(location_id),
    }
    pat_res = await async_client.post("/api/v1/patients", json=patient_payload)
    patient_id = pat_res.json()["clinic_patient_id"]

    # 2. Create doctor X
    doc_payload = {
        "full_name": "Doctor X",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    doc_res = await async_client.post("/api/v1/staff", json=doc_payload)
    doctor_id = doc_res.json()["id"]

    # 3. Create work session
    ws_payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-02",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
    }
    ws_res = await async_client.post("/api/v1/work-sessions", json=ws_payload)
    ws_id = ws_res.json()["id"]

    # 4. Assign doctor X to work session
    assign_payload = {
        "staff_id": doctor_id,
        "role": "DOCTOR",
        "station": "Room 1",
    }
    await async_client.post(f"/api/v1/work-sessions/{ws_id}/staff", json=assign_payload)

    # 5. Book appointment A: slot 10:00-10:30
    apt1_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-02T10:00:00Z",
        "slot_end": "2026-06-02T10:30:00Z",
    }
    apt1_res = await async_client.post("/api/v1/appointments", json=apt1_payload)
    assert apt1_res.status_code == 201

    # 6. Book appointment B (overlapping with A): slot 10:15-10:45
    apt2_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-02T10:15:00Z",
        "slot_end": "2026-06-02T10:45:00Z",
    }
    apt2_res = await async_client.post("/api/v1/appointments", json=apt2_payload)
    assert apt2_res.status_code in (422, 409)


@pytest.mark.asyncio
async def test_appointment_slot_adjacent_same_doctor_allowed(
    async_client, clean_db, location_id, service_type_id
) -> None:
    """Booking adjacent appointments for the same doctor should be allowed."""
    # 1. Create Patient
    patient_payload = {
        "full_name": "Patient A",
        "date_of_birth": "1995-05-15",
        "phone_primary": "+84988776651",
        "location_id": str(location_id),
    }
    pat_res = await async_client.post("/api/v1/patients", json=patient_payload)
    patient_id = pat_res.json()["clinic_patient_id"]

    # 2. Create doctor X
    doc_payload = {
        "full_name": "Doctor X",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    doc_res = await async_client.post("/api/v1/staff", json=doc_payload)
    doctor_id = doc_res.json()["id"]

    # 3. Create work session
    ws_payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-03",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
    }
    ws_res = await async_client.post("/api/v1/work-sessions", json=ws_payload)
    ws_id = ws_res.json()["id"]

    # 4. Assign doctor X to work session
    assign_payload = {
        "staff_id": doctor_id,
        "role": "DOCTOR",
        "station": "Room 1",
    }
    await async_client.post(f"/api/v1/work-sessions/{ws_id}/staff", json=assign_payload)

    # 5. Book appointment A: slot 10:00-10:30
    apt1_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-03T10:00:00Z",
        "slot_end": "2026-06-03T10:30:00Z",
    }
    apt1_res = await async_client.post("/api/v1/appointments", json=apt1_payload)
    assert apt1_res.status_code == 201

    # 6. Book appointment B (adjacent to A): slot 10:30-11:00
    apt2_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-03T10:30:00Z",
        "slot_end": "2026-06-03T11:00:00Z",
    }
    apt2_res = await async_client.post("/api/v1/appointments", json=apt2_payload)
    assert apt2_res.status_code == 201


@pytest.mark.asyncio
async def test_appointment_slot_overlap_after_cancel_allowed(
    async_client, clean_db, location_id, service_type_id
) -> None:
    """Rebooking overlapping slots after cancellation should be allowed."""
    # 1. Create Patient
    patient_payload = {
        "full_name": "Patient A",
        "date_of_birth": "1995-05-15",
        "phone_primary": "+84988776651",
        "location_id": str(location_id),
    }
    pat_res = await async_client.post("/api/v1/patients", json=patient_payload)
    patient_id = pat_res.json()["clinic_patient_id"]

    # 2. Create doctor X
    doc_payload = {
        "full_name": "Doctor X",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    doc_res = await async_client.post("/api/v1/staff", json=doc_payload)
    doctor_id = doc_res.json()["id"]

    # 3. Create work session
    ws_payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-04",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
    }
    ws_res = await async_client.post("/api/v1/work-sessions", json=ws_payload)
    ws_id = ws_res.json()["id"]

    # 4. Assign doctor X to work session
    assign_payload = {
        "staff_id": doctor_id,
        "role": "DOCTOR",
        "station": "Room 1",
    }
    await async_client.post(f"/api/v1/work-sessions/{ws_id}/staff", json=assign_payload)

    # 5. Book appointment A: slot 10:00-10:30
    apt1_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-04T10:00:00Z",
        "slot_end": "2026-06-04T10:30:00Z",
    }
    apt1_res = await async_client.post("/api/v1/appointments", json=apt1_payload)
    assert apt1_res.status_code == 201
    apt1_id = apt1_res.json()["id"]

    # 6. Cancel appointment A
    cancel_res = await async_client.patch(
        f"/api/v1/appointments/{apt1_id}/cancel",
        json={"reason": "Patient changed mind"},
    )
    assert cancel_res.status_code == 200

    # 7. Book appointment B (overlapping/same slot as A): slot 10:00-10:30
    apt2_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-04T10:00:00Z",
        "slot_end": "2026-06-04T10:30:00Z",
    }
    apt2_res = await async_client.post("/api/v1/appointments", json=apt2_payload)
    assert apt2_res.status_code == 201


@pytest.mark.asyncio
async def test_appointment_slot_overlap_different_doctor_allowed(
    async_client, clean_db, location_id, service_type_id
) -> None:
    """Booking overlapping slots for different doctors should be allowed."""
    # 1. Create Patient
    patient_payload = {
        "full_name": "Patient A",
        "date_of_birth": "1995-05-15",
        "phone_primary": "+84988776651",
        "location_id": str(location_id),
    }
    pat_res = await async_client.post("/api/v1/patients", json=patient_payload)
    patient_id = pat_res.json()["clinic_patient_id"]

    # 2. Create doctor X
    doc_x_payload = {
        "full_name": "Doctor X",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    doc_x_res = await async_client.post("/api/v1/staff", json=doc_x_payload)
    doctor_x_id = doc_x_res.json()["id"]

    # 3. Create doctor Y
    doc_y_payload = {
        "full_name": "Doctor Y",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    doc_y_res = await async_client.post("/api/v1/staff", json=doc_y_payload)
    doctor_y_id = doc_y_res.json()["id"]

    # 4. Create work session
    ws_payload = {
        "location_id": str(location_id),
        "session_date": "2026-06-05",
        "session_type": "EVENING",
        "start_time": "17:00:00",
        "end_time": "21:00:00",
    }
    ws_res = await async_client.post("/api/v1/work-sessions", json=ws_payload)
    ws_id = ws_res.json()["id"]

    # 5. Assign doctor X to work session
    assign_x_payload = {
        "staff_id": doctor_x_id,
        "role": "DOCTOR",
        "station": "Room 1",
    }
    await async_client.post(
        f"/api/v1/work-sessions/{ws_id}/staff", json=assign_x_payload
    )

    # 6. Assign doctor Y to work session
    assign_y_payload = {
        "staff_id": doctor_y_id,
        "role": "DOCTOR",
        "station": "Room 2",
    }
    await async_client.post(
        f"/api/v1/work-sessions/{ws_id}/staff", json=assign_y_payload
    )

    # 7. Book appointment for doctor X: slot 10:00-10:30
    apt1_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_x_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-05T10:00:00Z",
        "slot_end": "2026-06-05T10:30:00Z",
    }
    apt1_res = await async_client.post("/api/v1/appointments", json=apt1_payload)
    assert apt1_res.status_code == 201

    # 8. Book appointment for doctor Y (same slot): slot 10:00-10:30
    apt2_payload = {
        "clinic_patient_id": patient_id,
        "doctor_id": doctor_y_id,
        "work_session_id": ws_id,
        "location_id": str(location_id),
        "service_type_id": str(service_type_id),
        "booking_channel": "WEBSITE",
        "slot_start": "2026-06-05T10:00:00Z",
        "slot_end": "2026-06-05T10:30:00Z",
    }
    apt2_res = await async_client.post("/api/v1/appointments", json=apt2_payload)
    assert apt2_res.status_code == 201
