#!/usr/bin/env python3
"""Sinh dữ liệu cho trang tài liệu `docs/he-thong/index.html` rồi NHÚNG thẳng vào trang.

    python3 scripts/he-thong-data.py                       # đọc code + viet-tay.json
    python3 scripts/he-thong-data.py --so-do so-do.json    # + số đo thật đo từ Mac

Trang là MỘT tệp tự chứa (không CDN, không fetch): tải về bấm đúp là mở. Vì thế
dữ liệu phải nằm ngay trong trang, giữa thẻ `<script id="du-lieu">` — script này
chỉ thay đúng khối ấy, phần giao diện giữ nguyên.

Hai nguồn, tách bạch để trang luôn nói rõ "theo code" hay "đã đo":
  * THEO CODE — đọc thẳng docker-compose*.yml, caddy/Caddyfile, scripts/systemd/,
    số migration, số route Next. Đổi cấu hình rồi chạy lại là trang khớp.
  * VIẾT TAY — docs/he-thong/viet-tay.json: lời giải thích, rủi ro, đề xuất.
    Chỗ trỏ vào code ghi bằng "neo" {"tep", "tim"}: script tự tìm dòng, nên số
    dòng không mục theo thời gian; chuỗi tìm biến mất thì in cảnh báo.
  * ĐÃ ĐO — tệp --so-do (khuôn ở docs/he-thong/viet-tay.json → "khuon_so_do").
    Không có tệp thì trang hiện "chưa đo" cạnh các số đo cũ có ghi ngày.

Chỉ đọc. Không gọi mạng, không chạm VPS, không đọc tệp .env.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

GOC = Path(__file__).resolve().parent.parent
TRANG = GOC / "docs/he-thong/index.html"
VIET_TAY = GOC / "docs/he-thong/viet-tay.json"
MO_KHOI = '<script id="du-lieu" type="application/json">'
DONG_KHOI = "</script>"

canh_bao: list[str] = []


# ---------------------------------------------------------------- compose ----
def doc_compose(tep: Path) -> dict[str, dict[str, Any]]:
    """Đọc phần `services:` của một compose — đủ cho trang, không cần PyYAML.

    Compose của repo thụt 2 dấu cách: tên dịch vụ ở cột 2, khoá ở cột 4, phần
    tử danh sách ở cột 6. Chỉ lấy vài khoá trang cần; khoá lạ bỏ qua.
    """
    if not tep.exists():
        return {}
    dich_vu: dict[str, dict[str, Any]] = {}
    trong_services = False
    hien_tai: dict[str, Any] | None = None
    khoa_ds: str | None = None
    for dong in tep.read_text(encoding="utf-8").splitlines():
        if not dong.strip() or dong.lstrip().startswith("#"):
            continue
        thut = len(dong) - len(dong.lstrip(" "))
        if thut == 0:
            trong_services = dong.startswith("services:")
            hien_tai = None
            continue
        if not trong_services:
            continue
        noi_dung = dong.strip()
        if thut == 2 and noi_dung.endswith(":"):
            hien_tai = dich_vu.setdefault(noi_dung[:-1], {})
            khoa_ds = None
            continue
        if hien_tai is None:
            continue
        if thut == 4:
            khoa, _, gia_tri = noi_dung.partition(":")
            gia_tri = gia_tri.strip()
            khoa_ds = None
            if khoa in ("image", "mem_limit", "restart", "container_name"):
                hien_tai[khoa] = gia_tri.strip("\"'")
            elif khoa in ("command", "profiles") and gia_tri.startswith("["):
                hien_tai[khoa] = [
                    x.strip().strip("\"'")
                    for x in gia_tri.strip("[]").split(",")
                    if x.strip()
                ]
            elif khoa == "ports" or (khoa in ("command", "profiles") and not gia_tri):
                khoa_ds = khoa
                hien_tai.setdefault(khoa, [])
        elif thut >= 6 and khoa_ds and noi_dung.startswith("- "):
            hien_tai[khoa_ds].append(noi_dung[2:].strip().strip("\"'"))
    return dich_vu


def gon_bien(gia_tri: str) -> str:
    """`${KUMA_PORT:-3001}` → `3001`: trang cho người đọc, không cho máy.

    Cú pháp biến của Caddy cũng gọn: `{$X:mặc định}` → mặc định, `{$X}` → ‹X›.
    """
    gia_tri = re.sub(r"\{\$[A-Z0-9_]+:([^{}]*)\}", r"\1", gia_tri)
    gia_tri = re.sub(r"\{\$([A-Z0-9_]+)\}", r"‹\1›", gia_tri)
    while True:
        moi = re.sub(r"\$\{[A-Z0-9_]+:?-([^${}]*)\}", r"\1", gia_tri)
        if moi == gia_tri:
            return re.sub(r"\$\{[A-Z0-9_]+[^}]*\}", "?", moi)
        gia_tri = moi


def tom_compose() -> dict[str, Any]:
    nguon = {
        "ung_dung": "docker-compose.yml",
        "supabase": "docker-compose.supabase.yml",
        "ung_dung_staging": "docker-compose.staging.yml",
        "supabase_staging": "docker-compose.supabase.staging.yml",
    }
    kq: dict[str, Any] = {}
    for ten, tep in nguon.items():
        dv = doc_compose(GOC / tep)
        for gt in dv.values():
            for k in ("mem_limit", "image"):
                if k in gt:
                    gt[k] = gon_bien(gt[k])
            if "ports" in gt:
                gt["ports"] = [gon_bien(p) for p in gt["ports"]]
        kq[ten] = {"tep": tep, "dich_vu": dv}
    if not kq["ung_dung"]["dich_vu"]:
        canh_bao.append("không đọc được dịch vụ nào trong docker-compose.yml")
    return kq


# ------------------------------------------------------------------ caddy ----
def doc_caddy(tep: Path) -> list[dict[str, str]]:
    """Liệt kê (khối site, đường, đích) theo thứ tự Caddy xét."""
    if not tep.exists():
        return []
    tuyen: list[dict[str, str]] = []
    matcher: dict[str, str] = {}
    site = ""
    duong = ""
    sau = 0
    for so, dong in enumerate(tep.read_text(encoding="utf-8").splitlines(), 1):
        s = dong.strip()
        if not s or s.startswith("#"):
            continue
        if sau == 0 and s.endswith("{"):
            site = s[:-1].strip() or "(cấu hình chung)"
            if site.startswith("("):
                site = f"đoạn dùng chung {site} — site nào import thì có"
        m = re.match(r"(@\w+)\s+path\s+(.+)$", s)
        if m:
            matcher[m.group(1)] = m.group(2)
        m = re.match(r"handle(?:_path)?\s*(\S*)\s*\{$", s)
        if m:
            duong = matcher.get(m.group(1), m.group(1)) or "mọi đường còn lại"
        m = re.match(r"reverse_proxy\s+(\S+)", s)
        if m and m.group(1) != "{":
            tuyen.append(
                {
                    "site": gon_bien(site),
                    "duong": duong or "mọi đường",
                    "dich": gon_bien(m.group(1)),
                    "noi": f"{tep.relative_to(GOC)}:{so}",
                }
            )
        m = re.match(r"respond\s+\"?([^\"]*)\"?\s+(\d{3})$", s)
        if m and duong:
            tuyen.append(
                {
                    "site": gon_bien(site),
                    "duong": duong,
                    "dich": f"Caddy tự trả {m.group(2)}",
                    "noi": f"{tep.relative_to(GOC)}:{so}",
                }
            )
        sau += dong.count("{") - dong.count("}")
        if sau == 0:
            duong = ""
    return tuyen


# ---------------------------------------------------------------- systemd ----
def doc_systemd() -> list[dict[str, str]]:
    thu_muc = GOC / "scripts/systemd"
    kq = []
    for timer in sorted(thu_muc.glob("*.timer")):
        mo_ta = ""
        lich: list[str] = []
        for dong in timer.read_text(encoding="utf-8").splitlines():
            if dong.startswith("Description="):
                mo_ta = dong.split("=", 1)[1]
            if dong.startswith(("OnCalendar=", "OnUnitActiveSec=")):
                lich.append(dong.split("=", 1)[1])
        kq.append(
            {
                "ten": timer.stem,
                "mo_ta": mo_ta,
                "lich": lich,
                "noi": str(timer.relative_to(GOC)),
            }
        )
    return kq


# ------------------------------------------------------------------- neo ----
def giai_neo(nut: Any) -> None:
    """Đi khắp cây viết tay; mỗi {"neo": {"tep", "tim"}} → thêm "noi" = tệp:dòng."""
    if isinstance(nut, list):
        for x in nut:
            giai_neo(x)
        return
    if not isinstance(nut, dict):
        return
    neo = nut.get("neo")
    if isinstance(neo, dict) and neo.get("tep"):
        tep = GOC / neo["tep"]
        tim = neo.get("tim")
        if not tep.exists():
            canh_bao.append(f"neo lệch: không còn tệp {neo['tep']}")
            nut["noi"] = neo["tep"]
            nut["neo_lech"] = True
        elif tim:
            dong = [
                i
                for i, d in enumerate(tep.read_text(encoding="utf-8").splitlines(), 1)
                if tim in d
            ]
            if dong:
                nut["noi"] = f"{neo['tep']}:{','.join(map(str, dong[:4]))}"
            else:
                canh_bao.append(f"neo lệch: '{tim}' không còn trong {neo['tep']}")
                nut["noi"] = neo["tep"]
                nut["neo_lech"] = True
        else:
            # Không chuỗi tìm: chỉ kiểm tệp còn đó; dải dòng (nếu có) chép từ
            # báo cáo gốc qua "noi_ghi".
            nut["noi"] = neo["tep"] + nut.get("noi_ghi", "")
    for v in nut.values():
        giai_neo(v)


# ----------------------------------------------------------- việc cần làm ----
def doc_viec_can_lam() -> list[dict[str, Any]] | None:
    """Đọc 10 việc từ docs/VIEC-CAN-LAM.md nếu tệp đã vào main (PR #536)."""
    tep = GOC / "docs/VIEC-CAN-LAM.md"
    if not tep.exists():
        return None
    kq: list[dict[str, Any]] = []
    for dong in tep.read_text(encoding="utf-8").splitlines():
        m = re.match(r"### (\d+)\. (.+)$", dong)
        if m:
            kq.append({"so": int(m.group(1)), "ten": m.group(2).strip()})
        m = re.match(r"- \*\*Mức (\d)\*\*", dong)
        if m and kq and "muc" not in kq[-1]:
            kq[-1]["muc"] = int(m.group(1))
    return kq or None


# ------------------------------------------------------------------ số đo ----
def doc_so_do(tep: Path) -> dict[str, Any]:
    """Khuôn: viet-tay.json["khuon_so_do"]. Thiếu khoá thì để trống, không ném."""
    try:
        so_do = json.loads(tep.read_text(encoding="utf-8"))
    except (OSError, ValueError) as loi:
        sys.exit(f"Không đọc được {tep}: {loi}")
    if not isinstance(so_do, dict):
        sys.exit(f"{tep}: cần một object JSON")
    if not so_do.get("do_luc"):
        canh_bao.append("số đo thiếu 'do_luc' — trang sẽ ghi 'không rõ ngày đo'")
    for moi_truong in ("prod", "staging"):
        mang = (so_do.get(moi_truong) or {}).get("req_moi_gio")
        if mang is not None and (not isinstance(mang, list) or len(mang) != 24):
            canh_bao.append(
                f"{moi_truong}.req_moi_gio cần đúng 24 số (0h→23h) — bỏ qua biểu đồ"
            )
            so_do[moi_truong]["req_moi_gio"] = None
    return so_do


# ---------------------------------------------------------------- git ----
def chay(*lenh: str) -> str:
    try:
        return subprocess.run(
            lenh, cwd=GOC, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--so-do",
        type=Path,
        help="tệp JSON số đo thật (khuôn: viet-tay.json → khuon_so_do)",
    )
    p.add_argument("--ngay", help="ngày sinh trang YYYY-MM-DD (mặc định hôm nay)")
    tham = p.parse_args()

    viet_tay = json.loads(VIET_TAY.read_text(encoding="utf-8"))
    giai_neo(viet_tay)
    viec = doc_viec_can_lam()

    du_lieu = {
        "sinh_luc": tham.ngay or dt.date.today().isoformat(),
        "git": {
            "sha": chay("git", "rev-parse", "--short", "HEAD"),
            "ngay_commit": chay("git", "log", "-1", "--format=%cs"),
        },
        "theo_code": {
            "compose": tom_compose(),
            "caddy": doc_caddy(GOC / "caddy/Caddyfile"),
            "caddy_staging": doc_caddy(GOC / "caddy/Caddyfile.staging"),
            "systemd": doc_systemd(),
            "so_migration": len(list((GOC / "supabase/migrations").glob("*.sql"))),
            "so_route_next_api": len(
                [d for d in (GOC / "src/dashboard/app/api").iterdir() if d.is_dir()]
            ),
        },
        "viet_tay": viet_tay,
        "viec_tu_tep": viec,
        "so_do": doc_so_do(tham.so_do) if tham.so_do else None,
    }

    trang = TRANG.read_text(encoding="utf-8")
    dau = trang.find(MO_KHOI)
    cuoi = trang.find(DONG_KHOI, dau)
    if dau < 0 or cuoi < 0:
        sys.exit(f"{TRANG}: không thấy khối {MO_KHOI}")
    # `</` trong chuỗi JSON sẽ đóng thẻ script sớm — thoát thành `<\/`.
    nhung = json.dumps(du_lieu, ensure_ascii=False, indent=1).replace("</", "<\\/")
    TRANG.write_text(
        trang[: dau + len(MO_KHOI)] + "\n" + nhung + "\n" + trang[cuoi:],
        encoding="utf-8",
    )

    for c in canh_bao:
        print(f"CẢNH BÁO: {c}", file=sys.stderr)
    print(
        f"Đã nhúng dữ liệu vào {TRANG.relative_to(GOC)} "
        f"(code {du_lieu['git']['sha']}, "
        f"số đo: {'có' if du_lieu['so_do'] else 'chưa đo'})."
    )


if __name__ == "__main__":
    main()
