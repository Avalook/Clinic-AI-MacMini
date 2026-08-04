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

logger = structlog.get_logger()

# Trần bằng đúng con số bản cũ dùng (`.limit(500)`), để một tuần bất thường
# không đổi số dòng trả về giữa hai bản.
MAX_ROWS = 500

# Trạng thái không hiện trên lưới tuần — huỷ xong thì trả chỗ về ô trống.
HIDDEN_STATUSES = ("CANCELLED", "NO_SHOW", "DOCTOR_DECLINED")

_SQL = """
WITH tuan AS (
    SELECT a.id, a.slot_start, a.status, a.queue_number, a.doctor_id,
           a.booking_channel, a.clinic_patient_id, a.service_type_id,
           a.created_at
      FROM appointment a
     WHERE a.clinic_id  = $1::uuid
       AND a.slot_start >= $2
       AND a.slot_start <  $3
       AND a.status <> ALL($4::text[])
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
     GROUP BY a.clinic_patient_id
)
SELECT t.id, t.slot_start, t.status, t.queue_number, t.doctor_id,
       t.booking_channel,
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
       st.name     AS service_name
  FROM tuan t
  LEFT JOIN patient p
         ON p.clinic_patient_id = t.clinic_patient_id
        AND p.clinic_id = $1::uuid
  LEFT JOIN som_nhat s ON s.clinic_patient_id = t.clinic_patient_id
  LEFT JOIN staff d    ON d.id = t.doctor_id
  LEFT JOIN service_type st ON st.id = t.service_type_id
 ORDER BY t.slot_start, t.created_at, t.id
""" % MAX_ROWS


class WeekAppointmentsService:
    """Lịch hẹn của một tuần, đúng hình dạng mà lưới trang chủ cần."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def week(
        self, *, clinic_id: str, week_start: date
    ) -> list[dict[str, Any]]:
        """Bảy ngày kể từ ``week_start`` (giờ Việt Nam)."""
        start = _vn_midnight(week_start)
        end = _vn_midnight(week_start + timedelta(days=7))

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _SQL, clinic_id, start, end, list(HIDDEN_STATUSES)
            )

        logger.info("week_appointments", clinic_id=clinic_id, rows=len(rows))
        return [_row_to_dict(r) for r in rows]


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


def _row_to_dict(r: asyncpg.Record) -> dict[str, Any]:
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
        "doctor_id": str(r["doctor_id"]) if r["doctor_id"] else None,
        "booking_channel": r["booking_channel"],
        "phan_loai": r["phan_loai"],
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
