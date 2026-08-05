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

# Cho phép sử dụng cú pháp type hint hiện đại (Python 3.10+)
from __future__ import annotations

# Nhập lớp date từ module datetime (đổi tên thành _date để tránh xung đột)
from datetime import date as _date
# Nhập Any và Literal từ typing
from typing import Any, Literal

# Nhập thư viện asyncpg để kết nối PostgreSQL bất đồng bộ
import asyncpg
# Nhập thư viện structlog để ghi log có cấu trúc
import structlog

# Nhập ValidationError từ exceptions
from clinicai.api.exceptions import ValidationError
# Nhập các hàm xử lý ca trực: covers, merge_windows, shift_window
from clinicai.core.shifts import covers, merge_windows, shift_window

# Tạo logger structlog cho module này
logger = structlog.get_logger()

# Định nghĩa kiểu dữ liệu trạng thái ô lịch: trống, còn ít, đầy, đóng cửa
CellState = Literal["free", "few", "full", "closed"]

# Còn đúng một chỗ = "còn ít". Ngưỡng tính theo CHỖ, không theo phần trăm: với
# trần 3 thì 66% nghe như còn nhiều, mà thực tế chỉ còn một người nữa là hết.
FEW_REMAINING = 1  # Số chỗ còn lại để coi là "còn ít"


