#!/usr/bin/env python3
"""Sinh docs/BAN-DO-CODE.md — bản đồ "màn → API → router → service → test".

Tuyền 01/10/2026: "làm sao để tôi biết cần sửa bất cứ thứ gì ở đâu … để đưa
con AI khác biết và sửa ngay mà không cần quét toàn bộ code". BAN-DO-SUA.md
(viết tay) trả lời "muốn sửa gì → đi đâu"; tệp này là chuỗi file chi tiết, SINH
TỪ CODE để không bao giờ lỗi thời.

Phân tích TĨNH, chỉ thư viện chuẩn (regex cho TSX, ast cho Python):

  màn  app/**/page.tsx (kể cả app/print/**)
   └ thành phần nó import (tối đa 3 tầng, bỏ components/ui và tệp dùng chung)
      └ chuỗi "/api/…" chúng gọi  ──►  app/api/**/route.ts
                                         └ chuỗi "/api/v1/…" nó proxy tới
                                            └ hàm router FastAPI khớp decorator
                                               └ service gọi trong thân hàm
                                                  └ tệp test nhắc service đó

Chấp nhận không hoàn hảo: chỗ không suy được ghi "?" chứ không đoán.

    python3 scripts/ban-do-code.py           # ghi lại docs/BAN-DO-CODE.md
    python3 scripts/ban-do-code.py --kiem    # exit 1 nếu tệp lệch code (CI)
    python3 scripts/ban-do-code.py --in      # in ra stdout, không ghi
"""

# ruff: noqa: E501 — chuỗi tài liệu tiếng Việt và regex, cắt dòng chỉ làm khó đọc.
from __future__ import annotations

import ast
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
DASH = GOC / "src" / "dashboard"
APP = DASH / "app"
PY = GOC / "src" / "clinicai"
ROUTERS = PY / "api" / "v1" / "routers"
TESTS = GOC / "src" / "tests"
MIGRATIONS = GOC / "supabase" / "migrations"
DAU_RA = GOC / "docs" / "BAN-DO-CODE.md"

DONG_SINH = "> Sinh bởi `scripts/ban-do-code.py` lúc "
DUOI_TS = (".tsx", ".ts")
HTTP = ("get", "post", "put", "patch", "delete")
#: Gói Python KHÔNG tính là "service" (hạ tầng, quyền, khuôn dữ liệu).
BO_GOI = ("clinicai.api", "clinicai.core", "clinicai.schemas")
TANG_API = 3  # số tầng import đi theo để gom lời gọi /api
TANG_HIEN = 2  # số tầng import liệt kê ở dòng "thành phần"
NGUONG_DUNG_CHUNG = 0.25  # tệp mà > 25% số màn cùng import = hạ tầng, bỏ qua


def tuong_doi(p: Path) -> str:
    return p.relative_to(GOC).as_posix()


# ── Frontend ────────────────────────────────────────────────────────────────

RE_IMPORT = re.compile(
    r"""(?:import|export)\s[^;]*?\sfrom\s+["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)"""
)
# Chuỗi bắt đầu bằng /api/… — cho phép tiền tố `${API_BASE}` trong template.
RE_API = re.compile(r"""["'`](?:\$\{\w+\})?(/api/[^"'`\s?#]*)""")
RE_TITLE = re.compile(
    r"""metadata\s*=\s*\{\s*title:\s*["']([^"']+?)(?:\s*·\s*ClinicAI)?["']"""
)
RE_NAV = re.compile(r"""href:\s*"([^"]+)",\s*label:\s*"([^"]+)\"""")
RE_HANDLER = re.compile(
    r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE)\b"
)
RE_METHOD_TRUOC = re.compile(r"""["'](GET|POST|PUT|PATCH|DELETE)["']\s*,\s*$""")
RE_KHOA_TRUOC = re.compile(
    r"""(?<![\w/.-])["']?([A-Za-z_][\w-]*)["']?\s*:\s*(?:(?:async\s*)?\([^()]*\)\s*(?::\s*[\w<>| ]+)?=>\s*)?$"""
)
RE_CHUOI = re.compile(r"""["'`]([\w-]+)["'`]""")
RE_BANG_BANG = re.compile(r"""===\s*["']([\w-]+)["']\s*\?\s*$""")
RE_CASE = re.compile(r"""case\s+["']([\w-]+)["']\s*:""")
KHOA_CHUNG = {
    "path",
    "url",
    "duong",
    "href",
    "target",
    "endpoint",
    "backendPath",
    "default",
}
RE_TU_BANG = re.compile(r"""\.from\(\s*["']([a-z_][a-z0-9_]*)["']\s*\)""")


