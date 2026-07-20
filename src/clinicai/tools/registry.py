"""Central tool registry.

Every toolset self-registers into the global ``REGISTRY`` at import time
(see each ``tools/<toolset>/__init__.py``). Import :mod:`clinicai.tools`
(or any single toolset) to populate it, then introspect via the registry
methods or hand the Anthropic-shaped list to the Claude API.

Pattern borrowed from Hermes' ``tools/registry.py`` (self-register on import).

Note on schema typing: most tools follow the ``Input``/``Output`` Pydantic
pattern, but a few do not (e.g. ``task.check_task_sla`` takes a raw ``UUID``
and has no input model). ``input_schema`` is therefore ``type[BaseModel] |
None``; ``to_anthropic_tools`` emits an empty object schema for such tools.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolMeta:
    """Metadata describing one callable tool.

    Attributes:
        name: Fully-qualified id, e.g. ``"scheduling.create_appointment"``.
        toolset: Toolset slug, e.g. ``"scheduling"``.
        fn: The (async) tool function. Service/pool/trace args are injected
            by the caller; the registry only stores the callable.
        input_schema: Pydantic input model, or ``None`` for tools that take
            primitive args instead of a single input model.
        output_schema: Pydantic output model. For tools returning a list,
            this is the element model.
        description: One-line summary used in Claude tool-use definitions.
    """

    name: str
    toolset: str
    fn: Callable[..., Any]
    input_schema: type[BaseModel] | None
    output_schema: type[BaseModel]
    description: str


class ToolRegistry:
    """In-memory registry of :class:`ToolMeta`, keyed by fully-qualified name.

    Toolsets are loaded *lazily* on first read (``get``/``list_*``/
    ``to_anthropic_tools``) rather than at ``clinicai.tools`` import time.
    This avoids an import cycle: ``services.patient_context_service`` imports
    ``tools._common.context``, which would otherwise pull every toolset
    (incl. ``brief`` → back into that half-imported service) the moment any
    ``clinicai.tools.*`` submodule is touched. Lazy loading defers toolset
    imports until the service graph has settled.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolMeta] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Import every toolset once so each self-registers (idempotent)."""
        if self._loaded:
            return
        # Set the flag first: registration happens during load_all() and must
        # not re-enter this method.
        self._loaded = True
        from clinicai.tools import load_all

        load_all()

    def register(self, meta: ToolMeta) -> None:
        """Register a tool. Raises on duplicate name (catches double-register)."""
        if meta.name in self._tools:
            raise ValueError(f"Tool already registered: {meta.name}")
        self._tools[meta.name] = meta

    def get(self, name: str) -> ToolMeta | None:
        """Return the tool with this name, or ``None`` if not registered."""
        self._ensure_loaded()
        return self._tools.get(name)

    def list_toolset(self, toolset: str) -> list[ToolMeta]:
        """Return all registered tools belonging to ``toolset``."""
        self._ensure_loaded()
        return [m for m in self._tools.values() if m.toolset == toolset]

    def list_all(self) -> list[ToolMeta]:
        """Return every registered tool."""
        self._ensure_loaded()
        return list(self._tools.values())

    def to_anthropic_tools(self) -> list[dict[str, Any]]:
        """Render the registry as Claude API ``tools`` definitions.

        Each entry has ``name``, ``description`` and ``input_schema``
        (a JSON Schema object). Tools without an input model get an empty
        object schema.
        """
        self._ensure_loaded()
        tools: list[dict[str, Any]] = []
        for meta in self._tools.values():
            if meta.input_schema is None:
                input_schema: dict[str, Any] = {"type": "object", "properties": {}}
            else:
                input_schema = meta.input_schema.model_json_schema()
            tools.append(
                {
                    "name": meta.name,
                    "description": meta.description,
                    "input_schema": input_schema,
                }
            )
        return tools


# Global singleton. Toolsets register into this at import time.
REGISTRY = ToolRegistry()
