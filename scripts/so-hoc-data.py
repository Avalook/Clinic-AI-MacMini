#!/usr/bin/env python3
"""Sinh docs/so-hoc/data.js — dữ liệu cho "Sổ học hệ thống ClinicAI".

Tuyền 23/10/2026: canvas LEGO (hàng nghìn khối theo cấu trúc code) khó nhìn.
Sổ học xếp theo NGHIỆP VỤ: hành trình khách → khối → màn → thao tác → từ điển.

Hai nguồn, tách bạch:
  * SINH TỪ CODE (tệp này): màn gọi API nào, router/hàm dịch vụ nào, hàm ghi/đọc
    bảng nào, vòng lặp nào nghi N+1, màn nghe bảng nào, màn có tự tải không.
    Tái dùng phân tích của `scripts/ban-do-code.py` (import, không chép).
  * VIẾT TAY (`docs/so-hoc/viet-tay.json`): tên dễ hiểu, chia khối, "5 điều phải
    nhớ", thao tác chính, thẻ tự kiểm, từ điển, số đã đo. Sửa tệp đó rồi chạy lại.

Phân tích TĨNH, chỉ thư viện chuẩn. Chỗ không suy được để trống chứ không đoán.

    python3 scripts/so-hoc-data.py          # ghi docs/so-hoc/data.js
    python3 scripts/so-hoc-data.py --kiem   # không ghi; exit 1 nếu có cảnh báo (màn chưa
                                            # xếp khối, API thao tác mất, tệp:dòng hỏng)
"""

# ruff: noqa: E501 — chuỗi tài liệu tiếng Việt và regex, cắt dòng chỉ làm khó đọc.
from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "ban_do_code", GOC / "scripts" / "ban-do-code.py"
)
assert _spec and _spec.loader
bd = importlib.util.module_from_spec(_spec)
sys.modules["ban_do_code"] = bd  # dataclass cần module có trong sys.modules
_spec.loader.exec_module(bd)

VIET_TAY = GOC / "docs" / "so-hoc" / "viet-tay.json"
DAU_RA = GOC / "docs" / "so-hoc" / "data.js"
DASH, APP, PY = bd.DASH, bd.APP, bd.PY

SQL_METHOD = {"fetch", "fetchrow", "fetchval", "execute", "executemany"}
RE_GHI = [
    re.compile(r"\binsert\s+into\s+(?:public\.)?\"?([a-z_][a-z0-9_]*)", re.I),
    re.compile(
        r"\bupdate\s+(?:only\s+)?(?:public\.)?\"?([a-z_][a-z0-9_]*)\"?\s+(?:as\s+\w+\s+|\w+\s+)?set\b",
        re.I,
    ),
    re.compile(
        r"\bdelete\s+from\s+(?:only\s+)?(?:public\.)?\"?([a-z_][a-z0-9_]*)", re.I
    ),
]
RE_DOC = re.compile(
    r"\b(?:from|join)\s+(?:only\s+)?(?:public\.)?\"?([a-z_][a-z0-9_]*)", re.I
)
RE_NGHE = re.compile(r"useNgheBang\(\s*(\[[^\]]*\]|[A-Za-z_][\w]*)", re.S)
RE_TAI_LAI = re.compile(
    r"await\s+(tai|nap|napLai|reload|taiLai|load|pull|lamMoi|taiLaiKho|napKetQua)\w*\(\s*\)"
)
THU_DEN = {"xam": 0, "xanh": 1, "vang": 2, "do": 3}
RE_TEP_DONG = re.compile(
    r"((?:src|docs|supabase|scripts)/[\w()\[\]./-]+?\.(?:py|tsx?|sql|md|json|mts)):(\d+)"
)
RE_CHUOI_TRONG = re.compile(r"""["']([a-z_][a-z0-9_]*)["']""")


def rel(p: Path) -> str:
    return p.relative_to(GOC).as_posix()


# ── Backend: hàm dịch vụ → bảng ghi/đọc, nghi N+1 ──────────────────────────


