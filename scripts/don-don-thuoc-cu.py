#!/usr/bin/env python3
"""Dọn đơn thuốc cũ treo ở "Đang xử lý" của Nhà thuốc — 16/11/2026.

Danh sách lấy mọi dòng đơn CHƯA ĐÓNG, không giới hạn ngày. Thời chưa có nút huỷ,
khách không mua thì dòng nằm đó mãi (16/11: ~7.000 dòng, màn chỉ đọc 300 mới
nhất). Script đóng các dòng tạo TRƯỚC HÔM NAY, chưa thu tiền thuốc, chưa giao,
bằng đúng lệnh "Khách không lấy" của màn (`PharmacyService.tu_choi`) — không xoá
gì. Lệnh ấy tự từ chối dòng đã thu tiền (kể cả lần thu cũ, chuyển khoản chờ xác
minh) hoặc đã giao, nên số đã tính (doanh thu, kho, sổ nợ) không đổi.

    docker cp scripts/don-don-thuoc-cu.py <api>:/tmp/dd.py
    docker exec <api> python /tmp/dd.py                 # THỬ KHÔ
    docker exec <api> python /tmp/dd.py --that          # làm thật
    docker exec <api> python /tmp/dd.py --hoan-tac      # mở lại cả đợt

`--chi-luot=<id,id>` chỉ dùng trong test (DB test dùng chung giữa các bài).

Chạy lại an toàn: dòng đã đóng không còn trong danh sách ứng viên.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter

import asyncpg

DOT = "[DON-CU-1611]"
LY_DO = f"Dọn đơn cũ: khách không mua (lúc đó chưa có nút huỷ) {DOT}"

UNG_VIEN = """
SELECT r.id::text, l.name AS co_so,
       CASE WHEN r.created_at >= now() - interval '8 days' THEN '≤7 ngày'
            WHEN r.created_at >= now() - interval '31 days' THEN '8–30 ngày'
            ELSE '>30 ngày' END AS tuoi
  FROM public.prescription r
  JOIN public.visit v ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
  LEFT JOIN public.appointment ap
    ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
  LEFT JOIN public.clinic_location l
    ON l.id = coalesce(v.location_id, ap.location_id)
 WHERE r.clinic_id = $1::uuid
   AND r.removed_at IS NULL AND r.closed_at IS NULL
   AND coalesce(r.dispensed_qty, 0) = 0
   AND r.created_at < date_trunc('day', now() AT TIME ZONE 'Asia/Ho_Chi_Minh')
                      AT TIME ZONE 'Asia/Ho_Chi_Minh'
   AND NOT EXISTS (SELECT 1 FROM public.payment p
                    WHERE p.clinic_id = r.clinic_id AND p.visit_id = r.visit_id
                      AND p.kind = 'thuoc' AND p.status = 'PAID')
   AND NOT EXISTS (SELECT 1 FROM public.payment_cycle c
                    WHERE c.clinic_id = r.clinic_id AND c.visit_id = r.visit_id
                      AND c.kind = 'thuoc'
                      AND c.status IN ('PENDING_VERIFICATION', 'PAID'))
   -- Chỉ để test: giới hạn vào lượt của chính bài (NULL = mọi lượt).
   AND ($2::uuid[] IS NULL OR r.visit_id = ANY($2::uuid[]))
 ORDER BY r.created_at, r.id
"""


async def _nguoi(pool: asyncpg.Pool) -> object:
    from clinicai.api.identity import ClinicRole, StaffIdentity

    ql = await pool.fetchrow(
        """
        SELECT s.id::text AS id, s.auth_user_id::text AS au, s.full_name,
               m.clinic_id::text AS cid,
               coalesce(s.primary_location_id,
                        (SELECT id FROM clinic_location
                          WHERE clinic_id = m.clinic_id LIMIT 1))::text AS lid
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


async def _hoan_tac(pool: asyncpg.Pool, ident: object) -> int:
    """Mở lại đúng các dòng đợt này đóng: lệnh bù có sự kiện, không xoá sự kiện cũ."""
    from clinicai.services.pharmacy_service import _log

    n = 0
    async with pool.acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            "UPDATE public.prescription SET closed_at = NULL, refusal_reason = NULL,"
            " updated_at = now()"
            " WHERE clinic_id = $1::uuid AND refusal_reason = $2"
            " AND closed_at IS NOT NULL RETURNING id::text",
            ident.clinic_id,  # type: ignore[attr-defined]
            LY_DO,
        )
        for r in rows:
            await _log(
                conn,
                identity=ident,  # type: ignore[arg-type]
                event_type="pharmacy.refuse_undone",
                aggregate_type="prescription",
                aggregate_id=r["id"],
                payload={"dot": DOT},
            )
            n += 1
    print(f"  ✓ đã mở lại {n} dòng của đợt {DOT}")
    return 0


async def main() -> int:
    from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
    from clinicai.services.pharmacy_service import PharmacyService

    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn)
    try:
        ident = await _nguoi(pool)
        if "--hoan-tac" in sys.argv:
            return await _hoan_tac(pool, ident)
        chi = next(
            (a.split("=", 1)[1] for a in sys.argv if a.startswith("--chi-luot=")), ""
        )
        dong = await pool.fetch(
            UNG_VIEN,
            ident.clinic_id,  # type: ignore[attr-defined]
            chi.split(",") if chi else None,
        )
        nhom = Counter((r["co_so"] or "?", r["tuoi"]) for r in dong)
        luot = await pool.fetchval(
            "SELECT count(DISTINCT visit_id) FROM prescription"
            " WHERE id = ANY($1::uuid[])",
            [r["id"] for r in dong],
        )
        che_do = "LÀM THẬT" if that else "THỬ KHÔ"
        print(f"{che_do} · dưới tên {ident.full_name}")  # type: ignore[attr-defined]
        print(f"  dòng đơn sẽ đóng: {len(dong)} ({luot} lượt)")
        for (cs, tuoi), n in sorted(nhom.items()):
            print(f"    {cs} · {tuoi}: {n} dòng")
        if not that:
            print("\nĐây là THỬ KHÔ, chưa ghi gì. Thêm --that để làm thật.")
            return 0
        svc = PharmacyService(pool)
        dong_duoc = 0
        tu_choi: Counter[str] = Counter()
        for r in dong:
            try:
                kq = await svc.tu_choi(
                    identity=ident,  # type: ignore[arg-type]
                    prescription_id=r["id"],
                    ly_do=LY_DO,
                )
                if not kq.get("da_chot_tu_truoc"):
                    dong_duoc += 1
            except (ConflictError, ValidationError, NotFoundError) as exc:
                tu_choi[str(exc)[:120]] += 1
        print(f"  ✓ đã đóng {dong_duoc} dòng (lý do có mã {DOT})")
        for ly, n in tu_choi.most_common():
            print(f"  ↷ bỏ qua {n} dòng: {ly}")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
