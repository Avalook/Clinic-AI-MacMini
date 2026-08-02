"""Regression tests for the static tenant SQL gate."""

from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

_REPO = Path(__file__).resolve().parents[2]
_AUDIT = runpy.run_path(str(_REPO / "scripts/tests/tenant-scope-audit.py"))
has_clinic_scope = cast(Callable[[str], bool], _AUDIT["has_clinic_scope"])
or_bypasses_tenant = cast(Callable[[str], bool], _AUDIT["or_bypasses_tenant"])
stale_exemptions = cast(
    Callable[[frozenset[str]], list[str]], _AUDIT["stale_exemptions"]
)
stale_markers = cast(Callable[[frozenset[str]], list[str]], _AUDIT["stale_markers"])

# The audit reads its table list from a live schema (supabase/tests/
# derive_tenant_tables.sql); this job has no database. These are only the
# tables the exempted and marked statements actually name, and getting the
# list wrong fails these tests rather than passing them: too few tables means
# no tenant table is touched, which reports the exemption as unearned.
_TENANT_TABLES = frozenset({"pos_outbox", "clinic_membership"})


def test_projection_or_comment_does_not_count_as_tenant_scope() -> None:
    assert not has_clinic_scope("SELECT clinic_id, full_name FROM patient")
    assert not has_clinic_scope(
        "-- clinic_id = $1\nSELECT full_name FROM patient WHERE id = $1"
    )


def test_insert_column_and_filter_predicate_count_as_tenant_scope() -> None:
    assert has_clinic_scope(
        "INSERT INTO event_log (clinic_id, event_type) VALUES ($1, $2)"
    )
    assert has_clinic_scope(
        "SELECT full_name FROM patient WHERE clinic_id = $1 AND id = $2"
    )


def test_or_that_escapes_the_tenant_filter_is_caught() -> None:
    """The exact statement that shipped and leaked.

    SQL binds AND tighter than OR, so this reads
    (clinic_id = $2 AND phone_primary = …) OR (phone_secondary = …): a lookup by
    a patient's second phone number returned every clinic's patients. It passed
    the gate because clinic_id is present AND is a genuine predicate — which is
    why the gate had to learn about precedence, not just presence.
    """
    assert or_bypasses_tenant(
        "SELECT * FROM patient WHERE clinic_id = $2::uuid "
        "AND phone_primary = ANY($1::text[]) OR phone_secondary = ANY($1::text[])"
    )


def test_parenthesised_or_is_not_flagged() -> None:
    assert not or_bypasses_tenant(
        "SELECT * FROM patient WHERE clinic_id = $2::uuid "
        "AND (phone_primary = ANY($1::text[]) OR phone_secondary = ANY($1::text[]))"
    )


def test_tenant_repeated_in_every_branch_is_not_flagged() -> None:
    assert not or_bypasses_tenant(
        "SELECT * FROM patient WHERE (clinic_id = $1 AND a = 1) "
        "OR (clinic_id = $1 AND b = 2)"
    )


def test_or_inside_a_function_call_is_not_flagged() -> None:
    assert not or_bypasses_tenant(
        "SELECT * FROM patient WHERE clinic_id = $1 AND COALESCE(a, b) = ANY($2)"
    )


def test_no_cross_tenant_exemption_is_stale() -> None:
    """Every exemption must still be earned.

    The list is checked in both directions, like the service-role allowlist:
    adding an entry needs a reason, and KEEPING one needs the reason to still
    hold. notification_relay.py stayed on this list after its query had already
    been scoped per clinic — at which point "exempt from the tenant audit" reads
    as "someone reviewed this and it is fine", which nobody had.
    """
    assert stale_exemptions(_TENANT_TABLES) == []


def test_no_inline_cross_tenant_marker_is_stale() -> None:
    """Same rule for the per-statement marks, checked the same way.

    A `-- tenant-scope:` comment on a query that has since been scoped is the
    file-level failure in miniature: the mark stays, the reason evaporates, and
    the next reader takes it for a review.
    """
    assert stale_markers(_TENANT_TABLES) == []
