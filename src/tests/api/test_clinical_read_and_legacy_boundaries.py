"""Fail-closed contracts for medical reads and legacy mutation surfaces."""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import CLINICAL_WRITE_ROLES, ClinicRole, RoleGuard
from clinicai.api.v1.routers.brief import router as brief_router
from clinicai.api.v1.routers.clinical_forms import router as form_router
from clinicai.api.v1.routers.orchestrator import (
    router as orchestrator_router,
)
from clinicai.api.v1.routers.orchestrator import (
    scoped_thread_id,
)
from clinicai.api.v1.routers.scheduling import router as scheduling_router
from clinicai.services.clinical_form_service import WRITABLE_VISIT_STATUSES
from clinicai.services.clinical_record_service import validated_profile


def _route(router: object, path: str, method: str) -> APIRoute:
    return next(
        route
        for route in getattr(router, "routes")
        if isinstance(route, APIRoute)
        and route.path == path
        and method in route.methods
    )


def _role_guards(route: APIRoute) -> list[RoleGuard]:
    guards: list[RoleGuard] = []

    def visit(dependant: object) -> None:
        for dependency in getattr(dependant, "dependencies", ()):
            if isinstance(dependency.call, RoleGuard):
                guards.append(dependency.call)
            visit(dependency)

    visit(route.dependant)
    return guards


def test_medical_form_read_and_ai_brief_require_a_clinical_role() -> None:
    """Neither route may be reachable by a non-clinical role.

    Asserted as a SUBSET, not equality. The property that matters is the one in
    this test's name: reception, the cashier and management must not get in
    (ROLE-02). A route is free to be stricter — /brief is DOCTOR_ROLES + TKYK
    because the AI pre-visit summary is for whoever runs the consultation, and a
    sonographer nurse has no use for it. Demanding equality would have forced
    that guard to be widened to satisfy a test, which is backwards.
    """
    for route in (
        _route(form_router, "/clinical-forms", "GET"),
        _route(brief_router, "/brief/{clinic_patient_id}", "POST"),
    ):
        guards = _role_guards(route)
        assert len(guards) == 1
        allowed = guards[0].allowed_roles
        assert allowed, f"{route.path} has an empty role guard"
        assert allowed <= CLINICAL_WRITE_ROLES, (
            f"{route.path} admits non-clinical roles: "
            f"{sorted(r.value for r in allowed - CLINICAL_WRITE_ROLES)}"
        )


def test_legacy_scheduling_mutations_cannot_bypass_canonical_services() -> None:
    paths = {
        (route.path, method)
        for route in getattr(scheduling_router, "routes")
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert ("/appointments", "POST") not in paths
    assert ("/appointments/{id}/confirm", "PATCH") not in paths
    assert ("/appointments/{id}/cancel", "PATCH") not in paths

    expected = frozenset({ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA})
    for path, method in (
        ("/work-sessions", "POST"),
        ("/work-sessions/{id}/staff", "POST"),
    ):
        guards = _role_guards(_route(scheduling_router, path, method))
        assert len(guards) == 1
        assert guards[0].allowed_roles == expected


def test_every_terminal_or_unknown_visit_state_keeps_a_form_read_only() -> None:
    assert WRITABLE_VISIT_STATUSES == frozenset({"OPEN", "IN_PROGRESS"})


def test_medical_profile_columns_are_an_explicit_allowlist() -> None:
    profile = {"allergies": ["penicillin"], "notes": "theo dõi"}
    assert validated_profile(profile) == profile

    with pytest.raises(ValidationError, match="không hợp lệ"):
        validated_profile({"auth_user_id": "attacker-controlled"})


def test_debug_orchestrator_is_management_only_and_threads_are_actor_scoped() -> None:
    route = _route(orchestrator_router, "/orchestrator/chat", "POST")
    guards = _role_guards(route)
    assert len(guards) == 1
    assert guards[0].allowed_roles == frozenset({ClinicRole.MANAGEMENT})

    assert scoped_thread_id("clinic-a", "staff-a", "same-client-id") != (
        scoped_thread_id("clinic-a", "staff-b", "same-client-id")
    )
    assert scoped_thread_id("clinic-a", "staff-a", "same-client-id") != (
        scoped_thread_id("clinic-b", "staff-a", "same-client-id")
    )
