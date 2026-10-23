#!/usr/bin/env python3
"""Sinh docs/so-hoc/du-lieu-sinh.js — phần SINH TỪ CODE của "Sổ học hệ thống".

Tuyền 23/10/2026: bản canvas LEGO (hàng nghìn khối theo cấu trúc code) khó nhìn;
cần một sổ học xếp theo NGHIỆP VỤ, tên dễ hiểu đi trước tên code, có tốc độ từng
màn. Trang `docs/so-hoc/index.html` ghép hai nguồn:

  - `docs/so-hoc/viet-tay.js` — VIẾT TAY: khối nghiệp vụ, tên dễ hiểu, "5 điều
    phải nhớ", đường đi thao tác, thẻ tự kiểm, từ điển, đèn tốc độ đã đo.
  - `docs/so-hoc/du-lieu-sinh.js` — tệp NÀY sinh: mỗi màn gọi API nào, hàm
    router nào, service nào, đụng bảng nào, nghe bảng nào, nghi N+1 ở đâu.

Tái dùng phân tích tĩnh của `scripts/ban-do-code.py` (màn → API Next → router →
service), thêm ba thứ nó không làm: bảng mà từng hàm service đọc/ghi (quét chuỗi
SQL), vòng lặp `await` truy vấn (nghi N+1), và đường tin thời gian thực (bảng
`useNgheBang`, màn tự tải `lib/man-tu-tai.ts`, `LIVE_TABLES`).

Chỉ thư viện chuẩn. Chỗ không suy được thì để trống, không đoán.

    python3 scripts/so-hoc-data.py           # ghi lại docs/so-hoc/du-lieu-sinh.js
    python3 scripts/so-hoc-data.py --kiem    # chỉ kiểm viet-tay.js (tệp:dòng, route), exit 1 nếu sai
"""

# ruff: noqa: E501 — chuỗi tài liệu tiếng Việt và regex, cắt dòng chỉ làm khó đọc.
from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
THU_MUC = GOC / "docs" / "so-hoc"
DAU_RA = THU_MUC / "du-lieu-sinh.js"
VIET_TAY = THU_MUC / "viet-tay.js"

# `ban-do-code.py` có gạch nối nên không `import` thẳng được.
_spec = importlib.util.spec_from_file_location(
    "ban_do_code", GOC / "scripts" / "ban-do-code.py"
)
assert _spec and _spec.loader
bd = importlib.util.module_from_spec(_spec)
sys.modules["ban_do_code"] = bd
_spec.loader.exec_module(bd)

SQL_GOI = ("fetch", "fetchrow", "fetchval", "execute", "executemany")
RE_GHI = re.compile(
    r"\b(?:insert\s+into|update|delete\s+from)\s+(?:public\.)?\"?([a-z_][a-z0-9_]*)",
    re.I,
)
RE_DOC = re.compile(r"\b(?:from|join)\s+(?:public\.)?\"?([a-z_][a-z0-9_]*)", re.I)
RE_NGHE = re.compile(r"useNgheBang\(\s*\[([^\]]*)\]")
RE_CHUOI_BANG = re.compile(r"""["']([a-z_][a-z0-9_]*)["']""")
RE_REDIRECT = re.compile(r"""\bredirect\(\s*[`"']([^`"']+)""")


def tuong_doi(p: Path) -> str:
    return p.relative_to(GOC).as_posix()


# ── Bảng mà một hàm service đụng ────────────────────────────────────────────

_cay_cache: dict[Path, tuple[ast.Module, str] | None] = {}


def cay_cua(tep: Path) -> tuple[ast.Module, str] | None:
    if tep not in _cay_cache:
        txt = bd.doc(tep)
        try:
            _cay_cache[tep] = (ast.parse(txt), txt)
        except SyntaxError:
            _cay_cache[tep] = None
    return _cay_cache[tep]


