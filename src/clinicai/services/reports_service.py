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

    async def kpi_dat_lich_theo_nhan_vien(
        self, *, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Mỗi người đặt được bao nhiêu lịch — hôm nay, tuần này, tháng này.

        AI ĐẶT LỊCH ĐỌC TỪ SỔ SỰ KIỆN, KHÔNG TỪ BẢNG LỊCH HẸN. `appointment`
        không có cột người tạo (chỉ có `cancelled_by_staff_id` cho người huỷ),
        nên câu hỏi "ai đặt cái này" chỉ trả lời được qua `event_log`: mỗi lần
        đặt ghi một dòng `appointment.created` kèm `metadata.clinic_staff_id`.
        Đo trên staging 14/08/2026: 59/59 dòng đều có trường ấy.

        Hệ quả phải nói ra: lịch đặt TRƯỚC khi sổ bắt đầu ghi người thực hiện sẽ
        không có tên ai. Chúng rơi vào dòng "không rõ người đặt" thay vì bị bỏ
        im lặng — một bảng KPI thiếu vài chục lịch mà không nói gì là bảng khiến
        người ta cãi nhau về con số.

        TÁI KHÁM = CÓ MẮT XÍCH `lich_truoc_id`, đúng cùng một luật với nhãn ở màn
        đặt lịch. Không suy từ "khách này đã khám lần nào chưa": một khách cũ đặt
        một dịch vụ hoàn toàn mới thì đó là lịch khám mới, không phải tái khám.

        MỘT TRUY VẤN CHO CẢ BA KHOẢNG. Ba câu riêng chạy ở ba thời điểm khác
        nhau thì tổng ngày có thể không nằm trong tổng tuần — và người đọc sẽ
        tin vào con số lệch ấy.
        """
        bay_gio = datetime.now(CLINIC_TZ)
        dau_ngay = bay_gio.replace(hour=0, minute=0, second=0, microsecond=0)
        # Tuần bắt đầu THỨ HAI, cùng quy ước với lịch làm việc và với
        # `currentWeekStartVn()` ở giao diện. Chủ nhật là cuối tuần, không phải
        # đầu tuần — hai chỗ hiểu khác nhau thì con số tuần không khớp nhau.
        dau_tuan = dau_ngay - timedelta(days=dau_ngay.weekday())
        dau_thang = dau_ngay.replace(day=1)

        rows = await self._pool.fetch(
            """
            WITH dat AS (
                SELECT e.metadata->>'clinic_staff_id' AS staff_id,
                       e.occurred_at,
                       (a.lich_truoc_id IS NOT NULL)  AS la_tai_kham
                  FROM public.event_log e
                  JOIN public.appointment a
                    -- CẢ HAI ĐỀU LÀ `uuid`. Bản đầu viết `a.id::text =
                    -- e.aggregate_id` và Postgres từ chối thẳng ("operator does
                    -- not exist: text = uuid") — bắt được vì chạy thử trên dữ
                    -- liệu thật, chứ `tsc` lẫn `mypy` đều không đọc được bên
                    -- trong một chuỗi SQL.
                    ON a.id = e.aggregate_id
                   AND a.clinic_id = e.clinic_id
                 WHERE e.clinic_id = $1::uuid
                   AND e.event_type = 'appointment.created'
                   AND e.occurred_at >= $2
            )
            SELECT COALESCE(s.full_name, '(không rõ người đặt)') AS ten,
                   s.primary_department                          AS bo_phan,
                   count(*) FILTER (
                     WHERE d.occurred_at >= $4
                   ) AS ngay,
                   count(*) FILTER (
                     WHERE d.occurred_at >= $4 AND d.la_tai_kham
                   ) AS ngay_tai_kham,
                   count(*) FILTER (
                     WHERE d.occurred_at >= $3
                   ) AS tuan,
                   count(*) FILTER (
                     WHERE d.occurred_at >= $3 AND d.la_tai_kham
                   ) AS tuan_tai_kham,
                   count(*) AS thang,
                   count(*) FILTER (WHERE d.la_tai_kham) AS thang_tai_kham
              FROM dat d
              LEFT JOIN public.staff s ON s.id::text = d.staff_id
             GROUP BY s.full_name, s.primary_department
             ORDER BY thang DESC, ten
            """,
            identity.clinic_id,
            dau_thang,
            dau_tuan,
            dau_ngay,
        )

        return {
            "moc": {
                "dau_ngay": dau_ngay.isoformat(),
                "dau_tuan": dau_tuan.isoformat(),
                "dau_thang": dau_thang.isoformat(),
            },
            "items": [
                {
                    "ten": r["ten"],
                    "bo_phan": r["bo_phan"],
                    # Khám mới = tổng trừ tái khám. Tính ở đây chứ không bắt
                    # giao diện trừ: hai chỗ cùng làm một phép trừ là hai chỗ có
                    # thể trừ khác nhau.
                    "ngay": {
                        "tong": r["ngay"],
                        "tai_kham": r["ngay_tai_kham"],
                        "kham_moi": r["ngay"] - r["ngay_tai_kham"],
                    },
                    "tuan": {
                        "tong": r["tuan"],
                        "tai_kham": r["tuan_tai_kham"],
                        "kham_moi": r["tuan"] - r["tuan_tai_kham"],
                    },
                    "thang": {
                        "tong": r["thang"],
                        "tai_kham": r["thang_tai_kham"],
                        "kham_moi": r["thang"] - r["thang_tai_kham"],
                    },
                }
                for r in rows
            ],
        }

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
