"""Ký bệnh án, cho phép gửi kết quả, và đính chính bản đã ký.

BA HÀNH VI, MỘT CHIỀU, KHÔNG QUAY LẠI ĐƯỢC BẰNG NÚT XOÁ.

    DRAFT  ──ký──►  SIGNED  ──cho phép gửi──►  RELEASED
                       │                           │
                       └──────đính chính───────────┘
                                  ▼
                               AMENDED  (bản mới, bản cũ giữ nguyên)

Quyết định của Quang (2026-08-04):

  * CHỈ BÁC SĨ được ký. Không phải Quản lý, không phải Thư ký Y khoa. TKYK nhập
    hộ được — Notion cho phép — nhưng người ký là người chịu trách nhiệm chuyên
    môn, và đó luôn là bác sĩ.
  * Bác sĩ siêu âm ký kết quả siêu âm CỦA MÌNH, không ký bệnh án khám. Một lượt
    khám có thể có bệnh án do bác sĩ A ký và siêu âm do bác sĩ B ký.
  * KÝ và CHO PHÉP GỬI là hai bước riêng: *"bệnh án nguy hiểm thì phải cảnh báo
    CSKH chưa được gửi"*. Ký xong, kết quả vẫn chưa tới tay ai cho tới khi bác
    sĩ bấm nút thứ hai.
  * Đính chính bản ĐÃ GỬI thì tạo việc thông báo lại cho CSKH.

VÌ SAO KHÔNG CÓ HÀM "BỎ KÝ". Trigger `visit_finalized_block_update` chỉ cho một
đường ra khỏi FINALIZED: sang AMENDED. Đó là TT13/2011/TT-BYT, và nó đúng — một
bệnh án đã ký mà "bỏ ký" được thì chữ ký không có nghĩa gì. Ký nhầm cũng phải đi
đường đính chính, có lý do, giữ lại bản cũ.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity

logger = structlog.get_logger()

# Ai được ký. Quản lý KHÔNG có ở đây: ký là trách nhiệm chuyên môn, không phải
# quyền hành chính — và một Quản lý ký thay bác sĩ là một chữ ký sai người.
SIGNING_ROLES = (ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR)

# Trường bắt buộc trước khi ký. Notion §6: *"hệ thống kiểm tra các trường bắt
# buộc và liệt kê nội dung còn thiếu"* — liệt kê, không phải chặn với một câu
# chung chung rồi để bác sĩ tự đi tìm.
REQUIRED_SOAP = {
    "soap_subjective": "Lý do khám / triệu chứng",
    "soap_objective": "Khám lâm sàng",
    "soap_assessment": "Chẩn đoán",
    "soap_plan": "Hướng xử trí",
}


class ClinicalSignService:
    """Ký / cho phép gửi / đính chính hồ sơ của một lượt khám."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Đọc ────────────────────────────────────────────────────────────

    async def status(
        self, *, identity: StaffIdentity, visit_id: str
    ) -> dict[str, Any]:
        """Trạng thái hồ sơ + những gì còn thiếu để ký được."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT st.*, cr.soap_subjective, cr.soap_objective,
                       cr.soap_assessment, cr.soap_plan,
                       p.full_name AS patient_name, p.patient_code
                  FROM public.v_clinical_status st
                  LEFT JOIN public.clinical_record cr
                         ON cr.visit_id = st.visit_id
                  LEFT JOIN public.patient p
                         ON p.clinic_patient_id = st.clinic_patient_id
                        AND p.clinic_id = st.clinic_id
                 WHERE st.clinic_id = $1::uuid AND st.visit_id = $2::uuid
                """,
                identity.clinic_id,
                visit_id,
            )
        if row is None:
            raise ValidationError("Không tìm thấy lượt khám ở phòng khám này.")

        missing = missing_fields(dict(row))
        state = row["clinical_state"]
        return {
            "visit_id": str(row["visit_id"]),
            "patient_name": row["patient_name"],
            "patient_code": row["patient_code"],
            "state": state,
            "version": row["version"],
            "signed_at": (
                row["finalized_at"].isoformat() if row["finalized_at"] else None
            ),
            "signed_by_name": row["signed_by_name"],
            "released_at": (
                row["released_at"].isoformat() if row["released_at"] else None
            ),
            "released_by_name": row["released_by_name"],
            "last_amended_at": (
                row["last_amended_at"].isoformat() if row["last_amended_at"] else None
            ),
            "missing": missing,
            "can_sign": state == "DRAFT" and not missing,
            # Cho phép gửi CHỈ sau khi ký. Đây là chốt chặn mà Quang muốn:
            # bệnh án nguy hiểm thì bác sĩ giữ lại, CSKH không thấy nút gửi.
            "can_release": state == "SIGNED",
            "can_amend": state in ("SIGNED", "RELEASED", "AMENDED"),
        }

    # ── Ghi ────────────────────────────────────────────────────────────

    async def sign(
        self, *, identity: StaffIdentity, visit_id: str
    ) -> dict[str, Any]:
        """Bác sĩ ký bệnh án. Sau bước này nội dung bị khoá."""
        _assert_doctor(identity)

        state = await self.status(identity=identity, visit_id=visit_id)
        if state["state"] != "DRAFT":
            raise ValidationError(
                f"Hồ sơ đang ở trạng thái {state['state']}, không ký lại được. "
                "Muốn sửa thì dùng đính chính."
            )
        if state["missing"]:
            raise ValidationError(
                "Chưa ký được, còn thiếu: " + ", ".join(state["missing"])
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                signed = await conn.fetchval(
                    """
                    UPDATE public.visit
                       SET status = 'FINALIZED', finalized_at = now(),
                           finalized_by = $3::uuid, updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND status <> 'FINALIZED'
                    RETURNING visit_id
                    """,
                    identity.clinic_id,
                    visit_id,
                    identity.staff_id,
                )
                if signed is None:
                    # Người khác vừa ký xong giữa hai câu lệnh. Không phải lỗi.
                    return {"ok": True, "already_signed": True}
                await _log(
                    conn,
                    identity,
                    visit_id,
                    "clinical.signed",
                    {"version": state["version"]},
                )

        logger.info(
            "clinical_signed",
            visit_id=visit_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "state": "SIGNED"}

    async def release(
        self, *, identity: StaffIdentity, visit_id: str, note: str | None = None
    ) -> dict[str, Any]:
        """Bước hai: bác sĩ cho phép CSKH gửi kết quả cho bệnh nhân."""
        _assert_doctor(identity)

        state = await self.status(identity=identity, visit_id=visit_id)
        if state["state"] == "DRAFT":
            raise ValidationError("Phải ký bệnh án trước khi cho phép gửi.")
        if state["state"] == "RELEASED":
            return {"ok": True, "already_released": True}

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO public.clinical_release
                        (clinic_id, visit_id, released_by, note)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4)
                    """,
                    identity.clinic_id,
                    visit_id,
                    identity.staff_id,
                    note,
                )
                await _log(
                    conn, identity, visit_id, "clinical.released", {"note": note}
                )

        logger.info(
            "clinical_released",
            visit_id=visit_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "state": "RELEASED"}

    async def amend(
        self,
        *,
        identity: StaffIdentity,
        visit_id: str,
        reason: str,
        corrected: dict[str, Any],
    ) -> dict[str, Any]:
        """Đính chính bản đã ký: tạo phiên bản mới, GIỮ NGUYÊN bản cũ.

        Nếu bản cũ ĐÃ được cho phép gửi thì thu hồi quyền gửi và tạo việc thông
        báo lại cho CSKH — Notion §6: *"Nếu bản cũ đã gửi cho bệnh nhân, hệ
        thống phải tạo công việc thông báo lại."*
        """
        _assert_doctor(identity)

        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("Đính chính bắt buộc phải ghi lý do.")
        corrected = {
            k: v for k, v in (corrected or {}).items() if k in REQUIRED_SOAP
        }
        if not corrected:
            raise ValidationError(
                "Chưa có nội dung nào được sửa. Chọn ít nhất một mục."
            )

        state = await self.status(identity=identity, visit_id=visit_id)
        if state["state"] == "DRAFT":
            raise ValidationError(
                "Hồ sơ chưa ký thì sửa trực tiếp, không cần đính chính."
            )
        was_released = state["state"] == "RELEASED"

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                before = await conn.fetchrow(
                    "SELECT soap_subjective, soap_objective, soap_assessment,"
                    "       soap_plan"
                    "  FROM public.clinical_record WHERE visit_id = $1::uuid",
                    visit_id,
                )
                # asyncpg trả jsonb về dạng CHUỖI. Giải mã để "giá trị
                # trước" trong visit_amendment là JSON thật, không phải một
                # chuỗi JSON bị đóng gói hai lần.
                original = {
                    k: _loads(before[k]) if before else None for k in corrected
                }

                # AMENDED trước: trigger chỉ cho FINALIZED → AMENDED, nên phải
                # mở khoá rồi mới ghi được nội dung mới.
                await conn.execute(
                    "UPDATE public.visit SET status = 'AMENDED', updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                    identity.clinic_id,
                    visit_id,
                )
                # `::jsonb` vì các cột SOAP là jsonb, không phải text. Truyền
                # chuỗi trần vào đây sẽ ném "invalid input syntax for type json"
                # ngay ký tự tiếng Việt đầu tiên.
                sets = ", ".join(
                    f"{k} = ${i + 2}::jsonb" for i, k in enumerate(corrected)
                )
                await conn.execute(  # noqa: S608 — khoá cột từ REQUIRED_SOAP
                    f"UPDATE public.clinical_record SET {sets}, updated_at = now()"
                    " WHERE visit_id = $1::uuid",
                    visit_id,
                    *(json.dumps(v, ensure_ascii=False) for v in corrected.values()),
                )
                await conn.execute(
                    """
                    INSERT INTO public.visit_amendment
                        (visit_id, amended_by, reason, corrected_fields,
                         original_values, corrected_values)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6::jsonb)
                    """,
                    visit_id,
                    identity.staff_id,
                    reason,
                    list(corrected.keys()),
                    json.dumps(original, ensure_ascii=False),
                    json.dumps(corrected, ensure_ascii=False),
                )

                if was_released:
                    # Bản cũ đã được phép gửi ⇒ thu hồi. KHÔNG xoá dòng: "đã
                    # từng cho phép gửi" là sự thật đã xảy ra, và nếu kết quả đã
                    # tới tay bệnh nhân thì thu hồi không làm điều đó biến mất.
                    await conn.execute(
                        """
                        UPDATE public.clinical_release
                           SET revoked_at = now(), revoked_by = $2::uuid,
                               revoke_reason = $3
                         WHERE visit_id = $1::uuid AND revoked_at IS NULL
                        """,
                        visit_id,
                        identity.staff_id,
                        f"Hồ sơ được đính chính: {reason}",
                    )
                    await _create_renotify_task(conn, identity, visit_id, reason)

                await _log(
                    conn,
                    identity,
                    visit_id,
                    "clinical.amended",
                    {
                        "reason": reason,
                        "fields": list(corrected.keys()),
                        "was_released": was_released,
                    },
                )

        logger.info(
            "clinical_amended",
            visit_id=visit_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
            fields=list(corrected.keys()),
            was_released=was_released,
        )
        return {
            "ok": True,
            "state": "AMENDED",
            # Màn hình phải nói ra: bản cũ đã tới tay bệnh nhân, và một việc
            # gọi lại vừa được tạo.
            "renotify_created": was_released,
        }

    async def sign_ultrasound(
        self, *, identity: StaffIdentity, ultrasound_id: str
    ) -> dict[str, Any]:
        """Bác sĩ siêu âm ký kết quả CỦA MÌNH."""
        if identity.role not in SIGNING_ROLES:
            raise ValidationError("Chỉ bác sĩ mới ký được kết quả siêu âm.")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT performed_by, signed_at FROM public.ultrasound_record"
                " WHERE ultrasound_id = $1::uuid AND clinic_id = $2::uuid",
                ultrasound_id,
                identity.clinic_id,
            )
            if row is None:
                raise ValidationError("Không tìm thấy kết quả siêu âm.")
            if row["signed_at"] is not None:
                return {"ok": True, "already_signed": True}
            # "Ký kết quả CỦA MÌNH" — quyết định của Quang. Bác sĩ siêu âm khác
            # ký hộ là ghi sai người chịu trách nhiệm chuyên môn.
            if row["performed_by"] and str(row["performed_by"]) != str(
                identity.staff_id
            ):
                raise ValidationError(
                    "Chỉ bác sĩ đã thực hiện ca siêu âm này mới ký được."
                )
            await conn.execute(
                "UPDATE public.ultrasound_record"
                "   SET signed_by = $2::uuid, signed_at = now(), updated_at = now()"
                " WHERE ultrasound_id = $1::uuid",
                ultrasound_id,
                identity.staff_id,
            )

        logger.info(
            "ultrasound_signed",
            ultrasound_id=ultrasound_id,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "signed": True}


# ── Luật thuần ─────────────────────────────────────────────────────────────


def missing_fields(row: dict[str, Any]) -> list[str]:
    """Những mục còn trống, bằng TÊN NGƯỜI ĐỌC HIỂU.

    Trả về "Chẩn đoán" chứ không phải "soap_assessment": bác sĩ đang đứng trước
    một cái form, không phải trước một cái bảng.

    CÁC CỘT SOAP LÀ `jsonb`, không phải text — nội dung thật trông như
    ``{"chan_doan": "viêm phần phụ"}``. Kiểm bằng ``str(...).strip()`` sẽ coi
    ``{}`` là ĐÃ ĐIỀN, vì chuỗi "{}" không rỗng. Nghĩa là một hồ sơ trống rỗng
    vẫn ký được, và cái chốt chặn duy nhất trước chữ ký sẽ luôn nói "đủ rồi".
    """
    return [
        label
        for field, label in REQUIRED_SOAP.items()
        if _blank_json(row.get(field))
    ]


def _blank_json(value: Any) -> bool:
    """Một mục SOAP coi là TRỐNG khi không có giá trị con nào có chữ."""
    if value is None:
        return True
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return not value.strip()
    if isinstance(value, dict):
        return not any(str(v or "").strip() for v in value.values())
    if isinstance(value, list):
        return not any(str(v or "").strip() for v in value)
    return not str(value).strip()


def _loads(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _assert_doctor(identity: StaffIdentity) -> None:
    if identity.role not in SIGNING_ROLES:
        raise ValidationError(
            "Chỉ bác sĩ mới ký được bệnh án. Thư ký Y khoa nhập hộ được, nhưng "
            "người ký phải là bác sĩ chịu trách nhiệm chuyên môn."
        )


async def _create_renotify_task(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    visit_id: str,
    reason: str,
) -> None:
    """Việc cho CSKH: gọi lại báo bệnh nhân rằng kết quả đã đính chính."""
    row = await conn.fetchrow(
        "SELECT clinic_patient_id FROM public.visit WHERE visit_id = $1::uuid",
        visit_id,
    )
    if row is None:
        return
    await conn.execute(
        """
        INSERT INTO public.cskh_action
            (clinic_id, source_ref, clinic_patient_id, category, status,
             description)
        VALUES ($1::uuid, $2, $3::uuid, 'Thông báo lại kết quả', 'PENDING', $4)
        """,
        identity.clinic_id,
        f"amend:{visit_id}",
        row["clinic_patient_id"],
        f"Kết quả đã gửi cho bệnh nhân vừa được bác sĩ đính chính. Lý do: {reason}."
        " Cần liên hệ lại và gửi bản mới.",
    )


async def _log(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    visit_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    await conn.execute(
        """
        INSERT INTO public.event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, event_published)
        VALUES ($1::uuid, $2, 'visit', $3::uuid, $4::jsonb, $5::jsonb,
                'api:clinical', FALSE)
        """,
        identity.clinic_id,
        event_type,
        visit_id,
        json.dumps(payload, ensure_ascii=False),
        json.dumps(
            {
                "actor_auth_user_id": identity.auth_user_id,
                "actor_staff_id": identity.staff_id,
                "actor_role": identity.role.value,
            }
        ),
    )
