"""Lưới đặt chỗ nói ĐÚNG điều trigger sẽ làm (Tuyền 29/09/2026: "sửa đi").

Kịch bản gốc: quản lý hạ BS X 18:00 xuống 1 chỗ → lưới vẫn cho bấm ghế 2 rồi máy
chủ báo đầy; nâng lên 4 → lưới chỉ vẽ 2 ghế. Gốc: lưới tự cộng lịch và lấy trần
CHUNG của phòng khám, còn trigger `enforce_slot_capacity` chặn theo
`resolve_effective_cap` (bác sĩ × khung, có luật riêng).

Mỗi bài ở đây đặt lịch THẬT qua trigger và so với con số `luoi_ngay` trả — số
lưới nói "còn" thì trigger nhận, nói "đầy" thì trigger từ chối.

Thêm: danh sách trạng thái "chết" chỉ còn một bản ở Python
(`core/trang_thai_lich.py`); SQL giữ bản của nó, và bài cuối so hai bên.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.core.trang_thai_lich import DEAD_STATUSES
from clinicai.services.capacity_service import CapacityService, luoi_ngay
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

PHUT_18 = 18 * 60


def _thu_hai_xa() -> dt.date:
    """Một thứ Hai xa trong tương lai, khác nhau mỗi lần chạy — không đụng tuần
    mà bài kiểm khác đã công bố."""
    hom_nay = dt.datetime.now(CLINIC_TZ).date()
    tuan = 60 + uuid.uuid4().int % 800
    return hom_nay + dt.timedelta(days=7 * tuan - hom_nay.weekday())


async def _dung(pool: asyncpg.Pool, ngay: dt.date, *, cong_bo: bool) -> dict[str, Any]:  # noqa: F811
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        bs = await _nguoi(conn, loc, "DOCTOR")
        loai = await conn.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, 'Khám G6', true) RETURNING id::text",
            CLINIC,
            f"G6-{uuid.uuid4().hex[:8]}",
        )
        thu2 = ngay - dt.timedelta(days=ngay.weekday())
        await conn.execute(
            "INSERT INTO work_roster (clinic_id, work_date, week_start, shift, station,"
            " staff_id, staff_name, status) VALUES ($1::uuid, $2, $3, 'FULL',"
            " 'LICH_KHAM', $4::uuid, 'BS G6', 'APPROVED')",
            CLINIC,
            ngay,
            thu2,
            bs.staff_id,
        )
        if cong_bo:
            await conn.execute(
                "INSERT INTO roster_week (clinic_id, week_start) VALUES ($1::uuid, $2)"
                " ON CONFLICT DO NOTHING",
                CLINIC,
                thu2,
            )
    return {"loc": loc, "bs": bs.staff_id, "loai": loai, "ngay": ngay}


async def _dat(
    pool: asyncpg.Pool,  # noqa: F811
    ca: dict[str, Any],
    *,
    phut: int = PHUT_18,
    bac_si: str | None = "",
    kenh: str = "PHONE",
) -> str:
    """Đặt một lịch THẲNG vào bảng — trigger là người quyết."""
    pid = await pool.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'Khách G6', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"G6-{uuid.uuid4().hex[:10]}",
        ca["loc"],
    )
    bd = dt.datetime.combine(
        ca["ngay"], dt.time(phut // 60, phut % 60), tzinfo=CLINIC_TZ
    )
    return str(
        await pool.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, doctor_id, status,"
            " booking_channel) VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5,"
            " $6, $7::uuid, 'CONFIRMED', $8) RETURNING id::text",
            CLINIC,
            pid,
            ca["loc"],
            ca["loai"],
            bd,
            bd + dt.timedelta(minutes=15),
            ca["bs"] if bac_si == "" else bac_si,
            kenh,
        )
    )


async def _khung(
    pool: asyncpg.Pool,  # noqa: F811
    ca: dict[str, Any],
    *,
    bac_si: str | None = "",
    phut: int = PHUT_18,
    bo_qua: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(hàng, khung) mà lưới nhận được cho bác sĩ × phút này."""
    id_bs = ca["bs"] if bac_si == "" else bac_si
    kq = await luoi_ngay(
        CapacityService(pool),
        clinic_id=CLINIC,
        date=ca["ngay"].isoformat(),
        doctor_ids=[ca["bs"]],
        bo_qua_lich_id=bo_qua,
    )
    hang = next(h for h in kq["hang"] if h["doctor_id"] == id_bs)
    k = next(s for s in hang["slots"] if s["minute_of_day"] == phut)
    return hang, k