class KhoAst:
    """Cache cây AST theo tệp + tra định nghĩa hàm/phương thức."""

    def __init__(self) -> None:
        self.cay: dict[Path, ast.Module | None] = {}

    def lay(self, tep: Path) -> ast.Module | None:
        if tep not in self.cay:
            try:
                self.cay[tep] = ast.parse(bd.doc(tep))
            except SyntaxError:
                self.cay[tep] = None
        return self.cay[tep]

    def tim(self, tep: Path, ten: str) -> tuple[ast.AST, str | None] | None:
        """'Lop.ham' | 'ham' → (nút def, tên lớp chứa)."""
        cay = self.lay(tep)
        if cay is None:
            return None
        lop, _, ham = ten.rpartition(".")
        for n in cay.body:
            if lop and isinstance(n, ast.ClassDef) and n.name == lop:
                for m in n.body:
                    if (
                        isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and m.name == ham
                    ):
                        return m, lop
            if (
                not lop
                and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == ham
            ):
                return n, None
        return None

    def hang_chuoi(self, tep: Path) -> dict[str, str]:
        """Hằng chuỗi cấp module (SQL hay khai ở đây: `_SQL_X = \"\"\"...\"\"\"`)."""
        cay = self.lay(tep)
        ra: dict[str, str] = {}
        if cay is None:
            return ra
        for n in cay.body:
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                dich = n.targets if isinstance(n, ast.Assign) else [n.target]
                v = n.value
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    for t in dich:
                        if isinstance(t, ast.Name):
                            ra[t.id] = v.value
        return ra


AST = KhoAst()


def chuoi_trong(n: ast.AST, hang: dict[str, str]) -> list[str]:
    ra: list[str] = []
    for x in ast.walk(n):
        if isinstance(x, ast.Constant) and isinstance(x.value, str):
            ra.append(x.value)
        elif isinstance(x, ast.Name) and x.id in hang:
            ra.append(hang[x.id])
    return ra


def la_sql(n: ast.AST) -> bool:
    return (
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in SQL_METHOD
    )


