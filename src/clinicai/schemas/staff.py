"""Pydantic v2 schemas for Staff CRUD operations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class PrimaryDepartment(str, Enum):
    """Valid primary departments for staff members."""

    DOCTOR = "DOCTOR"
    ULTRASOUND_DOCTOR = "ULTRASOUND_DOCTOR"
    NURSE_ULTRASOUND = "NURSE_ULTRASOUND"
    RECEPTION = "RECEPTION"
    CSKH = "CSKH"
    MANAGEMENT = "MANAGEMENT"


class EmploymentType(str, Enum):
    """Valid employment types for staff members."""

    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"


class StaffCreateDTO(BaseModel):
    """Input schema for creating a new staff member."""

    full_name: str
    short_name: str | None = None
    primary_department: PrimaryDepartment
    primary_location_id: UUID | None = None
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    is_training: bool = False
    is_active: bool = True

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "full_name must not be blank"
            raise ValueError(msg)
        return v.strip()


class StaffUpdateDTO(BaseModel):
    """Input schema for partial-updating a staff member. All fields optional."""

    full_name: str | None = None
    short_name: str | None = None
    primary_department: PrimaryDepartment | None = None
    primary_location_id: UUID | None = None
    employment_type: EmploymentType | None = None
    is_training: bool | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            msg = "full_name must not be blank"
            raise ValueError(msg)
        return v.strip() if v else v


class StaffDTO(BaseModel):
    """Output schema returned from service layer."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    short_name: str | None = None
    primary_department: str
    primary_location_id: UUID | None = None
    employment_type: str
    is_training: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class Capability(str, Enum):
    """Allowed values for staff_capability.capability (D019: app-enforced).

    DB column is TEXT (no CHECK). Keep this list in sync with the
    comment block in migrations/20260522_019_create_staff_capability.sql.
    """

    RECEPTION = "RECEPTION"
    CASHIER = "CASHIER"
    PHLEBOTOMY = "PHLEBOTOMY"
    ULTRASOUND_NURSE = "ULTRASOUND_NURSE"
    CSKH = "CSKH"
    DOCTOR_CONSULTATION = "DOCTOR_CONSULTATION"


class ProficiencyLevel(str, Enum):
    """Allowed values for staff_capability.proficiency_level."""

    TRAINEE = "TRAINEE"
    COMPETENT = "COMPETENT"
    EXPERT = "EXPERT"


class StaffCapabilityDTO(BaseModel):
    """A staff_capability row, returned from upsert/query operations."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    staff_id: UUID
    capability: str
    proficiency_level: str
    created_at: datetime
