"""Clinical collaboration migration and stale writes use only local temp tables."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlsplit

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.clinical_record_service import ClinicalRecordService
from tests.quyen_gia import doi_quyen_theo_nhom_mau

VISIT = "10000000-0000-0000-0000-000000000001"
CLINIC = "20000000-0000-0000-0000-000000000001"
PATIENT = "30000000-0000-0000-0000-000000000001"
APPOINTMENT = "40000000-0000-0000-0000-000000000001"
STAFF = "50000000-0000-0000-0000-000000000001"
MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
pytestmark = [pytest.mark.asyncio, pytest.mark.db]


@pytest.fixture(autouse=True)
def _cua_quyen_theo_nhom_mau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bài này chạy trên bảng TEMP dựng tay — không có `capability_grant` /
    `v_quyen_hieu_luc`, nên cửa quyền thật (CORE-B3) chặn mọi lần lưu. Cửa giả
    trả lời theo nhóm mẫu của vai (bác sĩ, thư ký có "Ghi bệnh án"); cửa thật
    có bài riêng trên Postgres: `test_duong_kham_hoi_quyen_db.py`."""
    monkeypatch.setattr(
        "clinicai.services.clinical_record_service.doi_quyen",
        doi_quyen_theo_nhom_mau,
    )


class Context:
    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *_: object) -> None:
        pass


@pytest_asyncio.fixture
async def chart_conn(test_db_url: str) -> AsyncIterator[asyncpg.Connection]:
    target = urlsplit(test_db_url)
    if target.hostname not in {"localhost", "127.0.0.1"} or target.port != 55433:
        pytest.skip("Clinical SQL tests only use disposable localhost:55433")
    conn = await asyncpg.connect(test_db_url)
    try:
        await conn.execute(
            """
            CREATE TEMP TABLE clinical_record (
                visit_id uuid PRIMARY KEY, clinic_id uuid NOT NULL,
                chief_complaint_at_visit text, soap_subjective jsonb,
                soap_objective jsonb, soap_assessment jsonb, soap_plan jsonb
            );
            CREATE TEMP TABLE patient_medical_profile (
                clinic_patient_id uuid PRIMARY KEY, clinic_id uuid, blood_type text
            );
            CREATE TEMP TABLE appointment (
                id uuid, clinic_id uuid, clinic_patient_id uuid,
                doctor_id uuid, status text
            );
            CREATE TEMP TABLE patient (clinic_patient_id uuid, clinic_id uuid);
            CREATE TEMP TABLE staff (id uuid PRIMARY KEY, is_active boolean);
            CREATE TEMP TABLE prescription (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_ref text UNIQUE,
                clinic_patient_id uuid, visit_id uuid, clinic_id uuid,
                drug_name_raw text, quantity text, dosage_instructions text,
                caution text, quantity_num numeric, unit text,
                dispensed_qty numeric NOT NULL DEFAULT 0, closed_at timestamptz,
                created_at timestamptz DEFAULT now(),
                updated_at timestamptz DEFAULT now(),
                -- CP6: cột của đính chính đơn / nhà thuốc (bản thật: 4a).
                refusal_reason text, drug_catalog_id uuid, drug_mapped_by uuid,
                drug_mapped_at timestamptz, purchased_qty numeric,
                created_by uuid, removed_at timestamptz, removed_by uuid,
                removal_reason text, removed_in_correction_id uuid,
                superseded_by_id uuid, created_in_correction_id uuid
            );
            CREATE TEMP TABLE clinic_membership (
                staff_id uuid, clinic_id uuid, is_active boolean, role text
            );
            CREATE TEMP TABLE visit (
                visit_id uuid, clinic_id uuid, clinic_patient_id uuid,
                appointment_id uuid, status text, created_at timestamptz,
                attending_doctor_id uuid
            );
            """
        )
        # Run the actual SQL/function bodies with their targets confined to pg_temp.
        notify_sql = (
            MIGRATIONS / "20260806000001_notify_change_for_live_screens.sql"
        ).read_text()
        await conn.execute(
            notify_sql.split("COMMENT ON FUNCTION")[0].replace("public.", "pg_temp.")
        )
        migration = (
            MIGRATIONS / "20260915000005_clinical_collaboration.sql"
        ).read_text()
        await conn.execute(migration.replace("public.", "pg_temp."))
        parsers = (
            MIGRATIONS / "20260807000004_cap_phat_thuoc_mot_phan.sql"
        ).read_text()
        for function in re.findall(
            r"CREATE OR REPLACE FUNCTION public\."
            r"(?:so_luong_tu_van_ban|don_vi_tu_van_ban)"
            r"\(.*?\$function\$;",
            parsers,
            re.DOTALL,
        ):
            await conn.execute(function.replace("public.", "pg_temp."))
        await conn.execute("INSERT INTO staff VALUES ($1::uuid, true)", STAFF)
        await conn.execute(
            "INSERT INTO patient VALUES ($1::uuid, $2::uuid)", PATIENT, CLINIC
        )
        await conn.execute(
            "INSERT INTO appointment VALUES "
            "($1::uuid, $2::uuid, $3::uuid, NULL, 'CHECKED_IN')",
            APPOINTMENT,
            CLINIC,
            PATIENT,
        )
        await conn.execute(
            "INSERT INTO visit (visit_id, clinic_id, clinic_patient_id, "
            "appointment_id, status, created_at) VALUES "
            "($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'IN_PROGRESS', now())",
            VISIT,
            CLINIC,
            PATIENT,
            APPOINTMENT,
        )
        yield conn
    finally:
        await conn.close()


