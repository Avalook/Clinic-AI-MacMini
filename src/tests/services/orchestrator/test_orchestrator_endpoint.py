import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.api.v1.routers.orchestrator import get_orchestrator_service
from clinicai.main import app
from clinicai.orchestrator.service import OrchestratorService


@pytest.mark.asyncio
async def test_chat_endpoint_scheduling() -> None:
    # ASGITransport does not trigger lifespan → inject service via dependency override
    svc = OrchestratorService()
    app.dependency_overrides[get_orchestrator_service] = lambda: svc
    # /chat is staff-only now: it needs a tenant to pass to the graph, and
    # resolving one for real would want a database this test does not wire.
    app.dependency_overrides[get_current_identity] = lambda: StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="CSKH test",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id="a0000000-0000-4000-8000-000000000001",
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/orchestrator/chat",
                json={"user_message": "đặt lịch khám"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["route"] == "scheduling"
        assert data["error"] is None
        assert data["trace_id"] is not None
    finally:
        app.dependency_overrides.pop(get_orchestrator_service, None)
        app.dependency_overrides.pop(get_current_identity, None)
