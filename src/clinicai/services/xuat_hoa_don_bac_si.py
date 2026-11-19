"""Bác sĩ chỉ định + bác sĩ thực hiện của từng dòng hoá đơn khi xuất (Tuyền 19/11/2026).

Kế toán cần biết bác sĩ của từng dòng hàng. Lấy ĐÚNG như máy đã ghi, không suy
theo lịch / làn (luật tính lương 09/11 là việc khác); không có thì để trống:

* Dịch vụ: chỉ định = `service_order.authorized_by` (người ký chỉ định — KHÔNG
  lấy `recorded_by`: đó có thể là điều dưỡng gõ hộ, không phải bác sĩ chỉ định);
  thực hiện = `service_order.bac_si_lam_id`.
* Thuốc: chỉ định = bác sĩ kê `prescription.bac_si_chinh_id`.
* Khám: thực hiện = bác sĩ của phiên khám chính (`consultation` PRIMARY).

Excel: hai cột NGOÀI mẫu MISA (R, S) — 17 cột của mẫu giữ nguyên.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import copy
from typing import Any

import asyncpg
from openpyxl.utils import get_column_letter

COT_BS_CHI_DINH = 18
COT_BS_THUC_HIEN = 19
TIEU_DE_BAC_SI = (
    (COT_BS_CHI_DINH, "Bác sĩ chỉ định"),
    (COT_BS_THUC_HIEN, "Bác sĩ thực hiện"),
)

_BAC_SI_DONG = """
SELECT bl.id::text id, st_cd.full_name bs_chi_dinh, st_th.full_name bs_thuc_hien
FROM payment_bill_line bl
LEFT JOIN service_order o ON bl.source_type='service_order'
 AND o.clinic_id=bl.clinic_id AND o.id::text=bl.source_id
-- rx:gom-ca-lich-su: dòng đã thu trỏ dòng đơn lúc thu, kể cả dòng đã đính chính
LEFT JOIN prescription rx ON bl.source_type='prescription'
 AND rx.clinic_id=bl.clinic_id AND rx.id::text=bl.source_id
LEFT JOIN LATERAL (
 SELECT c.doctor_staff_id FROM consultation c
 WHERE bl.source_type='exam' AND c.clinic_id=bl.clinic_id
   AND c.visit_id=bl.visit_id AND c.kind='PRIMARY'
 ORDER BY c.round_no LIMIT 1) kham ON true
LEFT JOIN staff st_cd ON st_cd.id=coalesce(o.authorized_by, rx.bac_si_chinh_id)
LEFT JOIN staff st_th ON st_th.id=coalesce(o.bac_si_lam_id, kham.doctor_staff_id)
WHERE bl.clinic_id=$1::uuid AND bl.payment_cycle_id=ANY($2::uuid[])
"""


async def doc_bac_si_dong(
    conn: asyncpg.Connection, clinic_id: str, phieu_ids: Sequence[str]
) -> dict[str, dict[str, str]]:
    """{id dòng hoá đơn: {bs_chi_dinh, bs_thuc_hien}} — chưa ghi thì chuỗi rỗng."""
    return {
        r["id"]: {
            "bs_chi_dinh": r["bs_chi_dinh"] or "",
            "bs_thuc_hien": r["bs_thuc_hien"] or "",
        }
        for r in await conn.fetch(_BAC_SI_DONG, clinic_id, list(phieu_ids))
    }


def _chu(cell: Any, value: str) -> None:
    """Ghi CHỮ — tên bắt đầu bằng "=" không bao giờ thành công thức."""
    cell.value = value
    cell.data_type = "s"


def them_cot_bac_si(ws: Any) -> None:
    """Tiêu đề R, S mặc áo tiêu đề cột Q, rộng như cột M (tối thiểu 24)."""
    for c, ten in TIEU_DE_BAC_SI:
        o = ws.cell(1, c)
        o._style = copy(ws.cell(1, 17)._style)
        _chu(o, ten)
        ws.column_dimensions[get_column_letter(c)].width = max(
            ws.column_dimensions["M"].width or 0, 24
        )


def ghi_bac_si_dong(ws: Any, r: int, dong: Mapping[str, Any], kieu: Any) -> None:
    """Ghi bác sĩ vào dòng `r` — MỌI dòng (một hoá đơn có nhiều bác sĩ)."""
    for c, ten in (
        (COT_BS_CHI_DINH, dong.get("bs_chi_dinh")),
        (COT_BS_THUC_HIEN, dong.get("bs_thuc_hien")),
    ):
        ws.cell(r, c)._style = copy(kieu)
        if ten:
            _chu(ws.cell(r, c), str(ten))
