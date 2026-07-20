from datetime import date, timedelta

import pytest

from clinicai.graphs.scheduling import build_scheduling_subgraph
from clinicai.graphs.scheduling.nodes import (
    ask_date_node,
    ask_time_node,
    confirm_node,
)
from clinicai.graphs.scheduling.state import SchedulingState


@pytest.mark.asyncio
async def test_ask_date_first_turn_greeting():
    state: SchedulingState = {"user_message": "đặt lịch", "turn_count": 0}
    result = await ask_date_node(state)
    assert "khám vào ngày nào" in result["response"]
    assert result["step"] == "ask_date"
    assert result["turn_count"] == 1


@pytest.mark.asyncio
async def test_ask_date_parse_success():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    state: SchedulingState = {
        "user_message": "mai",
        "turn_count": 1,
        "step": "ask_date",
    }
    result = await ask_date_node(state)
    assert result["preferred_date"] == tomorrow
    assert result["step"] == "ask_time"


@pytest.mark.asyncio
async def test_ask_date_parse_fail_retry():
    state: SchedulingState = {
        "user_message": "blah",
        "turn_count": 1,
        "step": "ask_date",
    }
    result = await ask_date_node(state)
    assert result["step"] == "ask_date"
    assert "chưa nhận diện" in result["response"]


@pytest.mark.asyncio
async def test_ask_time_parse_success():
    state: SchedulingState = {
        "user_message": "sáng",
        "turn_count": 2,
        "step": "ask_time",
        "preferred_date": "2026-05-22",
    }
    result = await ask_time_node(state)
    assert result["preferred_time"] == "morning"
    assert result["step"] == "find_doctor"


@pytest.mark.asyncio
async def test_confirm_yes():
    state: SchedulingState = {
        "user_message": "có",
        "turn_count": 4,
        "step": "confirm",
        "preferred_date": "2026-05-22",
        "preferred_time": "morning",
    }
    result = await confirm_node(state)
    assert result["confirmed"] is True
    assert result["step"] == "done"


@pytest.mark.asyncio
async def test_confirm_no():
    state: SchedulingState = {
        "user_message": "hủy",
        "turn_count": 4,
        "step": "confirm",
        "preferred_date": "2026-05-22",
        "preferred_time": "morning",
    }
    result = await confirm_node(state)
    assert result["confirmed"] is False
    assert result["step"] == "done"


@pytest.mark.asyncio
async def test_subgraph_routes_by_step():
    """Conditional entry: step='ask_time' → ask_time_node parses 'sáng'."""
    graph = build_scheduling_subgraph()
    initial: SchedulingState = {
        "step": "ask_time",
        "user_message": "sáng",
        "turn_count": 2,
        "preferred_date": "2026-05-22",
        "response": "",
    }
    result = await graph.ainvoke(initial)
    assert result["preferred_time"] == "morning"