class CapacityService:
    """Sức chứa từng khung trong ngày, để giao diện tô màu ô lịch."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        # Lưu connection pool database
        self._pool = pool

    async def quote(
        self,
        *,
        date: str,  # Ngày cần báo giá (dạng YYYY-MM-DD)
        location_id: str,  # ID cơ sở
        doctor_id: str | None,  # ID bác sĩ, có thể null
        clinic_id: str,  # ID phòng khám
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
            # Chuyển chuỗi ngày thành đối tượng date
            day = _date.fromisoformat(date)
        except ValueError as exc:
            # Nếu ngày không hợp lệ thì ném lỗi validation
            raise ValidationError(
                f"Ngày không hợp lệ: {date!r}. Định dạng đúng là YYYY-MM-DD."
            ) from exc

        # Mở connection từ pool
        async with self._pool.acquire() as conn:
            # LỊCH TRỰC LÀ LUẬT CAO NHẤT — cao hơn cả ba tầng sức chứa.
            #
            # Một luật "BS Thành 18:00–18:15 tám chỗ" không có nghĩa gì vào ngày
            # bác sĩ ấy không đi làm. Trước đây lưới không hỏi lịch trực lần
            # nào: nó mời CSKH đặt vào một buổi chiều mà bác sĩ không có mặt, và
            # sai đó chỉ vỡ ra lúc bệnh nhân đã tới nơi.
            #
            # Chỉ có hiệu lực KHI NGÀY ĐÓ ĐÃ XẾP CA. CSKH đặt trước cả tháng,
            # lúc ấy lịch trực chưa có — coi "chưa xếp" là "không đi làm" sẽ
            # khoá sạch tương lai. Cùng cách phân biệt mà booking_service dùng
            # cho câu cảnh báo của nó, để hai nơi không nói hai điều khác nhau.
            # KHÔNG lọc theo TRẠM (quyết định của Quang, 2026-08-04): có tên
            # trong lịch trực hôm đó là nhận đặt được, dù trạm ghi là MAY_TRONG
            # hay LICH_KHAM. BSNT. Khánh Linh là ví dụ có thật.
            # Truy vấn lịch trực của bác sĩ trong ngày
            duty = await conn.fetchrow(
                """
                SELECT
                  EXISTS (
                    SELECT 1 FROM work_roster
                     WHERE clinic_id = $1::uuid AND work_date = $2
                       AND status = 'APPROVED'
                  ) AS roster_known,
                  coalesce((
                    SELECT array_agg(DISTINCT shift) FROM work_roster
                     WHERE clinic_id = $1::uuid AND work_date = $2
                       AND status = 'APPROVED' AND staff_id = $3::uuid
                  ), ARRAY[]::text[]) AS shifts,
                  (SELECT open_minute FROM clinic_hours_for_date($1::uuid, $2))
                    AS open_minute,
                  (SELECT close_minute FROM clinic_hours_for_date($1::uuid, $2))
                    AS close_minute
                """,
                clinic_id,  # ID phòng khám
                day,  # Ngày cần kiểm tra
                doctor_id,  # ID bác sĩ
            )
            # Kiểm tra xem lịch trực đã được xếp cho ngày đó chưa
            roster_known = bool(duty and duty["roster_known"])
            # Lấy danh sách ca trực của bác sĩ
            shifts: list[str] = list(duty["shifts"]) if duty else []
            # doctor_id = None nghĩa là "lưới chung, không lọc bác sĩ" — không
            # có ai để tra ca trực, và không được coi đó là nghỉ.
            # Kiểm tra bác sĩ có trực không (nếu không lọc bác sĩ thì coi là có trực)
            on_duty = doctor_id is None or bool(shifts)
            # Kiểm tra bác sĩ có nghỉ không (đã xếp ca nhưng không có ca)
            off_duty = roster_known and not on_duty
            # Nếu bác sĩ nghỉ
            if off_duty:
                # Trả về kết quả: đóng cửa vì bác sĩ nghỉ
                return {
                    "date": date,  # Ngày
                    "location_id": location_id,  # ID cơ sở
                    "doctor_id": doctor_id,  # ID bác sĩ
                    "closed": True,  # Đóng cửa
                    "off_duty": True,  # Bác sĩ nghỉ
                    "roster_known": True,  # Đã biết lịch trực
                    "shift_windows": [],  # Không có ca trực
                    "slots": [],  # Không có khung giờ
                }

            # CA SÁNG KHÔNG PHẢI CẢ NGÀY. Bản trước dừng ở mức NGÀY, nên BS
            # Thành chỉ trực ca sáng ngày 08/08 vẫn được mời đặt lúc 18:00 —
            # luật lịch trực đúng một nửa còn khó chịu hơn không có, vì nó tạo
            # cảm giác đã được kiểm.
            # Lấy giờ mở cửa (phút trong ngày)
            open_min = duty["open_minute"] if duty else None
            # Lấy giờ đóng cửa (phút trong ngày)
            close_min = duty["close_minute"] if duty else None
            # Khởi tạo danh sách các khoảng thời gian trực
            windows: list[tuple[int, int]] = []
            # Nếu có ca trực và có giờ mở/đóng cửa
            if shifts and open_min is not None and close_min is not None:
                # Gộp các khoảng thời gian trực lại với nhau
                windows = merge_windows(
                    [
                        w  # Khoảng thời gian trực
                        for s in shifts  # Lặp qua từng ca
                        if (w := shift_window(s, open_min, close_min)) is not None  # Lấy khoảng thời gian của ca
                    ]
                )

            # Truy vấn sức chứa và mức sử dụng cho từng khung giờ
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
                         -- `coalesce` thay cho `($n IS NULL OR col = $n)`:
                         -- cùng nghĩa, không nhánh OR nào để bộ lọc tenant lọt
                         -- qua. Đây là lọc "một bác sĩ hay mọi bác sĩ", không
                         -- phải lọc tenant — nhưng bài soi không phân biệt được,
                         -- và nó đúng khi không phân biệt: một OR ở tầng WHERE
                         -- là chỗ để lộ dữ liệu phòng khám khác.
                         AND a.doctor_id IS NOT DISTINCT FROM
                             coalesce($3::uuid, a.doctor_id)
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
                clinic_id,  # ID phòng khám
                day,  # Ngày cần báo giá
                doctor_id,  # ID bác sĩ
                location_id,  # ID cơ sở
            )

        # Tạo danh sách các khung giờ với thông tin sức chứa
        slots_out = [
            {
                "time": _hhmm(r["minute_of_day"]),  # Thời gian dạng HH:mm
                "minute_of_day": r["minute_of_day"],  # Phút trong ngày
                "slot_minutes": r["slot_minutes"],  # Độ dài khung (phút)
                "regular_cap": r["regular_cap"],  # Số chỗ đặt trước tối đa
                "walkin_cap": r["walkin_cap"],  # Số chỗ vãng lai tối đa
                "regular_used": r["regular_used"],  # Số chỗ đặt trước đã dùng
                "walkin_used": r["walkin_used"],  # Số chỗ vãng lai đã dùng
                "state": cell_state(r["regular_cap"], r["regular_used"]),  # Trạng thái ô
            }
            for r in rows  # Lặp qua từng dòng kết quả
            # Ngoài ca trực thì khung đó không tồn tại với bác sĩ này. Bỏ hẳn
            # khỏi danh sách chứ không đánh dấu "đầy": đầy là hết chỗ, còn đây
            # là không có mặt, và hai thứ đó cần hai cách xử lý khác nhau.
            if not windows or covers(windows, r["minute_of_day"])  # Chỉ giữ khung nằm trong ca trực
        ]

        return {
            "date": date,  # Ngày
            "location_id": location_id,  # ID cơ sở
            "doctor_id": doctor_id,  # ID bác sĩ
            # Rỗng = phòng khám đóng cửa ngày đó (clinic_hours_for_date không
            # trả dòng nào). Khác hẳn "mở cửa nhưng hết chỗ", và giao diện phải
            # nói được hai điều đó bằng hai câu khác nhau.
            "closed": not slots_out,  # Đóng cửa nếu không có khung giờ nào
            # Ba câu khác nhau, đừng gộp: "phòng khám đóng cửa", "bác sĩ không
            # có ca trực", "còn chỗ". Gộp thành một ô xám thì người dùng không
            # biết nên đổi NGÀY hay đổi BÁC SĨ.
            "off_duty": False,  # Bác sĩ không nghỉ
            "roster_known": roster_known,  # Đã biết lịch trực chưa
            # Ca trực của bác sĩ hôm đó, để màn hình nói được "chỉ trực buổi
            # sáng" thay vì im lặng bỏ bớt nửa lưới.
            "shift_windows": [list(w) for w in windows],  # Danh sách khoảng thời gian trực
            # CÓ PHẢI CA LẺ KHÔNG — tính ở đây vì chỉ ở đây mới biết giờ mở
            # cửa. Để trình duyệt tự suy ra (đếm số ô rồi so với lưới) là một
            # phép đoán gián tiếp, sai mỗi khi lưới đổi vì lý do khác.
            "partial_shift": bool(windows) and windows != [(open_min, close_min)],  # Có phải ca lẻ không
            "slots": slots_out,  # Danh sách các khung giờ
        }


def cell_state(regular_cap: int, regular_used: int) -> CellState:
    """Trạng thái ô để tô màu — theo CHỖ ĐẶT HẸN, không tính chỗ vãng lai.

    Chỗ vãng lai là phần để dành cho khách đến thẳng quầy; đếm nó vào ô mà CSKH
    nhìn khi đặt trước sẽ khiến khung trông còn chỗ trong khi phần đặt trước đã
    hết — và trigger sẽ từ chối đúng lượt đặt tiếp theo.
    """
    # Nếu số chỗ đã dùng >= số chỗ tối đa thì ô đầy
    if regular_used >= regular_cap:
        return "full"
    # Nếu số chỗ còn lại <= ngưỡng "còn ít" thì ô còn ít
    if regular_cap - regular_used <= FEW_REMAINING:
        return "few"
    # Ngược lại thì ô còn trống
    return "free"


def _hhmm(minute_of_day: int) -> str:
    # Chuyển phút trong ngày sang định dạng HH:mm
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"