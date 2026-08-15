"""Patient CRUD service using asyncpg pool."""

from __future__ import annotations

import datetime
import json
import re
from typing import Any
from uuid import UUID

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.core.phone import normalize_vn_phone
from clinicai.core.phone import phone_variants as _phone_variants
from clinicai.schemas.patient import (
    DuplicateMatch,
    PatientCreateDTO,
    PatientCreateResult,
    PatientDTO,
    PatientUpdateDTO,
)

logger = structlog.get_logger()

# Ten digits, leading zero, a plausible Vietnamese prefix. Enforced server-side
# because the form is not the only caller.
PHONE_RE = re.compile(r"^0(2|3|5|7|8|9)\d{8}$")


def validate_phone(value: str | None, label: str) -> None:
    """Raise when a phone number is present but malformed."""
    phone = (value or "").strip()
    if phone and not PHONE_RE.match(phone):
        raise ValidationError(
            f"{label} không hợp lệ (10 số, bắt đầu bằng 0; đầu số 02/03/05/07/08/09)."
        )


# Columns written on INSERT, in order (patient_code prepended at call site).
_INSERT_COLUMNS = (
    "full_name",
    "date_of_birth",
    "phone_primary",
    "phone_secondary",
    "national_id_number",
    "location_id",
    "is_active",
    "gender",
    "ethnicity",
    "nationality",
    "occupation",
    "patient_objection",
    "address",
    "guardian_name",
    "birth_year",
    "province_code",
    "province_name",
    "ward_code",
    "ward_name",
    "address_detail",
    "van_de_di_kham",
    "linh_vuc",
)


