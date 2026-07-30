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
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from clinicai.api.identity import (
    CLINICAL_WRITE_ROLES,
    StaffIdentity,
    require_role,
)
from clinicai.api.rate_limit import InMemoryRateLimiter
from clinicai.voice.transcribe import (
    Transcriber,
    VoiceModelNotConfiguredError,
    VoiceModelNotInstalledError,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])
MAX_AUDIO_BYTES = 25 * 1024 * 1024
_ALLOWED_AUDIO_TYPES: dict[str, frozenset[str]] = {
    "wav": frozenset({"audio/wav", "audio/x-wav", "audio/wave"}),
    "mp3": frozenset({"audio/mpeg", "audio/mp3"}),
    "m4a": frozenset({"audio/mp4", "audio/m4a", "audio/x-m4a"}),
}
_VOICE_GUARD = require_role(*CLINICAL_WRITE_ROLES)
VOICE_RATE_LIMIT = InMemoryRateLimiter(
    scope="voice-transcribe",
    limit=10,
    window_seconds=60,
)


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


def _validated_extension_and_mime(request: Request, ext: str) -> str:
    normalized_ext = ext.lstrip(".").lower()
    allowed_mime_types = _ALLOWED_AUDIO_TYPES.get(normalized_ext)
    supplied_mime = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if allowed_mime_types is None or supplied_mime not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=("Chỉ chấp nhận WAV, MP3 hoặc M4A với Content-Type tương ứng."),
        )
    return normalized_ext


async def _read_limited_audio(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content-Length không hợp lệ.",
            ) from None
        if declared_size < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content-Length không hợp lệ.",
            )
        if declared_size > MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Audio vượt quá giới hạn {MAX_AUDIO_BYTES} byte.",
            )

    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        received += len(chunk)
        if received > MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Audio vượt quá giới hạn {MAX_AUDIO_BYTES} byte.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    request: Request,
    transcriber: Annotated[Transcriber, Depends(get_transcriber)],
    _identity: Annotated[StaffIdentity, Depends(_VOICE_GUARD)],
    _rate_limit: Annotated[None, Depends(VOICE_RATE_LIMIT)],
    ext: str = "wav",
    language: str = "vi",
) -> TranscribeResponse:
    """Nhận audio (raw body) → trả transcript NHÁP. KHÔNG ghi hồ sơ lâm sàng."""
    start = time.monotonic()
    normalized_ext = _validated_extension_and_mime(request, ext)
    data = await _read_limited_audio(request)
    if not data:
        raise HTTPException(status_code=400, detail="Audio rỗng.")

    suffix = "." + normalized_ext
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