def ham_trong_tep(cay: ast.Module) -> dict[str, ast.AST]:
    """'ten' và 'Lop.ten' → nút hàm (cấp module + phương thức của lớp)."""
    ra: dict[str, ast.AST] = {}
    for n in cay.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ra[n.name] = n
        elif isinstance(n, ast.ClassDef):
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    ra[f"{n.name}.{m.name}"] = m
                    ra.setdefault(m.name, m)
    return ra


def chuoi_trong(n: ast.AST) -> str:
    return "\n".join(
        x.value
        for x in ast.walk(n)
        if isinstance(x, ast.Constant) and isinstance(x.value, str)
    )


def goi_cuc_bo(n: ast.AST, ham: dict[str, ast.AST]) -> list[ast.AST]:
    """Hàm cùng tệp được gọi trong thân `n` (self.x(), x()) — một tầng."""
    ra: list[ast.AST] = []
    for c in ast.walk(n):
        if not isinstance(c, ast.Call):
            continue
        f = c.func
        ten = (
            f.attr
            if isinstance(f, ast.Attribute)
            and isinstance(f.value, ast.Name)
            and f.value.id in ("self", "cls")
            else (f.id if isinstance(f, ast.Name) else None)
        )
        if ten and ten in ham and ham[ten] is not n and ham[ten] not in ra:
            ra.append(ham[ten])
    return ra


def co_sql(n: ast.AST) -> bool:
    return any(
        isinstance(c, ast.Call)
        and isinstance(c.func, ast.Attribute)
        and c.func.attr in SQL_GOI
        for c in ast.walk(n)
    )


def vong_nghi_n1(n: ast.AST, ham: dict[str, ast.AST]) -> list[int]:
    """Dòng của vòng for/while mà thân có `await` một truy vấn (trực tiếp, hoặc
    gọi hàm cùng tệp có truy vấn). Chỉ là NGHI — vòng 3 phần tử cũng bị bắt."""
    ra: list[int] = []
    co_sql_cache: dict[int, bool] = {}
    for v in ast.walk(n):
        if not isinstance(v, (ast.For, ast.AsyncFor, ast.While)):
            continue
        for a in ast.walk(ast.Module(body=v.body, type_ignores=[])):
            if not (isinstance(a, ast.Await) and isinstance(a.value, ast.Call)):
                continue
            f = a.value.func
            if isinstance(f, ast.Attribute) and f.attr in SQL_GOI:
                ra.append(v.lineno)
                break
            ten = (
                f.attr
                if isinstance(f, ast.Attribute)
                else (f.id if isinstance(f, ast.Name) else None)
            )
            dich = ham.get(ten or "")
            if dich is not None and dich is not n:
                k = id(dich)
                if k not in co_sql_cache:
                    co_sql_cache[k] = co_sql(dich)
                if co_sql_cache[k]:
                    ra.append(v.lineno)
                    break
    return sorted(set(ra))


def phan_tich_service(k: bd.KyHieu, bang_that: set[str]) -> dict:
    """{doc, ghi, n1: ['tệp:dòng'], tep, dong} cho một ký hiệu service."""
    tep = bd.tep_module(k.module)
    trong = {
        "doc": [],
        "ghi": [],
        "n1": [],
        "tep": tuong_doi(tep) if tep else "",
        "dong": 0,
    }
    if tep is None:
        return trong
    cc = cay_cua(tep)
    if cc is None:
        return trong
    cay, _ = cc
    ham = ham_trong_tep(cay)
    ten = k.hien.split(".")[-1] if "." in k.hien else k.hien
    nut = ham.get(k.hien) or (
        ham.get(ten) if "." in k.hien or not k.hien[:1].isupper() else None
    )
    if nut is None:
        return trong  # chỉ khởi tạo lớp / không tìm được — không đoán
    trong["dong"] = getattr(nut, "lineno", 0)
    cac = [nut, *goi_cuc_bo(nut, ham)]
    chu = "\n".join(chuoi_trong(x) for x in cac)
    ghi = [b.lower() for b in RE_GHI.findall(chu) if b.lower() in bang_that]
    doc_ = [b.lower() for b in RE_DOC.findall(chu) if b.lower() in bang_that]
    trong["ghi"] = list(dict.fromkeys(ghi))
    trong["doc"] = [b for b in dict.fromkeys(doc_) if b not in trong["ghi"]]
    for x in cac:
        for d in vong_nghi_n1(x, ham):
            trong["n1"].append(f"{trong['tep']}:{d}")
    trong["n1"] = list(dict.fromkeys(trong["n1"]))
    return trong


