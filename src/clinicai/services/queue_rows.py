"""Cầu nối giữa HÀNG DỮ LIỆU và luật thứ tự gọi.

`queue_order.py` phải giữ THUẦN — không import gì chạm database — nên nó không
biết một hàng SQL trông thế nào, cũng không biết đọc cấu hình khung giờ. Còn ba
service nuôi ba bảng lịch (hàng chờ, bảng bác sĩ, lưới tuần) đều cần đúng một
việc: đổi hàng SQL thành `QueueEntry`, gom theo ngày làm việc, rồi hỏi luật.

Viết ba lần là ba cơ hội để chúng lệch nhau — đúng thứ vừa mới phải dọn xong ở
bản TypeScript. Nên nó nằm ở đây, đúng một bản.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.clinic_policy import grace_ms_from_slot_minutes
from clinicai.services.queue_order import (
    QueueDecision,
    QueueEntry,
    explain_queue,
)


def entry_from_row(row: Mapping[str, Any], *, id_key: str = "id") -> QueueEntry:
    """Một hàng SQL → một dòng hàng chờ.

    Các khoá phải có: ``slot_start``, ``queue_number``, ``booking_channel``,
    ``checked_in_at``, ``slot_minutes``. ``doctor_id`` và ``b3_ready`` là tuỳ —
    thiếu thì coi như chưa xếp bác sĩ và chưa có kết quả về.
    """
    doctor_id = row.get("doctor_id")
    return QueueEntry(
        appointment_id=str(row[id_key]),
        doctor_id=str(doctor_id) if doctor_id else None,
        queue_number=row["queue_number"],
        slot_start=row["slot_start"],
        checked_in_at=row["checked_in_at"],
        booking_channel=row["booking_channel"],
        grace_ms=grace_ms_from_slot_minutes(row.get("slot_minutes")),
        b3_ready=bool(row.get("b3_ready")),
        visit_status=row.get("visit_status"),
    )


def thu_tu_goi_theo_ngay(
    rows: Sequence[Mapping[str, Any]], *, id_key: str = "id"
) -> dict[str, QueueDecision]:
    """Thứ tự gọi, tính RIÊNG cho từng ngày làm việc, khoá theo mã lịch hẹn.

    VÌ SAO CẮT THEO NGÀY: "người được gọi tiếp theo" chỉ có nghĩa trong một
    buổi. Bảng bác sĩ nhìn tới 31 ngày và lưới trang chủ nhìn 7 ngày — xếp
    chung cả khoảng thành một hàng duy nhất sẽ cho ra những con số thứ tự vô
    nghĩa, kiểu "người thứ 214 của tháng".

    Ngày cắt theo giờ VIỆT NAM, không theo giờ máy chủ. Máy chủ chạy UTC, nên
    một lịch 7 giờ sáng giờ Việt Nam là 0 giờ cùng ngày UTC — trùng nhau; nhưng
    một lịch 6 giờ chiều là 11 giờ sáng UTC, và nếu có ca tối muộn thì ranh
    giới ngày UTC cắt ngay giữa buổi làm việc.
    """
    theo_ngay: dict[str, list[QueueEntry]] = {}
    for row in rows:
        ngay = row["slot_start"].astimezone(CLINIC_TZ).date().isoformat()
        theo_ngay.setdefault(ngay, []).append(entry_from_row(row, id_key=id_key))

    out: dict[str, QueueDecision] = {}
    for entries in theo_ngay.values():
        for d in explain_queue(entries):
            out[d.entry.appointment_id] = d
    return out
