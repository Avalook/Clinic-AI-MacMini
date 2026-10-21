#!/usr/bin/env python3
"""Chụp cấu trúc database → docs/ban-do/db.json cho bản đồ web (lớp database).

Đọc từ khuôn test `khuon` (= mọi migration của main) trong container `chung_test_db`:
nhân bản ra DB tạm, đọc, xoá — đúng cách `scripts/test-nhanh.sh` làm, CHỈ ĐỌC, không
đụng prod. Ghi: bảng (cột, khoá chính, RLS), khoá ngoại, trigger, hàm SQL (bảng nó
ghi + migration định nghĩa nó), view. Không ghi thân hàm, không ghi dữ liệu.

    python3 scripts/ban-do-db.py                    # chụp lại docs/ban-do/db.json
    python3 scripts/ban-do-db.py --so-dong tep.json # kèm số dòng prod (JSON bảng→số,
                                                    # lấy chỉ-đọc từ pg_stat_user_tables)

Khuôn thiếu migration của main → chạy trước: scripts/test-nhanh.sh --cap-nhat-khuon
"""

# ruff: noqa: E501 — câu SQL và chuỗi tiếng Việt, cắt dòng chỉ làm khó đọc.
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
MIGRATIONS = GOC / "supabase" / "migrations"
DAU_RA = GOC / "docs" / "ban-do" / "db.json"
CONTAINER = os.environ.get("TEST_NHANH_CONTAINER", "chung_test_db")
KHUON = "khuon"

SQL = r"""
SELECT json_build_object(
  'bang', (SELECT json_agg(json_build_object(
      'ten', c.relname, 'rls', c.relrowsecurity,
      'cot', (SELECT json_agg(json_build_object('ten', a.attname,
                 'kieu', format_type(a.atttypid, a.atttypmod), 'bat_buoc', a.attnotnull)
                 ORDER BY a.attnum)
               FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped),
      'khoa_chinh', (SELECT json_agg(a.attname) FROM pg_index i
                       JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                      WHERE i.indrelid = c.oid AND i.indisprimary)) ORDER BY c.relname)
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')),
  'lien_ket', (SELECT json_agg(json_build_object(
      'tu', cl.relname,
      'tu_cot', (SELECT json_agg(a.attname ORDER BY k.o) FROM unnest(con.conkey) WITH ORDINALITY k(n, o)
                   JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.n),
      'den', cf.relname) ORDER BY cl.relname, con.conname)
    FROM pg_constraint con JOIN pg_class cl ON cl.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = cl.relnamespace JOIN pg_class cf ON cf.oid = con.confrelid
    WHERE con.contype = 'f' AND n.nspname = 'public'),
  'trigger', (SELECT json_agg(json_build_object('bang', c.relname, 'ten', t.tgname,
      'ham', p.proname, 'dinh_nghia', pg_get_triggerdef(t.oid)) ORDER BY c.relname, t.tgname)
    FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_proc p ON p.oid = t.tgfoid WHERE NOT t.tgisinternal AND n.nspname = 'public'),
  'ham', (SELECT json_agg(json_build_object('ten', p.proname,
      'tham_so', pg_get_function_identity_arguments(p.oid), 'than', p.prosrc) ORDER BY p.proname)
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace JOIN pg_language l ON l.oid = p.prolang
    WHERE n.nspname = 'public' AND l.lanname IN ('plpgsql', 'sql') AND p.prokind = 'f'),
  'view', (SELECT json_agg(json_build_object('ten', c.relname, 'dinh_nghia', pg_get_viewdef(c.oid, true))
      ORDER BY c.relname)
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('v', 'm')),
  'so_migration', (SELECT count(*) FROM supabase_migrations.schema_migrations),
  'migration_moi_nhat', (SELECT max(version) FROM supabase_migrations.schema_migrations)
)
"""

