"""Lỗi sinh hiệu mang TÊN Ô tới tận thân trả về (27/09/2026, đợt 3).

Màn đo trên điện thoại tô đúng ô lỗi theo ``truong`` máy chủ trả — không tự
đoán ô từ câu chữ. Bộ xử lý lỗi chung chỉ thêm ``truong`` khi lỗi có nó; mọi
lỗi khác giữ nguyên dạng ``{error, message}``.
"""

from __future__ import annotations

import json

from clinicai.api.exceptions import ValidationError
from clinicai.main import clinicai_exception_handler
from clinicai.services.sinh_hieu_service import LoiSinhHieuError


async def _than(exc: ValidationError) -> dict[str, object]:
    r = await clinicai_exception_handler(None, exc)  # type: ignore[arg-type]
    assert r.status_code == 422
    than: dict[str, object] = json.loads(bytes(r.body))
    return than


async def test_loi_co_truong_di_toi_than_tra_ve() -> None:
    than = await _than(
        LoiSinhHieuError(
            "Huyết áp tâm thu phải lớn hơn tâm trương.", ("systolic", "diastolic")
        )
    )
    assert than == {
        "error": "VALIDATION_ERROR",
        "message": "Huyết áp tâm thu phải lớn hơn tâm trương.",
        "truong": ["systolic", "diastolic"],
    }


async def test_loi_khong_gan_o_nao_giu_dang_cu() -> None:
    assert await _than(LoiSinhHieuError("Dữ liệu sinh hiệu không đúng dạng.")) == {
        "error": "VALIDATION_ERROR",
        "message": "Dữ liệu sinh hiệu không đúng dạng.",
    }
    assert await _than(ValidationError("x")) == {
        "error": "VALIDATION_ERROR",
        "message": "x",
    }
