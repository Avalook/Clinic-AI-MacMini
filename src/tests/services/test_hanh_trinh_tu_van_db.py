"""Khối HÀNH TRÌNH, nhóm 1 — dây H1/H3 (docs/BAN-DO-DAY-NOI-LEGO.md "Bản chốt 24/09").

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_hanh_trinh_tu_van_db.py

Chị Lan check-in khám loại "qua tư vấn": điều dưỡng đo trước → hàng tư vấn (hàng
chung) → tư vấn xong → hàng bác sĩ chính. Bác sĩ chính thấy chị "sắp tới" nhưng
chưa gọi được. Mọi bước xếp hàng do khối Hành trình NGHE sự kiện rồi làm — không
lệnh ghi nào gọi thẳng.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events import worker as nguoi_dua_tin
from clinicai.events.catalogue import HANH_TRINH
from clinicai.events.consumers.hanh_trinh import xu_ly_hanh_trinh
from clinicai.services.booking_service import BookingService
from clinicai.services.luot_kham_service import LuotKhamService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@dataclasses.dataclass
class Lan:
    appt: str
    visit: str
    loc: str
    le_tan: StaffIdentity
    bac_si: StaffIdentity


async def _hanh_trinh(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Người đưa tin chạy một vòng cho khối Hành trình (ở máy thật là worker)."""
    while await nguoi_dua_tin.lam_mot_dong(pool, HANH_TRINH):
        pass


async def _check_in(pool: asyncpg.Pool, *, qua_tu_van: bool) -> Lan:  # noqa: F811
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        le_tan = await _nguoi(conn, loc, "RECEPTION")
        bac_si = await _nguoi(conn, loc, "DOCTOR")
        loai = await conn.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active, qua_tu_van)"
            " VALUES ($1::uuid, $2, 'Khám thử tư vấn', true, $3) RETURNING id::text",
            CLINIC,
            f"TV-{uuid.uuid4().hex[:8]}",
            qua_tu_van,
        )
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'Chị Lan', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"LAN-{uuid.uuid4().hex[:8]}",
            loc,
        )
        bd = datetime.now(UTC) + timedelta(minutes=30)
        appt = await conn.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, doctor_id, status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
            " 'CONFIRMED') RETURNING id::text",
            CLINIC,
            pid,
            loc,
            loai,
            bd,
            bd + timedelta(minutes=15),
            bac_si.staff_id,
        )
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=le_tan
    )
    visit = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    return Lan(str(appt), str(visit), str(loc), le_tan, bac_si)


async def _hang(pool: asyncpg.Pool, visit: str) -> dict[str, str]:  # noqa: F811
    rows = await pool.fetch(
        "SELECT lane, status FROM queue_entry WHERE visit_id = $1::uuid"
        " AND status NOT IN ('left', 'cancelled')",
        visit,
    )
    return {r["lane"]: r["status"] for r in rows}


async def _duong_di(pool: asyncpg.Pool, visit: str) -> str | None:  # noqa: F811
    v = await pool.fetchval(
        "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid", visit
    )
    return str(v) if v is not None else None


async def _phien_tu_van(pool: asyncpg.Pool, visit: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'TU_VAN'",
            visit,
        )
    )


async def _do_sinh_hieu(pool: asyncpg.Pool, lan: Lan) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, lan.loc, "NURSE_ULTRASOUND")
    svc = LuotKhamService(pool)
    await svc.bat_dau_do_sinh_hieu(visit_id=lan.visit, identity=dd)
    await svc.record_vitals(
        visit_id=lan.visit, raw={"systolic": 118, "diastolic": 76}, identity=dd
    )


async def test_h1_check_in_qua_tu_van_cho_do_sinh_hieu_truoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    lan = await _check_in(pool, qua_tu_van=True)
    # Chưa chạy khối Hành trình: check-in KHÔNG tự xếp (không gọi thẳng).
    assert await _hang(pool, lan.visit) == {}
    await _hanh_trinh(pool)
    assert await _duong_di(pool, lan.visit) == "TU_VAN"
    assert await _hang(pool, lan.visit) == {"TU_VAN": "blocked"}  # chờ đo

    # Bác sĩ chính thấy chị "sắp tới", chưa có chỗ chờ ở hàng bác sĩ.
    bang = await LuotKhamService(pool).hang_cho(identity=lan.bac_si, room_id=None)
    [sap] = [x for x in bang["sap_toi"] if x["visit_id"] == lan.visit]
    assert sap["dang_o"] == "chờ đo sinh hiệu"
    assert not [x for x in bang["hang_cho"] if x["visit_id"] == lan.visit]

    await _do_sinh_hieu(pool, lan)
    await _hanh_trinh(pool)
    assert await _hang(pool, lan.visit) == {"TU_VAN": "waiting"}
    bang = await LuotKhamService(pool).hang_cho(identity=lan.bac_si, room_id=None)
    [sap] = [x for x in bang["sap_toi"] if x["visit_id"] == lan.visit]
    assert sap["dang_o"] == "chờ tư vấn"

    # Hàng tư vấn là hàng CHUNG: một bác sĩ khác mở màn tư vấn cũng thấy.
    async with pool.acquire() as conn:
        bs_tu_van = await _nguoi(conn, lan.loc, "DOCTOR")
    tv = await LuotKhamService(pool).hang_cho(
        identity=bs_tu_van, room_id=None, tu_van=True
    )
    assert any(
        x["visit_id"] == lan.visit and x["loai"] == "TU_VAN" for x in tv["hang_cho"]
    )


