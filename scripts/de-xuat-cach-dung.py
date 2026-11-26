#!/usr/bin/env python3
"""ĐỀ XUẤT cách dùng có cấu trúc cho danh mục thuốc — CHỈ ĐỌC (PR E, 26/11/2026).

Đọc câu `cach_dung` của thuốc đang dùng, in bảng đề xuất (kiểu, mỗi lần, số lần,
khoảng, chu kỳ, trong N ngày) + câu máy sẽ sinh, để Tuyền / dược sĩ duyệt rồi khai
ở Kho thuốc › Danh mục › Sửa. KHÔNG ghi gì: giao dịch READ ONLY.

Chạy (DB thử local):
    PYTHONPATH=src DATABASE_URL=postgresql://… \
        .venv/bin/python scripts/de-xuat-cach-dung.py
Thêm `--csv tệp.csv` để ghi bảng ra tệp (mặc định in ra màn).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys

import asyncpg

from clinicai.services.thuoc.cach_dung import cau_cach_dung, doc_ct
from clinicai.services.thuoc.tach_cau import de_xuat

COT = ["thuoc", "don_vi_kho", "cau_goc", "kieu", "moi_lan", "so_lan", "khoang_lan",
       "khoang_so_lan", "chu_ky", "trong_ngay", "cau_may_sinh", "da_khai"]  # fmt: skip


async def chay(dsn: str) -> list[dict[str, str]]:
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction(readonly=True):
            rows = await conn.fetch(
                "SELECT name_raw, don_vi_ban, cach_dung, cach_dung_ct"
                "  FROM public.drug_catalog WHERE is_active ORDER BY name_raw"
            )
    finally:
        await conn.close()
    ra = []
    for r in rows:
        ct = de_xuat(r["cach_dung"])
        ra.append(
            {
                "thuoc": r["name_raw"],
                "don_vi_kho": r["don_vi_ban"] or "",
                "cau_goc": r["cach_dung"] or "",
                "kieu": ct.kieu,
                "moi_lan": "" if ct.moi_lan is None else str(ct.moi_lan),
                "so_lan": "" if ct.so_lan is None else str(ct.so_lan),
                "khoang_lan": "–".join(map(str, ct.khoang_lan or ())),
                "khoang_so_lan": "–".join(map(str, ct.khoang_so_lan or ())),
                "chu_ky": f"{ct.tu_ngay}–{ct.den_ngay}" if ct.kieu == "chu_ky" else "",
                "trong_ngay": str(ct.trong_ngay or ""),
                "cau_may_sinh": cau_cach_dung(ct, r["cach_dung"] or ""),
                "da_khai": "có" if doc_ct(r["cach_dung_ct"]) else "",
            }
        )
    return ra


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", help="ghi bảng ra tệp CSV thay vì in ra màn")
    a = p.parse_args()
    dsn = os.environ.get("DATABASE_URL") or ""
    dsn = dsn.replace("postgresql+asyncpg", "postgresql")
    if not dsn:
        print("Thiếu DATABASE_URL.", file=sys.stderr)
        return 2
    ra = asyncio.run(chay(dsn))
    out = open(a.csv, "w", newline="", encoding="utf-8") if a.csv else sys.stdout
    w = csv.DictWriter(out, fieldnames=COT, delimiter="\t" if not a.csv else ",")
    w.writeheader()
    w.writerows(ra)
    if a.csv:
        out.close()
    dem: dict[str, int] = {}
    for r in ra:
        dem[r["kieu"]] = dem.get(r["kieu"], 0) + 1
    print(f"{len(ra)} thuốc đang dùng — theo kiểu đề xuất: {dem}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
