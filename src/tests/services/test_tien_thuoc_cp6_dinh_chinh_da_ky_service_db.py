"""CP6 bước 4c: đính chính SOAP/đơn thuốc của bệnh án đã ký."""

# ruff: noqa: F811 — fixture q được import để pytest phát hiện.

from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import clinical_sign_service
from clinicai.services.clinical_sign_service import ClinicalSignService
from clinicai.services.dinh_chinh_don import DonDaDoiError, prescription_fingerprint
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (  # noqa: F401
    Quay,
    _don,
    _nhap_lo,
    _thuoc,
    q,
)
from tests.services.test_tien_thuoc_cp3_db import _giao, _san_sang, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

LY_DO = "Bác sĩ đính chính đơn sau khi ký"


async def _ky(q: Quay) -> None:
    await q.pool.execute(
        """
        INSERT INTO clinical_record
            (clinic_id, visit_id, soap_subjective, soap_objective,
             soap_assessment, soap_plan)
        VALUES ($1::uuid, $2::uuid, '{"s":"cũ"}', '{"o":"cũ"}',
                '{"a":"cũ"}', '{"p":"cũ"}')
        """,
        CLINIC,
        q.visit_id,
    )
    await q.pool.execute(
        "UPDATE visit SET status = 'FINALIZED', finalized_at = now(),"
        " finalized_by = $2::uuid WHERE visit_id = $1::uuid",
        q.visit_id,
        q.bac_si.staff_id,
    )


async def _rx_rows(q: Quay) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in await q.pool.fetch(
            "SELECT id, drug_name_raw, quantity, dosage_instructions, caution"
            " FROM prescription WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " AND removed_at IS NULL ORDER BY id",
            CLINIC,
            q.visit_id,
        )
    ]


async def _fp(q: Quay) -> str:
    return prescription_fingerprint(await _rx_rows(q))


async def _revision(q: Quay) -> int:
    return int(
        await q.pool.fetchval(
            "SELECT revision FROM clinical_record"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
            CLINIC,
            q.visit_id,
        )
    )


def _item(
    row_id: str | None, name: str, quantity: str, dosage: str | None = None
) -> dict[str, Any]:
    return {
        "id": row_id,
        "drug_name": name,
        "quantity": quantity,
        "dosage": dosage,
    }


async def _amendments(q: Quay) -> list[asyncpg.Record]:
    return list(
        await q.pool.fetch(
            "SELECT amendment_id::text, clinic_id::text, corrected_fields,"
            " original_values, corrected_values FROM visit_amendment"
            " WHERE visit_id = $1::uuid ORDER BY amended_at, amendment_id",
            q.visit_id,
        )
    )


async def test_soap_only_tao_mot_amendment_co_clinic_id(q: Quay) -> None:
    rx = await _don(q)
    await _ky(q)
    out = await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason="Sửa SOAP sau ký",
        corrected={"soap_plan": {"p": "mới"}},
        expected_revision=await _revision(q),
    )
    [am] = await _amendments(q)
    assert out["state"] == "AMENDED" and am["clinic_id"] == CLINIC
    assert am["corrected_fields"] == ["soap_plan"]
    assert [str(row["id"]) for row in await _rx_rows(q)] == [rx]
    assert not await q.pool.fetchval(
        "SELECT count(*) FROM prescription_correction WHERE visit_id = $1::uuid",
        q.visit_id,
    )


async def test_rx_only_snapshot_va_replacement_cung_mot_amendment(q: Quay) -> None:
    rx, _, _ = await _san_sang(q)
    await _ky(q)
    await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason=LY_DO,
        corrected={"don_thuoc": [_item(rx, "Thuốc thay", "10 viên", "Tối 1")]},
        expected_revision=await _revision(q),
        expected_rx=await _fp(q),
    )
    [am] = await _amendments(q)
    assert am["corrected_fields"] == ["don_thuoc"]
    original = am["original_values"]
    corrected = am["corrected_values"]
    if isinstance(original, str):
        original = json.loads(original)
    if isinstance(corrected, str):
        corrected = json.loads(corrected)
    old = original["don_thuoc"][0]
    new = corrected["don_thuoc"][0]
    assert old["id"] == rx and old["superseded_by_id"] == new["id"]
    assert new["replaces_id"] == rx and new["id"] != rx
    assert await q.pool.fetchval(
        "SELECT amendment_id = $2::uuid FROM prescription_correction"
        " WHERE visit_id = $1::uuid",
        q.visit_id,
        am["amendment_id"],
    )
    payload = await q.pool.fetchval(
        "SELECT payload FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type = 'clinical.amended' ORDER BY occurred_at DESC LIMIT 1",
        q.visit_id,
    )
    assert "Thuốc thay" not in str(payload) and "Tối 1" not in str(payload)