def doc(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def giai_import(tu: Path, dich: str) -> Path | None:
    if dich.startswith("@/"):
        goc = DASH / dich[2:]
    elif dich.startswith("."):
        goc = (tu.parent / dich).resolve()
    else:
        return None
    for ung in (goc, *(goc.with_name(goc.name + d) for d in DUOI_TS)):
        if ung.is_file() and ung.suffix in DUOI_TS:
            return ung
    for d in DUOI_TS:
        if (goc / f"index{d}").is_file():
            return goc / f"index{d}"
    return None


_import_cache: dict[Path, list[Path]] = {}


def cac_import(p: Path) -> list[Path]:
    if p not in _import_cache:
        ra: list[Path] = []
        for m in RE_IMPORT.finditer(doc(p)):
            dich = m.group(1) or m.group(2)
            f = giai_import(p, dich)
            if f is not None and f not in ra and "node_modules" not in f.parts:
                ra.append(f)
        _import_cache[p] = ra
    return _import_cache[p]


def la_ui(p: Path) -> bool:
    return (DASH / "components" / "ui") in p.parents


def duyet(page: Path, tang: int) -> dict[Path, int]:
    """Tệp → tầng (page = 0), theo import cục bộ, bỏ components/ui."""
    tham: dict[Path, int] = {page: 0}
    hang = [page]
    while hang:
        p = hang.pop(0)
        if tham[p] >= tang:
            continue
        for f in cac_import(p):
            if f in tham or la_ui(f) or f.name in ("page.tsx", "route.ts"):
                continue
            tham[f] = tham[p] + 1
            hang.append(f)
    return tham


def chuan_duong(s: str) -> list[str]:
    """'/api/visits/${id}/x' → ['api','visits','*','x']; '/' cuối = thêm '*'."""
    s = s.split("?")[0]
    # `${…}` ngay sau một chữ (không sau "/") là phần đuôi/chuỗi truy vấn → cắt.
    s = re.sub(r"(?<=[^/])\$\{.*$", "", s)
    if "${" in s:
        s = re.sub(r"\$\{[^}]*\}?", "*", s)
    phan = s.strip("/").split("/") if s.strip("/") else []
    ra = [
        "*" if ("*" in x or x.startswith("[") or x.startswith("{")) else x for x in phan
    ]
    if s.endswith("/") and ra:
        ra.append("*")
    return ra


def khop(goi: list[str], mau: list[str]) -> int:
    """-1 = không khớp; còn lại = số đoạn khớp NGUYÊN VĂN (càng cao càng đúng)."""
    if len(goi) != len(mau):
        return -1
    diem = 0
    for a, b in zip(goi, mau):
        if a == b:
            diem += 1
        elif a != "*" and b != "*":
            return -1
    return diem


def chon_tot_nhat(goi: list[str], ung: dict[str, list[str]]) -> list[str]:
    diem = {k: khop(goi, v) for k, v in ung.items()}
    cao = max((d for d in diem.values() if d >= 0), default=-1)
    return sorted(k for k, d in diem.items() if d == cao and cao >= 0)


def route_cua_page(p: Path) -> str:
    phan = [
        x
        for x in p.relative_to(APP).parent.parts
        if not (x.startswith("(") and x.endswith(")"))
    ]
    return "/" + "/".join(phan)


def route_cua_api(p: Path) -> str:
    return "/" + "/".join(("api", *p.relative_to(APP / "api").parent.parts))


@dataclass
class ApiNext:
    duong: str
    tep: Path
    #: (method?, path, khoá thao tác?) — khoá = tên mục trong bảng ánh xạ của
    #: route.ts (vd `"xep-phong": (id) => "/api/v1/…"`) hay nhánh `case "x":`.
    backend: list[tuple[str | None, str, str | None]] = field(default_factory=list)
    bang_thang: list[str] = field(default_factory=list)


def doc_api_next() -> dict[str, ApiNext]:
    ra: dict[str, ApiNext] = {}
    for tep in sorted(APP.glob("api/**/route.ts")):
        txt = doc(tep)
        a = ApiNext(route_cua_api(tep), tep)
        handlers = [(m.start(), m.group(1)) for m in RE_HANDLER.finditer(txt)]
        for m in re.finditer(r"""["'`](?:\$\{\w+\})?(/api/v1/[^"'`\s?#]*)""", txt):
            truoc = txt[max(0, m.start() - 80) : m.start()]
            mm = RE_METHOD_TRUOC.search(truoc)
            if mm:
                method: str | None = mm.group(1)
            else:
                ten = [h for pos, h in handlers if pos < m.start()]
                method = f"~{ten[-1]}" if ten else None
            khoa = None
            mk = RE_KHOA_TRUOC.search(txt[max(0, m.start() - 160) : m.start()])
            mb = RE_BANG_BANG.search(txt[max(0, m.start() - 160) : m.start()])
            if mk and mk.group(1) not in KHOA_CHUNG:
                khoa = mk.group(1)
            elif mb:
                khoa = mb.group(1)
            else:
                cs = list(RE_CASE.finditer(txt[max(0, m.start() - 400) : m.start()]))
                if cs:
                    khoa = cs[-1].group(1)
            muc = (method, m.group(1), khoa)
            if muc not in a.backend:
                a.backend.append(muc)
        a.bang_thang = sorted(set(RE_TU_BANG.findall(txt)))
        ra[a.duong] = a
    return ra


# ── Backend ─────────────────────────────────────────────────────────────────


@dataclass
class HamRouter:
    method: str
    duong: str
    tep: Path
    ten: str
    dong: int
    service: list[str] = field(default_factory=list)
    sql_tai_cho: bool = False  # thân hàm tự gọi conn.fetch/execute
    da_nghi: bool = False  # gọi bao_da_nghi → đường cũ, trả 410


@dataclass
class KyHieu:
    """Một service/hàm nghiệp vụ được router gọi."""

    hien: str  # "DayNoiService.doc" / "phi_kham_service.tinh" / "tinh_gia"
    nhom: str  # "DayNoiService" / "phi_kham_service" — gom ở bảng ngược
    module: str  # "clinicai.services.day_noi_service"
    tu: list[str]  # từ khoá tra test: [lớp/hàm, phương thức]


def tep_module(module: str) -> Path | None:
    p = GOC / "src" / Path(*module.split("."))
    if p.with_suffix(".py").is_file():
        return p.with_suffix(".py")
    if (p / "__init__.py").is_file():
        return p / "__init__.py"
    return None


def bang_import(cay: ast.AST) -> dict[str, tuple[str, str | None]]:
    """tên cục bộ → (module, tên gốc | None nếu là module). Nhận cả thân hàm
    (import cục bộ trong hàm router — hay gặp để tránh vòng import)."""
    ra: dict[str, tuple[str, str | None]] = {}
    than = cay.body if isinstance(cay, ast.Module) else [x for x in ast.walk(cay)]
    for n in than:
        if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            for a in n.names:
                con = f"{n.module}.{a.name}"
                if tep_module(con) is not None:
                    ra[a.asname or a.name] = (con, None)
                else:
                    ra[a.asname or a.name] = (n.module, a.name)
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    ra[a.asname] = (a.name, None)
    return {
        k: v
        for k, v in ra.items()
        if v[0].startswith("clinicai.") and not v[0].startswith(BO_GOI)
    }


def _ten_goi(n: ast.expr) -> str | None:
    return n.id if isinstance(n, ast.Name) else None


def service_trong_ham(
    ham: ast.AST,
    imp: dict[str, tuple[str, str | None]],
    ham_cuc_bo: dict[str, ast.AST],
    da_vao: set[str],
) -> list[KyHieu]:
    ra: list[KyHieu] = []
    bien: dict[str, str] = {}  # biến cục bộ → tên lớp đã import
    imp = {**imp, **bang_import(ham)}
    # Chỉ đi THÂN hàm: tham số mặc định là cổng quyền (Depends(cua_quyen(…))),
    # không phải nghiệp vụ.
    than = ast.Module(body=list(getattr(ham, "body", [])), type_ignores=[])

    def them(local: str, phuong: str | None) -> None:
        module, goc = imp[local]
        if goc is None:  # module alias: mod.ham()
            if phuong is None:
                return
            ten_mod = module.rsplit(".", 1)[-1]
            ra.append(KyHieu(f"{ten_mod}.{phuong}", ten_mod, module, [ten_mod, phuong]))
        else:
            hien = f"{goc}.{phuong}" if phuong else goc
            nhom = goc if goc[:1].isupper() else module.rsplit(".", 1)[-1]
            ra.append(KyHieu(hien, nhom, module, [goc] + ([phuong] if phuong else [])))

    if isinstance(ham, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for a in [*ham.args.args, *ham.args.kwonlyargs]:
            if isinstance(a.annotation, ast.Name) and a.annotation.id in imp:
                bien[a.arg] = a.annotation.id
    for n in ast.walk(than):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            f = _ten_goi(n.value.func)
            if f in imp:
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        bien[t.id] = f
    for n in ast.walk(than):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute):
            v = f.value
            if isinstance(v, ast.Call) and _ten_goi(v.func) in imp:
                them(v.func.id, f.attr)  # type: ignore[union-attr]
            elif isinstance(v, ast.Name) and v.id in imp:
                them(v.id, f.attr)
            elif isinstance(v, ast.Name) and v.id in bien:
                them(bien[v.id], f.attr)
        elif isinstance(f, ast.Name):
            if f.id in imp:
                if imp[f.id][1] is not None and not imp[f.id][1][:1].isupper():  # type: ignore[index]
                    them(f.id, None)
            elif f.id in ham_cuc_bo and f.id not in da_vao:
                da_vao.add(f.id)
                ra.extend(service_trong_ham(ham_cuc_bo[f.id], imp, ham_cuc_bo, da_vao))
    # lớp chỉ được khởi tạo (không gọi phương thức) vẫn là một dấu vết
    hien_co = {k.nhom for k in ra}
    for n in ast.walk(than):
        if isinstance(n, ast.Call) and _ten_goi(n.func) in imp:
            goc = imp[n.func.id][1]  # type: ignore[union-attr]
            if goc and goc[:1].isupper() and goc not in hien_co:
                them(n.func.id, None)
                hien_co.add(goc)
    return ra


def doc_router() -> tuple[list[HamRouter], dict[str, KyHieu]]:
    ham_ra: list[HamRouter] = []
    ky: dict[str, KyHieu] = {}
    tep_list = sorted(ROUTERS.glob("*.py")) + [PY / "api" / "v1" / "patients.py"]
    for tep in tep_list:
        try:
            cay = ast.parse(doc(tep))
        except SyntaxError:
            continue
        tien_to = ""
        for n in cay.body:
            if (
                isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Call)
                and _ten_goi(n.value.func) == "APIRouter"
            ):
                for kw in n.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        tien_to = str(kw.value.value)
        imp = bang_import(cay)
        cuc_bo = {
            n.name: n
            for n in cay.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for n in cay.body:
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in n.decorator_list:
                if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)):
                    continue
                if _ten_goi(d.func.value) != "router":
                    continue
                cac_method: list[str] = []
                if d.func.attr in HTTP:
                    cac_method = [d.func.attr.upper()]
                elif d.func.attr == "api_route":
                    for kw in d.keywords:
                        if kw.arg == "methods" and isinstance(
                            kw.value, (ast.List, ast.Tuple)
                        ):
                            cac_method = [
                                str(e.value).upper()
                                for e in kw.value.elts
                                if isinstance(e, ast.Constant)
                            ]
                if not cac_method:
                    continue
                duong = None
                if d.args and isinstance(d.args[0], ast.Constant):
                    duong = str(d.args[0].value)
                for kw in d.keywords:
                    if kw.arg == "path" and isinstance(kw.value, ast.Constant):
                        duong = str(kw.value.value)
                if duong is None:
                    continue
                sv = service_trong_ham(n, imp, cuc_bo, {n.name})
                ten_sv: list[str] = []
                for k in sv:
                    ky.setdefault(k.hien, k)
                    if k.hien not in ten_sv:
                        ten_sv.append(k.hien)
                sql = any(
                    isinstance(x, ast.Call)
                    and isinstance(x.func, ast.Attribute)
                    and x.func.attr
                    in ("fetch", "fetchrow", "fetchval", "execute", "executemany")
                    for x in ast.walk(n)
                )
                nghi = any(
                    isinstance(x, ast.Call) and _ten_goi(x.func) == "bao_da_nghi"
                    for x in ast.walk(n)
                )
                for m in cac_method:
                    ham_ra.append(
                        HamRouter(
                            m,
                            "/api/v1" + tien_to + duong,
                            tep,
                            n.name,
                            n.lineno,
                            ten_sv,
                            sql,
                            nghi,
                        )
                    )
    return ham_ra, ky


