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

from datetime import date as _date
from typing import Any, Literal

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.core.shifts import (
    ca_tu_settings,
    covers,
    merge_windows,
    shift_windows,
)

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
        # ĐỔI SANG date THẬT TRƯỚC KHI GỬI XUỐNG. Tham số `$2::date` khiến
        # Postgres khai kiểu là date, và asyncpg KHÔNG tự đọc chuỗi cho kiểu đó
        # — nó gọi thẳng .toordinal() và ném AttributeError, thành lỗi 500.
        #
        # Chỗ này 500 suốt mà không ai thấy: endpoint /appointments/quote bị
        # route `{id}` nuốt nên chưa bao giờ chạy tới đây, và mọi test đều gọi
        # cell_state() — hàm thuần — chứ không đi qua asyncpg. Nó chỉ lộ ra
        # đúng lúc lưới đặt lịch bắt đầu gọi thật.
        try:
            day = _date.fromisoformat(date)
        except ValueError as exc:
            raise ValidationError(
                f"Ngày không hợp lệ: {date!r}. Định dạng đúng là YYYY-MM-DD."
            ) from exc

        async with self._pool.acquire() as conn:
            # LỊCH TRỰC LÀ LUẬT CAO NHẤT — cao hơn cả ba tầng sức chứa.
            #
            # Một luật "BS Thành 18:00–18:15 tám chỗ" không có nghĩa gì vào ngày
            # bác sĩ ấy không đi làm. Trước đây lưới không hỏi lịch trực lần
            # nào: nó mời CSKH đặt vào một buổi chiều mà bác sĩ không có mặt, và
            # sai đó chỉ vỡ ra lúc bệnh nhân đã tới nơi.
            #
            # Chỉ có hiệu lực KHI TUẦN ĐÓ ĐÃ ĐƯỢC ÁP DỤNG — không phải khi
            # "có dòng trong bảng". Một tuần trải sẵn từ mẫu là bản nháp; khoá
            # ô đặt lịch dựa trên bản nháp là từ chối khách vì một quyết định
            # chưa ai ra. Xem migration 20260808000001. CSKH đặt trước cả tháng,
            # lúc ấy lịch trực chưa có — coi "chưa xếp" là "không đi làm" sẽ
            # khoá sạch tương lai. Cùng cách phân biệt mà booking_service dùng
            # cho câu cảnh báo của nó, để hai nơi không nói hai điều khác nhau.
            # KHÔNG lọc theo TRẠM (quyết định của Quang, 2026-08-04): có tên
            # trong lịch trực hôm đó là nhận đặt được, dù trạm ghi là MAY_TRONG
            # hay LICH_KHAM. BSNT. Khánh Linh là ví dụ có thật.
            duty = await conn.fetchrow(
                """
                SELECT
                  EXISTS (
                    SELECT 1 FROM work_roster
                     WHERE clinic_id = $1::uuid AND work_date = $2
                       AND status = 'APPROVED'
                   AND EXISTS (
                     SELECT 1 FROM roster_week rw
                      WHERE rw.clinic_id = work_roster.clinic_id
                        AND rw.week_start = work_roster.week_start
                   )
                  ) AS roster_known,
                  coalesce((
                    SELECT array_agg(DISTINCT shift) FROM work_roster
                     WHERE clinic_id = $1::uuid AND work_date = $2
                       AND staff_id = $3::uuid
                       AND status = 'APPROVED'
                   AND EXISTS (
                     SELECT 1 FROM roster_week rw
                      WHERE rw.clinic_id = work_roster.clinic_id
                        AND rw.week_start = work_roster.week_start
                   )
                  ), ARRAY[]::text[]) AS shifts,
                  (SELECT open_minute FROM clinic_hours_for_date($1::uuid, $2))
                    AS open_minute,
                  (SELECT close_minute FROM clinic_hours_for_date($1::uuid, $2))
                    AS close_minute,
                  -- Giờ ca của phòng khám. Bản trước ĐỌC `duty["settings"]` mà
                  -- KHÔNG chọn cột này, nên asyncpg ném KeyError ngay khi chọn
                  -- một bác sĩ có lịch trực đã duyệt — tức là đường đi thường
                  -- nhất của màn đặt lịch. Test không bắt được vì dòng giả lập
                  -- là dict do chính bài kiểm dựng, và dict thì có đủ khoá mình
                  -- tự cho vào; asyncpg.Record thì không.
                  (SELECT settings FROM clinic WHERE id = $1::uuid) AS settings
                """,
                clinic_id,
                day,
                doctor_id,
            )
            roster_known = bool(duty and duty["roster_known"])
            shifts: list[str] = list(duty["shifts"]) if duty else []
            # doctor_id = None nghĩa là "lưới chung, không lọc bác sĩ" — không
            # có ai để tra ca trực, và không được coi đó là nghỉ.
            on_duty = doctor_id is None or bool(shifts)
            off_duty = roster_known and not on_duty
            if off_duty:
                return {
                    "date": date,
                    "location_id": location_id,
                    "doctor_id": doctor_id,
                    "closed": True,
                    "off_duty": True,
                    "roster_known": True,
                    "shift_windows": [],
                    "slots": [],
                }

            # CA SÁNG KHÔNG PHẢI CẢ NGÀY. Bản trước dừng ở mức NGÀY, nên BS
            # Thành chỉ trực ca sáng ngày 08/08 vẫn được mời đặt lúc 18:00 —
            # luật lịch trực đúng một nửa còn khó chịu hơn không có, vì nó tạo
            # cảm giác đã được kiểm.
            open_min = duty["open_minute"] if duty else None
            close_min = duty["close_minute"] if duty else None
            ca = ca_tu_settings(duty["settings"] if duty else None)

            # KHUNG CỦA PHÒNG KHÁM — dùng khi CHƯA chọn bác sĩ.
            #
            # Giờ mở cửa (07:00–22:00) rộng hơn tổng ba ca, nên lưới dựng theo
            # giờ mở cửa mời cả những khung không thuộc ca nào: sớm hơn ca
            # sáng, nghỉ trưa, sau ca tối. Từ 21/08/2026 `booking_service`
            # TỪ CHỐI đúng những khung ấy — mời rồi mới mắng là cách chắc chắn
            # nhất để người trực mất niềm tin vào lưới.
            khung_phong_kham: list[tuple[int, int]] = []
            if open_min is not None and close_min is not None:
                khung_phong_kham = shift_windows("FULL", open_min, close_min, ca)

            windows: list[tuple[int, int]] = []
            if shifts and open_min is not None and close_min is not None:
                windows = merge_windows(
                    [
                        w
                        for s in shifts
                        for w in shift_windows(s, open_min, close_min, ca)
                    ]
                )

            # Ca trực của bác sĩ đã hẹp hơn khung phòng khám; không có bác sĩ
            # thì lấy khung phòng khám. `windows` vẫn giữ nguyên nghĩa "ca trực
            # của người này" cho `partial_shift` và cho màn hình.
            khung_loc = windows or khung_phong_kham

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
                  -- Phép đếm nằm ở `slot_seats_used()` — CÙNG hàm mà trigger
                  -- gọi khi nó nhận hay từ chối. Trước đây chỗ này tự đếm bằng
                  -- SQL riêng, và luật vừa đổi: một ghế vãng lai nay có thể bị
                  -- một khách có hẹn ĐẾN MUỘN chiếm (20260807000001). Hai bản
                  -- chép tay của một luật thì bản nào cũng sẽ lỡ mất lần sửa
                  -- tiếp theo.
                  LEFT JOIN LATERAL (
                      SELECT
                        slot_seats_used(
                            $1::uuid, $3::uuid,
                            ($2::date + make_interval(mins => sl.minute_of_day))
                                AT TIME ZONE 'Asia/Ho_Chi_Minh',
                            ($2::date + make_interval(
                                mins => sl.minute_of_day + sl.slot_minutes))
                                AT TIME ZONE 'Asia/Ho_Chi_Minh',
                            FALSE, NULL, $4::uuid) AS regular_used,
                        slot_seats_used(
                            $1::uuid, $3::uuid,
                            ($2::date + make_interval(mins => sl.minute_of_day))
                                AT TIME ZONE 'Asia/Ho_Chi_Minh',
                            ($2::date + make_interval(
                                mins => sl.minute_of_day + sl.slot_minutes))
                                AT TIME ZONE 'Asia/Ho_Chi_Minh',
                            TRUE, NULL, $4::uuid) AS walkin_used
                  ) used ON TRUE
                 ORDER BY sl.minute_of_day
                """,
                clinic_id,
                day,
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
            # Ngoài ca trực thì khung đó không tồn tại với bác sĩ này. Bỏ hẳn
            # khỏi danh sách chứ không đánh dấu "đầy": đầy là hết chỗ, còn đây
            # là không có mặt, và hai thứ đó cần hai cách xử lý khác nhau.
            if not khung_loc or covers(khung_loc, r["minute_of_day"])
        ]

        return {
            "date": date,
            "location_id": location_id,
            "doctor_id": doctor_id,
            # Rỗng = phòng khám đóng cửa ngày đó (clinic_hours_for_date không
            # trả dòng nào). Khác hẳn "mở cửa nhưng hết chỗ", và giao diện phải
            # nói được hai điều đó bằng hai câu khác nhau.
            "closed": not slots_out,
            # Ba câu khác nhau, đừng gộp: "phòng khám đóng cửa", "bác sĩ không
            # có ca trực", "còn chỗ". Gộp thành một ô xám thì người dùng không
            # biết nên đổi NGÀY hay đổi BÁC SĨ.
            "off_duty": False,
            "roster_known": roster_known,
            # Ca trực của bác sĩ hôm đó, để màn hình nói được "chỉ trực buổi
            # sáng" thay vì im lặng bỏ bớt nửa lưới.
            "shift_windows": [list(w) for w in windows],
            # CÓ PHẢI CA LẺ KHÔNG — tính ở đây vì chỉ ở đây mới biết giờ mở
            # cửa. Để trình duyệt tự suy ra (đếm số ô rồi so với lưới) là một
            # phép đoán gián tiếp, sai mỗi khi lưới đổi vì lý do khác.
            "partial_shift": bool(windows) and windows != [(open_min, close_min)],
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