async def test_soap_va_rx_cung_transaction_chi_mot_amendment(q: Quay) -> None:
    rx, _, _ = await _san_sang(q)
    await _ky(q)
    await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason=LY_DO,
        corrected={
            "soap_assessment": {"a": "mới"},
            "don_thuoc": [_item(rx, "Thuốc thay", "10 viên", "Sáng 1")],
        },
        expected_revision=await _revision(q),
        expected_rx=await _fp(q),
    )
    [am] = await _amendments(q)
    assert set(am["corrected_fields"]) == {"soap_assessment", "don_thuoc"}
    assert await q.pool.fetchval(
        'SELECT soap_assessment = \'{"a":"mới"}\'::jsonb'
        " FROM clinical_record WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert (await _rx_rows(q))[0]["dosage_instructions"] == "Sáng 1"
    assert await q.pool.fetchval(
        "SELECT amendment_id = $2::uuid FROM prescription_correction"
        " WHERE visit_id = $1::uuid",
        q.visit_id,
        am["amendment_id"],
    )


async def test_rx_loi_sau_khi_ghi_soap_thi_rollback_toan_bo(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    rx = await _don(q)
    await _ky(q)
    revision = await _revision(q)
    expected_rx = await _fp(q)

    async def loi_rx(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("rx write failed")

    monkeypatch.setattr(clinical_sign_service, "ap_dung_don_da_ky", loi_rx)
    with pytest.raises(RuntimeError, match="rx write failed"):
        await ClinicalSignService(q.pool).amend(
            identity=q.bac_si,
            visit_id=q.visit_id,
            reason=LY_DO,
            corrected={
                "soap_plan": {"p": "không được commit"},
                "don_thuoc": [_item(rx, "thuoc go tay", "10 viên", "Tối 1")],
            },
            expected_revision=revision,
            expected_rx=expected_rx,
        )

    assert await q.pool.fetchval(
        "SELECT status = 'FINALIZED' FROM visit WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert await q.pool.fetchval(
        'SELECT soap_plan = \'{"p":"cũ"}\'::jsonb FROM clinical_record'
        " WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert await _revision(q) == revision
    assert await _fp(q) == expected_rx
    assert await _amendments(q) == []
    assert not await q.pool.fetchval(
        "SELECT count(*) FROM prescription_correction WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert not await q.pool.fetchval(
        "SELECT count(*) FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type IN ('clinical.amended', 'prescription.corrected')",
        q.visit_id,
    )


async def test_hai_dinh_chinh_cung_fingerprint_chi_mot_commit(q: Quay) -> None:
    rx = await _don(q)
    await _ky(q)
    expected = await _fp(q)
    revision = await _revision(q)

    async def sua(dosage: str) -> object:
        try:
            return await ClinicalSignService(q.pool).amend(
                identity=q.bac_si,
                visit_id=q.visit_id,
                reason=LY_DO,
                corrected={"don_thuoc": [_item(rx, "thuoc go tay", "10 viên", dosage)]},
                expected_revision=revision,
                expected_rx=expected,
            )
        except Exception as exc:  # kết quả cạnh tranh được kiểm kiểu ngay dưới
            return exc

    results = await asyncio.gather(sua("Sáng 1"), sua("Tối 1"))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, DonDaDoiError) for result in results) == 1
    assert len(await _amendments(q)) == 1


async def test_hai_dinh_chinh_soap_cung_revision_chi_mot_commit(q: Quay) -> None:
    await _don(q)
    await _ky(q)
    revision = await _revision(q)

    async def sua(value: str) -> object:
        try:
            return await ClinicalSignService(q.pool).amend(
                identity=q.bac_si,
                visit_id=q.visit_id,
                reason="Đính chính SOAP cạnh tranh",
                corrected={"soap_plan": {"p": value}},
                expected_revision=revision,
            )
        except Exception as exc:  # kết quả cạnh tranh được kiểm kiểu ngay dưới
            return exc

    results = await asyncio.gather(sua("bản A"), sua("bản B"))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, ConflictError) for result in results) == 1
    assert len(await _amendments(q)) == 1


