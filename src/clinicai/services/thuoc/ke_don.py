"""Ô chọn thuốc ở màn kê đơn (Bàn khám, Bàn tư vấn, quầy bán lẻ) — kế hoạch mục 13.

Trước đây ô chọn trả MỌI tên của phiếu + danh mục, kể cả thuốc rác không giá và
nhãn phiếu chưa gắn thuốc kho, không có tồn. Bác sĩ kê "Transamin", "Pricefil"
(không giá) → cả hoá đơn thuốc của lượt kẹt ở quầy.

Nay máy chủ trả sẵn cho mỗi thuốc: tồn của cơ sở theo đơn vị kê ("còn 3 hộp" /
"hết hàng"), cờ `chon_duoc` + lý do. Thuốc còn hàng xếp trước. Hết hàng vẫn kê
được (quầy giao khi về hàng — luật giao hiện có). Tồn lấy từ `danh_muc` của Kho
thuốc + `BangDonVi.ton_goc` — không đếm tồn lần thứ hai.

Không hiện "kho còn — chuyển ra quầy" ở bàn khám (Tuyền 26/11): việc chuyển là
của người kho, ở màn Kho thuốc.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.services.don_vi_thuoc import BangDonVi, so_dep
from clinicai.services.pharmacy_service import PharmacyService

LY_DO_CHUA_GIA = "Chưa có giá — nhờ kho điền giá ở Danh mục rồi mới kê được."


def chu_ton_ke_don(bang: BangDonVi, ton_theo_don_vi: list[dict[str, Any]]) -> str:
    """Chữ “còn 3 hộp” theo đơn vị gốc; chưa khai đơn vị thì đọc từng đơn vị lô."""
    if bang.co_goc:
        tong = bang.ton_goc(ton_theo_don_vi)
        tong = tong.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return f"còn {so_dep(tong)} {bang.goc}" if tong > 0 else "hết hàng"
    phan = [
        f"{so_dep(Decimal(str(x.get('ton') or 0)))} {x.get('don_vi') or ''}".strip()
        for x in ton_theo_don_vi
        if Decimal(str(x.get("ton") or 0)) > 0
    ]
    return "còn " + " · ".join(phan) if phan else "hết hàng"


def sap_xep_ke_don(
    mau: list[dict[str, Any]],
    ton: dict[str, list[dict[str, Any]]],
    bang: dict[str, BangDonVi],
) -> list[dict[str, Any]]:
    """Hàm thuần: bỏ nhãn chưa gắn thuốc kho, gắn tồn + cờ chọn được, xếp lại.

    Thứ tự: chọn được & còn hàng → chọn được & hết hàng → chưa có giá. Trong
    cùng nhóm giữ thứ tự cũ (phiếu trước, danh mục sau)."""
    ra: list[dict[str, Any]] = []
    for m in mau:
        ma = m.get("drug_catalog_id")
        if not ma:
            continue
        b = bang.get(str(ma), BangDonVi())
        chu = chu_ton_ke_don(b, ton.get(str(ma), []))
        co_gia = m.get("gia") is not None or any(
            d.get("gia") is not None for d in m.get("cac_don_vi") or []
        )
        ra.append(
            {
                **m,
                "ton_chu": chu,
                "con_hang": chu != "hết hàng",
                "chon_duoc": co_gia,
                "ly_do_khong_chon": None if co_gia else LY_DO_CHUA_GIA,
            }
        )
    ra.sort(key=lambda x: (not x["chon_duoc"], not x["con_hang"]))
    return ra


async def gan_ton_ke_don(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    mau: list[dict[str, Any]],
    bang: dict[str, BangDonVi],
) -> list[dict[str, Any]]:
    """Một dòng gọi từ `phieu_kham_service.tham_chieu_that`."""
    dm = await PharmacyService(pool).danh_muc(identity=identity)
    ton = {str(r["id"]): list(r.get("ton_theo_don_vi") or []) for r in dm}
    return sap_xep_ke_don(mau, ton, bang)


__all__ = ["LY_DO_CHUA_GIA", "chu_ton_ke_don", "gan_ton_ke_don", "sap_xep_ke_don"]
