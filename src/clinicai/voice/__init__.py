"""Voice-to-EMR (on-prem, tiếng Việt) — PhoWhisper."""

from clinicai.voice.transcribe import (
    PhoWhisperTranscriber,
    Transcriber,
    TranscriptResult,
    TranscriptSegment,
    VoiceModelNotConfiguredError,
    VoiceModelNotInstalledError,
)

__all__ = [
    "PhoWhisperTranscriber",
    "Transcriber",
    "TranscriptResult",
    "TranscriptSegment",
    "VoiceModelNotConfiguredError",
    "VoiceModelNotInstalledError",
]
