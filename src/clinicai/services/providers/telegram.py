"""Telegram Bot API provider — sends notifications via Telegram.

Phase 3 of the System Design completion plan (Bài 23 — Notification System).

Requires two env vars:
  TELEGRAM_BOT_TOKEN  — from @BotFather
  TELEGRAM_CHAT_ID    — group/channel chat ID to send notifications to

If either is unset, messages are logged but not sent (safe fallback).
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

TELEGRAM_API = "https://api.telegram.org"
SEND_TIMEOUT = 10.0  # seconds


async def send_telegram(message: str) -> dict[str, Any]:
    """Send a text message to the configured Telegram chat.

    Returns the Telegram API response dict on success, or an error dict.
    Does NOT raise on failure — the caller handles retry logic.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        logger.info(
            "telegram_skipped",
            reason="TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set",
        )
        return {"ok": False, "skipped": True}

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=SEND_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            raw_result = resp.json()

        result: dict[str, Any] = (
            raw_result
            if isinstance(raw_result, dict)
            else {"ok": False, "error": "invalid Telegram response"}
        )

        if not result.get("ok"):
            logger.warning(
                "telegram_send_failed",
                status_code=resp.status_code,
                description=result.get("description"),
            )
        else:
            logger.info("telegram_sent", chat_id=chat_id)

        return result
    except httpx.HTTPError as exc:
        logger.error("telegram_http_error", error=str(exc))
        return {"ok": False, "error": str(exc)}
