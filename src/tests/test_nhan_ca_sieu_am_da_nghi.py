"""S0-6 (18/09/2026): "nhận ca" siêu âm của rail cũ đã nghỉ — trả 410.

Endpoint `/ultrasound/queue/{id}/nhan` ghi đè người đã nhận (người sau thắng,
không 409). Không màn nào gọi nó nữa: màn Phòng siêu âm dùng rail mới
(`LuotKhamService.start_service`, khoá dòng + 409). Target Contract 18/09:
không sửa logic cũ, không xoá cứng ngay — trả 410 ENDPOINT_RETIRED và ghi log
người gọi; xoá hẳn khi một thời gian không còn ai gọi.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.ultrasound import NhanCaRequest, nhan_ca_sieu_am


@pytest.mark.asyncio
async def test_nhan_ca_rail_cu_tra_410_va_khong_ghi_gi() -> None:
    ai = StaffIdentity(
        staff_id="20000000-0000-4000-8000-000000000001",
        auth_user_id="30000000-0000-4000-8000-000000000001",
        full_name="BS SA",
        department="ULTRASOUND_DOCTOR",
        role=ClinicRole.ULTRASOUND_DOCTOR,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )
    with (
        patch(
            "clinicai.api.v1.routers.ultrasound.UltrasoundBoardService.nhan_ca",
            new=AsyncMock(),
        ) as nhan_ca,
        patch("clinicai.api.v1.routers.ultrasound.logger") as log,
    ):
        with pytest.raises(HTTPException) as e:
            await nhan_ca_sieu_am(
                work_item_id=UUID("10000000-0000-4000-8000-000000000001"),
                body=NhanCaRequest(),
                identity=ai,
                pool=AsyncMock(),
            )
    assert e.value.status_code == 410
    assert isinstance(e.value.detail, dict)
    assert e.value.detail["error"] == "ENDPOINT_RETIRED"
    nhan_ca.assert_not_called()
    log.warning.assert_called_once()
    assert log.warning.call_args.kwargs["staff_id"] == ai.staff_id
