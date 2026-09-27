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

import json
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date
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

from clinicai.core.clock import now_vn
from clinicai.core.database import get_db_pool
from clinicai.core.shifts import ca_tu_settings, covers, shift_windows

logger = structlog.get_logger()

SUPABASE_AUDIENCE = "authenticated"
#: Độ lệch đồng hồ cho phép giữa GoTrue (máy cấp token) và API, tính bằng giây.
#: 15/09/2026 trên stack local: GoTrue chạy trong máy ảo Docker có đồng hồ nhanh
#: hơn máy thật vài phần giây → token vừa cấp có `iat` "ở tương lai" và PyJWT
#: (mặc định lệch 0 giây) trả 401 "The token is not yet valid (iat)" — người vừa
#: đăng nhập bị đá ra ngẫu nhiên. 5 giây chỉ nới đúng chừng ấy cho iat/exp.
JWT_CLOCK_LEEWAY_SECONDS = 5


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
    # NGƯỜI NGOÀI PHÒNG KHÁM — lab, phòng chụp, nơi làm dịch vụ gửi ra ngoài.
    #
    # Vào để làm đúng MỘT việc: gửi kết quả họ vừa làm. Tuyền yêu cầu tài khoản
    # này 16/09/2026; tôi đã nêu lo ngại rằng một mật khẩu thường trực nằm ngoài
    # tầm quản lý của phòng khám là một cánh cửa mở mãi, và Tuyền chốt vẫn làm.
    #
    # Nên nó được chặn theo CÙNG cách vai DISPLAY bị chặn, và vì cùng một lý do:
    # `get_current_identity` từ chối thẳng, nên MỌI endpoint đang có và MỌI
    # endpoint viết sau này đều đóng với vai này mà không ai phải nhớ gì. Chỉ
    # `get_partner_identity` mở ra, và hôm nay đúng hai đường dùng nó.
    #
    # Danh sách cho phép thì bỏ sót; danh sách từ chối thì không.
    PARTNER = "PARTNER"


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

    #: VAI THEO VỊ TRÍ HÔM NAY (Tuyền chốt 16/09/2026). Tài khoản Phùng Thị Minh
    #: Thư là Điều dưỡng, hôm nay đứng Lễ tân + Thu ngân: menu đã đi theo vị trí
    #: nhưng mọi cửa thu ngân, check-out, đặt lịch vẫn trả 403 vì chỉ xét vai tài
    #: khoản. Tập này là các vai VẬN HÀNH mà lịch hôm nay cấp thêm — không bao giờ
    #: có vai bác sĩ (xem `VAI_THEO_VI_TRI`).
    vai_theo_vi_tri: frozenset[ClinicRole] = frozenset()
    #: Có giá trị khi cửa gác đã THAY `role` bằng vai của vị trí hôm nay: đây là
    #: vai tài khoản gốc. Nhật ký thao tác ghi cả hai ("Minh Thư, tài khoản Điều
    #: dưỡng, làm với vai Lễ tân") — không thì mất dấu ai thật sự đã bấm.
    vai_tai_khoan: ClinicRole | None = None
    #: VAI THEO LEGO ĐANG BẬT ĐỦ (Tuyền chốt 26/09/2026 — "chỉ cần lego"). None =
    #: CHƯA TÍNH (danh tính dựng tay trong test, người chưa có dòng quyền nào):
    #: giữ nguyên luật cũ theo vai tài khoản. Có giá trị thì các vai do lego quyết
    #: (`VAI_DO_LEGO`) CHỈ đến từ đây — tài khoản bác sĩ tắt lego Bàn khám thì
    #: không còn vai bác sĩ ở các cửa cũ.
    vai_theo_lego: frozenset[ClinicRole] | None = None

    def cac_vai(self) -> frozenset[ClinicRole]:
        """MỌI vai người này làm được HÔM NAY: vai vận hành vị trí trong lịch cấp,
        vai lego đang bật mang lại, vai tài khoản gốc (trừ vai do lego quyết khi
        đã tính lego), và vai cửa gác đã thay vào."""
        vai = set(self.vai_theo_vi_tri)
        goc = self.vai_goc
        if self.vai_theo_lego is None:
            vai.update((self.role, goc))
            return frozenset(vai)
        from clinicai.permissions.catalogue import VAI_DO_LEGO

        vai |= self.vai_theo_lego
        if goc.value not in VAI_DO_LEGO:
            vai.add(goc)
        if self.role != goc:
            # Cửa gác đã thay vai (theo vị trí hoặc theo lego) — vai hợp lệ.
            vai.add(self.role)
        return frozenset(vai)

    @property
    def vai_goc(self) -> ClinicRole:
        """Vai TÀI KHOẢN — khớp `clinic_membership.role` trong database."""
        return self.vai_tai_khoan or self.role

    def ds_vai(self) -> list[str]:
        """`cac_vai()` dạng chuỗi, để truyền vào truy vấn (`$n::text[]`)."""
        return sorted(v.value for v in self.cac_vai())

    def co_vai(self, roles: Iterable[ClinicRole]) -> bool:
        """Có ÍT NHẤT MỘT vai hôm nay nằm trong `roles`.

        Dùng thay cho `identity.role in roles` ở MỌI kiểm tra nghiệp vụ (Tuyền
        duyệt 16/09/2026). Vai giấy phép (bác sĩ, thư ký, quản lý) không bao giờ
        đến từ lịch, nên với chúng kết quả y như so vai tài khoản; chỉ các vai
        vận hành (lễ tân, điều dưỡng, trưởng ca) mở thêm cho người đứng vị trí.
        """
        return not self.cac_vai().isdisjoint(roles)

    def can_write_clinical(self) -> bool:
        return self.co_vai(CLINICAL_WRITE_ROLES)

    def is_doctor(self) -> bool:
        return self.co_vai(PHYSICIAN_ROLES)

    def is_cashier(self) -> bool:
        return self.co_vai(CASHIER_ROLES)


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
                leeway=JWT_CLOCK_LEEWAY_SECONDS,
            )
        signing_key = _jwk_client().get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["ES256", "RS256"],
            audience=SUPABASE_AUDIENCE,
            leeway=JWT_CLOCK_LEEWAY_SECONDS,
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
    vai_tai_khoan = role_from_department(membership_role)
    # Vị trí ĐANG TRONG CA ĐÃ DUYỆT cấp vai vận hành (S0-7) — cùng bộ lọc với
    # thanh bên (`/me/vi-tri-hom-nay`). Cache 30 giây ở dưới nghĩa là vai đổi
    # chậm tối đa 30 giây sau giờ đổi ca.
    vi_tri_hien_hanh = await doc_vi_tri_hien_hanh(pool, str(clinic_id), str(row["id"]))
    vai_lego = await doc_vai_theo_lego(
        pool, str(clinic_id), str(row["id"]), vai_tai_khoan
    )
    identity = StaffIdentity(
        staff_id=str(row["id"]),
        auth_user_id=str(row["auth_user_id"]),
        full_name=row["full_name"],
        department=dept,
        role=vai_tai_khoan,
        clinic_id=str(clinic_id),
        location_id=str(location_id),
        location_name=row["location_name"] or "",
        short_name=row["short_name"] or "",
        clinic_name=row["clinic_name"] or "",
        vai_theo_vi_tri=vai_tu_vi_tri(
            [tram for tram, _ca in vi_tri_hien_hanh], vai_tai_khoan
        ),
        vai_theo_lego=vai_lego,
    )
    # Only the success path is cached. A 403 stays uncached so a staff member
    # who has just been granted a membership gets in on their next request
    # rather than after the TTL.
    _cache_put(cache_key, identity, now)
    return identity


