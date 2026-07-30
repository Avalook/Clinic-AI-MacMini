"""Care-episode lifecycle: CSKH confirms whether a course of care is finished.

Ported from ``src/dashboard/app/api/episodes/route.ts`` (W5, ADR-0012) so the rule
lives in the backend and the dashboard stops holding a service-role key for it.
Rules preserved 1:1:

* Only ``PENDING_CLOSE`` episodes can be acted on. The doctor's screen parks an
  episode there; CSKH then either confirms it is over (``close``) or says the
  patient is still being followed and the doctor simply forgot to book the next
  visit (``reopen``).
* ``close``  → ``CLOSED``, stamping ``closed_at`` and ``close_reason``.
* ``reopen`` → ``OPEN``, clearing both.
* The transition is guarded on the current status inside the UPDATE, so two people
  confirming the same episode at once cannot both succeed — the loser gets 409.

Two things the Next route could not do, which are fixed here:

* the status change and its audit event are written in ONE transaction, so an
  episode can never close without a matching ``episode.closed`` event;
* the acting staff is the server-verified ``StaffIdentity``, never a cookie.
"""

from __future__ import annotations

import json
from typing import Literal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

EpisodeAction = Literal["close", "reopen"]

PENDING_CLOSE = "PENDING_CLOSE"

# action -> (new status, close_reason, event type)
_TRANSITIONS: dict[str, tuple[str, str | None, str]] = {
    "close": ("CLOSED", "cskh_confirmed", "episode.closed"),
    "reopen": ("OPEN", None, "episode.reopened"),
}


def resolve_transition(action: str) -> tuple[str, str | None, str]:
    """Map an action to (next status, close reason, event type).

    Pure, so the transition table can be tested without a database.
    """
    try:
        return _TRANSITIONS[action]
    except KeyError:
        raise ValueError(f"Hành động không hợp lệ: {action!r}") from None


class EpisodeService:
    """Close and reopen care episodes over the asyncpg pool."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def set_status(
        self,
        *,
        episode_id: str,
        action: EpisodeAction,
        identity: StaffIdentity,
    ) -> str:
        """Move an episode out of PENDING_CLOSE. Returns the new status.

        Raises ConflictError (409) when the episode is no longer waiting for
        confirmation — either it does not exist, or somebody else just handled it.
        """
        next_status, close_reason, event_type = resolve_transition(action)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                updated_id = await conn.fetchval(
                    """
                    UPDATE care_episode
                       SET status       = $2,
                           closed_at    = CASE WHEN $2 = 'CLOSED' THEN now() END,
                           close_reason = $3,
                           updated_at   = now()
                     WHERE id = $1::uuid
                       AND status = $4
                       AND clinic_id = $5::uuid
                    RETURNING id
                    """,
                    episode_id,
                    next_status,
                    close_reason,
                    PENDING_CLOSE,
                    identity.clinic_id,
                )
                if updated_id is None:
                    raise ConflictError(
                        "Đợt khám không còn chờ xác nhận (đã được xử lý)."
                    )

                await conn.execute(
                    """
                    INSERT INTO event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, metadata, source, event_published)
                    VALUES ($6::uuid, $1, 'care_episode', $2, $3, $4, $5, FALSE)
                    """,
                    event_type,
                    str(updated_id),
                    json.dumps({"episode_id": episode_id, "status": next_status}),
                    json.dumps(
                        {
                            "clinic_role": identity.role.value,
                            "clinic_staff_id": identity.staff_id,
                            "actor_auth_user_id": identity.auth_user_id,
                        }
                    ),
                    f"api:episode-{action}",
                    identity.clinic_id,
                )

        logger.info(
            "episode_status_changed",
            episode_id=episode_id,
            action=action,
            status=next_status,
            by_staff_id=identity.staff_id,
        )
        return next_status
