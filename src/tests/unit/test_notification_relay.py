"""Unit tests for the event_log notification outbox relay."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from clinicai.services.notification_relay import poll_and_deliver

CLINIC_ID = "a0000000-0000-4000-8000-000000000001"


def _relay_db(
    rows: list[dict[str, Any]], *fetchvals: object
) -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()
    acquire = AsyncMock()
    acquire.__aenter__.return_value = conn
    pool.acquire.return_value = acquire
    conn.fetch.return_value = rows
    conn.fetchval.side_effect = fetchvals
    conn.execute.return_value = "UPDATE 1"
    return pool, conn


@pytest.mark.asyncio
async def test_relay_claims_and_marks_canonical_event_log_row() -> None:
    event_id = uuid4()
    pool, conn = _relay_db(
        [
            {
                "event_id": event_id,
                "event_type": "appointment.created",
                "payload": {"patient_name": "Lan"},
                "metadata": {},
            }
        ],
        True,  # advisory lock acquired
        True,  # event still unpublished after acquiring the lock
    )

    with (
        patch(
            "clinicai.services.notification_relay.notification_templates.render",
            return_value="Có lịch hẹn mới",
        ),
        patch(
            "clinicai.services.notification_relay.telegram.send_telegram",
            new=AsyncMock(return_value={"ok": True}),
        ),
    ):
        assert await poll_and_deliver(pool, clinic_id=CLINIC_ID) == 1

    select_sql = conn.fetch.await_args.args[0]
    assert "SELECT event_id" in select_sql
    assert "ORDER BY occurred_at" in select_sql
    assert "clinic_id = $1::uuid" in select_sql
    assert conn.fetch.await_args.args[1] == CLINIC_ID
    assert "SELECT id" not in select_sql
    assert "created_at" not in select_sql

    claim_sql = conn.fetchval.await_args_list[0].args[0]
    assert "pg_try_advisory_lock" in claim_sql
    update_calls = [
        call.args
        for call in conn.execute.await_args_list
        if "UPDATE event_log" in call.args[0]
    ]
    assert len(update_calls) == 1
    assert "WHERE event_id = $1 AND clinic_id = $2::uuid" in update_calls[0][0]
    assert update_calls[0][1] == event_id
    assert update_calls[0][2] == CLINIC_ID


@pytest.mark.asyncio
async def test_relay_does_not_send_event_claimed_by_another_worker() -> None:
    pool, conn = _relay_db(
        [
            {
                "event_id": uuid4(),
                "event_type": "appointment.created",
                "payload": {},
                "metadata": {},
            }
        ],
        False,
    )
    send = AsyncMock(return_value={"ok": True})

    with (
        patch(
            "clinicai.services.notification_relay.notification_templates.render",
            return_value="Có lịch hẹn mới",
        ),
        patch(
            "clinicai.services.notification_relay.telegram.send_telegram",
            new=send,
        ),
    ):
        assert await poll_and_deliver(pool, clinic_id=CLINIC_ID) == 0

    send.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_result", "expected_attempts"),
    [
        ({"ok": False}, 3),
        ({"ok": False, "skipped": True}, 1),
    ],
)
async def test_relay_does_not_publish_unaccepted_delivery(
    provider_result: dict[str, object], expected_attempts: int
) -> None:
    pool, conn = _relay_db(
        [
            {
                "event_id": uuid4(),
                "event_type": "appointment.created",
                "payload": {},
                "metadata": {},
            }
        ],
        True,
        True,
    )

    with (
        patch(
            "clinicai.services.notification_relay.notification_templates.render",
            return_value="Có lịch hẹn mới",
        ),
        patch(
            "clinicai.services.notification_relay.telegram.send_telegram",
            new=AsyncMock(return_value=provider_result),
        ) as send,
    ):
        assert await poll_and_deliver(pool, clinic_id=CLINIC_ID) == 0

    assert send.await_count == expected_attempts
    assert not any(
        "UPDATE event_log" in call.args[0] for call in conn.execute.await_args_list
    )