async def danh_tinh_nhan_vien(
    conn: asyncpg.Connection, *, clinic_id: str, staff_id: str
) -> StaffIdentity | None:
    """Danh tính của MỘT nhân viên để khối hệ thống làm THAY người ấy.

    Dây H4 (Tuyền chốt 24/09/2026): thu tiền xong, khối Hành trình xếp phòng
    thay cho người vừa thu — bằng đúng quyền của người ấy, không bằng quyền
    "hệ thống" vô hạn. Không qua JWT (không có yêu cầu HTTP nào ở đây).

    Không tính vai theo vị trí trực: mọi lệnh gọi từ đây hỏi CAPABILITY
    (`can`/`doi_quyen`), không hỏi vai. Nhân viên đã nghỉ, hay không còn thuộc
    phòng khám này → None: bên gọi bỏ qua, để người thật làm tay.
    """
    row = await conn.fetchrow(
        """
        SELECT s.id::text AS id, s.auth_user_id::text AS auth_user_id,
               s.full_name, s.short_name, s.primary_department,
               m.role AS membership_role,
               s.primary_location_id::text AS location_id,
               l.name AS location_name
          FROM staff s
          JOIN clinic_membership m
            ON m.staff_id = s.id AND m.clinic_id = $1::uuid AND m.is_active
          LEFT JOIN clinic_location l ON l.id = s.primary_location_id
         WHERE s.id = $2::uuid AND s.is_active IS NOT FALSE
         ORDER BY m.created_at, m.id
         LIMIT 1
        """,
        clinic_id,
        staff_id,
    )
    if row is None or row["location_id"] is None:
        return None
    return StaffIdentity(
        staff_id=row["id"],
        auth_user_id=row["auth_user_id"] or "",
        full_name=row["full_name"] or "",
        department=row["primary_department"],
        role=role_from_department(row["membership_role"]),
        clinic_id=clinic_id,
        location_id=row["location_id"],
        location_name=row["location_name"] or "",
        short_name=row["short_name"] or "",
    )


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
    if identity.role is ClinicRole.PARTNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đối tác chỉ được gửi kết quả",
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


