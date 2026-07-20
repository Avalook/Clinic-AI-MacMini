import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.api.v1.routers.orchestrator import get_orchestrator_service
from clinicai.main import app
from clinicai.orchestrator.service import OrchestratorService


@pytest.mark.asyncio
async def test_chat_endpoint_scheduling():
    # ASGITransport does not trigger lifespan → inject service via dependency override
    svc = OrchestratorService()
    app.dependency_overrides[get_orchestrator_service] = lambda: svc
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
