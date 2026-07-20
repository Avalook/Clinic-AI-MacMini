"""Pre-visit brief sub-graph builder (P9.5).

Flow:
    START
      → aggregate_context
      → generate_brief    (skipped if aggregate set state.error)
      → render_markdown   (skipped if generate failed)
      → END

The skip-on-error pattern is intentional: API caller inspects state.error
to map 404 (patient_not_found) vs 500 (LLM failure) rather than the graph
raising mid-flight.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from clinicai.graphs.pre_visit_brief.nodes import (
    make_aggregate_context_node,
    make_generate_brief_node,
    make_render_markdown_node,
)
from clinicai.graphs.pre_visit_brief.state import PreVisitBriefState

if TYPE_CHECKING:
    import asyncpg

    from clinicai.llm.anthropic_client import AnthropicClient


def build_pre_visit_brief_subgraph(
    pool: "asyncpg.Pool",
    llm_client: "AnthropicClient",
) -> Any:
    """Compile the pre_visit_brief sub-graph with closure-injected pool + LLM."""
    sg = StateGraph(PreVisitBriefState)

    sg.add_node("aggregate_context", make_aggregate_context_node(pool))
    sg.add_node("generate_brief", make_generate_brief_node(llm_client))
    sg.add_node("render_markdown", make_render_markdown_node())

    sg.add_edge(START, "aggregate_context")
    sg.add_edge("aggregate_context", "generate_brief")
    sg.add_edge("generate_brief", "render_markdown")
    sg.add_edge("render_markdown", END)

    return sg.compile()
