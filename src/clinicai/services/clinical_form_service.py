"""Specialty exam forms attached to a visit (W5, ADR-0012).

Ported from ``src/dashboard/app/api/clinical-form/route.ts``. The rule that
matters is the finalisation gate:

    A visit with status FINALIZED is READ-ONLY. Correcting a closed record goes
    through the amendment flow (ADR-0008) — never by editing the form and never
    by quietly flipping visit.status back.

The route enforced that in the application layer because the append-only
migration was still pending. It is enforced here for the same reason, and the
comment is kept so nobody mistakes it for belt-and-braces.

WHICH LIST THE CODE IS CHECKED AGAINST. ``service_code`` is a FORM code — PK,
SK, NT, HMVS, NK — not a ``service_type`` code. ClinicalRecordForm derives it
from the service *name* via ``resolveServiceCode`` and ServiceFormEngine sends
it, so that is what the column has always held.

This first validated against ``service_type`` instead, on the reasoning that the
backend cannot see ``lib/form-schemas``. That reasoning was right and the
conclusion was wrong: the two vocabularies do not intersect, so every save
failed once the route was switched over — the catalogue code refused by Next,
the UI's code refused here. The list of forms now lives in
``clinical_form_catalogue`` (migration 20260730000011), which is the fix ADR-0011
anticipated: config as data, readable by both sides. Rendering stays in the
frontend; this only answers whether the clinic uses that form at all.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.phieu_kham.doc_chu import noi_dung_phieu
from clinicai.phieu_kham.mang_sang import MA_CHAN_DOAN, chan_doan_tu_phieu
from clinicai.services.audit import record_event
from clinicai.services.sinh_hieu_buoi import chi_so_do, sinh_hieu_cua_buoi
from clinicai.services.thu_ky_bac_si import bac_si_cua_thu_ky, kiem_thu_ky_duoc_lam

logger = structlog.get_logger()

# Trạng thái lượt khám còn GHI ĐƯỢC hồ sơ.
#
# Danh sách TRẮNG, không phải kiểm `!= FINALIZED`. Cố ý: một trạng thái CUỐI
# thêm sau này sẽ không lọt qua được, còn danh sách đen thì lọt.
#
# INCOMPLETE (khách về giữa chừng) nằm TRONG danh sách này. Nó là trạng thái
# KHÔNG-CUỐI: khách còn quay lại, và khoá bút lúc này là bắt bác sĩ phải đính
# chính một hồ sơ chưa ai ký. FINALIZED và AMENDED thì bất biến theo Thông tư 13.
WRITABLE_VISIT_STATUSES: frozenset[str] = frozenset(
    {"OPEN", "IN_PROGRESS", "INCOMPLETE"}
)


def actor_label(identity: StaffIdentity) -> str:
    """``created_by``/``updated_by`` are free text; keep the route's format."""
    return f"{identity.role.value} · {identity.staff_id}"


def coerce_form_data(raw: Any) -> dict[str, Any]:
    """A form response is an object. Anything else is stored as an empty one.

    Mirrors the route: a list or a scalar is not a partially-valid form, and
    guessing at it would put unreadable data on a clinical record.
    """
    if isinstance(raw, dict):
        return raw
    return {}


