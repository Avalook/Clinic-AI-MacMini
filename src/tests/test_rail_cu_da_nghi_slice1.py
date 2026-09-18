"""Slice 1 (18/09/2026): mọi lối GHI của rail cũ trả 410 và không chạm database.

Rail mới (service_order → review_round → tep_ket_qua) là nguồn duy nhất. Các
endpoint dưới đây ghi ``service_log``, ``lab_result`` hoặc ``service_order_draft``
/ ``work_item.payload`` — không màn chuẩn nào còn gọi (nút "Chỉ định CLS" trong
bệnh án đã gỡ cùng lượt). Mỗi endpoint: 410 ENDPOINT_RETIRED, pool không được
dùng tới, log ghi người gọi.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers import lab, service_log, work_items

AI = StaffIdentity(
    staff_id="20000000-0000-4000-8000-000000000001",
    auth_user_id="30000000-0000-4000-8000-000000000001",
    full_name="BS",
    department="DOCTOR",
    role=ClinicRole.DOCTOR,
    clinic_id="a0000000-0000-4000-8000-000000000001",
    location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
    location_name="Kim Ngưu",
)
ID = UUID("10000000-0000-4000-8000-000000000001")

DA_NGHI = [
    lab.order_lab_test,
    lab.enter_lab_result,
    service_log.create_service_item,
    service_log.progress_service_item,
    service_log.create_sono_row,
    service_log.progress_sono_row,
    service_log.remove_sono_row,
    work_items.order_services,
    work_items.remove_service_order,
    work_items.add_to_service_order_draft,
    work_items.replace_service_order_draft,
    work_items.approve_service_order_draft,
    work_items.discard_service_order_draft,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("ham", DA_NGHI, ids=lambda f: f.__name__)
async def test_loi_ghi_rail_cu_tra_410_khong_cham_db(ham: Any) -> None:
    pool = MagicMock()
    kwargs: dict[str, Any] = {}
    for ten in inspect.signature(ham).parameters:
        if ten == "identity":
            kwargs[ten] = AI
        elif ten == "pool":
            kwargs[ten] = pool
        elif ten == "body":
            kwargs[ten] = MagicMock()
        else:
            kwargs[ten] = ID
    with patch("clinicai.api.nghi_huu.logger") as log:
        with pytest.raises(HTTPException) as e:
            await ham(**kwargs)
    assert e.value.status_code == 410
    assert isinstance(e.value.detail, dict)
    assert e.value.detail["error"] == "ENDPOINT_RETIRED"
    assert pool.mock_calls == []
    assert log.warning.call_args.kwargs["staff_id"] == AI.staff_id
