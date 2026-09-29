"""Trạng thái lịch hẹn KHÔNG còn giữ chỗ — MỘT danh sách cho cả phía Python.

Trước 29/09/2026 danh sách này chép ở bốn nơi: `lib/slot-capacity.ts`,
`lib/thong-ke-khung-gio.ts`, trigger `enforce_slot_capacity` và
`man_dat_lich_doc.py` (cộng vài bản rời trong các service). Trình duyệt nay
không giữ bản nào nữa — máy chủ trả sẵn số ghế và cờ `giu_cho`.

SQL vẫn giữ bản của nó (trigger chạy trong Postgres, không đọc được Python),
nhưng `src/tests/db/test_trang_thai_chet_khop_sql.py` so hai bên từng chữ: sửa
một bên mà quên bên kia thì test đỏ.
"""

from __future__ import annotations

#: Huỷ / không đến / bác sĩ từ chối chờ phân lại — không chiếm ghế của ai.
DEAD_STATUSES: frozenset[str] = frozenset({"CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"})


def giu_cho(status: str | None) -> bool:
    """Lịch ở trạng thái này có còn chiếm một ghế trong khung không."""
    return (status or "").strip() not in DEAD_STATUSES
