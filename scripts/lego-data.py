#!/usr/bin/env python3
"""Sinh dữ liệu cho "Bản đồ lego toàn hệ thống" — nhúng thẳng vào docs/lego/index.html.

Tuyền 23/10/2026: bản đồ trước (canvas, sổ học) khô và khó đọc. Bản lego: khối nối
dây, bấm một thao tác thì dây sáng lên và hiện từng bước có chấm đỏ / vàng / xanh.
Trang phải TỰ CHỨA (không CDN, không fetch): tải về, bấm đúp là mở.

Hai nguồn, tách bạch:
  * VIẾT TAY `docs/lego/viet-tay.json`: chia khối, lời giải thích, thao tác (59
    đường đi lấy từ sổ học #535 + thao tác bổ sung), số đã đo, đề xuất, phân tích
    1.000 người cùng bấm.
  * SINH TỪ CODE (tệp này): sự kiện → bên nhận (`events/catalogue.py`), bên nhận
    ghi bảng nào, bảng nào có trigger báo tin (migrations), danh sách bảng màn
    nghe (`RealtimeRefresher.tsx`, `useNgheBang`), màn tự tải (`man-tu-tai.ts`),
    số cấu hình thật (bể kết nối, số tiến trình, nhịp worker…), và phân tích tĩnh
    hàm dịch vụ của từng thao tác: mấy câu SQL, có giao dịch không, khoá gì.

Phân tích TĨNH, chỉ thư viện chuẩn. Không suy được thì để trống, không đoán.
Số "ước theo code" = đếm `await conn.*` (đọc sâu 2 tầng), không phải số đo.

    python3 scripts/lego-data.py          # ghi dữ liệu vào docs/lego/index.html
    python3 scripts/lego-data.py --kiem   # không ghi; exit 1 nếu tệp:dòng hỏng,
                                          # bảng/sự kiện lạ, hoặc trang lệch code
"""

# ruff: noqa: E501 — chuỗi tài liệu tiếng Việt và regex, cắt dòng chỉ làm khó đọc.
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
PY = GOC / "src" / "clinicai"
DASH = GOC / "src" / "dashboard"
MIG = GOC / "supabase" / "migrations"
VIET_TAY = GOC / "docs" / "lego" / "viet-tay.json"
TRANG = GOC / "docs" / "lego" / "index.html"
MO = "/*<<DU-LIEU>>*/"
DONG = "/*<</DU-LIEU>>*/"

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
RE_TEP_DONG = re.compile(
    r"((?:src|docs|supabase|scripts|caddy|docker)/[\w()\[\]./-]+?\.(?:py|tsx?|sql|md|json|mts|cjs|sh|service|timer|conf)|Dockerfile\.api|docker-compose[\w.]*\.yml|caddy/Caddyfile):(\d+)"
)
#: Tên không phải bảng (từ khoá SQL, CTE hay gặp, hàm) — bỏ khi trích bảng.
KHONG_PHAI_BANG = {
    "select",
    "the",
    "lateral",
    "unnest",
    "jsonb_array_elements",
    "generate_series",
    "jsonb_each",
    "json_each",
    "jsonb_to_recordset",
    "now",
    "v",
    "x",
    "t",
    "s",
    "d",
    "only",
    "dong",
    "cte",
    "base",
    "rows",
    "data",
    "src",
    "new",
    "old",
    "excluded",
    "values",
    "jsonb_array_elements_text",
    "string_to_array",
    "regexp_split_to_table",
}


def rel(p: Path) -> str:
    return p.relative_to(GOC).as_posix()


def doc(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def dong_so(txt: str, vi_tri: int) -> int:
    return txt.count("\n", 0, vi_tri) + 1


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=GOC,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "?"


# ── Sự kiện: danh mục + bên nhận ───────────────────────────────────────────


def doc_catalogue() -> dict[str, dict]:
    tep = PY / "events" / "catalogue.py"
    cay = ast.parse(doc(tep))
    hang: dict[str, str] = {}
    for n in cay.body:
        if (
            isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
        ):
            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                hang[n.targets[0].id] = n.value.value
    ra: dict[str, dict] = {}
    for n in ast.walk(cay):
        if not (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "SuKien"
        ):
            continue
        kw = {k.arg: k.value for k in n.keywords}
        ten = kw.get("ten")
        if not (isinstance(ten, ast.Constant) and isinstance(ten.value, str)):
            continue
        cons: list[str] = []
        c = kw.get("consumers")
        if isinstance(c, (ast.List, ast.Tuple)):
            for e in c.elts:
                if isinstance(e, ast.Name) and e.id in hang:
                    cons.append(hang[e.id])
                elif isinstance(e, ast.Constant) and isinstance(e.value, str):
                    cons.append(e.value)
        nhan = kw.get("nhan")
        mod = kw.get("source_module")
        ra[ten.value] = {
            "nhan": nhan.value if isinstance(nhan, ast.Constant) else "",
            "module": mod.value if isinstance(mod, ast.Constant) else "",
            "consumers": cons,
            "nguon": f"{rel(tep)}:{n.lineno}",
        }
    return ra


def bang_trong_sql(txt: str) -> tuple[set[str], set[str]]:
    ghi: set[str] = set()
    for r in RE_GHI:
        ghi |= {m.group(1).lower() for m in r.finditer(txt)}
    docb = {m.group(1).lower() for m in RE_DOC.finditer(txt)}
    return ghi - KHONG_PHAI_BANG, docb - KHONG_PHAI_BANG


def doc_consumer(bang_that: set[str]) -> dict[str, dict]:
    """Tên bên nhận → tệp, hàm, bảng nó ghi (regex trên chính tệp của nó)."""
    thu = PY / "events" / "consumers"
    hang_cat: dict[str, str] = {}
    for m in re.finditer(
        r'^([A-Z_]+)\s*=\s*"([a-z_.]+)"', doc(PY / "events" / "catalogue.py"), re.M
    ):
        hang_cat[m.group(1)] = m.group(2)
    ra: dict[str, dict] = {}
    for tep in sorted(thu.glob("*.py")):
        txt = doc(tep)
        hang = dict(hang_cat)
        for m in re.finditer(r'^([A-Z_]+)\s*=\s*"([a-z_.]+)"', txt, re.M):
            hang[m.group(1)] = m.group(2)
        ghi, _ = bang_trong_sql(txt)
        for m in re.finditer(
            r"^dang_ky\(\s*([A-Za-z_]+)\s*,\s*([a-z_0-9]+)\s*\)", txt, re.M
        ):
            ten = hang.get(m.group(1), m.group(1))
            ra[ten] = {
                "tep": rel(tep),
                "ham": m.group(2),
                "nguon": f"{rel(tep)}:{dong_so(txt, m.start())}",
                "bang_ghi": sorted(b for b in ghi if b in bang_that),
            }
    return ra


# ── Trigger báo tin (migrations) ───────────────────────────────────────────

RE_DO = re.compile(r"DO\s+(\$[A-Za-z_]*\$).*?\1", re.S)
RE_TAO_TRG = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(\w+)\s+(.*?);", re.S | re.I
)
RE_BO_TRG = re.compile(
    r"DROP\s+TRIGGER\s+(?:IF\s+EXISTS\s+)?(trg_notify_\w+)\s+ON\s+(?:public\.)?(\w+)\s*;",
    re.I,
)