GHI = re.compile(
    r"\b(?:INSERT\s+INTO|DELETE\s+FROM|(?<!DO\s)UPDATE)\s+(?:public\.)?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
KHONG_PHAI_BANG = {
    "set",
    "only",
    "public",
    "if",
    "not",
    "loop",
    "sau",
    "blocked",
    "into",
    "from",
}
DOC = re.compile(r"\b(?:FROM|JOIN)\s+(?:public\.)?([a-z_][a-z0-9_]*)", re.IGNORECASE)


def psql(db: str, lenh: str) -> str:
    r = subprocess.run(
        [
            "docker",
            "exec",
            "-e",
            "PGOPTIONS=--client-min-messages=warning",
            CONTAINER,
            "psql",
            "-U",
            "postgres",
            "-d",
            db,
            "-v",
            "ON_ERROR_STOP=1",
            "-qtA",
            "-c",
            lenh,
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    if r.returncode:
        raise SystemExit(f"psql lỗi ({db}): {r.stderr.strip()}")
    return r.stdout


def noi_dinh_nghia() -> dict[str, tuple[str, int]]:
    """Hàm SQL → (migration CUỐI định nghĩa nó, dòng) — bản đang chạy là bản cuối."""
    mau = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?\"?([a-z_][a-z0-9_]*)",
        re.I,
    )
    ra: dict[str, tuple[str, int]] = {}
    for tep in sorted(MIGRATIONS.glob("*.sql")):
        for i, dong in enumerate(tep.read_text(encoding="utf-8").splitlines(), 1):
            m = mau.search(dong)
            if m:
                ra[m.group(1).lower()] = (tep.relative_to(GOC).as_posix(), i)
    return ra


def main(argv: list[str]) -> int:
    so_tep = len(list(MIGRATIONS.glob("*.sql")))
    tam = f"tam_ban_do_db_{os.getpid()}"
    for _ in range(10):
        try:
            psql("template1", f'CREATE DATABASE "{tam}" TEMPLATE "{KHUON}"')
            break
        except SystemExit:
            time.sleep(1)
    else:
        raise SystemExit(
            "Không nhân bản được khuôn — container chung_test_db có chạy không?"
        )
    try:
        d = json.loads(
            psql(tam, "SET default_transaction_read_only = on;" + SQL)
            .strip()
            .splitlines()[-1]
        )
    finally:
        psql("template1", f'DROP DATABASE IF EXISTS "{tam}" WITH (FORCE)')
    if d["so_migration"] < so_tep:
        print(
            f"⚠ khuôn có {d['so_migration']} migration, repo có {so_tep} — chạy"
            " scripts/test-nhanh.sh --cap-nhat-khuon rồi chụp lại.",
            file=sys.stderr,
        )

    noi = noi_dinh_nghia()
    for h in d["ham"]:
        than = h.pop("than") or ""
        h["ghi_bang"] = sorted({b.lower() for b in GHI.findall(than)} - KHONG_PHAI_BANG)
        tep, dong = noi.get(h["ten"].lower(), ("", 0))
        h["dinh_nghia"] = {"tep": tep, "dong": dong}
    for v in d["view"]:
        v["doc_bang"] = sorted(
            {b.lower() for b in DOC.findall(v.pop("dinh_nghia") or "")}
        )
    for t in d["trigger"]:
        m = re.search(r"(BEFORE|AFTER|INSTEAD OF)\s+(.+?)\s+ON\s", t.pop("dinh_nghia"))
        t["khi"] = f"{m.group(1)} {m.group(2)}" if m else ""
    d["lay_luc"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    if "--so-dong" in argv:
        tep_so = Path(argv[argv.index("--so-dong") + 1])
        d["so_dong_prod"] = json.loads(tep_so.read_text(encoding="utf-8"))
        d["so_dong_luc"] = datetime.fromtimestamp(tep_so.stat().st_mtime).strftime(
            "%d/%m/%Y"
        )
    DAU_RA.parent.mkdir(parents=True, exist_ok=True)
    DAU_RA.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
    print(
        f"Đã ghi {DAU_RA.relative_to(GOC)}: {len(d['bang'])} bảng · {len(d['lien_ket'])} liên kết"
        f" · {len(d['trigger'])} trigger · {len(d['ham'])} hàm · {len(d['view'])} view"
        f" · migration {d['so_migration']} ({d['migration_moi_nhat']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
