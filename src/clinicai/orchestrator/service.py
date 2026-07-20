from typing import Optional
from uuid import UUID, uuid4

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver

from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.orchestrator.graph import build_orchestrator_graph
from clinicai.orchestrator.state import OrchestratorState

logger = structlog.get_logger(__name__)


class OrchestratorService:
    def __init__(
        self,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        llm_client: Optional[AnthropicClient] = None,
        use_llm_respond: bool = True,
        scheduling_pool: Optional[object] = None,
        scheduling_location_id: Optional[UUID] = None,
        lab_triage_pool: Optional[object] = None,
        task_manager_pool: Optional[object] = None,
    ):
        self._graph = build_orchestrator_graph(
            checkpointer,
            llm_client,
            use_llm_respond,
            scheduling_pool=scheduling_pool,
            scheduling_location_id=scheduling_location_id,
            lab_triage_pool=lab_triage_pool,
            task_manager_pool=task_manager_pool,
        )

    async def chat(
        self,
        user_message: str,
        patient_id: Optional[UUID] = None,
        trace_id: Optional[UUID] = None,
        thread_id: Optional[str] = None,
    ) -> dict:
        if trace_id is None:
            trace_id = uuid4()
        if thread_id is None:
            thread_id = str(trace_id)
        initial_state: OrchestratorState = {
            "trace_id": trace_id,
            "user_message": user_message,
            "patient_id": patient_id,
        }
        config = {"configurable": {"thread_id": thread_id}}
        try:
            final_state = await self._graph.ainvoke(initial_state, config=config)
            return {
                "trace_id": trace_id,
                "route": final_state.get("route"),
                "response": final_state.get("response"),
                "error": None,
            }
        except Exception as e:
            logger.error("orchestrator_failed", trace_id=str(trace_id), error=str(e))
            return {
                "trace_id": trace_id,
                "route": None,
                "response": None,
                "error": str(e),
            }
