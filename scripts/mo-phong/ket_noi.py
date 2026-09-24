"""Kết nối cho bộ mô phỏng: đăng nhập tài khoản THỬ, gọi API như giao diện gọi.

CHỈ CHẠY TRÊN MÁY LOCAL: API phải ở 127.0.0.1 và database là container
`clinicai_thu_db` do `scripts/dev-up.sh` dựng. Mật khẩu tài khoản thử (giả,
@dr4women.local) đọc từ biến TEST_PW hoặc từ chính `scripts/dev-up.sh`.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
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


#: Ai muốn nghe mọi lời gọi API (đo thời gian, đếm lỗi) thì thêm hàm vào đây:
#: ghi(email, cach, duong, ma_http, ms).
NGHE_LOI_GOI: list[Any] = []


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
        t0 = time.monotonic()
        r = self._c.request(cach, duong, **kw)
        ms = (time.monotonic() - t0) * 1000
        for ghi in NGHE_LOI_GOI:
            ghi(self.email, cach, duong, r.status_code, ms)
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
    """Đọc DB local (dò trạng thái / kiểm cuối). Ghi thì dùng `ghi_sql` cho rõ."""
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


WEB = os.environ.get("MO_PHONG_WEB", "http://127.0.0.1:3100")


class PhienWeb:
    """Phiên TRÌNH DUYỆT của một tài khoản thử — gọi route `/api/*` của Next
    y như trình duyệt (cookie `clinicai-auth-<cổng>` dạng @supabase/ssr).

    Dùng cho những việc CHỈ có đường giao diện (vd Quản lý tạo tài khoản đăng
    nhập ở `/api/admin/users`)."""

    def __init__(self, email: str) -> None:
        import base64
        import json as _json

        env = _env_local()
        r = httpx.post(
            f"http://127.0.0.1:{env['SUPABASE_API_PORT']}/auth/v1/token?grant_type=password",
            headers={"apikey": env["SUPABASE_ANON_KEY"]},
            json={"email": email, "password": _mat_khau_thu()},
            timeout=20,
        )
        r.raise_for_status()
        gia_tri = "base64-" + base64.urlsafe_b64encode(
            _json.dumps(r.json()).encode()
        ).decode().rstrip("=")
        ten = f"clinicai-auth-{env['SUPABASE_API_PORT']}"
        manh = [gia_tri[i : i + 3180] for i in range(0, len(gia_tri), 3180)]
        cookies = {ten: manh[0]} if len(manh) == 1 else {f"{ten}.{i}": m for i, m in enumerate(manh)}
        self._c = httpx.Client(base_url=WEB, cookies=cookies, timeout=60)

    def goi(self, cach: str, duong: str, *, mong: int | tuple[int, ...] = (200, 201), **kw: Any) -> Any:
        r = self._c.request(cach, duong, **kw)
        try:
            body: Any = r.json()
        except ValueError:
            body = r.text[:300]
        mong_t = (mong,) if isinstance(mong, int) else mong
        if r.status_code not in mong_t:
            raise LoiApi(r.status_code, f"WEB {cach} {duong}", body)
        return body


def ghi_sql(cau: str, *, ly_do: str) -> None:
    """GHI thẳng DB local — CHỈ cho cấu hình KHÔNG có API/màn nào sửa được.

    Mỗi lần dùng là một PHÁT HIỆN (thiếu API), nên bắt buộc ghi lý do.
    """
    kiem_chi_local()
    print(f"  ⚠ ghi thẳng DB (không có API): {ly_do}", flush=True)
    sql(cau)
