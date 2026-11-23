"""Route-level regression tests for expensive endpoint guards.

Hai cửa AI đắt `/lab/triage/{id}` và `/orchestrator/chat` (cùng bộ giới hạn
của chúng) đã gỡ 24/11/2026 — không màn nào gọi. Cửa đắt còn lại: giọng nói.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from clinicai.api.identity import RoleGuard
from clinicai.api.v1.routers.voice import VOICE_RATE_LIMIT
from clinicai.api.v1.routers.voice import router as voice_router
from clinicai.permissions.y_khoa import cua_ghi_y_khoa


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

    # 24/09/2026: hỏi QUYỀN ghi bệnh án / điền kết quả, không hỏi vai.
    assert not [call for call in calls if isinstance(call, RoleGuard)]
    assert cua_ghi_y_khoa in calls
    assert VOICE_RATE_LIMIT in calls


def test_production_limits_are_bounded_and_nonzero() -> None:
    assert (VOICE_RATE_LIMIT.limit, VOICE_RATE_LIMIT.window_seconds) == (10, 60)
