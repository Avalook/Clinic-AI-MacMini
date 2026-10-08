"""Lịch hẹn một tuần, kèm PHÂN LOẠI KHÁM — một truy vấn, một vòng mạng.

VÌ SAO CHUYỂN XUỐNG ĐÂY.

"Tái khám hay Khám lần đầu" là một LUẬT NGHIỆP VỤ, và nó đang nằm trong hai file
TSX với hai bản sao gần giống nhau (``home/page.tsx`` và ``tasks/page.tsx`` —
chính chú thích trong mã cũng viết "giống bảng Lịch hẹn khám ở Trang chủ"). Hai
bản sao của một luật là hai câu trả lời chờ ngày lệch nhau.

Cách tính cũ còn tốn một VÒNG MẠNG THỨ HAI và một truy vấn không có giới hạn:

    đọc lịch hẹn tuần                    (1 vòng)
    → gom clinic_patient_id
    → đọc TOÀN BỘ lịch sử hẹn của từng người đó, .in(), KHÔNG limit   (1 vòng)
    → tìm mốc sớm nhất bằng JavaScript

Hôm nay prod mới có 49 lịch hẹn nên vòng thứ hai chỉ kéo 4 dòng — nhưng nó lớn
theo lịch sử của phòng khám, mãi mãi, để tính đúng một chuỗi ký tự mỗi dòng.

Ở đây nó là một truy vấn: mốc sớm nhất của mỗi bệnh nhân tính ngay trong SQL,
không dòng nào rời database ngoài số dòng thật sự hiển thị.

GIỮ NGUYÊN HÀNH VI, KỂ CẢ CHỖ TRÔNG NHƯ THIẾU SÓT: mốc sớm nhất tính trên MỌI
lịch hẹn của bệnh nhân — kể cả lịch đã huỷ, đã no-show — vì bản cũ không lọc
trạng thái ở truy vấn ``prior``. Đổi điều đó ở đây sẽ làm một số bệnh nhân đổi
từ "Tái khám" sang "Khám lần đầu" mà không ai yêu cầu. Muốn đổi thì đổi có chủ
ý, ở một thay đổi riêng, sau khi đã đối chiếu.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import asyncpg
import structlog

from clinicai.core.clock import CLINIC_TZ
from clinicai.core.trang_thai_lich import (
    DEAD_STATUSES,
    giu_cho,
    trang_thai_hien_thi,
)
from clinicai.services.hanh_trinh_khach_service import dang_o_cac_luot
from clinicai.services.queue_order import QueueDecision
from clinicai.services.queue_rows import thu_tu_goi_theo_ngay

logger = structlog.get_logger()

# Trần bằng đúng con số bản cũ dùng (`.limit(500)`), để một tuần bất thường
# không đổi số dòng trả về giữa hai bản.
MAX_ROWS = 500

# Trạng thái không hiện trên lưới tuần — huỷ xong thì trả chỗ về ô trống.
# Cùng danh sách "không giữ chỗ" của core/trang_thai_lich (29/09/2026).
HIDDEN_STATUSES = tuple(sorted(DEAD_STATUSES))

_SQL = (
    """
