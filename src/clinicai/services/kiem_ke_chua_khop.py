"""Câu nói dòng kiểm kê ca "Chưa khớp" — vì sao và sửa thế nào, đủ để nhân viên tự
hiểu (Tuyền 20/11/2026).

VÌ SAO. Staging 20/11: phiếu cuối ca gõ Eluna = 0 lúc 11:34 khi sổ còn 1, 11:39 mới
bán 1, chốt 11:41 → lệch −1 không trừ được (quầy đã 0). Câu cũ "Quầy không còn đủ
tồn … thuốc đã đi sau lúc đếm" đúng nhưng không nói đếm lúc nào, bán lúc nào, nên
người thử tưởng máy trừ hai lần. Câu mới kể đúng thứ tự từ sổ kho + cách sửa.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.core.clock import CLINIC_TZ


def _so(v: Decimal) -> str:
    s = format(v.normalize(), "f")
    return s if "." not in s else s.rstrip("0").rstrip(".")


def _gio(t: datetime) -> str:
    return t.astimezone(CLINIC_TZ).strftime("%H:%M")


def cau_chua_khop(
    *,
    don_vi: str,
    dem: Decimal,
    ton_may: Decimal,
    moc: datetime,
    ra_sau: list[tuple[datetime, Decimal]],
) -> str | None:
    """Câu cho dòng lệch ÂM không trừ hết vì quầy đã bán / giao SAU lúc đếm.
    `ra_sau` = (giờ, số) các lần giao ròng sau mốc đếm. Không có lần nào → None
    (người gọi giữ câu chung). Thuần."""
    tong = sum((so for _, so in ra_sau), Decimal(0))
    if tong <= 0:
        return None
    dau, cuoi = _gio(ra_sau[0][0]), _gio(ra_sau[-1][0])
    khi = f"lúc {dau}" if dau == cuoi else f"từ {dau} tới {cuoi}"
    return (
        f"Quầy không còn đủ để trừ phần lệch: đếm {_so(dem)} {don_vi} lúc"
        f" {_gio(moc)} khi sổ còn {_so(ton_may)}; sau đó bán / giao {_so(tong)}"
        f" {don_vi} {khi} — số đếm có trước lần bán. Đếm nhầm thì Hoàn tác phiếu"
        " → Sửa số đếm; kệ thật thiếu thì đếm lại, lập phiếu kiểm đột xuất."
    )


async def cau_cho_dong(
    conn: asyncpg.Connection, clinic_id: str, location_id: str, dong: Any
) -> str | None:
    """Câu "Chưa khớp" cho một dòng của `_tinh_lech` (cần `thuoc`, `don_vi`, `dem`,
    `ton_may`, `moc`, `lech`). None khi không dựng được câu cụ thể hơn câu chung:
    lệch dương (thiếu lô để cộng — câu chung đã đúng) hoặc không có mốc đếm."""
    if dong["moc"] is None or dong["lech"] >= 0:
        return None
    rows = await conn.fetch(
        """
        SELECT t.performed_at AS luc, sum(-t.quantity) AS so
          FROM public.inventory_txn t
          JOIN public.drug_batch b ON b.id = t.drug_batch_id
         WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid
           AND b.noi_chua = 'QUAY' AND b.drug_catalog_id = $3::uuid
           AND lower(btrim(b.unit)) = $4
           AND t.txn_type IN ('DISPENSE', 'DISPENSE_REVERSAL')
           AND t.performed_at > $5
         GROUP BY t.performed_at
        HAVING sum(-t.quantity) <> 0
         ORDER BY t.performed_at
        """,
        clinic_id,
        location_id,
        dong["thuoc"],
        dong["don_vi"],
        dong["moc"],
    )
    return cau_chua_khop(
        don_vi=dong["don_vi"],
        dem=Decimal(str(dong["dem"])),
        ton_may=Decimal(str(dong["ton_may"])),
        moc=dong["moc"],
        ra_sau=[(r["luc"], Decimal(str(r["so"]))) for r in rows],
    )
