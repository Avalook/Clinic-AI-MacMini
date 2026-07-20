"""Pre-visit brief tools (P9.5)."""

from clinicai.tools.brief.generate_brief import PreVisitBrief, generate_brief
from clinicai.tools.brief.render_markdown import render_brief_markdown

__all__ = ["PreVisitBrief", "generate_brief", "render_brief_markdown"]


def _register() -> None:
    """Self-register brief tools into the global REGISTRY.

    Only ``generate_brief`` is registered. ``render_brief_markdown`` is a
    synchronous formatter returning ``str`` — not an LLM-callable tool, so
    it is intentionally excluded.
    """
    from clinicai.services.patient_context_service import PatientContext
    from clinicai.tools.registry import REGISTRY, ToolMeta

    REGISTRY.register(
        ToolMeta(
            name="brief.generate_brief",
            toolset="brief",
            fn=generate_brief,
            input_schema=PatientContext,
            output_schema=PreVisitBrief,
            description="Sinh bản tóm tắt tiền khám (pre-visit brief) từ ngữ cảnh BN.",
        )
    )


_register()
