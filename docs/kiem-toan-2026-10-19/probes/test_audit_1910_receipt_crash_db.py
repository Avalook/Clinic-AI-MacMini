"""Audit: lost receipt after a committed command must not duplicate activity."""

# ruff: noqa: F811 -- imported fixture follows the repository convention.

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import asyncpg
import pytest

from clinicai.api.idempotency import IdempotencyGuard
from clinicai.api.v1.routers.cskh import TuongTacRequest, ghi_tuong_tac
from tests.services.test_phieu_kham_db import _luot, _nguoi, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_committed_interaction_retries_once_after_receipt_write_failure(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with pool.acquire() as conn:
        person = await _nguoi(conn, "CSKH")
        visit = await _luot(conn, person)
    key = "audit-crash-" + uuid.uuid4().hex
    endpoint = "POST /api/v1/cskh/tuong-tac"
    body = TuongTacRequest(
        clinic_patient_id=uuid.UUID(visit["patient"]),
        loai="KHAC",
        kenh="GOI",
        ket_qua="DA_LIEN_HE",
        noi_dung="Synthetic audit contact, once only",
    )
    guard = IdempotencyGuard(key=key, endpoint=endpoint, request_hash="a" * 64)
    with monkeypatch.context() as patch:
        patch.setattr(
            IdempotencyGuard,
            "save",
            AsyncMock(
                side_effect=RuntimeError("Synthetic receipt persistence failure")
            ),
        )
        with pytest.raises(RuntimeError, match="receipt persistence"):
            await ghi_tuong_tac(body=body, identity=person, pool=pool, idem=guard)
    first = await pool.fetchval(
        "SELECT count(*) FROM tuong_tac_cskh WHERE clinic_patient_id=$1::uuid",
        visit["patient"],
    )
    assert first == 1, "The domain operation committed before receipt failure"
    # Advance just the reservation's timestamp; no sleep or system clock changes.
    await pool.execute(
        "UPDATE idempotency_key SET updated_at=now()-interval '6 minutes'"
        " WHERE key=$1 AND endpoint=$2 AND actor_id=$3",
        key,
        endpoint,
        person.auth_user_id,
    )
    await ghi_tuong_tac(body=body, identity=person, pool=pool, idem=guard)
    count = await pool.fetchval(
        "SELECT count(*) FROM tuong_tac_cskh WHERE clinic_patient_id=$1::uuid",
        visit["patient"],
    )
    assert count == 1, "Same command was executed twice after its receipt was lost"
