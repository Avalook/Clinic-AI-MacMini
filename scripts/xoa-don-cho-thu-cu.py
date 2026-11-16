#!/usr/bin/env python3
"""XOÁ HẲN đơn thuốc CHỜ THU tồn cũ — Tuyền chốt 16/11/2026.

Thời chưa có nút "Khách không mua đơn này" (#643), khách không mua thì đơn thuốc nằm
ở danh sách chờ thu mãi (16/11: màn Quầy thu hiện 339 khách chờ, toàn khách cũ).
Tuyền: xoá hẳn các đơn CHỜ THU tạo trước 12:00 14/11/2026; lượt nào ĐÃ tạo bill
(thu xong / chờ xác minh / đã huỷ phiếu) giữ nguyên.

Ứng viên: dòng đơn hiện hành, chưa đóng, chưa giao, lượt CHƯA có lần thu tiền
thuốc nào (`payment` / `payment_cycle` kind thuoc, mọi trạng thái), tạo trước mốc.
Xoá bằng DELETE thường — trigger `prescription_dinh_chinh_guard` vẫn canh: dòng
của hồ sơ ĐÃ KÝ hoặc đã có dấu vết (thu / bán / giao / đính chính) bị DB từ chối →
script bỏ qua dòng đó và báo. Khoá ngoại (phân lô, trả thuốc, chờ gán lô, vật tư
bán, dòng thay thế) đều RESTRICT: dòng nào bị trỏ tới thì DB từ chối, không kéo
theo gì. Không đụng bảng tiền nào.

Trước khi xoá, chép NGUYÊN dòng ra tệp JSONL (`--luu`); `--khoi-phuc` chèn lại
đúng các dòng ấy (cùng id). Mỗi dòng xoá ghi một sự kiện `pharmacy.don_cu_xoa`.

    docker cp scripts/xoa-don-cho-thu-cu.py <api>:/tmp/xd.py
    docker exec <api> python /tmp/xd.py --truoc=2026-11-14T12:00+07:00     # thử khô
    docker exec <api> python /tmp/xd.py --truoc=2026-11-14T12:00+07:00 \
        --luu=/tmp/xoa-don-1611.jsonl --that
    docker cp <api>:/tmp/xoa-don-1611.jsonl /home/clinicai/backups/   # GIỮ tệp
    docker exec <api> python /tmp/xd.py --khoi-phuc=/tmp/xoa-don-1611.jsonl

`--chi-luot=<id,id>` chỉ dùng trong test (DB test dùng chung giữa các bài).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Any

import asyncpg

DOT = "[XOA-DON-CHO-THU-1611]"

UNG_VIEN = """
SELECT r.id::text, r.visit_id::text, r.clinic_patient_id::text AS khach,
       coalesce(l.name, '?') AS co_so
  FROM public.prescription r
  JOIN public.visit v ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
  LEFT JOIN public.appointment ap
    ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
  LEFT JOIN public.clinic_location l
    ON l.id = coalesce(v.location_id, ap.location_id)
 WHERE r.clinic_id = $1::uuid
   AND r.removed_at IS NULL AND r.closed_at IS NULL
   AND coalesce(r.dispensed_qty, 0) = 0
   AND r.created_at < $3::timestamptz
   AND NOT EXISTS (SELECT 1 FROM public.payment p
                    WHERE p.clinic_id = r.clinic_id AND p.visit_id = r.visit_id
                      AND p.kind = 'thuoc')
   AND NOT EXISTS (SELECT 1 FROM public.payment_cycle c
                    WHERE c.clinic_id = r.clinic_id AND c.visit_id = r.visit_id
                      AND c.kind = 'thuoc')
   AND ($2::uuid[] IS NULL OR r.visit_id = ANY($2::uuid[]))
 ORDER BY r.created_at, r.id
