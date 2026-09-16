"""Prescription row identity and physician approval of secretary drafts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError


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


def _locked_prescription_matches(
    existing: list[Any], incoming: list[dict[str, Any]]
) -> list[tuple[Any, dict[str, Any]]]:
    """Resolve all locked rows before writing; never guess legacy identities."""
    by_id = {item["id"]: item for item in incoming if item["id"] is not None}
    matches = []
    for row in existing:
        if not ((row["dispensed_qty"] or 0) > 0 or row["closed_at"] is not None):
            continue
        key = _prescription_key(row["drug_name_raw"], row["quantity"])
        item = by_id.get(str(row["id"]))
        if item is None:
            legacy = [
                candidate
                for candidate in incoming
                if candidate["id"] is None
                and _prescription_key(
                    candidate.get("drug_name"), candidate.get("quantity")
                )
                == key
            ]
            existing_count = sum(
                _prescription_key(candidate["drug_name_raw"], candidate["quantity"])
                == key
                for candidate in existing
            )
            if legacy and (len(legacy) != 1 or existing_count != 1):
                raise ValidationError(
                    "Đơn thuốc cũ có dòng trùng tên và số lượng — "
                    "hãy tải lại bệnh án để lấy mã dòng trước khi lưu"
                )
            item = legacy[0] if legacy else None
        if (
            item is None
            or _prescription_key(item.get("drug_name"), item.get("quantity")) != key
        ):
            raise ConflictError(
                f"Thuốc “{row['drug_name_raw']}” ({row['quantity'] or '—'}) "
                "nhà thuốc đã cấp hoặc đã chốt — không xoá hay đổi số lượng "
                "được từ bệnh án. Giữ nguyên dòng này; cần đổi thì báo nhà thuốc."
            )
        matches.append((row, item))
    return matches


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
        "FOR UPDATE",
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
    """Choose draft or live write using the locked chart snapshot."""
    physician = identity.co_vai({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR})
    if not physician and not identity.co_vai({ClinicRole.TKYK}) and items is not None:
        raise SafetyGateError("Chỉ bác sĩ kê thuốc hoặc thư ký nhập đơn thuốc nháp")
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
    if identity.co_vai({ClinicRole.TKYK}) and items is not None:
        # The mature form sends all displayed rows on every chart save. Merely
        # saving SOAP must not create a new pending prescription when these are
        # still the physician-approved rows. Preserve an existing pending draft.
        if await _approved_rows_unchanged(
            conn, visit_id=visit_id, clinic_id=identity.clinic_id, items=items
        ):
            return PrescriptionWrite(draft, None)
        rows = await conn.fetch(
            "SELECT id FROM prescription "
            "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
            visit_id,
            identity.clinic_id,
        )
        safe_items = _validated_prescription_items(
            items, {str(row["id"]) for row in rows}
        )
        return PrescriptionWrite(
            {"items": safe_items, "recorded_by": identity.staff_id}, None
        )
    if draft and items is not None:
        if not await _approved_rows_unchanged(
            conn, visit_id=visit_id, clinic_id=identity.clinic_id, items=items
        ):
            raise PrescriptionDraftPendingError(
                "Có đơn thuốc thư ký nhập chờ duyệt — "
                "bác sĩ cần duyệt trước khi sửa đơn"
            )
        return PrescriptionWrite(draft, None)
    return PrescriptionWrite(draft, items)
