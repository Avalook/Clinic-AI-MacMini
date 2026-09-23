"""Kết nối cho bộ mô phỏng: đăng nhập tài khoản THỬ, gọi API như giao diện gọi.

CHỈ CHẠY TRÊN MÁY LOCAL: API phải ở 127.0.0.1 và database là container
`clinicai_thu_db` do `scripts/dev-up.sh` dựng. Mật khẩu tài khoản thử (giả,
@dr4women.local) đọc từ biến TEST_PW hoặc từ chính `scripts/dev-up.sh`.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx

REPO = Path(__file__).resolve().parents[2]
API = os.environ.get("MO_PHONG_API", "http://127.0.0.1:8100")
DB_CONTAINER = "clinicai_thu_db"


def _env_local() -> dict[str, str]:
    ra: dict[str, str] = {}
    for dong in (REPO / ".env.thu-local").read_text().splitlines():
        if "=" in dong and not dong.lstrip().startswith("#"):
            k, _, v = dong.partition("=")
            ra[k.strip()] = v.strip()
    return ra


def _mat_khau_thu() -> str:
    if os.environ.get("TEST_PW"):
        return os.environ["TEST_PW"]
    m = re.search(r'TEST_PW="\$\{TEST_PW:-([^}]+)\}"', (REPO / "scripts/dev-up.sh").read_text())
    if not m:
        raise SystemExit("không tìm thấy mật khẩu tài khoản thử — đặt TEST_PW")
    return m.group(1)


def kiem_chi_local() -> None:
    if not API.startswith("http://127.0.0.1:"):
        raise SystemExit(f"Chỉ chạy trên máy local — API đang là {API}")
    ten = subprocess.run(
        ["docker", "inspect", "-f", "{{.Name}}", DB_CONTAINER],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    if ten != f"/{DB_CONTAINER}":
        raise SystemExit(f"Không thấy {DB_CONTAINER} — chạy scripts/dev-up.sh trước")


class LoiApi(Exception):
    def __init__(self, ma: int, duong: str, noi_dung: Any) -> None:
        super().__init__(f"{ma} {duong}: {noi_dung}")
        self.ma = ma
        self.noi_dung = noi_dung


class NguoiDung:
    """Một tài khoản thử đã đăng nhập — gọi API bằng token của chính người ấy."""

    def __init__(self, email: str) -> None:
        env = _env_local()
        r = httpx.post(
            f"http://127.0.0.1:{env['SUPABASE_API_PORT']}/auth/v1/token?grant_type=password",
            headers={"apikey": env["SUPABASE_ANON_KEY"]},
            json={"email": email, "password": _mat_khau_thu()},
            timeout=20,
        )
        r.raise_for_status()
        self.email = email
        self._h = {
            "Authorization": f"Bearer {r.json()['access_token']}",
            "X-API-Key": os.environ.get("BACKEND_API_KEY", "staging-local-api-key"),
        }
        self._c = httpx.Client(base_url=f"{API}/api/v1", headers=self._h, timeout=60)

    def goi(self, cach: str, duong: str, *, mong: int | tuple[int, ...] = (200, 201), **kw: Any) -> Any:
        r = self._c.request(cach, duong, **kw)
        mong_t = (mong,) if isinstance(mong, int) else mong
        try:
            body: Any = r.json()
        except ValueError:
            body = r.text
        if r.status_code not in mong_t:
            raise LoiApi(r.status_code, f"{cach} {duong}", body)
        return body

    def get(self, duong: str, **kw: Any) -> Any:
        return self.goi("GET", duong, **kw)

    def post(self, duong: str, json: Any = None, **kw: Any) -> Any:
        return self.goi("POST", duong, json=json if json is not None else {}, **kw)


def sql(cau: str) -> list[list[str]]:
    """Đọc DB local (chỉ để dò trạng thái / kiểm cuối) — không ghi."""
    env = _env_local()
    # Mật khẩu đi qua BIẾN MÔI TRƯỜNG (`-e PGPASSWORD` không kèm giá trị), không
    # nằm trên dòng lệnh — dòng lệnh hiện ra trong log khi lệnh hỏng.
    r = subprocess.run(
        ["docker", "exec", "-i", "-e", "PGPASSWORD",
         DB_CONTAINER, "psql", "-U", "postgres", "-At", "-F", "\t", "-c", cau],
        capture_output=True, text=True, check=False,
        env={**os.environ, "PGPASSWORD": env["SUPABASE_DB_PASSWORD"]},
    )
    if r.returncode != 0:
        raise RuntimeError(f"SQL hỏng: {r.stderr.strip()[:300]}\n  câu: {cau[:300]}")
    out = r.stdout
    return [d.split("\t") for d in out.splitlines() if d]
