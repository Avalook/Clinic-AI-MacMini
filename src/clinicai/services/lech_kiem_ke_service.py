"""Khối "Lệch kiểm kê" ở Báo cáo kho + quản lý sửa số sau cùng (Tuyền 31/10/2026).

Gom hai nguồn lệch về một bảng: Kiểm ca ở QUẦY (theo thuốc + đơn vị) và Kiểm đếm
kho (theo từng hàng lô, KHO hoặc QUẦY). Phiếu đã chốt không đổi; quản lý sửa số sau
cùng bằng một dòng MỚI ở `kiem_ke_sua_so` kèm `ADJUST` đúng phần chênh, nên lịch sử
còn nguyên và sửa sai thì sửa tiếp một dòng nữa.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.core.tran import canh_bao_neu_day
from clinicai.permissions.can import can
from clinicai.services.kho_thuoc_service import dau_ngay_vn, khoang_xnt
from clinicai.services.kiem_ke_ca_service import (
    _ap_lech,
    _ghi_adjust,
    _khoa_lo_quay,
    ca_cua_gio,
    so_hoac_none,
)
from clinicai.services.pharmacy_service import ghi_nhat_ky

#: Ai sửa được số sau cùng: người xem báo cáo hoặc quản trị phòng khám — không phải
#: mọi người đang đứng quầy. Router gác cửa bằng đúng hai quyền này.
QUYEN_SUA_SO = ("report.view", "config.clinic.manage")

TRAN_DONG = 1000

_SQL_CA = """
SELECT 'CA' AS nguon, d.id::text AS dong_id, k.ngay, k.ca, k.loai,
       k.chot_luc AS luc, d.drug_catalog_id::text AS drug_catalog_id,
       c.name_raw AS ten, c.ma_hang, NULL::text AS so_lo, 'QUAY' AS noi_chua,
       d.don_vi, d.ton_may AS so_so, d.giao_da_tach AS giao_chua_gan_lo,
       d.dem AS so_dem, d.lech, d.ly_do, d.chua_ap, d.chua_ap_ly_do,
       s.full_name AS nguoi, k.hoan_tac_luc IS NOT NULL AS da_hoan_tac
  FROM public.kiem_ke_ca_dong d
  JOIN public.kiem_ke_ca k ON k.id = d.kiem_ke_ca_id
  JOIN public.drug_catalog c ON c.id = d.drug_catalog_id
  LEFT JOIN public.staff s ON s.id = k.chot_boi
 WHERE k.clinic_id = $1::uuid AND k.location_id = $2::uuid
   AND k.trang_thai = 'CHOT' AND k.ngay BETWEEN $3 AND $4
   AND d.lech IS NOT NULL AND d.lech <> 0
   AND NOT EXISTS (SELECT 1 FROM public.kiem_ke_ca n
                    WHERE n.phieu_truoc_id = k.id AND n.trang_thai = 'CHOT')
"""

_SQL_KHO = """
SELECT 'KHO' AS nguon, d.id::text AS dong_id, pk.tao_luc AS luc,
       d.drug_catalog_id::text AS drug_catalog_id,
       c.name_raw AS ten, c.ma_hang, b.batch_code AS so_lo, b.noi_chua,
       b.unit AS don_vi, d.ton_may AS so_so, d.giao_da_tach AS giao_chua_gan_lo,
       d.thuc_te AS so_dem, d.lech, d.ly_do, s.full_name AS nguoi, pk.ma_phieu,
       EXISTS (SELECT 1 FROM public.phieu_kho h WHERE h.hoan_tac_cua = pk.id)
           AS da_hoan_tac
  FROM public.phieu_kho_dong d
  JOIN public.phieu_kho pk ON pk.id = d.phieu_kho_id
  JOIN public.drug_catalog c ON c.id = d.drug_catalog_id
  JOIN public.drug_batch b ON b.id = d.drug_batch_id
  LEFT JOIN public.staff s ON s.id = pk.tao_boi
 WHERE pk.clinic_id = $1::uuid AND pk.location_id = $2::uuid
   AND pk.loai = 'KIEM' AND pk.hoan_tac_cua IS NULL
   AND pk.tao_luc >= $3 AND pk.tao_luc < $4
   AND d.lech <> 0
