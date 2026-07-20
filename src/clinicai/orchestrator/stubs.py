"""Sub-graph stub nodes.

P9.x WILL MIGRATE to src/clinicai/graphs/{name}/ — each stub becomes
its own LangGraph sub-graph with real business logic.

Stubs intentionally KHÔNG gọi LLM: chỉ set handled_by marker + placeholder
response để trace flow đúng và giữ contract response non-null.
"""

from __future__ import annotations

import structlog

from clinicai.orchestrator.state import OrchestratorState

logger = structlog.get_logger(__name__)

_STUB_MESSAGE_TEMPLATE = (
    "[STUB-{name}] Tính năng đang phát triển, "
    "em sẽ chuyển yêu cầu của chị tới bộ phận phù hợp."
)


def _stub_payload(name: str) -> dict:
    return {
        "handled_by": f"{name}_stub",
        "response": _STUB_MESSAGE_TEMPLATE.format(name=name),
    }


async def scheduling_stub_node(state: OrchestratorState) -> dict:
    logger.info("stub_scheduling", trace_id=str(state.get("trace_id")))
    return _stub_payload("scheduling")


async def lab_triage_stub_node(state: OrchestratorState) -> dict:
    logger.info("stub_lab_triage", trace_id=str(state.get("trace_id")))
    return _stub_payload("lab_triage")


async def communication_stub_node(state: OrchestratorState) -> dict:
    logger.info("stub_communication", trace_id=str(state.get("trace_id")))
    return _stub_payload("communication")


async def task_manager_stub_node(state: OrchestratorState) -> dict:
    logger.info("stub_task_manager", trace_id=str(state.get("trace_id")))
    return _stub_payload("task_manager")


async def previsit_brief_stub_node(state: OrchestratorState) -> dict:
    # P9.5: real pre_visit_brief graph is callable via
    # `clinicai.graphs.pre_visit_brief.build_pre_visit_brief_subgraph()` and
    # exposed through POST /api/v1/brief/{clinic_patient_id}. The stub here
    # remains as the event-driven fallback; wiring the real graph into the
    # orchestrator router is deferred to P13 (cron trigger).
    logger.info("stub_previsit_brief", trace_id=str(state.get("trace_id")))
    return _stub_payload("previsit_brief")
