"""Đổi lịch tại chỗ (Tuyền chốt 29/09/2026) — trên Postgres thật.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55720/postgres \\
        .venv/bin/pytest src/tests/services/test_doi_lich_nhanh_db.py

Khách hẹn NGÀY MAI đến quầy HÔM NAY: lễ tân mở popover Đổi lịch, chọn "ngay bây
giờ" → [Đổi & Check-in luôn]. Một giao dịch: đổi lịch (lịch sử + sự kiện) rồi
check-in (số khám theo HÔM NAY).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.idempotency import IdempotencyGuard
from clinicai.api.identity import StaffIdentity
from clinicai.api.v1.routers.booking import DoiLichNhanhRequest, doi_lich_nhanh_post
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import booking_service as bs_mod
from clinicai.services.booking_service import BookingService
from clinicai.services.doi_lich_nhanh import o_doi_lich
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dung(pool: asyncpg.Pool) -> dict[str, Any]:  # noqa: F811
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        return {
            "loc": loc,
            "le_tan": await _nguoi(conn, loc, "RECEPTION"),
            "cskh": await _nguoi(conn, loc, "CSKH"),
            "bs": await _nguoi(conn, loc, "DOCTOR"),
            "dv": await conn.fetchval(
                "INSERT INTO service_type (clinic_id, code, name, is_active)"
                " VALUES ($1::uuid, $2, 'Khám đổi lịch nhanh', true)"
                " RETURNING id::text",
                CLINIC,
                f"DLN-{uuid.uuid4().hex[:8]}",
            ),
        }


async def _lich(
    pool: asyncpg.Pool,  # noqa: F811
    ca: dict[str, Any],
    bd: datetime,
    *,
    status: str = "CONFIRMED",
    so: str | None = None,
) -> str:
    pid = await pool.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'Khách đổi lịch', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"DLN-{uuid.uuid4().hex[:10]}",
        ca["loc"],
    )
    return str(
        await pool.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, doctor_id, status,"
            " queue_number) VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5,"
            " $6, $7::uuid, $8, $9) RETURNING id::text",
            CLINIC,
            pid,
            ca["loc"],
            ca["dv"],
            bd,
            bd + timedelta(minutes=15),
            ca["bs"].staff_id,
            status,
            so,
        )
    )


def _mai_9h() -> datetime:
    mai = datetime.now(CLINIC_TZ).date() + timedelta(days=1)
    return datetime(mai.year, mai.month, mai.day, 9, 0, tzinfo=CLINIC_TZ)


def _bay_gio() -> datetime:
    return datetime.now(UTC).replace(second=0, microsecond=0)


async def _dem(pool: asyncpg.Pool, ten: str, aggregate: str) -> int:  # noqa: F811
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = $1"
            " AND aggregate_id = $2::uuid",
            ten,
            aggregate,
        )
    )


async def _goi(
    pool: asyncpg.Pool,  # noqa: F811
    identity: StaffIdentity,
    appt: str,
    body: DoiLichNhanhRequest,
) -> Any:
    return await doi_lich_nhanh_post(
        appointment_id=UUID(appt),
        body=body,
        identity=identity,
        pool=pool,
        idem=IdempotencyGuard(
            key=None, endpoint=f"POST /api/v1/appointments/{appt}/doi-lich-nhanh"
        ),
    )


async def test_mai_sang_hom_nay_check_in_so_theo_hom_nay_va_goi_lai_cung_khoa(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    hom_nay_som = datetime.now(CLINIC_TZ).replace(
        hour=0, minute=5, second=0, microsecond=0
    )
    await _lich(pool, ca, hom_nay_som, status="CHECKED_IN", so="3")
    await _lich(pool, ca, _mai_9h() + timedelta(hours=2), status="CHECKED_IN", so="7")
    appt = await _lich(pool, ca, _mai_9h())

    # Popover đọc được ô "ngay bây giờ" cho bác sĩ cũ, và cho check-in.
    o = await o_doi_lich(pool, identity=ca["le_tan"], appointment_id=appt, ngay=None)
    assert o["la_hom_nay"] and o["cho_check_in"]
    hang = next(h for h in o["bac_si"] if h["id"] == ca["bs"].staff_id)
    assert hang["bs_cu"] and hang["ngay_bay_gio"] is not None

    bd = _bay_gio()
    body = DoiLichNhanhRequest(
        slot_start=bd,
        slot_end=bd + timedelta(minutes=15),
        doctor_id=UUID(ca["bs"].staff_id),
        ly_do="Khách đến sớm",
        check_in=True,
        idempotency_key=f"dln-{uuid.uuid4().hex}",
    )
    kq = await _goi(pool, ca["le_tan"], appt, body)
    assert kq["status"] == "CHECKED_IN"
    assert kq["queue_number"] == "4", "số khám theo HÔM NAY, không theo ngày mai"
    assert kq["visit_id"]

    r = await pool.fetchrow(
        "SELECT tu_bat_dau, den_bat_dau, ly_do FROM appointment_doi_lich"
        " WHERE appointment_id = $1::uuid",
        appt,
    )
    assert r["tu_bat_dau"] == _mai_9h() and r["den_bat_dau"] == bd
    assert r["ly_do"].startswith("Khách đến sớm")
    assert await _dem(pool, "appointment.rescheduled", appt) == 1

    # Gửi lại CÙNG khoá → cùng kết quả, không ghi lần hai.
    lai = await _goi(pool, ca["le_tan"], appt, body)
    assert json.loads(lai.body) == kq
    assert await _dem(pool, "appointment.rescheduled", appt) == 1
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM appointment_doi_lich WHERE appointment_id = $1::uuid",
            appt,
        )
        == 1
    )


async def test_day_cho_thi_chan(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    # Tuần xa trong tương lai, CÔNG BỐ lịch trực → trần có chặn.
    hom_nay = datetime.now(CLINIC_TZ).date()
    tuan = 60 + uuid.uuid4().int % 800
    thu2 = hom_nay + timedelta(days=7 * tuan - hom_nay.weekday())
    ngay = thu2 + timedelta(days=1)
    await pool.execute(
        "INSERT INTO work_roster (clinic_id, work_date, week_start, shift, station,"
        " staff_id, staff_name, status) VALUES ($1::uuid, $2, $3, 'FULL',"
        " 'LICH_KHAM', $4::uuid, 'BS DLN', 'APPROVED')",
        CLINIC,
        ngay,
        thu2,
        ca["bs"].staff_id,
    )
    await pool.execute(
        "INSERT INTO roster_week (clinic_id, week_start) VALUES ($1::uuid, $2)"
        " ON CONFLICT DO NOTHING",
        CLINIC,
        thu2,
    )
    await pool.execute(
        "INSERT INTO doctor_booking_override (clinic_id, doctor_id, regular_cap,"
        " effective_from, effective_to, minute_start, minute_end, created_by, reason)"
        " VALUES ($1::uuid, $2::uuid, 1, $3, $3, 540, 555, $2::uuid, 'DLN')",
        CLINIC,
        ca["bs"].staff_id,
        ngay,
    )
    chin_gio = datetime(ngay.year, ngay.month, ngay.day, 9, 0, tzinfo=CLINIC_TZ)
    await _lich(pool, ca, chin_gio)  # chiếm chỗ duy nhất
    appt = await _lich(pool, ca, chin_gio + timedelta(hours=1))

    o = await o_doi_lich(
        pool, identity=ca["le_tan"], appointment_id=appt, ngay=ngay.isoformat()
    )
    hang = next(h for h in o["bac_si"] if h["id"] == ca["bs"].staff_id)
    assert next(x for x in hang["o"] if x["gio"] == "09:00")["trang_thai"] == "DAY"

    with pytest.raises(ConflictError):
        await BookingService(pool).doi_lich_nhanh(
            appointment_id=appt,
            identity=ca["le_tan"],
            slot_start=chin_gio,
            slot_end=chin_gio + timedelta(minutes=15),
            doctor_id=ca["bs"].staff_id,
            ly_do="Khách xin đổi",
            check_in=False,
        )
    assert await _dem(pool, "appointment.rescheduled", appt) == 0


async def test_khong_quyen_check_in_chi_doi_duoc(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    await ve_goi_mau_cu(pool, ca["cskh"])  # gói lego cũ (mở full lego 30/09)
    appt = await _lich(pool, ca, _mai_9h())
    o = await o_doi_lich(pool, identity=ca["cskh"], appointment_id=appt, ngay=None)
    assert o["cho_check_in"] is False
    bd = _bay_gio()
    svc = BookingService(pool)
    with pytest.raises(SafetyGateError):
        await svc.doi_lich_nhanh(
            appointment_id=appt,
            identity=ca["cskh"],
            slot_start=bd,
            slot_end=bd + timedelta(minutes=15),
            doctor_id=ca["bs"].staff_id,
            ly_do="Khách đến sớm",
            check_in=True,
        )
    # Bị từ chối thì lịch giữ nguyên, không lịch sử.
    assert (
        await pool.fetchval(
            "SELECT slot_start FROM appointment WHERE id = $1::uuid", appt
        )
        == _mai_9h()
    )
    assert await _dem(pool, "appointment.rescheduled", appt) == 0

    moi = _mai_9h() + timedelta(hours=1)
    kq = await svc.doi_lich_nhanh(
        appointment_id=appt,
        identity=ca["cskh"],
        slot_start=moi,
        slot_end=moi + timedelta(minutes=15),
        doctor_id=ca["bs"].staff_id,
        ly_do="Khách xin đổi",
        check_in=False,
    )
    assert kq["status"] == "CONFIRMED" and kq["visit_id"] is None
    assert await _dem(pool, "appointment.rescheduled", appt) == 1


async def test_ngoai_ca_ngay_bay_gio_kem_check_in_thi_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Giả "bây giờ" nằm ngoài mọi ca (ca bác sĩ chưa bắt đầu).
    monkeypatch.setattr(bs_mod, "covers", lambda windows, minute: False)
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    bd = _bay_gio()
    kq = await BookingService(pool).doi_lich_nhanh(
        appointment_id=appt,
        identity=ca["le_tan"],
        slot_start=bd,
        slot_end=bd + timedelta(minutes=15),
        doctor_id=ca["bs"].staff_id,
        ly_do="Khách đến sớm",
        check_in=True,
    )
    assert kq["status"] == "CHECKED_IN" and kq["ngoai_ca"] is True
    ly_do = await pool.fetchval(
        "SELECT ly_do FROM appointment_doi_lich WHERE appointment_id = $1::uuid", appt
    )
    assert "ngoài ca" in ly_do


async def test_ngoai_ca_khong_phai_bay_gio_van_chan(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bs_mod, "covers", lambda windows, minute: False)
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    svc = BookingService(pool)
    moi = _mai_9h() + timedelta(hours=1)
    # Không kèm check-in → luật "ngoài khung ca" giữ nguyên.
    with pytest.raises(ValidationError, match="không thuộc ca nào"):
        await svc.doi_lich_nhanh(
            appointment_id=appt,
            identity=ca["le_tan"],
            slot_start=moi,
            slot_end=moi + timedelta(minutes=15),
            doctor_id=ca["bs"].staff_id,
            ly_do="Khách xin đổi",
            check_in=False,
        )
    # Kèm check-in nhưng khung KHÔNG phải bây giờ (cùng ngày, 40 phút nữa).
    sau = _bay_gio() + timedelta(minutes=40)
    if sau.astimezone(CLINIC_TZ).date() == datetime.now(CLINIC_TZ).date():
        with pytest.raises(ValidationError, match="không thuộc ca nào"):
            await svc.doi_lich_nhanh(
                appointment_id=appt,
                identity=ca["le_tan"],
                slot_start=sau,
                slot_end=sau + timedelta(minutes=15),
                doctor_id=ca["bs"].staff_id,
                ly_do="Khách đến sớm",
                check_in=True,
            )
    # Check-in luôn chỉ khi đổi sang HÔM NAY.
    with pytest.raises(ValidationError, match="hôm nay"):
        await svc.doi_lich_nhanh(
            appointment_id=appt,
            identity=ca["le_tan"],
            slot_start=moi,
            slot_end=moi + timedelta(minutes=15),
            doctor_id=ca["bs"].staff_id,
            ly_do="Khách đến sớm",
            check_in=True,
        )
    assert await _dem(pool, "appointment.rescheduled", appt) == 0
