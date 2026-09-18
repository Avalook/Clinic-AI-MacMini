"""S0-4 (18/09/2026): phiếu chuyên khoa theo đúng phạm vi thư ký như bệnh án SOAP.

Trước bản này `ClinicalFormService.save_form` không gọi `kiem_thu_ky_duoc_lam`:
thư ký được phân cho BS A ghi được phiếu của khách BS B. Bệnh án SOAP thì đã chặn
(clinical_record_service.py). Chạy với MO_QUYEN_TAM_THOI TẮT (conftest) — trên
prod luật này chỉ có hiệu lực khi công tắc mở quyền tạm được tắt.
"""

from __future__ import annotations

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.clinical_form_service import ClinicalFormService
from tests.services.fake_sql import SqlConn, pool

CLINIC = "a0000000-0000-4000-8000-000000000001"
ME = "b0000000-0000-4000-8000-000000000001"
BS1 = "b0000000-0000-4000-8000-000000000002"
BS2 = "b0000000-0000-4000-8000-000000000003"
VISIT = "e0000000-0000-4000-8000-000000000001"


def who(role: ClinicRole, staff: str = ME) -> StaffIdentity:
    return StaffIdentity(
        staff_id=staff,
        auth_user_id=staff,
        full_name="x",
        department=role.value,
        role=role,
        clinic_id=CLINIC,
        location_id=CLINIC,
        location_name="CS",
    )


def _pool(bac_si_cua_luot: str) -> SqlConn:
    return pool(
        ("FROM public.thu_ky_bac_si", [BS1]),
        (
            "FROM visit v",
            {"visit_id": VISIT, "status": "OPEN", "bac_si": bac_si_cua_luot},
        ),
        ("clinical_form_catalogue", 1),
    )


@pytest.mark.asyncio
async def test_thu_ky_khong_ghi_phieu_cua_khach_bac_si_khac() -> None:
    p = _pool(BS2)
    with pytest.raises(SafetyGateError):
        await ClinicalFormService(p).save_form(
            visit_id=VISIT,
            service_code="NT",
            form_data={"ly_do": "x"},
            identity=who(ClinicRole.TKYK),
        )
    assert not p.da_goi("INSERT INTO clinical_form_response")


@pytest.mark.asyncio
async def test_thu_ky_ghi_phieu_cua_khach_bac_si_minh() -> None:
    p = _pool(BS1)
    await ClinicalFormService(p).save_form(
        visit_id=VISIT,
        service_code="NT",
        form_data={"ly_do": "x"},
        identity=who(ClinicRole.TKYK),
    )
    assert p.da_goi("INSERT INTO clinical_form_response")


@pytest.mark.asyncio
async def test_bac_si_khong_bi_kiem_pham_vi_thu_ky() -> None:
    p = _pool(BS2)
    await ClinicalFormService(p).save_form(
        visit_id=VISIT,
        service_code="NT",
        form_data={"ly_do": "x"},
        identity=who(ClinicRole.DOCTOR, BS1),
    )
    assert p.da_goi("INSERT INTO clinical_form_response")
