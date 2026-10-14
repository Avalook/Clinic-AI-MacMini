"""Sửa/hủy/hoàn lô trên DB thật, sổ chỉ thêm và cô lập cơ sở."""

# ruff: noqa: F811
import asyncio
import json
import uuid
from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import lo_thuoc_service as lo
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _batch(q: Quay, expired: bool = True) -> str:
    batch = await _nhap_lo(q, await _thuoc_moi(q), 20)
    if expired:
        await q.pool.execute(
            "UPDATE drug_batch SET expiry_date=$2 WHERE id=$1::uuid",
            batch,
            hom_nay_vn() - timedelta(days=1),
        )
    return batch


async def test_sua_lo_co_lich_su_va_hoan_bang_sua_lai(q: Quay) -> None:
    batch = await _batch(q)
    original = await q.pool.fetchrow(
        "SELECT batch_code,expiry_date FROM drug_batch WHERE id=$1::uuid", batch
    )
    await lo.sua_lo(
        q.pool,
        identity=q.duoc_si,
        drug_batch_id=batch,
        batch_code="LO-MOI",
        expiry_date="rác",
    )
    assert (
        await q.pool.fetchval(
            "SELECT expiry_date FROM drug_batch WHERE id=$1::uuid", batch
        )
        is None
    )
    log = await q.pool.fetchrow(
        "SELECT payload,metadata FROM event_log WHERE aggregate_id=$1::uuid "
        "AND event_type='pharmacy.batch_updated'",
        batch,
    )
    assert json.loads(log["payload"])["after"] == {
        "batch_code": "LO-MOI",
        "expiry_date": None,
    }
    assert json.loads(log["metadata"])["clinic_staff_id"] == q.duoc_si.staff_id
    await lo.sua_lo(
        q.pool,
        identity=q.duoc_si,
        drug_batch_id=batch,
        batch_code=original["batch_code"],
        expiry_date=original["expiry_date"],
    )
    assert (
        await q.pool.fetchval(
            "SELECT expiry_date FROM drug_batch WHERE id=$1::uuid", batch
        )
        == original["expiry_date"]
    )


async def test_huy_retry_va_hoan_khong_nhan_doi(q: Quay) -> None:
    batch = await _batch(q)
    key = str(uuid.uuid4())
    args: dict[str, Any] = dict(
        identity=q.duoc_si, drug_batch_id=batch, ly_do="Hết hạn", khoa_gui=key
    )
    a, b = await asyncio.gather(lo.huy_lo(q.pool, **args), lo.huy_lo(q.pool, **args))
    assert a["inventory_txn_id"] == b["inventory_txn_id"]
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE id=$1::uuid", batch
        )
        == 0
    )
    args2: dict[str, Any] = dict(
        identity=q.duoc_si, inventory_txn_id=a["inventory_txn_id"]
    )
    c, d = await asyncio.gather(
        lo.hoan_huy_lo(q.pool, **args2), lo.hoan_huy_lo(q.pool, **args2)
    )
    assert c["inventory_txn_id"] == d["inventory_txn_id"]
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE id=$1::uuid", batch
        )
        == 20
    )
    assert (
        await q.pool.fetchval(
            "SELECT sum(quantity) FROM inventory_txn WHERE drug_batch_id=$1::uuid",
            batch,
        )
        == 20
    )


async def test_huy_bat_buoc_ly_do_va_dung_han(q: Quay) -> None:
    batch = await _batch(q, expired=False)
    for ly in ["", "   ", "Có lý do"]:
        with pytest.raises(ValidationError):
            await lo.huy_lo(
                q.pool,
                identity=q.duoc_si,
                drug_batch_id=batch,
                ly_do=ly,
                khoa_gui=str(uuid.uuid4()),
            )
    with pytest.raises(NotFoundError):
        await lo.hoan_huy_lo(
            q.pool, identity=q.duoc_si, inventory_txn_id=str(uuid.uuid4())
        )


