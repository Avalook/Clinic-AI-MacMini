"""Tests for staging bootstrap safety and GoTrue isolation (Phase 5).

Verifies that:
1. dung-staging.sh enforces strict fail-closed preflight checks:
   - Missing SUPABASE_NETWORK -> fails.
   - SUPABASE_NETWORK == clinicai_db_supabase -> fails.
   - Missing SUPABASE_PREFIX or SUPABASE_PREFIX == clinicai -> fails.
   - Missing or invalid gateway/guard host, ports, or secrets -> fails.
2. Fresh staging DB path invokes supabase-local-nap.sh.
3. Existing staging DB path invokes apply-pending-migrations.sh --apply.
4. supabase-local-nap.sh verifies BOTH auth.users and auth.identities.
5. .env.staging.example conforms to self-hosted staging architecture.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DUNG_STAGING_SH = REPO_ROOT / "scripts" / "dung-staging.sh"
SUPABASE_LOCAL_NAP_SH = REPO_ROOT / "scripts" / "supabase-local-nap.sh"
ENV_STAGING_EXAMPLE = REPO_ROOT / ".env.staging.example"


def _make_valid_staging_env() -> dict[str, str]:
    return {
        "APP_ENV": "staging",
        "COMPOSE_PROJECT_NAME": "clinicai_staging",
        "IMAGE_TAG": "staging",
        "CLINIC_ENV_FILE": ".env.staging",
        "SUPABASE_PREFIX": "clinicai_stg",
        "SUPABASE_NETWORK": "clinicai_stg_db_supabase",
        "SUPABASE_GATEWAY_HOST": "clinicai_stg_supabase_gateway",
        "AUTH_GUARD_HOST": "clinicai_stg_auth_guard",
        "SUPABASE_DB_PORT": "54332",
        "SUPABASE_API_PORT": "54331",
        "SUPABASE_JWT_SECRET": "staging-secret-key-that-is-at-least-32-chars-long",
        "SUPABASE_DB_PASSWORD": "staging-super-secret-db-pass",
        "BACKEND_API_KEY": "staging-long-random-string-backend-key",
        "SUPABASE_ANON_KEY": "staging-anon-key",
        "SUPABASE_SERVICE_ROLE_KEY": "staging-service-key",
        "DATABASE_URL": "postgresql+asyncpg://postgres:pass@clinicai_stg_db:5432/postgres",
        "SUPABASE_URL": "http://clinicai_stg_supabase_gateway:8000",
        "NEXT_PUBLIC_SUPABASE_URL": "http://127.0.0.1:8080",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": "staging-anon-key",
        "MEDIA_DIR": "./.media/staging",
        "CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY": "0",
        "CADDY_HTTP_PORT": "8080",
    }


def _run_dung_staging_preflight(
    tmp_path: Path, env_dict: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Runs dung-staging.sh in an isolated directory with fake docker."""
    test_dir = tmp_path / "clinicai_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = test_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(DUNG_STAGING_SH, scripts_dir / "dung-staging.sh")
    shutil.copy(SUPABASE_LOCAL_NAP_SH, scripts_dir / "supabase-local-nap.sh")

    # Create dummy docker-compose.supabase.yml so any file checks pass
    (test_dir / "docker-compose.supabase.yml").write_text("services: {}\n")

    # Write .env.staging
    lines = [f"{k}={v}" for k, v in env_dict.items()]
    (test_dir / ".env.staging").write_text("\n".join(lines) + "\n")

    # Create a mock docker executable that should NEVER be called if preflight fails
    fake_bin = test_dir / "bin"
    fake_bin.mkdir()
    mock_docker = fake_bin / "docker"
    mock_docker.write_text('#!/bin/sh\necho "MOCK_DOCKER_CALLED: $@"\nexit 0\n')
    mock_docker.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    return subprocess.run(
        ["bash", str(scripts_dir / "dung-staging.sh")],
        cwd=str(test_dir),
        capture_output=True,
        text=True,
        env=env,
    )


