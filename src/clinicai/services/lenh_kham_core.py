"""Nền chung của mọi LỆNH trên một lượt khám — khoá, biên nhận, lỗi có mã.

Bóc khỏi ``luot_kham_service`` ngày 24/09/2026 (bước 1 của đợt bóc lõi, xem
docs/DANG-LAM.md). Trước đó năm khối khác — chỉ định, chọn dịch vụ, xếp phòng,
thực hiện dịch vụ, thu tiền — mượn HÀM NỘI BỘ của khối Khám
(``LuotKhamService._lock_visit``, ``._receipt_get``…): muốn đổi khối Khám là
phải dò xem năm khối kia có vỡ không. Nay chúng dùng nền này; khối Khám cũng
vậy (tên cũ vẫn trỏ về đây để không vỡ chỗ nào).

Hai luật giữ nguyên:
  * KHOÁ LƯỢT TRƯỚC: mỗi lệnh khoá dòng ``visit`` đầu tiên, nên hai lệnh trên
    cùng lượt luôn chạy nối tiếp và thứ tự khoá cố định (không deadlock chéo).
  * BIÊN NHẬN TRONG CÙNG GIAO DỊCH: khoá gửi lại giữ bằng advisory lock, đọc
    biên nhận → làm việc → ghi biên nhận → commit một lần. Chết giữa chừng thì
    cả việc lẫn biên nhận cùng mất; gửi lại là làm lại từ đầu.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity


class LuotKhamConflictError(ConflictError):
    """409 kèm mã máy đọc được (``error_code``) và câu cho người đọc."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


class LuotKhamValidationError(ValidationError):
    """422 kèm mã — dữ liệu gửi lên tự mâu thuẫn."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


def ma_uuid(value: Any, cau: str) -> str:
    """Chuẩn hoá một mã UUID; rác thì báo lỗi 422 bằng câu của người gọi."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(cau) from None


def bam_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def khoa_luot(
    conn: asyncpg.Connection,
    clinic_id: str,
    visit_id: str,
    *,
    cho_phep_da_ky: bool = False,
    cho_phep_ve_giua_chung: bool = False,
) -> asyncpg.Record:
    """Khoá dòng ``visit``; lượt đã đóng / khách bỏ về thì báo 409 có mã.

    `cho_phep_ve_giua_chung` (Tuyền chốt 29/09/2026 — "ngày cũ sửa được hết, ai
    sửa gì cũng đã có lịch sử"): lượt INCOMPLETE (khách về giữa chừng) vẫn SỬA
    được ở các lệnh bật cờ này — thực hiện dịch vụ, lưu sinh hiệu. Mỗi lệnh ấy
    tự ghi sổ sự kiện của nó. FINALIZED / AMENDED (đã ký, TT13) vẫn khoá.
    """
    row = await conn.fetchrow(
        """
        SELECT visit_id::text AS visit_id, status,
               attending_doctor_id::text AS doctor_id
          FROM visit
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           FOR UPDATE
        """,
        clinic_id,
        visit_id,
    )
    if row is None:
        raise NotFoundError("Không tìm thấy lượt khám này.")
    # INCOMPLETE (khách về giữa chừng) nói riêng một câu: người đứng quầy
    # cần biết khách đã rời đi, không phải "lượt đã đóng" như ký xong.
    if row["status"] == "INCOMPLETE" and not cho_phep_ve_giua_chung:
        raise LuotKhamConflictError(
            "VISIT_INCOMPLETE", "Khách đã rời phòng khám giữa chừng."
        )
    hop_le = {"OPEN", "IN_PROGRESS"}
    if cho_phep_da_ky:
        hop_le.add("FINALIZED")
    if cho_phep_ve_giua_chung:
        hop_le.add("INCOMPLETE")
    if row["status"] not in hop_le:
        raise LuotKhamConflictError("VISIT_CLOSED", "Lượt khám này đã đóng.")
    return row


async def khoa_flow(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> asyncpg.Record:
    """Dòng ``encounter_flow`` của lượt (tạo nếu chưa có), đã khoá."""
    await conn.execute(
        """
        INSERT INTO encounter_flow (clinic_id, visit_id)
        VALUES ($1::uuid, $2::uuid)
        ON CONFLICT (visit_id) DO NOTHING
        """,
        clinic_id,
        visit_id,
    )
    row = await conn.fetchrow(
        """
        SELECT vitals_status, plan_check_status, route_decision, content_revision
          FROM encounter_flow
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           FOR UPDATE
        """,
        clinic_id,
        visit_id,
    )
    assert row is not None  # vừa chèn trong cùng transaction
    return row


async def luot_cua(
    conn: asyncpg.Connection, table: str, clinic_id: str, row_id: str
) -> str:
    """Lượt khám chứa một phiên khám hoặc một chỉ định — để khoá visit trước."""
    if table == "consultation":
        visit = await conn.fetchval(
            "SELECT visit_id::text FROM consultation"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            clinic_id,
            row_id,
        )
        cau = "Không tìm thấy phiên khám này."
    else:
        visit = await conn.fetchval(
            "SELECT visit_id::text FROM service_order"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            clinic_id,
            row_id,
        )
        cau = "Không tìm thấy chỉ định này."
    if visit is None:
        raise NotFoundError(cau)
    return str(visit)


async def bien_nhan_doc(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    action: str,
    key: str | None,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Biên nhận của lần gửi trước cùng khoá (nếu có) — giữ khoá tới hết giao dịch."""
    if not key:
        return None
    if not 8 <= len(key) <= 200:
        raise ValidationError("Khoá gửi lại phải dài từ 8 đến 200 ký tự.")
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
        f"{identity.clinic_id}|{identity.staff_id}|{action}|{key}",
    )
    row = await conn.fetchrow(
        """
        SELECT payload_hash, result
          FROM command_receipt
         WHERE clinic_id = $1::uuid AND actor_staff_id = $2::uuid
           AND action = $3 AND idempotency_key = $4
        """,
        identity.clinic_id,
        identity.staff_id,
        action,
        key,
    )
    if row is None:
        return None
    if row["payload_hash"] != bam_payload(payload):
        raise LuotKhamConflictError(
            "IDEMPOTENCY_KEY_REUSED",
            "Khoá gửi lại này đã dùng cho một yêu cầu khác.",
        )
    result = row["result"]
    loaded = json.loads(result) if isinstance(result, str) else result
    return dict(loaded)


async def bien_nhan_ghi(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    action: str,
    key: str | None,
    payload: dict[str, Any],
    target: str,
    result: dict[str, Any],
) -> None:
    if not key:
        return
    await conn.execute(
        """
        INSERT INTO command_receipt
            (clinic_id, actor_staff_id, action, idempotency_key,
             payload_hash, target_ref, result)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid, $7::jsonb)
        """,
        identity.clinic_id,
        identity.staff_id,
        action,
        key,
        bam_payload(payload),
        target,
        json.dumps(result),
    )


__all__ = [
    "LuotKhamConflictError",
    "LuotKhamValidationError",
    "bam_payload",
    "bien_nhan_doc",
    "bien_nhan_ghi",
    "khoa_flow",
    "khoa_luot",
    "luot_cua",
    "ma_uuid",
]
