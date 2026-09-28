#!/usr/bin/env python3
"""Cấp bù sau khi Bàn khám / Phòng dịch vụ có thêm khối `duyet_ket_qua` (28/09/2026).

Tuyền chốt: thư ký, bác sĩ, điều dưỡng xếp cùng phòng "bản chất node giống nhau,
thao tác như nhau, song song" — mở cả duyệt kết quả / cho gửi kết quả. Lego lưu
theo KHỐI, nên thêm khối vào định nghĩa lego không tự cấp cho người đã bật:
script này cấp `duyet_ket_qua` cho ai đang có khối `kham` (Bàn khám) hoặc
`thuc_hien` (Phòng dịch vụ). Kèm: bác sĩ đang hoạt động mà CHƯA có khối nào (vd
tài khoản bác sĩ vừa tạo) → bật lego như mọi bác sĩ (tư vấn, bàn khám, lịch).

    docker cp scripts/cap-duyet-ket-qua.py <api>:/tmp/cdk.py
    docker exec <api> python /tmp/cdk.py          # THỬ KHÔ
    docker exec <api> python /tmp/cdk.py --that   # làm thật

Đi qua PermissionService (cap_khoi / doi_lego) — cùng sổ kiểm toán, cùng cache.
Chạy lại được.
"""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

LEGO_BAC_SI = ("tu_van", "ban_kham", "lich_lam_viec")


async def main() -> int:
    from clinicai.api.identity import ClinicRole, StaffIdentity
    from clinicai.services.permission_service import PermissionService

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
        can_cap = await pool.fetch(
            """
            SELECT s.id::text AS id, s.full_name
              FROM staff s
              JOIN clinic_membership m ON m.staff_id = s.id AND m.is_active
               AND m.clinic_id = $1::uuid
             WHERE s.is_active
               AND EXISTS (SELECT 1 FROM v_quyen_hieu_luc q
                            WHERE q.clinic_id = $1::uuid AND q.staff_id = s.id
                              AND q.work_pack IN ('kham', 'thuc_hien'))
               AND NOT EXISTS (SELECT 1 FROM v_quyen_hieu_luc q
                                WHERE q.clinic_id = $1::uuid AND q.staff_id = s.id
                                  AND q.work_pack = 'duyet_ket_qua')
             GROUP BY s.id, s.full_name ORDER BY s.full_name
            """,
            cid,
        )
        bs_trong = await pool.fetch(
            """
            SELECT s.id::text AS id, s.full_name
              FROM staff s
              JOIN clinic_membership m ON m.staff_id = s.id AND m.is_active
               AND m.clinic_id = $1::uuid AND m.role = 'DOCTOR'
             WHERE s.is_active AND s.auth_user_id IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM v_quyen_hieu_luc q
                                WHERE q.clinic_id = $1::uuid AND q.staff_id = s.id)
            """,
            cid,
        )
        print(
            f"{'LÀM THẬT' if that else 'THỬ KHÔ'} · thao tác dưới tên {ql['full_name']}"
        )
        print(f"  cấp khối duyet_ket_qua cho {len(can_cap)} người:")
        print("    " + ", ".join(r["full_name"] for r in can_cap))
        print(
            f"  bác sĩ chưa có quyền nào → bật {', '.join(LEGO_BAC_SI)}: "
            f"{', '.join(r['full_name'] for r in bs_trong) or '—'}"
        )
        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
            return 0
        svc = PermissionService(pool)
        for r in bs_trong:
            for ma in LEGO_BAC_SI:
                await svc.doi_lego(staff_id=r["id"], ma=ma, bat=True, identity=ident)
            print(f"  ✓ bác sĩ {r['full_name']}")
        for r in can_cap:
            await svc.cap_khoi(
                staff_id=r["id"],
                khoi="duyet_ket_qua",
                identity=ident,
                ly_do="Cùng phòng thao tác như nhau (28/09/2026)",
            )
        print(f"  ✓ đã cấp duyet_ket_qua cho {len(can_cap)} người")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
