"""The CSKH upload cap must run while the ASGI body is still arriving."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send


@pytest.mark.asyncio
async def test_chunked_body_stops_before_downstream_receives_everything() -> None:
    from clinicai.api.middleware import CskhUploadSizeLimitMiddleware

    messages: Iterator[Message] = iter(
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"5678", "more_body": True},
            {"type": "http.request", "body": b"9", "more_body": False},
        ]
    )
    downstream_completed = False
    sent: list[Message] = []

    async def receive() -> Message:
        return next(messages)

    async def send(message: Message) -> None:
        sent.append(message)

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal downstream_completed
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if not message.get("more_body", False):
                break
        downstream_completed = True

    middleware = CskhUploadSizeLimitMiddleware(downstream, max_body_bytes=5)
    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/cskh/ket-qua/tep",
        "headers": [],
    }
    await middleware(scope, receive, send)

    assert downstream_completed is False
    assert next(m for m in sent if m["type"] == "http.response.start")["status"] == 413


@pytest.mark.asyncio
async def test_declared_oversize_is_rejected_without_reading_body() -> None:
    from clinicai.api.middleware import CskhUploadSizeLimitMiddleware

    receive_called = False
    sent: list[Message] = []

    async def receive() -> Message:
        nonlocal receive_called
        receive_called = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        raise AssertionError("oversized body reached downstream")

    middleware = CskhUploadSizeLimitMiddleware(downstream, max_body_bytes=5)
    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/cskh/ket-qua/tep",
        "headers": [(b"content-length", b"6")],
    }
    await middleware(scope, receive, send)

    assert receive_called is False
    assert next(m for m in sent if m["type"] == "http.response.start")["status"] == 413


def test_real_multipart_is_rejected_before_route_handler() -> None:
    """Exercise Starlette's multipart parser, not only a fake receive loop."""
    from clinicai.api.middleware import CskhUploadSizeLimitMiddleware

    app = FastAPI()
    handler_called = False

    @app.middleware("http")
    async def base_http_layer(request: Any, call_next: Any) -> Any:
        return await call_next(request)

    @app.post("/api/v1/cskh/ket-qua/tep")
    async def upload(file: UploadFile = File(...)) -> dict[str, bool]:
        nonlocal handler_called
        handler_called = True
        return {"ok": True}

    app.add_middleware(CskhUploadSizeLimitMiddleware, max_body_bytes=1024)
    response = TestClient(app).post(
        "/api/v1/cskh/ket-qua/tep",
        files={"file": ("large.pdf", b"x" * 2048, "application/pdf")},
    )

    assert response.status_code == 413
    assert handler_called is False


def test_chunked_multipart_is_rejected_before_route_handler() -> None:
    """No Content-Length must not bypass the receive-stream counter."""
    from clinicai.api.middleware import CskhUploadSizeLimitMiddleware

    app = FastAPI()
    handler_called = False

    @app.middleware("http")
    async def base_http_layer(request: Any, call_next: Any) -> Any:
        return await call_next(request)

    @app.post("/api/v1/cskh/ket-qua/tep")
    async def upload(file: UploadFile = File(...)) -> dict[str, bool]:
        nonlocal handler_called
        handler_called = True
        return {"ok": True}

    app.add_middleware(CskhUploadSizeLimitMiddleware, max_body_bytes=1024)
    boundary = "clinicai-test-boundary"

    def body_chunks() -> Any:
        yield (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="large.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        yield b"x" * 800
        yield b"x" * 800
        yield f"\r\n--{boundary}--\r\n".encode()

    response = TestClient(app).post(
        "/api/v1/cskh/ket-qua/tep",
        content=body_chunks(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    assert response.status_code == 413
    assert handler_called is False
