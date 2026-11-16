#!/usr/bin/env python3
"""Chuyển tồn đang nằm ở QUẦY về KHO cho một cơ sở — 16/11/2026.

Lúc bật tách kho / quầy, mọi lô cũ mặc định ở QUẦY (migration 20261014160000).
Phòng khám bắt đầu dùng thật cả kho và quầy: hàng thực tế nằm ở kho. Script lập
MỘT phiếu chuyển Quầy → Kho (nhiều phiếu nếu > 200 lô) qua đúng
`kho_thuoc_service.chuyen_kho` của màn — cùng sổ, cùng nhật ký, hiện ở
"Phiếu chuyển đã lưu" và bấm Hoàn tác được.

Không rút:
  - phần đã bán chưa giao (giữ cho khách — `drug_batch_kha_dung`);
  - phần thuốc đã giao CHƯA gắn lô (đã rời kệ quầy; rút về kho thì không còn gì
    để gán) — để lại ở quầy, rút từ lô hạn xa nhất trước.

    docker cp scripts/chuyen-ton-quay-ve-kho.py <api>:/tmp/ck.py
    docker exec <api> python /tmp/ck.py "Hào Nam"          # THỬ KHÔ
    docker exec <api> python /tmp/ck.py "Hào Nam" --that   # làm thật

Chạy lại an toàn: khoá chống gửi trùng cố định theo cơ sở + phiếu, lần hai trả
lại đúng phiếu đã lập.
"""

from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal

import asyncpg

LY_DO = "Chuyển tồn đầu kỳ về kho khi bắt đầu dùng tách kho / quầy (16/11/2026)"


async def main() -> int:
    from clinicai.api.identity import ClinicRole, StaffIdentity
    from clinicai.services.kho_thuoc_service import PHIEU_TOI_DA_DONG, chuyen_kho
    from clinicai.services.kiem_ke_ca_service import giao_chua_gan_lo_theo_don_vi

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    that = "--that" in sys.argv
    if len(args) != 1:
        raise SystemExit('Dùng: python ck.py "<tên cơ sở>" [--that]')
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn)
    try:
        cs = await pool.fetch(
            "SELECT id::text, clinic_id::text, name FROM clinic_location"
            " WHERE name ILIKE '%' || $1 || '%'",
            args[0],
        )
        if len(cs) != 1:
            ten = [c["name"] for c in cs]
            raise SystemExit(f"✗ Tên cơ sở khớp {len(cs)} nơi, cần đúng 1: {ten}")
        lid, cid, ten_cs = cs[0]["id"], cs[0]["clinic_id"], cs[0]["name"]
        ql = await pool.fetchrow(
            """
            SELECT s.id::text AS id, s.auth_user_id::text AS au, s.full_name
              FROM staff s JOIN clinic_membership m ON m.staff_id = s.id
               AND m.is_active AND m.clinic_id = $1::uuid
             WHERE m.role = 'MANAGEMENT' AND s.is_active
             ORDER BY (s.full_name = 'Quản lý hệ thống') DESC LIMIT 1
            """,
            cid,
        )
        if ql is None:
            raise SystemExit("✗ Không có tài khoản Quản lý đang hoạt động để đứng tên.")
        ident = StaffIdentity(
            staff_id=ql["id"],
            auth_user_id=ql["au"] or "",
            full_name=ql["full_name"],
            department="MANAGEMENT",
            role=ClinicRole.MANAGEMENT,
            clinic_id=cid,
            location_id=lid,
            location_name=ten_cs,
        )
        lo = await pool.fetch(
            """
            SELECT b.id::text, b.drug_catalog_id::text AS thuoc, b.batch_code,
                   b.unit, lower(btrim(coalesce(b.unit, ''))) AS dv,
                   b.quantity_on_hand AS ton,
                   public.drug_batch_kha_dung(b.clinic_id, b.id) AS kha,
                   coalesce(c.name_base, c.name_raw, '?') AS ten
              FROM drug_batch b
              LEFT JOIN drug_catalog c
                ON c.id = b.drug_catalog_id AND c.clinic_id = b.clinic_id
             WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid
               AND b.noi_chua = 'QUAY' AND b.quantity_on_hand > 0
             ORDER BY b.expiry_date DESC NULLS FIRST, b.batch_code
            """,
            cid,
            lid,
        )
        async with pool.acquire() as conn:
            cho_gan = await giao_chua_gan_lo_theo_don_vi(
                conn, clinic_id=cid, location_id=lid
            )
        # Phần phải để lại ở quầy theo (thuốc, đơn vị): giao chưa gắn lô — trừ vào
        # lô hạn xa nhất trước (lô được xếp hạn xa → gần ở câu SELECT).
        con_giu = dict(cho_gan)
        dong: list[dict[str, str]] = []
        de_lai: list[str] = []
        for r in lo:
            kha = max(Decimal(str(r["kha"] or 0)), Decimal(0))
            giu = min(con_giu.get((r["thuoc"], r["dv"]), Decimal(0)), kha)
            if giu > 0:
                con_giu[(r["thuoc"], r["dv"])] -= giu
            rut = kha - giu
            ton = Decimal(str(r["ton"]))
            if rut < ton:
                de_lai.append(
                    f"    {r['ten']} · lô {r['batch_code']}: tồn {ton}, rút {rut}"
                    f" (đã bán chưa giao {ton - kha}, giao chưa gắn lô {giu})"
                    f" {r['unit']}"
                )
            if rut > 0:
                dong.append({"drug_batch_id": r["id"], "so_luong": str(rut)})

        che_do = "LÀM THẬT" if that else "THỬ KHÔ"
        print(f"{che_do} · cơ sở {ten_cs} · dưới tên {ql['full_name']}")
        print(f"  lô đang ở quầy còn tồn: {len(lo)}")
        print(f"  lô sẽ chuyển về kho:    {len(dong)}")
        print(f"  lô giữ lại một phần/hết ở quầy: {len(de_lai)}")
        for d in de_lai:
            print(d)
        if not that:
            print("\nĐây là THỬ KHÔ, chưa ghi gì. Thêm --that để làm thật.")
            return 0
        for i in range(0, len(dong), PHIEU_TOI_DA_DONG):
            kq = await chuyen_kho(
                pool,
                identity=ident,
                khoa_gui=f"chuyen-ton-quay-ve-kho-1611-{lid}-{i // PHIEU_TOI_DA_DONG}",
                huong="QUAY_KHO",
                ly_do=LY_DO,
                dong=dong[i : i + PHIEU_TOI_DA_DONG],
            )
            lai = " (đã lập từ lần chạy trước)" if kq.get("gui_lai") else ""
            print(f"  ✓ phiếu {kq['ma_phieu']}: {len(kq['dong'])} dòng{lai}")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