async def test_release_commit_khi_amend_dang_cho_lock_van_bi_revoke(q: Quay) -> None:
    await _don(q)
    await _ky(q)
    revision = await _revision(q)
    async with q.pool.acquire() as conn:
        transaction = conn.transaction()
        await transaction.start()
        await conn.execute(
            "SELECT 1 FROM visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            CLINIC,
            q.visit_id,
        )
        amendment = asyncio.create_task(
            ClinicalSignService(q.pool).amend(
                identity=q.bac_si,
                visit_id=q.visit_id,
                reason="Đính chính sau khi vừa cho gửi",
                corrected={"soap_plan": {"p": "mới"}},
                expected_revision=revision,
            )
        )
        await asyncio.sleep(0.1)
        assert not amendment.done(), "amend không chờ khóa visit"
        await conn.execute(
            "INSERT INTO clinical_release (clinic_id, visit_id, released_by)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid)",
            CLINIC,
            q.visit_id,
            q.bac_si.staff_id,
        )
        await transaction.commit()

    result = await amendment
    assert result["renotify_created"] is True
    assert await q.pool.fetchval(
        "SELECT revoked_at IS NOT NULL FROM clinical_release"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
        CLINIC,
        q.visit_id,
    )
    assert await q.pool.fetchval(
        "SELECT count(*) = 1 FROM hen_goi_lai"
        " WHERE clinic_id = $1::uuid AND clinic_patient_id ="
        " (SELECT clinic_patient_id FROM visit WHERE visit_id = $2::uuid)",
        CLINIC,
        q.visit_id,
    )


async def test_soap_stale_revision_bi_chan_trong_transaction(q: Quay) -> None:
    await _don(q)
    await _ky(q)
    stale = await _revision(q)
    await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason="Sửa SOAP lần một",
        corrected={"soap_plan": {"p": "lần một"}},
        expected_revision=stale,
    )
    with pytest.raises(ConflictError, match="tải lại"):
        await ClinicalSignService(q.pool).amend(
            identity=q.bac_si,
            visit_id=q.visit_id,
            reason="Sửa SOAP từ bản cũ",
            corrected={"soap_plan": {"p": "không được ghi"}},
            expected_revision=stale,
        )
    assert len(await _amendments(q)) == 1


async def test_status_va_audit_sau_commit_cung_amendment(q: Quay) -> None:
    rx, _, _ = await _san_sang(q)
    await _ky(q)
    out = await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason=LY_DO,
        corrected={
            "soap_assessment": {"a": "mới"},
            "don_thuoc": [_item(rx, "Thuốc thay", "10 viên", "Tối 1")],
        },
        expected_revision=await _revision(q),
        expected_rx=await _fp(q),
    )
    amendment_id = out["amendment_id"]
    status = await ClinicalSignService(q.pool).status(
        identity=q.bac_si, visit_id=q.visit_id
    )
    assert status["state"] == "AMENDED"
    assert status["last_amendment_id"] == amendment_id
    assert status["expected_rx"] == await _fp(q)

    correction = await q.pool.fetchrow(
        "SELECT id::text, amendment_id::text, corrected_by::text, reason"
        " FROM prescription_correction WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert correction is not None
    assert correction["amendment_id"] == amendment_id
    assert correction["corrected_by"] == q.bac_si.staff_id
    assert correction["reason"] == LY_DO

    events = await q.pool.fetch(
        "SELECT event_type, payload, metadata, correlation_id::text"
        " FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type IN ('clinical.amended', 'prescription.corrected')"
        " ORDER BY event_type",
        q.visit_id,
    )
    assert {row["event_type"] for row in events} == {
        "clinical.amended",
        "prescription.corrected",
    }
    for event in events:
        payload = event["payload"]
        metadata = event["metadata"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        assert payload["amendment_id"] == amendment_id
        assert metadata["clinic_staff_id"] == q.bac_si.staff_id
        assert event["correlation_id"] == amendment_id


async def test_amendment_duoc_release_lai_va_release_idempotent(q: Quay) -> None:
    await _don(q)
    await _ky(q)
    out = await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason="Sửa SOAP trước khi gửi lại",
        corrected={"soap_plan": {"p": "bản đính chính"}},
        expected_revision=await _revision(q),
    )
    amended = await ClinicalSignService(q.pool).status(
        identity=q.bac_si, visit_id=q.visit_id
    )
    assert amended["state"] == "AMENDED" and amended["can_release"] is True

    released = await ClinicalSignService(q.pool).release(
        identity=q.bac_si,
        visit_id=q.visit_id,
        expected_amendment_id=out["amendment_id"],
    )
    assert released["state"] == "RELEASED"
    status = await ClinicalSignService(q.pool).status(
        identity=q.bac_si, visit_id=q.visit_id
    )
    assert status["state"] == "RELEASED" and status["can_release"] is False
    again = await ClinicalSignService(q.pool).release(
        identity=q.bac_si, visit_id=q.visit_id
    )
    assert again["already_released"] is True


async def test_hai_release_dong_thoi_van_idempotent(q: Quay) -> None:
    await _don(q)
    await _ky(q)
    results = await asyncio.gather(
        ClinicalSignService(q.pool).release(identity=q.bac_si, visit_id=q.visit_id),
        ClinicalSignService(q.pool).release(identity=q.bac_si, visit_id=q.visit_id),
    )
    assert sum(result.get("state") == "RELEASED" for result in results) == 1
    assert sum(result.get("already_released") is True for result in results) == 1
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM clinical_release"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
            CLINIC,
            q.visit_id,
        )
        == 1
    )


