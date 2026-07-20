"""Security regression tests for the Zalo provider boundary."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from clinicai.services.providers import zalo


@pytest.mark.asyncio
async def test_stub_log_does_not_include_phone_or_message(monkeypatch) -> None:
    fake_logger = MagicMock()
    monkeypatch.setattr(zalo, "logger", fake_logger)

    result = await zalo.send_zalo("0901234567", "Chị Lan đang đau bụng")

    assert result == {"ok": True, "stub": True}
    _, kwargs = fake_logger.info.call_args
    assert "phone" not in kwargs
    assert "message" not in kwargs
    assert "message_preview" not in kwargs
