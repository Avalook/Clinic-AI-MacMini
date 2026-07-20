from typing import Optional
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from clinicai.graphs.lab_triage import build_lab_triage_subgraph
from clinicai.graphs.lab_triage.state import LabTriageState
from clinicai.graphs.pre_visit_brief import (
    PreVisitBriefState,
    build_pre_visit_brief_subgraph,
)
from clinicai.graphs.scheduling import build_scheduling_subgraph
from clinicai.graphs.task_manager import (
    TaskManagerState,
    build_task_manager_subgraph,
)
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.orchestrator.llm_nodes import (
    make_classify_intent_llm_node,
    make_respond_node_llm,
)
from clinicai.orchestrator.nodes import classify_intent_node, respond_node
from clinicai.orchestrator.state import OrchestratorState
from clinicai.orchestrator.stubs import (
    communication_stub_node,
    lab_triage_stub_node,
    previsit_brief_stub_node,
    scheduling_stub_node,
    task_manager_stub_node,
)

_VALID_ROUTES: set[str] = {
    "scheduling",
    "lab",
    "communication",
    "task",
    "previsit",
    "general",
}

_LAB_TRIAGE_HANDLED_BY = "lab_triage_subgraph"
_TASK_MANAGER_HANDLED_BY = "task_manager_subgraph"
_PREVISIT_BRIEF_HANDLED_BY = "previsit_brief_subgraph"

_PREVISIT_ACK_NO_PATIENT = (
    "Em đã ghi nhận yêu cầu xem tóm tắt trước khám. "
    "Vui lòng cung cấp mã bệnh nhân để em tổng hợp giúp ạ."
)
_PREVISIT_ACK_ERROR = (
    "Em chưa tổng hợp được tóm tắt trước khám lúc này. "
    "Bộ phận chăm sóc khách hàng sẽ hỗ trợ chị sớm."
)

_TASK_MANAGER_ACK_DEFAULT = (
    "Em đã ghi nhận yêu cầu liên quan tới công việc. "
    "Bộ phận điều phối sẽ kiểm tra và phản hồi sớm."
)
_TASK_MANAGER_ACK_OVERDUE = (
    "Em đã kiểm tra: hiện có {count} công việc đang quá hạn cần xử lý."
)

_LAB_TRIAGE_ACK_NO_ID = (
    "Em đã ghi nhận yêu cầu về kết quả xét nghiệm. "
    "Vui lòng cung cấp mã kết quả để em tra cứu giúp ạ."
)
_LAB_TRIAGE_ACK_SAFE = (
    "Kết quả xét nghiệm đã được phân loại. Bộ phận chăm sóc khách hàng sẽ liên hệ sớm."
)
_LAB_TRIAGE_ACK_BLOCKED = (
    "Kết quả xét nghiệm cần bác sĩ xem xét. "
    "Bác sĩ sẽ liên hệ chị trong thời gian sớm nhất."
)


def route_by_intent(state: OrchestratorState) -> str:
    """Map classify route → conditional edge target. Fallback 'general'."""
    route = state.get("route", "general")
    if route in _VALID_ROUTES:
        return route
    return "general"


def _make_lab_triage_wrapper_node(
    pool: Optional[object],
    llm_client: Optional[AnthropicClient],
):
    """Wrap the lab_triage sub-graph behind an orchestrator-state interface.

    The sub-graph uses a Pydantic BaseModel state; the orchestrator uses a
    TypedDict. Instead of forcing the two to share a schema, this wrapper
    translates: extract `lab_result_id` / `patient_id` from parent state,
    invoke the compiled sub-graph, and serialise the result back into
    orchestrator-state keys (response + handled_by + triage flags).
    """
    sub_graph = build_lab_triage_subgraph(pool=pool, llm_client=llm_client)

    async def lab_triage_wrapper(state: OrchestratorState) -> dict:
        lab_result_id = state.get("lab_result_id")
        if not lab_result_id:
            # No specific lab result attached → orchestrator can only ack.
            return {
                "handled_by": _LAB_TRIAGE_HANDLED_BY,
                "response": _LAB_TRIAGE_ACK_NO_ID,
            }

        sub_state = LabTriageState(
            lab_result_id=lab_result_id,
            clinic_patient_id=state.get("patient_id"),
        )
        result_dict = await sub_graph.ainvoke(sub_state)

        triage_group = result_dict.get("triage_group")
        escalation_note = result_dict.get("escalation_note")
        response_to_patient = result_dict.get("response_to_patient")

        # Pick a top-level response string for the orchestrator surface.
        if response_to_patient:
            response = response_to_patient
        elif escalation_note:
            response = _LAB_TRIAGE_ACK_BLOCKED
        else:
            # Fall back to a generic ack when neither field is populated
            # (e.g. fetch error before classify ran).
            response = _LAB_TRIAGE_ACK_SAFE

        return {
            "handled_by": _LAB_TRIAGE_HANDLED_BY,
            "response": response,
            "triage_group": triage_group,
            "requires_doctor_review": bool(
                result_dict.get("requires_doctor_review", False)
            ),
            "escalation_note": escalation_note,
        }

    return lab_triage_wrapper


