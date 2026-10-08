"""Staging online (01/10/2026) — các chốt bảo vệ PROD của script staging.

Thay bộ test cũ của scripts/dung-staging.sh (đã gỡ: staging dữ liệu thử, cổng
8080 trần). Staging mới chạy CHUNG VPS prod nên chốt quan trọng hơn:

1. scripts/lib/staging-chung.sh — kiem_env_staging / kiem_ten_staging dừng khi
   thấy tên, mạng, cổng, bí mật của PROD hoặc khoá gửi tin thật.
2. kiem_tai_nguyen — prod đang deploy (khoá /tmp/clinicai-deploy.lock) thì
   staging NHƯỜNG; đĩa thiếu thì không dựng.
3. deploy-staging.sh / staging-nap-ban-sao.sh dừng TRƯỚC mọi lệnh docker khi
   chốt hỏng (docker giả ghi lại mọi lần bị gọi).
4. Caddy prod chỉ biết MỘT tên của staging (clinicai-staging-cong), site phụ
   nạp qua `import` thư mục; Caddyfile staging không bao giờ rơi về tên prod.
5. .env.staging.example dựng được bằng compose.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "lib" / "staging-chung.sh"
ENV_STAGING_EXAMPLE = REPO / ".env.staging.example"
CADDYFILE_STAGING = REPO / "caddy" / "Caddyfile.staging"


def _env_hop_le() -> dict[str, str]:
    return {
        "APP_ENV": "staging",
        "COMPOSE_PROJECT_NAME": "clinicai_staging",
        "IMAGE_TAG": "staging",
        "SUPABASE_PREFIX": "clinicai_stg",
        "SUPABASE_NETWORK": "clinicai_stg_db_supabase",
        "SUPABASE_GATEWAY_HOST": "clinicai_stg_supabase_gateway",
        "AUTH_GUARD_HOST": "clinicai_stg_auth_guard",
        "SUPABASE_DB_PORT": "54332",
        "SUPABASE_API_PORT": "54331",
        "SUPABASE_JWT_SECRET": "staging-secret-dai-hon-32-ky-tu-cho-chac-an",
        "SUPABASE_DB_PASSWORD": "staging-db-pass",
        "BACKEND_API_KEY": "staging-backend-key",
        "SUPABASE_ANON_KEY": "staging-anon",
        "SUPABASE_SERVICE_ROLE_KEY": "staging-service",
        "DATABASE_URL": "postgresql+asyncpg://postgres:x@clinicai_stg_db:5432/postgres",
        "ANTHROPIC_API_KEY": "sk-staging-khong-phai-khoa-that",
        "POS_ADAPTER": "none",
    }


def _ghi_env(thu_muc: Path, env: dict[str, str]) -> Path:
    f = thu_muc / ".env.staging"
    f.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
    return f


def _goi_lib(
    tmp_path: Path,
    ham: str,
    env: dict[str, str] | None = None,
    them: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    f = _ghi_env(tmp_path, env if env is not None else _env_hop_le())
    moi_truong = {
        **os.environ,
        "STAGING_DIR": str(tmp_path),
        "STAGING_ENV_FILE": str(f),
        "PROD_DIR": str(tmp_path / "prod"),
        "PROD_DEPLOY_LOCK": str(tmp_path / "prod.lock"),
        **(them or {}),
    }
    return subprocess.run(
        ["bash", "-c", f'. "{LIB}"; {ham}'],
        capture_output=True,
        text=True,
        env=moi_truong,
    )


class TestChotEnv:
    def test_env_hop_le_qua(self, tmp_path: Path) -> None:
        r = _goi_lib(tmp_path, "kiem_ten_staging && kiem_env_staging && echo QUA")
        assert r.returncode == 0, r.stderr
        assert "QUA" in r.stdout

    @pytest.mark.parametrize(
        ("khoa", "gia_tri", "bao"),
        [
            ("SUPABASE_NETWORK", "clinicai_db_supabase", "SUPABASE_NETWORK"),
            ("SUPABASE_PREFIX", "clinicai", "SUPABASE_PREFIX"),
            (
                "SUPABASE_GATEWAY_HOST",
                "clinicai_supabase_gateway",
                "SUPABASE_GATEWAY_HOST",
            ),
            ("AUTH_GUARD_HOST", "clinicai_auth_guard", "AUTH_GUARD_HOST"),
            ("SUPABASE_DB_PORT", "54322", "SUPABASE_DB_PORT"),
            ("IMAGE_TAG", "prod", "IMAGE_TAG"),
            ("APP_ENV", "production", "APP_ENV"),
            (
                "DATABASE_URL",
                "postgresql://postgres:x@clinicai_db:5432/postgres",
                "DATABASE_URL",
            ),
            ("TELEGRAM_BOT_TOKEN", "123:abc", "TELEGRAM_BOT_TOKEN"),
            ("ZALO_ZNS_ACCESS_TOKEN", "that", "ZALO_ZNS_ACCESS_TOKEN"),
            ("POS_ADAPTER", "kiotviet", "POS_ADAPTER"),
            ("ANTHROPIC_API_KEY", "sk-ant-api03-that", "ANTHROPIC_API_KEY"),
            ("NOTIFICATION_RELAY_ENABLED", "true", "NOTIFICATION_RELAY_ENABLED"),
        ],
    )
    def test_ten_prod_hoac_khoa_that_bi_chan(
        self, tmp_path: Path, khoa: str, gia_tri: str, bao: str
    ) -> None:
        env = _env_hop_le()
        env[khoa] = gia_tri
        r = _goi_lib(tmp_path, "kiem_env_staging && echo QUA", env)
        assert r.returncode != 0
        assert bao in r.stderr
        assert "QUA" not in r.stdout

    def test_bi_mat_trung_prod_bi_chan(self, tmp_path: Path) -> None:
        prod = tmp_path / "prod"
        prod.mkdir()
        (prod / ".env.prod").write_text(
            f"SUPABASE_JWT_SECRET={_env_hop_le()['SUPABASE_JWT_SECRET']}\n"
        )
        r = _goi_lib(tmp_path, "kiem_env_staging && echo QUA")
        assert r.returncode != 0
        assert "TRÙNG prod" in r.stderr

    def test_ten_db_prod_bi_chan(self, tmp_path: Path) -> None:
        r = _goi_lib(
            tmp_path,
            "kiem_ten_staging && echo QUA",
            them={"STG_DB_CONTAINER": "clinicai_db"},
        )
        assert r.returncode != 0
        assert "database PROD" in r.stderr


class TestChotTaiNguyen:
    def test_prod_dang_deploy_thi_staging_nhuong(self, tmp_path: Path) -> None:
        (tmp_path / "prod.lock").mkdir()
        r = _goi_lib(tmp_path, "kiem_tai_nguyen && echo QUA")
        assert r.returncode != 0
        assert "prod đang deploy" in r.stderr

    def test_dia_thieu_thi_khong_dung(self, tmp_path: Path) -> None:
        r = _goi_lib(
            tmp_path,
            "kiem_tai_nguyen && echo QUA",
            them={"STG_DIA_TOI_THIEU_GB": "999999", "STG_RAM_TOI_THIEU_MB": "0"},
        )
        assert r.returncode != 0
        assert "đĩa còn" in r.stderr

    def test_kieu_rieng_khong_xet_khoa_prod(self, tmp_path: Path) -> None:
        (tmp_path / "prod.lock").mkdir()
        r = _goi_lib(
            tmp_path, "kiem_tai_nguyen && echo QUA", them={"STAGING_KIEU": "rieng"}
        )
        assert r.returncode == 0, r.stderr

    def test_nguong_mac_dinh_dung_chot(self) -> None:
        lib = LIB.read_text(encoding="utf-8")
        assert 'STG_RAM_TOI_THIEU_MB="${STG_RAM_TOI_THIEU_MB:-2560}"' in lib
        assert 'STG_DIA_TOI_THIEU_GB="${STG_DIA_TOI_THIEU_GB:-8}"' in lib
        assert "/proc/meminfo" in lib


def _repo_gia(tmp_path: Path) -> tuple[Path, Path]:
    """Một bản sao tối thiểu của scripts/ + docker giả ghi lại mọi lần gọi."""
    goc = tmp_path / "stg"
    (goc / "scripts" / "lib").mkdir(parents=True)
    for ten in (
        "deploy-staging.sh",
        "staging-nap-ban-sao.sh",
        "staging-che-du-lieu.sql",
    ):
        shutil.copy(REPO / "scripts" / ten, goc / "scripts" / ten)
    shutil.copy(LIB, goc / "scripts" / "lib" / "staging-chung.sh")
    _ghi_env(goc, _env_hop_le())
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    nhat_ky = tmp_path / "docker.log"
    for lenh in ("docker", "git"):
        (bin_ / lenh).write_text(
            f'#!/bin/sh\necho "{lenh} $*" >> "{nhat_ky}"\nexit 0\n'
        )
        (bin_ / lenh).chmod(0o755)
    return goc, nhat_ky


def _chay(
    tmp_path: Path, script: str, them: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    goc, _ = _repo_gia(tmp_path)
    return subprocess.run(
        ["bash", str(goc / "scripts" / script)],
        capture_output=True,
        text=True,
        cwd=str(goc),
        env={
            **os.environ,
            "PATH": f"{tmp_path / 'bin'}:{os.environ.get('PATH', '')}",
            "PROD_DIR": str(tmp_path / "prod"),
            "PROD_DEPLOY_LOCK": str(tmp_path / "prod.lock"),
            "STAGING_DEPLOY_LOCK": str(tmp_path / "stg.lock"),
            **them,
        },
    )


class TestScriptDungTruocDocker:
    def test_deploy_staging_nhuong_prod_dang_deploy(self, tmp_path: Path) -> None:
        (tmp_path / "prod.lock").mkdir()
        r = _chay(tmp_path, "deploy-staging.sh", {})
        assert r.returncode != 0
        assert "prod đang deploy" in r.stderr
        log = tmp_path / "docker.log"
        assert not log.exists() or "docker" not in log.read_text()

    def test_deploy_staging_khong_chay_trong_thu_muc_prod(self, tmp_path: Path) -> None:
        goc, _ = _repo_gia(tmp_path)
        r = subprocess.run(
            ["bash", str(goc / "scripts" / "deploy-staging.sh")],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{tmp_path / 'bin'}:{os.environ.get('PATH', '')}",
                "PROD_DIR": str(goc),
                "STAGING_DEPLOY_LOCK": str(tmp_path / "stg.lock"),
            },
        )
        assert r.returncode != 0
        assert "thư mục PROD" in r.stderr

    def test_nap_tu_choi_database_prod(self, tmp_path: Path) -> None:
        r = _chay(
            tmp_path, "staging-nap-ban-sao.sh", {"STG_DB_CONTAINER": "clinicai_db"}
        )
        assert r.returncode != 0
        assert "database PROD" in r.stderr
        log = tmp_path / "docker.log"
        assert not log.exists() or "exec" not in log.read_text()

    def test_dung_builder_rieng_co_tran_ram(self) -> None:
        sh = (REPO / "scripts" / "deploy-staging.sh").read_text(encoding="utf-8")
        assert "--driver docker-container" in sh
        assert '--driver-opt "memory=$STG_BUILDER_RAM"' in sh
        assert "nice -n 19" in sh and "ionice -c3" in sh
        assert "label=com.docker.compose.project=$STG_APP_PROJECT" in sh


class TestCaddy:
    def test_caddy_prod_nap_site_phu_qua_thu_muc(self) -> None:
        prod = (REPO / "caddy" / "Caddyfile").read_text(encoding="utf-8")
        assert "import /etc/caddy/them/*.caddy" in prod
        compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
        assert "./caddy/them:/etc/caddy/them:ro" in compose
        assert (REPO / "caddy" / "them" / "README.md").exists()

    def test_mau_site_staging_chi_goi_mot_ten(self) -> None:
        mau = (REPO / "caddy" / "staging-tren-prod.caddy.mau").read_text(
            encoding="utf-8"
        )
        assert "reverse_proxy clinicai-staging-cong:80" in mau
        assert "dashboard:" not in mau and "clinicai_supabase_gateway" not in mau
        assert "X-Robots-Tag" in mau

    def test_caddyfile_staging_khong_roi_ve_ten_prod(self) -> None:
        stg = CADDYFILE_STAGING.read_text(encoding="utf-8")
        assert "{$SITE_ADDRESS}" in stg
        assert "{$AUTH_GUARD_HOST:clinicai_stg_auth_guard}" in stg
        assert "{$SUPABASE_GATEWAY_HOST:clinicai_stg_supabase_gateway}" in stg
        assert (
            ":clinicai_supabase_gateway}" not in stg
            and ":clinicai_auth_guard}" not in stg
        )
        assert "noindex" in stg

    def test_mang_cau_khong_dung_ten_dich_vu(self) -> None:
        stg = (REPO / "docker-compose.staging.yml").read_text(encoding="utf-8")
        assert "clinicai-staging-cong" in stg
        assert "oom_score_adj" in stg and "cpu_shares" in stg

    def test_db_staging_du_khoa_cho_nap_mot_giao_dich(self) -> None:
        # Nạp lại đêm giữ khoá cả lược đồ cũ + mới trong MỘT giao dịch; mặc
        # định 64 hỏng "out of shared memory" (08/10/2026, docs/STAGING.md).
        sb = (REPO / "docker-compose.supabase.staging.yml").read_text(encoding="utf-8")
        assert "- max_locks_per_transaction=256" in sb


class TestStagingEnvExample:
    def test_example_co_ten_rieng_cua_staging(self) -> None:
        content = ENV_STAGING_EXAMPLE.read_text()
        for dong in (
            "SUPABASE_PREFIX=clinicai_stg",
            "SUPABASE_NETWORK=clinicai_stg_db_supabase",
            "SUPABASE_GATEWAY_HOST=clinicai_stg_supabase_gateway",
            "AUTH_GUARD_HOST=clinicai_stg_auth_guard",
            "SUPABASE_DB_PORT=54332",
            "SUPABASE_API_PORT=54331",
            "CADDY_FILE=./caddy/Caddyfile.staging",
            "IMAGE_TAG=staging",
        ):
            assert dong in content

    def test_docker_compose_config_succeeds_with_example(self) -> None:
        sach = {k: v for k, v in os.environ.items() if not k.startswith("CADDY_")}
        for files in (
            ["-f", "docker-compose.yml"],
            ["-f", "docker-compose.yml", "-f", "docker-compose.staging.yml"],
        ):
            proc = subprocess.run(
                [
                    "docker",
                    "compose",
                    "--env-file",
                    ".env.staging.example",
                    *files,
                    "config",
                ],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                env={**sach, "CLINIC_ENV_FILE": ".env.staging.example"},
            )
            assert proc.returncode == 0, f"docker compose config failed:\n{proc.stderr}"

    def test_staging_compose_caddy_chi_nghe_localhost_8080(self) -> None:
        sach = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("CADDY_") and k != "SITE_ADDRESS"
        }
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                ".env.staging.example",
                "-f",
                "docker-compose.yml",
                "-f",
                "docker-compose.staging.yml",
                "config",
                "--format",
                "json",
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env={**sach, "CLINIC_ENV_FILE": ".env.staging.example"},
        )
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        caddy = data["services"]["caddy"]
        assert caddy["environment"]["SITE_ADDRESS"] == ":80"
        cong = {
            (str(p.get("host_ip")), str(p.get("published"))) for p in caddy["ports"]
        }
        assert ("127.0.0.1", "8080") in cong
        assert "staging_edge" in caddy["networks"]
        # day-tep / theo dõi tắt ở staging; trần RAM + bị giết trước prod.
        assert "day-tep" not in data["services"]
        assert "uptime-kuma" not in data["services"]
        for svc in ("api", "dashboard", "su-kien", "caddy"):
            assert data["services"][svc]["oom_score_adj"] == 800
            assert data["services"][svc]["cpu_shares"] == 256

    def test_supabase_staging_tat_realtime_co_tran(self) -> None:
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                ".env.staging.example",
                "-f",
                "docker-compose.supabase.yml",
                "-f",
                "docker-compose.supabase.staging.yml",
                "-p",
                "clinicai_stg_db",
                "config",
                "--format",
                "json",
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        svc = json.loads(proc.stdout)["services"]
        assert "realtime" not in svc
        assert set(svc["gateway"]["depends_on"]) == {"auth", "rest"}
        assert svc["db"]["container_name"] == "clinicai_stg_db"
        for ten in ("db", "auth", "rest", "gateway", "auth-guard"):
            assert svc[ten]["oom_score_adj"] == 900
            assert svc[ten].get("mem_limit")
