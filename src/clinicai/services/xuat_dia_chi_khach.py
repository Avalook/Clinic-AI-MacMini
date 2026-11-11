"""File Excel địa chỉ khách để kế toán rà (chị Hoài, 11/11/2026).

Chị cần danh sách mã BN · họ tên · SĐT · địa chỉ để đánh dấu khách đang sai địa chỉ
rồi vào phần mềm sửa (`/customers` → Thông tin hành chính). Đây là xuất HÀNG LOẠT
SĐT + địa chỉ, nên:

* chỉ người có `accounting.finance.full` (lego Kế toán; Quản lý có sẵn) — cửa ở router;
* lọc ĐÚNG như màn Danh sách bệnh nhân (`bo_loc`: ô tìm + tab, phạm vi thư ký) — file
  ra đúng những dòng người ta đang nhìn, không thêm;
* địa chỉ theo luật chung `dia_chi_khach` (ô sửa được thắng);
* mỗi lần tải ghi nhật ký: số dòng, có tìm không, tab — KHÔNG ghi chữ trong ô tìm
  (có thể là tên / SĐT khách).
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.audit import record_event
from clinicai.services.danh_sach_benh_nhan_loc import (
    CO_SO_SQL,
    bo_loc,
    chuoi_tim,
    doc_loc,
)
from clinicai.services.dia_chi_khach import dia_chi_khach
from clinicai.services.excel_export import excel_table

#: Quyền tải file — router gác bằng đúng hằng số này, màn hỏi đúng chuỗi này.
QUYEN_XUAT = "accounting.finance.full"
#: Trần dòng một file (~8.700 hồ sơ hôm nay). Chạm trần thì file có dòng báo.
TRAN = 20_000
COT: tuple[str, ...] = (
    "Mã BN",
    "Họ tên",
    "SĐT",
    "Địa chỉ",
    "Hoạt động gần nhất",
    "Địa chỉ đúng chưa / ghi chú",
)

# Cùng `CO_SO_SQL` với màn (tham số $1–$7 từ `bo_loc`); $8 = trần. Xếp như màn mặc
# định (hoạt động gần nhất trước, khoá phụ mã khách).
_SQL = (
    CO_SO_SQL
    + """
SELECT p.patient_code, p.full_name, p.phone_primary,
       p.address, p.address_detail, p.ward_name, p.province_name, c.luc
  FROM co_so c
  JOIN patient p
    ON p.clinic_id = $1::uuid AND p.clinic_patient_id = c.clinic_patient_id
 WHERE c.khop
 ORDER BY c.luc DESC, c.clinic_patient_id
 LIMIT $8
"""
)


def _dong(r: Any) -> list[Any]:
    return [
        r["patient_code"],
        r["full_name"],
        r["phone_primary"],
        dia_chi_khach(r) or "",
        r["luc"],
        None,
    ]


async def xuat_dia_chi_khach(
    pool: asyncpg.Pool, *, identity: StaffIdentity, q: Any, loc: Any
) -> bytes:
    """Bytes .xlsx một bảng; tham số rác → như màn (không lọc), không ném."""
    nen = await bo_loc(pool, identity, q=q, loc=loc)
    async with pool.acquire() as conn:
        rows = await conn.fetch(_SQL, *nen, TRAN)
        dong = [_dong(r) for r in rows]
        if canh_bao_neu_day("xuat_dia_chi_khach", len(rows), TRAN):
            dong.append(
                ["", f"Đã cắt ở {TRAN:,} dòng — lọc hẹp lại (ô tìm / tab) để tải đủ."]
                + [None] * (len(COT) - 2)
            )
        await record_event(
            conn,
            event_type="patient.list_exported",
            aggregate_type="patient",
            aggregate_id=str(identity.clinic_id),
            identity=identity,
            origin="api:patients-danh-sach-xlsx",
            payload={
                "so_dong": len(rows),
                "co_tim": bool(chuoi_tim(q)),
                "loc": doc_loc(loc) or "",
            },
        )
    return excel_table([("Địa chỉ khách", COT, dong)])


__all__ = ["COT", "QUYEN_XUAT", "TRAN", "xuat_dia_chi_khach"]
