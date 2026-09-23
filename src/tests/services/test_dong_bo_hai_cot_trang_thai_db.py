"""Hai cột trạng thái chỉ định khớp nhau ở Postgres (migration 20260924000011).

`execution_status` là nguồn thật; `exec_status` là bản chiếu cho màn cũ. Trigger
`service_order_dong_bo_trang_thai` kéo hai chiều — mọi lối ghi đều đi qua, kể cả
đối tác tự lấy mẫu (lối cũ chỉ ghi cột cũ, trước đây làm hành trình báo "chưa làm").
"""

from __future__ import annotations

import asyncpg
import pytest

from tests.services.test_xac_nhan_tep_ket_qua_db import (
    CLINIC_A,
    _tao_benh_nhan_va_visit,
    _tao_external_order,
    _tao_staff,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _chi_dinh_doi_moi(conn: asyncpg.Connection, *, doi_moi: bool = True) -> str:
    doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
    _pid, _aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
    oid = await _tao_external_order(conn, CLINIC_A, vid)
    await conn.execute(
        "UPDATE service_order SET exec_status = 'assigned',"
        "       selection_status = $2, routing_status = $3,"
        "       started_at = NULL, finished_at = NULL"
        " WHERE id = $1::uuid",
        oid,
        "SELECTED" if doi_moi else None,
        "ASSIGNED" if doi_moi else None,
    )
    return oid


async def _doc(conn: asyncpg.Connection, oid: str) -> asyncpg.Record:
    r = await conn.fetchrow(
        "SELECT exec_status, execution_status, execution_revision,"
        "       started_at, finished_at FROM service_order WHERE id = $1::uuid",
        oid,
    )
    assert r is not None
    return r


async def test_loi_cu_ghi_cot_cu_thi_cot_moi_theo(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Đối tác tự lấy mẫu (lối cũ) ghi `performed` → cột mới COMPLETED."""
    async with pool.acquire() as conn:
        oid = await _chi_dinh_doi_moi(conn)
        await conn.execute(
            "UPDATE service_order SET exec_status = 'performed' WHERE id = $1::uuid",
            oid,
        )
        r = await _doc(conn, oid)
    assert r["execution_status"] == "COMPLETED"
    assert r["execution_revision"] == 1


async def test_chi_dinh_doi_cu_giu_null(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        oid = await _chi_dinh_doi_moi(conn, doi_moi=False)
        await conn.execute(
            "UPDATE service_order SET exec_status = 'performed' WHERE id = $1::uuid",
            oid,
        )
        r = await _doc(conn, oid)
    assert r["execution_status"] is None


async def test_duong_moi_keo_cot_cu_va_ghi_gio(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        oid = await _chi_dinh_doi_moi(conn)
        await conn.execute(
            "UPDATE service_order SET execution_status = 'IN_PROGRESS'"
            " WHERE id = $1::uuid",
            oid,
        )
        r = await _doc(conn, oid)
        assert r["exec_status"] == "in_progress"
        assert r["started_at"] is not None and r["finished_at"] is None
        await conn.execute(
            "UPDATE service_order SET execution_status = 'COMPLETED'"
            " WHERE id = $1::uuid",
            oid,
        )
        r = await _doc(conn, oid)
    assert r["exec_status"] == "performed"
    assert r["finished_at"] is not None


async def test_khong_lam_duoc_khi_chua_co_phong_dong_ca_cot_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Trước đây cột cũ kẹt `authorized` → lượt không đóng, quầy thấy dòng mở."""
    async with pool.acquire() as conn:
        oid = await _chi_dinh_doi_moi(conn)
        await conn.execute(
            "UPDATE service_order SET exec_status = 'authorized', room_id = NULL,"
            "       routing_status = 'UNASSIGNED' WHERE id = $1::uuid",
            oid,
        )
        await conn.execute(
            "UPDATE service_order SET execution_status = 'NOT_PERFORMED',"
            "       not_performed_reason = 'Khách từ chối' WHERE id = $1::uuid",
            oid,
        )
        r = await _doc(conn, oid)
    assert r["exec_status"] == "not_performed"


async def test_lam_lai_tro_ve_hang_phong(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        oid = await _chi_dinh_doi_moi(conn)
        for tt in ("IN_PROGRESS", "INTERRUPTED"):
            await conn.execute(
                "UPDATE service_order SET execution_status = $2 WHERE id = $1::uuid",
                oid,
                tt,
            )
        r = await _doc(conn, oid)
    assert r["exec_status"] == "assigned"