def doc_trigger() -> dict[str, str]:
    """Bảng → migration (tệp:dòng) cuối cùng gắn trigger gọi notify_row_change."""
    co: dict[str, str] = {}
    for tep in sorted(MIG.glob("*.sql")):
        txt = re.sub(r"--[^\n]*", "", doc(tep))
        su_kien: list[tuple[int, str, str | None]] = []  # (vị trí, bảng, tạo|None=bỏ)
        for m in RE_DO.finditer(txt):
            khoi = m.group(0)
            if "notify_row_change" not in khoi or "trg_notify_" not in khoi:
                continue
            for a in re.finditer(r"ARRAY\s*\[(.*?)\]", khoi, re.S):
                for ten in re.findall(r"'([a-z_][a-z0-9_]*)'", a.group(1)):
                    su_kien.append((m.start() + a.start(), ten, "tao"))
        for m in RE_TAO_TRG.finditer(txt):
            than = m.group(2)
            if "notify_row_change" not in than:
                continue
            on = re.search(r"\bON\s+(?:public\.)?(\w+)", than, re.I)
            if on:
                su_kien.append((m.start(), on.group(1).lower(), "tao"))
        for m in RE_BO_TRG.finditer(txt):
            su_kien.append((m.start(), m.group(2).lower(), None))
        for vt, bang, loai in sorted(su_kien):
            if loai:
                co[bang] = f"{rel(tep)}:{dong_so(txt, vt)}"
            else:
                co.pop(bang, None)
    return co


def doc_bang_that() -> tuple[set[str], dict[str, str]]:
    """Mọi bảng tạo trong migrations + câu COMMENT ON TABLE đầu tiên (rút gọn)."""
    bang: set[str] = set()
    ghi_chu: dict[str, str] = {}
    for tep in sorted(MIG.glob("*.sql")):
        txt = doc(tep)
        bang |= {
            m.lower()
            for m in re.findall(
                r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?\"?([a-z_][a-z0-9_]*)",
                txt,
                re.I,
            )
        }
        for m in re.finditer(
            r"COMMENT\s+ON\s+TABLE\s+(?:public\.)?(\w+)\s+IS\s+((?:'(?:[^']|'')*'\s*)+);",
            txt,
            re.I | re.S,
        ):
            cau = " ".join(re.findall(r"'((?:[^']|'')*)'", m.group(2))).replace(
                "''", "'"
            )
            cau = re.split(r"(?<=[.!?])\s", cau.strip())[0][:180]
            ghi_chu[m.group(1).lower()] = cau
    return bang, ghi_chu


# ── Giao diện: bảng màn nghe ───────────────────────────────────────────────


def doc_live_tables() -> tuple[list[str], str]:
    tep = DASH / "app" / "(dashboard)" / "RealtimeRefresher.tsx"
    txt = doc(tep)
    m = re.search(r"const LIVE_TABLES = \[(.*?)\] as const", txt, re.S)
    if not m:
        return [], rel(tep)
    than = re.sub(r"//[^\n]*", "", m.group(1))
    return re.findall(r'"([a-z_0-9]+)"', than), f"{rel(tep)}:{dong_so(txt, m.start())}"


def doc_man_tu_tai() -> tuple[list[str], list[str], str]:
    tep = DASH / "lib" / "man-tu-tai.ts"
    txt = doc(tep)
    m = re.search(r"MAN_TU_TAI[^=]*=\s*\[(.*?)\];", txt, re.S)
    mau = re.findall(r"/\^(.*?)\$/", m.group(1)) if m else []
    b = re.search(r"BANG_LAYOUT[^=]*=\s*\[(.*?)\]", txt, re.S)
    return (
        mau,
        re.findall(r'"([a-z_]+)"', b.group(1)) if b else [],
        f"{rel(tep)}:{dong_so(txt, m.start()) if m else 1}",
    )


def route_cua_tep(p: Path) -> str:
    """app/(dashboard)/thu-ngan/QuayThuNgan.tsx → /thu-ngan (thư mục chứa).

    Thư mục `_lam-viec/…` là thành phần dùng chung nhiều màn; tệp nằm thẳng
    dưới (dashboard) là layout — gắn vào mọi màn.
    """
    goc = [x for x in p.relative_to(DASH / "app").parts[:-1] if not x.startswith("(")]
    chung = next((x for x in goc if x.startswith("_")), None)
    if chung:
        return f"(dùng chung: {chung}/{p.stem})"
    if not goc:
        return "(layout — mọi màn)"
    return "/" + "/".join(goc)


def doc_nghe_bang() -> list[dict]:
    ra = []
    for tep in sorted((DASH / "app").rglob("*.tsx")) + sorted(
        (DASH / "components").rglob("*.tsx")
    ):
        if "node_modules" in tep.parts:
            continue
        txt = doc(tep)
        for m in re.finditer(r"useNgheBang\(\s*(\[[^\]]*\]|[A-Za-z_]\w*)", txt, re.S):
            arg = m.group(1)
            if arg.startswith("["):
                bang = re.findall(r'"([a-z_0-9]+)"', re.sub(r"//[^\n]*", "", arg))
            else:
                k = re.search(rf"const {re.escape(arg)}\b[^=]*=\s*\[(.*?)\]", txt, re.S)
                bang = re.findall(r'"([a-z_0-9]+)"', k.group(1)) if k else []
            if not bang:
                continue
            route = (
                route_cua_tep(tep) if (DASH / "app") in tep.parents else "(dùng chung)"
            )
            ra.append(
                {
                    "tep": rel(tep),
                    "nguon": f"{rel(tep)}:{dong_so(txt, m.start())}",
                    "route": route,
                    "bang": bang,
                }
            )
    return ra


# ── Số cấu hình thật ───────────────────────────────────────────────────────


def tim(tep: Path, mau: str, nhom: int = 1) -> tuple[str, str]:
    txt = doc(tep)
    m = re.search(mau, txt, re.M)
    if not m:
        return "?", rel(tep)
    return m.group(nhom), f"{rel(tep)}:{dong_so(txt, m.start())}"


