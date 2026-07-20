import sys

import pytest

from clinicai.voice.transcribe import (
    PhoWhisperTranscriber,
    TranscriptResult,
    TranscriptSegment,
    VoiceModelNotConfiguredError,
    VoiceModelNotInstalledError,
)


def test_transcript_result_shape():
    seg = TranscriptSegment(start=0.0, end=1.2, text="xin chào")
    res = TranscriptResult(
        text="xin chào",
        language="vi",
        model="phowhisper",
        duration_s=1.2,
        segments=[seg],
    )
    assert res.segments[0].text == "xin chào"
    assert res.language == "vi"


def test_construction_succeeds_without_deps(monkeypatch):
    """Construct luôn OK (model lazy) — không chặn app boot."""
    monkeypatch.delenv("VOICE_MODEL", raising=False)
    t = PhoWhisperTranscriber()
    assert t is not None


@pytest.mark.asyncio
async def test_transcribe_raises_when_model_not_configured(monkeypatch):
    monkeypatch.delenv("VOICE_MODEL", raising=False)
    t = PhoWhisperTranscriber()
    with pytest.raises(VoiceModelNotConfiguredError):
        await t.transcribe("dummy.wav")


@pytest.mark.asyncio
async def test_transcribe_raises_when_faster_whisper_missing(monkeypatch):
    """Có VOICE_MODEL nhưng faster-whisper chưa cài → lỗi rõ ràng."""
    monkeypatch.setenv("VOICE_MODEL", "/opt/models/phowhisper-medium-ct2")
    # Ép import faster_whisper thất bại bất kể env thật có cài hay không.
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    t = PhoWhisperTranscriber()
    with pytest.raises(VoiceModelNotInstalledError):
        await t.transcribe("dummy.wav")
