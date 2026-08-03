"""Sức chứa để VẼ, đọc từ đúng nguồn mà trigger dùng để CHẶN.

VÌ SAO FILE NÀY ĐƯỢC VIẾT LẠI.

Trước đây có hai hệ sức chứa chạy song song:

    block_budget            42 dòng, độ mịn theo GIỜ, chỉ dùng để TÔ MÀU ô lịch
    3 tầng override         độ mịn theo PHÚT, là thứ trigger THI HÀNH

Không ai đối chiếu chúng. Lưới có thể vẽ "còn chỗ" trong khi trigger từ chối, và
người dùng chỉ biết sau khi bấm — đúng loại mâu thuẫn im lặng mà cả đợt rà soát
này đi tìm, chỉ là ở một cặp khác.

`block_budget` còn mang một mô hình khác hẳn: ngân sách PHÚT ("bác sĩ có 60 phút
mỗi giờ, khách mới ăn 15 phút"). Mô hình đó đã bị bỏ — thời lượng khám giờ là số
liệu ĐO ĐƯỢC (v_consultation_duration), còn giới hạn đặt lịch là SỐ CHỖ do Trưởng
ca cấu hình. Giữ lại một hệ tô màu theo mô hình đã bỏ nghĩa là màn hình nói một
thứ mà hệ thống không còn tin.

Giờ chỉ còn một nguồn: `resolve_effective_cap()` — cùng hàm, cùng tham số, cùng
phòng khám và cùng bác sĩ mà `enforce_slot_capacity()` gọi khi nó quyết định
nhận hay từ chối. Nếu lưới nói còn chỗ thì đặt được; nếu nói đầy thì đúng là đầy.
"""

from __future__ import annotations

from typing import Any, Literal

import asyncpg
import structlog

logger = structlog.get_logger()

CellState = Literal["free", "few", "full", "closed"]

# Còn đúng một chỗ = "còn ít". Ngưỡng tính theo CHỖ, không theo phần trăm: với
# trần 3 thì 66% nghe như còn nhiều, mà thực tế chỉ còn một người nữa là hết.
FEW_REMAINING = 1


class CapacityService:
    """Sức chứa từng khung trong ngày, để giao diện tô màu ô lịch."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def quote(
        self,
        *,
        date: str,
        location_id: str,
        doctor_id: str | None,
        clinic_id: str,
    ) -> dict[str, Any]:
        """Trả về từng khung của ngày với sức chứa và mức đã dùng.

        ``date`` là ngày giờ VN, dạng ``YYYY-MM-DD``.

        Một truy vấn duy nhất: giờ mở cửa → sinh các mốc khung → sức chứa hiệu
        lực của từng mốc → đếm lịch còn sống. Gọi resolve_effective_cap trong
        vòng lặp Python cũng ra kết quả ấy nhưng tốn một vòng mạng cho mỗi khung,
        và mở ra khả năng hai khung đọc hai trạng thái khác nhau giữa chừng.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH hours AS (
                    SELECT open_minute, close_minute
                      FROM clinic_hours_for_date($1::uuid, $2::date)
                ),
                -- Độ dài khung đến từ chính resolver, đọc ở mốc mở cửa. Nó có
                -- thể do bác sĩ này quy định (tầng 2), nên không dùng mặc định
                -- phòng khám ở đây.
                step AS (
                    SELECT r.slot_minutes
                      FROM hours h
                      CROSS JOIN LATERAL resolve_effective_cap(
                          $1::uuid, $3::uuid,
                          ($2::date + make_interval(mins => h.open_minute))
                              AT TIME ZONE 'Asia/Ho_Chi_Minh') r
                ),
                slots AS (
                    SELECT generate_series(
                               h.open_minute,
                               h.close_minute - 1,
                               s.slot_minutes) AS minute_of_day,
                           s.slot_minutes
                      FROM hours h CROSS JOIN step s
                )
                SELECT sl.minute_of_day,
                       sl.slot_minutes,
                       cap.regular_cap,
                       cap.walkin_cap,
                       coalesce(used.regular_used, 0) AS regular_used,
                       coalesce(used.walkin_used, 0)  AS walkin_used
                  FROM slots sl
                  CROSS JOIN LATERAL resolve_effective_cap(
                      $1::uuid, $3::uuid,
                      ($2::date + make_interval(mins => sl.minute_of_day))
                          AT TIME ZONE 'Asia/Ho_Chi_Minh') cap
                  LEFT JOIN LATERAL (
                      SELECT
                        count(*) FILTER (
                            WHERE upper(coalesce(a.booking_channel,'')) <> 'WALK_IN'
                        ) AS regular_used,
                        count(*) FILTER (
                            WHERE upper(coalesce(a.booking_channel,'')) =  'WALK_IN'
                        ) AS walkin_used
                        FROM appointment a
                       WHERE a.clinic_id = $1::uuid
                         AND a.location_id = $4::uuid
                         AND ($3::uuid IS NULL OR a.doctor_id = $3::uuid)
                         -- Cùng cách gom khung mà trigger dùng: mốc bắt đầu rơi
                         -- vào [khung, khung + độ dài).
                         AND a.slot_start >= ($2::date
                                 + make_interval(mins => sl.minute_of_day))
                                 AT TIME ZONE 'Asia/Ho_Chi_Minh'
                         AND a.slot_start <  ($2::date + make_interval(
                                 mins => sl.minute_of_day + sl.slot_minutes))
                                 AT TIME ZONE 'Asia/Ho_Chi_Minh'
                         -- Trạng thái chết không giữ chỗ — cùng danh sách với
                         -- DEAD_STATUSES ở booking_service và enforce_slot_capacity.
                         AND a.status NOT IN ('CANCELLED','NO_SHOW','DOCTOR_DECLINED')
                  ) used ON TRUE
                 ORDER BY sl.minute_of_day
                """,
                clinic_id,
                date,
                doctor_id,
                location_id,
            )

        slots_out = [
            {
                "time": _hhmm(r["minute_of_day"]),
                "minute_of_day": r["minute_of_day"],
                "slot_minutes": r["slot_minutes"],
                "regular_cap": r["regular_cap"],
                "walkin_cap": r["walkin_cap"],
                "regular_used": r["regular_used"],
                "walkin_used": r["walkin_used"],
                "state": cell_state(r["regular_cap"], r["regular_used"]),
            }
            for r in rows
        ]

        return {
            "date": date,
            "location_id": location_id,
            "doctor_id": doctor_id,
            # Rỗng = phòng khám đóng cửa ngày đó (clinic_hours_for_date không
            # trả dòng nào). Khác hẳn "mở cửa nhưng hết chỗ", và giao diện phải
            # nói được hai điều đó bằng hai câu khác nhau.
            "closed": not slots_out,
            "slots": slots_out,
        }


def cell_state(regular_cap: int, regular_used: int) -> CellState:
    """Trạng thái ô để tô màu — theo CHỖ ĐẶT HẸN, không tính chỗ vãng lai.

    Chỗ vãng lai là phần để dành cho khách đến thẳng quầy; đếm nó vào ô mà CSKH
    nhìn khi đặt trước sẽ khiến khung trông còn chỗ trong khi phần đặt trước đã
    hết — và trigger sẽ từ chối đúng lượt đặt tiếp theo.
    """
    if regular_used >= regular_cap:
        return "full"
    if regular_cap - regular_used <= FEW_REMAINING:
        return "few"
    return "free"


def _hhmm(minute_of_day: int) -> str:
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"
