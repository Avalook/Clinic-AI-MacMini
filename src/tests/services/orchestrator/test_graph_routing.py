import pytest

from clinicai.orchestrator.service import OrchestratorService


@pytest.mark.asyncio
async def test_scheduling_route():
    svc = OrchestratorService()
    r = await svc.chat(user_message="Tôi muốn đặt lịch hẹn ngày mai")
    assert r["route"] == "scheduling"
    assert r["error"] is None


@pytest.mark.asyncio
async def test_lab_route():
    svc = OrchestratorService()
    r = await svc.chat(user_message="Cho tôi xem kết quả xét nghiệm")
    assert r["route"] == "lab"
    assert r["error"] is None


@pytest.mark.asyncio
async def test_general_fallback_route():
    svc = OrchestratorService()
    r = await svc.chat(user_message="Xin chào bác sĩ")
    assert r["route"] == "general"
    assert r["error"] is None
