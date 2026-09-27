"""XEM LẠI một lượt khám — một nguồn đọc chung, chỉ đọc, cắt theo vai.

Batch pilot 18/09/2026 (Pack B). Mỗi vai cần "xem lại cái đã làm": điều dưỡng
xem số vừa đo, bác sĩ/thư ký xem lượt đã khám, trưởng ca xem chỉ định đã điều
phối, lễ tân xem hành trình, thu ngân xem giao dịch. Thay vì mỗi màn một bảng
lịch sử riêng, tất cả đọc từ NGUỒN CANONICAL (visit, vital_measurement,
consultation, clinical_record, clinical_form_response, service_order,
review_round, prescription, payment, follow_up_case, event_log) qua MỘT hàm, và
hàm này quyết ai thấy mục nào — theo QUYỀN (lego), không theo vai (đợt 3,
27/09/2026):

  * hành chính, dòng thời gian sự kiện, lượt trước: mọi thành viên nội bộ;
  * sinh hiệu: quyền y khoa hoặc đo sinh hiệu;
  * lâm sàng (bệnh án, phiếu, ký, đơn thuốc, theo dõi, vòng đọc) và NỘI DUNG
    kết quả: quyền y khoa (`QUYEN_Y_KHOA`); thư ký chỉ khách của bác sĩ mình;
  * dịch vụ: mọi người thấy trạng thái + mốc thời gian (không thấy nội dung);
  * tài chính: thu tiền dịch vụ / thuốc, tiếp đón, điều phối;
  * cấp thuốc: nhà thuốc, thu tiền thuốc, quyền y khoa.

Không ghi gì. Mọi câu khoá theo clinic_id.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import VAI_LAM_VIEC, ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import quyen_hieu_luc
from clinicai.permissions.y_khoa import QUYEN_Y_KHOA, doc_duoc_in_phieu
from clinicai.services.audit_labels import action_label
from clinicai.services.luot_kham_rules import (
    doi_phong_duoc,
    hien_so_do_buoi,
    nhan_nguon_sinh_hieu,
)
from clinicai.services.sinh_hieu_buoi import sinh_hieu_cua_buoi
from clinicai.services.thu_ky_bac_si import kiem_khach

#: AI GỌI ĐƯỢC Xem lượt / bảng Hành trình: MỌI thành viên nội bộ đang hoạt động
#: — theo VAI TÀI KHOẢN, không theo lego (đợt 3, 27/09/2026). Hành trình là màn
#: "luôn bật" (`catalogue.LUON_BAT`); trước đây hỏi `co_vai(...)`, nên tắt lego
#: mang vai (vd lễ tân tắt Tiếp đón) là mất luôn màn này. Nội dung vẫn cắt theo
#: QUYỀN ở `muc_duoc_xem`.
GOI_DUOC: frozenset[ClinicRole] = VAI_LAM_VIEC

#: Mục nào mở theo quyền nào (đợt 3, 27/09/2026 — thay các tập VAI cũ). Lâm sàng
#: = đúng cửa y khoa chung (`permissions/y_khoa.QUYEN_Y_KHOA`): ai mở được phiếu
#: khám thì thấy phần lâm sàng của lượt; ai không có thì KHÔNG lộ chữ bác sĩ viết.
QUYEN_SINH_HIEU: tuple[str, ...] = (*QUYEN_Y_KHOA, "vitals.measure")
QUYEN_TAI_CHINH: tuple[str, ...] = (
    "payment.service.collect",
    "payment.medicine.collect",
    "reception.checkin.perform",
    "dispatch.manage",
)
QUYEN_THUOC: tuple[str, ...] = (
    *QUYEN_Y_KHOA,
    "pharmacy.dispense",
    "pharmacy.view",
    "payment.medicine.collect",
)


def goi_duoc(identity: StaffIdentity) -> bool:
    """Được mở Xem lượt / Hành trình: thành viên nội bộ (vai tài khoản)."""
    return identity.vai_goc in GOI_DUOC


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


def muc_duoc_xem(quyen: Collection[str]) -> dict[str, bool]:
    """Người có các quyền này thấy mục nào — thuần, test được không cần DB."""
    co = set(quyen)

    def mot(ds: tuple[str, ...]) -> bool:
        return not co.isdisjoint(ds)

    return {
        "hanh_chinh": True,
        "su_kien": True,
        "lich_su": True,
        "dich_vu": True,
        "sinh_hieu": mot(QUYEN_SINH_HIEU),
        "lam_sang": mot(QUYEN_Y_KHOA),
        "tai_chinh": mot(QUYEN_TAI_CHINH),
        "thuoc": mot(QUYEN_THUOC),
    }


async def dong_thoi_gian_luot(
    conn: asyncpg.Connection, cid: str, visit_id: str
) -> list[dict[str, Any]]:
    """Dòng thời gian của một lượt — đọc PROJECTION `luot_dong_thoi_gian` (dựng
    từ sổ sự kiện, dựng lại được bằng phát lại). Không có nội dung lâm sàng:
    chi tiết là whitelist của bên nhận (`dong_thoi_gian.CHI_TIET_HIEN`)."""
    rows = await conn.fetch(
        """
        SELECT d.occurred_at, d.event_type, d.nhan, d.chi_tiet,
               d.actor_type, s.full_name AS ai
          FROM luot_dong_thoi_gian d
          LEFT JOIN staff s ON s.id = d.actor_staff_id
         WHERE d.clinic_id = $1::uuid AND d.visit_id = $2::uuid
         ORDER BY d.occurred_at, d.thu_tu
         LIMIT 300
        """,
        cid,
        visit_id,
    )
    return [
        {
            "luc": _iso(r["occurred_at"]),
            "su_kien": r["event_type"],
            "nhan": r["nhan"],
            "chi_tiet": json.loads(r["chi_tiet"])
            if isinstance(r["chi_tiet"], str)
            else (r["chi_tiet"] or {}),
            "ai": r["ai"] or ("Hệ thống" if r["actor_type"] == "SYSTEM" else None),
        }
        for r in rows
    ]


class XemLuotService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        if not goi_duoc(identity):
            raise SafetyGateError("Tài khoản của bạn không xem lại lượt khám.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            muc = muc_duoc_xem(await quyen_hieu_luc(conn, identity))
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
                       a.slot_start, a.status AS lich_status,
                       a.so_booking, a.so_tiep_don
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
                    "so_booking": v["so_booking"],
                    "so_tiep_don": v["so_tiep_don"],
                },
                # Nút [In phiếu khám] ở Xem lượt — mở từ MỌI khâu (Tuyền 27/09).
                # Cùng luật cửa trang in (QUYEN_Y_KHOA ∪ QUYEN_IN_PHIEU — quầy
                # tiếp đón / thu tiền / nhà thuốc in được, Tuyền 27/09).
                "in_phieu": await doc_duoc_in_phieu(conn, identity),
                "hanh_chinh": await self._hanh_chinh(conn, cid, v),
                "dich_vu": await self._dich_vu(conn, cid, visit_id, muc["lam_sang"]),
                "su_kien": await self._su_kien(conn, cid, v),
                "dong_thoi_gian": await dong_thoi_gian_luot(conn, cid, visit_id),
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
              (SELECT f.vitals_status FROM encounter_flow f
                WHERE f.clinic_id = $1::uuid AND f.visit_id = $2::uuid)
                                                             AS vitals_status,
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
        # Sinh hiệu theo BUỔI (27/09/2026, đợt 3): cùng luật màn Đo sinh hiệu.
        do = await sinh_hieu_cua_buoi(conn, cid, v["visit_id"])
        da_do = do is not None and hien_so_do_buoi(
            vitals_status=r["vitals_status"],
            co_so_do_luot_nay=bool(do["co_so_do_luot_nay"]),
        )
        return {
            "check_in_luc": _iso(v["checked_in_at"]),
            "trang_thai_luot": v["status"],
            # INCOMPLETE = khách về giữa chừng (checkout_service.close) — lễ tân
            # và CSKH cần thấy rõ, không lẫn với "đã khám xong".
            "ve_giua_chung": v["status"] == "INCOMPLETE",
            "dich_vu_kham": v["dich_vu_kham"],
            "bac_si": v["bac_si"],
            "da_do_sinh_hieu": da_do,
            # "lượt trước" = số đo của lượt khác cùng buổi (nhãn do máy chủ trả).
            "sinh_hieu_nguon": (
                nhan_nguon_sinh_hieu(
                    nguon_visit_id=do["nguon_visit_id"], visit_id=v["visit_id"]
                )
                if da_do and do is not None
                else None
            ),
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
                     ORDER BY q.created_at DESC LIMIT 1)      AS goi_luc,
                   -- Ghi chú khi bấm Xong / Đã lấy mẫu (24/09/2026).
                   (SELECT a.ghi_chu FROM service_execution_attempt a
                     WHERE a.clinic_id = o.clinic_id AND a.service_order_id = o.id
                       AND a.ghi_chu IS NOT NULL
                     ORDER BY a.attempt_no DESC LIMIT 1)      AS ghi_chu_lam,
                   nv.ghi_chu_lay_mau AS ghi_chu_doi_tac_lay_mau,
                   nv.ghi_chu_tai_lieu AS ghi_chu_doi_tac_tai_lieu
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
              LEFT JOIN doi_tac_nhan_viec nv
                ON nv.clinic_id = o.clinic_id AND nv.service_order_id = o.id
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
                # Khách đã BỎ chỉ định ở quầy (Tuyền 24/09/2026: "xoá rác đo mật
                # độ xương chỉ định đã huỷ") — không còn là "chờ xếp phòng".
                "trang_thai": (
                    "khach_khong_lam"
                    if r.get("selection_status") == "NOT_SELECTED"
                    else r["exec_status"]
                ),
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
                # Ghi chú vận hành (không phải kết quả lâm sàng) — ai xem lượt
                # cũng thấy: điều dưỡng lấy mẫu, phòng, đối tác.
                "ghi_chu": [
                    g
                    for g in (
                        r.get("ghi_chu_lam"),
                        r.get("ghi_chu_doi_tac_lay_mau"),
                        r.get("ghi_chu_doi_tac_tai_lieu"),
                    )
                    if g
                ],
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