def _generate_patient_code(attempt: int = 0) -> str:
    """Generate a human-readable patient code: BN-YYYY-XXXXXX.

    Year + microsecond-resolution suffix; ``attempt`` adds jitter so a retry
    after a (rare) UNIQUE clash lands on a different code. The DB column has a
    UNIQUE constraint as the final safety net.
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    seq = (int(now.strftime("%f")) + attempt * 7919) % 1_000_000
    return f"BN-{now.year}-{seq:06d}"


def _record_to_dto(record: asyncpg.Record) -> PatientDTO:
    """Convert an asyncpg Record into a PatientDTO."""
    return PatientDTO.model_validate(dict(record))


# Every query below carries the tenant. The backend bypasses RLS, so a missing
# clinic_id is always supplied by the caller: identity.clinic_id is required,
# returns NULL once there are two — an un-plumbed caller then reads nothing
# instead of everything. Fail closed, and spelled out inline so it is visible.


class PatientService:
    """CRUD operations for the patient table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_patient(
        self, data: PatientCreateDTO, identity: StaffIdentity
    ) -> PatientCreateResult:
        """Register a patient: CCCD/phone guards → insert → non-blocking MPI.

        Order (mirrors the dashboard intake guard it replaces):
          0. Cơ sở phải CÓ THẬT và ĐANG HOẠT ĐỘNG.
          1. CCCD hard pre-check — UNIQUE, ``force`` does NOT override → 409.
          2. Phone soft block — same phone_primary already on file and not
             ``force`` → return ``duplicate`` WITHOUT inserting (operator decides).
          3. Insert all demographic fields with a generated patient_code.
          4. Run MPI dedup-queue in the background (never blocks the create).
        """
        clinic_id = identity.clinic_id

        async with self._pool.acquire() as conn, conn.transaction():
            # 0) CƠ SỞ — thêm khi nghiệm thu 11/08/2026. Hai lỗi, một chỗ sửa:
            #
            #   • `location_id` không tồn tại  → khoá ngoại `patient_location_id_fkey`
            #     nổ ở tầng DB, không ai bắt, trả về **HTTP 500 "An internal server
            #     error occurred."** Một mã 500 cho dữ liệu người dùng gửi sai là
            #     lỗi của mình, không phải của họ.
            #   • `location_id` trỏ tới cơ sở ĐÃ NGỪNG HOẠT ĐỘNG → khoá ngoại hợp lệ
            #     nên đi lọt, tạo hồ sơ ở một chi nhánh đã đóng cửa. Cái này tệ hơn
            #     vì nó im lặng: không lỗi, không cảnh báo, chỉ có một bệnh nhân
            #     nằm ở nơi không còn ai làm việc.
            #
            # Kiểm ở đây thay vì ở BFF vì BFF chạy bằng quyền của người dùng, mà
            # `clinic_location` không mở cho vai `authenticated` (đã đo: 401
            # permission denied). Và vì đây là luật nghiệp vụ — chỗ của nó là FastAPI.
            if data.location_id:
                co_so = await conn.fetchrow(
                    "SELECT name, is_active FROM clinic_location "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid;",
                    str(data.location_id),
                    clinic_id,
                )
                if co_so is None:
                    raise ValidationError("Không tìm thấy cơ sở này.")
                if not co_so["is_active"]:
                    raise ValidationError(
                        f"Cơ sở {co_so['name']} đã ngừng hoạt động — chọn cơ sở khác."
                    )

            # 1) CCCD hard conflict (cannot be forced — column is UNIQUE).
            if data.national_id_number:
                existing = await conn.fetchrow(
                    "SELECT patient_code, full_name FROM patient "
                    "WHERE national_id_number = $1 AND clinic_id = "
                    "$2::uuid LIMIT 1;",
                    data.national_id_number,
                    clinic_id,
                )
                if existing:
                    raise ConflictError(
                        f"CCCD này đã có hồ sơ "
                        f"({existing['patient_code']} · {existing['full_name']})."
                    )

            # 2) Phone soft block — warn, let the operator force (feedback #9).
            if data.phone_primary and not data.force:
                variants = _phone_variants(data.phone_primary)
                dupes = await conn.fetch(
                    "SELECT clinic_patient_id, patient_code, full_name, "
                    "date_of_birth FROM patient "
                    "WHERE (phone_primary = ANY($1::text[]) "
                    "OR phone_secondary = ANY($1::text[])) "
                    "AND clinic_id = $2::uuid LIMIT 5;",
                    variants,
                    clinic_id,
                )
                if dupes:
                    return PatientCreateResult(
                        duplicate=True,
                        matches=[DuplicateMatch(**dict(r)) for r in dupes],
                    )

            # 3) Insert (retry on the rare patient_code UNIQUE clash).
            dto = await self._insert_patient(conn, data, identity.clinic_id)

            # 4) Audit, in the same transaction as the row it describes. The
            # dashboard used to write this afterwards with the service-role key,
            # so a crash in between registered a patient nobody could account
            # for — and it was the last frontend write that bypassed RLS.
            await conn.execute(
                """
                INSERT INTO event_log
                    (clinic_id, event_type, aggregate_type, aggregate_id,
                     payload, metadata, source, event_published)
                VALUES ($5::uuid,
                        'patient.created', 'patient', $1, $2, $3, $4, FALSE)
                """,
                str(dto.clinic_patient_id),
                json.dumps(
                    {
                        "clinic_patient_id": str(dto.clinic_patient_id),
                        "patient_code": dto.patient_code,
                        "full_name": data.full_name,
                        "date_of_birth": (
                            data.date_of_birth.isoformat()
                            if data.date_of_birth
                            else None
                        ),
                        "phone_primary": data.phone_primary,
                        "phone_secondary": data.phone_secondary,
                        "national_id_number": data.national_id_number,
                        "location_id": (
                            str(data.location_id) if data.location_id else None
                        ),
                    }
                ),
                json.dumps(
                    {
                        "clinic_role": identity.role.value,
                        "clinic_staff_id": identity.staff_id,
                        "actor_auth_user_id": identity.auth_user_id,
                    }
                ),
                "api:patient-intake",
                identity.clinic_id,
            )

        # 5) MPI deduplication (non-blocking — must never fail the create).
        await self._mpi_autoqueue(dto, data, clinic_id)
        return PatientCreateResult(patient=dto)

    async def _insert_patient(
        self,
        conn: asyncpg.Connection,
        data: PatientCreateDTO,
        clinic_id: str,
    ) -> PatientDTO:
        """INSERT one patient row, generating patient_code with clash retry.

        clinic_id is written explicitly. There is no column DEFAULT to fall back
        on any more (20260730000014) and no caller without a tenant: an INSERT
        that forgets it fails on NOT NULL, loudly, instead of filing the patient
        under whichever clinic the database guessed.
        """
        placeholders = ", ".join(f"${i}" for i in range(1, len(_INSERT_COLUMNS) + 2))
        tenant = f"${len(_INSERT_COLUMNS) + 2}::uuid"
        query = (
            "INSERT INTO patient "
            f"(patient_code, {', '.join(_INSERT_COLUMNS)}, clinic_id) "
            f"VALUES ({placeholders}, {tenant}) RETURNING *;"
        )
        values: list[object] = [getattr(data, col) for col in _INSERT_COLUMNS]
        values.append(clinic_id)

        for attempt in range(5):
            patient_code = _generate_patient_code(attempt)
            try:
                # create_patient owns the outer transaction that also writes
                # the audit event. Each retry needs its own savepoint: after a
                # PostgreSQL UNIQUE violation the surrounding transaction is
                # aborted until that savepoint is rolled back.
                async with conn.transaction():
                    row = await conn.fetchrow(query, patient_code, *values)
            except asyncpg.UniqueViolationError as exc:
                constraint = (exc.constraint_name or "") + " " + str(exc)
                if "national_id" in constraint.lower():
                    # Race after the pre-check — report clearly, don't retry.
                    raise ConflictError(
                        "CCCD này vừa được tạo cho hồ sơ khác."
                    ) from exc
                # patient_code clash → regenerate and retry.
                logger.warning("patient_code_clash", patient_code=patient_code)
                continue
            logger.info(
                "patient_created",
                clinic_patient_id=str(row["clinic_patient_id"]),
                patient_code=patient_code,
            )
            return _record_to_dto(row)

        raise ValidationError("Không tạo được mã BN, thử lại.")

    async def _mpi_autoqueue(
        self, dto: PatientDTO, data: PatientCreateDTO, clinic_id: str
    ) -> None:
        """Queue a merge-review if MPI finds likely-same patients. Best-effort."""
        try:
            from clinicai.services.mpi_service import MPIService

            mpi = MPIService()
            candidates = await mpi.find_candidates(self._pool, data, clinic_id)
            if candidates:
                queued = await mpi.auto_queue_if_needed(
                    self._pool, dto.clinic_patient_id, candidates, clinic_id
                )
                if queued:
                    logger.info(
                        "mpi_auto_queued",
                        clinic_patient_id=str(dto.clinic_patient_id),
                        queue_count=len(queued),
                    )
        except Exception:
            logger.warning(
                "mpi_dedup_failed",
                clinic_patient_id=str(dto.clinic_patient_id),
                exc_info=True,
            )

    async def get_by_id(
        self, clinic_patient_id: UUID, clinic_id: str
    ) -> PatientDTO | None:
        """Fetch a single patient by primary key. Returns None if absent."""
        query = (
            "SELECT * FROM patient WHERE clinic_patient_id = $1 "
            "AND clinic_id = $2::uuid;"
        )
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, clinic_patient_id, clinic_id)
        if row is None:
            return None
        return _record_to_dto(row)

    async def get_summary_data(
        self, clinic_patient_id: UUID, clinic_id: str
    ) -> dict[str, Any] | None:
        """Return raw summary fields for the tools layer.

        Joins patient + EXISTS pregnancy(ONGOING) + MAX appointment(COMPLETED).
        Returns None if patient does not exist. The tool layer wraps the dict
        into PatientSummaryOutput — keeping shaping out of the service.
        """
        query = """
            SELECT
                p.clinic_patient_id,
                p.patient_code,
                p.full_name,
                p.phone_primary,
                p.date_of_birth,
                (
                    SELECT MAX(a.slot_start)::date
                    FROM appointment a
                    WHERE a.clinic_patient_id = p.clinic_patient_id
                      AND a.status = 'COMPLETED'
                ) AS last_visit_date,
                EXISTS (
                    SELECT 1 FROM pregnancy pr
                    WHERE pr.clinic_patient_id = p.clinic_patient_id
                      AND pr.outcome = 'ONGOING'
                ) AS active_pregnancy
            FROM patient p
            WHERE p.clinic_patient_id = $1
              AND p.clinic_id = $2::uuid;
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, clinic_patient_id, clinic_id)
        if row is None:
            return None
        return dict(row)

    async def get_by_phone(self, phone: str, clinic_id: str) -> list[PatientDTO]:
        """Return all patients matching a phone number (primary or secondary)."""
        variants = _phone_variants(phone)
        if not variants:
            return []
        query = """
            SELECT * FROM patient
            WHERE clinic_id = $2::uuid
              AND (phone_primary = ANY($1::text[])
                   OR phone_secondary = ANY($1::text[])
                   OR EXISTS (SELECT 1 FROM public.patient_sdt_them t
                               WHERE t.clinic_patient_id
                                     = patient.clinic_patient_id
                                 AND t.so_dien_thoai = ANY($1::text[])))
            ORDER BY created_at DESC;
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, variants, clinic_id)
        return [_record_to_dto(r) for r in rows]

    async def find_phone_duplicates(
        self, phone: str, clinic_id: str
    ) -> list[dict[str, Any]]:
        """Read-only: patients already on file with this phone (any spelling).

        Returns MINIMAL fields (full_name, patient_code, birth_year) for a soft
        "shared number?" warning at intake — never blocks creation. ``birth_year``
        comes from ``date_of_birth`` (year-only patients store ``YYYY-01-01``), so
        it does not depend on the optional ``birth_year`` column. Does NOT log the
        phone or names. Returns ``[]`` when the input has no digits.
        """
        variants = _phone_variants(phone)
        if not variants:
            return []
        query = """
            SELECT
                patient_code,
                full_name,
                EXTRACT(YEAR FROM date_of_birth)::int AS birth_year
            FROM patient
            WHERE clinic_id = $2::uuid
              AND (phone_primary = ANY($1::text[])
                   OR phone_secondary = ANY($1::text[])
                   OR EXISTS (SELECT 1 FROM public.patient_sdt_them t
                               WHERE t.clinic_patient_id
                                     = patient.clinic_patient_id
                                 AND t.so_dien_thoai = ANY($1::text[])))
            ORDER BY created_at DESC
            LIMIT 10;
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, variants, clinic_id)
        return [
            {
                "full_name": r["full_name"],
                "patient_code": r["patient_code"],
                "birth_year": r["birth_year"],
            }
            for r in rows
        ]

    async def update_patient(
        self,
        clinic_patient_id: UUID,
        data: PatientUpdateDTO,
        identity: StaffIdentity,
    ) -> PatientDTO:
        """Partial-update a patient. Only non-None fields are written.

        TENANT SCOPE. The backend connects as the database owner, so RLS does
        NOT apply to anything in this process — a query without clinic_id in its
        WHERE reaches every clinic. This one used to update by
        clinic_patient_id alone, which would have let a member of one clinic
        edit another's patient by id the moment a second tenant existed.
        ``identity`` is required: there is no caller without a tenant any
        more, and making it optional is what kept the guessing fallback alive.
        """
        updates = data.model_dump(exclude_none=True)
        # `sua_luc` là thẻ khoá lạc quan, KHÔNG phải cột — lấy ra trước khi dựng
        # câu SET, nếu không nó sẽ thành `sua_luc = $n` và câu lệnh nổ.
        sua_luc = updates.pop("sua_luc", None)
        if not updates:
            raise ValidationError("No fields to update")

        for column, label in (
            ("phone_primary", "SĐT chính"),
            ("phone_secondary", "SĐT người nhà"),
        ):
            if updates.get(column):
                validate_phone(str(updates[column]), label)

        # Build dynamic SET clause
        set_parts: list[str] = []
        values: list[object] = []
        for idx, (col, val) in enumerate(updates.items(), start=1):
            set_parts.append(f"{col} = ${idx}")
            values.append(val)

        # Always touch updated_at
        set_parts.append(f"updated_at = ${len(values) + 1}")
        values.append(datetime.datetime.now(tz=datetime.timezone.utc))

        # WHERE clause params. The tenant filter is unconditional — an earlier
        # version only added it when an identity was supplied, so a caller
        # without one updated across every clinic.
        values.append(clinic_patient_id)
        where_idx = len(values)
        values.append(identity.clinic_id if identity else None)
        tenant_idx = len(values)

        # KHOÁ LẠC QUAN. Chỉ ghi đè nếu hồ sơ dưới database vẫn đúng mốc mà máy
        # khách đã đọc. Ai chen vào giữa thì mốc đã đổi, câu UPDATE khớp 0 hàng,
        # và người bấm sau nhận được lời từ chối thay vì lặng lẽ xoá công của
        # người bấm trước.
        khoa_sql = ""
        if sua_luc is not None:
            values.append(sua_luc)
            khoa_sql = f"AND updated_at = ${len(values)} "

        query = (
            f"UPDATE patient SET {', '.join(set_parts)} "
            f"WHERE clinic_patient_id = ${where_idx} "
            f"AND clinic_id = ${tenant_idx}::uuid "
            f"{khoa_sql}"
            "RETURNING *;"
        )

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)

            if row is None and sua_luc is not None:
                # KHÔNG khớp 0 hàng vì hai lý do rất khác nhau: hồ sơ không tồn
                # tại, hay hồ sơ vừa bị người khác sửa. Trả nhầm "không tìm thấy"
                # cho trường hợp thứ hai là nói dối người dùng — họ đang nhìn
                # thẳng vào hồ sơ ấy trên màn hình.
                con_do = await conn.fetchrow(
                    "SELECT updated_at FROM patient "
                    "WHERE clinic_patient_id = $1 AND clinic_id = $2::uuid;",
                    clinic_patient_id,
                    identity.clinic_id if identity else None,
                )
                if con_do is not None:
                    raise ConflictError(
                        "Hồ sơ này vừa được người khác sửa. Mở lại để xem thay "
                        "đổi mới nhất rồi nhập lại — thay đổi của bạn CHƯA được "
                        "lưu."
                    )

        if row is None:
            raise ResourceNotFoundError(f"Patient {clinic_patient_id} not found")

        logger.info(
            "patient_updated",
            clinic_patient_id=str(clinic_patient_id),
            fields=list(updates.keys()),
        )
        return _record_to_dto(row)

    async def them_so_dien_thoai(
        self,
        *,
        clinic_patient_id: str,
        so_dien_thoai: str,
        loai: str,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Gắn thêm một số điện thoại vào hồ sơ CÓ SẴN (Tuyền 15/08/2026).

        Khách dùng 2–3 số; trước đây số thứ ba không có chỗ ghi nên người trực
        hoặc ghi đè số cũ hoặc tạo hồ sơ mới. Đường này sinh ra để ô cảnh báo
        trùng ở màn tạo bệnh nhân có một lối đi thứ ba: "đây đúng là khách cũ,
        thêm số cho họ" — thay vì chỉ hai lối "tạo mới" và "bỏ dở".

        Số được CHUẨN HOÁ trước khi ghi (dạng 0 + 9 số — CHECK của bảng cũng
        đòi đúng dạng ấy). Trùng với số đã có TRONG CHÍNH hồ sơ này → báo rõ,
        không ghi. Trùng với số của hồ sơ KHÁC thì vẫn cho — hai mẹ con dùng
        chung số là hợp lệ, cùng triết lý với phone_primary xưa nay.
        """
        if loai not in ("CHINH", "NGUOI_NHA"):
            raise ValidationError("Loại số phải là CHINH hoặc NGUOI_NHA.")
        chuan = normalize_vn_phone(so_dien_thoai)
        if chuan is None:
            raise ValidationError(
                "Số điện thoại không hợp lệ — cần 10 chữ số bắt đầu bằng 0."
            )
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                ho_so = await conn.fetchrow(
                    """
                    SELECT phone_primary, phone_secondary
                      FROM patient
                     WHERE clinic_patient_id = $1::uuid
                       AND clinic_id = $2::uuid
                    """,
                    clinic_patient_id,
                    identity.clinic_id,
                )
                if ho_so is None:
                    raise ResourceNotFoundError(
                        "Không tìm thấy hồ sơ khách ở phòng khám này."
                    )
                if chuan in (ho_so["phone_primary"], ho_so["phone_secondary"]):
                    raise ConflictError("Số này đã nằm trên hồ sơ của chính khách rồi.")
                da_ghi = await conn.fetchval(
                    """
                    INSERT INTO public.patient_sdt_them
                        (clinic_id, clinic_patient_id, so_dien_thoai, loai,
                         created_by_staff_id)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)
                    ON CONFLICT (clinic_patient_id, so_dien_thoai) DO NOTHING
                    RETURNING id
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    chuan,
                    loai,
                    identity.staff_id,
                )
                if da_ghi is None:
                    raise ConflictError("Số này đã được thêm cho khách từ trước.")
                # Ghi sổ thao tác — nhưng KHÔNG ghi số đầy đủ vào payload:
                # event_log sống lâu hơn mọi màn hình, 4 số cuối đủ để đối
                # chiếu khi cần mà không thành một bản sao danh bạ.
                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, metadata, source, event_published)
                    VALUES ($1::uuid, 'patient.phone_added', 'patient',
                            $2::uuid, $3::jsonb, $4::jsonb, 'api', FALSE)
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    json.dumps({"loai": loai, "duoi": chuan[-4:]}),
                    json.dumps(
                        {
                            "clinic_role": identity.role.value,
                            "clinic_staff_id": identity.staff_id,
                            "origin": "api",
                        }
                    ),
                )
        logger.info(
            "patient_phone_added",
            clinic_patient_id=clinic_patient_id,
            loai=loai,
        )
        return {"so_dien_thoai": chuan, "loai": loai}

    async def xoa_so_dien_thoai(
        self,
        *,
        clinic_patient_id: str,
        so_dien_thoai: str,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Gỡ một số THÊM khỏi hồ sơ (Tuyền 15/08/2026 — "cho phép xoá").

        Chỉ đụng bảng số-thêm: hai số chính thức trên hồ sơ sửa qua đường
        sửa-hồ-sơ như trước, mỗi cửa một việc. Xoá là xoá THẬT (không soft
        delete): số gỡ rồi mà còn tra ra là gọi nhầm người theo một số không
        còn của họ — cột tìm kiếm gộp tự tươi nhờ trigger. Vết "đã từng có,
        ai gỡ, lúc nào" nằm ở event_log, với 4 số cuối như lúc thêm.
        """
        chuan = normalize_vn_phone(so_dien_thoai)
        if chuan is None:
            raise ValidationError("Số điện thoại không hợp lệ.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                da_xoa = await conn.fetchval(
                    """
                    DELETE FROM public.patient_sdt_them
                     WHERE clinic_id = $1::uuid
                       AND clinic_patient_id = $2::uuid
                       AND so_dien_thoai = $3
                    RETURNING loai
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    chuan,
                )
                if da_xoa is None:
                    raise ResourceNotFoundError(
                        "Số này không nằm trong danh sách số thêm của khách."
                    )
                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, metadata, source, event_published)
                    VALUES ($1::uuid, 'patient.phone_removed', 'patient',
                            $2::uuid, $3::jsonb, $4::jsonb, 'api', FALSE)
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    json.dumps({"loai": da_xoa, "duoi": chuan[-4:]}),
                    json.dumps(
                        {
                            "clinic_role": identity.role.value,
                            "clinic_staff_id": identity.staff_id,
                            "origin": "api",
                        }
                    ),
                )
        logger.info("patient_phone_removed", clinic_patient_id=clinic_patient_id)
        return {"da_xoa": True}

