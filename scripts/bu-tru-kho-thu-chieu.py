#!/usr/bin/env python3
"""Bù trừ kho cho các lần thu tiền thuốc TRƯỚC khi có "thu xong là giao" — 16/11/2026.

Kho thuốc thật nhập vào prod từ 14/11 13:56 (phiếu nhập thật đầu tiên PN-HN-0001,
soát 19/11 — không phải 15/11 như bản đầu). Tuyền 19/11: LƯU script, CHƯA chạy
`--that` khi chưa bảo. Bản "thu xong là giao" (#641: quầy
trước → thiếu thì kho → cả hai thiếu thì sổ đối chiếu) lên prod muộn hơn, nên các
lần thu trong khoảng đó chưa trừ kho (trừ dòng nhân viên đã bấm Giao tay).

Script chạy SAU KHI #641 đã lên prod, gọi ĐÚNG hàm của luật mới
(`tu_giao_khi_thu`) cho từng lần thu tiền thuốc PAID có paid_at trong
[--tu, --den): chỉ giao phần còn lại (số đã thu − số đã giao), nên dòng đã giao
tay không bị trừ hai lần; lần thu đã hoàn tác (VOIDED) / chờ xác minh bỏ qua.

* Thử khô (mặc định): chạy THẬT từng lần thu trong giao dịch rồi CUỘN LẠI — số in
  ra đúng là số sẽ ghi (lấy ở quầy / ở kho / vào sổ đối chiếu, theo thuốc).
* `--that --luu=<tệp>`: ghi; mỗi lần thu một giao dịch; tệp JSONL ghi các dòng sổ
  kho / sổ đối chiếu vừa sinh để hoàn tác đúng chỗ.
* `--hoan-tac=<tệp>`: đảo đúng các lần giao trong tệp (DISPENSE_REVERSAL về đúng
  lô), huỷ dòng đối chiếu, trả số đã giao của dòng đơn.

    docker cp scripts/bu-tru-kho-thu-chieu.py <api>:/tmp/bu.py
    docker exec <api> python /tmp/bu.py --tu=2026-11-14T13:56+07:00          # thử khô
    docker exec <api> python /tmp/bu.py --tu=2026-11-14T13:56+07:00 \
        --luu=/tmp/bu-tru-kho-1611.jsonl --that
    docker exec <api> python /tmp/bu.py --hoan-tac=/tmp/bu-tru-kho-1611.jsonl

`--den` mặc định = bây giờ. `--chi-luot=<id,id>` chỉ dùng trong test.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

DOT = "[BU-TRU-KHO-1611]"
LY_DO_HOAN_TAC = f"Hoàn tác bù trừ kho {DOT}"

UNG_VIEN = """
SELECT c.payment_cycle_id::text AS cycle, c.visit_id::text AS visit
  FROM public.payment_cycle c
 WHERE c.clinic_id = $1::uuid AND c.kind = 'thuoc' AND c.status = 'PAID'
   AND c.paid_at >= $2::timestamptz AND c.paid_at < $3::timestamptz
   AND ($4::uuid[] IS NULL OR c.visit_id = ANY($4::uuid[]))
   AND EXISTS (
       SELECT 1 FROM public.payment_bill_line b
         JOIN public.prescription r
           ON r.id::text = b.source_id AND r.clinic_id = b.clinic_id
        WHERE b.clinic_id = c.clinic_id AND b.payment_cycle_id = c.payment_cycle_id
          AND b.kind = 'thuoc' AND b.source_type = 'prescription'
          AND r.closed_at IS NULL AND r.removed_at IS NULL
          AND b.quantity > coalesce(r.dispensed_qty, 0))
 ORDER BY c.paid_at, c.payment_cycle_id
"""

_RX_CUA_LAN = """
SELECT r.id::text FROM public.payment_bill_line b
  JOIN public.prescription r ON r.id::text = b.source_id AND r.clinic_id = b.clinic_id
 WHERE b.clinic_id = $1::uuid AND b.payment_cycle_id = $2::uuid
   AND b.kind = 'thuoc' AND b.source_type = 'prescription' AND r.removed_at IS NULL
