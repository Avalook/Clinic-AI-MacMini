"""Voice-to-EMR transcription (on-prem, tiếng Việt) — PhoWhisper.

D011: PhoWhisper ON-PREMISE — audio KHÔNG rời phòng khám. KHÔNG gọi API STT ngoài.

LUỒNG AN TOÀN (ca A — bác sĩ đọc tại phòng khám):
    mic → file audio → transcribe() → transcript NHÁP (text)
    → bác sĩ XEM/SỬA trong dashboard → LƯU qua /api/clinical-record (gate cũ)
Module này CHỈ trả TEXT nháp. KHÔNG tự ghi clinical_record (giữ ranh giới an
toàn: hồ sơ lâm sàng chỉ được ghi qua đường có gate + người duyệt). Cột DB
`voice_transcript` / `voice_note_reviewed` (migration 017) là nơi lưu nháp +
cờ đã-duyệt — do bác sĩ chốt, không phải module này.

BACKEND: faster-whisper (CTranslate2) chạy model PhoWhisper đã convert sang CT2.
faster-whisper là dependency TÙY CHỌN, import LAZY → file này import được kể cả
khi CHƯA cài (test chạy với fake transcriber). Cài thật = bước operator on-prem:

    pip install faster-whisper
    # convert PhoWhisper (HuggingFace) sang CTranslate2:
    ct2-transformers-converter --model vinai/PhoWhisper-medium \\
        --output_dir /opt/models/phowhisper-medium-ct2 --quantization int8
    # rồi đặt env: VOICE_MODEL=/opt/models/phowhisper-medium-ct2

Chọn model theo máy: tiếng Việt y tế → PhoWhisper medium/large; máy yếu → small.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import structlog

logger = structlog.get_logger(__name__)

MODEL_ENV = "VOICE_MODEL"


class VoiceModelNotInstalledError(RuntimeError):
    """faster-whisper chưa được cài (dependency on-prem tùy chọn)."""


class VoiceModelNotConfiguredError(RuntimeError):
    """Chưa đặt env VOICE_MODEL trỏ tới model PhoWhisper (CT2)."""


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str
    model: str
    duration_s: float
    segments: list[TranscriptSegment]


class Transcriber(Protocol):
    """Giao diện nhận giọng nói → text. Cho phép fake trong test + đổi backend."""

    async def transcribe(
        self, audio_path: str, language: str = "vi"
    ) -> TranscriptResult: ...


class PhoWhisperTranscriber:
    """Transcriber on-prem dùng faster-whisper (CTranslate2) + model PhoWhisper.

    Model nạp LAZY ở lần transcribe đầu (không chặn app boot). Construction luôn
    thành công kể cả khi chưa cài faster-whisper / chưa đặt VOICE_MODEL — lỗi chỉ
    nổ khi thực sự gọi transcribe(), kèm hướng dẫn cài rõ ràng.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        device: str = "auto",
        compute_type: str = "default",
    ) -> None:
        self._model_name = model or os.getenv(MODEL_ENV)
        self._device = device
        self._compute_type = compute_type
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not self._model_name:
            raise VoiceModelNotConfiguredError(
                f"Chưa đặt env {MODEL_ENV}. Trỏ tới thư mục model PhoWhisper (CT2) "
                "on-prem, ví dụ VOICE_MODEL=/opt/models/phowhisper-medium-ct2."
            )
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise VoiceModelNotInstalledError(
                "Chưa cài faster-whisper. On-prem (D011 — audio không rời PK): "
                "`pip install faster-whisper`, convert PhoWhisper sang CT2 bằng "
                "ct2-transformers-converter, rồi đặt VOICE_MODEL."
            ) from exc
        logger.info("voice_model_load", model=self._model_name, device=self._device)
        self._model = WhisperModel(
            self._model_name,
            device=self._device,
            compute_type=self._compute_type,
        )
        return self._model

    async def transcribe(
        self, audio_path: str, language: str = "vi"
    ) -> TranscriptResult:
        model = self._ensure_model()
        # faster-whisper là blocking → chạy trong thread để không chẹn event loop.
        return await asyncio.to_thread(self._run, model, audio_path, language)

    def _run(self, model: Any, audio_path: str, language: str) -> TranscriptResult:
        segments_iter, info = model.transcribe(
            audio_path, language=language, vad_filter=True
        )
        segs = [
            TranscriptSegment(
                start=float(s.start),
                end=float(s.end),
                text=(s.text or "").strip(),
            )
            for s in segments_iter
        ]
        text = " ".join(s.text for s in segs).strip()
        return TranscriptResult(
            text=text,
            language=str(getattr(info, "language", language)),
            model=self._model_name or "",
            duration_s=float(getattr(info, "duration", 0.0)),
            segments=segs,
        )
