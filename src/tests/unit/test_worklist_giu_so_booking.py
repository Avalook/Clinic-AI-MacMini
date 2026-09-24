"""response_model của /work-items phải GIỮ số tiếp đón + số booking (24/09/2026).

Service đã trả hai trường này từ 23/09, nhưng schema thiếu nên FastAPI lọc bỏ:
màn lễ tân hiện số riêng của bác sĩ và "Số booking —". Bắt được khi bấm thật.
"""

from __future__ import annotations

from clinicai.api.v1.routers.work_items import WorklistItem


def test_schema_worklist_co_so_tiep_don_va_so_booking() -> None:
    cot = set(WorklistItem.model_fields)
    assert {"so_tiep_don", "so_booking", "queue_number"} <= cot
