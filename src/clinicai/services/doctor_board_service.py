"""Bảng khám của bác sĩ — một truy vấn thay cho ba, và hai luật rời TSX.

HAI LUẬT NGHIỆP VỤ ĐANG NẰM TRONG TRÌNH DUYỆT:

  ① "Tái khám / Khám lần đầu" — bản sao thứ hai của luật đã chuyển xuống
    ``week_appointments_service``. Chú thích trong chính mã TSX viết "giống bảng
    Lịch hẹn khám ở Trang chủ", tức là người viết đã biết mình đang chép.

  ② "Chờ đọc kết quả (B3)" — lượt nào có kết quả xét nghiệm về ĐỦ (ít nhất một
    phiếu đã có kết quả, và không còn phiếu nào đang chờ) thì được kéo lên đầu
    hàng đợi. Luật này quyết định THỨ TỰ GỌI BỆNH NHÂN, và nó đang sống trong
    ``lib/queue.ts`` cùng hai truy vấn phụ trợ.

Cả hai đều tốn một VÒNG MẠNG NỐI TIẾP riêng, và cả hai đều chỉ cần dữ liệu mà
truy vấn đầu tiên đã chạm tới:

    đọc lịch hẹn 31 ngày                                    (1 vòng)
    → gom appointment_id → đọc lab_result                   (1 vòng)
    → gom clinic_patient_id → đọc TOÀN BỘ lịch sử hẹn       (1 vòng, KHÔNG limit)

Ở đây là một vòng. ``phan_loai`` và ``b3_ready`` về cùng dòng dữ liệu.

GIỮ NGUYÊN HÀNH VI, kể cả những chỗ trông như thiếu sót — vì đổi chúng ở đây là
đổi thứ tự gọi bệnh nhân mà không ai yêu cầu:

  * mốc "lần đầu" tính trên MỌI lịch hẹn kể cả đã huỷ (bản cũ không lọc);
  * "đã có kết quả" = ``result_value`` HOẶC ``external_ref`` khác rỗng sau khi
    cắt khoảng trắng, đúng như ``b3ReadyApptIds`` trong lib/queue.ts;
  * lịch KHÔNG bị lọc theo trạng thái — bảng bác sĩ hiện cả lịch đã huỷ, khác
    hẳn lưới tuần ở trang chủ.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg
import structlog

from clinicai.services.queue_order import QueueDecision
from clinicai.services.queue_rows import thu_tu_goi_theo_ngay

logger = structlog.get_logger()

# Bằng đúng `.limit(400)` của bản cũ, để một khoảng bất thường không đổi số dòng.
MAX_ROWS = 400

_SQL = (
    """