async def get_partner_identity(
    identity: StaffIdentity = Depends(_resolve_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffIdentity:
    """Danh tính cho các đường của ĐỐI TÁC.

    CỬA = LEGO 21 "Đối tác" (quyền `partner.work`, kiểm toán 27/09/2026) —
    trước đây hỏi vai PARTNER/MANAGEMENT nên quyền này không lệnh nào kiểm: thu
    lego chỉ mất mục trên thanh bên. Tài khoản đối tác có lego này từ preset
    (migration 20260925000015); quản lý có vì preset có mọi khối — và thu lego
    của ai thì người ấy mất cửa, kể cả quản lý.

    Chiều kia KHÔNG đổi: vai PARTNER vẫn bị `get_current_identity` từ chối ở mọi
    nơi khác. Đừng đổi dependency ở đây sang `get_current_identity` — nó từ chối
    đúng vai mà cửa này mở cho (xem `test_vai_man_hinh.py`).
    """
    # Nhập muộn: `permissions.can` nhập ngược module này.
    from clinicai.permissions.can import can

    async with pool.acquire() as conn:
        co = await can(conn, identity, "partner.work")
    if not co:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn chưa được cấp quyền “Đối tác”.",
        )
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
        co = identity.cac_vai()
        if identity.role not in self.allowed_roles or identity.role not in co:
            # Vai đang dùng không qua (hoặc là vai do lego quyết mà lego đã tắt),
            # nhưng VỊ TRÍ HÔM NAY hay LEGO ĐANG BẬT cho phép: yêu cầu đi tiếp dưới
            # vai ấy. Thay `role` ngay tại cửa (thay vì thêm một tập vai) để MỌI
            # kiểm tra phía sau — loại thanh toán được thu, vai được đọc hàng
            # chờ… — tự đúng mà không phải sửa 41 chỗ.
            for vai in sorted(co & self.allowed_roles, key=lambda r: r.value):
                logger.info(
                    "role_theo_vi_tri"
                    if vai in identity.vai_theo_vi_tri
                    else "role_theo_lego",
                    vai_tai_khoan=identity.vai_goc.value,
                    vai_hom_nay=vai.value,
                    staff_id=identity.staff_id,
                )
                return replace(identity, role=vai, vai_tai_khoan=identity.vai_goc)
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


def dung_vai(identity: StaffIdentity, allowed: Iterable[ClinicRole]) -> StaffIdentity:
    """Danh tính đi dưới ĐÚNG vai mà thao tác cần.

    Cửa gác router chỉ thay `role` khi vai tài khoản KHÔNG qua được cửa. Có cửa
    rộng hơn thao tác (bảng chuyển trạng thái lịch hẹn quyết sau), nên người
    tài khoản Điều dưỡng đứng Lễ tân hôm nay check-in được nhờ vai theo lịch,
    nhưng nhật ký vẫn ghi "Điều dưỡng" (smoke 18/09, tài khoản đa vai). Gọi hàm
    này ngay sau khi kiểm quyền của thao tác: vai tài khoản đủ thì giữ nguyên;
    chỉ vị trí hôm nay cho phép thì đi dưới vai vị trí, giữ vai tài khoản gốc ở
    `vai_tai_khoan` — `record_event` ghi cả hai.
    """
    duoc = frozenset(allowed)
    co = identity.cac_vai()
    if identity.role in duoc and identity.role in co:
        return identity
    for vai in sorted(co & duoc, key=lambda r: r.value):
        return replace(identity, role=vai, vai_tai_khoan=identity.vai_goc)
    return identity


def require_role(*allowed: ClinicRole) -> RoleGuard:
    """Dependency factory: 403 unless the caller's role is in ``allowed``."""
    return RoleGuard(frozenset(allowed))


#: Mọi vai LÀM VIỆC TRONG phòng khám. Không có DISPLAY (cái tivi) và không có
#: PARTNER (người ngoài phòng khám) — hai vai ấy đóng theo thiết kế, và nới
#: chúng ra là một quyết định về bảo mật chứ không phải một bước dọn dẹp.
VAI_LAM_VIEC: frozenset[ClinicRole] = frozenset(ClinicRole) - {
    ClinicRole.DISPLAY,
    ClinicRole.PARTNER,
}


#: Vị trí trong lịch → vai VẬN HÀNH mà người đứng đó được dùng hôm nay.
#:
#: CHỈ VAI VẬN HÀNH. Lịch cấp quyền lễ tân, điều dưỡng, trưởng ca; KHÔNG cấp
#: bác sĩ, bác sĩ siêu âm, thư ký hay quản lý — khám, kê đơn, duyệt kết quả là
#: việc có chứng chỉ hành nghề đứng sau, không thể thành của ai đó chỉ vì bảng
#: xếp ca ghi nhầm một ô. `test_vai_theo_vi_tri.py` canh điều này.
#:
#: Khít với nhóm "Lễ tân" / "Điều dưỡng" / "Trưởng ca" của thanh bên
#: (`nav-items.ts` NHOM_THEO_VI_TRI).
VAI_THEO_VI_TRI: dict[str, ClinicRole] = {
    "T1_LETAN": ClinicRole.RECEPTION,
    "T1_THUNGAN": ClinicRole.RECEPTION,
    "T2_XEPTHUOC": ClinicRole.RECEPTION,
    "T2_TAODON": ClinicRole.RECEPTION,
    "T1_DOCHISO": ClinicRole.NURSE_ULTRASOUND,
    "T1_LAYMAU": ClinicRole.NURSE_ULTRASOUND,
    "T1_TT_DD": ClinicRole.NURSE_ULTRASOUND,
    "T1_TTNG_DD1": ClinicRole.NURSE_ULTRASOUND,
    "T1_TTNG_DD2": ClinicRole.NURSE_ULTRASOUND,
    "T1_SA_DD": ClinicRole.NURSE_ULTRASOUND,
    "T4_SA_DD1": ClinicRole.NURSE_ULTRASOUND,
    "T4_SA_DD2": ClinicRole.NURSE_ULTRASOUND,
    "T4_SANCHAU_DD": ClinicRole.NURSE_ULTRASOUND,
    "T4_SAN_DD": ClinicRole.NURSE_ULTRASOUND,
    "T4_BIO_DD": ClinicRole.NURSE_ULTRASOUND,
    "DIEU_PHOI": ClinicRole.TRUONG_CA,
    # Mã ĐỜI CŨ còn trong lịch 14–27/09/2026 (khớp `MA_VI_TRI_CU` ở nav-items.ts):
    # lịch quản lý đã xếp thì phải được hiểu, dù ghi theo mẫu cũ.
    "LE_TAN": ClinicRole.RECEPTION,
    "LAY_MAU": ClinicRole.NURSE_ULTRASOUND,
    "PHU_BS_SA": ClinicRole.NURSE_ULTRASOUND,
}

#: Thứ tự HIỂN THỊ khi một người có nhiều vai vận hành trong ngày: Lễ tân ở trên,
#: Điều dưỡng ở dưới (Tuyền 17/09/2026). Vai đầu là "vai chính" của trang chủ.
THU_TU_VAI_VAN_HANH: tuple[ClinicRole, ...] = (
    ClinicRole.RECEPTION,
    ClinicRole.NURSE_ULTRASOUND,
    ClinicRole.TRUONG_CA,
)

#: Không vai nào trong tập này được cấp qua lịch, dù bảng trên có ghi gì.
VAI_KHONG_CAP_QUA_LICH: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.MANAGEMENT,
        ClinicRole.PARTNER,
        ClinicRole.DISPLAY,
    }
)


