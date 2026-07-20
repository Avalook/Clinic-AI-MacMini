"""Map (preferred_time, weekday_flag) → session_type string.

Dr4Women business rule (D-xxx in 06_HARD_DECISIONS_AND_STYLE.md):
- Weekday (Mon-Fri) only has EVENING sessions.
- Weekend (Sat-Sun) only has WEEKEND_MORNING and WEEKEND_AFTERNOON sessions.
- Any other (preferred_time, weekday) combination is invalid and returns None
  so the sub-graph can ask the user to pick a different time/date.
"""

from __future__ import annotations

from datetime import date as date_type

_WEEKDAY_MAP = {
    "morning": None,
    "afternoon": None,
    "evening": "EVENING",
}

_WEEKEND_MAP = {
    "morning": "WEEKEND_MORNING",
    "afternoon": "WEEKEND_AFTERNOON",
    "evening": None,
}


def map_to_session_type(
    preferred_time: str | None,
    session_date: date_type,
) -> str | None:
    """Translate (preferred_time, date) into a SessionType enum string.

    Returns None when the combination has no matching session offering.
    """
    if preferred_time is None:
        return None
    is_weekend = session_date.weekday() >= 5
    mapping = _WEEKEND_MAP if is_weekend else _WEEKDAY_MAP
    return mapping.get(preferred_time)
