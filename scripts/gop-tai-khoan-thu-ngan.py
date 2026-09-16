#!/usr/bin/env python3
"""Cho hai tài khoản quầy thu ngân cũ NGHỈ, sau khi đã có tài khoản `thu-ngan`.

    docker exec <api> python /tmp/gop-tai-khoan-thu-ngan.py          # THỬ KHÔ
    docker exec <api> python /tmp/gop-tai-khoan-thu-ngan.py --that   # làm thật

Tuyền chốt 16/09/2026: một tài khoản `thu-ngan` có cả hai quầy. Hai tài khoản
`thu-ngan-thuoc` và `thu-ngan-dich-vu` dựng trước đó không còn dùng.

NGHỈ, KHÔNG XOÁ. Tài khoản đăng nhập (auth.users) giữ nguyên; chỉ tắt hồ sơ
nhân sự và thẻ thành viên, nên đăng nhập vào sẽ không có quyền gì. Lý do: mọi
lần thu tiền đã ghi dưới hai tài khoản ấy vẫn trỏ vào hồ sơ của chúng — xoá hồ
sơ là để lại những khoản thu không biết ai thu. Bật lại chỉ là đổi một cột.

KIỂM TRƯỚC KHI TẮT: phải có `thu-ngan` đang hoạt động. Tắt hai tài khoản cũ khi
tài khoản mới chưa có là để phòng khám không còn ai thu tiền được.
"""

import asyncio
import os
import sys

import asyncpg

MOI = "thu-ngan@dr4women.vn"
CU = ("thu-ngan-thuoc@dr4women.vn", "thu-ngan-dich-vu@dr4women.vn")


async def main() -> int:
    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        co_moi = await conn.fetchval(
            """
            SELECT count(*) FROM staff s
              JOIN auth.users u ON u.id = s.auth_user_id
              JOIN clinic_membership m ON m.staff_id = s.id AND m.is_active
             WHERE u.email = $1 AND s.is_active
            """,
            MOI,
        )
        if not co_moi:
            print(f"✗ Chưa có {MOI} đang hoạt động — DỪNG, không tắt tài khoản cũ.")
            return 2
        print(f"✓ {MOI} đang hoạt động.")
        for email in CU:
            sid = await conn.fetchval(
                """
                SELECT s.id::text FROM staff s
                  JOIN auth.users u ON u.id = s.auth_user_id
                 WHERE u.email = $1 AND s.is_active
                """,
                email,
            )
            if sid is None:
                print(f"  · {email}: đã nghỉ hoặc không có — bỏ qua")
                continue
            if not that:
                print(f"  → sẽ cho nghỉ {email}")
                continue
            async with conn.transaction():
                await conn.execute(
                    "UPDATE clinic_membership SET is_active = FALSE "
                    "WHERE staff_id = $1::uuid",
                    sid,
                )
                await conn.execute(
                    "UPDATE staff SET is_active = FALSE WHERE id = $1::uuid", sid
                )
            print(f"  ✓ đã cho nghỉ {email}")
        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
