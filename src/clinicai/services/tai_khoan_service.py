"""Tài khoản đăng nhập của nhân viên — phần dữ liệu của /settings/tai-khoan.

Route Next `/api/admin/users` giữ khoá quản trị GoTrue (tạo/xoá/đổi mật khẩu
người dùng GoTrue — backend không giữ khoá ấy, ADR-0012). Mọi thứ còn lại — ai
thuộc phòng khám nào, nối/gỡ `staff.auth_user_id`, khoá `app_credential`, chép
mật khẩu GoTrue sang `app_credential` (GoTrue là nguồn sự thật, xem
`dong_bo_mat_khau`), ghi nhật ký — nằm ở đây, mỗi việc MỘT giao dịch, lọc theo
phòng khám của người gọi.

THỨ TỰ VỚI GOTRUE. Thu hồi: giao dịch này chạy TRƯỚC, xoá người dùng GoTrue
SAU. Xoá GoTrue hỏng thì người dùng ấy còn đó nhưng không nối nhân viên nào —
identity.py từ chối mọi token của nó. Ngược lại (xoá GoTrue trước, giao dịch hỏng
sau) thì nhân viên trỏ vào người dùng không còn, và app_credential vẫn mở.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.services.audit import record_event
from clinicai.services.dong_bo_mat_khau import dong_bo

#: Cùng `origin` với nhật ký tài khoản cũ (`/staff/{id}/nhat-ky-tai-khoan`) để
#: màn Lịch sử thao tác gom một nhóm.
ORIGIN = "api:staff-account"

KHONG_TIM_THAY = "Nhân viên không tồn tại trong phòng khám hiện tại."
DA_CO_TAI_KHOAN = "Nhân viên này đã được nối với tài khoản khác."
CHUA_CO_TAI_KHOAN = "Nhân viên này chưa có tài khoản đăng nhập."
DA_DOI = "Tài khoản đã thay đổi; tải lại trang rồi thử lại."

# Nhân viên của phòng khám người gọi. `staff` không có clinic_id — phạm vi đi
# qua clinic_membership còn hiệu lực (cùng luật route Next cũ dùng).
_THUOC_PHONG_KHAM = """
    EXISTS (SELECT 1 FROM clinic_membership m
             WHERE m.staff_id = s.id AND m.clinic_id = $2::uuid AND m.is_active)
