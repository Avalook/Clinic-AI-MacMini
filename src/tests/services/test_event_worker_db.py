"""Người đưa tin trên Postgres thật — nền event-driven bước 2.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55471/postgres \\
        poetry run pytest src/tests/services/test_event_worker_db.py

Sáu kiểu hỏng phải bị chặn, tất cả đều đã xảy ra ở hệ khác ngoài đời:
  1. Giao được tin → projection có dòng, dòng giao thành DONE.
  2. Giao hai lần (at-least-once) → màn KHÔNG có hai dòng.
  3. Bên nhận hỏng → RETRY, có hẹn giờ thử lại, không mất sự kiện.
  4. Hỏng quá số lần → DEAD, KHÔNG xoá, hiện ở màn sức khoẻ.
  5. Worker chết giữa chừng → thu hồi được, không kẹt IN_PROGRESS.
  6. Cùng một đối tượng → xử lý đúng thứ tự, không nhảy cóc.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT, ChiDinhDaDat
from clinicai.events.emit import HE_THONG, emit_event
from clinicai.events.worker import (
    SO_LAN_THU_TOI_DA,
    SuKienDaNhan,
    dang_ky,
    lam_mot_dong,
    thu_hoi_thue,
)

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


async def _chi_dinh(
    pool: asyncpg.Pool, *, visit_id: str, order_id: str, lan: int = 1
) -> str:
    async with pool.acquire() as conn, conn.transaction():
        return await emit_event(
            conn,
            ten="service_order.placed",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=lan,
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
        )


async def _lam_het(pool: asyncpg.Pool, consumer: str, gioi_han: int = 50_000) -> None:
    """Làm sạch hàng đợi của một bên nhận.

    Các test chạy chung một DB nên hàng đợi có thể còn dòng của test trước;
    `lam_mot_dong` lấy dòng cũ nhất chứ không lấy dòng của riêng test này.
    """
    for _ in range(gioi_han):
        if not await lam_mot_dong(pool, consumer):
            return


async def test_giao_duoc_thi_projection_co_dong(pool: asyncpg.Pool) -> None:
    visit_id, order_id = str(uuid.uuid4()), str(uuid.uuid4())
    event_id = await _chi_dinh(pool, visit_id=visit_id, order_id=order_id)

    await _lam_het(pool, DONG_THOI_GIAN_LUOT)

    dong = await pool.fetchrow(
        "SELECT * FROM luot_dong_thoi_gian WHERE event_id = $1::uuid", event_id
    )
    assert dong is not None
    assert str(dong["visit_id"]) == visit_id
    assert dong["nhan"] == "Đã chỉ định dịch vụ"

    giao = await pool.fetchrow(
        "SELECT status, processed_at FROM event_delivery"
        " WHERE event_id = $1::uuid AND consumer = $2",
        event_id,
        DONG_THOI_GIAN_LUOT,
    )
    assert giao is not None
    assert giao["status"] == "DONE"
    assert giao["processed_at"] is not None


async def test_giao_lai_lan_hai_khong_nhan_doi_dong(pool: asyncpg.Pool) -> None:
    visit_id, order_id = str(uuid.uuid4()), str(uuid.uuid4())
    event_id = await _chi_dinh(pool, visit_id=visit_id, order_id=order_id)
    await _lam_het(pool, DONG_THOI_GIAN_LUOT)

    # Giả lập giao lại: đẩy dòng về PENDING như khi worker chết sau khi ghi.
    await pool.execute(
        "UPDATE event_delivery SET status = 'PENDING', processed_at = NULL"
        " WHERE event_id = $1::uuid AND consumer = $2",
        event_id,
        DONG_THOI_GIAN_LUOT,
    )
    await _lam_het(pool, DONG_THOI_GIAN_LUOT)

    so_dong = await pool.fetchval(
        "SELECT count(*) FROM luot_dong_thoi_gian WHERE visit_id = $1::uuid", visit_id
    )
    assert so_dong == 1


async def test_ben_nhan_hong_thi_thu_lai_chu_khong_mat(pool: asyncpg.Pool) -> None:
    ten_gia = f"ben_nhan_hong_{uuid.uuid4().hex[:6]}"

    async def luon_hong(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
        raise RuntimeError("giả vờ hỏng")

    dang_ky(ten_gia, luon_hong)

    visit_id, order_id = str(uuid.uuid4()), str(uuid.uuid4())
    event_id = await _chi_dinh(pool, visit_id=visit_id, order_id=order_id)
    await pool.execute(
        "INSERT INTO event_delivery (event_id, consumer, clinic_id, aggregate_id,"
        " aggregate_version) VALUES ($1::uuid, $2, $3::uuid, $4::uuid, 1)",
        event_id,
        ten_gia,
        CLINIC,
        order_id,
    )

    await lam_mot_dong(pool, ten_gia)

    dong = await pool.fetchrow(
        "SELECT status, attempts, last_error, next_attempt_at > now() AS con_cho"
        " FROM event_delivery WHERE event_id = $1::uuid AND consumer = $2",
        event_id,
        ten_gia,
    )
    assert dong is not None
    assert dong["status"] == "RETRY"
    assert dong["attempts"] == 1
    assert "giả vờ hỏng" in dong["last_error"]
    assert dong["con_cho"] is True


async def test_hong_qua_so_lan_thi_vao_hop_chet_va_van_con_do(
    pool: asyncpg.Pool,
) -> None:
    ten_gia = f"ben_nhan_chet_{uuid.uuid4().hex[:6]}"

    async def luon_hong(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
        raise RuntimeError("hỏng mãi")

    dang_ky(ten_gia, luon_hong)

    visit_id, order_id = str(uuid.uuid4()), str(uuid.uuid4())
    event_id = await _chi_dinh(pool, visit_id=visit_id, order_id=order_id)
    await pool.execute(
        "INSERT INTO event_delivery (event_id, consumer, clinic_id, aggregate_id,"
        " aggregate_version, attempts)"
        " VALUES ($1::uuid, $2, $3::uuid, $4::uuid, 1, $5)",
        event_id,
        ten_gia,
        CLINIC,
        order_id,
        SO_LAN_THU_TOI_DA - 1,
    )

    await lam_mot_dong(pool, ten_gia)

    dong = await pool.fetchrow(
        "SELECT status FROM event_delivery WHERE event_id = $1::uuid AND consumer = $2",
        event_id,
        ten_gia,
    )
    assert dong is not None
    assert dong["status"] == "DEAD"

    suc_khoe = await pool.fetchrow(
        "SELECT chet FROM v_event_delivery_suc_khoe WHERE consumer = $1", ten_gia
    )
    assert suc_khoe is not None
    assert suc_khoe["chet"] == 1


async def test_worker_chet_giua_chung_thi_thu_hoi_duoc(pool: asyncpg.Pool) -> None:
    visit_id, order_id = str(uuid.uuid4()), str(uuid.uuid4())
    event_id = await _chi_dinh(pool, visit_id=visit_id, order_id=order_id)

    # Giả lập: worker nhận việc rồi chết, hạn thuê đã qua.
    await pool.execute(
        "UPDATE event_delivery SET status = 'IN_PROGRESS',"
        " lease_expires_at = now() - interval '1 minute', locked_by = 'worker_chet'"
        " WHERE event_id = $1::uuid AND consumer = $2",
        event_id,
        DONG_THOI_GIAN_LUOT,
    )

    assert await thu_hoi_thue(pool) >= 1

    dong = await pool.fetchrow(
        "SELECT status, locked_by FROM event_delivery"
        " WHERE event_id = $1::uuid AND consumer = $2",
        event_id,
        DONG_THOI_GIAN_LUOT,
    )
    assert dong is not None
    assert dong["status"] == "RETRY"
    assert dong["locked_by"] is None

    await _lam_het(pool, DONG_THOI_GIAN_LUOT)
    xong = await pool.fetchval(
        "SELECT status FROM event_delivery WHERE event_id = $1::uuid AND consumer = $2",
        event_id,
        DONG_THOI_GIAN_LUOT,
    )
    assert xong == "DONE"


async def test_cung_mot_doi_tuong_thi_dung_thu_tu(pool: asyncpg.Pool) -> None:
    """Sự kiện số 2 không được xử lý trước sự kiện số 1 của cùng chỉ định."""
    ten_gia = f"ghi_thu_tu_{uuid.uuid4().hex[:6]}"
    da_xu_ly: list[int] = []

    async def ghi_lai(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
        assert su_kien.aggregate_version is not None
        da_xu_ly.append(su_kien.aggregate_version)

    dang_ky(ten_gia, ghi_lai)

    visit_id, order_id = str(uuid.uuid4()), str(uuid.uuid4())
    e1 = await _chi_dinh(pool, visit_id=visit_id, order_id=order_id, lan=1)
    e2 = await _chi_dinh(pool, visit_id=visit_id, order_id=order_id, lan=2)
    for event_id, lan in ((e1, 1), (e2, 2)):
        await pool.execute(
            "INSERT INTO event_delivery (event_id, consumer, clinic_id, aggregate_id,"
            " aggregate_version) VALUES ($1::uuid, $2, $3::uuid, $4::uuid, $5)",
            event_id,
            ten_gia,
            CLINIC,
            order_id,
            lan,
        )

    # Dù sự kiện 2 được hẹn sớm hơn, nó vẫn phải chờ sự kiện 1 xong.
    await pool.execute(
        "UPDATE event_delivery SET next_attempt_at = now() - interval '1 hour'"
        " WHERE event_id = $1::uuid AND consumer = $2",
        e2,
        ten_gia,
    )

    await _lam_het(pool, ten_gia)

    assert da_xu_ly == [1, 2]
