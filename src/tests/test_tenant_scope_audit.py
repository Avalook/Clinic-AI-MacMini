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
