#!/usr/bin/env python3
"""Thêm lego vào một kỹ năng rồi bật lego ấy cho người đang có kỹ năng — 28/09/2026.

Vì sao có: bảng kỹ năng 27/09 thiếu lego "Đặt lịch" cho CSKH và Lễ tân (Tuyền:
"cskh chưa có node đặt lịch"), thiếu "Thêm bệnh nhân" cho CSKH; 28/09 thêm lego
"Đối tác" cho kỹ năng Lấy mẫu (người phòng khám thao tác hộ đối tác). Script CHỈ THÊM:
không bỏ rồi bật lại kỹ năng, nên không ai mất quyền giữa chừng trong giờ làm.
Bật lego đi qua PermissionService.doi_lego — cùng sổ kiểm toán, cùng cache.

    docker cp scripts/them-lego-cho-ky-nang.py <api>:/tmp/tl.py
    docker exec <api> python /tmp/tl.py            # THỬ KHÔ
    docker exec <api> python /tmp/tl.py --that     # làm thật

Chạy lại được: lego đã có trong kỹ năng / người đã bật thì bỏ qua.
"""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

THEM: dict[str, tuple[str, ...]] = {
    "cskh": ("dat_lich", "them_benh_nhan"),
    "le_tan": ("dat_lich",),
    # 28/09: người lấy mẫu thao tác hộ đối tác (màn /doi-tac).
    "lay_mau": ("doi_tac",),
}


async def main() -> int:
    from clinicai.api.identity import ClinicRole, StaffIdentity
    from clinicai.permissions.catalogue import MAN
    from clinicai.services.permission_service import PermissionService

    for ds in THEM.values():
        for m in ds:
            if m not in MAN:
                raise SystemExit(f"✗ Không có lego {m} trong catalogue.")
    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn)
    try:
        cid = await pool.fetchval(
            "SELECT clinic_id::text FROM clinic_room WHERE code = 'KN-TIEPDON' LIMIT 1"
        )
        ql = await pool.fetchrow(
            """
            SELECT s.id::text AS id, s.auth_user_id::text AS au, s.full_name,
                   s.primary_location_id::text AS lid
              FROM staff s JOIN clinic_membership m ON m.staff_id = s.id
               AND m.is_active AND m.clinic_id = $1::uuid
             WHERE m.role = 'MANAGEMENT' AND s.is_active
             ORDER BY (s.full_name = 'Quản lý hệ thống') DESC LIMIT 1
            """,
            cid,
        )
        ident = StaffIdentity(
            staff_id=ql["id"],
            auth_user_id=ql["au"] or "",
            full_name=ql["full_name"],
            department="MANAGEMENT",
            role=ClinicRole.MANAGEMENT,
            clinic_id=cid,
            location_id=ql["lid"],
            location_name=None,
        )
        svc = PermissionService(pool)
        print(f"{'LÀM THẬT' if that else 'THỬ KHÔ'} · dưới tên {ql['full_name']}")
        for ky, them in THEM.items():
            co = await pool.fetchval(
                "SELECT lego FROM ky_nang WHERE clinic_id = $1::uuid AND ma = $2",
                cid,
                ky,
            )
            if co is None:
                print(f"  ✗ không có kỹ năng {ky} — bỏ qua")
                continue
            moi = [m for m in them if m not in co]
            nguoi = await pool.fetch(
                "SELECT s.id::text AS id, s.full_name FROM nhan_su_ky_nang n"
                " JOIN staff s ON s.id = n.staff_id AND s.is_active"
                " WHERE n.clinic_id = $1::uuid AND n.ky_nang_ma = $2 ORDER BY 2",
                cid,
                ky,
            )
            print(f"  {ky}: lego {list(co)} + {moi or '(đã đủ)'}")
            print(f"    {len(nguoi)} người: {', '.join(r['full_name'] for r in nguoi)}")
            if not that:
                continue
            if moi:
                await pool.execute(
                    "UPDATE ky_nang SET lego = lego || $3::text[], updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND ma = $2",
                    cid,
                    ky,
                    moi,
                )
            for r in nguoi:
                hien = await svc.lego_cua_nguoi(staff_id=r["id"], identity=ident)
                da_bat = {m["ma"] for m in hien["lego"] if m["bat"]}
                for m in them:
                    if m not in da_bat:
                        await svc.doi_lego(
                            staff_id=r["id"], ma=m, bat=True, identity=ident
                        )
                        print(f"    ✓ {r['full_name']}: + {m}")
        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
