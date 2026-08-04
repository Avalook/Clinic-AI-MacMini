"""Số liệu báo cáo — gộp những chỗ đang đếm theo kiểu N+1.

NGUỒN ĐẶT LỊCH. Trang báo cáo trước đây lấy danh sách kênh đặt lịch (7 dòng),
rồi bắn MỘT truy vấn đếm cho TỪNG kênh, cộng một truy vấn nữa cho kênh trống —
8 lượt PostgREST cho một con số mà `GROUP BY` trả trong một lượt. Số truy vấn
lớn dần theo số kênh, nên thêm một kênh Zalo mới là thêm một lượt mạng.

`GROUP BY` cũng đúng hơn về mặt số liệu: 8 truy vấn rời chạy ở 8 thời điểm khác
nhau, nên tổng các phần có thể không bằng tổng — một lịch hẹn đặt xen vào giữa
sẽ được đếm hoặc bị bỏ tuỳ thứ tự.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import asyncpg
import structlog

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ

logger = structlog.get_logger()


class ReportsService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def booking_channels(
        self, *, identity: StaffIdentity, days: int = 30
    ) -> dict[str, Any]:
        """Lịch hẹn theo nguồn đặt, trong `days` ngày gần nhất.

        Trả về CẢ kênh có 0 lịch (join từ danh mục) — một kênh biến mất khỏi
        biểu đồ trông giống như chưa từng khai, khác hẳn với "kênh này tháng
        này không ai đặt".
        """
        end = datetime.now(CLINIC_TZ).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        start = end - timedelta(days=days)

        rows = await self._pool.fetch(
            """
            SELECT c.code,
                   c.name,
                   count(a.id) AS n
              FROM public.booking_channel c
              LEFT JOIN public.appointment a
                     ON a.booking_channel = c.code
                    AND a.clinic_id = $1::uuid
                    AND a.slot_start >= $2 AND a.slot_start < $3
             GROUP BY c.code, c.name
             ORDER BY n DESC, c.name
            """,
            identity.clinic_id,
            start,
            end,
        )

        # Hai nhóm KHÔNG nằm trong danh mục, và chúng khác nhau:
        #   - chưa khai kênh  (booking_channel IS NULL)
        #   - khai một chuỗi không có trong danh mục ("Zalo" vs "ZALO_PK")
        # Gộp hai thứ này lại thì không ai biết là quên nhập hay nhập sai.
        extra = await self._pool.fetchrow(
            """
            SELECT count(*) FILTER (WHERE a.booking_channel IS NULL) AS chua_khai,
                   count(*) FILTER (
                       WHERE a.booking_channel IS NOT NULL
                         AND NOT EXISTS (SELECT 1 FROM public.booking_channel c
                                          WHERE c.code = a.booking_channel)
                   ) AS ngoai_danh_muc
              FROM public.appointment a
             WHERE a.clinic_id = $1::uuid
               AND a.slot_start >= $2 AND a.slot_start < $3
            """,
            identity.clinic_id,
            start,
            end,
        )

        return {
            "items": [
                {"code": r["code"], "name": r["name"], "count": r["n"]} for r in rows
            ],
            "unset": extra["chua_khai"],
            "unknown": extra["ngoai_danh_muc"],
        }
