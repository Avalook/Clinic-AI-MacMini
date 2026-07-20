"""Anthropic model constants. Sonnet 4 retired Apr 2026 → dùng Sonnet 4.6."""

from typing import Literal

MAIN_BRAIN_MODEL = "claude-sonnet-4-6"
GATEWAY_MODEL = "claude-haiku-4-5-20251001"

Tier = Literal["main_brain", "gateway"]

TIER_TO_MODEL: dict[str, str] = {
    "main_brain": MAIN_BRAIN_MODEL,
    "gateway": GATEWAY_MODEL,
}
