"""[Không đo] sinh hiệu + lý do (30/10/2026).

    scripts/test-nhanh.sh src/tests/services/test_sinh_hieu_khong_do_db.py

Người đo bấm [Không đo] → chạm chip lý do. Ghi MỘT dòng `sinh_hieu_khong_do`
(lý do, ai, lúc nào), KHÔNG ghi số giả; lượt đi tiếp như đã đo (cùng sự kiện
`vitals.recorded` có cờ → hàng tư vấn mở). Màn đo / bàn khám / phiếu khám đọc
"Không đo · <lý do>". Đo thật sau đó vẫn được và THẮNG.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.phieu_kham.mang_sang import doc_dau_phieu
from clinicai.services.booking_service import BookingService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.sinh_hieu_service import LoiSinhHieuError, SinhHieuService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _luot_qua_tu_van(
    pool: asyncpg.Pool,  # noqa: F811
) -> tuple[str, StaffIdentity, StaffIdentity]:
    """Check-in một lượt loại khám QUA tư vấn → (visit, người đo, bác sĩ)."""
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        le_tan = await _nguoi(conn, loc, "RECEPTION")
        bac_si = await _nguoi(conn, loc, "DOCTOR")
        dd = await _nguoi(conn, loc, "NURSE_ULTRASOUND")
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN không đo', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"KD-{uuid.uuid4().hex[:10]}",
            loc,
        )
        dv = await conn.fetchval(
            "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid"
            " AND is_active AND coalesce(qua_tu_van, false) ORDER BY code LIMIT 1",
            CLINIC,
        )
        if dv is None:
            dv = await conn.fetchval(
                "UPDATE service_type SET qua_tu_van = true WHERE id = ("
                " SELECT id FROM service_type WHERE clinic_id = $1::uuid"
                " AND is_active ORDER BY code LIMIT 1) RETURNING id::text",
                CLINIC,
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
            dv,
            bd,
            bd + timedelta(minutes=15),
            bac_si.staff_id,
        )
    await BookingService(pool).apply_action(
        appointment_id=str(appt), action="checkin", identity=le_tan
    )
    await chay_hanh_trinh(pool)
    vid = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    return str(vid), dd, bac_si


async def _hang_tu_van(pool: asyncpg.Pool, vid: str) -> list[str]:  # noqa: F811
    return [
        r["status"]
        for r in await pool.fetch(
            "SELECT status FROM queue_entry WHERE visit_id = $1::uuid"
            " AND lane = 'TU_VAN' AND status NOT IN ('done', 'left', 'cancelled')",
            vid,
        )
    ]


async def _mot(pool: asyncpg.Pool, vid: str, ai: StaffIdentity) -> dict[str, Any]:  # noqa: F811
    [x] = [
        x
        for x in (await LuotKhamService(pool).bang(identity=ai))["luot"]
        if x["visit_id"] == vid
    ]
    return dict(x)


async def test_khong_do_khach_di_tiep_khong_so_gia_va_do_sau_thang(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    vid, dd, bac_si = await _luot_qua_tu_van(pool)
    assert await _hang_tu_van(pool, vid) == ["blocked"]  # chờ đo
    svc = SinhHieuService(pool)

    kq = await svc.khong_do(visit_id=vid, ly_do="TRE_NHO", identity=dd)
    assert kq["ok"] is True and kq["nhan"] == "Không đo · Trẻ nhỏ"
    await chay_hanh_trinh(pool)

    # Đi tiếp như đã đo: luồng recorded, hàng tư vấn mở; KHÔNG có số đo.
    assert (
        await pool.fetchval(
            "SELECT vitals_status FROM encounter_flow WHERE visit_id = $1::uuid", vid
        )
        == "recorded"
    )
    assert await _hang_tu_van(pool, vid) == ["waiting"]
    assert not await pool.fetchval(
        "SELECT count(*) FROM vital_measurement WHERE visit_id = $1::uuid", vid
    )
    # Bản ghi có lý do, người ghi, giờ; sự kiện cùng tên có cờ.
    [row] = await pool.fetch(
        "SELECT * FROM sinh_hieu_khong_do WHERE visit_id = $1::uuid", vid
    )
    assert row["ly_do"] == "TRE_NHO" and row["ghi_chu"] is None
    assert str(row["ghi_boi"]) == dd.staff_id and row["ghi_luc"] is not None
    ev = await pool.fetchval(
        "SELECT payload FROM domain_event WHERE event_type = 'vitals.recorded'"
        " AND aggregate_id = $1::uuid ORDER BY aggregate_version DESC LIMIT 1",
        vid,
    )
    p = json.loads(ev) if isinstance(ev, str) else dict(ev)
    assert p["khong_do"] is True and p["ly_do_khong_do"] == "TRE_NHO"

    # Màn đo / bàn khám / phiếu khám: "Không đo · Trẻ nhỏ" thay ô trống.
    x = await _mot(pool, vid, bac_si)
    assert x["sinh_hieu"] is None and x["khong_do"]["nhan"] == "Không đo · Trẻ nhỏ"
    async with pool.acquire() as conn:
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=vid)
    assert dau["sinh_hieu_khong_do"] == "Không đo · Trẻ nhỏ"

    # Bấm trùng → already, không thêm dòng; đổi lý do → dòng mới, không sự kiện mới.
    assert (await svc.khong_do(visit_id=vid, ly_do="TRE_NHO", identity=dd))["already"]
    so_su_kien = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE event_type = 'vitals.recorded'"
        " AND aggregate_id = $1::uuid",
        vid,
    )
    kq = await svc.khong_do(
        visit_id=vid, ly_do="KHAC", ghi_chu="  Khách   đang sốt cao  ", identity=dd
    )
    assert kq["nhan"] == "Không đo · Khách đang sốt cao"
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM sinh_hieu_khong_do WHERE visit_id = $1::uuid", vid
        )
        == 2
    )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = 'vitals.recorded'"
            " AND aggregate_id = $1::uuid",
            vid,
        )
        == so_su_kien
    )

    # ĐO SAU vẫn được (không cần Bắt đầu — luồng đã qua bước) và THẮNG.
    await svc.record_vitals(
        visit_id=vid, raw={"systolic": 118, "diastolic": 76}, identity=dd
    )
    await chay_hanh_trinh(pool)
    x = await _mot(pool, vid, bac_si)
    assert x["sinh_hieu"]["tam_thu"] == 118 and x["khong_do"] is None
    async with pool.acquire() as conn:
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=vid)
    assert dau["sinh_hieu_khong_do"] is None
    # Đã có số đo → không ghi "Không đo" nữa.
    with pytest.raises(LuotKhamConflictError):
        await svc.khong_do(visit_id=vid, ly_do="TU_CHOI", identity=dd)


async def test_khong_do_dau_vao_rac_va_quyen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    vid, dd, _bac_si = await _luot_qua_tu_van(pool)
    svc = SinhHieuService(pool)
    for ma, chu in (
        (None, None),
        ("", None),
        ("rác", None),
        (123, None),
        ("KHAC", None),
        ("KHAC", "   "),
        ("KHAC", ["x"]),
    ):
        with pytest.raises(LoiSinhHieuError):
            await svc.khong_do(visit_id=vid, ly_do=ma, ghi_chu=chu, identity=dd)
    with pytest.raises(Exception):  # noqa: B017 — mã lượt rác (422 chung)
        await svc.khong_do(visit_id="rác", ly_do="TU_CHOI", identity=dd)
    # Postgres ép: "Khác" phải có chữ, mã ngoài danh sách bị chặn.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO sinh_hieu_khong_do (clinic_id, visit_id, ly_do)"
            " VALUES ($1::uuid, $2::uuid, 'KHAC')",
            CLINIC,
            vid,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO sinh_hieu_khong_do (clinic_id, visit_id, ly_do)"
            " VALUES ($1::uuid, $2::uuid, 'BAT_KY')",
            CLINIC,
            vid,
        )
    # Sổ chỉ ghi thêm.
    await svc.khong_do(visit_id=vid, ly_do="DO_NOI_KHAC", identity=dd)
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE sinh_hieu_khong_do SET ly_do = 'TU_CHOI' WHERE visit_id = $1::uuid",
            vid,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "DELETE FROM sinh_hieu_khong_do WHERE visit_id = $1::uuid", vid
        )