class TempFunctionConnection:
    """Only remap hardcoded SQL parser functions into the temporary test schema."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    def __getattr__(self, name: str) -> Any:
        return getattr(self.conn, name)

    async def executemany(self, query: str, args: Any) -> None:
        await self.conn.executemany(query.replace("public.", "pg_temp."), args)


def service(conn: asyncpg.Connection) -> ClinicalRecordService:
    pool = MagicMock()
    pool.acquire.return_value = Context(TempFunctionConnection(conn))
    return ClinicalRecordService(pool)


async def save(conn: asyncpg.Connection, **kwargs: Any) -> dict[str, Any]:
    role = kwargs.pop("role", ClinicRole.DOCTOR)
    staff = StaffIdentity(
        staff_id=STAFF,
        auth_user_id=STAFF,
        full_name="Test doctor",
        department=role.value,
        role=role,
        clinic_id=CLINIC,
        location_id=CLINIC,
        location_name="Test location",
    )
    # Phạm vi thư ký theo bác sĩ (luật 15/09) có test riêng ở test_luat_1509_*;
    # ở đây chỉ kiểm cơ chế revision/bản nháp nên để phạm vi mở (None).
    with (
        patch(
            "clinicai.services.clinical_record_service.record_event",
            new=AsyncMock(),
        ),
        patch(
            "clinicai.services.clinical_record_service.bac_si_cua_thu_ky",
            new=AsyncMock(return_value=None),
        ),
    ):
        return await service(conn).save(
            appointment_id=APPOINTMENT,
            clinic_patient_id=PATIENT,
            identity=staff,
            **kwargs,
        )


async def test_database_revision_bumps_even_when_writer_supplies_old_revision(
    chart_conn: asyncpg.Connection,
) -> None:
    await chart_conn.execute(
        "INSERT INTO clinical_record (visit_id, clinic_id) VALUES ($1::uuid, $2::uuid)",
        VISIT,
        CLINIC,
    )
    assert await chart_conn.fetchval("SELECT revision FROM clinical_record") == 1
    await chart_conn.execute(
        "UPDATE clinical_record SET revision = 1, soap_plan = '{}'::jsonb"
    )
    assert await chart_conn.fetchval("SELECT revision FROM clinical_record") == 2
    await chart_conn.execute("UPDATE clinical_record SET revision = 999")
    assert await chart_conn.fetchval("SELECT revision FROM clinical_record") == 3


async def test_stale_full_save_cannot_overwrite_chart_or_profile(
    chart_conn: asyncpg.Connection,
) -> None:
    first = await save(
        chart_conn,
        expected_revision=0,
        assessment={"diagnosis": "First"},
        profile={"blood_type": "A"},
    )
    assert first["revision"] == 1
    with pytest.raises(ConflictError):
        await save(
            chart_conn,
            expected_revision=0,
            assessment={"diagnosis": "Stale"},
            profile={"blood_type": "B"},
        )
    assert await chart_conn.fetchval("SELECT revision FROM clinical_record") == 1
    assert json.loads(
        await chart_conn.fetchval("SELECT soap_assessment FROM clinical_record")
    ) == {"diagnosis": "First"}
    assert (
        await chart_conn.fetchval("SELECT blood_type FROM patient_medical_profile")
        == "A"
    )
    second = await save(
        chart_conn, expected_revision=1, assessment={"diagnosis": "Current"}
    )
    assert second["revision"] == 2


async def test_objective_edit_bumps_revision_and_blocks_preexisting_snapshot(
    chart_conn: asyncpg.Connection,
) -> None:
    # Đường "điều dưỡng lưu sinh hiệu qua bệnh án" (vitals_only) đã nghỉ 17/09
    # — sinh hiệu đo ở màn Đo sinh hiệu (vital_measurement, có test riêng). Sửa
    # phần khám thực thể vẫn phải tăng revision và chặn bản chụp cũ.
    await save(chart_conn, expected_revision=0, assessment={"diagnosis": "First"})
    with pytest.raises(ValidationError):
        await save(chart_conn, vitals_only=True, objective={"vitals": {"bp": "1"}})
    vitals = await save(
        chart_conn,
        expected_revision=1,
        objective={"findings": "Bụng mềm"},
        objective_sent=True,
    )
    assert vitals["revision"] == 2
    with pytest.raises(ConflictError):
        await save(
            chart_conn,
            expected_revision=1,
            objective={"findings": "Stale"},
            objective_sent=True,
        )
    objective = json.loads(
        await chart_conn.fetchval("SELECT soap_objective FROM clinical_record")
    )
    assert objective["findings"] == "Bụng mềm"


async def test_chart_and_profile_triggers_emit_only_table_and_clinic(
    chart_conn: asyncpg.Connection,
) -> None:
    messages: asyncio.Queue[str] = asyncio.Queue()
    await chart_conn.add_listener(
        "clinicai_changes",
        lambda _conn, _pid, _channel, payload: messages.put_nowait(payload),
    )
    await save(
        chart_conn,
        expected_revision=0,
        subjective={"sensitive": "Private text"},
        profile={"blood_type": "A"},
    )
    received = [json.loads(await asyncio.wait_for(messages.get(), 2)) for _ in range(2)]
    assert {payload["t"] for payload in received} == {
        "clinical_record",
        "patient_medical_profile",
    }
    assert all(payload == {"t": payload["t"], "c": CLINIC} for payload in received)


async def _nhap_cu(
    conn: asyncpg.Connection, items: list[dict[str, Any]], recorded_by: str = STAFF
) -> int:
    """Nháp đơn của thư ký CÒN TREO từ trước 24/09/2026 (dữ liệu cũ). Nay không
    lệnh nào tạo được nháp nữa (thư ký ghi thẳng); đường DUYỆT nháp cũ vẫn giữ
    đủ chốt an toàn. Trả revision hiện tại của hồ sơ."""
    await conn.execute(
        "UPDATE clinical_record SET prescription_draft = $1::jsonb",
        json.dumps({"items": items, "recorded_by": recorded_by}),
    )
    return int(await conn.fetchval("SELECT revision FROM clinical_record"))


async def test_thu_ky_ke_don_thang_nha_thuoc_thay_ngay(
    chart_conn: asyncpg.Connection,
) -> None:
    """Tuyền chốt 24/09: thư ký = bác sĩ — không nháp, không duyệt."""
    items = [
        {
            "id": None,
            "drug_name": "Drug A",
            "quantity": "10 viên",
            "dosage": "Morning",
            "caution": None,
        }
    ]
    kq = await save(
        chart_conn, role=ClinicRole.TKYK, expected_revision=0, prescriptions=items
    )
    assert kq["revision"] == 1
    row = await chart_conn.fetchrow("SELECT * FROM prescription")
    assert row["drug_name_raw"] == "Drug A" and str(row["created_by"]) == STAFF
    assert row["quantity_num"] == 10 and row["unit"] == "viên"
    assert (
        await chart_conn.fetchval("SELECT prescription_draft FROM clinical_record")
        is None
    )


async def test_ghi_thang_thay_nhap_cu_nen_duyet_nhap_cu_bi_tu_choi(
    chart_conn: asyncpg.Connection,
) -> None:
    await save(chart_conn, expected_revision=0)
    rev = await _nhap_cu(
        chart_conn, [{"id": None, "drug_name": "First drug", "quantity": "10 viên"}]
    )
    moi = [{"drug_name": "Second drug", "quantity": "20 viên"}]
    await save(
        chart_conn, role=ClinicRole.TKYK, expected_revision=rev, prescriptions=moi
    )
    assert (
        await chart_conn.fetchval("SELECT prescription_draft FROM clinical_record")
        is None
    )
    with pytest.raises(ConflictError):
        await save(
            chart_conn, expected_revision=rev + 1, approve_prescription_draft=True
        )
    assert (
        await chart_conn.fetchval("SELECT drug_name_raw FROM prescription")
        == "Second drug"
    )


async def test_other_attending_doctor_cannot_approve_unassigned_appointment_draft(
    chart_conn: asyncpg.Connection,
) -> None:
    await save(chart_conn, expected_revision=0)
    rev = await _nhap_cu(
        chart_conn, [{"id": None, "drug_name": "Drug A", "quantity": "10 viên"}]
    )
    await chart_conn.execute(
        "UPDATE visit SET attending_doctor_id = $1::uuid",
        "60000000-0000-0000-0000-000000000001",
    )
    with pytest.raises(SafetyGateError):
        await save(chart_conn, expected_revision=rev, approve_prescription_draft=True)
    assert await chart_conn.fetchval("SELECT revision FROM clinical_record") == rev
    assert (
        await chart_conn.fetchval("SELECT prescription_draft FROM clinical_record")
        is not None
    )


async def test_locked_rx_removal_draft_cannot_be_approved_and_rolls_back_chart(
    chart_conn: asyncpg.Connection,
) -> None:
    items = [{"drug_name": "Drug A", "quantity": "10 viên", "dosage": "Morning"}]
    await save(chart_conn, expected_revision=0, prescriptions=items)
    await chart_conn.execute("UPDATE prescription SET dispensed_qty = 2")
    before = await chart_conn.fetchrow("SELECT * FROM prescription")
    rev = await _nhap_cu(chart_conn, [])  # nháp cũ: xoá hết đơn
    with pytest.raises(ConflictError):
        await save(
            chart_conn,
            expected_revision=rev,
            approve_prescription_draft=True,
            assessment={"diagnosis": "Must rollback"},
        )
    assert await chart_conn.fetchval("SELECT revision FROM clinical_record") == rev
    assert (
        await chart_conn.fetchval("SELECT soap_assessment FROM clinical_record") is None
    )
    assert await chart_conn.fetchrow("SELECT * FROM prescription") == before
    assert (
        json.loads(
            await chart_conn.fetchval("SELECT prescription_draft FROM clinical_record")
        )["items"]
        == []
    )


async def test_chart_only_save_with_pending_draft_keeps_approved_ids_and_snapshot(
    chart_conn: asyncpg.Connection,
) -> None:
    await save(
        chart_conn,
        expected_revision=0,
        prescriptions=[
            {"drug_name": "Drug A", "quantity": "10 viên", "dosage": "Morning"}
        ],
    )
    before = await chart_conn.fetchrow("SELECT * FROM prescription")
    approved_payload = [
        {
            "id": str(before["id"]),
            "drug_name": before["drug_name_raw"],
            "quantity": before["quantity"],
            "dosage": before["dosage_instructions"],
            "caution": before["caution"],
        }
    ]
    rev = await _nhap_cu(
        chart_conn, [{"id": None, "drug_name": "Pending drug", "quantity": "20 viên"}]
    )
    snapshot = await chart_conn.fetchval(
        "SELECT prescription_draft FROM clinical_record"
    )
    result = await save(
        chart_conn,
        expected_revision=rev,
        prescriptions=approved_payload,
        assessment={"diagnosis": "Chart correction"},
    )
    assert result["revision"] == rev + 1
    assert await chart_conn.fetchrow("SELECT * FROM prescription") == before
    assert (
        await chart_conn.fetchval("SELECT prescription_draft FROM clinical_record")
        == snapshot
    )
