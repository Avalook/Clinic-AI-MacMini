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
from time import monotonic
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
    PHARMACIST = "PHARMACIST"
    # Màn hình TV phòng chờ. KHÔNG phải người — là cái máy treo tường.
    #
    # Tồn tại vì lý do an toàn, không phải vì tiện: nếu cái tivi đăng nhập bằng
    # một tài khoản nhân viên thường (Lễ tân chẳng hạn), thì bất kỳ ai đứng cạnh
    # nó cũng chỉ cần mở một tab mới là đọc được hồ sơ bệnh nhân. Một máy tính
    # bỏ đó suốt ngày trong phòng chờ công cộng phải có ít quyền nhất có thể.
    #
    # Vai này bị `get_current_identity` TỪ CHỐI, nên nó bị chặn ở MỌI endpoint
    # theo mặc định — kể cả những endpoint chưa có RoleGuard. Chỉ
    # `get_display_identity` nhận nó, và hôm nay đúng một đường dùng dependency
    # đó. Thêm endpoint mới sau này cũng tự động loại vai này ra, không phải
    # nhớ gì cả.
    DISPLAY = "DISPLAY"


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

# HOLDS A MEDICAL LICENCE. Ordering a test and signing off a result are acts a
# medical secretary must not perform, so TKYK is deliberately absent — see
# lab.py's _ORDER_GUARD / _REVIEW_GUARD.
#
# Named PHYSICIAN_ROLES rather than DOCTOR_ROLES because the old name read as
# "everyone at the doctor's desk", which is a different and wider set (that one
# is DOCTOR_DESK_ROLES below). The browser mirrored the wide reading and drew
# "Chỉ định XN"/"Duyệt kết quả" for TKYK, who then got a 403 from these guards.
# Two names, because they are two questions.
PHYSICIAN_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR})

# WORKS THE DOCTOR'S DESK. The secretary opens the same board and moves the same
# appointment on the doctor's behalf. Mirrors roles.ts isDoctorRole.
DOCTOR_DESK_ROLES = frozenset(
    {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR, ClinicRole.TKYK}
)

CASHIER_ROLES = frozenset(
    {ClinicRole.CASHIER, ClinicRole.CASHIER_THUOC, ClinicRole.CASHIER_DV}
)


def role_from_department(dept: str | None) -> ClinicRole:
    """Map a persisted role code, rejecting missing or unknown authority.

    The legacy name remains because callers and tests use it, but request
    authorization now supplies the per-clinic ``clinic_membership.role`` rather
    than the global ``staff.primary_department``.
    """
    if dept and dept in _VALID_ROLES:
        return ClinicRole(dept)
    # CSKH is not a harmless display fallback: it can read patient details and
    # record customer-care interactions. A typo or NULL membership role is bad
    # authorization data, so fail closed instead of silently granting that role.
    logger.error("invalid_membership_role", department=dept)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Tài khoản có vai trò không hợp lệ",
    )


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

    # WHICH SITE. "Phòng khám Dr4Women, cơ sở Kim Ngưu" is one fact in two
    # parts, and only the first half was ever carried on the request.
    #
    # location_id decides which branch an appointment belongs to and which row
    # of block_budget its capacity is read from. Because it was not on the
    # identity, every caller that needed it took it from the request body —
    # which is how BookingHub ended up sending `locations[0].id`, i.e. "the
    # first branch in the dropdown", as the place a patient would be seen.
    #
    # Required, like clinic_id, and for the same reason: 20260803000007 makes
    # staff.primary_location_id NOT NULL, so a request that reaches a service
    # always knows where its author works. Optional here would just move the
    # guessing somewhere less visible.
    location_id: str
    location_name: str

    # HAI TRƯỜNG CHỈ ĐỂ HIỂN THỊ, VÀ CHÚNG CÓ MẶC ĐỊNH.
    #
    # Không dùng cho phân quyền — tên gọi thì không cho phép ai làm gì. Chúng ở
    # đây vì dashboard đọc danh tính từ GET /api/v1/me, mà thanh đầu trang phải
    # nói được "Nguyễn A · Phòng khám Dr4Women, cơ sở Kim Ngưu". Thiếu chúng thì
    # frontend lại phải tự truy vấn thêm — đúng thứ việc nối /me đang gỡ bỏ.
    #
    # Có mặc định "" vì 41 chỗ trong test dựng StaffIdentity bằng tay; bắt buộc
    # hai trường trang trí này sẽ làm hỏng cả 41 chỗ để đổi lấy con số không.
    short_name: str = ""
    clinic_name: str = ""

    def can_write_clinical(self) -> bool:
        return self.role in CLINICAL_WRITE_ROLES

    def is_doctor(self) -> bool:
        return self.role in PHYSICIAN_ROLES

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


# --------------------------------------------------------------------------- #
# Membership lookup cache
# --------------------------------------------------------------------------- #
# ONE SUPABASE ROUND TRIP PER REQUEST, FOR AN ANSWER THAT CHANGES A FEW TIMES A
# YEAR. Every authenticated call ran the membership query below against Supabase
# Cloud in Seoul — roughly 60–90ms from Vietnam, before the endpoint did any of
# its own work. A single button press in the dashboard already pays
# `supabase.auth.getUser()` plus the hop to FastAPI; this was a third leg on top.
#
# WHY A TTL AND NOT INVALIDATION. The honest options were a short TTL or a
# LISTEN/NOTIFY invalidation channel on clinic_membership. The second is
# strictly better and strictly more machinery — and this cache lives in one API
# process on one Mac, so a role change would still have to reach other replicas
# the day there are any. 30 seconds is chosen so a deactivated account or a
# changed role stops working within the time it takes to walk to the front desk,
# which is the actual failure mode being bounded.
#
# WHAT IS NOT CACHED. The JWT is verified on EVERY request, always. An expired
# or forged token is rejected before this cache is consulted, so the cache can
# never extend a session — it only remembers which staff row a still-valid token
# maps to. A 403 is not cached either: a staff member who has just been given
# their membership should not have to wait out a TTL to get in.
_IDENTITY_TTL_SECONDS = 30.0
_IDENTITY_CACHE_MAX = 512
_identity_cache: dict[tuple[str, str | None], tuple[float, StaffIdentity]] = {}