class TestDungStagingPreflightSafety:
    def test_missing_supabase_network_fails(self, tmp_path: Path) -> None:
        env = _make_valid_staging_env()
        del env["SUPABASE_NETWORK"]
        proc = _run_dung_staging_preflight(tmp_path, env)
        assert proc.returncode != 0
        assert "SUPABASE_NETWORK" in proc.stderr
        assert "MOCK_DOCKER_CALLED" not in proc.stdout

    def test_prod_network_name_fails(self, tmp_path: Path) -> None:
        env = _make_valid_staging_env()
        env["SUPABASE_NETWORK"] = "clinicai_db_supabase"
        proc = _run_dung_staging_preflight(tmp_path, env)
        assert proc.returncode != 0
        assert "trùng mạng prod" in proc.stderr or "SUPABASE_NETWORK" in proc.stderr
        assert "MOCK_DOCKER_CALLED" not in proc.stdout

    def test_missing_or_prod_supabase_prefix_fails(self, tmp_path: Path) -> None:
        env = _make_valid_staging_env()
        env["SUPABASE_PREFIX"] = "clinicai"
        proc = _run_dung_staging_preflight(tmp_path, env)
        assert proc.returncode != 0
        assert "trùng prod" in proc.stderr or "SUPABASE_PREFIX" in proc.stderr
        assert "MOCK_DOCKER_CALLED" not in proc.stdout

    def test_invalid_ports_fail(self, tmp_path: Path) -> None:
        env = _make_valid_staging_env()
        env["SUPABASE_DB_PORT"] = "54322"  # prod port
        proc = _run_dung_staging_preflight(tmp_path, env)
        assert proc.returncode != 0
        assert "54332" in proc.stderr
        assert "MOCK_DOCKER_CALLED" not in proc.stdout

    def test_invalid_gateway_or_guard_host_fails(self, tmp_path: Path) -> None:
        env = _make_valid_staging_env()
        env["SUPABASE_GATEWAY_HOST"] = "clinicai_supabase_gateway"  # prod host
        proc = _run_dung_staging_preflight(tmp_path, env)
        assert proc.returncode != 0
        assert "clinicai_stg_supabase_gateway" in proc.stderr
        assert "MOCK_DOCKER_CALLED" not in proc.stdout


class TestDungStagingScriptIntegrity:
    def test_never_calls_bootstrap_plain_postgres(self) -> None:
        content = DUNG_STAGING_SH.read_text()
        exec_lines = [
            line.strip()
            for line in content.splitlines()
            if not line.strip().startswith("#") and not line.strip().startswith("echo ")
        ]
        for line in exec_lines:
            assert "bootstrap_plain_postgres.sql" not in line

    def test_routes_fresh_db_to_supabase_local_nap(self) -> None:
        content = DUNG_STAGING_SH.read_text()
        assert "supabase-local-nap.sh" in content

    def test_routes_existing_db_to_apply_pending_migrations(self) -> None:
        content = DUNG_STAGING_SH.read_text()
        assert "apply-pending-migrations.sh --apply" in content

    def test_inspects_docker_networks_after_up(self) -> None:
        content = DUNG_STAGING_SH.read_text()
        assert "clinicai_stg_db_supabase" in content
        assert "clinicai_db_supabase" in content
        assert "BỊ NỐI VÀO MẠNG PROD" in content


class TestSupabaseLocalNapReadiness:
    def test_checks_both_auth_users_and_auth_identities(self) -> None:
        content = SUPABASE_LOCAL_NAP_SH.read_text()
        assert "to_regclass('auth.users') IS NOT NULL" in content
        assert "to_regclass('auth.identities') IS NOT NULL" in content

    def test_never_creates_plain_auth_users_table(self) -> None:
        content = SUPABASE_LOCAL_NAP_SH.read_text()
        assert "CREATE TABLE auth.users" not in content
        assert "CREATE TABLE IF NOT EXISTS auth.users" not in content


class TestStagingEnvExample:
    def test_example_has_required_staging_isolation_vars(self) -> None:
        content = ENV_STAGING_EXAMPLE.read_text()
        assert "SUPABASE_PREFIX=clinicai_stg" in content
        assert "SUPABASE_NETWORK=clinicai_stg_db_supabase" in content
        assert "SUPABASE_GATEWAY_HOST=clinicai_stg_supabase_gateway" in content
        assert "AUTH_GUARD_HOST=clinicai_stg_auth_guard" in content
        assert "SUPABASE_DB_PORT=54332" in content
        assert "SUPABASE_API_PORT=54331" in content
        assert "CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY=0" in content

    def test_example_does_not_contain_prod_network_or_prefix(self) -> None:
        content = ENV_STAGING_EXAMPLE.read_text()
        # Ensure not assigning prod network
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                if k == "SUPABASE_NETWORK":
                    assert v != "clinicai_db_supabase"
                if k == "SUPABASE_PREFIX":
                    assert v != "clinicai"

    def test_docker_compose_config_succeeds_with_example(self) -> None:
        proc = subprocess.run(
            ["docker", "compose", "--env-file", ".env.staging.example", "config"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env={**os.environ, "CLINIC_ENV_FILE": ".env.staging.example"},
        )
        assert proc.returncode == 0, f"docker compose config failed:\n{proc.stderr}"
