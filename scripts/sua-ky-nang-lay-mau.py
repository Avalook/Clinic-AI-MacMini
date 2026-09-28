#!/usr/bin/env python3
"""Kỹ năng "Lấy mẫu xét nghiệm" mở phòng LẤY MẪU (KN-LAYMAU) — 28/09/2026.

Bản 27/09 đổi nhầm kỹ năng này sang phòng Siêu âm + Thủ thuật, nên người có kỹ
năng Lấy mẫu không mở được phòng Lấy mẫu (Tuyền: "việc lấy mẫu là một node riêng
biệt"). Script: với mỗi người đang có kỹ năng → BỎ (theo định nghĩa cũ: phòng
chỉ kỹ năng này cần thì rút, phòng kỹ năng khác cần thì giữ) → đổi định nghĩa
sang KN-LAYMAU → BẬT lại. Đi qua KyNangService — cùng sổ kiểm toán, cùng cache.

    docker cp scripts/sua-ky-nang-lay-mau.py <api>:/tmp/lm.py
    docker exec <api> python /tmp/lm.py          # THỬ KHÔ
    docker exec <api> python /tmp/lm.py --that   # làm thật

Chạy lại được: định nghĩa đã đúng thì chỉ bật lại (không đổi gì).
"""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

MA = "lay_mau"
PHONG = "KN-LAYMAU"


async def main() -> int:
    from clinicai.api.identity import ClinicRole, StaffIdentity
    from clinicai.services.ky_nang_service import KyNangService

    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn)
    try:
        cid = await pool.fetchval(
            "SELECT clinic_id::text FROM clinic_room WHERE code = $1 LIMIT 1", PHONG
        )
        phong_id = await pool.fetchval(
            "SELECT id::text FROM clinic_room"
            " WHERE code = $1 AND clinic_id = $2::uuid AND is_active",
            PHONG,
            cid,
        )
        # Kiểm TRƯỚC khi đổi gì: bỏ kỹ năng rồi mới vấp phòng tắt là mất kỹ năng
        # của cả nhóm (đã xảy ra trên máy thử 28/09).
        if not phong_id:
            raise SystemExit(
                f"✗ Phòng {PHONG} không có hoặc đang tắt — bật phòng trước."
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
        cu = await pool.fetchval(
            "SELECT array(SELECT r.name FROM clinic_room r"
            " WHERE r.id = ANY(k.phong_ids) ORDER BY r.name)"
            " FROM ky_nang k WHERE k.clinic_id = $1::uuid AND k.ma = $2",
            cid,
            MA,
        )
        nguoi = await pool.fetch(
            "SELECT s.id::text AS id, s.full_name FROM nhan_su_ky_nang n"
            " JOIN staff s ON s.id = n.staff_id AND s.is_active"
            " WHERE n.clinic_id = $1::uuid AND n.ky_nang_ma = $2 ORDER BY 2",
            cid,
            MA,
        )
        print(f"{'LÀM THẬT' if that else 'THỬ KHÔ'} · dưới tên {ql['full_name']}")
        print(f"  phòng của kỹ năng hiện tại: {', '.join(cu or []) or '—'}")
        print(f"  → đổi thành: {PHONG}")
        print(f"  cấp lại cho {len(nguoi)} người: ")
        print("    " + ", ".join(r["full_name"] for r in nguoi))
        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
            return 0
        svc = KyNangService(pool)
        for r in nguoi:
            await svc.doi(staff_id=r["id"], ma=MA, bat=False, identity=ident)
        await pool.execute(
            "UPDATE ky_nang SET phong_ids = ARRAY[$3::uuid], updated_at = now()"
            " WHERE clinic_id = $1::uuid AND ma = $2",
            cid,
            MA,
            phong_id,
        )
        for r in nguoi:
            await svc.doi(staff_id=r["id"], ma=MA, bat=True, identity=ident)
            print(f"  ✓ {r['full_name']}")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
