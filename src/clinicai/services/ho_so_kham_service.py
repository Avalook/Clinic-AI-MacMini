"""Hồ sơ một lần khám — bản ĐỌC gộp, để xem trước và xuất PDF.

Tuyền 16/09/2026: *"cskh cũng phải có chỗ preview hồ sơ khám và tải về được bản
pdf"*. CSKH là người gửi kết quả cho khách, nên họ cần thấy trọn một lần khám ở
một chỗ: ai khám, sinh hiệu, phiếu khám bác sĩ ghi, chỉ định nào đã làm và kết
quả, tệp kết quả, xét nghiệm, đơn thuốc.

CHỈ ĐỌC, và đọc từ ĐÚNG MỘT ĐƯỜNG DỮ LIỆU của luồng khám (visit → consultation →
phieu_kham_luot | clinical_form_response → service_order → tep_ket_qua), không
tự suy ra gì. Mỗi kết quả mang theo trạng thái duyệt/cho phép gửi của nó: bản
xem không được biến một kết quả CHƯA được bác sĩ duyệt thành thứ trông như đã
chốt.

Phiếu khám v5 (29/09/2026) trả kèm trong ``phieu_kham`` với ``v5: true`` và
``muc`` đã dịch thành chữ (``phieu_kham/doc_chu.py``); sinh hiệu là lần đo của
BUỔI (``sinh_hieu_buoi``), kèm ``nguon = "lượt trước"`` khi đo ở lượt khác.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.phieu_kham.doc_chu import doc_phieu_v5_chu
from clinicai.services.luot_kham_rules import nhan_nguon_sinh_hieu
from clinicai.services.sinh_hieu_buoi import chi_so_do, sinh_hieu_cua_buoi


def _d(row: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class HoSoKhamService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(
        self, *, identity: StaffIdentity, appointment_id: str
    ) -> dict[str, Any]:
        clinic = identity.clinic_id
        async with self._pool.acquire() as conn:
            lich = await conn.fetchrow(
                """
                SELECT a.id::text AS appointment_id, a.slot_start, a.status,
                       a.notes,
                       s.name AS dich_vu, bs.full_name AS bac_si,
                       l.name AS co_so,
                       p.clinic_patient_id::text AS clinic_patient_id,
                       p.patient_code AS ma_bn, p.full_name AS ten,
                       p.date_of_birth AS ngay_sinh, p.birth_year AS nam_sinh,
                       p.gender AS gioi_tinh, p.phone_primary AS sdt,
                       coalesce(nullif(p.address_detail, ''), p.address) AS dia_chi,
                       p.van_de_di_kham
                  FROM public.appointment a
                  JOIN public.patient p
                    ON p.clinic_patient_id = a.clinic_patient_id
                   AND p.clinic_id = a.clinic_id
                  LEFT JOIN public.service_type s
                    ON s.id = a.service_type_id AND s.clinic_id = a.clinic_id
                  LEFT JOIN public.staff bs ON bs.id = a.doctor_id
                  LEFT JOIN public.clinic_location l
                    ON l.id = a.location_id AND l.clinic_id = a.clinic_id
                 WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
                """,
                appointment_id,
                clinic,
            )
            if lich is None:
                raise NotFoundError("Không tìm thấy lần khám này.")

            luot = await conn.fetchrow(
                """
                SELECT v.visit_id::text AS visit_id, v.status,
                       v.checked_in_at, v.exam_completed_at, v.closed_at,
                       bs.full_name AS bac_si_kham
                  FROM public.visit v
                  LEFT JOIN public.staff bs ON bs.id = v.attending_doctor_id
                 WHERE v.appointment_id = $1::uuid AND v.clinic_id = $2::uuid
                 ORDER BY v.created_at DESC
                 LIMIT 1
                """,
                appointment_id,
                clinic,
            )
            visit_id = luot["visit_id"] if luot else None

            sinh_hieu: dict[str, Any] | None = None
            phieu_v5: list[dict[str, Any]] = []
            phien: list[asyncpg.Record] = []
            phieu: list[asyncpg.Record] = []
            chi_dinh: list[asyncpg.Record] = []
            don_thuoc: list[asyncpg.Record] = []
            if visit_id:
                # Sinh hiệu theo BUỔI (29/09/2026): lượt check-in thêm cùng ngày
                # không đo lại vẫn có số của buổi (cùng luật phiếu khám).
                do = await sinh_hieu_cua_buoi(conn, clinic, visit_id)
                sinh_hieu = chi_so_do(do, kem=["nguoi_do"])
                if sinh_hieu is not None and do is not None:
                    sinh_hieu["nguon"] = nhan_nguon_sinh_hieu(
                        nguon_visit_id=do["nguon_visit_id"], visit_id=visit_id
                    )
                phien = await conn.fetch(
                    """
                    SELECT c.round_no AS vong, c.kind AS loai, c.status,
                           c.outcome AS ket_luan, c.started_at, c.completed_at,
                           bs.full_name AS bac_si
                      FROM public.consultation c
                      LEFT JOIN public.staff bs ON bs.id = c.doctor_staff_id
                     WHERE c.visit_id = $1::uuid AND c.clinic_id = $2::uuid
                     ORDER BY c.round_no, c.created_at
                    """,
                    visit_id,
                    clinic,
                )
                phieu = await conn.fetch(
                    """
                    SELECT f.service_code AS form_code, f.form_data, f.updated_at,
                           s.full_name AS nguoi_ghi
                      FROM public.clinical_form_response f
                      -- updated_by là chữ tự do "VAI · staff_id" (actor_label).
                      LEFT JOIN public.staff s
                        ON s.id::text = split_part(
                               coalesce(f.updated_by, f.created_by), ' · ', 2)
                     WHERE f.visit_id = $1::uuid AND f.clinic_id = $2::uuid
                     ORDER BY f.created_at
                    """,
                    visit_id,
                    clinic,
                )
                # Phiếu khám v5 (`phieu_kham_luot`) — chuẩn của lượt mới; bảng đời
                # cũ ở trên giữ cho lượt cũ (29/09/2026).
                phieu_v5 = await doc_phieu_v5_chu(
                    conn, clinic_id=clinic, visit_id=visit_id
                )
                chi_dinh = await conn.fetch(
                    """
                    SELECT o.id::text AS id, o.service_code,
                           o.service_name AS ten, o.exec_status AS trang_thai,
                           o.result_note AS ket_qua, o.bac_si_danh_gia,
                           o.not_performed_reason AS ly_do_khong_lam,
                           o.finished_at, o.ket_qua_luc, o.duyet_luc,
                           nl.full_name AS nguoi_lam, nd.full_name AS nguoi_duyet
                      FROM public.service_order o
                      LEFT JOIN public.staff nl ON nl.id = o.performed_by
                      LEFT JOIN public.staff nd ON nd.id = o.duyet_boi
                     WHERE o.visit_id = $1::uuid AND o.clinic_id = $2::uuid
                       AND o.exec_status NOT IN ('draft', 'cancelled')
                     ORDER BY o.created_at
                    """,
                    visit_id,
                    clinic,
                )
                don_thuoc = await conn.fetch(
                    """
                    SELECT drug_name_raw AS ten_thuoc,
                           dosage_instructions AS cach_dung,
                           coalesce(quantity_num::text, quantity) AS so_luong,
                           unit AS don_vi, quantity_note AS ghi_chu_so_luong,
                           caution AS luu_y
                      FROM public.prescription
                     WHERE visit_id = $1::uuid AND clinic_id = $2::uuid
                       AND removed_at IS NULL
                     ORDER BY created_at
                    """,
                    visit_id,
                    clinic,
                )

            tep = await conn.fetch(
                """
                SELECT t.id::text AS id, t.ten_hien_thi, t.loai_tep, t.mime,
                       t.so_byte, t.tai_len_luc,
                       t.service_order_id::text AS service_order_id,
                       t.cho_phep_gui_luc IS NOT NULL AS duoc_gui,
                       t.gui_luc
                  FROM public.v_tep_ket_qua_hieu_luc t
                 WHERE t.clinic_id = $1::uuid
                   AND t.clinic_patient_id = $2::uuid
                   AND (t.appointment_id = $3::uuid
                        OR t.service_order_id IN (
                            SELECT o.id FROM public.service_order o
                             WHERE o.visit_id = $4::uuid AND o.clinic_id = $1::uuid))
                 ORDER BY t.tai_len_luc
                """,
                clinic,
                lich["clinic_patient_id"],
                appointment_id,
                visit_id,
            )
            xet_nghiem = await conn.fetch(
                """
                SELECT test_name AS ten,
                       coalesce(result_value, result_numeric::text) AS ket_qua,
                       result_unit AS don_vi, reference_range_low AS thap,
                       reference_range_high AS cao, flag AS co,
                       requires_doctor_review AND reviewed_at IS NULL AS cho_duyet,
                       result_received_at
                  FROM public.lab_result
                 WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
                   AND (appointment_id = $3::uuid OR visit_id = $4::uuid)
                   AND (result_value IS NOT NULL OR result_numeric IS NOT NULL)
                 ORDER BY result_received_at NULLS LAST, created_at
                """,
                clinic,
                lich["clinic_patient_id"],
                appointment_id,
                visit_id,
            )

        return {
            "lich": _d(lich),
            "luot": _d(luot),
            "sinh_hieu": sinh_hieu,
            "phien_kham": [dict(r) for r in phien],
            "phieu_kham": [dict(r) for r in phieu] + phieu_v5,
            "chi_dinh": [dict(r) for r in chi_dinh],
            "tep": [dict(r) for r in tep],
            "xet_nghiem": [dict(r) for r in xet_nghiem],
            "don_thuoc": [dict(r) for r in don_thuoc],
        }
