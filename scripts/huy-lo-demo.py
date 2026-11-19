#!/usr/bin/env python3
"""Huỷ các lô MẪU `DEMO1709-*` còn tồn — Tuyền duyệt 16/11/2026.

Lô mẫu 17/09 (nhân bản 08/10) không có thật, nhưng còn tồn: Hào Nam (chuyển từ
quầy về kho trưa 16/11) và Kim Ngưu. Có "thu xong là giao" (#641, FEFO) thì bán
ra sẽ trừ vào lô giả trước, lô thật không giảm — phải đưa các lô này về 0 trước.

Đi qua đúng thao tác "Huỷ thuốc" của màn (`PharmacyService.huy`: dòng DISCARD có
lý do, không xoá lịch sử, không đụng tiền), đứng tên đúng cơ sở của lô. `huy_lo`
(huỷ lô HẾT HẠN) không dùng được vì lô mẫu hạn 2027. Hoàn tác: cộng lại đúng số
bằng `PharmacyService.dieu_chinh` (ADJUST có lý do). Hai lệnh đều có khoá gửi trùng
cố định theo lô → chạy lại không ghi thêm.

    docker cp scripts/huy-lo-demo.py <api>:/tmp/hd.py
    docker exec <api> python /tmp/hd.py                                  # thử khô
    docker exec <api> python /tmp/hd.py --luu=/tmp/huy-lo-demo-1611.jsonl --that
    docker exec <api> python /tmp/hd.py --hoan-tac=/tmp/huy-lo-demo-1611.jsonl

`--chi-lo=<id,id>` chỉ dùng trong test.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
import uuid
from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

DOT = "[HUY-LO-DEMO-1611]"
LY_DO = f"Lô mẫu DEMO17/09 nhân bản 08/10 — không có thật (Tuyền 16/11) {DOT}"
LY_DO_HOAN = f"Hoàn tác huỷ lô mẫu DEMO {DOT}"
#: Kho thật nhập prod trưa 15/11 (giờ VN) — lần giao vào lô mẫu sau mốc này là
#: bán thật bị trừ nhầm vào lô giả: nhắc kiểm kho chỉnh lô thật.
MOC_KHO_THAT = datetime.fromisoformat("2026-11-15T12:00:00+07:00")

UNG_VIEN = """
SELECT b.id::text, b.location_id::text AS loc, l.name AS co_so, b.noi_chua,
       b.batch_code, b.quantity_on_hand AS ton,
       public.drug_batch_kha_dung(b.clinic_id, b.id) AS kha_dung,
       (SELECT count(*) FROM public.inventory_txn t
         WHERE t.drug_batch_id = b.id) AS so_dong_so
  FROM public.drug_batch b JOIN public.clinic_location l ON l.id = b.location_id
 WHERE b.clinic_id = $1::uuid AND b.batch_code LIKE 'DEMO1709-%'
   AND b.quantity_on_hand <> 0
   AND ($2::uuid[] IS NULL OR b.id = ANY($2::uuid[]))
 ORDER BY l.name, b.noi_chua, b.batch_code
"""

GIAO_NHAM = """
SELECT coalesce(c.name_base, c.name_raw, '?') AS ten, b.batch_code,
       -t.quantity AS so, t.performed_at, s.full_name AS nguoi
  FROM public.inventory_txn t
  JOIN public.drug_batch b ON b.id = t.drug_batch_id
  LEFT JOIN public.drug_catalog c ON c.id = b.drug_catalog_id
  LEFT JOIN public.staff s ON s.id = t.performed_by_staff_id
 WHERE t.clinic_id = $1::uuid AND b.batch_code LIKE 'DEMO1709-%'
   AND t.txn_type = 'DISPENSE' AND t.performed_at >= $2::timestamptz
   AND NOT EXISTS (SELECT 1 FROM public.inventory_txn x WHERE x.reverses_txn_id = t.id)
 ORDER BY t.performed_at
