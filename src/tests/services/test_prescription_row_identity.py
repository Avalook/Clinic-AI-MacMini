"""Dispensed prescriptions retain identity when a clinical record is saved."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError as ModelValidationError

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.v1.routers.clinical_records import PrescriptionItem
from clinicai.services.clinical_record_service import ClinicalRecordService

VISIT = "10000000-0000-0000-0000-000000000001"
CLINIC = "20000000-0000-0000-0000-000000000001"
PATIENT = "30000000-0000-0000-0000-000000000001"
RX_A = "40000000-0000-0000-0000-000000000001"
RX_B = "40000000-0000-0000-0000-000000000002"
FOREIGN_RX = "40000000-0000-0000-0000-000000000003"


def stored(rx_id: str, *, locked: bool = True, name: str = "Drug A") -> dict[str, Any]:
    return {
        "id": UUID(rx_id),
        "drug_name_raw": name,
        "quantity": "10 viên",
        "dispensed_qty": 2 if locked else 0,
        "closed_at": None,
    }


def submitted(rx_id: Any = None, *, dosage: str = "Morning") -> dict[str, Any]:
    return {
        "id": rx_id,
        "drug_name": "Drug A",
        "quantity": "10 viên",
        "dosage": dosage,
        "caution": "After food",
    }


async def replace(conn: Any, items: list[dict[str, Any]]) -> None:
    await ClinicalRecordService(None)._replace_prescriptions(
        conn,
        visit_id=VISIT,
        clinic_patient_id=PATIENT,
        clinic_id=CLINIC,
        prescriptions=items,
    )


def connection(rows: list[dict[str, Any]]) -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = rows
    return conn


def test_request_retains_valid_prescription_uuid() -> None:
    item = PrescriptionItem.model_validate(submitted(RX_A))
    assert item.model_dump()["id"] == UUID(RX_A)
    assert PrescriptionItem.model_validate(submitted()).model_dump()["id"] is None


def test_request_rejects_malformed_prescription_uuid() -> None:
    with pytest.raises(ModelValidationError):
        PrescriptionItem.model_validate(submitted("not-a-uuid"))


@pytest.mark.asyncio
async def test_same_name_quantity_rows_update_the_correct_dosages_by_id() -> None:
    conn = connection([stored(RX_A), stored(RX_B)])
    await replace(conn, [submitted(RX_B, dosage="Evening"), submitted(RX_A)])
    updates = [
        call.args for call in conn.execute.await_args_list if "UPDATE" in call.args[0]
    ]
    assert [(str(args[1]), args[3]) for args in updates] == [
        (RX_A, "Morning"),
        (RX_B, "Evening"),
    ]
    conn.executemany.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rows", [[stored(RX_A), stored(RX_B)], [stored(RX_A), stored(RX_B, locked=False)]]
)
async def test_legacy_rows_with_ambiguous_existing_identity_are_rejected(
    rows: list[dict[str, Any]],
) -> None:
    conn = connection(rows)
    with pytest.raises(ValidationError):
        await replace(conn, [submitted(), submitted(dosage="Evening")])
    conn.execute.assert_not_awaited()
    conn.executemany.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_multiple_candidates_for_one_locked_row_are_rejected() -> None:
    conn = connection([stored(RX_A)])
    with pytest.raises(ValidationError):
        await replace(conn, [submitted(), submitted(dosage="Evening")])
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_unambiguous_legacy_payload_is_supported() -> None:
    conn = connection([stored(RX_A)])
    await replace(conn, [submitted()])
    assert str(conn.execute.await_args_list[0].args[1]) == RX_A
    conn.executemany.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("rx_id", [FOREIGN_RX, "not-a-uuid", ""])
async def test_unknown_or_invalid_id_is_rejected_before_writes(rx_id: str) -> None:
    conn = connection([stored(RX_A)])
    with pytest.raises(ValidationError):
        await replace(conn, [submitted(RX_A), submitted(rx_id)])
    conn.execute.assert_not_awaited()
    conn.executemany.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_id_is_rejected_even_with_different_fields() -> None:
    conn = connection([stored(RX_A)])
    with pytest.raises(ValidationError):
        await replace(
            conn, [submitted(RX_A), {**submitted(UUID(RX_A)), "drug_name": ""}]
        )
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "items",
    [[], [submitted(RX_A)], [{**submitted(RX_B), "drug_name": ""}, submitted(RX_A)]],
)
async def test_missing_locked_row_rejects_before_any_updates(
    items: list[dict[str, Any]],
) -> None:
    conn = connection([stored(RX_A), stored(RX_B)])
    with pytest.raises(ConflictError):
        await replace(conn, items)
    conn.execute.assert_not_awaited()
    conn.executemany.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value", [("drug_name", "Other drug"), ("quantity", "20 viên")]
)
async def test_locked_row_cannot_change_name_or_quantity(
    field: str, value: str
) -> None:
    conn = connection([stored(RX_A)])
    with pytest.raises(ConflictError):
        await replace(conn, [{**submitted(RX_A), field: value}])
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_closed_undispensed_row_is_also_locked() -> None:
    conn = connection(
        [{**stored(RX_A, locked=False), "closed_at": datetime.now(timezone.utc)}]
    )
    await replace(conn, [submitted(RX_A)])
    conn.executemany.assert_not_awaited()
    assert str(conn.execute.await_args_list[0].args[1]) == RX_A


@pytest.mark.asyncio
async def test_unlocked_known_id_and_new_row_remain_drafts() -> None:
    conn = connection([stored(RX_A, locked=False)])
    await replace(conn, [submitted(RX_A), {**submitted(), "drug_name": "New drug"}])
    assert "DELETE" in conn.execute.await_args_list[0].args[0]
    assert len(conn.executemany.await_args.args[1]) == 2
