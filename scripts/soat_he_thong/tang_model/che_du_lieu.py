"""Bộ LỌC trước khi mã nguồn rời máy.

Quang đồng ý "chỉ code (và dữ liệu staging đã che) ra khỏi máy". Bộ lọc này biến lời
đồng ý đó thành mã: đường dẫn nào KHÔNG BAO GIỜ gửi, và mẫu chuỗi nào bị che nếu
lỡ nằm trong mã. Không thay thế việc không đặt bí mật vào code — chỉ là lưới thứ hai.

Tầng này KHÔNG gửi dữ liệu database. Dữ liệu thật chưa từng đi qua đây.
"""

from __future__ import annotations

import re

#: Đường dẫn (tiền tố hoặc mẫu con) không bao giờ gửi.
CAM_DUONG = (
    ".env",
    "secrets",
    "supabase/fixtures",  # tài khoản/khách thử có thể giống thật
    "scripts/staff-emails",
    ".pem",
    ".key",
    "id_rsa",
    "node_modules/",
    ".git/",
    "ket-qua/",
    "backup",
    "dump",
    ".media/",
)
#: Mẫu giống bí mật → che. Thận trọng nghiêng về che nhiều.
MAU_BI_MAT = (
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*KEY-----", re.S),
    re.compile(
        r"""(?i)\b(?:password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*["'][^"'\s]{8,}["']"""
    ),
)
#: Số điện thoại VN và email trong mã (vd dữ liệu mẫu trong test) — che luôn.
MAU_CA_NHAN = (
    re.compile(r"(?<!\d)(?:\+?84|0)(?:3|5|7|8|9)\d{8}(?!\d)"),
    re.compile(r"\b[\w.+-]+@(?!dr4women\.local\b|example\.)[\w-]+\.[\w.]+\b"),
)


def duoc_gui(duong: str) -> bool:
    d = duong.replace("\\", "/").lower()
    return not any(c in d for c in CAM_DUONG)


def sach(text: str) -> tuple[str, int]:
    """(văn bản đã che, số chỗ đã che)."""
    n = 0
    for m in (*MAU_BI_MAT, *MAU_CA_NHAN):
        text, k = m.subn("«ĐÃ-CHE»", text)
        n += k
    return text, n