"""


def _tham_so(ten: str) -> str:
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"{ten}=")), "")


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


async def _khoi_phuc(pool: asyncpg.Pool, ident: Any, tep: str) -> int:
    """Chèn lại đúng các dòng đã lưu (cùng id) — dòng đã có thì bỏ qua."""
    from clinicai.services.pharmacy_service import _log

    with open(tep, encoding="utf-8") as f:
        dong = [json.loads(x) for x in f if x.strip()]
    lai = 0
    async with pool.acquire() as conn, conn.transaction():
        # Cột tự sinh (vd dispense_status) không chèn được — để DB tự tính lại.
        cot = ", ".join(
            f'"{r["column_name"]}"'
            for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = 'public' AND table_name = 'prescription'"
                " AND is_generated = 'NEVER' ORDER BY ordinal_position"
            )
        )
        for d in dong:
            moi = await conn.fetchval(
                f"INSERT INTO public.prescription ({cot})"  # noqa: S608 — tên cột từ catalog
                f" SELECT {cot} FROM jsonb_populate_record("
                " NULL::public.prescription, $1::jsonb)"
                " ON CONFLICT (id) DO NOTHING RETURNING id::text",
                json.dumps(d, ensure_ascii=False),
            )
            if moi:
                lai += 1
                await _log(
                    conn,
                    identity=ident,
                    event_type="pharmacy.don_cu_khoi_phuc",
                    aggregate_type="prescription",
                    aggregate_id=moi,
                    payload={"dot": DOT},
                )
    print(f"  ✓ đã khôi phục {lai}/{len(dong)} dòng từ {tep}")
    return 0


async def _xoa(pool: asyncpg.Pool, ident: Any, dong: list[Any], tep: str) -> None:
    from clinicai.services.pharmacy_service import _log

    xoa = 0
    bo_qua: Counter[str] = Counter()
    with open(tep, "a", encoding="utf-8") as f:
        async with pool.acquire() as conn:
            for r in dong:
                try:
                    async with conn.transaction():
                        ban = await conn.fetchval(
                            "SELECT to_jsonb(p) FROM public.prescription p"
                            " WHERE p.id = $1::uuid FOR UPDATE",
                            r["id"],
                        )
                        n = await conn.execute(
                            "DELETE FROM public.prescription"
                            " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                            " AND removed_at IS NULL AND closed_at IS NULL",
                            r["id"],
                            ident.clinic_id,
                        )
                        if n != "DELETE 1":
                            bo_qua["dòng đã đổi trạng thái"] += 1
                            continue
                        await _log(
                            conn,
                            identity=ident,
                            event_type="pharmacy.don_cu_xoa",
                            aggregate_type="prescription",
                            aggregate_id=r["id"],
                            payload={"dot": DOT, "visit_id": r["visit_id"]},
                        )
                    # Chỉ ghi bản lưu khi giao dịch xoá đã commit.
                    f.write(ban if isinstance(ban, str) else json.dumps(ban))
                    f.write("\n")
                    f.flush()
                    xoa += 1
                except (
                    asyncpg.CheckViolationError,
                    asyncpg.ForeignKeyViolationError,
                ) as e:
                    bo_qua[str(e).split("\n")[0][:110]] += 1
    print(f"  ✓ đã xoá {xoa} dòng (bản lưu: {tep})")
    for ly, n in bo_qua.most_common():
        print(f"  ↷ bỏ qua {n} dòng: {ly}")


async def main() -> int:
    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn)
    try:
        ident = await _nguoi(pool)
        if tep := _tham_so("--khoi-phuc"):
            return await _khoi_phuc(pool, ident, tep)
        truoc_chu = _tham_so("--truoc")
        if not truoc_chu:
            raise SystemExit("✗ Thiếu --truoc, vd --truoc=2026-11-14T12:00+07:00")
        truoc = datetime.fromisoformat(truoc_chu)
        if truoc.tzinfo is None:
            raise SystemExit("✗ --truoc phải có múi giờ, vd 2026-11-14T12:00+07:00")
        chi = _tham_so("--chi-luot")
        dong = await pool.fetch(
            UNG_VIEN, ident.clinic_id, chi.split(",") if chi else None, truoc
        )
        che_do = "LÀM THẬT" if that else "THỬ KHÔ"
        print(f"{che_do} · xoá đơn CHỜ THU tạo trước {truoc.isoformat()}")
        luot = len({r["visit_id"] for r in dong})
        khach = len({r["khach"] for r in dong})
        print(f"  dòng đơn: {len(dong)} · lượt: {luot} · khách: {khach}")
        for cs, n in sorted(Counter(r["co_so"] for r in dong).items()):
            print(f"    {cs}: {n} dòng")
        if not that:
            print("\nĐây là THỬ KHÔ, chưa ghi gì. Thêm --luu=<tệp> --that để xoá.")
            return 0
        tep = _tham_so("--luu")
        if not tep:
            raise SystemExit("✗ Làm thật phải có --luu=<tệp> để giữ bản lưu.")
        await _xoa(pool, ident, dong, tep)
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
