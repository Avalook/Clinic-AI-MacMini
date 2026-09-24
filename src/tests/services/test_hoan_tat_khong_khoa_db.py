"""Hoàn tất khám — không còn "Ký bệnh án", và KHÔNG khoá hồ sơ (CORE-A, 23/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_hoan_tat_khong_khoa_db.py

Tuyền chốt 23/09: "chỉ cần nút hoàn tất là khám xong… không khoá, sửa thoải
mái". Nên sau Hoàn tất:
  * lượt KHÔNG thành FINALIZED, bệnh án vẫn sửa thẳng;
  * "Cho phép CSKH gửi" mở ra (trước Hoàn tất thì không);
  * nhắc tái khám tính lượt này — dựa vào khám đã hoàn tất, không vào chữ ký.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.clinical_record_service import ClinicalRecordService
from clinicai.services.clinical_sign_service import ClinicalSignService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.recall_service import RecallService
from tests.services.test_luot_kham_service_db import CLINIC, pool  # noqa: F401
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dang_kham(q: Quay) -> tuple[str, str]:  # noqa: F811
    """Lượt đã check-in, bác sĩ đang khám, có bệnh án. Trả (lịch hẹn, bệnh nhân)."""
    await q.pool.execute(
        "UPDATE appointment SET status = 'CHECKED_IN'"
        " WHERE id = (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)",
        q.visit_id,
    )
    await q.pool.execute(
        "UPDATE visit SET status = 'OPEN', exam_completed_at = NULL,"
        " attending_doctor_id = $2::uuid WHERE visit_id = $1::uuid",
        q.visit_id,
        q.bac_si.staff_id,
    )
    await q.pool.execute(
        "UPDATE consultation SET status = 'in_progress', started_by = $2::uuid,"
        " doctor_staff_id = $2::uuid WHERE id = $1::uuid",
        q.consultation_id,
        q.bac_si.staff_id,
    )
    # Nhắc tái khám lấy lịch đến hạn trong 7 ngày tới (_UPCOMING_DAYS).
    hen_kham = (date.today() + timedelta(days=3)).isoformat()
    await q.pool.execute(
        """
        INSERT INTO clinical_record
            (clinic_id, visit_id, soap_subjective, soap_objective,
             soap_assessment, soap_plan)
        VALUES ($1::uuid, $2::uuid, '{"ly_do": "Khám định kỳ"}',
                '{"kham": "Bình thường"}', '{"chan_doan": "Viêm nhẹ"}',
                jsonb_build_object('xu_tri', 'Theo dõi',
                                   'tai_kham', jsonb_build_object('ngay', $3::text)))
        ON CONFLICT (visit_id) DO UPDATE SET soap_plan = EXCLUDED.soap_plan
        """,
        CLINIC,
        q.visit_id,
        hen_kham,
    )
    row = await q.pool.fetchrow(
        "SELECT appointment_id::text AS hen, clinic_patient_id::text AS bn"
        " FROM visit WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert row is not None
    return row["hen"], row["bn"]


async def _hoan_tat(q: Quay) -> dict[str, Any]:  # noqa: F811
    return await LuotKhamService(q.pool).kham_xong(
        consultation_id=q.consultation_id, identity=q.bac_si
    )


async def test_truoc_hoan_tat_chua_cho_gui(q: Quay) -> None:  # noqa: F811
    await _dang_kham(q)
    st = await ClinicalSignService(q.pool).status(
        identity=q.bac_si, visit_id=q.visit_id
    )
    assert st["state"] == "DRAFT"
    assert st["can_release"] is False
    assert st["can_sign"] is False  # không còn nút ký
    with pytest.raises(ValidationError, match="hoàn tất khám"):
        await ClinicalSignService(q.pool).release(
            identity=q.bac_si, visit_id=q.visit_id
        )


async def test_hoan_tat_khong_khoa_va_van_sua_benh_an_duoc(
    q: Quay,  # noqa: F811
) -> None:
    hen, bn = await _dang_kham(q)
    assert (await _hoan_tat(q)).get("ok") is True

    v = await q.pool.fetchrow(
        "SELECT status, finalized_at, exam_completed_at FROM visit"
        " WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert v["status"] != "FINALIZED" and v["finalized_at"] is None
    assert v["exam_completed_at"] is not None

    # Sửa thẳng bệnh án sau khi hoàn tất — không cần đính chính.
    rev = await q.pool.fetchval(
        "SELECT revision FROM clinical_record WHERE visit_id = $1::uuid", q.visit_id
    )
    await ClinicalRecordService(q.pool).save(
        appointment_id=hen,
        clinic_patient_id=bn,
        identity=q.bac_si,
        expected_revision=rev,
        assessment={"chan_doan": "Viêm nhẹ — bổ sung sau hoàn tất"},
    )
    moi = await q.pool.fetchval(
        "SELECT soap_assessment ->> 'chan_doan' FROM clinical_record"
        " WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert moi == "Viêm nhẹ — bổ sung sau hoàn tất"

    st = await ClinicalSignService(q.pool).status(
        identity=q.bac_si, visit_id=q.visit_id
    )
    assert st["can_amend"] is False  # lượt mới không cần đính chính


async def test_sau_hoan_tat_bac_si_cho_phep_gui_duoc(q: Quay) -> None:  # noqa: F811
    await _dang_kham(q)
    await _hoan_tat(q)
    svc = ClinicalSignService(q.pool)
    st = await svc.status(identity=q.bac_si, visit_id=q.visit_id)
    assert st["state"] == "SIGNED"  # = đã hoàn tất, chưa cho phép gửi
    assert st["can_release"] is True
    assert st["signed_by_name"] == q.bac_si.full_name
    assert st["signed_at"] is not None

    assert (await svc.release(identity=q.bac_si, visit_id=q.visit_id))["ok"]
    st2 = await svc.status(identity=q.bac_si, visit_id=q.visit_id)
    assert st2["state"] == "RELEASED"


async def test_nhac_tai_kham_tinh_luot_da_hoan_tat_khong_can_ky(
    q: Quay,  # noqa: F811
) -> None:
    await _dang_kham(q)
    await _hoan_tat(q)
    bn = await q.pool.fetchval(
        "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    trang_thai = await q.pool.fetchrow(
        "SELECT a.status AS hen, c.status AS phien, c.outcome,"
        " (SELECT count(*) FROM appointment f WHERE f.clinic_patient_id ="
        "  v.clinic_patient_id AND f.slot_start >= now()"
        "  AND f.status IN ('SCHEDULED','CSKH_CONFIRMED','CONFIRMED','CHECKED_IN'))"
        " AS lich_sau"
        " FROM visit v JOIN appointment a ON a.id = v.appointment_id"
        " JOIN consultation c ON c.visit_id = v.visit_id AND c.id = $2::uuid"
        " WHERE v.visit_id = $1::uuid",
        q.visit_id,
        q.consultation_id,
    )
    assert dict(trang_thai) == {
        "hen": "COMPLETED",
        "phien": "completed",
        "outcome": "NO_SERVICES",
        "lich_sau": 0,
    }
    hom_nay = date.today()
    ds = await RecallService(q.pool).due_followups(clinic_id=CLINIC, today=hom_nay)
    assert any(f.clinic_patient_id == bn for f in ds), (
        "Lượt đã hoàn tất (chưa từng ký) phải vào danh sách nhắc tái khám"
    )
