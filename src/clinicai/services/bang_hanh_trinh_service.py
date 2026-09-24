"""BẢNG HÀNH TRÌNH CHUNG — mỗi khách hôm nay: đang ở đâu, đã xong gì, còn chờ gì.

Tuyền đề xuất và đồng ý 24/09/2026 ("cần có thêm 1 bảng để mọi người cùng biết
à bệnh nhân này đã làm gì rồi"). Một bảng cho MỌI người, mở được từ mọi màn
(nút Xem hành trình) và bảng tổng này.

CHỈ ĐỌC, không luật nghiệp vụ mới: "đã xong gì" đọc projection dòng thời gian
(`luot_dong_thoi_gian`, dựng từ sổ sự kiện); "đang ở đâu" và "còn chờ gì" đọc
hiện trạng (hàng chờ, chỉ định, tệp kết quả). Không có nội dung lâm sàng.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.xem_luot_service import GOI_DUOC

_TRAN_LUOT = 300
_SO_VIEC_XONG = 6


def _dau_ngay() -> datetime:
    return datetime.now(CLINIC_TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def _noi(q: dict[str, Any]) -> str:
    if q["lane"] == "TU_VAN":
        return "bác sĩ tư vấn"
    if q["lane"] == "DOCTOR":
        return f"bác sĩ {q['bac_si']}" if q["bac_si"] else "bác sĩ chính"
    return q["phong"] or "phòng dịch vụ"


def dang_o(luot: dict[str, Any], hang: list[dict[str, Any]]) -> str:
    """Một câu "khách đang ở đâu" — hàm thuần, kiểm được không cần DB."""
    if luot["status"] == "INCOMPLETE":
        return "Bỏ về giữa chừng"
    if luot["closed_at"] is not None:
        return "Đã về"
    dang = [q for q in hang if q["status"] in ("serving", "called")]
    if dang:
        return "Đang ở " + _noi(dang[0])
    cho = [q for q in hang if q["status"] == "waiting"]
    if cho:
        return "Chờ " + ", ".join(dict.fromkeys(_noi(q) for q in cho))
    doi = [q for q in hang if q["status"] == "blocked"]
    if doi:
        return "Đợi (" + ", ".join(dict.fromkeys(_noi(q) for q in doi)) + ")"
    return "Ở quầy — chưa vào hàng nào"


def con_cho(
    hang: list[dict[str, Any]],
    chi_dinh: list[dict[str, Any]],
    tep_chua_xem: int,
    phieu_chua_xem: int = 0,
) -> list[str]:
    """Những việc còn chờ của một khách — hàm thuần."""
    out: list[str] = []
    for q in hang:
        if q["status"] == "waiting":
            out.append("Chờ " + _noi(q))
    for o in chi_dinh:
        ten = o["ten"]
        if o["selection_status"] == "PENDING":
            out.append(f"Chờ khách chọn làm: {ten}")
        elif o["selection_status"] == "SELECTED":
            ex = o["execution_status"] or "PENDING"
            if ex == "PENDING" and o["routing_status"] in (None, "UNASSIGNED"):
                # Đã trả mà chưa có phòng = TRÁCH NHIỆM đang rơi (người thu không
                # có quyền điều phối, hoặc dây tự xếp đang tắt) — nói thẳng.
                out.append(
                    f"ĐÃ TRẢ TIỀN — chờ xếp phòng: {ten}"
                    if o.get("da_tra")
                    else f"Chờ trả tiền: {ten}"
                )
            elif ex == "PENDING" and o["routing_status"] == "REASSIGNMENT_REQUIRED":
                out.append(f"Cần xếp lại phòng: {ten}")
            elif ex == "PENDING":
                out.append(f"Chờ làm {ten} ở {o['phong'] or 'phòng'}")
            elif ex == "INTERRUPTED":
                out.append(f"Dừng giữa chừng: {ten}")
            elif ex == "COMPLETED" and o["ngoai"] and o["ket_qua_luc"] is None:
                out.append(f"Chờ kết quả đối tác: {ten}")
    if tep_chua_xem:
        out.append(f"{tep_chua_xem} tệp kết quả chưa bác sĩ nào xem")
    if phieu_chua_xem:
        out.append(f"{phieu_chua_xem} phiếu kết quả chưa bác sĩ nào xem")
    return out


class BangHanhTrinhService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def hom_nay(self, *, identity: StaffIdentity) -> dict[str, Any]:
        if not identity.co_vai(GOI_DUOC):
            raise SafetyGateError("Vai của bạn không xem bảng hành trình.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            luot = [
                dict(r)
                for r in await conn.fetch(
                    """
                    SELECT v.visit_id::text AS visit_id, v.status, v.closed_at,
                           v.checked_in_at, p.full_name, p.patient_code,
                           a.so_booking, a.so_tiep_don, st.name AS loai_kham,
                           d.full_name AS bac_si
                      FROM visit v
                      JOIN patient p
                        ON p.clinic_patient_id = v.clinic_patient_id
                       AND p.clinic_id = v.clinic_id
                      LEFT JOIN appointment a
                        ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
                      LEFT JOIN service_type st ON st.id = v.service_type_id
                      LEFT JOIN staff d ON d.id = v.attending_doctor_id
                     WHERE v.clinic_id = $1::uuid AND v.created_at >= $2
                     -- Khách CÒN ở phòng khám trước, người mới tới trước: có
                     -- cắt ở trần thì cắt những lượt đã về lâu nhất.
                     ORDER BY (v.closed_at IS NOT NULL), v.created_at DESC
                     LIMIT $3
                    """,
                    cid,
                    _dau_ngay(),
                    _TRAN_LUOT,
                )
            ]
            ids = [x["visit_id"] for x in luot]
            hang: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for r in await conn.fetch(
                """
                SELECT q.visit_id::text AS visit_id, q.lane, q.status,
                       r.name AS phong, d.full_name AS bac_si
                  FROM queue_entry q
                  LEFT JOIN clinic_room r ON r.id = q.room_id
                  LEFT JOIN staff d ON d.id = q.doctor_staff_id
                 WHERE q.clinic_id = $1::uuid AND q.visit_id = ANY($2::uuid[])
                   AND q.status IN ('blocked', 'waiting', 'called', 'serving')
                 ORDER BY q.eligible_at NULLS LAST, q.created_at
                """,
                cid,
                ids,
            ):
                hang[r["visit_id"]].append(dict(r))
            chi_dinh: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for r in await conn.fetch(
                """
                SELECT o.visit_id::text AS visit_id, o.service_name AS ten,
                       o.selection_status, o.routing_status, o.execution_status,
                       o.ket_qua_luc, r.name AS phong,
                       coalesce(n.lam_ben_ngoai, false) AS ngoai,
                       EXISTS (
                           SELECT 1 FROM payment_bill_line bl
                             JOIN payment_cycle c
                               ON c.clinic_id = bl.clinic_id
                              AND c.payment_cycle_id = bl.payment_cycle_id
                            WHERE bl.clinic_id = o.clinic_id
                              AND bl.source_type = 'service_order'
                              AND bl.source_id = o.id::text
                              AND c.status = 'PAID') AS da_tra
                  FROM service_order o
                  LEFT JOIN clinic_room r ON r.id = o.room_id
                  LEFT JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                 WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
                   AND o.exec_status NOT IN ('draft', 'cancelled')
                 ORDER BY o.created_at
                """,
                cid,
                ids,
            ):
                chi_dinh[r["visit_id"]].append(dict(r))
            tep = {
                r["visit_id"]: int(r["so"])
                for r in await conn.fetch(
                    """
                    SELECT o.visit_id::text AS visit_id, count(*) AS so
                      FROM tep_ket_qua t
                      JOIN service_order o
                        ON o.id = t.service_order_id AND o.clinic_id = t.clinic_id
                     WHERE t.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
                       AND t.da_xem_luc IS NULL
                       AND coalesce(t.xac_nhan_trang_thai, 'HOP_LE') = 'HOP_LE'
                     GROUP BY o.visit_id
                    """,
                    cid,
                    ids,
                )
            }
            phieu = {
                r["visit_id"]: int(r["so"])
                for r in await conn.fetch(
                    """
                    SELECT o.visit_id::text AS visit_id, count(DISTINCT o.id) AS so
                      FROM service_order o
                      JOIN form_instance f
                        ON f.service_order_id = o.id AND f.clinic_id = o.clinic_id
                     WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
                       AND f.trang_thai = 'READY' AND o.da_xem_ket_qua_luc IS NULL
                     GROUP BY o.visit_id
                    """,
                    cid,
                    ids,
                )
            }
            xong: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for r in await conn.fetch(
                """
                SELECT visit_id::text AS visit_id, nhan, occurred_at
                  FROM (
                    SELECT d.*, row_number() OVER (
                             PARTITION BY d.visit_id
                             ORDER BY d.occurred_at DESC, d.thu_tu DESC) AS hang
                      FROM luot_dong_thoi_gian d
                     WHERE d.clinic_id = $1::uuid AND d.visit_id = ANY($2::uuid[])
                  ) x
                 WHERE hang <= $3
                 ORDER BY occurred_at
                """,
                cid,
                ids,
                _SO_VIEC_XONG,
            ):
                xong[r["visit_id"]].append(
                    {"nhan": r["nhan"], "luc": r["occurred_at"].isoformat()}
                )
        return {
            "luot": [
                {
                    "visit_id": x["visit_id"],
                    "ten": x["full_name"],
                    "ma": x["patient_code"],
                    "so_booking": x["so_booking"],
                    "so_quay": x["so_tiep_don"],
                    "loai_kham": x["loai_kham"],
                    "bac_si": x["bac_si"],
                    "check_in_luc": x["checked_in_at"].isoformat()
                    if x["checked_in_at"]
                    else None,
                    "dang_o": dang_o(x, hang[x["visit_id"]]),
                    "da_xong": xong[x["visit_id"]],
                    "con_cho": con_cho(
                        hang[x["visit_id"]],
                        chi_dinh[x["visit_id"]],
                        tep.get(x["visit_id"], 0),
                        phieu.get(x["visit_id"], 0),
                    ),
                    "da_ve": x["closed_at"] is not None,
                }
                for x in luot
            ],
            "bi_cat": len(luot) >= _TRAN_LUOT,
        }


__all__ = ["BangHanhTrinhService", "con_cho", "dang_o"]
