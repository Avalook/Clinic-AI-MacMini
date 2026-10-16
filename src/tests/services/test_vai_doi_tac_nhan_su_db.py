"""Tài khoản ĐỐI TÁC tạo được ở màn Nhân sự (Tuyền 16/10/2026) — Postgres thật.

Đối tác vào làm ở /doi-tac: tạo nhân sự vai PARTNER qua đúng đường "Thêm nhân viên"
→ có dòng `staff` + `clinic_membership` đúng vai, được cấp SẴN gói mẫu "Đối tác"
(chỉ cửa `partner.work`), KHÔNG kéo theo quyền thu tiền, xem tài chính, cấu hình.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import asyncpg
import pytest
from pydantic import ValidationError as PydanticValidationError

from clinicai.api.identity import ClinicRole, StaffIdentity, doc_vai_theo_lego
from clinicai.permissions import cache
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import PRESET
from clinicai.schemas.staff import PrimaryDepartment, StaffCreateDTO
from clinicai.services.staff_service import StaffService
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: Đối tác KHÔNG được có — tiền của phòng khám, hồ sơ khách, cấu hình.
KHONG_DUOC_CAP = (
    "payment.service.collect",
    "payment.medicine.collect",
    "accounting.finance.full",
    "report.view",
    "config.clinic.manage",
    "permission.manage",
    "staff.manage",
    "clinical.consult.perform",
    "booking.create",
)


async def _tao_doi_tac(pool: asyncpg.Pool) -> tuple[StaffIdentity, str]:
    async with pool.acquire() as conn:
        loc = str(
            await conn.fetchval(
                "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
                " AND is_active ORDER BY created_at, id LIMIT 1",
                CLINIC,
            )
        )
    ten = f"Đối tác thử {uuid.uuid4().hex[:6]}"
    dto = await StaffService(pool, CLINIC).create_staff(
        StaffCreateDTO(
            full_name=ten,
            primary_department=PrimaryDepartment.PARTNER,
            primary_location_id=UUID(loc),
        )
    )
    assert dto.primary_department == "PARTNER"
    sid = str(dto.id)
    cache.quen(CLINIC, sid)
    return (
        StaffIdentity(
            staff_id=sid,
            auth_user_id=str(uuid.uuid4()),
            full_name=ten,
            department="PARTNER",
            role=ClinicRole.PARTNER,
            clinic_id=CLINIC,
            location_id=loc,
            location_name="Cơ sở test",
            vai_theo_lego=await doc_vai_theo_lego(
                pool, CLINIC, sid, ClinicRole.PARTNER
            ),
        ),
        sid,
    )


async def test_tao_nhan_su_doi_tac_duoc_cap_san_dung_cua_doi_tac(
    pool: asyncpg.Pool,
) -> None:
    doi_tac, sid = await _tao_doi_tac(pool)
    vai = await pool.fetchval(
        "SELECT role FROM clinic_membership WHERE clinic_id=$1::uuid"
        " AND staff_id=$2::uuid",
        CLINIC,
        sid,
    )
    assert vai == "PARTNER"
    assert PRESET["PARTNER"] == ["doi_tac"]  # gói mẫu: đúng một khối
    async with pool.acquire() as conn:
        assert await can(conn, doi_tac, "partner.work")
        for quyen in KHONG_DUOC_CAP:
            assert not await can(conn, doi_tac, quyen), quyen


def test_vai_la_hoac_sai_chu_hoa_van_bi_tu_choi() -> None:
    for xau in ("Partner", "DOI_TAC", "partner "):
        with pytest.raises(PydanticValidationError):
            StaffCreateDTO(
                full_name="X",
                primary_department=xau,  # type: ignore[arg-type]
                primary_location_id=uuid.uuid4(),
            )
