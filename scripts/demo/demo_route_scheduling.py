"""DEMO: full route bệnh nhân → orchestrator → scheduling → LLM thật.

Mục tiêu (cho người không rành code xem demo): chứng minh luồng SỐNG —
một câu nhắn của bệnh nhân được PHÂN LOẠI bằng Anthropic THẬT (Haiku),
định tuyến vào sub-graph đặt lịch THẬT (rule-based slot-filling), rồi sinh
một câu trả lời lễ tân bằng Anthropic THẬT (Sonnet / tier main_brain).

LƯU Ý TRUNG THỰC:
- Sub-graph scheduling là RULE-BASED, KHÔNG gọi LLM bên trong. LLM thật nằm ở
  (a) bước phân loại intent (Haiku, tier="gateway") và (b) tầng trả lời bệnh
  nhân (Sonnet, tier="main_brain"). Demo gọi LIVE cả hai.
- Bước tra cứu bác sĩ (find_doctor) cần pool DB → demo dùng MOCK pool + mock
  tool find_work_sessions (theo pattern test_find_doctor_node.py). KHÔNG đụng
  DATABASE_URL prod, KHÔNG seed DB.

CHẠY:
    python scripts/demo/demo_route_scheduling.py
(yêu cầu ANTHROPIC_API_KEY trong env hoặc .env)
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

from dotenv import load_dotenv

import clinicai.tools.scheduling.find_work_sessions as _fws_module
from clinicai.graphs.scheduling import build_scheduling_subgraph
from clinicai.graphs.scheduling.state import SchedulingState
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.orchestrator.llm_nodes import (
    make_classify_intent_llm_node,
    make_respond_node_llm,
)
from clinicai.orchestrator.state import OrchestratorState
from clinicai.tools.scheduling.find_work_sessions import (
    FindWorkSessionsOutput,
    WorkSessionResult,
)

DEMO_MESSAGE = "Em muốn đặt lịch khám thai tuần sau, sáng thứ 7 được không ạ?"


def _sep(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _fake_session(doctor_name: str = "BS Trần Thị A") -> WorkSessionResult:
    """Một ca làm việc giả lập (thay cho truy vấn DB thật)."""
    return WorkSessionResult(
        session_id=uuid4(),
        session_date=date(2026, 5, 25),
        session_type="EVENING",
        start_time="18:00",
        end_time="21:00",
        max_patients=20,
        available_doctors=[
            {"staff_id": str(uuid4()), "full_name": doctor_name, "on_call_flag": True}
        ],
    )


async def run() -> int:
    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("THIẾU ANTHROPIC_API_KEY.")
        print("Cách khắc phục:")
        print('  export ANTHROPIC_API_KEY="sk-ant-..."  (hoặc thêm vào .env)')
        print("rồi chạy lại: python scripts/demo/demo_route_scheduling.py")
        return 1

    llm = AnthropicClient()
    trace_id = uuid4()

    _sep("TIN NHẮN BỆNH NHÂN (input)")
    print(f'  "{DEMO_MESSAGE}"')

    # ---- 1. PHÂN LOẠI INTENT — Anthropic Haiku THẬT (tier=gateway) ---------- #
    _sep("[1] PHÂN LOẠI INTENT  —  LLM THẬT (Haiku, tier=gateway)")
    classify_node = make_classify_intent_llm_node(llm)
    classify_state: OrchestratorState = {
        "trace_id": trace_id,
        "user_message": DEMO_MESSAGE,
    }
    classify_out = await classify_node(classify_state)
    route = classify_out.get("route")
    print("  [LLM REQUEST] system=CLASSIFY_SYSTEM_PROMPT · message=tin nhắn trên")
    print(f"  [ROUTE LLM trả về] -> {route!r}")
    verdict = "KHỚP ✓" if route == "scheduling" else "LỆCH ✗"
    print(f"  [KỲ VỌNG] -> 'scheduling'   ==>  {verdict}")

    # ---- 2. SUB-GRAPH ĐẶT LỊCH THẬT (rule-based, mock pool/tool) ------------ #
    _sep("[2] SUB-GRAPH SCHEDULING THẬT (rule-based slot-filling)")
    # find_doctor cần pool DB → mock tool find_work_sessions (không đụng DB thật)
    _fws_module.find_work_sessions = AsyncMock(
        return_value=FindWorkSessionsOutput(sessions=[_fake_session()])
    )
    sched_graph = build_scheduling_subgraph(pool=AsyncMock(), location_id=uuid4())

    # 2a) Lượt đầu trên chính câu của bệnh nhân (vào node ask_date)
    turn1 = await sched_graph.ainvoke({"user_message": DEMO_MESSAGE, "turn_count": 0})
    print("  [LƯỢT 1 — vào node ask_date]")
    print(f"    step  -> {turn1.get('step')}")
    print(f"    đáp   -> {turn1.get('response')}")

    # 2b) Mô phỏng lượt đã đủ ngày+giờ → node find_doctor (dùng mock tool)
    seeded: SchedulingState = {
        "user_message": "tối nay nhé",
        "preferred_date": "2026-05-25",
        "preferred_time": "evening",
        "step": "find_doctor",
        "turn_count": 2,
    }
    turn2 = await sched_graph.ainvoke(seeded)
    print("\n  [LƯỢT 2 — node find_doctor, tool find_work_sessions = MOCK]")
    print(f"    step             -> {turn2.get('step')}")
    print(f"    bác sĩ đề xuất   -> {turn2.get('preferred_doctor')}")
    print(f"    số bác sĩ tìm thấy-> {len(turn2.get('candidate_doctors', []))}")
    print(f"    đáp              -> {turn2.get('response')}")
    print(f"    handled_by       -> {turn2.get('handled_by')}")

    # ---- 3. TẦNG TRẢ LỜI BỆNH NHÂN — Anthropic Sonnet THẬT (main_brain) ----- #
    _sep("[3] TRẢ LỜI BỆNH NHÂN  —  LLM THẬT (Sonnet, tier=main_brain)")
    respond_node = make_respond_node_llm(llm)
    respond_state: OrchestratorState = {
        "trace_id": trace_id,
        "user_message": DEMO_MESSAGE,
        "route": route or "scheduling",
    }
    respond_out = await respond_node(respond_state)
    print("  [LLM REQUEST] system=RESPOND_SYSTEM_PROMPT · route=scheduling")
    print("  [LLM RESPONSE THẬT]:")
    print(f"    {respond_out.get('response')}")

    _sep("KẾT THÚC DEMO")
    print("  input -> [Haiku phân loại] -> scheduling -> [sub-graph slot-filling]")
    print("        -> [Sonnet trả lời lễ tân].  Mọi bước LLM ở trên là gọi THẬT.")

    await llm.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
