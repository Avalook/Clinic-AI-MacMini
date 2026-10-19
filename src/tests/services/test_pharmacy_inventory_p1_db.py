"""HTTP and database guards for receive, adjust, and discard inventory writes."""

# ruff: noqa: F811 — fixture `q` is imported from CP1.

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import httpx
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity, _resolve_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


AI: dict[str, StaffIdentity] = {}


@pytest_asyncio.fixture
async def api(q: Quay) -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_db_pool] = lambda: q.pool
    app.dependency_overrides[_resolve_identity] = lambda: AI["ai"]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://pharmacy-p1"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)


async def _post(
    api: httpx.AsyncClient,
    identity: StaffIdentity,
    path: str,
    body: dict[str, Any],
    key: str | None,
) -> httpx.Response:
    AI["ai"] = identity
    headers = {"Idempotency-Key": key} if key is not None else {}
    return await api.post("/api/v1" + path, json=body, headers=headers)


async def _ton(q: Quay, drug_batch_id: str) -> Any:
    return await q.pool.fetchval(
        "SELECT quantity_on_hand FROM drug_batch WHERE id = $1::uuid", drug_batch_id
    )


async def test_adjust_retry_cung_khoa_chi_ghi_mot_dong(
    q: Quay, api: httpx.AsyncClient
) -> None:
    drug = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 'viên') RETURNING id::text",
            q.duoc_si.clinic_id,
            f"Thuốc P1 {uuid.uuid4().hex[:8]}",
        )
    )
    batch = await _nhap_lo(q, drug, 20)
    body = {"drug_batch_id": batch, "so_luong": -2, "ly_do": "Kiểm kê thiếu"}
    key = str(uuid.uuid4())

    a, b = await asyncio.gather(
        _post(api, q.duoc_si, "/pharmacy/adjust", body, key),
        _post(api, q.duoc_si, "/pharmacy/adjust", body, key),
    )

    assert a.status_code == b.status_code == 201, (a.text, b.text)
    assert a.json() == b.json()
    assert await _ton(q, batch) == 18
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE drug_batch_id=$1::uuid"
            " AND txn_type='ADJUST' AND reason='Kiểm kê thiếu'",
            batch,
        )
        == 1
    )


async def test_discard_retry_cung_khoa_chi_ghi_mot_dong(
    q: Quay, api: httpx.AsyncClient
) -> None:
    drug = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 'viên') RETURNING id::text",
            q.duoc_si.clinic_id,
            f"Thuốc P1 {uuid.uuid4().hex[:8]}",
        )
    )
    batch = await _nhap_lo(q, drug, 20)
    body = {"drug_batch_id": batch, "so_luong": 2, "ly_do": "Vỡ"}
    key = str(uuid.uuid4())

    a = await _post(api, q.duoc_si, "/pharmacy/discard", body, key)
    b = await _post(api, q.duoc_si, "/pharmacy/discard", body, key)

    assert a.status_code == b.status_code == 201, (a.text, b.text)
    assert a.json() == b.json()
    assert await _ton(q, batch) == 18
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE drug_batch_id=$1::uuid"
            " AND txn_type='DISCARD' AND reason='Vỡ'",
            batch,
        )
        == 1
    )


async def test_cung_khoa_nhung_khac_noi_dung_bi_tu_choi(
    q: Quay, api: httpx.AsyncClient
) -> None:
    drug = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 'viên') RETURNING id::text",
            q.duoc_si.clinic_id,
            f"Thuốc P1 {uuid.uuid4().hex[:8]}",
        )
    )
    batch = await _nhap_lo(q, drug, 20)
    key = str(uuid.uuid4())
    first = await _post(
        api,
        q.duoc_si,
        "/pharmacy/adjust",
        {"drug_batch_id": batch, "so_luong": -2, "ly_do": "Kiểm kê"},
        key,
    )
    changed = await _post(
        api,
        q.duoc_si,
        "/pharmacy/adjust",
        {"drug_batch_id": batch, "so_luong": -3, "ly_do": "Kiểm kê"},
        key,
    )

    assert first.status_code == 201, first.text
    assert changed.status_code == 409, changed.text
    assert await _ton(q, batch) == 18


async def test_cung_khoa_cua_nhan_vien_khac_khong_phat_lai_ket_qua(
    q: Quay, api: httpx.AsyncClient
) -> None:
    drug = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 'viên') RETURNING id::text",
            q.duoc_si.clinic_id,
            f"Thuốc P1 {uuid.uuid4().hex[:8]}",
        )
    )
    batch = await _nhap_lo(q, drug, 20)
    body = {"drug_batch_id": batch, "so_luong": -2, "ly_do": "Kiểm kê"}
    key = str(uuid.uuid4())

    first = await _post(api, q.duoc_si, "/pharmacy/adjust", body, key)
    other_staff = await _post(api, q.bac_si, "/pharmacy/adjust", body, key)

    assert first.status_code == other_staff.status_code == 201
    assert await _ton(q, batch) == 16
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE drug_batch_id=$1::uuid"
            " AND txn_type='ADJUST' AND reason='Kiểm kê'",
            batch,
        )
        == 2
    )


