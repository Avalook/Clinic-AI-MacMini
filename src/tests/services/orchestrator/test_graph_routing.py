from uuid import UUID

import pytest

from clinicai.orchestrator.service import OrchestratorService


@pytest.mark.asyncio
async def test_scheduling_route() -> None:
    svc = OrchestratorService()
    r = await svc.chat(
        user_message="Tôi muốn đặt lịch hẹn ngày mai",
        clinic_id=UUID("a0000000-0000-4000-8000-000000000001"),
    )
    assert r["route"] == "scheduling"
    assert r["error"] is None


@pytest.mark.asyncio
async def test_lab_route() -> None:
    svc = OrchestratorService()
    r = await svc.chat(
        user_message="Cho tôi xem kết quả xét nghiệm",
        clinic_id=UUID("a0000000-0000-4000-8000-000000000001"),
    )
    assert r["route"] == "lab"
    assert r["error"] is None


@pytest.mark.asyncio
async def test_general_fallback_route() -> None:
    svc = OrchestratorService()
    r = await svc.chat(
        user_message="Xin chào bác sĩ",
        clinic_id=UUID("a0000000-0000-4000-8000-000000000001"),
    )
    assert r["route"] == "general"
    assert r["error"] is None
