"""Quyền theo lịch, nửa "mở", trên Postgres thật (28/09/2026).

Tuyền: bác sĩ – thư ký – điều dưỡng xếp CÙNG PHÒNG trong lịch làm việc thì làm
cùng nhau; thư ký thao tác thay bác sĩ trên tài khoản của mình → Bàn khám (không
chọn phòng) của thư ký hiện khách của bác sĩ cùng phòng, và KHÔNG hiện khách của
bác sĩ phòng khác.
"""

from __future__ import annotations

import datetime as dt
import uuid

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.permissions.can import can
from clinicai.services.permission_service import PermissionService
from tests.services.test_luot_kham_service_db import KichBan, _hanh_trinh, _nguoi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _xep(
    conn: asyncpg.Connection, cid: str, room_id: str, ai: StaffIdentity
) -> None:
    """Một vị trí mới trong phòng `room_id` + xếp `ai` vào đó cả ngày hôm nay."""
    ma = f"T-LICH-{uuid.uuid4().hex[:6]}"
    await conn.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, room_id)"
        " VALUES ($1::uuid, $2, $2, $3::uuid)",
        cid,
        ma,
        room_id,
    )
    hom_nay = await conn.fetchval(
        "SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
    )
    await conn.execute(
        "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
        " staff_id, staff_name, status)"
        " VALUES ($1::uuid, $2, $3, 'FULL', $4, $5::uuid, $6,"
        " 'APPROVED')",
        cid,
        hom_nay - dt.timedelta(days=hom_nay.weekday()),
        hom_nay,
        ma,
        ai.staff_id,
        ai.full_name,
    )


async def _vao_hang_kham(kb: KichBan) -> None:
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)


def _co_luot(hc: dict[str, object], visit_id: str) -> bool:
    return any(
        r["visit_id"] == visit_id and r["loai"] == "KHAM"
        for r in hc["hang_cho"]  # type: ignore[attr-defined]
    )


async def _nhu_tren_prod(kb: KichBan) -> None:
    """Thư ký có lego Bàn khám (gồm quyền Hoàn tất khám) — y như prod 28/09,
    nơi 12/12 người kỹ năng TKYK / Phụ BS có quyền ấy. Thiếu bước này bài kiểm
    không tái hiện được lỗi: thư ký không có Hoàn tất thì bản cũ đã cho thấy hết."""
    async with kb.pool.acquire() as conn:
        ql = await _nguoi(conn, kb.location_id, "MANAGEMENT")
    await PermissionService(kb.pool).doi_lego(
        staff_id=kb.thu_ky.staff_id, ma="ban_kham", bat=True, identity=ql
    )
    async with kb.pool.acquire() as conn:
        assert await can(conn, kb.thu_ky, "clinical.consult.finalize")


async def test_thu_ky_cung_phong_thay_khach_bac_si(kb: KichBan) -> None:
    await _nhu_tren_prod(kb)
    await _vao_hang_kham(kb)
    cid = kb.bac_si.clinic_id
    async with kb.pool.acquire() as conn:
        await _xep(conn, cid, kb.phong_sa, kb.bac_si)
        await _xep(conn, cid, kb.phong_sa, kb.thu_ky)
    hc = await kb.svc.hang_cho(identity=kb.thu_ky, room_id=None)
    assert _co_luot(hc, kb.visit_id), "thư ký cùng phòng phải thấy khách bác sĩ"


async def test_thu_ky_phong_khac_khong_thay_khach_bac_si(kb: KichBan) -> None:
    await _nhu_tren_prod(kb)
    await _vao_hang_kham(kb)
    cid = kb.bac_si.clinic_id
    async with kb.pool.acquire() as conn:
        await _xep(conn, cid, kb.phong_sa, kb.bac_si)
        await _xep(conn, cid, kb.phong_mau, kb.bac_si_2)
        await _xep(conn, cid, kb.phong_mau, kb.thu_ky)
    hc = await kb.svc.hang_cho(identity=kb.thu_ky, room_id=None)
    assert not _co_luot(hc, kb.visit_id), "khách bác sĩ phòng khác không hiện"


async def test_thu_ky_chua_xep_lich_van_thay(kb: KichBan) -> None:
    # Mở, không khoá: chưa có lịch thì thấy mọi bác sĩ — kể cả khi thư ký có
    # quyền Hoàn tất khám (bản cũ trả "khách của chính tôi" = rỗng).
    await _nhu_tren_prod(kb)
    await _vao_hang_kham(kb)
    hc = await kb.svc.hang_cho(identity=kb.thu_ky, room_id=None)
    assert _co_luot(hc, kb.visit_id)
