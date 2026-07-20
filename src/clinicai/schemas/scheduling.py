"""Pydantic v2 schemas for Work Session, Assignment, and Appointment operations."""

from __future__ import annotations

import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class SessionType(str, Enum):
    """Valid session types for work sessions."""

    EVENING = "EVENING"
    WEEKEND_MORNING = "WEEKEND_MORNING"
    WEEKEND_AFTERNOON = "WEEKEND_AFTERNOON"


class AppointmentStatus(str, Enum):
    """Status machine for appointments.

    Valid transitions:
      SCHEDULED → CONFIRMED → CHECKED_IN → COMPLETED
      SCHEDULED → CANCELLED
      SCHEDULED → NO_SHOW
    """

    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# Work Session
# ---------------------------------------------------------------------------


class WorkSessionCreateDTO(BaseModel):
    """Input schema for creating a new work session."""

    location_id: UUID
    session_date: datetime.date
    session_type: SessionType
    start_time: datetime.time
    end_time: datetime.time
    max_patients: int | None = None

    @model_validator(mode="after")
    def end_after_start(self) -> WorkSessionCreateDTO:
        if self.end_time <= self.start_time:
            msg = "end_time must be after start_time"
            raise ValueError(msg)
        return self


class WorkSessionDTO(BaseModel):
    """Output schema for a work session record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    session_date: datetime.date
    session_type: str
    start_time: datetime.time
    end_time: datetime.time
    max_patients: int | None = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Work Session Staff Assignment
# ---------------------------------------------------------------------------


class WorkSessionStaffAssignDTO(BaseModel):
    """Input schema for assigning a staff member to a work session."""

    work_session_id: UUID
    staff_id: UUID
    role: str
    station: str
    on_call_flag: bool = False


class WorkSessionStaffDTO(BaseModel):
    """Output schema for a work_session_staff record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_session_id: UUID
    staff_id: UUID
    role: str
    station: str
    on_call_flag: bool
    is_training: bool
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Appointment
# ---------------------------------------------------------------------------


class AppointmentCreateDTO(BaseModel):
    """Input schema for creating a new appointment."""

    clinic_patient_id: UUID
    doctor_id: UUID | None = None
    work_session_id: UUID | None = None
    location_id: UUID
    service_type_id: UUID
    booking_channel: str | None = None
    slot_start: datetime.datetime
    slot_end: datetime.datetime
    assigned_station: str | None = None
    queue_number: str | None = None
    is_priority_slot: bool = False
    is_walkin: bool = False

    @model_validator(mode="after")
    def slot_end_after_start(self) -> AppointmentCreateDTO:
        if self.slot_end <= self.slot_start:
            msg = "slot_end must be after slot_start"
            raise ValueError(msg)
        return self


class AppointmentUpdateDTO(BaseModel):
    """Input schema for partial-updating an appointment."""

    assigned_station: str | None = None
    queue_number: str | None = None
    is_priority_slot: bool | None = None
    doctor_id: UUID | None = None
    work_session_id: UUID | None = None


class AppointmentDTO(BaseModel):
    """Output schema for an appointment record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_patient_id: UUID
    doctor_id: UUID | None = None
    work_session_id: UUID | None = None
    location_id: UUID
    service_type_id: UUID
    booking_channel: str | None = None
    slot_start: datetime.datetime
    slot_end: datetime.datetime
    assigned_station: str | None = None
    queue_number: str | None = None
    is_priority_slot: bool
    is_walkin: bool
    status: str
    confirmed_at: datetime.datetime | None = None
    cancelled_at: datetime.datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
