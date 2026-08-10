"""The middleware stack is pinned, because reading main.py cannot tell you it.

Starlette's ``add_middleware`` does ``user_middleware.insert(0, …)``: the LAST
call ends up OUTERMOST. main.py used to register them in the order the comment
described and therefore built the exact reverse of it —

    DbError → api_key → Timing → RequestId → routes

instead of

    RequestId → Timing → api_key → DbError → routes

which cost two things the comments promised. Timing sat *inside* the API-key
gate, so the rejected-request flood it exists to surface was the one thing it
could never record; and RequestId sat innermost, so no 401/403/503 carried an
``X-Request-ID`` and no auth log line had ``request_id`` bound.

Nothing about that is visible in a diff, in mypy, or in any behavioural test —
the app serves traffic perfectly with the stack inside out. So it gets asserted
directly.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def app_middleware_names() -> list[str]:
    os.environ.setdefault("APP_ENV", "test")
    from clinicai.main import app

    names: list[str] = []
    for mw in app.user_middleware:
        dispatch = (mw.kwargs or {}).get("dispatch")
        # Starlette khai `kwargs` là dict[str, Any] và `cls` là
        # _MiddlewareFactory, nên mypy không thấy `__name__` ở cả hai nhánh.
        # Đây là bài kiểm THỨ TỰ middleware — tên chỉ để đọc, nên lấy bằng
        # getattr với giá trị dự phòng thay vì ép kiểu một thứ Starlette không
        # hứa.
        target = dispatch if dispatch else mw.cls
        names.append(str(getattr(target, "__name__", target)))
    return names


def test_stack_is_outermost_first(app_middleware_names: list[str]) -> None:
    """user_middleware[0] is outermost; this is the order requests see."""
    assert app_middleware_names == [
        "RequestIdMiddleware",
        "TimingMiddleware",
        "CskhUploadSizeLimitMiddleware",
        "api_key_middleware",
        "DbErrorMiddleware",
    ]


def test_timing_is_outside_the_api_key_gate(
    app_middleware_names: list[str],
) -> None:
    """A rejected request still costs the server time, and still gets recorded."""
    assert app_middleware_names.index("TimingMiddleware") < app_middleware_names.index(
        "api_key_middleware"
    )


def test_request_id_wraps_everything(app_middleware_names: list[str]) -> None:
    """Including the 401s and 503s — those are the responses people report."""
    assert app_middleware_names[0] == "RequestIdMiddleware"


def test_db_error_is_inside_timing(app_middleware_names: list[str]) -> None:
    """So the buffer records the 503 the client got, not the 500 default.

    DbErrorMiddleware turns a dead connection into a *response*. Outside Timing,
    the exception would still be in flight when Timing's ``finally`` ran, and
    the ops screen would show 500 for something the client received as 503.
    """
    assert app_middleware_names.index("DbErrorMiddleware") > app_middleware_names.index(
        "TimingMiddleware"
    )


def test_telemetry_reads_the_generated_request_id() -> None:
    """The id is generated, so it cannot come back out of ``request.headers``.

    TimingMiddleware used to read ``request.headers.get("X-Request-ID")``, which
    is only ever set when an upstream proxy sends one. Behind Caddy nothing
    does, so every entry in the ops error feed carried request_id=None while the
    screen printed "dùng mã này để tra trong log" beside it.
    """
    from clinicai.api.middleware import current_request_id, request_id_ctx

    token = request_id_ctx.set("abc-123")
    try:
        assert current_request_id() == "abc-123"
    finally:
        request_id_ctx.reset(token)

    assert current_request_id() is None
