#!/usr/bin/env python3
"""Bác sĩ mới nhận ĐÚNG bộ quyền bác sĩ đang dùng (28/09/2026).

`tai-khoan-theo-danh-sach.py` tạo hồ sơ + tài khoản nhưng KHÔNG cấp quyền —
bác sĩ mới có 0 quyền, bác sĩ cũ có 8 (khám, chỉ định, ghi bệnh án, điền /
duyệt kết quả, tư vấn, hoàn tất khám, xem lịch làm việc).

KHÔNG dùng preset vai DOCTOR: preset có 18 quyền, còn bác sĩ cũ đã được quản lý
THU lại điều phối + làm dịch vụ mọi phòng (làm dịch vụ đi theo phòng được xếp
lịch). Script chép các quyền ĐANG HIỆU LỰC của một bác sĩ mẫu (`MAU`) — bác sĩ
mới giống hệt bác sĩ cũ, quản lý chỉnh tiếp ở màn Phân quyền.

    docker cp scripts/cap-quyen-bac-si-moi.py <api>:/tmp/cq.py
    docker exec <api> python /tmp/cq.py          # THỬ KHÔ
    docker exec <api> python /tmp/cq.py --that   # làm thật

Chạy lại được: quyền đã có thì bỏ qua.
"""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

TEN = ["BS Nguyễn Thuỳ Linh", "BS Hoàng Quốc Dũng", "BS Xuân Thanh"]
MAU = "BS Hằng"

_QUYEN_HIEU_LUC = """
SELECT g.capability, g.scope_type, g.scope_id::text AS scope_id, g.tu_khoi
  FROM capability_grant g
 WHERE g.clinic_id = $1::uuid AND g.staff_id = $2::uuid
   AND g.revoked_at IS NULL
   AND (g.valid_until IS NULL OR g.valid_until > now())
"""


async def main() -> int:
    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        ho_so = {
            r["full_name"]: r
            for r in await conn.fetch(
                """
                SELECT s.id::text AS id, s.full_name, m.clinic_id::text AS cid
                  FROM staff s JOIN clinic_membership m
                    ON m.staff_id = s.id AND m.is_active AND m.role = 'DOCTOR'
                 WHERE s.is_active AND s.full_name = ANY($1::text[])
                """,
                [*TEN, MAU],
            )
        }
        thieu = sorted({*TEN, MAU} - set(ho_so))
        if thieu:
            raise SystemExit(f"✗ Không thấy hồ sơ bác sĩ đang làm: {', '.join(thieu)}")
        mau = ho_so[MAU]
        ql = await conn.fetchval(
            "SELECT s.id::text FROM staff s WHERE s.full_name = 'Quản lý hệ thống'"
            " AND s.is_active LIMIT 1"
        )
        mau_q = await conn.fetch(_QUYEN_HIEU_LUC, mau["cid"], mau["id"])
        print(f"{'LÀM THẬT' if that else 'THỬ KHÔ'} · chép quyền của {MAU}")
        print("  " + ", ".join(sorted(q["capability"] for q in mau_q)))
        can: list[tuple[dict, asyncpg.Record]] = []
        for ten in TEN:
            r = ho_so[ten]
            co = {
                (q["capability"], q["scope_type"], q["scope_id"])
                for q in await conn.fetch(_QUYEN_HIEU_LUC, r["cid"], r["id"])
            }
            them = [
                q
                for q in mau_q
                if (q["capability"], q["scope_type"], q["scope_id"]) not in co
            ]
            print(f"  {ten:<22} +{len(them)}")
            can += [(dict(r), q) for q in them]
        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
            return 0
        async with conn.transaction():
            for r, q in can:
                await conn.execute(
                    """
                    INSERT INTO capability_grant
                        (clinic_id, staff_id, capability, scope_type, scope_id,
                         tu_khoi, granted_by, ly_do)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid, $6, $7::uuid, $8)
                    ON CONFLICT DO NOTHING
                    """,
                    r["cid"],
                    r["id"],
                    q["capability"],
                    q["scope_type"],
                    q["scope_id"],
                    q["tu_khoi"],
                    ql,
                    f"Bác sĩ mới — chép quyền {MAU} (28/09/2026)",
                )
        # Bộ nhớ quyền của API tự quên sau 5 giây (permissions/cache.py).
        print(f"\n✓ Xong: cấp {len(can)} quyền — có hiệu lực trong ~5 giây.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
