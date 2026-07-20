"""Lab triage sub-graph builder.

Flow:
    receive → fetch → classify → {advise | hard_block → create_review_tasks} → END

The GROUP_C → hard_block routing is the safety gate: patient-facing
responses are suppressed and an escalation note is set for BS review.
P9.3: hard_block is followed by create_review_tasks, which enqueues
exactly one URGENT LAB_REVIEW staff task with SLA=4h.

Args:
    pool: asyncpg Pool. When None, fetch_node short-circuits with an
        error and the graph terminates early. create_review_tasks also
        no-ops without a pool (escalation_note alone carries the alert).
    llm_client: AnthropicClient. When None, classify_node safety-falls
        back to PENDING + requires_doctor_review=True and routes to
        hard_block.

Note: `location_id` previously appeared in the signature for parity with
the scheduling sub-graph (T-P9.2-01). Lab triage doesn't need location
context, so the param was dropped in T-P9.2-04.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import asyncpg
from langgraph.graph import END, StateGraph

from clinicai.graphs.lab_triage.nodes import (
    make_advise_node,
    make_classify_node,
    make_create_review_tasks_node,
    make_fetch_node,
    make_hard_block_node,
    make_receive_node,
)
from clinicai.graphs.lab_triage.state import LabTriageState, LabTriageStep

if TYPE_CHECKING:
    from clinicai.llm.anthropic_client import AnthropicClient


def _route_after_receive(state: LabTriageState) -> str:
    """Route after receive: error / step=DONE → END; else → fetch."""
    if state.step == LabTriageStep.DONE:
        return "__end__"
    return "fetch"


def _route_after_fetch(state: LabTriageState) -> str:
    """Route after fetch: error or no row → END; else → classify."""
    if state.error is not None or state.lab_result_row is None:
        return "__end__"
    return "classify"


def _route_after_classify(state: LabTriageState) -> str:
    """Route after classify: hard_block when GROUP_C, or when the classify
    node safety-falls back (requires_doctor_review=True even though the
    result isn't GROUP_C — e.g. no LLM wired, or classify exception).
    Otherwise advise.
    """
    if state.triage_group == "GROUP_C":
        return "hard_block"
    if state.requires_doctor_review:
        return "hard_block"
    return "advise"


def build_lab_triage_subgraph(
    pool: Optional[asyncpg.Pool] = None,
    llm_client: Optional["AnthropicClient"] = None,
):
    """Compile the lab_triage sub-graph with closure-injected pool + LLM."""
    sg = StateGraph(LabTriageState)

    sg.add_node("receive", make_receive_node())
    sg.add_node("fetch", make_fetch_node(pool))
    sg.add_node("classify", make_classify_node(pool, llm_client))
    sg.add_node("advise", make_advise_node(pool))
    sg.add_node("hard_block", make_hard_block_node(pool))
    sg.add_node("create_review_tasks", make_create_review_tasks_node(pool))

    sg.set_entry_point("receive")

    sg.add_conditional_edges(
        "receive",
        _route_after_receive,
        {"fetch": "fetch", "__end__": END},
    )
    sg.add_conditional_edges(
        "fetch",
        _route_after_fetch,
        {"classify": "classify", "__end__": END},
    )
    sg.add_conditional_edges(
        "classify",
        _route_after_classify,
        {"advise": "advise", "hard_block": "hard_block"},
    )
    sg.add_edge("advise", END)
    sg.add_edge("hard_block", "create_review_tasks")
    sg.add_edge("create_review_tasks", END)

    return sg.compile()
