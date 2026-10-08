"""Màn Đặt lịch chỉ coi bác sĩ là "đang trực" khi có ca Ở CƠ SỞ ĐANG ĐỨNG.

    scripts/test-nhanh.sh src/tests/services/test_dat_lich_theo_co_so_db.py

Tuyền 08/10/2026 (Hào Nam vừa mở, lịch làm việc chưa xếp ai): bảng Bác sĩ × tuần
ở Hào Nam vẫn hiện "Còn 96" cho các bác sĩ có ca ở Kim Ngưu — lưới hỏi lịch trực
theo `clinic_id + ngày`, không theo cơ sở. Cơ sở của ca = vị trí → phòng → cơ sở;
vị trí không gắn phòng (Điều phối) thuộc mọi cơ sở.

Tuần thử nằm xa trong tương lai (một tuần riêng mỗi lượt chạy) để `roster_week`
của bài không đổi hành vi bài khác chạy song song trên cùng DB.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, date, datetime, timedelta

import asyncpg
import pytest

from clinicai.services.capacity_service import CapacityService, bang_tuan, luoi_ngay
from clinicai.services.man_dat_lich_doc import hub_dat_lich
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_loc_co_so_nhom_a_db import _phong_o
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _benh_nhan, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@dataclasses.dataclass
class Bo:
    ca: Ca
    loc_b: str
    thu_hai: date


async def _co_so_moi(pool: asyncpg.Pool) -> str:  # noqa: F811
    # is_active = false: cơ sở đang mở thứ hai đổi hành vi tự gán cơ sở của bài
    # khác chạy song song; lưới không xét is_active.
    return str(
        await pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, 'Cơ sở đặt lịch thử', false) RETURNING id::text",
            CLINIC,
            f"DL{uuid.uuid4().hex[:6]}",
        )
    )


async def _vi_tri(conn: asyncpg.Connection, phong: str | None) -> str:
    ma = f"DLCS-{uuid.uuid4().hex[:8]}"
    await conn.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, room_id)"
        " VALUES ($1::uuid, $2, $2, $3::uuid)",
        CLINIC,
        ma,
        phong,
    )
    return ma


@pytest.fixture
async def bo(pool: asyncpg.Pool) -> Bo:  # noqa: F811
    """Bác sĩ trực thứ Ba ở cơ sở A (vị trí gắn phòng A), thứ Tư ở vị trí
    không gắn phòng; tuần đã áp dụng."""
    ca = await _dung(pool)
    loc_b = await _co_so_moi(pool)
    goc = date(2046, 1, 1)
    thu_hai = (
        goc
        + timedelta(days=(7 - goc.weekday()) % 7)
        + timedelta(weeks=uuid.uuid4().int % 2000)
    )
    async with pool.acquire() as conn:
        vt_a = await _vi_tri(conn, await _phong_o(conn, ca.loc))
        vt_chung = await _vi_tri(conn, None)
        # Phòng ở cơ sở B có tồn tại — B không "rỗng phòng", chỉ chưa xếp ca.
        await _phong_o(conn, loc_b)
        await conn.execute(
            "INSERT INTO roster_week (clinic_id, week_start) VALUES ($1::uuid, $2)"
            " ON CONFLICT DO NOTHING",
            CLINIC,
            thu_hai,
        )
        for ngay, vt in (
            (thu_hai + timedelta(days=1), vt_a),
            (thu_hai + timedelta(days=2), vt_chung),
        ):
            await conn.execute(
                "INSERT INTO work_roster (clinic_id, week_start, work_date, shift,"
                " station, staff_id, staff_name, status) VALUES ($1::uuid, $2, $3,"
                " 'FULL', $4, $5::uuid, 'BS thử', 'APPROVED')",
                CLINIC,
                thu_hai,
                ngay,
                vt,
                ca.bac_si.staff_id,
            )
    return Bo(ca, loc_b, thu_hai)


async def test_quote_chi_tinh_ca_o_co_so_dang_dung(
    pool: asyncpg.Pool,  # noqa: F811
    bo: Bo,
) -> None:
    svc = CapacityService(pool)
    bs = bo.ca.bac_si.staff_id
    thu_ba = (bo.thu_hai + timedelta(days=1)).isoformat()
    thu_tu = (bo.thu_hai + timedelta(days=2)).isoformat()

    async def nghi(ngay: str, loc: str | None) -> bool:
        q = await svc.quote(date=ngay, location_id=loc, doctor_id=bs, clinic_id=CLINIC)
        return bool(q["off_duty"])

    # Ca ở phòng cơ sở A: trực ở A, NGHỈ ở B (lỗi cũ: B cũng thấy "còn chỗ").
    assert await nghi(thu_ba, bo.ca.loc) is False
    assert await nghi(thu_ba, bo.loc_b) is True
    # Không chọn cơ sở = mọi cơ sở (hành vi cũ giữ nguyên).
    assert await nghi(thu_ba, None) is False
    # Vị trí không gắn phòng (kiểu Điều phối) thuộc mọi cơ sở.
    assert await nghi(thu_tu, bo.ca.loc) is False
    assert await nghi(thu_tu, bo.loc_b) is False


async def test_bang_tuan_va_luoi_ngay_theo_co_so(
    pool: asyncpg.Pool,  # noqa: F811
    bo: Bo,
) -> None:
    svc = CapacityService(pool)
    bs = bo.ca.bac_si.staff_id
    thu_ba = (bo.thu_hai + timedelta(days=1)).isoformat()

    async def o_thu_ba(loc: str) -> str:
        bang = await bang_tuan(
            svc,
            pool,
            week_start=bo.thu_hai.isoformat(),
            location_id=loc,
            clinic_id=CLINIC,
            hom_nay=date.today().isoformat(),
        )
        hang = next(h for h in bang["bac_si"] if h["id"] == bs)
        return str(hang["o"][1]["trang_thai"])

    assert await o_thu_ba(bo.loc_b) == "NGHI"
    assert await o_thu_ba(bo.ca.loc) != "NGHI"

    async def luoi_nghi(loc: str) -> bool:
        luoi = await luoi_ngay(
            svc, clinic_id=CLINIC, date=thu_ba, doctor_ids=[bs], location_id=loc
        )
        hang = next(h for h in luoi["hang"] if h["doctor_id"] == bs)
        return bool(hang["off_duty"])

    assert await luoi_nghi(bo.loc_b) is True
    assert await luoi_nghi(bo.ca.loc) is False


async def test_luoi_ngay_location_rac_khong_nem(
    pool: asyncpg.Pool,  # noqa: F811
    bo: Bo,
) -> None:
    luoi = await luoi_ngay(
        CapacityService(pool),
        clinic_id=CLINIC,
        date=(bo.thu_hai + timedelta(days=1)).isoformat(),
        doctor_ids=[bo.ca.bac_si.staff_id],
        location_id="khong-phai-uuid",
    )
    assert luoi["hang"]  # rác = không lọc cơ sở, không 500


async def test_the_lich_hom_nay_chi_cua_co_so_dang_dung(
    pool: asyncpg.Pool,  # noqa: F811
    bo: Bo,
) -> None:
    ca = bo.ca
    bd = datetime.now(UTC) + timedelta(minutes=1)
    lich: dict[str, str] = {}
    for loc in (ca.loc, bo.loc_b):
        lich[loc] = str(
            await pool.fetchval(
                "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
                " service_type_id, slot_start, slot_end, status)"
                " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6,"
                " 'CONFIRMED') RETURNING id::text",
                CLINIC,
                await _benh_nhan(pool, ca),
                loc,
                ca.loai_kham,
                bd,
                bd + timedelta(minutes=15),
            )
        )
    for loc, khac in ((ca.loc, bo.loc_b), (bo.loc_b, ca.loc)):
        ai = dataclasses.replace(ca.le_tan, location_id=loc)
        thay = {a["id"] for a in (await hub_dat_lich(pool, identity=ai))["appts"]}
        assert lich[loc] in thay
        assert lich[khac] not in thay
    # Không chọn cơ sở thấy cả hai.
    ai = dataclasses.replace(ca.le_tan, location_id="")
    thay = {a["id"] for a in (await hub_dat_lich(pool, identity=ai))["appts"]}
    assert set(lich.values()) <= thay


async def test_chot_lich_truc_khi_dat_theo_co_so_cua_lich(
    pool: asyncpg.Pool,  # noqa: F811
    bo: Bo,
) -> None:
    """Đặt / gán / đổi lịch: bác sĩ chỉ trực cơ sở A thì lịch ở B bị báo
    "không có lịch làm việc" (prod bật luật bắt buộc thì chặn)."""
    from clinicai.core.clock import CLINIC_TZ
    from clinicai.services.booking_service import BookingService

    svc = BookingService(pool)
    bs = bo.ca.bac_si.staff_id
    gio = datetime.combine(
        bo.thu_hai + timedelta(days=1), datetime.min.time(), tzinfo=CLINIC_TZ
    ) + timedelta(hours=10)
    async with pool.acquire() as conn:
        o_b = await svc._roster_warning(
            conn, bs, gio, bo.ca.le_tan, location_id=bo.loc_b
        )
        o_a = await svc._roster_warning(
            conn, bs, gio, bo.ca.le_tan, location_id=bo.ca.loc
        )
        moi_noi = await svc._roster_warning(conn, bs, gio, bo.ca.le_tan)
    assert o_b is not None and "không có lịch làm việc" in o_b
    assert o_a is None
    assert moi_noi is None
