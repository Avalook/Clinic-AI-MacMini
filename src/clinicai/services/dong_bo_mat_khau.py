"""Mật khẩu GoTrue → app_credential, một chiều (GoTrue là nguồn sự thật).

Luật đồng bộ nằm trong hàm SQL `dong_bo_app_credential` (migration
20261006420000) — ở đó mới khoá dòng được. File này chỉ gọi nó: từ
`TaiKhoanService` ngay sau thao tác tài khoản, và từ vòng `su-kien` mỗi phút để
bắt mọi lối khác (script nhân sự, tự đổi mật khẩu ở /reset-password, lời gọi
hỏng giữa chừng).
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()

NHIP_GIAY = 60


async def dong_bo(
    conn: asyncpg.Connection | asyncpg.Pool,
    staff_id: str | None = None,
    *,
    mo_lai: bool = False,
) -> dict[str, int]:
    """Một lượt đồng bộ → {them, sua, mo_lai, trung_email}.

    `mo_lai` CHỈ dành cho "Tạo tài khoản" (nối lại có chủ ý) của đúng `staff_id`.
    Gọi trong giao dịch của người gọi thì chung giao dịch ấy.
    """
    row: Any = await conn.fetchrow(
        "SELECT * FROM public.dong_bo_app_credential($1::uuid, $2::boolean)",
        staff_id,
        mo_lai,
    )
    return {k: int(row[k]) for k in ("them", "sua", "mo_lai", "trung_email")}


async def mot_vong(pool: asyncpg.Pool) -> dict[str, int] | None:
    """Lượt định kỳ cho mọi nhân viên. KHÔNG BAO GIỜ ném (vòng su-kien phải sống).

    Có thay đổi thì ghi log; 0 thay đổi thì im. Hỏng → kho lỗi `loi_nhom`.
    """
    try:
        ket = await dong_bo(pool)
    except Exception as exc:  # noqa: BLE001 — một việc phụ không được làm chết worker
        logger.exception("dong_bo_app_credential_loi")
        from clinicai.services.kho_loi import ghi_loi

        await ghi_loi(pool, nguon="worker", vi_tri="dong_bo_app_credential", exc=exc)
        return None
    if ket["trung_email"]:
        # Lặp mỗi phút tới khi có người gỡ trùng — đúng ý: việc cần người xử lý.
        logger.warning("dong_bo_app_credential", **ket)
    elif any(ket.values()):
        logger.info("dong_bo_app_credential", **ket)
    return ket