# ── Test ────────────────────────────────────────────────────────────────────


class KhoTest:
    def __init__(self) -> None:
        self.dem: dict[Path, Counter[str]] = {}
        for p in sorted(TESTS.rglob("test_*.py")):
            self.dem[p] = Counter(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", doc(p)))
        self._cache: dict[str, list[Path]] = {}

    def cho(self, k: KyHieu, toi_da: int = 2) -> list[Path]:
        if k.hien in self._cache:
            return self._cache[k.hien]
        ten_mod = k.module.rsplit(".", 1)[-1]
        neo = k.tu[0]
        phuong = k.tu[-1] if len(k.tu) > 1 else None
        xep: list[tuple[int, int, str, Path]] = []
        la_lop = neo[:1].isupper()
        for p, c in self.dem.items():
            # Lớp: tệp phải nhắc tên lớp. Hàm/module: phải nhắc tên MODULE (dòng
            # import) — tên hàm trần như `record_event` trùng chữ quá nhiều.
            if la_lop and not c[neo]:
                continue
            if not la_lop and not c[ten_mod]:
                continue
            d_phuong = c[phuong] if phuong else 0
            d_neo = c[neo] + c[ten_mod]
            xep.append((-d_phuong, -d_neo, p.as_posix(), p))
        xep.sort()
        if phuong and any(x[0] < 0 for x in xep):
            xep = [x for x in xep if x[0] < 0]
        ra = [x[3] for x in xep[:toi_da]]
        self._cache[k.hien] = ra
        return ra


# ── Quyền (lego) & tiêu đề màn ──────────────────────────────────────────────


def doc_lego() -> list[tuple[str, str, str, str]]:
    """[(đường, mã lego, tên, mặc định cho)] từ permissions/catalogue.py MAN."""
    tep = PY / "permissions" / "catalogue.py"
    ra: list[tuple[str, str, str, str]] = []
    try:
        cay = ast.parse(doc(tep))
    except SyntaxError:
        return ra
    for n in ast.walk(cay):
        if isinstance(n, ast.Call) and _ten_goi(n.func) == "_lego" and len(n.args) >= 5:
            a = n.args
            if not all(isinstance(x, ast.Constant) for x in (a[0], a[1], a[4])):
                continue
            if not isinstance(a[2], ast.List):
                continue
            for e in a[2].elts:
                if isinstance(e, ast.Constant):
                    ra.append(
                        (
                            str(e.value),
                            str(a[0].value),
                            str(a[1].value),
                            str(a[4].value),
                        )  # type: ignore[attr-defined]
                    )
    return ra


def lego_cho(route: str, lego: list[tuple[str, str, str, str]]) -> str:
    tot = None
    for duong, ma, ten, cho in lego:
        if route == duong or route.startswith(duong.rstrip("/") + "/"):
            if tot is None or len(duong) > len(tot[0]):
                tot = (duong, ma, ten, cho)
    if tot is None:
        return "?"
    return f"lego `{tot[1]}` ({tot[2]} · mặc định: {tot[3]})"


# ── Sự kiện & bảng ──────────────────────────────────────────────────────────


def hang_so_trong(module: str, ten: str) -> str | None:
    tep = tep_module(module)
    if tep is None:
        return None
    try:
        cay = ast.parse(doc(tep))
    except SyntaxError:
        return None
    for n in cay.body:
        if isinstance(n, (ast.Assign, ast.AnnAssign)):
            dich = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in dich:
                if (
                    isinstance(t, ast.Name)
                    and t.id == ten
                    and isinstance(n.value, ast.Constant)
                ):
                    return str(n.value.value)
    return None


def doc_su_kien() -> list[tuple[str, str, list[str], str]]:
    """[(tệp consumer, tên consumer, các event_type nghe, cách nghe)]."""
    catalogue = PY / "events" / "catalogue.py"
    cay = ast.parse(doc(catalogue))
    hang: dict[str, str] = {}
    for n in cay.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant):
            for t in n.targets:
                if isinstance(t, ast.Name) and isinstance(n.value.value, str):
                    hang[t.id] = n.value.value
    nghe: dict[str, list[str]] = defaultdict(list)  # tên hằng consumer → event
    for n in ast.walk(cay):
        if isinstance(n, ast.Call) and _ten_goi(n.func) == "SuKien":
            ten = None
            cons: list[str] = []
            for kw in n.keywords:
                if kw.arg == "ten" and isinstance(kw.value, ast.Constant):
                    ten = str(kw.value.value)
                if kw.arg == "consumers" and isinstance(
                    kw.value, (ast.List, ast.Tuple)
                ):
                    cons = [e.id for e in kw.value.elts if isinstance(e, ast.Name)]
            if ten:
                for c in cons:
                    nghe[c].append(ten)
    ra: list[tuple[str, str, list[str], str]] = []
    for tep in sorted((PY / "events" / "consumers").glob("*.py")):
        if tep.name == "__init__.py":
            continue
        try:
            ct = ast.parse(doc(tep))
        except SyntaxError:
            continue
        imp_all: dict[str, tuple[str, str]] = {}
        for n in ct.body:
            if isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    imp_all[a.asname or a.name] = (n.module, a.name)
        for n in ct.body:
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)):
                continue
            c = n.value
            f = _ten_goi(c.func)
            if f not in ("dang_ky", "dang_ky_loai") or not c.args:
                continue
            a0 = c.args[0]
            ham = (
                c.args[1].id
                if len(c.args) > 1 and isinstance(c.args[1], ast.Name)
                else "?"
            )
            if not isinstance(a0, ast.Name):
                continue
            goc = imp_all.get(a0.id, ("", a0.id))[1]
            if f == "dang_ky":
                if goc not in hang:  # hằng khai lại trong chính tệp consumer
                    gt = hang_so_trong(f"clinicai.events.consumers.{tep.stem}", goc)
                    goc = next((k for k, v in hang.items() if v == gt), goc)
                ten_c = hang.get(goc, "?")
                ev = sorted(set(nghe.get(goc, [])))
                ra.append((tuong_doi(tep), ten_c, ev, f"sự kiện → `{ham}`"))
            else:
                mod = imp_all.get(
                    a0.id, (f"clinicai.events.consumers.{tep.stem}", a0.id)
                )[0]
                gt = hang_so_trong(mod, goc) or hang_so_trong(
                    f"clinicai.events.consumers.{tep.stem}", goc
                )
                ra.append((tuong_doi(tep), gt or "?", [], f"hẹn giờ → `{ham}`"))
    return ra


