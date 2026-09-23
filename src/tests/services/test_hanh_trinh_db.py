"""Hành trình một lượt khám hiện đủ trên một màn — khách là trên hết.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55475/postgres \
        poetry run pytest src/tests/services/test_hanh_trinh_db.py

Trước đây muốn biết "khách này đang ở đâu, đã làm gì" phải mở bốn màn và hỏi ba
người. Dòng thời gian dựng từ sổ sự kiện trả lời được bằng một câu truy vấn — và
dựng lại được từ đầu nếu cần.

Bài này cũng canh một thứ dễ mất: **không chữ lâm sàng nào lọt vào màn này**.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.events.catalogue import (
    DONG_THOI_GIAN_LUOT,
    ChiDinhDaDat,
    DichVuDaBatDau,
    DichVuDaXong,
    KhachDaToi,
    PhieuDaHoanTat,
    SinhHieuDaDo,
)
from clinicai.events.emit import HE_THONG, emit_event
from clinicai.events.worker import lam_mot_dong

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield p
    await p.close()


async def _lam_het(pool: asyncpg.Pool) -> None:
    for _ in range(50_000):
        if not await lam_mot_dong(pool, DONG_THOI_GIAN_LUOT):
            return


async def test_mot_man_thay_ca_hanh_trinh(pool: asyncpg.Pool) -> None:
    visit_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())

    async with pool.acquire() as conn, conn.transaction():
        await emit_event(
            conn,
            ten="visit.checked_in",
            clinic_id=CLINIC,
            aggregate_id=visit_id,
            payload=KhachDaToi(visit_id=visit_id, so_thu_tu=12),
            boi=HE_THONG,
            correlation_id=visit_id,
        )
        await emit_event(
            conn,
            ten="vitals.recorded",
            clinic_id=CLINIC,
            aggregate_id=visit_id,
            payload=SinhHieuDaDo(visit_id=visit_id),
            boi=HE_THONG,
            correlation_id=visit_id,
        )
        await emit_event(
            conn,
            ten="service_order.placed",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=1,
            payload=ChiDinhDaDat(
                order_id=order_id,
                service_code="SA-DAUDO",
                service_name="Siêu âm đầu dò",
                consultation_id=str(uuid.uuid4()),
                visit_id=visit_id,
                selection_status="PENDING",
                billing_status="UNPAID",
            ),
            boi=HE_THONG,
            correlation_id=visit_id,
        )
        await emit_event(
            conn,
            ten="service.started",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=2,
            payload=DichVuDaBatDau(
                visit_id=visit_id,
                service_order_id=order_id,
                attempt_id=str(uuid.uuid4()),
                attempt_no=1,
                execution_revision=2,
            ),
            boi=HE_THONG,
            correlation_id=visit_id,
        )
        await emit_event(
            conn,
            ten="service.completed",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=3,
            payload=DichVuDaXong(
                visit_id=visit_id,
                service_order_id=order_id,
                attempt_id=str(uuid.uuid4()),
                attempt_no=1,
                execution_revision=3,
            ),
            boi=HE_THONG,
            correlation_id=visit_id,
        )

        await emit_event(
            conn,
            ten="result_form.completed",
            clinic_id=CLINIC,
            # Phiếu là đối tượng riêng — không dùng chung số phiên bản với chỉ định.
            aggregate_id=str(uuid.uuid4()),
            aggregate_version=1,
            payload=PhieuDaHoanTat(
                service_order_id=order_id,
                visit_id=visit_id,
                form_id="KQ_SA_TC_BT",
                form_version=1,
                so_o_con_trong=0,
            ),
            boi=HE_THONG,
            correlation_id=visit_id,
        )

    await _lam_het(pool)

    dong = await pool.fetch(
        "SELECT event_type, nhan, chi_tiet FROM luot_dong_thoi_gian"
        " WHERE visit_id = $1::uuid ORDER BY occurred_at, thu_tu",
        visit_id,
    )
    assert [d["event_type"] for d in dong] == [
        "visit.checked_in",
        "vitals.recorded",
        "service_order.placed",
        "service.started",
        "service.completed",
        "result_form.completed",
    ]
    assert [d["nhan"] for d in dong][:2] == [
        "Khách đã tới (check-in)",
        "Đã đo sinh hiệu",
    ]

    # Không một chữ lâm sàng nào lọt vào màn này: chỉ mã, số và tên dịch vụ.
    ca_man = " ".join(
        json.dumps(json.loads(d["chi_tiet"]), ensure_ascii=False) for d in dong
    )
    assert "huyết áp" not in ca_man.lower()
    assert "SA-DAUDO" in ca_man


async def test_dung_lai_duoc_tu_so_su_kien(pool: asyncpg.Pool) -> None:
    """Phép thử của cả thiết kế: xoá màn đi, chạy lại sổ, phải ra đúng như cũ."""
    visit_id = str(uuid.uuid4())
    async with pool.acquire() as conn, conn.transaction():
        await emit_event(
            conn,
            ten="visit.checked_in",
            clinic_id=CLINIC,
            aggregate_id=visit_id,
            payload=KhachDaToi(visit_id=visit_id, so_thu_tu=7),
            boi=HE_THONG,
            correlation_id=visit_id,
        )
    await _lam_het(pool)
    truoc = await pool.fetchval(
        "SELECT count(*) FROM luot_dong_thoi_gian WHERE visit_id = $1::uuid", visit_id
    )
    assert truoc == 1

    # Xoá projection và giao lại: màn phải dựng lại y như cũ.
    await pool.execute(
        "DELETE FROM luot_dong_thoi_gian WHERE visit_id = $1::uuid", visit_id
    )
    await pool.execute(
        "UPDATE event_delivery d SET status = 'PENDING', processed_at = NULL"
        "  FROM domain_event e"
        " WHERE e.event_id = d.event_id AND d.consumer = $1"
        "   AND e.correlation_id = $2::uuid",
        DONG_THOI_GIAN_LUOT,
        visit_id,
    )
    await _lam_het(pool)

    sau = await pool.fetch(
        "SELECT event_type, nhan FROM luot_dong_thoi_gian WHERE visit_id = $1::uuid",
        visit_id,
    )
    assert [r["event_type"] for r in sau] == ["visit.checked_in"]
