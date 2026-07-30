"""Unit tests for the work-item state machine and its role gate (W4).

The dependency gates themselves are SQL and are covered by
supabase/tests/workflow_kernel.sql; what is pinned here is the pure part — which
commands are legal from which status, and which roles the Command API admits.
"""

from __future__ import annotations

import pytest

from clinicai.api.identity import ClinicRole
from clinicai.api.v1.routers.work_items import _WORK_ITEM_GUARD
from clinicai.services.work_item_service import (
    CANCELLED,
    COMPLETED,
    IN_PROGRESS,
    PENDING,
    SKIPPED,
    is_terminal,
    resolve_transition,
)


class TestTransitions:
    def test_start_only_from_pending(self) -> None:
        allowed, result = resolve_transition("start")
        assert allowed == frozenset({PENDING})
        assert result == IN_PROGRESS

    def test_complete_requires_work_to_have_begun(self) -> None:
        # Completing straight out of PENDING would leave started_at empty and
        # make "how long did this take" unanswerable for every report.
        allowed, result = resolve_transition("complete")
        assert allowed == frozenset({IN_PROGRESS})
        assert result == COMPLETED

    @pytest.mark.parametrize(
        ("command", "expected"), [("skip", SKIPPED), ("cancel", CANCELLED)]
    )
    def test_skip_and_cancel_available_until_finished(
        self, command: str, expected: str
    ) -> None:
        allowed, result = resolve_transition(command)
        assert allowed == frozenset({PENDING, IN_PROGRESS})
        assert result == expected

    @pytest.mark.parametrize("status", [COMPLETED, SKIPPED, CANCELLED])
    def test_nothing_moves_a_finished_item(self, status: str) -> None:
        for command in ("start", "complete", "skip", "cancel"):
            allowed, _ = resolve_transition(command)
            assert status not in allowed

    def test_terminal_statuses(self) -> None:
        assert (
            is_terminal(COMPLETED) and is_terminal(SKIPPED) and is_terminal(CANCELLED)
        )
        assert not is_terminal(PENDING) and not is_terminal(IN_PROGRESS)

    @pytest.mark.parametrize(
        "command", ["", "START", "finish", "done", "complete ", "reopen"]
    )
    def test_unknown_commands_are_refused(self, command: str) -> None:
        with pytest.raises(ValueError):
            resolve_transition(command)


class TestRouterGuard:
    def test_every_working_role_may_reach_the_command_api(self) -> None:
        # The flow is worked by everybody; the node's own actor_roles is what
        # narrows each station, so the router must not narrow it first.
        assert _WORK_ITEM_GUARD.allowed_roles == frozenset(ClinicRole)
