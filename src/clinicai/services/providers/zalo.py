"""Zalo OA API provider — stub with correct interface.

Phase 3 of the System Design completion plan (Bài 23 — Notification System).

This is a STUB — it logs only delivery metadata and does not call the Zalo API.
Replace with real implementation when you have a Zalo Official Account and
API access token.

Required env vars (for real implementation):
  ZALO_OA_ACCESS_TOKEN  — from Zalo Developer portal
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


async def send_zalo(phone: str, message: str) -> dict[str, Any]:
    """Send a message to a phone number via Zalo OA.

    STUB: logs the message and returns success. Replace with real Zalo API
    call when credentials are available.
    """
    logger.info(
        "zalo_stub_send",
        provider="zalo",
        stub=True,
    )
    return {"ok": True, "stub": True}
