"""Unit tests for server-authoritative identity/role (Phase 4, cluster #1)."""

from __future__ import annotations

import asyncio
import datetime as dt

import jwt
import pytest
from fastapi import HTTPException, Request

from clinicai.api import identity as ident_mod
from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
    role_from_department,
    verify_supabase_jwt,
)

SECRET = "test-jwt-secret-at-least-32-bytes"


# --------------------------- role mapping --------------------------- #
def test_role_from_department_valid() -> None:
    for role in ClinicRole:
        assert role_from_department(role.value) is role


def test_role_from_department_unknown_defaults_cskh() -> None:
    assert role_from_department("SOMETHING_ELSE") is ClinicRole.CSKH
    assert role_from_department(None) is ClinicRole.CSKH


def test_identity_predicates() -> None:
    doc = StaffIdentity(
        "s1",
        "u1",
        "BS A",
        "DOCTOR",
        ClinicRole.DOCTOR,
        "a0000000-0000-4000-8000-000000000001",
    )
    assert doc.is_doctor() and doc.can_write_clinical() and not doc.is_cashier()
    nurse = StaffIdentity(
        "s2",
        "u2",
        "ĐD B",
        "NURSE_ULTRASOUND",
        ClinicRole.NURSE_ULTRASOUND,
        "a0000000-0000-4000-8000-000000000001",
    )
    assert nurse.can_write_clinical() and not nurse.is_doctor()
    cashier = StaffIdentity(
        "s3",
        "u3",
        "TN C",
        "CASHIER",
        ClinicRole.CASHIER,
        "a0000000-0000-4000-8000-000000000001",
    )
    assert cashier.is_cashier() and not cashier.can_write_clinical()


# --------------------------- JWT verification --------------------------- #
def _token(
    secret: str = SECRET,
    aud: str = "authenticated",
    exp_delta: int = 3600,
    sub: str = "user-123",
) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": sub, "aud": aud, "exp": now + dt.timedelta(seconds=exp_delta)}
    return jwt.encode(payload, secret, algorithm="HS256")


def test_verify_jwt_hs256_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    claims = verify_supabase_jwt(_token())
    assert claims["sub"] == "user-123"


def test_verify_jwt_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    with pytest.raises(HTTPException) as e:
        verify_supabase_jwt(_token(exp_delta=-10))
    assert e.value.status_code == 401


def test_verify_jwt_wrong_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    with pytest.raises(HTTPException) as e:
        verify_supabase_jwt(_token(aud="anon"))
    assert e.value.status_code == 401


def test_verify_jwt_wrong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    with pytest.raises(HTTPException) as e:
        verify_supabase_jwt(_token(secret="attacker-secret-at-least-32-bytes"))
    assert e.value.status_code == 401


# --------------------------- get_current_identity --------------------------- #
class _FakePool:
    def __init__(self, row: object) -> None:
        if row is None:
            self._rows: list[object] = []
        elif isinstance(row, list):
            self._rows = row
        else:
            self._rows = [row]
        self.query = ""
        self.args: tuple[object, ...] = ()

    async def fetch(self, query: str, *args: object) -> list[object]:
        self.query = query
        self.args = args
        requested_clinic = args[1] if len(args) > 1 else None
        if requested_clinic is None:
            return self._rows
        return [
            row
            for row in self._rows
            if isinstance(row, dict) and row.get("clinic_id") == requested_clinic
        ]


def _req(auth: str | None, clinic_id: str | None = None) -> Request:
    """A real Starlette Request, so the header lookup behaves as in production."""
    headers = [(b"authorization", auth.encode())] if auth is not None else []
    if clinic_id is not None:
        headers.append((b"x-clinic-id", clinic_id.encode()))
    return Request({"type": "http", "headers": headers})


def test_get_current_identity_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ident_mod, "verify_supabase_jwt", lambda _t: {"sub": "u-1"})
    pool = _FakePool(
        {
            "id": "staff-9",
            "auth_user_id": "u-1",
            "full_name": "TS.BS. Phan Chí Thành",
            "primary_department": "DOCTOR",
            "membership_role": "DOCTOR",
            "clinic_id": "a0000000-0000-4000-8000-000000000001",
        }
    )
    ident = asyncio.run(get_current_identity(_req("Bearer abc"), pool))
    assert ident.staff_id == "staff-9"
    assert ident.role is ClinicRole.DOCTOR
    assert ident.can_write_clinical()
    # The tenant travels with the identity so services never fall back to the
    # transitional clinic_id DEFAULT (ADR-0009).
    assert ident.clinic_id == "a0000000-0000-4000-8000-000000000001"


