"""Voice router test — app FastAPI tối giản (không lifespan/DB)."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import clinicai.api.v1.routers.voice as voice_router
from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.api.v1.routers.voice import (
    VOICE_RATE_LIMIT,
    get_transcriber,
    router,
)
from clinicai.voice.transcribe import (
    TranscriptResult,
    TranscriptSegment,
    VoiceModelNotInstalledError,
)

_NOTE = "bệnh nhân đau bụng dưới ba ngày"


class _FakeTranscriber:
    async def transcribe(
        self, audio_path: str, language: str = "vi"
    ) -> TranscriptResult:
        return TranscriptResult(
            text=_NOTE,
            language=language,
            model="fake-phowhisper",
            duration_s=2.5,
            segments=[TranscriptSegment(start=0.0, end=2.5, text=_NOTE)],
        )


class _UnavailableTranscriber:
    async def transcribe(self, audio_path: str, language: str = "vi") -> None:
        raise VoiceModelNotInstalledError("chưa cài faster-whisper")


def _identity(role: ClinicRole = ClinicRole.DOCTOR) -> StaffIdentity:
    return StaffIdentity(
        staff_id="staff-voice",
        auth_user_id="auth-voice",
        full_name="Test Doctor",
        department=role.value,
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def _app(transcriber: object, role: ClinicRole = ClinicRole.DOCTOR) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_transcriber] = lambda: transcriber
    app.dependency_overrides[get_current_identity] = lambda: _identity(role)
    return app


@pytest.fixture(autouse=True)
def _reset_voice_rate_limit() -> Iterator[None]:
    VOICE_RATE_LIMIT.reset()
    yield
    VOICE_RATE_LIMIT.reset()


def test_transcribe_returns_draft_transcript() -> None:
    client = TestClient(_app(_FakeTranscriber()))
    resp = client.post(
        "/api/v1/voice/transcribe",
        content=b"RIFFfakeaudio",
        headers={"Content-Type": "audio/wav"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == _NOTE
    assert body["draft"] is True  # luôn nháp — bác sĩ phải duyệt
    assert body["model"] == "fake-phowhisper"
    assert len(body["segments"]) == 1


def test_empty_body_rejected() -> None:
    client = TestClient(_app(_FakeTranscriber()))
    resp = client.post(
        "/api/v1/voice/transcribe",
        content=b"",
        headers={"Content-Type": "audio/wav"},
    )
    assert resp.status_code == 400


def test_model_unavailable_returns_503() -> None:
    client = TestClient(_app(_UnavailableTranscriber()))
    resp = client.post(
        "/api/v1/voice/transcribe",
        content=b"RIFFfakeaudio",
        headers={"Content-Type": "audio/wav"},
    )
    assert resp.status_code == 503


def test_reception_cannot_use_voice_transcription() -> None:
    client = TestClient(_app(_FakeTranscriber(), ClinicRole.RECEPTION))
    resp = client.post(
        "/api/v1/voice/transcribe",
        content=b"RIFFfakeaudio",
        headers={"Content-Type": "audio/wav"},
    )
    assert resp.status_code == 403


@pytest.mark.parametrize(
    ("ext", "content_type"),
    [
        ("exe", "audio/wav"),
        ("wav", "application/octet-stream"),
        ("mp3", "audio/wav"),
    ],
)
def test_unsupported_or_mismatched_audio_type_is_rejected(
    ext: str, content_type: str
) -> None:
    client = TestClient(_app(_FakeTranscriber()))
    resp = client.post(
        f"/api/v1/voice/transcribe?ext={ext}",
        content=b"fakeaudio",
        headers={"Content-Type": content_type},
    )
    assert resp.status_code == 415


def test_content_length_above_limit_is_rejected_before_transcription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(voice_router, "MAX_AUDIO_BYTES", 8)
    client = TestClient(_app(_FakeTranscriber()))

    resp = client.post(
        "/api/v1/voice/transcribe",
        content=b"123456789",
        headers={"Content-Type": "audio/wav"},
    )

    assert resp.status_code == 413


def test_streamed_body_above_limit_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(voice_router, "MAX_AUDIO_BYTES", 8)
    client = TestClient(_app(_FakeTranscriber()))

    resp = client.post(
        "/api/v1/voice/transcribe",
        content=(chunk for chunk in (b"1234", b"56789")),
        headers={"Content-Type": "audio/wav"},
    )

    assert resp.status_code == 413
