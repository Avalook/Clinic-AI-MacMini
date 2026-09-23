"""Bảy phiếu khám — định nghĩa theo phiên bản, cổng kiểm một lần lưu, dữ liệu đọc kèm.

GÓI NÀY KHÔNG TỰ QUYẾT BA THỨ, và cả ba được CẮM TỪ NGOÀI VÀO:

1. **Phiếu gắn vào đâu.** Bảy phiếu khám (5 chuyên khoa + Thủ thuật + Sàn chậu)
   gắn vào consultation/visit. Chỉ phiếu KẾT QUẢ DỊCH VỤ mới gắn
   `service_order`. `form_instance` hiện chỉ có `service_order_id`, nên chỗ
   lưu một lần điền phiếu khám CHƯA CÓ — INTEGRATION_BLOCKER, không vá bằng
   cách giả khám thành một chỉ định. Gói này vì thế không mở/ghi
   `form_instance` nào; nó cung cấp cổng `kiem_luu` mà chỗ lưu tương lai gọi.
2. **Hồ sơ đã chốt chưa.** Clinical shell truyền `editable` /
   `finalized_locked` / `amendment_mode` (`phieu_kham.che_do`). Gói này không
   đọc trạng thái lượt, không biết mốc chốt ở đâu.
3. **Ai được làm.** `KiemQuyen` do hệ phân quyền của CORE cung cấp. Gói này
   không thêm capability, không mượn capability của module khác.

Còn lại là việc của gói: khung theo ĐÚNG phiên bản, kiểm dữ liệu theo khoá ổn
định (không so tên), phần mang sang, kết quả CLS theo `service_order_id`.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.phieu_kham.che_do import doi_ghi_duoc
from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.phieu_kham.khung import kiem_du_lieu, la_phieu_kham
from clinicai.phieu_kham.mang_sang import doc_dau_phieu

#: Việc cần hỏi quyền. Đây là NHÃN của lời hỏi gửi sang hệ phân quyền, không
#: phải capability — ánh xạ sang capability nào là việc của CORE.
HanhDong = Literal["doc_phieu", "ghi_phieu", "doc_ket_qua_cls"]

#: Hệ phân quyền của CORE: không có quyền thì RAISE (SafetyGateError).
KiemQuyen = Callable[[asyncpg.Connection, StaffIdentity, HanhDong], Awaitable[None]]


async def chua_noi_quyen(
    conn: asyncpg.Connection, identity: StaffIdentity, hanh_dong: HanhDong
) -> None:
    """Mặc định khi CHƯA nối hệ phân quyền: chặn tất. Đóng khi nghi ngờ."""
    raise SafetyGateError(f"Phiếu khám chưa được nối với hệ phân quyền ({hanh_dong}).")


class PhieuKhamService:
    def __init__(self, pool: asyncpg.Pool, *, kiem_quyen: KiemQuyen) -> None:
        self._pool = pool
        self._kiem_quyen = kiem_quyen

    # ------------------------------------------------------------------
    async def khung_theo_ban(
        self, *, form_id: str, version: int | None, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Khung của MỘT phiên bản (hoặc bản đang dùng nếu `version` None).

        Phiếu đã bắt đầu điền thì ghim phiên bản của nó: xuất bản v2 thêm một
        ô thì phiếu v1 vẫn không có ô ấy.
        """
        if not la_phieu_kham(form_id):
            raise ValidationError(f"“{form_id}” không phải phiếu khám.")
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            dong = await conn.fetchrow(
                "SELECT form_id, version, ten, khung FROM form_definition"
                " WHERE clinic_id = $1::uuid AND form_id = $2"
                "   AND (($3::int IS NULL AND trang_thai = 'PUBLISHED')"
                "        OR version = $3::int)",
                identity.clinic_id,
                form_id,
                version,
            )
        if dong is None:
            ban = f" v{version}." if version is not None else " nào đang dùng."
            raise ValidationError(f"Phiếu “{form_id}” chưa có bản{ban}")
        return {
            "form_id": dong["form_id"],
            "version": dong["version"],
            "ten": dong["ten"],
            "khung": json.loads(dong["khung"]),
        }

    async def kiem_luu(
        self,
        *,
        form_id: str,
        version: int,
        du_lieu: dict[str, Any],
        che_do: object,
        identity: StaffIdentity,
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
        """Cổng một lần lưu — chỗ lưu phiếu khám (khi có) gọi TRƯỚC khi ghi.

        Thứ tự có chủ ý: chế độ trước (hồ sơ đã chốt thì không cần biết dữ liệu
        đúng hay sai), rồi quyền, rồi khung đúng phiên bản, rồi từng ô.
        """
        doi_ghi_duoc(che_do)
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "ghi_phieu")
        ban = await self.khung_theo_ban(
            form_id=form_id, version=version, identity=identity
        )
        return kiem_du_lieu(ban["khung"], du_lieu)

    # ------------------------------------------------------------------
    async def dau_phieu(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            return await doc_dau_phieu(
                conn, clinic_id=identity.clinic_id, visit_id=visit_id
            )

    async def ket_qua_chi_dinh(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_ket_qua_cls")
            return await doc_ket_qua_theo_chi_dinh(
                conn, clinic_id=identity.clinic_id, visit_id=visit_id
            )


__all__ = ["HanhDong", "KiemQuyen", "PhieuKhamService", "chua_noi_quyen"]
