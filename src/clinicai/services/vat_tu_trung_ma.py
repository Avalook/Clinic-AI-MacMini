"""Mặt hàng ở danh mục THUỐC mà thật ra là VẬT TƯ: `drug_catalog.ma_hang` trùng
`service_price.ma_kiotviet` nhóm vat_tu (đầu dò Bio SP000152/153, 31/10/2026).

Tuyền: giữ nguyên nút "Lấy thêm" ở quầy thuốc, tiền vẫn là tiền thuốc, nhưng tồn
trừ ở Kho vật tư. Tách riêng khỏi `vat_tu_ban_service` vì `pharmacy_service` cần
hỏi câu này mà không được import ngược về phía kho vật tư.
"""

from __future__ import annotations

from collections.abc import Iterable

import asyncpg

#: `$1` = phòng khám, `{thuoc}` = cột mã thuốc của câu ngoài. Chỉ khớp khi mã có
#: thật và trỏ tới ĐÚNG MỘT vật tư; mã rỗng, không có bên vật tư, hay trùng nhiều
#: vật tư thì giữ như thuốc thường — đoán nhầm là trừ nhầm kho.
VAT_TU_CUA_THUOC = """
(SELECT CASE WHEN count(*) = 1 THEN (array_agg(sp.id))[1] END
   FROM public.drug_catalog d
   JOIN public.service_price sp
     ON sp.clinic_id = d.clinic_id AND sp."group" = 'vat_tu'
    AND btrim(sp.ma_kiotviet) = btrim(d.ma_hang) AND btrim(d.ma_hang) <> ''
  WHERE d.clinic_id = $1::uuid AND d.id = {thuoc})
"""


async def thuoc_la_vat_tu(
    conn: asyncpg.Connection, clinic_id: str, thuoc_ids: Iterable[str | None]
) -> set[str]:
    """Những mã thuốc trong `thuoc_ids` thật ra là vật tư."""
    ds = sorted({str(t) for t in thuoc_ids if t})
    if not ds:
        return set()
    rows = await conn.fetch(
        "SELECT x.id::text AS id FROM unnest($2::uuid[]) AS x(id)"
        f" WHERE {VAT_TU_CUA_THUOC.format(thuoc='x.id')} IS NOT NULL",
        clinic_id,
        ds,
    )
    return {r["id"] for r in rows}


__all__ = ["VAT_TU_CUA_THUOC", "thuoc_la_vat_tu"]
