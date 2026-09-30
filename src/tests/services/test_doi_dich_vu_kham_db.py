"""Đổi dịch vụ khám ở menu ⋯ dòng lịch hẹn (V5, 30/09/2026) — trên Postgres thật.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55564/postgres \\
        .venv/bin/pytest src/tests/services/test_doi_dich_vu_kham_db.py

Trước check-in: chỉ đổi lịch (luật bác sĩ bắt buộc chạy lại). Sau check-in: đổi
cả lượt khi chưa vướng gì, rồi khối Hành trình xếp lại hàng chờ đầu tiên.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity
from clinicai.api.v1.routers.booking import (
    DoiDichVuKhamRequest,
    doi_dich_vu_kham_post,
    o_doi_dich_vu_kham,
)
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import HANH_TRINH
from clinicai.services.booking_service import BookingService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _hanh_trinh(pool: asyncpg.Pool) -> None:  # noqa: F811
    from tests.chay_nguoi_dua_tin import chay_het

    await chay_het(pool, HANH_TRINH)


async def _loai(pool: asyncpg.Pool, ten: str, *, qua_tu_van: bool = False) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active, qua_tu_van)"
            " VALUES ($1::uuid, $2, $3, true, $4) RETURNING id::text",
            CLINIC,
            f"DDV-{uuid.uuid4().hex[:8]}",
            ten,
            qua_tu_van,
        )
    )


async def _dung(pool: asyncpg.Pool, *, qua_tu_van: bool = False) -> dict[str, Any]:  # noqa: F811
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        ca: dict[str, Any] = {
            "loc": loc,
            "le_tan": await _nguoi(conn, loc, "RECEPTION"),
            "cskh": await _nguoi(conn, loc, "CSKH"),
            "bs": await _nguoi(conn, loc, "DOCTOR"),
        }
    ca["dv"] = await _loai(pool, "Khám cũ", qua_tu_van=qua_tu_van)
    ca["dv_moi"] = await _loai(pool, "Khám mới", qua_tu_van=not qua_tu_van)
    pid = await pool.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'Khách đổi dịch vụ', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"DDV-{uuid.uuid4().hex[:10]}",
        loc,
    )
    bd = datetime.now(UTC) + timedelta(minutes=30)
    ca["pid"] = pid
    ca["appt"] = str(
        await pool.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, doctor_id, status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
            " 'CONFIRMED') RETURNING id::text",
            CLINIC,
            pid,
            loc,
            ca["dv"],
            bd,
            bd + timedelta(minutes=15),
            ca["bs"].staff_id,
        )
    )
    return ca


async def _doi(
    pool: asyncpg.Pool,  # noqa: F811
    identity: StaffIdentity,
    appt: str,
    dv: str,
) -> dict[str, Any]:
    return await doi_dich_vu_kham_post(
        appointment_id=UUID(appt),
        body=DoiDichVuKhamRequest(service_type_id=UUID(dv)),
        identity=identity,
        pool=pool,
    )


async def _check_in(pool: asyncpg.Pool, ca: dict[str, Any]) -> str:  # noqa: F811
    await BookingService(pool).apply_action(
        appointment_id=ca["appt"], action="checkin", identity=ca["le_tan"]
    )
    await _hanh_trinh(pool)
    return str(
        await pool.fetchval(
            "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid",
            ca["appt"],
        )
    )


async def _hang(pool: asyncpg.Pool, visit: str) -> dict[str, str]:  # noqa: F811
    rows = await pool.fetch(
        "SELECT lane, status FROM queue_entry WHERE visit_id = $1::uuid"
        " AND status NOT IN ('left', 'cancelled', 'done')",
        visit,
    )
    return {r["lane"]: r["status"] for r in rows}


async def test_truoc_check_in_doi_lich_ghi_su_kien_va_lich_su(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    goi = await o_doi_dich_vu_kham(
        appointment_id=UUID(ca["appt"]), identity=ca["cskh"], pool=pool
    )
    assert goi["duoc_doi"] and not goi["da_check_in"]
    assert goi["dich_vu_hien_tai"]["id"] == ca["dv"]
    assert any(x["id"] == ca["dv_moi"] and not x["hien_tai"] for x in goi["lua_chon"])

    kq = await _doi(pool, ca["cskh"], ca["appt"], ca["dv_moi"])
    assert kq["doi"] and kq["dich_vu"] == "Khám mới" and not kq["da_check_in"]
    assert (
        await pool.fetchval(
            "SELECT service_type_id::text FROM appointment WHERE id = $1::uuid",
            ca["appt"],
        )
        == ca["dv_moi"]
    )
    su_kien = await pool.fetchrow(
        "SELECT payload FROM domain_event WHERE event_type ="
        " 'appointment.service_switched' AND aggregate_id = $1::uuid",
        ca["appt"],
    )
    assert su_kien is not None
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type ="
            " 'appointment.service_switched' AND aggregate_id = $1",
            ca["appt"],
        )
        == 1
    )

    # Chọn lại đúng dịch vụ đang có: không lỗi, không ghi thêm.
    lai = await _doi(pool, ca["cskh"], ca["appt"], ca["dv_moi"])
    assert lai["doi"] is False
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type ="
            " 'appointment.service_switched' AND aggregate_id = $1::uuid",
            ca["appt"],
        )
        == 1
    )


async def test_luat_bac_si_bat_buoc_chan_va_bao_trong_danh_sach(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        bs_khac = await _nguoi(conn, ca["loc"], "DOCTOR")
    await pool.execute(
        "INSERT INTO luat_bac_si_bat_buoc (clinic_id, service_type_id,"
        " required_staff_id, cach_tinh, chan_han, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, 'CHUA_TUNG', true, true)",
        CLINIC,
        ca["dv_moi"],
        bs_khac.staff_id,
    )
    goi = await o_doi_dich_vu_kham(
        appointment_id=UUID(ca["appt"]), identity=ca["le_tan"], pool=pool
    )
    [muc] = [x for x in goi["lua_chon"] if x["id"] == ca["dv_moi"]]
    assert muc["chan"] and "lần đầu" in (muc["ghi_chu"] or "")

    with pytest.raises(ConflictError, match="Đổi bác sĩ"):
        await _doi(pool, ca["le_tan"], ca["appt"], ca["dv_moi"])
    assert (
        await pool.fetchval(
            "SELECT service_type_id::text FROM appointment WHERE id = $1::uuid",
            ca["appt"],
        )
        == ca["dv"]
    )


async def test_sau_check_in_doi_ca_luot_va_xep_lai_hang_dau_tien(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    # Loại cũ qua tư vấn → khách đứng hàng TƯ VẤN.
    ca = await _dung(pool, qua_tu_van=True)
    visit = await _check_in(pool, ca)
    assert await _hang(pool, visit) == {"TU_VAN": "blocked"}

    kq = await _doi(pool, ca["le_tan"], ca["appt"], ca["dv_moi"])
    assert kq["da_check_in"]
    assert (
        await pool.fetchval(
            "SELECT service_type_id::text FROM visit WHERE visit_id = $1::uuid", visit
        )
        == ca["dv_moi"]
    )
    await _hanh_trinh(pool)
    # Loại mới không qua tư vấn → thẳng hàng bác sĩ chính; chỗ tư vấn đã huỷ.
    assert await _hang(pool, visit) == {"DOCTOR": "waiting"}
    assert (
        await pool.fetchval(
            "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid",
            visit,
        )
        == "PRIMARY"
    )

    # Đổi lại loại qua tư vấn → về hàng tư vấn (phiên tư vấn cũ mở lại).
    await _doi(pool, ca["le_tan"], ca["appt"], ca["dv"])
    await _hanh_trinh(pool)
    assert await _hang(pool, visit) == {"TU_VAN": "blocked"}
    assert (
        await pool.fetchval(
            "SELECT status FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'TU_VAN'",
            visit,
        )
        == "queued"
    )
    assert (
        await pool.fetchval(
            "SELECT status FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
        == "cancelled"
    )


@pytest.mark.parametrize("vuong", ["tick", "phieu", "phien"])
async def test_sau_check_in_vuong_thi_may_chu_noi_ro_ly_do(
    pool: asyncpg.Pool,  # noqa: F811
    vuong: str,
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca)
    if vuong == "tick":
        gia = await pool.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, active) VALUES ($1::uuid, $2, 'Phí khám thử', 'dich_vu',"
            " 100000, true)"
            " RETURNING id::text",
            CLINIC,
            f"PK-{uuid.uuid4().hex[:8]}",
        )
        await pool.execute(
            "INSERT INTO luot_phi_kham (clinic_id, visit_id, service_price_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid)",
            CLINIC,
            visit,
            gia,
        )
        cau = "dịch vụ khám con"
    elif vuong == "phieu":
        await pool.execute(
            "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version)"
            " SELECT clinic_id, $2::uuid, form_id, version FROM form_definition"
            " WHERE clinic_id = $1::uuid ORDER BY form_id LIMIT 1",
            CLINIC,
            visit,
        )
        cau = "phiếu khám"
    else:
        await pool.execute(
            "UPDATE consultation SET status = 'in_progress' WHERE visit_id = $1::uuid",
            visit,
        )
        cau = "bắt đầu khám"

    goi = await o_doi_dich_vu_kham(
        appointment_id=UUID(ca["appt"]), identity=ca["le_tan"], pool=pool
    )
    assert not goi["duoc_doi"] and cau in goi["ly_do_khong_doi"]
    with pytest.raises(ConflictError, match=cau):
        await _doi(pool, ca["le_tan"], ca["appt"], ca["dv_moi"])
    assert (
        await pool.fetchval(
            "SELECT service_type_id::text FROM visit WHERE visit_id = $1::uuid", visit
        )
        == ca["dv"]
    )


async def test_khong_co_quyen_nao_thi_chan(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    await pool.execute(
        "DELETE FROM capability_grant WHERE clinic_id = $1::uuid"
        " AND staff_id = $2::uuid"
        " AND capability IN ('booking.manage', 'reception.checkin.perform')",
        CLINIC,
        ca["bs"].staff_id,
    )
    with pytest.raises(SafetyGateError):
        await BookingService(pool).doi_dich_vu_kham(
            appointment_id=ca["appt"], service_type_id=ca["dv_moi"], identity=ca["bs"]
        )
