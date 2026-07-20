"""Tool: kb.read_policy — fetch a versioned policy rule from kb_policy_rule."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

import asyncpg
import structlog
from pydantic import BaseModel

from clinicai.tools._common.context import TraceContext

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


class ReadPolicyInput(BaseModel):
    """Input schema for the kb.read_policy tool."""

    policy_key: str
    ctx: TraceContext


class PolicyOutput(BaseModel):
    """Returned policy rule. rule_data is None if the key (or table) is absent."""

    policy_key: str
    rule_data: dict[str, Any] | None
    version: int | None
    trace_id: UUID


async def read_policy(
    input: ReadPolicyInput,
    pool: asyncpg.Pool,
) -> PolicyOutput:
    """Read a kb_policy_rule row by policy_key.

    The kb_policy_rule table arrives in Phase 10. Until then we catch
    UndefinedTableError and return rule_data=None so callers can degrade
    gracefully instead of crashing the orchestrator.
    """
    logger.info(
        "tool.kb.read_policy",
        policy_key=input.policy_key,
        trace_id=str(input.ctx.trace_id),
    )

    query = """
        SELECT rule_data, version
        FROM kb_policy_rule
        WHERE policy_key = $1
        ORDER BY version DESC
        LIMIT 1;
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, input.policy_key)
    except asyncpg.UndefinedTableError:
        logger.warning(
            "kb_policy_rule_table_missing",
            policy_key=input.policy_key,
            trace_id=str(input.ctx.trace_id),
        )
        return PolicyOutput(
            policy_key=input.policy_key,
            rule_data=None,
            version=None,
            trace_id=input.ctx.trace_id,
        )

    if row is None:
        return PolicyOutput(
            policy_key=input.policy_key,
            rule_data=None,
            version=None,
            trace_id=input.ctx.trace_id,
        )

    rule_data = row["rule_data"]
    if isinstance(rule_data, str):
        rule_data = json.loads(rule_data)

    return PolicyOutput(
        policy_key=input.policy_key,
        rule_data=rule_data,
        version=row["version"],
        trace_id=input.ctx.trace_id,
    )