# ── Đường tin thời gian thực ────────────────────────────────────────────────


def doc_live_tables() -> list[str]:
    txt = bd.doc(bd.APP / "(dashboard)" / "RealtimeRefresher.tsx")
    m = re.search(r"const LIVE_TABLES = \[(.*?)\] as const", txt, re.S)
    if not m:
        return []
    than = re.sub(r"//[^\n]*", "", m.group(1))
    return RE_CHUOI_BANG.findall(than)


def doc_man_tu_tai() -> list[re.Pattern[str]]:
    txt = bd.doc(bd.DASH / "lib" / "man-tu-tai.ts")
    m = re.search(r"const MAN_TU_TAI[^=]*=\s*\[(.*?)\];", txt, re.S)
    if not m:
        return []
    ra = []
    for mm in re.finditer(r"/(\^.*?\$)/", m.group(1)):
        ra.append(re.compile(mm.group(1).replace("\\/", "/")))
    return ra


def bang_co_trigger() -> list[str]:
    """Bảng có trigger gọi notify_row_change (pg_notify) — theo migration."""
    co: set[str] = set()
    re_trg = re.compile(
        r"create\s+(?:or\s+replace\s+)?trigger\s+\"?\w+\"?\s+after[^;]*?\bon\s+(?:public\.)?\"?([a-z_][a-z0-9_]*)[^;]*?notify_row_change",
        re.I | re.S,
    )
    for tep in sorted(bd.MIGRATIONS.glob("*.sql")):
        txt = re.sub(r"--[^\n]*", "", bd.doc(tep))
        co.update(m.group(1).lower() for m in re_trg.finditer(txt))
        # Mẫu vòng lặp: foreach t in array['a','b'] … notify_row_change
        if "notify_row_change" in txt:
            for arr in re.finditer(r"array\s*\[([^\]]*)\]", txt, re.I):
                if "notify_row_change" in txt[arr.end() : arr.end() + 1500]:
                    co.update(
                        x.lower()
                        for x in RE_CHUOI_BANG.findall(arr.group(1).replace("'", '"'))
                    )
    return sorted(co)


# ── Ghép ────────────────────────────────────────────────────────────────────


