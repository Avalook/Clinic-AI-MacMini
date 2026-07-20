"""Tests for the central tool registry (clinicai.tools.registry).

Importing ``clinicai.tools`` triggers every toolset to self-register, so the
registry is already populated by the time these tests run.
"""

from clinicai.tools import REGISTRY
from clinicai.tools.registry import ToolMeta


def test_all_tools_registered() -> None:
    """All 16 tools across 8 toolsets self-register on import.

    (render_brief_markdown is intentionally excluded — sync, returns str.)
    """
    all_tools = REGISTRY.list_all()
    assert len(all_tools) >= 16
    assert all(isinstance(m, ToolMeta) for m in all_tools)
    # Names are unique.
    names = [m.name for m in all_tools]
    assert len(names) == len(set(names))


def test_get_by_name() -> None:
    meta = REGISTRY.get("scheduling.create_appointment")
    assert meta is not None
    assert meta.toolset == "scheduling"
    assert callable(meta.fn)


def test_get_unknown_returns_none() -> None:
    assert REGISTRY.get("does_not.exist") is None


def test_list_toolset() -> None:
    # All 5 scheduling tools register (incl. find_oncall_staff, find_work_sessions).
    scheduling = REGISTRY.list_toolset("scheduling")
    assert len(scheduling) == 5
    assert all(m.toolset == "scheduling" for m in scheduling)


def test_to_anthropic_tools() -> None:
    tools = REGISTRY.to_anthropic_tools()
    assert isinstance(tools, list)
    assert len(tools) == len(REGISTRY.list_all())
    for t in tools:
        assert isinstance(t, dict)
        assert "name" in t
        assert "description" in t
        assert "input_schema" in t
        assert isinstance(t["input_schema"], dict)