def _make_task_manager_wrapper_node(pool: object):
    """Wrap the task_manager sub-graph behind the orchestrator state surface.

    Conservative default: today's orchestrator routing only signals "this
    intent is about tasks" — it doesn't yet carry structured CreateTask /
    UpdateTask payloads. The wrapper therefore runs a read-only flow
    (empty filter → no tasks → empty SLA list) and returns a generic ack.
    Future routing can attach `task_input`/`update_input` to the parent
    state and have this wrapper forward them.
    """
    sub_graph = build_task_manager_subgraph(pool=pool)

    async def task_manager_wrapper(state: OrchestratorState) -> dict:
        sub_state = TaskManagerState()
        result_dict = await sub_graph.ainvoke(sub_state)

        sla_results = result_dict.get("sla_results", []) or []
        overdue = sum(1 for r in sla_results if getattr(r, "is_overdue", False))
        if overdue:
            response = _TASK_MANAGER_ACK_OVERDUE.format(count=overdue)
        else:
            response = _TASK_MANAGER_ACK_DEFAULT

        return {
            "handled_by": _TASK_MANAGER_HANDLED_BY,
            "response": response,
        }

    return task_manager_wrapper


def _make_previsit_brief_wrapper_node(
    pool: object,
    llm_client: AnthropicClient,
):
    """Wrap the pre_visit_brief sub-graph behind the orchestrator state surface.

    The sub-graph is pull/event-driven: it needs a concrete patient. The
    orchestrator only carries `patient_id` (Optional) — when absent the wrapper
    can only acknowledge. When present it maps patient_id → clinic_patient_id,
    runs the real sub-graph, and surfaces the brief headline into `response`
    (the BS-facing markdown stays inside the sub-graph; we don't add new
    orchestrator-state fields).
    """
    sub_graph = build_pre_visit_brief_subgraph(pool=pool, llm_client=llm_client)

    async def previsit_brief_wrapper(state: OrchestratorState) -> dict:
        patient_id = state.get("patient_id")
        if not patient_id:
            return {
                "handled_by": _PREVISIT_BRIEF_HANDLED_BY,
                "response": _PREVISIT_ACK_NO_PATIENT,
            }

        sub_state = PreVisitBriefState(
            clinic_patient_id=patient_id,
            trace_id=state.get("trace_id"),
        )
        result_dict = await sub_graph.ainvoke(sub_state)

        brief = result_dict.get("brief")
        if result_dict.get("error") or brief is None:
            return {
                "handled_by": _PREVISIT_BRIEF_HANDLED_BY,
                "response": _PREVISIT_ACK_ERROR,
            }

        return {
            "handled_by": _PREVISIT_BRIEF_HANDLED_BY,
            "response": brief.headline,
        }

    return previsit_brief_wrapper


def build_orchestrator_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    llm_client: Optional[AnthropicClient] = None,
    use_llm_respond: bool = True,
    scheduling_pool: Optional[object] = None,
    scheduling_location_id: Optional[UUID] = None,
    lab_triage_pool: Optional[object] = None,
    task_manager_pool: Optional[object] = None,
    previsit_pool: Optional[object] = None,
):
    """Factory.

    - checkpointer=None → MemorySaver
    - llm_client=None   → rule-based classify + template respond (offline)
    - llm_client given  → Haiku classify; respond uses Sonnet if use_llm_respond,
                          else template respond_node.
    - scheduling_pool + scheduling_location_id given → wire the real scheduling
      sub-graph. Otherwise fall back to the stub node.
    - lab_triage_pool given → wire the real lab_triage sub-graph (uses
      `llm_client` when supplied; otherwise classify safety-falls back to
      hard_block). Without a pool the legacy stub keeps test coverage.
    - previsit_pool + llm_client given → wire the real pre_visit_brief sub-graph
      (needs both a pool and an LLM). Otherwise fall back to the stub node.

    Conditional edges: classify → 5 sub-graphs/stubs OR respond (general).
    Each branch → END directly (no loop back to respond).
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    classify_node = (
        classify_intent_node
        if llm_client is None
        else make_classify_intent_llm_node(llm_client)
    )

    respond = (
        make_respond_node_llm(llm_client)
        if (llm_client is not None and use_llm_respond)
        else respond_node
    )

    if scheduling_pool is not None and scheduling_location_id is not None:
        scheduling_node = build_scheduling_subgraph(
            pool=scheduling_pool,
            location_id=scheduling_location_id,
        )
    else:
        scheduling_node = scheduling_stub_node

    if lab_triage_pool is not None:
        lab_triage_node = _make_lab_triage_wrapper_node(
            pool=lab_triage_pool,
            llm_client=llm_client,
        )
    else:
        lab_triage_node = lab_triage_stub_node

    if task_manager_pool is not None:
        task_manager_node = _make_task_manager_wrapper_node(
            pool=task_manager_pool,
        )
    else:
        task_manager_node = task_manager_stub_node

    if previsit_pool is not None and llm_client is not None:
        previsit_brief_node = _make_previsit_brief_wrapper_node(
            pool=previsit_pool,
            llm_client=llm_client,
        )
    else:
        previsit_brief_node = previsit_brief_stub_node

    graph = StateGraph(OrchestratorState)
    graph.add_node("classify_intent", classify_node)
    graph.add_node("respond", respond)
    graph.add_node("scheduling_stub", scheduling_node)
    graph.add_node("lab_triage_stub", lab_triage_node)
    graph.add_node("communication_stub", communication_stub_node)
    graph.add_node("task_manager_stub", task_manager_node)
    graph.add_node("previsit_brief_stub", previsit_brief_node)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "scheduling": "scheduling_stub",
            "lab": "lab_triage_stub",
            "communication": "communication_stub",
            "task": "task_manager_stub",
            "previsit": "previsit_brief_stub",
            "general": "respond",
        },
    )

    graph.add_edge("scheduling_stub", END)
    graph.add_edge("lab_triage_stub", END)
    graph.add_edge("communication_stub", END)
    graph.add_edge("task_manager_stub", END)
    graph.add_edge("previsit_brief_stub", END)
    graph.add_edge("respond", END)

    return graph.compile(checkpointer=checkpointer)
