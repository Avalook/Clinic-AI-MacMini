"""Unit tests for the pure care-episode transition table (W5).

The DB paths (the PENDING_CLOSE guard, the transactional audit event) are
exercised by integration tests; this file pins the rules that used to live in
``src/dashboard/app/api/episodes/route.ts``.
"""

from __future__ import annotations

import pytest

from clinicai.api.v1.routers.episodes import _EPISODE_GUARD
from clinicai.services.episode_service import PENDING_CLOSE, resolve_transition


class TestResolveTransition:
    def test_close_stamps_the_cskh_reason(self) -> None:
        status, reason, event = resolve_transition("close")
        assert (status, reason, event) == ("CLOSED", "cskh_confirmed", "episode.closed")

    def test_reopen_clears_the_reason(self) -> None:
        # Reopening means "the patient is still in care" — leaving a close_reason
        # behind would make the episode look finished in every report.
        status, reason, event = resolve_transition("reopen")
        assert (status, reason, event) == ("OPEN", None, "episode.reopened")

    @pytest.mark.parametrize("action", ["", "CLOSE", "delete", "closed", "reopen "])
    def test_anything_else_is_rejected(self, action: str) -> None:
        with pytest.raises(ValueError):
            resolve_transition(action)

    def test_only_pending_close_is_actionable(self) -> None:
        assert PENDING_CLOSE == "PENDING_CLOSE"


class TestEpisodeGuard:
    """CHỈ LEGO (28/09/2026): cửa hỏi QUYỀN quản lý lịch hẹn / CSKH, không hỏi
    vai — cấp lego cho ai thì người ấy qua."""

    def test_cua_hoi_quyen_khong_hoi_vai(self) -> None:
        assert set(_EPISODE_GUARD.quyen) == {"booking.manage", "crm.manage"}
