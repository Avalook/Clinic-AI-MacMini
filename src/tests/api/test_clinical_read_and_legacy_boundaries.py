"""Fail-closed contracts for medical reads and legacy mutation surfaces."""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import RoleGuard
from clinicai.api.v1.routers.clinical_forms import router as form_router
from clinicai.api.v1.routers.clinical_records import router as record_router
from clinicai.api.v1.routers.orchestrator import (
    router as orchestrator_router,
)
from clinicai.api.v1.routers.orchestrator import (
    scoped_thread_id,
)
from clinicai.api.v1.routers.scheduling import router as scheduling_router
from clinicai.permissions.catalogue import PRESET, QUYEN
from clinicai.permissions.y_khoa import QUYEN_Y_KHOA, cua_y_khoa
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


def _cua_quyen(route: APIRoute) -> list[object]:
    """Cửa QUYỀN (`cua_quyen`, có `.quyen`) của route — CHỈ LEGO 28/09/2026."""
    guards: list[object] = []

    def visit(dependant: object) -> None:
        for dependency in getattr(dependant, "dependencies", ()):
            if hasattr(dependency.call, "quyen"):
                guards.append(dependency.call)
            visit(dependency)

    visit(route.dependant)
    return guards


def _calls(route: APIRoute) -> list[object]:
    ra: list[object] = []

    def visit(dependant: object) -> None:
        for dependency in getattr(dependant, "dependencies", ()):
            ra.append(dependency.call)
            visit(dependency)

    visit(route.dependant)
    return ra


def test_medical_reads_ask_a_permission_not_a_role() -> None:
    """Đọc nội dung y khoa hỏi QUYỀN (24/09/2026, Tuyền chốt: "quản lý quyền
    cao nhất — có module đó thì mọi quyền của nó có cả").

    Thứ phải giữ của ROLE-02: KHÔNG MẶC ĐỊNH cho người làm vận hành. Lễ tân, thu
    ngân, CSKH, dược sĩ, trưởng ca không nhận khối khám / kết quả nào theo nhóm
    mẫu, nên không mở được — trừ khi quản lý cấp. Quản lý có đủ khối nên mở được.
    """
    for route in (
        _route(form_router, "/clinical-forms", "GET"),
        _route(record_router, "/clinical-records/doc", "GET"),
        _route(record_router, "/clinical-records/in-theo-lich/{appointment_id}", "GET"),
    ):
        assert cua_y_khoa in _calls(route), route.path
        assert not _role_guards(route), f"{route.path} vẫn gác theo vai"

    khoi_y_khoa = {QUYEN[q].khoi for q in QUYEN_Y_KHOA}
    # Mở full lego (Tuyền 30/09/2026): mọi vai nội bộ có khối y khoa trong nhóm
    # mẫu; đối tác (người ngoài) thì không. Cửa vẫn hỏi QUYỀN (ở trên).
    assert not khoi_y_khoa & set(PRESET["PARTNER"])
    for vai in (
        "RECEPTION",
        "CASHIER",
        "CASHIER_DV",
        "CASHIER_THUOC",
        "CSKH",
        "PHARMACIST",
        "TRUONG_CA",
        "DOCTOR",
        "ULTRASOUND_DOCTOR",
        "TKYK",
        "NURSE_ULTRASOUND",
        "MANAGEMENT",
    ):
        assert khoi_y_khoa & set(PRESET[vai]), vai


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

    # CHỈ LEGO (28/09/2026): cửa hỏi quyền cài đặt phòng khám / điều phối ca.
    expected = ("config.clinic.manage", "dispatch.manage")
    for path, method in (
        ("/work-sessions", "POST"),
        ("/work-sessions/{id}/staff", "POST"),
    ):
        assert not _role_guards(_route(scheduling_router, path, method))
        guards = _cua_quyen(_route(scheduling_router, path, method))
        assert len(guards) == 1
        assert getattr(guards[0], "quyen", None) == expected


def test_every_terminal_or_unknown_visit_state_keeps_a_form_read_only() -> None:
    # Danh sách TRẮNG: trạng thái lạ (kể cả một trạng thái cuối thêm sau này)
    # mặc định KHÔNG ghi được. Đó là tính chất cần giữ, không phải tập hợp cụ thể.
    for khoa in ("FINALIZED", "AMENDED", "CANCELLED", "MOT_TRANG_THAI_MOI"):
        assert khoa not in WRITABLE_VISIT_STATUSES
    assert "INCOMPLETE" in WRITABLE_VISIT_STATUSES


def test_medical_profile_columns_are_an_explicit_allowlist() -> None:
    profile = {"allergies": ["penicillin"], "notes": "theo dõi"}
    assert validated_profile(profile) == profile

    with pytest.raises(ValidationError, match="không hợp lệ"):
        validated_profile({"auth_user_id": "attacker-controlled"})


def test_debug_orchestrator_is_management_only_and_threads_are_actor_scoped() -> None:
    route = _route(orchestrator_router, "/orchestrator/chat", "POST")
    assert not _role_guards(route)
    guards = _cua_quyen(route)
    assert len(guards) == 1
    # CHỈ LEGO (28/09/2026): lego Vận hành hệ thống.
    assert getattr(guards[0], "quyen", None) == ("ops.view",)

    assert scoped_thread_id("clinic-a", "staff-a", "same-client-id") != (
        scoped_thread_id("clinic-a", "staff-b", "same-client-id")
    )
    assert scoped_thread_id("clinic-a", "staff-a", "same-client-id") != (
        scoped_thread_id("clinic-b", "staff-a", "same-client-id")
    )
