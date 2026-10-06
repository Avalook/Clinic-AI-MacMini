"""Số booking cấp NGAY lúc đặt (luồng chuẩn bước 4, Tuyền chốt 23/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_so_booking_db.py

"Khi khách đặt online thì lập tức có 1 số thứ tự booking theo thời gian thực,
khi đến phòng khám thì số này được đứng cạnh số check-in của khách."
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from tests.services.test_phong_la_tai_nguyen_db import CLINIC, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _ngay_rieng(pool: asyncpg.Pool, so_ngay: int = 1) -> datetime:  # noqa: F811
    """Một ngày xa (tuần chưa công bố lịch trực → không có trần) mà `so_ngay`
    ngày liền từ đó CHƯA có lịch hẹn nào của CLINIC.

    Số booking đếm theo (phòng khám, ngày hẹn giờ VN) — một lịch có sẵn cùng
    ngày làm số bắt đầu từ 2. Ngày ngẫu nhiên thôi chưa đủ: các tệp test chạy
    cùng worker xdist dùng chung database, nhiều tệp cũng đặt lịch ở ngày xa
    ngẫu nhiên (vd test_quay_va_tu_van_2409_db đặt 09:00 giờ VN), DB chung
    chạy tay còn tích luỹ qua các lần — 06/10/2026 trùng ngày, đỏ ở CI máy.
    """
    for _ in range(50):
        ngay = datetime.now(UTC).replace(hour=2, minute=0, second=0, microsecond=0)
        ngay += timedelta(days=random.randint(400, 4000))
        if not await pool.fetchval(
            "SELECT EXISTS (SELECT 1 FROM appointment WHERE clinic_id = $1::uuid"
            " AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
            " BETWEEN ($2::timestamptz AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
            " AND ($2::timestamptz AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + $3::int)",
            CLINIC,
            ngay,
            so_ngay - 1,
        ):
            return ngay
    raise AssertionError("50 lần không tìm được ngày trống lịch hẹn")


async def _dat(pool: asyncpg.Pool, luc: datetime) -> str:  # noqa: F811
    async with pool.acquire() as conn:
        loc, dv = await conn.fetchrow(
            "SELECT (SELECT id FROM clinic_location WHERE clinic_id = $1::uuid"
            "        AND is_active ORDER BY created_at, id LIMIT 1),"
            "       (SELECT id FROM service_type WHERE clinic_id = $1::uuid"
            "        ORDER BY id LIMIT 1)",
            CLINIC,
        )
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN số booking', $3) RETURNING clinic_patient_id",
            CLINIC,
            f"SB-{uuid.uuid4().hex[:8]}",
            loc,
        )
        return str(
            await conn.fetchval(
                "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
                " service_type_id, slot_start, slot_end, status)"
                " VALUES ($1::uuid, $2, $3, $4, $5, $6, 'SCHEDULED') RETURNING id",
                CLINIC,
                pid,
                loc,
                dv,
                luc,
                luc + timedelta(minutes=15),
            )
        )


async def _so(pool: asyncpg.Pool, appt: str) -> int | None:  # noqa: F811
    v = await pool.fetchval(
        "SELECT so_booking FROM appointment WHERE id = $1::uuid", appt
    )
    return int(v) if v is not None else None


async def test_dat_lich_co_so_ngay_theo_thu_tu_dat(pool: asyncpg.Pool) -> None:  # noqa: F811
    ngay = await _ngay_rieng(pool)
    # Đặt khung MUỘN trước, khung SỚM sau: số theo thứ tự ĐẶT, không theo giờ hẹn.
    a = await _dat(pool, ngay + timedelta(hours=5))
    b = await _dat(pool, ngay + timedelta(hours=1))
    c = await _dat(pool, ngay + timedelta(hours=3))
    assert [await _so(pool, x) for x in (a, b, c)] == [1, 2, 3]


async def test_doi_gio_cung_ngay_giu_so_doi_sang_ngay_khac_nhan_so_moi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ngay = await _ngay_rieng(pool, so_ngay=2)  # dùng cả ngày hôm sau
    a = await _dat(pool, ngay + timedelta(hours=1))
    b = await _dat(pool, ngay + timedelta(hours=2))
    await pool.execute(
        "UPDATE appointment SET slot_start = slot_start + interval '3 hours',"
        " slot_end = slot_end + interval '3 hours' WHERE id = $1::uuid",
        a,
    )
    assert await _so(pool, a) == 1  # cùng ngày: giữ số

    ngay_khac = ngay + timedelta(days=1)
    c = await _dat(pool, ngay_khac + timedelta(hours=1))
    await pool.execute(
        "UPDATE appointment SET slot_start = $2, slot_end = $3 WHERE id = $1::uuid",
        b,
        ngay_khac + timedelta(hours=2),
        ngay_khac + timedelta(hours=2, minutes=15),
    )
    assert await _so(pool, c) == 1
    assert await _so(pool, b) == 2  # ngày mới: số tiếp theo của ngày ấy


async def test_huy_lich_giu_so_khong_cap_lai(pool: asyncpg.Pool) -> None:  # noqa: F811
    ngay = await _ngay_rieng(pool)
    a = await _dat(pool, ngay + timedelta(hours=1))
    await pool.execute(
        "UPDATE appointment SET status = 'CANCELLED', ly_do_huy_ma = 'BAO_KHI_XAC_NHAN'"
        " WHERE id = $1::uuid",
        a,
    )
    b = await _dat(pool, ngay + timedelta(hours=1))
    assert (await _so(pool, a), await _so(pool, b)) == (1, 2)
