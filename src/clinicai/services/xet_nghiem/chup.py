"""Chụp việc đối tác lúc chỉ định (kế hoạch 4.3).

MỘT hàm chụp, gọi từ mỗi chỗ tạo chỉ định (bác sĩ duyệt `authorize_orders`, mở phiên
`dat_chi_dinh`, làm thêm tại quầy `_tick`) bằng đúng một dòng, cùng giao dịch với
INSERT service_order. Không luật nào ở chỗ gọi.

Dịch vụ có đối tác MẶC ĐỊNH còn hoạt động (cả dòng gán lẫn đối tác) ⇒ một dòng
`xet_nghiem_viec` chụp đối tác + giá gợi ý lúc đó. Đổi gán sau này không đổi dòng
cũ. Gọi lại an toàn (khoá chính service_order_id, ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

from collections.abc import Sequence

import asyncpg

#: Giá gợi ý: giá của cặp (đối tác, dịch vụ) > giá bảng giá; 0/NULL ⇒ để trống (câu 6).
_CHUP_SQL = """
INSERT INTO public.xet_nghiem_viec
    (service_order_id, clinic_id, doi_tac_id, gia_goi_y_luc_chi_dinh)
SELECT o.id, o.clinic_id, a.doi_tac_id,
       nullif(coalesce(a.gia_goi_y, sp.unit_price), 0)
  FROM public.service_order o
  JOIN public.service_price sp
    ON sp.clinic_id = o.clinic_id AND sp."group" = 'dich_vu'
   AND sp.service_code = o.service_code
  JOIN public.doi_tac_dich_vu a
    ON a.clinic_id = o.clinic_id AND a.service_price_id = sp.id
   AND a.mac_dinh AND a.ngung_luc IS NULL
  JOIN public.doi_tac d
    ON d.clinic_id = a.clinic_id AND d.id = a.doi_tac_id AND d.ngung_luc IS NULL
 WHERE o.clinic_id = $1::uuid AND o.id = ANY($2::uuid[])
ON CONFLICT (service_order_id) DO NOTHING
"""


async def tao_viec_neu_doi_tac(
    conn: asyncpg.Connection, *, clinic_id: str, order_ids: Sequence[str]
) -> None:
    """Gọi trong giao dịch tạo chỉ định. Không có dịch vụ đối tác ⇒ không làm gì."""
    if order_ids:
        await conn.execute(_CHUP_SQL, clinic_id, list(order_ids))


async def chep_viec(
    conn: asyncpg.Connection, *, clinic_id: str, tu_order: str, sang_order: str
) -> None:
    """Chỉ định mới THAY chỉ định cũ (hoàn tác ở sổ sửa chỉ định) giữ đúng đối tác đã
    chụp của dòng cũ — không chụp lại theo gán hiện tại. Dòng cũ không có chụp ⇒
    thôi (việc ở lại luồng cũ)."""
    await conn.execute(
        """
        INSERT INTO public.xet_nghiem_viec
            (service_order_id, clinic_id, doi_tac_id, gia_goi_y_luc_chi_dinh)
        SELECT $3::uuid, v.clinic_id, v.doi_tac_id, v.gia_goi_y_luc_chi_dinh
          FROM public.xet_nghiem_viec v
         WHERE v.clinic_id = $1::uuid AND v.service_order_id = $2::uuid
        ON CONFLICT (service_order_id) DO NOTHING
        """,
        clinic_id,
        tu_order,
        sang_order,
    )