async def doc_vai_theo_lego(
    pool: asyncpg.Pool, clinic_id: str, staff_id: str, vai_tai_khoan: ClinicRole
) -> frozenset[ClinicRole] | None:
    """Vai mà lego đang bật đủ mang lại (Tuyền chốt 26/09/2026).

    None — giữ luật cũ theo vai tài khoản — khi: tài khoản ngoài phòng khám
    (Đối tác, TV), hoặc người CHƯA CÓ dòng quyền nào. Vế sau là lưới an toàn: một
    phòng khám chưa cấp quyền (hay một bản sao lỗi) không được làm mọi người mất
    vai trong im lặng. Migration 15 đã cấp gói mẫu cho mọi thành viên.
    """
    if vai_tai_khoan in (ClinicRole.PARTNER, ClinicRole.DISPLAY):
        return None
    from clinicai.permissions.catalogue import vai_tu_lego

    khoi = [
        r["work_pack"]
        for r in await pool.fetch(
            "SELECT DISTINCT work_pack FROM v_quyen_hieu_luc"
            " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
            "   AND scope_type = 'CLINIC'",
            clinic_id,
            staff_id,
        )
    ]
    if not khoi:
        return None
    return frozenset(ClinicRole(v) for v in vai_tu_lego(khoi))


def vai_tu_vi_tri(
    vi_tri: list[str] | tuple[str, ...], vai_tai_khoan: ClinicRole
) -> frozenset[ClinicRole]:
    """Vai vận hành lịch hôm nay cấp thêm. Thuần — test được không cần DB."""
    # Tài khoản ngoài phòng khám không bao giờ được cấp gì từ lịch.
    if vai_tai_khoan in (ClinicRole.PARTNER, ClinicRole.DISPLAY):
        return frozenset()
    return frozenset(
        VAI_THEO_VI_TRI[v]
        for v in vi_tri
        if v in VAI_THEO_VI_TRI
        and VAI_THEO_VI_TRI[v] not in VAI_KHONG_CAP_QUA_LICH
        and VAI_THEO_VI_TRI[v] != vai_tai_khoan
    )


