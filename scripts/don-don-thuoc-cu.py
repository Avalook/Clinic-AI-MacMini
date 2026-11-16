#!/usr/bin/env python3
"""Dọn việc thu tiền thuốc còn tồn trước một mốc — 16/11/2026.

Danh sách Nhà thuốc lấy mọi dòng đơn CHƯA ĐÓNG, không giới hạn ngày. Thời chưa có
nút huỷ / chưa tự giao khi thu, việc dồn lại (16/11: ~7.000 dòng, màn chỉ đọc 300).
Tuyền chốt: dọn mọi việc tồn tạo trước 12:00 thứ Bảy 14/11/2026. Không xoá gì.

Hai loại, hai lệnh riêng:

* CHỜ THU (mặc định) — dòng chưa thu tiền thuốc, chưa giao → đóng bằng đúng lệnh
  "Khách không lấy" của màn (`PharmacyService.tu_choi`). Lệnh ấy tự từ chối dòng
  đã thu (kể cả lần thu cũ, chuyển khoản chờ xác minh) hoặc đã giao.
* ĐÃ THU CHƯA GIAO (`--da-thu`) — Tuyền chọn "ghi đã giao, KHÔNG trừ kho": thuốc
  đã đưa khách hồi đó, kho vừa chuyển tồn thật về KHO sáng 16/11. Mỗi lượt MỘT
  giao dịch: giao không lô (`_giao_khong_lo`, không ghi sổ kho) → huỷ dòng chờ gán
  lô vừa sinh, lý do "đối chiếu đầu kỳ" (`huy_cho_gan_lo`) → chốt dòng (`chot`).
  Tiền đã thu không đổi; sổ kho không có dòng nào mới.

    docker cp scripts/don-don-thuoc-cu.py <api>:/tmp/dd.py
    docker exec <api> python /tmp/dd.py --truoc=2026-11-14T12:00+07:00   # thử khô
    docker exec <api> python /tmp/dd.py --truoc=2026-11-14T12:00+07:00 --that
    docker exec <api> python /tmp/dd.py --truoc=... --da-thu [--that]
    docker exec <api> python /tmp/dd.py --hoan-tac         # mở lại đợt chờ thu
    docker exec <api> python /tmp/dd.py --hoan-tac-da-thu  # đợt đã thu → chưa giao

Không có `--truoc` thì mốc = đầu ngày hôm nay (giờ VN).
`--chi-luot=<id,id>` chỉ dùng trong test (DB test dùng chung giữa các bài).
Chạy lại an toàn: dòng đã đóng không còn trong danh sách ứng viên.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

DOT = "[DON-CU-1611]"
LY_DO = f"Dọn đơn cũ: khách không mua (lúc đó chưa có nút huỷ) {DOT}"
DOT_B = "[DA-GIAO-DAU-KY-1611]"
LY_DO_B = (
    "Đối chiếu đầu kỳ: thuốc đã thu tiền và đã đưa khách trước khi hệ thống "
    f"tự giao — ghi đã giao, không trừ kho {DOT_B}"
)

_LOC = """
  FROM public.prescription r
  JOIN public.visit v ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
  LEFT JOIN public.appointment ap
    ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
  LEFT JOIN public.clinic_location l
    ON l.id = coalesce(v.location_id, ap.location_id)
 WHERE r.clinic_id = $1::uuid
   AND r.removed_at IS NULL AND r.closed_at IS NULL
   AND r.created_at < coalesce($3::timestamptz,
        date_trunc('day', now() AT TIME ZONE 'Asia/Ho_Chi_Minh')
        AT TIME ZONE 'Asia/Ho_Chi_Minh')
   -- Chỉ để test: giới hạn vào lượt của chính bài (NULL = mọi lượt).
   AND ($2::uuid[] IS NULL OR r.visit_id = ANY($2::uuid[]))
"""
_DA_THU = """
   (EXISTS (SELECT 1 FROM public.payment p
             WHERE p.clinic_id = r.clinic_id AND p.visit_id = r.visit_id
               AND p.kind = 'thuoc' AND p.status = 'PAID')
    OR EXISTS (SELECT 1 FROM public.payment_cycle c
                WHERE c.clinic_id = r.clinic_id AND c.visit_id = r.visit_id
                  AND c.kind = 'thuoc' AND c.status = 'PAID'))
