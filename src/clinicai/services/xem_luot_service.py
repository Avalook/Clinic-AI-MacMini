"""XEM LẠI một lượt khám — một nguồn đọc chung, chỉ đọc, cắt theo vai.

Batch pilot 18/09/2026 (Pack B). Mỗi vai cần "xem lại cái đã làm": điều dưỡng
xem số vừa đo, bác sĩ/thư ký xem lượt đã khám, trưởng ca xem chỉ định đã điều
phối, lễ tân xem hành trình, thu ngân xem giao dịch. Thay vì mỗi màn một bảng
lịch sử riêng, tất cả đọc từ NGUỒN CANONICAL (visit, vital_measurement,
consultation, clinical_record, clinical_form_response, service_order,
review_round, prescription, payment, follow_up_case, event_log) qua MỘT hàm, và
hàm này quyết vai nào thấy mục nào:

  * hành chính, dòng thời gian sự kiện, lượt trước: mọi vai được gọi;
  * sinh hiệu: vai lâm sàng + điều dưỡng;
  * lâm sàng (bệnh án, phiếu, ký, đơn thuốc, theo dõi, vòng đọc) và NỘI DUNG
    kết quả: bác sĩ, thư ký y khoa (chỉ khách của bác sĩ mình), bác sĩ siêu âm;
  * dịch vụ: mọi vai thấy trạng thái + mốc thời gian (không thấy nội dung);
  * tài chính: thu ngân, lễ tân, trưởng ca, quản lý;
  * cấp thuốc: nhà thuốc, thu ngân thuốc, vai lâm sàng.

Không ghi gì. Mọi câu khoá theo clinic_id.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit_labels import action_label
from clinicai.services.luot_kham_rules import doi_phong_duoc
from clinicai.services.thu_ky_bac_si import kiem_khach

GOI_DUOC = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
        ClinicRole.RECEPTION,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
        ClinicRole.CASHIER,
        ClinicRole.CASHIER_DV,
        ClinicRole.CASHIER_THUOC,
        ClinicRole.PHARMACIST,
    }
)
LAM_SANG = frozenset({ClinicRole.DOCTOR, ClinicRole.TKYK, ClinicRole.ULTRASOUND_DOCTOR})
SINH_HIEU = LAM_SANG | {ClinicRole.NURSE_ULTRASOUND}
TAI_CHINH = frozenset(
    {
        ClinicRole.CASHIER,
        ClinicRole.CASHIER_DV,
        ClinicRole.CASHIER_THUOC,
        ClinicRole.RECEPTION,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
    }
)
THUOC = LAM_SANG | {ClinicRole.PHARMACIST, ClinicRole.CASHIER_THUOC}


def _iso(v: Any) -> str | None:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return None


def _so(v: Any) -> float | int | None:
    if v is None:
        return None
    return float(v) if isinstance(v, Decimal) else v


def _json(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


async def doc_su_kien_luot(
    conn: asyncpg.Connection, cid: str, visit_id: str, appointment_id: Any
) -> list[dict[str, Any]]:
    """Việc ĐÃ xảy ra trong một lượt, theo nhật ký sự kiện (`event_log`).

    Dùng chung cho màn xem lại lượt và màn check-out — chỉ ghi nhận việc thật,
    không phải các bước dự kiến tạo sẵn lúc check-in.
    """
    rows = await conn.fetch(
        """
        SELECT e.event_type, e.occurred_at, s.full_name AS ai,
               e.metadata ->> 'clinic_role' AS vai
          FROM event_log e
          LEFT JOIN staff s
            ON s.id::text = e.metadata ->> 'clinic_staff_id'
         WHERE e.clinic_id = $1::uuid
           AND (e.aggregate_id = $2::uuid
                OR ($3::uuid IS NOT NULL AND e.aggregate_id = $3::uuid))
         ORDER BY e.occurred_at, e.event_id
         LIMIT 300
        """,
        cid,
        visit_id,
        appointment_id,
    )
    return [
        {
            "viec": action_label(r["event_type"]),
            "ma": r["event_type"],
            "luc": _iso(r["occurred_at"]),
            "ai": r["ai"],
            "vai": r["vai"],
        }
        for r in rows
    ]


def _moc_dich_vu(r: Any) -> list[dict[str, Any]]:
    """Dòng thời gian một chỉ định: BS chỉ định → xếp phòng → phòng gọi → bắt
    đầu → xong / không làm được → có kết quả → bác sĩ duyệt. Mốc chưa có bỏ."""
    xong = "Không làm được" if r["exec_status"] == "not_performed" else "Xong"
    moc = [
        ("Ghi chỉ định", r["created_at"], r["nguoi_ghi"]),
        ("Bác sĩ duyệt chỉ định", r["authorized_at"], r["nguoi_duyet"]),
        ("Xếp phòng", r["assigned_at"], r["nguoi_xep"]),
        ("Phòng gọi khách", r["goi_luc"], None),
        ("Bắt đầu làm", r["started_at"], r["nguoi_lam"]),
        (xong, r["finished_at"], r["nguoi_lam"]),
        ("Có kết quả", r["ket_qua_luc"], None),
        ("Bác sĩ duyệt kết quả", r["duyet_luc"], r["nguoi_duyet_ket_qua"]),
    ]
    return [{"viec": v, "luc": _iso(luc), "ai": ai} for v, luc, ai in moc if luc]


def muc_duoc_xem(identity: StaffIdentity) -> dict[str, bool]:
    """Vai này thấy mục nào — thuần, test được không cần database."""
    return {
        "hanh_chinh": True,
        "su_kien": True,
        "lich_su": True,
        "dich_vu": True,
        "sinh_hieu": identity.co_vai(SINH_HIEU),
        "lam_sang": identity.co_vai(LAM_SANG),
        "tai_chinh": identity.co_vai(TAI_CHINH),
        "thuoc": identity.co_vai(THUOC),
    }


class XemLuotService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        if not identity.co_vai(GOI_DUOC):
            raise SafetyGateError("Vai của bạn không xem lại lượt khám.")
        cid = identity.clinic_id
        muc = muc_duoc_xem(identity)
        async with self._pool.acquire() as conn:
            v = await conn.fetchrow(
                """
                SELECT v.visit_id::text AS visit_id, v.status, v.checked_in_at,
                       v.closed_at, v.exam_completed_at, v.finalized_at,
                       v.clinic_patient_id::text AS patient_id,
                       v.appointment_id::text AS appointment_id,
                       fb.full_name AS nguoi_ky,
                       p.full_name, p.patient_code,
                       st.name AS dich_vu_kham, st.form_code,
                       d.full_name AS bac_si,
                       n.name AS dang_o_buoc, r.name AS dang_o_phong,
                       a.slot_start, a.status AS lich_status
                  FROM visit v
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN service_type st ON st.id = v.service_type_id
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                  LEFT JOIN staff fb ON fb.id = v.finalized_by
                  LEFT JOIN node_definition n
                    ON n.clinic_id = v.clinic_id AND n.code = v.current_node_code
                  LEFT JOIN clinic_room r
                    ON r.id = v.current_room_id AND r.clinic_id = v.clinic_id
                  LEFT JOIN appointment a
                    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
                 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                """,
                cid,
                visit_id,
            )
            if v is None:
                raise NotFoundError("Không tìm thấy lượt khám này.")
            if identity.co_vai({ClinicRole.TKYK}):
                await kiem_khach(conn, identity, v["patient_id"])
            out: dict[str, Any] = {
                "visit_id": v["visit_id"],
                "muc": muc,
                "khach": {
                    "id": v["patient_id"],
                    "ten": v["full_name"],
                    "ma": v["patient_code"],
                },
                "hanh_chinh": await self._hanh_chinh(conn, cid, v),
                "dich_vu": await self._dich_vu(conn, cid, visit_id, muc["lam_sang"]),
                "su_kien": await self._su_kien(conn, cid, v),
                "lich_su": await self._lich_su(conn, cid, v),
            }
            if muc["sinh_hieu"]:
                out["sinh_hieu"] = await self._sinh_hieu(conn, cid, v)
            if muc["lam_sang"]:
                out["lam_sang"] = await self._lam_sang(conn, cid, v)
            if muc["tai_chinh"]:
                out["tai_chinh"] = await self._tai_chinh(conn, cid, visit_id)
            if muc["thuoc"]:
                out["thuoc"] = await self._thuoc(conn, cid, visit_id)
        return out

    # ------------------------------------------------------------------

    @staticmethod
    async def _hanh_chinh(
        conn: asyncpg.Connection, cid: str, v: asyncpg.Record
    ) -> dict[str, Any]:
        r = await conn.fetchrow(
            """
            SELECT
              EXISTS (SELECT 1 FROM vital_measurement m WHERE m.clinic_id = $1::uuid
                       AND m.visit_id = $2::uuid)                     AS da_do,
              EXISTS (SELECT 1 FROM payment pm WHERE pm.clinic_id = $1::uuid
                       AND pm.visit_id = $2::uuid AND pm.kind = 'dich_vu'
                       AND pm.status = 'PAID' AND pm.voided_at IS NULL) AS da_thu_dv,
              EXISTS (SELECT 1 FROM payment pm WHERE pm.clinic_id = $1::uuid
                       AND pm.visit_id = $2::uuid AND pm.kind = 'thuoc'
                       AND pm.status = 'PAID' AND pm.voided_at IS NULL) AS da_thu_thuoc,
              (SELECT min(a.slot_start) FROM appointment a
                WHERE a.clinic_id = $1::uuid AND a.clinic_patient_id = $3::uuid
                  AND a.slot_start > now()
                  -- Lịch đã check-in / đã khám xong không phải "lịch tiếp
                  -- theo" (smoke 18/09: lịch 18:00 hôm nay vừa check-in hiện
                  -- thành lịch tiếp theo của chính lượt ấy).
                  AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED',
                                       'CHECKED_IN', 'COMPLETED'))
                                                                    AS lich_tiep
            """,
            cid,
            v["visit_id"],
            v["patient_id"],
        )
        assert r is not None
        return {
            "check_in_luc": _iso(v["checked_in_at"]),
            "trang_thai_luot": v["status"],
            # INCOMPLETE = khách về giữa chừng (checkout_service.close) — lễ tân
            # và CSKH cần thấy rõ, không lẫn với "đã khám xong".
            "ve_giua_chung": v["status"] == "INCOMPLETE",
            "dich_vu_kham": v["dich_vu_kham"],
            "bac_si": v["bac_si"],
            "da_do_sinh_hieu": r["da_do"],
            "kham_xong_luc": _iso(v["exam_completed_at"]),
            "dang_o": v["dang_o_phong"] or v["dang_o_buoc"],
            "da_thu_dich_vu": r["da_thu_dv"],
            "da_thu_thuoc": r["da_thu_thuoc"],
            "dong_luot_luc": _iso(v["closed_at"]),
            "lich_tiep_theo": _iso(r["lich_tiep"]),
        }

    @staticmethod
    async def _dich_vu(
        conn: asyncpg.Connection, cid: str, vid: str, noi_dung: bool
    ) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT o.id::text AS id, o.service_name, o.node_code, o.exec_status,
                   o.created_at, o.authorized_at, o.assigned_at, o.started_at,
                   o.finished_at, o.ket_qua_luc, o.duyet_luc,
                   o.not_performed_reason, o.result_note, o.cancel_reason,
                   rb.full_name AS nguoi_ghi, ab.full_name AS nguoi_duyet,
                   sb.full_name AS nguoi_xep, pb.full_name AS nguoi_lam,
                   db.full_name AS nguoi_duyet_ket_qua, rm.name AS phong,
                   o.selection_status, o.execution_status, o.routing_revision,
                   o.room_id::text AS room_id,
                   coalesce(nd.lam_ben_ngoai, false) AS doi_tac,
                   (SELECT count(*) FROM tep_ket_qua t
                     WHERE t.clinic_id = o.clinic_id AND t.service_order_id = o.id)
                                                              AS so_tep,
                   (SELECT q.status FROM queue_entry q
                     WHERE q.clinic_id = o.clinic_id AND q.ref_id = o.id
                       AND q.reason = 'SERVICE'
                     ORDER BY q.created_at DESC LIMIT 1)      AS hang_cho,
                   (SELECT q.called_at FROM queue_entry q
                     WHERE q.clinic_id = o.clinic_id AND q.ref_id = o.id
                       AND q.reason = 'SERVICE'
                     ORDER BY q.created_at DESC LIMIT 1)      AS goi_luc
              FROM service_order o
              LEFT JOIN staff rb ON rb.id = o.recorded_by
              LEFT JOIN staff ab ON ab.id = o.authorized_by
              LEFT JOIN staff sb ON sb.id = o.assigned_by
              LEFT JOIN staff pb ON pb.id = o.performed_by
              LEFT JOIN staff db ON db.id = o.duyet_boi
              LEFT JOIN clinic_room rm
                ON rm.id = o.room_id AND rm.clinic_id = o.clinic_id
              LEFT JOIN node_definition nd
                ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
             WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
             ORDER BY o.created_at, o.id
            """,
            cid,
            vid,
        )
        return [
            {
                "id": r["id"],
                "dich_vu": r["service_name"],
                "node": r["node_code"],
                "trang_thai": r["exec_status"],
                "phong": r["phong"],
                # Đổi phòng ngay trong màn xem lượt (23/09/2026) — lệnh vẫn tự
                # kiểm quyền + cổng tiền; đây chỉ để biết có bày nút không.
                "phong_id": r.get("room_id"),
                "routing_revision": r.get("routing_revision"),
                "doi_phong_duoc": doi_phong_duoc(
                    selection_status=r.get("selection_status"),
                    execution_status=r.get("execution_status"),
                    exec_status=r["exec_status"],
                    doi_tac=bool(r.get("doi_tac")),
                ),
                "so_tep": int(r["so_tep"] or 0),
                "ly_do_khong_lam": r["not_performed_reason"],
                "ly_do_huy": r["cancel_reason"],
                "ket_qua_ghi": r["result_note"] if noi_dung else None,
                # Dòng thời gian: BS chỉ định → trưởng ca xếp phòng → phòng gọi
                # → bắt đầu → xong → có kết quả → bác sĩ duyệt.
                "moc": _moc_dich_vu(r),
            }
            for r in rows
        ]

    @staticmethod
    async def _su_kien(
        conn: asyncpg.Connection, cid: str, v: asyncpg.Record
    ) -> list[dict[str, Any]]:
        return await doc_su_kien_luot(
            conn, cid, str(v["visit_id"]), v["appointment_id"]
        )

    @staticmethod
    async def _lich_su(
        conn: asyncpg.Connection, cid: str, v: asyncpg.Record
    ) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT x.visit_id::text AS visit_id, x.checked_in_at, x.created_at,
                   x.status, st.name AS dich_vu, d.full_name AS bac_si
              FROM visit x
              LEFT JOIN service_type st ON st.id = x.service_type_id
              LEFT JOIN staff d ON d.id = x.attending_doctor_id
             WHERE x.clinic_id = $1::uuid AND x.clinic_patient_id = $2::uuid
               AND x.visit_id <> $3::uuid
             ORDER BY coalesce(x.checked_in_at, x.created_at) DESC
             LIMIT 20
            """,
            cid,
            v["patient_id"],
            v["visit_id"],
        )
        return [
            {
                "visit_id": r["visit_id"],
                "luc": _iso(r["checked_in_at"] or r["created_at"]),
                "trang_thai": r["status"],
                "dich_vu": r["dich_vu"],
                "bac_si": r["bac_si"],
            }
            for r in rows
        ]

    @staticmethod
    async def _sinh_hieu(
        conn: asyncpg.Connection, cid: str, v: asyncpg.Record
    ) -> dict[str, Any]:
        rows = await conn.fetch(
            """
            SELECT m.visit_id::text AS visit_id, m.systolic, m.diastolic, m.pulse,
                   m.temperature, m.weight_kg, m.height_cm, m.respiratory_rate,
                   m.spo2, m.bmi, m.pain_score, m.created_at,
                   s.full_name AS nguoi_do
              FROM vital_measurement m
              JOIN visit x ON x.visit_id = m.visit_id AND x.clinic_id = m.clinic_id
              LEFT JOIN staff s ON s.id = m.recorded_by
             WHERE m.clinic_id = $1::uuid AND x.clinic_patient_id = $2::uuid
             ORDER BY m.created_at DESC
             LIMIT 30
            """,
            cid,
            v["patient_id"],
        )

        def dong(r: asyncpg.Record) -> dict[str, Any]:
            return {
                "luc": _iso(r["created_at"]),
                "nguoi_do": r["nguoi_do"],
                "tam_thu": r["systolic"],
                "tam_truong": r["diastolic"],
                "mach": r["pulse"],
                "nhiet_do": _so(r["temperature"]),
                "can_nang": _so(r["weight_kg"]),
                "chieu_cao": _so(r["height_cm"]),
                "nhip_tho": r["respiratory_rate"],
                "spo2": r["spo2"],
                "bmi": _so(r["bmi"]),
                "muc_do_dau": r["pain_score"],
            }

        return {
            "luot_nay": [dong(r) for r in rows if r["visit_id"] == v["visit_id"]],
            "luot_truoc": [dong(r) for r in rows if r["visit_id"] != v["visit_id"]][
                :10
            ],
        }

    @staticmethod
    async def _lam_sang(
        conn: asyncpg.Connection, cid: str, v: asyncpg.Record
    ) -> dict[str, Any]:
        vid = v["visit_id"]
        phien = await conn.fetch(
            """
            SELECT c.kind, c.round_no, c.status, c.outcome, c.started_at,
                   c.completed_at, d.full_name AS bac_si, sb.full_name AS nguoi_bam
              FROM consultation c
              LEFT JOIN staff d ON d.id = c.doctor_staff_id
              LEFT JOIN staff sb ON sb.id = c.started_by
             WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
             ORDER BY c.round_no
            """,
            cid,
            vid,
        )
        ba = await conn.fetchrow(
            """
            SELECT soap_assessment, soap_plan, chief_complaint_at_visit, revision,
                   prescription_draft IS NOT NULL AS co_don_nhap, updated_at
              FROM clinical_record
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            """,
            cid,
            vid,
        )
        phieu = await conn.fetchrow(
            """
            SELECT service_code, created_by, updated_by, created_at, updated_at
              FROM clinical_form_response
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
             ORDER BY updated_at DESC LIMIT 1
            """,
            cid,
            vid,
        )
        ten_nguoi = {
            str(r["id"]): r["full_name"]
            for r in await conn.fetch(
                "SELECT id, full_name FROM staff WHERE id::text = ANY($1::text[])",
                [
                    x
                    for x in (
                        phieu["created_by"] if phieu else None,
                        phieu["updated_by"] if phieu else None,
                    )
                    if x
                ],
            )
        }
        vong = await conn.fetch(
            """
            SELECT r.round_no, r.status, q.need, q.status AS yc_status,
                   q.waived_reason, o.service_name, wb.full_name AS nguoi_quyet
              FROM review_round r
              JOIN round_requirement q
                ON q.round_id = r.id AND q.clinic_id = r.clinic_id
              JOIN service_order o
                ON o.id = q.service_order_id AND o.clinic_id = q.clinic_id
              LEFT JOIN staff wb ON wb.id = q.waived_by
             WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
             ORDER BY r.round_no, q.created_at
            """,
            cid,
            vid,
        )
        theo_doi = await conn.fetch(
            """
            SELECT f.status, f.reason, f.due_at, f.closed_at,
                   s.full_name AS chu, o.service_name
              FROM follow_up_case f
              LEFT JOIN staff s ON s.id = f.owner_staff_id
              LEFT JOIN service_order o
                ON o.id = f.service_order_id AND o.clinic_id = f.clinic_id
             WHERE f.clinic_id = $1::uuid AND f.visit_id = $2::uuid
             ORDER BY f.created_at
            """,
            cid,
            vid,
        )
        tk = _json(ba["soap_plan"]) if ba else None
        return {
            "ky": {
                "da_ky": v["status"] in ("FINALIZED", "AMENDED"),
                "trang_thai": v["status"],
                "luc": _iso(v["finalized_at"]),
                "nguoi_ky": v["nguoi_ky"],
            },
            "phien": [
                {
                    "loai": r["kind"],
                    "vong": r["round_no"],
                    "trang_thai": r["status"],
                    "ket_qua": r["outcome"],
                    "bat_dau": _iso(r["started_at"]),
                    "xong": _iso(r["completed_at"]),
                    "bac_si": r["bac_si"],
                    "nguoi_bam_bat_dau": r["nguoi_bam"],
                }
                for r in phien
            ],
            "benh_an": {
                "ly_do": ba["chief_complaint_at_visit"] if ba else None,
                "chan_doan": _json(ba["soap_assessment"]) if ba else None,
                "ke_hoach": tk,
                "revision": ba["revision"] if ba else None,
                "co_don_nhap_cho_duyet": bool(ba["co_don_nhap"]) if ba else False,
                "cap_nhat_luc": _iso(ba["updated_at"]) if ba else None,
            },
            "phieu": (
                {
                    "ma": phieu["service_code"],
                    "nguoi_tao": ten_nguoi.get(str(phieu["created_by"] or "")),
                    "nguoi_sua_cuoi": ten_nguoi.get(str(phieu["updated_by"] or "")),
                    "tao_luc": _iso(phieu["created_at"]),
                    "sua_luc": _iso(phieu["updated_at"]),
                    "form_code": v["form_code"],
                }
                if phieu
                else None
            ),
            "vong_doc": [
                {
                    "vong": r["round_no"],
                    "trang_thai": r["status"],
                    "dich_vu": r["service_name"],
                    "can": r["need"],
                    "yeu_cau": r["yc_status"],
                    "nguoi_quyet": r["nguoi_quyet"],
                    "ly_do": r["waived_reason"],
                }
                for r in vong
            ],
            "theo_doi": [
                {
                    "trang_thai": r["status"],
                    "ly_do": r["reason"],
                    "han": _iso(r["due_at"]),
                    "dong_luc": _iso(r["closed_at"]),
                    "chu": r["chu"],
                    "dich_vu": r["service_name"],
                }
                for r in theo_doi
            ],
        }

    @staticmethod
    async def _tai_chinh(
        conn: asyncpg.Connection, cid: str, vid: str
    ) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT pm.id::text AS id, pm.kind, pm.status, pm.amount, pm.paid_at,
                   pm.voided_at, pm.void_reason, s.full_name AS nguoi_thu,
                   vb.full_name AS nguoi_huy, pm.paid_by_text
              FROM payment pm
              LEFT JOIN staff s ON s.id = pm.paid_by_staff_id
              LEFT JOIN staff vb ON vb.id = pm.voided_by_staff_id
             WHERE pm.clinic_id = $1::uuid AND pm.visit_id = $2::uuid
             ORDER BY pm.paid_at NULLS LAST, pm.created_at
            """,
            cid,
            vid,
        )
        return [
            {
                "id": r["id"],
                "loai": r["kind"],
                "trang_thai": r["status"],
                "so_tien": _so(r["amount"]),
                "luc": _iso(r["paid_at"]),
                "nguoi_thu": r["nguoi_thu"] or r["paid_by_text"],
                "huy_luc": _iso(r["voided_at"]),
                "nguoi_huy": r["nguoi_huy"],
                "ly_do_huy": r["void_reason"],
            }
            for r in rows
        ]

    @staticmethod
    async def _thuoc(
        conn: asyncpg.Connection, cid: str, vid: str
    ) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            """
            -- rx:gom-ca-lich-su: Xem lượt là LỊCH SỬ — hiện cả dòng đã đính
            -- chính (đánh dấu), để thấy "thuốc A được thay bằng B vì ...".
            SELECT pr.id::text, pr.drug_name_raw, pr.quantity, pr.quantity_num,
                   pr.unit, pr.dosage_instructions, pr.dispensed_qty,
                   pr.dispensed_at, pr.dispense_status, pr.refusal_reason,
                   pr.closed_at, s.full_name AS nguoi_cap,
                   pr.removed_at, pr.removal_reason,
                   pr.superseded_by_id::text AS thay_boi,
                   sg.full_name AS nguoi_dinh_chinh
              FROM prescription pr
              LEFT JOIN staff s ON s.id = pr.dispensed_by_staff_id
              LEFT JOIN staff sg ON sg.id = pr.removed_by
             WHERE pr.clinic_id = $1::uuid AND pr.visit_id = $2::uuid
             ORDER BY pr.created_at, pr.id
            """,
            cid,
            vid,
        )
        return [
            {
                "thuoc": r["drug_name_raw"],
                "so_luong": _so(r["quantity_num"]) or r["quantity"],
                "don_vi": r["unit"],
                "cach_dung": r["dosage_instructions"],
                "da_cap": _so(r["dispensed_qty"]),
                "cap_luc": _iso(r["dispensed_at"]),
                "trang_thai_cap": r["dispense_status"],
                "ly_do_tu_choi": r["refusal_reason"],
                "nguoi_cap": r["nguoi_cap"],
                # CP6: dòng đã đính chính vẫn hiện — đánh dấu, kèm dòng thay.
                "id": r["id"],
                "da_dinh_chinh": r["removed_at"] is not None,
                "dinh_chinh_luc": _iso(r["removed_at"]),
                "ly_do_dinh_chinh": r["removal_reason"],
                "nguoi_dinh_chinh": r["nguoi_dinh_chinh"],
                "thay_boi": r["thay_boi"],
            }
            for r in rows
        ]
