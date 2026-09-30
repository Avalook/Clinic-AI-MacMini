"""Các màn ĐỌC của lượt khám — bảng lượt khám, phòng hôm nay, hàng chờ theo
phòng, chỉ định hôm nay (trưởng ca), kết quả chờ duyệt.

Bóc khỏi ``luot_kham_service`` ngày 24/09/2026 (bước 5 đợt bóc lõi): chỉ
ĐỌC, không ghi gì — sửa một màn đọc không phải mở file lệnh của khối Khám.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import (
    StaffIdentity,
)
from clinicai.core.clock import doc_ngay_xem, hom_nay_vn, now_vn
from clinicai.permissions.can import can, doi_quyen
from clinicai.permissions.doc_bang import (
    QUYEN_BANG_LUOT,
    doi_mot_quyen,
    quyen_doc_hang_cho,
)
from clinicai.permissions.lich import bac_si_cung_phong_hom_nay, khach_cua_toi
from clinicai.permissions.y_khoa import doc_duoc_y_khoa
from clinicai.services import luot_kham_rules as rules
from clinicai.services.bac_si_ky import sql_join_bac_si_ky_luot
from clinicai.services.bac_si_phu_trach import (
    VAI_BAC_SI,
    bac_si_trong_ca_hoac_ca_ngay,
)
from clinicai.services.doi_tac_service import trang_thai_doi_tac
from clinicai.services.lenh_kham_core import ma_uuid as _uuid
from clinicai.services.luot_kham_chung import (
    _cung_ngay_vn,
    _iso,
    _num,
    _theo_luat_xep_hang,
)
from clinicai.services.sinh_hieu_buoi import sinh_hieu_cua_buoi_nhieu
from clinicai.services.thu_ky_bac_si import bac_si_cua_thu_ky

logger = structlog.get_logger()

#: Trần số chỉ định trả về cho bảng trưởng ca trong một lần đọc. Có trần là đúng
#: (một ngày hỏng dữ liệu không được kéo sập màn), nhưng cắt mà không báo thì
#: sai — xem `bi_cat` trong `chi_dinh_hom_nay`.
_TRAN_CHI_DINH_HOM_NAY = 500


def la_phong_dich_vu(nodes: list[str]) -> bool:
    """Phòng có làm dịch vụ (node `DICHVU-*`) — hiện ở danh sách Phòng dịch vụ.

    29/09/2026: trước đây màn lọc "không có node KHAM-" — từ khi mọi phòng có
    bác sĩ được thêm node KHAM-* (bác sĩ đa năng, 28/09) thì Siêu âm, Thủ thuật,
    Sàn chậu… biến khỏi danh sách. Kho thuốc (`DICHVU-THUOC`) là nhà thuốc,
    không phải phòng làm dịch vụ.
    """
    return any(n.startswith("DICHVU-") and n != "DICHVU-THUOC" for n in nodes if n)


class BangLuotKham:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def bang(
        self, *, identity: StaffIdentity, ngay: Any = None
    ) -> dict[str, Any]:
        """Bảng làm việc theo NGÀY check-in (mặc định hôm nay).

        `ngay` (29/09/2026, YYYY-MM-DD; rác/None = hôm nay — `doc_ngay_xem`):
        quay lại một NGÀY CŨ để xem và sửa (Đo sinh hiệu, Bàn khám). Ngày cũ
        lấy MỌI lượt check-in ngày ấy, kể cả đã xong; không có "lịch chờ
        check-in", không tính phút chờ, không bày ô "bỏ qua tư vấn" (việc đổi
        đường đi là của hôm nay). Chỉ ĐỌC: mỗi lệnh sửa vẫn tự hỏi luật của nó.
        """
        cid = identity.clinic_id
        hom_nay = hom_nay_vn()
        ngay_xem = doc_ngay_xem(ngay) or hom_nay
        la_hom_nay = ngay_xem == hom_nay
        async with self._pool.acquire() as conn:
            # Theo LEGO, không theo vai (đợt 3, 27/09/2026) — `permissions/doc_bang`.
            await doi_mot_quyen(
                conn, identity, QUYEN_BANG_LUOT, cau="Bạn không có quyền xem bảng này."
            )
            # Theo QUYỀN (khối khám / kết quả), không theo vai — 24/09/2026.
            doc_noi_dung = await doc_duoc_y_khoa(conn, identity)
            visits = await conn.fetch(
                """
                SELECT v.visit_id::text AS visit_id, v.checked_in_at,
                       v.attending_doctor_id::text AS doctor_id,
                       p.full_name, p.patient_code, d.full_name AS doctor_name,
                       f.vitals_status, f.route_decision, f.finished_at,
                       f.goi_do_luc, g.full_name AS goi_do_boi,
                       f.vitals_started_at, bd.full_name AS vitals_started_by,
                       ap.so_tiep_don, ap.so_booking, lk.name AS loai_kham
                  FROM visit v
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                  LEFT JOIN encounter_flow f
                    ON f.visit_id = v.visit_id AND f.clinic_id = v.clinic_id
                  LEFT JOIN staff g ON g.id = f.goi_do_boi
                  LEFT JOIN staff bd ON bd.id = f.vitals_started_by
                  LEFT JOIN appointment ap
                    ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
                  LEFT JOIN service_type lk
                    ON lk.clinic_id = v.clinic_id
                   AND lk.id = coalesce(v.service_type_id, ap.service_type_id)
                 WHERE v.clinic_id = $1::uuid
                   -- INCOMPLETE cố ý không hiện hôm nay: khách đã về. Ngày cũ
                   -- (xem lại để sửa, 29/09/2026) thì hiện mọi lượt.
                   AND (v.status IN ('OPEN', 'IN_PROGRESS') OR NOT $3::boolean)
                   AND v.checked_in_at IS NOT NULL
                   AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       = $4::date
                   -- Thư ký chỉ thấy lượt của bác sĩ mình (20260915000020).
                   AND coalesce(v.attending_doctor_id::text, '~')
                       = ANY(coalesce(
                             $2::text[],
                             ARRAY[coalesce(v.attending_doctor_id::text, '~')]))
                 ORDER BY v.checked_in_at, v.visit_id
                """,
                cid,
                await bac_si_cua_thu_ky(conn, identity),
                la_hom_nay,
                ngay_xem,
            )
            ids = [r["visit_id"] for r in visits]
            # Sinh hiệu theo BUỔI (27/09/2026, đợt 3): lượt check-in thêm trong
            # ngày thấy lần đo của lượt trước — không hiện "Chờ đo" lần nữa.
            vitals: dict[str, dict[str, Any]] = {}
            phien: list[asyncpg.Record] = []
            ghi_chu: list[asyncpg.Record] = []
            chi_dinh: list[asyncpg.Record] = []
            hang_cho: list[asyncpg.Record] = []
            vong: list[asyncpg.Record] = []
            yeu_cau: list[asyncpg.Record] = []
            if ids:
                vitals = await sinh_hieu_cua_buoi_nhieu(conn, cid, ids)
                phien = await conn.fetch(
                    """
                    SELECT c.id::text AS id, c.visit_id::text AS visit_id, c.round_no,
                           c.kind, c.status, c.outcome,
                           c.doctor_staff_id::text AS doctor_id,
                           c.started_by::text AS started_by
                      FROM consultation c
                     WHERE c.clinic_id = $1::uuid AND c.visit_id = ANY($2::uuid[])
                     ORDER BY c.visit_id, c.round_no
                    """,
                    cid,
                    ids,
                )
                if doc_noi_dung:
                    ghi_chu = await conn.fetch(
                        """
                        SELECT n.consultation_id::text AS consultation_id, n.body,
                               n.created_at, s.full_name AS recorded_by_name
                          FROM consultation_note n
                          JOIN consultation c
                            ON c.id = n.consultation_id AND c.clinic_id = n.clinic_id
                          LEFT JOIN staff s ON s.id = n.recorded_by
                         WHERE n.clinic_id = $1::uuid AND c.visit_id = ANY($2::uuid[])
                         ORDER BY n.created_at
                        """,
                        cid,
                        ids,
                    )
                chi_dinh = await conn.fetch(
                    """
                    SELECT o.id::text AS id, o.visit_id::text AS visit_id,
                           o.consultation_id::text AS consultation_id,
                           o.service_code, o.service_name, o.node_code, o.exec_status,
                           o.room_id::text AS room_id, r.name AS room_name,
                           o.hold_until_round, o.version, o.result_note,
                           o.not_performed_reason,
                           rec.full_name AS recorded_by_name,
                           au.full_name AS authorized_by_name,
                           pf.full_name AS performed_by_name,
                           coalesce(nd.lam_ben_ngoai, false) AS doi_tac,
                           o.ket_qua_luc, o.doi_tac_cho_tai_lieu_luc,
                           o.selection_status, o.execution_status,
                           o.routing_revision,
                           lam.started_at AS lam_bat_dau_luc,
                           lam.ended_at AS lam_xong_luc,
                           lam.status AS lam_trang_thai,
                           lam.phong AS lam_phong,
                           -- Có phiếu kết quả đã hoàn tất để bác sĩ mở đọc
                           -- (nhóm 3 nợ, 24/09) + đã có ai chuyên môn xem chưa.
                           EXISTS (SELECT 1 FROM form_instance f
                                    WHERE f.clinic_id = o.clinic_id
                                      AND f.service_order_id = o.id
                                      AND f.trang_thai = 'READY') AS co_phieu,
                           o.da_xem_ket_qua_luc,
                           -- Khách trả TRỰC TIẾP cho đối tác (27/09/2026): đối
                           -- tác đã ghi nhận thu chưa — sổ của khối Đối tác.
                           EXISTS (SELECT 1 FROM service_price sp
                                    WHERE sp.clinic_id = o.clinic_id
                                      AND sp.service_code = o.service_code
                                      AND sp.active AND sp."group" = 'dich_vu'
                                      AND sp.billing_owner = 'EXTERNAL_PARTNER')
                             AS doi_tac_thu,
                           (SELECT tt.so_tien FROM doi_tac_thanh_toan tt
                             WHERE tt.clinic_id = o.clinic_id
                               AND tt.service_order_id = o.id
                               AND tt.huy_luc IS NULL) AS doi_tac_da_thu_so_tien
                      FROM service_order o
                      LEFT JOIN node_definition nd
                        ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                      LEFT JOIN clinic_room r
                        ON r.id = o.room_id AND r.clinic_id = o.clinic_id
                      -- GIỜ CỦA PHÒNG (luồng chuẩn bước 8, 23/09/2026): bác sĩ
                      -- chính thấy dịch vụ đang làm ở đâu, bắt đầu/xong lúc nào —
                      -- nối thẳng tới lần làm gần nhất mà phòng đã bấm.
                      LEFT JOIN LATERAL (
                          SELECT a.started_at,
                                 coalesce(a.completed_at, a.interrupted_at) AS ended_at,
                                 a.status, ar.name AS phong
                            FROM service_execution_attempt a
                            LEFT JOIN clinic_room ar
                              ON ar.id = a.room_id_snapshot
                             AND ar.clinic_id = a.clinic_id
                           WHERE a.clinic_id = o.clinic_id
                             AND a.service_order_id = o.id
                           ORDER BY a.attempt_no DESC
                           LIMIT 1
                      ) lam ON true
                      LEFT JOIN staff rec ON rec.id = o.recorded_by
                      LEFT JOIN staff au ON au.id = o.authorized_by
                      LEFT JOIN staff pf ON pf.id = o.performed_by
                     WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
                       AND (o.exec_status <> 'draft' OR $3::boolean)
                     ORDER BY o.created_at, o.id
                    """,
                    cid,
                    ids,
                    # Nháp chỉ định: người có lego Bàn khám (27/09 đợt 3).
                    await can(conn, identity, "clinical.consult.perform"),
                )
                hang_cho = await conn.fetch(
                    """
                    SELECT q.id::text AS id, q.visit_id::text AS visit_id, q.lane,
                           q.reason, q.ref_id::text AS ref_id, q.status,
                           q.eligible_at, q.created_at,
                           q.room_id::text AS room_id,
                           q.doctor_staff_id::text AS doctor_id
                      FROM queue_entry q
                     WHERE q.clinic_id = $1::uuid AND q.visit_id = ANY($2::uuid[])
                       AND q.status NOT IN ('done', 'left', 'cancelled')
                    """,
                    cid,
                    ids,
                )
                vong = await conn.fetch(
                    """
                    SELECT r.id::text AS id, r.visit_id::text AS visit_id,
                           r.round_no, r.status
                      FROM review_round r
                     WHERE r.clinic_id = $1::uuid AND r.visit_id = ANY($2::uuid[])
                     ORDER BY r.visit_id, r.round_no
                    """,
                    cid,
                    ids,
                )
                if vong:
                    yeu_cau = await conn.fetch(
                        """
                        SELECT q.round_id::text AS round_id,
                               q.service_order_id::text AS order_id, q.need, q.status,
                               o.exec_status, o.selection_status
                          FROM round_requirement q
                          JOIN service_order o
                            ON o.id = q.service_order_id AND o.clinic_id = q.clinic_id
                         WHERE q.clinic_id = $1::uuid AND q.round_id = ANY($2::uuid[])
                        """,
                        cid,
                        [r["id"] for r in vong],
                    )
            phong = await conn.fetch(
                """
                SELECT r.id::text AS id, r.code, r.name,
                       array_agg(rn.node_code ORDER BY rn.node_code) AS nodes
                  FROM clinic_room r
                  JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.is_active AND r.accepting
                 GROUP BY r.id, r.code, r.name, r.sort
                 ORDER BY r.sort, r.code
                """,
                cid,
            )
            dich_vu = await conn.fetch(
                """
                SELECT DISTINCT ON (s.service_code)
                       s.service_code, s.name, s.node_code, n.actor_roles
                  FROM service_price s
                  JOIN node_definition n
                    ON n.clinic_id = s.clinic_id AND n.code = s.node_code
                 WHERE s.clinic_id = $1::uuid AND s.active
                   AND s.node_code LIKE 'DICHVU-%'
                 ORDER BY s.service_code, (s."group" = 'dich_vu') DESC
                """,
                cid,
            )
            lich: list[asyncpg.Record] = []
            if la_hom_nay and await can(conn, identity, "reception.checkin.perform"):
                lich = await conn.fetch(
                    """
                    SELECT a.id::text AS id, a.slot_start, a.status,
                           p.full_name, p.patient_code, d.full_name AS doctor_name
                      FROM appointment a
                      JOIN patient p
                        ON p.clinic_patient_id = a.clinic_patient_id
                       AND p.clinic_id = a.clinic_id
                      LEFT JOIN staff d ON d.id = a.doctor_id
                     WHERE a.clinic_id = $1::uuid
                       AND a.status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
                       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                           = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                     ORDER BY a.slot_start, a.id
                    """,
                    cid,
                )

        by_visit: dict[str, dict[str, Any]] = {}
        bay_gio = now_vn()
        for v in visits:
            by_visit[v["visit_id"]] = {
                "visit_id": v["visit_id"],
                "ma_bn": v["patient_code"],
                "ten": v["full_name"],
                "bac_si_id": v["doctor_id"],
                "bac_si": v["doctor_name"],
                "check_in_luc": _iso(v["checked_in_at"]),
                "sinh_hieu_trang_thai": v["vitals_status"] or "pending",
                # Mốc [Bắt đầu] đo — trạng thái "đang đo" đọc từ ĐÂY và từ
                # `sinh_hieu_trang_thai`, không còn suy từ giờ gọi.
                "bat_dau_do_luc": _iso(v["vitals_started_at"]),
                "bat_dau_do_boi": v["vitals_started_by"],
                # DỮ LIỆU CŨ: giữ để lượt trước 23/09 còn đọc được giờ gọi.
                # Màn Đo sinh hiệu KHÔNG dùng nó làm trạng thái nữa.
                "goi_do_luc": _iso(v["goi_do_luc"]),
                "goi_do_boi": v["goi_do_boi"],
                "so_tiep_don": v["so_tiep_don"],
                "so_booking": v.get("so_booking"),
                # Màn đo sinh hiệu (27/09 tối): loại khám + phút chờ + cờ chờ lâu
                # — ngưỡng ở luot_kham_rules, màn chỉ tô màu.
                "loai_kham": v.get("loai_kham"),
                "cho_phut": (
                    cho := rules.phut_cho(v["checked_in_at"], bay_gio)
                    if la_hom_nay
                    else None
                ),
                "cho_lau": rules.cho_do_lau(cho),
                "dich": v["route_decision"],
                "ket_thuc_luc": _iso(v["finished_at"]),
                "sinh_hieu": None,
                "phien": [],
                "chi_dinh": [],
                "hang_cho": [],
                "vong": [],
            }
        for vid_, m in vitals.items():
            item = by_visit[vid_]
            # Buổi có số mà lượt này còn "chờ đo" (dây tắt / lượt kia đo SAU khi
            # lượt này check-in) → vẫn Chờ đo, khớp hàng tư vấn.
            if not rules.hien_so_do_buoi(
                vitals_status=item["sinh_hieu_trang_thai"],
                co_so_do_luot_nay=bool(m["co_so_do_luot_nay"]),
            ):
                continue
            item["sinh_hieu"] = {
                "tam_thu": m["systolic"],
                "tam_truong": m["diastolic"],
                "mach": m["pulse"],
                "nhiet_do": _num(m["temperature"]),
                "can_nang": _num(m["weight_kg"]),
                "chieu_cao": _num(m["height_cm"]),
                "nhip_tho": m["respiratory_rate"],
                "spo2": m["spo2"],
                "bmi": _num(m["bmi"]),
                "muc_do_dau": m["pain_score"],
                "luc": _iso(m["created_at"]),
                "nguoi_do": m["nguoi_do"],
                # "lượt trước" khi số đo của lượt khác cùng buổi; None = lượt này.
                "nguon": rules.nhan_nguon_sinh_hieu(
                    nguon_visit_id=m["nguon_visit_id"], visit_id=vid_
                ),
            }
        notes_by: dict[str, list[dict[str, Any]]] = {}
        for n in ghi_chu:
            notes_by.setdefault(n["consultation_id"], []).append(
                {
                    "noi_dung": n["body"],
                    "nguoi_ghi": n["recorded_by_name"],
                    "luc": _iso(n["created_at"]),
                }
            )
        for c in phien:
            by_visit[c["visit_id"]]["phien"].append(
                {
                    "id": c["id"],
                    "vong": c["round_no"],
                    "loai": c["kind"],
                    "trang_thai": c["status"],
                    "ket_qua": c["outcome"],
                    "bac_si_id": c["doctor_id"],
                    "nguoi_bat_dau_id": c["started_by"],
                    "ghi_chu": notes_by.get(c["id"], []),
                }
            )
        # Ô tick "Bỏ qua bác sĩ tư vấn" ở màn đo sinh hiệu đọc TRẠNG THÁI THẬT
        # (25/09/2026): phiên tư vấn huỷ = đang bỏ qua; đổi được khi bên nhận chưa
        # bắt đầu. Lượt không qua tư vấn → None (không hiện ô).
        for item in by_visit.values():
            tv = next((p for p in item["phien"] if p["loai"] == "TU_VAN"), None)
            chinh = next((p for p in item["phien"] if p["loai"] == "PRIMARY"), None)
            if tv is None or not la_hom_nay:
                item["tu_van"] = None
                continue
            bo_qua = tv["trang_thai"] == "cancelled"
            item["tu_van"] = {
                "bo_qua": bo_qua,
                "doi_duoc": (
                    chinh is None or chinh["trang_thai"] in ("queued", "cancelled")
                )
                if bo_qua
                else tv["trang_thai"] == "queued",
            }
        for o in chi_dinh:
            by_visit[o["visit_id"]]["chi_dinh"].append(
                {
                    "id": o["id"],
                    "phien_id": o["consultation_id"],
                    "ma_dich_vu": o["service_code"],
                    "ten_dich_vu": o["service_name"],
                    "node": o["node_code"],
                    "trang_thai": o["exec_status"],
                    "phong_id": o["room_id"],
                    "phong": o["room_name"],
                    "giu_toi_vong": o["hold_until_round"],
                    "version": o["version"],
                    "nguoi_ghi": o["recorded_by_name"],
                    "nguoi_duyet": o["authorized_by_name"],
                    "nguoi_lam": o["performed_by_name"],
                    "ket_qua": o["result_note"] if doc_noi_dung else None,
                    "ly_do_khong_lam": o["not_performed_reason"],
                    # Lần làm gần nhất ở phòng: bắt đầu/xong lúc nào, ở phòng
                    # nào (có thể khác phòng được xếp nếu lễ tân đã đổi).
                    "lam_bat_dau_luc": _iso(o.get("lam_bat_dau_luc")),
                    "lam_xong_luc": _iso(o.get("lam_xong_luc")),
                    "lam_trang_thai": o.get("lam_trang_thai"),
                    "lam_phong": o.get("lam_phong"),
                    "co_phieu": bool(o.get("co_phieu")),
                    "da_xem_ket_qua_luc": _iso(o.get("da_xem_ket_qua_luc")),
                    "routing_revision": o.get("routing_revision"),
                    "doi_phong_duoc": rules.doi_phong_duoc(
                        selection_status=o.get("selection_status"),
                        execution_status=o.get("execution_status"),
                        exec_status=o["exec_status"],
                        doi_tac=bool(o["doi_tac"]),
                    ),
                    # Việc gửi đối tác: không phòng nào của phòng khám xếp được,
                    # màn hình nói trạng thái ĐỐI TÁC thay vì "chờ xếp phòng".
                    "doi_tac": o["doi_tac"],
                    # "Đối tác đã thu / chưa thu" (27/09/2026). None = không
                    # phải việc khách trả đối tác.
                    "doi_tac_thu_tien": (
                        (
                            "DA_THU"
                            if o.get("doi_tac_da_thu_so_tien") is not None
                            else "CHUA_THU"
                        )
                        if o.get("doi_tac_thu")
                        else None
                    ),
                    "doi_tac_da_thu_so_tien": (
                        int(o["doi_tac_da_thu_so_tien"])
                        if o.get("doi_tac_da_thu_so_tien") is not None
                        else None
                    ),
                    "trang_thai_doi_tac": (
                        trang_thai_doi_tac(
                            exec_status=o["exec_status"],
                            cho_tai_lieu=o["doi_tac_cho_tai_lieu_luc"] is not None,
                            co_ket_qua=o["ket_qua_luc"] is not None,
                        )
                        if o["doi_tac"]
                        else None
                    ),
                }
            )
        views = [
            rules.QueueView(q["id"], q["status"], q["eligible_at"], q["created_at"])
            for q in hang_cho
        ]
        order = {e.id: i for i, e in enumerate(rules.order_queue(views))}
        for q in sorted(hang_cho, key=lambda x: order.get(x["id"], 0)):
            by_visit[q["visit_id"]]["hang_cho"].append(
                {
                    "id": q["id"],
                    "hang": q["lane"],
                    "ly_do": q["reason"],
                    "ref_id": q["ref_id"],
                    "trang_thai": q["status"],
                    "du_dieu_kien_luc": _iso(q["eligible_at"]),
                    "phong_id": q["room_id"],
                    "bac_si_id": q["doctor_id"],
                }
            )
        req_by: dict[str, list[dict[str, Any]]] = {}
        for q in yeu_cau:
            req_by.setdefault(q["round_id"], []).append(
                {
                    "chi_dinh_id": q["order_id"],
                    "can": q["need"],
                    # Cùng luật với vòng đọc (`luot_kham_rules.requirement_state`):
                    # chỉ định không làm / khách không chọn → bác sĩ phải quyết.
                    "trang_thai": (
                        "needs_decision"
                        if q["status"] == "open"
                        and (
                            q["exec_status"] in rules.KHONG_THUC_HIEN
                            or q["selection_status"] == "NOT_SELECTED"
                        )
                        else q["status"]
                    ),
                }
            )
        for r in vong:
            by_visit[r["visit_id"]]["vong"].append(
                {
                    "id": r["id"],
                    "vong": r["round_no"],
                    "trang_thai": r["status"],
                    "yeu_cau": req_by.get(r["id"], []),
                }
            )
        return {
            "vai": identity.role.value,
            "toi": identity.staff_id,
            "ngay": ngay_xem.isoformat(),
            "hom_nay": la_hom_nay,
            "luot": list(by_visit.values()),
            "phong": [
                {
                    "id": p["id"],
                    "ma": p["code"],
                    "ten": p["name"],
                    "nodes": list(p["nodes"]),
                }
                for p in phong
            ],
            "dich_vu": [
                {
                    "ma": s["service_code"],
                    "ten": s["name"],
                    "node": s["node_code"],
                    "vai_lam": list(s["actor_roles"] or []),
                }
                for s in dich_vu
            ],
            "lich_cho_check_in": [
                {
                    "id": a["id"],
                    "gio": _iso(a["slot_start"]),
                    "ten": a["full_name"],
                    "ma_bn": a["patient_code"],
                    "bac_si": a["doctor_name"],
                }
                for a in lich
            ],
        }

    async def phong_hom_nay(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Phòng mà người gọi đứng trong lịch HÔM NAY — mỗi phòng một hàng chờ."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT r.id::text AS id, r.code, r.name, r.floor, r.sort,
                       array_agg(DISTINCT w.station) AS vi_tri,
                       array_agg(DISTINCT rn.node_code) AS nodes
                  FROM work_roster w
                  JOIN vi_tri_lam_viec v
                    ON v.clinic_id = w.clinic_id AND v.code = w.station
                  JOIN clinic_room r
                    ON r.id = v.room_id AND r.clinic_id = w.clinic_id AND r.is_active
                  LEFT JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE w.clinic_id = $1::uuid AND w.staff_id = $2::uuid
                   AND w.status <> 'REJECTED'
                   AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                 GROUP BY r.id, r.code, r.name, r.floor, r.sort
                 ORDER BY r.sort, r.code
                """,
                identity.clinic_id,
                identity.staff_id,
            )
            tat_ca = await conn.fetch(
                """
                SELECT r.id::text AS id, r.code, r.name, r.floor,
                       array_agg(rn.node_code ORDER BY rn.node_code) AS nodes
                  FROM clinic_room r
                  JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.is_active
                 GROUP BY r.id, r.code, r.name, r.floor, r.sort
                 ORDER BY r.sort, r.code
                """,
                identity.clinic_id,
            )
        return {
            "phong_cua_toi": [
                {
                    "id": r["id"],
                    "code": r["code"],
                    "ten": r["name"],
                    "tang": r["floor"],
                    "vi_tri": list(r["vi_tri"] or []),
                    "nodes": [n for n in (r["nodes"] or []) if n],
                }
                for r in rows
            ],
            "tat_ca_phong": [
                {
                    "id": r["id"],
                    "code": r["code"],
                    "ten": r["name"],
                    "tang": r["floor"],
                    "nodes": list(r["nodes"] or []),
                    "la_phong_dich_vu": la_phong_dich_vu(r["nodes"] or []),
                }
                for r in tat_ca
            ],
        }

    async def hang_cho(
        self,
        *,
        identity: StaffIdentity,
        room_id: str | None,
        tu_van: bool = False,
        ngay: Any = None,
    ) -> dict[str, Any]:
        """HÀNG CHỜ của một phòng: ai đang chờ, ai đang trong phòng, ai đã xong.

        `ngay` (29/09/2026, YYYY-MM-DD; rác/None = hôm nay): xem lại hàng chờ
        của một NGÀY CŨ — khách check-in ngày ấy, mọi trạng thái. Ngày cũ không
        có "chưa xếp phòng" / "sắp tới" (việc của hôm nay). Chỉ ĐỌC: mỗi lệnh
        vẫn tự hỏi luật của nó khi bấm.

        Tuyền 16/09/2026: *"sẽ luôn có 1 danh sách các khách đang xếp hàng, sau đó
        bác sĩ chọn rồi ấn bắt đầu khám cho người đó, rồi điền thông tin bên
        trong, khám xong thì ghi đã khám xong — vậy là check-out cho khách ở
        phòng đó"*.

        Một phòng có hai loại chỗ chờ:
          * chỉ định xếp vào phòng (siêu âm, lấy mẫu, thủ thuật) — theo `room_id`;
          * lượt khám chính của BÁC SĨ đứng phòng ấy hôm nay — khám chính chờ theo
            bác sĩ, không theo phòng, nên phải tra lịch để biết bác sĩ nào.

        THỨ TỰ: giờ vào hàng chờ, tức giờ đo sinh hiệu xong hoặc giờ được chỉ
        định; số thứ tự trong ngày là thứ tự CHECK-IN, như phiếu lễ tân phát.
        """
        cid = identity.clinic_id
        rid = _uuid(room_id, "Mã phòng không hợp lệ.") if room_id else None
        hom_nay = hom_nay_vn()
        ngay_xem = doc_ngay_xem(ngay) or hom_nay
        la_hom_nay = ngay_xem == hom_nay
        async with self._pool.acquire() as conn:
            # Hàng nào cần lego nào (đợt 3, 27/09/2026) — `permissions/doc_bang`.
            await doi_mot_quyen(
                conn,
                identity,
                quyen_doc_hang_cho(tu_van=tu_van, co_phong=rid is not None),
                phong_id=rid if rid is not None and not tu_van else None,
                cau="Bạn không có quyền thao tác ở hàng chờ này.",
            )
            # Theo QUYỀN (khối khám / kết quả), không theo vai — 24/09/2026.
            doc_noi_dung = await doc_duoc_y_khoa(conn, identity)
            phong = None
            if rid is not None:
                phong = await conn.fetchrow(
                    """
                    SELECT r.id::text AS id, r.code, r.name, r.floor,
                           array_agg(rn.node_code) AS nodes
                      FROM clinic_room r
                      LEFT JOIN clinic_room_node rn
                        ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                     WHERE r.clinic_id = $1::uuid AND r.id = $2::uuid
                     GROUP BY r.id
                    """,
                    cid,
                    rid,
                )
                if phong is None:
                    raise NotFoundError("Không tìm thấy phòng này.")
            # Khách đã trả mà chưa xếp phòng — mọi phòng làm được đều thấy để
            # nhận (Tuyền 24/09/2026: "không chỉ định thì khách vẫn xuất hiện ở
            # hàng đợi và có thể khám ở các dịch vụ khả thi").
            from clinicai.services.service_routing_service import cho_nhan_vao_phong

            chua_xep = (
                await cho_nhan_vao_phong(conn, cid, rid) if rid and la_hom_nay else []
            )
            # Bác sĩ có lượt khám chính trong hàng chờ này.
            if rid is not None:
                # 29/09/2026: theo CA đang diễn ra (không chỉ ngày) + tính cả
                # bác sĩ siêu âm; ngoài giờ ca rơi về cả ngày (hàng không rỗng).
                bac_si = await conn.fetch(
                    """
                    SELECT w.staff_id::text AS id, w.station, w.shift, w.status,
                           c.settings
                      FROM work_roster w
                      JOIN vi_tri_lam_viec v
                        ON v.clinic_id = w.clinic_id AND v.code = w.station
                      JOIN clinic_membership m
                        ON m.staff_id = w.staff_id AND m.clinic_id = w.clinic_id
                       AND m.is_active AND m.role = ANY($4::text[])
                      JOIN clinic c ON c.id = w.clinic_id
                     WHERE w.clinic_id = $1::uuid AND v.room_id = $2::uuid
                       AND w.status <> 'REJECTED'
                       AND w.work_date = $3::date
                     ORDER BY w.staff_id
                    """,
                    cid,
                    rid,
                    ngay_xem,
                    list(VAI_BAC_SI),
                )
                dong = [
                    (r["id"], str(r["station"]), str(r["shift"]), str(r["status"]))
                    for r in bac_si
                ]
                if la_hom_nay and bac_si:
                    bay_gio = now_vn()
                    ds_bac_si = bac_si_trong_ca_hoac_ca_ngay(
                        dong, bay_gio.hour * 60 + bay_gio.minute, bac_si[0]["settings"]
                    )
                else:
                    ds_bac_si = list(dict.fromkeys(ai for ai, *_ in dong))
            else:
                ds_bac_si = []
            so_bac_si_trong_phong = len(ds_bac_si)
            # "Khách của tôi" (không chọn phòng) cho người ĐIỀU PHỐI hoặc thư ký
            # chưa bị giới hạn theo bác sĩ: thấy lượt khám chính của MỌI bác sĩ.
            # Bản trước trả rỗng cho thư ký ở chế độ mở quyền — thư ký mở Bàn khám
            # mà không thấy ai (tự kiểm 16/09/2026).
            # THEO LEGO, không theo vai (27/09 đợt 3 — "chỉ dùng lego"):
            #   * đã được phân đi cùng bác sĩ (thư ký) → khách của bác sĩ ấy;
            #   * có quyền Hoàn tất khám ("bác sĩ") → khách của chính mình;
            #   * có Khám mà không Hoàn tất (thư ký chưa phân) → mọi bác sĩ;
            #   * lego Điều phối → mọi bác sĩ.
            #   * 28/09 — QUYỀN THEO LỊCH, nửa "mở" (`permissions/lich.py`): không
            #     chọn phòng thì "khách của tôi" = khách của các bác sĩ CÙNG PHÒNG
            #     với tôi trong lịch hôm nay; không có lịch thì như cũ.
            #   * 29/09 — thư ký đã phân theo bác sĩ: danh sách phân công HỢP với
            #     bác sĩ cùng phòng trong lịch hôm nay (`bac_si_cua_thu_ky`).
            tat_ca_bac_si = False
            if not tu_van:
                cua_toi = await bac_si_cua_thu_ky(conn, identity)
                if cua_toi is not None:
                    ds_bac_si = sorted(
                        {*ds_bac_si, *cua_toi} if rid is None else cua_toi
                    )
                elif rid is None:
                    la_bac_si = bool(
                        await conn.fetchval(
                            "SELECT EXISTS (SELECT 1 FROM clinic_membership"
                            " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
                            " AND is_active AND role = ANY($3::text[]))",
                            cid,
                            identity.staff_id,
                            list(VAI_BAC_SI),
                        )
                    )
                    ds_bac_si, tat_ca_bac_si = khach_cua_toi(
                        toi=identity.staff_id,
                        la_bac_si=la_bac_si,
                        # Lịch của NGÀY ĐANG XEM (ngày cũ → lịch hôm ấy).
                        cung_phong=await bac_si_cung_phong_hom_nay(
                            conn, cid, identity.staff_id, ngay_xem
                        ),
                        kham_duoc=await can(conn, identity, "clinical.consult.perform"),
                    )
                elif await can(conn, identity, "clinical.consult.finalize"):
                    ds_bac_si = sorted({*ds_bac_si, identity.staff_id})
                # Mở full lego (30/09/2026): ai cũng có lego Điều phối, nên chỉ
                # mở "mọi bác sĩ" khi người ấy KHÔNG có danh sách bác sĩ của
                # riêng mình (là bác sĩ / cùng phòng trong lịch / thư ký đã
                # phân) — bác sĩ mở Bàn khám vẫn thấy đúng khách của mình.
                if (
                    rid is None
                    and not ds_bac_si
                    and await can(conn, identity, "dispatch.manage")
                ):
                    tat_ca_bac_si = True
            rows = await conn.fetch(
                """
                WITH stt AS (
                    SELECT v.visit_id,
                           row_number() OVER (ORDER BY v.checked_in_at, v.visit_id)
                               AS so
                      FROM visit v
                     WHERE v.clinic_id = $1::uuid AND v.checked_in_at IS NOT NULL
                       AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                           = $6::date
                )
                SELECT q.id::text AS id, q.status, q.lane, q.reason,
                       q.ref_id::text AS ref_id, q.visit_id::text AS visit_id,
                       q.eligible_at, q.called_at, q.serving_at, q.done_at,
                       q.created_at,
                       stt.so AS so_thu_tu,
                       ap.so_booking, ap.so_tiep_don,
                       p.clinic_patient_id::text AS clinic_patient_id,
                       p.full_name, p.patient_code, p.uu_tien, p.uu_tien_ly_do,
                       v.appointment_id::text AS appointment_id,
                       v.checked_in_at,
                       st.name AS dich_vu_kham, st.form_code,
                       d.full_name AS bac_si,
                       coalesce(o.service_name, st.name) AS viec,
                       o.service_code, o.node_code, o.exec_status,
                       o.result_note, o.ket_qua_luc, o.duyet_luc,
                       o.not_performed_reason, pf.full_name AS nguoi_lam,
                       v.status AS visit_status, v.finalized_at,
                       -- "Người ký" = BÁC SĨ (Tuyền 29/09/2026); người bấm chỉ
                       -- hiện nhỏ khi không phải chính bác sĩ ấy.
                       bsky.full_name AS nguoi_ky,
                       CASE WHEN fb.id IS DISTINCT FROM bsky.id
                            THEN fb.full_name END AS nguoi_bam_ky,
                       c.status AS phien_status, c.kind AS phien_kind,
                       r.name AS phong
                  FROM queue_entry q
                  JOIN visit v ON v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id
                  JOIN stt ON stt.visit_id = q.visit_id
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN service_type st ON st.id = v.service_type_id
                  LEFT JOIN staff d
                    ON d.id = coalesce(q.doctor_staff_id, v.attending_doctor_id)
                  LEFT JOIN service_order o
                    ON o.id = q.ref_id AND q.reason = 'SERVICE'
                   AND o.clinic_id = q.clinic_id
                  LEFT JOIN consultation c
                    ON c.id = q.ref_id AND q.reason <> 'SERVICE'
                   AND c.clinic_id = q.clinic_id
                  LEFT JOIN clinic_room r ON r.id = q.room_id
                  LEFT JOIN staff pf ON pf.id = o.performed_by
                  LEFT JOIN staff fb ON fb.id = v.finalized_by
                """
                + sql_join_bac_si_ky_luot("v", "bsky")
                + """
                  LEFT JOIN appointment ap
                    ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
                 WHERE q.clinic_id = $1::uuid
                   AND (q.status IN ('blocked', 'waiting', 'called', 'serving', 'done')
                        -- Ngày cũ: cả chỗ chờ khách đã về (`left`) — quay lại
                        -- làm / sửa được (Tuyền 29/09/2026).
                        OR (q.status = 'left' AND NOT $7::boolean))
                   AND (
                        ($2::uuid IS NOT NULL AND q.lane = 'ROOM'
                             AND q.room_id = $2::uuid)
                     -- Hàng TƯ VẤN là hàng CHUNG: ai mở màn tư vấn cũng thấy hết.
                     OR ($5::boolean AND q.lane = 'TU_VAN')
                     OR (NOT $5::boolean AND q.lane = 'DOCTOR'
                             AND ($4::boolean
                                  OR q.doctor_staff_id::text = ANY($3::text[])
                                  -- Khách CHƯA có bác sĩ (lịch hẹn không gắn
                                  -- bác sĩ): hiện ở mọi hàng chờ khám có bác sĩ,
                                  -- ai bấm Bắt đầu khám thì nhận. Bản trước khách
                                  -- này không nằm trong hàng chờ của AI cả (tự
                                  -- kiểm 16/09/2026).
                                  OR (q.doctor_staff_id IS NULL
                                      AND cardinality($3::text[]) > 0)))
                     -- KHÁCH ĐẶT THỦ THUẬT / SÀN CHẬU (loại khám "đi thẳng
                     -- phòng") — MỞ (Tuyền 24/09/2026: "khách chọn khám sàn chậu
                     -- hay thủ thuật thì open cho họ, họ có thể được event ở các
                     -- phòng thủ thuật hay sàn chậu này"): lượt khám chính hiện
                     -- ở MỌI phòng làm thủ thuật, dù đã gắn bác sĩ nào. Ai ở
                     -- phòng ấy bấm Bắt đầu khám là nhận.
                     OR ($2::uuid IS NOT NULL AND NOT $5::boolean
                         AND q.lane = 'DOCTOR'
                         AND EXISTS (
                             SELECT 1 FROM service_type dt
                               LEFT JOIN appointment da
                                 ON da.id = v.appointment_id
                                AND da.clinic_id = v.clinic_id
                              WHERE dt.clinic_id = v.clinic_id
                                AND dt.id = coalesce(v.service_type_id,
                                                     da.service_type_id)
                                AND dt.di_thang_phong)
                         AND EXISTS (
                             SELECT 1 FROM clinic_room_node rn
                              WHERE rn.clinic_id = q.clinic_id
                                AND rn.room_id = $2::uuid
                                AND rn.node_code = 'DICHVU-THUTHUAT'))
                   )
                 ORDER BY
                   CASE q.status WHEN 'serving' THEN 0 WHEN 'called' THEN 1
                        WHEN 'waiting' THEN 2 WHEN 'blocked' THEN 3 ELSE 4 END,
                   coalesce(q.eligible_at, q.created_at), q.id
                """,
                cid,
                rid,
                ds_bac_si,
                tat_ca_bac_si,
                tu_van,
                ngay_xem,
                la_hom_nay,
            )
            # SẮP TỚI (Tuyền chốt 24/09): khách của bác sĩ chính đang ở bước tư
            # vấn — bác sĩ chính THẤY trước nhưng chưa gọi được (chưa có chỗ chờ
            # ở hàng bác sĩ). Tư vấn bấm Xong thì khách mới vào hàng thật.
            sap_toi = (
                []
                if tu_van or not la_hom_nay
                else await conn.fetch(
                    """
                    SELECT v.visit_id::text AS visit_id, p.full_name, p.patient_code,
                           a.so_tiep_don, a.so_booking,
                           q.status AS tu_van_status, f.vitals_status
                      FROM consultation c
                      JOIN visit v
                        ON v.visit_id = c.visit_id AND v.clinic_id = c.clinic_id
                      JOIN patient p
                        ON p.clinic_patient_id = v.clinic_patient_id
                       AND p.clinic_id = v.clinic_id
                      LEFT JOIN appointment a
                        ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
                      LEFT JOIN encounter_flow f
                        ON f.visit_id = v.visit_id AND f.clinic_id = v.clinic_id
                      LEFT JOIN queue_entry q
                        ON q.ref_id = c.id AND q.clinic_id = c.clinic_id
                       AND q.status NOT IN ('done', 'left', 'cancelled')
                     WHERE c.clinic_id = $1::uuid AND c.kind = 'TU_VAN'
                       AND c.status IN ('queued', 'in_progress')
                       AND v.status IN ('OPEN', 'IN_PROGRESS')
                       AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                           = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       AND ($3::boolean
                            OR v.attending_doctor_id::text = ANY($2::text[])
                            OR (v.attending_doctor_id IS NULL
                                AND cardinality($2::text[]) > 0))
                     ORDER BY v.checked_in_at, v.visit_id
                    """,
                    cid,
                    ds_bac_si,
                    tat_ca_bac_si,
                )
            )
        now_rows = [
            {
                "id": r["id"],
                "trang_thai": r["status"],
                "loai": (
                    "TU_VAN"
                    if r["reason"] == "TU_VAN"
                    else "KHAM"
                    if r["reason"] != "SERVICE"
                    else "DICH_VU"
                ),
                "ref_id": r["ref_id"],
                "visit_id": r["visit_id"],
                "clinic_patient_id": r["clinic_patient_id"],
                "appointment_id": r["appointment_id"],
                "so_thu_tu": int(r["so_thu_tu"]),
                # Số booking (cấp lúc đặt) + số check-in (quầy cấp) — hiện cạnh
                # tên ở MỌI khâu (Tuyền 27/09). `so_thu_tu` giữ để xếp hàng.
                "so_booking": r["so_booking"],
                "so_tiep_don": r["so_tiep_don"],
                "ten": r["full_name"],
                "ma_bn": r["patient_code"],
                "uu_tien": bool(r["uu_tien"]),
                "uu_tien_ly_do": r["uu_tien_ly_do"],
                "viec": r["viec"],
                "dich_vu_kham": r["dich_vu_kham"],
                "form_code": r["form_code"],
                "service_code": r["service_code"],
                "node_code": r["node_code"],
                "exec_status": r["exec_status"],
                "phien_status": r["phien_status"],
                "bac_si": r["bac_si"],
                "phong": r["phong"],
                "vao_hang_luc": _iso(r["eligible_at"] or r["created_at"]),
                # Mốc check-in của CẢ lượt: khách quay lại bác sĩ chính đọc kết
                # quả thì đồng hồ tổng vẫn chạy từ lúc vào phòng khám.
                "checkin_luc": _iso(r["checked_in_at"]),
                "vong": r["phien_kind"],
                # Khách QUAY LẠI bác sĩ chính (Tuyền 29/09): phiên khám chính đã
                # bắt đầu (bác sĩ chỉ định rồi cho đi làm dịch vụ, chưa bấm Khám
                # xong) mà chỗ chờ lại "đang chờ" = khách làm xong dịch vụ, về
                # đọc kết quả — Bàn khám xếp vào "Kết quả cần đọc", không phải
                # "Chờ khám".
                "quay_lai_doc_kq": (
                    r["phien_kind"] == "PRIMARY"
                    and r["phien_status"] == "in_progress"
                    and r["status"] in ("waiting", "called")
                ),
                "goi_luc": _iso(r["called_at"]),
                "bat_dau_luc": _iso(r["serving_at"]),
                "xong_luc": _iso(r["done_at"]),
                "ket_qua_luc": _iso(r["ket_qua_luc"]),
                "duyet_luc": _iso(r["duyet_luc"]),
                # Bệnh án đã ký (FINALIZED/AMENDED): màn khoá phiếu theo mốc
                # NÀY, không theo trạng thái hàng chờ — khách còn "đang khám"
                # mà bác sĩ đã ký thì phiếu tự lưu sẽ ăn 409 (rà 18/09).
                "da_ky": r["visit_status"] in ("FINALIZED", "AMENDED"),
                "ky_luc": _iso(r["finalized_at"]),
                "nguoi_ky": r["nguoi_ky"],
                "nguoi_bam_ky": r["nguoi_bam_ky"],
                "nguoi_lam": r["nguoi_lam"],
                # Nội dung kết quả là chữ chuyên môn: chỉ vai đọc lâm sàng thấy.
                "ket_qua_ghi": r["result_note"] if doc_noi_dung else None,
                "ly_do_khong_lam": r["not_performed_reason"],
            }
            for r in _theo_luat_xep_hang(rows)
            # Người đã xong chỉ giữ của hôm nay (ngày cũ: giữ hết — xem lại).
            if not la_hom_nay
            or r["status"] != "done"
            or (r["done_at"] is not None and _cung_ngay_vn(r["done_at"]))
        ]
        return {
            "phong": (
                {
                    "id": phong["id"],
                    "code": phong["code"],
                    "ten": phong["name"],
                    "tang": phong["floor"],
                    "nodes": [n for n in (phong["nodes"] or []) if n],
                }
                if phong
                else None
            ),
            "hang_cho": now_rows,
            "chua_xep_phong": chua_xep,
            "sap_toi": [
                {
                    "visit_id": r["visit_id"],
                    "ten": r["full_name"],
                    "ma_bn": r["patient_code"],
                    "so_tiep_don": r["so_tiep_don"],
                    "so_booking": r["so_booking"],
                    "dang_o": (
                        "đang tư vấn"
                        if r["tu_van_status"] == "serving"
                        else "chờ tư vấn"
                        if r["vitals_status"] == "recorded"
                        else "chờ đo sinh hiệu"
                    ),
                }
                for r in sap_toi
            ],
            # Phòng khám mà hôm nay chưa có bác sĩ nào trong lịch: màn nói rõ
            # vì sao hàng chờ khám trống, thay vì trông như "hết khách".
            "so_bac_si_trong_phong": so_bac_si_trong_phong if rid else None,
            "ngay": ngay_xem.isoformat(),
            "hom_nay": la_hom_nay,
        }

    async def chi_dinh_hom_nay(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Mọi chỉ định bác sĩ đã duyệt hôm nay, chia bốn nhóm cho trưởng ca.

        Cần điều phối (chưa có phòng) · Đã điều phối (có phòng, chưa làm) ·
        Đang thực hiện · Đã hoàn tất (đã làm / không làm được). Trưởng ca chỉ
        XẾP PHÒNG từng chỉ định — không tạo chỉ định, không bấm xong thay phòng.
        Kèm các mốc để dựng dòng thời gian, và vòng đọc kết quả (khách đã quay
        lại bác sĩ chưa).
        """
        # Lego 9 Điều phối khách (27/09 đợt 3, thay vai Trưởng ca / Quản lý).
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                "dispatch.manage",
                cau="Bạn không có quyền xem điều phối.",
            )
        rows = await self._pool.fetch(
            """
            SELECT o.id::text AS id, o.visit_id::text AS visit_id,
                   o.service_name, o.exec_status, o.created_at, o.authorized_at,
                   o.assigned_at, o.started_at, o.finished_at, o.ket_qua_luc,
                   rm.name AS phong, pb.full_name AS nguoi_lam,
                   p.full_name, p.patient_code,
                   (SELECT r.status FROM round_requirement q
                      JOIN review_round r
                        ON r.id = q.round_id AND r.clinic_id = q.clinic_id
                     WHERE q.clinic_id = o.clinic_id AND q.service_order_id = o.id
                     ORDER BY r.round_no DESC LIMIT 1)          AS vong_doc,
                   (SELECT q.need FROM round_requirement q
                     WHERE q.clinic_id = o.clinic_id AND q.service_order_id = o.id
                     ORDER BY q.created_at DESC LIMIT 1)        AS can,
                   -- Không phòng nào (kể cả phòng đối tác) làm bước này: chỉ
                   -- định sẽ kẹt "chờ xếp phòng" mãi — cấu hình, không phải
                   -- việc trưởng ca tự xoay được. Tính trong CƠ SỞ của lượt:
                   -- phòng ở cơ sở khác không cứu được khách đang đứng ở đây
                   -- (mô phỏng 24/09: phòng Lấy mẫu ở Hào Nam che mất báo
                   -- "không phòng nào làm được" ở Kim Ngưu).
                   NOT EXISTS (
                       SELECT 1 FROM clinic_room_node rn
                         JOIN clinic_room r2
                           ON r2.id = rn.room_id AND r2.clinic_id = rn.clinic_id
                        WHERE rn.clinic_id = o.clinic_id
                          AND rn.node_code = o.node_code
                          AND r2.is_active
                          AND (coalesce(v.location_id, (
                                   SELECT a.location_id FROM appointment a
                                    WHERE a.id = v.appointment_id
                                      AND a.clinic_id = v.clinic_id)) IS NULL
                               OR r2.location_id = coalesce(v.location_id, (
                                   SELECT a.location_id FROM appointment a
                                    WHERE a.id = v.appointment_id
                                      AND a.clinic_id = v.clinic_id))))
                                                                AS khong_co_phong
              FROM service_order o
              JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
              JOIN patient p
                ON p.clinic_patient_id = v.clinic_patient_id
               AND p.clinic_id = v.clinic_id
              LEFT JOIN clinic_room rm
                ON rm.id = o.room_id AND rm.clinic_id = o.clinic_id
              LEFT JOIN staff pb ON pb.id = o.performed_by
             WHERE o.clinic_id = $1::uuid
               AND o.exec_status NOT IN ('draft', 'cancelled')
               -- Khách BỎ ở quầy không còn là việc của ai (24/09/2026).
               AND o.selection_status IS DISTINCT FROM 'NOT_SELECTED'
               AND (o.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                   = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             ORDER BY o.created_at, o.id
             LIMIT $2
            """,
            identity.clinic_id,
            _TRAN_CHI_DINH_HOM_NAY,
        )
        # Cắt bớt mà không nói là nói dối bằng cách im lặng: trưởng ca nhìn một
        # bảng thiếu người mà tưởng đã hết. Đếm tổng để màn hình báo được.
        tong = await self._pool.fetchval(
            """
            SELECT count(*) FROM service_order o
             WHERE o.clinic_id = $1::uuid
               AND o.exec_status NOT IN ('draft', 'cancelled')
               -- Cùng điều kiện với danh sách (khách BỎ không tính) — lệch là
               -- báo nhầm "bảng đang bị cắt".
               AND o.selection_status IS DISTINCT FROM 'NOT_SELECTED'
               AND (o.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                   = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
            """,
            identity.clinic_id,
        )
        nhom = {
            "authorized": "can_dieu_phoi",
            "assigned": "da_dieu_phoi",
            "in_progress": "dang_thuc_hien",
            "performed": "da_hoan_tat",
            "not_performed": "da_hoan_tat",
        }
        return {
            "chi_dinh": [
                {
                    "id": r["id"],
                    "visit_id": r["visit_id"],
                    "ten": r["full_name"],
                    "ma_bn": r["patient_code"],
                    "dich_vu": r["service_name"],
                    "trang_thai": r["exec_status"],
                    "nhom": nhom.get(r["exec_status"], "can_dieu_phoi"),
                    "phong": r["phong"],
                    "nguoi_lam": r["nguoi_lam"],
                    "can": r["can"],
                    "vong_doc": r["vong_doc"],
                    "khong_co_phong": bool(r["khong_co_phong"]),
                    "chi_dinh_luc": _iso(r["authorized_at"] or r["created_at"]),
                    "xep_phong_luc": _iso(r["assigned_at"]),
                    "bat_dau_luc": _iso(r["started_at"]),
                    "xong_luc": _iso(r["finished_at"]),
                    "ket_qua_luc": _iso(r["ket_qua_luc"]),
                }
                for r in rows
            ],
            "tong": int(tong or 0),
            # True = bảng đang thiếu; màn hình phải nói ra, đừng để người dùng
            # tự phát hiện bằng cách không tìm thấy khách của mình.
            "bi_cat": int(tong or 0) > len(rows),
        }

    async def ket_qua_cho_duyet(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Chỉ định đã có kết quả (tệp hoặc nội dung) mà bác sĩ chưa duyệt.

        Cả chỉ định ĐÃ duyệt mà có tệp mới tải lên sau đó (đối tác gửi bản điều
        chỉnh): tệp mới không thừa hưởng lần duyệt cũ, nên phải quay lại đây —
        nếu không nó nằm im mãi, CSKH không bao giờ thấy (smoke 18/09).
        """
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, "result.review.approve")
            rows = await conn.fetch(
                """
                SELECT o.id::text AS id, o.service_name, o.node_code,
                       o.result_note, o.ket_qua_luc, o.exec_status,
                       o.visit_id::text AS visit_id,
                       v.appointment_id::text AS appointment_id,
                       p.clinic_patient_id::text AS clinic_patient_id,
                       p.full_name, p.patient_code,
                       d.full_name AS bac_si, v.attending_doctor_id::text AS bac_si_id,
                       pf.full_name AS nguoi_lam, o.duyet_luc
                  FROM service_order o
                  JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
                  LEFT JOIN node_definition nd
                    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                  LEFT JOIN staff pf ON pf.id = o.performed_by
                 WHERE o.clinic_id = $1::uuid
                   AND (
                     (coalesce(nd.lam_ben_ngoai, false) AND EXISTS (
                         SELECT 1 FROM tep_ket_qua t
                          WHERE t.clinic_id = o.clinic_id
                            AND t.service_order_id = o.id
                            AND t.xac_nhan_trang_thai = 'HOP_LE'
                     ))
                     OR
                     (
                       NOT coalesce(nd.lam_ben_ngoai, false)
                       AND o.ket_qua_luc IS NOT NULL
                     )
                   )
                   AND (o.duyet_luc IS NULL
                        OR EXISTS (SELECT 1 FROM tep_ket_qua t
                                    WHERE t.clinic_id = o.clinic_id
                                      AND t.service_order_id = o.id
                                      AND t.xac_nhan_trang_thai = 'HOP_LE'
                                      AND t.cho_phep_gui_luc IS NULL))
                   AND o.exec_status NOT IN ('draft', 'cancelled')
                   AND o.created_at > now() - interval '60 days'
                 ORDER BY (v.attending_doctor_id = $2::uuid) DESC NULLS LAST,
                          o.ket_qua_luc, o.id
                 LIMIT 200
                """,
                cid,
                identity.staff_id,
            )
            teps = await conn.fetch(
                """
                SELECT t.id::text AS id, t.service_order_id::text AS order_id,
                       t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte, t.tai_len_luc,
                       t.cho_phep_gui_luc IS NOT NULL AS da_cho_gui
                  FROM tep_ket_qua t
                 WHERE t.clinic_id = $1::uuid
                   AND t.service_order_id = ANY($2::uuid[])
                   AND t.xac_nhan_trang_thai = 'HOP_LE'
                 ORDER BY t.tai_len_luc
                """,
                cid,
                [r["id"] for r in rows],
            )
        theo: dict[str, list[dict[str, Any]]] = {}
        for t in teps:
            theo.setdefault(t["order_id"], []).append(
                {
                    "id": t["id"],
                    "ten": t["ten_hien_thi"],
                    "loai_tep": t["loai_tep"],
                    "mime": t["mime"],
                    "so_byte": int(t["so_byte"]),
                    "tai_len_luc": _iso(t["tai_len_luc"]),
                    "da_cho_gui": t["da_cho_gui"],
                }
            )
        return {
            "ket_qua": [
                {
                    "id": r["id"],
                    "dich_vu": r["service_name"],
                    "node_code": r["node_code"],
                    "noi_dung": r["result_note"],
                    "ket_qua_luc": _iso(r["ket_qua_luc"]),
                    "visit_id": r["visit_id"],
                    "appointment_id": r["appointment_id"],
                    "clinic_patient_id": r["clinic_patient_id"],
                    "ten": r["full_name"],
                    "ma_bn": r["patient_code"],
                    "bac_si": r["bac_si"],
                    "cua_toi": r["bac_si_id"] == identity.staff_id,
                    "nguoi_lam": r["nguoi_lam"],
                    "tep": theo.get(r["id"], []),
                    # Đã duyệt một lần — thẻ này có mặt vì có tệp mới chưa duyệt.
                    "duyet_lan_truoc": _iso(r["duyet_luc"]),
                }
                for r in rows
            ]
        }
