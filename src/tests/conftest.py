"""Root test conftest — DB-test isolation via DATABASE_URL_TEST.

Why this file exists
--------------------
DB-touching tests across the suite read ``DATABASE_URL`` directly (each module
calls ``load_dotenv()`` + ``os.getenv("DATABASE_URL")``). Without isolation,
a plain ``pytest`` run would pick up the prod ``DATABASE_URL`` from ``.env`` and
run DB tests against PRODUCTION — including integration tests that issue
unconditional ``DELETE FROM patient`` / ``appointment`` on the ``public`` schema.

This conftest forces an explicit opt-in: DB tests only ever connect to a
separate ``DATABASE_URL_TEST``. When it is unset we blank out ``DATABASE_URL``
(present-but-empty, so the per-module ``load_dotenv()`` cannot restore the prod
value) and every DB fixture hits its ``if not DATABASE_URL: pytest.skip`` guard.

Set a disposable test DB to actually run them:
    DATABASE_URL_TEST=postgresql://user:pass@host/dbname_test pytest -m db
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

# Loaded before any test module is imported, so the redirect below wins over
# each module's own load_dotenv() (override=False keeps an already-set key).
load_dotenv()

_TEST_DB_URL = os.environ.get("DATABASE_URL_TEST")
if _TEST_DB_URL:
    # Opt-in: point every DB fixture at the disposable test database.
    os.environ["DATABASE_URL"] = _TEST_DB_URL
else:
    # No test DB → blank (but PRESENT) so load_dotenv() won't restore prod and
    # DB fixtures skip cleanly. NEVER fall back to the prod DATABASE_URL.
    os.environ["DATABASE_URL"] = ""

# Same isolation for the API-key gate: if `.env` carries a real BACKEND_API_KEY,
# the api_key_middleware would 401 every endpoint unit test (they send no
# X-API-Key). Blank-but-PRESENT → middleware uses its dev fallback (allow), and
# load_dotenv(override=False) can't restore the prod key. Auth-specific tests
# still set their own key via monkeypatch.
os.environ["BACKEND_API_KEY"] = ""

# Fixtures that imply a live Postgres connection. Any test requesting one of
# these (or living under integration/) is tagged `db` for `-m "not db"`.
_DB_FIXTURES = {
    "temp_schema_db",
    "db_conn",
    "db_pool",
    "patient_service",
    "location_id",
    "service_type_id",
    "clean_db",
    "cleanup_patients",
    "async_client",
}
_DB_PATH_HINTS = ("/integration/", "test_checkpointer_postgres")


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Session-scoped test DB URL; skips the whole session when unset."""
    url = os.environ.get("DATABASE_URL_TEST")
    if not url:
        pytest.skip("DATABASE_URL_TEST not set")
    return url


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-tag DB-dependent tests with the `db` marker (no test edits needed)."""
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        fixturenames = set(getattr(item, "fixturenames", ()))
        if (fixturenames & _DB_FIXTURES) or any(
            hint in nodeid for hint in _DB_PATH_HINTS
        ):
            item.add_marker(pytest.mark.db)
