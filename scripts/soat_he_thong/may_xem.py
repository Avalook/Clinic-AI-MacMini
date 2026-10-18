"""Máy XEM & DUYỆT — người bấm quyết định, agent chỉ ghi lại.

    .venv/bin/python scripts/soat_he_thong/may_xem.py            # lần quét mới nhất
    .venv/bin/python scripts/soat_he_thong/may_xem.py --lan 20261018-083848

Chỉ nghe `127.0.0.1` (không bao giờ `0.0.0.0`): báo cáo có đường dẫn tệp và mã
bản ghi nội bộ, không được lộ ra mạng văn phòng. Việc DUY NHẤT nó ghi là thêm một
dòng vào `ket-qua/so-duyet.jsonl`. Không có đường nào để nó sửa code, chạy lệnh hay
đụng database — đó là chủ ý: agent đề xuất, người quyết (hiến pháp §14 mức RECOMMEND).

Quyết định: `chap_nhan` (đưa vào hàng sửa), `bo_qua` (kèm lý do), `can_them`
(cần thêm thông tin). Quyết định gắn vào `id` ổn định của phát hiện nên lần quét
sau không hỏi lại điều đã bỏ qua.
"""

from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "soat_he_thong"

from soat_he_thong import bao_cao, tien_do  # noqa: E402
from soat_he_thong.chay import KET_QUA, doc_so_duyet  # noqa: E402
from soat_he_thong.khuon import DoPhu, PhatHien  # noqa: E402

QUYET_DINH = {"chap_nhan", "bo_qua", "can_them"}
RE_ID = re.compile(r"^[0-9a-f]{12}$")
TOI_DA_THAN = 4096
HOST_HOP_LE = ("127.0.0.1", "localhost")


def lan_moi_nhat() -> Path:
    cac = (
        sorted(p for p in KET_QUA.iterdir() if (p / "phat-hien.jsonl").is_file())
        if KET_QUA.is_dir()
        else []
    )
    if not cac:
        raise SystemExit("Chưa có lần quét nào. Chạy chay.py trước.")
    return cac[-1]


def dung_bao_cao(lan: Path) -> str:
    giu = [
        PhatHien.tu_dict(json.loads(d))
        for d in (lan / "phat-hien.jsonl").read_text(encoding="utf8").splitlines()
        if d.strip()
    ]
    do = [DoPhu(**d) for d in json.loads((lan / "do-phu.json").read_text("utf8"))]
    return bao_cao.html(giu, do, [], doc_so_duyet(KET_QUA / "so-duyet.jsonl"))


def ghi_quyet_dinh(duong: Path, d: dict[str, object], ten: str) -> str | None:
    """Trả None nếu hợp lệ & đã ghi; ngược lại là lý do từ chối."""
    id_ = str(d.get("id", ""))
    qd = str(d.get("quyet_dinh", ""))
    ly = str(d.get("ly_do", "")).strip()[:500]
    if not RE_ID.match(id_):
        return "id không hợp lệ"
    if qd not in QUYET_DINH:
        return "quyết định không hợp lệ"
    if qd != "chap_nhan" and not ly:
        return "bỏ qua / cần thêm thông tin thì phải có lý do"
    duong.parent.mkdir(parents=True, exist_ok=True)
    dong = {
        "id": id_,
        "quyet_dinh": qd,
        "ly_do": ly,
        "boi": ten,
        "luc": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    with duong.open("a", encoding="utf8") as f:
        f.write(json.dumps(dong, ensure_ascii=False) + "\n")
    return None


def tao_handler(lan: Path) -> type[BaseHTTPRequestHandler]:
    ten = getpass.getuser()
    duong_duyet = KET_QUA / "so-duyet.jsonl"

    class H(BaseHTTPRequestHandler):
        server_version = "SoatHeThong"

        def _host_ok(self) -> bool:
            # Chặn DNS-rebinding: chỉ nhận Host là localhost/127.0.0.1.
            return self.headers.get("Host", "").split(":")[0] in HOST_HOP_LE

        def _tra(
            self, ma: int, body: bytes, kieu: str = "text/html; charset=utf-8"
        ) -> None:
            self.send_response(ma)
            self.send_header("Content-Type", kieu)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            csp = "default-src 'self' 'unsafe-inline'"
            self.send_header("Content-Security-Policy", csp)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                self._tra(403, b"forbidden", "text/plain")
                return
            duong = self.path.split("?")[0]
            if duong == "/tien-do":
                KET_QUA.mkdir(parents=True, exist_ok=True)
                self._tra(200, tien_do.trang(KET_QUA).encode("utf8"))
                return
            if duong != "/":
                self._tra(404, b"not found", "text/plain")
                return
            self._tra(200, dung_bao_cao(lan).encode("utf8"))

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok() or self.path not in ("/duyet", "/dung", "/tiep"):
                self._tra(403, b"forbidden", "text/plain")
                return
            # Chống CSRF từ trang web khác: bắt buộc JSON (kích hoạt preflight mà
            # máy này không trả lời) và Origin, nếu có, phải là chính nó.
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self._tra(415, b"content-type", "text/plain")
                return
            goc = self.headers.get("Origin")
            if (
                goc is not None
                and goc.split("://")[-1].split(":")[0] not in HOST_HOP_LE
            ):
                self._tra(403, b"origin", "text/plain")
                return
            try:
                n = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                n = 0
            if not 0 < n <= TOI_DA_THAN:
                self._tra(413, b"body", "text/plain")
                return
            try:
                d = json.loads(self.rfile.read(n))
            except json.JSONDecodeError:
                self._tra(400, b"json", "text/plain")
                return
            if not isinstance(d, dict):
                self._tra(400, b"json", "text/plain")
                return
            if self.path in ("/dung", "/tiep"):
                # Công tắc dừng khẩn: có tệp DUNG là mọi lần gọi model bị chặn.
                tep_dung = KET_QUA / "DUNG"
                if self.path == "/dung":
                    KET_QUA.mkdir(parents=True, exist_ok=True)
                    tep_dung.write_text(f"dừng bởi {ten}\n", encoding="utf8")
                else:
                    tep_dung.unlink(missing_ok=True)
                self._tra(200, b"ok", "text/plain")
                return
            loi = ghi_quyet_dinh(duong_duyet, d, ten)
            if loi:
                self._tra(400, loi.encode("utf8"), "text/plain; charset=utf-8")
                return
            self._tra(200, b"ok", "text/plain")

        def log_message(self, *a: object) -> None:  # im lặng
            pass

    return H


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Máy xem & duyệt (chỉ localhost)")
    ap.add_argument("--lan", help="tên thư mục lần quét (mặc định: mới nhất)")
    ap.add_argument("--cong", type=int, default=8765)
    a = ap.parse_args(argv)
    lan = KET_QUA / a.lan if a.lan else lan_moi_nhat()
    srv = ThreadingHTTPServer(("127.0.0.1", a.cong), tao_handler(lan))
    print(f"Mở http://127.0.0.1:{a.cong}/  (lần quét {lan.name}) — Ctrl+C để dừng")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