#: Khoá ân hạn trong ``clinic.settings``: số phút vai theo lịch còn giữ trước giờ
#: vào ca và sau giờ hết ca. Mặc định 0 (Target Contract 18/09/2026, C2).
KHOA_AN_HAN_CA = "vai_lich_an_han_phut"
AN_HAN_CA_TOI_DA = 120


#: Công tắc luật "vai theo ca" trong ``clinic.settings``. CHỈ đúng ``true`` mới
#: bật; mặc định TẮT (HOLD_FOR_PROD, 18/09/2026): lịch prod ngày thường chỉ có
#: ca tối trong khi phòng khám mở 07–22 — chưa đủ chắc để bật cho người thật.
KHOA_BAT_LUAT_CA = "vai_lich_theo_ca"


def _settings_dict(raw: object) -> dict[str, Any]:
    doc: Any = raw
    if isinstance(doc, (str, bytes)):
        try:
            doc = json.loads(doc)
        except (ValueError, TypeError):
            return {}
    return doc if isinstance(doc, dict) else {}


def luat_ca_dang_bat(raw: object) -> bool:
    """Luật S0-7 có bật cho phòng khám này không. Rác → tắt, không ném."""
    return _settings_dict(raw).get(KHOA_BAT_LUAT_CA) is True


def an_han_ca_tu_settings(raw: object) -> int:
    """``clinic.settings`` → số phút ân hạn quanh ca. Rác → 0, không ném.

    Ngoài 0–120 cũng là rác: ân hạn 1000 phút là cấp vai cả ngày trá hình, đúng
    thứ luật này sinh ra để chặn.
    """
    v = _settings_dict(raw).get(KHOA_AN_HAN_CA)
    if isinstance(v, bool) or not isinstance(v, int):
        return 0
    return v if 0 <= v <= AN_HAN_CA_TOI_DA else 0


