"""Lab-domain tools (classify, triage — stubs until Phase 9.4)."""


def _register() -> None:
    """Self-register lab tools into the global REGISTRY."""
    from clinicai.tools.lab.classify import ClassifyResult, classify_lab_result
    from clinicai.tools.lab.query_lab_result import (
        LabResultRow,
        QueryLabResultFilter,
        query_lab_result,
    )
    from clinicai.tools.registry import REGISTRY, ToolMeta

    REGISTRY.register(
        ToolMeta(
            name="lab.classify_lab_result",
            toolset="lab",
            fn=classify_lab_result,
            input_schema=LabResultRow,  # classifies a single lab_result row
            output_schema=ClassifyResult,
            description="Phân loại 1 dòng kết quả XN (rules → LLM) để phân luồng.",
        )
    )
    REGISTRY.register(
        ToolMeta(
            name="lab.query_lab_result",
            toolset="lab",
            fn=query_lab_result,
            input_schema=QueryLabResultFilter,
            output_schema=LabResultRow,  # returns list[LabResultRow]
            description="Truy vấn kết quả xét nghiệm theo bộ lọc (read-only).",
        )
    )


_register()
