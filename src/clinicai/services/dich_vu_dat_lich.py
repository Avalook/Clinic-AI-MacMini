"""Danh sách dịch vụ ĐẶT LỊCH theo nhóm (Tuyền chốt 07/10/2026 — T0 của
docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md).

Một nguồn cho MỌI ô chọn dịch vụ khi đặt / sửa lịch / đổi dịch vụ (Thêm khách
hàng, Đặt lịch, sửa lịch ở Quản lý khách hàng, popover Đổi dịch vụ khám). Nhóm
là cột `service_type.nhom` (migration 20261007600000) — màn hình chỉ vẽ nhóm
máy chủ trả, không tự xếp theo tên.

* **Khám** — 7 loại khám đang có.
* **Điều trị** — 6 dịch vụ, mỗi loại trỏ đúng dòng bảng giá.
* **Thuốc** — ẩn hẳn (T4): có dòng cũng không trả.
* **Khác** — không bắt chọn dịch vụ; ghi chú khuyến khích, KHÔNG bắt buộc.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

import asyncpg

#: Thứ tự nhóm hiện trên ô chọn. Thuốc không có ở đây = ẩn (T4).
NHOM_HIEN: tuple[tuple[str, str], ...] = (
    ("KHAM", "Khám"),
    ("DIEU_TRI", "Điều trị"),
    ("KHAC", "Khác"),
)

#: Gợi ý (không chặn lưu) cho nhóm cần chữ của người đặt.
GOI_Y_GHI_CHU: dict[str, str] = {
    "KHAC": "Nên ghi chú khách cần gì (không bắt buộc).",
}

#: Mã phiếu của loại khám → mã lĩnh vực trên hồ sơ khách (CHECK
#: `patient_linh_vuc` chỉ nhận 5 mã). Thủ thuật / Sàn chậu / Điều trị / Khác
#: không có lĩnh vực.
LINH_VUC_THEO_PHIEU: dict[str, str] = {
    "PK": "PK",
    "SK": "SK",
    "NT": "NT",
    "HMVS": "HMVS",
    "NK": "NK",
}

#: Cột đọc dùng chung (popover đổi dịch vụ dùng cùng mẩu này).
COT_SQL = "id::text AS id, name, nhom, form_code, thu_tu"

_DOC_SQL = f"""
SELECT {COT_SQL}
  FROM public.service_type
 WHERE clinic_id = $1::uuid AND is_active AND nhom <> 'THUOC'
 ORDER BY thu_tu, name
"""

_DAU_RAC = re.compile(r"^[*#\s]+")


def ten_sach(ten: str | None) -> str:
    """Tên hiện trên ô chọn: bỏ dấu `*` / `#` đầu tên (dấu cũ của bảng tay)."""
    return _DAU_RAC.sub("", ten or "").strip()


def gom_nhom(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Gom các loại khám thành nhóm theo `NHOM_HIEN`. Thuần — test được.

    Giữ nguyên thứ tự vào (người gọi đã xếp ``thu_tu, name``). Khoá phụ của
    dòng (``hien_tai``, ``chan``, ``ghi_chu`` của popover đổi dịch vụ) đi theo
    mục. Nhóm rỗng không trả. Dòng "FREE" (dịch vụ rác đời đầu) không trả.
    """
    theo_nhom: dict[str, list[dict[str, Any]]] = {ma: [] for ma, _ in NHOM_HIEN}
    for r in rows:
        nhom = str(r.get("nhom") or "KHAM")
        ten = ten_sach(r.get("name") if "name" in r else r.get("ten"))
        if nhom not in theo_nhom or not ten or ten.upper() == "FREE":
            continue
        muc: dict[str, Any] = {
            "id": str(r["id"]),
            "ten": ten,
            "linh_vuc": LINH_VUC_THEO_PHIEU.get(str(r.get("form_code") or "")),
        }
        for k in ("hien_tai", "chan", "ghi_chu"):
            if k in r:
                muc[k] = r[k]
        theo_nhom[nhom].append(muc)
    return [
        {
            "ma": ma,
            "ten": ten,
            "goi_y_ghi_chu": GOI_Y_GHI_CHU.get(ma),
            "dich_vu": theo_nhom[ma],
        }
        for ma, ten in NHOM_HIEN
        if theo_nhom[ma]
    ]


async def doc(conn: asyncpg.Connection, clinic_id: str) -> dict[str, Any]:
    """Các nhóm dịch vụ đang bật của phòng khám (chỉ loại `is_active`)."""
    rows = await conn.fetch(_DOC_SQL, clinic_id)
    return {"nhom": gom_nhom([dict(r) for r in rows])}


__all__ = [
    "COT_SQL",
    "GOI_Y_GHI_CHU",
    "LINH_VUC_THEO_PHIEU",
    "NHOM_HIEN",
    "doc",
    "gom_nhom",
    "ten_sach",
]
