"""Secretary prescriptions remain pending until a physician approves a snapshot."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from tests.quyen_gia import doi_quyen_theo_nhom_mau
from tests.services.test_clinical_record_revision import (
    STAFF,
    identity,
    save,
    setup_service,
)


@pytest.fixture(autouse=True)
def _cua_quyen_theo_nhom_mau(monkeypatch: pytest.MonkeyPatch) -> None:
    """`conn` là mock đếm từng lần fetchval — cửa quyền thật (CORE-B3) không
    chạy được ở đây. Cửa giả trả lời theo nhóm mẫu của vai: điều dưỡng không có
    "Ghi bệnh án" nên vẫn bị chặn ngay ở cổng, đúng như bài kiểm canh."""
    monkeypatch.setattr(
        "clinicai.services.clinical_record_service.doi_quyen",
        doi_quyen_theo_nhom_mau,
    )


ITEM = {
    "id": None,
    "drug_name": "Drug A",
    "quantity": "10 viên",
    "dosage": "Morning",
    "caution": None,
}
DRAFT = {"items": [ITEM], "recorded_by": "60000000-0000-0000-0000-000000000001"}


def pending_service() -> tuple[Any, AsyncMock]:
    service, conn = setup_service(2)
    appointment, stored = list(conn.fetchrow.side_effect)
    conn.fetchrow.side_effect = [appointment, {**stored, "prescription_draft": DRAFT}]
    return service, conn


@pytest.mark.asyncio
@pytest.mark.parametrize("items", [[ITEM]])
async def test_secretary_rx_is_stored_as_pending_and_never_written_live(
    items: list[dict[str, Any]],
) -> None:
    service, conn = setup_service(2)
    conn.fetch.return_value = []
    await save(
        service,
        identity=identity(ClinicRole.TKYK),
        expected_revision=2,
        prescriptions=items,
    )
    service._replace_prescriptions.assert_not_awaited()
    assert "prescription_draft" in conn.fetchval.await_args.args[0]
    draft = json.loads(conn.fetchval.await_args.args[8])
    assert draft == {"items": items, "recorded_by": STAFF}


@pytest.mark.asyncio
async def test_secretary_empty_rx_does_not_open_draft() -> None:
    service, conn = setup_service(2)
    conn.fetch.return_value = []
    await save(
        service,
        identity=identity(ClinicRole.TKYK),
        expected_revision=2,
        prescriptions=[],
    )
    service._replace_prescriptions.assert_not_awaited()
    assert conn.fetchval.await_args.args[8] is None


@pytest.mark.asyncio
async def test_secretary_unchanged_approved_rx_does_not_open_draft() -> None:
    service, conn = setup_service(2)
    row_id = "70000000-0000-0000-0000-000000000001"
    conn.fetch.return_value = [
        {
            "id": row_id,
            "drug_name_raw": "Drug A",
            "quantity": "10 viên",
            "dosage_instructions": "Morning",
            "caution": None,
        }
    ]
    await save(
        service,
        identity=identity(ClinicRole.TKYK),
        expected_revision=2,
        prescriptions=[{**ITEM, "id": row_id}],
        assessment={"diagnosis": "Updated chart only"},
    )
    service._replace_prescriptions.assert_not_awaited()
    assert conn.fetchval.await_args.args[8] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR])
async def test_physician_approval_promotes_exact_stored_draft_and_clears_pending(
    role: ClinicRole,
) -> None:
    service, conn = pending_service()
    conn.fetchval.side_effect = [STAFF, 3]
    with patch(
        "clinicai.services.clinical_record_service.record_event", new=AsyncMock()
    ) as audit:
        # Caller RX cannot replace what the physician reviewed in the stored snapshot.
        await service.save(
            appointment_id="40000000-0000-0000-0000-000000000001",
            clinic_patient_id="30000000-0000-0000-0000-000000000001",
            identity=identity(role),
            expected_revision=2,
            approve_prescription_draft=True,
            prescriptions=[{**ITEM, "drug_name": "Tampered"}],
        )
    service._replace_prescriptions.assert_awaited_once()
    assert service._replace_prescriptions.await_args.kwargs["prescriptions"] == [ITEM]
    assert service._replace_prescriptions.await_args.kwargs["created_by"] == STAFF
    assert conn.fetchval.await_args.args[8] is None
    event = next(
        call.kwargs
        for call in audit.await_args_list
        if call.kwargs["event_type"] == "prescription.draft_approved"
    )
    assert event["payload"]["recorded_by"] == DRAFT["recorded_by"]
    assert event["payload"]["revision"] == 3
    assert "items" not in event["payload"]


@pytest.mark.asyncio
async def test_pending_draft_blocks_physician_changes_to_approved_rx() -> None:
    service, conn = pending_service()
    conn.fetch.return_value = []
    with pytest.raises(ConflictError) as raised:
        await save(service, expected_revision=2, prescriptions=[ITEM])
    assert raised.value.error_code == "PRESCRIPTION_DRAFT_PENDING"
    conn.fetchval.assert_not_awaited()
    service._replace_prescriptions.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("items", [None, []])
async def test_pending_draft_allows_chart_only_save_and_preserves_draft(
    items: Any,
) -> None:
    service, conn = pending_service()
    conn.fetch.return_value = []
    await save(
        service,
        expected_revision=2,
        prescriptions=items,
        assessment={"diagnosis": "Correction"},
    )
    service._replace_prescriptions.assert_not_awaited()
    assert json.loads(conn.fetchval.await_args.args[8]) == DRAFT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role", [ClinicRole.TKYK, ClinicRole.NURSE_ULTRASOUND, ClinicRole.RECEPTION]
)
async def test_non_physician_cannot_approve(role: ClinicRole) -> None:
    service, conn = pending_service()
    with pytest.raises(SafetyGateError):
        await save(
            service,
            identity=identity(role),
            expected_revision=2,
            approve_prescription_draft=True,
        )
    conn.fetchval.assert_not_awaited()
    service._replace_prescriptions.assert_not_awaited()


@pytest.mark.asyncio
async def test_approval_without_pending_draft_is_rejected() -> None:
    service, conn = setup_service(2)
    with pytest.raises(ConflictError):
        await save(service, expected_revision=2, approve_prescription_draft=True)
    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "items",
    [
        [{**ITEM, "id": "70000000-0000-0000-0000-000000000001"}],
        [{**ITEM, "id": STAFF}, {**ITEM, "id": STAFF}],
    ],
)
async def test_pending_draft_invalid_identities_return_pending_conflict(
    items: list[dict[str, Any]],
) -> None:
    service, conn = pending_service()
    conn.fetch.return_value = [
        {
            "id": STAFF,
            "drug_name_raw": "Drug A",
            "quantity": "10 viên",
            "dosage_instructions": "Morning",
            "caution": None,
        }
    ]
    with pytest.raises(ConflictError) as raised:
        await save(service, expected_revision=2, prescriptions=items)
    assert raised.value.error_code == "PRESCRIPTION_DRAFT_PENDING"
    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
async def test_secretary_draft_rejects_foreign_live_prescription_id() -> None:
    service, conn = setup_service(2)
    conn.fetch.return_value = []
    from clinicai.api.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await save(
            service,
            identity=identity(ClinicRole.TKYK),
            expected_revision=2,
            prescriptions=[{**ITEM, "id": STAFF}],
        )
    conn.fetchval.assert_not_awaited()
    service._replace_prescriptions.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("items", [[ITEM], []])
async def test_nurse_full_save_cannot_mutate_or_clear_live_rx(
    items: list[dict[str, Any]],
) -> None:
    service, conn = setup_service(2)
    with pytest.raises(SafetyGateError):
        await save(
            service,
            identity=identity(ClinicRole.NURSE_ULTRASOUND),
            expected_revision=2,
            prescriptions=items,
        )
    conn.fetchval.assert_not_awaited()
    service._replace_prescriptions.assert_not_awaited()


@pytest.mark.asyncio
async def test_dieu_duong_khong_con_ghi_duoc_phan_chuyen_mon() -> None:
    """Điều dưỡng ghi chẩn đoán → bị chặn (Tuyền chốt 16/09/2026).

    Trước đó vai này lưu được trọn hồ sơ; bài kiểm cũ canh đúng điều ấy. Nay
    điều dưỡng chỉ đo sinh hiệu, nên một lần lưu mang theo `assessment` phải
    dừng NGAY ở cổng quyền — trước khi chạm tới đơn thuốc hay bản sửa đổi.
    """
    service, conn = setup_service(2)
    with pytest.raises(SafetyGateError):
        await save(
            service,
            identity=identity(ClinicRole.NURSE_ULTRASOUND),
            expected_revision=2,
            prescriptions=None,
            assessment={"diagnosis": "Chart correction"},
        )
    conn.fetchval.assert_not_awaited()
    service._replace_prescriptions.assert_not_awaited()
