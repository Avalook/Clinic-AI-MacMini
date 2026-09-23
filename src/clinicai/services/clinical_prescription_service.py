"""Ghi đơn thuốc: bác sĩ và thư ký y khoa ghi thẳng; nháp cũ của thư ký (OFF)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.ho_so.cong_doc import NguCanhHoSo, dong


def _prescription_key(name: Any, quantity: Any) -> tuple[str, str]:
    return (
        " ".join(str(name or "").split()).lower(),
        " ".join(str(quantity or "").split()).lower(),
    )


def _validated_prescription_items(
    prescriptions: list[dict[str, Any]], existing_ids: set[str]
) -> list[dict[str, Any]]:
    """Validate every supplied identity against the locked visit/clinic query."""
    seen: set[str] = set()
    validated = []
    for item in prescriptions:
        raw_id = item.get("id")
        row_id = None
        if raw_id is not None:
            try:
                row_id = str(uuid.UUID(str(raw_id)))
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValidationError("Mã dòng đơn thuốc không hợp lệ") from exc
            if row_id not in existing_ids:
                raise ValidationError("Dòng đơn thuốc không thuộc lượt khám này")
            if row_id in seen:
                raise ValidationError("Mã dòng đơn thuốc bị lặp trong đơn gửi lên")
            seen.add(row_id)
        if (item.get("drug_name") or "").strip():
            validated.append({**item, "id": row_id})
    return validated


class PrescriptionDraftPendingError(ConflictError):
    error_code = "PRESCRIPTION_DRAFT_PENDING"


@dataclass(frozen=True)
class PrescriptionWrite:
    draft: dict[str, Any] | None
    items: list[dict[str, Any]] | None
    recorded_by: str | None = None


async def _approved_rows_unchanged(
    conn: asyncpg.Connection,
    *,
    visit_id: Any,
    clinic_id: str | None,
    items: list[dict[str, Any]],
) -> bool:
    rows = await conn.fetch(
        "SELECT id, drug_name_raw, quantity, dosage_instructions, caution "
        "FROM prescription WHERE visit_id = $1::uuid AND clinic_id = $2::uuid "
        "AND removed_at IS NULL ORDER BY id FOR UPDATE",
        visit_id,
        clinic_id,
    )
    try:
        validated = _validated_prescription_items(
            items, {str(row["id"]) for row in rows}
        )
    except ValidationError:
        return False

    def values(row_id: Any, *fields: Any) -> tuple[str, ...]:
        return (str(row_id or ""), *(str(field or "").strip() for field in fields))

    old = sorted(
        values(
            row["id"],
            row["drug_name_raw"],
            row["quantity"],
            row["dosage_instructions"],
            row["caution"],
        )
        for row in rows
    )
    new = sorted(
        values(
            item["id"],
            item.get("drug_name"),
            item.get("quantity"),
            item.get("dosage"),
            item.get("caution"),
        )
        for item in validated
    )
    return old == new


async def prepare_prescription_write(
    conn: asyncpg.Connection,
    *,
    visit_id: Any,
    identity: StaffIdentity,
    draft: dict[str, Any] | None,
    items: list[dict[str, Any]] | None,
    approve: bool,
) -> PrescriptionWrite:
    """Ghi đơn thuốc THẲNG — thư ký y khoa ngang bác sĩ (Tuyền chốt 24/09/2026).

    "Kê đơn: thư ký = bác sĩ, không nháp, không duyệt (phòng khám cho phép).
    Đơn ghi đúng người nhập, kèm bác sĩ chính của lượt." Người nhập nằm ở
    `prescription.created_by`, bác sĩ chính ở `prescription.bac_si_chinh_id`
    (trigger điền từ lượt khám, migration 20260924000003).

    NHÁP CŨ (trước 24/09) — OFF, không xoá: nháp còn treo vẫn duyệt được
    (`approve`) để dữ liệu cũ không kẹt; một lần ghi thẳng mới THAY nháp (nháp
    bị xoá). Lưu hồ sơ không đụng đơn thì nháp giữ nguyên.
    """
    physician = identity.co_vai({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR})
    ke_don = physician or identity.co_vai({ClinicRole.TKYK})
    if not ke_don and items is not None:
        raise SafetyGateError("Chỉ bác sĩ hoặc thư ký y khoa kê thuốc")
    if approve:
        if not physician:
            raise SafetyGateError("Chỉ bác sĩ mới duyệt đơn thuốc thư ký đã nhập")
        if not draft:
            raise ConflictError("Không có đơn thuốc nháp đang chờ duyệt")
        owner = await conn.fetchval(
            "SELECT attending_doctor_id FROM visit "
            "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
            visit_id,
            identity.clinic_id,
        )
        if owner is not None and str(owner) != identity.staff_id:
            raise SafetyGateError(
                "Lượt khám này thuộc bác sĩ khác — không thể duyệt đơn"
            )
        return PrescriptionWrite(None, draft["items"], str(draft["recorded_by"]))
    if items is None:
        return PrescriptionWrite(draft, None)
    if draft and await _approved_rows_unchanged(
        conn, visit_id=visit_id, clinic_id=identity.clinic_id, items=items
    ):
        # Form gửi lại mọi dòng đang hiện mỗi lần lưu hồ sơ: đơn không đổi thì
        # không ghi gì, nháp cũ giữ nguyên.
        return PrescriptionWrite(draft, None)
    if identity.co_vai({ClinicRole.TKYK}) and not physician:
        # Mã dòng thư ký gửi phải thuộc đúng lượt này (giữ chốt cũ).
        rows = await conn.fetch(
            "SELECT id FROM prescription "
            "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid "
            "AND removed_at IS NULL ORDER BY id FOR UPDATE",
            visit_id,
            identity.clinic_id,
        )
        items = _validated_prescription_items(items, {str(row["id"]) for row in rows})
    # Ghi thẳng; nháp cũ (nếu có) bị thay.
    return PrescriptionWrite(None, items)


# ── CỔNG ĐỌC cho hồ sơ khám (cách B, 24/09/2026 — `ho_so/cong_doc.py`) ──────


async def don_thuoc_cho_ho_so(
    conn: asyncpg.Connection, ngu_canh: NguCanhHoSo
) -> dict[str, Any]:
    """Các dòng đơn thuốc CÒN HIỆU LỰC của lượt đang xem."""
    if not ngu_canh.visit_id:
        return {"prescriptions": []}
    rows = await conn.fetch(
        """
        SELECT id::text, drug_catalog_id::text, drug_name_raw, quantity,
               dosage_instructions, caution
          FROM prescription
         WHERE visit_id = $1::uuid AND clinic_id = $2::uuid
           AND removed_at IS NULL
         ORDER BY created_at
        """,
        ngu_canh.visit_id,
        ngu_canh.clinic_id,
    )
    return {"prescriptions": [dong(r) for r in rows]}