def doc_cau_hinh() -> dict[str, dict]:
    dbpy = PY / "core" / "database.py"
    wk = PY / "worker.py"
    ra: dict[str, dict] = {}

    def dat(ma: str, y: str, kq: tuple[str, str]) -> None:
        ra[ma] = {"y": y, "gia_tri": kq[0], "nguon": kq[1]}

    dat(
        "pool_api",
        "Bể kết nối API — trần mặc định",
        tim(dbpy, r"^POOL_MAX_SIZE = (\d+)"),
    )
    dat(
        "pool_min",
        "Bể kết nối — giữ sẵn tối thiểu",
        tim(dbpy, r"^POOL_MIN_SIZE = (\d+)"),
    )
    dat(
        "pool_worker",
        "Bể kết nối của worker (su-kien, day-tep…)",
        tim(dbpy, r"^WORKER_POOL_MAX_SIZE = (\d+)"),
    )
    dat(
        "sql_timeout",
        "Mỗi câu SQL bị huỷ sau (giây)",
        tim(dbpy, r"^COMMAND_TIMEOUT = (\d+)"),
    )
    dat(
        "pool_staging",
        "Bể API ở staging",
        tim(
            GOC / "docker-compose.staging.yml",
            r"POOL_MAX_SIZE: \$\{POOL_MAX_SIZE:-(\d+)\}",
        ),
    )
    dat(
        "uvicorn",
        "Lệnh chạy API (không có --workers ⇒ 1 tiến trình)",
        tim(GOC / "Dockerfile.api", r'^CMD \[("uvicorn".*)\]'),
    )
    dat(
        "next_tran",
        "Số tiến trình Next tối đa (cluster.cjs)",
        tim(DASH / "cluster.cjs", r"Math\.min\(nhan, (\d+)\)"),
    )
    dat(
        "next_tg",
        "Next: thời gian tối đa một request (0 = không giới hạn)",
        tim(DASH / "cluster.cjs", r"mayChu\.requestTimeout = (\d+)"),
    )
    dat(
        "dash_ram",
        "RAM tối đa dashboard",
        tim(GOC / "docker-compose.yml", r"DASHBOARD_MEMORY_LIMIT:-(\w+)\}"),
    )
    dat(
        "api_ram",
        "RAM tối đa api",
        tim(GOC / "docker-compose.yml", r"API_MEMORY_LIMIT:-(\w+)\}"),
    )
    dat(
        "caddy_ram",
        "RAM tối đa Caddy",
        tim(GOC / "docker-compose.yml", r"CADDY_MEMORY_LIMIT:-(\w+)\}"),
    )
    dat(
        "sukien_ram",
        "RAM tối đa su-kien",
        tim(GOC / "docker-compose.yml", r"SU_KIEN_MEMORY_LIMIT:-(\w+)\}"),
    )
    dat(
        "sukien_nghi",
        "Worker su-kien nghỉ giữa các vòng (giây)",
        tim(wk, r"wait_for\(stop\.wait\(\), timeout=([\d.]+)\)\s*\n\s*break"),
    )
    dat(
        "gotrue_pool",
        "Bể DB của GoTrue",
        tim(GOC / "docker-compose.supabase.yml", r'GOTRUE_DB_MAX_POOL_SIZE: "(\d+)"'),
    )
    dat(
        "pgrst_pool",
        "Bể DB của PostgREST",
        tim(GOC / "docker-compose.supabase.yml", r'PGRST_DB_POOL: "(\d+)"'),
    )
    dat(
        "pg_image",
        "Phiên bản Postgres",
        tim(GOC / "docker-compose.supabase.yml", r"image: (postgres:\d+)"),
    )
    dat(
        "max_conn",
        "max_connections của Postgres (ghi trong ngân sách kết nối)",
        tim(dbpy, r"max_connections=(\d+)"),
    )
    dat(
        "queue_sse",
        "Hàng tin mỗi tab ở bộ phát (đầy thì bỏ)",
        tim(PY / "core" / "change_broker.py", r"^QUEUE_SIZE = (\d+)"),
    )
    dat(
        "noi_lai",
        "Bộ nghe LISTEN nối lại sau (giây)",
        tim(PY / "core" / "change_broker.py", r"^RECONNECT_DELAY_S = ([\d.]+)"),
    )
    dat(
        "nhip_sse",
        "Nhịp giữ dòng SSE (giây)",
        tim(PY / "api" / "v1" / "routers" / "events.py", r"^HEARTBEAT_S = ([\d.]+)"),
    )
    dat(
        "gop_tin",
        "Trình duyệt gộp tin trong (ms) + lệch ngẫu nhiên",
        tim(
            DASH / "lib" / "nhip-lam-moi.ts",
            r"NHIP_NGHE_TIN = \{ choToiDa: (\d+), jitter: (\d+) \}",
        ),
    )
    dat(
        "poll",
        "Hỏi lại dự phòng mỗi (ms), kể cả khi SSE khoẻ",
        tim(
            DASH / "app" / "(dashboard)" / "RealtimeRefresher.tsx",
            r"^const POLL_MS = ([\d_]+);",
        ),
    )
    dat(
        "chuong_poll",
        "Chuông tự hỏi lại mỗi (ms)",
        tim(
            DASH / "app" / "(dashboard)" / "NotificationContext.tsx",
            r"^const POLL_MS = ([\d_]+);",
        ),
    )
    dat(
        "identity_ttl",
        "API nhớ danh tính người gọi (giây)",
        tim(PY / "api" / "identity.py", r"^_IDENTITY_TTL_SECONDS = ([\d.]+)"),
    )
    dat(
        "tran_nguoi",
        "Trần lượt gọi / người / 60 giây (quá thì 429)",
        tim(PY / "api" / "runaway_guard.py", r"^DEFAULT_CEILING = (\d+)"),
    )
    dat(
        "lan_thu",
        "Bên nhận sự kiện thử tối đa (lần) rồi vào DEAD",
        tim(PY / "events" / "worker.py", r"^SO_LAN_THU_TOI_DA = (\d+)"),
    )
    dat(
        "han_thue",
        "Hạn nhận việc của worker (giây)",
        tim(PY / "events" / "worker.py", r"^HAN_THUE_GIAY = (\d+)"),
    )
    dat(
        "idem_ttl",
        "Idempotency-Key sống (giờ)",
        tim(PY / "api" / "idempotency.py", r"^KEY_TTL_HOURS = (\d+)"),
    )
    dat(
        "sao_luu_15p",
        "Lịch sao lưu 15 phút",
        tim(
            GOC / "scripts" / "systemd" / "clinicai-backup-15p.timer",
            r"^OnCalendar=(.+)$",
        ),
    )
    dat(
        "sao_luu_dem",
        "Lịch sao lưu đêm",
        tim(
            GOC / "scripts" / "systemd" / "clinicai-backup.timer", r"^OnCalendar=(.+)$"
        ),
    )
    dat(
        "staging_nap",
        "Nạp staging từ bản sao",
        tim(
            GOC / "scripts" / "systemd" / "clinicai-staging-nap.timer",
            r"^OnCalendar=(.+)$",
        ),
    )
    dat(
        "giu_15p",
        "Giữ bản sao 15 phút (ngày)",
        tim(
            GOC / "scripts" / "systemd" / "clinicai-backup-15p.service",
            r"BACKUP_KEEP_DAYS=(\d+)",
        ),
    )
    dat(
        "canh_pool",
        "Cảnh báo khi chờ mượn kết nối quá (ms)",
        tim(PY / "core" / "quan_sat.py", r"^NGUONG_CHO_POOL_MS = ([\d.]+)"),
    )
    return ra