class PhanTichHam:
    """Đi từ một hàm dịch vụ, theo lời gọi (self.x / hàm cùng tệp / hàm import
    từ clinicai.*) tối đa `TANG` tầng; gom bảng ghi/đọc và vòng lặp nghi N+1."""

    TANG = 3

    def __init__(self, bang_that: set[str]) -> None:
        self.bang_that = bang_that
        self.cache: dict[tuple[str, str], dict] = {}
        self._co_sql: dict[tuple[str, str], bool] = {}

    def _imp(self, tep: Path) -> dict[str, tuple[str, str | None]]:
        cay = AST.lay(tep)
        return bd.bang_import(cay) if cay is not None else {}

    def _giai(
        self, tep: Path, lop: str | None, goi: ast.Call, noi: ast.AST | None = None
    ) -> tuple[Path, str] | None:
        """Lời gọi → (tệp, 'Lop.ham' | 'ham'). `noi` = hàm chứa lời gọi, để đọc
        cả import CỤC BỘ trong thân hàm (hay gặp: tránh vòng import)."""
        f = goi.func
        imp = self._imp(tep)
        if noi is not None:
            imp = {**imp, **bd.bang_import(noi)}
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            v = f.value.id
            if v in ("self", "cls") and lop:
                return tep, f"{lop}.{f.attr}"
            if v in imp:
                mod, goc = imp[v]
                t = bd.tep_module(mod)
                if t is None:
                    return None
                return (t, f.attr) if goc is None else (t, f"{goc}.{f.attr}")
        if isinstance(f, ast.Name):
            if AST.tim(tep, f.id):
                return tep, f.id
            if f.id in imp and imp[f.id][1]:
                mod, goc = imp[f.id]
                t = bd.tep_module(mod)
                if t is not None and goc and not goc[:1].isupper():
                    return t, goc
        return None

    def co_sql(self, tep: Path, ten: str, tang: int = 0) -> bool:
        """Hàm này (hoặc hàm nó gọi, 2 tầng) có chạm DB không."""
        khoa = (rel(tep), ten)
        if khoa in self._co_sql:
            return self._co_sql[khoa]
        self._co_sql[khoa] = False  # chặn vòng đệ quy
        kq = AST.tim(tep, ten)
        if kq is None:
            return False
        n, lop = kq
        ra = any(la_sql(x) for x in ast.walk(n))
        if not ra and tang < 2:
            for x in ast.walk(n):
                if isinstance(x, ast.Await) and isinstance(x.value, ast.Call):
                    d = self._giai(tep, lop, x.value, n)
                    if d and self.co_sql(d[0], d[1], tang + 1):
                        ra = True
                        break
        self._co_sql[khoa] = ra
        return ra

    def chay(self, tep: Path, ten: str) -> dict:
        khoa = (rel(tep), ten)
        if khoa in self.cache:
            return self.cache[khoa]
        ghi: dict[str, str] = {}
        doc: dict[str, str] = {}
        n1: list[dict] = []
        da: set[tuple[str, str]] = set()
        dong_def = 0

        def di(t: Path, ham: str, tang: int) -> None:
            nonlocal dong_def
            if (rel(t), ham) in da or len(da) > 60:
                return
            da.add((rel(t), ham))
            kq = AST.tim(t, ham)
            if kq is None:
                return
            n, lop = kq
            if tang == 0:
                dong_def = getattr(n, "lineno", 0)
            hang = AST.hang_chuoi(t)
            for s in chuoi_trong(n, hang):
                if not re.search(r"\b(select|insert|update|delete|with)\b", s, re.I):
                    continue
                for r in RE_GHI:
                    for b in r.findall(s):
                        b = b.lower()
                        if b in self.bang_that:
                            ghi.setdefault(b, f"{rel(t)}:{getattr(n, 'lineno', 0)}")
                for b in RE_DOC.findall(s):
                    b = b.lower()
                    if b in self.bang_that:
                        doc.setdefault(b, f"{rel(t)}:{getattr(n, 'lineno', 0)}")
            # Vòng lặp có await truy vấn bên trong = nghi N+1.
            for v in ast.walk(n) if "/permissions/" not in rel(t) else []:
                than: list[ast.AST] = []
                if isinstance(v, (ast.For, ast.AsyncFor, ast.While)):
                    than = list(v.body)
                elif isinstance(
                    v, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
                ):
                    than = [v]
                for b in than:
                    for a in ast.walk(b):
                        if not (
                            isinstance(a, ast.Await) and isinstance(a.value, ast.Call)
                        ):
                            continue
                        goi = a.value
                        nhan = None
                        if la_sql(goi):
                            nhan = f"conn.{goi.func.attr}"  # type: ignore[union-attr]
                        else:
                            d = self._giai(t, lop, goi, n)
                            # Kiểm quyền (`can`…) có cache theo lượt gọi — không tính.
                            if (
                                d
                                and "/permissions/" not in d[0].as_posix()
                                and self.co_sql(d[0], d[1])
                            ):
                                nhan = d[1]
                        if nhan:
                            muc = {
                                "dong": f"{rel(t)}:{a.lineno}",
                                "goi": nhan,
                                "trong": ham,
                            }
                            if muc not in n1:
                                n1.append(muc)
                            break
            if tang >= self.TANG:
                return
            for x in ast.walk(n):
                if isinstance(x, ast.Call):
                    d = self._giai(t, lop, x, n)
                    if d:
                        di(d[0], d[1], tang + 1)

        di(tep, ten, 0)
        ra = {
            "tep": rel(tep),
            "dong": dong_def,
            "ghi": sorted(ghi),
            "doc": sorted(set(doc) - set(ghi)),
            "n1": n1[:6],
        }
        self.cache[khoa] = ra
        return ra


# ── Frontend: màn nghe bảng nào, tự tải không, tải lại sau ghi ─────────────


def bang_live() -> list[str]:
    txt = bd.doc(APP / "(dashboard)" / "RealtimeRefresher.tsx")
    m = re.search(r"const LIVE_TABLES = \[(.*?)\] as const", txt, re.S)
    return (
        re.findall(r'"([a-z_0-9]+)"', re.sub(r"//[^\n]*", "", m.group(1))) if m else []
    )


def man_tu_tai() -> list[re.Pattern[str]]:
    txt = bd.doc(DASH / "lib" / "man-tu-tai.ts")
    m = re.search(r"MAN_TU_TAI[^=]*=\s*\[(.*?)\];", txt, re.S)
    ra = []
    for js in re.findall(r"^\s*/(.+)/,\s*$", m.group(1) if m else "", re.M):
        ra.append(re.compile(js.replace(r"\/", "/")))
    return ra