WITH tuan AS (
    SELECT a.id, a.slot_start, a.status, a.queue_number, a.doctor_id,
           a.so_booking, a.so_tiep_don,
           a.booking_channel, a.clinic_patient_id, a.service_type_id,
           a.created_at, a.bac_si_da_go_id
      FROM appointment a
     WHERE a.clinic_id  = $1::uuid
       AND a.slot_start >= $2
       AND a.slot_start <  $3
       AND a.status <> ALL($4::text[])
       -- Chỉ lịch của cơ sở đang đứng (hai cơ sở, 08/10/2026); NULL = mọi cơ sở.
       AND coalesce(a.location_id, $5::uuid)
           IS NOT DISTINCT FROM coalesce($5::uuid, a.location_id)
     -- THỨ TỰ PHẢI XÁC ĐỊNH, và bản cũ thì không.
     --
     -- Prod đang có BA lịch hẹn cùng mốc 10:15 ngày 15/07. Với `ORDER BY
     -- slot_start` trần, Postgres được phép trả chúng theo thứ tự bất kỳ, và
     -- thực tế nó đổi giữa các lần chạy — nghĩa là lưới trang chủ xếp ba bệnh
     -- nhân ấy khác nhau mỗi lần tải. Lễ tân đọc dọc danh sách để gọi tên thì
     -- đó không phải chuyện hình thức.
     --
     -- created_at = thứ tự đặt lịch, câu trả lời có nghĩa nhất cho "ai trước"
     -- trong cùng một khung. id chốt lại phần còn lại để không bao giờ hoà.
     ORDER BY a.slot_start, a.created_at, a.id
     LIMIT %d
),
-- Mốc hẹn SỚM NHẤT của từng bệnh nhân xuất hiện trong tuần. Chỉ những người
-- thật sự có mặt trên lưới, nên đây là một phép quét hẹp chứ không phải toàn
-- bảng — và không dòng nào phải đi qua mạng.
som_nhat AS (
    SELECT a.clinic_patient_id, min(a.slot_start) AS dau_tien
      FROM appointment a
     WHERE a.clinic_id = $1::uuid
       AND a.clinic_patient_id IN (SELECT clinic_patient_id FROM tuan)
       -- LỊCH ĐÃ HUỶ / KHÔNG ĐẾN / BÁC SĨ TỪ CHỐI KHÔNG TÍNH LÀ LẦN TRƯỚC.
       --
       -- Bản cũ quét MỌI trạng thái, nên một khách đặt rồi huỷ, hôm sau đặt
       -- lại, thì lịch thứ hai bị gọi là lần-không-phải-đầu — dù họ chưa từng
       -- bước chân tới. Cùng lúc màn Quản lý khách hàng gọi đúng người ấy là
       -- "Khách mới" (nó đếm lượt khám XONG, và cố ý bỏ lịch đã huỷ). Hai màn
       -- nói ngược nhau về cùng một người, trong cùng một ca trực.
       --
       -- Chỉ lộ ra khi đổi cách gọi tên ngày 14/08/2026: "Tái khám" là thuật
       -- ngữ về LOẠI LỊCH nên bản cũ còn đọc xuôi được, nhưng "Khám cũ" là câu
       -- khẳng định về NGƯỜI — và với khách chưa từng tới thì nó sai thẳng.
       AND a.status <> ALL($4::text[])
     GROUP BY a.clinic_patient_id
)
SELECT t.id, t.slot_start, t.status, t.queue_number, t.doctor_id,
       t.so_booking, t.so_tiep_don,
       t.booking_channel,
       -- LỊCH NÀY VỪA MẤT BÁC SĨ: có người phụ trách, nhưng người ấy không còn
       -- ca KHÁM vào đúng ngày khám.
       --
       -- Cùng luật với cảnh báo ở màn Quản lý khách hàng (customers/page.tsx).
       -- Bảng "check đặt lịch" trước nay không có gì nói chuyện này, nên quản
       -- lý gỡ một ca trực xong thì hàng lịch của khách nằm im dưới tên một bác
       -- sĩ hôm đó không đi làm — và người trực chỉ biết khi khách tới quầy.
       --
       -- `station = 'LICH_KHAM'`: câu hỏi không phải "hôm ấy có mặt ở phòng
       -- khám không" mà "hôm ấy có ngồi bàn khám không". Một bác sĩ còn ca thủ
       -- thuật ngoài giờ vẫn là mất bác sĩ đối với lịch hẹn khám.
       --
       -- CHỈ TÍNH CHO LỊCH CÒN CỨU ĐƯỢC — chưa tới giờ và chưa check-in. Lịch
       -- đã qua mà mất bác sĩ thì không đổi lại được nữa; tô cảnh báo ở đó chỉ
       -- làm ngập bảng và dạy người đọc bỏ qua màu cảnh báo.
       (
         t.doctor_id IS NOT NULL
         AND t.slot_start > now()
         -- Tuần CHƯA công bố lịch trực = đặt tự do (luật 15/09/2026): không có
         -- ca trong bảng nháp không phải là bác sĩ nghỉ (16/09/2026).
         AND public.tuan_lich_truc_da_cong_bo($1::uuid, t.slot_start)
         AND t.status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
         AND NOT EXISTS (
           SELECT 1 FROM public.work_roster w
            WHERE w.clinic_id = $1::uuid
              AND w.staff_id  = t.doctor_id
              AND public.la_ca_kham_bac_si(w.clinic_id, w.station)
              AND w.work_date =
                  (t.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
         )
       ) AS mat_bac_si,
       -- BÁC SĨ ĐÃ BỊ GỠ khỏi lịch này khi ca trực của họ bị xoá.
       --
       -- Sau khi gỡ, `doctor_id` về NULL nên cờ `mat_bac_si` ở trên TẮT — nó
       -- đòi lịch phải CÓ bác sĩ. Cột này là thứ giữ cho màn hình còn nói được,
       -- và nói rõ hơn: đổi từ ai. Thiếu nó thì CSKH gọi khách chỉ nói được
       -- "lịch của chị bị đổi", không biết khách đang chờ gặp ai.
       bs_go.full_name AS bac_si_da_go,
       -- BÁC SĨ BỊ GỠ ĐÃ CÓ CA KHÁM TRỞ LẠI hôm đó chưa? Hai tình huống cần
       -- hai câu khác nhau trên màn: "đã nghỉ — xếp bác sĩ khác" (gọi khách
       -- đổi lịch) vs "ca đã xếp lại — gán lại bác sĩ" (việc nội bộ, một cú
       -- bấm). Sau bản add_shift tự gắn lại 15/08, nhánh hai chỉ còn xảy ra
       -- khi ghế của khung cũ đã bị lịch khác chiếm — nói đúng tình huống để
       -- người trực khỏi gọi khách vì một chuyện không cần gọi.
       (
         t.bac_si_da_go_id IS NOT NULL
         AND EXISTS (
           SELECT 1 FROM public.work_roster wg
            WHERE wg.clinic_id = $1::uuid
              AND wg.staff_id  = t.bac_si_da_go_id
              AND public.la_ca_kham_bac_si(wg.clinic_id, wg.station)
              AND wg.work_date =
                  (t.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
         )
       ) AS bs_go_co_ca_lai,
       -- Lịch VƯỢT SỨC CHỨA sau khi công bố lịch trực (20260915000014) — trang
       -- chủ báo cam ngay trên dòng lịch, cùng nguồn với khung báo CSKH.
       EXISTS (
         SELECT 1 FROM public.v_viec_cskh vv
          WHERE vv.clinic_id = $1::uuid
            AND vv.appointment_id = t.id
            AND vv.trang_thai = 'VUOT_SUC_CHUA'
       ) AS vuot_suc_chua,
       CASE
         WHEN p.clinic_patient_id IS NULL THEN ''
         WHEN t.slot_start > s.dau_tien  THEN 'Tái khám'
         ELSE 'Khám lần đầu'
       END AS phan_loai,
       p.clinic_patient_id, p.patient_code, p.full_name, p.date_of_birth,
       p.phone_primary, p.phone_secondary, p.gender, p.ethnicity,
       p.nationality, p.occupation, p.patient_objection, p.address,
       p.guardian_name,
       d.full_name AS doctor_name,
       st.name     AS service_name,
       v.checked_in_at,
       v.thu_tu_tay_ms,
       v.visit_id,
       -- NHÃN TRẠNG THÁI (30/09/2026): khách đã về hay chưa là chuyện của
       -- LƯỢT, không phải của `appointment.status` — `trang_thai_hien_thi`.
       v.trang_thai_luot, v.ve_luc, v.kham_xong,
       p.uu_tien AS khach_uu_tien,
       p.uu_tien_ly_do,
       cap.slot_minutes,
       -- Số ghế TRỰC TIẾP của đúng (bác sĩ × khung) này, theo luật riêng —
       -- cùng hàm trigger dùng khi chặn. Trình duyệt không lấy trần chung của
       -- phòng khám nữa (29/09/2026).
       cap.walkin_cap
  FROM tuan t
  LEFT JOIN patient p
         ON p.clinic_patient_id = t.clinic_patient_id
        AND p.clinic_id = $1::uuid
  LEFT JOIN som_nhat s ON s.clinic_patient_id = t.clinic_patient_id
  LEFT JOIN staff d    ON d.id = t.doctor_id
  LEFT JOIN staff bs_go ON bs_go.id = t.bac_si_da_go_id
  LEFT JOIN service_type st ON st.id = t.service_type_id
  -- GIỜ ĐẾN THẬT. Endpoint này trước đây không trả `checked_in_at`, nên luật
  -- "có hẹn và đến đúng giờ" ở lưới trang chủ CHƯA TỪNG CHẠY: mọi dòng đều rơi
  -- xuống làn đến-sau và xếp theo giờ hẹn. Nhìn thì giống đang hoạt động, vì
  -- xếp theo giờ hẹn cũng ra một thứ tự hợp lý — chỉ sai khi có người đến muộn.
  LEFT JOIN LATERAL (
      SELECT vi.checked_in_at, vi.thu_tu_tay_ms, vi.visit_id::text AS visit_id,
             vi.status AS trang_thai_luot, vi.closed_at AS ve_luc,
             (vi.exam_completed_at IS NOT NULL) AS kham_xong
        FROM visit vi
       WHERE vi.appointment_id = t.id AND vi.clinic_id = $1::uuid
       ORDER BY vi.checked_in_at NULLS LAST
       LIMIT 1
  ) v ON TRUE
  LEFT JOIN LATERAL public.resolve_effective_cap(
      $1::uuid, t.doctor_id, t.slot_start
  ) cap ON TRUE
 ORDER BY t.slot_start, t.created_at, t.id
"""
    % MAX_ROWS
)


class WeekAppointmentsService:
    """Lịch hẹn của một tuần, đúng hình dạng mà lưới trang chủ cần."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def week(
        self,
        *,
        clinic_id: str,
        week_start: date,
        location_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Bảy ngày kể từ ``week_start`` (giờ Việt Nam).

        ``location_id``: chỉ lịch của cơ sở ấy; ``None`` = mọi cơ sở.
        """
        start = _vn_midnight(week_start)
        end = _vn_midnight(week_start + timedelta(days=7))

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _SQL,
                clinic_id,
                start,
                end,
                list(HIDDEN_STATUSES),
                location_id or None,
            )
            # Khách đang ở / đang chờ ở đâu — cùng hàm với Hành trình khách,
            # chỉ cho lượt CÒN MỞ (thường chỉ hôm nay, vài chục lượt).
            dang_o = await dang_o_cac_luot(
                conn,
                clinic_id=clinic_id,
                visit_ids=[
                    str(r["visit_id"])
                    for r in rows
                    if r.get("visit_id")
                    and r.get("ve_luc") is None
                    # INCOMPLETE / FINALIZED / AMENDED cố ý không hỏi chỗ đứng:
                    # khách đã về / hồ sơ đã ký — nhãn do trang_thai_hien_thi.
                    and r.get("trang_thai_luot") in ("OPEN", "IN_PROGRESS")
                ],
            )

        logger.info("week_appointments", clinic_id=clinic_id, rows=len(rows))
        quyet_dinh = thu_tu_goi_theo_ngay(rows)
        dem = dem_ghe_truc_tiep(rows)
        return [
            _row_to_dict(r, quyet_dinh.get(str(r["id"])), dem, dang_o) for r in rows
        ]


def _khoa_khung(r: Any) -> tuple[str, int] | None:
    """(bác sĩ, đầu khung theo epoch) — y như trigger gom: floor(epoch / giây)."""
    phut = r.get("slot_minutes")
    if not phut or r.get("slot_start") is None:
        return None
    giay = int(phut) * 60
    return (
        str(r.get("doctor_id") or ""),
        int(r["slot_start"].timestamp()) // giay * giay,
    )


def dem_ghe_truc_tiep(rows: list[Any]) -> dict[tuple[str, int], int]:
    """Số ghế trực tiếp (WALK_IN, còn giữ chỗ) đã có người, theo (bác sĩ, khung).

    Lưới tuần trang chủ trước đây tự đếm ở trình duyệt rồi so với TRẦN CHUNG
    của phòng khám — lệch ngay khi quản lý đặt luật riêng cho một bác sĩ × giờ.
    Nay đếm ở đây, cùng luật chọn ghế với `slot_seats_ban` (kênh WALK_IN, trạng
    thái còn giữ chỗ), và trả sẵn số ghế còn trống trên từng dòng.
    """
    out: dict[tuple[str, int], int] = {}
    for r in rows:
        if not giu_cho(r.get("status")):
            continue
        if (r.get("booking_channel") or "").strip().upper() != "WALK_IN":
            continue
        k = _khoa_khung(r)
        if k is not None:
            out[k] = out.get(k, 0) + 1
    return out


def _ghe_truc_tiep_con(r: Any, dem: dict[tuple[str, int], int] | None) -> int | None:
    """Số ghế trực tiếp còn trống ở khung của dòng này; None = không biết."""
    tran = r.get("walkin_cap")
    k = _khoa_khung(r)
    if dem is None or tran is None or k is None:
        return None
    return max(int(tran) - dem.get(k, 0), 0)


def _vn_midnight(day: date) -> datetime:
    """Nửa đêm giờ Việt Nam của một ngày, dạng ``datetime`` CÓ múi giờ.

    HAI ĐIỀU, VÀ CẢ HAI ĐỀU TỪNG LÀM HỎNG THẬT.

    (1) Phải là ``datetime`` chứ không phải chuỗi. Tham số so với một cột
    ``timestamptz`` được Postgres khai kiểu, và asyncpg KHÔNG tự đọc chuỗi cho
    kiểu đó — nó ném ``DataError`` và cả endpoint thành 500. Đúng lỗi này đã
    làm ``/appointments/quote`` chết lặng suốt một thời gian dài; lần này chính
    script đối chiếu bắt được nó trước khi rời máy.

    (2) Phải MANG múi giờ. Một ``datetime`` trần sẽ được hiểu theo TimeZone của
    phiên kết nối — thứ không ai ở đây kiểm soát — nên biên tuần sẽ lệch 7 giờ
    ở một môi trường và đúng ở môi trường khác.
    """
    return datetime.combine(day, time.min, tzinfo=CLINIC_TZ)


def _row_to_dict(
    r: asyncpg.Record,
    d: QueueDecision | None = None,
    dem: dict[tuple[str, int], int] | None = None,
    dang_o: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Đúng hình dạng lồng nhau mà ``WeekApptRow`` (TSX) đang đọc.

    PostgREST trả quan hệ thành object lồng; giữ y hệt để phía trình duyệt không
    phải sửa một dòng nào — đây là chỗ dễ làm hỏng màn hình nhất, và cũng là
    chỗ dễ đối chiếu nhất.
    """
    return {
        "id": str(r["id"]),
        "slot_start": r["slot_start"].isoformat(),
        "status": r["status"],
        "queue_number": r["queue_number"],
        # Số booking (cấp lúc đặt) đứng cạnh số quầy (cấp lúc check-in) —
        # luồng chuẩn bước 4, 23/09/2026.
        "so_booking": r.get("so_booking"),
        "so_tiep_don": r.get("so_tiep_don"),
        "doctor_id": str(r["doctor_id"]) if r["doctor_id"] else None,
        "booking_channel": r["booking_channel"],
        "phan_loai": r["phan_loai"],
        "mat_bac_si": bool(r["mat_bac_si"]),
        "bac_si_da_go": r["bac_si_da_go"],
        "bac_si_da_go_co_ca_lai": bool(r["bs_go_co_ca_lai"]),
        "vuot_suc_chua": bool(r.get("vuot_suc_chua")),
        # Lịch này còn chiếm ghế không — trình duyệt đọc cờ này, không giữ
        # danh sách trạng thái chết của riêng nó (29/09/2026).
        "giu_cho": giu_cho(r["status"]),
        # Ghế TRỰC TIẾP còn trống ở (bác sĩ × khung) của dòng này, theo luật
        # riêng của bác sĩ ấy — ô xanh "đặt vào đây" hiện theo số này.
        "ghe_truc_tiep_con": _ghe_truc_tiep_con(r, dem),
        # Giờ đến thật + thứ tự gọi. Trước đây endpoint này không trả
        # `checked_in_at`, nên bản TypeScript của luật chạy ở đây luôn coi mọi
        # người là "chưa đến" và xếp theo giờ hẹn — luật đúng, dữ liệu thiếu.
        "checked_in_at": (
            r["checked_in_at"].isoformat() if r["checked_in_at"] else None
        ),
        # Lượt khám của lịch (đã check-in) — bấm tên khách mở popup Hành trình
        # khách (29/09/2026). Chưa check-in → None → mở hồ sơ khách.
        "visit_id": str(r["visit_id"]) if r.get("visit_id") else None,
        # NHÃN TRẠNG THÁI do máy chủ quyết (30/09/2026) — màn chỉ vẽ `nhan`
        # bằng màu `tone`. Lượt đã check-out LUÔN "Đã về".
        "trang_thai": trang_thai_hien_thi(
            lich=r["status"],
            luot=r.get("trang_thai_luot"),
            ve_luc=r.get("ve_luc"),
            kham_xong=bool(r.get("kham_xong")),
            dang_o=(dang_o or {}).get(str(r.get("visit_id") or "")),
        ),
        "call_order": d.call_order if d else None,
        "call_tier": d.call_tier if d else None,
        "call_reason": d.call_reason if d else None,
        "promoted": d.promoted if d else False,
        "promoted_over": d.promoted_over if d else 0,
        "uu_tien": d.uu_tien if d else False,
        "uu_tien_ly_do": r.get("uu_tien_ly_do"),
        "patient": (
            {
                "clinic_patient_id": str(r["clinic_patient_id"]),
                "patient_code": r["patient_code"],
                "full_name": r["full_name"],
                "date_of_birth": (
                    r["date_of_birth"].isoformat() if r["date_of_birth"] else None
                ),
                "phone_primary": r["phone_primary"],
                "phone_secondary": r["phone_secondary"],
                "gender": r["gender"],
                "ethnicity": r["ethnicity"],
                "nationality": r["nationality"],
                "occupation": r["occupation"],
                "patient_objection": r["patient_objection"],
                "address": r["address"],
                "guardian_name": r["guardian_name"],
            }
            if r["clinic_patient_id"]
            else None
        ),
        "doctor": {"full_name": r["doctor_name"]} if r["doctor_name"] else None,
        "service": {"name": r["service_name"]} if r["service_name"] else None,
    }
