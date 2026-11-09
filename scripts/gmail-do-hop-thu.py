#!/usr/bin/env python3
"""Đo hộp thư kết quả đối tác trên Gmail — CHỈ ĐỌC, báo cáo đã che tên (chặng G0).

Kế hoạch: docs/KE-HOACH-KET-QUA-QUA-GMAIL.md mục 3 G0. Chạy trên Mac sau
`gmail-cap-quyen.py` (cần .venv của repo cho phần thử đọc chữ PDF):

    .venv/bin/python scripts/gmail-do-hop-thu.py
    .venv/bin/python scripts/gmail-do-hop-thu.py --tu truemedicine.laymauxn@gmail.com

Đọc TOÀN BỘ thư từ người gửi đối tác, nhưng chỉ lấy: ngày, tiêu đề, tên + cỡ tệp đính
kèm. KHÔNG đọc thân thư, KHÔNG sửa / gắn nhãn / đánh dấu đã đọc. Thử đọc chữ 20 PDF gần
nhất trong BỘ NHỚ (không ghi ra đĩa), chỉ ĐẾM: có chữ / có SĐT / có tên / có mã đối tác.

Báo cáo .md (quyền 600, ngoài repo): tên khách thay bằng KHACH_001…, không SĐT, không
nội dung PDF. In ra màn hình chỉ các con số.
"""

from __future__ import annotations

import argparse
import base64
import http.client
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
TOKEN_URI = "https://oauth2.googleapis.com/token"
PHAM_VI = "https://www.googleapis.com/auth/gmail.readonly"
NGUOI_GUI = "truemedicine.laymauxn@gmail.com"
VN = timezone(timedelta(hours=7))
SO_PDF_THU_CHU = 20
SO_LAN_THU = 8
#: Đọc LẦN LƯỢT, nghỉ giữa hai thư: Gmail giới hạn số lượt gọi cùng lúc trên một
#: tài khoản (09/11: 8 rồi 4 luồng song song đều bị 403 rateLimitExceeded).
NGHI_GIUA_THU = 0.1
_PHAN = "filename,mimeType,body(size,attachmentId)"
TRUONG = (
    "id,internalDate,payload(headers,"
    + _PHAN
    + ",parts("
    + _PHAN
    + ",parts("
    + _PHAN
    + ",parts("
    + _PHAN
    + "))))"
)
TIEU_DE_MAU = re.compile(
    r"^Kết quả xét nghiệm:\s*(?P<ten>.+?)\s*-\s*Ngày xét nghiệm:\s*"
    r"(?P<ngay>\d{2}[-/]\d{2}[-/]\d{4})\s*$",
    re.IGNORECASE,
)
TEN_TEP_MAU = re.compile(
    r"^(?P<ten>.+?)_(?P<ma>\d{6}-\d{6})_(?P<xn>.+)_(?P<dt>[A-Za-z0-9]+)\.pdf$",
    re.IGNORECASE,
)
#: Chữ khuôn mẫu được giữ khi che tiêu đề lạ. KHÔNG thêm chữ có thể là họ/tên người
#: (09/11: "lại" từng lọt — là họ Lại của khách).
TU_GIU = {
    "kết", "quả", "xét", "nghiệm", "ngày", "re", "fw", "fwd", "gửi",
    "bổ", "sung", "sửa", "kq", "xn", "hpv", "pdf",
}  # fmt: skip


class GmailError(Exception):
    """Lỗi gọi Google — câu ngắn, không chứa token."""


# ---------- gọi Google (thư viện chuẩn) ----------


def _ly_do(e: urllib.error.HTTPError) -> str:
    """Mã lý do Google trả (vd rateLimitExceeded) — không chứa token hay dữ liệu thư."""
    try:
        loi = json.load(e).get("error", {})
    except ValueError:
        return "?"
    if not isinstance(loi, dict):
        return str(loi)[:80]
    chi_tiet = loi.get("errors") or [{}]
    return str(chi_tiet[0].get("reason") or loi.get("status") or "?")[:80]


