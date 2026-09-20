"""Mã dòng đơn thuốc đi-về nguyên vẹn qua request Lưu bệnh án.

Hành vi lưu đơn (giữ id, id lạ / lặp, bản cũ thiếu id, không ghi dở dang, mức
dấu vết A/B/C) chạy trên DB thật ở
`test_tien_thuoc_cp6_dinh_chinh_service_db.py` — thay cho các ca trước đây chạy
trên kết nối giả (CP6 bước 4b, 20/09/2026).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError as ModelValidationError

from clinicai.api.v1.routers.clinical_records import (
    ClinicalRecordSaveRequest,
    PrescriptionItem,
)

RX_A = "40000000-0000-0000-0000-000000000001"


def submitted(rx_id: Any = None) -> dict[str, Any]:
    return {
        "id": rx_id,
        "drug_name": "Drug A",
        "quantity": "10 viên",
        "dosage": "Morning",
        "caution": "After food",
    }


def test_request_retains_valid_prescription_uuid() -> None:
    item = PrescriptionItem.model_validate(submitted(RX_A))
    assert item.model_dump()["id"] == UUID(RX_A)
    assert PrescriptionItem.model_validate(submitted()).model_dump()["id"] is None


def test_request_rejects_malformed_prescription_uuid() -> None:
    with pytest.raises(ModelValidationError):
        PrescriptionItem.model_validate(submitted("not-a-uuid"))


def test_request_mang_ly_do_dinh_chinh() -> None:
    body = ClinicalRecordSaveRequest.model_validate(
        {
            "appointment_id": RX_A,
            "clinic_patient_id": RX_A,
            "prescriptions": [submitted(RX_A)],
            "prescription_correction_reason": "Đổi thuốc vì dị ứng",
        }
    )
    assert body.prescription_correction_reason == "Đổi thuốc vì dị ứng"
    with pytest.raises(ModelValidationError):
        ClinicalRecordSaveRequest.model_validate(
            {
                "appointment_id": RX_A,
                "clinic_patient_id": RX_A,
                "prescription_correction_reason": "x" * 1001,
            }
        )
