"""Vai nào THẤY được một màn thì phải GỌI được dữ liệu của màn đó.

VÌ SAO CÓ FILE NÀY. Menu bên trái do ``NAV_ROLES`` trong ``lib/roles.ts`` quyết
định; quyền gọi API do ``require_role(...)`` trong FastAPI quyết định. Hai bảng,
hai ngôn ngữ, không ai đối chiếu — và khi chúng lệch thì lỗi hiện ra dưới dạng
tệ nhất có thể: nhân viên thấy mục trên menu, bấm vào, và nhận một trang trắng
hoặc một thông báo cấm. Không phải "chưa làm xong", cũng không phải "sai mật
khẩu" — không có cách nào để họ đoán được chuyện gì đang xảy ra.

Chuyện này đã xảy ra đủ nhiều để người ta phải viết chú thích tay ngay trong
``roles.ts``: "/nhan-su chỉ MANAGEMENT vì routers/staff.py gác MANAGEMENT",
"/ops/telemetry cũng vậy". Chú thích tay đúng cho tới lần ai đó đổi một bên.

CÁCH BẮT. Đọc ``NAV_ROLES`` từ nguồn TypeScript, đọc tập vai của từng route
thẳng từ đối tượng ``app`` đang chạy (``RoleGuard.allowed_roles`` — lớp ấy vốn
được viết ra để đọc lại được), rồi với mỗi trang có giới hạn vai, đòi:

    vai thấy được menu  ⊆  vai gọi được endpoint mà trang ĐÓ tự gọi lúc dựng

CHỈ KIỂM TRANG KHÔNG RẼ NHÁNH THEO VAI. ``/tasks`` gọi ``/cashier/board`` nhưng
chỉ khi người mở là thu ngân — nó là một trang dựng ra ba màn khác nhau cho ba
nhóm người. Với những trang như thế, phép so "tập vai của trang ⊆ tập vai của
endpoint" là sai đề, nên chúng bị BỎ QUA và ĐẾM lại (xem test cuối file), chứ
không được lặng lẽ tính là đã kiểm.

GIỚI HẠN, nói rõ thay vì để người sau tự phát hiện:
  * Chỉ xét lời gọi ``fetchFromBackend`` viết thẳng trong ``page.tsx``. Nút bấm
    trong component con, và các lời gọi đi vòng qua route Next ``/api/...``,
    nằm ngoài tầm.
  * Chỉ bắt chiều "thấy mà không gọi được". Chiều ngược lại — endpoint KHÔNG có
    chốt vai nào trong khi màn hình chỉ mở cho Quản lý — là một danh sách riêng
    cần người quyết từng cái, không phải thứ test này tự sửa được.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from clinicai.api.identity import RoleGuard
from clinicai.main import app

# src/tests/ -> src/ -> src/dashboard
DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard"
ROLES_TS = DASHBOARD / "lib" / "roles.ts"
PAGES_ROOT = DASHBOARD / "app"

# Chốt chống-xanh-giả: dưới ngưỡng này nghĩa là bộ đọc đã hỏng (đổi cách viết
# NAV_ROLES, đổi tên fetchFromBackend…) và test đang gác rỗng.
MIN_PAGES_CHECKED = 4

# Dấu hiệu một trang RẼ NHÁNH theo vai — nó dựng nhiều màn khác nhau cho nhiều
# nhóm người, nên lời gọi trong đó là có điều kiện.
_ROLE_BRANCH = re.compile(
    r"\brole\s*===|\bis[A-Z]\w*Role\(|\bcan[A-Z]\w*\(|\bisCashierRole\b"
)


def _role_lists_in(src: str) -> dict[str, list[str]]:
    """``const DOCTOR_ROLES_LIST: ClinicRole[] = [...]`` → tên: các vai."""
    pattern = r"const (\w+):\s*ClinicRole\[\]\s*=\s*\[(.*?)\]"
    return {
        m.group(1): re.findall(r'"(\w+)"', m.group(2))
        for m in re.finditer(pattern, src, re.S)
    }


def _nav_roles() -> dict[str, list[str] | str]:
    src = ROLES_TS.read_text(encoding="utf-8")
    spreads = _role_lists_in(src)
    block = re.search(r"const NAV_ROLES[^=]*=\s*\{(.*?)\n\};", src, re.S)
    assert block is not None, (
        f"không tìm thấy NAV_ROLES trong {ROLES_TS} — cách khai báo đã đổi và "
        "chốt này đang gác rỗng."
    )
    nav: dict[str, list[str] | str] = {}
    for m in re.finditer(r'"(/[^"]*)":\s*(?:"(all)"|\[(.*?)\])', block.group(1), re.S):
        href, everyone, body = m.groups()
        if everyone:
            nav[href] = "all"
            continue
        roles = re.findall(r'"(\w+)"', body)
        for name in re.findall(r"\.\.\.(\w+)", body):
            roles += spreads.get(name, [])
        nav[href] = sorted(set(roles))
    return nav


def _guard_roles(dependant: Any) -> set[str]:
    """Mọi vai được RoleGuard trên route này (kể cả guard ở tầng router)."""
    found: set[str] = set()
    call = getattr(dependant, "call", None)
    if isinstance(call, RoleGuard):
        found |= {r.value for r in call.allowed_roles}
    for sub in getattr(dependant, "dependencies", []):
        found |= _guard_roles(sub)
    return found


def _guarded_routes() -> dict[str, set[str]]:
    routes: dict[str, set[str]] = {}
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        path = getattr(route, "path", None)
        if dependant is None or path is None:
            continue
        roles = _guard_roles(dependant)
        if roles:
            routes.setdefault(path, set()).update(roles)
    return routes


def _matches(call: str, route: str) -> bool:
    """Cùng phép so đoạn-theo-đoạn với test_dashboard_backend_paths."""
    call_segments, route_segments = call.split("/"), route.split("/")
    if len(call_segments) != len(route_segments):
        return False
    for got, want in zip(call_segments, route_segments):
        if want.startswith("{") and want.endswith("}"):
            continue
        if got == "{}":
            continue
        if got != want:
            return False
    return True


def _href_of(page: Path) -> str:
    """``app/(dashboard)/nhac-tai-kham/page.tsx`` → ``/nhac-tai-kham``."""
    parts = page.relative_to(PAGES_ROOT).parts[:-1]
    visible = [p for p in parts if not (p.startswith("(") and p.endswith(")"))]
    return "/" + "/".join(visible)


def _backend_calls(src: str) -> list[str]:
    raw = re.findall(r"fetchFromBackend(?:<[^>]*>)?\(\s*[`\"']([^`\"']+)", src)
    calls = []
    for path in raw:
        path = path.split("?", 1)[0]
        calls.append(re.sub(r"\$\{[^}]*\}", "{}", path).rstrip("/"))
    return calls


def _audit() -> tuple[list[str], int, list[str]]:
    """(vi phạm, số trang đã kiểm, trang bỏ qua vì rẽ nhánh theo vai)"""
    nav = _nav_roles()
    guarded = _guarded_routes()
    violations: list[str] = []
    checked = 0
    branching: list[str] = []

    for page in sorted(PAGES_ROOT.rglob("page.tsx")):
        href = _href_of(page)
        allowed = nav.get(href)
        if allowed is None or allowed == "all":
            continue
        src = page.read_text(encoding="utf-8")
        calls = _backend_calls(src)
        if not calls:
            continue
        if _ROLE_BRANCH.search(src):
            branching.append(href)
            continue
        checked += 1
        for call in calls:
            for route, roles in guarded.items():
                if not _matches(call, route):
                    continue
                blocked = sorted(set(allowed) - roles)
                if blocked:
                    violations.append(
                        f"  ✗ {href} mở cho {blocked} nhưng {route} từ chối họ\n"
                        f"      menu cho : {sorted(allowed)}\n"
                        f"      API cho  : {sorted(roles)}"
                    )
    return violations, checked, branching


def test_every_role_that_sees_a_page_can_load_that_page() -> None:
    violations, _, _ = _audit()
    if violations:
        raise AssertionError(
            "NAV_ROLES (roles.ts) mở màn cho những vai mà require_role (FastAPI) "
            "chặn — họ sẽ thấy mục trên menu rồi bấm vào và nhận trang trắng:\n"
            + "\n".join(violations)
            + "\n\nSửa MỘT trong hai: bớt vai ở NAV_ROLES, hoặc mở thêm ở "
            "require_role. Đừng sửa cả hai cho khớp nhau mà chưa hỏi bên nào đúng."
        )


def test_the_audit_still_sees_the_dashboard() -> None:
    """Chốt chống-xanh-giả: bộ đọc trên phải thật sự kiểm được vài trang."""
    _, checked, branching = _audit()
    assert checked >= MIN_PAGES_CHECKED, (
        f"chỉ kiểm được {checked} trang (chờ ít nhất {MIN_PAGES_CHECKED}). "
        "Có thể NAV_ROLES hoặc fetchFromBackend đã đổi cách viết và test đang "
        f"gác rỗng — kiểm {ROLES_TS} và {PAGES_ROOT}."
    )
    # Không phải khẳng định, chỉ để người đọc thấy phần nào NẰM NGOÀI tầm.
    assert isinstance(branching, list)
