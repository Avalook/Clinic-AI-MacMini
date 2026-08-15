"""MPI (Master Patient Index) deduplication engine.

Scores candidate patients against each other using weighted matching
and auto-queues high-confidence duplicates for human review.
"""

from __future__ import annotations

import difflib
from typing import Any
from uuid import UUID

import asyncpg
import structlog

from clinicai.core.phone import normalize_vn_phone, phone_variants
from clinicai.schemas.patient import PatientCreateDTO, PatientDTO

logger = structlog.get_logger()

# TODO: move to config / env var
MPI_THRESHOLD = 70.0

# Scoring weights
_PHONE_WEIGHT = 50.0
_NATIONAL_ID_WEIGHT = 40.0
_NAME_WEIGHT = 10.0


class MPIService:
    """Master Patient Index deduplication scoring and queue management."""

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def score(candidate: PatientDTO, existing: PatientDTO) -> float:
        """Return a similarity score (0.0–100.0) between two patients.

        Weighted components:
          - phone_primary exact match:          50 pts
          - national_id_number exact (non-null): 40 pts
          - full_name fuzzy (SequenceMatcher):   0–10 pts
        """
        total = 0.0

        # Phone match
        candidate_phone = (
            normalize_vn_phone(candidate.phone_primary)
            if candidate.phone_primary
            else None
        )
        existing_phone = (
            normalize_vn_phone(existing.phone_primary)
            if existing.phone_primary
            else None
        )
        if candidate_phone is not None and candidate_phone == existing_phone:
            total += _PHONE_WEIGHT

        # National ID match (both must be non-null)
        if (
            candidate.national_id_number
            and existing.national_id_number
            and candidate.national_id_number == existing.national_id_number
        ):
            total += _NATIONAL_ID_WEIGHT

        # Name fuzzy match
        name_ratio = difflib.SequenceMatcher(
            None,
            candidate.full_name.lower(),
            existing.full_name.lower(),
        ).ratio()
        total += name_ratio * _NAME_WEIGHT

        return min(total, 100.0)

    # ------------------------------------------------------------------
    # Candidate lookup
    # ------------------------------------------------------------------

    @staticmethod
    async def find_candidates(
        pool: asyncpg.Pool,
        data: PatientCreateDTO,
        clinic_id: str,
    ) -> list[PatientDTO]:
        """Find existing patients that may match the incoming data.

        Searches by phone_primary OR national_id_number (if provided).
        """
        conditions: list[str] = []
        params: list[object] = []
        idx = 1

        if data.phone_primary:
            # SỐ THÊM cũng là số của khách (patient_sdt_them, 15/08/2026):
            # khách đăng ký lần trước bằng số phụ, lần này đọc lại đúng số ấy
            # — không có vế thứ ba này thì dedup im lặng và hồ sơ tách đôi,
            # đúng cái mà bảng số-thêm sinh ra để chống.
            conditions.append(
                f"(phone_primary = ANY(${idx}::text[]) "
                f"OR phone_secondary = ANY(${idx}::text[]) "
                f"OR EXISTS (SELECT 1 FROM public.patient_sdt_them t "
                f"WHERE t.clinic_patient_id = patient.clinic_patient_id "
                f"AND t.so_dien_thoai = ANY(${idx}::text[])))"
            )
            params.append(phone_variants(data.phone_primary))
            idx += 1

        if data.national_id_number:
            conditions.append(f"national_id_number = ${idx}")
            params.append(data.national_id_number)
            idx += 1

        # HỌ TÊN + NĂM SINH — vế thứ ba, và là vế duy nhất bắt được người khai
        # số điện thoại khác.
        #
        # Notion §2 Lễ tân, tiêu chí kỹ thuật 2: *"kiểm tra khả năng trùng theo
        # SĐT đã chuẩn hoá, KẾT HỢP HỌ TÊN VÀ NĂM SINH"*. Trước đây chỉ có SĐT
        # và CCCD — nên một người khai số mới, hoặc chưa có CCCD, sẽ tạo hồ sơ
        # thứ hai mà không có gì cảnh báo.
        #
        # DÙNG `full_name_unaccent`, KHÔNG gọi unaccent() lúc truy vấn: cột đó
        # là GENERATED (lower + bỏ dấu + đ→d) nên luôn khớp với chính nó, và nó
        # có chỉ mục `idx_patient_full_name_unaccent`. Tự tính lại ở vế trái sẽ
        # bỏ qua chỉ mục và mở đường cho hai công thức chuẩn hoá lệch nhau.
        # Vế phải dùng ĐÚNG biểu thức của cột để hai bên không bao giờ khác cách
        # hiểu "Nguyễn" và "Nguyen".
        #
        # NĂM SINH thì KHÔNG tin cột `birth_year`: đo trên prod, nó chỉ được
        # điền ở 25/49 hồ sơ (ứng dụng ghi, không phải cột sinh tự động). Lấy nó
        # khi có, còn lại tính từ date_of_birth — nếu chỉ dựa vào cột đó thì
        # đúng một nửa số hồ sơ sẽ âm thầm không bao giờ báo trùng.
        #
        # So NĂM chứ không so NGÀY: ngày sinh hay bị nhập lệch, còn trùng cả tên
        # lẫn năm sinh thì đã đáng để con người nhìn lại.
        if data.full_name and data.date_of_birth:
            conditions.append(
                f"(full_name_unaccent = lower(replace(replace("
                f"f_unaccent(${idx}), 'đ', 'd'), 'Đ', 'D'))"
                f" AND coalesce(birth_year, date_part('year', date_of_birth))"
                f" = ${idx + 1})"
            )
            params.append(data.full_name)
            params.append(float(data.date_of_birth.year))
            idx += 2

        if not conditions:
            return []

        where = " OR ".join(conditions)
        # Scoped to one clinic: a "duplicate" in another clinic is not a
        # duplicate, it is a different chart for possibly the same person, and
        # merging across tenants would be wrong as well as a leak (W8).
        params.append(clinic_id)
        query = (  # noqa: S608
            f"SELECT * FROM patient WHERE ({where}) AND clinic_id = ${idx}::uuid;"
        )

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [PatientDTO.model_validate(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Auto-queue
    # ------------------------------------------------------------------

    async def auto_queue_if_needed(
        self,
        pool: asyncpg.Pool,
        new_patient_id: UUID,
        candidates: list[PatientDTO],
        clinic_id: str,
    ) -> list[UUID]:
        """Insert into mpi_merge_queue for each candidate scoring >= threshold.

        Returns list of newly created queue entry IDs.
        """
        queue_ids: list[UUID] = []

        query = """
            INSERT INTO mpi_merge_queue (
                clinic_id, patient_id_a, patient_id_b, score, status
            )
            VALUES ($4::uuid,
                    $1, $2, $3, 'PENDING')
            RETURNING id;
        """

        async with pool.acquire() as conn:
            for candidate in candidates:
                if candidate.clinic_patient_id == new_patient_id:
                    continue

                # Build a temporary DTO for the new patient to score
                # We need the new patient's data — fetch it
                new_row = await conn.fetchrow(
                    "SELECT * FROM patient WHERE clinic_patient_id = $1 "
                    "AND clinic_id = $2::uuid;",
                    new_patient_id,
                    clinic_id,
                )
                if new_row is None:
                    continue

                new_dto = PatientDTO.model_validate(dict(new_row))
                match_score = self.score(new_dto, candidate)

                if match_score < MPI_THRESHOLD:
                    logger.debug(
                        "mpi_below_threshold",
                        new_patient_id=str(new_patient_id),
                        candidate_id=str(candidate.clinic_patient_id),
                        score=match_score,
                    )
                    continue

                row = await conn.fetchrow(
                    query,
                    new_patient_id,
                    candidate.clinic_patient_id,
                    round(match_score, 2),
                    clinic_id,
                )
                queue_id = row["id"]
                queue_ids.append(queue_id)

                logger.info(
                    "mpi_queued",
                    queue_id=str(queue_id),
                    patient_id_a=str(new_patient_id),
                    patient_id_b=str(candidate.clinic_patient_id),
                    score=match_score,
                )

        return queue_ids

    # ------------------------------------------------------------------
    # Queue retrieval
    # ------------------------------------------------------------------

    @staticmethod
    async def get_pending_queue(
        pool: asyncpg.Pool,
        clinic_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch pending MPI merge queue entries sorted by score DESC."""
        query = """
            SELECT * FROM mpi_merge_queue
            WHERE status = 'PENDING'
              AND clinic_id = $2::uuid
            ORDER BY score DESC
            LIMIT $1;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, limit, clinic_id)
        return [dict(r) for r in rows]
