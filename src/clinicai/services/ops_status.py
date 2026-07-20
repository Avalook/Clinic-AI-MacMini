"""Merge live DB readiness with a one-way, sanitized host snapshot."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import asyncpg
from pydantic import ValidationError

from clinicai.schemas.ops import (
    BackupStatus,
    LiveProbe,
    OpsHostSnapshot,
    OpsStatusResponse,
    SecurityFinding,
    SnapshotState,
)

OverallState = Literal["healthy", "degraded", "critical"]
BackupState = Literal["fresh", "stale", "critical", "unknown"]
FindingState = Literal["good", "warning", "critical", "unknown"]

_MAX_SNAPSHOT_BYTES = 256 * 1024
_SNAPSHOT_STALE_SECONDS = 180
_SNAPSHOT_EXPIRED_SECONDS = 600
_BACKUP_STALE_HOURS = 26
_BACKUP_CRITICAL_HOURS = 48


class OpsStatusService:
    """Read-only status collection. Raw errors and snapshot fields never escape."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        status_file: str | Path | None = None,
    ) -> None:
        self._pool = pool
        resolved_status_file: str | Path = (
            status_file
            if status_file is not None
            else os.environ.get("OPS_STATUS_FILE") or "/run/clinicai-ops/status.json"
        )
        self._status_file = Path(resolved_status_file)

    async def collect(self, *, now: datetime | None = None) -> OpsStatusResponse:
        observed_at = now or datetime.now(UTC)
        snapshot, snapshot_state, snapshot_age = await self._read_snapshot(observed_at)
        database = await self._probe_database()

        backup = self._backup_status(snapshot, observed_at)
        security = self._security_findings(snapshot)
        overall = self._overall(snapshot, snapshot_state, database, backup, security)

        return OpsStatusResponse(
            generated_at=observed_at,
            environment=snapshot.environment if snapshot else "unknown",
            overall=overall,
            snapshot_state=snapshot_state,
            snapshot_age_seconds=snapshot_age,
            database=database,
            services=list(snapshot.services) if snapshot else [],
            host=snapshot.host if snapshot else None,
            backup=backup,
            security=security,
            log_counts=snapshot.log_counts if snapshot else None,
        )

    async def _read_snapshot(
        self, now: datetime
    ) -> tuple[OpsHostSnapshot | None, SnapshotState, float | None]:
        try:
            raw = await asyncio.to_thread(self._read_bounded_file)
            snapshot = OpsHostSnapshot.model_validate(json.loads(raw))
        except FileNotFoundError:
            return None, "unknown", None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            return None, "invalid", None

        generated_at = snapshot.generated_at
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=UTC)
        age = max(0.0, (now - generated_at.astimezone(UTC)).total_seconds())
        if age > _SNAPSHOT_EXPIRED_SECONDS:
            state: SnapshotState = "expired"
        elif age > _SNAPSHOT_STALE_SECONDS:
            state = "stale"
        else:
            state = "fresh"
        return snapshot, state, round(age, 1)

    def _read_bounded_file(self) -> str:
        stat = self._status_file.stat()
        if stat.st_size > _MAX_SNAPSHOT_BYTES:
            raise OSError("snapshot exceeds size limit")
        return self._status_file.read_text(encoding="utf-8")

    async def _probe_database(self) -> LiveProbe:
        started = time.perf_counter()
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception:
            return LiveProbe(state="down")
        latency = round((time.perf_counter() - started) * 1000, 2)
        return LiveProbe(state="healthy", latency_ms=latency)

    @staticmethod
    def _backup_status(snapshot: OpsHostSnapshot | None, now: datetime) -> BackupStatus:
        if snapshot is None or snapshot.backup is None:
            return BackupStatus(state="unknown")
        item = snapshot.backup
        completed_at = item.completed_at
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=UTC)
        age_hours = max(
            0.0, (now - completed_at.astimezone(UTC)).total_seconds() / 3600
        )
        if not item.verified or age_hours > _BACKUP_CRITICAL_HOURS:
            state: BackupState = "critical"
        elif age_hours > _BACKUP_STALE_HOURS:
            state = "stale"
        else:
            state = "fresh"
        return BackupStatus(
            state=state,
            completed_at=completed_at,
            age_hours=round(age_hours, 1),
            verified=item.verified,
            archive_bytes=item.archive_bytes,
            offsite_uploaded=item.offsite_uploaded,
            scope=item.scope,
        )

    @staticmethod
    def _security_findings(
        snapshot: OpsHostSnapshot | None,
    ) -> list[SecurityFinding]:
        if snapshot is None:
            return [
                SecurityFinding(
                    id="host-snapshot",
                    label="Kiểm tra host",
                    state="unknown",
                    detail=(
                        "Chưa có snapshot host hợp lệ; "
                        "không giả định hệ thống đang an toàn."
                    ),
                )
            ]

        network = snapshot.network
        ingress_good = (
            not network.api_host_published
            and not network.dashboard_host_published
            and network.caddy_running
        )
        funnel_good = not network.funnel_enabled or network.funnel_targets_caddy
        dozzle_state: FindingState = (
            "critical"
            if not network.dozzle_loopback_only
            else ("good" if network.dozzle_auth_enabled else "warning")
        )
        return [
            SecurityFinding(
                id="ingress",
                label="Ingress ứng dụng",
                state="good" if ingress_good else "critical",
                detail=(
                    "API và dashboard không publish trực tiếp ra host."
                    if ingress_good
                    else "API/dashboard đang bypass Caddy hoặc Caddy không chạy."
                ),
            ),
            SecurityFinding(
                id="funnel",
                label="Tailscale Funnel",
                state="good" if funnel_good else "critical",
                detail=(
                    "Funnel tắt hoặc đang trỏ đúng vào Caddy."
                    if funnel_good
                    else "Funnel đang bỏ qua Caddy."
                ),
            ),
            SecurityFinding(
                id="dozzle",
                label="Bảo vệ log",
                state=dozzle_state,
                detail=(
                    "Dozzle giới hạn loopback và đã bật xác thực."
                    if dozzle_state == "good"
                    else (
                        "Dozzle chỉ ở loopback nhưng chưa bật xác thực riêng."
                        if dozzle_state == "warning"
                        else "Dozzle có thể truy cập ngoài loopback."
                    )
                ),
            ),
        ]

    @staticmethod
    def _overall(
        snapshot: OpsHostSnapshot | None,
        snapshot_state: SnapshotState,
        database: LiveProbe,
        backup: BackupStatus,
        security: list[SecurityFinding],
    ) -> OverallState:
        if database.state == "down":
            return "critical"
        if any(item.state == "critical" for item in security):
            return "critical"
        if snapshot and any(
            item.id in {"api", "dashboard", "caddy"} and item.state == "down"
            for item in snapshot.services
        ):
            return "critical"
        if (
            snapshot_state != "fresh"
            or backup.state != "fresh"
            or any(item.state != "good" for item in security)
        ):
            return "degraded"
        return "healthy"