# ── Phân tích tĩnh hàm dịch vụ ─────────────────────────────────────────────


def chuoi_cua(n: ast.AST, hang: dict[str, str]) -> str:
    """Chuỗi SQL trong một biểu thức: hằng, f-string, nối `+`, tên hằng module."""
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return n.value
    if isinstance(n, ast.JoinedStr):
        return "".join(chuoi_cua(v, hang) for v in n.values)
    if isinstance(n, ast.FormattedValue):
        return chuoi_cua(n.value, hang)
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
        return chuoi_cua(n.left, hang) + chuoi_cua(n.right, hang)
    if isinstance(n, ast.Name):
        return hang.get(n.id, "")
    return ""


class KhoAst:
    def __init__(self) -> None:
        self.cay: dict[Path, ast.Module | None] = {}
        self.nho: dict[tuple[str, int], dict] = {}

    def lay(self, tep: Path) -> ast.Module | None:
        if tep not in self.cay:
            try:
                self.cay[tep] = ast.parse(doc(tep))
            except SyntaxError:
                self.cay[tep] = None
        return self.cay[tep]

    def ham_tai(self, tep: Path, dong: int) -> ast.AST | None:
        cay = self.lay(tep)
        if cay is None:
            return None
        tot = None
        for n in ast.walk(cay):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                dau = min([d.lineno for d in n.decorator_list] + [n.lineno])
                if dau <= dong <= (n.end_lineno or n.lineno):
                    if tot is None or n.lineno > tot.lineno:
                        tot = n
        return tot

    def ham_ten(self, tep: Path, ten: str) -> ast.AST | None:
        cay = self.lay(tep)
        if cay is None:
            return None
        for n in ast.walk(cay):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == ten:
                return n
        return None

    def hang_chuoi(self, tep: Path) -> dict[str, str]:
        cay = self.lay(tep)
        ra: dict[str, str] = {}
        if cay is None:
            return ra
        for n in cay.body:
            if (
                isinstance(n, ast.Assign)
                and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
            ):
                s = chuoi_cua(n.value, {})
                if s:
                    ra[n.targets[0].id] = s
        return ra

    def import_cua(self, tep: Path) -> dict[str, Path]:
        cay = self.lay(tep)
        ra: dict[str, Path] = {}
        if cay is None:
            return ra
        for n in ast.walk(cay):
            if (
                isinstance(n, ast.ImportFrom)
                and n.module
                and n.module.startswith("clinicai.")
            ):
                goc = GOC / "src" / Path(*n.module.split("."))
                p = (
                    goc.with_suffix(".py")
                    if goc.with_suffix(".py").exists()
                    else goc / "__init__.py"
                )
                for a in n.names:
                    ra[a.asname or a.name] = p
        return ra

    def phan_tich(self, tep: Path, ham: ast.AST, sau: int = 0) -> dict:
        khoa = (str(tep), getattr(ham, "lineno", 0))
        if khoa in self.nho:
            return self.nho[khoa]
        kq = {
            "sql": 0,
            "sql_vong": 0,
            "giao_dich": False,
            "khoa": set(),
            "ghi": set(),
            "doc": set(),
            "con": 0,
        }
        self.nho[khoa] = kq  # chặn đệ quy
        hang = self.hang_chuoi(tep)
        imp = self.import_cua(tep)
        trong_vong: set[int] = set()
        for n in ast.walk(ham):
            if isinstance(
                n,
                (
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.ListComp,
                    ast.SetComp,
                    ast.DictComp,
                    ast.GeneratorExp,
                ),
            ):
                for c in ast.walk(n):
                    trong_vong.add(id(c))
        cac_chuoi: list[str] = []
        for n in ast.walk(ham):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                cac_chuoi.append(n.value)
            elif isinstance(n, ast.Name) and n.id in hang:
                cac_chuoi.append(hang[n.id])
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            ten = (
                f.attr
                if isinstance(f, ast.Attribute)
                else (f.id if isinstance(f, ast.Name) else "")
            )
            if isinstance(f, ast.Attribute) and ten in SQL_METHOD:
                kq["sql"] += 1
                if id(n) in trong_vong:
                    kq["sql_vong"] += 1
            if ten == "transaction":
                kq["giao_dich"] = True
            if ten in {"bien_nhan_doc", "bien_nhan_ghi"}:
                kq["khoa"].add(
                    "biên nhận lệnh (command_receipt) — bấm lại trả kết quả cũ"
                )
            if ten in {"khoa_luot", "_khoa_luot_thu"}:
                kq["khoa"].add("khoá dòng lượt khám (SELECT … FOR UPDATE)")
            if sau >= 2 or not ten or ten in SQL_METHOD:
                continue
            # Đọc sâu: self.x / x trong cùng tệp, hoặc hàm import từ clinicai.*
            dich: tuple[Path, ast.AST] | None = None
            if (
                isinstance(f, ast.Attribute)
                and isinstance(f.value, ast.Name)
                and f.value.id in {"self", "cls"}
            ):
                h = self.ham_ten(tep, ten)
                if h is not None:
                    dich = (tep, h)
            elif isinstance(f, ast.Name):
                if f.id in imp and imp[f.id].exists():
                    h = self.ham_ten(imp[f.id], f.id)
                    if h is not None:
                        dich = (imp[f.id], h)
                else:
                    h = self.ham_ten(tep, f.id)
                    if h is not None and h is not ham:
                        dich = (tep, h)
            elif (
                isinstance(f, ast.Attribute)
                and isinstance(f.value, ast.Name)
                and f.value.id in imp
            ):
                p = imp[f.value.id]
                if p.exists():
                    h = self.ham_ten(p, ten)
                    if h is not None:
                        dich = (p, h)
            if dich is not None:
                con = self.phan_tich(dich[0], dich[1], sau + 1)
                if con is kq:
                    continue
                kq["con"] += con["sql"]
                # Hàm con gọi TRONG vòng lặp: mọi câu SQL của nó nhân theo số vòng.
                kq["sql_vong"] += con["sql_vong"] + (
                    con["sql"] if id(n) in trong_vong else 0
                )
                kq["giao_dich"] |= con["giao_dich"]
                kq["khoa"] |= con["khoa"]
                kq["ghi"] |= con["ghi"]
                kq["doc"] |= con["doc"]
        sql = "\n".join(cac_chuoi)
        ghi, docb = bang_trong_sql(sql)
        kq["ghi"] |= ghi
        kq["doc"] |= docb
        if re.search(r"FOR\s+UPDATE", sql, re.I):
            kq["khoa"].add("khoá dòng (SELECT … FOR UPDATE)")
        if re.search(r"FOR\s+UPDATE\s+SKIP\s+LOCKED", sql, re.I):
            kq["khoa"].add("nhận việc không giẫm nhau (SKIP LOCKED)")
        if "pg_advisory_xact_lock" in sql:
            kq["khoa"].add("khoá tư vấn trong giao dịch (pg_advisory_xact_lock)")
        if re.search(r"ON\s+CONFLICT", sql, re.I):
            kq["khoa"].add("ON CONFLICT (ràng buộc UNIQUE chặn trùng)")
        if re.search(r"\brevision\b", sql):
            kq["khoa"].add("so số phiên bản (revision) — lệch là từ chối")
        return kq


