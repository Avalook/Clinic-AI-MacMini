"""Hẹn giờ — "sau bao lâu thì làm gì", và làm đúng lúc còn cần.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55475/postgres \
        poetry run pytest src/tests/services/test_hen_gio_db.py

Bài quan trọng nhất ở đây là bài thứ ba: **hết cần thì đừng nhắc**. Một hệ hay
nhắc sai sẽ dạy người trực bỏ qua mọi lời nhắc, và sau đó lời nhắc đúng cũng vô
dụng.
"""

from __future__ import annotations

import os
import uuid
from datetime import timedelta
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận + loại hẹn
from clinicai.events.catalogue import TRACH_NHIEM_DICH_VU, DichVuKhongLam
from clinicai.events.consumers.trach_nhiem import HEN_KIEM_LAI
from clinicai.events.emit import HE_THONG, emit_event
from clinicai.events.hen_gio import (
    HenDenHan,
    dang_ky_loai,
    hen,
    huy_hen,
    lam_mot_hen,
    thu_hoi_hen_treo,
)
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


async def _visit(conn: asyncpg.Connection) -> str:
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN test hẹn giờ', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"HG-{uuid.uuid4().hex[:10]}",
        loc,
    )
    return str(
        await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', now())"
            " RETURNING visit_id::text",
            CLINIC,
            pid,
        )
    )


async def test_chua_toi_gio_thi_chua_lam(pool: asyncpg.Pool) -> None:
    da_goi: list[str] = []

    async def ghi_nhan(conn: asyncpg.Connection, cai_hen: HenDenHan) -> bool:
        da_goi.append(cai_hen.id)
        return True

    loai = f"test.chua_toi.{uuid.uuid4().hex[:6]}"
    dang_ky_loai(loai, ghi_nhan)

    async with pool.acquire() as conn, conn.transaction():
        await hen(
            conn,
            clinic_id=CLINIC,
            loai=loai,
            sau=timedelta(hours=1),
            ve_cai_gi=str(uuid.uuid4()),
        )
    for _ in range(50):
        if not await lam_mot_hen(pool):
            break
    assert da_goi == []


async def test_toi_gio_thi_lam(pool: asyncpg.Pool) -> None:
    da_goi: list[str] = []

    async def ghi_nhan(conn: asyncpg.Connection, cai_hen: HenDenHan) -> bool:
        da_goi.append(cai_hen.chi_tiet.get("dau_hieu", ""))
        return True

    loai = f"test.toi_gio.{uuid.uuid4().hex[:6]}"
    dau_hieu = uuid.uuid4().hex
    dang_ky_loai(loai, ghi_nhan)

    async with pool.acquire() as conn, conn.transaction():
        ma = await hen(
            conn,
            clinic_id=CLINIC,
            loai=loai,
            sau=timedelta(seconds=-1),  # đã tới hạn
            ve_cai_gi=str(uuid.uuid4()),
            chi_tiet={"dau_hieu": dau_hieu},
        )
    assert ma is not None
    for _ in range(200):
        if not await lam_mot_hen(pool):
            break
    assert dau_hieu in da_goi

    dong = await pool.fetchrow(
        "SELECT trang_thai, ket_qua FROM hen_gio WHERE id = $1::uuid", ma
    )
    assert dong is not None
    assert dong["trang_thai"] == "XONG" and dong["ket_qua"] == "da_lam"


async def test_het_can_thi_khong_nhac(pool: asyncpg.Pool) -> None:
    """Người ta xử lý xong trước giờ hẹn — không được bắn lời nhắc sai."""
    loai = f"test.het_can.{uuid.uuid4().hex[:6]}"

    async def khong_con_can(conn: asyncpg.Connection, cai_hen: HenDenHan) -> bool:
        return False

    dang_ky_loai(loai, khong_con_can)
    async with pool.acquire() as conn, conn.transaction():
        ma = await hen(
            conn,
            clinic_id=CLINIC,
            loai=loai,
            sau=timedelta(seconds=-1),
            ve_cai_gi=str(uuid.uuid4()),
        )
    for _ in range(200):
        if not await lam_mot_hen(pool):
            break
    dong = await pool.fetchrow(
        "SELECT trang_thai, ket_qua FROM hen_gio WHERE id = $1::uuid", ma
    )
    assert dong is not None
    # "Hết cần" là một kết thúc bình thường, không phải lỗi.
    assert dong["trang_thai"] == "BO_QUA" and dong["ket_qua"] == "het_can"