def nghe_trong(tep: Path) -> list[tuple[list[str], int]]:
    txt = bd.doc(tep)
    ra = []
    for m in RE_NGHE.finditer(txt):
        g = m.group(1)
        dong = txt.count("\n", 0, m.start()) + 1
        if g.startswith("["):
            ra.append((RE_CHUOI_TRONG.findall(g), dong))
            continue
        # Hằng trong cùng tệp (hoặc tệp nó import) — `const BANG_X = [...]`.
        tim = [txt] + [bd.doc(f) for f in bd.cac_import(tep)]
        bang: list[str] = []
        for t in tim:
            mm = re.search(
                rf"(?:const|let)\s+{re.escape(g)}\b[^=]*=\s*\[(.*?)\]", t, re.S
            )
            if mm:
                bang = RE_CHUOI_TRONG.findall(mm.group(1))
                break
        ra.append((bang, dong))
    return ra


def la_chuyen_huong(txt: str) -> bool:
    than = re.sub(
        r"^\s*(import|export\s+const\s+metadata)[^\n]*\n", "", txt, flags=re.M
    )
    return bool(
        re.search(r"\b(redirect|permanentRedirect)\(", than)
    ) and "<" not in re.sub(r"<[A-Z]\w*>", "", re.sub(r"//[^\n]*", "", than)).replace(
        "=>", ""
    )


