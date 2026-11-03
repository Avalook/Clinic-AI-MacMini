"""Chọn adapter mô hình từ chuỗi `hãng:model`.

    anthropic:claude-haiku-5-5      → Claude (adapter riêng)
    openai:<model> · gemini:<model> · deepseek:<model> · ollama:<model>
                                    → chuẩn OpenAI Chat Completions
    <hãng khác>:<model>             → cần biến TRO_LY_URL_<HÃNG>

KHOÁ: tệp `/run/secrets/tro_ly_khoa_<hãng>` (docker secret) nếu có, không thì
biến `TRO_LY_KHOA_<HÃNG>`. Cố ý KHÔNG đọc `ANTHROPIC_API_KEY`: có biến ấy là
main.py bật AI phân loại xét nghiệm (cùng lý do `agent_tom_tat.py` dùng khoá tệp).
Ollama chạy tại chỗ không cần khoá.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from clinicai.adapters.mo_hinh.anthropic import MoHinhAnthropic
from clinicai.adapters.mo_hinh.openai_compat import MoHinhOpenAICompat
from clinicai.ports.mo_hinh import MoHinhError, MoHinhPort

URL_MAC_DINH: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama": "http://localhost:11434/v1",
}
KHONG_CAN_KHOA = {"ollama"}


def doc_khoa(hang: str) -> str | None:
    tep = Path(os.environ.get("TRO_LY_THU_MUC_KHOA", "/run/secrets")) / (
        f"tro_ly_khoa_{hang}"
    )
    try:
        v = tep.read_text().strip()
    except OSError:
        v = ""
    return v or os.environ.get(f"TRO_LY_KHOA_{hang.upper()}", "").strip() or None


def tao_mo_hinh(cau_hinh: str, *, pool: Any = None) -> MoHinhPort:
    hang, _, model = cau_hinh.strip().partition(":")
    hang = hang.lower()
    if not hang or not model:
        raise MoHinhError(f"Cấu hình mô hình phải dạng 'hãng:model', nhận {cau_hinh!r}")
    khoa = doc_khoa(hang)
    if hang == "anthropic":
        if not khoa:
            raise MoHinhError(
                "Thiếu khoá: tệp tro_ly_khoa_anthropic hoặc TRO_LY_KHOA_ANTHROPIC"
            )
        return MoHinhAnthropic(model, api_key=khoa, pool=pool)
    url = os.environ.get(f"TRO_LY_URL_{hang.upper()}") or URL_MAC_DINH.get(hang)
    if not url:
        raise MoHinhError(f"Hãng {hang!r} lạ: đặt TRO_LY_URL_{hang.upper()}")
    if not khoa and hang not in KHONG_CAN_KHOA:
        raise MoHinhError(
            f"Thiếu khoá: tệp tro_ly_khoa_{hang} hoặc TRO_LY_KHOA_{hang.upper()}"
        )
    return MoHinhOpenAICompat(hang, model, base_url=url, api_key=khoa, pool=pool)


__all__ = ["URL_MAC_DINH", "doc_khoa", "tao_mo_hinh"]