def tach_nguon(s: str) -> tuple[Path, int] | None:
    m = RE_TEP_DONG.search(s or "")
    if not m:
        return None
    return GOC / m.group(1), int(m.group(2))


# ── Dựng bước cho một thao tác ─────────────────────────────────────────────


def ten_bang(ds: list[str]) -> list[str]:
    """'payment (chỉ khi PAID)' → payment; 'hoặc x (…)' → x; '(A/B: appointment, visit)' → appointment, visit."""
    ra: list[str] = []
    for raw in ds:
        raw = raw.strip()
        if raw.startswith("(") and ":" in raw:
            ra += re.findall(r"[a-z_][a-z0-9_]+", raw.split(":", 1)[1])
            continue
        raw = re.sub(r"^hoặc\s+", "", raw)
        m = re.match(r"([a-z_][a-z0-9_.]*)(?=$|[\s(])", raw)
        if m:
            ra.append(m.group(1))
    return list(dict.fromkeys(ra))


def ma_nhat_ky() -> set[str]:
    """Mã nhật ký thao tác (event_log) có nhãn — khác sự kiện nghiệp vụ của catalogue."""
    txt = doc(PY / "services" / "audit_labels.py")
    return set(re.findall(r'^\s+"([a-z_]+\.[a-z_.]+)":', txt, re.M))


MA_NHAT_KY: set[str] = set()
CATALOGUE: dict[str, dict] = {}


def ten_su_kien(ds: list[str]) -> tuple[list[str], list[str]]:
    """Tách sự kiện nghiệp vụ (catalogue) khỏi mã nhật ký thao tác (event_log)."""
    sk: list[str] = []
    vet: list[str] = []
    for raw in ds:
        nhat = "event_log" in raw or "record_event" in raw
        for phan in re.split(r"\s+(?:hoặc|/)\s+", raw):
            m = re.match(r"\s*([a-z_]+\.[a-z_.]+)", phan)
            if m:
                ma = m.group(1)
                (
                    vet if nhat or (ma in MA_NHAT_KY and ma not in CATALOGUE) else sk
                ).append(ma)
    return list(dict.fromkeys(sk)), list(dict.fromkeys(vet))


def gon(ds: list[str], n: int = 6) -> str:
    return ", ".join(ds[:n]) + (f" … (+{len(ds) - n})" if len(ds) > n else "")