def test_get_current_identity_uses_role_of_selected_clinic_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One person may have a different role at each clinic.

    ``staff.primary_department`` is global and therefore cannot authorize a
    multi-clinic request.  The role and clinic must come from the same active
    membership row selected by the identity query.
    """
    monkeypatch.setattr(ident_mod, "verify_supabase_jwt", lambda _t: {"sub": "u-1"})
    pool = _FakePool(
        [
            {
                "id": "staff-9",
                "auth_user_id": "u-1",
                "full_name": "BS làm việc nhiều phòng khám",
                "primary_department": "DOCTOR",
                "membership_role": "DOCTOR",
                "clinic_id": "a0000000-0000-4000-8000-000000000001",
            },
            {
                "id": "staff-9",
                "auth_user_id": "u-1",
                "full_name": "BS làm việc nhiều phòng khám",
                "primary_department": "DOCTOR",
                "membership_role": "MANAGEMENT",
                "clinic_id": "b0000000-0000-4000-8000-000000000002",
            },
        ]
    )

    ident = asyncio.run(
        get_current_identity(
            _req("Bearer abc", "b0000000-0000-4000-8000-000000000002"),
            pool,
        )
    )

    assert ident.department == "DOCTOR"
    assert ident.clinic_id == "b0000000-0000-4000-8000-000000000002"
    assert ident.role is ClinicRole.MANAGEMENT
    assert "m.role AS membership_role" in pool.query
    assert pool.args[1] == "b0000000-0000-4000-8000-000000000002"


def test_get_current_identity_refuses_ambiguous_multi_clinic_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A multi-clinic login must select a clinic instead of landing arbitrarily."""
    monkeypatch.setattr(ident_mod, "verify_supabase_jwt", lambda _t: {"sub": "u-1"})
    pool = _FakePool(
        [
            {
                "id": "staff-9",
                "auth_user_id": "u-1",
                "full_name": "BS nhiều nơi",
                "primary_department": "DOCTOR",
                "membership_role": "DOCTOR",
                "clinic_id": "a0000000-0000-4000-8000-000000000001",
            },
            {
                "id": "staff-9",
                "auth_user_id": "u-1",
                "full_name": "BS nhiều nơi",
                "primary_department": "DOCTOR",
                "membership_role": "MANAGEMENT",
                "clinic_id": "b0000000-0000-4000-8000-000000000002",
            },
        ]
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_identity(_req("Bearer abc"), pool))

    assert exc.value.status_code == 403
    assert "X-Clinic-ID" in str(exc.value.detail)


def test_get_current_identity_rejects_malformed_clinic_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ident_mod, "verify_supabase_jwt", lambda _t: {"sub": "u-1"})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            get_current_identity(_req("Bearer abc", "not-a-uuid"), _FakePool(None))
        )

    assert exc.value.status_code == 400


def test_get_current_identity_rejects_clinic_without_active_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """X-Clinic-ID selects among memberships; it never grants a tenant."""
    monkeypatch.setattr(ident_mod, "verify_supabase_jwt", lambda _t: {"sub": "u-1"})
    pool = _FakePool(
        {
            "id": "staff-9",
            "auth_user_id": "u-1",
            "full_name": "BS A",
            "primary_department": "DOCTOR",
            "membership_role": "DOCTOR",
            "clinic_id": "a0000000-0000-4000-8000-000000000001",
        }
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            get_current_identity(
                _req("Bearer abc", "b0000000-0000-4000-8000-000000000002"),
                pool,
            )
        )

    assert exc.value.status_code == 403


def test_get_current_identity_without_membership_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Acting without a tenant is how a row lands in the wrong clinic, so a staff
    # row with no membership must fail closed rather than default to one.
    monkeypatch.setattr(ident_mod, "verify_supabase_jwt", lambda _t: {"sub": "u-2"})
    pool = _FakePool(
        {
            "id": "staff-10",
            "auth_user_id": "u-2",
            "full_name": "Chưa gán phòng khám",
            "primary_department": "DOCTOR",
            "membership_role": None,
            "clinic_id": None,
        }
    )
    with pytest.raises(HTTPException) as e:
        asyncio.run(get_current_identity(_req("Bearer abc"), pool))
    assert e.value.status_code == 403


def test_get_current_identity_missing_bearer() -> None:
    with pytest.raises(HTTPException) as e:
        asyncio.run(get_current_identity(_req(None), _FakePool(None)))
    assert e.value.status_code == 401


def test_get_current_identity_no_linked_staff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ident_mod, "verify_supabase_jwt", lambda _t: {"sub": "u-x"})
    with pytest.raises(HTTPException) as e:
        asyncio.run(get_current_identity(_req("Bearer abc"), _FakePool(None)))
    assert e.value.status_code == 403


# --------------------------- require_role --------------------------- #
def test_require_role_allows_and_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    ident = StaffIdentity(
        "s1",
        "u1",
        "BS A",
        "DOCTOR",
        ClinicRole.DOCTOR,
        "a0000000-0000-4000-8000-000000000001",
    )
    dep_ok = require_role(ClinicRole.DOCTOR, ClinicRole.TKYK)
    assert asyncio.run(dep_ok(ident)) is ident

    dep_block = require_role(ClinicRole.CASHIER)
    with pytest.raises(HTTPException) as e:
        asyncio.run(dep_block(ident))
    assert e.value.status_code == 403
