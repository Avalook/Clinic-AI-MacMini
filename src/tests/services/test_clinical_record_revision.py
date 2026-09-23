"""Full chart saves detect stale snapshots before any chart/profile/RX write."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError as ModelValidationError

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.clinical_records import ClinicalRecordSaveRequest
from clinicai.services.clinical_record_service import ClinicalRecordService


@pytest.fixture(autouse=True)
def _cua_quyen_co_bai_kiem_rieng(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cửa quyền `clinical.record.write` (CORE-B3) có bài kiểm trên Postgres thật
    (`test_duong_kham_hoi_quyen_db.py`). Ở đây `conn` là mock đếm từng lần
    fetchval, nên cửa quyền không được tiêu mất một lần của phép kiểm thứ tự."""
    monkeypatch.setattr(
        "clinicai.services.clinical_record_service.doi_quyen",
        AsyncMock(return_value=None),
    )


VISIT = "10000000-0000-0000-0000-000000000001"
CLINIC = "20000000-0000-0000-0000-000000000001"
PATIENT = "30000000-0000-0000-0000-000000000001"
APPOINTMENT = "40000000-0000-0000-0000-000000000001"
STAFF = "50000000-0000-0000-0000-000000000001"


class Context:
    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *_: object) -> None:
        pass


def setup_service(revision: int) -> tuple[Any, AsyncMock]:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=Context(conn))
    pool = MagicMock()
    pool.acquire.return_value = Context(conn)
    conn.fetchrow.side_effect = [
        {
            "status": "CHECKED_IN",
            "doctor_id": STAFF,
            "clinic_patient_id": PATIENT,
            "patient_in_clinic": True,
            "doctor_in_clinic": True,
        },
        # Khoá thật của hồ sơ khám là `huyet_ap` (ClinicalRecordForm). Trước
        # 15/09 test dùng "bp" — không màn nào ghi khoá đó, và không luật nào
        # đọc sinh hiệu nên không lộ ra.
        {"soap_objective": {"vitals": {"huyet_ap": "120/80"}}, "revision": revision}
        if revision
        else None,
    ]

    # Lần lưu có đổi sinh hiệu còn hỏi "khách có đang mang thai" (luật sinh
    # hiệu 15/09) — trả không; mọi lượt đọc khác là revision mới.
    async def fetchval(sql: str, *_: Any) -> Any:
        if "thu_ky_bac_si" in sql:
            # Thư ký được phân đi cùng đúng bác sĩ của lịch hẹn (STAFF). Chưa
            # phân ai = [] = bị chặn (Tuyền chốt 15/09/2026, luật cứng).
            return [STAFF]
        return False if "pregnancy" in sql else revision + 1

    conn.fetchval.side_effect = fetchval
    service = ClinicalRecordService(pool)
    service._writable_visit = AsyncMock(return_value=VISIT)  # type: ignore[method-assign]
    service._save_profile = AsyncMock()  # type: ignore[method-assign]
    service._replace_prescriptions = AsyncMock()  # type: ignore[method-assign]
    service._dong_bo_luong_kham = AsyncMock()  # type: ignore[method-assign]
    return service, conn


def identity(role: ClinicRole = ClinicRole.DOCTOR) -> StaffIdentity:
    return StaffIdentity(
        staff_id=STAFF,
        auth_user_id=STAFF,
        full_name="Test staff",
        department=role.value,
        role=role,
        clinic_id=CLINIC,
        location_id=CLINIC,
        location_name="Test location",
    )


async def save(service: ClinicalRecordService, **kwargs: Any) -> dict[str, Any]:
    with patch(
        "clinicai.services.clinical_record_service.record_event", new=AsyncMock()
    ):
        return await service.save(
            appointment_id=APPOINTMENT,
            clinic_patient_id=PATIENT,
            identity=kwargs.pop("identity", identity()),
            **kwargs,
        )


@pytest.mark.parametrize("revision", [-1, "1", True])
def test_request_rejects_invalid_expected_revision(revision: Any) -> None:
    with pytest.raises(ModelValidationError):
        ClinicalRecordSaveRequest.model_validate(
            {
                "appointment_id": APPOINTMENT,
                "clinic_patient_id": PATIENT,
                "expected_revision": revision,
            }
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    # Điều dưỡng rời danh sách 16/09/2026 — nay chỉ ghi sinh hiệu.
    "role",
    [ClinicRole.DOCTOR, ClinicRole.TKYK],
)
@pytest.mark.parametrize("expected", [None, 0, 1, 3])
async def test_missing_or_stale_revision_rejects_before_related_writes(
    role: ClinicRole,
    expected: int | None,
) -> None:
    service, conn = setup_service(2)
    with pytest.raises(ConflictError):
        await save(
            service,
            identity=identity(role),
            expected_revision=expected,
            profile={"blood_type": "A"},
            prescriptions=[],
        )
    conn.execute.assert_not_awaited()
    conn.fetchval.assert_not_awaited()
    service._save_profile.assert_not_awaited()
    service._replace_prescriptions.assert_not_awaited()
    assert "FOR UPDATE" in conn.fetchrow.await_args_list[-1].args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("revision", [0, 1, 5])
async def test_matching_snapshot_returns_new_database_revision(revision: int) -> None:
    service, conn = setup_service(revision)
    result = await save(
        service,
        expected_revision=revision,
        # Lần lưu đầu (revision 0) chưa có số cũ: luật 15/09 bắt buộc huyết áp.
        objective={"vitals": {"huyet_ap": "118/76", "pulse": 72}},
        objective_sent=True,
    )
    assert result["revision"] == revision + 1
    assert "RETURNING revision" in conn.fetchval.await_args.args[0]


@pytest.mark.asyncio
async def test_vitals_only_duong_cu_bi_tu_choi() -> None:
    """17/09/2026: đường đón-khám cũ đã bỏ — sinh hiệu chỉ đo ở màn Đo sinh hiệu."""
    service, conn = setup_service(5)
    with pytest.raises(ValidationError, match="màn Đo sinh hiệu"):
        await save(
            service, vitals_only=True, objective={"vitals": {"huyet_ap": "125/80"}}
        )
    conn.execute.assert_not_awaited()