"""


class _CuonLaiError(Exception):
    """Thử khô: cuộn giao dịch sau khi đã đo."""


def _tham_so(ten: str) -> str:
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"{ten}=")), "")


def _gio(chu: str, ten: str) -> datetime:
    t = datetime.fromisoformat(chu)
    if t.tzinfo is None:
        raise SystemExit(f"✗ {ten} phải có múi giờ, vd 2026-11-15T12:00+07:00")
    return t


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


async def _vet(conn: asyncpg.Connection, cid: str, rx: list[str]) -> tuple[set, set]:
    txn = {
        r["id"]
        for r in await conn.fetch(
            "SELECT id::text FROM public.inventory_txn WHERE clinic_id = $1::uuid"
            " AND txn_type = 'DISPENSE' AND ref_type = 'prescription'"
            " AND ref_id = ANY($2::uuid[])",
            cid,
            rx,
        )
    }
    cho = {
        r["id"]
        for r in await conn.fetch(
            "SELECT id::text FROM public.thuoc_giao_chua_gan_lo"
            " WHERE clinic_id = $1::uuid AND prescription_id = ANY($2::uuid[])",
            cid,
            rx,
        )
    }
    return txn, cho


async def _bu_mot_lan(
    pool: asyncpg.Pool, ident: Any, lan: Any, that: bool, tong: dict
) -> dict | None:
    from clinicai.services.tu_giao_khi_thu import tu_giao_khi_thu

    cid = ident.clinic_id
    ban: dict | None = None
    try:
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "SELECT 1 FROM public.visit WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid FOR UPDATE",
                cid,
                lan["visit"],
            )
            rx = [r["id"] for r in await conn.fetch(_RX_CUA_LAN, cid, lan["cycle"])]
            txn0, cho0 = await _vet(conn, cid, rx)
            kq = await tu_giao_khi_thu(conn, identity=ident, cycle_id=lan["cycle"])
            txn1, cho1 = await _vet(conn, cid, rx)
            moi_txn, moi_cho = sorted(txn1 - txn0), sorted(cho1 - cho0)
            for r in await conn.fetch(
                "SELECT b.noi_chua, coalesce(c.name_base, c.name_raw, '?') AS ten,"
                " b.batch_code, -t.quantity AS sl FROM public.inventory_txn t"
                " JOIN public.drug_batch b ON b.id = t.drug_batch_id"
                " LEFT JOIN public.drug_catalog c ON c.id = b.drug_catalog_id"
                " WHERE t.id = ANY($1::uuid[])",
                moi_txn,
            ):
                noi = f"{r['noi_chua']} lô {r['batch_code']}"
                tong[(r["ten"], noi)] += Decimal(str(r["sl"]))
                if str(r["batch_code"]).startswith("DEMO"):
                    tong[("_demo", "")] += 1
            for r in await conn.fetch(
                "SELECT coalesce(c.name_base, c.name_raw, '?') AS ten, g.so_luong"
                " FROM public.thuoc_giao_chua_gan_lo g"
                " LEFT JOIN public.drug_catalog c ON c.id = g.drug_catalog_id"
                " WHERE g.id = ANY($1::uuid[])",
                moi_cho,
            ):
                tong[(r["ten"], "ĐỐI CHIẾU")] += Decimal(str(r["so_luong"]))
            tong[("_luot", "")] += 1
            tong[("_bo_qua", "")] += len(kq.bo_qua)
            ban = {
                "cycle": lan["cycle"],
                "visit": lan["visit"],
                "txn": moi_txn,
                "cho_gan": moi_cho,
                "bo_qua": kq.bo_qua,
            }
            if not that:
                raise _CuonLaiError
    except _CuonLaiError:
        return None
    return ban


async def _hoan_tac(pool: asyncpg.Pool, ident: Any, tep: str) -> int:
    from clinicai.services.hoan_tac_giao_service import (
        cac_lan_giao,
        ghi_dong_dao,
        giam_da_giao,
        huy_cho_gan_lo,
    )
    from clinicai.services.pharmacy_service import _log

    cid = ident.clinic_id
    with open(tep, encoding="utf-8") as f:
        ds = [json.loads(x) for x in f if x.strip()]
    dao = 0
    for b in ds:
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "SELECT 1 FROM public.visit WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid FOR UPDATE",
                cid,
                b["visit"],
            )
            rx = [r["id"] for r in await conn.fetch(_RX_CUA_LAN, cid, b["cycle"])]
            tra: dict[str, Decimal] = defaultdict(Decimal)
            for lan in await cac_lan_giao(conn, cid, rx):
                if lan.id in b["txn"] and lan.con > 0:
                    await ghi_dong_dao(
                        conn,
                        clinic_id=cid,
                        staff_id=ident.staff_id,
                        lan=lan,
                        ly_do=LY_DO_HOAN_TAC,
                    )
                    tra[lan.prescription_id] += lan.con
                    dao += 1
            for gid in b["cho_gan"]:
                huy = await huy_cho_gan_lo(
                    conn,
                    clinic_id=cid,
                    staff_id=ident.staff_id,
                    ly_do=LY_DO_HOAN_TAC,
                    dong_id=gid,
                )
                for p, so in huy.items():
                    tra[p] += so
            for p, so in tra.items():
                await giam_da_giao(conn, clinic_id=cid, prescription_id=p, so=so)
                await _log(
                    conn,
                    identity=ident,
                    event_type="pharmacy.dispense_undone",
                    aggregate_type="prescription",
                    aggregate_id=p,
                    payload={"dot": DOT, "quantity": str(so)},
                )
    print(f"  ✓ đã hoàn tác {len(ds)} lần thu ({dao} lần giao đảo về đúng lô)")
    return 0


async def main() -> int:
    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn)
    try:
        ident = await _nguoi(pool)
        if tep := _tham_so("--hoan-tac"):
            return await _hoan_tac(pool, ident, tep)
        tu_chu = _tham_so("--tu")
        if not tu_chu:
            raise SystemExit("✗ Thiếu --tu, vd --tu=2026-11-14T13:56+07:00")
        tu = _gio(tu_chu, "--tu")
        den_chu = _tham_so("--den")
        den = _gio(den_chu, "--den") if den_chu else datetime.now().astimezone()
        tep = _tham_so("--luu")
        if that and not tep:
            raise SystemExit("✗ Làm thật phải có --luu=<tệp> để hoàn tác được.")
        chi = _tham_so("--chi-luot")
        ds = await pool.fetch(
            UNG_VIEN, ident.clinic_id, tu, den, chi.split(",") if chi else None
        )
        che_do = "LÀM THẬT" if that else "THỬ KHÔ (chạy rồi cuộn lại)"
        print(f"{che_do} · lần thu PAID từ {tu.isoformat()} tới {den.isoformat()}")
        print(f"  lần thu còn dòng chưa giao: {len(ds)}")
        tong: dict = defaultdict(Decimal)
        f = open(tep, "a", encoding="utf-8") if that else None
        try:
            for lan in ds:
                ban = await _bu_mot_lan(pool, ident, lan, that, tong)
                if f is not None and ban is not None:
                    f.write(json.dumps(ban, ensure_ascii=False) + "\n")
                    f.flush()
        finally:
            if f is not None:
                f.close()
        print(f"  lần thu đã xử lý: {int(tong.pop(('_luot', ''), 0))}")
        bo = int(tong.pop(("_bo_qua", ""), 0))
        print(f"  dòng bị bỏ qua (vẫn còn nút Giao): {bo}")
        demo = int(tong.pop(("_demo", ""), 0))
        print(f"  ⚠ lần trừ vào lô DEMO*: {demo}" if demo else "  lô DEMO*: 0")
        for (ten, noi), sl in sorted(tong.items()):
            print(f"    {ten} · {noi}: {sl.normalize()}")
        if not that:
            print("\nĐây là THỬ KHÔ, đã cuộn lại. Thêm --luu=<tệp> --that để ghi.")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
