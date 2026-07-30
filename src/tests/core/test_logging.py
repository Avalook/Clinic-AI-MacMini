"""Regression tests for the production log PII/secret scrubber."""

from __future__ import annotations

from clinicai.core.logging import REDACTED, redact_sensitive_data


def test_redacts_sensitive_keys_recursively_without_mutating_input() -> None:
    original = {
        "event": "notification_failed",
        "phone": "0901234567",
        "nested": {
            "email": "patient@example.com",
            "message_preview": "Em dang dau bung",
        },
        "items": [{"authorization": "Bearer secret-token"}],
    }

    scrubbed = redact_sensitive_data(None, "info", original)

    assert scrubbed == {
        "event": "notification_failed",
        "phone": REDACTED,
        "nested": {"email": REDACTED, "message_preview": REDACTED},
        "items": [{"authorization": REDACTED}],
    }
    assert original["phone"] == "0901234567"
    nested = original["nested"]
    assert isinstance(nested, dict)
    assert nested["email"] == "patient@example.com"


def test_redacts_email_phone_and_bearer_token_embedded_in_error_text() -> None:
    scrubbed = redact_sensitive_data(
        None,
        "error",
        {
            "event": "provider_error",
            "error": (
                "contact patient@example.com / +84 901 234 567; "
                "Authorization: Bearer abc.def-123"
            ),
        },
    )

    error = scrubbed["error"]
    assert "patient@example.com" not in error
    assert "+84 901 234 567" not in error
    assert "abc.def-123" not in error
    assert error.count(REDACTED) == 3


def test_preserves_operational_event_and_non_sensitive_dimensions() -> None:
    scrubbed = redact_sensitive_data(
        None,
        "info",
        {
            "event": "llm_call",
            "trace_id": "761ea09b-902f-43ee-8e7b-b3ea1b344053",
            "model": "claude-sonnet",
            "input_tokens": 42,
        },
    )

    assert scrubbed["event"] == "llm_call"
    assert scrubbed["model"] == "claude-sonnet"
    assert scrubbed["input_tokens"] == 42


def test_scrubs_contact_data_even_when_stdlib_log_message_becomes_event() -> None:
    scrubbed = redact_sensitive_data(
        None,
        "warning",
        {"event": "Could not notify patient@example.com at 0901234567"},
    )

    assert scrubbed["event"] == f"Could not notify {REDACTED} at {REDACTED}"