def dung_buoc(t: dict, ctx: dict) -> tuple[list[dict], dict]:
    """Bước mặc định từ dữ liệu cấu trúc. Thao tác có `buoc` viết tay thì dùng bản tay."""
    pt = {
        "sql": 0,
        "sql_vong": 0,
        "giao_dich": False,
        "khoa": set(),
        "ghi": set(),
        "doc": set(),
    }
    for dv in t.get("dich_vu", []):
        tn = tach_nguon(dv.get("nguon", ""))
        if not tn or not tn[0].exists():
            continue
        h = ctx["ast"].ham_tai(*tn)
        if h is None:
            continue
        kq = ctx["ast"].phan_tich(tn[0], h)
        pt["sql"] = max(pt["sql"], kq["sql"] + kq["con"])
        pt["sql_vong"] = max(pt["sql_vong"], kq["sql_vong"])
        pt["giao_dich"] |= kq["giao_dich"]
        pt["khoa"] |= kq["khoa"]
        pt["ghi"] |= kq["ghi"] & ctx["bang_that"]
        pt["doc"] |= kq["doc"] & ctx["bang_that"]
    if t.get("buoc"):
        return t["buoc"], pt
    ghi_khai = ten_bang(t.get("bang_ghi", []))
    live = ctx["live"]
    trig = ctx["trigger"]
    nghia = ctx["nghia"]
    buoc: list[dict] = []
    buoc.append(
        {
            "y": f"{(t.get('ai') or 'Nhân viên').split(' — ')[0]} bấm {re.sub(r'^Bấm ', '', t['nut'])} ở màn {t.get('man_ten') or t['man']}.",
            "chi_tiet": t.get("man", ""),
            "nguon": t.get("nut_nguon", ""),
            "den": "xanh",
            "lop": ["trinh-duyet"],
            "thoi_gian": "tức thì",
            "nhan_tg": "uoc",
        }
    )
    buoc.append(
        {
            "y": "Trình duyệt gửi lệnh qua Caddy tới Next; route /api/* của Next xác minh phiên (GoTrue) rồi chuyển tiếp sang FastAPI.",
            "chi_tiet": t.get("api", ""),
            "nguon": "",
            "den": "xanh",
            "lop": ["caddy", "next", "gotrue"],
            "thoi_gian": "~5–10 ms",
            "nhan_tg": "uoc",
        }
    )
    so = pt["sql"]
    ten_dv = " → ".join(d["ten"].split(" (")[0] for d in t.get("dich_vu", [])[:3])
    if so:
        # Lệnh GHI có vòng lặp (ghi từng dòng hoá đơn…) chỉ vàng; lệnh ĐỌC mới đỏ.
        la_doc = t.get("api", "").startswith("GET")
        den = (
            "do"
            if pt["sql_vong"] >= 3 and la_doc
            else ("vang" if so > 25 or pt["sql_vong"] else "xanh")
        )
        vi_sao = (
            f"Có {pt['sql_vong']} câu SQL nằm trong vòng lặp — số câu tăng theo số dòng (nghi N+1)."
            if pt["sql_vong"]
            else (f"Khoảng {so} câu SQL nối đuôi trên một kết nối." if so > 25 else "")
        )
        tg = max(5, round(so * 0.8 + 4))
        chi = (
            f"~{so} câu SQL"
            + (
                " · trong MỘT giao dịch"
                if pt["giao_dich"]
                else " · không thấy giao dịch"
            )
            + (f" · {pt['sql_vong']} câu trong vòng lặp" if pt["sql_vong"] else "")
        )
    else:
        den, vi_sao, tg, chi = (
            "xanh",
            "",
            5,
            "không đếm được câu SQL (hàm gọi qua lớp khác)",
        )
    buoc.append(
        {
            "y": f"FastAPI nhận ở router, gọi hàm dịch vụ làm luật: {ten_dv}.",
            "chi_tiet": chi,
            "nguon": (t.get("dich_vu") or [{}])[0].get("nguon", "")
            or t.get("router", ""),
            "den": den,
            "vi_sao_den": vi_sao,
            "lop": ["api", "postgres"],
            "thoi_gian": f"~{tg} ms",
            "nhan_tg": "uoc",
        }
    )
    if pt["khoa"]:
        buoc.append(
            {
                "y": "Chống làm trùng / hai người cùng bấm: "
                + "; ".join(sorted(pt["khoa"]))
                + ".",
                "chi_tiet": "ép ở Postgres",
                "nguon": "",
                "den": "xanh",
                "lop": ["postgres"],
                "thoi_gian": "",
                "nhan_tg": "uoc",
            }
        )
    if ghi_khai:
        co_trg = [b for b in ghi_khai if b in trig]
        buoc.append(
            {
                "y": "Ghi vào sổ dữ liệu: "
                + "; ".join(f"{b} ({nghia.get(b, '…')})" for b in ghi_khai[:5])
                + ".",
                "chi_tiet": (
                    f"{len(co_trg)} bảng có trigger báo tin: {gon(co_trg)}"
                    if co_trg
                    else "không bảng nào có trigger báo tin"
                ),
                "nguon": "",
                "den": "xanh",
                "lop": ["postgres"],
                "thoi_gian": "lúc COMMIT",
                "nhan_tg": "uoc",
            }
        )
    sk, _vet = ten_su_kien(t.get("su_kien", []))
    cons: list[str] = []
    for s in sk:
        cons += [c for c in ctx["cat"].get(s, {}).get("consumers", []) if c not in cons]
    if cons:
        ten_c = [ctx["consumer_viet"].get(c, {}).get("ten", c) for c in cons]
        buoc.append(
            {
                "y": f"Sổ sự kiện ghi {gon(sk, 3)}; worker su-kien (vòng nghỉ {ctx['nghi']} giây) giao cho {len(cons)} bên nhận: {gon(ten_c)}.",
                "chi_tiet": "mỗi bên nhận một giao dịch riêng → mỗi bên bắn tin riêng",
                "nguon": ctx["cat"].get(sk[0], {}).get("nguon", "") if sk else "",
                "den": "vang",
                "vi_sao_den": f"Chậm tới {ctx['nghi']} giây mỗi vòng; bên nhận ghi tiếp sinh thêm đợt tin (~3 đợt cách ~1 giây).",
                "lop": ["su-kien", "postgres"],
                "thoi_gian": "0–1 giây / đợt",
                "nhan_tg": "uoc",
            }
        )
    elif sk:
        buoc.append(
            {
                "y": f"Ghi sổ sự kiện {gon(sk, 3)} — không bên nhận nào chạy tiếp.",
                "chi_tiet": "chỉ để lại vết",
                "nguon": "",
                "den": "xanh",
                "lop": ["postgres"],
                "thoi_gian": "",
                "nhan_tg": "uoc",
            }
        )
    ban_tin = [b for b in ghi_khai if b in trig]
    if ban_tin:
        man = t.get("man_tu_cap_nhat", [])
        thuong = [b for b in ban_tin if b in live]
        den = "vang" if thuong else "xanh"
        buoc.append(
            {
                "y": "Trigger notify_row_change → pg_notify → bộ phát SSE đẩy tin “bảng vừa đổi” xuống mọi tab của phòng khám."
                + (f" Màn tự cập nhật: {gon(man, 5)}." if man else ""),
                "chi_tiet": (
                    f"{len(thuong)} bảng nằm trong LIVE_TABLES ⇒ mọi tab “màn thường” dựng lại cả trang (2 GoTrue + 6–8 API mỗi lần)"
                    if thuong
                    else "chỉ màn nghe đúng bảng mới tải lại"
                ),
                "nguon": ctx["live_nguon"],
                "den": den,
                "vi_sao_den": "Đo prod: mỗi lần ghi kéo 7–10 lần dựng lại trang ở mọi tab."
                if thuong
                else "",
                "lop": ["sse", "next", "trinh-duyet"],
                "thoi_gian": "~0,6–1 giây (gộp tin)",
                "nhan_tg": "uoc",
            }
        )
    sau = t.get("sau_khi_ghi", "")
    if sau:
        cho = bool(re.search(r"\bawait\b", sau)) and not sau.lower().startswith(
            "không await"
        )
        buoc.append(
            {
                "y": ("Nút chờ tải lại xong mới nhả: " if cho else "Sau khi ghi: ")
                + sau,
                "chi_tiet": "",
                "nguon": "",
                "den": "do" if cho and "tai()" in sau else ("vang" if cho else "xanh"),
                "vi_sao_den": "Người bấm chờ cả lượt tải bảng dù dữ liệu đã ghi xong."
                if cho
                else "",
                "lop": ["trinh-duyet"],
                "thoi_gian": "",
                "nhan_tg": "uoc",
            }
        )
    return buoc, pt


# ── Ráp ─────────────────────────────────────────────────────────────────────