def git(*a: str) -> str:
    try:
        return subprocess.check_output(["git", *a], cwd=GOC, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"


# ── Dựng dữ liệu ───────────────────────────────────────────────────────────


def sinh() -> tuple[dict, list[str]]:
    canh: list[str] = []
    vt = json.loads(bd.doc(VIET_TAY) or "{}")

    api_next = bd.doc_api_next()
    ham_router, ky = bd.doc_router()
    bang_ds = bd.doc_bang()
    bang_that = {b for b, _, _ in bang_ds}
    pt = PhanTichHam(bang_that)
    live = bang_live()
    tu_tai = man_tu_tai()

    mau_next = {k: bd.chuan_duong(k) for k in api_next}
    mau_be: dict[str, list[str]] = {}
    theo_khoa: dict[str, object] = {}
    for h in ham_router:
        k = f"{h.method} {h.duong}"
        theo_khoa[k] = h
        mau_be[k] = bd.chuan_duong(h.duong)

    def tim_backend(method: str | None, duong: str) -> list:
        goi = bd.chuan_duong(duong)
        ung = mau_be
        if method and not method.startswith("~"):
            ung = {k: v for k, v in mau_be.items() if k.startswith(method + " ")}
        ra = [theo_khoa[k] for k in bd.chon_tot_nhat(goi, ung)]
        if method and method.startswith("~") and len(ra) > 1:
            ra = [h for h in ra if h.method == method[1:]] or ra
        return ra

    next_be: dict[str, list] = {}
    for k, a in api_next.items():
        ds: list = []
        for method, duong, khoa in a.backend:
            for h in tim_backend(method, duong):
                if (h, khoa) not in ds:
                    ds.append((h, khoa))
        next_be[k] = ds

    # Hàm dịch vụ: "Lop.ham" → phân tích (ghi/đọc/N+1).
    ham_dv: dict[str, dict] = {}

    def phan_tich_sv(ten: str) -> dict | None:
        if ten in ham_dv:
            return ham_dv[ten]
        k = ky.get(ten)
        if k is None:
            return None
        tep = bd.tep_module(k.module)
        if tep is None or "." not in ten and ten[:1].isupper():
            return None
        ten_ham = (
            ten.split(".", 1)[1]
            if ten.startswith(k.module.rsplit(".", 1)[-1] + ".")
            else ten
        )
        if AST.tim(tep, ten_ham) is None:
            return None
        ham_dv[ten] = pt.chay(tep, ten_ham)
        return ham_dv[ten]

    router_ra: dict[str, dict] = {}

    def ghi_router(h) -> str:
        k = f"{h.method} {h.duong}"
        if k not in router_ra:
            sv = [s for s in h.service if phan_tich_sv(s)]
            router_ra[k] = {
                "ham": h.ten,
                "tep": f"{rel(h.tep)}:{h.dong}",
                "dv": sv,
                "sql_tai_cho": h.sql_tai_cho,
                "nghi": h.da_nghi,
            }
        return k

    pages = sorted(
        (p for p in APP.rglob("page.tsx") if "node_modules" not in p.parts),
        key=bd.route_cua_page,
    )
    cay = {p: bd.duyet(p, bd.TANG_API) for p in pages}
    dem = Counter(f for t in cay.values() for f in t if f.name != "page.tsx")
    dung_chung = {f for f, c in dem.items() if c > bd.NGUONG_DUNG_CHUNG * len(pages)}
    nhan_nav = dict(bd.RE_NAV.findall(bd.doc(APP / "(dashboard)" / "nav-items.ts")))
    lego = bd.doc_lego()

    man_ra: list[dict] = []
    nghe_bang: dict[str, set[str]] = defaultdict(set)  # bảng → route nghe tự tải
    for p in pages:
        route = bd.route_cua_page(p)
        txt = bd.doc(p)
        mt = bd.RE_TITLE.search(txt)
        tep_cay = {f: t for f, t in cay[p].items() if f not in dung_chung}
        api: list[str] = []
        be_thang: list[str] = []
        chu: set[str] = set()
        for f in tep_cay:
            chu.update(bd.RE_CHUOI.findall(bd.doc(f)))
        for f in sorted(tep_cay, key=lambda x: x.as_posix()):
            for m in bd.RE_API.finditer(bd.doc(f)):
                s = m.group(1)
                chu.update(bd.chuan_duong(s))
                if s.startswith("/api/v1/"):
                    if s not in be_thang:
                        be_thang.append(s)
                    continue
                for t in bd.chon_tot_nhat(bd.chuan_duong(s), mau_next):
                    if t not in api:
                        api.append(t)
        be_keys: list[str] = []
        for t in api:
            for h, khoa in next_be.get(t, []):
                if khoa is not None and khoa not in chu:
                    continue
                k = ghi_router(h)
                if k not in be_keys:
                    be_keys.append(k)
        for s in be_thang:
            for h in tim_backend(None, s):
                k = ghi_router(h)
                if k not in be_keys:
                    be_keys.append(k)
        nghe: list[dict] = []
        tai_lai: list[str] = []
        co_lbs = False
        for f in sorted(tep_cay, key=lambda x: x.as_posix()):
            for bang, dong in nghe_trong(f):
                nghe.append({"bang": bang, "o": f"{rel(f)}:{dong}"})
            t = bd.doc(f)
            for m in RE_TAI_LAI.finditer(t):
                tai_lai.append(f"{rel(f)}:{t.count(chr(10), 0, m.start()) + 1}")
            if "LiveBoardSync" in t and f == p:
                co_lbs = True
        mau_route = re.sub(r"\[[^\]]+\]", "x", route)
        tu = any(r.search(mau_route) for r in tu_tai)
        for n in nghe:
            for b in n["bang"]:
                nghe_bang[b].add(route)
        man_ra.append(
            {
                "route": route,
                "page": rel(p),
                "tieu_de": (mt.group(1) if mt else nhan_nav.get(route, "")),
                "chuyen_huong": la_chuyen_huong(txt),
                "quyen": bd.lego_cho(route, lego),
                "api_next": api,
                "be": be_keys,
                "nghe": nghe,
                "tu_tai": tu,
                "live_board_sync": co_lbs,
                # Lời gọi backend lúc DỰNG TRANG trên máy chủ (page.tsx) — mỗi lần
                # RealtimeRefresher dựng lại trang là chạy lại chừng ấy lời gọi.
                "ssr_goi": len(
                    re.findall(
                        r"\b(?:fetchFromBackend|backendFetch|fetchBackend)\w*\s*(?:<[^>]*>)?\(",
                        txt,
                    )
                ),
                "tai_lai_sau_ghi": tai_lai[:8],
                "so_tai_lai": len(tai_lai),
            }
        )

    # Bảng → màn tự cập nhật: màn tự tải nghe qua useNgheBang; màn thường dựng
    # lại cả trang khi bảng nằm trong LIVE_TABLES (RealtimeRefresher).
    bang_ra = []
    dem_ghi: Counter[str] = Counter()
    for r in router_ra.values():
        for s in r["dv"]:
            for b in ham_dv[s]["ghi"]:
                dem_ghi[b] += 1
    for b, tep, sua in bang_ds:
        bang_ra.append(
            {
                "ten": b,
                "tao_o": tep,
                "so_sua": sua,
                "live": b in live,
                "man_nghe": sorted(nghe_bang.get(b, set())),
                "so_api_ghi": dem_ghi.get(b, 0),
            }
        )

    # ── Gắn dữ liệu viết tay ──
    khoi = vt.get("khoi", [])
    route_khoi: dict[str, str] = {}
    for k in khoi:
        for r in k.get("routes", []):
            route_khoi[r] = k["id"]
    for m in man_ra:
        m["khoi"] = route_khoi.get(m["route"], "")
        if not m["khoi"] and not m["chuyen_huong"]:
            canh.append(f"màn chưa xếp khối: {m['route']}")
    for r in route_khoi:
        if r not in {m["route"] for m in man_ra}:
            canh.append(f"viet-tay.json xếp route không có trong code: {r}")

    # Thao tác viết tay: tra router + hàm dịch vụ + bảng ghi từ code để đối chiếu.
    for k in khoi:
        for mv in k.get("man", []):
            for tt in mv.get("thao_tac", []):
                api = tt.get("api", "")
                mm = re.match(r"(GET|POST|PUT|PATCH|DELETE)\s+(\S+)", api)
                if not mm:
                    continue
                ung = tim_backend(mm.group(1), mm.group(2))
                if not ung:
                    canh.append(
                        f"thao tác '{tt.get('nut')}' ở {mv.get('route')}: không tìm thấy {api} trong router"
                    )
                    continue
                tt["_be"] = ghi_router(ung[0])

    # Đèn tốc độ theo code (đã đo thì viết tay ghi đè).
    do_that = {d["route"]: d for d in vt.get("do_that", [])}
    bao_cao: dict[str, list[dict]] = defaultdict(list)
    for b in vt.get("bao_cao_man", []):
        bao_cao[b["route"]].append(b)
    for m in man_ra:
        ly_do: list[str] = []
        diem = 0
        n1_get: list[dict] = []
        for k in m["be"]:
            if not k.startswith("GET "):
                continue
            for s in router_ra[k]["dv"]:
                for x in ham_dv[s]["n1"]:
                    if all(y["dong"] != x["dong"] for y in n1_get):
                        n1_get.append({**x, "api": k})
        # Luật đèn (theo code): có chỗ nghi N+1 trên đường tải +1; màn
        # thường bị dựng lại cả trang theo tin mà page.tsx có ≥2 lời gọi máy chủ +1; ≥3 chỗ
        # `await tải lại` +1. 0 = xanh · 1–2 = vàng · ≥3 = đỏ.
        if n1_get:
            diem += 1
            ly_do.append(
                f"{len(n1_get)} chỗ nghi N+1 (vòng lặp có await truy vấn) trên các đường GET của màn"
            )
        if not m["tu_tai"] and not m["chuyen_huong"] and m["ssr_goi"] >= 2:
            diem += 1
            ly_do.append(
                f"màn thường: tin của bất kỳ bảng nào trong {len(live)} bảng LIVE_TABLES đều dựng lại cả trang"
                f" — chạy lại {m['ssr_goi']} lời gọi máy chủ ở page.tsx"
            )
        if m["live_board_sync"]:
            ly_do.append("có LiveBoardSync: dựng thêm một lần lúc vào màn")
        if len(m["be"]) >= 25:  # chỉ ghi, không cộng điểm: cây tệp to ≠ màn gọi hết
            ly_do.append(
                f"cây tệp của màn chứa {len(m['be'])} đường API backend (kể cả popup)"
            )
        if m["so_tai_lai"] >= 3:
            diem += 1
            ly_do.append(f"{m['so_tai_lai']} chỗ `await tải lại` sau thao tác")
        m["n1"] = n1_get[:8]
        if m["chuyen_huong"]:
            den, nguon = "xam", "chuyển hướng — không có giao diện"
        elif not m["be"]:
            den, nguon = (
                "xam",
                "chưa đo — không thấy API trong code (màn tĩnh hoặc lối không suy được)",
            )
        else:
            den = "xanh" if diem == 0 else "vang" if diem <= 2 else "do"
            nguon = "theo code"
        for b in bao_cao.get(m["route"], []):
            ly_do.append(f"Báo cáo #530 [{b['ma']}]: {b['y']} ({b['nguon']})")
            if b.get("den") and THU_DEN[b["den"]] > THU_DEN[den]:
                den, nguon = b["den"], "theo code · báo cáo #530"
        if m["route"] in do_that:
            d = do_that[m["route"]]
            den, nguon = d["den"], "đã đo"
            ly_do = d["so_do"] + ly_do
        m["den"] = {"mau": den, "nguon": nguon, "ly_do": ly_do}

    so_r = {k: i for i, k in enumerate(router_ra)}
    so_h = {k: i for i, k in enumerate(ham_dv)}
    for k in khoi:
        for mv in k.get("man", []):
            for tt in mv.get("thao_tac", []):
                if "_be" in tt:
                    tt["_be"] = so_r[tt["_be"]]
    du_lieu = {
        "sinh_luc": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "commit": git("rev-parse", "--short", "HEAD"),
        "commit_ngay": git("log", "-1", "--format=%cs"),
        "live_tables": live,
        # Gọn cho trình duyệt: router và hàm dịch vụ thành MẢNG, màn/thao tác trỏ
        # bằng chỉ số (mỗi khoá "METHOD /api/v1/…" chỉ viết một lần).
        "man": [dict(m, be=[so_r[k] for k in m["be"]]) for m in man_ra],
        "router": [
            [k, r["ham"], r["tep"], [so_h[x] for x in r["dv"]], int(r["sql_tai_cho"])]
            for k, r in router_ra.items()
        ],
        "ham_dv": [
            [ten, h["tep"], h["dong"], h["ghi"], h["doc"][:6], h["n1"]]
            for ten, h in ham_dv.items()
        ],
        "bang": bang_ra,
        "su_kien": [
            {"tep": t, "ten": ten, "nghe": ev, "cach": cach}
            for t, ten, ev, cach in bd.doc_su_kien()
        ],
        "viet_tay": vt,
    }
    return du_lieu, canh


def main(argv: list[str]) -> int:
    du_lieu, canh = sinh()
    vt = du_lieu["viet_tay"]
    so_tt = sum(
        len(m.get("thao_tac", [])) for k in vt.get("khoi", []) for m in k.get("man", [])
    )
    so_the = sum(len(k.get("the", [])) for k in vt.get("khoi", []))
    den = Counter(m["den"]["mau"] for m in du_lieu["man"])
    print(
        f"màn {len(du_lieu['man'])} · khối {len(vt.get('khoi', []))} · thao tác viết tay {so_tt} · "
        f"thẻ {so_the} · từ điển {len(vt.get('tu_dien', []))} · router {len(du_lieu['router'])} · "
        f"hàm dịch vụ {len(du_lieu['ham_dv'])} · đèn {dict(den)}"
    )
    # Mọi tệp:dòng trong phần viết tay phải còn trỏ vào tệp có thật, dòng chưa
    # vượt cuối tệp. Không bắt được dòng TRÔI (code đổi, số dòng còn hợp lệ).
    chu = json.dumps(
        {k: v for k, v in vt.items() if k != "tu_manh"}, ensure_ascii=False
    )
    so_ref = 0
    for tep, dong in RE_TEP_DONG.findall(chu):
        so_ref += 1
        f = GOC / tep
        if not f.is_file():
            canh.append(f"tệp:dòng trỏ tệp không có: {tep}:{dong}")
        elif int(dong) > bd.doc(f).count("\n") + 1:
            canh.append(f"tệp:dòng vượt cuối tệp: {tep}:{dong}")
    print(f"tệp:dòng viết tay: {so_ref} chỗ")
    for c in canh:
        print("  ⚠", c)
    noi_dung = (
        "// SINH bởi scripts/so-hoc-data.py — đừng sửa tay. Sửa docs/so-hoc/viet-tay.json rồi chạy lại.\n"
        "window.SO_HOC = "
        + json.dumps(du_lieu, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    print(f"cỡ: {len(noi_dung.encode()) // 1024} KB")
    if "--kiem" in argv:
        return 1 if canh else 0
    DAU_RA.parent.mkdir(parents=True, exist_ok=True)
    DAU_RA.write_text(noi_dung, encoding="utf-8")
    print(f"Đã ghi {rel(DAU_RA)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
