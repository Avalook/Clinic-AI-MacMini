"""Vai KẾ TOÁN `ACCOUNTANT` (Tuyền 16/10/2026) — một NHÃN vai, KHÔNG phải quyền.

Khoá năm điều, trên Postgres thật (migration 20261016400000 áp vào DB tạm):
  1. Tạo nhân sự vai ACCOUNTANT qua service và qua API thật: có dòng
     `clinic_membership`/`staff` đúng vai, và được CẤP SẴN đúng gói mẫu "Kế toán"
     (khối `ke_toan` có cả quyền xem tài chính lẫn đặt thuế) — không hơn.
  2. Có lego Kế toán thì ghi công ty xuất hoá đơn được, xem/đặt thuế được.
  3. KHÔNG có lego thì 403 (service lẫn API) — vai không tự cấp quyền nào.
  4. Vai không kéo theo vai vận hành nào qua lego (không thu tiền, không khám).
  5. Đầu vào rác: vai lạ / sai chữ hoa vẫn 422, database vẫn từ chối vai lạ.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import asyncpg
import httpx
import pytest
import pytest_asyncio
from pydantic import ValidationError as PydanticValidationError

from clinicai.api.identity import (
    VAI_KHONG_CAP_QUA_LICH,
    VAI_LAM_VIEC,
    ClinicRole,
    StaffIdentity,
    doc_vai_theo_lego,
    get_current_identity,
    la_noi_bo,
    role_from_department,
)
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import SafetyGateError
from clinicai.main import app
from clinicai.permissions import cache
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import PRESET, quyen_cua_khoi, vai_tu_lego
from clinicai.schemas.staff import PrimaryDepartment, StaffCreateDTO
from clinicai.services.hoa_don_cong_ty_service import HoaDonCongTyService
from clinicai.services.nhan_vai import nhan_vai
from clinicai.services.report_access_service import ReportAccessService
from clinicai.services.staff_service import StaffService
from tests.services.test_hoa_don_cong_ty_db import CT_A, _phieu
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_quyen_lego_man_db import _nguoi as nguoi_theo_lego
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: Quyền KHÔNG được đến từ vai Kế toán, dù tạo với gói mẫu của nó.
KHONG_DUOC_CAP = (
    "payment.service.collect",
    "payment.medicine.collect",
    "permission.manage",
    "staff.manage",
    "config.clinic.manage",
    "clinical.consult.perform",
    "booking.create",
)


async def _co_so(conn: asyncpg.Connection) -> str:
    return str(
        await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
    )


async def _danh_tinh(pool: asyncpg.Pool, staff_id: str, ten: str) -> StaffIdentity:
    """Danh tính y như đăng nhập thật: vai do lego quyết tính bằng hàm máy chủ."""
    async with pool.acquire() as conn:
        loc = await _co_so(conn)
    cache.quen(CLINIC, staff_id)
    return StaffIdentity(
        staff_id=staff_id,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department="ACCOUNTANT",
        role=ClinicRole.ACCOUNTANT,
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
        vai_theo_lego=await doc_vai_theo_lego(
            pool, CLINIC, staff_id, ClinicRole.ACCOUNTANT
        ),
    )


async def _tao_ke_toan_qua_service(pool: asyncpg.Pool) -> StaffIdentity:
    """Tạo nhân sự vai ACCOUNTANT bằng đúng đường màn "Thêm nhân viên"."""
    async with pool.acquire() as conn:
        loc = await _co_so(conn)
    ten = f"Kế toán thử {uuid.uuid4().hex[:6]}"
    dto = await StaffService(pool, CLINIC).create_staff(
        StaffCreateDTO(
            full_name=ten,
            primary_department=PrimaryDepartment.ACCOUNTANT,
            primary_location_id=UUID(loc),
        )
    )
    assert dto.primary_department == "ACCOUNTANT"
    return await _danh_tinh(pool, str(dto.id), ten)


async def _tao_ke_toan_tro_ngai(pool: asyncpg.Pool) -> StaffIdentity:
    """Tài khoản vai ACCOUNTANT KHÔNG có dòng cấp quyền nào (quản lý đã thu hết).

    Trigger `staff_ensure_default_membership` tự tạo membership từ vai của staff
    (nên CHECK ở CẢ HAI bảng phải có 'ACCOUNTANT'); không ai cấp quyền ở đây."""
    async with pool.acquire() as conn:
        loc = await _co_so(conn)
        ten = f"Kế toán trống {uuid.uuid4().hex[:6]}"
        sid = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id,"
            " is_active) VALUES ($1, 'ACCOUNTANT', $2::uuid, true) RETURNING id::text",
            ten,
            loc,
        )
        await conn.execute(
            "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
            " VALUES ($1::uuid, $2::uuid, 'ACCOUNTANT', true)"
            " ON CONFLICT ON CONSTRAINT uq_clinic_membership DO NOTHING",
            CLINIC,
            sid,
        )
    return await _danh_tinh(pool, str(sid), ten)


async def test_tao_nhan_su_ke_toan_duoc_cap_san_dung_goi_ke_toan(
    pool: asyncpg.Pool,
) -> None:
    ke_toan = await _tao_ke_toan_qua_service(pool)
    async with pool.acquire() as conn:
        role = await conn.fetchval(
            "SELECT role FROM clinic_membership WHERE staff_id = $1::uuid",
            ke_toan.staff_id,
        )
        khoi_db = await conn.fetchval(
            "SELECT khoi FROM quyen_preset WHERE clinic_id = $1::uuid"
            " AND ma = 'ACCOUNTANT' AND he_thong AND active",
            CLINIC,
        )
        duoc_cap = {
            r["capability"]
            for r in await conn.fetch(
                "SELECT capability FROM capability_grant"
                " WHERE staff_id = $1::uuid AND revoked_at IS NULL",
                ke_toan.staff_id,
            )
        }
        assert role == "ACCOUNTANT"
        # Nhóm mẫu trong DB = nhóm trong code = gói "Kế toán" (không thu tiền).
        assert (
            sorted(khoi_db) == sorted(PRESET["ACCOUNTANT"]) == sorted(PRESET["KE_TOAN"])
        )
        mong_doi = {q for k in PRESET["ACCOUNTANT"] for q in quyen_cua_khoi(k)}
        assert duoc_cap == mong_doi
        # Việc kèm: khối Kế toán có ĐỦ cả xem tài chính lẫn đặt thuế (/ke-toan
        # tab Thuế suất) — không phải thêm gì.
        assert {"accounting.finance.full", "accounting.tax.manage"} <= duoc_cap
        for q in KHONG_DUOC_CAP:
            assert not await can(conn, ke_toan, q), q
    # Nhãn tiếng Việt do máy chủ trả cho bảng lịch.
    assert nhan_vai("ACCOUNTANT") == ("Kế toán", "Kế toán")


async def test_ke_toan_co_lego_ghi_cong_ty_xuat_hoa_don_duoc(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    ke_toan = await _tao_ke_toan_qua_service(pool)
    c = await _phieu(pool, q, q.thu_ngan)
    svc = HoaDonCongTyService(pool)
    r = await svc.ghi_hoa_don(identity=ke_toan, payment_cycle_id=c, **CT_A)
    assert r["doi"] is True
    assert (await svc.doc_hoa_don(identity=ke_toan, payment_cycle_id=c))["cong_ty"][
        "ten_cong_ty"
    ] == CT_A["ten_cong_ty"]
    acc = await ReportAccessService(pool).access(ke_toan, None)
    assert acc["ke_toan"] is True and acc["quan_ly"] is False


async def test_ke_toan_khong_co_lego_bi_chan_vai_khong_tu_cap_quyen(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    trong = await _tao_ke_toan_tro_ngai(pool)
    c = await _phieu(pool, q, q.thu_ngan)
    svc = HoaDonCongTyService(pool)
    for goi in (
        svc.ghi_hoa_don(identity=trong, payment_cycle_id=c, **CT_A),
        svc.doc_hoa_don(identity=trong, payment_cycle_id=c),
        svc.bo_hoa_don(identity=trong, payment_cycle_id=c),
    ):
        with pytest.raises(SafetyGateError):
            await goi
    acc = await ReportAccessService(pool).access(trong, None)
    assert acc["ke_toan"] is False and acc["tai_chinh"] is False
    async with pool.acquire() as conn:
        for quyen in (
            "accounting.finance.full",
            "accounting.tax.manage",
            "report.view",
        ):
            assert not await can(conn, trong, quyen), quyen


async def test_vai_ke_toan_khong_keo_theo_vai_van_hanh_nao(
    pool: asyncpg.Pool,
) -> None:
    # Gói mẫu của vai không bật đủ lego của vai vận hành nào (không thu tiền,
    # không khám, không phát thuốc): `vai_theo_lego` rỗng thì mọi cửa hỏi vai
    # vận hành vẫn đóng.
    assert vai_tu_lego(PRESET["ACCOUNTANT"]) == frozenset()
    ke_toan = await _tao_ke_toan_qua_service(pool)
    assert ke_toan.vai_theo_lego == frozenset()
    assert ke_toan.role is ClinicRole.ACCOUNTANT
    for vai in (
        ClinicRole.CASHIER,
        ClinicRole.CASHIER_DV,
        ClinicRole.CASHIER_THUOC,
        ClinicRole.DOCTOR,
        ClinicRole.PHARMACIST,
        ClinicRole.MANAGEMENT,
        ClinicRole.RECEPTION,
    ):
        assert not ke_toan.co_vai({vai}), vai


def test_vai_ke_toan_la_thanh_vien_noi_bo_nhu_vai_thuong() -> None:
    assert role_from_department("ACCOUNTANT") is ClinicRole.ACCOUNTANT
    assert ClinicRole.ACCOUNTANT in VAI_LAM_VIEC
    # Không là người ngoài (PARTNER) cũng không là cái tivi (DISPLAY).
    assert ClinicRole.PARTNER not in VAI_LAM_VIEC
    assert ClinicRole.DISPLAY not in VAI_LAM_VIEC
    assert la_noi_bo(
        StaffIdentity(
            staff_id="s",
            auth_user_id="a",
            full_name="KT",
            department="ACCOUNTANT",
            role=ClinicRole.ACCOUNTANT,
            clinic_id="c",
            location_id="l",
            location_name="x",
        )
    )
    # Không vai lạ lọt qua: mã lạ / rác vẫn 403 như trước.
    for rac in ("ACCOUNTAN", "accountant", " ACCOUNTANT", "KE_TOAN", "", None):
        with pytest.raises(Exception, match="403|không hợp lệ"):
            role_from_department(rac)
    assert ClinicRole.ACCOUNTANT not in VAI_KHONG_CAP_QUA_LICH  # như CSKH/Dược sĩ


def test_dto_nhan_ke_toan_va_chan_vai_rac() -> None:
    ok = StaffCreateDTO(
        full_name="A",
        primary_department="ACCOUNTANT",  # type: ignore[arg-type]
    )
    assert ok.primary_department is PrimaryDepartment.ACCOUNTANT
    for rac in ("accountant", "ACCOUNTANT ", "KE_TOAN", "ACCOUNTANTS", "", None, 7):
        with pytest.raises(PydanticValidationError):
            StaffCreateDTO(full_name="A", primary_department=rac)  # type: ignore[arg-type]


async def test_database_nhan_ke_toan_va_van_tu_choi_vai_la(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        loc = await _co_so(conn)
        sid = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id,"
            " is_active) VALUES ('KT ràng buộc', 'ACCOUNTANT', $1::uuid, true)"
            " RETURNING id::text",
            loc,
        )
        for ban in ("ACCOUNTANTS", "accountant", "KE_TOAN"):
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO clinic_membership (clinic_id, staff_id, role,"
                    " is_active) VALUES ($1::uuid, $2::uuid, $3, true)",
                    CLINIC,
                    sid,
                    ban,
                )
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "UPDATE staff SET primary_department = $2 WHERE id = $1::uuid",
                    sid,
                    ban,
                )
        # 14 vai cũ vẫn hợp lệ (migration chỉ THÊM, không bỏ vai nào).
        for cu in (
            "DOCTOR", "ULTRASOUND_DOCTOR", "NURSE_ULTRASOUND", "RECEPTION", "CSKH",
            "MANAGEMENT", "CASHIER", "CASHIER_THUOC", "CASHIER_DV", "TKYK",
            "TRUONG_CA", "PHARMACIST", "DISPLAY", "PARTNER",
        ):  # fmt: skip
            await conn.execute(
                "UPDATE staff SET primary_department = $2 WHERE id = $1::uuid",
                sid,
                cu,
            )


@pytest_asyncio.fixture
async def client(pool: asyncpg.Pool) -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_db_pool] = lambda: pool
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    app.dependency_overrides.pop(get_db_pool, None)
    app.dependency_overrides.pop(get_current_identity, None)


def _ai_la(ai: StaffIdentity) -> None:
    app.dependency_overrides[get_current_identity] = lambda: ai


async def test_api_them_nhan_vien_vai_ke_toan_201_vai_la_422(
    pool: asyncpg.Pool, client: httpx.AsyncClient
) -> None:
    quan_ly_nhan_su = await nguoi_theo_lego(pool, "MANAGEMENT", ["nhan_su"])
    _ai_la(quan_ly_nhan_su)
    async with pool.acquire() as conn:
        loc = await _co_so(conn)
    body: dict[str, Any] = {
        "full_name": f"KT api {uuid.uuid4().hex[:5]}",
        "primary_department": "ACCOUNTANT",
        "primary_location_id": loc,
    }
    res = await client.post("/api/v1/staff", json=body)
    assert res.status_code == 201, res.text
    assert res.json()["primary_department"] == "ACCOUNTANT"
    for rac in ("KE_TOAN", "accountant", "ACCOUNTANT_", "", None, 5):
        res = await client.post(
            "/api/v1/staff", json={**body, "primary_department": rac}
        )
        assert res.status_code == 422, (rac, res.text)


async def test_api_vai_ke_toan_co_lego_200_khong_lego_403(
    pool: asyncpg.Pool, client: httpx.AsyncClient
) -> None:
    co_lego = await _tao_ke_toan_qua_service(pool)
    khong_lego = await _tao_ke_toan_tro_ngai(pool)
    _ai_la(co_lego)
    res = await client.get("/api/v1/ke-toan/thue-suat")
    assert res.status_code == 200, res.text
    _ai_la(khong_lego)
    res = await client.get("/api/v1/ke-toan/thue-suat")
    assert res.status_code == 403, res.text
    res = await client.put(
        "/api/v1/ke-toan/thue-suat/nhom/DICH_VU", json={"thue_suat": "8"}
    )
    assert res.status_code == 403, res.text
    # Cửa "mọi thành viên nội bộ" thì ACCOUNTANT vào được (không bị 403 oan).
    for duong in ("/api/v1/feature-mode", "/api/v1/reports/access"):
        res = await client.get(duong)
        assert res.status_code == 200, (duong, res.text)