async def test_status_khong_tron_state_cu_voi_rx_moi(q: Quay) -> None:
    rx = await _don(q)
    await _ky(q)
    old_fp = await _fp(q)
    revision = await _revision(q)
    first_read_done = asyncio.Event()
    amendment_committed = asyncio.Event()

    class StatusConn:
        def __init__(self, raw: asyncpg.Connection) -> None:
            self.raw = raw

        def transaction(self, *args: Any, **kwargs: Any) -> Any:
            return self.raw.transaction(*args, **kwargs)

        async def fetchrow(self, query: str, *args: Any) -> Any:
            row = await self.raw.fetchrow(query, *args)
            if "FROM public.v_clinical_status" in query:
                first_read_done.set()
                await asyncio.wait_for(amendment_committed.wait(), timeout=2)
            return row

        async def fetch(self, query: str, *args: Any) -> Any:
            return await self.raw.fetch(query, *args)

    class StatusPool:
        @asynccontextmanager
        async def acquire(self) -> Any:
            async with q.pool.acquire() as raw:
                yield StatusConn(raw)

    async def amend_between_status_reads() -> None:
        await asyncio.wait_for(first_read_done.wait(), timeout=2)
        await ClinicalSignService(q.pool).amend(
            identity=q.bac_si,
            visit_id=q.visit_id,
            reason=LY_DO,
            corrected={"don_thuoc": [_item(rx, "thuoc go tay", "10 viên", "Tối 1")]},
            expected_revision=revision,
            expected_rx=old_fp,
        )
        amendment_committed.set()

    writer = asyncio.create_task(amend_between_status_reads())
    snapshot = await ClinicalSignService(StatusPool()).status(
        identity=q.bac_si, visit_id=q.visit_id
    )
    await writer
    assert snapshot["state"] == "SIGNED"
    assert snapshot["last_amendment_id"] is None
    assert snapshot["expected_rx"] == old_fp

    fresh = await ClinicalSignService(q.pool).status(
        identity=q.bac_si, visit_id=q.visit_id
    )
    assert fresh["state"] == "AMENDED"
    assert fresh["last_amendment_id"] is not None
    assert fresh["expected_rx"] != old_fp


async def test_expected_rx_stale_409_khong_tao_amendment_thu_hai(q: Quay) -> None:
    rx = await _don(q)
    await _ky(q)
    stale = await _fp(q)
    await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason=LY_DO,
        corrected={"don_thuoc": [_item(rx, "thuoc go tay", "10 viên", "Sáng 1")]},
        expected_revision=await _revision(q),
        expected_rx=stale,
    )
    with pytest.raises(DonDaDoiError, match="tải lại"):
        await ClinicalSignService(q.pool).amend(
            identity=q.bac_si,
            visit_id=q.visit_id,
            reason=LY_DO,
            corrected={"don_thuoc": [_item(rx, "thuoc go tay", "10 viên", "Tối 1")]},
            expected_revision=await _revision(q),
            expected_rx=stale,
        )
    assert len(await _amendments(q)) == 1


