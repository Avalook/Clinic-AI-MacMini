"""Thu tiền thuốc xong là giao luôn — kho quầy trừ ngay lúc thu (16/11/2026).

* tiền mặt: thu xong → dòng đã giao đủ số mua, lô QUẦY trừ đúng số;
* hoàn tác lần thu → thuốc về quầy, tồn trở lại đúng số cũ (không trừ lố);
* chuyển khoản: chờ xác minh thì CHƯA trừ, xác minh xong mới trừ;
* quầy thiếu tồn → thu vẫn được, phần thiếu vào sổ "đã giao, chưa gắn lô";
* khách bỏ bớt (mua 4 / kê 10) → chỉ trừ 4.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import (  # noqa: F401
    Quay,
    _don,
    _thuoc,
    q,
)
from tests.services.test_tien_thuoc_cp3_db import _thu, _xac_minh

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mặc định prod (Tuyền 20/09): thu không giữ chỗ lô.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _chuan_bi(q: Quay, ke: int, ton: int) -> tuple[str, str]:  # noqa: F811
    rx = await _don(q, ke)
    thuoc = await _thuoc(q)
    svc = PharmacyService(q.pool)
    await svc.xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=thuoc
    )
    lo = ""
    if ton:
        kq = await svc.nhap_lo(
            identity=q.duoc_si,
            drug_catalog_id=thuoc,
            so_luong=ton,
            batch_code=f"LO-{uuid.uuid4().hex[:8]}",
            expiry_date=hom_nay_vn() + timedelta(days=400),
            unit="viên",
        )
        lo = str(kq["drug_batch_id"])
    return rx, lo


async def _ton(q: Quay, lo: str) -> Decimal:  # noqa: F811
    return Decimal(
        str(
            await q.pool.fetchval(
                "SELECT quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
            )
        )
    )


async def _da_giao(q: Quay, rx: str) -> Decimal:  # noqa: F811
    return Decimal(
        str(
            await q.pool.fetchval(
                "SELECT coalesce(dispensed_qty, 0) FROM prescription"
                " WHERE id = $1::uuid",
                rx,
            )
        )
    )


async def test_thu_tien_mat_tru_kho_ngay_hoan_tac_tra_ve(q: Quay) -> None:  # noqa: F811
    rx, lo = await _chuan_bi(q, ke=10, ton=30)
    kq = await _thu(q)
    assert await _da_giao(q, rx) == 10
    assert await _ton(q, lo) == 20

    await PaymentService(q.pool).void_payment(
        payment_cycle_id=kq["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="thuoc",
        reason="Thu nhầm",
        identity=q.thu_ngan,
    )
    assert await _da_giao(q, rx) == 0
    assert await _ton(q, lo) == 30  # về quầy, không trừ lố


async def test_chuyen_khoan_chi_tru_khi_xac_minh(q: Quay) -> None:  # noqa: F811
    rx, lo = await _chuan_bi(q, ke=5, ton=30)
    kq = await _thu(q, "TRANSFER")
    assert kq["status"] == "PENDING_VERIFICATION"
    assert await _ton(q, lo) == 30
    await _xac_minh(q, kq["payment_cycle_id"])
    assert await _da_giao(q, rx) == 5
    assert await _ton(q, lo) == 25


async def test_quay_thieu_ton_van_thu_duoc(q: Quay) -> None:  # noqa: F811
    rx, lo = await _chuan_bi(q, ke=10, ton=4)
    kq = await _thu(q)
    assert kq["status"] == "PAID"
    assert await _da_giao(q, rx) == 10
    assert await _ton(q, lo) == 0
    cho = await q.pool.fetchval(
        "SELECT coalesce(sum(so_luong), 0) FROM thuoc_giao_chua_gan_lo"
        " WHERE prescription_id = $1::uuid AND huy_luc IS NULL",
        rx,
    )
    assert Decimal(str(cho)) == 6

    # Hoàn tác lần thu: 4 viên về lô, 6 viên chờ gán lô huỷ — không trừ lố.
    await PaymentService(q.pool).void_payment(
        payment_cycle_id=kq["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="thuoc",
        reason="Khách đổi ý",
        identity=q.thu_ngan,
    )
    assert await _ton(q, lo) == 4
    assert await _da_giao(q, rx) == 0
    cho = await q.pool.fetchval(
        "SELECT coalesce(sum(so_luong), 0) FROM thuoc_giao_chua_gan_lo"
        " WHERE prescription_id = $1::uuid AND huy_luc IS NULL",
        rx,
    )
    assert Decimal(str(cho)) == 0


async def test_khach_mua_bot_chi_tru_so_mua(q: Quay) -> None:  # noqa: F811
    rx, lo = await _chuan_bi(q, ke=10, ton=30)
    await q.pool.execute(
        "UPDATE prescription SET purchased_qty = 4 WHERE id = $1::uuid", rx
    )
    await _thu(q)
    assert await _da_giao(q, rx) == 4
    assert await _ton(q, lo) == 26
