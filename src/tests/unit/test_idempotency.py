"""Unit tests for endpoint/actor-scoped atomic idempotency."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.idempotency import IdempotencyGuard


def _pool() -> MagicMock:
    pool = MagicMock()
    pool.fetchrow = AsyncMock()
    pool.execute = AsyncMock(return_value="UPDATE 1")
    return pool


@pytest.mark.asyncio
async def test_acquire_reserves_key_atomically_for_endpoint_and_actor() -> None:
    pool = _pool()
    pool.fetchrow.return_value = {"key": "request-1"}
    guard = IdempotencyGuard(key="request-1", endpoint="POST /api/v1/payments")

    guard = await guard.acquire(pool, actor_id="staff-a")

    sql, key, endpoint, actor_id = pool.fetchrow.await_args.args
    assert "INSERT INTO idempotency_key" in sql
    assert "ON CONFLICT (key, endpoint, actor_id) DO NOTHING" in sql
    assert (key, endpoint, actor_id) == (
        "request-1",
        "POST /api/v1/payments",
        "staff-a",
    )
    assert not guard.is_replay


@pytest.mark.asyncio
async def test_acquire_replays_only_matching_endpoint_and_actor() -> None:
    pool = _pool()
    pool.fetchrow.side_effect = [
        None,  # INSERT lost to the existing composite key
        None,  # stale reservation was not reclaimable
        {
            "response": json.dumps({"ok": True}),
            "status_code": 201,
            "state": "COMPLETED",
        },
    ]
    guard = IdempotencyGuard(key="same-client-key", endpoint="POST /appointments")

    guard = await guard.acquire(pool, actor_id="staff-b")

    assert guard.is_replay
    assert guard.cached_response is not None
    assert guard.cached_response.status_code == 201
    assert guard.actor_id == "staff-b"
    lookup = pool.fetchrow.await_args_list[2].args
    assert lookup[1:] == ("same-client-key", "POST /appointments", "staff-b")


@pytest.mark.asyncio
async def test_concurrent_in_progress_request_returns_conflict() -> None:
    pool = _pool()
    pool.fetchrow.side_effect = [
        None,
        None,
        {"response": None, "status_code": 200, "state": "PROCESSING"},
    ]
    guard = IdempotencyGuard(key="request-2", endpoint="POST /appointments")

    with pytest.raises(ConflictError, match="đang được xử lý"):
        await guard.acquire(pool)


@pytest.mark.asyncio
async def test_save_completes_the_exact_reservation() -> None:
    pool = _pool()
    pool.fetchrow.return_value = {"key": "request-3"}
    guard = IdempotencyGuard(key="request-3", endpoint="POST /payments")
    guard = await guard.acquire(pool, actor_id="staff-c")

    await guard.save(pool, {"ok": True}, status_code=201)

    sql, response, status_code, key, endpoint, actor_id = pool.execute.await_args.args
    assert "state = 'COMPLETED'" in sql
    assert json.loads(response) == {"ok": True}
    assert (status_code, key, endpoint, actor_id) == (
        201,
        "request-3",
        "POST /payments",
        "staff-c",
    )


@pytest.mark.asyncio
async def test_missing_key_never_touches_database() -> None:
    pool = _pool()
    guard = IdempotencyGuard(key=None, endpoint="POST /appointments")

    guard = await guard.acquire(pool)
    await guard.save(pool, {"ok": True})

    pool.fetchrow.assert_not_awaited()
    pool.execute.assert_not_awaited()