class ClinicalFormService:
    """Read and upsert specialty exam forms."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_form(
        self, *, visit_id: str, service_code: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            SELECT form_data, updated_at
              FROM clinical_form_response
             WHERE visit_id = $1::uuid AND service_code = $2
               AND clinic_id = $3::uuid
            """,
            visit_id,
            service_code.upper(),
            identity.clinic_id,
        )
        # Số đo sinh hiệu MỚI NHẤT của BUỔI — màn phiếu hiện kèm (24/09/2026:
        # route giao diện thôi tự đọc `vital_measurement` bằng Supabase; 29/09:
        # lượt check-in thêm cùng ngày không đo lại vẫn có số của buổi).
        async with self._pool.acquire() as conn:
            sinh_hieu_moi = chi_so_do(
                await sinh_hieu_cua_buoi(conn, identity.clinic_id, visit_id)
            )
        if row is None:
            return {"form_data": {}, "updated_at": None, "sinh_hieu_moi": sinh_hieu_moi}
        return {
            "form_data": _as_dict(row["form_data"]),
            "updated_at": row["updated_at"],
            "sinh_hieu_moi": sinh_hieu_moi,
        }

    async def lich_su_kham(
        self, *, clinic_patient_id: str, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        """Các lượt khám TRƯỚC của một bệnh nhân, mới nhất trước.

        Trả về ĐỦ `form_data` để màn hình dựng lại nguyên phiếu hôm đó — bác sĩ
        bấm vào một ngày là thấy lại chính những gì đã ghi, không phải một bản
        tóm tắt do ai đó chọn hộ.

        `visit_id` đi kèm để màn hình phân biệt "đang xem lại" với "đang khám":
        phiếu cũ mở ở chế độ CHỈ XEM. Không có ranh giới đó thì bác sĩ gõ vào
        một phiếu tưởng là hôm nay và ghi đè lên bệnh án tháng trước.

        HAI NGUỒN (29/09/2026 — Tuyền: "lượt khám trước không thấy phiếu v5"):
        lượt có phiếu v5 (`phieu_kham_luot`) lấy phiếu v5 làm chuẩn — MỘT dòng
        mỗi lượt (phiếu sửa gần nhất, đúng phiếu Bàn khám mở), `phieu_v5: true`,
        `form_data` là {khoá ô: chữ đọc được} theo khung (chẩn đoán đứng đầu),
        kèm `chan_doan`. Lượt không có phiếu v5 đọc bảng đời cũ như trước.
        """
        async with self._pool.acquire() as conn:
            cu = await conn.fetch(
                """
                SELECT r.visit_id::text,
                       r.service_code,
                       r.form_data,
                       r.updated_at,
                       v.checked_in_at,
                       v.status        AS visit_status,
                       s.full_name     AS bac_si,
                       st.name         AS ten_dich_vu
                  FROM clinical_form_response r
                  JOIN visit v
                    ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
                  LEFT JOIN staff s ON s.id = v.attending_doctor_id
                  LEFT JOIN appointment a ON a.id = v.appointment_id
                  LEFT JOIN service_type st
                    ON st.id = a.service_type_id AND st.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid
                   AND v.clinic_patient_id = $2::uuid
                   AND NOT EXISTS (
                       SELECT 1 FROM phieu_kham_luot p
                        WHERE p.clinic_id = r.clinic_id
                          AND p.visit_id = r.visit_id)
                 ORDER BY coalesce(v.checked_in_at, r.updated_at) DESC
                 LIMIT 20
                """,
                identity.clinic_id,
                clinic_patient_id,
            )
            v5 = await conn.fetch(
                """
                SELECT DISTINCT ON (p.visit_id)
                       p.visit_id::text,
                       p.form_id       AS service_code,
                       p.du_lieu,
                       d.khung,
                       p.sua_luc       AS updated_at,
                       v.checked_in_at,
                       v.status        AS visit_status,
                       s.full_name     AS bac_si,
                       st.name         AS ten_dich_vu
                  FROM phieu_kham_luot p
                  JOIN visit v
                    ON v.visit_id = p.visit_id AND v.clinic_id = p.clinic_id
                  JOIN form_definition d
                    ON d.clinic_id = p.clinic_id AND d.form_id = p.form_id
                   AND d.version = p.version
                  LEFT JOIN staff s ON s.id = v.attending_doctor_id
                  LEFT JOIN service_type st
                    ON st.id = v.service_type_id AND st.clinic_id = v.clinic_id
                 WHERE p.clinic_id = $1::uuid
                   AND v.clinic_patient_id = $2::uuid
                 ORDER BY p.visit_id, p.sua_luc DESC
                """,
                identity.clinic_id,
                clinic_patient_id,
            )

        def chung(r: asyncpg.Record) -> dict[str, Any]:
            return {
                "visit_id": r["visit_id"],
                "service_code": r["service_code"],
                "ten_dich_vu": r["ten_dich_vu"],
                "bac_si": r["bac_si"],
                "kham_luc": r["checked_in_at"] or r["updated_at"],
                "visit_status": r["visit_status"],
            }

        ra = [
            {**chung(r), "form_data": _as_dict(r["form_data"]), "phieu_v5": False}
            for r in cu
        ]
        for r in v5:
            du_lieu = _as_dict(r["du_lieu"])
            chu = {
                d["ma"]: d["chu"]
                for m in noi_dung_phieu(r["khung"], du_lieu)
                for d in m["dong"]
            }
            chan_doan = chan_doan_tu_phieu(du_lieu)
            ma_cd = next((k for k in MA_CHAN_DOAN if k in chu), None)
            if ma_cd is not None:
                chu = {ma_cd: chu[ma_cd], **chu}
            ra.append(
                {
                    **chung(r),
                    "form_data": chu,
                    "phieu_v5": True,
                    "chan_doan": chan_doan,
                }
            )
        ra.sort(key=lambda x: x["kham_luc"], reverse=True)
        return ra[:20]

    async def save_form(
        self,
        *,
        visit_id: str,
        service_code: str,
        form_data: Any,
        identity: StaffIdentity,
        ghep: bool = False,
        bo_truong: list[str] | None = None,
    ) -> None:
        """Upsert one form for one visit. Refuses once the visit is finalised.

        `ghep=True`: `form_data` là CÁC Ô VỪA ĐỔI, ghép vào bản đang lưu (jsonb
        `||`) và bỏ các khoá trong `bo_truong`. Ghi cả phiếu (mặc định) là
        người lưu sau đè sạch người lưu trước — đo được 17/09/2026: thư ký gõ
        PARA cùng lúc bác sĩ gõ Dị ứng thuốc, chữ của thư ký mất.
        """
        code = (service_code or "").strip().upper()
        if not code:
            raise ValidationError("Thiếu service_code")

        payload = coerce_form_data(form_data)
        actor = actor_label(identity)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Bác sĩ của lượt: CÙNG nguồn với bệnh án SOAP (bác sĩ của lịch
                # hẹn), lùi về bác sĩ phụ trách lượt khi lượt không có lịch.
                # Khóa visit (FOR UPDATE OF v) để đồng bộ với transaction ký (sign),
                # ngăn form bị sửa quanh/sau chữ ký mà không đi qua AMENDED.
                visit = await conn.fetchrow(
                    "SELECT v.visit_id, v.status,"
                    " coalesce(a.doctor_id, v.attending_doctor_id)::text AS bac_si"
                    " FROM visit v LEFT JOIN appointment a"
                    " ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id"
                    " WHERE v.visit_id = $1::uuid AND v.clinic_id = $2::uuid"
                    " FOR UPDATE OF v",
                    visit_id,
                    identity.clinic_id,
                )
                if visit is None:
                    raise NotFoundError("Không tìm thấy buổi khám")
                if visit["status"] not in WRITABLE_VISIT_STATUSES:
                    raise ConflictError(
                        "Hồ sơ không còn ở trạng thái cho phép sửa — luật cấm sửa. "
                        "Phải đính chính qua luồng AMENDED."
                    )
                # S0-4 (18/09/2026): thư ký chỉ ghi phiếu cho bác sĩ mình được
                # phân — y hệt bệnh án SOAP. Trước bản này phiếu chuyên khoa bỏ
                # qua bước kiểm này. (Công tắc mở quyền tạm BẬT thì hàm tự bỏ
                # qua — xem thu_ky_bac_si.bac_si_cua_thu_ky.)
                if identity.co_vai({ClinicRole.TKYK}):
                    kiem_thu_ky_duoc_lam(
                        await bac_si_cua_thu_ky(conn, identity), visit["bac_si"]
                    )

                known_code = await conn.fetchval(
                    "SELECT 1 FROM clinical_form_catalogue "
                    "WHERE form_code = $1 AND is_active "
                    "AND clinic_id = $2::uuid "
                    "LIMIT 1",
                    code,
                    identity.clinic_id,
                )
                if not known_code:
                    raise ValidationError(f"Phòng khám chưa dùng phiếu: {code}")

                # created_by is stamped once and never overwritten — it answers
                # "who opened this form", which an update must not rewrite.
                await conn.execute(
                    """
                    INSERT INTO clinical_form_response
                        (clinic_id, visit_id, service_code, form_data,
                         created_by, updated_by)
                    VALUES ($5::uuid, $1::uuid, $2, $3, $4, $4)
                    ON CONFLICT ON CONSTRAINT uq_clinical_form_visit_service
                    DO UPDATE SET
                        form_data  = CASE WHEN $6::boolean
                            THEN (coalesce(clinical_form_response.form_data,
                                           '{}'::jsonb)
                                  || EXCLUDED.form_data) - $7::text[]
                            ELSE EXCLUDED.form_data END,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = now()
                    """,
                    visit_id,
                    code,
                    json.dumps(payload),
                    actor,
                    identity.clinic_id,
                    ghep,
                    list(bo_truong or []),
                )

                # Phiếu khám là ghi chép lâm sàng. Lưu MÃ phiếu và các nhóm
                # trường đã điền, KHÔNG lưu giá trị — /audit-log mở cho vai vận
                # hành, còn nội dung phiếu thì không.
                await record_event(
                    conn,
                    event_type="clinical_form.saved",
                    aggregate_type="clinical_form_response",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin="api:clinical-form",
                    payload={
                        "visit_id": visit_id,
                        "service_code": code,
                        "field_groups": (
                            sorted(payload.keys()) if isinstance(payload, dict) else []
                        ),
                    },
                )

        logger.info(
            "clinical_form_saved",
            visit_id=visit_id,
            service_code=code,
            by_staff_id=identity.staff_id,
        )


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return value or {}