def vi_tri_dang_trong_ca(
    dong: Sequence[tuple[str, str, str]], phut: int, settings: object
) -> list[tuple[str, str]]:
    """Dòng lịch hôm nay ``(trạm, ca, trạng thái)`` → những ``(trạm, ca)`` đang
    cấp vai: ĐÃ DUYỆT và moc ``phut`` nằm trong giờ ca (± ân hạn).

    Thuần — cửa gác và thanh bên cùng gọi qua `doc_vi_tri_hien_hanh`. Giờ ca đọc
    ``clinic.settings.ca_lam_viec`` qua `core.shifts`, cùng nguồn với đặt lịch.
    Ca FULL là HAI khoảng (nghỉ trưa ở giữa), nên giờ nghỉ trưa không cấp vai.

    Công tắc `luat_ca_dang_bat` TẮT (mặc định) → hành vi TRƯỚC S0-7: mọi dòng
    trừ REJECTED cấp vai cả ngày.
    """
    if not luat_ca_dang_bat(settings):
        cu: list[tuple[str, str]] = []
        for tram, ma_ca, trang_thai in dong:
            if trang_thai != "REJECTED" and (tram, ma_ca) not in cu:
                cu.append((tram, ma_ca))
        return cu
    ca = ca_tu_settings(settings)
    an_han = an_han_ca_tu_settings(settings)
    ket: list[tuple[str, str]] = []
    for tram, ma_ca, trang_thai in dong:
        if trang_thai != "APPROVED":
            continue
        khoang = [
            (lo - an_han, hi + an_han)
            for lo, hi in shift_windows(ma_ca, 0, 24 * 60, ca)
        ]
        if covers(khoang, phut) and (tram, ma_ca) not in ket:
            ket.append((tram, ma_ca))
    return ket


async def doc_vi_tri_hien_hanh(
    pool: asyncpg.Pool,
    clinic_id: str,
    staff_id: str,
    *,
    hom_nay: date | None = None,
    phut: int | None = None,
) -> list[tuple[str, str]]:
    """Vị trí người này ĐANG đứng — bộ lọc DUY NHẤT cho vai theo lịch (S0-7).

    Thứ tự: ca sớm trước, rồi thứ tự vị trí trong lịch; vai đầu là "vai chính"
    quyết định màn hình (lib/clinic-session.ts).
    """
    bay_gio = now_vn()
    ngay = hom_nay or bay_gio.date()
    moc = phut if phut is not None else bay_gio.hour * 60 + bay_gio.minute
    rows = await pool.fetch(
        """
        SELECT w.station, w.shift, w.status, c.settings
          FROM public.work_roster w
          JOIN public.clinic c ON c.id = w.clinic_id
          LEFT JOIN public.vi_tri_lam_viec v
            ON v.clinic_id = w.clinic_id AND v.code = w.station
         WHERE w.clinic_id = $1::uuid
           AND w.staff_id = $2::uuid
           AND w.work_date = $3::date
           -- Lọc APPROVED/giờ ca nằm ở `vi_tri_dang_trong_ca` (theo công tắc).
           AND w.status <> 'REJECTED'
         ORDER BY array_position(ARRAY['SANG', 'CHIEU', 'TOI', 'FULL'], w.shift),
                  v.sort NULLS LAST, w.station
        """,
        clinic_id,
        staff_id,
        ngay,
    )
    if not rows:
        return []
    return vi_tri_dang_trong_ca(
        [(str(r["station"]), str(r["shift"]), str(r["status"])) for r in rows],
        moc,
        rows[0]["settings"],
    )


def vai_theo_thu_tu(vi_tri: list[str], vai_tai_khoan: ClinicRole) -> list[str]:
    """Vai vận hành các vị trí hôm nay mang lại — KỂ CẢ vai trùng vai tài khoản
    (lễ tân đứng Lễ tân vẫn là "hôm nay làm Lễ tân") — xếp Lễ tân → Điều dưỡng →
    Trưởng ca. Chỉ để HIỂN THỊ; quyền dùng `vai_tu_vi_tri`."""
    if vai_tai_khoan in (ClinicRole.PARTNER, ClinicRole.DISPLAY):
        return []
    co = {
        VAI_THEO_VI_TRI[v]
        for v in vi_tri
        if v in VAI_THEO_VI_TRI and VAI_THEO_VI_TRI[v] not in VAI_KHONG_CAP_QUA_LICH
    }
    return [v.value for v in THU_TU_VAI_VAN_HANH if v in co]


