"""The Command API behind the workflow kernel (W4, ADR-0011, doc §4.3).

A work item never changes because someone PATCHed a status. It changes because
somebody issued a business command — start, complete, skip, cancel — and the
command was allowed. Everything that decides "allowed" lives here:

* the transition is legal for the current status;
* the caller's role is one the node definition names as an actor;
* the blocking dependency gate for that command is open (FS/SS gate `start`,
  FF/SF gate `complete`), evaluated by ``work_item_gate_blockers`` in SQL so no
  caller can route around it;
* nobody else moved the item in the meantime — the UPDATE carries the version
  the caller read, and a lost race is a 409 rather than a silent overwrite.

The status change and its ``work_item_event`` row are written in one
transaction, so history cannot disagree with state.
"""

from __future__ import annotations

import json
from typing import Literal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError

logger = structlog.get_logger()

Command = Literal["start", "complete", "skip", "cancel"]

PENDING = "PENDING"
IN_PROGRESS = "IN_PROGRESS"
COMPLETED = "COMPLETED"
SKIPPED = "SKIPPED"
CANCELLED = "CANCELLED"

TERMINAL: frozenset[str] = frozenset({COMPLETED, SKIPPED, CANCELLED})

# command -> (statuses it may be issued from, resulting status)
_TRANSITIONS: dict[str, tuple[frozenset[str], str]] = {
    "start": (frozenset({PENDING}), IN_PROGRESS),
    "complete": (frozenset({IN_PROGRESS}), COMPLETED),
    # Skipping and cancelling are decisions available at any point before the
    # item is finished — a nurse can skip vitals she has already started.
    "skip": (frozenset({PENDING, IN_PROGRESS}), SKIPPED),
    "cancel": (frozenset({PENDING, IN_PROGRESS}), CANCELLED),
}

# Only start and complete are gated. Skipping and cancelling are how a stuck
# flow gets unstuck, so a shut gate must never prevent them.
_GATED: dict[str, str] = {"start": "start", "complete": "complete"}


def resolve_transition(command: str) -> tuple[frozenset[str], str]:
    """(statuses the command may be issued from, resulting status).

    Pure, so the state machine is testable without a database.
    """
    try:
        return _TRANSITIONS[command]
    except KeyError:
        raise ValueError(f"Lệnh không hợp lệ: {command!r}") from None


def is_terminal(status: str) -> bool:
    return status in TERMINAL


