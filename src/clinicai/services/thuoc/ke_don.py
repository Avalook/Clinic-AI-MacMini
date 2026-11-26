"""Ô chọn thuốc ở màn kê đơn (Bàn khám, Bàn tư vấn, quầy bán lẻ) — kế hoạch mục 13.

Máy chủ trả sẵn cho mỗi thuốc kho tồn của cơ sở theo đơn vị gốc ("còn 3 hộp" /
"hết hàng"); thuốc còn hàng xếp trước. KHÔNG chặn gì (Tuyền 26/11: "kệ bác sĩ
muốn gõ cứ cho gõ") — hết hàng, chưa có giá, nhãn phiếu chưa gắn kho vẫn chọn
được như cũ. Tồn lấy từ `danh_muc` của Kho thuốc + `BangDonVi.ton_goc` — không
đếm tồn lần thứ hai.

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
from clinicai.services.thuoc.cach_dung_db import gan_mac_dinh_ke_don
from clinicai.services.thuoc.me_con import chu_me_con


def chu_ton_ke_don(bang: BangDonVi, ton_theo_don_vi: list[dict[str, Any]]) -> str:
    """Chữ “còn 3 hộp” theo đơn vị gốc; chưa khai đơn vị thì đọc từng đơn vị lô."""
    if bang.co_goc:
        tong = bang.ton_goc(ton_theo_don_vi)
        tong = tong.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if tong <= 0:
            return "hết hàng"
        # Có khai mẹ (hộp = N viên): "còn 303 hộp + 50 viên" (Tuyền 26/11).
        return f"còn {chu_me_con(bang, tong) or f'{so_dep(tong)} {bang.goc}'}"
    phan = [
        f"{so_dep(Decimal(str(x.get('ton') or 0)))} {x.get('don_vi') or ''}".strip()
        for x in ton_theo_don_vi
        if Decimal(str(x.get("ton") or 0)) > 0
    ]
    return "còn " + " · ".join(phan) if phan else "hết hàng"


def chu_quy_cach(r: dict[str, Any]) -> str:
    """Khối đơn vị con của Danh mục → " (1 hộp = 60 viên)"; chưa khai → "" (Tuyền
    26/11: đơn vị thống nhất là "hộp", hiện kèm số viên cho người kê biết)."""
    so, con, me = r.get("so_con"), r.get("don_vi_con"), r.get("don_vi_ban")
    if not (so and con and me) or Decimal(str(so)) <= 1:
        return ""
    return f" (1 {me} = {so_dep(Decimal(str(so)))} {con})"


def sap_xep_ke_don(
    mau: list[dict[str, Any]],
    ton: dict[str, list[dict[str, Any]]],
    bang: dict[str, BangDonVi],
) -> list[dict[str, Any]]:
    """Hàm thuần: gắn tồn cho thuốc kho, xếp thuốc còn hàng lên trước.

    Nhãn phiếu chưa gắn thuốc kho giữ nguyên (không tồn, `con_hang` False). Trong
    cùng nhóm giữ thứ tự cũ (phiếu trước, danh mục sau) — sort ổn định."""
    ra: list[dict[str, Any]] = []
    for m in mau:
        ma = m.get("drug_catalog_id")
        if not ma:
            ra.append({**m, "ton_chu": None, "con_hang": False})
            continue
        chu = chu_ton_ke_don(bang.get(str(ma), BangDonVi()), ton.get(str(ma), []))
        ra.append({**m, "ton_chu": chu, "con_hang": chu != "hết hàng"})
    ra.sort(key=lambda x: not x["con_hang"])
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
    async with pool.acquire() as conn:  # cách dùng mặc định có cấu trúc (PR E)
        await gan_mac_dinh_ke_don(conn, identity.clinic_id, mau)
        qc = {
            str(r["id"]): chu_quy_cach(dict(r))
            for r in await conn.fetch(
                "SELECT id::text, don_vi_ban, don_vi_con,"
                " so_lieu_moi_don_vi_goc AS so_con FROM public.drug_catalog"
                " WHERE clinic_id = $1::uuid AND don_vi_con IS NOT NULL",
                identity.clinic_id,
            )
        }
    ra = sap_xep_ke_don(mau, ton, bang)
    for m in ra:
        if m["con_hang"] and qc.get(str(m.get("drug_catalog_id"))):
            m["ton_chu"] += qc[str(m["drug_catalog_id"])]
    return ra


__all__ = ["chu_quy_cach", "chu_ton_ke_don", "gan_ton_ke_don", "sap_xep_ke_don"]
