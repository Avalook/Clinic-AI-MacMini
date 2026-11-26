"""Giao thuốc chỉ cho dòng ĐÃ nằm trong lần thu PAID (giả lập PR D, bất biến I4).

Trước 26/11 lệnh giao (`PharmacyService.giao_trong_giao_dich`) chỉ hỏi "lượt có lần
thu thuốc PAID chưa" — dòng vào đơn SAU lần thu (bác sĩ đính chính, dòng thay thế id
mới mang sẵn thuốc kho) giao được mà chưa ai trả tiền. Giả lập bước 0 tái hiện:
giao thành công, `dispensed_qty` 4 mà không dòng hoá đơn nào phủ.

Lần thu ĐỜI CŨ (`legacy`, hoặc không có dòng hoá đơn nào) không truy được dòng nào đã
trả — giữ luật cũ (giao theo lượt), không đoán.
"""

from __future__ import annotations

import asyncpg

from clinicai.api.exceptions import ConflictError

_LAN_THU_SQL = """
SELECT c.payment_cycle_id::text AS payment_cycle_id, c.legacy,
       EXISTS (SELECT 1 FROM public.payment_bill_line bl
                WHERE bl.clinic_id = c.clinic_id
                  AND bl.payment_cycle_id = c.payment_cycle_id) AS co_dong,
       EXISTS (SELECT 1 FROM public.payment_bill_line bl
                WHERE bl.clinic_id = c.clinic_id
                  AND bl.payment_cycle_id = c.payment_cycle_id
                  AND bl.source_type = 'prescription'
                  AND bl.source_id = $3) AS co_dong_nay
  FROM public.payment_cycle c
 WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
   AND c.kind = 'thuoc' AND c.status = 'PAID'
"""


async def lan_thu_cua_dong(
    conn: asyncpg.Connection, clinic_id: str, visit_id: object, prescription_id: str
) -> asyncpg.Record:
    """Lần thu PAID phủ dòng này; ném 409 câu tiếng Việt nếu chưa thu / chưa phủ."""
    lan = await conn.fetchrow(_LAN_THU_SQL, clinic_id, visit_id, prescription_id)
    if lan is None:
        raise ConflictError(
            "Tiền thuốc của lượt này chưa thu — thu tiền thuốc trước "
            "rồi mới giao thuốc."
        )
    if not lan["legacy"] and lan["co_dong"] and not lan["co_dong_nay"]:
        raise ConflictError(
            "Dòng thuốc này chưa nằm trong lần thu tiền thuốc (thêm vào đơn sau khi "
            "thu) — huỷ phiếu thu rồi thu lại cả dòng này trước khi giao."
        )
    return lan
