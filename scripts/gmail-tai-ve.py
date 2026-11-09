#!/usr/bin/env python3
"""Tải về TOÀN BỘ thư kết quả của các đối tác từ Gmail phòng khám (CHỈ ĐỌC).

Tuyền 09/11/2026: "không cần che tên, lấy về full" — để xem đủ mẫu thư/PDF của từng
phòng xét nghiệm trước khi làm G1–G4 (docs/KE-HOACH-KET-QUA-QUA-GMAIL.md mục 8).

    .venv/bin/python -u scripts/gmail-tai-ve.py
    .venv/bin/python -u scripts/gmail-tai-ve.py --tu cskh@greenlab.vn

Với mỗi người gửi: mọi thư (kể cả Thùng rác) → tệp đính kèm lưu ở
`~/.clinicai/ket-qua-gmail/<người gửi>/<YYYY-MM>/<ngày>_<id>_<tên gốc>` (thư mục 700,
tệp 600, NGOÀI repo); mỗi thư một dòng trong `thu.jsonl` (ngày, tiêu đề, thân thư,
tệp). Cuối cùng ghi `danh-sach.csv` (mở bằng Excel/Numbers). Chạy lại ⇒ bỏ qua
thư đã có.

DỮ LIỆU SỨC KHOẺ THẬT, KHÔNG CHE. Không chép vào repo, Downloads, iCloud, Drive;
không dán vào chat. Không sửa / xoá / gắn nhãn thư (quyền chỉ đọc).
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_DUONG = Path(__file__).resolve().parent / "gmail-do-hop-thu.py"
_spec = importlib.util.spec_from_file_location("gmail_do_hop_thu", _DUONG)
assert _spec and _spec.loader
g = importlib.util.module_from_spec(_spec)
sys.modules["gmail_do_hop_thu"] = g
_spec.loader.exec_module(g)

NGUOI_GUI = (
    "truemedicine.laymauxn@gmail.com",
    "cskh@greenlab.vn",
    "reports@highdetectlab.com",
    "cvn007_nipt@eurofinsasia.com",
)
TRAN_THAN = 4000


def _b64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _ten_an_toan(s: str) -> str:
    s = re.sub(r"[/\\:\x00-\x1f]", "_", s).strip(" .") or "tep"
    return s[:150]


def _than_thu(phan: list[dict[str, Any]]) -> str:
    """Thân thư dạng chữ: ưu tiên text/plain, không có thì text/html bỏ thẻ."""
    for kieu in ("text/plain", "text/html"):
        for p in phan:
            du_lieu = (p.get("body") or {}).get("data")
            if p.get("mimeType") == kieu and du_lieu and not p.get("filename"):
                chu = _b64(du_lieu).decode("utf-8", "replace")
                if kieu == "text/html":
                    chu = html.unescape(re.sub(r"<[^>]+>", " ", chu))
                return " ".join(chu.split())[:TRAN_THAN]
    return ""


def _ghi_tep(duong: Path, data: bytes) -> None:
    duong.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(duong, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def tai_mot(token: str, mid: str, tu: str, goc: Path, rac: set[str]) -> dict[str, Any]:
    r = g._goi(f"{g.GMAIL}/messages/{mid}?format=full", token=token)
    tai = r.get("payload", {})
    dau = {h["name"].lower(): h["value"] for h in tai.get("headers", [])}
    luc = datetime.fromtimestamp(int(r.get("internalDate", 0)) / 1000, g.VN)
    phan = g._cac_phan(tai)
    tep = []
    for p in phan:
        ten, than = p.get("filename") or "", p.get("body") or {}
        if not ten:
            continue
        if than.get("attachmentId"):
            a = g._goi(
                f"{g.GMAIL}/messages/{mid}/attachments/{than['attachmentId']}",
                token=token,
            )
            data = _b64(a["data"])
        elif than.get("data"):
            data = _b64(than["data"])
        else:
            continue
        ra = (
            goc / tu / f"{luc:%Y-%m}" / f"{luc:%Y-%m-%d}_{mid[-8:]}_{_ten_an_toan(ten)}"
        )
        _ghi_tep(ra, data)
        tep.append({"ten": ten, "co": len(data), "duong": str(ra)})
    return {
        "id": mid,
        "nguoi_gui": tu,
        "ngay": luc.isoformat(),
        "tu": dau.get("from", ""),
        "tieu_de": dau.get("subject", ""),
        "than": _than_thu(phan),
        "thung_rac": mid in rac,
        "tep": tep,
    }


def tai_nguoi_gui(token: str, tu: str, goc: Path, so_ghi: Path, da_co: set[str]) -> int:
    q = f"from:{tu}"
    ids = g.liet_ke(token, q, ca_rac=True)
    rac = set(g.liet_ke(token, q + " in:trash", ca_rac=True))
    moi = [i for i in ids if i not in da_co]
    print(f"{tu}: {len(ids)} thư ({len(rac)} ở Thùng rác) · cần tải {len(moi)}")
    loi = 0
    for so, mid in enumerate(moi, 1):
        try:
            ban = tai_mot(token, mid, tu, goc, rac)
        except (g.GmailError, KeyError, ValueError) as e:
            loi += 1
            print(f"  bỏ qua thư {mid}: {str(e)[:120]}")
            continue
        with so_ghi.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ban, ensure_ascii=False) + "\n")
        da_co.add(mid)
        if so % 50 == 0:
            print(f"  {tu}: {so}/{len(moi)}")
        time.sleep(g.NGHI_GIUA_THU)
    return loi


def ghi_csv(so_ghi: Path, ra: Path) -> int:
    dong = 0
    fd = os.open(ra, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["Người gửi", "Ngày nhận", "Tiêu đề", "Thân thư", "Tên tệp",
             "Cỡ (KB)", "Ở Thùng rác", "Đường dẫn tệp", "Mã thư Gmail"]
        )  # fmt: skip
        for x in sorted(_doc_so(so_ghi), key=lambda b: (b["nguoi_gui"], b["ngay"])):
            ngay = x["ngay"][:16].replace("T", " ")
            co_ban = [x["nguoi_gui"], ngay, x["tieu_de"], x["than"]]
            cuoi = ["có" if x["thung_rac"] else "", "", x["id"]]
            for t in x["tep"] or [{"ten": "", "co": 0, "duong": ""}]:
                cuoi[1] = t["duong"]
                w.writerow([*co_ban, t["ten"], round(t["co"] / 1024), *cuoi])
                dong += 1
    return dong


def _doc_so(so_ghi: Path) -> list[dict[str, Any]]:
    if not so_ghi.exists():
        return []
    return [json.loads(d) for d in so_ghi.read_text(encoding="utf-8").splitlines() if d]


def main() -> None:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mac_dinh = Path("~/.clinicai").expanduser()
    p.add_argument("--khoa", type=Path, default=mac_dinh / "gmail-oauth.json")
    p.add_argument("--tu", action="append", help="người gửi (lặp lại được)")
    p.add_argument("--ra", type=Path, default=mac_dinh / "ket-qua-gmail")
    a = p.parse_args()
    goc = a.ra.expanduser().resolve()
    if goc.is_relative_to(Path(__file__).resolve().parent.parent):
        sys.exit("Không tải dữ liệu khách vào trong repo.")
    goc.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(goc, 0o700)
    so_ghi = goc / "thu.jsonl"
    da_co = {x["id"] for x in _doc_so(so_ghi)}
    try:
        token = g.lay_token(a.khoa.expanduser())
        loi = sum(
            tai_nguoi_gui(token, tu, goc, so_ghi, da_co) for tu in a.tu or NGUOI_GUI
        )
    except g.GmailError as e:
        sys.exit(str(e))
    os.chmod(so_ghi, 0o600) if so_ghi.exists() else None
    dong = ghi_csv(so_ghi, goc / "danh-sach.csv")
    print(f"Xong. {len(da_co)} thư đã có · {loi} thư lỗi (chạy lại để thử tiếp).")
    print(f"Tệp: {goc} · bảng: {goc / 'danh-sach.csv'} ({dong} dòng)")


if __name__ == "__main__":
    main()