def sinh() -> tuple[dict, list[str]]:
    vt = json.loads(doc(VIET_TAY))
    canh: list[str] = []
    bang_that, ghi_chu = doc_bang_that()
    trigger = doc_trigger()
    live, live_nguon = doc_live_tables()
    mau_tu_tai, bang_layout, tu_tai_nguon = doc_man_tu_tai()
    nghe = doc_nghe_bang()
    cat = doc_catalogue()
    CATALOGUE.update(cat)
    MA_NHAT_KY.update(ma_nhat_ky())
    consumer = doc_consumer(bang_that)
    cau_hinh = doc_cau_hinh()
    nghia = dict(vt.get("nghia_bang", {}))
    ctx = {
        "ast": KhoAst(),
        "bang_that": bang_that,
        "trigger": trigger,
        "live": set(live),
        "live_nguon": live_nguon,
        "nghia": nghia,
        "cat": cat,
        "consumer_viet": vt.get("consumer", {}),
        "nghi": cau_hinh["sukien_nghi"]["gia_tri"],
    }

    route_khoi: dict[str, str] = {}
    for k in vt["khoi_nghiep_vu"]:
        for r in k["routes"]:
            route_khoi[r] = k["id"]

    def khoi_cua_route(r: str) -> str | None:
        r = r.split("?")[0]
        if r in route_khoi:
            return route_khoi[r]
        tot = None
        for goc, k in route_khoi.items():
            g = re.sub(r"\[[^\]]+\]", "[^/]+", goc)
            if re.fullmatch(g, r) or (goc != "/" and r.startswith(goc + "/")):
                if tot is None or len(goc) > len(tot[0]):
                    tot = (goc, k)
        return tot[1] if tot else None

    # Thao tác
    ops = []
    bang_doc_boi: dict[str, set[str]] = defaultdict(set)
    bang_ghi_boi: dict[str, set[str]] = defaultdict(set)
    for t in vt["thao_tac"]:
        buoc, pt = dung_buoc(t, ctx)
        ghi = ten_bang(t.get("bang_ghi", []))
        ghi += [b for b in t.get("bang_ghi_them", [])]
        docb = sorted(set(t.get("bang_doc", [])) | (pt["doc"] - set(ghi)))
        sk, vet = ten_su_kien(t.get("su_kien", []))
        for s in sk:
            if s not in cat:
                canh.append(f"{t['id']}: sự kiện '{s}' không có trong catalogue")
        cons: list[str] = []
        for s in sk:
            cons += [c for c in cat.get(s, {}).get("consumers", []) if c not in cons]
        qua = [t["khoi"]]
        for r in t.get("man_tu_cap_nhat", []):
            k = khoi_cua_route(r.split(" ")[0])
            if k and k not in qua:
                qua.append(k)
        for c in cons:
            k = vt.get("consumer", {}).get(c, {}).get("khoi")
            if k and k not in qua:
                qua.append(k)
        for k in t.get("khoi_them", []):
            if k not in qua:
                qua.append(k)
        lop = t.get("ha_tang") or (
            ["trinh-duyet", "caddy", "next", "gotrue", "api", "postgres"]
            + (["su-kien"] if cons else [])
            + (["sse"] if any(b in trigger for b in ghi) else [])
        )
        day_ht = t.get("day_ha_tang") or (
            [
                ["trinh-duyet", "caddy", "goi"],
                ["caddy", "next", "goi"],
                ["next", "gotrue", "goi"],
                ["next", "api", "goi"],
                ["api", "postgres", "bang"],
            ]
            + (
                [["postgres", "su-kien", "su-kien"], ["su-kien", "postgres", "bang"]]
                if cons
                else []
            )
            + (
                [
                    ["postgres", "sse", "su-kien"],
                    ["sse", "next", "su-kien"],
                    ["next", "trinh-duyet", "su-kien"],
                ]
                if any(b in trigger for b in ghi)
                else []
            )
        )
        day_nv = []
        for r in t.get("man_tu_cap_nhat", []):
            k = khoi_cua_route(r.split(" ")[0])
            if k and k != t["khoi"]:
                day_nv.append([t["khoi"], k, "bang"])
        for c in cons:
            k = vt.get("consumer", {}).get(c, {}).get("khoi")
            if k and k != t["khoi"]:
                day_nv.append([t["khoi"], k, "su-kien"])
        for d in t.get("day_them", []):
            day_nv.append(d)
        seen = set()
        day_nv = [
            d for d in day_nv if not (tuple(d[:2]) in seen or seen.add(tuple(d[:2])))
        ]
        for b in ghi:
            bang_ghi_boi[b].add(t["id"])
        for b in docb:
            bang_doc_boi[b].add(t["id"])
        tong = t.get("tong_thoi_gian")
        if not tong and not pt["sql"]:
            tong = {"y": "xem thời gian từng bước", "nhan": "uoc"}
        elif not tong:
            tong = {
                "y": f"~{max(10, round(pt['sql'] * 0.8 + 12))} ms phía máy chủ cho lệnh ghi"
                + (" + 0–3 giây cho chuỗi sự kiện" if cons else ""),
                "nhan": "uoc",
            }
        ops.append(
            {
                "id": t["id"],
                "ten": t["ten"],
                "khoi": t["khoi"],
                "ai": t.get("ai", ""),
                "man": t.get("man", ""),
                "man_ten": t.get("man_ten", ""),
                "nut": t.get("nut", ""),
                "nut_nguon": t.get("nut_nguon", ""),
                "api": t.get("api", ""),
                "router": t.get("router", ""),
                "dich_vu": t.get("dich_vu", []),
                "bang_ghi": ghi,
                "bang_doc": docb,
                "su_kien": sk,
                "nhat_ky": vet,
                "consumers": cons,
                "giao_dich": t.get("giao_dich")
                or (
                    "có — một giao dịch"
                    if pt["giao_dich"]
                    else ("không thấy trong code đọc được" if pt["sql"] else "?")
                ),
                "khoa": t.get("khoa")
                or ("; ".join(sorted(pt["khoa"])) or "không thấy khoá riêng"),
                "so_sql": t.get("so_sql") or (f"~{pt['sql']}" if pt["sql"] else "?"),
                "buoc": buoc,
                "qua": qua,
                "ha_tang": lop,
                "day_nv": day_nv,
                "day_ht": day_ht,
                "man_tu_cap_nhat": t.get("man_tu_cap_nhat", []),
                "chuoi": t.get("chuoi", []),
                "tong": tong,
                "noi_bat": t.get("noi_bat", False),
                "nguon_goc": t.get("nguon_goc", "viết mới 23/10, đọc main @ 00bde52"),
                "phat_hien": t.get("phat_hien", []),
            }
        )

    # Bên nhận cũng ghi bảng
    for c, info in consumer.items():
        for b in info["bang_ghi"]:
            bang_ghi_boi[b].add("bên nhận: " + c)

    # Màn nghe bảng
    man_nghe: dict[str, set[str]] = defaultdict(set)
    for n in nghe:
        for b in n["bang"]:
            man_nghe[b].add(n["route"])
    for b in live:
        man_nghe[b].add("mọi màn thường (RealtimeRefresher)")

    # Bảng: chỉ những bảng có người đụng tới / có trigger / có nghĩa viết tay
    quan_tam = (
        set(bang_ghi_boi) | set(bang_doc_boi) | set(trigger) | set(nghia) | set(live)
    )
    bang = {}
    for b in sorted(quan_tam):
        if b not in bang_that and "." not in b:
            continue
        ghi_ops = sorted(bang_ghi_boi.get(b, ()))
        bang[b] = {
            "nghia": nghia.get(b) or "",
            "ghi_chu": ghi_chu.get(b, ""),
            "trigger": trigger.get(b, ""),
            "live": b in live,
            "man_nghe": sorted(man_nghe.get(b, ())),
            "ghi_boi": ghi_ops,
            "doc_boi": sorted(bang_doc_boi.get(b, ())),
        }
        nghe_ma_khong = [r for r in man_nghe.get(b, ()) if not r.startswith("mọi")]
        if nghe_ma_khong and not trigger.get(b):
            bang[b]["canh"] = (
                "Có màn nghe bảng này nhưng bảng KHÔNG có trigger báo tin — nghe vô ích."
            )

    # Chủ bảng theo khối: khối có nhiều thao tác ghi nhất
    chu: dict[str, str] = {}
    for b, ids in bang_ghi_boi.items():
        dem: dict[str, int] = defaultdict(int)
        for i in ids:
            if i.startswith("bên nhận: "):
                k = vt.get("consumer", {}).get(i[10:], {}).get("khoi")
            else:
                k = next((o["khoi"] for o in ops if o["id"] == i), None)
            if k:
                dem[k] += 1
        if dem:
            chu[b] = max(dem, key=lambda k: (dem[k], k))
    for b, k in vt.get("chu_bang", {}).items():
        chu[b] = k
    for b in bang:
        bang[b]["chu"] = chu.get(b, "")

    su_kien = {k: v for k, v in cat.items()}
    du_lieu = {
        "sinh_luc": vt.get("cap_nhat"),
        "sha": git_sha(),
        "goc_code": vt.get("goc_code", ""),
        "khoi_nghiep_vu": vt["khoi_nghiep_vu"],
        "khoi_ha_tang": vt["khoi_ha_tang"],
        "day_ha_tang": vt["day_ha_tang"],
        "consumer": {
            c: {**vt.get("consumer", {}).get(c, {}), **consumer.get(c, {})}
            for c in sorted(set(consumer) | set(vt.get("consumer", {})))
        },
        "su_kien": su_kien,
        "bang": bang,
        "thao_tac": ops,
        "cau_hinh": cau_hinh,
        "live": {
            "bang": live,
            "nguon": live_nguon,
            "man_tu_tai": mau_tu_tai,
            "bang_layout": bang_layout,
            "tu_tai_nguon": tu_tai_nguon,
            "nghe": nghe,
        },
        "do_that": vt.get("do_that", []),
        "de_xuat": vt.get("de_xuat", []),
        "tai": vt.get("tai", {}),
        "hang_doi": vt.get("hang_doi", {}),
        "gioi_thieu": vt.get("gioi_thieu", {}),
        "chua_phu": vt.get("chua_phu", []),
    }

    # Kiểm
    for o in ops:
        if o["khoi"] not in {k["id"] for k in vt["khoi_nghiep_vu"]}:
            canh.append(f"{o['id']}: khối '{o['khoi']}' không có")
        for b in o["bang_ghi"]:
            if b not in bang_that and "." not in b:
                canh.append(f"{o['id']}: bảng ghi '{b}' không có trong migrations")
    ma_dx = {d["id"] for d in data_de_xuat(du_lieu)}
    for o in vt["thao_tac"]:
        for i, b in enumerate(o.get("buoc", [])):
            for d in b.get("de_xuat", []):
                if d not in ma_dx:
                    canh.append(f"{o['id']} bước {i + 1}: đề xuất '{d}' không có")
    for d in du_lieu["de_xuat"]:
        g = d.get("gan", {})
        if g.get("loai") == "thao_tac" and not any(o["id"] == g.get("id") for o in ops):
            canh.append(f"đề xuất {d['id']}: gắn vào thao tác lạ '{g.get('id')}'")
    for ma, ch in cau_hinh.items():
        if ch["gia_tri"] == "?":
            canh.append(f"cấu hình '{ma}': không đọc được từ {ch['nguon']}")
    canh += kiem_tep_dong(du_lieu)
    canh += kiem_ten_ham(ops)
    return du_lieu, canh


