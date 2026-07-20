"""Event-log domain tools."""


def _register() -> None:
    """Self-register event-log tools into the global REGISTRY."""
    from clinicai.tools.event_log.append import (
        AppendEventInput,
        AppendEventOutput,
        append_event,
    )
    from clinicai.tools.registry import REGISTRY, ToolMeta

    REGISTRY.register(
        ToolMeta(
            name="event_log.append_event",
            toolset="event_log",
            fn=append_event,
            input_schema=AppendEventInput,
            output_schema=AppendEventOutput,
            description="Ghi một sự kiện vào nhật ký sự kiện (event log).",
        )
    )


_register()