async def test_hen_hai_lan_cho_mot_chuyen_chi_con_mot(pool: asyncpg.Pool) -> None:
    loai = f"test.trung.{uuid.uuid4().hex[:6]}"
    ve = str(uuid.uuid4())
    async with pool.acquire() as conn, conn.transaction():
        a = await hen(
            conn, clinic_id=CLINIC, loai=loai, sau=timedelta(hours=1), ve_cai_gi=ve
        )
        b = await hen(
            conn, clinic_id=CLINIC, loai=loai, sau=timedelta(hours=2), ve_cai_gi=ve
        )
    assert a is not None and b is None


async def test_xong_som_thi_go_hen(pool: asyncpg.Pool) -> None:
    loai = f"test.go.{uuid.uuid4().hex[:6]}"
    ve = str(uuid.uuid4())
    async with pool.acquire() as conn, conn.transaction():
        ma = await hen(
            conn, clinic_id=CLINIC, loai=loai, sau=timedelta(hours=1), ve_cai_gi=ve
        )
    async with pool.acquire() as conn, conn.transaction():
        await huy_hen(conn, clinic_id=CLINIC, loai=loai, ve_cai_gi=ve)
    dong = await pool.fetchval("SELECT trang_thai FROM hen_gio WHERE id = $1::uuid", ma)
    assert dong == "BO_QUA"


async def test_worker_chet_giua_chung_thi_thu_hoi_duoc(pool: asyncpg.Pool) -> None:
    loai = f"test.treo.{uuid.uuid4().hex[:6]}"
    async with pool.acquire() as conn, conn.transaction():
        ma = await hen(
            conn,
            clinic_id=CLINIC,
            loai=loai,
            sau=timedelta(hours=1),
            ve_cai_gi=str(uuid.uuid4()),
        )
    await pool.execute(
        "UPDATE hen_gio SET trang_thai = 'DANG_LAM',"
        " thue_den = now() - interval '1 minute' WHERE id = $1::uuid",
        ma,
    )
    assert await thu_hoi_hen_treo(pool) >= 1
    assert (
        await pool.fetchval("SELECT trang_thai FROM hen_gio WHERE id = $1::uuid", ma)
        == "CHO"
    )


async def test_viec_qua_han_thi_noi_len_dau_bang(pool: asyncpg.Pool) -> None:
    """Đường đi trọn vẹn: sự kiện → việc có hạn → tới hạn → ưu tiên cao nhất."""
    order_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        vid = await _visit(conn)
        async with conn.transaction():
            await emit_event(
                conn,
                ten="service.not_performed",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=DichVuKhongLam(
                    visit_id=vid,
                    service_order_id=order_id,
                    ly_do="EQUIPMENT_UNAVAILABLE_BEFORE_START",
                    execution_revision=1,
                    da_thu_tien=True,
                ),
                boi=HE_THONG,
            )
    for _ in range(500):
        if not await lam_mot_dong(pool, TRACH_NHIEM_DICH_VU):
            break

    viec = await pool.fetchrow(
        "SELECT id::text, priority, due_at FROM work_item"
        " WHERE service_order_id = $1::uuid",
        order_id,
    )
    assert viec is not None
    assert viec["due_at"] is not None, "Việc mở ra mà không có hạn thì vẫn dễ bị quên"
    assert viec["priority"] == "P1"

    # Kéo giờ hẹn về quá khứ để không phải chờ 4 tiếng.
    await pool.execute(
        "UPDATE hen_gio SET den_gio = now() - interval '1 minute'"
        " WHERE loai = $1 AND ve_cai_gi = $2::uuid",
        HEN_KIEM_LAI,
        viec["id"],
    )
    for _ in range(200):
        if not await lam_mot_hen(pool):
            break

    assert (
        await pool.fetchval(
            "SELECT priority FROM work_item WHERE id = $1::uuid", viec["id"]
        )
        == "P0"
    )
