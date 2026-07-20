"""Pydantic v2 schemas for Patient CRUD operations."""

from __future__ import annotations

import re
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from clinicai.core.phone import normalize_vn_phone

_CCCD_RE = re.compile(r"^\d{12}$")
_LINH_VUC = {"PK", "SK", "NT", "HMVS", "NK"}
_GENDER = {"Nam", "Nữ", "Khác"}


def _blank_to_none(v: object) -> object:
    """Empty/whitespace string → None (frontend sends "" for unset fields)."""
    if isinstance(v, str) and not v.strip():
        return None
    return v


class PatientCreateDTO(BaseModel):
    """Input schema for creating a new patient.

    Mirrors the dashboard intake form: core identity + admin (mục I) + structured
    address + CSKH fields. Lenient on secondary fields (bad gender/linh_vuc/
    birth_year → coerced to None, NEVER blocks creation); strict on identity
    (Vietnamese mobile phone, CCCD 12 digits → reject).
    """

    full_name: str
    date_of_birth: date | None = None
    birth_year: int | None = None
    phone_primary: str | None = None
    phone_secondary: str | None = None
    national_id_number: str | None = None
    location_id: UUID
    # Hành chính (mục I form khám)
    gender: str | None = None
    ethnicity: str | None = None
    nationality: str | None = None
    occupation: str | None = None
    patient_objection: str | None = None
    address: str | None = None
    guardian_name: str | None = None
    # Địa chỉ có cấu trúc (sau sáp nhập: tỉnh → phường, bỏ huyện)
    province_code: str | None = None
    province_name: str | None = None
    ward_code: str | None = None
    ward_name: str | None = None
    address_detail: str | None = None
    # CSKH (đặt lịch)
    van_de_di_kham: str | None = None
    linh_vuc: str | None = None
    is_active: bool = True
    # Cho phép tạo dù trùng SĐT (nhân viên đã xác nhận). KHÔNG nới CCCD.
    force: bool = False

    @field_validator(
        "date_of_birth",
        "birth_year",
        "phone_primary",
        "phone_secondary",
        "national_id_number",
        "gender",
        "ethnicity",
        "nationality",
        "occupation",
        "patient_objection",
        "address",
        "guardian_name",
        "province_code",
        "province_name",
        "ward_code",
        "ward_name",
        "address_detail",
        "van_de_di_kham",
        "linh_vuc",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v: object) -> object:
        return _blank_to_none(v)

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "full_name must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("phone_primary", "phone_secondary")
    @classmethod
    def _phone_10_digits(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = normalize_vn_phone(v)
        if normalized is None:
            msg = "phone must be a supported Vietnamese mobile number"
            raise ValueError(msg)
        return normalized

    @field_validator("national_id_number")
    @classmethod
    def _cccd_12_digits(cls, v: str | None) -> str | None:
        if v is not None and not _CCCD_RE.match(v):
            msg = "national_id_number must be exactly 12 digits"
            raise ValueError(msg)
        return v

    @field_validator("birth_year")
    @classmethod
    def _birth_year_range(cls, v: int | None) -> int | None:
        # Ngoài 1900–2100 → bỏ (field phụ, không chặn tạo BN).
        return v if v is not None and 1900 <= v <= 2100 else None

    @field_validator("gender")
    @classmethod
    def _gender_whitelist(cls, v: str | None) -> str | None:
        return v if v in _GENDER else None

    @field_validator("linh_vuc")
    @classmethod
    def _linh_vuc_whitelist(cls, v: str | None) -> str | None:
        return v if v in _LINH_VUC else None

    @model_validator(mode="after")
    def _dob_from_birth_year(self) -> PatientCreateDTO:
        # Chỉ nhớ năm sinh → đặt date_of_birth = YYYY-01-01 để tuổi + chỗ hiển
        # thị NGÀY vẫn chạy (mirror dashboard feedback B5#4).
        if self.date_of_birth is None and self.birth_year is not None:
            self.date_of_birth = date(self.birth_year, 1, 1)
        return self


class PatientUpdateDTO(BaseModel):
    """Input schema for partial-updating a patient. All fields optional."""

    full_name: str | None = None
    date_of_birth: date | None = None
    phone_primary: str | None = None
    phone_secondary: str | None = None
    national_id_number: str | None = None
    location_id: UUID | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            msg = "full_name must not be blank"
            raise ValueError(msg)
        return v.strip() if v else v

    @field_validator("phone_primary", "phone_secondary", mode="before")
    @classmethod
    def normalize_phone(cls, v: object) -> str | None:
        v = _blank_to_none(v)
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("phone must be a string")
        normalized = normalize_vn_phone(v)
        if normalized is None:
            raise ValueError("phone must be a supported Vietnamese mobile number")
        return normalized


def _mask_national_id(value: str | None) -> str | None:
    """Mask CCCD for display: show first 3 and last 2 chars only."""
    if value is None:
        return None
    if len(value) <= 5:
        return re.sub(r".", "*", value)
    return value[:3] + "*" * (len(value) - 5) + value[-2:]


class PhoneDuplicateMatch(BaseModel):
    """One patient already on file with a queried phone number.

    Deliberately MINIMAL — only what reception needs to recognise a person
    (feedback #9: a mother registering with her own number for her child).
    NO national_id, NO address: this is a soft warning surface, not a profile.
    """

    full_name: str
    patient_code: str
    birth_year: int | None = None


class PhoneCheckResult(BaseModel):
    """Result of the read-only phone-duplicate lookup."""

    exists: bool
    matches: list[PhoneDuplicateMatch]


class PatientDTO(BaseModel):
    """Output schema returned from service layer. national_id is masked."""

    model_config = ConfigDict(from_attributes=True)

    clinic_patient_id: UUID
    patient_code: str
    national_id_number: str | None = None
    full_name: str
    date_of_birth: date | None = None
    phone_primary: str | None = None
    phone_secondary: str | None = None
    location_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("national_id_number", mode="before")
    @classmethod
    def mask_national_id(cls, v: str | None) -> str | None:
        return _mask_national_id(v)


class DuplicateMatch(BaseModel):
    """One existing patient sharing the incoming phone_primary.

    Surfaced to reception in the block-before-insert guard so they can recognise
    the person and decide whether to proceed (force). MINIMAL fields only.
    """

    clinic_patient_id: UUID
    patient_code: str
    full_name: str
    date_of_birth: date | None = None


class PatientCreateResult(BaseModel):
    """Outcome of create_patient: either a soft duplicate-block, or the new row.

    ``patient is None and duplicate is True`` → phone already on file (no insert
    happened; caller may retry with force). Otherwise ``patient`` holds the row.
    A hard CCCD conflict does NOT return here — it raises ConflictError (409).
    """

    duplicate: bool = False
    matches: list[DuplicateMatch] = []
    patient: PatientDTO | None = None
