"""Voice-to-EMR transcription API (on-prem PhoWhisper).

POST /voice/transcribe (audio raw trong body) → transcript NHÁP tiếng Việt.

AN TOÀN: endpoint này CHỈ trả text nháp (`draft: true`). Nó KHÔNG ghi
clinical_record. Bác sĩ xem/sửa trong dashboard rồi LƯU qua /api/clinical-record
(đường có gate visit OPEN/IN_PROGRESS + người duyệt). Giữ voice ngoài write-path.

Audio gửi dưới dạng raw request body (không multipart → không cần python-multipart).
Đặt đuôi file qua query `?ext=wav|m4a|mp3` để faster-whisper/ffmpeg nhận đúng.
503 khi model chưa cài / chưa cấu hình on-prem (xem clinicai/voice/transcribe.py).
"""

from __future__ import annotations

import os
import tempfile
import time
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from clinicai.voice.transcribe import (
    Transcriber,
    VoiceModelNotConfiguredError,
    VoiceModelNotInstalledError,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


def get_transcriber(request: Request) -> Transcriber:
    """FastAPI dependency: yields the app's voice Transcriber singleton."""
    transcriber: Optional[Transcriber] = getattr(
        request.app.state, "voice_transcriber", None
    )
    if transcriber is None:
        raise HTTPException(
            status_code=503, detail="Voice transcriber chưa được khởi tạo."
        )
    return transcriber


class TranscriptSegmentOut(BaseModel):
    start: float
    end: float
    text: str


class TranscribeResponse(BaseModel):
    transcript: str
    language: str
    model: str
    duration_s: float
    segments: list[TranscriptSegmentOut]
    elapsed_ms: int
    # Luôn true: đây là NHÁP, bác sĩ phải duyệt trước khi vào hồ sơ.
    draft: bool = True


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    request: Request,
    transcriber: Annotated[Transcriber, Depends(get_transcriber)],
    ext: str = "wav",
    language: str = "vi",
) -> TranscribeResponse:
    """Nhận audio (raw body) → trả transcript NHÁP. KHÔNG ghi hồ sơ lâm sàng."""
    start = time.monotonic()
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Audio rỗng.")

    suffix = "." + ext.lstrip(".").lower()
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            result = await transcriber.transcribe(tmp_path, language=language)
        except (VoiceModelNotInstalledError, VoiceModelNotConfiguredError) as exc:
            logger.warning("voice_transcribe_unavailable", reason=str(exc))
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "voice_transcribe_ok",
        chars=len(result.text),
        duration_s=result.duration_s,
        elapsed_ms=elapsed_ms,
    )
    return TranscribeResponse(
        transcript=result.text,
        language=result.language,
        model=result.model,
        duration_s=result.duration_s,
        segments=[
            TranscriptSegmentOut(start=s.start, end=s.end, text=s.text)
            for s in result.segments
        ],
        elapsed_ms=elapsed_ms,
    )
