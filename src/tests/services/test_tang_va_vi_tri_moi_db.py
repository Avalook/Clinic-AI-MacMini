"""Tầng là danh mục thật và vị trí mới chọn được toàn bộ nhân sự đang làm."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any, cast

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.api.v1.routers.identity import vi_tri_hom_nay
from clinicai.services.clinic_config_service import ClinicConfigService
from clinicai.services.clinic_floor_service import ClinicFloorService
from clinicai.services.config_service import MA_CA_KHAM_BAC_SI, RosterService
from clinicai.services.day_noi_service import DayNoiService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _quan_ly_va_co_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> tuple[StaffIdentity, str]:
    async with pool.acquire() as conn:
        location_id = await conn.fetchval(
            "SELECT id::text FROM clinic_location"
            " WHERE clinic_id = $1::uuid AND is_active"
            " ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        assert location_id is not None
        return await _nguoi(conn, location_id, "MANAGEMENT"), location_id


async def _node_code(pool: asyncpg.Pool) -> str:  # noqa: F811
    code = await pool.fetchval(
        "SELECT code FROM node_definition"
        " WHERE clinic_id = $1::uuid AND is_active ORDER BY code LIMIT 1",
        CLINIC,
    )
    assert code is not None
    return str(code)


async def test_tang_co_thu_tu_doi_ten_va_an_mem_an_toan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    identity, location_id = await _quan_ly_va_co_so(pool)
    room_service = ClinicConfigService(pool)
    floor_service = ClinicFloorService(pool)
    suffix = uuid.uuid4().hex[:6]

    floor_a = await floor_service.create(
        identity=identity,
        location_id=location_id,
        name=f"Tầng thử A {suffix}",
    )
    floor_b = await floor_service.create(
        identity=identity,
        location_id=location_id,
        name=f"Tầng thử B {suffix}",
    )
    node_code = await _node_code(pool)
    room = await room_service.create_room(
        identity=identity,
        location_id=location_id,
        name=f"Phòng thử tầng {suffix}",
        node_code=node_code,
        floor_id=floor_a["floor_id"],
    )

    try:
        assert (
            await pool.fetchval(
                "SELECT floor FROM clinic_room WHERE id = $1::uuid", room["room_id"]
            )
            == f"Tầng thử A {suffix}"
        )

        renamed = f"Tầng đã đổi {suffix}"
        await floor_service.rename(
            identity=identity,
            floor_id=floor_a["floor_id"],
            name=renamed,
        )
        assert (
            await pool.fetchval(
                "SELECT floor FROM clinic_room WHERE id = $1::uuid", room["room_id"]
            )
            == renamed
        )

        with pytest.raises(ValidationError, match="còn 1 phòng đang hoạt động"):
            await floor_service.set_active(
                identity=identity,
                floor_id=floor_a["floor_id"],
                is_active=False,
            )

        active_floor_ids = [
            row["id"]
            for row in await pool.fetch(
                "SELECT id::text FROM clinic_floor"
                " WHERE location_id = $1::uuid AND is_active"
                " ORDER BY sort_order, id",
                location_id,
            )
        ]
        requested_order = [
            floor_id
            for floor_id in active_floor_ids
            if floor_id not in {floor_a["floor_id"], floor_b["floor_id"]}
        ] + [floor_b["floor_id"], floor_a["floor_id"]]
        await floor_service.reorder(
            identity=identity,
            location_id=location_id,
            floor_ids=requested_order,
        )
        overview = await room_service.overview(identity=identity)
        location = next(
            item for item in overview["locations"] if item["location_id"] == location_id
        )
        managed = [
            floor
            for floor in location["floors"]
            if floor["floor_id"] in {floor_a["floor_id"], floor_b["floor_id"]}
        ]
        assert [floor["floor_id"] for floor in managed] == [
            floor_b["floor_id"],
            floor_a["floor_id"],
        ]
        assert managed[1]["floor"] == renamed
        assert managed[1]["rooms"][0]["room_id"] == room["room_id"]

        with pytest.raises(ValidationError, match="đủ mọi tầng"):
            await floor_service.reorder(
                identity=identity,
                location_id=location_id,
                floor_ids=[floor_a["floor_id"]],
            )
    finally:
        await room_service.set_room_active(
            identity=identity, room_id=room["room_id"], is_active=False
        )
        await floor_service.set_active(
            identity=identity, floor_id=floor_a["floor_id"], is_active=False
        )
        await floor_service.set_active(
            identity=identity, floor_id=floor_b["floor_id"], is_active=False
        )


async def test_vi_tri_moi_mo_cho_moi_vai_dang_hoat_dong_tru_display(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    identity, _ = await _quan_ly_va_co_so(pool)
    service = DayNoiService(pool)
    created = await service.tao_vi_tri(
        identity=identity,
        ten=f"Vị trí mở đủ vai {uuid.uuid4().hex[:6]}",
        nhom_nghe="CHUNG",
    )
    station = await pool.fetchval(
        "SELECT code FROM vi_tri_lam_viec WHERE id = $1::uuid", created["id"]
    )
    expected = set(
        await pool.fetch(
            "SELECT DISTINCT s.primary_department AS role"
            " FROM clinic_membership m JOIN staff s ON s.id = m.staff_id"
            " WHERE m.clinic_id = $1::uuid AND m.is_active AND s.is_active"
            "   AND s.primary_department <> 'DISPLAY'",
            CLINIC,
        )
    )
    expected_roles = {row["role"] for row in expected}
    actual_roles = set(
        await pool.fetch(
            "SELECT vai FROM vai_duoc_vao_tram"
            " WHERE clinic_id = $1::uuid AND tram_ma = $2 AND is_active",
            CLINIC,
            station,
        )
    )
    assert {row["vai"] for row in actual_roles} == expected_roles


async def test_lich_tuan_khong_tra_nhan_su_da_roi_phong_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    identity, location_id = await _quan_ly_va_co_so(pool)
    async with pool.acquire() as conn:
        staff_id = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id,"
            " is_active) VALUES ($1, 'RECEPTION', $2::uuid, true) RETURNING id::text",
            f"Đã rời phòng khám {uuid.uuid4().hex[:6]}",
            location_id,
        )
        await conn.execute(
            "UPDATE clinic_membership SET is_active = false"
            " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid",
            CLINIC,
            staff_id,
        )

    result = await RosterService(pool).lich_tuan(identity=identity, tuan=date.today())
    assert staff_id not in {row["id"] for row in result["nhan_su"]}


async def test_khong_an_vi_tri_khi_con_ca_hom_nay_hoac_tuong_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    identity, _ = await _quan_ly_va_co_so(pool)
    service = DayNoiService(pool)
    created = await service.tao_vi_tri(
        identity=identity,
        ten=f"Vị trí còn ca {uuid.uuid4().hex[:6]}",
        nhom_nghe="CHUNG",
    )
    station = await pool.fetchval(
        "SELECT code FROM vi_tri_lam_viec WHERE id = $1::uuid", created["id"]
    )
    today = date.today()
    roster_id = await pool.fetchval(
        "INSERT INTO work_roster"
        " (clinic_id, week_start, work_date, shift, station, staff_id,"
        " staff_name, status)"
        " VALUES ($1::uuid, $2, $3, 'FULL', $4, $5::uuid, $6, 'APPROVED')"
        " RETURNING id::text",
        CLINIC,
        today - timedelta(days=today.weekday()),
        today,
        station,
        identity.staff_id,
        identity.full_name,
    )
    try:
        with pytest.raises(ValidationError, match="còn 1 ca hôm nay hoặc tương lai"):
            await service.sua_vi_tri(
                identity=identity,
                vi_tri_id=created["id"],
                is_active=False,
            )
    finally:
        await pool.execute("DELETE FROM work_roster WHERE id = $1::uuid", roster_id)
        await service.sua_vi_tri(
            identity=identity,
            vi_tri_id=created["id"],
            is_active=False,
        )


async def test_khong_them_ca_vao_vi_tri_da_ngung_su_dung(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    identity, _ = await _quan_ly_va_co_so(pool)
    station_service = DayNoiService(pool)
    created = await station_service.tao_vi_tri(
        identity=identity,
        ten=f"Vị trí đã tắt {uuid.uuid4().hex[:6]}",
        nhom_nghe="CHUNG",
    )
    station = await pool.fetchval(
        "SELECT code FROM vi_tri_lam_viec WHERE id = $1::uuid", created["id"]
    )
    await station_service.sua_vi_tri(
        identity=identity, vi_tri_id=created["id"], is_active=False
    )
    with pytest.raises(ValidationError, match="đã ngừng sử dụng"):
        await RosterService(pool).add_shift(
            work_date=date.today() + timedelta(days=1),
            station=station,
            shift="SANG",
            identity=identity,
        )


async def test_vi_tri_bac_si_that_da_tat_khong_duoc_nham_la_cot_lich_ao(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    identity, _ = await _quan_ly_va_co_so(pool)
    real_codes = sorted(MA_CA_KHAM_BAC_SI - {"LICH_KHAM"})
    row = await pool.fetchrow(
        "SELECT id::text, code, is_active FROM vi_tri_lam_viec"
        " WHERE clinic_id = $1::uuid AND code = ANY($2::text[]) LIMIT 1",
        CLINIC,
        real_codes,
    )
    assert row is not None, "seed test phải có ít nhất một vị trí bác sĩ thật"
    await pool.execute(
        "UPDATE vi_tri_lam_viec SET is_active = false WHERE id = $1::uuid", row["id"]
    )
    try:
        with pytest.raises(ValidationError, match="đã ngừng sử dụng"):
            await RosterService(pool).add_shift(
                work_date=date.today() + timedelta(days=1),
                station=row["code"],
                shift="SANG",
                identity=identity,
            )
    finally:
        await pool.execute(
            "UPDATE vi_tri_lam_viec SET is_active = $2 WHERE id = $1::uuid",
            row["id"],
            row["is_active"],
        )


async def test_phong_khong_bat_duoc_trong_tang_da_tat_va_tang_bat_lai_xep_cuoi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    identity, location_id = await _quan_ly_va_co_so(pool)
    floor_service = ClinicFloorService(pool)
    room_service = ClinicConfigService(pool)
    suffix = uuid.uuid4().hex[:6]
    floor = await floor_service.create(
        identity=identity,
        location_id=location_id,
        name=f"Tầng bật lại {suffix}",
    )
    room = await room_service.create_room(
        identity=identity,
        location_id=location_id,
        name=f"Phòng bật lại {suffix}",
        node_code=await _node_code(pool),
        floor_id=floor["floor_id"],
    )
    await room_service.set_room_active(
        identity=identity, room_id=room["room_id"], is_active=False
    )
    await floor_service.set_active(
        identity=identity, floor_id=floor["floor_id"], is_active=False
    )
    with pytest.raises(ValidationError, match="bật lại tầng trước"):
        await room_service.set_room_active(
            identity=identity, room_id=room["room_id"], is_active=True
        )
    max_before = await pool.fetchval(
        "SELECT coalesce(max(sort_order), 0) FROM clinic_floor"
        " WHERE location_id = $1::uuid AND is_active",
        location_id,
    )
    await floor_service.set_active(
        identity=identity, floor_id=floor["floor_id"], is_active=True
    )
    sort_after = await pool.fetchval(
        "SELECT sort_order FROM clinic_floor WHERE id = $1::uuid", floor["floor_id"]
    )
    assert sort_after > max_before
    await room_service.set_room_active(
        identity=identity, room_id=room["room_id"], is_active=True
    )
    await room_service.set_room_active(
        identity=identity, room_id=room["room_id"], is_active=False
    )
    await floor_service.set_active(
        identity=identity, floor_id=floor["floor_id"], is_active=False
    )


async def test_lich_lam_viec_sap_theo_thu_tu_tang_da_cau_hinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    identity, location_id = await _quan_ly_va_co_so(pool)
    floor_service = ClinicFloorService(pool)
    room_service = ClinicConfigService(pool)
    station_service = DayNoiService(pool)
    suffix = uuid.uuid4().hex[:6]
    floor_a = await floor_service.create(
        identity=identity, location_id=location_id, name=f"Tầng A lịch {suffix}"
    )
    floor_b = await floor_service.create(
        identity=identity, location_id=location_id, name=f"Tầng B lịch {suffix}"
    )
    node_code = await _node_code(pool)
    room_a = await room_service.create_room(
        identity=identity,
        location_id=location_id,
        name=f"Phòng A lịch {suffix}",
        node_code=node_code,
        floor_id=floor_a["floor_id"],
    )
    room_b = await room_service.create_room(
        identity=identity,
        location_id=location_id,
        name=f"Phòng B lịch {suffix}",
        node_code=node_code,
        floor_id=floor_b["floor_id"],
    )
    station_a = await station_service.tao_vi_tri(
        identity=identity,
        ten=f"Vị trí A lịch {suffix}",
        nhom_nghe="CHUNG",
        room_id=room_a["room_id"],
    )
    station_b = await station_service.tao_vi_tri(
        identity=identity,
        ten=f"Vị trí B lịch {suffix}",
        nhom_nghe="CHUNG",
        room_id=room_b["room_id"],
    )
    active_ids = [
        row["id"]
        for row in await pool.fetch(
            "SELECT id::text FROM clinic_floor"
            " WHERE location_id = $1::uuid AND is_active ORDER BY sort_order, id",
            location_id,
        )
    ]
    requested = [
        floor_id
        for floor_id in active_ids
        if floor_id not in {floor_a["floor_id"], floor_b["floor_id"]}
    ] + [floor_b["floor_id"], floor_a["floor_id"]]
    try:
        await floor_service.reorder(
            identity=identity, location_id=location_id, floor_ids=requested
        )
        payload = await vi_tri_hom_nay(identity=identity, pool=pool)
        catalog = cast(list[dict[str, Any]], payload["danh_muc"])
        codes = [item["code"] for item in catalog]
        code_a = await pool.fetchval(
            "SELECT code FROM vi_tri_lam_viec WHERE id = $1::uuid", station_a["id"]
        )
        code_b = await pool.fetchval(
            "SELECT code FROM vi_tri_lam_viec WHERE id = $1::uuid", station_b["id"]
        )
        assert codes.index(code_b) < codes.index(code_a)
    finally:
        for station in (station_a, station_b):
            await station_service.sua_vi_tri(
                identity=identity, vi_tri_id=station["id"], is_active=False
            )
        for room in (room_a, room_b):
            await room_service.set_room_active(
                identity=identity, room_id=room["room_id"], is_active=False
            )
        for floor in (floor_a, floor_b):
            await floor_service.set_active(
                identity=identity, floor_id=floor["floor_id"], is_active=False
            )
