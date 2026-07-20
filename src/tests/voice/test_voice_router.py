"""Voice router test — app FastAPI tối giản (không lifespan/DB)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from clinicai.api.v1.routers.voice import get_transcriber, router
from clinicai.voice.transcribe import (
    TranscriptResult,
    TranscriptSegment,
    VoiceModelNotInstalledError,
)

_NOTE = "bệnh nhân đau bụng dưới ba ngày"


class _FakeTranscriber:
    async def transcribe(self, audio_path, language="vi"):
        return TranscriptResult(
            text=_NOTE,
            language=language,
            model="fake-phowhisper",
            duration_s=2.5,
            segments=[TranscriptSegment(start=0.0, end=2.5, text=_NOTE)],
        )


class _UnavailableTranscriber:
    async def transcribe(self, audio_path, language="vi"):
        raise VoiceModelNotInstalledError("chưa cài faster-whisper")


def _app(transcriber):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_transcriber] = lambda: transcriber
    return app


def test_transcribe_returns_draft_transcript():
    client = TestClient(_app(_FakeTranscriber()))
    resp = client.post("/api/v1/voice/transcribe", content=b"RIFFfakeaudio")
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == _NOTE
    assert body["draft"] is True  # luôn nháp — bác sĩ phải duyệt
    assert body["model"] == "fake-phowhisper"
    assert len(body["segments"]) == 1


def test_empty_body_rejected():
    client = TestClient(_app(_FakeTranscriber()))
    resp = client.post("/api/v1/voice/transcribe", content=b"")
    assert resp.status_code == 400


def test_model_unavailable_returns_503():
    client = TestClient(_app(_UnavailableTranscriber()))
    resp = client.post("/api/v1/voice/transcribe", content=b"RIFFfakeaudio")
    assert resp.status_code == 503
