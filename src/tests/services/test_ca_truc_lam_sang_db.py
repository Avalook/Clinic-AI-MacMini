"""Cửa ca trực lâm sàng trên Postgres thật — bốn ca nghiệm thu phần A."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio

from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import PhienKhamBatDau
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.ca_truc import doi_dung_ca
from clinicai.services.ngoai_le_ca_truc_service import NgoaiLeCaTrucService
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _vi_tri(
    conn: Any, room_id: str, nhom: str, lan: int | None, sort: int
) -> str:
    ma = f"VT-CA-{uuid.uuid4().hex[:8]}"
    await conn.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, nhom_nghe, room_id,"
        " lan, sort) VALUES ($1::uuid, $2, $2, $3, $4::uuid, $5, $6)",
        CLINIC,
        ma,
        nhom,
        room_id,
        lan,
        sort,
    )
    return ma


async def _truc(conn: Any, ma: str, staff_id: str, ca: str = "FULL") -> None:
    await conn.execute(
        "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
        " staff_id, staff_name, status)"
        " SELECT $1::uuid, d - (extract(isodow FROM d)::int - 1), d, $4, $2,"
        " $3::uuid, 'Test ca truc', 'APPROVED'"
        " FROM (SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d) x",
        CLINIC,
        ma,
        staff_id,
        ca,
    )


async def _noi_tai_khoan(conn: Any, identity: Any) -> None:
    await conn.execute(
        "INSERT INTO auth.users (id) VALUES ($1::uuid) ON CONFLICT DO NOTHING",
        identity.auth_user_id,
    )
    await conn.execute(
        "UPDATE staff SET auth_user_id=$2::uuid WHERE id=$1::uuid",
        identity.staff_id,
        identity.auth_user_id,
    )


@pytest_asyncio.fixture
async def ca(pool: Any) -> dict[str, Any]:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        room = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " floor, is_active, accepting, sort) VALUES ($1::uuid, $2::uuid,"
            " $3, $3, 'KHAM-PHUKHOA', '1', true, true, 999) RETURNING id::text",
            CLINIC,
            loc,
            f"P-CA-{uuid.uuid4().hex[:7]}",
        )
        bs = await _nguoi(conn, loc, "DOCTOR")
        bs_2 = await _nguoi(conn, loc, "DOCTOR")
        thu_ky = await _nguoi(conn, loc, "TKYK")
        khong_ca = await _nguoi(conn, loc, "TKYK")
        quan_ly = await _nguoi(conn, loc, "MANAGEMENT")
        for ai in (bs, bs_2, thu_ky, khong_ca, quan_ly):
            await _noi_tai_khoan(conn, ai)
        vt_bs = await _vi_tri(conn, room, "BAC_SI", 1, 1)
        vt_bs_2 = await _vi_tri(conn, room, "BAC_SI", 2, 2)
        vt_tk = await _vi_tri(conn, room, "DIEU_DUONG", 1, 3)
        await _truc(conn, vt_bs, bs.staff_id)
        await _truc(conn, vt_bs_2, bs_2.staff_id)
        await _truc(conn, vt_tk, thu_ky.staff_id)
    return {
        "pool": pool,
        "bs": bs,
        "thu_ky": thu_ky,
        "khong_ca": khong_ca,
        "quan_ly": quan_ly,
    }


async def test_khong_co_ca_bi_chan_bang_cau_tieng_viet(ca: dict[str, Any]) -> None:
    async with ca["pool"].acquire() as conn:
        with pytest.raises(SafetyGateError, match="không có ca trực hôm nay"):
            async with doi_dung_ca(conn, ca["khong_ca"], ca["bs"].staff_id):
                pass


async def test_thu_ky_cung_ca_cung_lan_lam_duoc(ca: dict[str, Any]) -> None:
    async with ca["pool"].acquire() as conn:
        async with doi_dung_ca(conn, ca["thu_ky"], ca["bs"].staff_id) as bac_si:
            assert bac_si == ca["bs"].staff_id


async def test_quan_ly_mo_ngoai_le_co_ly_do_thi_lam_duoc(ca: dict[str, Any]) -> None:
    svc = NgoaiLeCaTrucService(ca["pool"])
    mo = await svc.mo(
        staff_id=ca["khong_ca"].staff_id,
        bac_si_id=ca["bs"].staff_id,
        ngay=None,
        ly_do="Bổ sung người hỗ trợ ca đột xuất",
        identity=ca["quan_ly"],
    )
    assert mo["ly_do"] == "Bổ sung người hỗ trợ ca đột xuất"
    async with ca["pool"].acquire() as conn:
        async with doi_dung_ca(conn, ca["khong_ca"], ca["bs"].staff_id):
            pass


async def test_domain_event_ghi_dung_on_behalf_of(ca: dict[str, Any]) -> None:
    consultation_id = str(uuid.uuid4())
    visit_id = str(uuid.uuid4())
    async with ca["pool"].acquire() as conn, conn.transaction():
        async with doi_dung_ca(conn, ca["thu_ky"], ca["bs"].staff_id):
            await emit_event(
                conn,
                ten="consultation.started",
                clinic_id=CLINIC,
                aggregate_id=consultation_id,
                aggregate_version=1,
                correlation_id=visit_id,
                payload=PhienKhamBatDau(
                    visit_id=visit_id,
                    consultation_id=consultation_id,
                    loai="PRIMARY",
                ),
                boi=nguoi(ca["thu_ky"]),
            )
        row = await conn.fetchrow(
            "SELECT actor_staff_id::text AS actor, on_behalf_of::text AS behalf"
            " FROM domain_event WHERE aggregate_id=$1::uuid",
            consultation_id,
        )
    assert (row["actor"], row["behalf"]) == (
        ca["thu_ky"].staff_id,
        ca["bs"].staff_id,
    )
