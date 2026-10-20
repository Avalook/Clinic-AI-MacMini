"""Pure boundary probe for booking datetimes without a timezone offset.

Imports the request model and service helper from the pinned-main source tree.
No database, network, production credentials, or patient data are used.
"""

from uuid import uuid4

import pytest

from clinicai.api.v1.routers.booking import BookingRequest
from clinicai.services.booking_service import _chan_dat_vao_qua_khu


def test_booking_model_accepts_naive_time_then_service_comparison_raises() -> None:
    body = BookingRequest(
        clinic_patient_id=uuid4(),
        service_type_id=uuid4(),
        slot_start="2026-10-20T09:00:00",
        slot_end="2026-10-20T09:30:00",
    )

    assert body.slot_end.tzinfo is None
    with pytest.raises(TypeError):
        _chan_dat_vao_qua_khu(body.slot_end)
