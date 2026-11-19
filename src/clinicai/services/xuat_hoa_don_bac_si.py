"""Bác sĩ chỉ định + bác sĩ thực hiện của từng dòng hoá đơn khi xuất (Tuyền 19/11/2026).

Kế toán cần biết bác sĩ của từng dòng hàng. Luật chung (Tuyền 29/09,
`bac_si_ky`): ở chỗ ghi "bác sĩ" KHÔNG BAO GIỜ hiện tên người không phải bác sĩ —
mọi nguồn dưới đây đều lọc qua `sql_bac_si_dau_tien` (vai DOCTOR /
ULTRASOUND_DOCTOR còn hoạt động); không ai là bác sĩ → trống (trừ ngoại lệ
"người bấm" của cột thực hiện, dưới). Không suy theo lịch
/ làn (luật tính lương 09/11 là việc khác).

* Dịch vụ: chỉ định = `sql_join_bac_si_chi_dinh` — CÙNG hàm "BS chỉ định" của các
  màn khác (người duyệt → người ghi → BS chính của lượt → BS lịch hẹn). Bẫy đã
  cắn (staging 19/11): thư ký / điều dưỡng bấm hộ thì máy ghi CHÍNH họ vào
  `authorized_by` (luật 23/09 "không bịa tên bác sĩ khác") — đọc thẳng cột ấy
  là hiện tên thư ký ở cột bác sĩ. Thực hiện = `bac_si_lam_id`; máy không ghép
  được (lịch chưa có bác sĩ lúc làm) → người bấm Hoàn tất `performed_by` kèm
  hậu tố "(người bấm)" — ngoại lệ Tuyền chốt 19/11, chỉ ở màn/file này.
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

from clinicai.services.bac_si_ky import sql_bac_si_dau_tien, sql_join_bac_si_chi_dinh

COT_BS_CHI_DINH = 18
COT_BS_THUC_HIEN = 19
TIEU_DE_BAC_SI = (
    (COT_BS_CHI_DINH, "Bác sĩ chỉ định"),
    (COT_BS_THUC_HIEN, "Bác sĩ thực hiện"),
)
# Máy không ghép được bác sĩ (lúc làm phòng chưa có bác sĩ trên lịch) → ghi người
# bấm Hoàn tất, có hậu tố để kế toán không đọc nhầm là bác sĩ (Tuyền 19/11).
HAU_TO_NGUOI_BAM = " (người bấm)"


def _bac_si(cot: str, ten: str) -> str:
    """LEFT JOIN LATERAL: `cot` → (id, full_name) nếu người đó LÀ bác sĩ."""
    con = sql_bac_si_dau_tien([cot], "bl.clinic_id")
    return f"LEFT JOIN LATERAL ({con}) {ten} ON true"


_BAC_SI_DONG = f"""
SELECT bl.id::text id,
 coalesce(bscd.full_name, bsrx.full_name) bs_chi_dinh,
 coalesce(bsth.full_name, bskh.full_name,
  nb.full_name || '{HAU_TO_NGUOI_BAM}') bs_thuc_hien
FROM payment_bill_line bl
LEFT JOIN service_order o ON bl.source_type='service_order'
 AND o.clinic_id=bl.clinic_id AND o.id::text=bl.source_id
LEFT JOIN staff nb ON nb.id=o.performed_by
-- rx:gom-ca-lich-su: dòng đã thu trỏ dòng đơn lúc thu, kể cả dòng đã đính chính
LEFT JOIN prescription rx ON bl.source_type='prescription'
 AND rx.clinic_id=bl.clinic_id AND rx.id::text=bl.source_id
LEFT JOIN LATERAL (
 SELECT c.doctor_staff_id FROM consultation c
 WHERE bl.source_type='exam' AND c.clinic_id=bl.clinic_id
   AND c.visit_id=bl.visit_id AND c.kind='PRIMARY'
 ORDER BY c.round_no LIMIT 1) kham ON true
{sql_join_bac_si_chi_dinh("o", "bscd")}
{_bac_si("rx.bac_si_chinh_id", "bsrx")}
{_bac_si("o.bac_si_lam_id", "bsth")}
{_bac_si("kham.doctor_staff_id", "bskh")}
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