def invalidate_identity_cache(auth_user_id: str | None = None) -> None:
    """Drop cached memberships — all of them, or one login's.

    Call after a write that changes who someone is: staff_service does this so a
    role change or deactivation takes effect on the next request instead of at
    the end of the TTL.
    """
    if auth_user_id is None:
        _identity_cache.clear()
        return
    for key in [k for k in _identity_cache if k[0] == auth_user_id]:
        _identity_cache.pop(key, None)


def _cache_get(key: tuple[str, str | None], now: float) -> StaffIdentity | None:
    hit = _identity_cache.get(key)
    if hit is None:
        return None
    expires_at, identity = hit
    if expires_at <= now:
        _identity_cache.pop(key, None)
        return None
    return identity


def _cache_put(
    key: tuple[str, str | None], identity: StaffIdentity, now: float
) -> None:
    if len(_identity_cache) >= _IDENTITY_CACHE_MAX:
        # A clinic has tens of staff, not hundreds; hitting this bound means
        # something is wrong (token churn, a load test), and the safe response
        # is to stop growing rather than to evict cleverly.
        _identity_cache.clear()
    _identity_cache[key] = (now + _IDENTITY_TTL_SECONDS, identity)


async def _resolve_identity(
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffIdentity:
    """Verify JWT → active staff → one active clinic membership. Raises 401/403.

    KHÔNG dùng trực tiếp làm dependency của endpoint. Dùng
    ``get_current_identity`` (người thật) hoặc ``get_display_identity`` (thêm cả
    màn hình phòng chờ) — xem ghi chú ở ClinicRole.DISPLAY.
    """
    claims = verify_supabase_jwt(_bearer_token(request))
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject")

    requested_clinic_id = _requested_clinic_id(request)

    cache_key = (str(sub), requested_clinic_id)
    now = monotonic()
    cached = _cache_get(cache_key, now)
    if cached is not None:
        return cached

    rows = await pool.fetch(
        """
        SELECT s.id, s.auth_user_id, s.full_name, s.short_name,
               s.primary_department,
               m.clinic_id, m.role AS membership_role,
               s.primary_location_id, l.name AS location_name,
               c.name AS clinic_name
        FROM staff s
        LEFT JOIN clinic_membership m
               ON m.staff_id = s.id AND m.is_active
        LEFT JOIN clinic_location l
               ON l.id = s.primary_location_id
        LEFT JOIN clinic c
               ON c.id = m.clinic_id
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
    location_id = row["primary_location_id"]
    if location_id is None:
        # 20260803000007 made this NOT NULL, so reaching here means the row
        # predates it or the column was cleared by a direct write. Fail closed:
        # a booking filed under a guessed branch is exactly what that migration
        # exists to prevent, and it is not visible after the fact.
        logger.warning("staff_without_location", staff_id=str(row["id"]))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản chưa được gán cơ sở khám",
        )

    membership_role = row["membership_role"]
    identity = StaffIdentity(
        staff_id=str(row["id"]),
        auth_user_id=str(row["auth_user_id"]),
        full_name=row["full_name"],
        department=dept,
        role=role_from_department(membership_role),
        clinic_id=str(clinic_id),
        location_id=str(location_id),
        location_name=row["location_name"] or "",
        short_name=row["short_name"] or "",
        clinic_name=row["clinic_name"] or "",
    )
    # Only the success path is cached. A 403 stays uncached so a staff member
    # who has just been granted a membership gets in on their next request
    # rather than after the TTL.
    _cache_put(cache_key, identity, now)
    return identity


async def get_current_identity(
    identity: StaffIdentity = Depends(_resolve_identity),
) -> StaffIdentity:
    """Danh tính của một NGƯỜI đang làm việc.

    Từ chối vai DISPLAY. Đây là chốt quan trọng nhất của vai đó: mọi endpoint
    trong hệ đều đi qua dependency này (có RoleGuard hay không), nên chặn ở đây
    nghĩa là cái tivi bị chặn ở khắp nơi MÀ KHÔNG PHẢI liệt kê chỗ nào. Bản
    kiểm kê 06/08 đếm được 26/119 endpoint chưa có RoleGuard — một danh sách
    cho phép sẽ bỏ sót đúng những chỗ ấy.
    """
    if identity.role is ClinicRole.DISPLAY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản màn hình chỉ được xem bảng gọi số",
        )
    return identity


async def get_display_identity(
    identity: StaffIdentity = Depends(_resolve_identity),
) -> StaffIdentity:
    """Danh tính cho bảng gọi số phòng chờ — nhận cả vai DISPLAY.

    CHỈ dùng cho endpoint không trả về một mẩu danh tính nào của người bệnh.
    Trước khi gắn dependency này vào một đường mới, hãy đọc lại ràng buộc ① ở
    đầu ``display_board_service``.
    """
    return identity


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