WITH lich AS (
    SELECT a.id, a.slot_start, a.status, a.queue_number, a.booking_channel,
           a.clinic_patient_id, a.service_type_id, a.created_at, a.doctor_id
      FROM appointment a
     WHERE a.clinic_id  = $1::uuid
       AND a.slot_start >= $2
       AND a.slot_start <  $3
       -- `coalesce` thay cho `($4 IS NULL OR col = $4)` — xem ghi chú cùng
       -- kiểu ở capacity_service. `IS NOT DISTINCT FROM` để dòng có doctor_id
       -- NULL (chưa xếp bác sĩ) vẫn lọt khi không lọc, đúng như OR cũ.
       AND a.doctor_id IS NOT DISTINCT FROM coalesce($4::uuid, a.doctor_id)
       -- $5 rỗng = MỌI trạng thái. Cùng lối viết `coalesce` với dòng trên, để
       -- không có nhánh nào chỉ chạy khi tham số vắng mặt.
       AND a.status = ANY(coalesce($5::text[], ARRAY[a.status]))
     -- Thứ tự phải XÁC ĐỊNH: nhiều lịch trùng mốc giờ là chuyện thường, và
     -- `ORDER BY slot_start` trần cho phép Postgres đổi thứ tự giữa các lần
     -- chạy. Bảng này là thứ bác sĩ đọc dọc để gọi tên.
     ORDER BY a.slot_start, a.created_at, a.id
     LIMIT %d
),
som_nhat AS (
    SELECT a.clinic_patient_id, min(a.slot_start) AS dau_tien
      FROM appointment a
     WHERE a.clinic_id = $1::uuid
       AND a.clinic_patient_id IN (SELECT clinic_patient_id FROM lich)
     GROUP BY a.clinic_patient_id
),
-- Luật B3, nguyên văn từ lib/queue.ts: có kết quả = result_value HOẶC
-- external_ref khác rỗng sau khi cắt khoảng trắng. Sẵn sàng đọc = có ít nhất
-- một phiếu đã kết quả VÀ không còn phiếu nào chờ.
lab AS (
    SELECT l.appointment_id,
           -- `coalesce(a, b) IS NOT NULL` thay cho `a IS NOT NULL OR b IS NOT
           -- NULL` — cùng nghĩa, và không có OR nào trong mệnh đề WHERE.
           --
           -- OR này là lọc NỘI DUNG (có kết quả hay chưa), không phải lọc
           -- tenant, nên bài soi phạm vi tenant báo nhầm. Nhưng nới bài soi để
           -- bỏ qua một hình dạng là mở đường cho hình dạng ấy ở chỗ nguy hiểm
           -- thật — rẻ hơn là viết lại câu này.
           count(*) FILTER (
               WHERE coalesce(
                       nullif(btrim(coalesce(l.result_value, '')), ''),
                       nullif(btrim(coalesce(l.external_ref,  '')), '')
                     ) IS NOT NULL
           ) AS da_co,
           count(*) FILTER (
               WHERE coalesce(
                       nullif(btrim(coalesce(l.result_value, '')), ''),
                       nullif(btrim(coalesce(l.external_ref,  '')), '')
                     ) IS NULL
           ) AS con_cho
      FROM lab_result l
     WHERE l.clinic_id = $1::uuid
       AND l.appointment_id IN (SELECT id FROM lich)
     GROUP BY l.appointment_id
)
SELECT g.id, g.slot_start, g.status, g.queue_number, g.booking_channel,
       CASE
         WHEN p.clinic_patient_id IS NULL THEN ''
         WHEN g.slot_start > s.dau_tien  THEN 'Tái khám'
         ELSE 'Khám lần đầu'
       END AS phan_loai,
       coalesce(lb.da_co > 0 AND lb.con_cho = 0, FALSE) AS b3_ready,
       v.checked_in_at,
       p.clinic_patient_id, p.patient_code, p.full_name, p.date_of_birth,
       p.phone_primary, p.phone_secondary, p.gender, p.ethnicity,
       p.nationality, p.occupation, p.patient_objection, p.address,
       p.guardian_name,
       st.name AS service_name,
       -- PHIẾU KHÁM CHỌN THEO GIỚI, và chọn ở SQL chứ không ở trình duyệt.
       --
       -- Trước đây màn hình tự đoán phiếu bằng cách dò từ khoá trong TÊN dịch
       -- vụ ("nam khoa" → NK, "sản" → SK). Sáu trong mười bốn dịch vụ của
       -- Dr4Women không dò ra, và bác sĩ mở lượt khám thì phần phiếu ẩn hẳn,
       -- không một lời nào.
       --
       -- `form_code_nam` chỉ khai cho dịch vụ mà nội dung khám khác nhau theo
       -- giới. Hôm nay đúng một dịch vụ: khám tiền hôn nhân — nữ khám phụ
       -- khoa, nam khám nam khoa. `coalesce` để mọi dịch vụ còn lại dùng chung
       -- một phiếu cho cả hai giới, không phải khai hai lần.
       CASE WHEN p.gender = 'Nam'
            THEN coalesce(st.form_code_nam, st.form_code)
            ELSE st.form_code
       END AS service_form_code,
       cap.slot_minutes
  FROM lich g
  LEFT JOIN patient p
         ON p.clinic_patient_id = g.clinic_patient_id
        AND p.clinic_id = $1::uuid
  LEFT JOIN som_nhat s ON s.clinic_patient_id = g.clinic_patient_id
  LEFT JOIN lab      lb ON lb.appointment_id  = g.id
  LEFT JOIN service_type st ON st.id = g.service_type_id
  -- Một lịch hẹn chỉ có một lượt khám (đã kiểm trên prod: tối đa 1). LATERAL +
  -- LIMIT 1 để một ngày dữ liệu lệch không nhân đôi dòng của cả bảng.
  LEFT JOIN LATERAL (
      SELECT vi.checked_in_at FROM visit vi
       WHERE vi.appointment_id = g.id AND vi.clinic_id = $1::uuid
       ORDER BY vi.checked_in_at NULLS LAST
       LIMIT 1
  ) v ON TRUE
  -- Độ dài khung của CHÍNH lịch này → cửa sổ "đến đúng giờ" của luật gọi.
  -- Cùng hàm mà trigger sức chứa dùng, nên bảng gọi số và bộ nhận lịch không
  -- thể hiểu khác nhau về độ dài một khung.
  LEFT JOIN LATERAL public.resolve_effective_cap(
      $1::uuid, g.doctor_id, g.slot_start
  ) cap ON TRUE
 ORDER BY g.slot_start, g.created_at, g.id