@pytest.mark.parametrize("scope", ["location_id", "clinic_id"])
async def test_lo_co_so_khac_khong_sua_huy_hoan_duoc(q: Quay, scope: str) -> None:
    batch = await _batch(q)
    wrong = (
        replace(q.duoc_si, clinic_id=str(uuid.uuid4()))
        if scope == "clinic_id"
        else replace(q.duoc_si, location_id=str(uuid.uuid4()))
    )
    with pytest.raises(NotFoundError):
        await lo.sua_lo(
            q.pool,
            identity=wrong,
            drug_batch_id=batch,
            batch_code="KHAC",
            expiry_date=None,
        )
    with pytest.raises(NotFoundError):
        await lo.huy_lo(
            q.pool,
            identity=wrong,
            drug_batch_id=batch,
            ly_do="Hết hạn",
            khoa_gui=str(uuid.uuid4()),
        )
    result = await lo.huy_lo(
        q.pool,
        identity=q.duoc_si,
        drug_batch_id=batch,
        ly_do="Hết hạn",
        khoa_gui=str(uuid.uuid4()),
    )
    with pytest.raises(NotFoundError):
        await lo.hoan_huy_lo(
            q.pool, identity=wrong, inventory_txn_id=result["inventory_txn_id"]
        )


async def test_hai_nguoi_huy_khoa_khac_chi_mot_lan(q: Quay) -> None:
    batch = await _batch(q)

    async def huy() -> dict[str, Any]:
        return await lo.huy_lo(
            q.pool,
            identity=q.duoc_si,
            drug_batch_id=batch,
            ly_do="Hết hạn",
            khoa_gui=str(uuid.uuid4()),
        )

    results = await asyncio.gather(huy(), huy(), return_exceptions=True)
    assert sum(isinstance(item, ValidationError) for item in results) == 1
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE drug_batch_id=$1::uuid "
            "AND txn_type='DISCARD'",
            batch,
        )
        == 1
    )


async def test_hoan_huy_con_doc_duoc_sau_tai_lai_man(q: Quay) -> None:
    batch = await _batch(q)
    result = await lo.huy_lo(
        q.pool,
        identity=q.duoc_si,
        drug_batch_id=batch,
        ly_do="Hết hạn",
        khoa_gui=str(uuid.uuid4()),
    )
    rows = await PharmacyService(q.pool).ton_kho(identity=q.duoc_si)
    assert (
        next(row for row in rows if row["id"] == batch)["huy_lo_txn_id"]
        == result["inventory_txn_id"]
    )
    await lo.hoan_huy_lo(
        q.pool, identity=q.duoc_si, inventory_txn_id=result["inventory_txn_id"]
    )
    rows = await PharmacyService(q.pool).ton_kho(identity=q.duoc_si)
    assert next(row for row in rows if row["id"] == batch)["huy_lo_txn_id"] is None


async def test_ba_lenh_lo_di_qua_cua_quyen_ghi(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    from importlib import import_module
    from unittest.mock import AsyncMock

    from fastapi.routing import APIRoute

    from clinicai.api.v1.routers import pharmacy
    from clinicai.core.exceptions import SafetyGateError

    gates = import_module("clinicai.permissions.cua_quyen")
    check = AsyncMock(return_value=False)
    monkeypatch.setattr(gates, "can", check)
    for path in ("sua-lo", "huy-lo-het-han", "hoan-huy-lo"):
        route = next(
            route
            for route in pharmacy.router.routes
            if isinstance(route, APIRoute) and route.path == f"/pharmacy/{path}"
        )
        assert pharmacy._GHI in [dep.call for dep in route.dependant.dependencies]
    with pytest.raises(SafetyGateError):
        await pharmacy._GHI(identity=q.duoc_si, pool=q.pool)
    assert check.await_args is not None
    assert check.await_args.args[2] == "pharmacy.dispense"
