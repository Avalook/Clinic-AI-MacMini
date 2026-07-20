"""Tests for the sanitized, read-only operations snapshot service."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from clinicai.services.ops_status import OpsStatusService


class _Acquire:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def fetchval(self, _query: str) -> int:
        return 1


class _Pool:
    def acquire(self) -> _Acquire:
        return _Acquire()


def _snapshot(now: datetime) -> dict[str, object]:
    return {
        "format_version": 1,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "environment": "production",
        "services": [
            {"id": "api", "state": "healthy", "restart_count": 0},
            {"id": "dashboard", "state": "healthy", "restart_count": 0},
            {"id": "caddy", "state": "healthy", "restart_count": 0},
        ],
        "network": {
            "api_host_published": False,
            "dashboard_host_published": False,
            "caddy_running": True,
            "funnel_enabled": True,
            "funnel_targets_caddy": True,
            "dozzle_loopback_only": True,
            "dozzle_auth_enabled": True,
        },
        "host": {"disk_used_percent": 44.0},
        "backup": {
            "completed_at": (now - timedelta(hours=8))
            .isoformat()
            .replace("+00:00", "Z"),
            "verified": True,
            "archive_bytes": 123617,
            "offsite_uploaded": False,
            "scope": "public-schema-only",
        },
        "log_counts": {"window_minutes": 15, "warnings": 1, "errors": 0},
    }


@pytest.mark.asyncio
async def test_valid_snapshot_and_database_are_healthy(tmp_path: Path) -> None:
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps(_snapshot(now)))

    result = await OpsStatusService(_Pool(), status_file=status_file).collect(now=now)

    assert result.overall == "healthy"
    assert result.database.state == "healthy"
    assert result.database.latency_ms is not None
    assert result.backup.state == "fresh"
    assert all(item.state == "good" for item in result.security)


@pytest.mark.asyncio
async def test_missing_snapshot_degrades_without_throwing(tmp_path: Path) -> None:
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    result = await OpsStatusService(
        _Pool(), status_file=tmp_path / "missing.json"
    ).collect(now=now)

    assert result.overall == "degraded"
    assert result.snapshot_state == "unknown"
    assert result.database.state == "healthy"


@pytest.mark.asyncio
async def test_stale_snapshot_and_old_backup_raise_warnings(tmp_path: Path) -> None:
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    payload = _snapshot(now - timedelta(minutes=4))
    payload["backup"] = {
        "completed_at": (now - timedelta(hours=30)).isoformat().replace("+00:00", "Z"),
        "verified": True,
        "archive_bytes": 1000,
        "offsite_uploaded": False,
        "scope": "public-schema-only",
    }
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps(payload))

    result = await OpsStatusService(_Pool(), status_file=status_file).collect(now=now)

    assert result.snapshot_state == "stale"
    assert result.backup.state == "stale"
    assert result.overall == "degraded"


@pytest.mark.asyncio
async def test_unknown_fields_or_secrets_fail_closed(tmp_path: Path) -> None:
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    payload = _snapshot(now)
    payload["database_url"] = "postgresql://user:secret@private-host/db"
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps(payload))

    result = await OpsStatusService(_Pool(), status_file=status_file).collect(now=now)
    encoded = result.model_dump_json()

    assert result.snapshot_state == "invalid"
    assert "secret" not in encoded
    assert "private-host" not in encoded
