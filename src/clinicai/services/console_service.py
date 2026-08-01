"""Số liệu cho Bảng điều khiển của chủ sản phẩm.

Gom mọi thứ cần nhìn vào MỘT chỗ, thay vì phải mở docker ps, đọc log, gõ psql
rồi tự ghép lại trong đầu. Mỗi khối là một câu hỏi thật: hệ đang gánh bao nhiêu
việc, ai đăng nhập được, đã báo lỗi gì mà chưa sửa.

Mỗi khối chịu lỗi riêng: một truy vấn hỏng thì khối đó trả None và trang vẫn vẽ
phần còn lại. Một bảng điều khiển chết cả trang vì một số liệu là bảng điều
khiển vô dụng đúng lúc cần nó nhất.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()


class ConsoleService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _safe(self, sql: str, *args: Any) -> list[dict[str, Any]] | None:
        try:
            rows = await self._pool.fetch(sql, *args)
            return [dict(r) for r in rows]
        except Exception as exc:  # noqa: BLE001 - một khối hỏng không được giết cả trang
            logger.warning("console_block_failed", error=str(exc)[:200])
            return None

    async def overview(self, *, clinic_id: str) -> dict[str, Any]:
        workload = await self._safe(
            """
            SELECT n.workspace,
                   count(*) FILTER (WHERE w.status = 'PENDING')::int     AS pending,
                   count(*) FILTER (WHERE w.status = 'IN_PROGRESS')::int AS in_progress,
                   count(*) FILTER (WHERE EXISTS (
                       SELECT 1 FROM work_item_gate_blockers(w.id, 'start')
                   ))::int AS blocked
              FROM work_item w
              JOIN node_definition n
                ON n.code = w.node_code AND n.clinic_id = w.clinic_id
             WHERE w.clinic_id = $1::uuid
               AND w.status IN ('PENDING', 'IN_PROGRESS')
               AND n.workspace IS NOT NULL
             GROUP BY n.workspace
             ORDER BY n.workspace
            """,
            clinic_id,
        )

        accounts = await self._safe(
            """
            SELECT u.email,
                   s.full_name,
                   m.role,
                   (s.id IS NULL) AS is_gate
              FROM auth.users u
              LEFT JOIN staff s ON s.auth_user_id = u.id AND s.is_active
              LEFT JOIN clinic_membership m
                ON m.staff_id = s.id AND m.is_active AND m.clinic_id = $1::uuid
             ORDER BY (s.id IS NULL) DESC, m.role NULLS LAST, u.email
            """,
            clinic_id,
        )

        totals = await self._safe(
            """
            SELECT
              (SELECT count(*) FROM patient
                WHERE clinic_id = $1::uuid AND is_active)::int AS benh_nhan,
              (SELECT count(*) FROM appointment
                WHERE clinic_id = $1::uuid
                  AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                      = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)::int
                AS lich_hom_nay,
              (SELECT count(*) FROM visit
                WHERE clinic_id = $1::uuid AND status = 'OPEN')::int
                AS luot_dang_mo,
              (SELECT count(*) FROM work_item
                WHERE clinic_id = $1::uuid
                  AND status IN ('PENDING', 'IN_PROGRESS'))::int
                AS viec_dang_mo,
              (SELECT count(*) FROM service_price
                WHERE clinic_id = $1::uuid AND active
                  AND unit_price IS NOT NULL)::int AS dich_vu_co_gia,
              (SELECT count(*) FROM service_price
                WHERE clinic_id = $1::uuid AND active)::int AS dich_vu_tong
            """,
            clinic_id,
        )

        feedback = await self._safe(
            """
            SELECT id::text, created_at, page_url, role_at_time, comment,
                   severity, status, image_path
              FROM owner_feedback
             ORDER BY (status = 'moi') DESC, created_at DESC
             LIMIT 20
            """
        )

        return {
            "workload": workload,
            "accounts": accounts,
            "totals": totals[0] if totals else None,
            "feedback": feedback,
        }

    async def add_feedback(
        self,
        *,
        comment: str,
        severity: str,
        page_url: str | None,
        role_at_time: str | None,
        staff_name: str | None,
        image_path: str | None,
    ) -> str:
        row = await self._pool.fetchrow(
            """
            INSERT INTO owner_feedback
                (comment, severity, page_url, role_at_time, staff_name, image_path)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id::text
            """,
            comment,
            severity,
            page_url,
            role_at_time,
            staff_name,
            image_path,
        )
        logger.info("owner_feedback_added", severity=severity, page=page_url)
        return str(row["id"])