async def test_phan_lo_kho_don_thuan_khong_lam_expected_rx_stale(q: Quay) -> None:
    rx = await _don(q)
    expected = await _fp(q)
    drug = await _thuoc(q)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug
    )
    await PharmacyService(q.pool).phan_lo(
        identity=q.duoc_si,
        prescription_id=rx,
        drug_batch_id=await _nhap_lo(q, drug),
        so_luong=10,
    )
    await _ky(q)
    await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason=LY_DO,
        corrected={"don_thuoc": [_item(rx, "thuoc go tay", "10 viên", "Tối 1")]},
        expected_revision=await _revision(q),
        expected_rx=expected,
    )
    assert len(await _amendments(q)) == 1


async def test_da_thu_giao_giu_sale_dispense_va_release_renotify(q: Quay) -> None:
    rx, _, batch = await _san_sang(q)
    payment = await _thu(q)
    await _giao(q, rx, batch, 10)
    bill_before = await q.pool.fetch(
        "SELECT source_id, quantity, unit_price, line_total FROM payment_bill_line"
        " WHERE payment_cycle_id = $1::uuid ORDER BY id",
        payment["payment_cycle_id"],
    )
    before = await q.pool.fetch(
        "SELECT id::text, txn_type, quantity, payment_cycle_id::text,"
        " allocation_id::text FROM inventory_txn"
        " WHERE clinic_id = $1::uuid AND txn_type IN ('SALE','DISPENSE')"
        " AND allocation_id IN (SELECT id FROM prescription_allocation"
        " WHERE prescription_id = $2::uuid) ORDER BY id",
        CLINIC,
        rx,
    )
    await _ky(q)
    await q.pool.execute(
        "INSERT INTO clinical_release (clinic_id, visit_id, released_by)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid)",
        CLINIC,
        q.visit_id,
        q.bac_si.staff_id,
    )
    await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason=LY_DO,
        corrected={"don_thuoc": [_item(rx, "Thuốc sau khám lại", "5 viên")]},
        expected_revision=await _revision(q),
        expected_rx=await _fp(q),
    )
    after = await q.pool.fetch(
        "SELECT id::text, txn_type, quantity, payment_cycle_id::text,"
        " allocation_id::text FROM inventory_txn"
        " WHERE clinic_id = $1::uuid AND txn_type IN ('SALE','DISPENSE')"
        " AND allocation_id IN (SELECT id FROM prescription_allocation"
        " WHERE prescription_id = $2::uuid) ORDER BY id",
        CLINIC,
        rx,
    )
    assert [tuple(row) for row in after] == [tuple(row) for row in before]
    bill_after = await q.pool.fetch(
        "SELECT source_id, quantity, unit_price, line_total FROM payment_bill_line"
        " WHERE payment_cycle_id = $1::uuid ORDER BY id",
        payment["payment_cycle_id"],
    )
    assert [tuple(row) for row in bill_after] == [tuple(row) for row in bill_before]
    assert await q.pool.fetchval(
        "SELECT revoked_at IS NOT NULL FROM clinical_release WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM hen_goi_lai WHERE clinic_id = $1::uuid"
            " AND clinic_patient_id = (SELECT clinic_patient_id FROM visit"
            " WHERE visit_id = $2::uuid)",
            CLINIC,
            q.visit_id,
        )
        == 1
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM cskh_action WHERE clinic_id = $1::uuid"
            " AND visit_link_raw = $2",
            CLINIC,
            q.visit_id,
        )
        == 1
    )


@pytest.mark.parametrize("other_doctor", [False, True])
async def test_ultrasound_only_va_doctor_khac_bi_chan(
    q: Quay, other_doctor: bool
) -> None:
    await _don(q)
    await _ky(q)
    identity = dataclasses.replace(
        q.bac_si,
        role=ClinicRole.ULTRASOUND_DOCTOR if not other_doctor else ClinicRole.DOCTOR,
        staff_id=q.duoc_si.staff_id if other_doctor else q.bac_si.staff_id,
        vai_tai_khoan=None,
    )
    with pytest.raises(SafetyGateError):
        await ClinicalSignService(q.pool).amend(
            identity=identity,
            visit_id=q.visit_id,
            reason="Không có quyền sửa",
            corrected={"soap_plan": {"p": "không được ghi"}},
            expected_revision=await _revision(q),
        )
    assert await _amendments(q) == []