def data_de_xuat(d: dict) -> list[dict]:
    return d.get("de_xuat", [])


def kiem_tep_dong(du_lieu: dict) -> list[str]:
    """Mọi `tệp:dòng` trong dữ liệu phải trỏ vào tệp có thật và dòng có thật."""
    loi: list[str] = []
    so_dong: dict[Path, int] = {}
    txt = json.dumps(du_lieu, ensure_ascii=False)
    for m in RE_TEP_DONG.finditer(txt):
        p = GOC / m.group(1)
        n = int(m.group(2))
        if p not in so_dong:
            so_dong[p] = doc(p).count("\n") + 1 if p.exists() else 0
        if so_dong[p] == 0:
            loi.append(f"tệp không có: {m.group(1)}")
        elif n > so_dong[p]:
            loi.append(f"dòng quá cuối tệp: {m.group(0)} (tệp có {so_dong[p]} dòng)")
    return sorted(set(loi))


def kiem_ten_ham(ops: list[dict]) -> list[str]:
    """Router `tệp:dòng ten` và hàm dịch vụ `Lop.ham` phải nằm trong ±3 dòng quanh dòng ghi."""
    loi: list[str] = []
    for o in ops:
        cap = [(o.get("router", ""), (o.get("router", "").split() or [""])[-1])]
        cap += [
            (d.get("nguon", ""), d.get("ten", "").split(" (")[0].split(".")[-1])
            for d in o.get("dich_vu", [])
        ]
        for nguon, ten in cap:
            tn = tach_nguon(nguon)
            if (
                not tn
                or not re.fullmatch(r"[A-Za-z_]\w*", ten or "")
                or not tn[0].suffix == ".py"
            ):
                continue
            dong = doc(tn[0]).splitlines()
            vung = "\n".join(dong[max(0, tn[1] - 4) : tn[1] + 3])
            if ten not in vung:
                loi.append(f"{o['id']}: không thấy '{ten}' quanh {rel(tn[0])}:{tn[1]}")
    return loi


def main(argv: list[str]) -> int:
    du_lieu, canh = sinh()
    goi = json.dumps(du_lieu, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    trang = doc(TRANG)
    if MO not in trang or DONG not in trang:
        print(f"Thiếu dấu {MO} … {DONG} trong {rel(TRANG)}", file=sys.stderr)
        return 1
    dau, _, sau = trang.partition(MO)
    _, _, duoi = sau.partition(DONG)
    moi = f"{dau}{MO}window.LEGO={goi};{DONG}{duoi}"
    tom = (
        f"{len(du_lieu['thao_tac'])} thao tác · {len(du_lieu['khoi_nghiep_vu'])} khối nghiệp vụ · "
        f"{len(du_lieu['khoi_ha_tang'])} khối hạ tầng · {len(du_lieu['bang'])} bảng · "
        f"{len(du_lieu['su_kien'])} sự kiện · {len(du_lieu['de_xuat'])} đề xuất"
    )
    for c in canh:
        print("CẢNH BÁO:", c, file=sys.stderr)
    if "--kiem" in argv:
        # Bỏ sha khi so: commit mới không được làm trang "lệch".
        def bo_sha(s: str) -> str:
            return re.sub(r'"sha":"[^"]*"', '"sha":""', s)

        lech = bo_sha(moi) != bo_sha(trang)
        if lech:
            print(
                f"{rel(TRANG)} lệch dữ liệu — chạy: python3 scripts/lego-data.py",
                file=sys.stderr,
            )
        print(tom)
        return 1 if (canh or lech) else 0
    TRANG.write_text(moi, encoding="utf-8")
    print(f"Ghi {rel(TRANG)} ({len(moi.encode()) // 1024} KB): {tom}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
