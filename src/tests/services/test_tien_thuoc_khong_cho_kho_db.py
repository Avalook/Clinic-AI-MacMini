"""Thu tiền thuốc KHÔNG chờ kho (công tắc tắt — chế độ staging/prod đang chạy).

Tuyền chốt 20/09/2026: thu tiền thuốc không chờ kho / chọn lô
(`CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY=0`). Lỗi bộ mô phỏng 20 khách bắt được
24/09/2026: lần thu như thế KHÔNG gắn lô nào, nhưng lệnh giao chỉ đi đường "giao
đúng lô đã bán" → mọi đơn thu theo cách mới KHÔNG GIAO ĐƯỢC THUỐC. Mọi bài kiểm
nhà thuốc trước đây đều BẬT công tắc, nên đúng chế độ đang chạy chưa ai kiểm.

Luật sau khi sửa (theo DỮ LIỆU, không theo công tắc): lần thu đã gắn lô → giao
đúng lô ấy; lần thu không gắn lô → giao thẳng từ lô dược sĩ chọn, vẫn không vượt
số kê và không vượt tồn.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import pytest

from clinicai.api.exceptions import ValidationError
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import (
    _chon,
    _dong_da_xac_dinh,
    _giao,
    _thu,
    _ton,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def test_thu_khong_chon_lo_van_giao_duoc_va_tru_kho(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    lo = await _nhap_lo(q, drug, 100)
    kq = await _thu(q)
    assert kq["status"] == "PAID"
    giao = await _giao(q, rx, lo, 10)
    assert float(giao["dispensed_qty"]) == 10
    assert await _ton(q, lo) == 90


async def test_da_chon_lo_truoc_khi_thu_van_giao_duoc(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 6)
    lo = await _nhap_lo(q, drug, 50)
    await _chon(q, rx, lo, 6)
    await _thu(q)
    await _giao(q, rx, lo, 4)
    giao = await _giao(q, rx, lo, 2)
    assert float(giao["dispensed_qty"]) == 6
    assert await _ton(q, lo) == 44


async def test_khong_giao_qua_so_ke(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 5)
    lo = await _nhap_lo(q, drug, 50)
    await _thu(q)
    with pytest.raises(ValidationError):
        await _giao(q, rx, lo, 6)
