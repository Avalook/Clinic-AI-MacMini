"""The realtime table list exists twice. This makes the two agree.

WHAT WENT WRONG WITHOUT IT. ``RealtimeRefresher.tsx`` subscribed to twenty
tables. The ``supabase_realtime`` publication contained two. Subscribing to a
table that is not published raises no error, logs nothing, and returns a
perfectly healthy channel — it simply never delivers an event. So for months the
app showed a pulsing green "Realtime" pill, counted "+N cập nhật" that was always
zero, and actually synchronised through a 25-second ``setInterval``. Nobody could
see it because *nothing was broken*: data did arrive, just late, and the only
symptom was a clinic that felt slow.

Two lists in two languages that must match, with silence as the failure mode, is
exactly what a test is for.

DIRECTION OF THE CHECK. Subscribing to an unpublished table is the dangerous
half — it fakes liveness. Publishing a table nobody subscribes to only wastes
WAL and RLS evaluation, so it is a warning-shaped problem, not a lie; the test
reports it but the hard assertion is on the first.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_CLIENT = _REPO / "src/dashboard/app/(dashboard)/RealtimeRefresher.tsx"
_MIGRATIONS = _REPO / "supabase/migrations"


def _published_tables() -> set[str]:
    """Every table any migration adds to ``supabase_realtime``.

    Covers both spellings used in this repo: the direct
    ``ALTER PUBLICATION … ADD TABLE public.x`` and the guarded loop in
    20260803000004 that lists tables in a plpgsql array.
    """
    published: set[str] = set()
    # The trailing `;` matters: 20260803000004 also contains the statement as a
    # plpgsql *format string* (`... ADD TABLE public.%I`), and without anchoring
    # on the semicolon the optional `public\.` group backtracks and captures the
    # literal word "public" as a table name.
    direct = re.compile(
        r"ALTER\s+PUBLICATION\s+supabase_realtime\s+ADD\s+TABLE\s+"
        r"(?:ONLY\s+)?(?:public\.)?\"?(\w+)\"?\s*;",
        re.IGNORECASE,
    )
    for sql_file in sorted(_MIGRATIONS.glob("*.sql")):
        text = sql_file.read_text(encoding="utf-8")
        published.update(m.group(1) for m in direct.finditer(text))

        # The loop form: live_tables text[] := ARRAY[ 'a', 'b', … ];
        for block in re.finditer(
            r"live_tables\s+text\[\]\s*:=\s*ARRAY\s*\[(.*?)\]", text, re.DOTALL
        ):
            published.update(re.findall(r"'(\w+)'", block.group(1)))

        # …and the removals. 20260803000008 unpublishes nine tables that reached
        # the publication by hand (dashboard clicks, or a maintenance script that
        # lives outside supabase/migrations/ so nobody can tell whether it ran).
        # Without reading the DROPs, this file would keep asserting against a
        # picture of the publication that migrations alone never described.
        for block in re.finditer(
            r"unwatched\s+text\[\]\s*:=\s*ARRAY\s*\[(.*?)\]", text, re.DOTALL
        ):
            published.difference_update(re.findall(r"'(\w+)'", block.group(1)))
    return published


def _subscribed_tables() -> set[str]:
    """The LIVE_TABLES array the browser actually subscribes to."""
    text = _CLIENT.read_text(encoding="utf-8")
    match = re.search(r"const LIVE_TABLES = \[(.*?)\] as const;", text, re.DOTALL)
    assert match, "LIVE_TABLES not found in RealtimeRefresher.tsx"
    # Drop // comments before pulling the quoted names out.
    body = re.sub(r"//[^\n]*", "", match.group(1))
    return set(re.findall(r'"(\w+)"', body))


@pytest.mark.skipif(not _CLIENT.exists(), reason="dashboard sources not present")
def test_every_subscribed_table_is_published() -> None:
    """A subscription to an unpublished table is silent, permanent nothing."""
    missing = _subscribed_tables() - _published_tables()
    assert not missing, (
        "RealtimeRefresher subscribes to tables that no migration publishes: "
        f"{sorted(missing)}. Those subscriptions will never fire and the UI "
        "will fall back to polling while still showing a live indicator. Add "
        "them to the publication, or remove them from LIVE_TABLES."
    )


@pytest.mark.skipif(not _CLIENT.exists(), reason="dashboard sources not present")
def test_publication_has_no_unwatched_tables() -> None:
    """Publishing what nobody watches costs WAL and an RLS check per subscriber."""
    unwatched = _published_tables() - _subscribed_tables()
    assert not unwatched, (
        f"Published but not subscribed: {sorted(unwatched)}. Every published "
        "table makes Realtime re-run RLS for each subscriber on each change. "
        "Either subscribe to it or drop it from the publication."
    )
