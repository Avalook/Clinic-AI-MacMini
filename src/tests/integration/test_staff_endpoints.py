"""Integration tests for Staff FastAPI endpoints."""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import asyncpg
import pytest
from httpx import AsyncClient

from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.main import app


@pytest.fixture(autouse=True)
async def management_identity(
    db_pool: asyncpg.Pool,
) -> AsyncIterator[None]:
    """Drive staff endpoints through their real MANAGEMENT authorization gate."""
    clinic_id = await db_pool.fetchval(
        "SELECT id FROM clinic ORDER BY created_at LIMIT 1"
    )
    identity = StaffIdentity(
        staff_id=str(uuid4()),
        auth_user_id=str(uuid4()),
        full_name="Integration Test Manager",
        department=ClinicRole.MANAGEMENT.value,
        role=ClinicRole.MANAGEMENT,
        clinic_id=str(clinic_id),
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )
    app.dependency_overrides[get_current_identity] = lambda: identity
    yield
    app.dependency_overrides.pop(get_current_identity, None)


@pytest.mark.asyncio
async def test_create_and_get_staff_success(
    async_client: AsyncClient, clean_db: None, location_id: UUID
) -> None:
    """POST /api/v1/staff and then GET /api/v1/staff/{id} should succeed."""
    payload = {
        "full_name": "Test Staff Member",
        "short_name": "TSM",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
        "employment_type": "FULL_TIME",
        "is_training": False,
        "is_active": True,
    }

    # 1. Create Staff
    res_create = await async_client.post("/api/v1/staff", json=payload)
    assert res_create.status_code == 201
    created = res_create.json()
    assert created["full_name"] == "Test Staff Member"
    staff_id = created["id"]

    # 2. Get Staff
    res_get = await async_client.get(f"/api/v1/staff/{staff_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == staff_id


@pytest.mark.asyncio
async def test_get_staff_not_found(async_client: AsyncClient, clean_db: None) -> None:
    """GET /api/v1/staff/{id} with missing ID returns 404."""
    res = await async_client.get(f"/api/v1/staff/{uuid4()}")
    assert res.status_code == 404
    assert res.json()["error"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_staff_filters(
    async_client: AsyncClient, clean_db: None, location_id: UUID
) -> None:
    """GET /api/v1/staff filters location_id and assignable correctly."""
    # Need to insert this location into DB first to satisfy references,
    # but we can just set primary_location_id to None or location_id.
    # Since primary_location_id is nullable, we can set it to None!
    # Let's create:
    # 1. Active & Non-training staff (assignable) at location_id
    staff_active_assignable = {
        "full_name": "Active Assignable",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
        "is_training": False,
        "is_active": True,
    }
    # 2. Active & Training staff at location_id
    staff_training = {
        "full_name": "Active Training",
        "primary_department": "NURSE_ULTRASOUND",
        "primary_location_id": str(location_id),
        "is_training": True,
        "is_active": True,
    }
    # 3. Active & Non-training staff at location = None
    staff_other_loc = {
        "full_name": "Active Other Location",
        "primary_department": "CSKH",
        "primary_location_id": None,
        "is_training": False,
        "is_active": True,
    }

    await async_client.post("/api/v1/staff", json=staff_active_assignable)
    await async_client.post("/api/v1/staff", json=staff_training)
    await async_client.post("/api/v1/staff", json=staff_other_loc)

    # Test list_active without filters -> returns all 3
    res_all = await async_client.get("/api/v1/staff")
    assert res_all.status_code == 200
    assert len(res_all.json()) == 3

    # Test list_active filtered by location_id -> returns 2
    res_loc = await async_client.get(
        "/api/v1/staff", params={"location_id": str(location_id)}
    )
    assert res_loc.status_code == 200
    assert len(res_loc.json()) == 2
    assert {s["full_name"] for s in res_loc.json()} == {
        "Active Assignable",
        "Active Training",
    }

    # Test list_assignable -> returns 2 (Active Assignable and Active Other Location)
    res_assignable = await async_client.get(
        "/api/v1/staff", params={"assignable": "true"}
    )
    assert res_assignable.status_code == 200
    assert len(res_assignable.json()) == 2
    assert {s["full_name"] for s in res_assignable.json()} == {
        "Active Assignable",
        "Active Other Location",
    }

    # Test list_assignable + location_id -> returns 1
    res_assignable_loc = await async_client.get(
        "/api/v1/staff",
        params={"assignable": "true", "location_id": str(location_id)},
    )
    assert res_assignable_loc.status_code == 200
    assert len(res_assignable_loc.json()) == 1
    assert res_assignable_loc.json()[0]["full_name"] == "Active Assignable"


@pytest.mark.asyncio
async def test_update_staff_success(
    async_client: AsyncClient, clean_db: None, location_id: UUID
) -> None:
    """PATCH /api/v1/staff/{id} updates fields successfully."""
    payload = {
        "full_name": "Before Update",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    created = (await async_client.post("/api/v1/staff", json=payload)).json()
    staff_id = created["id"]

    update_payload = {
        "full_name": "After Update",
        "employment_type": "PART_TIME",
    }
    res_update = await async_client.patch(
        f"/api/v1/staff/{staff_id}", json=update_payload
    )
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["full_name"] == "After Update"
    assert updated["employment_type"] == "PART_TIME"


@pytest.mark.asyncio
async def test_delete_staff_success(
    async_client: AsyncClient, clean_db: None, location_id: UUID
) -> None:
    """DELETE /api/v1/staff/{id} soft-deactivates staff."""
    payload = {
        "full_name": "To Be Deleted",
        "primary_department": "DOCTOR",
        "primary_location_id": str(location_id),
    }
    created = (await async_client.post("/api/v1/staff", json=payload)).json()
    staff_id = created["id"]

    res_delete = await async_client.delete(f"/api/v1/staff/{staff_id}")
    assert res_delete.status_code == 204

    # Verify status is inactive
    res_get = await async_client.get(f"/api/v1/staff/{staff_id}")
    assert res_get.status_code == 200
    assert res_get.json()["is_active"] is False