"""

CHO_THU = f"""
SELECT r.id::text, r.visit_id::text, l.name AS co_so
{_LOC}
   AND coalesce(r.dispensed_qty, 0) = 0
   AND NOT {_DA_THU}
   AND NOT EXISTS (SELECT 1 FROM public.payment_cycle c
                    WHERE c.clinic_id = r.clinic_id AND c.visit_id = r.visit_id
                      AND c.kind = 'thuoc' AND c.status = 'PENDING_VERIFICATION')
 ORDER BY r.created_at, r.id
"""

DA_THU = f"""
SELECT r.id::text, r.visit_id::text, l.name AS co_so,
       coalesce(r.purchased_qty, r.quantity_num) - coalesce(r.dispensed_qty, 0)
           AS con
{_LOC}
   AND {_DA_THU}
   AND coalesce(r.purchased_qty, r.quantity_num) > coalesce(r.dispensed_qty, 0)
 ORDER BY r.visit_id, r.created_at, r.id
"""


def _tham_so(ten: str) -> str:
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"{ten}=")), "")


async def _nguoi(pool: asyncpg.Pool) -> Any:
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


def _in_tom_tat(che_do: str, ident: Any, loai: str, dong: list[Any]) -> None:
    nhom = Counter(r["co_so"] or "?" for r in dong)
    luot = len({r["visit_id"] for r in dong})
    print(f"{che_do} · {loai} · dưới tên {ident.full_name}")
    print(f"  dòng đơn: {len(dong)} ({luot} lượt)")
    for cs, n in sorted(nhom.items()):
        print(f"    {cs}: {n} dòng")


async def _don_cho_thu(pool: asyncpg.Pool, ident: Any, dong: list[Any]) -> None:
    from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
    from clinicai.services.pharmacy_service import PharmacyService

    svc = PharmacyService(pool)
    dong_duoc = 0
    bo_qua: Counter[str] = Counter()
    for r in dong:
        try:
            kq = await svc.tu_choi(identity=ident, prescription_id=r["id"], ly_do=LY_DO)
            if not kq.get("da_chot_tu_truoc"):
                dong_duoc += 1
        except (ConflictError, ValidationError, NotFoundError) as exc:
            bo_qua[str(exc)[:120]] += 1
    print(f"  ✓ đã đóng {dong_duoc} dòng (lý do có mã {DOT})")
    for ly, n in bo_qua.most_common():
        print(f"  ↷ bỏ qua {n} dòng: {ly}")


async def _ghi_da_giao(pool: asyncpg.Pool, ident: Any, dong: list[Any]) -> None:
    """Mỗi lượt một giao dịch: giao không lô → huỷ chờ gán lô (không trừ kho) → chốt."""
    from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
    from clinicai.services.hoan_tac_giao_service import huy_cho_gan_lo
    from clinicai.services.pharmacy_service import PharmacyService
    from clinicai.services.tuong_tac_cskh_service import _ConnectionBoundPool

    theo_luot: dict[str, list[Any]] = {}
    for r in dong:
        theo_luot.setdefault(r["visit_id"], []).append(r)
    xong = 0
    bo_qua: Counter[str] = Counter()
    for ds in theo_luot.values():
        try:
            async with pool.acquire() as conn, conn.transaction():
                svc = PharmacyService(_ConnectionBoundPool(conn))  # type: ignore[arg-type]
                for r in ds:
                    don = await svc._khoa_theo_luot(conn, ident, r["id"])
                    await svc._giao_khong_lo(
                        conn,
                        identity=ident,
                        don=don,
                        prescription_id=r["id"],
                        luong=Decimal(str(r["con"])),
                    )
                    await huy_cho_gan_lo(
                        conn,
                        clinic_id=ident.clinic_id,
                        staff_id=ident.staff_id,
                        ly_do=LY_DO_B,
                        prescription_ids=[r["id"]],
                    )
                    await svc.chot(
                        identity=ident, prescription_id=r["id"], ly_do=LY_DO_B
                    )
            xong += 1
        except (ConflictError, ValidationError, NotFoundError) as exc:
            bo_qua[str(exc)[:120]] += 1
    print(f"  ✓ đã ghi đã giao (không trừ kho) + chốt {xong} lượt (mã {DOT_B})")
    for ly, n in bo_qua.most_common():
        print(f"  ↷ bỏ qua {n} lượt (giữ nguyên cả lượt): {ly}")


async def _hoan_tac(pool: asyncpg.Pool, ident: Any) -> int:
    """Mở lại các dòng đợt CHỜ THU: lệnh bù có sự kiện, không xoá sự kiện cũ."""
    from clinicai.services.pharmacy_service import _log

    async with pool.acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            "UPDATE public.prescription SET closed_at = NULL, refusal_reason = NULL,"
            " updated_at = now()"
            " WHERE clinic_id = $1::uuid AND refusal_reason = $2"
            " AND closed_at IS NOT NULL RETURNING id::text",
            ident.clinic_id,
            LY_DO,
        )
        for r in rows:
            await _log(
                conn,
                identity=ident,
                event_type="pharmacy.refuse_undone",
                aggregate_type="prescription",
                aggregate_id=r["id"],
                payload={"dot": DOT},
            )
    print(f"  ✓ đã mở lại {len(rows)} dòng của đợt {DOT}")
    return 0


async def _hoan_tac_da_thu(pool: asyncpg.Pool, ident: Any) -> int:
    """Trả đợt ĐÃ THU về "đã thu, chưa giao": mở dòng, bớt đúng số đợt đã ghi giao.
    Dòng chờ gán lô đã huỷ giữ nguyên làm vết."""
    from clinicai.services.hoan_tac_giao_service import giam_da_giao
    from clinicai.services.pharmacy_service import _log

    async with pool.acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            "SELECT prescription_id::text AS rx, sum(so_luong) AS sl"
            " FROM public.thuoc_giao_chua_gan_lo"
            " WHERE clinic_id = $1::uuid AND huy_ly_do = $2 GROUP BY 1",
            ident.clinic_id,
            LY_DO_B,
        )
        for r in rows:
            # Hàm có sẵn: giảm số đã giao, về 0 thì xoá dấu người/giờ giao
            # (ràng buộc prescription_cap_thi_co_dau_vet), mở lại dòng đã chốt.
            await giam_da_giao(
                conn,
                clinic_id=ident.clinic_id,
                prescription_id=r["rx"],
                so=Decimal(str(r["sl"])),
            )
            await _log(
                conn,
                identity=ident,
                event_type="pharmacy.dispense_undone",
                aggregate_type="prescription",
                aggregate_id=r["rx"],
                payload={"dot": DOT_B, "quantity": str(r["sl"])},
            )
        # Không chạy lại được hai lần: đánh dấu vết đã hoàn tác.
        await conn.execute(
            "UPDATE public.thuoc_giao_chua_gan_lo"
            " SET huy_ly_do = huy_ly_do || ' (đã hoàn tác)'"
            " WHERE clinic_id = $1::uuid AND huy_ly_do = $2",
            ident.clinic_id,
            LY_DO_B,
        )
    print(f"  ✓ đã trả {len(rows)} dòng của đợt {DOT_B} về đã thu, chưa giao")
    return 0


async def main() -> int:
    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn)
    try:
        ident = await _nguoi(pool)
        if "--hoan-tac" in sys.argv:
            return await _hoan_tac(pool, ident)
        if "--hoan-tac-da-thu" in sys.argv:
            return await _hoan_tac_da_thu(pool, ident)
        chi = _tham_so("--chi-luot")
        truoc_chu = _tham_so("--truoc")
        truoc = datetime.fromisoformat(truoc_chu) if truoc_chu else None
        if truoc is not None and truoc.tzinfo is None:
            raise SystemExit("✗ --truoc phải có múi giờ, vd 2026-11-14T12:00+07:00")
        da_thu = "--da-thu" in sys.argv
        dong = await pool.fetch(
            DA_THU if da_thu else CHO_THU,
            ident.clinic_id,
            chi.split(",") if chi else None,
            truoc,
        )
        loai = (
            "ĐÃ THU CHƯA GIAO → ghi đã giao" if da_thu else "CHỜ THU → khách không lấy"
        )
        moc = truoc.isoformat() if truoc else "đầu ngày hôm nay"
        _in_tom_tat(
            "LÀM THẬT" if that else "THỬ KHÔ", ident, f"{loai} · trước {moc}", dong
        )
        if not that:
            print("\nĐây là THỬ KHÔ, chưa ghi gì. Thêm --that để làm thật.")
            return 0
        if da_thu:
            await _ghi_da_giao(pool, ident, dong)
        else:
            await _don_cho_thu(pool, ident, dong)
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
