"""Được phép ghép hồ sơ của người này vào màn hình của người kia không.

docs/spec-form-nam-khoa.md §6.5, mở rộng cho MỌI dịch vụ khám theo yêu cầu của
Quang (04/08/2026).

ĐIỀU PHẢI HIỂU ĐÚNG TRƯỚC KHI ĐỌC FILE NÀY.

Spec viết "RLS phải chặn vợ đọc hồ sơ NK". Rà lại thì tiền đề đó không đúng với
hệ thống hôm nay: `auth.users` có 0 tài khoản không phải nhân viên — bệnh nhân
KHÔNG đăng nhập, và `authenticated` trong mọi policy nghĩa là nhân viên phòng
khám.

Nên rủi ro thật là: bác sĩ mở hồ sơ hiếm muộn của người vợ, và hệ thống tự kéo
dữ liệu nam khoa của người chồng vào màn hình đó — rồi in lên phiếu kết quả của
người vợ. Đó là việc của TẦNG ỨNG DỤNG khi ghép dữ liệu, không phải của RLS.
Hàm dưới đây là thứ tầng ứng dụng phải hỏi trước khi ghép.

LIÊN KẾT KHÔNG PHẢI ĐỒNG Ý. Hai vợ chồng cùng đi khám hiếm muộn vẫn là hai
người bệnh với hai hồ sơ riêng; chồng có quyền không cho vợ biết kết quả tinh
dịch đồ, và hệ thống phải giữ được quyền đó.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.audit import record_event

logger = structlog.get_logger()

#: Phạm vi "mọi form". Một chuỗi riêng chứ không phải danh sách rỗng: rỗng đọc
#: được thành "chưa khai gì", còn ALL là một lựa chọn có chủ ý.
ALL_FORMS = "ALL"

#: Quan hệ được ghi nhận, khớp `patient_link_relation` ở database.
RELATIONS = frozenset({"SPOUSE", "PARTNER", "FAMILY"})

#: Ai được ghi liên kết và ghi đồng ý.
#:
#: Bản đồng ý phải dựa trên một tờ giấy có chữ ký bệnh nhân (`source_document`),
#: và người cầm tờ giấy đó là lễ tân hoặc CSKH. Nhưng nó quyết định ai đọc được
#: hồ sơ bệnh án của ai — nên không mở cho thu ngân, dược, hay bảng điều phối.
CONSENT_WRITE_ROLES = frozenset(
    {
        ClinicRole.MANAGEMENT,
        ClinicRole.DOCTOR,
        ClinicRole.RECEPTION,
        ClinicRole.CSKH,
        ClinicRole.TKYK,
    }
)


@dataclass(frozen=True)
class Consent:
    subject_patient_id: str
    grantee_patient_id: str
    form_codes: tuple[str, ...]
    revoked_at: datetime | None


def may_surface(
    *,
    subject_patient_id: str,
    viewing_patient_id: str,
    form_code: str,
    consents: list[Consent],
) -> bool:
    """Hồ sơ `form_code` của `subject` có được hiện trong buổi khám của
    `viewing` không.

    Cùng một người thì luôn được: hồ sơ của chính mình không cần ai đồng ý.

    Mặc định là KHÔNG. Một hàm quyết định quyền riêng tư phải nghiêng về từ
    chối khi thiếu dữ liệu — thiếu bản đồng ý và thiếu thông tin là hai chuyện
    khác nhau với người viết code, nhưng với bệnh nhân thì chỉ có một: dữ liệu
    của họ vừa hiện lên một màn hình họ không biết.
    """
    if subject_patient_id == viewing_patient_id:
        return True
    for c in consents:
        if c.revoked_at is not None:
            continue
        if c.subject_patient_id != subject_patient_id:
            continue
        if c.grantee_patient_id != viewing_patient_id:
            continue
        if ALL_FORMS in c.form_codes or form_code in c.form_codes:
            return True
    return False


_CONSENT_SQL = """
SELECT subject_patient_id, grantee_patient_id, form_codes, revoked_at
  FROM public.clinical_data_consent
 WHERE clinic_id = $1::uuid
   AND revoked_at IS NULL
   AND (subject_patient_id = $2::uuid OR grantee_patient_id = $2::uuid)
