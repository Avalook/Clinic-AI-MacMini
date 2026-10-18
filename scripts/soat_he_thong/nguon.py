"""Lớp ĐỌC repo cho các bộ quét — chỉ đọc, không ghi, không mạng, không database.

Mọi bộ quét lấy dữ liệu qua `Nguon` để (a) có MỘT chỗ cache tệp, (b) bài kiểm
"agent chỉ đọc" (`test_agent_soat_chi_doc.py`) chỉ phải canh một cửa, (c) bộ quét
chạy được trên cây thư mục GIẢ trong test (gốc là tham số, không phải hằng).
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

FuncNode = ast.FunctionDef | ast.AsyncFunctionDef

GOC = Path(__file__).resolve().parent.parent.parent
#: Mọi router đều gắn dưới tiền tố này ở `src/clinicai/main.py`.
TIEN_TO_API = "/api/v1"
HTTP = ("get", "post", "put", "patch", "delete")


def ten_goi(n: ast.expr) -> str | None:
    """Tên cuối của một biểu thức gọi: `a.b.c(...)` → "c"."""
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        return n.attr
    if isinstance(n, ast.Call):
        return ten_goi(n.func)
    return None


@dataclass(frozen=True)
class Route:
    method: str
    duong: str
    tep: Path
    ten: str
    dong: int
    #: Hàm gọi `bao_da_nghi` — đường cũ, trả 410, không còn là cửa ghi thật.
    da_nghi: bool


class Nguon:
    """Cửa duy nhất vào repo."""

    def __init__(self, goc: Path = GOC) -> None:
        self.goc = goc
        self.py = goc / "src" / "clinicai"
        self.tests = goc / "src" / "tests"
        self.dash = goc / "src" / "dashboard"
        self.migrations_dir = goc / "supabase" / "migrations"
        self._txt: dict[Path, str] = {}

    # ── đọc tệp ────────────────────────────────────────────────────────────
    def doc(self, p: Path) -> str:
        if p not in self._txt:
            self._txt[p] = p.read_text(encoding="utf8", errors="replace")
        return self._txt[p]

    def tuong_doi(self, p: Path) -> str:
        try:
            return str(p.resolve().relative_to(self.goc.resolve()))
        except ValueError:
            return str(p)

    def dong_thu(self, p: Path, n: int) -> str:
        ds = self.doc(p).splitlines()
        return ds[n - 1].strip() if 0 < n <= len(ds) else ""

    # ── liệt kê tệp ────────────────────────────────────────────────────────
    def py_nguon(self) -> list[Path]:
        return sorted(p for p in self.py.rglob("*.py") if "__pycache__" not in p.parts)

    def py_test(self) -> list[Path]:
        return sorted(
            p for p in self.tests.rglob("*.py") if "__pycache__" not in p.parts
        )

    def ts_dashboard(self) -> list[Path]:
        ra: list[Path] = []
        for p in self.dash.rglob("*"):
            if p.suffix not in (".ts", ".tsx"):
                continue
            if any(x in p.parts for x in ("node_modules", ".next", "tests", "e2e")):
                continue
            ra.append(p)
        return sorted(ra)

    def migrations(self) -> list[Path]:
        return sorted(self.migrations_dir.glob("*.sql"))

    # ── cây cú pháp Python + chỉ mục hàm ───────────────────────────────────
    @cached_property
    def cay_py(self) -> dict[Path, ast.Module]:
        ra: dict[Path, ast.Module] = {}
        for p in self.py_nguon():
            try:
                ra[p] = ast.parse(self.doc(p))
            except SyntaxError:
                continue
        return ra

    @cached_property
    def ham_theo_ten(self) -> dict[str, list[tuple[Path, FuncNode]]]:
        """Tên trần → mọi hàm cùng tên (đủ để theo dõi lời gọi không biết kiểu)."""
        ra: dict[str, list[tuple[Path, FuncNode]]] = defaultdict(list)
        for p, cay in self.cay_py.items():
            for n in ast.walk(cay):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    ra[n.name].append((p, n))
        return ra

    def dong_cua_ham(
        self, node: FuncNode, tran: int = 4
    ) -> list[tuple[Path, FuncNode]]:
        """Mọi hàm `node` gọi tới `tran` tầng (theo TÊN, nên rộng hơn thật: hai
        hàm trùng tên đều bị tính). Rộng là chủ ý — bộ quét tìm cái VẮNG MẶT, mà
        vắng mặt thì rộng tay là phía an toàn (ít báo nhầm)."""
        thay: set[int] = {id(node)}
        ra: list[tuple[Path, FuncNode]] = []
        hang: list[FuncNode] = [node]
        for _ in range(tran):
            moi: list[FuncNode] = []
            for h in hang:
                for x in ast.walk(h):
                    if not isinstance(x, ast.Call):
                        continue
                    t = ten_goi(x.func)
                    if t == "Depends" and x.args:
                        t = ten_goi(x.args[0])
                    for p, m in self.ham_theo_ten.get(t or "", []):
                        if id(m) not in thay:
                            thay.add(id(m))
                            ra.append((p, m))
                            moi.append(m)
            hang = moi
            if not hang:
                break
        return ra

    def van_ban_cua_ham(self, tep: Path, node: FuncNode) -> str:
        """Mã nguồn của hàm + chuỗi hằng cấp module mà thân hàm nhắc tới.

        SQL thường nằm ở hằng `_SQL_X = \"\"\"INSERT …\"\"\"` ngoài hàm; chỉ đọc thân
        hàm sẽ bỏ sót, và báo 'không ghi gì' là báo sai."""
        txt = ast.get_source_segment(self.doc(tep), node) or ""
        hang = self.hang_chuoi.get(tep, {})
        nhac = {x.id for x in ast.walk(node) if isinstance(x, ast.Name)}
        return txt + "\n" + "\n".join(hang[t] for t in sorted(nhac) if t in hang)

    @cached_property
    def hang_chuoi(self) -> dict[Path, dict[str, str]]:
        ra: dict[Path, dict[str, str]] = {}
        for p, cay in self.cay_py.items():
            d: dict[str, str] = {}
            for n in cay.body:
                if not isinstance(n, ast.Assign):
                    continue
                v = ast.get_source_segment(self.doc(p), n.value) or ""
                if '"' in v or "'" in v:
                    d.update({t.id: v for t in n.targets if isinstance(t, ast.Name)})
            ra[p] = d
        return ra

    # ── route FastAPI ──────────────────────────────────────────────────────
    @cached_property
    def routes(self) -> list[Route]:
        """Mọi `@router.<method>("/đường")` cấp module trong `api/v1`."""
        ra: list[Route] = []
        for tep, cay in self.cay_py.items():
            if "api" not in tep.parts or "v1" not in tep.parts:
                continue
            tien_to = ""
            for n in cay.body:
                if (
                    isinstance(n, ast.Assign)
                    and isinstance(n.value, ast.Call)
                    and ten_goi(n.value.func) == "APIRouter"
                ):
                    for kw in n.value.keywords:
                        if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                            tien_to = str(kw.value.value)
            for n in cay.body:
                if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                da_nghi = any(
                    isinstance(x, ast.Call) and ten_goi(x.func) == "bao_da_nghi"
                    for x in ast.walk(n)
                )
                for d in n.decorator_list:
                    if not (
                        isinstance(d, ast.Call)
                        and isinstance(d.func, ast.Attribute)
                        and ten_goi(d.func.value) == "router"
                        and d.func.attr in HTTP
                        and d.args
                        and isinstance(d.args[0], ast.Constant)
                    ):
                        continue
                    ra.append(
                        Route(
                            d.func.attr.upper(),
                            TIEN_TO_API + tien_to + str(d.args[0].value),
                            tep,
                            n.name,
                            n.lineno,
                            da_nghi,
                        )
                    )
        return ra


_BO_COMMENT_SQL = re.compile(r"--[^\n]*")


def bo_comment_sql(txt: str) -> str:
    return _BO_COMMENT_SQL.sub("", txt)