def mo_quyen_tam_thoi() -> bool:
    """Đang bật chế độ MỞ QUYỀN TẠM THỜI?

    Tuyền chốt 16/09/2026: *"giờ này mở quyền giúp tôi, tất cả các tài khoản
    đều có thể thao tác đã, đừng bị phụ thuộc lịch khám nữa, trừ bác sĩ ra
    thui, tại giờ đang rối, trước mắt giải quyết vậy đã"*.

    LÀ CÔNG TẮC, KHÔNG PHẢI XOÁ LUẬT. Những luật bị nới ở đây đều từng được
    chốt có lý do — đặc biệt luật "thư ký nào theo bác sĩ ấy" (Tuyền, 15/09).
    Xoá chúng đi thì lúc phòng khám hết rối, dựng lại là dựng lại từ đầu, và
    lý do đằng sau từng luật đã mất. Để sau một công tắc thì tắt là về như cũ.

    MẶC ĐỊNH TẮT — HỎNG THÌ ĐÓNG (kiểm toán 27/09/2026, Tuyền: "xử lý đi,
    đừng để vậy"). Trước đó mặc định BẬT với lý do "biến rơi rụng thì quyền tự
    siết lại trong im lặng". Nhưng từ 26/09 quyền đã đi theo LEGO của tài khoản
    (không còn phụ thuộc lịch), prod đặt `MO_QUYEN_TAM_THOI=0` và mô phỏng xanh
    — lý do ấy hết đúng, còn chiều ngược lại (biến rơi rụng là cả hệ tự MỞ quyền
    trong im lặng) thì nguy hiểm hơn. Chỉ đúng "1" / "true" / "yes" mới bật; máy
    chủ vẫn KÊU TO lúc khởi động khi bật (xem `main.py`).

    Bật lại: đặt `MO_QUYEN_TAM_THOI=1` trong `.env.prod` rồi dựng lại container.
    """
    return os.environ.get("MO_QUYEN_TAM_THOI", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


class RoleGuardCoTheMo(RoleGuard):
    """Cửa gác nới ra khi công tắc mở quyền tạm thời đang bật.

    ĐỌC CÔNG TẮC LÚC GỌI, KHÔNG PHẢI LÚC DỰNG. Bản đầu quyết định tập vai ngay
    trong hàm dựng — mà hàm dựng chạy lúc *import module*, tức trước khi bất kỳ
    ai kịp đặt biến môi trường. Hệ quả: đặt `MO_QUYEN_TAM_THOI=0` rồi mà quyền
    vẫn mở, và không có gì trên màn hình mâu thuẫn với điều đó. Đọc lúc gọi tốn
    thêm một lần tra `os.environ` mỗi yêu cầu — không đo được, và đổi lại là
    công tắc thật sự bật tắt được.

    `allowed_roles` vẫn giữ tập GỐC, cố ý: máy kiểm phạm vi và các bài kiểm đối
    chiếu với `roles.ts` phải đọc được Ý ĐỊNH của cửa này, chứ không phải trạng
    thái tạm thời của một biến môi trường.
    """

    async def __call__(
        self,
        identity: StaffIdentity = Depends(get_current_identity),
    ) -> StaffIdentity:
        # Vai theo vị trí hôm nay đi TRƯỚC công tắc: người đứng Lễ tân thì làm
        # việc dưới vai Lễ tân, để kiểm tra phía sau đọc đúng vai.
        if identity.role not in self.allowed_roles and any(
            v in self.allowed_roles for v in identity.cac_vai()
        ):
            return await super().__call__(identity)
        if mo_quyen_tam_thoi() and identity.role in VAI_LAM_VIEC:
            return identity
        return await super().__call__(identity)


def require_role_co_the_mo(*allowed: ClinicRole) -> RoleGuard:
    """Như `require_role`, nhưng NHẬN MỌI VAI LÀM VIỆC khi công tắc đang bật.

    CHỈ DÙNG CHO CỬA KHÔNG PHẢI VIỆC CỦA BÁC SĨ. Khám, kê đơn, chẩn đoán, duyệt
    chỉ định vẫn `require_role(DOCTOR)` — Tuyền nói rõ "trừ bác sĩ ra thui", và
    đó là ranh giới có luật hành nghề đứng sau, không phải một quy ước nội bộ.
    """
    return RoleGuardCoTheMo(frozenset(allowed))
