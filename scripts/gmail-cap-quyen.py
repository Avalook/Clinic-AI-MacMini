#!/usr/bin/env python3
"""Cấp quyền CHỈ ĐỌC Gmail phòng khám cho Clinic AI (chặng G0).

Kế hoạch: docs/KE-HOACH-KET-QUA-QUA-GMAIL.md mục 2. Chạy trên Mac, một lần cho mỗi
tài khoản Gmail (prod: Gmail phòng khám; staging: Gmail THỬ):

    python3 scripts/gmail-cap-quyen.py
    python3 scripts/gmail-cap-quyen.py \\
        --client ~/.clinicai/gmail-client-thu.json --ra ~/.clinicai/gmail-oauth-thu.json

1. Đọc OAuth client loại "Desktop app" (JSON tải từ Google Cloud, để NGOÀI repo).
2. Mở trình duyệt tới màn đồng ý, phạm vi DUY NHẤT `gmail.readonly`. Chủ hộp thư
   tự bấm "Nâng cao → Đi tới …" và "Cho phép" — script không bấm thay.
3. Google trả mã về cổng loopback 127.0.0.1 (PKCE S256 + state) → refresh token.
4. Ghi {client_id, client_secret, refresh_token, scope, tao_luc} vào tệp quyền 600 —
   đúng dạng Docker secret `gmail_oauth` (kế hoạch 1.15). KHÔNG in token ra màn hình.

Google cấp phạm vi khác đúng `gmail.readonly` ⇒ dừng, không ghi tệp.
Chỉ dùng thư viện chuẩn Python.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

PHAM_VI = "https://www.googleapis.com/auth/gmail.readonly"
CHO_TOI_DA_GIAY = 600
KHOA_CLIENT = ("client_id", "client_secret", "auth_uri", "token_uri")


def _doc_client(duong: Path) -> dict[str, str]:
    try:
        goc = json.loads(duong.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"Không đọc được tệp client {duong}: {e.__class__.__name__}")
    c = goc.get("installed")
    if not isinstance(c, dict):
        sys.exit("Tệp client không phải loại 'Desktop app' (thiếu 'installed').")
    for k in KHOA_CLIENT:
        if not c.get(k):
            sys.exit(f"Tệp client thiếu '{k}'.")
    return {k: str(c[k]) for k in KHOA_CLIENT}


class _NhanMa(http.server.BaseHTTPRequestHandler):
    ket_qua: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802 — tên do http.server quy định
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" not in q and "error" not in q:
            self.send_response(404)
            self.end_headers()
            return
        _NhanMa.ket_qua = {k: v[0] for k, v in q.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        chu = (
            "Chưa cấp quyền — quay lại cửa sổ dòng lệnh."
            if "error" in q
            else "Đã nhận quyền. Đóng tab này, quay lại cửa sổ dòng lệnh."
        )
        kieu = "font:16px sans-serif"
        trang = f"<!doctype html><meta charset=utf-8><p style='{kieu}'>{chu}"
        self.wfile.write(trang.encode())

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Không ghi log truy cập — dòng log có chứa mã cấp quyền."""


def _doi_ma(
    client: dict[str, str], ma: str, xac_minh: str, chuyen_ve: str
) -> dict[str, object]:
    than = urllib.parse.urlencode(
        {
            "code": ma,
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "redirect_uri": chuyen_ve,
            "grant_type": "authorization_code",
            "code_verifier": xac_minh,
        }
    ).encode()
    yc = urllib.request.Request(client["token_uri"], data=than, method="POST")
    try:
        with urllib.request.urlopen(yc, timeout=30) as r:
            return dict(json.load(r))
    except urllib.error.HTTPError as e:
        try:
            ly_do = json.load(e).get("error", "?")
        except ValueError:
            ly_do = "?"
        sys.exit(f"Google từ chối đổi mã (HTTP {e.code}, {ly_do}). Chạy lại script.")


def _ghi_bi_mat(duong: Path, du_lieu: dict[str, object]) -> None:
    duong.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(duong.parent, 0o700)
    tam = duong.with_suffix(".tam")
    fd = os.open(tam, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(du_lieu, f, ensure_ascii=False, indent=2)
    os.chmod(tam, 0o600)
    os.replace(tam, duong)


def _url_dong_y(client: dict[str, str], chuyen_ve: str, thach: str, tt: str) -> str:
    return (
        client["auth_uri"]
        + "?"
        + urllib.parse.urlencode(
            {
                "client_id": client["client_id"],
                "redirect_uri": chuyen_ve,
                "response_type": "code",
                "scope": PHAM_VI,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "false",
                "code_challenge": thach,
                "code_challenge_method": "S256",
                "state": tt,
            }
        )
    )


def main() -> None:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mac_dinh = Path("~/.clinicai").expanduser()
    p.add_argument("--client", type=Path, default=mac_dinh / "gmail-client.json")
    p.add_argument("--ra", type=Path, default=mac_dinh / "gmail-oauth.json")
    p.add_argument(
        "--khong-mo-trinh-duyet", action="store_true", help="chỉ in đường dẫn"
    )
    a = p.parse_args()
    ra = a.ra.expanduser().resolve()
    if ra.is_relative_to(Path(__file__).resolve().parent.parent):
        sys.exit("Không ghi khoá vào trong repo. Dùng đường dẫn ngoài repo.")

    client = _doc_client(a.client.expanduser())
    xac_minh = secrets.token_urlsafe(64)
    bam = hashlib.sha256(xac_minh.encode()).digest()
    thach = base64.urlsafe_b64encode(bam).rstrip(b"=").decode()
    tt = secrets.token_urlsafe(24)

    may = http.server.HTTPServer(("127.0.0.1", 0), _NhanMa)
    chuyen_ve = f"http://127.0.0.1:{may.server_port}/"
    threading.Thread(target=may.serve_forever, daemon=True).start()
    url = _url_dong_y(client, chuyen_ve, thach, tt)
    print("Mở màn đồng ý của Google. Chủ hộp thư tự đăng nhập và bấm 'Cho phép'.")
    print(url)
    if not a.khong_mo_trinh_duyet:
        webbrowser.open(url)

    het = time.monotonic() + CHO_TOI_DA_GIAY
    while not _NhanMa.ket_qua and time.monotonic() < het:
        time.sleep(0.3)
    may.shutdown()
    kq = _NhanMa.ket_qua
    if not kq:
        sys.exit("Hết 10 phút chưa thấy Google trả về. Chạy lại script.")
    if kq.get("state") != tt:
        sys.exit("Sai 'state' — không phải trình duyệt của bạn trả về. Không ghi gì.")
    if "error" in kq:
        sys.exit(f"Không được cấp quyền: {kq['error']}.")

    tk = _doi_ma(client, kq["code"], xac_minh, chuyen_ve)
    pham_vi = set(str(tk.get("scope", "")).split())
    if pham_vi != {PHAM_VI}:
        sys.exit(f"Google cấp {sorted(pham_vi)} — chỉ nhận đúng gmail.readonly.")
    if not tk.get("refresh_token"):
        sys.exit(
            "Google không trả refresh token. Thu hồi quyền cũ ở "
            "myaccount.google.com/permissions rồi chạy lại."
        )
    _ghi_bi_mat(
        ra,
        {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "refresh_token": tk["refresh_token"],
            "scope": PHAM_VI,
            "tao_luc": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        },
    )
    print(f"Đã ghi {ra} (quyền 600). Không in nội dung khoá.")


if __name__ == "__main__":
    main()