def sinh() -> dict:
    api_next = bd.doc_api_next()
    ham_router, ky = bd.doc_router()
    lego = bd.doc_lego()
    nhan_nav = dict(bd.RE_NAV.findall(bd.doc(bd.APP / "(dashboard)" / "nav-items.ts")))
    bang_tat_ca = bd.doc_bang()
    bang_that = {b for b, _, _ in bang_tat_ca}
    live = doc_live_tables()
    tu_tai = doc_man_tu_tai()

    mau_next = {k: bd.chuan_duong(k) for k in api_next}
    mau_be: dict[str, list[str]] = {}
    ham_theo_khoa: dict[str, bd.HamRouter] = {}
    for h in ham_router:
        khoa = f"{h.method} {h.duong}"
        ham_theo_khoa[khoa] = h
        mau_be[khoa] = bd.chuan_duong(h.duong)

    def tim_backend(method: str | None, duong: str) -> list[bd.HamRouter]:
        ung = mau_be
        if method and not method.startswith("~"):
            ung = {k: v for k, v in mau_be.items() if k.startswith(method + " ")}
        ra = [ham_theo_khoa[k] for k in bd.chon_tot_nhat(bd.chuan_duong(duong), ung)]
        if method and method.startswith("~") and len(ra) > 1:
            ra = [h for h in ra if h.method == method[1:]] or ra
        return ra

    next_be: dict[str, list[tuple[bd.HamRouter, str | None]]] = {}
    for k, a in api_next.items():
        ds: list[tuple[bd.HamRouter, str | None]] = []
        for method, duong, khoa in a.backend:
            for h in tim_backend(method, duong):
                if (h, khoa) not in ds:
                    ds.append((h, khoa))
        next_be[k] = ds

    sv_cache: dict[str, dict] = {}

    def sv_info(x: str) -> dict:
        if x not in sv_cache:
            sv_cache[x] = phan_tich_service(ky[x], bang_that)
        return sv_cache[x]

    pages = sorted(
        (p for p in bd.APP.rglob("page.tsx") if "node_modules" not in p.parts),
        key=bd.route_cua_page,
    )
    cay_page = {p: bd.duyet(p, bd.TANG_API) for p in pages}
    dem = Counter(f for t in cay_page.values() for f in t if f.name != "page.tsx")
    dung_chung = {f for f, c in dem.items() if c > bd.NGUONG_DUNG_CHUNG * len(pages)}

    man_ra: list[dict] = []
    for p in pages:
        route = bd.route_cua_page(p)
        txt = bd.doc(p)
        mt = bd.RE_TITLE.search(txt)
        tieu_de = mt.group(1) if mt else nhan_nav.get(route, "")
        tep_cay = {f: t for f, t in cay_page[p].items() if f not in dung_chung}
        # Trang chỉ còn redirect: thân ngắn, có redirect(), không JSX.
        chuyen = None
        mr = RE_REDIRECT.search(txt)
        if mr and len(txt) < 3000 and not re.search(r"return\s*\(?\s*<", txt):
            chuyen = mr.group(1)
        goi_next: list[str] = []
        goi_be: list[str] = []
        chu: set[str] = set()
        nghe: list[str] = []
        refresh = 0
        live_sync = False
        for f in tep_cay:
            t = bd.doc(f)
            chu.update(bd.RE_CHUOI.findall(t))
            for m in RE_NGHE.finditer(t):
                for b in RE_CHUOI_BANG.findall(m.group(1)):
                    if b not in nghe:
                        nghe.append(b)
            refresh += t.count("router.refresh()")
            live_sync = live_sync or "<LiveBoardSync" in t
        for f in sorted(tep_cay, key=lambda x: x.as_posix()):
            for m in bd.RE_API.finditer(bd.doc(f)):
                s = m.group(1)
                chu.update(bd.chuan_duong(s))
                if s.startswith("/api/v1/"):
                    if s not in goi_be:
                        goi_be.append(s)
                    continue
                for t in bd.chon_tot_nhat(bd.chuan_duong(s), mau_next):
                    if t not in goi_next:
                        goi_next.append(t)
        # endpoint backend + service
        dau_cuoi: list[dict] = []
        sv: list[str] = []

        def them_ham(h: bd.HamRouter) -> None:
            moi = {
                "m": h.method,
                "duong": h.duong,
                "ham": h.ten,
                "tep": f"{tuong_doi(h.tep)}:{h.dong}",
                "sv": h.service[:6],
            }
            if moi not in dau_cuoi:
                dau_cuoi.append(moi)
            sv.extend(x for x in h.service if x not in sv)

        for t in goi_next:
            for h, khoa in next_be.get(t, []):
                if khoa is not None and khoa not in chu:
                    continue
                them_ham(h)
        ssr: list[dict] = []
        for s in goi_be:
            for h in tim_backend(None, s):
                them_ham(h)
                ssr.append({"duong": h.duong, "tep": f"{tuong_doi(h.tep)}:{h.dong}"})
        doc_b: Counter[str] = Counter()
        ghi_b: Counter[str] = Counter()
        n1: list[dict] = []
        for x in sv:
            i = sv_info(x)
            doc_b.update(i["doc"])
            ghi_b.update(i["ghi"])
            for d in i["n1"]:
                n1.append({"sv": x, "o": d})
        la_tu_tai = any(r.match(route) for r in tu_tai)
        lego_ma = bd.lego_cho(route, lego)
        man_ra.append(
            {
                "route": route,
                "tieu_de": tieu_de,
                "tep": tuong_doi(p),
                "lego": "" if lego_ma == "?" else lego_ma.replace("`", ""),
                "chuyen_huong": chuyen,
                "api_next": goi_next,
                "ssr": ssr,
                "dau_cuoi": dau_cuoi[:40],
                "so_dau_cuoi": len(dau_cuoi),
                "service": sv[:40],
                "so_service": len(sv),
                "bang_doc": [b for b, _ in doc_b.most_common(10)],
                "bang_ghi": [b for b, _ in ghi_b.most_common(10)],
                "nghi_n1": n1[:12],
                "so_nghi_n1": len(n1),
                "nghe_bang": nghe,
                "tu_tai": la_tu_tai,
                "live_board_sync": live_sync,
                "router_refresh": refresh,
            }
        )

    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=GOC,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sha = "?"
    return {
        "sinh_luc": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "commit": sha,
        "man": man_ra,
        "live_tables": live,
        "bang_trigger": bang_co_trigger(),
        "bang": [{"ten": b, "tao": t, "sua": s} for b, t, s in bang_tat_ca],
        "so_route_api_next": len(api_next),
        "so_ham_router": len(ham_router),
    }


