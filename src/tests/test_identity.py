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
        self._row = row

    async def fetchrow(self, _query: str, *_args: object) -> object:
        return self._row


def _req(auth: str | None) -> Request:
    """A real Starlette Request, so the header lookup behaves as in production."""
    headers = [(b"authorization", auth.encode())] if auth is not None else []
    return Request({"type": "http", "headers": headers})


def test_get_current_identity_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ident_mod, "verify_supabase_jwt", lambda _t: {"sub": "u-1"})
    pool = _FakePool(
        {
            "id": "staff-9",
            "auth_user_id": "u-1",
            "full_name": "TS.BS. Phan Chí Thành",
            "primary_department": "DOCTOR",
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
