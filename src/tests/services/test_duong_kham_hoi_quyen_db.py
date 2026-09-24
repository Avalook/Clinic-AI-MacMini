"""Đường khám chính hỏi QUYỀN, không hỏi vai (CORE-B3, 23/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_duong_kham_hoi_quyen_db.py

Check-in → sinh hiệu → khám → ghi bệnh án → duyệt kết quả → thu tiền dịch vụ.

Cách thử rẻ mà chắc: mỗi lệnh hỏi quyền ĐẦU TIÊN trong giao dịch, trước khi tìm
bản ghi. Gọi với một mã không tồn tại thì:
  * không có quyền  → bị chặn vì QUYỀN;
  * có quyền        → qua cửa quyền, rồi mới vấp "không tìm thấy".
Người thử mang vai CSKH — vai không có nhóm mẫu nào — để chứng minh quyền, không
phải vai, là thứ quyết định.
"""

from __future__ import annotations

import dataclasses
import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import cache
from clinicai.permissions.catalogue import PRESET
from clinicai.services.booking_service import BookingService
from clinicai.services.clinical_record_service import ClinicalRecordService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.payment_service import PaymentService

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield p
    await p.close()


async def _nguoi(pool: asyncpg.Pool, role: str, quyen: list[str]) -> StaffIdentity:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        ten = f"Test quyền {role} {uuid.uuid4().hex[:6]}"
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
        for q in quyen:
            await conn.execute(
                "INSERT INTO capability_grant (clinic_id, staff_id, capability,"
                " tu_khoi) SELECT $1::uuid, $2::uuid, c.ma, c.work_pack"
                "  FROM capability c WHERE c.ma = $3",
                CLINIC,
                sid,
                q,
            )
    cache.quen(CLINIC, sid)
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


def _ma() -> str:
    return str(uuid.uuid4())


Lenh = Callable[[asyncpg.Pool, StaffIdentity], Awaitable[Any]]

LENH: list[tuple[str, str, Lenh]] = [
    (
        "check-in",
        "reception.checkin.perform",
        lambda p, ai: BookingService(p).apply_action(
            appointment_id=_ma(), action="checkin", identity=ai
        ),
    ),
    (
        "bắt đầu đo sinh hiệu",
        "vitals.measure",
        lambda p, ai: LuotKhamService(p).bat_dau_do_sinh_hieu(
            visit_id=_ma(), identity=ai
        ),
    ),
    (
        "lưu sinh hiệu",
        "vitals.measure",
        lambda p, ai: LuotKhamService(p).record_vitals(
            visit_id=_ma(), raw={"systolic": 120, "diastolic": 80}, identity=ai
        ),
    ),
    (
        "bắt đầu khám",
        "clinical.consult.perform",
        lambda p, ai: LuotKhamService(p).start_consultation(
            consultation_id=_ma(), identity=ai
        ),
    ),
    (
        "khám xong",
        "clinical.consult.perform",
        lambda p, ai: LuotKhamService(p).kham_xong(consultation_id=_ma(), identity=ai),
    ),
    (
        "ghi chú khám",
        "clinical.record.write",
        lambda p, ai: LuotKhamService(p).save_note(
            consultation_id=_ma(), body="ghi chú", identity=ai
        ),
    ),
    (
        "ghi bệnh án",
        "clinical.record.write",
        lambda p, ai: ClinicalRecordService(p).save(
            appointment_id=_ma(), clinic_patient_id=_ma(), identity=ai
        ),
    ),
    (
        "duyệt kết quả",
        "result.review.approve",
        lambda p, ai: LuotKhamService(p).duyet_ket_qua(
            order_id=_ma(), danh_gia=None, identity=ai
        ),
    ),
    (
        "thu tiền dịch vụ",
        "payment.service.collect",
        lambda p, ai: PaymentService(p).record_payment(
            visit_id=_ma(),
            kind="dich_vu",
            amount=None,
            clinic_patient_id=None,
            identity=ai,
            idempotency_key=_ma(),
        ),
    ),
]


def _vi_quyen(loi: BaseException) -> bool:
    return isinstance(loi, SafetyGateError) and "quyền" in str(loi)


@pytest.mark.parametrize(("ten", "quyen", "lenh"), LENH, ids=[x[0] for x in LENH])
async def test_khong_co_quyen_thi_bi_chan(
    pool: asyncpg.Pool, ten: str, quyen: str, lenh: Lenh
) -> None:
    ai = await _nguoi(pool, "CSKH", [])
    with pytest.raises(SafetyGateError) as loi:
        await lenh(pool, ai)
    assert _vi_quyen(loi.value), f"{ten}: bị chặn nhưng không vì quyền: {loi.value}"


@pytest.mark.parametrize(("ten", "quyen", "lenh"), LENH, ids=[x[0] for x in LENH])
async def test_co_quyen_thi_qua_cua_du_khong_dung_vai(
    pool: asyncpg.Pool, ten: str, quyen: str, lenh: Lenh
) -> None:
    """Vai CSKH chưa từng làm được các việc này — cấp quyền là làm được."""
    ai = await _nguoi(pool, "CSKH", [quyen])
    try:
        await lenh(pool, ai)
    except Exception as loi:  # noqa: BLE001 — mã giả nên phải vấp ở bước sau
        assert not _vi_quyen(loi), f"{ten}: có quyền mà vẫn bị chặn vì quyền: {loi}"


async def test_duyet_ket_qua_danh_sach_cung_hoi_quyen(pool: asyncpg.Pool) -> None:
    ai = await _nguoi(pool, "CSKH", [])
    with pytest.raises(SafetyGateError):
        await LuotKhamService(pool).ket_qua_cho_duyet(identity=ai)
    co = await _nguoi(pool, "CSKH", ["result.review.approve"])
    assert isinstance(await LuotKhamService(pool).ket_qua_cho_duyet(identity=co), dict)


async def test_dung_vi_tri_le_tan_hom_nay_khong_tu_cap_quyen(
    pool: asyncpg.Pool,
) -> None:
    """Được xếp vào vị trí/phòng KHÔNG tự sinh quyền (CORE, 23/09/2026).

    Tài khoản Điều dưỡng đứng Lễ tân hôm nay (vai theo vị trí = RECEPTION) mà
    chưa được cấp quyền check-in thì vẫn không check-in được.
    """
    dd = await _nguoi(pool, "NURSE_ULTRASOUND", [])
    dung_le_tan = dataclasses.replace(
        dd, vai_theo_vi_tri=frozenset({ClinicRole.RECEPTION})
    )
    with pytest.raises(SafetyGateError) as loi:
        await BookingService(pool).apply_action(
            appointment_id=_ma(), action="checkin", identity=dung_le_tan
        )
    assert _vi_quyen(loi.value)


async def test_nhom_mau_trong_code_khop_nhom_mau_he_thong_trong_database(
    pool: asyncpg.Pool,
) -> None:
    """Người mới vào được cấp theo nhóm mẫu TRONG DATABASE; màn quản lý và các
    bài kiểm đọc `PRESET` trong code. Lệch là người mới nhận một bộ quyền khác
    với bộ mọi người tưởng. (Migration 20260923000011 hứa có bài kiểm này.)"""
    rows = await pool.fetch(
        "SELECT ma, khoi FROM quyen_preset WHERE clinic_id = $1::uuid AND he_thong",
        CLINIC,
    )
    trong_db = {r["ma"]: set(r["khoi"]) for r in rows}
    for vai, khoi in PRESET.items():
        assert trong_db.get(vai, set()) == set(khoi), f"nhóm mẫu {vai} lệch"
