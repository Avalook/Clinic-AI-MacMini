"""Đặt thuế suất GTGT cho kế toán (G5b · Tuyền 14/10/2026, Q16).

Hai tầng lưu: NHÓM (Dịch vụ / Thuốc / Vật tư — bảng `thue_suat_nhom`) và TỪNG
MẶT HÀNG (`service_price.thue_suat_ma`, `drug_catalog.thue_suat_ma`). Tầng thứ
ba — sửa tay từng dòng lúc xuất — không lưu ở đây (đi kèm lệnh xuất).

Cửa: ĐẶT cần quyền `accounting.tax.manage`; XEM cần một trong hai quyền kế toán.
Thuế không chạm vận hành: không có đường nào ở quầy / hoá đơn / báo cáo ngày
đọc các cột này.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.permissions.can import can, doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.thue_gtgt import NHOM_HANG, chuan_hoa_thue_suat

QUYEN_DAT = "accounting.tax.manage"
QUYEN_XEM = ("accounting.finance.full", QUYEN_DAT)
LOAI_MAT_HANG = ("dich_vu", "thuoc", "vat_tu")
TOI_DA_TIM = 50


def doc_thue_dat(raw: Any) -> str | None:
    """Giá trị người gõ → mã chuẩn; trống = bỏ đặt (None); rác → báo lỗi tiếng Việt."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    ma = chuan_hoa_thue_suat(raw)
    if ma is None:
        raise ValidationError(
            "Thuế suất không hợp lệ — nhập số từ 0 đến 100 (vd 8), KCT hoặc KKKNT."
        )
    return ma


class ThueSuatService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def _doi_xem(self, conn: asyncpg.Connection, identity: StaffIdentity) -> None:
        for q in QUYEN_XEM:
            if await can(conn, identity, q):
                return
        await doi_quyen(conn, identity, QUYEN_XEM[0])

    async def xem(
        self, *, identity: StaffIdentity, tim: str | None = None
    ) -> dict[str, Any]:
        """Thuế suất theo nhóm + (có `tim`) tối đa 50 mặt hàng khớp tên / mã."""
        async with self.pool.acquire() as conn:
            await self._doi_xem(conn, identity)
            nhom = {
                r["nhom"]: r["thue_suat_ma"]
                for r in await conn.fetch(
                    "SELECT nhom, thue_suat_ma FROM thue_suat_nhom"
                    " WHERE clinic_id=$1::uuid",
                    identity.clinic_id,
                )
            }
            mat_hang: list[dict[str, Any]] = []
            chuoi = (tim or "").strip()[:80]
            if chuoi:
                like = f"%{chuoi.replace('%', ' ').replace('_', ' ')}%"
                mat_hang = [
                    dict(r)
                    for r in await conn.fetch(
                        """
                        SELECT * FROM (
                          SELECT CASE WHEN "group"='vat_tu' THEN 'vat_tu'
                                      ELSE 'dich_vu' END loai,
                                 id::text id, service_code ma, name ten,
                                 thue_suat_ma
                            FROM service_price
                           WHERE clinic_id=$1::uuid AND active
                             AND "group" IN ('dich_vu', 'vat_tu')
                             AND (name ILIKE $2 OR service_code ILIKE $2)
                          UNION ALL
                          SELECT 'thuoc', id::text, coalesce(ma_hang, ''),
                                 name_raw, thue_suat_ma
                            FROM drug_catalog
                           WHERE clinic_id=$1::uuid AND is_active
                             AND (name_raw ILIKE $2 OR ma_hang ILIKE $2)
                        ) x ORDER BY ten LIMIT $3""",
                        identity.clinic_id,
                        like,
                        TOI_DA_TIM,
                    )
                ]
        return {
            "nhom": {n: nhom.get(n) for n in NHOM_HANG},
            "mat_hang": mat_hang,
            "duoc_dat": await self._co_quyen_dat(identity),
        }

    async def _co_quyen_dat(self, identity: StaffIdentity) -> bool:
        async with self.pool.acquire() as conn:
            return await can(conn, identity, QUYEN_DAT)

    async def dat_nhom(
        self, *, identity: StaffIdentity, nhom: str, thue_suat: Any
    ) -> dict[str, Any]:
        if nhom not in NHOM_HANG:
            raise ValidationError("Nhóm hàng không có thật.")
        ma = doc_thue_dat(thue_suat)
        async with self.pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_DAT)
            if ma is None:
                await conn.execute(
                    "DELETE FROM thue_suat_nhom WHERE clinic_id=$1::uuid AND nhom=$2",
                    identity.clinic_id,
                    nhom,
                )
            else:
                await conn.execute(
                    "INSERT INTO thue_suat_nhom(clinic_id, nhom, thue_suat_ma, sua_boi)"
                    " VALUES($1::uuid,$2,$3,$4::uuid)"
                    " ON CONFLICT (clinic_id, nhom) DO UPDATE"
                    " SET thue_suat_ma=EXCLUDED.thue_suat_ma,"
                    "     sua_boi=EXCLUDED.sua_boi, sua_luc=now()",
                    identity.clinic_id,
                    nhom,
                    ma,
                    identity.staff_id,
                )
            await record_event(
                conn,
                event_type="accounting.tax_group_set",
                aggregate_type="clinic",
                aggregate_id=identity.clinic_id,
                identity=identity,
                origin="api:ke-toan-thue",
                payload={"nhom": nhom, "thue_suat": ma},
            )
        return {"ok": True, "nhom": nhom, "thue_suat": ma}

    async def dat_mat_hang(
        self, *, identity: StaffIdentity, loai: str, id_: str, thue_suat: Any
    ) -> dict[str, Any]:
        if loai not in LOAI_MAT_HANG:
            raise ValidationError("Loại mặt hàng không có thật.")
        ma = doc_thue_dat(thue_suat)
        if loai == "thuoc":
            sql = (
                "UPDATE drug_catalog SET thue_suat_ma=$3"
                " WHERE clinic_id=$1::uuid AND id::text=$2"
            )
        else:
            sql = (
                "UPDATE service_price SET thue_suat_ma=$3"
                " WHERE clinic_id=$1::uuid AND id::text=$2"
                " AND \"group\" = ANY(ARRAY['dich_vu','vat_tu'])"
            )
        async with self.pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_DAT)
            trang_thai = await conn.execute(sql, identity.clinic_id, id_, ma)
            if trang_thai.endswith(" 0"):
                raise ValidationError("Không tìm thấy mặt hàng này.")
            await record_event(
                conn,
                event_type="accounting.tax_item_set",
                aggregate_type="clinic",
                aggregate_id=identity.clinic_id,
                identity=identity,
                origin="api:ke-toan-thue",
                payload={"loai": loai, "mat_hang_id": id_, "thue_suat": ma},
            )
        return {"ok": True, "loai": loai, "id": id_, "thue_suat": ma}