class WorkItemService:
    """Issue commands against work items."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def issue(
        self,
        *,
        work_item_id: str,
        command: Command,
        identity: StaffIdentity,
        expected_version: int | None = None,
        reason: str | None = None,
    ) -> dict[str, object]:
        """Run one command. Returns the item's new status and version.

        Raises NotFoundError (404) when the item is not in the caller's clinic,
        SafetyGateError (403) when the caller's role may not act on the node,
        and ConflictError (409) for an illegal transition, a shut gate, or a
        version that someone else has already moved past.
        """
        allowed_from, next_status = resolve_transition(command)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                item = await conn.fetchrow(
                    """
                    SELECT w.id, w.status, w.version, w.node_code, w.clinic_id,
                           n.actor_roles, n.name AS node_name,
                           m.role AS membership_role
                      FROM work_item w
                      JOIN clinic_membership m
                        ON m.clinic_id = w.clinic_id
                       AND m.staff_id = $2::uuid
                       AND m.is_active
                       AND m.clinic_id = $3::uuid
                       AND m.role = $4
                      LEFT JOIN node_definition n
                        ON n.clinic_id = w.clinic_id
                       AND n.code = w.node_code
                     WHERE w.id = $1::uuid
                       AND w.clinic_id = $3::uuid
                     FOR UPDATE OF w
                    """,
                    work_item_id,
                    identity.staff_id,
                    identity.clinic_id,
                    identity.role.value,
                )
                # Both halves of the identity are re-checked against the same
                # active membership. A membership in some other clinic (or a
                # stale role changed after identity resolution) grants nothing.
                if item is None:
                    raise NotFoundError("Không tìm thấy đầu việc")

                current: str = item["status"]
                if current not in allowed_from:
                    raise ConflictError(
                        f"Không thể '{command}' khi đầu việc đang ở "
                        f"trạng thái {current}"
                    )

                actor_roles: list[str] = list(item["actor_roles"] or [])
                membership_role = str(item["membership_role"])
                if actor_roles and membership_role not in actor_roles:
                    logger.info(
                        "work_item_role_forbidden",
                        node_code=item["node_code"],
                        role=membership_role,
                        allowed=actor_roles,
                    )
                    raise SafetyGateError(
                        f"Vai trò của bạn không phụ trách bước '{item['node_name']}'"
                    )

                phase = _GATED.get(command)
                if phase is not None:
                    blockers = await conn.fetch(
                        "SELECT node_code, dependency_type "
                        "FROM work_item_gate_blockers($1::uuid, $2)",
                        work_item_id,
                        phase,
                    )
                    if blockers:
                        names = ", ".join(sorted({b["node_code"] for b in blockers}))
                        raise ConflictError(f"Còn bước chưa xong: {names}")

                updated = await conn.fetchrow(
                    """
                    UPDATE work_item
                       SET status      = $2,
                           started_at  = CASE
                                             WHEN $2 = 'IN_PROGRESS' THEN now()
                                             ELSE started_at
                                         END,
                           finished_at = CASE
                                             WHEN $2 IN
                                                  ('COMPLETED', 'SKIPPED', 'CANCELLED')
                                             THEN now()
                                             ELSE finished_at
                                         END,
                           version     = version + 1,
                           updated_at  = now()
                     WHERE id = $1::uuid
                       AND status = $3
                       AND ($4::integer IS NULL OR version = $4::integer)
                       AND clinic_id = $5::uuid
                    RETURNING version
                    """,
                    work_item_id,
                    next_status,
                    current,
                    expected_version,
                    identity.clinic_id,
                )
                if updated is None:
                    raise ConflictError(
                        "Đầu việc vừa được người khác cập nhật — hãy tải lại"
                    )

                await conn.execute(
                    """
                    INSERT INTO work_item_event
                        (clinic_id, work_item_id, command, from_status, to_status,
                         actor_staff_id, actor_role, reason, metadata)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid, $7, $8, $9)
                    """,
                    identity.clinic_id,
                    work_item_id,
                    command,
                    current,
                    next_status,
                    identity.staff_id,
                    membership_role,
                    reason,
                    json.dumps({"node_code": item["node_code"]}),
                )

        logger.info(
            "work_item_command",
            work_item_id=work_item_id,
            command=command,
            node_code=item["node_code"],
            from_status=current,
            to_status=next_status,
            by_staff_id=identity.staff_id,
            by_role=membership_role,
        )
        return {
            "id": work_item_id,
            "status": next_status,
            "version": updated["version"],
        }

    async def list_for_visit(
        self,
        *,
        visit_id: str,
        identity: StaffIdentity,
    ) -> list[dict[str, object]]:
        """The visit's work items, in flow order, with what the caller may do.

        Joins the LIVE node_definition, not the pinned
        node_definition_version.snapshot. The two can differ, and `issue()`
        authorises from the live row — so displaying the snapshot's actor_roles
        would produce an item that looks actionable to a role the gate then
        refuses. Pinning is for history; authorisation is live, and the read
        path has to agree with the write path or the UI lies.

        Membership is re-checked in the query rather than trusted from the
        identity, the same way issue() does it: the backend bypasses RLS, so
        this join is the only thing standing between a caller and another
        clinic's board.
        """
        rows = await self._pool.fetch(
            """
            -- Flow order, not alphabetical. Ordering by flow_group sorted the
            -- board kham → sinh_hieu → thu_ngan → tiep_nhan, i.e. "tạo chỉ
            -- định" above the check-in that has to happen first. Depth is
            -- distance from a node nothing depends on, so the board reads in
            -- the order the day actually happens, for any catalogue.
            WITH RECURSIVE depth AS (
                SELECT n.code, 0 AS level
                  FROM node_definition n
                 WHERE n.clinic_id = $2::uuid
                   AND NOT EXISTS (
                       SELECT 1 FROM node_dependency d
                        WHERE d.clinic_id = n.clinic_id
                          AND d.successor_code = n.code)
                UNION
                SELECT d.successor_code, p.level + 1
                  FROM node_dependency d
                  JOIN depth p ON p.code = d.predecessor_code
                 WHERE d.clinic_id = $2::uuid
                   AND p.level < 64          -- a cycle terminates, not hangs
            ),
            flow AS (
                SELECT code, max(level) AS level FROM depth GROUP BY code
            )
            SELECT w.id,
                   w.node_code,
                   w.status,
                   w.priority,
                   w.version,
                   w.assigned_role,
                   w.assigned_to,
                   w.started_at,
                   w.finished_at,
                   n.name        AS node_name,
                   n.flow_group,
                   n.workspace,
                   n.actor_roles,
                   -- Mine to act on? The node's own actor list is what narrows
                   -- the flow per station; an empty list means anyone working
                   -- the flow may take it.
                   (n.actor_roles IS NULL
                    OR cardinality(n.actor_roles) = 0
                    OR m.role = ANY (n.actor_roles))  AS actionable_by_me,
                   EXISTS (
                       SELECT 1 FROM work_item_gate_blockers(w.id, 'start')
                   )                                   AS blocked
              FROM work_item w
              JOIN clinic_membership m
                ON m.clinic_id = w.clinic_id
               AND m.staff_id = $3::uuid
               AND m.is_active
               AND m.role = $4
              LEFT JOIN node_definition n
                ON n.clinic_id = w.clinic_id
               AND n.code = w.node_code
              LEFT JOIN flow f ON f.code = w.node_code
             WHERE w.visit_id = $1::uuid
               AND w.clinic_id = $2::uuid
               AND w.status <> 'CANCELLED'
             ORDER BY f.level NULLS LAST, w.node_code
            """,
            visit_id,
            identity.clinic_id,
            identity.staff_id,
            identity.role.value,
        )

        return [
            {
                "id": str(r["id"]),
                "node_code": r["node_code"],
                "node_name": r["node_name"],
                "flow_group": r["flow_group"],
                "workspace": r["workspace"],
                "status": r["status"],
                "priority": r["priority"],
                "version": r["version"],
                "assigned_role": r["assigned_role"],
                "assigned_to": str(r["assigned_to"]) if r["assigned_to"] else None,
                "actor_roles": list(r["actor_roles"] or []),
                "actionable_by_me": bool(r["actionable_by_me"]),
                "blocked": bool(r["blocked"]),
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
            }
            for r in rows
        ]

    async def blockers(
        self,
        *,
        work_item_id: str,
        phase: str,
        identity: StaffIdentity,
    ) -> list[dict[str, str]]:
        """Return blockers only when the item belongs to the active membership."""
        rows = await self._pool.fetch(
            """
            SELECT w.id AS scoped_work_item_id,
                   b.node_code,
                   b.dependency_type
              FROM work_item w
              JOIN clinic_membership m
                ON m.clinic_id = w.clinic_id
               AND m.staff_id = $4::uuid
               AND m.is_active
               AND m.role = $5
              LEFT JOIN LATERAL
                   work_item_gate_blockers(w.id, $2) b ON TRUE
             WHERE w.id = $1::uuid
               AND w.clinic_id = $3::uuid
            """,
            work_item_id,
            phase,
            identity.clinic_id,
            identity.staff_id,
            identity.role.value,
        )
        if not rows:
            # Cross-clinic and nonexistent identifiers are deliberately
            # indistinguishable at this boundary.
            raise NotFoundError("Không tìm thấy đầu việc")
        return [
            {"node_code": r["node_code"], "dependency_type": r["dependency_type"]}
            for r in rows
            if r["node_code"] is not None
        ]
