#!/usr/bin/env python3
"""Đo số liệu thật của hệ thống (CHỈ ĐỌC) rồi ghi `docs/he-thong/so-do.json`.

Chạy trên Mac:  python3 scripts/do-so-do.py [--nhung]
  - gửi scripts/so-do/caddy.py và scripts/so-do/vps.sh vào `ssh clinic-vps-moi`
    (nice/ionice thấp): log Caddy 24 giờ, DB prod/staging, ổ đĩa, sao lưu, máy;
  - thêm bản sao lưu mới nhất đã kéo về Mac;
  - ghi JSON theo khuôn `khuon_so_do` của docs/he-thong/viet-tay.json;
  - `--nhung`: chạy luôn scripts/he-thong-data.py --so-do để nhúng vào trang.

Không ghi gì lên VPS. Không in IP hay thông tin khách. Đo trong giờ khám vẫn nhẹ
(chỉ đọc log và thống kê), nhưng đừng chạy dồn nhiều lần liên tiếp.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
MAY = "clinic-vps-moi"
RA = GOC / "docs" / "he-thong" / "so-do.json"
SAO_LUU_MAC = Path.home() / "Projects" / "ClinicAI-Backups" / "ban-sao"


def qua_ssh(lenh: str, tep: Path) -> dict:
    kq = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", MAY, lenh],
        stdin=tep.open("rb"),
        capture_output=True,
        timeout=600,
    )
    if kq.returncode != 0:
        sys.exit(f"{tep.name} lỗi trên VPS: {kq.stderr.decode(errors='replace')}")
    if kq.stderr.strip():
        # vd thiếu lệnh trên VPS — không im lặng cho qua.
        sys.exit(f"{tep.name} báo trên VPS: {kq.stderr.decode(errors='replace')}")
    return json.loads(kq.stdout)


def ban_mac() -> dict | None:
    """Bản dump chính mới nhất đã kéo về Mac (bỏ _auth, Notion, .manifest)."""
    if not SAO_LUU_MAC.is_dir():
        return None
    tep = [
        p
        for p in SAO_LUU_MAC.glob("*.sql.gz")
        if "_auth" not in p.name and "notion" not in p.name
    ]
    if not tep:
        return None
    moi = max(tep, key=lambda p: p.stat().st_mtime)
    return {
        "tep": moi.name,
        "tuoi_gio": round((time.time() - moi.stat().st_mtime) / 3600, 1),
        "co_mb": round(moi.stat().st_size / 1048576),
    }


def iso(gio_vps: str) -> str:
    """'2026-10-23 15:02:50 +0700' → '2026-10-23T15:02+07:00' (khuôn trang)."""
    ngay, gio, lech = gio_vps.split()
    return f"{ngay}T{gio[:5]}{lech[:3]}:{lech[3:]}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Đo số liệu thật (chỉ đọc).")
    ap.add_argument("--nhung", action="store_true", help="nhúng luôn vào trang")
    args = ap.parse_args()

    caddy = qua_ssh("nice -n 19 ionice -c3 python3 -", GOC / "scripts/so-do/caddy.py")
    vps = qua_ssh("nice -n 19 bash -s", GOC / "scripts/so-do/vps.sh")

    def db(x: dict) -> dict:
        return {
            "ket_noi": x["ket_noi"],
            "max_ket_noi": x["max_ket_noi"],
            "dung_luong_gb": x["dung_luong_gb"],
            "ket_noi_theo_trang_thai": x["ket_noi_theo_trang_thai"],
            "bang_to_mb": x["bang_to_mb"],
            "cau_cham": x["cau_ton_thoi_gian_nhat"],
            "thong_ke_cau_tu": x["thong_ke_cau_tu"],
        }

    sl = vps["sao_luu"]
    moi_nhat = sl["vps_15_phut"]
    if not moi_nhat.get("ban_moi_nhat"):
        moi_nhat = sl["vps_hang_dem"]
    so_do = {
        "do_luc": iso(vps["do_luc"]),
        "ghi_chu": (
            "Đo chỉ đọc từ Mac (scripts/do-so-do.py): 24 giờ log Caddy qua docker "
            "logs, pg_stat_activity/pg_stat_statements, df. Giờ VN. Không có "
            "IP/thông tin khách. p95_ms = /api/*; chi tiết api/trang ở *_chi_tiet; "
            "bỏ tệp tĩnh và SSE. cau_cham cộng dồn từ thong_ke_cau_tu."
        ),
        "prod": caddy["prod"],
        "staging": caddy["staging"],
        "db": db(vps["db"]["prod"]),
        "db_staging": db(vps["db"]["staging"]),
        "o_dia": {
            "vps_goc_pct": vps["o_dia"]["vps_goc"]["dung_pct"],
            "vps_goc_con_gb": vps["o_dia"]["vps_goc"]["con_gb"],
            "cfs_pct": vps["o_dia"]["cfs"]["dung_pct"],
            "cfs_con_gb": vps["o_dia"]["cfs"]["con_gb"],
        },
        "may_vps": vps["may"],
        "sao_luu": {
            "ban_moi_nhat": moi_nhat.get("ban_moi_nhat"),
            "tuoi_gio": moi_nhat.get("tuoi_gio"),
            "hang_dem": sl["vps_hang_dem"],
            "moi_15_phut": sl["vps_15_phut"],
            "cfs": sl["cfs"],
            "mac": ban_mac(),
        },
    }
    RA.write_text(
        json.dumps(so_do, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"Đã ghi {RA.relative_to(GOC)} — đo lúc {so_do['do_luc']}")
    if args.nhung:
        subprocess.run(
            [sys.executable, str(GOC / "scripts/he-thong-data.py"), "--so-do", str(RA)],
            check=True,
        )


if __name__ == "__main__":
    main()
