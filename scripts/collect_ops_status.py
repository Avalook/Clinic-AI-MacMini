#!/usr/bin/env python3
"""Write a sanitized, one-way host status snapshot for the Ops Center."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SERVICE_IDS = (
    "api",
    "dashboard",
    "caddy",
    "worker",
    "notification-relay",
    "rabbitmq",
    "dozzle",
    "uptime-kuma",
)
CORE_SERVICES = frozenset({"api", "dashboard", "caddy"})
LOOPBACK_IPS = frozenset({"127.0.0.1", "::1"})


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def percent(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value.strip().rstrip("%")))
    except ValueError:
        return None


class Collector:
    def __init__(self, repo: Path, env_file: Path, project: str) -> None:
        self.repo = repo
        self.env_file = env_file
        self.project = project
        self.values = read_env(env_file)
        self.command_env = {**os.environ, "CLINIC_ENV_FILE": str(env_file)}
        self.compose = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-p",
            project,
        ]

    def container_id(self, service: str) -> str:
        lines = run(
            [*self.compose, "ps", "-q", service], env=self.command_env
        ).splitlines()
        return lines[0] if lines else ""

    def service_status(self, service: str) -> dict[str, Any]:
        container = self.container_id(service)
        if not container:
            return {
                "id": service,
                "state": "down" if service in CORE_SERVICES else "disabled",
                "restart_count": 0,
            }
        state = run(
            [
                "docker",
                "inspect",
                "--format",
                (
                    "{{if .State.Health}}{{.State.Health.Status}}"
                    "{{else}}{{.State.Status}}{{end}}"
                ),
                container,
            ]
        )
        restarts_raw = run(
            ["docker", "inspect", "--format", "{{.RestartCount}}", container]
        )
        state_value = "healthy" if state in {"healthy", "running"} else "down"
        item: dict[str, Any] = {
            "id": service,
            "state": state_value,
            "restart_count": int(restarts_raw) if restarts_raw.isdigit() else 0,
        }
        stats_raw = run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{json .}}",
                container,
            ]
        )
        try:
            stats = json.loads(stats_raw) if stats_raw else {}
        except json.JSONDecodeError:
            stats = {}
        cpu = percent(stats.get("CPUPerc"))
        memory = percent(stats.get("MemPerc"))
        if cpu is not None:
            item["cpu_percent"] = cpu
        if memory is not None:
            item["memory_percent"] = memory
        return item

    def host_published(self, service: str) -> bool:
        container = self.container_id(service)
        return bool(container and run(["docker", "port", container]))

    def dozzle_loopback_only(self) -> bool:
        container = self.container_id("dozzle")
        if not container:
            return True
        raw = run(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .HostConfig.PortBindings}}",
                container,
            ]
        )
        try:
            bindings = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False
        host_ips = {
            entry.get("HostIp", "")
            for entries in (bindings or {}).values()
            for entry in (entries or [])
        }
        return bool(host_ips) and host_ips.issubset(LOOPBACK_IPS)

    def disk_used_percent(self) -> float:
        raw = run(["df", "-Pk", "/"])
        lines = raw.splitlines()
        if len(lines) < 2:
            return 0.0
        columns = lines[-1].split()
        return percent(columns[4]) or 0.0

    def log_counts(self) -> dict[str, int]:
        warnings = 0
        errors = 0
        for service in ("api", "dashboard", "caddy"):
            container = self.container_id(service)
            if not container:
                continue
            output = run(["docker", "logs", "--since", "15m", container])
            for line in output.splitlines():
                try:
                    level = str(json.loads(line).get("level", "")).lower()
                except (json.JSONDecodeError, AttributeError):
                    level = ""
                if level in {"error", "fatal", "critical"}:
                    errors += 1
                elif level in {"warn", "warning"}:
                    warnings += 1
        return {"window_minutes": 15, "warnings": warnings, "errors": errors}

    def backup(self, status_dir: Path) -> dict[str, Any] | None:
        path = status_dir / "backup-status.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        allowed = {
            "completed_at": raw.get("completed_at"),
            "verified": raw.get("verified"),
            "archive_bytes": raw.get("archive_bytes"),
            "offsite_uploaded": raw.get("offsite_uploaded"),
            "scope": raw.get("scope"),
        }
        if (
            not isinstance(allowed["completed_at"], str)
            or allowed["verified"] is not True
            or not isinstance(allowed["archive_bytes"], int)
            or not isinstance(allowed["offsite_uploaded"], bool)
            or allowed["scope"] != "public-schema-only"
        ):
            return None
        return allowed

    def collect(self, status_dir: Path) -> dict[str, Any]:
        services = [self.service_status(service) for service in SERVICE_IDS]
        caddy_port = self.values.get("CADDY_HTTP_PORT", "80") or "80"
        funnel = run(["tailscale", "funnel", "status"])
        funnel_enabled = "Funnel on" in funnel
        funnel_targets_caddy = (
            not funnel_enabled or f"proxy http://127.0.0.1:{caddy_port}" in funnel
        )
        environment = self.values.get("APP_ENV", "")
        if environment not in {"production", "staging"}:
            environment = "staging"
        return {
            "format_version": 1,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "environment": environment,
            "services": services,
            "network": {
                "api_host_published": self.host_published("api"),
                "dashboard_host_published": self.host_published("dashboard"),
                "caddy_running": any(
                    item["id"] == "caddy" and item["state"] == "healthy"
                    for item in services
                ),
                "funnel_enabled": funnel_enabled,
                "funnel_targets_caddy": funnel_targets_caddy,
                "dozzle_loopback_only": self.dozzle_loopback_only(),
                "dozzle_auth_enabled": self.values.get("DOZZLE_AUTH_PROVIDER", "none")
                != "none",
            },
            "host": {"disk_used_percent": self.disk_used_percent()},
            "backup": self.backup(status_dir),
            "log_counts": self.log_counts(),
        }


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp_name = tempfile.mkstemp(prefix=".status.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "target", choices=("prod", "staging"), nargs="?", default="prod"
    )
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    repo = args.repo.resolve()
    env_file = repo / (".env.prod" if args.target == "prod" else ".env.staging")
    if not env_file.is_file() or not shutil.which("docker"):
        return 1
    values = read_env(env_file)
    configured_root = values.get("OPS_STATUS_DIR", "").strip()
    status_root = (
        Path(configured_root).expanduser()
        if configured_root
        else Path.home() / ".clinicai" / "ops"
    )
    if not status_root.is_absolute():
        status_root = repo / status_root
    environment = values.get("APP_ENV", "staging")
    status_dir = status_root / environment
    project = "clinicai_prod" if args.target == "prod" else "clinicai_staging"
    payload = Collector(repo, env_file, project).collect(status_dir)
    atomic_write(status_dir / "status.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
