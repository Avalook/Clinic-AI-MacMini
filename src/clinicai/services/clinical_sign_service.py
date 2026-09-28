"""Hồ sơ đã hoàn tất: cho phép gửi và đính chính. (Ký kết quả SIÊU ÂM vẫn ở đây.)

KHÔNG CÒN "KÝ BỆNH ÁN" từ 23/09/2026 (CORE-A). Tuyền chốt: Hoàn tất = khám
xong, KHÔNG khoá — bệnh án vẫn sửa trực tiếp sau đó. Nên:
  * "Cho phép gửi" dựa vào KHÁM ĐÃ HOÀN TẤT (phiên cuối kết thúc NO_SERVICES /
    DONE), không dựa vào khoá. Trạng thái nội bộ vẫn tên `SIGNED` = "đã hoàn tất,
    chưa cho phép gửi" để API không đổi hình.
  * "Đính chính" chỉ còn cho lượt CŨ đã từng ký (FINALIZED/AMENDED) — lượt mới
    không khoá thì sửa thẳng, không cần đính chính.


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
import uuid
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import doi_quyen
from clinicai.services.dinh_chinh_don import (
    ap_dung_don_da_ky,
    chuan_bi_don_da_ky,
    prescription_fingerprint,
    validate_amendment_prescriptions,
)

logger = structlog.get_logger()

# Ai được ký kết quả siêu âm. Ký bệnh án khám CHỈ dành riêng cho bác sĩ khám (DOCTOR).
ULTRASOUND_SIGNING_ROLES = (ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR)
SIGNING_ROLES = ULTRASOUND_SIGNING_ROLES

# Trường bắt buộc trước khi ký. Notion §6: *"hệ thống kiểm tra các trường bắt
# buộc và liệt kê nội dung còn thiếu"* — liệt kê, không phải chặn với một câu
# chung chung rồi để bác sĩ tự đi tìm.
#: Ô của phiếu chuyên khoa được tính là CHẨN ĐOÁN khi ký (S0-8, 18/09/2026).
#: Phiếu Sản dùng `ket_luan`; phiếu HMVS tách nguyên nhân vợ/chồng/phối hợp.
#: KHÔNG gồm `cd_phan_loai`, `cd_tien_luong`: đó là ô chọn, không phải chẩn đoán.
KHOA_CHAN_DOAN_PHIEU = (
    "chan_doan",
    "ket_luan",
    "cd_nguyen_nhan_vo",
    "cd_nguyen_nhan_chong",
    "cd_nguyen_nhan_phoi_hop",
    "cd_phan_biet",
    "cd_benh_kem",
)
#: "Kế hoạch tiếp theo" của HMVS khi còn đang đánh giá.
KHOA_KE_HOACH_TIEP_THEO = ("tai_kham_ngay", "chu_ky_dieu_tri_tiep", "tai_kham_xn")
THIEU_KE_HOACH_KHI_DANG_DANH_GIA = (
    "Chẩn đoán — đang tiếp tục đánh giá: cần kế hoạch tiếp theo "
    "(ngày tái khám, chu kỳ điều trị tiếp theo hoặc xét nghiệm kiểm lại)"
)

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

    async def status(self, *, identity: StaffIdentity, visit_id: str) -> dict[str, Any]:
        """Trạng thái hồ sơ (chưa hoàn tất / đã hoàn tất / đã cho gửi / đính chính)."""
        async with self._pool.acquire() as conn:
            # Hai câu đọc phải cùng một MVCC snapshot: nếu amendment commit giữa
            # chúng, không được trả state/amendment cũ cùng fingerprint Rx mới.
            async with conn.transaction(isolation="repeatable_read", readonly=True):
                row = await conn.fetchrow(
                    """
                    SELECT st.*, cr.soap_subjective, cr.soap_objective,
                           cr.soap_assessment, cr.soap_plan,
                           cr.revision AS record_revision,
                           cr.chief_complaint_at_visit,
                           p.full_name AS patient_name, p.patient_code,
                           (SELECT a.amendment_id::text
                              FROM public.visit_amendment a
                             WHERE a.clinic_id = st.clinic_id
                               AND a.visit_id = st.visit_id
                             ORDER BY a.amended_at DESC, a.amendment_id DESC
                             LIMIT 1) AS last_amendment_id,
                           -- PHIẾU CHUYÊN KHOA + SINH HIỆU ĐÃ ĐO cũng là nội dung bệnh
                           -- án (17/09/2026): thư ký điền "Lý do khám" ở phiếu Nội
                           -- tiết, điều dưỡng đo ở màn Đo sinh hiệu — nút ký không được
                           -- báo thiếu những thứ đã có.
                           (SELECT jsonb_object_agg(k, v)
                              FROM public.clinical_form_response f,
                                   jsonb_each(f.form_data) AS e(k, v)
                             WHERE f.visit_id = st.visit_id
                               AND f.clinic_id = st.clinic_id) AS phieu_chuyen_khoa,
                           EXISTS (SELECT 1 FROM public.vital_measurement m
                                    WHERE m.visit_id = st.visit_id
                                      AND m.clinic_id = st.clinic_id) AS co_sinh_hieu,
                           ht.completed_at AS hoan_tat_luc,
                           ht.hoan_tat_boi
                      FROM public.v_clinical_status st
                      LEFT JOIN LATERAL (
                           SELECT c.completed_at, sc.full_name AS hoan_tat_boi
                             FROM public.consultation c
                             LEFT JOIN public.staff sc ON sc.id = c.completed_by
                            WHERE c.clinic_id = st.clinic_id
                              AND c.visit_id = st.visit_id
                              AND c.status = 'completed'
                              AND c.outcome IN ('NO_SERVICES', 'DONE')
                            ORDER BY c.completed_at DESC LIMIT 1) ht ON true
                      LEFT JOIN public.clinical_record cr
                             ON cr.visit_id = st.visit_id
                            AND cr.clinic_id = st.clinic_id
                      LEFT JOIN public.patient p
                             ON p.clinic_patient_id = st.clinic_patient_id
                            AND p.clinic_id = st.clinic_id
                     WHERE st.clinic_id = $1::uuid AND st.visit_id = $2::uuid
                    """,
                    identity.clinic_id,
                    visit_id,
                )
                rx_rows = (
                    [
                        dict(rx)
                        for rx in await conn.fetch(
                            """
                            SELECT id, drug_name_raw, quantity,
                                   dosage_instructions, caution
                              FROM public.prescription
                             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                               AND removed_at IS NULL AND nguon = 'BAC_SI'
                             ORDER BY id
                            """,
                            identity.clinic_id,
                            visit_id,
                        )
                    ]
                    if row is not None
                    else []
                )
        if row is None:
            raise ValidationError("Không tìm thấy lượt khám ở phòng khám này.")

        missing = missing_fields(dict(row))
        # View lịch sử ưu tiên AMENDED, nhưng một amendment đã được cho phép gửi
        # lại phải là RELEASED để release() idempotent và UI không nói sai.
        state = "RELEASED" if row["released_at"] is not None else row["clinical_state"]
        # Khám đã hoàn tất (không khoá) = "đã hoàn tất, chưa cho phép gửi".
        hoan_tat_luc = _optional_row_value(row, "hoan_tat_luc")
        if state == "DRAFT" and hoan_tat_luc is not None:
            state = "SIGNED"
        moc = row["finalized_at"] or hoan_tat_luc
        return {
            "visit_id": str(row["visit_id"]),
            "patient_name": row["patient_name"],
            "patient_code": row["patient_code"],
            "state": state,
            "version": row["version"],
            # Phiên bản bệnh án bác sĩ đang xem — gửi lại khi ký (15/09/2026).
            "record_revision": row["record_revision"],
            "expected_rx": prescription_fingerprint(rx_rows),
            "last_amendment_id": _optional_row_value(row, "last_amendment_id"),
            # Giờ + người HOÀN TẤT (lượt cũ đã ký: giờ + người ký).
            "signed_at": moc.isoformat() if moc else None,
            "signed_by_name": row["signed_by_name"]
            or _optional_row_value(row, "hoan_tat_boi"),
            "released_at": (
                row["released_at"].isoformat() if row["released_at"] else None
            ),
            "released_by_name": row["released_by_name"],
            "last_amended_at": (
                row["last_amended_at"].isoformat() if row["last_amended_at"] else None
            ),
            "missing": missing,
            # Không còn nút ký — giữ khoá cho API không đổi hình.
            "can_sign": False,
            # Cho phép gửi CHỈ sau khi khám hoàn tất. Đây là chốt chặn Quang
            # muốn: bệnh án nguy hiểm thì bác sĩ giữ lại, CSKH không thấy nút gửi.
            "can_release": state in ("SIGNED", "AMENDED"),
            # Đính chính chỉ cho lượt CŨ đã khoá; lượt mới sửa thẳng.
            "can_amend": _optional_row_value(row, "visit_status")
            in ("FINALIZED", "AMENDED"),
        }

    # ── Ghi ────────────────────────────────────────────────────────────

    # `sign()` ĐÃ GỠ 23/09/2026 (CORE-A): không còn bước "Ký bệnh án". Mốc khoá
    # là HOÀN TẤT KHÁM — `LuotKhamService._khoa_ho_so_khi_hoan_tat`, chạy trong
    # chính giao dịch bác sĩ phụ trách bấm Hoàn tất (hồ sơ đã được kiểm đủ).

    async def release(
        self,
        *,
        identity: StaffIdentity,
        visit_id: str,
        note: str | None = None,
        expected_amendment_id: str | None = None,
    ) -> dict[str, Any]:
        """Bước hai: bác sĩ cho phép CSKH gửi kết quả cho bệnh nhân.

        CHỈ BÁC SĨ CHÍNH CỦA LƯỢT. Bác sĩ siêu âm ký kết quả siêu âm CỦA
        MÌNH; cho phép gửi bệnh án là trách nhiệm bác sĩ khám.

        expected_amendment_id: nếu hồ sơ ở AMENDED, bác sĩ phải gửi
        last_amendment_id đang nhìn. Không khớp ⇒ 409 (tải lại trước).
        """
        # QUYỀN HỎI ĐẦU TIÊN, trước khi tìm lượt (luật chung của CORE-B3): người
        # không có quyền nhận câu "chưa được cấp quyền", không phải "không tìm
        # thấy". Hỏi lại trong giao dịch ghi bên dưới — quyền có thể bị thu
        # giữa hai lần.
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                "clinical.consult.finalize",
                cau="Bạn chưa được cấp quyền cho phép gửi hồ sơ.",
            )
        state = await self.status(identity=identity, visit_id=visit_id)
        if state["state"] == "DRAFT":
            raise ValidationError("Phải hoàn tất khám trước khi cho phép gửi.")
        if state["state"] == "RELEASED":
            return {"ok": True, "already_released": True}

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Statement FOR UPDATE có thể lấy snapshot TRƯỚC khi chờ lock.
                # Vì vậy chỉ khóa visit ở đây; state/release phải đọc bằng
                # statement mới sau khi lock đã thật sự thuộc giao dịch này.
                locked_visit = await conn.fetchval(
                    "SELECT visit_id FROM public.visit"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    " FOR UPDATE",
                    identity.clinic_id,
                    visit_id,
                )
                if locked_visit is None:
                    raise ValidationError("Không tìm thấy lượt khám ở phòng khám này.")
                locked = await conn.fetchrow(
                    """
                    SELECT v.status,
                           v.attending_doctor_id::text,
                           EXISTS (
                               SELECT 1 FROM public.clinical_release r
                                WHERE r.clinic_id = v.clinic_id
                                  AND r.visit_id = v.visit_id
                                  AND r.revoked_at IS NULL
                           ) AS active_release,
                           (SELECT a.amendment_id::text
                              FROM public.visit_amendment a
                             WHERE a.clinic_id = v.clinic_id
                               AND a.visit_id = v.visit_id
                             ORDER BY a.amended_at DESC, a.amendment_id DESC
                             LIMIT 1) AS latest_amendment_id,
                           EXISTS (
                               SELECT 1 FROM public.consultation c
                                WHERE c.clinic_id = v.clinic_id
                                  AND c.visit_id = v.visit_id
                                  AND c.status = 'completed'
                                  AND c.outcome IN ('NO_SERVICES', 'DONE')
                           ) AS kham_hoan_tat
                      FROM public.visit v
                     WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                    """,
                    identity.clinic_id,
                    visit_id,
                )
                assert locked is not None
                # QUYỀN (không vai, CORE-A/B3): cho phép gửi hồ sơ là việc của
                # người được Hoàn tất khám — cùng quyền `clinical.consult.finalize`.
                await doi_quyen(
                    conn,
                    identity,
                    "clinical.consult.finalize",
                    cau="Bạn chưa được cấp quyền cho phép gửi hồ sơ.",
                )
                # Bác sĩ chính: kiểm SAU lock vì attending_doctor_id có thể
                # đổi giữa lúc status() đọc và lúc lock xong.
                _assert_release_doctor_is_attending(
                    identity, locked["attending_doctor_id"]
                )
                locked_state = (
                    "RELEASED"
                    if locked["active_release"]
                    else (
                        ("AMENDED" if locked["latest_amendment_id"] else "SIGNED")
                        if locked["status"] == "FINALIZED"
                        # Lượt CŨ đã đính chính giữ nguyên AMENDED; lượt mới
                        # không khoá thì "khám đã hoàn tất" = SIGNED.
                        else "AMENDED"
                        if locked["status"] == "AMENDED"
                        else "SIGNED"
                        if _optional_row_value(locked, "kham_hoan_tat")
                        else locked["status"]
                    )
                )
                if locked_state == "RELEASED":
                    return {"ok": True, "already_released": True}
                if locked_state != state["state"]:
                    raise ConflictError(
                        "Bệnh án vừa thay đổi — tải lại trước khi cho phép gửi."
                    )
                # AMENDED: bác sĩ phải nhìn đúng amendment mới nhất.
                if locked_state == "AMENDED":
                    latest = locked["latest_amendment_id"]
                    if expected_amendment_id != latest:
                        raise ConflictError(
                            "Hồ sơ vừa được đính chính — tải lại trước khi "
                            "cho phép gửi."
                        )
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
        expected_revision: int | None = None,
        expected_rx: str | None = None,
    ) -> dict[str, Any]:
        """Đính chính bản đã ký: tạo phiên bản mới, GIỮ NGUYÊN bản cũ.

        Nếu bản cũ ĐÃ được cho phép gửi thì thu hồi quyền gửi và tạo việc thông
        báo lại cho CSKH — Notion §6: *"Nếu bản cũ đã gửi cho bệnh nhân, hệ
        thống phải tạo công việc thông báo lại."*
        """
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("Đính chính bắt buộc phải ghi lý do.")
        corrected = {
            k: v
            for k, v in (corrected or {}).items()
            if k in REQUIRED_SOAP or k == "don_thuoc"
        }
        if not corrected:
            raise ValidationError(
                "Chưa có nội dung nào được sửa. Chọn ít nhất một mục."
            )
        if expected_revision is None:
            raise ValidationError(
                "Thiếu expected_revision — tải lại bệnh án trước khi đính chính."
            )
        rx_requested = "don_thuoc" in corrected
        if rx_requested:
            corrected = {
                **corrected,
                "don_thuoc": validate_amendment_prescriptions(corrected["don_thuoc"]),
            }
        if rx_requested and not expected_rx:
            raise ValidationError(
                "Thiếu expected_rx — tải lại bệnh án trước khi đính chính đơn thuốc."
            )
        if rx_requested and len(reason) < 5:
            raise ValidationError("Lý do đính chính đơn thuốc phải có ít nhất 5 ký tự.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Quyền hỏi ĐẦU TIÊN trong giao dịch, trước khi tìm lượt.
                await doi_quyen(
                    conn,
                    identity,
                    "clinical.consult.finalize",
                    cau="Bạn chưa được cấp quyền đính chính hồ sơ.",
                )
                # Tách statement khóa khỏi statement đọc revision/release.
                # Ở READ COMMITTED, join/subquery trong chính SELECT FOR UPDATE
                # có thể giữ snapshot cũ sau khi chờ transaction trước commit.
                locked_visit = await conn.fetchval(
                    "SELECT visit_id FROM public.visit"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    " FOR UPDATE",
                    identity.clinic_id,
                    visit_id,
                )
                if locked_visit is None:
                    raise ValidationError("Không tìm thấy lượt khám ở phòng khám này.")
                visit = await conn.fetchrow(
                    """
                    SELECT v.status, v.clinic_patient_id::text,
                           v.attending_doctor_id::text,
                           cr.revision AS record_revision,
                           EXISTS (
                               SELECT 1 FROM public.clinical_release r
                                WHERE r.clinic_id = v.clinic_id
                                  AND r.visit_id = v.visit_id
                                  AND r.revoked_at IS NULL
                           ) AS was_released
                      FROM public.visit v
                      LEFT JOIN public.clinical_record cr
                             ON cr.clinic_id = v.clinic_id
                            AND cr.visit_id = v.visit_id
                     WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                    """,
                    identity.clinic_id,
                    visit_id,
                )
                assert visit is not None
                _assert_amend_authority(identity, visit["attending_doctor_id"])
                if visit["status"] not in ("FINALIZED", "AMENDED"):
                    raise ValidationError(
                        "Hồ sơ chưa hoàn tất thì sửa trực tiếp, không cần đính chính."
                    )
                if visit["record_revision"] != expected_revision:
                    raise ConflictError(
                        "Bệnh án vừa thay đổi — tải lại trước khi đính chính."
                    )
                was_released = bool(visit["was_released"])

                rx_plan = None
                if rx_requested:
                    assert expected_rx is not None
                    rx_plan = await chuan_bi_don_da_ky(
                        conn,
                        visit_id=visit_id,
                        clinic_id=identity.clinic_id,
                        prescriptions=corrected["don_thuoc"],
                        identity=identity,
                        expected_rx=expected_rx,
                    )
                    if not rx_plan.changed:
                        corrected.pop("don_thuoc")
                        rx_requested = False
                if not corrected:
                    raise ValidationError(
                        "Chưa có nội dung nào được sửa. Chọn ít nhất một mục."
                    )

                soap_corrected = {
                    key: value
                    for key, value in corrected.items()
                    if key in REQUIRED_SOAP
                }
                before = await conn.fetchrow(
                    "SELECT soap_subjective, soap_objective, soap_assessment,"
                    "       soap_plan"
                    "  FROM public.clinical_record"
                    " WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
                    visit_id,
                    identity.clinic_id,
                )
                # asyncpg trả jsonb về dạng CHUỖI. Giải mã để "giá trị
                # trước" trong visit_amendment là JSON thật, không phải một
                # chuỗi JSON bị đóng gói hai lần.
                original = {
                    key: _loads(before[key]) if before else None
                    for key in soap_corrected
                }
                corrected_values: dict[str, Any] = dict(soap_corrected)
                if rx_requested and rx_plan is not None:
                    original["don_thuoc"] = rx_plan.original_snapshot
                    corrected_values["don_thuoc"] = rx_plan.corrected_snapshot

                amendment_id = str(uuid.uuid4())

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
                await conn.execute(
                    """
                    INSERT INTO public.visit_amendment
                        (amendment_id, clinic_id, visit_id, amended_by,
                         reason, corrected_fields,
                         original_values, corrected_values)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid,
                            $5, $6, $7::jsonb, $8::jsonb)
                    """,
                    amendment_id,
                    identity.clinic_id,
                    visit_id,
                    identity.staff_id,
                    reason,
                    list(corrected.keys()),
                    json.dumps(original, ensure_ascii=False),
                    json.dumps(corrected_values, ensure_ascii=False),
                )
                await conn.execute(
                    "SELECT set_config('clinicai.amendment_id', $1, true)",
                    amendment_id,
                )

                if soap_corrected:
                    sets = ", ".join(
                        f"{key} = ${index + 2}::jsonb"
                        for index, key in enumerate(soap_corrected)
                    )
                    await conn.execute(  # noqa: S608 — keys từ REQUIRED_SOAP
                        f"UPDATE public.clinical_record SET {sets}, updated_at = now()"
                        f" WHERE visit_id = $1::uuid"
                        f" AND clinic_id = ${len(soap_corrected) + 2}::uuid",
                        visit_id,
                        *(
                            json.dumps(value, ensure_ascii=False)
                            for value in soap_corrected.values()
                        ),
                        identity.clinic_id,
                    )

                rx_result: dict[str, Any] | None = None
                if rx_requested and rx_plan is not None:
                    rx_result = await ap_dung_don_da_ky(
                        conn,
                        plan=rx_plan,
                        amendment_id=amendment_id,
                        visit_id=visit_id,
                        clinic_id=identity.clinic_id,
                        clinic_patient_id=visit["clinic_patient_id"],
                        created_by=identity.staff_id,
                        identity=identity,
                        reason=reason,
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
                         WHERE visit_id = $1::uuid AND clinic_id = $4::uuid
                           AND revoked_at IS NULL
                        """,
                        visit_id,
                        identity.staff_id,
                        f"Hồ sơ được đính chính: {reason}",
                        identity.clinic_id,
                    )
                    await _create_renotify_task(
                        conn,
                        identity,
                        visit_id,
                        reason,
                        amendment_id=amendment_id,
                    )

                await _log(
                    conn,
                    identity,
                    visit_id,
                    "clinical.amended",
                    {
                        "fields": list(corrected.keys()),
                        "was_released": was_released,
                        "amendment_id": amendment_id,
                        "correction_id": (
                            rx_result["correction_id"] if rx_result else None
                        ),
                    },
                    correlation_id=amendment_id,
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
            "amendment_id": amendment_id,
        }

    async def sign_ultrasound(
        self, *, identity: StaffIdentity, ultrasound_id: str
    ) -> dict[str, Any]:
        """Bác sĩ siêu âm ký kết quả CỦA MÌNH."""
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                "result.review.approve",
                cau="Bạn chưa có quyền ký kết quả.",
            )
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
            # ký hộ là ghi sai người chịu trách nhiệm chuyên môn. "Của mình" =
            # người thực hiện ghi trên phiếu, HOẶC bác sĩ đã nhận ca siêu âm
            # (work_item.assigned_to, 15/09/2026) — phiếu cũ do thư ký lưu nháp
            # trước từng ghi thư ký làm người thực hiện và khoá bác sĩ thật.
            nhan_ca = await conn.fetchval(
                "SELECT w.assigned_to::text FROM public.work_item w"
                "  JOIN public.ultrasound_record u ON u.visit_id = w.visit_id"
                " WHERE u.ultrasound_id = $1::uuid AND w.clinic_id = $2::uuid"
                "   AND w.node_code = 'DICHVU-SIEUAM' AND w.status <> 'CANCELLED'"
                " ORDER BY w.created_at DESC LIMIT 1",
                ultrasound_id,
                identity.clinic_id,
            )
            if (
                row["performed_by"]
                and str(row["performed_by"]) != str(identity.staff_id)
                and nhan_ca != str(identity.staff_id)
            ):
                raise ValidationError(
                    "Chỉ bác sĩ đã thực hiện ca siêu âm này mới ký được."
                )
            await conn.execute(
                "UPDATE public.ultrasound_record"
                "   SET signed_by = $2::uuid, signed_at = now(), updated_at = now(),"
                "       performed_by = $2::uuid"
                " WHERE ultrasound_id = $1::uuid AND clinic_id = $3::uuid",
                ultrasound_id,
                identity.staff_id,
                identity.clinic_id,
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
    phieu = _loads(row.get("phieu_chuyen_khoa")) or {}
    if not isinstance(phieu, dict):
        phieu = {}

    def phieu_co(*khoa: str, tien_to: tuple[str, ...] = ()) -> bool:
        for k, v in phieu.items():
            if (k in khoa or k.startswith(tien_to)) and not _blank_json(v):
                return True
        return False

    # HMVS "ĐANG TIẾP TỤC ĐÁNH GIÁ" (S0-8, Target Contract 18/09/2026): nguồn
    # HMVS cho phép hồ sơ chưa kết luận nguyên nhân; ký được khi bác sĩ chọn rõ
    # trạng thái ấy VÀ có kế hoạch tiếp theo. Không nhận "đang đánh giá" viết
    # lách vào ô chẩn đoán phân biệt.
    dang_danh_gia = phieu.get("cd_trang_thai") == "DANG_DANH_GIA"
    dang_danh_gia_co_ke_hoach = dang_danh_gia and phieu_co(*KHOA_KE_HOACH_TIEP_THEO)

    thay_the = {
        "soap_subjective": phieu_co("ly_do", "ly_do_khac", "benh_su")
        or not _blank_json(row.get("chief_complaint_at_visit")),
        "soap_objective": bool(row.get("co_sinh_hieu"))
        or phieu_co(tien_to=("kls_", "kham_")),
        "soap_assessment": phieu_co(*KHOA_CHAN_DOAN_PHIEU) or dang_danh_gia_co_ke_hoach,
        # Nội tiết (batch pilot 18/09): hướng xử trí của phiếu là quyết định /
        # phác đồ MHT và điều trị hỗ trợ — bản trước không biết các ô này nên
        # phiếu NT đã ghi đủ xử trí vẫn bị báo thiếu "Hướng xử trí".
        "soap_plan": phieu_co(
            "dieu_tri",
            "pp_dieu_tri",
            "loi_dan",
            "huong_xu_tri",
            "mht_quyet_dinh",
            "mht_phac_do",
            "dieu_tri_ho_tro",
            "dieu_tri_ho_tro_chi_tiet",
        ),
    }
    thieu = [
        label
        for field, label in REQUIRED_SOAP.items()
        if _blank_json(row.get(field)) and not thay_the.get(field, False)
    ]
    # Đang đánh giá mà chưa có kế hoạch: nói đúng cái còn thiếu, không chỉ
    # "Chẩn đoán" — bác sĩ đã chọn đúng trạng thái, cái thiếu là kế hoạch.
    #
    # Và KHÔNG lách được bằng chữ ở ô chẩn đoán (rà 18/09): "đang đánh giá" mà
    # có `cd_phan_biet` vẫn phải có kế hoạch tiếp theo mới ký.
    if dang_danh_gia and not dang_danh_gia_co_ke_hoach:
        thieu = [label for label in thieu if label != REQUIRED_SOAP["soap_assessment"]]
        thieu.append(THIEU_KE_HOACH_KHI_DANG_DANH_GIA)
    return thieu


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


def _optional_row_value(row: Any, key: str) -> Any:
    """Asyncpg Record và fake dict cùng trả None cho cột mới chưa stub."""
    try:
        return row[key]
    except KeyError:
        return None


def _assert_amend_authority(
    identity: StaffIdentity, attending_doctor_id: str | None
) -> None:
    """Chỉ bác sĩ chính của lượt đính chính (quyền đã hỏi bằng `doi_quyen`)."""
    if attending_doctor_id is None:
        raise SafetyGateError(
            "Lượt chưa có bác sĩ chính — chưa thể xác định quyền đính chính."
        )
    if attending_doctor_id != identity.staff_id:
        raise SafetyGateError(
            "Lượt này của bác sĩ khác — chỉ bác sĩ chính của lượt được đính chính."
        )


def _assert_release_doctor_is_attending(
    identity: StaffIdentity, attending_doctor_id: str | None
) -> None:
    """Bác sĩ cho phép gửi phải là bác sĩ chính của lượt.

    Kiểm SAU lock vì attending_doctor_id có thể đổi giữa lúc status() đọc
    (trước lock) và lúc transaction thật sự giữ lock.
    """
    if attending_doctor_id is None:
        raise SafetyGateError(
            "Lượt chưa có bác sĩ chính — chưa thể cho phép gửi bệnh án."
        )
    if attending_doctor_id != identity.staff_id:
        raise SafetyGateError(
            "Lượt này của bác sĩ khác — chỉ bác sĩ chính của lượt cho phép gửi."
        )


async def _create_renotify_task(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    visit_id: str,
    reason: str,
    *,
    amendment_id: str | None = None,
) -> None:
    """Việc cho CSKH: gọi lại báo bệnh nhân rằng kết quả đã đính chính."""
    row = await conn.fetchrow(
        "SELECT clinic_patient_id FROM public.visit"
        " WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
        visit_id,
        identity.clinic_id,
    )
    if row is None:
        return
    # VIỆC NÀY PHẢI HIỆN Ở MÀN CSKH, và trước 08/08/2026 nó không hiện.
    #
    # Nó từng chỉ ghi vào `cskh_action` với status 'PENDING'. Nhưng màn Quản lý
    # khách hàng nay lấy việc từ `v_trang_thai_cskh`, và view ấy không đọc
    # `cskh_action` (bảng đó là hàng nhập khẩu từ Notion, 0 dòng trên bản thật).
    # Nghĩa là: bác sĩ đính chính một kết quả ĐÃ GỬI CHO BỆNH NHÂN, và việc gọi
    # lại báo họ không xuất hiện ở đâu cả. Đây là loại việc mà bỏ sót thì bệnh
    # nhân đang cầm một tờ kết quả sai.
    #
    # Nay ghi vào `hen_goi_lai` — bảng việc mà view ĐỌC — với ngày gọi là HÔM
    # NAY. Vẫn giữ dòng `cskh_action` bên dưới cho nhật ký nhập khẩu cũ đọc
    # được liên tục.
    await conn.execute(
        """
        INSERT INTO public.hen_goi_lai
            (clinic_id, clinic_patient_id, ngay_goi, ly_do, tao_boi_staff_id)
        VALUES ($1::uuid, $2::uuid,
                (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, $3, $4::uuid)
        """,
        identity.clinic_id,
        row["clinic_patient_id"],
        f"Bác sĩ đã đính chính kết quả ĐÃ GỬI cho bệnh nhân. Lý do: {reason}."
        " Gọi lại và gửi bản mới.",
        identity.staff_id,
    )
    await conn.execute(
        """
        INSERT INTO public.cskh_action
            (clinic_id, source_ref, clinic_patient_id, category, status,
             description, visit_link_raw)
        VALUES ($1::uuid, $2, $3::uuid, 'Thông báo lại kết quả', 'PENDING', $4,
                $5)
        """,
        identity.clinic_id,
        f"amend:{amendment_id or visit_id}",
        row["clinic_patient_id"],
        f"Kết quả đã gửi cho bệnh nhân vừa được bác sĩ đính chính. Lý do: {reason}."
        " Cần liên hệ lại và gửi bản mới.",
        # GẮN LƯỢT KHÁM VÀO VIỆC. Không có khoá này thì màn CSKH không biết
        # việc đang nói về lượt khám nào, nên không đọc được bác sĩ đã cho phép
        # gửi lại chưa — và một việc "thông báo lại kết quả" mà không tra được
        # trạng thái duyệt là đúng thứ nguy hiểm mà cái chốt hai bước sinh ra
        # để chặn.
        visit_id,
    )


async def _log(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    visit_id: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO public.event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, correlation_id, source, event_published)
        VALUES ($1::uuid, $2, 'visit', $3::uuid, $4::jsonb, $5::jsonb,
                $6::uuid, 'api:clinical', FALSE)
        """,
        identity.clinic_id,
        event_type,
        visit_id,
        json.dumps(payload, ensure_ascii=False),
        json.dumps(
            # TÊN KHOÁ PHẢI KHỚP `audit.record_event`. File này từng ghi
            # `actor_staff_id`/`actor_role` trong khi mười đường ghi còn lại
            # dùng `clinic_staff_id`/`clinic_role` — và màn Lịch sử thao tác
            # tra theo tên chuẩn, nên dòng nào ghi bằng tên lệch sẽ hiện
            # "Hệ thống" thay vì tên bác sĩ đã ký bệnh án.
            #
            # Sửa được sạch vì đường này chưa phát dòng nào trên prod. Để chạy
            # rồi mới sửa thì view đọc phải gánh thêm một nhánh COALESCE nữa,
            # vĩnh viễn — event_log chỉ ghi thêm, không sửa lại được.
            {
                "actor_auth_user_id": identity.auth_user_id,
                "clinic_staff_id": identity.staff_id,
                "clinic_role": identity.role.value,
                # Vai tài khoản gốc (vai dùng có thể khác).
                "vai_tai_khoan": identity.vai_goc.value,
            }
        ),
        correlation_id,
    )
