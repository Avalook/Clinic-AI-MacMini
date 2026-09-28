#!/usr/bin/env python3
"""Chuyển MỘT nhân sự sang vai khác, quyền y hệt một người mẫu của vai ấy.

Tuyền 28/09/2026: "chuyển người này sang cskh cho tôi, Kim Tiến ấy, nick là
kim-tien". Làm bốn việc trong một giao dịch database + một lời gọi GoTrue:

  1. Tên đăng nhập → `<tai-khoan>@<đuôi>` (GIỮ mật khẩu cũ).
  2. Thẻ thành viên: vai cũ TẮT, vai mới BẬT (đăng nhập đòi đúng MỘT thẻ bật).
  3. `staff.primary_department` = vai mới.
  4. Quyền: THU mọi quyền đang có (đóng dấu `revoked_at`, không xoá) → CHÉP
     quyền đang hiệu lực của người mẫu (vd CSKH "Đặng Dương").

    docker cp scripts/doi-vai-nhan-su.py <api>:/tmp/dv.py
    docker exec <api> python /tmp/dv.py --ten "Kim Tiến" --vai CSKH \
        --mau "Đặng Dương" --tai-khoan kim-tien            # THỬ KHÔ
    … --that                                                # làm thật

Người được chuyển đăng xuất rồi đăng nhập lại để thanh bên đổi theo vai mới.
Chạy lại được: đã đúng vai / tên / quyền thì không đổi gì thêm.
"""

# ruff: noqa: E501 — script vận hành, câu SQL / thông báo giữ nguyên một dòng.
from __future__ import annotations

import argparse
import asyncio
import os

import asyncpg
import httpx

TEN_MIEN = os.environ.get("DUOI_TEN_DANG_NHAP", "dr4women.vn")

