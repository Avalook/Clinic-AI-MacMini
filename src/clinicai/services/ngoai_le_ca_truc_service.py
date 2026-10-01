"""Mở, huỷ và xem ngoại lệ ca trực lâm sàng — chỉ permission.manage."""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import doc_ngay_xem, hom_nay_vn
from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.events.catalogue import NgoaiLeCaTruc
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen


class NgoaiLeCaTrucService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @staticmethod
    def _ra(row: asyncpg.Record) -> dict[str, Any]:
        return dict(row)

    async def mo(
        self,
        *,
        staff_id: str,
        bac_si_id: str | None,
        ngay: date | str | None,
        ly_do: str,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        ngay_xet = hom_nay_vn() if ngay is None else doc_ngay_xem(ngay)
        ly_do = " ".join(ly_do.split())
        if ngay_xet is None:
            raise ValidationError("Ngày mở ngoại lệ không hợp lệ.")
        if len(ly_do) < 3:
            raise ValidationError("Cần ghi rõ lý do mở ngoại lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "permission.manage")
            dung_nguoi = await conn.fetchval(
                """
                SELECT EXISTS (
                           SELECT 1 FROM staff s
                           JOIN clinic_membership m
                             ON m.staff_id=s.id AND m.clinic_id=$1::uuid
                            AND m.is_active
                            WHERE s.id=$2::uuid AND s.is_active
                       )
                   AND (
                           $3::uuid IS NULL OR EXISTS (
                               SELECT 1 FROM staff bs
                               JOIN clinic_membership m
                                 ON m.staff_id=bs.id AND m.clinic_id=$1::uuid
                                AND m.is_active
                                AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
                                WHERE bs.id=$3::uuid AND bs.is_active
                           )
                       )
                """,
                identity.clinic_id,
                staff_id,
                bac_si_id,
            )
            if not dung_nguoi:
                raise ValidationError(
                    "Người làm thay hoặc bác sĩ không thuộc phòng khám này."
                )
            row = await conn.fetchrow(
                """
                INSERT INTO ngoai_le_ca_truc
                    (clinic_id, staff_id, ngay, bac_si_id, ly_do, mo_boi)
                VALUES ($1::uuid,$2::uuid,$3::date,$4::uuid,$5,$6::uuid)
                RETURNING id::text, staff_id::text, ngay, bac_si_id::text,
                          ly_do, mo_boi::text, mo_luc, huy_boi::text, huy_luc
                """,
                identity.clinic_id,
                staff_id,
                ngay_xet,
                bac_si_id,
                ly_do,
                identity.staff_id,
            )
            assert row is not None
            await emit_event(
                conn,
                ten="clinical_shift.exception_opened",
                clinic_id=identity.clinic_id,
                aggregate_id=row["id"],
                payload=NgoaiLeCaTruc(
                    staff_id=staff_id,
                    bac_si_id=bac_si_id,
                    ngay=ngay_xet,
                    ly_do=ly_do,
                ),
                boi=nguoi(identity),
            )
        return self._ra(row)

    async def huy(self, *, ngoai_le_id: str, identity: StaffIdentity) -> dict[str, Any]:
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "permission.manage")
            row = await conn.fetchrow(
                """
                UPDATE ngoai_le_ca_truc
                   SET huy_boi=$3::uuid, huy_luc=now()
                 WHERE clinic_id=$1::uuid AND id=$2::uuid AND huy_luc IS NULL
                RETURNING id::text, staff_id::text, ngay, bac_si_id::text,
                          ly_do, mo_boi::text, mo_luc, huy_boi::text, huy_luc
                """,
                identity.clinic_id,
                ngoai_le_id,
                identity.staff_id,
            )
            if row is None:
                raise ResourceNotFoundError("Ngoại lệ không còn mở hoặc không tồn tại.")
            await emit_event(
                conn,
                ten="clinical_shift.exception_cancelled",
                clinic_id=identity.clinic_id,
                aggregate_id=ngoai_le_id,
                payload=NgoaiLeCaTruc(
                    staff_id=row["staff_id"],
                    bac_si_id=row["bac_si_id"],
                    ngay=row["ngay"],
                    ly_do=row["ly_do"],
                ),
                boi=nguoi(identity),
            )
        return self._ra(row)

    async def danh_sach(
        self, *, ngay: date | str | None, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        ngay_xet = hom_nay_vn() if ngay is None else doc_ngay_xem(ngay)
        if ngay_xet is None:
            return []
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, "permission.manage")
            rows = await conn.fetch(
                """
                SELECT n.id::text, n.staff_id::text, s.full_name AS staff_name,
                       n.ngay, n.bac_si_id::text, bs.full_name AS bac_si_name,
                       n.ly_do, n.mo_boi::text, mo.full_name AS mo_boi_name,
                       n.mo_luc, n.huy_boi::text, n.huy_luc
                  FROM ngoai_le_ca_truc n
                  JOIN staff s ON s.id=n.staff_id
                  JOIN staff mo ON mo.id=n.mo_boi
             LEFT JOIN staff bs ON bs.id=n.bac_si_id
                 WHERE n.clinic_id=$1::uuid AND n.ngay=$2::date
              ORDER BY (n.huy_luc IS NULL) DESC, n.mo_luc DESC
                """,
                identity.clinic_id,
                ngay_xet,
            )
        return [self._ra(r) for r in rows]


__all__ = ["NgoaiLeCaTrucService"]
