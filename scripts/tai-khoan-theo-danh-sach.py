#!/usr/bin/env python3
"""Tài khoản theo DANH SÁCH NHÂN SỰ THẬT (Tuyền chốt 28/09/2026).

Quy tắc tên đăng nhập: tên không dấu nối gạch (`nguyen-thi-tien`); bác sĩ thêm
`bs-` (`bs-vu-trong-hung`). Mật khẩu chung `MAT_KHAU_MOI` (mặc định 12345678) —
đặt lại cho CẢ người đã có tài khoản. Hồ sơ không còn trong danh sách thì KHOÁ
(không xoá cứng: hồ sơ gắn lịch sử khám / thu, database chặn xoá — khoá = tắt
đăng nhập + ẩn khỏi mọi danh sách, lịch sử cũ giữ nguyên).

Dữ liệu cá nhân nằm NGOÀI git: tệp kế hoạch JSON
    {"nguoi": [{ten, tai_khoan, ho_so (tên hồ sơ đang có | null = tạo mới), vai}],
     "khoa": [tên hồ sơ], "doi_ten_ho_so": {tên cũ: tên mới}}

    docker cp scripts/tai-khoan-theo-danh-sach.py <api>:/tmp/tk.py
    docker cp tai-khoan-2809.json <api>:/tmp/tk.json
    docker exec <api> python /tmp/tk.py --ke-hoach /tmp/tk.json          # THỬ KHÔ
    docker exec <api> python /tmp/tk.py --ke-hoach /tmp/tk.json --that   # làm thật

Việc tạo / đổi tài khoản trên prod do NGƯỜI chạy (Tuyền), không do máy tự làm.
Chạy lại được: ai đã đúng tên + đã khoá thì bỏ qua phần ấy.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import asyncpg
import httpx

TEN_MIEN = os.environ.get("DUOI_TEN_DANG_NHAP", "dr4women.vn")
MAT_KHAU = os.environ.get("MAT_KHAU_MOI", "12345678")
KHOA_LAU = "876000h"  # ~100 năm — GoTrue "ban", đảo lại được bằng ban_duration "none"


async def main() -> int:
    if "--ke-hoach" not in sys.argv:
        raise SystemExit("✗ Thiếu --ke-hoach <tệp JSON>.")
    with open(sys.argv[sys.argv.index("--ke-hoach") + 1], encoding="utf-8") as f:
        kh: dict[str, Any] = json.load(f)
    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    hdr = {"apikey": key, "Authorization": f"Bearer {key}"}

    conn = await asyncpg.connect(dsn)
    try:
        cid = await conn.fetchval(
            "SELECT clinic_id::text FROM clinic_room WHERE code = 'KN-TIEPDON' LIMIT 1"
        )
        if not cid:
            raise SystemExit("✗ Không thấy cơ sở Kim Ngưu (phòng KN-TIEPDON).")
        rows = await conn.fetch(
            """
            SELECT s.id::text AS id, s.full_name, s.auth_user_id::text AS uid,
                   u.email, s.is_active, m.role
              FROM staff s
              JOIN clinic_membership m ON m.staff_id = s.id AND m.clinic_id = $1::uuid
              LEFT JOIN auth.users u ON u.id = s.auth_user_id
             WHERE s.is_active AND m.is_active
            """,
            cid,
        )
        theo_ten: dict[str, list[asyncpg.Record]] = {}
        for r in rows:
            theo_ten.setdefault(r["full_name"], []).append(r)
        email_co = {
            r["email"]: r["id"]
            for r in await conn.fetch("SELECT id::text AS id, email FROM auth.users")
        }

        loi: list[str] = []
        doi: list[dict[str, Any]] = []
        moi: list[dict[str, Any]] = []
        for n in kh["nguoi"]:
            email = f"{n['tai_khoan']}@{TEN_MIEN}"
            if n["ho_so"] is None:
                if n["ten"] in theo_ten:
                    loi.append(f"{n['ten']}: ghi 'tạo mới' mà đã có hồ sơ cùng tên")
                if email in email_co:
                    loi.append(f"{email}: tên đăng nhập đã có người dùng")
                moi.append({**n, "email": email})
                continue
            hs = theo_ten.get(n["ho_so"], [])
            if len(hs) != 1:
                loi.append(
                    f"{n['ten']}: hồ sơ '{n['ho_so']}' tìm thấy {len(hs)} (cần đúng 1)"
                )
                continue
            h = hs[0]
            chu = email_co.get(email)
            if chu and chu != h["uid"]:
                loi.append(f"{email}: đã thuộc tài khoản khác")
            doi.append(
                {
                    **n,
                    "email": email,
                    "staff_id": h["id"],
                    "uid": h["uid"],
                    "email_cu": h["email"],
                    "vai_hien": h["role"],
                }
            )
        khoa = []
        for ten in kh["khoa"]:
            for h in theo_ten.get(ten, []):
                khoa.append(
                    {
                        "ten": ten,
                        "staff_id": h["id"],
                        "uid": h["uid"],
                        "email": h["email"],
                    }
                )
        con_lai = sorted(
            {r["full_name"] for r in rows}
            - {n["ho_so"] for n in kh["nguoi"] if n["ho_so"]}
            - set(kh["khoa"])
        )

        print(f"{'LÀM THẬT' if that else 'THỬ KHÔ'} · @{TEN_MIEN} · mật khẩu chung")
        print(f"\nĐỔI TÊN ĐĂNG NHẬP + ĐẶT LẠI MẬT KHẨU ({len(doi)}):")
        for d in doi:
            ten_moi = kh.get("doi_ten_ho_so", {}).get(d["ho_so"])
            ghi = f"  (đổi tên hồ sơ '{d['ho_so']}' → '{ten_moi}')" if ten_moi else ""
            print(f"  {d['ho_so']:<26} {d['email_cu'] or '—':<34} → {d['email']}{ghi}")
        print(f"\nTẠO MỚI ({len(moi)}):")
        for m in moi:
            print(f"  {m['ten']:<26} {m['vai']:<18} {m['email']}")
        print(f"\nKHOÁ (tắt đăng nhập + ẩn, không xoá lịch sử) ({len(khoa)}):")
        for k in khoa:
            print(f"  {k['ten']:<26} {k['email'] or '—'}")
        print(
            f"\nGIỮ NGUYÊN — không có trong danh sách, cần Tuyền xem ({len(con_lai)}):"
        )
        print("  " + ", ".join(con_lai))
        if loi:
            print("\n✗ DỪNG — xung đột:")
            for x in loi:
                print(f"    {x}")
            return 2
        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
            return 0

        async with httpx.AsyncClient(timeout=30.0) as http:
            for cu, moi_ten in kh.get("doi_ten_ho_so", {}).items():
                await conn.execute(
                    "UPDATE staff SET full_name = $2"
                    " WHERE full_name = $1 AND is_active",
                    cu,
                    moi_ten,
                )
            for d in doi:
                uid = d["uid"]
                if uid is None:
                    r = await http.post(
                        f"{base}/auth/v1/admin/users",
                        headers=hdr,
                        json={
                            "email": d["email"],
                            "password": MAT_KHAU,
                            "email_confirm": True,
                        },
                    )
                    r.raise_for_status()
                    await conn.execute(
                        "UPDATE staff SET auth_user_id = $1::uuid WHERE id = $2::uuid",
                        r.json()["id"],
                        d["staff_id"],
                    )
                else:
                    r = await http.put(
                        f"{base}/auth/v1/admin/users/{uid}",
                        headers=hdr,
                        json={
                            "email": d["email"],
                            "password": MAT_KHAU,
                            "email_confirm": True,
                            "ban_duration": "none",
                        },
                    )
                    if r.status_code >= 300:
                        print(f"  ✗ {d['email']}: {r.status_code} {r.text[:120]}")
                        continue
                print(f"  ✓ đổi  {d['email']}")
            for m in moi:
                r = await http.post(
                    f"{base}/auth/v1/admin/users",
                    headers=hdr,
                    json={
                        "email": m["email"],
                        "password": MAT_KHAU,
                        "email_confirm": True,
                    },
                )
                if r.status_code >= 300:
                    print(f"  ✗ {m['email']}: {r.status_code} {r.text[:120]}")
                    continue
                uid = r.json()["id"]
                async with conn.transaction():
                    sid = await conn.fetchval(
                        """
                        INSERT INTO staff (full_name, is_active, auth_user_id,
                                           primary_department, primary_location_id)
                        VALUES ($1, TRUE, $3::uuid, $4,
                                (SELECT l.id FROM clinic_location l
                                  WHERE l.clinic_id = $2::uuid AND l.is_active
                                  ORDER BY l.created_at LIMIT 1))
                        RETURNING id::text
                        """,
                        m["ten"],
                        cid,
                        uid,
                        m["vai"],
                    )
                    await conn.execute(
                        "INSERT INTO clinic_membership"
                        " (clinic_id, staff_id, role, is_active)"
                        " VALUES ($1::uuid, $2::uuid, $3, TRUE)"
                        " ON CONFLICT (clinic_id, staff_id, role)"
                        " DO UPDATE SET is_active = TRUE",
                        cid,
                        sid,
                        m["vai"],
                    )
                print(f"  ✓ tạo  {m['email']}")
            for k in khoa:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE clinic_membership SET is_active = FALSE"
                        " WHERE staff_id = $1::uuid",
                        k["staff_id"],
                    )
                    await conn.execute(
                        "UPDATE staff SET is_active = FALSE WHERE id = $1::uuid",
                        k["staff_id"],
                    )
                if k["uid"]:
                    await http.put(
                        f"{base}/auth/v1/admin/users/{k['uid']}",
                        headers=hdr,
                        json={"ban_duration": KHOA_LAU},
                    )
                print(f"  ✓ khoá {k['ten']}")
        print(
            "\nXong. Quyền người mới: chạy tiếp"
            " scripts/ky-nang-tu-file.py --that --cap-quyen."
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
