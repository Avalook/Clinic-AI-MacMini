"""Gộp log Caddy 24 giờ gần nhất thành số đo cho prod và staging. CHỈ ĐỌC.

Chạy TRÊN VPS (scripts/do-so-do.py gửi tệp này vào `ssh … python3 -`), in một JSON.
Không in IP hay thông tin khách: chỉ số đếm, thời gian, đường dẫn đã thay mã bằng :id.
"""

import json
import re
import subprocess
import time
from collections import Counter, defaultdict

GIO = 24
BAY_GIO = time.time()
TU = BAY_GIO - GIO * 3600
LECH_VN = 7 * 3600
NGUON = {
    # journalctl bằng user clinicai trả RỖNG IM LẶNG (không thuộc nhóm
    # systemd-journal) — lần đo đầu 23/10 ra prod 0 request vì vậy. docker logs
    # đọc được cả log driver journald (prod) lẫn json-file (staging).
    "prod": ["docker", "logs", "--since", f"{GIO}h", "clinicai_prod-caddy-1"],
    "staging": ["docker", "logs", "--since", f"{GIO}h", "clinicai_staging-caddy-1"],
}
# Caddy prod đứng trước cả staging và giám sát: chỉ đếm đúng tên miền.
TEN_MIEN = {"prod": "dr4women.io.vn", "staging": "staging.dr4women.io.vn"}
MA = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f-]{27,}|/\d+(?=/|$)|/DEMO-[^/]+|/[0-9a-f]{24,}", re.I
)
TINH = re.compile(r"^/(_next/|favicon|manifest|icon|apple-touch|robots)")


def phan_vi(xs: list[float], p: float) -> int | None:
    if not xs:
        return None
    xs.sort()
    return round(xs[min(len(xs) - 1, int(len(xs) * p))] * 1000)


def do(ten: str) -> dict:
    p = subprocess.Popen(
        NGUON[ten],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    assert p.stdout is not None
    theo_gio: Counter[int] = Counter()
    theo_giay: Counter[int] = Counter()
    trang_thai: Counter[str] = Counter()
    api: list[float] = []
    trang: list[float] = []
    duong: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
    may: set[str] = set()
    tong = tinh = sse = 0
    for dong in p.stdout:
        if '"handled request"' not in dong:
            continue
        try:
            r = json.loads(dong[dong.index("{") :])
        except ValueError:
            continue
        ts = r.get("ts", 0)
        rq = r.get("request", {})
        if ts < TU or rq.get("host") != TEN_MIEN[ten]:
            continue
        uri = rq.get("uri", "").split("?")[0]
        giay = float(r.get("duration", 0) or 0)
        tong += 1
        theo_gio[int((ts + LECH_VN) // 3600) % 24] += 1
        theo_giay[int(ts)] += 1
        trang_thai[f"{int(r.get('status', 0)) // 100}xx"] += 1
        may.add(rq.get("client_ip") or rq.get("remote_ip") or "")
        if TINH.match(uri):
            tinh += 1
            continue
        if "events/stream" in uri:
            sse += 1
            continue
        (api if uri.startswith("/api/") else trang).append(giay)
        k = rq.get("method", "") + " " + MA.sub("/:id", uri)
        duong[k][0] += 1
        duong[k][1] += giay
    p.wait()
    dinh = max(theo_gio.items(), key=lambda kv: kv[1]) if theo_gio else None
    top = sorted(duong.items(), key=lambda kv: -kv[1][1])[:15]
    return {
        "tong_req_24h": tong,
        # Khuôn trang he-thong: 24 số theo giờ trong ngày, 0h → 23h (giờ VN).
        "req_moi_gio": [theo_gio.get(h, 0) for h in range(24)],
        "gio_dinh": (
            {
                "gio": dinh[0],
                "so_req": dinh[1],
                "req_moi_giay_tb": round(dinh[1] / 3600, 1),
            }
            if dinh
            else None
        ),
        "req_moi_giay_dinh": max(theo_giay.values()) if theo_giay else 0,
        "p95_ms": phan_vi(api, 0.95),
        "p50_ms_chi_tiet": {"api": phan_vi(api, 0.5), "trang": phan_vi(trang, 0.5)},
        "p95_ms_chi_tiet": {"api": phan_vi(api, 0.95), "trang": phan_vi(trang, 0.95)},
        "p99_ms_chi_tiet": {"api": phan_vi(api, 0.99), "trang": phan_vi(trang, 0.99)},
        "so_req_tren_3_giay": sum(1 for x in api + trang if x > 3),
        "trang_thai": dict(trang_thai),
        "tep_tinh": tinh,
        "mo_ket_noi_sse": sse,
        "so_may_khac_nhau": len(may),
        "top_duong": [
            {
                "duong": k,
                "so": int(v[0]),
                "p95_ms": None,
                "tb_ms": round(v[1] / v[0] * 1000),
                "tong_giay": round(v[1]),
            }
            for k, v in top
        ],
    }


print(json.dumps({ten: do(ten) for ten in NGUON}, ensure_ascii=False))
