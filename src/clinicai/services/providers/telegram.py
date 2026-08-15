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
    # NHIỀU KÊNH, phân cách bằng dấu phẩy (15/08/2026: chat riêng của Tuyền
    # + nhóm "MVP2: Clinic AI"). Tin đi ĐỦ mọi kênh; "thành công" nghĩa là
    # tất cả cùng nhận — thiếu một kênh là relay giữ sự kiện lại thử tiếp,
    # chấp nhận hiếm hoi trùng tin ở kênh đã nhận còn hơn một kênh lặng lẽ
    # không bao giờ được báo.
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        logger.info(
            "telegram_skipped",
            reason="TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set",
        )
        return {"ok": False, "skipped": True}

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    cac_kenh = [c.strip() for c in chat_id.split(",") if c.strip()]

    try:
        ket_cuoi: dict[str, Any] = {"ok": True}
        async with httpx.AsyncClient(timeout=SEND_TIMEOUT) as client:
            for kenh in cac_kenh:
                resp = await client.post(
                    url,
                    json={
                        "chat_id": kenh,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
                raw_result = resp.json()
                result: dict[str, Any] = (
                    raw_result
                    if isinstance(raw_result, dict)
                    else {"ok": False, "error": "invalid Telegram response"}
                )
                if not result.get("ok"):
                    logger.warning(
                        "telegram_send_failed",
                        chat_id=kenh,
                        status_code=resp.status_code,
                        description=result.get("description"),
                    )
                    ket_cuoi = result
                else:
                    logger.info("telegram_sent", chat_id=kenh)
        return ket_cuoi
    except httpx.HTTPError as exc:
        logger.error("telegram_http_error", error=str(exc))
        return {"ok": False, "error": str(exc)}
