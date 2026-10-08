"""Hai cơ sở cùng node (08/10/2026, mở Hào Nam): phòng của lượt phải cùng cơ sở.

Trước đó `place_visit_at_first_station` và `move_visit_to_station` chọn/nhận
phòng theo node của CẢ phòng khám — khách Hào Nam check-in có thể bị đặt vào
phòng Kim Ngưu. Chốt nằm ở Postgres (migration 20261008100000).
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_ngay_kham_lo_hong_db import _co_so_khac
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _nhan_ban_phong_sang(conn: asyncpg.Connection, tu: str, sang: str) -> None:
    """Chép mọi phòng đang bật của cơ sở `tu` sang `sang`, sort NHỎ HƠN — để
    nếu SQL không lọc cơ sở thì nó chọn trúng phòng cơ sở kia."""
    phong = await conn.fetch(
        "SELECT id, node_code, sort FROM clinic_room"
        " WHERE clinic_id = $1::uuid AND location_id = $2::uuid AND is_active",
        CLINIC,
        tu,
    )
    for p in phong:
        moi = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3, $4, $5,"
            " true, true, $6) RETURNING id",
            CLINIC,
            sang,
            f"HN-{uuid.uuid4().hex[:8]}",
            "Phòng cơ sở kia",
            p["node_code"],
            (p["sort"] or 0) - 10_000,
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " SELECT clinic_id, $2::uuid, node_code FROM clinic_room_node"
            " WHERE room_id = $1::uuid ON CONFLICT DO NOTHING",
            p["id"],
            moi,
        )


async def test_check_in_vao_tram_dau_dung_co_so(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    khac = await _co_so_khac(pool, ca.loc)
    async with pool.acquire() as conn:
        await _nhan_ban_phong_sang(conn, ca.loc, khac)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    co_so_phong = await pool.fetchval(
        "SELECT r.location_id::text FROM visit v"
        " JOIN clinic_room r ON r.id = v.current_room_id WHERE v.visit_id = $1::uuid",
        visit,
    )
    assert co_so_phong in (None, ca.loc), "check-in không được đặt khách sang cơ sở kia"


async def test_phong_khac_co_so_bi_db_tu_choi(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    khac = await _co_so_khac(pool, ca.loc)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    async with pool.acquire() as conn:
        phong_khac = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3, 'Kia',"
            " 'LUOTKHAM-01', true, true, 1) RETURNING id",
            CLINIC,
            khac,
            f"HN-{uuid.uuid4().hex[:8]}",
        )
        with pytest.raises(asyncpg.RaiseError, match="cơ sở khác"):
            await conn.execute(
                "UPDATE visit SET current_room_id = $2::uuid WHERE visit_id = $1::uuid",
                visit,
                phong_khac,
            )
        with pytest.raises(asyncpg.RaiseError, match="cơ sở khác"):
            await conn.execute(
                "UPDATE work_item SET room_id = $2::uuid WHERE visit_id = $1::uuid",
                visit,
                phong_khac,
            )
        # Cùng cơ sở thì vẫn ghi được như cũ.
        phong_cung = await conn.fetchval(
            "SELECT id FROM clinic_room WHERE clinic_id = $1::uuid"
            " AND location_id = $2::uuid AND is_active ORDER BY sort LIMIT 1",
            CLINIC,
            ca.loc,
        )
        await conn.execute(
            "UPDATE visit SET current_room_id = $2::uuid WHERE visit_id = $1::uuid",
            visit,
            phong_cung,
        )


async def test_tv_chi_goi_khach_cua_co_so_minh(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Tuyền 08/10: "TV Hào Nam chỉ có số của Hào Nam" — Kim Ngưu tạm đóng."""
    from datetime import UTC, datetime, timedelta

    from clinicai.services.display_board_service import DisplayBoardService

    ca = await _dung(pool)
    khac = await _co_so_khac(pool, ca.loc)
    bd = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=45)
    hen: dict[str, str] = {}
    for loc in (ca.loc, khac):
        hen[loc] = str(
            await pool.fetchval(
                "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
                " service_type_id, slot_start, slot_end, doctor_id, status)"
                " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
                " 'CONFIRMED') RETURNING id::text",
                CLINIC,
                await _benh_nhan(pool, ca),
                loc,
                ca.loai_kham,
                bd,
                bd + timedelta(minutes=15),
                ca.bac_si.staff_id,
            )
        )
    tu, den = bd - timedelta(hours=1), bd + timedelta(hours=1)
    svc = DisplayBoardService(pool)
    # Bảng TV không mang id (ràng buộc ① — không định danh), nên so SỐ DÒNG với
    # số lịch hẹn của từng cơ sở trong khung giờ.
    dem = {
        loc: await pool.fetchval(
            "SELECT count(*) FROM appointment WHERE clinic_id = $1::uuid"
            " AND location_id = $2::uuid AND slot_start >= $3 AND slot_start < $4"
            " AND status <> ALL (ARRAY['CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'])",
            CLINIC,
            loc,
            tu,
            den,
        )
        for loc in (ca.loc, khac)
    }
    mot = await svc.board(clinic_id=CLINIC, start=tu, end=den, location_id=ca.loc)
    assert len(mot["items"]) == dem[ca.loc]
    # Không truyền cơ sở → như cũ (cả phòng khám) — gồm cả lịch cơ sở kia.
    tat_ca = await svc.board(clinic_id=CLINIC, start=tu, end=den)
    assert len(tat_ca["items"]) >= dem[ca.loc] + dem[khac] > len(mot["items"])
    assert hen  # hai lịch hẹn đã tạo
