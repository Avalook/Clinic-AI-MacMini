"""Communication channel tools (Zalo, Pancake, SMS — stubs until Phase 12)."""


def _register() -> None:
    """Self-register communication tools into the global REGISTRY."""
    from clinicai.tools.communication.send_zalo import (
        SendZaloInput,
        SendZaloOutput,
        send_zalo_message,
    )
    from clinicai.tools.registry import REGISTRY, ToolMeta

    REGISTRY.register(
        ToolMeta(
            name="communication.send_zalo_message",
            toolset="communication",
            fn=send_zalo_message,
            input_schema=SendZaloInput,
            output_schema=SendZaloOutput,
            description="[STUB] Gửi tin nhắn Zalo (chưa triển khai — Phase 12).",
        )
    )


_register()