_QUYEN = """
SELECT g.grant_id::text AS id, g.capability, g.scope_type,
       g.scope_id::text AS scope_id, g.tu_khoi
  FROM capability_grant g
 WHERE g.clinic_id = $1::uuid AND g.staff_id = $2::uuid AND g.revoked_at IS NULL
   AND (g.valid_until IS NULL OR g.valid_until > now())
"""


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ten", required=True, help="full_name hồ sơ cần chuyển")
    ap.add_argument("--vai", required=True, help="vai mới, vd CSKH")
    ap.add_argument("--mau", required=True, help="full_name người mẫu của vai mới")
    ap.add_argument("--tai-khoan", required=True, help="tên đăng nhập mới")
    ap.add_argument("--that", action="store_true")
    a = ap.parse_args()

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    hdr = {"apikey": key, "Authorization": f"Bearer {key}"}
    email = f"{a.tai_khoan.strip().lower()}@{TEN_MIEN}"

    conn = await asyncpg.connect(dsn)
    try:
        ho_so = await conn.fetch(
            """
            SELECT s.id::text AS id, s.full_name, s.primary_department,
                   s.auth_user_id::text AS uid, u.email, m.clinic_id::text AS cid,
                   m.role
              FROM staff s
              JOIN clinic_membership m ON m.staff_id = s.id AND m.is_active
              LEFT JOIN auth.users u ON u.id = s.auth_user_id
             WHERE s.is_active AND s.full_name = ANY($1::text[])
            """,
            [a.ten, a.mau],
        )
        theo = {}
        for r in ho_so:
            theo.setdefault(r["full_name"], []).append(r)
        for ten in (a.ten, a.mau):
            if len(theo.get(ten, [])) != 1:
                raise SystemExit(
                    f"✗ '{ten}': tìm thấy {len(theo.get(ten, []))} hồ sơ đang làm"
                    " (cần đúng 1)."
                )
        nv, mau = theo[a.ten][0], theo[a.mau][0]
        if mau["role"] != a.vai:
            raise SystemExit(
                f"✗ Người mẫu '{a.mau}' đang là {mau['role']}, không phải {a.vai}."
            )
        chu = await conn.fetchval(
            "SELECT id::text FROM auth.users WHERE email = $1", email
        )
        if chu and chu != nv["uid"]:
            raise SystemExit(f"✗ {email} đã thuộc tài khoản khác.")
        ql = await conn.fetchval(
            "SELECT id::text FROM staff WHERE full_name = 'Quản lý hệ thống'"
            " AND is_active LIMIT 1"
        )
        cu = await conn.fetch(_QUYEN, nv["cid"], nv["id"])
        moi = await conn.fetch(_QUYEN, mau["cid"], mau["id"])
        khoa = lambda q: (q["capability"], q["scope_type"], q["scope_id"])  # noqa: E731
        can_giu = {khoa(q) for q in moi}
        thu = [q for q in cu if khoa(q) not in can_giu]
        co = {khoa(q) for q in cu}
        cap = [q for q in moi if khoa(q) not in co]

        print(f"{'LÀM THẬT' if a.that else 'THỬ KHÔ'} · {a.ten}")
        print(f"  tên đăng nhập: {nv['email'] or '—'} → {email}")
        print(f"  vai: {nv['role']} → {a.vai}")
        print(
            f"  thu {len(thu)} quyền: {', '.join(sorted({q['tu_khoi'] or q['capability'] for q in thu})) or '—'}"
        )
        print(
            f"  cấp {len(cap)} quyền (chép {a.mau}): {', '.join(sorted({q['tu_khoi'] or q['capability'] for q in cap})) or '—'}"
        )
        if not a.that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
            return 0

        async with conn.transaction():
            if nv["role"] != a.vai:
                await conn.execute(
                    "UPDATE clinic_membership SET is_active = false"
                    " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid AND role <> $3",
                    nv["cid"],
                    nv["id"],
                    a.vai,
                )
                await conn.execute(
                    "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
                    " VALUES ($1::uuid, $2::uuid, $3, true)"
                    " ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = true",
                    nv["cid"],
                    nv["id"],
                    a.vai,
                )
            await conn.execute(
                "UPDATE staff SET primary_department = $2 WHERE id = $1::uuid",
                nv["id"],
                a.vai,
            )
            for q in thu:
                await conn.execute(
                    "UPDATE capability_grant SET revoked_at = now(), revoked_by = $2::uuid,"
                    " ly_do = coalesce(ly_do || ' · ', '') || $3"
                    " WHERE grant_id = $1::uuid AND revoked_at IS NULL",
                    q["id"],
                    ql,
                    f"Chuyển vai sang {a.vai} (28/09/2026)",
                )
            for q in cap:
                await conn.execute(
                    """
                    INSERT INTO capability_grant
                        (clinic_id, staff_id, capability, scope_type, scope_id,
                         tu_khoi, granted_by, ly_do)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid, $6, $7::uuid, $8)
                    ON CONFLICT DO NOTHING
                    """,
                    nv["cid"],
                    nv["id"],
                    q["capability"],
                    q["scope_type"],
                    q["scope_id"],
                    q["tu_khoi"],
                    ql,
                    f"Chuyển vai sang {a.vai} — chép quyền {a.mau} (28/09/2026)",
                )
            if nv["uid"] and nv["email"] != email:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    r = await http.put(
                        f"{base}/auth/v1/admin/users/{nv['uid']}",
                        headers=hdr,
                        json={"email": email, "email_confirm": True},
                    )
                if r.status_code >= 300:
                    # Lỗi đổi tên đăng nhập → huỷ cả giao dịch, không để nửa vời.
                    raise SystemExit(
                        f"✗ Đổi tên đăng nhập lỗi: {r.status_code} {r.text[:160]}"
                    )
        print(
            f"\n✓ Xong. {a.ten} đăng xuất rồi đăng nhập lại bằng '{a.tai_khoan}'"
            " (mật khẩu cũ). Quyền có hiệu lực trong ~5 giây."
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