"""

_LINK_SQL = """
SELECT l.id, l.relation, l.patient_a, l.patient_b,
       CASE WHEN l.patient_a = $2::uuid THEN l.patient_b ELSE l.patient_a END
           AS other_patient_id,
       p.full_name AS other_name,
       p.patient_code AS other_code
  FROM public.patient_link l
  LEFT JOIN public.patient p
         ON p.clinic_patient_id = CASE WHEN l.patient_a = $2::uuid
                                       THEN l.patient_b ELSE l.patient_a END
        AND p.clinic_id = l.clinic_id
 WHERE l.clinic_id = $1::uuid
   AND $2::uuid IN (l.patient_a, l.patient_b)
"""


class ConsentService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def load(self, *, identity: StaffIdentity, patient_id: str) -> list[Consent]:
        rows = await self._pool.fetch(_CONSENT_SQL, identity.clinic_id, patient_id)
        return [
            Consent(
                subject_patient_id=str(r["subject_patient_id"]),
                grantee_patient_id=str(r["grantee_patient_id"]),
                form_codes=tuple(r["form_codes"] or ()),
                revoked_at=r["revoked_at"],
            )
            for r in rows
        ]

    async def linked_partners(
        self, *, identity: StaffIdentity, patient_id: str
    ) -> list[dict[str, Any]]:
        """Ai được liên kết với bệnh nhân này, và xem được form nào của họ.

        Trả về CẢ hai chiều để màn hình nói đúng câu: "chồng đã cho phép xem hồ
        sơ HMVS, chưa cho phép xem hồ sơ NK". Một danh sách chỉ nói "đã liên
        kết" sẽ được đọc thành "xem được hết".
        """
        links = await self._pool.fetch(_LINK_SQL, identity.clinic_id, patient_id)
        consents = await self.load(identity=identity, patient_id=patient_id)
        out: list[dict[str, Any]] = []
        for r in links:
            other = str(r["other_patient_id"])
            shared_to_me = next(
                (
                    list(c.form_codes)
                    for c in consents
                    if c.subject_patient_id == other
                    and c.grantee_patient_id == patient_id
                ),
                [],
            )
            shared_by_me = next(
                (
                    list(c.form_codes)
                    for c in consents
                    if c.subject_patient_id == patient_id
                    and c.grantee_patient_id == other
                ),
                [],
            )
            out.append(
                {
                    "link_id": str(r["id"]),
                    "relation": r["relation"],
                    "patient_id": other,
                    "full_name": r["other_name"],
                    "patient_code": r["other_code"],
                    #: Form của NGƯỜI KIA mà bệnh nhân này được xem.
                    "they_shared_with_this_patient": shared_to_me,
                    #: Form của bệnh nhân này mà người kia được xem.
                    "this_patient_shared_with_them": shared_by_me,
                }
            )
        return out

    # ── Đọc có chốt ────────────────────────────────────────────────────────
    #
    # ĐÂY LÀ CHỖ DUY NHẤT đọc được hồ sơ của một bệnh nhân trong buổi khám của
    # một bệnh nhân KHÁC. Mọi màn hình muốn ghép dữ liệu hai người phải đi qua
    # đây; `get_form` của clinical_form_service đọc theo `visit_id`, mà một buổi
    # khám chỉ thuộc một người, nên nó không ghép chéo được.

    async def shared_form(
        self,
        *,
        identity: StaffIdentity,
        subject_patient_id: str,
        viewing_patient_id: str,
        form_code: str,
    ) -> dict[str, Any]:
        """Hồ sơ `form_code` của `subject`, nếu `viewing` được phép xem.

        Không tìm thấy và không được phép trả về CÙNG một hình dạng "không có
        gì" cho màn hình, nhưng KHÁC nhau ở `allowed` — màn hình cần nói được
        "chồng chưa cho phép xem hồ sơ này" thay vì để trống, vì để trống sẽ
        được đọc thành "chưa khám" và bác sĩ sẽ chỉ định lại một lần nữa.
        """
        code = (form_code or "").strip().upper()
        if not code:
            raise ValidationError("Thiếu mã form")

        consents = await self.load(identity=identity, patient_id=viewing_patient_id)
        allowed = may_surface(
            subject_patient_id=subject_patient_id,
            viewing_patient_id=viewing_patient_id,
            form_code=code,
            consents=consents,
        )
        if not allowed:
            logger.info(
                "consent_denied",
                clinic_id=identity.clinic_id,
                form_code=code,
                staff_id=identity.staff_id,
            )
            return {"allowed": False, "form_code": code, "responses": []}

        rows = await self._pool.fetch(
            """
            SELECT r.id, r.visit_id, r.form_data, r.updated_at
              FROM public.clinical_form_response r
              JOIN public.visit v
                ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
             WHERE r.clinic_id = $1::uuid
               AND v.clinic_patient_id = $2::uuid
               AND r.service_code = $3
             ORDER BY r.updated_at DESC
             LIMIT 20
            """,
            identity.clinic_id,
            subject_patient_id,
            code,
        )
        return {
            "allowed": True,
            "form_code": code,
            "responses": [
                {
                    "id": str(r["id"]),
                    "visit_id": str(r["visit_id"]),
                    "form_data": r["form_data"],
                    "updated_at": (
                        r["updated_at"].isoformat() if r["updated_at"] else None
                    ),
                }
                for r in rows
            ],
        }

    # ── Ghi ────────────────────────────────────────────────────────────────

    async def link(
        self,
        *,
        identity: StaffIdentity,
        patient_a: str,
        patient_b: str,
        relation: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Ghi nhận hai bệnh nhân có quan hệ. KHÔNG mở quyền đọc gì cả."""
        rel = (relation or "").strip().upper()
        if rel not in RELATIONS:
            raise ValidationError(
                f"Quan hệ không hợp lệ: {relation!r}. "
                f"Chọn một trong {', '.join(sorted(RELATIONS))}."
            )
        if patient_a == patient_b:
            raise ValidationError("Không liên kết một người với chính mình.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await _must_exist(conn, identity, patient_a)
                await _must_exist(conn, identity, patient_b)
                try:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO public.patient_link
                            (clinic_id, patient_a, patient_b, relation,
                             created_by, note)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5::uuid, $6)
                        RETURNING id
                        """,
                        identity.clinic_id,
                        patient_a,
                        patient_b,
                        rel,
                        identity.staff_id,
                        note,
                    )
                except asyncpg.UniqueViolationError as exc:
                    # Liên kết đối xứng: (B,A) đụng đúng chỉ mục của (A,B).
                    raise ConflictError(
                        "Hai bệnh nhân này đã được liên kết rồi."
                    ) from exc
                assert row is not None
                link_id = str(row["id"])
                await record_event(
                    conn,
                    event_type="patient_link.created",
                    aggregate_type="patient_link",
                    aggregate_id=link_id,
                    identity=identity,
                    origin="api:patient-consent",
                    payload={
                        "patient_a": patient_a,
                        "patient_b": patient_b,
                        "relation": rel,
                    },
                )
        return {"link_id": link_id, "relation": rel}

    async def grant(
        self,
        *,
        identity: StaffIdentity,
        subject_patient_id: str,
        grantee_patient_id: str,
        form_codes: list[str],
        source_document: str,
    ) -> dict[str, Any]:
        """Ghi nhận: `subject` đồng ý cho `grantee` xem những form này."""
        codes = [c.strip().upper() for c in form_codes if c and c.strip()]
        if not codes:
            raise ValidationError(
                "Phải nêu rõ form nào được chia sẻ, hoặc 'ALL' cho tất cả."
            )
        doc = (source_document or "").strip()
        if not doc:
            raise ValidationError(
                "Thiếu bản đồng ý có chữ ký — không ghi đồng ý chia sẻ hồ sơ "
                "chỉ dựa trên lời nói."
            )
        if subject_patient_id == grantee_patient_id:
            raise ValidationError("Hồ sơ của chính mình không cần đồng ý.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                try:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO public.clinical_data_consent
                            (clinic_id, subject_patient_id, grantee_patient_id,
                             form_codes, granted_by_staff_id, source_document)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::text[],
                                $5::uuid, $6)
                        RETURNING id
                        """,
                        identity.clinic_id,
                        subject_patient_id,
                        grantee_patient_id,
                        codes,
                        identity.staff_id,
                        doc,
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise ConflictError(
                        "Đã có một bản đồng ý đang hiệu lực cho cặp này. Thu "
                        "hồi bản cũ trước khi ghi bản mới."
                    ) from exc
                except asyncpg.ForeignKeyViolationError as exc:
                    # Trigger `clinical_data_consent_needs_link` dùng mã lỗi này.
                    raise ValidationError(str(exc).split("\n")[0]) from exc
                assert row is not None
                consent_id = str(row["id"])
                await record_event(
                    conn,
                    event_type="clinical_data_consent.granted",
                    aggregate_type="clinical_data_consent",
                    aggregate_id=consent_id,
                    identity=identity,
                    origin="api:patient-consent",
                    payload={
                        "subject_patient_id": subject_patient_id,
                        "grantee_patient_id": grantee_patient_id,
                        # MÃ form, không phải nội dung form.
                        "form_codes": codes,
                    },
                )
        return {"consent_id": consent_id, "form_codes": codes}

    async def revoke(
        self, *, identity: StaffIdentity, consent_id: str, reason: str
    ) -> dict[str, Any]:
        """Thu hồi — GHI THÊM chứ không xoá, và bắt buộc có lý do.

        "Đã từng đồng ý" là một sự thật đã xảy ra. Nếu dữ liệu đã được đọc thì
        việc thu hồi không làm điều đó chưa từng xảy ra, và xoá dòng cũ chỉ làm
        mất câu trả lời cho "vì sao hôm ấy màn hình hiện được".
        """
        why = (reason or "").strip()
        if not why:
            raise ValidationError("Phải ghi lý do thu hồi.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    UPDATE public.clinical_data_consent
                       SET revoked_at = now(), revoked_by = $3::uuid,
                           revoke_reason = $4
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                       AND revoked_at IS NULL
                    RETURNING id
                    """,
                    consent_id,
                    identity.clinic_id,
                    identity.staff_id,
                    why,
                )
                if row is None:
                    raise NotFoundError(
                        "Không tìm thấy bản đồng ý đang hiệu lực với mã này."
                    )
                await record_event(
                    conn,
                    event_type="clinical_data_consent.revoked",
                    aggregate_type="clinical_data_consent",
                    aggregate_id=consent_id,
                    identity=identity,
                    origin="api:patient-consent",
                    payload={"reason": why},
                )
        return {"consent_id": consent_id, "revoked": True}


async def _must_exist(
    conn: asyncpg.Connection, identity: StaffIdentity, patient_id: str
) -> None:
    """Bệnh nhân phải thuộc phòng khám này.

    `patient_link.patient_a/b` KHÔNG có khoá ngoại (bệnh nhân định danh bằng
    `clinic_patient_id`, không phải khoá chính của bảng), nên database không tự
    bắt được một id gõ nhầm — nó sẽ nằm im ở đó cho tới lúc ai đó tin nó.
    """
    ok = await conn.fetchval(
        "SELECT 1 FROM public.patient "
        "WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
        patient_id,
        identity.clinic_id,
    )
    if not ok:
        raise NotFoundError(f"Không tìm thấy bệnh nhân {patient_id}")
