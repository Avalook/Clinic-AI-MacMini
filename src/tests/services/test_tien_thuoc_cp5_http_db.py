"""Review CP5 P1-A: hoàn tiền và khách trả thuốc chống GỬI TRÙNG qua HTTP thật.

Mất phản hồi rồi trình duyệt / proxy gửi lại CÙNG `Idempotency-Key` phải nhận
lại kết quả lần đầu — không tạo khoản hoàn thứ hai, không có lần trả /
RETURN_RECEIVED thứ hai, tồn vật lý chỉ +1.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio

from clinicai.api.identity import StaffIdentity, _resolve_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _ton
from tests.services.test_tien_thuoc_cp5_db import (
    _da_thu_giao,
    _dong_thuoc,
    _ql,
    _xuat,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

AI: dict[str, StaffIdentity] = {}


@pytest_asyncio.fixture
async def api(q: Quay) -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_db_pool] = lambda: q.pool
    app.dependency_overrides[_resolve_identity] = lambda: AI["ai"]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://cp5"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)


async def _gui(
    api: httpx.AsyncClient,
    ai: StaffIdentity,
    path: str,
    body: dict[str, Any],
    khoa: str,
) -> httpx.Response:
    AI["ai"] = ai
    return await api.post(
        "/api/v1" + path, json=body, headers={"Idempotency-Key": khoa}
    )


async def test_hoan_tien_mat_gui_lai_cung_khoa_chi_mot_khoan(
    q: Quay, api: httpx.AsyncClient
) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    body = {
        "payment_cycle_id": lan,
        "visit_id": q.visit_id,
        "kind": "thuoc",
        "method": "CASH",
        "reason": "Khách không lấy 2 viên",
        "dong": [{"payment_bill_line_id": await _dong_thuoc(q, lan), "so_luong": 2}],
    }
    khoa = "cp5-hoan-" + uuid.uuid4().hex
    a = await _gui(api, _ql(q), "/payments/hoan-tien", body, khoa)
    b = await _gui(api, _ql(q), "/payments/hoan-tien", body, khoa)
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    assert a.json()["refund_id"] == b.json()["refund_id"]
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_refund WHERE payment_cycle_id = $1::uuid", lan
        )
        == 1
    )
    assert (
        await q.pool.fetchval(
            "SELECT sum(amount) FROM payment_refund WHERE payment_cycle_id = $1::uuid",
            lan,
        )
        == 10_000
    )
    # Khoá KHÁC = thao tác mới, hợp lệ (hoàn thêm lần nữa).
    c = await _gui(api, _ql(q), "/payments/hoan-tien", body, khoa + "-2")
    assert c.status_code == 200 and c.json()["refund_id"] != a.json()["refund_id"]


async def test_khach_tra_gui_lai_cung_khoa_chi_mot_lan_tra(
    q: Quay, api: httpx.AsyncClient
) -> None:
    rx, lo, _ = await _da_thu_giao(q, 4)
    ton = await _ton(q, lo)
    body = {
        "dispense_txn_id": await _xuat(q, rx),
        "so_luong": 1,
        "ly_do": "Khách dị ứng",
    }
    khoa = "cp5-tra-" + uuid.uuid4().hex
    a = await _gui(api, q.duoc_si, "/pharmacy/khach-tra", body, khoa)
    b = await _gui(api, q.duoc_si, "/pharmacy/khach-tra", body, khoa)
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    assert a.json()["drug_return_id"] == b.json()["drug_return_id"]
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM drug_return WHERE prescription_id = $1::uuid", rx
        )
        == 1
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE txn_type = 'RETURN_RECEIVED'"
            " AND drug_batch_id = $1::uuid",
            lo,
        )
        == 1
    )
    assert await _ton(q, lo) == ton + 1
