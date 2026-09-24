"""Sổ sự kiện trên Postgres thật — nền event-driven bước 1.

Chạy (DB dùng một lần, đã nạp migration + seed):

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55471/postgres \\
        poetry run pytest src/tests/services/test_domain_event_db.py

Năm điều phải đúng, vì cả thiết kế đứng trên chúng:
  1. Phát một sự kiện thì dòng giao cho từng bên nhận sinh ra CÙNG giao dịch.
  2. Giao dịch hỏng thì cả hai cùng biến mất — không có sự kiện mồ côi.
  3. Sổ chỉ thêm: UPDATE và DELETE bị Postgres chặn, không nhờ ai nhớ.
  4. Cùng một đối tượng không có hai sự kiện trùng số thứ tự.
  5. Sự kiện cần đúng thứ tự mà thiếu số thứ tự thì hỏng NGAY lúc phát.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT, ChiDinhDaDat
from clinicai.events.emit import HE_THONG, NguoiGayRa, ai_agent, emit_event

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


def _payload(order_id: str) -> ChiDinhDaDat:
    return ChiDinhDaDat(
        order_id=order_id,
        service_code="SA-DAUDO",
        service_name="Siêu âm đầu dò",
        consultation_id=str(uuid.uuid4()),
        visit_id=str(uuid.uuid4()),
        selection_status="PENDING",
        billing_status="UNPAID",
    )


async def test_phat_su_kien_sinh_dong_giao_cung_giao_dich(pool: asyncpg.Pool) -> None:
    order_id = str(uuid.uuid4())
    nguoi_bam = NguoiGayRa(
        actor_type="HUMAN", staff_id=str(uuid.uuid4()), role="DOCTOR"
    )

    async with pool.acquire() as conn, conn.transaction():
        event_id = await emit_event(
            conn,
            ten="service_order.placed",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=1,
            payload=_payload(order_id),
            boi=nguoi_bam,
        )

    su_kien = await pool.fetchrow(
        "SELECT * FROM domain_event WHERE event_id = $1::uuid", event_id
    )
    assert su_kien is not None
    assert su_kien["event_type"] == "service_order.placed"
    assert su_kien["aggregate_type"] == "service_order"
    assert su_kien["actor_type"] == "HUMAN"
    assert su_kien["is_public"] is True
    assert su_kien["tx_id"] is not None

    giao = await pool.fetch(
        "SELECT consumer, status, attempts FROM event_delivery"
        " WHERE event_id = $1::uuid",
        event_id,
    )
    assert [(g["consumer"], g["status"], g["attempts"]) for g in giao] == [
        (DONG_THOI_GIAN_LUOT, "PENDING", 0)
    ]


async def test_giao_dich_hong_thi_khong_con_gi_sot_lai(pool: asyncpg.Pool) -> None:
    """Không có sự kiện mồ côi: hiện trạng không đổi thì sự kiện cũng không có."""
    order_id = str(uuid.uuid4())
    with pytest.raises(RuntimeError, match="hong giua chung"):
        async with pool.acquire() as conn, conn.transaction():
            await emit_event(
                conn,
                ten="service_order.placed",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=_payload(order_id),
                boi=HE_THONG,
            )
            raise RuntimeError("hong giua chung")

    con_lai = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE aggregate_id = $1::uuid", order_id
    )
    assert con_lai == 0


async def test_so_chi_them_khong_sua_khong_xoa(pool: asyncpg.Pool) -> None:
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn, conn.transaction():
        event_id = await emit_event(
            conn,
            ten="service_order.placed",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=1,
            payload=_payload(order_id),
            boi=HE_THONG,
        )

    with pytest.raises(asyncpg.PostgresError, match="chi duoc THEM"):
        await pool.execute(
            "UPDATE domain_event SET payload = '{}'::jsonb WHERE event_id = $1::uuid",
            event_id,
        )
    with pytest.raises(asyncpg.PostgresError, match="chi duoc THEM"):
        await pool.execute(
            "DELETE FROM domain_event WHERE event_id = $1::uuid", event_id
        )


async def test_khong_hai_su_kien_trung_so_thu_tu(pool: asyncpg.Pool) -> None:
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn, conn.transaction():
        await emit_event(
            conn,
            ten="service_order.placed",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=1,
            payload=_payload(order_id),
            boi=HE_THONG,
        )

    with pytest.raises(asyncpg.UniqueViolationError):
        async with pool.acquire() as conn, conn.transaction():
            await emit_event(
                conn,
                ten="service_order.placed",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=_payload(order_id),
                boi=HE_THONG,
            )


async def test_thieu_so_thu_tu_thi_hong_ngay_luc_phat(pool: asyncpg.Pool) -> None:
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn, conn.transaction():
        with pytest.raises(ValueError, match="aggregate_version"):
            await emit_event(
                conn,
                ten="service_order.placed",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                payload=_payload(order_id),
                boi=HE_THONG,
            )


async def test_ai_phai_khai_phien_ban(pool: asyncpg.Pool) -> None:
    """AI ghi vào sổ thì sau này phải truy được bản nào đã quyết."""
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn, conn.transaction():
        event_id = await emit_event(
            conn,
            ten="service_order.placed",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=1,
            payload=_payload(order_id),
            boi=ai_agent(
                ten_agent="goi_y_phong", phien_ban="v0.1", thay_cho=str(uuid.uuid4())
            ),
        )

    dong = await pool.fetchrow(
        "SELECT actor_type, agent_version, on_behalf_of FROM domain_event"
        " WHERE event_id = $1::uuid",
        event_id,
    )
    assert dong is not None
    assert dong["actor_type"] == "AGENT"
    assert dong["agent_version"] == "v0.1"
    assert dong["on_behalf_of"] is not None


async def test_nguoi_phai_biet_la_ai(pool: asyncpg.Pool) -> None:
    """HUMAN mà không có staff_id thì Postgres chặn — không ghi 'ai đó đã bấm'."""
    order_id = str(uuid.uuid4())
    with pytest.raises(asyncpg.PostgresError):
        async with pool.acquire() as conn, conn.transaction():
            await emit_event(
                conn,
                ten="service_order.placed",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=_payload(order_id),
                boi=NguoiGayRa(actor_type="HUMAN"),
            )
