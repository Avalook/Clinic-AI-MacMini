"""Thư kết quả GIẢ cho video hướng dẫn "Kết quả về qua Gmail" — CHỈ stack local.

Không đọc hộp thư thật: thay 4 hàm của `gmail_api` bằng một hộp thư giả rồi chạy ĐÚNG
một vòng quét thật (`gmail.mot_vong`) — tờ, lý do chờ, Kho email ra y như prod.

    PYTHONPATH=src DATABASE_URL=… MEDIA_ROOT=… \
        python scripts/video-huong-dan/gmail_gia.py

Năm thư, mỗi thư một tình huống kịch bản cần (khách do `dung-du-lieu.mjs` dựng trước):
  tu_gan   khách có việc HPV đã lấy mẫu, PDF ghi HPV            ⇒ tự gán (dòng xanh)
  ho_so    khách đúng, đã khám hôm nay, chưa có chỉ định       ⇒ vào hồ sơ theo lượt
  nhieu    khách có HPV + ThinPrep cùng chờ, PDF không ghi loại ⇒ "nhiều chỉ định"
  la       tên + SĐT không có trong hệ thống                   ⇒ "không khớp khách"
  cu       thư trước mốc tự ghép                               ⇒ chỉ lưu ở Kho email
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import asyncpg

from clinicai.services.xet_nghiem import gmail, gmail_api
from clinicai.services.xet_nghiem.gmail_api import PhanPdf, ThuGmail

EMAIL = "ketqua@medlatec-mau.test"
MIEN = EMAIL.split("@")[1]
XAC_THUC = (
    f"mx.google.com; dkim=pass header.i=@{MIEN}; spf=pass smtp.mailfrom={EMAIL};"
    f" dmarc=pass header.from={MIEN}"
)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
VN = ZoneInfo("Asia/Ho_Chi_Minh")

#: (khoá, tên, SĐT, năm sinh, xét nghiệm in trên PDF, lùi bao nhiêu ngày)
THU = [
    ("tu_gan", "Hoàng Thị Thu Trang", "0900000121", 1993, "HPV định type PCR", 0),
    ("ho_so", "Ngô Thị Bích Ngọc", "0900000122", 1990, "Tổng phân tích máu", 0),
    ("nhieu", "Đặng Thị Kim Oanh", "0900000123", 1995, "Mẫu bệnh phẩm phụ khoa", 0),
    ("la", "Lý Thị Mẫu", "0900000199", 1985, "HPV định type PCR", 0),
    ("cu", "Hoàng Thị Thu Trang", "0900000121", 1993, "HPV định type PCR", 17),
]


def _html(ten: str, sdt: str, ns: int, xn: str, ngay: str) -> str:
    return f"""<!doctype html><meta charset="utf-8"><style>
