"""Security contracts for the staff and developer-tools API surfaces."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from clinicai.api.identity import (
    ClinicRole,
    RoleGuard,
    StaffIdentity,
    get_current_identity,
)
from clinicai.api.v1.routers import tools as tools_module
from clinicai.api.v1.routers.staff import router as staff_router
from clinicai.api.v1.routers.tools import router as tools_router
from clinicai.tools._common.context import new_trace


def _routes(router: object) -> list[APIRoute]:
    return [route for route in getattr(router, "routes") if isinstance(route, APIRoute)]


def _dependency_calls(route: APIRoute) -> list[object]:
    calls: list[object] = []

    def visit(dependant: object) -> None:
        for dependency in getattr(dependant, "dependencies", ()):
            calls.append(dependency.call)
            visit(dependency)

    visit(route.dependant)
    return calls


def test_every_tools_endpoint_requires_verified_staff_identity() -> None:
    """The dev/tool surface must never be protected by only the shared API key."""
    for route in _routes(tools_router):
        calls = _dependency_calls(route)
        assert get_current_identity in calls, route.path
        assert tools_module._require_tools_access in calls, route.path
        guards = [call for call in calls if isinstance(call, RoleGuard)]
        assert len(guards) == 1, route.path
        assert guards[0].allowed_roles == frozenset({ClinicRole.MANAGEMENT})


def test_tools_http_surface_is_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(HTTPException) as exc:
        tools_module._require_tools_access(_identity())
    assert exc.value.status_code == 404


def test_tools_http_surface_allows_management_in_explicit_test_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity()
    monkeypatch.setenv("APP_ENV", "test")
    assert tools_module._require_tools_access(identity) is identity


def test_tools_http_bodies_never_accept_a_caller_supplied_clinic_id() -> None:
    """Tenant always comes from StaffIdentity, never from request JSON."""
    tenant_tool_paths = {
        "/tools/patient/get-summary",
        "/tools/scheduling/find-oncall",
        "/tools/event-log/append",
        "/tools/task/create",
        "/tools/task/query",
    }
    by_path = {route.path: route for route in _routes(tools_router)}

    for path in tenant_tool_paths:
        body = by_path[path].body_field
        assert body is not None
        assert "clinic_id" not in body.type_.model_fields, path


def test_staff_reads_require_identity_and_writes_require_management() -> None:
    """All staff access is authenticated; mutations are MANAGEMENT-only."""
    for route in _routes(staff_router):
        calls = _dependency_calls(route)
        assert get_current_identity in calls, (route.path, route.methods)

        if route.methods & {"POST", "PATCH", "DELETE"}:
            guards = [call for call in calls if isinstance(call, RoleGuard)]
            assert len(guards) == 1, (route.path, route.methods)
            assert guards[0].allowed_roles == frozenset({ClinicRole.MANAGEMENT})


def _identity() -> StaffIdentity:
    clinic_id = uuid4()
    return StaffIdentity(
        staff_id=str(uuid4()),
        auth_user_id=str(uuid4()),
        full_name="Quản lý an toàn",
        department=ClinicRole.MANAGEMENT.value,
        role=ClinicRole.MANAGEMENT,
        clinic_id=str(clinic_id),
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def _awaited_arg(mock: AsyncMock, index: int) -> Any:
    awaited = mock.await_args
    assert awaited is not None
    return awaited.args[index]


@pytest.mark.asyncio
async def test_tools_build_tenant_inputs_from_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every tenant-aware tool receives the server-resolved clinic UUID."""
    identity = _identity()
    pool = MagicMock()
    publisher = MagicMock()

    patient_call = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(tools_module, "get_patient_summary", patient_call)
    await tools_module._patient_get_summary(
        tools_module.PatientSummaryRequest(
            patient_id=uuid4(),
            ctx=new_trace(),
        ),
        identity,
        pool,
    )
    assert str(_awaited_arg(patient_call, 0).clinic_id) == identity.clinic_id

    oncall_call = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(tools_module, "find_oncall_staff", oncall_call)
    await tools_module._scheduling_find_oncall(
        tools_module.FindOncallRequest(
            work_session_id=uuid4(),
            ctx=new_trace(),
        ),
        identity,
        pool,
    )
    assert str(_awaited_arg(oncall_call, 0).clinic_id) == identity.clinic_id

    append_call = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(tools_module, "append_event", append_call)
    await tools_module._event_log_append(
        tools_module.AppendEventRequest(
            event_type="security.test",
            entity_type="staff",
            entity_id=uuid4(),
            payload={},
            ctx=new_trace(),
        ),
        identity,
        pool,
        publisher,
    )
    assert str(_awaited_arg(append_call, 0).clinic_id) == identity.clinic_id

    create_call = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(tools_module, "create_task", create_call)
    await tools_module._task_create(
        tools_module.CreateTaskRequest(task_type="TEST", title="Tenant test"),
        identity,
        pool,
    )
    assert str(_awaited_arg(create_call, 1).clinic_id) == identity.clinic_id

    query_call = AsyncMock(return_value=[])
    monkeypatch.setattr(tools_module, "query_tasks", query_call)
    await tools_module._task_query(
        tools_module.QueryTasksRequest(),
        identity,
        pool,
    )
    assert str(_awaited_arg(query_call, 1).clinic_id) == identity.clinic_id
