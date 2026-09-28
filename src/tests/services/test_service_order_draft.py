"""Chỉ định thư ký nhập chờ bác sĩ duyệt (Tuyền chốt 15/09/2026).

Bác sĩ đọc, thư ký y khoa nhập; màn bác sĩ hiện song song; bác sĩ duyệt mới
gửi phòng. Chưa duyệt chỉ bác sĩ và thư ký thấy. Hành vi đầy đủ đã chạy thật
trên Postgres (smoke 15/09: 2 lần nhập → 1 bản nháp, duyệt bản cũ bị chặn, thư
ký/bác sĩ khác không duyệt được, duyệt đúng bản → việc về đúng 2 phòng). Các bài
dưới canh những chốt nằm TRƯỚC database, chạy được trong CI.
"""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import MagicMock

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.service_order_service import ServiceOrderService
from tests.quyen_gia import PoolGia, chot_bac_si_theo_nhom_mau


def _identity(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id="11111111-1111-4111-8111-111111111111",
        auth_user_id="u1",
        full_name="Người thử",
        department=role.value,
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


VISIT = "22222222-2222-4222-8222-222222222222"


def test_thu_ky_khong_tao_viec_that() -> None:
    pool = MagicMock()
    with pytest.raises(SafetyGateError):
        asyncio.run(
            ServiceOrderService(pool).create(
                visit_id=VISIT, codes=["SA"], identity=_identity(ClinicRole.TKYK)
            )
        )
    pool.acquire.assert_not_called()


@pytest.mark.parametrize("role", [ClinicRole.CSKH, ClinicRole.CASHIER])
def test_khong_co_quyen_chi_dinh_thi_khong_duyet(
    role: ClinicRole, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 28/09/2026: duyệt nháp hỏi QUYỀN chỉ định, không hỏi vai — thư ký / điều
    # dưỡng cùng phòng duyệt được như bác sĩ; người không có quyền thì không.
    chot_bac_si_theo_nhom_mau(monkeypatch)
    with pytest.raises(SafetyGateError):
        asyncio.run(
            ServiceOrderService(PoolGia()).approve_draft(  # type: ignore[arg-type]
                visit_id=VISIT, expected_version=1, identity=_identity(role)
            )
        )


def test_dieu_duong_khong_doc_duoc_nhap() -> None:
    with pytest.raises(SafetyGateError):
        asyncio.run(
            ServiceOrderService(MagicMock()).get_draft(
                visit_id=VISIT, identity=_identity(ClinicRole.NURSE_ULTRASOUND)
            )
        )


def test_duyet_kiem_phien_ban_va_bac_si_phu_trach_truoc_khi_tao_viec() -> None:
    ma = inspect.getsource(ServiceOrderService.approve_draft)
    tao_viec = ma.index("order_services(")
    assert ma.index('nhap["version"] != expected_version') < tao_viec
    assert ma.index("attending_doctor_id") < tao_viec
    assert ma.index("approved_at = now()") > tao_viec, "đánh dấu duyệt sau khi có việc"
