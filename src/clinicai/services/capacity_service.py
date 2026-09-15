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

import asyncio
import json
from datetime import date as _date
from datetime import timedelta
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

# MỘT KHUNG GIỜ còn đúng một chỗ = "còn ít". Tính theo CHỖ, không theo phần
# trăm: với trần 3 thì 66% nghe như còn nhiều, mà thực tế chỉ còn một người.
FEW_REMAINING = 1

# MỘT NGÀY (ô bảng Bác sĩ × tuần) "ít chỗ" = còn ≤ 2 chỗ HOẶC ≤ 20% tổng
# (Tuyền chốt 16/09/2026); số chỗ quản lý chỉnh qua `clinic.settings.it_cho_toi_da`.
IT_CHO_NGAY_MAC_DINH = 2
IT_CHO_NGAY_PHAN_TRAM = 20

#: Trạng thái MỘT Ô NGÀY của bảng Bác sĩ × tuần.
TrangThaiNgay = Literal[
    "CON_CHO", "IT_CHO", "DAY", "NGHI", "DONG_CUA", "TU_DO", "DA_QUA"
]


def nguong_it_cho(settings: object) -> int:
    """Ngưỡng "ít chỗ" của MỘT NGÀY từ `clinic.settings.it_cho_toi_da`.

    Hỏng/thiếu → mặc định; không bao giờ ném (dữ liệu cấu hình do người nhập).
    """
    doc: Any = settings
    if isinstance(doc, (str, bytes)):
        try:
            doc = json.loads(doc)
        except (ValueError, TypeError):
            return IT_CHO_NGAY_MAC_DINH
    if isinstance(doc, dict):
        v = doc.get("it_cho_toi_da")
        if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 50:
            return v
    return IT_CHO_NGAY_MAC_DINH


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
                  (SELECT settings FROM clinic WHERE id = $1::uuid) AS settings,
                  -- Tuần chứa ngày này đã công bố lịch trực chưa. Chưa thì trần
                  -- không chặn lịch hẹn (20260915000001) — lưới phải nói được
                  -- "vượt trần nhưng vẫn nhận" thay vì khoá ô.
                  public.tuan_lich_truc_da_cong_bo(
                      $1::uuid,
                      ($2::date + time '12:00') AT TIME ZONE 'Asia/Ho_Chi_Minh'
                  ) AS tuan_da_cong_bo
                """,
                clinic_id,
                day,
                doctor_id,
            )
            nguong = nguong_it_cho(duty["settings"] if duty else None)
            roster_known = bool(duty and duty["roster_known"])
            tuan_da_cong_bo = bool(duty and duty["tuan_da_cong_bo"])
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
                    "roster_week_published": tuan_da_cong_bo,
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
                ),
                -- Ghế đếm bằng slot_seats_ban — CÙNG luật mà trigger dựa
                -- vào (slot_seats_used nay là vỏ mỏng trên chính hàm này, xem
                -- 20260821000002). Trước đây mỗi khung gọi slot_seats_used
                -- HAI lần; hàm SECURITY DEFINER không inline được nên một
                -- lượt vẽ lưới là ~120 lượt quét riêng — đo 21/08/2026:
                -- 283ms/lượt, 25 người xem cùng lúc thì database ăn 349% CPU.
                -- Nay luật chạy MỘT lần cho cả ngày, phần chia khung còn lại
                -- là số học.
                ban AS (
                    SELECT b.loai,
                           b.ts_goc,
                           (EXTRACT(hour FROM b.ts
                                    AT TIME ZONE 'Asia/Ho_Chi_Minh')::int * 60
                          + EXTRACT(minute FROM b.ts
                                    AT TIME ZONE 'Asia/Ho_Chi_Minh')::int)
                               AS phut
                      FROM hours h
                      CROSS JOIN LATERAL slot_seats_ban(
                          $1::uuid, $3::uuid,
                          ($2::date + make_interval(mins => h.open_minute))
                              AT TIME ZONE 'Asia/Ho_Chi_Minh',
                          ($2::date + make_interval(mins => h.close_minute))
                              AT TIME ZONE 'Asia/Ho_Chi_Minh',
                          NULL, $4::uuid) b
                )
                SELECT sl.minute_of_day,
                       sl.slot_minutes,
                       cap.regular_cap,
                       cap.walkin_cap,
                       count(*) FILTER (WHERE b.loai = 'DAT_HEN')::int
                           AS regular_used,
                       -- Ghế trực tiếp: chỉ lịch lễ tân đặt tại quầy. Khách
                       -- hẹn đến muộn không còn chiếm ghế này (20260915000014).
                       count(*) FILTER (WHERE b.loai = 'VANG_LAI')::int
                           AS walkin_used
                  FROM slots sl
                  CROSS JOIN LATERAL resolve_effective_cap(
                      $1::uuid, $3::uuid,
                      ($2::date + make_interval(mins => sl.minute_of_day))
                          AT TIME ZONE 'Asia/Ho_Chi_Minh') cap
                  LEFT JOIN ban b
                    ON b.phut >= sl.minute_of_day
                   AND b.phut <  sl.minute_of_day + sl.slot_minutes
                 GROUP BY sl.minute_of_day, sl.slot_minutes,
                          cap.regular_cap, cap.walkin_cap
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
                # CÒN LẠI của phần đặt hẹn — màn hình in thẳng số này, không tự
                # trừ (16/09/2026: một nguồn "còn chỗ" cho mọi màn đặt lịch).
                "con_lai": max(r["regular_cap"] - r["regular_used"], 0),
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
            # Tuần CHƯA công bố lịch trực ⇒ khung đủ trần vẫn đặt được, đối soát
            # lúc công bố (CONTEXT v1.0). Lưới dùng cờ này để không khoá ô.
            "roster_week_published": tuan_da_cong_bo,
            # Tuần chưa công bố lịch trực = ĐẶT TỰ DO (luật 15/09/2026): trần
            # không chặn lịch hẹn, màn hình không được in "/3" như một giới hạn.
            "dat_tu_do": not tuan_da_cong_bo,
            "it_cho_toi_da": nguong,
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


def tom_tat_ngay(quote: dict[str, Any], *, hom_nay: str) -> dict[str, Any]:
    """Một ô ngày của bảng Bác sĩ × tuần, tóm từ CHÍNH kết quả `quote`.

    Không tự tính sức chứa lần nữa: ô ngày chỉ cộng các khung mà `quote` đã trả,
    nên bảng tuần và popup khung giờ không bao giờ nói hai con số khác nhau.
    """
    ngay = str(quote["date"])
    slots: list[dict[str, Any]] = list(quote.get("slots") or [])
    da_dat = sum(int(x["regular_used"]) for x in slots)
    con = sum(int(x["con_lai"]) for x in slots)
    tong = sum(int(x["regular_cap"]) for x in slots)
    trang_thai: TrangThaiNgay
    if ngay < hom_nay:
        trang_thai = "DA_QUA"
    elif quote.get("off_duty"):
        trang_thai = "NGHI"
    elif quote.get("closed"):
        trang_thai = "DONG_CUA"
    elif quote.get("dat_tu_do"):
        trang_thai = "TU_DO"
    elif con <= 0:
        trang_thai = "DAY"
    elif con <= max(
        int(quote.get("it_cho_toi_da", IT_CHO_NGAY_MAC_DINH)),
        -(-tong * IT_CHO_NGAY_PHAN_TRAM // 100),
    ):
        trang_thai = "IT_CHO"
    else:
        trang_thai = "CON_CHO"
    return {
        "date": ngay,
        "trang_thai": trang_thai,
        "da_dat": da_dat,
        # Đặt tự do thì không có "còn bao nhiêu" — in ra là bịa một giới hạn.
        "con_cho": None
        if trang_thai in ("TU_DO", "NGHI", "DONG_CUA", "DA_QUA")
        else con,
        "tong_cho": None
        if trang_thai in ("TU_DO", "NGHI", "DONG_CUA", "DA_QUA")
        else tong,
    }


async def bang_tuan(
    svc: CapacityService,
    pool: asyncpg.Pool,
    *,
    week_start: str,
    location_id: str,
    clinic_id: str,
    hom_nay: str,
) -> dict[str, Any]:
    """Bảng Bác sĩ × 7 ngày cho màn Đặt lịch (Tuyền duyệt 16/09/2026).

    Mỗi ô = `quote(ngày, bác sĩ)` rồi `tom_tat_ngay` — một nguồn duy nhất với
    popup khung giờ. Thêm một hàng "Chưa phân bác sĩ" (quote không lọc bác sĩ)
    cho lịch đặt trước khi có lịch trực.
    """
    try:
        dau = _date.fromisoformat(week_start)
    except ValueError as exc:
        raise ValidationError(
            f"Ngày không hợp lệ: {week_start!r}. Định dạng đúng là YYYY-MM-DD."
        ) from exc
    dau = dau - timedelta(days=dau.weekday())
    ngay = [(dau + timedelta(days=i)).isoformat() for i in range(7)]
    bac_si = await pool.fetch(
        """
        SELECT s.id::text AS id, s.full_name, m.role
          FROM clinic_membership m
          JOIN staff s ON s.id = m.staff_id AND s.is_active
         WHERE m.clinic_id = $1::uuid AND m.is_active
           AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
         ORDER BY s.full_name
        """,
        clinic_id,
    )
    hang: list[tuple[str | None, str, str | None]] = [
        (r["id"], r["full_name"], r["role"]) for r in bac_si
    ]
    hang.append((None, "Chưa phân bác sĩ", None))

    # Giới hạn song song để không chiếm hết pool của cả API.
    chan = asyncio.Semaphore(6)

    async def mot_o(bs: str | None, d: str) -> dict[str, Any]:
        async with chan:
            q = await svc.quote(
                date=d, location_id=location_id, doctor_id=bs, clinic_id=clinic_id
            )
        return tom_tat_ngay(q, hom_nay=hom_nay)

    ket_qua = await asyncio.gather(*(mot_o(bs, d) for bs, _, _ in hang for d in ngay))
    it = iter(ket_qua)
    return {
        "week_start": ngay[0],
        "ngay": ngay,
        "bac_si": [
            {"id": bs, "full_name": ten, "role": vai, "o": [next(it) for _ in ngay]}
            for bs, ten, vai in hang
        ],
    }
