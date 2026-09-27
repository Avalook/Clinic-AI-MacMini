"""Tests for custom exceptions and global exception handler."""

import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.core.exceptions import (
    ClinicAIBaseException,
    ExternalServiceError,
    ResourceNotFoundError,
    SafetyGateError,
    ValidationError,
)
from clinicai.main import app


# Register temporary endpoints on the app for test triggering
@app.get("/_test/base-exception")
async def trigger_base_exception() -> None:
    raise ClinicAIBaseException("Base exception message")


@app.get("/_test/not-found")
async def trigger_not_found() -> None:
    raise ResourceNotFoundError("Resource not found message")


@app.get("/_test/validation-error")
async def trigger_validation_error() -> None:
    raise ValidationError("Validation failed message")


@app.get("/_test/safety-gate-error")
async def trigger_safety_gate_error() -> None:
    raise SafetyGateError("Safety gate blocked message")


@app.get("/_test/external-service-error")
async def trigger_external_service_error() -> None:
    raise ExternalServiceError("External service failed message")


@app.get("/_test/unhandled-exception")
async def trigger_unhandled_exception() -> None:
    raise ValueError("Unhandled value error")


@pytest.mark.asyncio
async def test_base_exception_handling() -> None:
    """Test that custom ClinicAIBaseException returns custom format and HTTP 400."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/_test/base-exception")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "BAD_REQUEST"
    assert data["message"] == "Base exception message"


@pytest.mark.asyncio
async def test_resource_not_found_handling() -> None:
    """Test that ResourceNotFoundError returns custom format and HTTP 404."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/_test/not-found")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NOT_FOUND"
    assert data["message"] == "Resource not found message"


@pytest.mark.asyncio
async def test_validation_error_handling() -> None:
    """Test that ValidationError returns custom format and HTTP 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/_test/validation-error")
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert data["message"] == "Validation failed message"


@pytest.mark.asyncio
async def test_safety_gate_error_handling() -> None:
    """Test that SafetyGateError returns custom format and HTTP 403."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/_test/safety-gate-error")
    assert response.status_code == 403
    data = response.json()
    assert data["error"] == "SAFETY_GATE_ERROR"
    assert data["message"] == "Safety gate blocked message"


@pytest.mark.asyncio
async def test_external_service_error_handling() -> None:
    """Test that ExternalServiceError returns custom format and HTTP 502."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/_test/external-service-error")
    assert response.status_code == 502
    data = response.json()
    assert data["error"] == "EXTERNAL_SERVICE_ERROR"
    assert data["message"] == "External service failed message"


@pytest.mark.asyncio
async def test_unhandled_exception_handling() -> None:
    """Test that standard unhandled exceptions return HTTP 500 and do not leak
    stack traces.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/_test/unhandled-exception")
    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "INTERNAL_SERVER_ERROR"
    # Có mã lỗi để người dùng báo lại; mã khớp header và dòng log.
    rid = data["request_id"]
    assert rid and response.headers["X-Request-ID"] == rid
    assert f"mã lỗi {rid[:8]}" in data["message"]
    assert "ValueError" not in str(data)
    assert "Unhandled value error" not in str(data)


@pytest.mark.asyncio
async def test_ma_yeu_cau_tu_ngoai_chi_nhan_khi_dung_dang() -> None:
    """X-Request-ID ai gửi cũng được và đi vào mọi dòng log — rác thì thay mã mới."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        tot = await client.get("/health", headers={"X-Request-ID": "abcd1234-ef"})
        rac = await client.get(
            "/health", headers={"X-Request-ID": 'x" injected\\n{"level":"error"}'}
        )
    assert tot.headers["X-Request-ID"] == "abcd1234-ef"
    assert "injected" not in rac.headers["X-Request-ID"]
    assert len(rac.headers["X-Request-ID"]) == 36
