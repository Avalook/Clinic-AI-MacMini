"""Một cách trả lời cho endpoint đã nghỉ hưu: 410 ``ENDPOINT_RETIRED``.

Slice 1 (18/09/2026) nghỉ hưu các lối GHI của rail cũ (``service_log``,
``lab_result`` tạo/nhập, ``service_order_draft`` / ``order_services``). Rail mới
(``service_order`` → ``review_round`` → ``tep_ket_qua``) là nguồn duy nhất.

Không xoá cứng ngay (mẫu S0-6): endpoint vẫn trả lời, không ghi gì, và ghi log
người gọi — để biết còn ai dùng trước khi Đợt D xoá hẳn code.
"""

from __future__ import annotations

from typing import Any, NoReturn

import structlog
from fastapi import HTTPException

from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

#: Câu chỉ đường dùng chung cho các lối ghi đã nghỉ.
CHI_DINH_MOI = "Chỉ định đã chuyển sang khung Chỉ định của Bàn khám (luồng khám mới)."
KET_QUA_MOI = (
    "Kết quả gắn vào chỉ định ở phòng thực hiện, hoặc tải tệp kết quả của chỉ định."
)
LAM_O_PHONG = "Dịch vụ bắt đầu/xong ở hàng chờ phòng (luồng khám mới)."


def bao_da_nghi(
    *, endpoint: str, identity: StaffIdentity, thay_bang: str, **ref: Any
) -> NoReturn:
    """Ghi log người gọi rồi trả 410 kèm câu chỉ đường sang rail mới."""
    logger.warning(
        "endpoint_retired_called",
        endpoint=endpoint,
        staff_id=identity.staff_id,
        role=identity.role.value,
        **{k: str(v) for k, v in ref.items()},
    )
    raise HTTPException(
        status_code=410,
        detail={"error": "ENDPOINT_RETIRED", "message": thay_bang},
    )
