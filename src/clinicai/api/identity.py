"""Server-authoritative identity + role for clinic staff (Phase 4, cluster #1).

Every authenticated caller carries a Supabase JWT (Authorization: Bearer ...).
The backend VERIFIES that JWT, maps the auth user → the linked `staff` row via
`staff.auth_user_id`, and derives the clinic role from `staff.primary_department`.
Nothing is trusted from the client: not the role, not the identity.

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

import asyncpg
import jwt
import structlog
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient

from clinicai.core.database import get_db_pool

logger = structlog.get_logger()

SUPABASE_AUDIENCE = "authenticated"


class ClinicRole(str, Enum):
    """Mirror of staff.primary_department CHECK — the role IS the department."""

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
    """Derive clinic role from staff department. Unknown → CSKH (least privilege)."""
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


async def get_current_identity(
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffIdentity:
    """FastAPI dep: verify JWT → linked active staff → role. Raises 401/403."""
    claims = verify_supabase_jwt(_bearer_token(request))
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject")

    row = await pool.fetchrow(
        """
        SELECT id, auth_user_id, full_name, primary_department
        FROM staff
        WHERE auth_user_id = $1::uuid AND is_active IS NOT FALSE
        """,
        sub,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active staff account is linked to this login",
        )

    dept = row["primary_department"]
    return StaffIdentity(
        staff_id=str(row["id"]),
        auth_user_id=str(row["auth_user_id"]),
        full_name=row["full_name"],
        department=dept,
        role=role_from_department(dept),
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