RE_TAO_BANG = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?\"?([a-z_][a-z0-9_]*)\"?\s*\(",
    re.IGNORECASE,
)
RE_XOA_BANG = re.compile(
    r"drop\s+table\s+(?:if\s+exists\s+)?(?:public\.)?\"?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def doc_bang() -> list[tuple[str, str, int]]:
    tao: dict[str, str] = {}
    xoa: set[str] = set()
    txt_theo_tep: list[tuple[str, str]] = []
    for tep in sorted(MIGRATIONS.glob("*.sql")):
        txt = re.sub(r"--[^\n]*", "", doc(tep))
        txt_theo_tep.append((tep.name, txt))
        for m in RE_TAO_BANG.finditer(txt):
            b = m.group(1).lower()
            if b not in tao or b in xoa:
                tao[b] = tep.name
                xoa.discard(b)
        for m in RE_XOA_BANG.finditer(txt):
            b = m.group(1).lower()
            if b in tao and tao[b] != tep.name:
                xoa.add(b)
    ra: list[tuple[str, str, int]] = []
    for b in sorted(set(tao) - xoa):
        re_sua = re.compile(
            rf"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?(?:public\.)?\"?{b}\b",
            re.I,
        )
        sua = sum(1 for ten, t in txt_theo_tep if ten != tao[b] and re_sua.search(t))
        ra.append((b, tao[b], sua))
    return ra


# ── Dựng tài liệu ───────────────────────────────────────────────────────────


def gon(ds: list[str], toi_da: int) -> str:
    if not ds:
        return "?"
    phan = ", ".join(ds[:toi_da])
    return phan + (f" (+{len(ds) - toi_da})" if len(ds) > toi_da else "")


def gom_service(sv: list[str], ky: dict[str, KyHieu], toi_da: int = 6) -> str:
    """'A.x, A.y, B.z' → 'A.{x, y} · B.z' — theo thứ tự xuất hiện."""
    nhom: dict[str, list[str]] = {}
    for x in sv:
        k = ky[x]
        phuong = x[len(k.nhom) + 1 :] if x.startswith(k.nhom + ".") else ""
        ds = nhom.setdefault(k.nhom, [])
        if phuong and phuong not in ds:
            ds.append(phuong)
    phan = []
    for ten, ds in list(nhom.items())[:toi_da]:
        if not ds:
            phan.append(ten)
        elif len(ds) == 1:
            phan.append(f"{ten}.{ds[0]}")
        else:
            them = f", +{len(ds) - 4}" if len(ds) > 4 else ""
            phan.append(f"{ten}.{{{', '.join(ds[:4])}{them}}}")
    du = len(nhom) - toi_da
    return " · ".join(phan) + (f" (+{du} service)" if du > 0 else "")


def sinh() -> str:
    api_next = doc_api_next()
    ham_router, ky = doc_router()
    test = KhoTest()
    lego = doc_lego()
    nhan_nav = {
        h: nhan for h, nhan in RE_NAV.findall(doc(APP / "(dashboard)" / "nav-items.ts"))
    }

    mau_next = {k: chuan_duong(k) for k in api_next}
    mau_be: dict[str, list[str]] = {}
    ham_theo_khoa: dict[str, HamRouter] = {}
    for h in ham_router:
        khoa = f"{h.method} {h.duong}"
        ham_theo_khoa[khoa] = h
        mau_be[khoa] = chuan_duong(h.duong)

    def tim_backend(method: str | None, duong: str) -> list[HamRouter]:
        goi = chuan_duong(duong)
        ung = mau_be
        if method and not method.startswith("~"):
            ung = {k: v for k, v in mau_be.items() if k.startswith(method + " ")}
        ra = [ham_theo_khoa[k] for k in chon_tot_nhat(goi, ung)]
        if method and method.startswith("~") and len(ra) > 1:
            cung = [h for h in ra if h.method == method[1:]]
            ra = cung or ra
        return ra

    # Next route → backend funcs
    # Next route → [(hàm backend, khoá thao tác?)]
    next_be: dict[str, list[tuple[HamRouter, str | None]]] = {}
    for k, a in api_next.items():
        ds: list[tuple[HamRouter, str | None]] = []
        for method, duong, khoa in a.backend:
            for h in tim_backend(method, duong):
                if (h, khoa) not in ds:
                    ds.append((h, khoa))
        next_be[k] = ds

    pages = sorted(APP.rglob("page.tsx"), key=lambda p: route_cua_page(p))
    pages = [p for p in pages if "node_modules" not in p.parts]
    cay_page = {p: duyet(p, TANG_API) for p in pages}
    dem_dung = Counter(f for t in cay_page.values() for f in t if f.name != "page.tsx")
    dung_chung = sorted(
        f for f, c in dem_dung.items() if c > NGUONG_DUNG_CHUNG * len(pages)
    )

    tren_man: dict[str, set[str]] = defaultdict(set)  # nhóm service → màn
    next_tu_man: dict[str, set[str]] = defaultdict(set)
    khoi_man: list[str] = []
    du_lieu: list[
        tuple[Path, str, str, list[str], list[str], list[str], list[str], set[str]]
    ] = []
    for p in pages:
        route = route_cua_page(p)
        txt = doc(p)
        mt = RE_TITLE.search(txt)
        tieu_de = mt.group(1) if mt else nhan_nav.get(route, "")
        tep_cay = {f: t for f, t in cay_page[p].items() if f not in dung_chung}
        thanh_phan = sorted(
            (
                f
                for f, t in tep_cay.items()
                if 1 <= t <= TANG_HIEN and (APP in f.parents)
            ),
            key=lambda f: (tep_cay[f], f.as_posix()),
        )
        hien_tp = [
            f.name if f.parent == p.parent else f.relative_to(DASH).as_posix()
            for f in thanh_phan
        ]
        goi_next: list[str] = []
        goi_be_thang: list[str] = []
        khong_ro: list[str] = []
        # Mọi chuỗi chữ trong cây tệp của màn — để lọc route.ts "béo" (một route
        # nhiều thao tác) xuống đúng các thao tác màn này thật sự gửi.
        chu: set[str] = set()
        for f in tep_cay:
            chu.update(RE_CHUOI.findall(doc(f)))
        for f in sorted(tep_cay, key=lambda x: x.as_posix()):
            for m in RE_API.finditer(doc(f)):
                s = m.group(1)
                chu.update(chuan_duong(s))
                if s.startswith("/api/v1/"):
                    if s not in goi_be_thang:
                        goi_be_thang.append(s)
                    continue
                trung = chon_tot_nhat(chuan_duong(s), mau_next)
                if not trung:
                    if s not in khong_ro:
                        khong_ro.append(s)
                for t in trung:
                    if t not in goi_next:
                        goi_next.append(t)
        for t in goi_next:
            next_tu_man[t].add(route)
        du_lieu.append(
            (p, route, tieu_de, hien_tp, goi_next, goi_be_thang, khong_ro, chu)
        )

    for p, route, tieu_de, hien_tp, goi_next, goi_be_thang, khong_ro, chu in du_lieu:
        # route Next ít màn dùng = riêng của màn này → service của nó xếp trước
        goi_next = sorted(
            goi_next, key=lambda t: (len(next_tu_man[t]), goi_next.index(t))
        )
        sv: list[str] = []
        for t in goi_next:
            for h, khoa in next_be.get(t, []):
                if khoa is not None and khoa not in chu:
                    continue
                sv.extend(x for x in h.service if x not in sv)
        for s in goi_be_thang:
            for h in tim_backend(None, s):
                sv.extend(x for x in h.service if x not in sv)
        for x in sv:
            tren_man[ky[x].nhom].add(route)
        tests: Counter[str] = Counter()
        for x in sv:
            for tp in test.cho(ky[x]):
                tests[tp.name] += 1
        dong = [f"### `{route}`" + (f" — {tieu_de}" if tieu_de else "")]
        dong.append(f"- page: `{tuong_doi(p)}` · quyền: {lego_cho(route, lego)}")
        if hien_tp:
            dong.append(f"- thành phần: {gon(hien_tp, 8)}")
        if goi_next:
            dong.append(f"- gọi API Next: {gon([f'`{x}`' for x in goi_next], 10)}")
        if goi_be_thang:
            dong.append(
                f"- gọi thẳng backend (server): {gon([f'`{x}`' for x in goi_be_thang], 6)}"
            )
        if khong_ro:
            dong.append(
                f"- ? không khớp route.ts nào: {gon([f'`{x}`' for x in khong_ro], 5)}"
            )
        if not goi_next and not goi_be_thang:
            dong.append(
                "- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)"
            )
        if sv:
            dong.append(f"- service: {gom_service(sv, ky)}")
        if tests:
            xep = sorted(tests.items(), key=lambda kv: (-kv[1], kv[0]))
            dong.append(f"- test: {gon([k for k, _ in xep], 5)}")
        khoi_man.append("\n".join(dong))

    # ── Mục 2: Next API ──
    khoi_api: list[str] = []
    for k in sorted(api_next):
        a = api_next[k]
        dong = [f"#### `{k}` · `{tuong_doi(a.tep)}`"]
        be = next_be[k]
        if not a.backend:
            dong.append(
                "- backend: (không proxy /api/v1 — xử lý tại chỗ hoặc lối khác ?)"
            )
        for method, duong, khoa in a.backend:
            trung = tim_backend(method, duong)
            nhan = f"[{khoa}] " if khoa else ""
            if not trung:
                dong.append(f"- {nhan}`{duong}` → ?")
                continue
            for h in trung:
                if h.da_nghi:
                    svs = (
                        "ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây"
                    )
                elif h.service:
                    svs = gon(h.service, 4) + (
                        " + SQL ngay trong router" if h.sql_tai_cho else ""
                    )
                elif h.sql_tai_cho:
                    svs = "(SQL ngay trong router, không qua service)"
                else:
                    svs = "?"
                moi = f"- {nhan}{h.method} `{h.duong}` → `{tuong_doi(h.tep)}:{h.ten}` → {svs}"
                if moi not in dong:  # cùng đường viết hai lần trong route.ts
                    dong.append(moi)
        if a.bang_thang:
            dong.append(f"- ⚠ đọc DB thẳng: {', '.join(a.bang_thang)}")
        tp: Counter[str] = Counter()
        for h, _ in be:
            for x in h.service:
                for t in test.cho(ky[x]):
                    tp[tuong_doi(t)] += 1
        if tp:
            xep = sorted(tp.items(), key=lambda kv: (-kv[1], kv[0]))
            dong.append(f"- test: {gon([k2 for k2, _ in xep], 3)}")
        man = sorted(next_tu_man.get(k, set()))
        dong.append(
            f"- màn dùng: {gon(man, 6) if man else '(không màn nào gọi thấy được ?)'}"
        )
        khoi_api.append("\n".join(dong))

    # ── Mục 3: service → màn ──
    nhom_tep: dict[str, str] = {}
    for k in ky.values():
        tep = tep_module(k.module)
        nhom_tep.setdefault(k.nhom, tuong_doi(tep) if tep else "?")
    khoi_sv = ["| Service | Tệp | Màn dùng |", "|---|---|---|"]
    for nhom in sorted(nhom_tep, key=str.lower):
        man = sorted(tren_man.get(nhom, set()))
        khoi_sv.append(
            f"| `{nhom}` | `{nhom_tep[nhom]}` | {gon(man, 8) if man else '— (chỉ API/worker)'} |"
        )

    # ── Mục 4: sự kiện ──
    khoi_sk = ["| Consumer | Tên | Nghe | Cách |", "|---|---|---|---|"]
    for tep, ten, ev, cach in doc_su_kien():
        nghe = gon([f"`{e}`" for e in ev], 15) if ev else "—"
        khoi_sk.append(f"| `{tep}` | `{ten}` | {nghe} | {cach} |")

    # ── Mục 5: bảng ──
    khoi_bang = ["| Bảng | Tạo ở migration | Số migration sửa sau |", "|---|---|---|"]
    for b, tep, sua in doc_bang():
        khoi_bang.append(f"| `{b}` | `{tep}` | {sua} |")

    dau = [
        "# BẢN ĐỒ CODE — màn → API → router → service → test",
        "",
        DONG_SINH + datetime.now().strftime("%Y-%m-%d %H:%M") + ". **Đừng sửa tay** —",
        "> chạy `python3 scripts/ban-do-code.py` để sinh lại; CI (`--kiem`, job backend",
        "> của `scripts/ci-may.sh`) đỏ khi tệp này lệch code.",
        "",
        "Tra theo việc trước ở `docs/BAN-DO-SUA.md`; tệp này là chuỗi file chi tiết.",
        "Tìm nhanh: tìm chuỗi route (vd `/thu-ngan/dich-vu`), tên route.ts hay tên",
        "service. **`?`** = phân tích tĩnh không suy được — mở file mà xem, đừng tin là",
        "không có. Thành phần đi tối đa "
        f"{TANG_API} tầng import (liệt kê {TANG_HIEN} tầng); bỏ `components/ui` và",
        f"tệp mà hơn {int(NGUONG_DUNG_CHUNG * 100)}% số màn cùng import (dùng chung): "
        + (", ".join(f"`{f.relative_to(DASH).as_posix()}`" for f in dung_chung) or "—")
        + ".",
        "",
        "Mục lục: 1. Màn · 2. API Next → backend · 3. Service → màn · "
        "4. Sự kiện (consumer) · 5. Bảng → migration",
        "",
        f"## 1. Màn ({len(pages)})",
        "",
    ]
    duoi = [
        "",
        f"## 2. API Next → backend ({len(api_next)})",
        "",
        "Mỗi `app/api/**/route.ts`: đường `/api/v1` nó proxy → hàm router FastAPI → service.",
        "",
        "\n\n".join(khoi_api),
        "",
        f"## 3. Service → màn ({len(nhom_tep)})",
        "",
        "\n".join(khoi_sv),
        "",
        "## 4. Sự kiện (consumer)",
        "",
        "Danh mục sự kiện: `src/clinicai/events/catalogue.py` (mỗi sự kiện khai một chỗ, "
        "kèm `consumers`). Worker: `src/clinicai/events/worker.py`.",
        "",
        "\n".join(khoi_sk),
        "",
        "## 5. Bảng → migration",
        "",
        "Bảng còn sống (tạo bằng `CREATE TABLE`, chưa `DROP`). Đổi lược đồ = migration MỚI.",
        "",
        "\n".join(khoi_bang),
        "",
    ]
    return "\n".join(dau) + "\n\n".join(khoi_man) + "\n" + "\n".join(duoi)


def bo_dong_sinh(s: str) -> str:
    return "\n".join(d for d in s.splitlines() if not d.startswith(DONG_SINH))


def main(argv: list[str]) -> int:
    noi_dung = sinh()
    if "--in" in argv:
        sys.stdout.write(noi_dung)
        return 0
    if "--kiem" in argv:
        cu = doc(DAU_RA)
        if bo_dong_sinh(cu) != bo_dong_sinh(noi_dung):
            import difflib

            khac = list(
                difflib.unified_diff(
                    bo_dong_sinh(cu).splitlines(),
                    bo_dong_sinh(noi_dung).splitlines(),
                    "docs/BAN-DO-CODE.md (đang có)",
                    "sinh từ code hiện tại",
                    lineterm="",
                    n=0,
                )
            )
            print("\n".join(khac[:40]))
            print(
                f"\nLỖI: docs/BAN-DO-CODE.md lệch code ({len(khac)} dòng khác). "
                "Chạy: python3 scripts/ban-do-code.py  rồi commit."
            )
            return 1
        print("docs/BAN-DO-CODE.md khớp code ✓")
        return 0
    DAU_RA.write_text(noi_dung, encoding="utf-8")
    print(f"Đã ghi {tuong_doi(DAU_RA)} ({noi_dung.count(chr(10))} dòng)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