async def test_h3_tu_van_xong_vao_hang_bac_si_chinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    lan = await _check_in(pool, qua_tu_van=True)
    await _hanh_trinh(pool)
    await _do_sinh_hieu(pool, lan)
    await _hanh_trinh(pool)
    async with pool.acquire() as conn:
        bs_tu_van = await _nguoi(conn, lan.loc, "DOCTOR")
    svc = LuotKhamService(pool)
    tv = await _phien_tu_van(pool, lan.visit)
    await svc.start_consultation(consultation_id=tv, identity=bs_tu_van)
    assert await _hang(pool, lan.visit) == {"TU_VAN": "serving"}

    await svc.xong_tu_van(consultation_id=tv, identity=bs_tu_van)
    await _hanh_trinh(pool)
    assert await _duong_di(pool, lan.visit) == "PRIMARY"
    assert await _hang(pool, lan.visit) == {"TU_VAN": "done", "DOCTOR": "waiting"}
    bang = await svc.hang_cho(identity=lan.bac_si, room_id=None)
    assert not [x for x in bang["sap_toi"] if x["visit_id"] == lan.visit]
    assert [x for x in bang["hang_cho"] if x["visit_id"] == lan.visit]


async def test_tu_van_nhan_duoc_khach_chua_do_khong_khoa(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    lan = await _check_in(pool, qua_tu_van=True)
    await _hanh_trinh(pool)
    async with pool.acquire() as conn:
        bs_tu_van = await _nguoi(conn, lan.loc, "DOCTOR")
    tv = await _phien_tu_van(pool, lan.visit)
    await LuotKhamService(pool).start_consultation(
        consultation_id=tv, identity=bs_tu_van
    )
    assert await _hang(pool, lan.visit) == {"TU_VAN": "serving"}


async def test_loai_khong_qua_tu_van_vao_thang_bac_si_chinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    lan = await _check_in(pool, qua_tu_van=False)
    await _hanh_trinh(pool)
    assert await _duong_di(pool, lan.visit) == "PRIMARY"
    assert await _hang(pool, lan.visit) == {"DOCTOR": "waiting"}


async def test_chay_lai_khong_nhan_doi(pool: asyncpg.Pool) -> None:  # noqa: F811
    lan = await _check_in(pool, qua_tu_van=True)
    await _hanh_trinh(pool)
    async with pool.acquire() as conn:
        again = await LuotKhamService(pool=None).xep_sau_check_in(
            conn, clinic_id=CLINIC, visit_id=lan.visit
        )
    assert again is None
    assert await _hang(pool, lan.visit) == {"TU_VAN": "blocked"}
    so = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE event_type = 'visit.routed'"
        " AND aggregate_id = $1::uuid",
        lan.visit,
    )
    assert so == 1


async def test_dieu_duong_khong_co_khoi_tu_van_thi_bi_chan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    lan = await _check_in(pool, qua_tu_van=True)
    await _hanh_trinh(pool)
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, lan.loc, "NURSE_ULTRASOUND")
    with pytest.raises(SafetyGateError, match="tư vấn"):
        await LuotKhamService(pool).start_consultation(
            consultation_id=await _phien_tu_van(pool, lan.visit), identity=dd
        )


async def test_phat_lai_thi_hanh_trinh_khong_lam_gi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Node TÁC VỤ: xếp lại hàng cho khách hôm qua khi phát lại sổ là sai."""
    lan = await _check_in(pool, qua_tu_van=True)
    sk = nguoi_dua_tin.SuKienDaNhan(
        event_id=str(uuid.uuid4()),
        event_type="visit.checked_in",
        clinic_id=CLINIC,
        aggregate_id=lan.visit,
        aggregate_version=None,
        occurred_at=None,
        seq=0,
        actor_type="SYSTEM",
        actor_staff_id=None,
        payload={"visit_id": lan.visit},
        replay_id=str(uuid.uuid4()),
        attempts=0,
    )
    async with pool.acquire() as conn:
        await xu_ly_hanh_trinh(conn, sk)
    assert await _duong_di(pool, lan.visit) is None
