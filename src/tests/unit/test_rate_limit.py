"""Unit tests for the process-local cost-abuse guard."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import HTTPException

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.rate_limit import InMemoryRateLimiter


def _identity(
    *, staff_id: str = "staff-1", clinic_id: str = "clinic-1"
) -> StaffIdentity:
    return StaffIdentity(
        staff_id=staff_id,
        auth_user_id=f"auth-{staff_id}",
        full_name="Test Doctor",
        department=ClinicRole.DOCTOR.value,
        role=ClinicRole.DOCTOR,
        clinic_id=clinic_id,
    )


def _clock(value: list[float]) -> Callable[[], float]:
    return lambda: value[0]


@pytest.mark.asyncio
async def test_limiter_rejects_request_above_per_actor_window() -> None:
    now = [100.0]
    limiter = InMemoryRateLimiter(
        scope="voice",
        limit=2,
        window_seconds=60,
        clock=_clock(now),
    )

    await limiter(_identity())
    await limiter(_identity())

    with pytest.raises(HTTPException) as raised:
        await limiter(_identity())

    assert raised.value.status_code == 429
    assert raised.value.headers == {"Retry-After": "60"}


@pytest.mark.asyncio
async def test_limiter_namespaces_buckets_by_tenant_and_staff() -> None:
    now = [100.0]
    limiter = InMemoryRateLimiter(
        scope="brief",
        limit=1,
        window_seconds=60,
        clock=_clock(now),
    )

    await limiter(_identity(staff_id="staff-1", clinic_id="clinic-a"))
    await limiter(_identity(staff_id="staff-2", clinic_id="clinic-a"))
    await limiter(_identity(staff_id="staff-1", clinic_id="clinic-b"))

    with pytest.raises(HTTPException) as raised:
        await limiter(_identity(staff_id="staff-1", clinic_id="clinic-a"))
    assert raised.value.status_code == 429


@pytest.mark.asyncio
async def test_limiter_releases_capacity_after_window() -> None:
    now = [100.0]
    limiter = InMemoryRateLimiter(
        scope="lab-triage",
        limit=1,
        window_seconds=30,
        clock=_clock(now),
    )
    identity = _identity()

    await limiter(identity)
    now[0] = 130.0

    await limiter(identity)
    assert limiter.bucket_count == 1


@pytest.mark.asyncio
async def test_limiter_fails_closed_when_actor_capacity_is_exhausted() -> None:
    now = [100.0]
    limiter = InMemoryRateLimiter(
        scope="orchestrator",
        limit=1,
        window_seconds=60,
        max_buckets=1,
        clock=_clock(now),
    )

    await limiter(_identity(staff_id="staff-1"))

    with pytest.raises(HTTPException) as raised:
        await limiter(_identity(staff_id="staff-2"))

    assert raised.value.status_code == 429
    assert "capacity" in str(raised.value.detail).lower()
