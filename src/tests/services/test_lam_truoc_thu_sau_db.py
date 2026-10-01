"""V10 — LÀM TRƯỚC, THU SAU (Tuyền 30/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55563/postgres \\
        .venv/bin/pytest src/tests/services/test_lam_truoc_thu_sau_db.py

"Chỉ định rồi mà chưa thu tiền cũng vẫn cho thực hiện đi rồi cuối buổi thu cũng
được." Chị Lan được chỉ định siêu âm, lễ tân chốt dịch vụ nhưng CHƯA thu: chị có
phòng ngay, phòng bắt đầu và làm xong được; check-out vẫn nhắc còn nợ; cuối buổi
quầy thu đúng số tiền (kể cả dịch vụ đã làm xong).

30/09/2026 tối: hành vi này nay là dây ``thu_truoc_khi_lam`` TẮT (mặc định BẬT
= thu trước, trừ lượt tick "Làm trước – thu sau" —
``test_thu_truoc_lam_truoc_tick_db``). Mọi bài ở đây chạy với dây TẮT.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from clinicai.services import finance_gate
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_routing_service import ServiceRoutingService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
    _su_kien,
    _thu,
    _thu_khoi_dieu_phoi,
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture(autouse=True)
async def _v10_day_tat(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    async with day_thu_truoc(pool, False):
        yield


async def _gate(pool: asyncpg.Pool, order: str) -> finance_gate.FinanceDecision:  # noqa: F811
    async with pool.acquire() as conn:
        g = await finance_gate.can_start(conn, CLINIC, order)
    assert g is not None
    return g


async def _con_no(pool: asyncpg.Pool, visit: str):  # type: ignore[no-untyped-def]  # noqa: F811
    async with pool.acquire() as conn:
        return await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)


async def _vuong(pool: asyncpg.Pool, ca, visit: str) -> set[str]:  # type: ignore[no-untyped-def]  # noqa: F811
    kq = await CheckoutService(pool).readiness(identity=ca.le_tan, visit_id=visit)
    return {b["type"] for b in kq["blockers"]}


async def test_chot_chua_thu_co_phong_lam_xong_check_out_bao_no_cuoi_buoi_thu_du(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)

    # Lễ tân chốt — KHÔNG thu.
    await _chon(pool, ca, visit, [order])
    await chay_hanh_trinh(pool)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid", visit
        )
        == 0
    )
    d = await _don(pool, order)
    assert d["routing_status"] == "ASSIGNED" and d["room_id"] is not None
    assert d["assigned_by"] == ca.le_tan.staff_id  # thay NGƯỜI CHỐT
    [xep] = await _su_kien(pool, "service.routed", order)
    assert json.loads(xep["payload"])["tu_dong"] is True
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE ref_id = $1::uuid"
            " AND lane = 'ROOM' AND status IN ('blocked', 'waiting')",
            order,
        )
        == 1
    )
    g = await _gate(pool, order)
    assert (g.finance_state, g.financially_ready, g.duoc_lam) == ("DUE", False, True)

    # Hoá đơn còn nợ TRƯỚC khi làm — số cuối buổi phải bằng đúng số này.
    truoc = await _con_no(pool, visit)
    assert order in {x.source_id for x in truoc.dong}
    assert truoc.tong > 0

    # Phòng bắt đầu + làm xong khi chưa thu.
    bd = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    d2 = await _don(pool, order)
    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=bd["attempt_id"],
        expected_execution_revision=int(d2["execution_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    assert (
        await pool.fetchval(
            "SELECT execution_status FROM service_order WHERE id = $1::uuid", order
        )
        == "COMPLETED"
    )

    # Làm xong mà chưa thu = khoản phải thu bình thường, KHÔNG rơi khỏi hoá đơn.
    g = await _gate(pool, order)
    assert (g.finance_state, g.needs_human_review) == ("DUE", False)
    sau = await _con_no(pool, visit)
    assert (sau.tong, sau.revision) == (truoc.tong, truoc.revision)

    # Check-out báo còn nợ — từ 01/10/2026 là vướng CỨNG "con_no" (đã làm mà
    # chưa thu: chặn tới khi thu hoặc ghi nợ — test_cong_no_check_out_db).
    assert "con_no" in await _vuong(pool, ca, visit)

    # Cuối buổi thu: đúng số tiền, dịch vụ đã làm nằm trong phiếu.
    await _thu(pool, visit, ca.thu_ngan)
    c = await pool.fetchrow(
        "SELECT payment_cycle_id::text AS id, amount FROM payment_cycle"
        " WHERE visit_id = $1::uuid AND kind = 'dich_vu' AND status = 'PAID'",
        visit,
    )
    assert int(c["amount"]) == truoc.tong
    assert order in {
        r["source_id"]
        for r in await pool.fetch(
            "SELECT source_id FROM payment_bill_line WHERE payment_cycle_id = $1::uuid",
            c["id"],
        )
    }
    assert (await _gate(pool, order)).finance_state == "PAID"
    assert (await _con_no(pool, visit)).tong == 0
    assert not {"unpaid_service", "con_no"} & await _vuong(pool, ca, visit)

    # Dây H4 chạy lại sau khi thu: vô hại (đã có phòng, không xếp thêm).
    await chay_hanh_trinh(pool)
    assert len(await _su_kien(pool, "service.routed", order)) == 1


async def test_nguoi_chot_khong_co_quyen_xep_thi_de_nguyen_thu_xong_xep(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Người chốt không có quyền điều phối → để nguyên; người thu có quyền thì
    lúc thu dây H4 xếp như cũ (``tu_xep_da_thu`` chạy lại)."""
    ca = await _dung(pool)
    await _thu_khoi_dieu_phoi(pool, ca.le_tan)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "UNASSIGNED"

    await _thu(pool, visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["routing_status"] == "ASSIGNED"
    assert d["assigned_by"] == ca.thu_ngan.staff_id


async def test_xep_tay_va_phong_du_kien_khi_chua_thu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Chưa thu: xếp tay được; chọn phòng ở quầy cho chỉ định ĐÃ CHỐT = xếp thật."""
    ca = await _dung(pool)
    await _thu_khoi_dieu_phoi(pool, ca.le_tan)  # để dây H4 không tự xếp
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["routing_status"] == "UNASSIGNED"

    kq = await ServiceRoutingService(pool).dat_phong_du_kien(
        order_id=order, room_id=ca.phong, identity=ca.thu_ngan
    )
    assert kq["ok"] is True
    d = await _don(pool, order)
    assert (d["routing_status"], d["room_id"]) == ("ASSIGNED", ca.phong)

    # Xếp tay đổi phòng lúc chưa thu — không còn SERVICE_FINANCE_NOT_READY.
    async with pool.acquire() as conn:
        from tests.services.test_thu_tien_xep_phong_mang_sang_db import _phong

        khac = await _phong(conn, ca.loc, "v10")
    await ServiceRoutingService(pool).assign(
        order_id=order,
        room_id=khac,
        expected_routing_revision=int(d["routing_revision"]),
        reason_code="LOAD_BALANCE",
        identity=ca.thu_ngan,
        idempotency_key=_khoa(),
    )
    assert (await _don(pool, order))["room_id"] == khac
