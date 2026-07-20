"""Knowledge-base tools."""


def _register() -> None:
    """Self-register knowledge-base tools into the global REGISTRY."""
    from clinicai.tools.kb.read_policy import (
        PolicyOutput,
        ReadPolicyInput,
        read_policy,
    )
    from clinicai.tools.registry import REGISTRY, ToolMeta

    REGISTRY.register(
        ToolMeta(
            name="kb.read_policy",
            toolset="kb",
            fn=read_policy,
            input_schema=ReadPolicyInput,
            output_schema=PolicyOutput,
            description="Đọc nội dung chính sách/tri thức theo khoá.",
        )
    )


_register()
