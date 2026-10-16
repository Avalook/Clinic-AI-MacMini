"""Bộ nhớ đệm trình duyệt cho tài nguyên tĩnh (14/10/2026, PERF).

Đo log prod 30 phút: manifest + icon PWA + favicon = ~28% request, mỗi lần chuyển
trang bị hỏi lại vì Next trả `max-age=0`. Snippet `tai_nguyen_tinh` ở Caddy sửa.

Cú pháp Caddy ở đây ĐÃ THỬ THẬT bằng `curl -I` (caddy:2-alpine, upstream giả trả
`max-age=0`): ba kiểu viết "gần giống" sai im lặng hoặc ra header đôi. Test này
canh: (1) hai Caddyfile dùng đúng MỘT bản snippet, (2) snippet đứng TRƯỚC `handle`
bắt-hết (không thì Next trả lời trước), (3) đúng kiểu cú pháp đã thử, (4) tài
nguyên có thể đổi theo phiên/đăng nhập KHÔNG lọt vào danh sách.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CADDYFILE = REPO / "caddy" / "Caddyfile"
CADDYFILE_STAGING = REPO / "caddy" / "Caddyfile.staging"

CACHE_CONTROL = (
    'header >Cache-Control "public, max-age=86400, stale-while-revalidate=604800"'
)
DUONG_TINH = {
    "/manifest.webmanifest",
    "/favicon.ico",
    "/icon.png",
    "/apple-icon.png",
    "/pwa/*",
    "/logo.png",
    "/clinicai-logo.svg",
}


def _snippet(duong_dan: Path) -> str:
    s = duong_dan.read_text(encoding="utf-8")
    m = re.search(r"^\(tai_nguyen_tinh\) \{\n.*?^\}\n", s, flags=re.S | re.M)
    assert m, f"{duong_dan.name}: thiếu snippet (tai_nguyen_tinh)"
    return m.group(0)


def test_hai_caddyfile_dung_cung_mot_ban_snippet() -> None:
    assert _snippet(CADDYFILE) == _snippet(CADDYFILE_STAGING)


def test_snippet_dung_cu_phap_da_thu_that() -> None:
    sn = _snippet(CADDYFILE)
    # `>` = ghi sau cùng, đè Cache-Control của upstream; `header_down @ok …` và
    # `header` không dấu `>` đều sai (không tác dụng / header đôi).
    assert CACHE_CONTROL in sn
    assert "handle_response @ok" in sn and "@ok status 2xx" in sn
    assert "copy_response\n" in sn
    assert "header_down" not in sn
    assert "copy_response_headers" not in sn
    # Không `immutable`: các tệp này không mang hash trong tên.
    assert "immutable" not in sn


def test_snippet_chi_gom_tai_nguyen_tinh_khong_gan_phien() -> None:
    m = re.search(r"@tinh path (.+)\n", _snippet(CADDYFILE))
    assert m
    # Đúng danh sách này — thêm đường nào phải sửa test có chủ ý: đường dẫn của
    # trang/API/tệp kết quả mang dữ liệu bệnh nhân KHÔNG được vào đây.
    assert set(m.group(1).split()) == DUONG_TINH


def test_import_dung_truoc_handle_bat_het_o_moi_site_nhan_dashboard() -> None:
    bat_het = r"^\thandle \{\n\t\treverse_proxy dashboard:3000\n\t\}$"
    for tep in (CADDYFILE, CADDYFILE_STAGING):
        # Bỏ phần định nghĩa snippet, chỉ xét thân các site.
        than = tep.read_text(encoding="utf-8").replace(_snippet(tep), "")
        imports = [
            m.start()
            for m in re.finditer(r"^\timport tai_nguyen_tinh$", than, flags=re.M)
        ]
        cuoi = [m.start() for m in re.finditer(bat_het, than, flags=re.M)]
        assert imports, tep.name
        # Mỗi `handle` bắt-hết có đúng một import đứng trước, không xen handle khác.
        assert len(imports) == len(cuoi), tep.name
        for i, b in zip(imports, cuoi, strict=True):
            assert i < b, tep.name
            xen = than[i:b].replace("import tai_nguyen_tinh", "")
            assert "handle" not in xen, tep.name
