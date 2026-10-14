"""Lego "Kế toán" (G5a, Tuyền 14/10/2026) — quyền THEO LEGO, không theo vai.

Kế toán = một gói khối Quản lý cấp cho tài khoản bất kỳ (vai tài khoản không
liên quan). Bài này khoá ba điều: (1) có khối thì xem tài chính đầy đủ mọi ca,
không cần lịch trực, nhưng KHÔNG thành Quản lý; (2) gói Kế toán không thu được
tiền — máy chủ chặn theo quyền của khối thu tiền; (3) khối không rò sang nhân
viên khác qua "mở full lego".
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import MAN, PRESET
from clinicai.services.doi_hinh_thuc_service import QUYEN_DOI
from clinicai.services.hoan_tien_service import co_quyen_hoan
from clinicai.services.payment_service import PaymentService
from clinicai.services.report_access_service import SHIFTS, ReportAccessService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_luot_kham_service_db import _nguoi as nguoi_theo_preset
from tests.services.test_quyen_lego_man_db import _nguoi as nguoi_theo_lego

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: Gói mẫu Kế toán đổi ra lego (đúng cái Quản lý bấm cấp).
GOI_KE_TOAN = ["bao_cao", "ke_toan", "ds_benh_nhan", "lich_lam_viec", "kho_vat_tu"]


async def _co(pool: asyncpg.Pool, ai: StaffIdentity, quyen: str) -> bool:
    async with pool.acquire() as conn:
        return await can(conn, ai, quyen)


async def test_goi_ke_toan_xem_tai_chinh_day_du_khong_can_lich(
    pool: asyncpg.Pool,
) -> None:
    # Vai tài khoản là CSKH — cố ý KHÔNG liên quan: quyền đến từ lego.
    ke_toan = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)
    svc = ReportAccessService(pool)
    acc = await svc.access(ke_toan, None)
    assert acc["tai_chinh"] and acc["legacy"] and acc["tai_chinh_day_du"]
    assert acc["ke_toan"] is True
    assert acc["cac_ca"] == list(SHIFTS)
    # Không có lịch trực nào mà vẫn qua cổng báo cáo mọi ngày / mọi ca.
    await svc.authorize(
        ke_toan, tu="2026-01-05", den="2026-01-06", ca="SANG", co_so=None
    )
    # Nhưng KHÔNG là Quản lý: cài đặt báo cáo vẫn chỉ Quản lý.
    assert acc["quan_ly"] is False
    with pytest.raises(SafetyGateError):
        await svc.settings(ke_toan)


async def test_thieu_khoi_ke_toan_van_theo_luat_cu(pool: asyncpg.Pool) -> None:
    """Có "Báo cáo" mà không có "Kế toán" → vẫn bị phạm vi lịch trực như trước."""
    khac = await nguoi_theo_lego(pool, "CSKH", ["bao_cao", "ds_benh_nhan"])
    acc = await ReportAccessService(pool).access(khac, None)
    assert not acc["tai_chinh"] and not acc["legacy"] and acc["ke_toan"] is False
    with pytest.raises(SafetyGateError):
        await ReportAccessService(pool).authorize(
            khac, tu="2026-01-05", den="2026-01-05", ca="SANG", co_so=None
        )


@pytest.mark.parametrize("kind", ["dich_vu", "thuoc"])
async def test_goi_ke_toan_khong_thu_tien_may_chu_chan(
    pool: asyncpg.Pool, kind: str
) -> None:
    ke_toan = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)
    assert not await _co(pool, ke_toan, "payment.service.collect")
    assert not await _co(pool, ke_toan, "payment.medicine.collect")
    svc = PaymentService(pool)
    # Cổng chung của thu / huỷ / xác minh một loại tiền.
    with pytest.raises(SafetyGateError):
        await svc._assert_kind_allowed(
            kind, ke_toan, "00000000-0000-0000-0000-000000000001"
        )
    # Lệnh thu thật: bị chặn ở cổng quyền, không phải vì lý do khác.
    with pytest.raises(SafetyGateError) as e:
        await svc.record_payment(
            visit_id="00000000-0000-0000-0000-000000000001",
            kind=kind,
            amount=100_000,
            clinic_patient_id=None,
            identity=ke_toan,
            idempotency_key=f"ke-toan-khong-thu-{kind}",
        )
    assert "quyền" in str(e.value).lower()


async def test_goi_ke_toan_khong_hoan_doi_hinh_thuc_ghi_no(
    pool: asyncpg.Pool,
) -> None:
    """Mọi lệnh tiền khác ngoài thu: hoàn · đổi hình thức · ghi nợ đều đòi quyền
    của khối thu tiền / tiếp đón — gói Kế toán không có."""
    ke_toan = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)
    async with pool.acquire() as conn:
        assert not await co_quyen_hoan(conn, ke_toan)
        assert not await co_quyen_hoan(conn, ke_toan, "dich_vu")
        assert not await co_quyen_hoan(conn, ke_toan, "thuoc")
        for quyen in QUYEN_DOI:
            assert not await can(conn, ke_toan, quyen)
        # Ghi nợ / huỷ nợ gác bằng quyền tiếp đón.
        assert not await can(conn, ke_toan, "reception.checkin.perform")


async def test_nhan_vien_mo_full_khong_tu_co_khoi_ke_toan(
    pool: asyncpg.Pool,
) -> None:
    """Mở full lego phát MỌI khối trừ khối chỉ-Quản-lý: kế toán phải nằm ngoài."""
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        for vai in ("CASHIER", "TRUONG_CA", "RECEPTION", "CSKH"):
            ai = await nguoi_theo_preset(conn, loc, vai)
            assert not await can(conn, ai, "accounting.finance.full"), vai
            # Còn thu tiền được như cũ (không ai mất việc).
            if vai in ("CASHIER", "RECEPTION"):
                assert await can(conn, ai, "payment.service.collect"), vai


async def test_quan_ly_co_khoi_ke_toan_va_goi_mau_khop_ma(
    pool: asyncpg.Pool,
) -> None:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        ql = await nguoi_theo_preset(conn, loc, "MANAGEMENT")
        assert await can(conn, ql, "accounting.finance.full")
        goi = await conn.fetchrow(
            "SELECT khoi, he_thong FROM quyen_preset"
            " WHERE clinic_id = $1::uuid AND ma = 'KE_TOAN'",
            CLINIC,
        )
    assert goi is not None and goi["he_thong"] is True
    assert sorted(goi["khoi"]) == sorted(PRESET["KE_TOAN"]) == sorted(GOI_KE_TOAN)
    # Gói Kế toán KHÔNG chứa khối thu tiền; lego "Kế toán" có đủ khối của nó.
    assert not {"thu_tien_dv", "thu_tien_thuoc"} & set(goi["khoi"])
    assert MAN["ke_toan"].khoi == ["ke_toan"]