async def test_release_amendment_stale_khi_amendment_moi_commit_truoc(
    q: Quay,
) -> None:
    """Tab xem A1; A2 commit trước khi release lấy lock => release A1 phải 409."""
    await _don(q)
    await _ky(q)
    rev = await _revision(q)
    # A1 commit
    a1 = await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason="A1",
        corrected={"soap_plan": {"p": "bản A1"}},
        expected_revision=rev,
    )
    a1_id = a1["amendment_id"]

    # Tab nhìn A1, bấm "Cho phép gửi" gửi expected_amendment_id = a1_id
    # Nhưng trước khi lock, A2 commit
    async with q.pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        await conn.execute(
            "SELECT 1 FROM visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            CLINIC,
            q.visit_id,
        )
        # Trong khi visit bị khóa, tạo task release A1
        release_task = asyncio.create_task(
            ClinicalSignService(q.pool).release(
                identity=q.bac_si,
                visit_id=q.visit_id,
                expected_amendment_id=a1_id,
            )
        )
        await asyncio.sleep(0.1)
        assert not release_task.done(), "release không chờ khóa visit"
        # A2 commit giữa lúc release chờ
        a2_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO visit_amendment"
            " (amendment_id, clinic_id, visit_id, amended_by, reason,"
            "  corrected_fields, original_values, corrected_values)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5,"
            "  $6, '{}'::jsonb, '{}'::jsonb)",
            a2_id,
            CLINIC,
            q.visit_id,
            q.bac_si.staff_id,
            "A2 commit trước release",
            ["soap_plan"],
        )
        await tx.commit()

    # release PHẢI 409 vì expected_amendment_id (A1) khác latest (A2).
    # release().status() đọc TRƯỚC lock: nó thấy state=AMENDED nên không
    # early-return. Sau lock, latest_amendment_id = A2 ≠ A1 → 409.
    with pytest.raises(ConflictError, match="đính chính"):
        await release_task
    assert not await q.pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM clinical_release"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        " AND revoked_at IS NULL)",
        CLINIC,
        q.visit_id,
    )


async def test_release_amendment_stale_khi_amendment_moi_commit_truoc_v2(
    q: Quay,
) -> None:
    """Tab xem A1; A2 commit giữa status/lock => release phải 409,
    không tạo clinical_release."""
    await _don(q)
    await _ky(q)
    rev = await _revision(q)
    a1 = await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason="A1",
        corrected={"soap_plan": {"p": "bản A1"}},
        expected_revision=rev,
    )
    a1_id = a1["amendment_id"]
    # A2 commit
    await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason="A2",
        corrected={"soap_plan": {"p": "bản A2"}},
        expected_revision=await _revision(q),
    )
    # Release gửi A1 (stale) => phải 409
    with pytest.raises(ConflictError, match="đính chính"):
        await ClinicalSignService(q.pool).release(
            identity=q.bac_si,
            visit_id=q.visit_id,
            expected_amendment_id=a1_id,
        )
    assert not await q.pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM clinical_release"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        " AND revoked_at IS NULL)",
        CLINIC,
        q.visit_id,
    )


@pytest.mark.parametrize("role_case", ["ultrasound", "other_doctor"])
async def test_release_bi_chan_cho_sieu_am_va_bac_si_khac(
    q: Quay, role_case: str
) -> None:
    """ULTRASOUND_DOCTOR và bác sĩ khác đều không release được."""
    await _don(q)
    await _ky(q)
    if role_case == "ultrasound":
        identity = dataclasses.replace(
            q.bac_si,
            role=ClinicRole.ULTRASOUND_DOCTOR,
            vai_tai_khoan=None,
        )
    else:
        identity = dataclasses.replace(
            q.bac_si,
            role=ClinicRole.DOCTOR,
            staff_id=q.duoc_si.staff_id,
        )
    with pytest.raises(SafetyGateError):
        await ClinicalSignService(q.pool).release(
            identity=identity,
            visit_id=q.visit_id,
        )
    assert not await q.pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM clinical_release"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid)",
        CLINIC,
        q.visit_id,
    )

