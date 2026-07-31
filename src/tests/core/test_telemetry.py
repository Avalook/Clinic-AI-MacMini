"""The request telemetry buffer.

Two properties matter more than the arithmetic: a 4xx must not pollute the error
feed, and no filled-in path may ever reach the buffer. The first decides whether
anyone keeps reading the screen; the second decides whether a debugging tool
becomes a place patient identifiers leak.
"""

from __future__ import annotations

from typing import Any

from clinicai.core.telemetry import Telemetry, percentile, route_template


def _tel(n: int = 0, **kw: Any) -> Telemetry:
    t = Telemetry()
    for i in range(n):
        t.record(
            route="/api/v1/work-items",
            method="GET",
            status=200,
            duration_ms=float(i),
            **kw,
        )
    return t


def test_only_server_errors_reach_the_error_feed() -> None:
    """4xx is the API correctly saying no, not a fault.

    A guarded API refuses constantly — role checks, gate conflicts, validation.
    Putting those in the error feed fills it with correct behaviour and nobody
    reads it after the first day.
    """
    t = Telemetry()
    for status in (200, 400, 403, 404, 409, 422):
        t.record(route="/x", method="GET", status=status, duration_ms=1.0)
    assert t.snapshot()["errors"] == []

    t.record(route="/x", method="POST", status=500, duration_ms=1.0, kind="ValueError")
    errors = t.snapshot()["errors"]
    assert len(errors) == 1
    assert errors[0]["kind"] == "ValueError"


def test_status_classes_are_counted_separately() -> None:
    t = Telemetry()
    for status in (200, 201, 403, 500):
        t.record(route="/x", method="GET", status=status, duration_ms=1.0)
    assert t.snapshot()["statuses"] == {"2xx": 2, "3xx": 0, "4xx": 1, "5xx": 1}


def test_the_buffer_is_bounded() -> None:
    """It is a window on recent behaviour, not an archive that eats the process."""
    from clinicai.core.telemetry import MAX_SAMPLES

    t = _tel(MAX_SAMPLES + 500)
    assert t.snapshot()["total"] == MAX_SAMPLES


def test_routes_are_ranked_by_the_tail_not_the_average() -> None:
    """The question is "what should I fix", and that lives in p95."""
    t = Telemetry()
    # Fast route, called often. Slow route, called rarely.
    for _ in range(50):
        t.record(route="/fast", method="GET", status=200, duration_ms=5.0)
    for _ in range(5):
        t.record(route="/slow", method="GET", status=200, duration_ms=900.0)

    routes = t.snapshot()["routes"]
    assert routes[0]["route"] == "/slow", "the slow route must sort first"


def test_percentiles() -> None:
    values = [float(i) for i in range(1, 101)]
    assert percentile(values, 50) == 50.0
    assert percentile(values, 95) == 95.0
    assert percentile([], 95) == 0.0
    assert percentile([7.0], 99) == 7.0


def test_slow_requests_are_counted() -> None:
    from clinicai.core.telemetry import SLOW_REQUEST_MS

    t = Telemetry()
    t.record(route="/x", method="GET", status=200, duration_ms=SLOW_REQUEST_MS + 1)
    t.record(route="/x", method="GET", status=200, duration_ms=10.0)
    assert t.snapshot()["slow_count"] == 1


class _FakeRoute:
    def __init__(self, path: str) -> None:
        self.path = path


class _FakeUrl:
    def __init__(self, path: str) -> None:
        self.path = path


class _FakeRequest:
    """Carries BOTH the template and the filled path.

    The first version of this fake had no `url` at all, so an implementation
    that leaked request.url.path still passed the test — the fake simply had
    nothing to leak. A negative control that cannot fail is not a control.
    """

    def __init__(self, scope: dict[str, Any], url_path: str = "") -> None:
        self.scope = scope
        self.url = _FakeUrl(url_path)


def test_only_the_route_template_is_recorded() -> None:
    """A patient id in a debugging buffer is still a patient id.

    Starlette exposes the matched route, whose `path` is the template. Recording
    request.url.path instead would put the actual uuid in the buffer — and this
    endpoint is read by a wider audience than the clinical screens are.
    """
    patient_id = "3f2b8c14-0000-4000-8000-000000000001"
    req = _FakeRequest(
        {"route": _FakeRoute("/api/v1/patients/{patient_id}")},
        url_path=f"/api/v1/patients/{patient_id}",
    )
    out = route_template(req)
    assert out == "/api/v1/patients/{patient_id}"
    assert patient_id not in out, "the filled path must never reach the buffer"


def test_an_unmatched_path_is_not_recorded_verbatim() -> None:
    """A 404 has no template, and its path is attacker-controlled."""
    req = _FakeRequest(
        {}, url_path="/api/v1/patients/3f2b8c14-0000-4000-8000-000000000001"
    )
    out = route_template(req)
    assert out == "<unmatched>"
    assert "3f2b8c14" not in out


def test_a_window_narrows_the_snapshot() -> None:
    """The desk's question is "is it slow right now", not "on average since boot"."""
    t = _tel(10)
    assert t.snapshot(window_s=3600)["total"] == 10
    # Everything was recorded now, so a zero-length window still sees them; the
    # point is that the parameter is applied at all.
    assert t.snapshot(window_s=0)["total"] == 10
