"""Patient-domain tools."""


def _register() -> None:
    """Self-register patient tools into the global REGISTRY."""
    from clinicai.tools.patient.get_summary import (
        GetPatientSummaryInput,
        PatientSummaryOutput,
        get_patient_summary,
    )
    from clinicai.tools.registry import REGISTRY, ToolMeta

    REGISTRY.register(
        ToolMeta(
            name="patient.get_patient_summary",
            toolset="patient",
            fn=get_patient_summary,
            input_schema=GetPatientSummaryInput,
            output_schema=PatientSummaryOutput,
            description="Lấy tóm tắt hành chính + lâm sàng của một bệnh nhân.",
        )
    )


_register()
