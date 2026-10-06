"""Quầy chốt hoá đơn dịch vụ 0đ — ghi nhận, không phải lần thu (Tuyền 06/10/2026).

DB cấm lần thu 0đ (`payment_cycle.amount > 0`), nên dòng 0đ (khám không tính
tiền…) không bao giờ được một lần thu phủ → lượt nằm mãi ở "chờ thu". Bấm
"Chốt dịch vụ" ghi một dòng `event_log` mang `revision` hoá đơn lúc chốt; quầy
coi lượt đã xong tiền khi revision ấy còn khớp hoá đơn hiện tại — chỉ định thêm
sau đó đổi revision, lượt quay lại hàng chờ.

Module riêng vì `bill_service` đã import `cashier_board_service`: để
`payment_service` giữ hàm này thì quầy import ngược thành vòng.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.services.audit import record_event

if TYPE_CHECKING:
    from clinicai.services.bill_service import HoaDon

CHOT_0D = "payment.service_zero_confirmed"


async def ghi_chot_0d(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    visit_id: str,
    hoa_don: HoaDon,
) -> None:
    """Ghi nhận quầy đã chốt — chỉ khi còn dòng phòng khám thu."""
    if not hoa_don.dong:
        return
    await record_event(
        conn,
        event_type=CHOT_0D,
        aggregate_type="visit",
        aggregate_id=visit_id,
        identity=identity,
        origin="api:payment",
        payload={"visit_id": visit_id, "revision": hoa_don.revision},
    )


async def doc_chot_0d(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: Sequence[str]
) -> dict[str, set[str]]:
    """visit_id → các revision hoá đơn dịch vụ quầy đã chốt 0đ."""
    if not visit_ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT aggregate_id::text AS aggregate_id, payload->>'revision' AS revision
          FROM event_log
         WHERE clinic_id = $1::uuid AND aggregate_type = 'visit'
           AND aggregate_id = ANY($2::uuid[]) AND event_type = $3
        """,
        clinic_id,
        list(visit_ids),
        CHOT_0D,
    )
    out: dict[str, set[str]] = {}
    for r in rows:
        out.setdefault(r["aggregate_id"], set()).add(r["revision"])
    return out


def da_chot_0d(hoa_don: HoaDon, revisions: set[str] | None) -> bool:
    """Hoá đơn 0đ (có dòng, không vấn đề) đã được quầy chốt đúng bản này."""
    return bool(
        revisions
        and hoa_don.dong
        and hoa_don.tong <= 0
        and not hoa_don.van_de
        and hoa_don.revision in revisions
    )
