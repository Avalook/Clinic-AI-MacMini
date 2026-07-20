"""Strict, sanitized schemas for the read-only operations dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ServiceState = Literal["healthy", "down", "disabled", "unknown"]
SnapshotState = Literal["fresh", "stale", "expired", "unknown", "invalid"]
FindingState = Literal["good", "warning", "critical", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HostServiceSnapshot(StrictModel):
    id: Literal[
        "api",
        "dashboard",
        "caddy",
        "worker",
        "notification-relay",
        "rabbitmq",
        "dozzle",
        "uptime-kuma",
    ]
    state: ServiceState
    restart_count: int = Field(ge=0, le=1_000_000)
    cpu_percent: float | None = Field(default=None, ge=0, le=100_000)
    memory_percent: float | None = Field(default=None, ge=0, le=100)


class NetworkSnapshot(StrictModel):
    api_host_published: bool
    dashboard_host_published: bool
    caddy_running: bool
    funnel_enabled: bool
    funnel_targets_caddy: bool
    dozzle_loopback_only: bool
    dozzle_auth_enabled: bool


class HostMetricsSnapshot(StrictModel):
    disk_used_percent: float = Field(ge=0, le=100)


class BackupSnapshot(StrictModel):
    completed_at: datetime
    verified: bool
    archive_bytes: int = Field(ge=0)
    offsite_uploaded: bool
    scope: Literal["public-schema-only"]


class LogCountsSnapshot(StrictModel):
    window_minutes: int = Field(ge=1, le=1_440)
    warnings: int = Field(ge=0)
    errors: int = Field(ge=0)


class OpsHostSnapshot(StrictModel):
    format_version: Literal[1]
    generated_at: datetime
    environment: Literal["production", "staging"]
    services: list[HostServiceSnapshot] = Field(max_length=16)
    network: NetworkSnapshot
    host: HostMetricsSnapshot
    backup: BackupSnapshot | None = None
    log_counts: LogCountsSnapshot


class LiveProbe(StrictModel):
    state: Literal["healthy", "down"]
    latency_ms: float | None = Field(default=None, ge=0)


class BackupStatus(StrictModel):
    state: Literal["fresh", "stale", "critical", "unknown"]
    completed_at: datetime | None = None
    age_hours: float | None = Field(default=None, ge=0)
    verified: bool | None = None
    archive_bytes: int | None = Field(default=None, ge=0)
    offsite_uploaded: bool | None = None
    scope: Literal["public-schema-only"] | None = None


class SecurityFinding(StrictModel):
    id: str = Field(max_length=64)
    label: str = Field(max_length=120)
    state: FindingState
    detail: str = Field(max_length=240)


class OpsStatusResponse(StrictModel):
    generated_at: datetime
    environment: Literal["production", "staging", "unknown"]
    overall: Literal["healthy", "degraded", "critical"]
    snapshot_state: SnapshotState
    snapshot_age_seconds: float | None = Field(default=None, ge=0)
    database: LiveProbe
    services: list[HostServiceSnapshot]
    host: HostMetricsSnapshot | None
    backup: BackupStatus
    security: list[SecurityFinding]
    log_counts: LogCountsSnapshot | None
