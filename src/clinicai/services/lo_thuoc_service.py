"""Sửa lô và huỷ hết hạn: giữ lịch sử, khoá lô, hoàn bằng dòng sổ mới."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.phieu_kham.khung import doc_ngay


async def so_ngay_canh_bao(conn: Any, clinic_id: str) -> int:
    raw = await conn.fetchval(
        "SELECT settings->>'pharmacy_expiry_warning_days' FROM clinic WHERE "
        "id=$1::uuid",
        clinic_id,
    )
    try:
        value = int(raw)
        return value if 0 <= value <= 365000 else 60
    except (TypeError, ValueError, OverflowError):
        return 60


async def doi_canh_bao(
    pool: asyncpg.Pool, *, identity: StaffIdentity, so_ngay: int
) -> dict[str, Any]:
    from clinicai.services.pharmacy_service import ghi_nhat_ky

    async with pool.acquire() as conn, conn.transaction():
        await conn.fetchrow(
            "SELECT id FROM clinic WHERE id=$1::uuid FOR UPDATE", identity.clinic_id
        )
        cu = await so_ngay_canh_bao(conn, identity.clinic_id)
        await conn.execute(
            "UPDATE clinic SET "
            "settings=jsonb_set(coalesce(settings,'{}'::jsonb),"
            "'{pharmacy_expiry_warning_days}',$2::jsonb) "
            "WHERE id=$1::uuid",
            identity.clinic_id,
            json.dumps(so_ngay),
        )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.expiry_warning_updated",
            aggregate_type="clinic",
            aggregate_id=identity.clinic_id,
            payload={"before": cu, "after": so_ngay},
        )
    return {"ok": True, "so_ngay_sap_het_han": so_ngay}


async def _lo(conn: asyncpg.Connection, identity: StaffIdentity, lo_id: str) -> Any:
    lo = await conn.fetchrow(
        "SELECT * FROM drug_batch WHERE id=$1::uuid AND clinic_id=$2::uuid AND "
        "location_id=$3::uuid FOR UPDATE",
        lo_id,
        identity.clinic_id,
        identity.location_id,
    )
    if lo is None:
        raise NotFoundError("Không tìm thấy lô trong kho cơ sở đang làm.")
    return lo


async def sua_lo(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    drug_batch_id: str,
    batch_code: str,
    expiry_date: Any,
) -> dict[str, Any]:
    from clinicai.services.pharmacy_service import ghi_nhat_ky

    ma = batch_code.strip()
    if not ma:
        raise ValidationError("Nhập số lô.")
    trong = expiry_date is None or (
        isinstance(expiry_date, str) and not expiry_date.strip()
    )
    han = expiry_date if isinstance(expiry_date, date) else doc_ngay(expiry_date)
    if not trong and han is None:
        raise ValidationError("Ngày hạn không đúng định dạng — nhập dd/mm/yyyy")
    async with pool.acquire() as conn, conn.transaction():
        lo = await _lo(conn, identity, drug_batch_id)
        if (
            han is None
            and lo["expiry_date"] is not None
            and lo["expiry_date"] < hom_nay_vn()
        ):
            raise ConflictError("Lô đã hết hạn — nhập hạn mới hoặc bấm Huỷ lô hết hạn")
        try:
            # Một lô có thể có hai hàng KHO / QUẦY (G7): sửa số lô / hạn là sửa
            # cả hai, một câu UPDATE — hai hàng cùng số lô luôn là cùng một lô.
            await conn.execute(
                "UPDATE drug_batch SET batch_code=$1, expiry_date=$2"
                " WHERE clinic_id=$3::uuid AND location_id=$4::uuid"
                " AND batch_code=$5",
                ma,
                han,
                identity.clinic_id,
                identity.location_id,
                lo["batch_code"],
            )
        except asyncpg.UniqueViolationError as exc:
            raise ConflictError(
                "Số lô này đã có trong kho cơ sở — nhập số lô khác."
            ) from exc
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.batch_updated",
            aggregate_type="drug_batch",
            aggregate_id=drug_batch_id,
            payload={
                "before": {
                    "batch_code": lo["batch_code"],
                    "expiry_date": str(lo["expiry_date"])
                    if lo["expiry_date"]
                    else None,
                },
                "after": {"batch_code": ma, "expiry_date": str(han) if han else None},
            },
        )
    return {"ok": True}


async def huy_lo(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    drug_batch_id: str,
    ly_do: str,
    khoa_gui: str,
) -> dict[str, Any]:
    from clinicai.services.pharmacy_service import ghi_nhat_ky

    ly = ly_do.strip()
    if not ly:
        raise ValidationError("Huỷ lô phải ghi lý do.")
    async with pool.acquire() as conn, conn.transaction():
        lo = await _lo(conn, identity, drug_batch_id)
        cu = await conn.fetchval(
            "SELECT id::text FROM inventory_txn WHERE clinic_id=$1::uuid AND "
            "drug_batch_id=$2::uuid AND txn_type='DISCARD' AND "
            "ref_type='expired_batch' AND ref_id=$3::uuid",
            identity.clinic_id,
            drug_batch_id,
            khoa_gui,
        )
        if cu:
            return {"ok": True, "inventory_txn_id": cu, "gui_lai": True}
        if lo["expiry_date"] is None or lo["expiry_date"] >= hom_nay_vn():
            raise ValidationError("Lô chưa hết hạn — dùng thao tác Huỷ thuốc nếu cần.")
        if lo["quantity_on_hand"] <= 0:
            raise ValidationError("Lô không còn tồn để huỷ.")
        txn = await conn.fetchval(
            "INSERT INTO inventory_txn "
            "(clinic_id,drug_batch_id,txn_type,quantity,"
            "reason,ref_type,ref_id,performed_by_staff_id) "
            "VALUES "
            "($1::uuid,$2::uuid,'DISCARD',$3,$4,'expired_batch',$5::uuid,$6::uuid) "
            "RETURNING id::text",
            identity.clinic_id,
            drug_batch_id,
            -lo["quantity_on_hand"],
            ly,
            khoa_gui,
            identity.staff_id,
        )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.batch_discarded",
            aggregate_type="drug_batch",
            aggregate_id=drug_batch_id,
            payload={
                "inventory_txn_id": txn,
                "quantity": str(lo["quantity_on_hand"]),
                "reason": ly,
            },
        )
    return {"ok": True, "inventory_txn_id": txn, "gui_lai": False}


async def hoan_huy_lo(
    pool: asyncpg.Pool, *, identity: StaffIdentity, inventory_txn_id: str
) -> dict[str, Any]:
    from clinicai.services.pharmacy_service import ghi_nhat_ky

    async with pool.acquire() as conn, conn.transaction():
        txn = await conn.fetchrow(
            "SELECT t.* FROM inventory_txn t JOIN drug_batch b ON "
            "b.id=t.drug_batch_id WHERE t.id=$1::uuid AND t.clinic_id=$2::uuid "
            "AND b.location_id=$3::uuid AND t.txn_type='DISCARD' AND "
            "t.ref_type='expired_batch'",
            inventory_txn_id,
            identity.clinic_id,
            identity.location_id,
        )
        if txn is None:
            raise NotFoundError("Không tìm thấy lượt huỷ lô hết hạn.")
        await _lo(conn, identity, str(txn["drug_batch_id"]))
        cu = await conn.fetchval(
            "SELECT id::text FROM inventory_txn WHERE clinic_id=$1::uuid AND "
            "ref_type='discard_undo' AND ref_id=$2::uuid",
            identity.clinic_id,
            inventory_txn_id,
        )
        if cu:
            return {"ok": True, "inventory_txn_id": cu, "gui_lai": True}
        dao = await conn.fetchval(
            "INSERT INTO inventory_txn "
            "(clinic_id,drug_batch_id,txn_type,quantity,"
            "reason,ref_type,ref_id,performed_by_staff_id) "
            "VALUES ($1::uuid,$2::uuid,'ADJUST',$3,'Hoàn tác huỷ lô hết "
            "hạn','discard_undo',$4::uuid,$5::uuid) RETURNING id::text",
            identity.clinic_id,
            txn["drug_batch_id"],
            -txn["quantity"],
            inventory_txn_id,
            identity.staff_id,
        )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.batch_discard_undone",
            aggregate_type="drug_batch",
            aggregate_id=str(txn["drug_batch_id"]),
            payload={"original_txn_id": inventory_txn_id, "inventory_txn_id": dao},
        )
    return {"ok": True, "inventory_txn_id": dao, "gui_lai": False}