"""


def _tham_so(ten: str) -> str:
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"{ten}=")), "")


def _khoa(*phan: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "huy-lo-demo-1611/" + "/".join(phan)))


async def _nguoi(pool: asyncpg.Pool) -> Any:
    from clinicai.api.identity import ClinicRole, StaffIdentity

    ql = await pool.fetchrow(
        """
        SELECT s.id::text AS id, s.auth_user_id::text AS au, s.full_name,
               m.clinic_id::text AS cid, s.primary_location_id::text AS lid
          FROM staff s JOIN clinic_membership m ON m.staff_id = s.id
           AND m.is_active
         WHERE m.role = 'MANAGEMENT' AND s.is_active
         ORDER BY (s.full_name = 'Quản lý hệ thống') DESC LIMIT 1
        """
    )
    if ql is None:
        raise SystemExit("✗ Không có tài khoản Quản lý đang hoạt động để đứng tên.")
    return StaffIdentity(
        staff_id=ql["id"],
        auth_user_id=ql["au"] or "",
        full_name=ql["full_name"],
        department="MANAGEMENT",
        role=ClinicRole.MANAGEMENT,
        clinic_id=ql["cid"],
        location_id=ql["lid"],
        location_name="",
    )


async def _hoan_tac(pool: asyncpg.Pool, ident: Any, tep: str) -> int:
    from clinicai.services.pharmacy_service import PharmacyService

    svc = PharmacyService(pool)
    with open(tep, encoding="utf-8") as f:
        ds = [json.loads(x) for x in f if x.strip()]
    for d in ds:
        await svc.dieu_chinh(
            identity=dataclasses.replace(ident, location_id=d["loc"]),
            drug_batch_id=d["id"],
            so_luong=d["so"],
            ly_do=LY_DO_HOAN,
            idempotency_key=_khoa("hoan", d["id"]),
        )
    print(f"  ✓ đã cộng lại {len(ds)} lô mẫu (ADJUST, lý do có mã {DOT})")
    return 0


async def main() -> int:
    from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
    from clinicai.services.pharmacy_service import PharmacyService

    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn)
    try:
        ident = await _nguoi(pool)
        if tep := _tham_so("--hoan-tac"):
            return await _hoan_tac(pool, ident, tep)
        chi = _tham_so("--chi-lo")
        ds = await pool.fetch(
            UNG_VIEN, ident.clinic_id, chi.split(",") if chi else None
        )
        che_do = "LÀM THẬT" if that else "THỬ KHÔ"
        print(f"{che_do} · huỷ lô mẫu DEMO1709-* còn tồn")
        nhom: Counter[tuple[str, str]] = Counter()
        ton: dict[tuple[str, str], Decimal] = {}
        am, giu = [], []
        for r in ds:
            k = (r["co_so"], r["noi_chua"])
            nhom[k] += 1
            ton[k] = ton.get(k, Decimal(0)) + Decimal(str(r["ton"]))
            if r["ton"] < 0:
                am.append(r["batch_code"])
            elif Decimal(str(r["kha_dung"] or 0)) < Decimal(str(r["ton"])):
                giu.append(r["batch_code"])
        for (cs, noi), n in sorted(nhom.items()):
            print(f"    {cs} · {noi}: {n} lô, tồn {ton[(cs, noi)].normalize():f}")
        if am:
            print(f"  ⚠ lô tồn ÂM (không huỷ được, để kiểm kho): {am}")
        if giu:
            print(f"  ⚠ lô đang giữ cho khách chưa giao (sẽ bị từ chối): {giu}")
        nham = await pool.fetch(GIAO_NHAM, ident.clinic_id, MOC_KHO_THAT)
        for g in nham:
            print(
                f"  ⚠ nhắc kiểm kho: {g['ten']} giao {g['so'].normalize():f} từ lô mẫu"
                f" {g['batch_code']} lúc {g['performed_at']:%d/%m %H:%M}"
                f" ({g['nguoi'] or '?'}) — lô thật đang dư đúng số này"
            )
        if not that:
            print("\nĐây là THỬ KHÔ, chưa ghi gì. Thêm --luu=<tệp> --that để huỷ.")
            return 0
        tep = _tham_so("--luu")
        if not tep:
            raise SystemExit("✗ Làm thật phải có --luu=<tệp> để hoàn tác được.")
        svc = PharmacyService(pool)
        xong = 0
        bo: Counter[str] = Counter()
        with open(tep, "a", encoding="utf-8") as f:
            for r in ds:
                if r["ton"] <= 0:
                    continue
                try:
                    # Khoá theo lô + số dòng sổ của lô: chạy lại lúc chưa đổi gì →
                    # cùng khoá, không huỷ hai lần; sau hoàn tác (sổ có thêm dòng)
                    # → khoá mới, huỷ thật. Khoá chỉ theo lô thì lần huỷ lại nhận
                    # "đã làm" mà không ghi gì (staging 20/11: 80 lô Kim Ngưu).
                    await svc.huy(
                        identity=dataclasses.replace(ident, location_id=r["loc"]),
                        drug_batch_id=r["id"],
                        so_luong=str(r["ton"]),
                        ly_do=LY_DO,
                        idempotency_key=_khoa("huy", r["id"], str(r["so_dong_so"])),
                    )
                except (ConflictError, ValidationError, NotFoundError) as exc:
                    bo[str(exc)[:110]] += 1
                    continue
                if await pool.fetchval(
                    "SELECT quantity_on_hand FROM public.drug_batch"
                    " WHERE id = $1::uuid",
                    r["id"],
                ):
                    bo["lệnh huỷ trả về nhưng lô vẫn còn tồn"] += 1
                    continue
                f.write(
                    json.dumps({"id": r["id"], "loc": r["loc"], "so": str(r["ton"])})
                    + "\n"
                )
                f.flush()
                xong += 1
        print(f"  ✓ đã huỷ {xong} lô (bản ghi hoàn tác: {tep})")
        for ly, n in bo.most_common():
            print(f"  ↷ bỏ qua {n} lô: {ly}")
        con = await pool.fetchval(
            "SELECT count(*) FROM public.drug_batch WHERE clinic_id = $1::uuid"
            " AND batch_code LIKE 'DEMO1709-%' AND quantity_on_hand > 0"
            " AND ($2::uuid[] IS NULL OR id = ANY($2::uuid[]))",
            ident.clinic_id,
            chi.split(",") if chi else None,
        )
        if con:
            print(f"  ✗ còn {con} lô mẫu tồn > 0 — CHƯA xong, xem các dòng ↷ ở trên")
            return 1
        print("  ✓ kiểm lại: mọi lô mẫu tồn = 0")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
