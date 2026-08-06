"""Pydantic v2 schemas for Staff CRUD operations."""

from __future__ import annotations

from datetime import date, datetime
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
    CASHIER = "CASHIER"
    CASHIER_THUOC = "CASHIER_THUOC"
    CASHIER_DV = "CASHIER_DV"
    TKYK = "TKYK"
    TRUONG_CA = "TRUONG_CA"
    PHARMACIST = "PHARMACIST"


class Gender(str, Enum):
    """Ba giá trị, khớp CHECK `staff_gender_hop_le` ở database."""

    NAM = "Nam"
    NU = "Nữ"
    KHAC = "Khác"


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
    # ── Hồ sơ cá nhân + pháp lý (migration 20260806000005) ──────────────
    #
    # Tám trường màn Quản lý nhân sự đã vẽ ra từ lâu trong khối "Chưa lưu được".
    # Nay có cột thật nên chúng đi qua đúng đường như mọi trường khác.
    date_of_birth: date | None = None
    gender: Gender | None = None
    national_id_number: str | None = None
    phone: str | None = None
    email: str | None = None
    license_number: str | None = None
    license_issued_on: date | None = None
    practice_scope: str | None = None

    @field_validator("national_id_number")
    @classmethod
    def cccd_12_chu_so(cls, v: str | None) -> str | None:
        """CCCD đúng 12 chữ số, hoặc để trống.

        Database cũng có CHECK — nhưng câu từ chối của Postgres là tiếng Anh và
        nói tên ràng buộc, còn người nhập thì cần biết ô nào sai và sai thế nào.
        """
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not (len(v) == 12 and v.isdigit()):
            msg = "Số CCCD phải đúng 12 chữ số"
            raise ValueError(msg)
        return v

    @field_validator("phone")
    @classmethod
    def sdt_hop_le(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().replace(" ", "")
        if not v:
            return None
        if not (v.isdigit() and 9 <= len(v) <= 11):
            msg = "Số điện thoại phải là 9–11 chữ số"
            raise ValueError(msg)
        return v

    @field_validator("email")
    @classmethod
    def email_co_dang_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            msg = "Email không hợp lệ"
            raise ValueError(msg)
        return v

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
    # Đọc lại sau khi lưu — không có thì biểu mẫu ghi xong vẫn hiện ô trống và
    # người dùng tưởng chưa lưu được.
    date_of_birth: date | None = None
    gender: str | None = None
    national_id_number: str | None = None
    phone: str | None = None
    email: str | None = None
    license_number: str | None = None
    license_issued_on: date | None = None
    practice_scope: str | None = None


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