"""


async def ds_lech(
    pool: asyncpg.Pool, *, identity: StaffIdentity, tu: Any, den: Any
) -> dict[str, Any]:
    """Dòng lệch trong [tu, den] của cơ sở đang làm, mới nhất trước. Ngày rác → hôm
    nay, không ném. Mỗi dòng kèm số sau cùng + lịch sử sửa."""
    a, b = khoang_xnt(tu, den, hom_nay_vn())
    async with pool.acquire() as conn:
        co_so = identity.location_id
        ca = await conn.fetch(
            _SQL_CA + " LIMIT $5", identity.clinic_id, co_so, a, b, TRAN_DONG
        )
        kho = await conn.fetch(
            _SQL_KHO + " LIMIT $5",
            identity.clinic_id,
            co_so,
            dau_ngay_vn(a),
            dau_ngay_vn(b + timedelta(days=1)),
            TRAN_DONG,
        )
        settings = await conn.fetchval(
            "SELECT settings FROM clinic WHERE id = $1::uuid", identity.clinic_id
        )
        ids = [r["dong_id"] for r in [*ca, *kho]]
        sua = await conn.fetch(
            """
            SELECT x.dong_id::text AS dong_id, x.so_cu, x.so_moi, x.ly_do, x.sua_luc,
                   s.full_name AS nguoi
              FROM public.kiem_ke_sua_so x
              LEFT JOIN public.staff s ON s.id = x.sua_boi
             WHERE x.clinic_id = $1::uuid AND x.dong_id = ANY($2::uuid[])
             ORDER BY x.sua_luc, x.id
            """,
            identity.clinic_id,
            ids,
        )
        sua_duoc = await _sua_duoc(conn, identity)
    canh_bao_neu_day("kho.lech_kiem_ke", len(ca) + len(kho), TRAN_DONG)
    theo_dong: dict[str, list[dict[str, Any]]] = {}
    for r in sua:
        theo_dong.setdefault(r["dong_id"], []).append(dict(r))
    dong: list[dict[str, Any]] = []
    for r in ca:
        dong.append(_dong(dict(r), theo_dong, sua_duoc))
    for r in kho:
        d = dict(r)
        v = d["luc"].astimezone(CLINIC_TZ)
        d["ngay"] = v.date()
        d["ca"] = ca_cua_gio(d["luc"], settings)
        d["loai"] = "KHO"
        dong.append(_dong(d, theo_dong, sua_duoc))
    dong.sort(key=lambda x: x["luc"], reverse=True)
    return {
        "tu": a.isoformat(),
        "den": b.isoformat(),
        "dong": dong,
        "sua_duoc": sua_duoc,
    }


async def _sua_duoc(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    for q in QUYEN_SUA_SO:
        if await can(conn, identity, q):
            return True
    return False


def _dong(
    d: dict[str, Any], theo_dong: dict[str, list[dict[str, Any]]], sua_duoc: bool
) -> dict[str, Any]:
    lich_su = theo_dong.get(d["dong_id"], [])
    d["so_sau_cung"] = lich_su[-1]["so_moi"] if lich_su else d["so_dem"]
    d["lich_su_sua"] = lich_su
    d["chua_ap"] = d.get("chua_ap")
    d["chua_ap_ly_do"] = d.get("chua_ap_ly_do")
    d["thao_tac"] = {"sua": sua_duoc and not d["da_hoan_tac"]}
    return d


async def sua_so_sau_cung(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    nguon: Any,
    dong_id: Any,
    so_moi: Any,
    ly_do: Any,
) -> dict[str, Any]:
    """Đặt lại số đếm sau cùng của một dòng lệch. Sổ ghi thêm `ADJUST` đúng phần
    chênh so với số sau cùng hiện tại; phiếu gốc giữ nguyên. Gửi lại cùng số → 422
    "không đổi", không ghi hai lần."""
    if nguon not in ("CA", "KHO"):
        raise ValidationError("Nguồn dòng kiểm không hợp lệ.")
    try:
        ma = str(uuid.UUID(str(dong_id)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationError("Mã dòng kiểm không hợp lệ.") from exc
    moi = so_hoac_none(so_moi)
    if moi is None:
        raise ValidationError("Số sau cùng phải là số không âm, hợp lý.")
    ly = " ".join(str(ly_do or "").split())
    if not ly or len(ly) > 1000:
        raise ValidationError("Ghi lý do sửa số (từ 1 đến 1000 ký tự).")
    async with pool.acquire() as conn, conn.transaction():
        if nguon == "CA":
            g = await conn.fetchrow(
                "SELECT d.id, d.dem AS so_goc, d.drug_catalog_id::text AS thuoc,"
                " d.don_vi, k.hoan_tac_luc, k.trang_thai, k.id::text AS phieu"
                " FROM public.kiem_ke_ca_dong d JOIN public.kiem_ke_ca k"
                " ON k.id = d.kiem_ke_ca_id WHERE d.id = $1::uuid"
                " AND d.clinic_id = $2::uuid AND k.location_id = $3::uuid"
                " FOR UPDATE OF k",
                ma,
                identity.clinic_id,
                identity.location_id,
            )
            if g is None or g["trang_thai"] != "CHOT":
                raise NotFoundError("Không tìm thấy dòng kiểm đã chốt này.")
            da_hoan_tac = g["hoan_tac_luc"] is not None
        else:
            g = await conn.fetchrow(
                "SELECT d.id, d.thuc_te AS so_goc, d.drug_batch_id::text AS lo,"
                " pk.id::text AS phieu, EXISTS (SELECT 1 FROM public.phieu_kho h"
                " WHERE h.hoan_tac_cua = pk.id) AS da_hoan_tac"
                " FROM public.phieu_kho_dong d JOIN public.phieu_kho pk"
                " ON pk.id = d.phieu_kho_id WHERE d.id = $1::uuid"
                " AND d.clinic_id = $2::uuid AND pk.location_id = $3::uuid"
                " AND pk.loai = 'KIEM' FOR UPDATE OF pk",
                ma,
                identity.clinic_id,
                identity.location_id,
            )
            if g is None:
                raise NotFoundError("Không tìm thấy dòng kiểm này.")
            da_hoan_tac = bool(g["da_hoan_tac"])
        if da_hoan_tac:
            raise ConflictError("Phiếu này đã hoàn tác — không sửa số được.")
        cu = await conn.fetchval(
            "SELECT so_moi FROM public.kiem_ke_sua_so WHERE clinic_id = $1::uuid"
            " AND nguon = $2 AND dong_id = $3::uuid"
            " ORDER BY sua_luc DESC, id DESC LIMIT 1",
            identity.clinic_id,
            nguon,
            ma,
        )
        so_cu = Decimal(str(cu if cu is not None else g["so_goc"]))
        chenh = moi - so_cu
        if chenh == 0:
            raise ValidationError("Số mới trùng số đang có — không có gì để sửa.")
        sua_id = await conn.fetchval(
            "INSERT INTO public.kiem_ke_sua_so (clinic_id, location_id, nguon, dong_id,"
            " so_cu, so_moi, ly_do, sua_boi) VALUES ($1::uuid, $2::uuid, $3, $4::uuid,"
            " $5, $6, $7, $8::uuid) RETURNING id::text",
            identity.clinic_id,
            identity.location_id,
            nguon,
            ma,
            so_cu,
            moi,
            ly,
            identity.staff_id,
        )
        if nguon == "CA":
            await _khoa_lo_quay(conn, identity, [g["thuoc"]])
            da_ap, _lo, thieu = await _ap_lech(
                conn,
                identity,
                g["thuoc"],
                g["don_vi"],
                chenh,
                sua_id,
                ly,
                ref_type="kiem_ke_sua",
            )
            if da_ap != chenh:
                raise ConflictError(f"Chưa sửa được: {thieu}")
        else:
            ton = await conn.fetchval(
                "SELECT quantity_on_hand FROM public.drug_batch WHERE id = $1::uuid"
                " AND clinic_id = $2::uuid FOR UPDATE",
                g["lo"],
                identity.clinic_id,
            )
            if Decimal(str(ton)) + chenh < 0:
                raise ConflictError(
                    f"Lô này chỉ còn {ton} — không trừ thêm được {-chenh}."
                )
            await _ghi_adjust(
                conn, identity, g["lo"], chenh, sua_id, ly, ref_type="kiem_ke_sua"
            )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.kiem_ke_sua_so",
            aggregate_type="kiem_ke_sua_so",
            aggregate_id=sua_id,
            payload={
                "nguon": nguon,
                "dong_id": ma,
                "so_cu": str(so_cu),
                "so_moi": str(moi),
                "ly_do": ly,
            },
        )
    return {"ok": True, "so_cu": so_cu, "so_moi": moi, "chenh": chenh}
