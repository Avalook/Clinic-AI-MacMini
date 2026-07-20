"""State for pre_visit_brief sub-graph (P9.5)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from clinicai.services.patient_context_service import PatientContext
from clinicai.tools.brief.generate_brief import PreVisitBrief


class PreVisitBriefState(BaseModel):
    """State passed through pre_visit_brief sub-graph nodes.

    `error` short-circuits subsequent nodes — set by aggregate_context_node
    when the patient is missing, or by generate_brief_node when the LLM
    response cannot be parsed.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input
    clinic_patient_id: UUID
    trace_id: Optional[UUID] = None

    # Intermediate
    patient_context: Optional[PatientContext] = None

    # Output
    brief: Optional[PreVisitBrief] = None
    brief_markdown: Optional[str] = None

    # Flow control
    error: Optional[str] = None
