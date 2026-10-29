"""Bác sĩ khác NHẬN khách — không mất dấu lịch hẹn (chốt 29/10/2026).

Lịch BS A quá tải, BS B khám: B thấy khách ở "Khách của bác sĩ khác", bấm Nhận
→ khách thành của B (mọi thứ ghi B), lịch hẹn vẫn là A ("Lịch: BS A"). Ai nhận
trước giữ; [Trả lại] hoàn tác khi chưa ai bắt đầu khám.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.services.doi_bac_si_service import DoiBacSiService
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.luot_kham_service import LuotKhamService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _luot(pool: asyncpg.Pool, visit: str) -> asyncpg.Record:  # noqa: F811
    return await pool.fetchrow(
        "SELECT v.attending_doctor_id::text AS bac_si, a.doctor_id::text AS lich,"
        "       c.doctor_staff_id::text AS phien,"
        "       q.doctor_staff_id::text AS hang"
        "  FROM visit v JOIN appointment a ON a.id = v.appointment_id"
        "  JOIN consultation c ON c.visit_id = v.visit_id AND c.kind = 'PRIMARY'"
        "  JOIN queue_entry q ON q.visit_id = v.visit_id AND q.lane = 'DOCTOR'"
        " WHERE v.visit_id = $1::uuid",
        visit,
    )


async def test_bac_si_b_thay_va_nhan_khach_lich_bac_si_a_roi_tra_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        bs_b = await _nguoi(conn, ca.loc, "DOCTOR")
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    truoc = await _luot(pool, visit)
    assert truoc["bac_si"] == truoc["lich"] == ca.bac_si.staff_id

    # Bàn khám của B: khách nằm ở "Khách của bác sĩ khác", ghi lịch BS A.
    hang = await BangLuotKham(pool).hang_cho(identity=bs_b, room_id=None)
    [k] = [x for x in hang["khach_bac_si_khac"] if x["visit_id"] == visit]
    assert k["lich_bac_si"] and k["lich_bac_si"] == k["bac_si_hien_tai"]

    await DoiBacSiService(pool).nhan_khach(identity=bs_b, visit_id=visit)
    sau = await _luot(pool, visit)
    assert sau["bac_si"] == sau["phien"] == sau["hang"] == bs_b.staff_id
    assert sau["lich"] == ca.bac_si.staff_id  # lịch hẹn GIỮ bác sĩ A

    # Giờ là khách của B, có nhãn "Lịch: BS A"; A không còn thấy ở hàng mình.
    hang = await BangLuotKham(pool).hang_cho(identity=bs_b, room_id=None)
    [d] = [x for x in hang["hang_cho"] if x["visit_id"] == visit]
    assert d["lich_bac_si"]
    assert visit not in [x["visit_id"] for x in hang["khach_bac_si_khac"]]
    hang_a = await BangLuotKham(pool).hang_cho(identity=ca.bac_si, room_id=None)
    assert visit not in [x["visit_id"] for x in hang_a["hang_cho"]]

    # Hoàn tác: về lại bác sĩ trên lịch.
    await DoiBacSiService(pool).tra_lai(identity=bs_b, visit_id=visit)
    ve = await _luot(pool, visit)
    assert ve["bac_si"] == ve["phien"] == ve["hang"] == ca.bac_si.staff_id


async def test_da_co_nguoi_bat_dau_kham_thi_khong_nhan_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        bs_b = await _nguoi(conn, ca.loc, "DOCTOR")
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    with pytest.raises(ConflictError):
        await DoiBacSiService(pool).nhan_khach(identity=bs_b, visit_id=visit)
    assert (await _luot(pool, visit))["bac_si"] == ca.bac_si.staff_id


async def test_dang_kham_truong_ca_chuyen_bac_si_roi_hoan_tac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tuyền 29/10/2026: khách ĐANG KHÁM thì bác sĩ khác không tự nhận được —
    trưởng ca chuyển ở Điều phối ca (ghi lý do), và chuyển ngược lại được."""
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        bs_b = await _nguoi(conn, ca.loc, "DOCTOR")
        tc = await _nguoi(conn, ca.loc, "TRUONG_CA")
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    svc = DoiBacSiService(pool)
    kq = await svc.doi(
        identity=tc,
        visit_id=visit,
        bac_si_moi_id=bs_b.staff_id,
        ly_do="khám nhầm người",
    )
    assert kq["bac_si_cu_id"] == ca.bac_si.staff_id
    sau = await _luot(pool, visit)
    assert sau["bac_si"] == sau["phien"] == sau["hang"] == bs_b.staff_id
    assert (
        await pool.fetchval("SELECT status FROM consultation WHERE id = $1::uuid", con)
        == "in_progress"
    ), "chuyển giữa chừng không được làm mất phiên đang khám"
    hang_b = await BangLuotKham(pool).hang_cho(identity=bs_b, room_id=None)
    assert visit in [x["visit_id"] for x in hang_b["hang_cho"]]
    hang_a = await BangLuotKham(pool).hang_cho(identity=ca.bac_si, room_id=None)
    assert visit not in [x["visit_id"] for x in hang_a["hang_cho"]]

    # [Hoàn tác] trên màn = chuyển ngược về bác sĩ cũ bằng chính lệnh này.
    await svc.doi(
        identity=tc,
        visit_id=visit,
        bac_si_moi_id=kq["bac_si_cu_id"],
        ly_do="Hoàn tác chuyển bác sĩ",
    )
    ve = await _luot(pool, visit)
    assert ve["bac_si"] == ve["phien"] == ve["hang"] == ca.bac_si.staff_id
