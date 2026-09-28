"""Giao thuốc KHÔNG cần lô, gán lô sau (Tuyền 28/09/2026).

"Chưa cần quan tâm lô nào, số lượng điền tay … áp dụng bán luôn, lô nhập và
gán sau." Trước bản này quầy không giao được khi kho chưa có lô: màn chỉ hiện
"Nhập lô ở Kho thuốc trước" và không có nút giao nào.

Luật: lần thu tiền thuốc KHÔNG gắn lô → giao không chọn lô được (không quá số
kê, không quá số mua); kho CHƯA trừ, dòng vào sổ `thuoc_giao_chua_gan_lo`; gán
lô sau → ghi DISPENSE, tồn lô giảm; mỗi lần giao gán đúng một lần.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services import ban_thuoc_service as bt
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import (
    _chon,
    _dong_da_xac_dinh,
    _thu,
    _ton,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    # Chế độ đang chạy trên prod: thu tiền thuốc không chờ kho.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _dong(q: Quay, rx: str) -> dict[str, Any]:
    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    luot = next(g for g in man["luot"] if g["visit_id"] == q.visit_id)
    return next(d for d in luot["dong"] if d["id"] == rx)


async def _giao_khong_lo(q: Quay, rx: str, so: Any) -> dict[str, Any]:
    return await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=so
    )


async def _cho(q: Quay) -> list[dict[str, Any]]:
    kq = await PharmacyService(q.pool).cho_gan_lo(identity=q.duoc_si)
    return list(kq["dong"])


async def test_kho_chua_co_lo_van_thu_va_giao_duoc(q: Quay) -> None:
    rx, _drug = await _dong_da_xac_dinh(q, 10)
    await _thu(q)
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is True
    kq = await _giao_khong_lo(q, rx, 4)
    assert float(kq["dispensed_qty"]) == 4
    # Còn phần bán chưa giao → nút vẫn còn; giao nốt thì hết nút.
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is True
    await _giao_khong_lo(q, rx, 6)
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is False
    cho = [d for d in await _cho(q) if d["prescription_id"] == rx]
    assert sorted(float(d["so_luong"]) for d in cho) == [4.0, 6.0]


async def test_khong_giao_qua_so_ke(q: Quay) -> None:
    rx, _drug = await _dong_da_xac_dinh(q, 5)
    await _thu(q)
    with pytest.raises(ValidationError):
        await _giao_khong_lo(q, rx, 6)


async def test_gan_lo_sau_thi_kho_moi_tru_va_chi_gan_mot_lan(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 8)
    await _thu(q)
    await _giao_khong_lo(q, rx, 8)
    lo = await _nhap_lo(q, drug, 30)
    assert await _ton(q, lo) == 30, "giao không lô chưa trừ kho"
    dong = next(d for d in await _cho(q) if d["prescription_id"] == rx)
    assert lo in {b["drug_batch_id"] for b in dong["lo_gan_duoc"]}
    svc = PharmacyService(q.pool)
    await svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo)
    assert await _ton(q, lo) == 22
    assert dong["id"] not in {d["id"] for d in await _cho(q)}
    with pytest.raises(ConflictError):
        await svc.gan_lo_da_giao(
            identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo
        )


async def test_da_chon_lo_nhung_lan_thu_khong_gan_lo_van_giao_khong_lo(
    q: Quay,
) -> None:
    # Thu không chờ kho: lô đã chọn KHÔNG gắn vào lần thu → trước bản này dòng
    # không có nút giao nào. Nay giao không lô được.
    rx, drug = await _dong_da_xac_dinh(q, 6)
    lo = await _nhap_lo(q, drug, 50)
    await _chon(q, rx, lo, 6)
    await _thu(q)
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is True
    await _giao_khong_lo(q, rx, 6)


async def test_dong_da_ban_theo_lo_thi_phai_giao_dung_lo(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Thu CHỜ kho (công tắc bật): lần thu gắn lô → giao đúng lô, không giao trơn.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    rx, drug = await _dong_da_xac_dinh(q, 6)
    lo = await _nhap_lo(q, drug, 50)
    await _chon(q, rx, lo, 6)
    await _thu(q)
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is False
    with pytest.raises(ValidationError):
        await _giao_khong_lo(q, rx, 6)
