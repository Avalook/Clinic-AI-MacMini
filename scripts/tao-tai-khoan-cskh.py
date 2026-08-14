#!/usr/bin/env python3
"""Cấp hồ sơ nhân sự + tài khoản đăng nhập cho một danh sách CSKH.

Tuyền 14/08/2026: danh sách 11 người, vai CSKH, mật khẩu 12345678 như bảng bàn
giao, tên tài khoản theo quy ước "Đặng Dương → dang-duong".

KHÔNG CHỈ TẠO TÀI KHOẢN. `identity.py` tra nhân sự qua `staff.auth_user_id`,
nên một tài khoản đăng nhập không gắn hồ sơ nhân sự sẽ đăng nhập được mà MỌI
thao tác ghi trả 403 — và màn hình không nói được vì sao (người dùng chỉ thấy
mình vào được rồi không làm được gì). Script làm đủ ba việc:

    hồ sơ nhân sự  →  thẻ thành viên vai CSKH  →  tài khoản đăng nhập, nối lại

CHẠY LẠI ĐƯỢC. Người đã có tài khoản thì bỏ qua, không tạo bản thứ hai: một
người xuất hiện hai lần trong `staff` là hai dòng trong mọi ô chọn bác sĩ/nhân
viên, và số liệu KPI của họ bị chia đôi.

    docker cp tao-tai-khoan-cskh.py <container_api>:/tmp/
    docker exec <container_api> python /tmp/tao-tai-khoan-cskh.py --that

Không có `--that` thì chỉ IN RA việc sẽ làm, không đụng gì.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import unicodedata

import asyncpg
import httpx

MAT_KHAU = "12345678"
TEN_MIEN = "dr4women.vn"

DANH_SACH = [
    "Đặng Dương",
    "Đào Thu Thảo",
    "Hồng Ngát",
    "Kim Tiến",
    "Nguyễn Thị Ngọc Giàu",
    "Nguyễn Thùy Trang",
    "Phương Thúy Nguyễn",
    "Thanh Tươi",
    "Thắng Trịnh",
    "Thu Hiền",
    "Hà Nguyễn",
]


def slug(ten: str) -> str:
    """Tên người → tên tài khoản. "Đặng Dương" → "dang-duong".

    `Đ`/`đ` phải thay TRƯỚC khi bỏ dấu: nó là một chữ cái riêng trong bảng chữ
    cái tiếng Việt, không phải `d` có dấu, nên NFD không tách nó ra. Bỏ bước này
    thì "Đặng Dương" ra "ng-duong".
    """
    ten = ten.replace("Đ", "D").replace("đ", "d")
    ten = unicodedata.normalize("NFD", ten)
    ten = "".join(c for c in ten if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", ten.lower()).strip("-")


async def main() -> int:
    that = "--that" in sys.argv
    moi_truong = os.environ.get("APP_ENV", "?")
    conn = await asyncpg.connect(
        os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    )
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    clinic_id = str(await conn.fetchval("SELECT id FROM public.clinic LIMIT 1"))

    # Mượn cơ sở làm việc của một CSKH đã có. `primary_location_id` là NOT NULL
    # — một nhân sự không thuộc cơ sở nào là thứ hệ thống không cho tồn tại.
    location_id = await conn.fetchval(
        """
        SELECT s.primary_location_id FROM public.staff s
          JOIN public.clinic_membership m ON m.staff_id = s.id
         WHERE m.clinic_id = $1::uuid AND m.role = 'CSKH' AND s.is_active
         LIMIT 1
        """,
        clinic_id,
    )
    if location_id is None:
        print("DỪNG: chưa có CSKH nào để mượn cơ sở làm việc.")
        return 2

    print(f"\nMôi trường: {moi_truong}   ({'TẠO THẬT' if that else 'chỉ xem trước'})\n")
    tao, bo_qua = [], []

    async with httpx.AsyncClient(timeout=30.0) as http:
        for ten in DANH_SACH:
            email = f"{slug(ten)}@{TEN_MIEN}"

            # Đã có người này chưa? Hỏi HAI đường, vì hai đường hỏng theo hai
            # kiểu khác nhau: trùng email (tài khoản đã tồn tại) và trùng tên
            # kèm vai CSKH (người đã có hồ sơ dưới một email khác — đúng ca của
            # "CSKH · Kim Tiến", email cskhkimtien@, sẽ lọt nếu chỉ hỏi email).
            trung_email = await conn.fetchval(
                "SELECT id FROM auth.users WHERE lower(email) = lower($1)", email
            )
            trung_ten = await conn.fetchval(
                """
                SELECT s.full_name FROM public.staff s
                  JOIN public.clinic_membership m ON m.staff_id = s.id
                 WHERE m.clinic_id = $1::uuid AND m.role = 'CSKH'
                   AND s.auth_user_id IS NOT NULL
                   AND s.full_name ILIKE '%' || $2 || '%'
                 LIMIT 1
                """,
                clinic_id,
                ten,
            )
            if trung_email or trung_ten:
                bo_qua.append((ten, email, trung_ten or "email đã tồn tại"))
                continue
            tao.append((ten, email))

        for ten, email, ly_do in bo_qua:
            print(f"  – bỏ qua  {ten:24} {email}   ← {ly_do}")
        for ten, email in tao:
            print(f"  + tạo     {ten:24} {email}")

        if not that:
            print(f"\n{len(tao)} sẽ tạo, {len(bo_qua)} bỏ qua. Thêm --that để làm thật.\n")
            await conn.close()
            return 0

        for ten, email in tao:
            r = await http.post(
                f"{base}/auth/v1/admin/users",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                json={"email": email, "password": MAT_KHAU, "email_confirm": True},
            )
            if r.status_code >= 300:
                print(f"  ✗ {ten}: tạo tài khoản hỏng — {r.status_code} {r.text[:120]}")
                continue
            auth_id = r.json()["id"]

            # Hồ sơ + tài khoản trong CÙNG một giao dịch. Tạo hồ sơ xong mà nối
            # tài khoản hỏng thì để lại một nhân sự "chưa link" trông y như chưa
            # được cấp — rồi lần chạy sau tạo thêm một hồ sơ nữa cho cùng người.
            async with conn.transaction():
                staff_id = await conn.fetchval(
                    """
                    INSERT INTO public.staff
                        (full_name, auth_user_id, is_active, primary_location_id,
                         primary_department)
                    VALUES ($1, $2::uuid, TRUE, $3::uuid, 'CSKH') RETURNING id
                    """,
                    ten,
                    auth_id,
                    location_id,
                )
                # Chèn `staff` đã tự sinh thẻ thành viên qua trigger; câu này để
                # bài không phụ thuộc vào trigger ấy còn sống.
                await conn.execute(
                    """
                    INSERT INTO public.clinic_membership
                        (clinic_id, staff_id, role, is_active)
                    VALUES ($1::uuid, $2::uuid, 'CSKH', TRUE)
                    ON CONFLICT (clinic_id, staff_id, role)
                    DO UPDATE SET is_active = TRUE
                    """,
                    clinic_id,
                    staff_id,
                )
            print(f"  ✓ {ten:24} {email}")

    n = await conn.fetchval(
        """
        SELECT count(*) FROM public.clinic_membership m
          JOIN public.staff s ON s.id = m.staff_id
         WHERE m.clinic_id = $1::uuid AND m.role = 'CSKH'
           AND s.auth_user_id IS NOT NULL AND s.is_active
        """,
        clinic_id,
    )
    print(f"\nTổng CSKH có tài khoản trên {moi_truong}: {n}\n")
    await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