# ── Kiểm phần viết tay ──────────────────────────────────────────────────────

RE_NGUON = re.compile(
    r"((?:src|docs|scripts|supabase|caddy|monitoring)/[\w./()\[\]@-]+?\.\w+):(\d+)(?:-(\d+))?"
)


def kiem_viet_tay(routes: set[str]) -> list[str]:
    if not VIET_TAY.is_file():
        return [f"thiếu {tuong_doi(VIET_TAY)}"]
    txt = VIET_TAY.read_text(encoding="utf-8")
    loi: list[str] = []
    so_dong: dict[str, int] = {}
    for m in RE_NGUON.finditer(txt):
        tep, dong = m.group(1), int(m.group(3) or m.group(2))
        if tep not in so_dong:
            p = GOC / tep
            so_dong[tep] = len(bd.doc(p).splitlines()) if p.is_file() else -1
        if so_dong[tep] < 0:
            loi.append(f"tệp không có: {m.group(0)}")
        elif dong > so_dong[tep]:
            loi.append(f"dòng vượt cuối tệp ({so_dong[tep]}): {m.group(0)}")
    # Chỉ giá trị bắt đầu bằng "/" — khoá "route" của bảng mảnh tên là chữ thường.
    for m in re.finditer(r'"route":\s*"(/[^"]*)"', txt):
        if m.group(1) not in routes:
            loi.append(f"route không có màn: {m.group(1)}")
    return loi


def main(argv: list[str]) -> int:
    du = sinh()
    routes = {m["route"] for m in du["man"]}
    loi = kiem_viet_tay(routes)
    for x in loi:
        print("⚠", x)
    if "--kiem" in argv:
        print("viet-tay.js khớp code ✓" if not loi else f"{len(loi)} chỗ lệch")
        return 1 if loi else 0
    THU_MUC.mkdir(parents=True, exist_ok=True)
    noi = json.dumps(du, ensure_ascii=False, separators=(",", ":"))
    DAU_RA.write_text(
        "// SINH bởi scripts/so-hoc-data.py — đừng sửa tay; chạy lại script.\n"
        f"window.SO_HOC_SINH = {noi};\n",
        encoding="utf-8",
    )
    print(
        f"ghi {tuong_doi(DAU_RA)} · {len(du['man'])} màn · {DAU_RA.stat().st_size // 1024} KB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