async def _luat_rieng(pool: asyncpg.Pool, ca: dict[str, Any], tran: int) -> None:  # noqa: F811
    """Luật THƯỜNG TRỰC theo bác sĩ × giờ: 18:00–18:15 còn `tran` chỗ hẹn."""
    await pool.execute(
        "DELETE FROM doctor_booking_override WHERE clinic_id = $1::uuid"
        " AND doctor_id = $2::uuid",
        CLINIC,
        ca["bs"],
    )
    await pool.execute(
        "INSERT INTO doctor_booking_override (clinic_id, doctor_id, regular_cap,"
        " effective_from, effective_to, minute_start, minute_end, created_by, reason)"
        " VALUES ($1::uuid, $2::uuid, $3, $4, $4, $5, $6, $2::uuid, 'G6')",
        CLINIC,
        ca["bs"],
        tran,
        ca["ngay"],
        PHUT_18,
        PHUT_18 + 15,
    )


async def test_ha_xuong_1_cho_luoi_bao_day_dung_luc_trigger_tu_choi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool, _thu_hai_xa(), cong_bo=True)
    await _luat_rieng(pool, ca, 1)
    hang, k = await _khung(pool, ca)
    assert hang["regular_chan"] is True
    assert k["regular_cap"] == 1, "trần của LUẬT RIÊNG, không phải trần chung"
    assert k["regular_used"] == 0

    await _dat(pool, ca)
    _, k = await _khung(pool, ca)
    assert k["regular_used"] >= k["regular_cap"], "lưới phải nói ĐẦY"
    with pytest.raises(asyncpg.CheckViolationError, match="Khung giờ đã đầy"):
        await _dat(pool, ca)

    # Khung bên cạnh không có luật riêng → trần mặc định của phòng khám.
    _, k2 = await _khung(pool, ca, phut=PHUT_18 + 15)
    mac_dinh = await pool.fetchval(
        "SELECT regular_cap FROM clinic_booking_policy($1::uuid)", CLINIC
    )
    assert k2["regular_cap"] == mac_dinh


async def test_nang_len_4_cho_luoi_ve_4_ghe_va_trigger_nhan_du_4(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool, _thu_hai_xa(), cong_bo=True)
    await _luat_rieng(pool, ca, 4)
    _, k = await _khung(pool, ca)
    assert k["regular_cap"] == 4
    for i in range(4):
        await _dat(pool, ca)
        _, k = await _khung(pool, ca)
        assert k["regular_used"] == i + 1
    with pytest.raises(asyncpg.CheckViolationError):
        await _dat(pool, ca)


async def test_tuan_chua_cong_bo_va_hang_chua_phan_khong_chan_lich_hen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool, _thu_hai_xa(), cong_bo=False)
    await _luat_rieng(pool, ca, 1)
    hang, k = await _khung(pool, ca)
    assert hang["regular_chan"] is False and hang["dat_tu_do"] is True
    # Trigger nhận vượt trần ở tuần chưa công bố — lưới không được khoá ô.
    await _dat(pool, ca)
    await _dat(pool, ca)
    _, k = await _khung(pool, ca)
    assert k["regular_used"] == 2 and k["regular_cap"] == 1

    # Hàng chưa phân bác sĩ: lịch hẹn không bị kiểm, ghế trực tiếp thì có.
    chua_phan, _ = await _khung(pool, ca, bac_si=None)
    assert chua_phan["regular_chan"] is False
    assert chua_phan["walkin_chan"] is True


async def test_sua_lich_khong_tinh_chinh_no(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool, _thu_hai_xa(), cong_bo=True)
    await _luat_rieng(pool, ca, 1)
    lich = await _dat(pool, ca)
    _, k = await _khung(pool, ca, bo_qua=lich)
    assert k["regular_used"] == 0, "lịch đang sửa không chiếm ghế của chính nó"
    # Trigger đồng ý: đổi giờ trong cùng khung vẫn nhận.
    await pool.execute(
        "UPDATE appointment SET slot_start = slot_start + interval '5 minutes'"
        " WHERE id = $1::uuid",
        lich,
    )


async def test_trang_thai_chet_python_khop_sql(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Một danh sách ở Python; trigger + hàm đếm ghế giữ bản SQL — phải khớp."""
    trigger = await pool.fetchval(
        "SELECT pg_get_functiondef('public.enforce_slot_capacity'::regproc)"
    )
    m = re.search(r"dead\s+text\[\]\s*:=\s*ARRAY\[([^\]]*)\]", trigger)
    assert m, "không tìm thấy danh sách `dead` trong trigger"
    assert set(re.findall(r"'([A-Z_]+)'", m.group(1))) == DEAD_STATUSES

    ban = await pool.fetchval(
        "SELECT pg_get_functiondef('public.slot_seats_ban(uuid, uuid, timestamptz,"
        " timestamptz, uuid, uuid)'::regprocedure)"
    )
    m = re.search(r"status\s+NOT\s+IN\s*\(([^)]*)\)", ban)
    assert m, "không tìm thấy danh sách trạng thái trong slot_seats_ban"
    assert set(re.findall(r"'([A-Z_]+)'", m.group(1))) == DEAD_STATUSES
