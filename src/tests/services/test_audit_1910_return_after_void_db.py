"""Read-only audit probe: medicine return after the original cycle is voided."""

from __future__ import annotations

import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp5_db import (
    _da_thu_giao,
    _huy_phieu,
    _xuat,
    q,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _bat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


async def test_return_after_void_cannot_refund_but_giu_lai_records_return(
    q,  # noqa: F811 -- fixture imported from the CP5 test module
) -> None:
    prescription_id, _, payment_cycle_id = await _da_thu_giao(q, 3)
    dispense_id = await _xuat(q, prescription_id)
    await _huy_phieu(q, payment_cycle_id)

    with pytest.raises(ConflictError, match="Không tìm thấy lần thu"):
        await PharmacyService(q.pool).khach_tra_thuoc(
            identity=q.duoc_si,
            dispense_txn_id=dispense_id,
            so_luong=1,
            ly_do="Khách trả do dị ứng",
            ket_cuc_tien="HOAN",
        )

    # The failed HOAN transaction must leave no partial return or inventory row.
    assert await q.pool.fetchval(
        "SELECT count(*) FROM drug_return WHERE original_dispense_txn_id=$1::uuid",
        dispense_id,
    ) == 0
    assert await q.pool.fetchval(
        "SELECT count(*) FROM inventory_txn WHERE ref_type='drug_return'"
        " AND txn_type='RETURN_RECEIVED' AND ref_id IN"
        " (SELECT id FROM drug_return WHERE original_dispense_txn_id=$1::uuid)",
        dispense_id,
    ) == 0

    # GIU_LAI remains the documented manual workaround, without an actual refund.
    result = await PharmacyService(q.pool).khach_tra_thuoc(
        identity=q.duoc_si,
        dispense_txn_id=dispense_id,
        so_luong=1,
        ly_do="Khách trả do dị ứng",
        ket_cuc_tien="GIU_LAI",
        ly_do_tien="Chờ thu ngân xử lý tiền",
    )
    assert result["ok"] is True
    assert result["hoan"] is None
    assert await q.pool.fetchval(
        "SELECT count(*) FROM drug_return WHERE original_dispense_txn_id=$1::uuid",
        dispense_id,
    ) == 1
