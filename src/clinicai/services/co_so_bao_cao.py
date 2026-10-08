"""Lọc báo cáo theo CƠ SỞ (08/10/2026 — mở cơ sở thứ hai Hào Nam).

Cơ sở của một lượt = ``coalesce(visit.location_id, appointment.location_id)``:
vài lượt cũ (và hai chỗ tạo lượt chưa điền) để trống ``visit.location_id``
nhưng lịch hẹn của lượt thì luôn có cơ sở (cột NOT NULL).

Tham số ``co_so`` từ người dùng: rỗng = tất cả cơ sở; UUID hợp lệ = một cơ sở;
RÁC = một mã không khớp cơ sở nào → mọi con số về 0. Không ném (luật đầu vào
người dùng — CLAUDE.md), và không lặng lẽ rơi về "tất cả": người hỏi một cơ sở
mà nhận số của cả phòng khám là nhận sai số mà không biết.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg

#: Mã không khớp cơ sở nào — ``co_so`` rác lọc ra rỗng.
KHONG_KHOP = "00000000-0000-0000-0000-000000000000"

#: Nhãn cho phần số liệu không gắn được cơ sở nào (lượt không cơ sở, không lịch
#: hẹn; lần thu không gắn lượt). Giữ thành một dòng riêng để TỔNG = CỘNG PHẦN.
TEN_CHUA_RO = "Chưa rõ cơ sở"


def doc_co_so(v: Any) -> str | None:
    """Rỗng → None (tất cả); UUID → dạng chuẩn; rác → ``KHONG_KHOP``. Không ném."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return str(uuid.UUID(s))
    except ValueError:
        return KHONG_KHOP


async def doc_ds_co_so(
    conn: asyncpg.Connection | asyncpg.Pool, clinic_id: str
) -> list[dict[str, str]]:
    """Cơ sở của phòng khám, theo tên — cùng thứ tự với ``/catalog/locations``."""
    rows = await conn.fetch(
        "SELECT id::text AS id, name FROM clinic_location"
        " WHERE clinic_id = $1::uuid ORDER BY name",
        clinic_id,
    )
    return [{"id": r["id"], "ten": r["name"]} for r in rows]
