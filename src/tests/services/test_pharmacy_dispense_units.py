"""Dispensing must never equate a box with a tablet without a conversion."""

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.pharmacy_service import PharmacyService


def identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="00000000-0000-0000-0000-000000000001",
        auth_user_id="00000000-0000-0000-0000-000000000002",
        full_name="Dược sĩ kiểm thử",
        department="Nhà thuốc",
        role=ClinicRole.PHARMACIST,
        clinic_id="00000000-0000-0000-0000-000000000003",
        location_id="00000000-0000-0000-0000-000000000004",
        location_name="Cơ sở kiểm thử",
    )


def connection(rx_unit: str | None, batch_unit: str | None) -> Any:
    conn = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock()
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    # CP3: cap_phat khoá lượt → dòng đơn, rồi đọc lần thu thuốc. Lần thu cũ
    # (`legacy`) đi luồng cấp phát cũ — đúng luồng các test này kiểm đơn vị.
    conn.fetchval = AsyncMock(return_value="v1")
    conn.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": "p1",
                "visit_id": "v1",
                "drug_name_raw": "Thuốc thử",
                "quantity_num": Decimal("2"),
                "unit": rx_unit,
                "dispensed_qty": Decimal("0"),
                "closed_at": None,
                "refusal_reason": None,
                "removed_at": None,
            },
            {"payment_cycle_id": "c1", "legacy": True},
            {
                "id": "b1",
                "quantity_on_hand": Decimal("100"),
                "unit": batch_unit,
                "expiry_date": date(2099, 12, 31),
                "name_base": "Thuốc thử",
            },
            {"dispensed_qty": Decimal("2"), "dispense_status": "CAP_DU"},
        ]
    )
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()  # emit_event: dòng giao cho bên nhận
    return conn


def service(conn: Any) -> PharmacyService:
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return PharmacyService(pool)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rx_unit", "batch_unit"),
    [
        ("hộp", "viên"),
        ("viên", "hộp"),
        ("vỉ", "viên"),
        ("ml", "ống"),
        ("viên", None),
        ("viên", " "),
    ],
)
async def test_incompatible_units_rejected_before_any_write(
    rx_unit: str | None, batch_unit: str | None
) -> None:
    conn = connection(rx_unit, batch_unit)
    with pytest.raises(ValidationError, match="đơn vị") as error:
        await service(conn).cap_phat(
            identity=identity(),
            prescription_id="p1",
            drug_batch_id="b1",
            so_luong="2",
        )
    if rx_unit and rx_unit.strip() and batch_unit and batch_unit.strip():
        assert rx_unit in str(error.value)
        assert batch_unit in str(error.value)
    # Chỉ có lệnh khoá lượt; không ghi sổ kho.
    assert all("inventory_txn" not in c.args[0] for c in conn.execute.await_args_list)
    assert conn.fetchrow.await_count == 3  # no prescription UPDATE either


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rx_unit", "batch_unit"),
    [
        ("hộp", "hộp"),
        (" VIÊN ", "viên"),
        ("vie\u0302n", "viên"),
        (None, "viên"),  # legacy unlabelled quantities retain batch-unit meaning
        (" ", "viên"),
    ],
)
async def test_equal_units_keep_stock_and_prescription_quantity_in_same_unit(
    rx_unit: str | None, batch_unit: str
) -> None:
    conn = connection(rx_unit, batch_unit)
    result = await service(conn).cap_phat(
        identity=identity(),
        prescription_id="p1",
        drug_batch_id="b1",
        so_luong="2",
    )
    assert result == {
        "ok": True,
        "dispensed_qty": Decimal("2"),
        "dispense_status": "CAP_DU",
    }
    inventory_sql, *inventory_args = conn.execute.await_args_list[1].args
    assert "inventory_txn" in inventory_sql
    assert inventory_args[3] == Decimal("-2")
    update_sql, *update_args = conn.fetchrow.await_args_list[3].args
    assert "UPDATE public.prescription" in update_sql
    assert update_args[2] == Decimal("2")
    assert "unit" in conn.fetchrow.await_args_list[0].args[0]
    assert "b.unit" in conn.fetchrow.await_args_list[2].args[0]
