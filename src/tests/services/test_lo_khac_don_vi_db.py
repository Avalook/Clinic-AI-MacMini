"""Màn "Đã giao, chưa trừ kho" nói ra LÔ KHÁC ĐƠN VỊ (17/10/2026).

Ca đã bấm thật: Androgel nhập 6 hộp, bán theo gói. Giao không lô được, nhưng không
lô nào gắn được vì khác đơn vị — màn chỉ nói "Chưa có lô gán được", người dùng không
biết kho đang có 6 hộp. Máy chủ trả thêm `lo_khac_don_vi` để giải thích; luật gán lô
KHÔNG đổi (lô khác đơn vị vẫn không gắn được).
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q / co được import.
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_quay_db import Co, _don, co  # noqa: F401
from tests.services.test_tien_thuoc_cp1_db import q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _nhap(co: Co, drug: str, so: int, don_vi: str) -> str:
    kq = await PharmacyService(co.q.pool).nhap_lo(
        identity=co.ds,
        drug_catalog_id=drug,
        so_luong=so,
        batch_code=f"LO-{uuid.uuid4().hex[:8]}",
        expiry_date=hom_nay_vn() + timedelta(days=900),
        unit=don_vi,
    )
    return str(kq["drug_batch_id"])


async def _dong_cho(co: Co, rx: str) -> dict[str, Any]:
    cho = await PharmacyService(co.q.pool).cho_gan_lo(identity=co.ds)
    return next(d for d in cho["dong"] if d["prescription_id"] == rx)


async def test_lo_hop_giao_theo_vien_khong_gan_duoc_nhung_man_noi_ro_lo_hop(
    co: Co,
) -> None:
    rx, drug = await _don(co, 3)  # đơn kê theo viên
    await _thu(co.q)
    lo_hop = await _nhap(co, drug, 5, "hộp")
    svc = PharmacyService(co.q.pool)
    await svc.cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=None, so_luong=1
    )
    d = await _dong_cho(co, rx)
    assert d["lo_gan_duoc"] == [], "lô khác đơn vị vẫn KHÔNG gắn được (luật không đổi)"
    assert [(x["drug_batch_id"], x["unit"], x["ton"]) for x in d["lo_khac_don_vi"]] == [
        (lo_hop, "hộp", D(5))
    ]


async def test_co_lo_cung_don_vi_thi_gan_duoc_va_van_liet_ke_lo_khac(co: Co) -> None:
    rx, drug = await _don(co, 3)
    await _thu(co.q)
    await _nhap(co, drug, 5, "hộp")
    lo_vien = await _nhap(co, drug, 10, "viên")
    await PharmacyService(co.q.pool).cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=None, so_luong=1
    )
    d = await _dong_cho(co, rx)
    assert [x["drug_batch_id"] for x in d["lo_gan_duoc"]] == [lo_vien]
    assert [x["unit"] for x in d["lo_khac_don_vi"]] == ["hộp"]


async def test_khong_co_lo_khac_don_vi_thi_danh_sach_rong(co: Co) -> None:
    rx, drug = await _don(co, 3)
    await _thu(co.q)
    await _nhap(co, drug, 10, "viên")
    await PharmacyService(co.q.pool).cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=None, so_luong=1
    )
    d = await _dong_cho(co, rx)
    assert d["lo_khac_don_vi"] == []
