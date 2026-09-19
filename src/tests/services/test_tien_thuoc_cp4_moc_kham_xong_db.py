"""Một mốc "khám xong" cho Nhà thuốc – Thu ngân – Payment (review CP4, 19/09/2026).

Mốc chuẩn là của LƯỢT: `visit.exam_completed_at`. Lịch hẹn COMPLETED chỉ còn là
nhánh tương thích dữ liệu cũ. Ba nhóm:
  A. không lịch hẹn, chưa khám xong  → chưa sẵn sàng ở cả ba màn;
  B. không lịch hẹn, đã khám xong    → sẵn sàng ở cả ba màn;
  C. lượt cũ có lịch hẹn COMPLETED   → không đổi hành vi.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services import ban_thuoc_service as bt
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import (  # noqa: F401
    Quay,
    _don,
    _nhap_lo,
    _thuoc,
    q,
)
from tests.services.test_tien_thuoc_cp3_db import (
    _chon,
    _dong_da_xac_dinh,
    _san_sang,
    _thu,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _khong_hen(q: Quay, *, kham_xong: bool) -> None:
    """Biến lượt của fixture thành lượt KHÔNG lịch hẹn."""
    await q.pool.execute(
        "UPDATE visit SET appointment_id = NULL,"
        " exam_completed_at = CASE WHEN $2 THEN now() END"
        " WHERE visit_id = $1::uuid",
        q.visit_id,
        kham_xong,
    )


async def _giai_doan(q: Quay) -> str:
    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    g: dict[str, Any] = next(x for x in man["luot"] if x["visit_id"] == q.visit_id)
    return str(g["giai_doan"])


async def _tren_quay(q: Quay) -> dict[str, Any] | None:
    bang = await CashierBoardService(q.pool).board(
        identity=q.thu_ngan, modes=["dich_vu", "thuoc"]
    )
    return next((i for i in bang["items"] if i["visit_id"] == q.visit_id), None)


# ── A ──────────────────────────────────────────────────────────────────────


async def test_a_khong_hen_chua_kham_xong_thi_chua_san_sang(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)  # xác định khi lượt còn lịch hẹn
    lo = await _nhap_lo(q, drug, 100)
    await _khong_hen(q, kham_xong=False)
    assert await _giai_doan(q) == bt.CHUA_SAN_SANG
    with pytest.raises(ConflictError, match="Khám xong"):
        await _chon(q, rx, lo, 10)
    with pytest.raises(ConflictError, match="chưa khám xong"):
        await PaymentService(q.pool).record_payment(
            visit_id=q.visit_id,
            kind="thuoc",
            amount=None,
            clinic_patient_id=None,
            identity=q.thu_ngan,
        )
    assert await _tren_quay(q) is None


# ── B ──────────────────────────────────────────────────────────────────────


async def test_b_khong_hen_da_kham_xong_thi_san_sang_ca_ba_man(q: Quay) -> None:
    await _khong_hen(q, kham_xong=True)
    _, _, lo = await _san_sang(q, 10, 100)
    assert await _giai_doan(q) == bt.SAN_SANG
    item = await _tren_quay(q)
    assert item is not None and item["hoa_don"]["thuoc"]["thu_duoc"]
    kq = await _thu(q)
    assert kq["status"] == "PAID"
    assert await _giai_doan(q) == bt.DA_THU


async def test_b_khong_hen_tien_kham_bao_thieu_nguon_gia_khong_phai_chua_kham(
    q: Quay,
) -> None:
    """Không đoán giá khám, không bỏ im lặng dòng tiền khám (luật CP1)."""
    await _khong_hen(q, kham_xong=True)
    item = await _tren_quay(q)
    assert item is not None
    hd = item["hoa_don"]["dich_vu"]
    assert not hd["thu_duoc"]
    assert any("chưa xác định loại khám" in v for v in hd["van_de"])
    with pytest.raises(ValidationError, match="chưa xác định loại khám"):
        await PaymentService(q.pool).record_payment(
            visit_id=q.visit_id,
            kind="dich_vu",
            amount=None,
            clinic_patient_id=None,
            identity=q.thu_ngan,
        )


# ── C ──────────────────────────────────────────────────────────────────────


async def test_c_luot_cu_lich_hen_completed_khong_doi_hanh_vi(q: Quay) -> None:
    # Fixture: lịch hẹn COMPLETED, exam_completed_at rỗng — dữ liệu cũ.
    assert (
        await q.pool.fetchval(
            "SELECT exam_completed_at FROM visit WHERE visit_id = $1::uuid", q.visit_id
        )
        is None
    )
    await _san_sang(q)
    assert await _giai_doan(q) == bt.SAN_SANG
    assert await _tren_quay(q) is not None
    assert (await _thu(q))["status"] == "PAID"


async def test_c_moc_cua_luot_thang_trang_thai_lich_hen(q: Quay) -> None:
    """Lượt đã khép (exam_completed_at) mà lịch hẹn còn CHECKED_IN → sẵn sàng."""
    await q.pool.execute(
        "UPDATE appointment SET status = 'CHECKED_IN' WHERE id ="
        " (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)",
        q.visit_id,
    )
    rx = await _don(q, 10)
    assert await _giai_doan(q) == bt.CHUA_SAN_SANG
    await q.pool.execute(
        "UPDATE visit SET exam_completed_at = now() WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert await _giai_doan(q) == bt.SAN_SANG
    drug = await _thuoc(q)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug
    )
    await _chon(q, rx, await _nhap_lo(q, drug, 100), 10)
    assert (await _thu(q))["status"] == "PAID"
