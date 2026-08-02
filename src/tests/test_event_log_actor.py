"""Every event_log writer must name the actor.

The column added in 20260802000003 only answers "ai đã làm việc này" if all
writers bind it. A tenth writer landing without `actor_staff_id` would not fail
anything at runtime — the INSERT succeeds, the row is simply anonymous — which
is exactly how the JSONB `clinic_staff_id` convention it replaced ended up 8/9
complete without anyone noticing.
"""

from __future__ import annotations

import ast
import os
import pathlib
import re

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SOURCE = _REPO / "src" / "clinicai"
_DASHBOARD = _REPO / "src" / "dashboard"
_DASHBOARD_SKIP = {"node_modules", ".next", "test-results", "playwright-report"}

# Below this, the walk found nothing rather than everything: a moved package or
# a typo'd glob would otherwise turn this gate into a test that always passes.
_MIN_WRITERS = 9

# supabase-js writes are a single chain: .from("event_log").insert({...}).
_TS_WRITE = re.compile(r"""\.from\(\s*["']event_log["']\s*\)\s*\.insert\(""")


def _event_log_inserts() -> list[tuple[pathlib.Path, str]]:
    """Return (file, sql) for every literal INSERT INTO event_log in the API."""
    found: list[tuple[pathlib.Path, str]] = []
    for path in sorted(_SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and "INSERT INTO event_log" in node.value
            ):
                found.append((path, node.value))
    return found


def _dashboard_sources() -> list[pathlib.Path]:
    """Dashboard TypeScript, minus everything npm and next put there."""
    files: list[pathlib.Path] = []
    for root, dirs, names in os.walk(_DASHBOARD):
        dirs[:] = [d for d in dirs if d not in _DASHBOARD_SKIP]
        files.extend(
            pathlib.Path(root) / name
            for name in names
            if name.endswith((".ts", ".tsx", ".mts"))
        )
    return sorted(files)


def test_every_event_log_writer_binds_an_actor() -> None:
    writers = _event_log_inserts()
    assert len(writers) >= _MIN_WRITERS, f"only found {len(writers)} event_log writers"

    missing = [
        str(path.relative_to(_REPO))
        for path, sql in writers
        if "actor_staff_id" not in sql
    ]
    assert not missing, f"event_log INSERT without actor_staff_id: {missing}"


def test_dashboard_does_not_write_event_log() -> None:
    """The UI tier has no writer to keep honest — it must stay that way.

    `lib/event-log.ts` used to insert straight into event_log with a service-role
    client. It had no callers left, and reviving that path would produce rows
    with no actor and no derived tenant (ADR-0009, ADR-0012). Writes belong in
    FastAPI, where the actor comes from the verified JWT.
    """
    sources = _dashboard_sources()
    assert len(sources) > 50, f"only walked {len(sources)} dashboard files"

    writers = [
        str(path.relative_to(_REPO))
        for path in sources
        if _TS_WRITE.search(path.read_text())
    ]
    assert not writers, f"dashboard writes event_log directly: {writers}"


def test_actor_is_not_also_written_into_metadata() -> None:
    """One column or one JSONB key — two of them means two truths to reconcile."""
    duplicates = [
        str(path.relative_to(_REPO))
        for path in sorted(_SOURCE.rglob("*.py"))
        if "clinic_staff_id" in path.read_text()
    ]
    assert not duplicates, f"metadata still carries clinic_staff_id: {duplicates}"
