"""Cửa giảm giá phải xác minh nhân viên và giữ tenant từ phiên đăng nhập."""

from fastapi.routing import APIRoute

from clinicai.api.identity import get_current_identity
from clinicai.api.v1.routers.payment import router


def test_giam_gia_khong_nhan_tenant_tu_body() -> None:
    routes = {
        route.path: route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path in {"/payments/giam-gia", "/payments/giam-gia/{id}/huy"}
    }
    assert len(routes) == 2
    for route in routes.values():
        assert route.methods == {"POST"}
        assert route.body_field is not None
        assert "clinic_id" not in route.body_field.type_.model_fields
        calls: list[object] = []

        def visit(dependant: object) -> None:
            for dependency in getattr(dependant, "dependencies", ()):
                calls.append(dependency.call)
                visit(dependency)

        visit(route.dependant)
        assert get_current_identity in calls, route.path