"""
    % MAX_ROWS
)


class DoctorBoardService:
    """Lịch hẹn trong một khoảng, kèm phân loại khám và cờ chờ đọc kết quả."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def board(
        self,
        *,
        clinic_id: str,
        start: datetime,
        end: datetime,
        doctor_id: str | None,
        statuses: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_SQL, clinic_id, start, end, doctor_id, statuses)

        logger.info(
            "doctor_board",
            clinic_id=clinic_id,
            doctor_id=doctor_id,
            rows=len(rows),
        )
        quyet_dinh = thu_tu_goi_theo_ngay(rows)
        return [_row_to_dict(r, quyet_dinh.get(str(r["id"]))) for r in rows]


def _row_to_dict(r: asyncpg.Record, d: QueueDecision | None = None) -> dict[str, Any]:
    """Đúng hình dạng ``DoctorApptRow`` (TSX) đang đọc.

    ``checked_in_at`` trả PHẲNG chứ không bọc trong mảng ``visit``: bản cũ nhận
    mảng từ PostgREST rồi tự lấy phần tử đầu, và "phần tử đầu" của một mảng
    không có thứ tự là một phép chọn ngẫu nhiên. Ở đây việc chọn đã xong, có
    thứ tự, trong database.
    """
    return {
        "id": str(r["id"]),
        "slot_start": r["slot_start"].isoformat(),
        "status": r["status"],
        "queue_number": r["queue_number"],
        "booking_channel": r["booking_channel"],
        "phan_loai": r["phan_loai"],
        "b3_ready": r["b3_ready"],
        "checked_in_at": (
            r["checked_in_at"].isoformat() if r["checked_in_at"] else None
        ),
        # Thứ tự gọi tính SẴN ở đây. Trước đây ba màn nhân viên mỗi màn tự gọi
        # `compareQueue` trong TSX từ một bản chép của luật — nay chúng chỉ đọc
        # con số này. Ngày nào không xếp được thì để trống, màn hình giữ nguyên
        # thứ tự SQL trả về (theo giờ hẹn) thay vì đoán.
        "call_order": d.call_order if d else None,
        "call_tier": d.call_tier if d else None,
        "call_reason": d.call_reason if d else None,
        "promoted": d.promoted if d else False,
        "promoted_over": d.promoted_over if d else 0,
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
        "service": (
            {
                "name": r["service_name"],
                # `None` = dịch vụ này KHÔNG có phiếu khám chuyên khoa (thủ
                # thuật, tư vấn). Màn hình phải nói ra điều đó thay vì ẩn — bác
                # sĩ không phân biệt được "không cần phiếu" với "hệ thống hỏng".
                "form_code": r["service_form_code"],
            }
            if r["service_name"]
            else None
        ),
    }