class Phien:
    """Giữ access token (sống ~1 giờ), tự làm mới — lượt nhiều giờ không bị 401."""

    LAM_MOI_SAU_GIAY = 45 * 60

    def __init__(self, khoa: Path) -> None:
        self.khoa = khoa
        self.lam_moi()

    def lam_moi(self) -> None:
        self.token = lay_token(self.khoa)
        self.luc = time.monotonic()

    def lay(self) -> str:
        if time.monotonic() - self.luc > self.LAM_MOI_SAU_GIAY:
            self.lam_moi()
        return self.token


def _goi(
    url: str, du_lieu: bytes | None = None, token: str | Phien | None = None
) -> Any:
    da_lam_moi = False
    for lan in range(SO_LAN_THU):
        yc = urllib.request.Request(url, data=du_lieu)
        if token:
            gia_tri = token.lay() if isinstance(token, Phien) else token
            yc.add_header("Authorization", f"Bearer {gia_tri}")
        try:
            with urllib.request.urlopen(yc, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            ly_do = _ly_do(e)
            if e.code == 401 and isinstance(token, Phien) and not da_lam_moi:
                token.lam_moi()  # token hết hạn giữa lượt dài
                da_lam_moi = True
                continue
            # Gmail báo vượt hạn mức tốc độ bằng 403 (rateLimitExceeded), không chỉ 429.
            gioi_han = e.code == 403 and "ratelimit" in ly_do.lower()
            if (e.code in (429, 500, 502, 503) or gioi_han) and lan < SO_LAN_THU - 1:
                time.sleep(min(2**lan, 32) + random.random())
                continue
            duong = url.split("?")[0]
            raise GmailError(f"Google trả HTTP {e.code} ({ly_do}): {duong}") from None
        except (OSError, http.client.HTTPException, ValueError) as e:
            # URLError, hết giờ / đứt kết nối khi đang ĐỌC thân, JSON cụt.
            if lan < SO_LAN_THU - 1:
                time.sleep(min(2**lan, 32) + random.random())
                continue
            raise GmailError(f"Mất kết nối Google: {e.__class__.__name__}") from None
    raise GmailError("Hết lượt thử")


def lay_token(duong: Path) -> str:
    k = json.loads(duong.read_text(encoding="utf-8"))
    than = urllib.parse.urlencode(
        {
            "client_id": k["client_id"],
            "client_secret": k["client_secret"],
            "refresh_token": k["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode()
    try:
        tk = _goi(TOKEN_URI, than)
    except GmailError as e:
        raise GmailError(f"Không làm mới được quyền Gmail ({e}). Cấp lại.") from None
    if tk.get("scope", "").split() != [PHAM_VI]:
        raise GmailError("Quyền không phải đúng gmail.readonly — dừng.")
    return str(tk["access_token"])


def liet_ke(token: str | Phien, q: str, ca_rac: bool) -> list[str]:
    ids: list[str] = []
    trang: str | None = None
    while True:
        tham = {"q": q, "maxResults": "500"}
        if ca_rac:
            tham["includeSpamTrash"] = "true"
        if trang:
            tham["pageToken"] = trang
        r = _goi(f"{GMAIL}/messages?{urllib.parse.urlencode(tham)}", token=token)
        ids += [m["id"] for m in r.get("messages", [])]
        trang = r.get("nextPageToken")
        if not trang:
            return ids


# ---------- phân tích (hàm thuần) ----------


@dataclass
class Thu:
    id: str
    luc: datetime
    tieu_de: str
    pdf: list[tuple[str, int, str]] = field(default_factory=list)  # tên, cỡ, attId


def _cac_phan(p: dict[str, Any]) -> list[dict[str, Any]]:
    ra = [p]
    for con in p.get("parts", []) or []:
        ra += _cac_phan(con)
    return ra


def doc_thu(r: dict[str, Any]) -> Thu:
    tai = r.get("payload", {})
    tieu = next(
        (h["value"] for h in tai.get("headers", []) if h["name"].lower() == "subject"),
        "",
    )
    luc = datetime.fromtimestamp(int(r.get("internalDate", 0)) / 1000, VN)
    pdf = []
    for p in _cac_phan(tai):
        ten = p.get("filename") or ""
        la_pdf = ten.lower().endswith(".pdf") or p.get("mimeType") == "application/pdf"
        if ten and la_pdf:
            b = p.get("body", {})
            pdf.append((ten, int(b.get("size", 0)), b.get("attachmentId", "")))
    return Thu(r["id"], luc, tieu, pdf)


def chuan(s: str) -> str:
    import unicodedata

    s = s.replace("đ", "d").replace("Đ", "D")
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^0-9a-z]+", " ", s.lower()).split())


def hinh_tieu_de(s: str) -> str:
    """Dạng tiêu đề không lộ tên: giữ chữ khuôn mẫu, chữ khác → x, số → 9."""
    if TIEU_DE_MAU.match(s):
        return "Kết quả xét nghiệm: <TÊN> - Ngày xét nghiệm: <dd-mm-yyyy>"

    def tu(m: re.Match[str]) -> str:
        return m.group(0) if m.group(0).lower() in TU_GIU else "x"

    return re.sub(r"\d", "9", re.sub(r"[^\W\d_]+", tu, s))


def hinh_ten_tep(s: str) -> tuple[str, str | None, str | None]:
    """(dạng, mã xét nghiệm, đuôi đối tác). Không theo mẫu ⇒ dạng che, (None, None)."""
    m = TEN_TEP_MAU.match(s)
    # Chỉ nhận mã ngắn kiểu HPV / TQ: phần giữa của đối tác khác có thể chứa tên người.
    if m and re.fullmatch(r"[A-Za-z0-9]{1,12}", m["xn"]):
        return f"<TEN>_<6so>-<6so>_<MA_XN>_{m['dt']}.pdf", m["xn"], m["dt"]
    return re.sub(r"\d", "9", re.sub(r"[^\W\d_]+", "x", s[:-4])) + ".pdf", None, None


def ten_khach(t: Thu) -> str:
    m = TIEU_DE_MAU.match(t.tieu_de)
    if m:
        return chuan(m["ten"])
    for ten, _, _ in t.pdf:
        mt = TEN_TEP_MAU.match(ten)
        if mt:
            return chuan(mt["ten"].replace("_", " "))
    return ""


def _mb(b: float) -> str:
    return f"{b / 1048576:.2f} MB"


# ---------- báo cáo ----------


def bao_cao(thu: list[Thu], thu_chu: Counter[str], ten_nguoi_gui: str, rac: int) -> str:
    thu.sort(key=lambda t: t.luc)
    ma_kh: dict[str, str] = {}

    def kh(t: Thu) -> str:
        k = ten_khach(t) or f"?{t.id}"
        return ma_kh.setdefault(k, f"KHACH_{len(ma_kh) + 1:03d}")

    co = [s for t in thu for _, s, _ in t.pdf]
    # Đếm mọi thư (cả mẫu tên tệp cũ không có mã) — không chỉ thư đã qua kh().
    so_khach = len({ten_khach(t) or t.id for t in thu})
    theo_thang = Counter(t.luc.strftime("%Y-%m") for t in thu)
    kieu_tieu = Counter(hinh_tieu_de(t.tieu_de) for t in thu)
    kieu_tep: Counter[str] = Counter()
    ma_xn: Counter[str] = Counter()
    duoi: Counter[str] = Counter()
    lap: dict[tuple[str, str], int] = defaultdict(int)
    for t in thu:
        for ten, _, _ in t.pdf:
            dang, xn, dt = hinh_ten_tep(ten)
            kieu_tep[dang] += 1
            if xn:
                ma_xn[xn.upper()] += 1
                duoi[(dt or "").upper()] += 1
                lap[(kh(t), xn.upper())] += 1
    khong_pdf = [t for t in thu if not t.pdf]
    nhieu_pdf = [t for t in thu if len(t.pdf) >= 2]
    sai_mau = [t for t in thu if not TIEU_DE_MAU.match(t.tieu_de)]
    gui_lai = sorted((k, n) for k, n in lap.items() if n >= 2)

    d = [f"# Báo cáo hộp thư kết quả đối tác — {datetime.now(VN):%d/%m/%Y %H:%M}", ""]
    d += [
        f"Người gửi: `{ten_nguoi_gui}` · đọc CHỈ tiêu đề, ngày, tên + cỡ tệp. "
        "Tên khách đã thay bằng KHACH_xxx; không có SĐT, không nội dung PDF.",
        "",
        "## Tổng quan",
        "",
        "| | |",
        "|---|---|",
        f"| Tổng số thư (hộp thư chính) | {len(thu)} |",
        f"| Kể cả Thư rác + Thùng rác | {rac} |",
        f"| Thư không đọc được (lỗi Google sau {SO_LAN_THU} lần thử) | "
        f"{thu_chu['khong_doc']} |",
    ]
    if thu:
        d += [
            f"| Thư đầu tiên | {thu[0].luc:%d/%m/%Y} |",
            f"| Thư gần nhất | {thu[-1].luc:%d/%m/%Y %H:%M} |",
            f"| Số khách khác nhau (theo tên) | {so_khach} |",
            f"| Tổng số PDF | {len(co)} |",
        ]
    if co:
        d += [
            f"| Cỡ PDF trung bình / lớn nhất | {_mb(sum(co) / len(co))} / "
            f"{_mb(max(co))} |",
            f"| **Tổng dung lượng PDF** | **{_mb(sum(co))}** |",
        ]
    d += ["", "## Số thư theo tháng", "", "| Tháng | Thư |", "|---|---|"]
    d += [f"| {k} | {v} |" for k, v in sorted(theo_thang.items())]
    d += ["", "## Kiểu tiêu đề", "", "| Dạng | Thư |", "|---|---|"]
    d += [f"| `{k}` | {v} |" for k, v in kieu_tieu.most_common()]
    d += ["", "## Kiểu tên tệp", "", "| Dạng | Tệp |", "|---|---|"]
    d += [f"| `{k}` | {v} |" for k, v in kieu_tep.most_common()]
    d += ["", "## Mã xét nghiệm trong tên tệp", "", "| Mã | Lần |", "|---|---|"]
    d += [f"| `{k}` | {v} |" for k, v in ma_xn.most_common()]
    d += ["", "Đuôi mã đối tác: " + ", ".join(f"`{k}` × {v}" for k, v in duoi.items())]
    d += [
        "",
        "## Ca lạ",
        "",
        f"- Thư **không có PDF**: {len(khong_pdf)}"
        + (f" (gần nhất {khong_pdf[-1].luc:%d/%m/%Y})" if khong_pdf else ""),
        f"- Thư **≥ 2 PDF**: {len(nhieu_pdf)}",
        f"- Tiêu đề **không theo mẫu**: {len(sai_mau)}",
        f"- Cùng khách + cùng mã xét nghiệm gửi ≥ 2 lần: {len(gui_lai)} cặp",
    ]
    d += [f"  - {k} · `{x}` × {n}" for (k, x), n in gui_lai[:40]]
    if len(gui_lai) > 40:
        d.append(f"  - … và {len(gui_lai) - 40} cặp nữa")
    n = thu_chu["thu"]
    d += [
        "",
        f"## Thử đọc chữ {n} PDF gần nhất (chỉ đếm, không lưu)",
        "",
        "| | Tệp |",
        "|---|---|",
        f"| Đọc được chữ | {thu_chu['co_chu']} / {n} |",
        f"| Có SĐT trong chữ | {thu_chu['co_sdt']} / {n} |",
        f"| Có tên khách (bỏ dấu) trong chữ | {thu_chu['co_ten']} / {n} |",
        f"| Có mã đối tác `999999-999999` trong chữ | {thu_chu['co_ma']} / {n} |",
        f"| Có năm sinh (4 số 19xx/20xx) trong chữ | {thu_chu['co_nam']} / {n} |",
    ]
    if thu_chu["loi_tai"]:
        d.append(f"| Không tải được | {thu_chu['loi_tai']} |")
    return "\n".join(d) + "\n"


def thu_doc_chu(token: str | Phien, thu: list[Thu]) -> Counter[str]:
    dem: Counter[str] = Counter()
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from clinicai.services.xet_nghiem.ghep_khach import chu_pdf, sdt_trong
    except Exception:  # noqa: BLE001 — thiếu .venv ⇒ bỏ phần này, báo rõ
        print("Bỏ phần thử đọc chữ PDF: chạy bằng .venv/bin/python của repo.")
        return dem
    mau = [t for t in sorted(thu, key=lambda t: t.luc, reverse=True) if t.pdf]
    for t in mau[:SO_PDF_THU_CHU]:
        ten, _, att = t.pdf[0]
        dem["thu"] += 1
        try:
            r = _goi(f"{GMAIL}/messages/{t.id}/attachments/{att}", token=token)
            data = base64.urlsafe_b64decode(r["data"] + "==")
        except (GmailError, KeyError, ValueError):
            dem["loi_tai"] += 1
            continue
        chu = chu_pdf(data)
        tk = ten_khach(t)
        mt = TEN_TEP_MAU.match(ten)
        dem["co_chu"] += len(chu.strip()) > 30
        dem["co_sdt"] += bool(sdt_trong(chu))
        dem["co_ten"] += bool(tk) and tk in chuan(chu)
        dem["co_ma"] += mt is not None and mt["ma"] in chu
        dem["co_nam"] += bool(re.search(r"(?<!\d)(19|20)\d{2}(?!\d)", chu))
        del data, chu
    return dem


def main() -> None:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mac_dinh = Path("~/.clinicai").expanduser()
    p.add_argument("--khoa", type=Path, default=mac_dinh / "gmail-oauth.json")
    p.add_argument("--tu", default=NGUOI_GUI, help="địa chỉ người gửi đối tác")
    p.add_argument("--ra", type=Path, default=None, help="tệp báo cáo .md")
    a = p.parse_args()
    ra = a.ra or mac_dinh / f"bao-cao-hop-thu-{datetime.now(VN):%Y%m%d-%H%M}.md"
    if ra.resolve().is_relative_to(Path(__file__).resolve().parent.parent):
        sys.exit("Không ghi báo cáo vào trong repo (có dữ liệu khách dù đã che).")
    try:
        token = Phien(a.khoa.expanduser())
        q = f"from:{a.tu}"
        dem_loi: Counter[str] = Counter()
        ids = liet_ke(token, q, ca_rac=False)
        rac = len(liet_ke(token, q, ca_rac=True))
        print(f"Trong đó Thùng rác: {len(liet_ke(token, q + ' in:trash', True))}")
        print(f"Tìm thấy {len(ids)} thư từ người gửi đối tác (kể cả rác: {rac}).")

        tham = urllib.parse.urlencode({"format": "full", "fields": TRUONG})
        thu: list[Thu] = []
        for so, i in enumerate(ids, 1):
            try:
                thu.append(doc_thu(_goi(f"{GMAIL}/messages/{i}?{tham}", token=token)))
            except GmailError:
                dem_loi["khong_doc"] += 1
            if so % 200 == 0:
                print(f"  đã đọc {so}/{len(ids)} thư")
            time.sleep(NGHI_GIUA_THU)
        dem = thu_doc_chu(token, thu)
        dem["khong_doc"] = dem_loi["khong_doc"]
    except GmailError as e:
        sys.exit(str(e))
    noi_dung = bao_cao(thu, dem, a.tu, rac)
    ra.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(ra, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(noi_dung)
    print(f"Đã ghi báo cáo {ra} (quyền 600).")


if __name__ == "__main__":
    main()