async def test_receive_retry_cung_khoa_chi_tao_mot_dong_so(
    q: Quay, api: httpx.AsyncClient
) -> None:
    drug = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 'viên') RETURNING id::text",
            q.duoc_si.clinic_id,
            f"Thuốc P1 {uuid.uuid4().hex[:8]}",
        )
    )
    batch_code = f"P1-{uuid.uuid4().hex[:10]}"
    body = {
        "drug_catalog_id": drug,
        "so_luong": 6,
        "batch_code": batch_code,
        "expiry_date": "2099-12-31",
        "unit": "viên",
    }
    key = str(uuid.uuid4())

    a = await _post(api, q.duoc_si, "/pharmacy/receive", body, key)
    b = await _post(api, q.duoc_si, "/pharmacy/receive", body, key)

    assert a.status_code == b.status_code == 201, (a.text, b.text)
    assert a.json() == b.json()
    assert float(a.json()["quantity_on_hand"]) == 6
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn t "
            "JOIN drug_batch b ON b.id=t.drug_batch_id"
            " WHERE b.batch_code=$1 AND t.txn_type='RECEIVE'",
            batch_code,
        )
        == 1
    )


async def test_receive_tu_choi_cung_khoa_khac_so_luong(
    q: Quay, api: httpx.AsyncClient
) -> None:
    drug = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 'viên') RETURNING id::text",
            q.duoc_si.clinic_id,
            f"Thuốc P1 {uuid.uuid4().hex[:8]}",
        )
    )
    body = {
        "drug_catalog_id": drug,
        "so_luong": 6,
        "batch_code": f"P1-{uuid.uuid4().hex[:10]}",
        "expiry_date": "2099-12-31",
        "unit": "viên",
    }
    key = str(uuid.uuid4())
    first = await _post(api, q.duoc_si, "/pharmacy/receive", body, key)
    changed = await _post(
        api,
        q.duoc_si,
        "/pharmacy/receive",
        {**body, "so_luong": 8},
        key,
    )

    assert first.status_code == 201, first.text
    assert changed.status_code == 409, changed.text
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE batch_code=$1",
            body["batch_code"],
        )
        == 6
    )


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (
            "/pharmacy/receive",
            {
                "drug_catalog_id": "c0000000-0000-4000-8000-000000000001",
                "so_luong": 1,
                "batch_code": "P1-NO-KEY",
                "expiry_date": "2099-12-31",
                "unit": "viên",
            },
        ),
        (
            "/pharmacy/adjust",
            {
                "drug_batch_id": "b0000000-0000-4000-8000-000000000001",
                "so_luong": -1,
                "ly_do": "Kiểm kê",
            },
        ),
        (
            "/pharmacy/discard",
            {
                "drug_batch_id": "b0000000-0000-4000-8000-000000000001",
                "so_luong": 1,
                "ly_do": "Vỡ",
            },
        ),
    ],
)
async def test_thao_tac_kho_thieu_khoa_gui_lai_bi_tu_choi(
    q: Quay, api: httpx.AsyncClient, path: str, body: dict[str, Any]
) -> None:
    AI["ai"] = q.duoc_si
    response = await api.post(
        "/api/v1" + path,
        json=body,
    )
    assert response.status_code == 422
    assert "Idempotency-Key" in response.text


async def test_nhap_cung_so_lo_khac_don_vi_bi_tu_choi(q: Quay) -> None:
    drug = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 'viên') RETURNING id::text",
            q.duoc_si.clinic_id,
            f"Thuốc P1 {uuid.uuid4().hex[:8]}",
        )
    )
    service = PharmacyService(q.pool)
    batch_code = f"P1-UNIT-{uuid.uuid4().hex[:8]}"
    await service.nhap_lo(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        so_luong=5,
        batch_code=batch_code,
        expiry_date=None,
        unit="hộp",
    )

    with pytest.raises(ConflictError, match="đơn vị"):
        await service.nhap_lo(
            identity=q.duoc_si,
            drug_catalog_id=drug,
            so_luong=3,
            batch_code=batch_code,
            expiry_date=None,
            unit="viên",
        )

    # Cùng đơn vị sau chuẩn hoá (NFC + bỏ khoảng trắng + không phân biệt hoa)
    # vẫn là cùng lô, không bị chia thành hai đơn vị tồn.
    await service.nhap_lo(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        so_luong=2,
        batch_code=batch_code,
        expiry_date=None,
        unit=" HỘP ",
    )
    assert (
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE batch_code=$1",
            batch_code,
        )
        == 7
    )


@pytest.mark.parametrize("numeric", ["NaN", "Infinity", "-Infinity"])
async def test_inventory_db_tu_choi_so_khong_huu_han(q: Quay, numeric: str) -> None:
    drug = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 'viên') RETURNING id::text",
            q.duoc_si.clinic_id,
            f"Thuốc P1 {uuid.uuid4().hex[:8]}",
        )
    )
    batch = await _nhap_lo(q, drug, 2)

    with pytest.raises(asyncpg.PostgresError):
        await q.pool.execute(
            "INSERT INTO inventory_txn"
            " (clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type,"
            " performed_by_staff_id)"
            " VALUES ($1::uuid, $2::uuid, 'ADJUST', $4::numeric, 'bad',"
            " 'manual', $3::uuid)",
            q.duoc_si.clinic_id,
            batch,
            q.duoc_si.staff_id,
            numeric,
        )

    with pytest.raises(asyncpg.PostgresError):
        await q.pool.execute(
            "UPDATE drug_batch SET quantity_on_hand=$2::numeric WHERE id=$1::uuid",
            batch,
            numeric,
        )

    with pytest.raises(asyncpg.PostgresError):
        await q.pool.execute(
            "UPDATE drug_batch SET cost_price=$2::numeric WHERE id=$1::uuid",
            batch,
            numeric,
        )
