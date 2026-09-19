"""MỘT câu cho "bác sĩ đã khám xong lượt này" (review CP4, 19/09/2026).

Nhà thuốc, Thu ngân và Payment phải hiểu cùng một câu. Trước bản này cả ba
đọc `appointment.status = 'COMPLETED'` — nhưng `visit.appointment_id` được
phép rỗng, nên một lượt không có lịch hẹn không bao giờ "khám xong" được: kẹt
ở Nhà thuốc và biến mất khỏi Thu ngân.

MỐC CHUẨN là của LƯỢT KHÁM: `visit.exam_completed_at`, ghi khi bác sĩ bấm Khám
xong (`luot_kham_service._khep_luot`), có lịch hẹn hay không.

NHÁNH TƯƠNG THÍCH DỮ LIỆU CŨ: lượt khám trước luồng lượt khám chỉ có lịch hẹn
COMPLETED mà không có `exam_completed_at`. Nhánh ấy KHÔNG phải nguồn sự thật
mới — đường ghi mới luôn ghi `exam_completed_at`.
"""

from __future__ import annotations


def kham_xong_sql(v: str) -> str:
    """Biểu thức SQL boolean cho lượt có bí danh bảng ``v`` (bảng `visit`)."""
    return (
        f"({v}.exam_completed_at IS NOT NULL"
        # Tương thích dữ liệu cũ (xem đầu file) — không phải nguồn sự thật mới.
        f" OR EXISTS (SELECT 1 FROM public.appointment a_kx"
        f" WHERE a_kx.id = {v}.appointment_id AND a_kx.clinic_id = {v}.clinic_id"
        f" AND a_kx.status = 'COMPLETED'))"
    )
