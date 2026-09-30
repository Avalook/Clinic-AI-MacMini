"""Đổi người trong ca (Tuyền 29/09/2026) — migration 20260929000001.

Kịch bản thật: Hà đứng Phòng siêu âm giữa ca phải về, trưởng ca xếp B vào thay.
B phải có NGAY trọn quyền của phòng (kể cả xếp phòng, xem lịch), Hà mất ngay,
lịch giữ vết, nhật ký ghi ai đổi — và trưởng ca làm được mà không cần lego
"Cài đặt phòng khám".
"""

from __future__ import annotations

import datetime as dt

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import cache
from clinicai.permissions.can import can
from clinicai.services.config_service import RosterService
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_luot_kham_service_db import KichBan, _nguoi
from tests.services.test_quyen_theo_lich_mo_db import _xep

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dong_lich(conn: asyncpg.Connection, staff_id: str) -> str:
    return str(
        await conn.fetchval(
            "SELECT id::text FROM work_roster WHERE staff_id = $1::uuid"
            " ORDER BY created_at DESC LIMIT 1",
            staff_id,
        )
    )


async def test_truong_ca_thay_nguoi_giua_ca(kb: KichBan) -> None:
    ha = kb.le_tan  # không lego phòng dịch vụ nào — quyền chỉ đến từ lịch
    async with kb.pool.acquire() as conn:
        b = await _nguoi(conn, kb.location_id, "CSKH")
        await ve_goi_mau_cu(conn, ha, b)  # gói lego cũ (mở full lego 30/09)
        await _xep(conn, ha.clinic_id, kb.phong_sa, ha)
        roster_id = await _dong_lich(conn, ha.staff_id)
        assert await can(conn, ha, "service.execute.start", phong_id=kb.phong_sa)
        # Hà vừa được hỏi quyền toàn phòng khám → câu "có" đang được nhớ.
        assert await can(conn, ha, "result.review.approve")
        assert not await can(conn, b, "service.execute.start", phong_id=kb.phong_sa)

    ket = await RosterService(kb.pool).thay_nguoi(
        roster_id=roster_id,
        staff_moi_id=b.staff_id,
        identity=kb.truong_ca,
        ly_do="Có việc đột xuất phải về",
    )
    assert ket["nguoi_moi_ten"] == b.full_name

    async with kb.pool.acquire() as conn:
        # B có ngay trọn quyền phòng + xếp phòng + xem lịch.
        assert await can(conn, b, "service.execute.start", phong_id=kb.phong_sa)
        assert await can(conn, b, "service.execute.complete", phong_id=kb.phong_sa)
        assert await can(conn, b, "result.review.approve")
        assert await can(conn, b, "service.routing.assign")
        assert await can(conn, b, "roster.view")
        # Hà mất ngay — kể cả quyền toàn phòng khám vừa được nhớ.
        assert not await can(conn, ha, "service.execute.start", phong_id=kb.phong_sa)
        assert not await can(conn, ha, "result.review.approve")
        # Vết + nhật ký.
        vet = await conn.fetchrow(
            "SELECT nguoi_cu_id::text, nguoi_moi_id::text, boi_staff_id::text, ly_do"
            " FROM work_roster_thay_nguoi WHERE roster_id = $1::uuid",
            roster_id,
        )
        assert vet is not None
        assert vet["nguoi_cu_id"] == ha.staff_id
        assert vet["nguoi_moi_id"] == b.staff_id
        assert vet["boi_staff_id"] == kb.truong_ca.staff_id
        assert vet["ly_do"] == "Có việc đột xuất phải về"
        assert await conn.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type ="
            " 'roster.shift_reassigned' AND aggregate_id = $1::uuid",
            roster_id,
        )

        hom_nay = await conn.fetchval(
            "SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
        )

    # Màn Lịch làm việc thấy vết và được bày khối đổi người.
    lich = await RosterService(kb.pool).lich_tuan(identity=kb.truong_ca, tuan=hom_nay)
    assert lich["doi_nguoi"] is True
    assert any(v["roster_id"] == roster_id for v in lich["thay_nguoi"])


async def test_khong_co_quyen_doi_nguoi_bi_chan(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        await ve_goi_mau_cu(conn, kb.le_tan)  # gói lego cũ (mở full lego 30/09)
        await _xep(conn, kb.dieu_duong.clinic_id, kb.phong_sa, kb.dieu_duong)
        roster_id = await _dong_lich(conn, kb.dieu_duong.staff_id)
    with pytest.raises(SafetyGateError):
        await RosterService(kb.pool).thay_nguoi(
            roster_id=roster_id, staff_moi_id=kb.thu_ky.staff_id, identity=kb.le_tan
        )


async def test_ca_da_qua_khong_doi_duoc(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        await _xep(conn, kb.dieu_duong.clinic_id, kb.phong_sa, kb.dieu_duong)
        roster_id = await _dong_lich(conn, kb.dieu_duong.staff_id)
        await conn.execute(
            "UPDATE work_roster SET work_date = work_date - 1 WHERE id = $1::uuid",
            roster_id,
        )
    with pytest.raises(ValidationError):
        await RosterService(kb.pool).thay_nguoi(
            roster_id=roster_id,
            staff_moi_id=kb.thu_ky.staff_id,
            identity=kb.truong_ca,
        )


async def test_kho_thuoc_khong_mo_quyen_ket_qua(kb: KichBan) -> None:
    """`DICHVU-` không còn ăn cả `DICHVU-THUOC`: đứng kho ≠ duyệt kết quả."""
    async with kb.pool.acquire() as conn:
        ai = await _nguoi(conn, kb.location_id, "CSKH")
        await ve_goi_mau_cu(conn, ai)  # gói lego cũ (mở full lego 30/09)
        kho = await conn.fetchval(
            "SELECT r.id::text FROM clinic_room r JOIN clinic_room_node n"
            " ON n.room_id = r.id WHERE r.clinic_id = $1::uuid"
            " AND n.node_code = 'DICHVU-THUOC' AND r.is_active LIMIT 1",
            ai.clinic_id,
        )
        if kho is None:
            pytest.skip("DB thử không có phòng kho thuốc")
        await _xep(conn, ai.clinic_id, kho, ai)
        assert not await can(conn, ai, "result.review.approve")
        assert not await can(conn, ai, "result.form.fill")


async def test_vi_tri_truong_ca_mo_dieu_phoi(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        ai = await _nguoi(conn, kb.location_id, "CSKH")
        await ve_goi_mau_cu(conn, ai)  # gói lego cũ (mở full lego 30/09)
        assert not await can(conn, ai, "dispatch.manage")
        hom_nay = await conn.fetchval(
            "SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
        )
        await conn.execute(
            "INSERT INTO work_roster (clinic_id, week_start, work_date, shift,"
            " station, staff_id, staff_name, status)"
            " VALUES ($1::uuid, $2, $3, 'FULL', 'DIEU_PHOI', $4::uuid, $5,"
            " 'APPROVED')",
            ai.clinic_id,
            hom_nay - dt.timedelta(days=hom_nay.weekday()),
            hom_nay,
            ai.staff_id,
            ai.full_name,
        )
        cache.quen(ai.clinic_id)
        assert await can(conn, ai, "dispatch.manage")
        assert await can(conn, ai, "roster.shift.swap")


async def test_quyen_moi_nam_trong_preset_truong_ca(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        assert await can(conn, kb.truong_ca, "roster.shift.swap")
        assert not await can(conn, kb.truong_ca, "config.clinic.manage")