body{{font-family:Arial,sans-serif;margin:48px;color:#1f2933}}
h1{{font-size:22px;margin:0}} .mau{{color:#b42318;font-weight:700;margin:6px 0 24px}}
table{{border-collapse:collapse;width:100%;margin-top:18px}}
td,th{{border:1px solid #cbd2d9;padding:8px;text-align:left;font-size:14px}}
</style>
<h1>MEDLATEC MẪU — PHIẾU KẾT QUẢ XÉT NGHIỆM</h1>
<p class="mau">TỆP MẪU DỰNG CHO VIDEO HƯỚNG DẪN — KHÔNG PHẢI KẾT QUẢ THẬT</p>
<p>Họ tên: <b>{ten.upper()}</b> &nbsp; Năm sinh: {ns}</p>
<p>SĐT: {sdt}</p><p>Ngày xét nghiệm: {ngay}</p>
<table><tr><th>Xét nghiệm</th><th>Kết quả</th><th>Tham chiếu</th></tr>
<tr><td>{xn}</td><td>Âm tính</td><td>Âm tính</td></tr></table>
"""


def _pdf(html: str, ra: Path) -> bytes:
    nguon = ra.with_suffix(".html")
    nguon.write_text(html, encoding="utf-8")
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={ra}", nguon.as_uri()],
        check=True, capture_output=True, timeout=60,
    )  # fmt: skip
    return ra.read_bytes()


class HopThuGia:
    """Hộp thư giả: chỉ trả thư của EMAIL; đối tác khác của stack local ⇒ trống."""

    def __init__(self) -> None:
        self.thu: dict[str, ThuGmail] = {}
        self.noi: dict[str, bytes] = {}

    async def liet_ke(
        self, _kh: object, q: str, trang: str | None = None, so: int = 100
    ) -> tuple[list[str], str | None, int]:
        if not q.startswith(f"from:{EMAIL} "):
            return [], None, 0
        return ([] if trang else list(self.thu)), None, len(self.thu)

    async def doc_thu(self, _kh: object, mid: str) -> ThuGmail | None:
        return self.thu.get(mid)

    async def tai_phan(self, _kh: object, mid: str, p: PhanPdf) -> bytes:
        return self.noi[mid]


def _dung_thu(hop: HopThuGia, tmp: Path) -> None:
    lan = time.strftime("%H%M%S")
    bay_gio = datetime.now(UTC)
    for i, (khoa, ten, sdt, ns, xn, lui) in enumerate(THU):
        # Thư về SAU lúc khách check-in / bác sĩ chỉ định (như đời thật) — thư sớm hơn
        # thì chỉ định "nhập sau thư" không còn là ứng viên.
        nhan = bay_gio - timedelta(days=lui) + timedelta(seconds=i)
        ngay = nhan.astimezone(VN).strftime("%d/%m/%Y")
        mid = f"video{lan}{khoa.replace('_', '')}"
        hop.noi[mid] = _pdf(_html(ten, sdt, ns, xn, ngay), tmp / f"{khoa}.pdf")
        hop.thu[mid] = ThuGmail(
            id=mid,
            nhan_luc=nhan,
            tu=EMAIL,
            tieu_de=f"Kết quả xét nghiệm: {ten.upper()} - Ngày xét nghiệm: {ngay}",
            than=f"Kính gửi phòng khám, Medlatec Mẫu gửi kết quả. NS: {ns}",
            pdf=[
                PhanPdf("1", f"KQ_{sdt[-4:]}_{lan}.pdf", len(hop.noi[mid]), "a", None)
            ],
            xac_thuc=XAC_THUC,
        )


async def main() -> int:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg", "postgresql")
    if urlparse(url).hostname not in ("127.0.0.1", "localhost"):
        print("Chỉ chạy với stack local.", file=sys.stderr)
        return 2
    pool = await asyncpg.create_pool(url, min_size=1, max_size=4)
    assert pool is not None
    cid = await pool.fetchval(
        "SELECT clinic_id::text FROM doi_tac WHERE email_gui_ket_qua = $1", EMAIL
    )
    if cid is None:
        print(f"Chưa có đối tác mang email {EMAIL} — chạy dung-du-lieu trước.")
        return 1
    hop = HopThuGia()
    with tempfile.TemporaryDirectory() as tmp:
        _dung_thu(hop, Path(tmp))
    os.environ[gmail.BIEN_PHONG_KHAM] = cid
    gmail_api.co_cau_hinh = lambda: True  # type: ignore[assignment]
    gmail_api.liet_ke = hop.liet_ke  # type: ignore[assignment]
    gmail_api.doc_thu = hop.doc_thu  # type: ignore[assignment]
    gmail_api.tai_phan = hop.tai_phan  # type: ignore[assignment]
    kq = await gmail.mot_vong(pool)
    rows = await pool.fetch(
        "SELECT email_message_id AS mid, ly_do_cho, luu_tru_vi_sao,"
        "       tep_ket_qua_id IS NOT NULL AS co_to"
        "  FROM drive_tep WHERE email_message_id = ANY($1::text[]) ORDER BY 1",
        list(hop.thu),
    )
    print(f"  · quét Gmail giả: {kq}")
    for r in rows:
        print(
            f"  · {r['mid']}: tờ={r['co_to']} chờ={r['ly_do_cho']}"
            f" lưu trữ={r['luu_tru_vi_sao']}"
        )
    await pool.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
