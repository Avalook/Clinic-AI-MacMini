"""Bắt đầu đo sinh hiệu — `StartVitals` trên Postgres thật.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \
        poetry run pytest src/tests/services/test_bat_dau_do_sinh_hieu_db.py

Phạm vi chốt với Tuyền + ChatGPT 23/09/2026:

    [Bắt đầu]            pending → in_progress, ghi ai/lúc nào, `vitals.started` 1 lần
    [Lưu] lần đầu        in_progress → recorded, THÊM một vital_measurement
    [Lưu] thêm sau đó    vẫn recorded, THÊM một dòng nữa, dòng cũ giữ nguyên
                         — KHÔNG gọi là "sửa", không có `vitals.corrected`
    `goi_do_*`           giữ cột và dữ liệu cũ, không dùng làm trạng thái
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.luot_kham_service import (
    LuotKhamConflictError,
    LuotKhamService,
)
from clinicai.services.permission_service import cap_preset_mac_dinh

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=6)
    yield p
    await p.close()


async def _co_so(conn: asyncpg.Connection) -> str:
    return str(
        await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
    )


async def _nguoi(conn: asyncpg.Connection, role: str) -> StaffIdentity:
    loc = await _co_so(conn)
    ten = f"Test {role} {uuid.uuid4().hex[:6]}"
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        ten,
        role,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        CLINIC,
        sid,
        role,
    )
    await cap_preset_mac_dinh(conn, clinic_id=CLINIC, staff_id=sid, vai=role)
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


async def _luot(conn: asyncpg.Connection) -> str:
    loc = await _co_so(conn)
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN đo sinh hiệu', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"SH-{uuid.uuid4().hex[:10]}",
        loc,
    )
    return str(
        await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'OPEN', now()) RETURNING visit_id::text",
            CLINIC,
            pid,
        )
    )


async def _flow(pool: asyncpg.Pool, vid: str) -> asyncpg.Record:
    row = await pool.fetchrow(
        "SELECT vitals_status, vitals_started_at, vitals_started_by::text AS boi,"
        "       goi_do_luc, goi_do_boi::text AS goi_boi"
        "  FROM encounter_flow WHERE visit_id = $1::uuid",
        vid,
    )
    assert row is not None
    return row


async def _so_su_kien(pool: asyncpg.Pool, vid: str, ten: str) -> int:
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM domain_event"
            " WHERE aggregate_id = $1::uuid AND event_type = $2",
            vid,
            ten,
        )
    )


async def _so_lan_do(pool: asyncpg.Pool, vid: str) -> int:
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM vital_measurement WHERE visit_id = $1::uuid", vid
        )
    )


# ── 1–4. Bắt đầu ───────────────────────────────────────────────────────────


async def test_bat_dau_chuyen_sang_dang_do_va_ghi_ai_luc_nao(
    pool: asyncpg.Pool,
) -> None:
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
        vid = await _luot(conn)
    svc = LuotKhamService(pool)

    kq = await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=dd)

    assert kq["already"] is False
    assert kq["vitals_status"] == "in_progress"
    f = await _flow(pool, vid)
    assert f["vitals_status"] == "in_progress"
    assert f["boi"] == dd.staff_id
    assert f["vitals_started_at"] is not None
    assert await _so_su_kien(pool, vid, "vitals.started") == 1


async def test_bam_hai_lan_khong_phat_su_kien_thu_hai(pool: asyncpg.Pool) -> None:
    """Double-click không phải lỗi, và không tạo ra lần bắt đầu thứ hai."""
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
        vid = await _luot(conn)
    svc = LuotKhamService(pool)

    dau = await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=dd)
    lai = await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=dd)

    assert lai["already"] is True
    assert lai["bat_dau_do_luc"] == dau["bat_dau_do_luc"], "mốc bắt đầu bị đổi"
    assert await _so_su_kien(pool, vid, "vitals.started") == 1


async def test_nguoi_khac_bam_sau_bi_tu_choi_kem_ten(pool: asyncpg.Pool) -> None:
    """Hai điều dưỡng cùng đo một khách là chuyện phải biết ngay."""
    async with pool.acquire() as conn:
        a = await _nguoi(conn, "NURSE_ULTRASOUND")
        b = await _nguoi(conn, "NURSE_ULTRASOUND")
        vid = await _luot(conn)
    svc = LuotKhamService(pool)

    await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=a)
    with pytest.raises(LuotKhamConflictError) as loi:
        await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=b)

    assert loi.value.error_code == "VITALS_STARTED_BY_OTHER"
    assert a.full_name in str(loi.value), "phải nói RÕ ai đã bắt đầu"
    # Không đổi người bắt đầu.
    assert (await _flow(pool, vid))["boi"] == a.staff_id
    assert await _so_su_kien(pool, vid, "vitals.started") == 1


async def test_hai_nguoi_bam_cung_luc_chi_mot_lan_bat_dau(pool: asyncpg.Pool) -> None:
    """Khoá dòng encounter_flow: người sau chờ, rồi thấy đã có người bắt đầu."""
    async with pool.acquire() as conn:
        a = await _nguoi(conn, "NURSE_ULTRASOUND")
        b = await _nguoi(conn, "NURSE_ULTRASOUND")
        vid = await _luot(conn)
    svc = LuotKhamService(pool)

    ket_qua = await asyncio.gather(
        svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=a),
        svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=b),
        return_exceptions=True,
    )
    thang = [r for r in ket_qua if isinstance(r, dict)]
    thua = [r for r in ket_qua if isinstance(r, LuotKhamConflictError)]
    assert len(thang) == 1 and len(thua) == 1, ket_qua
    assert thua[0].error_code == "VITALS_STARTED_BY_OTHER"
    assert await _so_su_kien(pool, vid, "vitals.started") == 1


# ── 5–7. Lưu sinh hiệu ─────────────────────────────────────────────────────


async def test_luu_lan_dau_chuyen_sang_da_do(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
        vid = await _luot(conn)
    svc = LuotKhamService(pool)

    await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=dd)
    await svc.record_vitals(
        visit_id=vid, raw={"systolic": 120, "diastolic": 80}, identity=dd
    )

    f = await _flow(pool, vid)
    assert f["vitals_status"] == "recorded"
    # Mốc bắt đầu vẫn nguyên — nó là dữ liệu đo thời gian chờ.
    assert f["boi"] == dd.staff_id
    assert await _so_lan_do(pool, vid) == 1
    assert await _so_su_kien(pool, vid, "vitals.recorded") == 1


async def test_luu_them_giu_nguyen_lan_do_cu(pool: asyncpg.Pool) -> None:
    """10:00 đo 120/80, 10:05 đo lại 118/78 — cả hai dòng đều còn.

    Đo lại sau năm phút là chuyện bình thường, không phải một lần sửa sai. Không
    có `vitals.corrected`, không có `visit_amendment`.
    """
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
        vid = await _luot(conn)
    svc = LuotKhamService(pool)

    await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=dd)
    await svc.record_vitals(
        visit_id=vid, raw={"systolic": 120, "diastolic": 80}, identity=dd
    )
    await svc.record_vitals(
        visit_id=vid, raw={"systolic": 118, "diastolic": 78}, identity=dd
    )

    assert (await _flow(pool, vid))["vitals_status"] == "recorded"
    rows = await pool.fetch(
        "SELECT systolic, diastolic FROM vital_measurement"
        " WHERE visit_id = $1::uuid ORDER BY created_at, id",
        vid,
    )
    assert [(r["systolic"], r["diastolic"]) for r in rows] == [(120, 80), (118, 78)]
    assert await _so_su_kien(pool, vid, "vitals.corrected") == 0
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM visit_amendment WHERE visit_id = $1::uuid", vid
        )
        == 0
    )


async def test_luu_thang_khong_can_bat_dau(pool: asyncpg.Pool) -> None:
    """[Bắt đầu] là mốc đo thời gian chờ, KHÔNG phải cửa khoá.

    Không ai bấm thì không bịa ra một người đã bấm: `vitals_started_*` để trống.
    """
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
        vid = await _luot(conn)
    svc = LuotKhamService(pool)

    await svc.record_vitals(
        visit_id=vid, raw={"systolic": 120, "diastolic": 80}, identity=dd
    )

    f = await _flow(pool, vid)
    assert f["vitals_status"] == "recorded"
    assert f["vitals_started_at"] is None
    assert f["boi"] is None
    assert await _so_su_kien(pool, vid, "vitals.started") == 0


# ── 8–10. Ranh giới ────────────────────────────────────────────────────────


async def test_da_do_roi_thi_khong_bat_dau_lai(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
        vid = await _luot(conn)
    svc = LuotKhamService(pool)
    await svc.record_vitals(
        visit_id=vid, raw={"systolic": 120, "diastolic": 80}, identity=dd
    )

    with pytest.raises(LuotKhamConflictError) as loi:
        await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=dd)
    assert loi.value.error_code == "VITALS_DONE"


async def test_bat_dau_khong_dung_toi_goi_do_cu(pool: asyncpg.Pool) -> None:
    """`goi_do_*` là dữ liệu cũ: giữ nguyên, không chép sang, không bị ghi đè.

    "Đã gọi" không chứng minh "đã bắt đầu đo".
    """
    async with pool.acquire() as conn:
        a = await _nguoi(conn, "NURSE_ULTRASOUND")
        b = await _nguoi(conn, "NURSE_ULTRASOUND")
        vid = await _luot(conn)
    svc = LuotKhamService(pool)

    # Lượt cũ: A đã GỌI bằng đường cũ.
    await svc.goi_do_sinh_hieu(visit_id=vid, identity=a)
    cu = await _flow(pool, vid)
    assert cu["goi_do_luc"] is not None
    assert cu["vitals_status"] == "pending", "gọi KHÔNG phải bắt đầu đo"

    # B bắt đầu đo.
    await svc.bat_dau_do_sinh_hieu(visit_id=vid, identity=b)
    moi = await _flow(pool, vid)
    assert moi["goi_do_luc"] == cu["goi_do_luc"], "giờ gọi cũ bị đổi"
    assert moi["goi_boi"] == a.staff_id, "người gọi cũ bị đổi"
    assert moi["boi"] == b.staff_id, "người bắt đầu phải là B, không suy từ người gọi"


async def test_postgres_chan_dang_do_ma_khong_co_nguoi(pool: asyncpg.Pool) -> None:
    """Không có trạng thái "đang đo" mà không có người đo — ép ở Postgres."""
    async with pool.acquire() as conn:
        vid = await _luot(conn)
        await conn.execute(
            "INSERT INTO encounter_flow (clinic_id, visit_id)"
            " VALUES ($1::uuid, $2::uuid) ON CONFLICT (visit_id) DO NOTHING",
            CLINIC,
            vid,
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "UPDATE encounter_flow SET vitals_status = 'in_progress'"
                " WHERE visit_id = $1::uuid",
                vid,
            )
