"""Chọn MẪU KẾT QUẢ cho một dịch vụ — một luật cho cả phòng dịch vụ lẫn phiếu khám.

Tuyền 23/09/2026 khuya: "làm tiếp phần phòng siêu âm điền kết quả". Trước đây
phòng chỉ thấy mẫu ĐÃ GẮN cho dịch vụ (`dich_vu_mau_ket_qua`) — mà chưa dịch vụ
nào được gắn, nên phòng siêu âm mở ra là "chưa gắn mẫu kết quả nào".

Thứ tự:
  1. Mẫu phòng khám đã GẮN cho dịch vụ (quyết định của quản lý) — dùng đúng nó.
  2. Chưa gắn: mẫu GỢI Ý của phiếu v5 (nhãn nguồn → `form_id_ket_qua`, ghép qua
     bảng mã viết tay `anh_xa_danh_muc`) đứng đầu và được chọn sẵn, kèm 18 mẫu
     dự phòng ("Mở nhanh 18 biểu mẫu" của v5) để chọn mẫu khác.
Không tự GẮN gì vào `dich_vu_mau_ket_qua` — gợi ý chỉ là lựa chọn mặc định lúc
mở phiếu; gắn chính thức vẫn là việc của quản lý.
"""

from __future__ import annotations

from functools import cache
from typing import Any

import asyncpg

from clinicai.phieu_kham import anh_xa_danh_muc as ax
from clinicai.phieu_kham.khung import tham_chieu_nguon


@cache
def _goi_y_theo_ma() -> dict[str, str]:
    """service_code → mã mẫu (không kèm `KQ_`), theo nhãn nguồn v5."""
    tc = tham_chieu_nguon()
    ra: dict[str, str] = {}
    for nhom in tc["chi_dinh_cls"]:
        for m in nhom["muc"]:
            dv = ax.CLS.get(m["nhan"])
            if dv and m.get("form_id_ket_qua"):
                ra.setdefault(dv.ma, m["form_id_ket_qua"].removeprefix("KQ_"))
    for t in tc["thu_thuat"]:
        dv = ax.THU_THUAT.get(t["ma"])
        if dv and t.get("form_id_ket_qua"):
            ra.setdefault(dv.ma, t["form_id_ket_qua"].removeprefix("KQ_"))
    return ra


def ma_mau_goi_y(service_code: str) -> str | None:
    return _goi_y_theo_ma().get(service_code)


async def mau_cho_dich_vu(
    conn: asyncpg.Connection, *, clinic_id: str, service_code: str
) -> tuple[list[dict[str, Any]], str | None]:
    """(danh sách mẫu để chọn, mẫu chọn sẵn)."""
    da_gan = [
        dict(r)
        for r in await conn.fetch(
            "SELECT m.ma, m.ten, m.nhom FROM dich_vu_mau_ket_qua d"
            "  JOIN ket_qua_mau m ON m.clinic_id = d.clinic_id AND m.ma = d.mau"
            "   AND m.active"
            " WHERE d.clinic_id = $1::uuid AND d.service_code = $2"
            " ORDER BY m.ten",
            clinic_id,
            service_code,
        )
    ]
    if da_gan:
        return da_gan, da_gan[0]["ma"]
    tat_ca = [
        dict(r)
        for r in await conn.fetch(
            "SELECT ma, ten, nhom FROM ket_qua_mau"
            " WHERE clinic_id = $1::uuid AND active ORDER BY nhom, ten",
            clinic_id,
        )
    ]
    goi_y = ma_mau_goi_y(service_code)
    if goi_y and any(m["ma"] == goi_y for m in tat_ca):
        tat_ca.sort(key=lambda m: m["ma"] != goi_y)
        return tat_ca, goi_y
    return tat_ca, None


__all__ = ["ma_mau_goi_y", "mau_cho_dich_vu"]
