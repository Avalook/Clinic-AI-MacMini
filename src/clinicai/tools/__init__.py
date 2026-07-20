"""Tools layer — thin, typed wrappers callable by agents / orchestrators.

Each toolset self-registers into the global ``REGISTRY`` when its package is
imported (see ``tools/<toolset>/__init__.py``). :func:`load_all` imports all
eight toolsets to trigger that registration.

Loading is driven lazily by ``REGISTRY`` on first read rather than eagerly at
this module's import time: ``services.patient_context_service`` imports the
foundational ``tools._common.context``, and eager loading here would re-enter
that service mid-import (via the ``brief`` toolset) — a circular import. The
registry calls :func:`load_all` the first time it is queried instead.
"""

from clinicai.tools.registry import REGISTRY, ToolMeta, ToolRegistry

_TOOLSETS = (
    "scheduling",
    "lab",
    "patient",
    "task",
    "brief",
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
