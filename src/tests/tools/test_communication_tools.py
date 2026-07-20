"""Unit tests for the communication.send_zalo stub tool."""

from __future__ import annotations

from uuid import uuid4

import pytest

from clinicai.tools._common.context import new_trace
from clinicai.tools.communication.send_zalo import (
    SendZaloInput,
    send_zalo_message,
)


@pytest.mark.asyncio
async def test_send_zalo_stub_returns_undelivered() -> None:
    """Stub must never claim delivery."""
    inp = SendZaloInput(
        patient_id=uuid4(),
        message="hello",
        ctx=new_trace(source_channel="zalo"),
    )

    out = await send_zalo_message(inp)

    assert out.delivered is False
    assert out.stub is True


@pytest.mark.asyncio
async def test_send_zalo_message_preview_truncated() -> None:
    """A 100-char message should be truncated to 50 chars in the preview."""
    message = "x" * 100
    inp = SendZaloInput(patient_id=uuid4(), message=message, ctx=new_trace())

    out = await send_zalo_message(inp)

    assert len(out.message_preview) == 50
    assert out.message_preview == "x" * 50


@pytest.mark.asyncio
async def test_send_zalo_trace_id_propagated() -> None:
    """Output trace_id must equal input ctx trace_id."""
    inp = SendZaloInput(patient_id=uuid4(), message="m", ctx=new_trace())

    out = await send_zalo_message(inp)

    assert out.trace_id == inp.ctx.trace_id
