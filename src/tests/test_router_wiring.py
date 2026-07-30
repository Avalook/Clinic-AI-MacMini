"""Every router module must actually be mounted (W5).

`clinical_records.py` was written, imported cleanly, type-checked, and never
reached: the line adding it to main.py silently failed to apply. Nothing caught
it — the module is valid Python, so ruff, mypy and 490 unit tests all passed
while POST /api/v1/clinical-records answered 404. Only driving real HTTP found
it, which is far too late for a route that writes clinical records.
"""

from __future__ import annotations

import pkgutil

import clinicai.api.v1.routers as routers_pkg
from clinicai.main import app


def _mounted_module_names() -> set[str]:
    """Module names behind the routers currently mounted on the app."""
    return {
        route.endpoint.__module__.rsplit(".", 1)[-1]
        for route in app.routes
        if hasattr(route, "endpoint")
    }


def test_every_router_module_is_mounted() -> None:
    available = {
        m.name
        for m in pkgutil.iter_modules(routers_pkg.__path__)
        if not m.name.startswith("_")
    }
    unmounted = sorted(available - _mounted_module_names())

    assert unmounted == [], (
        "these router modules exist but nothing includes them in main.py, so "
        f"their endpoints answer 404: {unmounted}"
    )


def test_the_clinical_write_endpoints_are_reachable() -> None:
    # The four W5 clinical routes, named explicitly: a 404 on any of these is a
    # silent data-loss path, not a missing feature.
    paths = {getattr(r, "path", "") for r in app.routes}
    for path in (
        "/api/v1/clinical-records",
        "/api/v1/clinical-forms",
        "/api/v1/ultrasound/measurements",
        "/api/v1/lab/orders",
        "/api/v1/lab/results/{lab_result_id}",
    ):
        assert path in paths, f"{path} is not mounted"
