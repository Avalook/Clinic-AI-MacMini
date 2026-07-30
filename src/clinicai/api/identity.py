"""Server-authoritative identity + role for clinic staff (Phase 4, cluster #1).

Every authenticated caller carries a Supabase JWT (Authorization: Bearer ...).
The backend VERIFIES that JWT, maps the auth user → the linked `staff` row via
`staff.auth_user_id`, and derives both tenant and role from the SAME active
`clinic_membership` row. Nothing is trusted from the client: not the role, not
the identity.

Single-clinic staff need no extra context. A staff member with multiple active
memberships must send ``X-Clinic-ID``; it only selects among memberships already
authorized by the database and never grants access on its own.

This replaces the old model where the frontend set a self-chosen `clinic_role`
cookie + picked any `staff_id` at a role-picker (spoofable — see spec §4 / audit).

Two verification modes (auto-selected):
  * SUPABASE_JWT_SECRET set → legacy HS256 shared secret.
  * else → asymmetric keys via the project JWKS endpoint (ES256/RS256).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any
from uuid import UUID

import asyncpg
import jwt
import structlog
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient

from clinicai.core.database import get_db_pool

logger = structlog.get_logger()

SUPABASE_AUDIENCE = "authenticated"


class ClinicRole(str, Enum):
    """Mirror of the role codes allowed on ``clinic_membership``."""

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


_VALID_ROLES = {r.value for r in ClinicRole}

# Roles allowed to write clinical records (mirror roles.ts canWriteClinical).
CLINICAL_WRITE_ROLES = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.NURSE_ULTRASOUND,
    }
)
DOCTOR_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR})
CASHIER_ROLES = frozenset(
    {ClinicRole.CASHIER, ClinicRole.CASHIER_THUOC, ClinicRole.CASHIER_DV}
)


def role_from_department(dept: str | None) -> ClinicRole:
    """Map a persisted role code. Unknown → CSKH (least privilege).

    The legacy name remains because callers and tests use it, but request
    authorization now supplies the per-clinic ``clinic_membership.role`` rather
    than the global ``staff.primary_department``.
    """
    if dept and dept in _VALID_ROLES:
        return ClinicRole(dept)
    logger.warning("unknown_department_defaulting_cskh", department=dept)
    return ClinicRole.CSKH


@dataclass(frozen=True)
class StaffIdentity:
    """The verified acting staff member for a request."""

    staff_id: str
    auth_user_id: str
    full_name: str
    department: str
    role: ClinicRole
    # The tenant this request acts in, resolved from clinic_membership (ADR-0009).
    #
    # Required, not optional. get_current_identity refuses a login with no
    # active membership, so a request that reaches a service always has a
    # tenant. While this said `str | None`, every query downstream carried a
    # `COALESCE(..., default_clinic_id())` for a case that could not happen —
    # and that fallback is exactly what silently files rows under a guess.
    # Typing it honestly is what let those be deleted: mypy now proves the
    # tenant is there instead of the database inventing one.
    clinic_id: str

    def can_write_clinical(self) -> bool:
        return self.role in CLINICAL_WRITE_ROLES

    def is_doctor(self) -> bool:
        return self.role in DOCTOR_ROLES

    def is_cashier(self) -> bool:
        return self.role in CASHIER_ROLES


# --------------------------------------------------------------------------- #
# JWT verification
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _jwk_client() -> PyJWKClient:
    base = os.environ["SUPABASE_URL"].rstrip("/")
    return PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json")


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase access token and return its claims. Raises 401 on failure."""
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    try:
        if secret:
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=SUPABASE_AUDIENCE,
            )
        signing_key = _jwk_client().get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["ES256", "RS256"],
            audience=SUPABASE_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        logger.info("jwt_verification_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return header[len("Bearer ") :].strip()


def _requested_clinic_id(request: Request) -> str | None:
    """Return a canonical active-clinic selector, rejecting malformed input.

    The header is a selector, not authority: the database query below accepts
    it only when the authenticated staff member has that active membership.
    A single-clinic staff member needs no header; a multi-clinic login must
    choose explicitly so requests never land in an arbitrary tenant.
    """
    raw = request.headers.get("X-Clinic-ID")
    if raw is None:
        return None
    try:
        return str(UUID(raw.strip()))
    except (AttributeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Clinic-ID must be a valid UUID",
        ) from None


async def get_current_identity(
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffIdentity:
    """Verify JWT → active staff → one active clinic membership. Raises 401/403."""
    claims = verify_supabase_jwt(_bearer_token(request))
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject")

    requested_clinic_id = _requested_clinic_id(request)
    rows = await pool.fetch(
        """
        SELECT s.id, s.auth_user_id, s.full_name, s.primary_department,
               m.clinic_id, m.role AS membership_role
        FROM staff s
        LEFT JOIN clinic_membership m
               ON m.staff_id = s.id AND m.is_active
        WHERE s.auth_user_id = $1::uuid AND s.is_active IS NOT FALSE
          AND ($2::uuid IS NULL OR m.clinic_id = $2::uuid)
        ORDER BY m.created_at, m.id
        LIMIT 2
        """,
        sub,
        requested_clinic_id,
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active staff membership is linked to this login and clinic",
        )
    if len(rows) > 1:
        # This is either a multi-clinic login without an explicit selector or
        # malformed provisioning with multiple active roles in one clinic.
        # Both are authorization ambiguity, so fail closed.
        logger.warning(
            "ambiguous_clinic_membership",
            staff_id=str(rows[0]["id"]),
            requested_clinic_id=requested_clinic_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Multiple active clinic memberships found; provide X-Clinic-ID"
                if requested_clinic_id is None
                else "Multiple active roles found for X-Clinic-ID"
            ),
        )

    row = rows[0]
    dept = row["primary_department"]
    clinic_id = row["clinic_id"]
    if clinic_id is None:
        # Every active staff member gets a membership from the
        # staff_ensure_default_membership trigger, so this means the row was
        # created before W3 or the trigger was bypassed. Fail closed: acting
        # without a tenant is how data lands in the wrong clinic.
        logger.warning("staff_without_membership", staff_id=str(row["id"]))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản chưa được gán vào phòng khám nào",
        )

    # A doctor may be MANAGEMENT at clinic A and DOCTOR at clinic B.  The
    # global primary_department describes the person, but only the membership
    # selected alongside clinic_id is authorized to describe this request.
    membership_role = row["membership_role"]
    return StaffIdentity(
        staff_id=str(row["id"]),
        auth_user_id=str(row["auth_user_id"]),
        full_name=row["full_name"],
        department=dept,
        role=role_from_department(membership_role),
        clinic_id=str(clinic_id),
    )


class RoleGuard:
    """Dependency that admits only ``allowed_roles``.

    A class rather than a closure so the gate can be read back — tests assert
    which roles a router admits without having to drive HTTP, and the set stays
    checkable against ``roles.ts``.
    """

    def __init__(self, allowed: frozenset[ClinicRole]) -> None:
        self.allowed_roles = allowed

    async def __call__(
        self,
        identity: StaffIdentity = Depends(get_current_identity),
    ) -> StaffIdentity:
        if identity.role not in self.allowed_roles:
            logger.info(
                "role_forbidden",
                role=identity.role.value,
                allowed=[r.value for r in self.allowed_roles],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role is not permitted to perform this action",
            )
        return identity


def require_role(*allowed: ClinicRole) -> RoleGuard:
    """Dependency factory: 403 unless the caller's role is in ``allowed``."""
    return RoleGuard(frozenset(allowed))
