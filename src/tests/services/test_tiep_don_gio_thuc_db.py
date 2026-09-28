"""Hàng chờ lễ tân xếp theo GIỜ VÀO HÀNG THẬT, không theo khung giờ đặt.

Tuyền 29/09/2026: "lễ tân đặt lịch cho khách A vào khung 18:00–18:15, khách A
tự động check-in và được xếp ĐẦU những người 18:00–18:15, trong khi đúng ra
phải theo thời gian thực."

Gốc: danh sách tiếp đón (`tiep_don_service.dung_dong`) lấy mốc xếp = giờ
check-in CHỈ cho khách vãng lai, còn khách có hẹn thì lấy GIỜ HẸN. Nên khách
vãng lai lễ tân vừa tạo (tự check-in) nhảy lên trước những người có hẹn cùng
khung đã đến và ngồi chờ từ trước; ngược lại người có hẹn đến muộn hơn A vẫn
đứng trước A. Bảng gọi số (`/queue`, `queue_order`) thì từ 15/09 đã xếp mọi
người theo giờ check-in — hai màn nói hai thứ tự.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55560/postgres \\
        .venv/bin/pytest src/tests/services/test_tiep_don_gio_thuc_db.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.api.v1.routers.queue import get_queue
from clinicai.services.tiep_don_service import TiepDonService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

VN = timezone(timedelta(hours=7))


def _ngay_rieng() -> date:
    """Một ngày xa, riêng cho mỗi lần chạy — không lẫn lịch của test khác."""
    return date(2031, 1, 1) + timedelta(days=uuid.uuid4().int % 3000)


def _luc(ngay: date, gio: int, phut: int) -> datetime:
    return datetime(ngay.year, ngay.month, ngay.day, gio, phut, tzinfo=VN)


async def _khach(
    conn: asyncpg.Connection,
    loc: str,
    ten: str,
    *,
    kenh: str,
    hen: datetime,
    check_in: datetime | None,
) -> str:
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, $3, $4::uuid) RETURNING clinic_patient_id::text",
        CLINIC,
        f"GT-{uuid.uuid4().hex[:8]}",
        ten,
        loc,
    )
    appt = str(
        await conn.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " slot_start, slot_end, status, booking_channel, is_walkin,"
            " service_type_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7,"
            " upper($7) = 'WALK_IN',"
            " (SELECT id FROM service_type WHERE clinic_id = $1::uuid"
            "  AND is_active ORDER BY code LIMIT 1))"
            " RETURNING id::text",
            CLINIC,
            pid,
            loc,
            hen,
            hen + timedelta(minutes=15),
            "CHECKED_IN" if check_in else "CONFIRMED",
            kenh,
        )
    )
    if check_in is not None:
        await conn.execute(
            "INSERT INTO visit (clinic_id, clinic_patient_id, appointment_id,"
            " status, checked_in_at, location_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 'OPEN', $4, $5::uuid)",
            CLINIC,
            pid,
            appt,
            check_in,
            loc,
        )
    return appt


async def _le_tan(pool: asyncpg.Pool) -> tuple[str, StaffIdentity]:  # noqa: F811
    async with pool.acquire() as conn:
        loc = str(
            await conn.fetchval(
                "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
                " AND is_active ORDER BY created_at, id LIMIT 1",
                CLINIC,
            )
        )
        return loc, await _nguoi(conn, loc, "RECEPTION")


def _thu_tu_tiep_don(goi: dict[str, object], ids: set[str]) -> list[str]:
    buoi = goi["buoi"]
    assert isinstance(buoi, list)
    return [
        d["appointment_id"]
        for b in buoi
        for d in b["dong"]
        if d["appointment_id"] in ids
    ]


async def _thu_tu_goi_so(
    pool: asyncpg.Pool,  # noqa: F811
    ngay: date,
    le_tan: StaffIdentity,
    ids: set[str],
) -> list[str]:
    kq = await get_queue(date=ngay, identity=le_tan, pool=pool)
    rows = kq["rows"]
    assert isinstance(rows, list)
    return [r["id"] for r in rows if r["id"] in ids]


async def test_vang_lai_le_tan_tao_sau_dung_sau_nguoi_da_den(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Kịch bản Tuyền: B hẹn 18:00 check-in 17:55; 18:05 lễ tân tạo A khung
    18:00–18:15 (vãng lai, tự check-in); C hẹn 18:00 nhưng 18:10 mới tới.
    Thứ tự thật: B → A → C, ở CẢ danh sách tiếp đón lẫn bảng gọi số."""
    ngay = _ngay_rieng()
    loc, le_tan = await _le_tan(pool)
    async with pool.acquire() as conn:
        b = await _khach(
            conn,
            loc,
            "Chị B",
            kenh="HOTLINE",
            hen=_luc(ngay, 18, 0),
            check_in=_luc(ngay, 17, 55),
        )
        a = await _khach(
            conn,
            loc,
            "Chị A",
            kenh="WALK_IN",
            hen=_luc(ngay, 18, 0),
            check_in=_luc(ngay, 18, 5),
        )
        c = await _khach(
            conn,
            loc,
            "Chị C",
            kenh="ONLINE",
            hen=_luc(ngay, 18, 0),
            check_in=_luc(ngay, 18, 10),
        )
    ids = {a, b, c}
    goi = await TiepDonService(pool).hom_nay(
        identity=le_tan, ngay=ngay, bay_gio=_luc(ngay, 18, 12)
    )
    assert _thu_tu_tiep_don(goi, ids) == [b, a, c]
    assert await _thu_tu_goi_so(pool, ngay, le_tan, ids) == [b, a, c]


async def test_vang_lai_check_in_truoc_khung_khong_vuot_nguoi_den_truoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Đúng dáng lỗi thấy trên màn: B hẹn 18:00 đã ngồi chờ từ 17:40; 17:50 lễ
    tân tạo A vào khung 18:00 → A tự check-in. Bản cũ xếp A (mốc 17:50) lên
    ĐẦU khung 18:00, trước B (mốc = giờ hẹn 18:00). A phải đứng SAU B.
    Người có hẹn CHƯA tới (D) vẫn đứng theo giờ hẹn."""
    ngay = _ngay_rieng()
    loc, le_tan = await _le_tan(pool)
    async with pool.acquire() as conn:
        b = await _khach(
            conn,
            loc,
            "Chị B",
            kenh="HOTLINE",
            hen=_luc(ngay, 18, 0),
            check_in=_luc(ngay, 17, 40),
        )
        a = await _khach(
            conn,
            loc,
            "Chị A",
            kenh="WALK_IN",
            hen=_luc(ngay, 18, 0),
            check_in=_luc(ngay, 17, 50),
        )
        d = await _khach(
            conn,
            loc,
            "Chị D",
            kenh="ONLINE",
            hen=_luc(ngay, 18, 15),
            check_in=None,
        )
    goi = await TiepDonService(pool).hom_nay(
        identity=le_tan, ngay=ngay, bay_gio=_luc(ngay, 17, 52)
    )
    assert _thu_tu_tiep_don(goi, {a, b, d}) == [b, a, d]
    assert await _thu_tu_goi_so(pool, ngay, le_tan, {a, b}) == [b, a]
