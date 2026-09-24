"""Tools layer — thin, typed wrappers callable by agents / orchestrators.

Each toolset self-registers into the global ``REGISTRY`` when its package is
imported (see ``tools/<toolset>/__init__.py``). :func:`load_all` imports all
seven toolsets to trigger that registration.

Loading is driven lazily by ``REGISTRY`` on first read rather than eagerly at
this module's import time: a service importing ``tools._common.context`` must
not pull every toolset back into itself mid-import (the old ``brief`` toolset —
gỡ 24/09/2026 — did exactly that). The registry calls :func:`load_all` the
first time it is queried instead.
"""

from clinicai.tools.registry import REGISTRY, ToolMeta, ToolRegistry

_TOOLSETS = (
    "scheduling",
    "lab",
    "patient",
    "task",
    "event_log",
    "kb",
    "communication",
)


def load_all() -> None:
    """Import every toolset so each self-registers into ``REGISTRY``."""
    import importlib

    for name in _TOOLSETS:
        importlib.import_module(f"clinicai.tools.{name}")


__all__ = ["REGISTRY", "ToolMeta", "ToolRegistry", "load_all"]
