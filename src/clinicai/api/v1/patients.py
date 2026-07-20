"""FastAPI endpoints for Patient CRUD operations."""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.schemas.patient import (
    PatientCreateDTO,
    PatientDTO,
    PatientUpdateDTO,
    PhoneCheckResult,
    PhoneDuplicateMatch,
)
from clinicai.services.patient_service import PatientService

router = APIRouter()

_INTAKE_GUARD = require_role(
    ClinicRole.CSKH,
    ClinicRole.RECEPTION,
    ClinicRole.MANAGEMENT,
    ClinicRole.TRUONG_CA,
)
_PATIENT_EDIT_GUARD = require_role(
    ClinicRole.CSKH,
    ClinicRole.RECEPTION,
    ClinicRole.MANAGEMENT,
    ClinicRole.TRUONG_CA,
    ClinicRole.DOCTOR,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.TKYK,
)


@router.post(
    "/patients",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
)
async def create_patient(
    data: PatientCreateDTO,
    _identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PatientDTO | JSONResponse:
    """Register a patient with MPI dedup. Three outcomes:

    * created      → 201, the PatientDTO.
    * phone dup    → 200 ``{"duplicate": true, "matches": [...]}`` (no insert).
    * CCCD conflict → 409 (raised as ConflictError by the service).
    """
    service = PatientService(pool)
    result = await service.create_patient(data)
    if result.patient is None:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "duplicate": True,
                "matches": jsonable_encoder(result.matches),
            },
        )
    return result.patient


# NOTE: must be declared BEFORE "/patients/{id}" — otherwise the literal path
# "check-phone" gets matched against {id} (UUID) and rejected with 422.
@router.get("/patients/check-phone", response_model=PhoneCheckResult)
async def check_phone_duplicate(
    phone: str,
    _identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PhoneCheckResult:
    """Read-only early warning: is this phone already on file (feedback #9)?

    Returns minimal identifying fields so reception can spot a relative sharing
    a number (e.g. a mother registering for her child). NEVER blocks creation —
    the warning is advisory; the operator decides.
    """
    if not phone.strip():
        raise ValidationError("phone query parameter must not be blank")
    service = PatientService(pool)
    matches = await service.find_phone_duplicates(phone)
    return PhoneCheckResult(
        exists=bool(matches),
        matches=[PhoneDuplicateMatch(**m) for m in matches],
    )


@router.get("/patients/{id}", response_model=PatientDTO)
async def get_patient_by_id(
    id: UUID,
    _identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PatientDTO:
    """Retrieve a single patient by ID. Raises ResourceNotFoundError if not found."""
    service = PatientService(pool)
    patient = await service.get_by_id(id)
    if patient is None:
        raise ResourceNotFoundError(f"Patient {id} not found")
    return patient


@router.get("/patients", response_model=list[PatientDTO])
async def get_patients_by_phone(
    phone: str,
    _identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[PatientDTO]:
    """Retrieve all patients matching a primary or secondary phone number."""
    if not phone.strip():
        raise ValidationError("phone query parameter must not be blank")
    service = PatientService(pool)
    return await service.get_by_phone(phone)


@router.patch("/patients/{id}", response_model=PatientDTO)
async def update_patient(
    id: UUID,
    data: PatientUpdateDTO,
    _identity: StaffIdentity = Depends(_PATIENT_EDIT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PatientDTO:
    """Partially update demographic details for a patient."""
    service = PatientService(pool)
    return await service.update_patient(id, data)
