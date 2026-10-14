"""Chốt hạn dùng của Postgres trả xung đột 409 có hướng xử lý."""

from __future__ import annotations

import json

import asyncpg
from starlette.requests import Request

from clinicai.main import exclusion_violation_handler


async def test_sql_chan_han_lo_tra_409_tieng_viet() -> None:
    exc = asyncpg.ExclusionViolationError.new(
        {"C": "23P01", "M": "Lô hết hạn", "n": "lo_het_han"}
    )
    response = await exclusion_violation_handler(Request({"type": "http"}), exc)
    assert response.status_code == 409
    body = json.loads(bytes(response.body))
    assert "hết hạn" in str(body)
    assert "đổi lô" in str(body)
    assert "hoàn" in str(body)