"""


class TaiKhoanService:
    def __init__(self, pool: asyncpg.Pool, identity: StaffIdentity) -> None:
        self._pool = pool
        self._ai = identity

    async def doc(self, staff_id: str) -> dict[str, Any]:
        """Tên + auth_user_id của một nhân viên CÙNG phòng khám, hoặc 404."""
        row = await self._pool.fetchrow(
            f"""
            SELECT s.id::text AS id, s.full_name, s.auth_user_id::text AS auth_user_id
              FROM staff s
             WHERE s.id = $1::uuid AND {_THUOC_PHONG_KHAM}
            """,
            staff_id,
            self._ai.clinic_id,
        )
        if row is None:
            # Không nói id có tồn tại ở phòng khám khác hay không.
            raise NotFoundError(KHONG_TIM_THAY)
        return dict(row)

    async def noi(self, staff_id: str, auth_user_id: str) -> dict[str, Any]:
        """Nối người dùng GoTrue vừa tạo vào nhân viên chưa có tài khoản.

        Đây cũng là đường HOÀN TÁC của thu hồi: hàng app_credential bị thu hồi
        của đúng nhân viên này được mở lại VỚI MẬT KHẨU MỚI vừa đặt ở GoTrue
        (chưa có hàng thì tạo) — trong cùng giao dịch.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                f"""
                SELECT s.full_name, s.auth_user_id
                  FROM staff s
                 WHERE s.id = $1::uuid AND {_THUOC_PHONG_KHAM}
                 FOR UPDATE OF s
                """,
                staff_id,
                self._ai.clinic_id,
            )
            if row is None:
                raise NotFoundError(KHONG_TIM_THAY)
            if row["auth_user_id"] is not None:
                raise ConflictError(DA_CO_TAI_KHOAN)
            await conn.execute(
                "UPDATE staff SET auth_user_id = $2::uuid WHERE id = $1::uuid",
                staff_id,
                auth_user_id,
            )
            dong_bo_ket = await dong_bo(conn, staff_id, mo_lai=True)
            mo_lai = dong_bo_ket["mo_lai"] > 0
            await record_event(
                conn,
                event_type="staff.account_tao",
                aggregate_type="staff",
                aggregate_id=staff_id,
                identity=self._ai,
                origin=ORIGIN,
                payload={
                    "staff_id": staff_id,
                    "hanh_dong": "tao",
                    "mo_lai_khoa_ung_dung": mo_lai,
                    "dong_bo": dong_bo_ket,
                },
            )
        return {
            "ok": True,
            "full_name": row["full_name"],
            "mo_lai_khoa_ung_dung": mo_lai,
            "dong_bo": dong_bo_ket,
        }

    async def da_doi(self, staff_id: str, hanh_dong: str) -> dict[str, Any]:
        """Sau "Đặt lại mật khẩu" / "Đổi tên đăng nhập" (GoTrue đã nhận): chép
        mật khẩu + email mới sang app_credential và ghi nhật ký — một giao dịch.

        Không mở hàng đã thu hồi (chỉ "Tạo tài khoản" mở). Không bao giờ nhận
        mật khẩu: chuỗi băm đọc thẳng từ auth.users.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            ten = await conn.fetchval(
                f"SELECT s.full_name FROM staff s WHERE s.id = $1::uuid"
                f" AND {_THUOC_PHONG_KHAM}",
                staff_id,
                self._ai.clinic_id,
            )
            if ten is None:
                raise NotFoundError(KHONG_TIM_THAY)
            dong_bo_ket = await dong_bo(conn, staff_id)
            await record_event(
                conn,
                event_type=f"staff.account_{hanh_dong}",
                aggregate_type="staff",
                aggregate_id=staff_id,
                identity=self._ai,
                origin=ORIGIN,
                payload={
                    "staff_id": staff_id,
                    "hanh_dong": hanh_dong,
                    "dong_bo": dong_bo_ket,
                },
            )
        return {"ok": True, "dong_bo": dong_bo_ket}

    async def thu_hoi(self, staff_id: str, auth_user_id: str) -> dict[str, Any]:
        """Gỡ nối + khoá app_credential + ghi nhật ký — một giao dịch.

        `auth_user_id` là tài khoản màn hình đang thấy: khác hiện tại (ai đó vừa
        gỡ/tạo lại ở tab khác) thì 409, không gỡ nhầm tài khoản mới.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                f"""
                SELECT s.full_name, s.auth_user_id::text AS auth_user_id
                  FROM staff s
                 WHERE s.id = $1::uuid AND {_THUOC_PHONG_KHAM}
                 FOR UPDATE OF s
                """,
                staff_id,
                self._ai.clinic_id,
            )
            if row is None:
                raise NotFoundError(KHONG_TIM_THAY)
            if row["auth_user_id"] is None:
                raise ConflictError(CHUA_CO_TAI_KHOAN)
            if row["auth_user_id"] != auth_user_id:
                raise ConflictError(DA_DOI)
            await conn.execute(
                "UPDATE staff SET auth_user_id = NULL WHERE id = $1::uuid",
                staff_id,
            )
            # Hàng đã thu hồi từ trước giữ nguyên dấu cũ (lúc, người) — không
            # ghi đè lịch sử bằng lần bấm sau.
            khoa = await conn.fetchval(
                """
                WITH k AS (
                    UPDATE app_credential
                       SET thu_hoi_luc = now(), thu_hoi_boi = $2::uuid,
                           updated_at = now()
                     WHERE staff_id = $1::uuid AND thu_hoi_luc IS NULL
                    RETURNING 1)
                SELECT count(*) > 0 FROM k
                """,
                staff_id,
                self._ai.staff_id,
            )
            await record_event(
                conn,
                event_type="staff.account_thu_hoi",
                aggregate_type="staff",
                aggregate_id=staff_id,
                identity=self._ai,
                origin=ORIGIN,
                payload={
                    "staff_id": staff_id,
                    "hanh_dong": "thu_hoi",
                    "auth_user_id_cu": auth_user_id,
                    "khoa_ung_dung": bool(khoa),
                },
            )
        return {"ok": True, "full_name": row["full_name"], "khoa_ung_dung": bool(khoa)}
