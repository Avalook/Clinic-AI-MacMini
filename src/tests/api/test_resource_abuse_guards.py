"""Route-level regression tests for expensive endpoint guards."""

from __future__ import annotations

from fastapi.routing import APIRoute

from clinicai.api.identity import CLINICAL_WRITE_ROLES, RoleGuard
from clinicai.api.v1.routers.brief import (
    BRIEF_RATE_LIMIT,
)
from clinicai.api.v1.routers.brief import (
    router as brief_router,
)
from clinicai.api.v1.routers.lab import (
    LAB_TRIAGE_RATE_LIMIT,
)
from clinicai.api.v1.routers.lab import (
    router as lab_router,
)
from clinicai.api.v1.routers.orchestrator import (
    ORCHESTRATOR_RATE_LIMIT,
)
from clinicai.api.v1.routers.orchestrator import (
    router as orchestrator_router,
)
from clinicai.api.v1.routers.voice import VOICE_RATE_LIMIT
from clinicai.api.v1.routers.voice import router as voice_router


def _route(router: object, path: str, method: str) -> APIRoute:
    routes = getattr(router, "routes")
    return next(
        route
        for route in routes
        if isinstance(route, APIRoute)
        and route.path == path
        and method in route.methods
    )


def _dependency_calls(route: APIRoute) -> set[object]:
    return {dependency.call for dependency in route.dependant.dependencies}


def test_voice_requires_clinical_role_and_rate_limit() -> None:
    route = _route(voice_router, "/voice/transcribe", "POST")
    calls = _dependency_calls(route)

    role_guards = [call for call in calls if isinstance(call, RoleGuard)]
    assert len(role_guards) == 1
    assert role_guards[0].allowed_roles == CLINICAL_WRITE_ROLES
    assert VOICE_RATE_LIMIT in calls


def test_all_expensive_ai_routes_attach_their_rate_limiter() -> None:
    cases = [
        (brief_router, "/brief/{clinic_patient_id}", BRIEF_RATE_LIMIT),
        (lab_router, "/lab/triage/{lab_result_id}", LAB_TRIAGE_RATE_LIMIT),
        (orchestrator_router, "/orchestrator/chat", ORCHESTRATOR_RATE_LIMIT),
    ]

    for router, path, limiter in cases:
        route = _route(router, path, "POST")
        assert limiter in _dependency_calls(route)


def test_production_limits_are_bounded_and_nonzero() -> None:
    assert (VOICE_RATE_LIMIT.limit, VOICE_RATE_LIMIT.window_seconds) == (10, 60)
    assert (BRIEF_RATE_LIMIT.limit, BRIEF_RATE_LIMIT.window_seconds) == (20, 60)
    assert (LAB_TRIAGE_RATE_LIMIT.limit, LAB_TRIAGE_RATE_LIMIT.window_seconds) == (
        30,
        60,
    )
    assert (
        ORCHESTRATOR_RATE_LIMIT.limit,
        ORCHESTRATOR_RATE_LIMIT.window_seconds,
    ) == (20, 60)
