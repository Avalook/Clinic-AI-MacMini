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
from datetime import date, datetime, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import finance_gate
from clinicai.services.xem_luot_service import goi_duoc

_TRAN_LUOT = 300
_SO_VIEC_XONG = 6


def _dau_ngay(ngay: date | None = None) -> datetime:
    if ngay is None:
        return datetime.now(CLINIC_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    return datetime(ngay.year, ngay.month, ngay.day, tzinfo=CLINIC_TZ)


def doc_ngay_xem(chuoi: str | None) -> date | None:
    """ "YYYY-MM-DD" → ngày; rác / rỗng → None = hôm nay (không ném — luật ngày
    giờ từ người dùng, CLAUDE.md)."""
    try:
        return date.fromisoformat((chuoi or "").strip())
    except ValueError:
        return None


def noi_hang(q: dict[str, Any]) -> str:
    """Tên chỗ của một dòng hàng chờ — dùng chung cho Hành trình và Tiếp đón."""
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
        return "Đang ở " + noi_hang(dang[0])
    cho = [q for q in hang if q["status"] == "waiting"]
    if cho:
        return "Chờ " + ", ".join(dict.fromkeys(noi_hang(q) for q in cho))
    doi = [q for q in hang if q["status"] == "blocked"]
    if doi:
        return "Đợi (" + ", ".join(dict.fromkeys(noi_hang(q) for q in doi)) + ")"
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
            out.append("Chờ " + noi_hang(q))
    for o in chi_dinh:
        ten = o["ten"]
        if o["selection_status"] == "PENDING":
            out.append(f"Chờ khách chọn làm: {ten}")
        elif o["selection_status"] == "SELECTED":
            ex = o["execution_status"] or "PENDING"
            if ex == "PENDING" and o["routing_status"] in (None, "UNASSIGNED"):
                # Đã chốt mà chưa có phòng = TRÁCH NHIỆM đang rơi (người chốt /
                # người thu không có quyền điều phối, hoặc dây tự xếp đang tắt)
                # — nói thẳng. V10 làm trước, thu sau: chưa trả KHÔNG phải lý do
                # chờ; chỉ ghi kèm "chưa thu" để quầy biết.
                # Dây "thu trước khi làm" BẬT (30/09/2026 tối) mà lượt không tick
                # "Làm trước – thu sau": chưa thu thì chưa xếp được — việc đang
                # chờ là TRẢ TIỀN (`duoc_lam` = cửa làm của FinanceGate).
                out.append(
                    f"ĐÃ TRẢ TIỀN — chờ xếp phòng: {ten}"
                    if o.get("da_tra")
                    else f"Chờ trả tiền: {ten}"
                    if o.get("duoc_lam") is False
                    else f"Chờ xếp phòng (chưa thu): {ten}"
                )
            elif ex == "PENDING" and o["routing_status"] == "REASSIGNMENT_REQUIRED":
                out.append(f"Cần xếp lại phòng: {ten}")
            elif ex == "PENDING":
                out.append(f"Chờ làm {ten} ở {o['phong'] or 'phòng'}")
            elif ex == "INTERRUPTED":
                out.append(f"Dừng giữa chừng: {ten}")
            elif (
                ex == "COMPLETED"
                and o["ngoai"]
                and o["ket_qua_luc"] is None
                and o.get("nhan_mau_luc") is None
            ):
                # Đối tác NHẬN MẪU là xong (Tuyền 29/09/2026) — chỉ còn chờ
                # đối tác nhận mẫu mới là việc dở.
                out.append(f"Chờ đối tác nhận mẫu: {ten}")
    if tep_chua_xem:
        out.append(f"{tep_chua_xem} tệp kết quả chưa bác sĩ nào xem")
    if phieu_chua_xem:
        out.append(f"{phieu_chua_xem} phiếu kết quả chưa bác sĩ nào xem")
    return out


class BangHanhTrinhService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def hom_nay(
        self, *, identity: StaffIdentity, ngay: str | None = None
    ) -> dict[str, Any]:
        """Bảng hành trình của MỘT ngày — mặc định hôm nay; ``ngay`` (YYYY-MM-DD)
        xem lại hôm qua, các hôm khác (Tuyền 30/09/2026)."""
        if not goi_duoc(identity):
            raise SafetyGateError("Tài khoản của bạn không xem bảng hành trình.")
        cid = identity.clinic_id
        tu = _dau_ngay(doc_ngay_xem(ngay))
        den = tu + timedelta(days=1)
        async with self._pool.acquire() as conn:
            luot = [
                dict(r)
                for r in await conn.fetch(
                    """
                    SELECT v.visit_id::text AS visit_id, v.status, v.closed_at,
                           v.checked_in_at, p.full_name, p.patient_code,
                           a.so_booking, a.so_tiep_don, st.name AS loai_kham,
                           a.created_at AS dat_luc,
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
                       AND v.created_at < $4
                       -- V8: lượt bán lẻ (chỉ mua thuốc) không có hành trình.
                       AND NOT v.ban_le
                     -- Khách CÒN ở phòng khám trước, người mới tới trước: có
                     -- cắt ở trần thì cắt những lượt đã về lâu nhất.
                     ORDER BY (v.closed_at IS NOT NULL), v.created_at DESC
                     LIMIT $3
                    """,
                    cid,
                    tu,
                    _TRAN_LUOT,
                    den,
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
                SELECT o.id::text AS id, o.visit_id::text AS visit_id,
                       o.service_name AS ten,
                       o.selection_status, o.routing_status, o.execution_status,
                       o.ket_qua_luc, r.name AS phong,
                       o.doi_tac_cho_tai_lieu_luc AS nhan_mau_luc,
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
            cua = await finance_gate.states_for_orders(
                conn, cid, [o["id"] for ds in chi_dinh.values() for o in ds]
            )
            for ds in chi_dinh.values():
                for o in ds:
                    q = cua.get(o["id"])
                    o["duoc_lam"] = q.duoc_lam if q is not None else None
            tep = {
                r["visit_id"]: int(r["so"])
                for r in await conn.fetch(
                    """
                    SELECT o.visit_id::text AS visit_id, count(*) AS so
                      FROM v_tep_ket_qua_hieu_luc t
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
            # HÀNH TRÌNH KHÁCH dạng gọn (Tuyền chốt 29/09/2026) — thay dải mốc
            # 28/09: đang ở / đang chờ PHÒNG nào, thanh đoạn màu, x/y dịch vụ
            # xong. Cùng hàm với trang chủ + khung đầy đủ. Nhập muộn vì
            # phieu_kham.hanh_trinh nhập `dang_o` từ đây.
            from clinicai.services.hanh_trinh_khach_service import (
                doc_hanh_trinh_khach,
            )

            htk = await doc_hanh_trinh_khach(conn, clinic_id=cid, visit_ids=ids)
        return {
            # Ngày máy chủ ĐÃ dùng (ngày rác → hôm nay) để màn hiện đúng.
            "ngay": tu.date().isoformat(),
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
                    "gon": htk[x["visit_id"]]["gon"] if x["visit_id"] in htk else None,
                }
                for x in luot
            ],
            "bi_cat": len(luot) >= _TRAN_LUOT,
        }


__all__ = ["BangHanhTrinhService", "con_cho", "dang_o", "noi_hang"]
