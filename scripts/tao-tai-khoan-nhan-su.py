#!/usr/bin/env python3
"""Cấp tài khoản đăng nhập cho MỌI nhân sự đang làm việc chưa có tài khoản.

Thay cho `tao-tai-khoan-cskh.py` (14/08/2026), vốn chỉ làm cho một danh sách
CSKH viết cứng và gán tất cả vào vai CSKH — kể cả ba người mà bảng bàn giao
16/09 ghi là **Quản lý hệ thống**.

    docker cp scripts/tao-tai-khoan-nhan-su.py <api>:/tmp/
    docker exec <api> python /tmp/tao-tai-khoan-nhan-su.py          # THỬ KHÔ
    docker exec <api> python /tmp/tao-tai-khoan-nhan-su.py --that   # làm thật

KHÔNG CHỈ TẠO TÀI KHOẢN. `identity.py` tra nhân sự qua `staff.auth_user_id`.
Một tài khoản không gắn hồ sơ nhân sự thì đăng nhập được mà MỌI thao tác ghi
trả 403 — người dùng chỉ thấy mình vào được rồi không làm được gì, và màn hình
không nói được vì sao. Script làm đủ ba việc, theo đúng thứ tự:

    hồ sơ nhân sự  →  thẻ thành viên (vai)  →  tài khoản, nối lại bằng auth_user_id

CHẠY LẠI ĐƯỢC. Ai đã có tài khoản thì bỏ qua. Một người thành hai dòng `staff`
là hai dòng trong mọi ô chọn bác sĩ, và KPI của họ bị chia đôi.

TRÙNG TÊN TÀI KHOẢN THÌ DỪNG LẠI VÀ BÁO, KHÔNG TỰ ĐOÁN. "Kim Tiến" có mặt cả
trong danh sách CSKH lẫn trong nhóm điều dưỡng của phòng khám. Tự thêm số vào
đuôi là tạo ra một tên đăng nhập không ai biết; gán nhầm vào người kia là trao
quyền xem hồ sơ bệnh nhân cho sai người. Cả hai đều tệ hơn việc dừng lại hỏi.

MẬT KHẨU CHUNG LÀ CHỖ YẾU, VÀ PHẢI ĐƯỢC BIẾT LÀ CHỖ YẾU. Bảng bàn giao ghi
`12345678` cho mọi người. Nó chấp nhận được trong ngày bàn giao, KHÔNG chấp nhận
được sau khi có bệnh nhân thật: một người biết quy ước tên tài khoản là vào được
hồ sơ bệnh án của cả phòng khám. Đổi bằng `MAT_KHAU_MOI=...`, và bắt đổi mật
khẩu ngay buổi đầu.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import unicodedata
from typing import Any

import asyncpg
import httpx

TEN_MIEN = os.environ.get("DUOI_TEN_DANG_NHAP", "dr4women.vn")
MAT_KHAU = os.environ.get("MAT_KHAU_MOI", "12345678")

#: Người CHƯA có hồ sơ nhân sự — thêm mới (tên, vai, tên tài khoản).
#: Nguồn: "Tài khoản CSKH .docx", bảng Tuyền gửi 16/09/2026. Tên tài khoản lấy
#: ĐÚNG như bảng, kể cả tiền tố `qlht-`, vì đó là thứ người ta sẽ gõ.
THEM_MOI: list[tuple[str, str, str]] = [
    ("Đào Thu Thảo", "CSKH", "dao-thu-thao"),
    ("Đặng Dương", "CSKH", "dang-duong"),
    ("Hồng Ngát", "CSKH", "hong-ngat"),
    ("Kim Tiến", "CSKH", "kim-tien"),
    ("Nguyễn Thị Ngọc Giàu", "CSKH", "nguyen-thi-ngoc-giau"),
    ("Nguyễn Thùy Trang", "CSKH", "nguyen-thuy-trang"),
    ("Phương Thúy Nguyễn", "CSKH", "phuong-thuy-nguyen"),
    ("Thanh Tươi", "CSKH", "thanh-tuoi"),
    ("Quản lý hệ thống", "MANAGEMENT", "quanlyhethong"),
    ("Hà Nguyễn", "MANAGEMENT", "qlht-ha-nguyen"),
    ("Thắng Trịnh", "MANAGEMENT", "qlht-thang-trinh"),
    ("Thu Hiền", "MANAGEMENT", "qlht-thu-hien"),
    # ── Năm vai có MÀN HÌNH nhưng chưa có một ai đăng nhập được vào (16/09) ──
    #
    # Đây là tài khoản THEO VỊ TRÍ, không theo người: ai vào ca ngồi chỗ nào thì
    # dùng tài khoản của chỗ đó. Khác hẳn mười hai dòng ở trên, vốn là tài khoản
    # của một con người cụ thể.
    #
    # Biết trước cái giá của lựa chọn ấy: `event_log` sẽ ghi "thu ngân thuốc đã
    # thu 300.000đ", không ghi được AI thu. Truy ngược một lần thu sai sẽ phải
    # tra lịch trực để đoán, mà lịch trực thì sửa được. Chấp nhận được lúc này
    # vì phòng khám chưa chốt ai ngồi quầy nào; khi chốt rồi thì tách ra thành
    # tài khoản từng người, và bản ghi cũ vẫn giữ nguyên.
    ("Trưởng ca", "TRUONG_CA", "truong-ca"),
    ("Thu ngân thuốc", "CASHIER_THUOC", "thu-ngan-thuoc"),
    ("Thu ngân dịch vụ", "CASHIER_DV", "thu-ngan-dich-vu"),
    # Tuyền đặt tên tài khoản này 16/09, giữ ĐÚNG chữ Tuyền viết.
    ("Đối tác phòng khám", "PARTNER", "doi-tac-pk"),
    # Cái tivi ở phòng chờ. Nó phải đăng nhập như mọi vai khác, và vai này bị
    # `get_current_identity` từ chối ở mọi đường ghi — xem identity.py.
    ("Màn hình phòng chờ", "DISPLAY", "man-hinh-phong-cho"),
]


def slug(ten: str) -> str:
    """Tên người → tên tài khoản. "Đặng Dương" → "dang-duong".

    `Đ`/`đ` phải đổi TRƯỚC khi bỏ dấu: NFKD tách được dấu của `á`, `ê`… nhưng
    `Đ` là một chữ cái riêng, không phải `D` + dấu, nên nó bị xoá thẳng và
    "Đặng Dương" ra "ng-duong".
    """
    ten = ten.replace("Đ", "D").replace("đ", "d")
    ten = unicodedata.normalize("NFKD", ten)
    ten = "".join(c for c in ten if not unicodedata.combining(c))
    ten = re.sub(r"[^A-Za-z0-9]+", "-", ten).strip("-").lower()
    return ten


async def main() -> int:
    that = "--that" in sys.argv
    moi_truong = os.environ.get("APP_ENV", "?")
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    conn = await asyncpg.connect(dsn)
    try:
        clinic_id = await conn.fetchval("SELECT id FROM clinic LIMIT 1")
        hien_co = await conn.fetch(
            """
            SELECT s.id::text AS staff_id, s.full_name, m.role,
                   s.auth_user_id IS NOT NULL AS co_tk
              FROM clinic_membership m
              JOIN staff s ON s.id = m.staff_id
             WHERE m.clinic_id = $1::uuid AND m.is_active AND s.is_active
             ORDER BY m.role, s.full_name
            """,
            clinic_id,
        )
        ten_hien_co = {r["full_name"] for r in hien_co}

        # ── Dựng kế hoạch trước, làm sau. Va chạm phải lộ ra ở bước này. ──
        ke_hoach: list[dict[str, Any]] = []
        for r in hien_co:
            if r["co_tk"]:
                continue
            ke_hoach.append(
                {
                    "viec": "cấp tài khoản",
                    "ten": r["full_name"],
                    "vai": r["role"],
                    "tk": slug(r["full_name"]),
                    "staff_id": r["staff_id"],
                }
            )
        vai_hien_co = {r["full_name"]: r["role"] for r in hien_co}
        lech_vai: list[str] = []
        for ten, vai, tk in THEM_MOI:
            if ten in ten_hien_co:
                # ĐÃ CÓ HỒ SƠ — dùng bản trong database, KHÔNG tạo người thứ
                # hai. Nhưng nếu vai trong bảng bàn giao khác vai đang lưu thì
                # phải NÓI RA: vai quyết định người ấy xem được hồ sơ nào. Bỏ
                # qua trong im lặng là để một khác biệt về quyền trôi đi.
                if vai_hien_co.get(ten) != vai:
                    lech_vai.append(
                        f"{ten}: bảng bàn giao ghi {vai}, "
                        f"database đang là {vai_hien_co.get(ten)}"
                    )
                continue
            ke_hoach.append(
                {"viec": "thêm mới", "ten": ten, "vai": vai, "tk": tk, "staff_id": None}
            )

        dem: dict[str, list[str]] = {}
        for k in ke_hoach:
            dem.setdefault(k["tk"], []).append(f"{k['ten']} ({k['vai']})")
        va_cham = {t: ng for t, ng in dem.items() if len(ng) > 1}

        print(f"Môi trường: {moi_truong} · đuôi tên đăng nhập: @{TEN_MIEN}")
        print(
            f"Đang làm việc: {len(hien_co)} · đã có tài khoản: "
            f"{sum(1 for r in hien_co if r['co_tk'])}"
        )
        print(f"Sẽ xử lý: {len(ke_hoach)}\n")
        for k in sorted(ke_hoach, key=lambda x: (x["vai"], x["ten"])):
            print(
                f"  {k['viec']:<14} {k['vai']:<18} {k['ten']:<24} {k['tk']}@{TEN_MIEN}"
            )

        if lech_vai:
            print("\n⚠ LỆCH VAI — dùng vai trong database, cần Tuyền xác nhận:")
            for d in lech_vai:
                print(f"    {d}")

        if va_cham:
            print("\n✗ TRÙNG TÊN TÀI KHOẢN — dừng, không đoán:")
            for t, ng in va_cham.items():
                print(f"    {t}@{TEN_MIEN}  ←  {' / '.join(ng)}")
            print("  Đặt tên khác cho một trong hai (sửa THEM_MOI), rồi chạy lại.")
            return 2

        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
            return 0

        async with httpx.AsyncClient(timeout=30.0) as http:
            for k in ke_hoach:
                email = f"{k['tk']}@{TEN_MIEN}"
                r = await http.post(
                    f"{base}/auth/v1/admin/users",
                    headers={"apikey": key, "Authorization": f"Bearer {key}"},
                    json={
                        "email": email,
                        "password": MAT_KHAU,
                        "email_confirm": True,
                    },
                )
                if r.status_code not in (200, 201):
                    # Đã tồn tại thì tra lại id thay vì bỏ cuộc: script phải
                    # chạy lại được sau một lần đứt giữa chừng.
                    tra = await http.get(
                        f"{base}/auth/v1/admin/users",
                        headers={"apikey": key, "Authorization": f"Bearer {key}"},
                        params={"filter": email},
                    )
                    ds = (
                        (tra.json() or {}).get("users", [])
                        if tra.status_code == 200
                        else []
                    )
                    uid = next((u["id"] for u in ds if u.get("email") == email), None)
                    if uid is None:
                        print(f"  ✗ {email}: {r.status_code} {r.text[:120]}")
                        continue
                else:
                    uid = r.json()["id"]

                async with conn.transaction():
                    staff_id = k["staff_id"]
                    if staff_id is None:
                        staff_id = await conn.fetchval(
                            """
                            -- `staff` KHÔNG có cột clinic_id hay clinic_role:
                            -- phòng khám đến từ `clinic_membership`, còn vai
                            -- đọc từ `primary_department` (departmentToRole).
                            -- Bản đầu của script đoán theo tên cột mình mong
                            -- muốn và chết giữa chừng, để lại một tài khoản
                            -- đăng nhập không gắn hồ sơ nào.
                            INSERT INTO staff
                                (full_name, is_active, auth_user_id,
                                 primary_department, primary_location_id)
                            VALUES ($1, TRUE, $3::uuid, $4,
                                    (SELECT l.id FROM clinic_location l
                                      WHERE l.clinic_id = $2::uuid AND l.is_active
                                      ORDER BY l.created_at LIMIT 1))
                            RETURNING id::text
                            """,
                            k["ten"],
                            clinic_id,
                            uid,
                            k["vai"],
                        )
                        await conn.execute(
                            """
                            INSERT INTO clinic_membership
                                (clinic_id, staff_id, role, is_active)
                            VALUES ($1::uuid, $2::uuid, $3, TRUE)
                            ON CONFLICT (clinic_id, staff_id, role)
                            DO UPDATE SET is_active = TRUE
                            """,
                            clinic_id,
                            staff_id,
                            k["vai"],
                        )
                    else:
                        await conn.execute(
                            "UPDATE staff SET auth_user_id = $1::uuid "
                            "WHERE id = $2::uuid",
                            uid,
                            staff_id,
                        )
                print(f"  ✓ {k['vai']:<18} {k['ten']:<24} {email}")
        print("\nXong. Mật khẩu chung — BẮT đổi ngay buổi đầu.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
