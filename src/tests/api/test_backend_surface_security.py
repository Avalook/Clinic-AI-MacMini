"""Security contracts for the staff and report API surfaces.

Bề mặt `/tools/*` (developer tools, vốn đã tự trả 404 ở production) gỡ hẳn
24/11/2026 — test_duong_cu_da_xoa.py canh không cho mọc lại.
"""

from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute

from clinicai.api.identity import (
    RoleGuard,
    get_current_identity,
)
from clinicai.api.v1.routers.clinic_config import router as clinic_config_router
from clinicai.api.v1.routers.reports import router as reports_router
from clinicai.api.v1.routers.staff import router as staff_router


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


def _quyen_cua(calls: list[Any]) -> set[str]:
    """Quyền mà các cửa `cua_quyen` của một route gác (21 lego, 25/09/2026)."""
    return {q for c in calls for q in getattr(c, "quyen", ())}


def test_staff_reads_require_identity_and_writes_require_management() -> None:
    """All staff access is authenticated; mutations hỏi QUYỀN lego 19 (Tuyền
    25/09/2026: theo tài khoản, không theo vai) — không còn cửa theo vai."""
    for route in _routes(staff_router):
        calls = _dependency_calls(route)
        assert get_current_identity in calls, (route.path, route.methods)

        if route.methods & {"POST", "PATCH", "DELETE"}:
            assert not [c for c in calls if isinstance(c, RoleGuard)], route.path
            assert _quyen_cua(calls) & {"staff.manage", "account.manage"}, (
                route.path,
                route.methods,
            )


def test_reports_and_the_staff_roster_are_management_only_reads() -> None:
    """Quang chốt 2026-08-06: báo cáo và danh sách nhân sự không mở cho mọi người.

    25/09/2026 (21 lego): gác bằng QUYỀN của lego Báo cáo / Cài đặt phòng khám,
    không bằng vai — thu lego là mất quyền đọc. Sơ đồ phòng (overview) và dịch vụ
    (services) CỐ Ý không nằm trong danh sách này: bảng điều phối và màn đặt lịch
    cần đọc chúng.
    """
    can_quyen = {
        "/reports/booking-channels": (reports_router, "report.view"),
        "/clinic-config/staff": (clinic_config_router, "config.clinic.manage"),
    }
    for path, (router, quyen) in can_quyen.items():
        route = next(r for r in _routes(router) if r.path == path)
        calls = _dependency_calls(route)
        assert not [c for c in calls if isinstance(c, RoleGuard)], path
        assert _quyen_cua(calls) == {quyen}, path
