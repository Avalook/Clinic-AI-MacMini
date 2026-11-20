"""Service and procedure tracking on ``service_log`` (W5, ADR-0012).

Chỉ còn phần THUẦN (từ vựng trạng thái + hàm dựng patch) mà router
``service_log`` lấy kiểu và test dùng. Đường GHI của hai rail này (``/service-log``
và ``/sono/queue``) đã nghỉ — router trả 410, ghi qua chỉ định mới — nên lớp dịch
vụ ghi bảng ``service_log`` đã gỡ.

Hai từ vựng trên một bảng, CỐ Ý giữ nguyên: một màn ghi trạng thái tiếng Việt,
màn kia ghi tiếng Anh, mỗi bên chỉ đọc lại dòng của mình. Gộp chúng là một
migration dữ liệu cộng hai màn đổi — không sửa lén ở đây.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, Literal

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole

# The general worklist (Vietnamese vocabulary).
TASK_WAITING = "Chờ làm"
TASK_IN_PROGRESS = "Đang làm"
TASK_DONE = "Hoàn tất"

# The ultrasound nurse's queue (English vocabulary).
QUEUE_WAITING = "WAITING"
QUEUE_IN_PROGRESS = "IN_PROGRESS"
QUEUE_DONE = "DONE"
QUEUE_CANCELLED = "CANCELLED"

TaskAction = Literal["start", "finish"]
QueueAction = Literal["start", "finish", "cancel"]
Milestone = Literal["sample", "sendlab", "result"]

# A lab row's three milestones are independent timestamps, not a status.
MILESTONE_COLUMN: dict[str, str] = {
    "sample": "started_at",
    "sendlab": "sent_to_lab_at",
    "result": "finished_at",
}

# The sono screen is the ultrasound nurse's own queue.
SONO_ROLES: frozenset[ClinicRole] = frozenset(
    {ClinicRole.NURSE_ULTRASOUND, ClinicRole.MANAGEMENT}
)


def source_ref(prefix: str) -> str:
    """``service_log.source_ref`` is UNIQUE and shared with the import pipeline."""
    return f"{prefix}-{int(datetime.now().timestamp() * 1000)}-{secrets.token_hex(4)}"


def task_patch(action: str, result_text: str | None) -> dict[str, Any]:
    """Columns to set for a worklist transition. Pure, so it is testable."""
    if action == "start":
        return {"started_at": "now", "status": TASK_IN_PROGRESS}
    if action == "finish":
        return {
            "finished_at": "now",
            "status": TASK_DONE,
            "result_text": (result_text or "").strip() or None,
        }
    raise ValidationError(f"Hành động không hợp lệ: {action!r}")


def queue_patch(action: str) -> dict[str, Any]:
    """Columns to set for an ultrasound-queue transition."""
    if action == "start":
        return {"started_at": "now", "status": QUEUE_IN_PROGRESS}
    if action == "finish":
        return {"finished_at": "now", "status": QUEUE_DONE}
    if action == "cancel":
        # Cancelling leaves the timestamps alone: what did happen still happened.
        return {"status": QUEUE_CANCELLED}
    raise ValidationError(f"Hành động không hợp lệ: {action!r}")
