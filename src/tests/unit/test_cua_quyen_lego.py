"""Lego nào mở màn thì backend phải HỎI đúng quyền ấy (kiểm toán 27/09/2026).

VÌ SAO CÓ FILE NÀY. Kiểm toán 27/09 gặp ba lego "chỉ là nhãn": quyền đã khai
(`worklist.handle`, `roster.view`, `partner.work`), thanh bên đã đi theo nó, nhưng
KHÔNG lệnh backend nào kiểm — thu lego thì mục biến khỏi thanh bên còn API vẫn mở
theo vai. Bài này đọc `NAV_QUYEN` (lib/roles.ts — quyền mở từng màn) rồi đòi mỗi
quyền ấy xuất hiện như một GIÁ TRỊ trong mã backend (không tính chú thích, docstring,
danh mục và bảng module) — tức có ít nhất một chỗ hỏi nó.

Và canh riêng ba cửa vừa nối, để ai lỡ tay trả về cửa vai là đỏ ngay.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

from clinicai.api import identity as identity_mod
from clinicai.permissions.catalogue import QUYEN

SRC = Path(__file__).resolve().parents[2]
BACKEND = SRC / "clinicai"
ROLES_TS = SRC / "dashboard" / "lib" / "roles.ts"

#: Khai báo, không phải chỗ kiểm: danh mục quyền và bảng ổ cắm module.
_KHONG_TINH = {BACKEND / "permissions" / "catalogue.py", BACKEND / "modules.py"}


def _quyen_mo_man() -> set[str]:
    src = ROLES_TS.read_text(encoding="utf-8")
    khoi = src[src.index("const NAV_QUYEN") : src.index("const TAT_KHOI_THANH_BEN")]
    return set(re.findall(r'"([a-z_]+\.[a-z_.]+)"', khoi))


def _chuoi_trong_ma(p: Path) -> set[str]:
    """Mọi hằng chuỗi trong một tệp, TRỪ docstring."""
    cay = ast.parse(p.read_text(encoding="utf-8"))
    docstring: set[int] = set()
    for nut in ast.walk(cay):
        if isinstance(
            nut, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            dau = nut.body[0] if nut.body else None
            if (
                isinstance(dau, ast.Expr)
                and isinstance(dau.value, ast.Constant)
                and isinstance(dau.value.value, str)
            ):
                docstring.add(id(dau.value))
    return {
        nut.value
        for nut in ast.walk(cay)
        if isinstance(nut, ast.Constant)
        and isinstance(nut.value, str)
        and id(nut) not in docstring
    }


def test_bo_doc_con_song() -> None:
    quyen = _quyen_mo_man()
    assert len(quyen) >= 25, f"chỉ đọc được {len(quyen)} quyền từ NAV_QUYEN"
    assert quyen <= set(QUYEN), f"quyền lạ: {sorted(quyen - set(QUYEN))}"


def test_moi_quyen_mo_man_deu_co_cho_backend_hoi() -> None:
    co: set[str] = set()
    for p in BACKEND.rglob("*.py"):
        if p not in _KHONG_TINH:
            co |= _chuoi_trong_ma(p)
    nhan = sorted(_quyen_mo_man() - co)
    assert not nhan, (
        "Lego chỉ là NHÃN — quyền mở màn mà không lệnh backend nào hỏi, nên thu "
        f"lego chỉ mất mục trên thanh bên còn API vẫn mở: {nhan}"
    )


def test_viec_can_xu_ly_hoi_worklist_handle() -> None:
    from clinicai.api.v1.routers import work_items
    from clinicai.services import work_item_service

    # Đợt 3 (27/09/2026, "chỉ dùng lego"): hàng đợi tiếp đón cũng theo lego.
    assert work_item_service.QUYEN_THEO_KHU == {
        "khu_van_hanh": "worklist.handle",
        "bang_dieu_phoi": "reception.checkin.perform",
    }
    # Cửa đọc khu và lệnh trên việc đều đi qua bảng ấy.
    assert "QUYEN_THEO_KHU" in inspect.getsource(
        work_items.require_workspace_read_access
    )
    assert "QUYEN_THEO_KHU" in inspect.getsource(
        work_item_service.WorkItemService.issue
    )


def test_lich_lam_viec_hoi_roster_view() -> None:
    from clinicai.main import app

    for route in app.routes:
        if getattr(route, "path", "") == "/api/v1/roster/lich-tuan":
            quyen = {
                q
                for d in route.dependant.dependencies  # type: ignore[attr-defined]
                for q in getattr(d.call, "quyen", ())
            }
            assert "roster.view" in quyen
            return
    raise AssertionError("không thấy đường /api/v1/roster/lich-tuan")


def test_doi_tac_hoi_partner_work_chu_khong_hoi_vai() -> None:
    nguon = inspect.getsource(identity_mod.get_partner_identity)
    assert '"partner.work"' in nguon
    assert "ClinicRole.PARTNER" not in nguon
    # Không được nằm sau get_current_identity — hàm ấy từ chối vai PARTNER.
    assert "get_current_identity" not in nguon.split('"""')[0] + nguon.split('"""')[-1]
