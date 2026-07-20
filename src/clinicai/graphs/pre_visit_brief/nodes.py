"""Nodes for pre_visit_brief sub-graph (P9.5).

Closure-factory pattern matching scheduling / lab_triage / task_manager.
Three nodes only: aggregate context → call Sonnet → render markdown.
Errors short-circuit downstream nodes via state.error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from clinicai.graphs.pre_visit_brief.state import PreVisitBriefState
from clinicai.services.patient_context_service import (
    PatientNotFoundError,
    aggregate_patient_context,
)
from clinicai.tools._common.context import new_trace
from clinicai.tools.brief.generate_brief import generate_brief
from clinicai.tools.brief.render_markdown import render_brief_markdown

if TYPE_CHECKING:
    import asyncpg

    from clinicai.llm.anthropic_client import AnthropicClient

logger = structlog.get_logger(__name__)


def make_aggregate_context_node(pool: "asyncpg.Pool"):
    """Build the node that loads aggregated patient context.

    On PatientNotFoundError → sets state.error (downstream nodes skip).
    Other exceptions propagate so the graph terminates with a 5xx.
    """

    async def aggregate_context_node(state: PreVisitBriefState) -> dict[str, Any]:
        trace = new_trace()
        try:
            ctx = await aggregate_patient_context(pool, state.clinic_patient_id, trace)
        except PatientNotFoundError as exc:
            logger.warning(
                "pre_visit_brief.aggregate.patient_not_found",
                clinic_patient_id=str(state.clinic_patient_id),
                error=str(exc),
            )
            return {"error": f"patient_not_found:{state.clinic_patient_id}"}

        logger.info(
            "pre_visit_brief.aggregate.ok",
            clinic_patient_id=str(state.clinic_patient_id),
            total_visits=ctx.total_visits,
            lab_count=len(ctx.latest_lab_results),
            ultrasound_count=len(ctx.latest_ultrasound_summary),
        )
        return {"patient_context": ctx}

    return aggregate_context_node


def make_generate_brief_node(llm_client: "AnthropicClient"):
    """Build the node that calls Sonnet to produce the structured brief.

    Skips when state.error is set or context is missing. LLM parse errors
    surface via state.error to keep the API response actionable.
    """

    async def generate_brief_node(state: PreVisitBriefState) -> dict[str, Any]:
        if state.error or state.patient_context is None:
            return {}

        trace = new_trace()
        try:
            brief = await generate_brief(state.patient_context, llm_client, trace)
        except ValueError as exc:
            logger.error(
                "pre_visit_brief.generate.parse_failed",
                clinic_patient_id=str(state.clinic_patient_id),
                error=str(exc),
            )
            return {"error": f"brief_generation_failed:{exc}"}
        except Exception as exc:
            # Anthropic transport / retry exhaustion etc.
            logger.error(
                "pre_visit_brief.generate.llm_failed",
                clinic_patient_id=str(state.clinic_patient_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return {"error": f"llm_failed:{type(exc).__name__}"}

        return {"brief": brief}

    return generate_brief_node


def make_render_markdown_node():
    """Build the node that renders the brief as Markdown. Pure function."""

    async def render_markdown_node(state: PreVisitBriefState) -> dict[str, Any]:
        if state.brief is None:
            return {}
        return {"brief_markdown": render_brief_markdown(state.brief)}

    return render_markdown_node
