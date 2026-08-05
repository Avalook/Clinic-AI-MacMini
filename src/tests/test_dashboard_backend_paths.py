"""Mọi đường dẫn /api/v1/... dashboard gọi phải trùng một route FastAPI có thật.

VÌ SAO CÓ FILE NÀY. ``test_router_wiring.py`` canh mối nối backend↔backend: router
nào tồn tại thì phải được mount, sau vụ ``clinical_records`` viết xong mà không ai
include nên trả 404 trong im lặng. Mối nối còn lại — dashboard gọi xuống FastAPI —
không có gì canh, và nó hỏng theo đúng cách đó:

    backend  :  GET/PUT /api/v1/feature-mode          (routers/config.py)
    dashboard:  GET/PUT /api/v1/config/feature-mode   (app/api/config/feature-mode)

Thừa đúng một đoạn ``config``. Nguồn gốc gần như chắc chắn là ``tags=["config"]``
trong ``main.py`` — tags chỉ gom nhóm trong trang /docs, KHÔNG tạo đoạn đường dẫn.
Màn đổi chế độ phòng khám vì thế 404 suốt, không ai thấy: TypeScript không biết
backend có route nào, mypy không biết dashboard gọi gì, và không test nào bắc cầu
qua hai ngôn ngữ. Nó chỉ lộ ra khi có người đọc tay hai file cạnh nhau.

CÁCH BẮT. Quét chuỗi ký tự trong ``src/dashboard``, chuẩn hoá ``${biến}`` thành một
đoạn bất kỳ, rồi đối chiếu với bảng route thật lấy từ chính đối tượng ``app``.
Không cần chạy server, không cần database — nên nó chạy được trong CI ở mọi PR.

GIỚI HẠN, nói rõ thay vì để người sau tự phát hiện:
  * Chỉ kiểm ĐƯỜNG DẪN, không kiểm phương thức (GET/POST) hay hình dạng body.
  * Chỉ thấy đường dẫn viết thẳng trong chuỗi. Đường ghép động hoàn toàn
    (``API + biến``) nằm ngoài tầm — nhưng repo này viết thẳng nên vẫn phủ được 62 chỗ.
  * Đoạn ``${biến}`` khớp với mọi đoạn, kể cả chỗ backend đòi chữ cố định.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from clinicai.main import app

# src/tests/ -> src/ -> src/dashboard
DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard"
SCAN_DIRS = ("app", "lib", "components")

# Số đường dẫn tối thiểu phải quét được. Không có ngưỡng này, một lần đổi cấu trúc
# (gom đường dẫn vào file hằng số chẳng hạn) sẽ làm bộ quét trả về rỗng và test
# vẫn XANH — một cái chốt gác im lặng còn tệ hơn không có chốt.
MIN_EXPECTED_CALLS = 40

# Chỉ nhận đường dẫn nằm trong chuỗi: ngay sau dấu nháy hoặc backtick.
_CALL = re.compile(r"""(?<=["'`])/api/v1/[^"'`\s]*""")
_TEMPLATE = re.compile(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
# (?<!:) để không cắt nhầm "https://..."
_LINE_COMMENT = re.compile(r"(?<!:)//.*$", re.M)


def _strip_comments(src: str) -> str:
    """Văn xuôi có nhắc đường dẫn không phải là lời gọi."""
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", src))


def _normalise(path: str) -> str:
    path = path.split("?", 1)[0]
    path = _TEMPLATE.sub("{}", path)
    return path.rstrip("/") or "/"


def _mounted_paths() -> list[str]:
    return sorted({r.path for r in app.routes if hasattr(r, "path")})


def _dashboard_calls() -> dict[str, set[str]]:
    """{đường dẫn đã chuẩn hoá: {file gọi nó}}"""
    calls: dict[str, set[str]] = {}
    for name in SCAN_DIRS:
        root = DASHBOARD / name
        if not root.exists():
            continue
        for f in (*root.rglob("*.ts"), *root.rglob("*.tsx")):
            src = _strip_comments(f.read_text(encoding="utf-8", errors="ignore"))
            for raw in _CALL.findall(src):
                calls.setdefault(_normalise(raw), set()).add(
                    str(f.relative_to(DASHBOARD))
                )
    return calls


def _matches(call: str, route: str) -> bool:
    call_segments, route_segments = call.split("/"), route.split("/")
    if len(call_segments) != len(route_segments):
        return False
    for got, want in zip(call_segments, route_segments):
        if want.startswith("{") and want.endswith("}"):
            continue  # tham số của backend: khớp mọi đoạn
        if got == "{}":
            continue  # biến của frontend: không kết luận được, cho qua
        if got != want:
            return False
    return True


def test_dashboard_only_calls_paths_that_exist() -> None:
    mounted = _mounted_paths()
    calls = _dashboard_calls()

    broken = {
        call: files
        for call, files in calls.items()
        if not any(_matches(call, route) for route in mounted)
    }

    if broken:
        lines = ["dashboard gọi những đường dẫn FastAPI không có → 404:"]
        for call, files in sorted(broken.items()):
            near = difflib.get_close_matches(call, mounted, n=3, cutoff=0.6)
            lines.append(f"\n  ✗ {call}")
            for f in sorted(files):
                lines.append(f"      gọi ở: {f}")
            if near:
                lines.append(f"      ý anh là: {', '.join(near)}")
        raise AssertionError("\n".join(lines))


def test_the_scanner_still_sees_the_dashboard() -> None:
    """Chốt chống-xanh-giả: bộ quét trên phải thật sự tìm thấy thứ gì đó."""
    found = len(_dashboard_calls())
    assert found >= MIN_EXPECTED_CALLS, (
        f"chỉ quét được {found} đường dẫn (chờ ít nhất {MIN_EXPECTED_CALLS}). "
        "Có thể dashboard đã đổi cách viết đường dẫn và test trên đang gác rỗng — "
        f"kiểm tra {DASHBOARD} và cập nhật bộ quét."
    )
