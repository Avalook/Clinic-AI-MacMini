"""Audit CLIN-003: invariant probe, expected RED before durable handoff repair."""

# ruff: noqa: F811 — imported pytest fixture follows this repository's convention.

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock

import asyncpg
import pytest

from clinicai.services import hen_tai_kham_service as htk
from tests.services.test_hen_tai_kham_db import (
    _chuan_bi,
    _hom_nay,
    _luu,
    _o,
    _viec,
)
from tests.services.test_phieu_kham_db import pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_saved_follow_date_recovers_handoff_after_transient_sync_failure(
    pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    doctor, visit = await _chuan_bi(pool)
    day = (_hom_nay() + dt.timedelta(days=30)).isoformat()
    with monkeypatch.context() as patch:
        patch.setattr(
            htk, "dong_bo", AsyncMock(side_effect=RuntimeError("audit transient"))
        )
        first = await _luu(pool, doctor, visit["visit"], {"pk_follow_date": _o(day)})
    assert first["ok"] is True
    assert first["hen_tai_kham"]["trang_thai"] == "LOI"
    # Healthy retry keeps the doctor's date, rather than fabricating a date edit.
    second = await _luu(
        pool,
        doctor,
        visit["visit"],
        {"pk_follow_date": _o(day), "pk_follow_note": _o("Synthetic audit note")},
    )
    assert second["ok"] is True
    tasks = await _viec(pool, visit["visit"])
    assert len(tasks) == 1, "The follow date persisted but its CSKH handoff was lost"
