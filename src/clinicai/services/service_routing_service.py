"""Service Lifecycle v1 — Routing chính thức (Slice 4).

Contract: docs/ai/lifecycle-v1/ClinicAI-ROUTING-v1.md (frozen).

Ba thứ tách rời:
  * ``eligible_rooms`` — tập phòng ĐỦ ĐIỀU KIỆN của một node, kèm tải hàng chờ
    và tín hiệu lịch trực, trong MỘT truy vấn;
  * ``rank_rooms`` (RuleBasedRoomAdvisor) — xếp hạng thuần, KHÔNG ghi gì;
  * ``ServiceRoutingService.assign / invalidate`` — lệnh DUY NHẤT đổi trạng thái
    routing. Gợi ý (của luật hay của AI sau này) chỉ là gợi ý: lệnh đọc lại và
    kiểm lại mọi điều kiện trong giao dịch.

Thứ tự khoá (ROUTING §7): lượt → biên nhận → service_order → revision →
selection + FinanceGate + hold → phòng → hàng chờ → trạng thái routing → sự
kiện → biên nhận. Cùng "lượt trước" với Selection / Payment / Execution.

OPEN, không tự chốt ở đây:
  * sinh hiệu có chặn điều phối không → seam ``luot_kham_rules.vitals_routing_block``;
  * ánh xạ vai → capability → ``can_route_*`` bên dưới;
  * có người trực là chốt cứng hay chỉ tín hiệu → ở v1 CHỈ là tín hiệu xếp hạng.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity, danh_tinh_nhan_vien
from clinicai.events.catalogue import DaXepPhong, DichVuDaChuyenPhong, XepPhongDaHuy
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.services import finance_gate
from clinicai.services import luot_kham_rules as rules
from clinicai.services.audit import record_event
from clinicai.services.day_noi import doc_day
from clinicai.services.hang_cho import (
    cap_nhat_vi_tri,
    khach_dang_duoc_phuc_vu,
    mo_cho_bi_chan,
)
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    LuotKhamValidationError,
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_flow,
    khoa_luot,
    luot_cua,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

ORIGIN = "api:service-routing"
ACTION_ASSIGN = "service_routing.assign"
ACTION_INVALIDATE = "service_routing.invalidate"
ACTION_TRANSFER = "service_routing.transfer_in_progress"
EVENT_ROUTED = "service.routed"
EVENT_INVALIDATED = "service.routing_invalidated"
EVENT_TRANSFERRED = "service.room_transferred"
ADVISOR = "rule-v1"

UNASSIGNED = "UNASSIGNED"
ASSIGNED = "ASSIGNED"
REASSIGNMENT_REQUIRED = "REASSIGNMENT_REQUIRED"

ASSIGN_REASONS = frozenset(
    {
        "INITIAL_ASSIGNMENT",
        "LOAD_BALANCE",
        "ROOM_UNAVAILABLE",
        "STAFF_UNAVAILABLE",
        "EQUIPMENT_FAILURE",
        "PATIENT_NEED",
        "MANUAL_CORRECTION",
        "OTHER",
    }
)

# NGUỒN của lần xếp (Tuyền 25/09/2026, migration 20260925000016) — để LỊCH SỬ nói
# "ai đổi, từ màn nào". 29/09/2026 (Tuyền): BỎ luật "trưởng ca đã xếp thì quầy
# thu không đổi được" — quầy vẫn đổi được, mọi lần đổi hiện ở Hành trình khách.
# Khi CHƯA xếp, `routing_nguon` = nguồn đặt PHÒNG DỰ KIẾN (quầy thu / trưởng ca);
# dây H4 xếp đúng phòng ấy thì sự kiện ghi `du_kien_nguon`.
NGUON_QUAY_THU = "quay_thu"
NGUON_TRUONG_CA = "truong_ca"
NGUON_TU_DONG = "tu_dong"
NGUON_KHAC = "khac"
NGUON_TU_NGUOI = frozenset({NGUON_QUAY_THU, NGUON_TRUONG_CA, NGUON_KHAC})
#: Nguồn → quyền của lego gọi lệnh (ngoài quyền xếp phòng chung).
QUYEN_THEO_NGUON = {
    NGUON_QUAY_THU: "payment.service.collect",
    NGUON_TRUONG_CA: "dispatch.manage",
}
INVALIDATE_REASONS = frozenset(
    {
        "ROOM_UNAVAILABLE",
        "STAFF_UNAVAILABLE",
        "EQUIPMENT_FAILURE",
        "CONFIG_CHANGED",
        "OTHER",
    }
)

#: Trục thực hiện: đã bắt đầu → không điều phối thường; đã kết thúc → không điều
#: phối nữa. INTERRUPTED không phải kết thúc (EXECUTION §2) — xếp lại phòng là
#: một bước của luồng thử lại.
_DANG_LAM = frozenset({"IN_PROGRESS"})
_KET_THUC = frozenset({"COMPLETED", "CANCELLED", "NOT_PERFORMED"})
_DANG_LAM_CU = frozenset({"in_progress"})
_KET_THUC_CU = frozenset({"performed", "not_performed", "cancelled"})


# ---------------------------------------------------------------------------
# Quyền — capability seam (ánh xạ vai cuối cùng còn OPEN)
# ---------------------------------------------------------------------------


#: Ba quyền riêng trong MỘT khối "Điều phối khách": quản lý bật cả khối, còn
#: tầng kỹ thuật vẫn tách được "xem gợi ý" khỏi "xếp phòng" khi cần siết.
QUYEN_XEM = "service.routing.view"
QUYEN_XEP = "service.routing.assign"
QUYEN_HUY = "service.routing.invalidate"


async def can_route_recommend(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> bool:
    return await can(conn, identity, QUYEN_XEM)


async def can_route_assign(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    return await can(conn, identity, QUYEN_XEP)


async def can_route_invalidate(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> bool:
    return await can(conn, identity, QUYEN_HUY)


# ---------------------------------------------------------------------------
# EligibleRoomQuery + RuleBasedRoomAdvisor
# ---------------------------------------------------------------------------

#: MỘT truy vấn: phòng cùng phòng khám, đang mở, đang nhận khách, làm được chỉ
#: định (node + dịch vụ) — kèm tải hàng chờ sống và tín hiệu "hôm nay có người
#: trực ở phòng". Tải và lịch trực là TÍN HIỆU xếp hạng, không phải điều kiện.
#:
#: "Làm được" = hàm Postgres ``phong_lam_duoc`` (30/09/2026): dịch vụ có gắn phòng
#: ở ``clinic_room_service`` thì CHỈ các phòng ấy; không gắn thì theo node như
#: cũ. Mọi chỗ tính "phòng làm được chỉ định này" gọi đúng hàm ấy.
_ELIGIBLE_SQL = """
SELECT r.id::text AS room_id, r.code, r.sort,
       EXISTS (
           SELECT 1 FROM work_roster w
             JOIN vi_tri_lam_viec v
               ON v.clinic_id = w.clinic_id AND v.code = w.station
            WHERE w.clinic_id = r.clinic_id AND v.room_id = r.id
              AND w.status <> 'REJECTED'
              AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
       ) AS co_nguoi_truc,
       -- SỐ NGƯỜI THẬT (Tuyền 24/09/2026: "số người đang chờ phải là số người
       -- thực tế đã được chỉ định"): mỗi khách một lần, chỉ lượt check-in HÔM
       -- NAY (lượt bỏ dở hôm trước không tính), và KHÔNG tính chính khách đang
       -- được xếp ($4) — trước đây khách thấy mình trong "1 đang chờ".
       (SELECT count(DISTINCT q.visit_id) FROM queue_entry q
          JOIN visit vq ON vq.visit_id = q.visit_id AND vq.clinic_id = q.clinic_id
         WHERE q.clinic_id = r.clinic_id AND q.room_id = r.id
           AND q.status IN ('blocked', 'waiting', 'called', 'serving')
           AND (vq.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           AND ($4::uuid IS NULL OR q.visit_id <> $4::uuid))::int AS tai
  FROM clinic_room r
 WHERE r.clinic_id = $1::uuid
   AND phong_lam_duoc(r.clinic_id, r.id, $2, $5)
   AND r.is_active AND r.accepting AND NOT r.la_doi_tac
   -- CÙNG CƠ SỞ với lượt khám (24/09/2026): phòng khám có nhiều cơ sở thì
   -- khách ở Kim Ngưu không được xếp sang phòng Hào Nam. Trước đây câu này
   -- không lọc cơ sở — bộ mô phỏng ngày khám bắt được một xét nghiệm máu bị xếp
   -- sang phòng lấy mẫu của cơ sở khác.
   AND ($3::uuid IS NULL OR r.location_id = $3::uuid)
"""


def phong_lam_duoc_sql(phong: str = "r", cd: str = "o") -> str:
    """Mẩu SQL dùng chung: phòng alias ``phong`` làm được chỉ định alias ``cd``
    (service_order) không. Chỉ là lời gọi hàm Postgres — luật ở MỘT chỗ."""
    return (
        f"phong_lam_duoc({phong}.clinic_id, {phong}.id,"
        f" {cd}.node_code, {cd}.service_code)"
    )


def cau_phong_khong_lam(ten_dich_vu: str | None, phong_lam: Sequence[str]) -> str:
    """Câu từ chối khi xếp vào phòng không làm dịch vụ — HÀM THUẦN.

    ``phong_lam`` = các phòng dịch vụ được GẮN riêng (rỗng = dịch vụ không thu
    hẹp, luật node: câu cũ)."""
    ten = ten_dich_vu.strip() if isinstance(ten_dich_vu, str) else ""
    ten = ten or "này"
    if not phong_lam:
        return f"Phòng này không làm dịch vụ {ten}."
    return (
        f"Phòng này không làm dịch vụ {ten} — dịch vụ chỉ làm ở: "
        f"{', '.join(phong_lam)}."
    )


async def phong_gan_dich_vu(
    conn: asyncpg.Connection, clinic_id: str, service_code: str | None
) -> list[str]:
    """Tên các phòng đang BẬT được gắn riêng dịch vụ này (rỗng = không thu hẹp)."""
    if not service_code:
        return []
    return [
        str(r["ten"])
        for r in await conn.fetch(
            "SELECT coalesce(r.name, r.code) AS ten FROM clinic_room_service s"
            " JOIN clinic_room r ON r.id = s.room_id AND r.clinic_id = s.clinic_id"
            " WHERE s.clinic_id = $1::uuid AND s.service_code = $2 AND r.is_active"
            " ORDER BY r.sort, r.code",
            clinic_id,
            service_code,
        )
    ]


async def co_so_cua_luot(
    conn: asyncpg.Connection,
    clinic_id: str,
    *,
    visit_id: str | None = None,
    order_id: str | None = None,
) -> str | None:
    """Cơ sở (clinic_location) nơi khách đang khám — theo lượt hoặc theo chỉ định.

    `visit.location_id` chỉ được ghi từ 24/09/2026; lượt cũ rơi về cơ sở của
    lịch hẹn."""
    if order_id is not None:
        v = await conn.fetchval(
            "SELECT coalesce(v.location_id, a.location_id)::text"
            " FROM service_order o JOIN visit v"
            " ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id"
            " LEFT JOIN appointment a"
            " ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id"
            " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid",
            clinic_id,
            order_id,
        )
        return str(v) if v else None
    if visit_id is not None:
        v = await conn.fetchval(
            "SELECT coalesce(v.location_id, a.location_id)::text FROM visit v"
            " LEFT JOIN appointment a"
            " ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id"
            " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
            clinic_id,
            visit_id,
        )
        return str(v) if v else None
    return None


@dataclass(frozen=True)
class RoomCandidate:
    room_id: str
    code: str
    sort: int
    co_nguoi_truc: bool
    tai: int


async def eligible_rooms(
    conn: asyncpg.Connection,
    clinic_id: str,
    node_code: str,
    location_id: str | None = None,
    tru_luot: str | None = None,
    service_code: str | None = None,
) -> list[RoomCandidate]:
    """EligibleRoomQuery — tập phòng hợp lệ của một chỉ định, một truy vấn.

    `service_code` = dịch vụ của chỉ định: dịch vụ gắn phòng riêng thì chỉ các
    phòng ấy (None = chỉ xét node). `location_id` = cơ sở của lượt khám; truyền
    vào thì chỉ lấy phòng cùng cơ sở (None = không lọc — chỉ dùng cho màn cấu
    hình). `tru_luot` = lượt của khách đang được xếp: không đếm chính họ vào số
    người chờ.

    Tầng sau (chọn BÁC SĨ trong phòng nhiều bác sĩ) lọc / xếp tiếp trên chính
    tập này — không tự tính lại "phòng nào làm được"."""
    return [
        RoomCandidate(
            room_id=r["room_id"],
            code=r["code"],
            sort=int(r["sort"]),
            co_nguoi_truc=bool(r["co_nguoi_truc"]),
            tai=int(r["tai"]),
        )
        for r in await conn.fetch(
            _ELIGIBLE_SQL, clinic_id, node_code, location_id, tru_luot, service_code
        )
    ]


def rank_rooms(rooms: Sequence[RoomCandidate]) -> list[dict[str, Any]]:
    """RuleBasedRoomAdvisor — hàm thuần, chỉ xếp hạng TRONG tập đủ điều kiện.

    Cùng luật của ``_tu_xep_phong`` cũ: có người trực hôm nay trước, rồi phòng ít
    người chờ nhất, rồi thứ tự cấu hình. Không có người trực vẫn được gợi ý —
    lịch trực chỉ là tín hiệu.
    """
    xep = sorted(rooms, key=lambda r: (not r.co_nguoi_truc, r.tai, r.sort, r.code))
    it_nhat = min((r.tai for r in rooms), default=0)
    out: list[dict[str, Any]] = []
    for i, r in enumerate(xep, start=1):
        ly_do = ["STAFF_ON_SHIFT" if r.co_nguoi_truc else "NO_ROSTER_SIGNAL"]
        if r.tai == it_nhat:
            ly_do.append("LOWEST_QUEUE")
        out.append(
            {
                "room_id": r.room_id,
                "rank": i,
                "reason_codes": ly_do,
                "queue_load": r.tai,
                "confidence": None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Đọc: chỉ định KHÁCH ĐÃ CHỐT chờ vào phòng (Tuyền 24/09/2026; V10 30/09/2026)
# ---------------------------------------------------------------------------
#
# "Thanh toán xong vẫn chỉ định [phòng] được bình thường" + "kể cả lễ tân không
# chỉ định thì khách vẫn xuất hiện ở hàng đợi và có thể khám ở các dịch vụ khả
# thi". Hai câu đọc dưới cùng MỘT điều kiện "khách chốt làm, chưa bắt đầu" —
# V10 (làm trước, thu sau): KHÔNG còn đòi đã trả tiền; xếp / đổi phòng vẫn đi
# qua lệnh `assign` (quyền, cửa `duoc_lam`, revision, cơ sở).

#: ĐỐI TÁC LÀM TRỌN (alias ``o`` = service_order) — khách KHÔNG vào phòng nào
#: của phòng khám, nên không có gì để xếp:
#:   * dịch vụ đánh dấu đối tác tự lấy mẫu / tự làm (`doi_tac_lay_mau`); hoặc
#:   * bước làm bên ngoài (`node_definition.lam_ben_ngoai`) mà KHÔNG phòng nội bộ
#:     nào của phòng khám làm bước ấy — chụp phim DICHVU-HINHANH-NGOAI trên prod
#:     (Kim Ngưu 12 phòng phủ mọi bước trừ bước này).
#: Bước làm bên ngoài CÓ phòng nội bộ (lấy máu, lấy dịch — điều dưỡng lấy mẫu ở
#: phòng Lấy mẫu rồi gửi đối tác) vẫn xếp phòng như thường.
#: 27/09/2026 (đợt 3): trước đây chỉ xét cờ dịch vụ — chụp phim cờ tắt thì quầy
#: hiện "Chưa có phòng nào làm được dịch vụ này" và dây H4 bỏ qua im lặng.
DOI_TAC_LAM_TRON_SQL = """(
       EXISTS (
           SELECT 1 FROM service_price sp
            WHERE sp.clinic_id = o.clinic_id AND sp.service_code = o.service_code
              AND sp.doi_tac_lay_mau)
    OR (EXISTS (
           SELECT 1 FROM node_definition nd
            WHERE nd.clinic_id = o.clinic_id AND nd.code = o.node_code
              AND nd.lam_ben_ngoai)
        AND NOT EXISTS (
           SELECT 1 FROM clinic_room r2
            WHERE r2.clinic_id = o.clinic_id
              AND r2.is_active AND NOT r2.la_doi_tac
              AND phong_lam_duoc(r2.clinic_id, r2.id, o.node_code, o.service_code)))
)"""

#: Khoá nội bộ của ``da_tra_cho_vao_phong`` — dùng tính phòng chọn được, bỏ
#: trước khi trả màn.
KHOA_NOI_BO = frozenset({"node_code", "service_code"})

#: Câu cho chỉ định đối tác làm trọn — màn vẽ nguyên câu này, không tự đặt.
CAU_DOI_TAC_LAM = "Đối tác làm — không cần xếp phòng."

#: Trạng thái gợi ý phòng (``recommend.trang_thai``) — màn chỉ bày ô chọn phòng
#: khi ``CO_PHONG``.
GOI_Y_CO_PHONG = "CO_PHONG"
GOI_Y_DOI_TAC_LAM = "DOI_TAC_LAM"
GOI_Y_KHONG_CO_PHONG = "KHONG_CO_PHONG"
CAU_KHONG_CO_PHONG = (
    "Chưa có phòng nào đang nhận khách làm được dịch vụ này ở cơ sở này (phòng có"
    " thể đang tạm ngừng). Việc cần làm: báo trưởng ca mở lại phòng, hoặc quản lý"
    " gán phòng ở Cấu trúc phòng khám."
)


async def doi_tac_lam_tron(
    conn: asyncpg.Connection, clinic_id: str, order_ids: Sequence[str]
) -> set[str]:
    """Trong các chỉ định này, cái nào ĐỐI TÁC LÀM TRỌN (không cần xếp phòng)."""
    if not order_ids:
        return set()
    return {
        str(r["id"])
        for r in await conn.fetch(
            f"SELECT o.id::text AS id FROM service_order o"
            f" WHERE o.clinic_id = $1::uuid AND o.id = ANY($2::uuid[])"
            f" AND {DOI_TAC_LAM_TRON_SQL}",
            clinic_id,
            list(order_ids),
        )
    }


# ── Chờ xếp phòng (dây H4 không xếp được) ──────────────────────────────────
#
# Trước 27/09/2026 H4 bỏ qua IM LẶNG khi không có phòng: khách đã chốt / đã trả
# mà không ai biết phải xếp tay. Nay mỗi lần như vậy réo chuông quầy (cùng cơ chế
# chuông vai của H8 "nhắc check-out") — mỗi chỉ định một chuông đang mở.

CHO_XEP_KHONG_CO_PHONG = "KHONG_CO_PHONG"
CHO_XEP_CHUA_CHON_PHONG = "CHUA_CHON_PHONG"
CHO_XEP_PHONG_DU_KIEN_HONG = "PHONG_DU_KIEN_KHONG_NHAN"
#: Vai nhận chuông "chờ xếp phòng": người đứng quầy (lễ tân kiêm thu ngân).
VAI_NHAN_CHO_XEP = ("RECEPTION", "CASHIER")

_CAU_CHO_XEP: dict[str, str] = {
    CHO_XEP_KHONG_CO_PHONG: (
        "Không phòng nào đang nhận khách làm được dịch vụ này (phòng có thể đang"
        " tạm ngừng). Việc cần làm: báo trưởng ca mở lại phòng, rồi xếp phòng ở"
        ' ô "Phòng làm dịch vụ (khách đã chốt)".'
    ),
    CHO_XEP_CHUA_CHON_PHONG: (
        'Dây "chỉ áp phòng lễ tân chọn" đang bật mà dịch vụ này chưa chọn phòng.'
        ' Việc cần làm: chọn phòng ở ô "Phòng làm dịch vụ (khách đã chốt)".'
    ),
    CHO_XEP_PHONG_DU_KIEN_HONG: (
        "Phòng lễ tân chọn đang tạm ngừng hoặc không làm được bước này. Việc cần"
        ' làm: chọn phòng khác ở ô "Phòng làm dịch vụ (khách đã chốt)".'
    ),
}


def cau_cho_xep_phong(ly_do: str | None) -> str:
    """Câu cho chuông "chờ xếp phòng" theo lý do. Hàm thuần; lý do lạ vẫn có câu."""
    if isinstance(ly_do, str) and ly_do in _CAU_CHO_XEP:
        return _CAU_CHO_XEP[ly_do]
    return (
        "Khách đã chốt dịch vụ nhưng chưa được xếp phòng. Việc cần làm: xếp phòng tay."
    )


def chon_phong_h4(
    ung_vien: Sequence[dict[str, Any]],
    phong_du_kien: str | None,
    *,
    chi_ap_phong_du_kien: bool,
) -> tuple[str | None, str | None]:
    """Dây H4 chọn phòng nào — HÀM THUẦN. Trả ``(room_id, None)`` hoặc
    ``(None, lý do chờ xếp)``.

    Mặc định: phòng lễ tân chọn (`phong_du_kien`) thắng nếu còn đủ điều kiện,
    không thì phòng vắng nhất. Dây ``h4_chi_ap_phong_du_kien`` BẬT: CHỈ áp phòng
    lễ tân chọn — không tự chọn phòng vắng nhất; chưa chọn / phòng ấy không còn
    nhận thì để chờ lễ tân xếp.
    """
    khop = next((u for u in ung_vien if u.get("room_id") == phong_du_kien), None)
    if chi_ap_phong_du_kien:
        if khop is not None:
            return str(khop["room_id"]), None
        if not phong_du_kien:
            return None, CHO_XEP_CHUA_CHON_PHONG
        return None, CHO_XEP_PHONG_DU_KIEN_HONG
    if khop is not None:
        return str(khop["room_id"]), None
    if ung_vien:
        return str(ung_vien[0]["room_id"]), None
    return None, CHO_XEP_KHONG_CO_PHONG


#: Khách đã chốt làm, chưa bắt đầu — tên cũ "đã trả" giữ cho khỏi đổi khắp nơi;
#: tiền không còn là điều kiện (V10), lọc bằng cửa ``duoc_lam`` ở ``_loc_da_tra``.
_DA_TRA_CHUA_LAM = f"""
       o.selection_status = 'SELECTED'
   AND o.exec_status IN ('authorized', 'assigned')
   AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
   AND v.status IN ('OPEN', 'IN_PROGRESS')
   -- Đối tác làm trọn: khách không vào phòng nào của phòng khám.
   AND NOT {DOI_TAC_LAM_TRON_SQL}
   -- Phòng đã gọi / đang làm thì không đổi được nữa (lệnh cũng từ chối).
   AND NOT EXISTS (
       SELECT 1 FROM queue_entry q
        WHERE q.clinic_id = o.clinic_id AND q.reason = 'SERVICE'
          AND q.ref_id = o.id AND q.status IN ('called', 'serving'))
"""


async def _loc_da_tra(
    conn: asyncpg.Connection, clinic_id: str, rows: Sequence[asyncpg.Record]
) -> list[asyncpg.Record]:
    tai_chinh = await finance_gate.states_for_orders(
        conn, clinic_id, [r["id"] for r in rows]
    )
    # V10 làm trước, thu sau: chưa thu vẫn vào — chỉ bỏ chỉ định tiền đang
    # hoàn / đã hoàn / sổ lệch (``finance_gate.CHO_LAM_STATES``).
    return [r for r in rows if (q := tai_chinh.get(r["id"])) is not None and q.duoc_lam]


async def da_tra_cho_vao_phong(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Quầy thu: theo lượt, chỉ định khách đã chốt chưa bắt đầu + phòng hiện tại
    — để lễ tân xếp / đổi phòng sau khi chốt / sau khi thu (trước: thu xong là
    mất chỗ chọn). V10: chưa thu vẫn có mặt."""
    if not visit_ids:
        return {}
    rows = await conn.fetch(
        f"""
        SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_name,
               o.routing_revision, o.room_id::text AS room_id, r.name AS phong,
               coalesce(o.routing_status, 'UNASSIGNED') AS routing_status,
               o.routing_nguon, o.node_code, o.service_code
          FROM service_order o
          JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
          LEFT JOIN clinic_room r ON r.id = o.room_id AND r.clinic_id = o.clinic_id
         WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
           AND {_DA_TRA_CHUA_LAM}
         ORDER BY o.created_at, o.id
        """,
        clinic_id,
        visit_ids,
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for r in await _loc_da_tra(conn, clinic_id, rows):
        out.setdefault(r["visit_id"], []).append(
            {
                "id": r["id"],
                "ten": r["service_name"],
                "room_id": r["room_id"] if r["routing_status"] == ASSIGNED else None,
                "phong": r["phong"] if r["routing_status"] == ASSIGNED else None,
                "routing_revision": int(r["routing_revision"]),
                # Quầy thu tính phòng chọn được theo bước + dịch vụ này
                # (27/09, 30/09/2026) — hai khoá nội bộ, bỏ trước khi trả màn
                # (``KHOA_NOI_BO``).
                "node_code": r["node_code"],
                "service_code": r["service_code"],
            }
        )
    return out


async def cho_nhan_vao_phong(
    conn: asyncpg.Connection, clinic_id: str, room_id: str
) -> list[dict[str, Any]]:
    """Phòng: khách ĐÃ CHỐT (đã trả hay chưa — V10) mà CHƯA XẾP PHÒNG, phòng này
    làm được, cùng cơ sở —
    hiện ở MỌI phòng như vậy để phòng nào rảnh bấm nhận (không để khách kẹt khi
    người thu không xếp, hay dây H4 không tự xếp được)."""
    rows = await conn.fetch(
        f"""
        SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_name,
               o.routing_revision, p.full_name, p.patient_code,
               v.checked_in_at
          FROM clinic_room pr
          JOIN service_order o
            ON o.clinic_id = pr.clinic_id
           AND {phong_lam_duoc_sql("pr", "o")}
          JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
          JOIN patient p ON p.clinic_patient_id = v.clinic_patient_id
          LEFT JOIN appointment a
            ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
         WHERE pr.clinic_id = $1::uuid AND pr.id = $2::uuid
           AND pr.is_active AND pr.accepting AND NOT pr.la_doi_tac
           AND coalesce(o.routing_status, 'UNASSIGNED') = 'UNASSIGNED'
           AND (pr.location_id IS NULL
                OR coalesce(v.location_id, a.location_id) IS NULL
                OR pr.location_id = coalesce(v.location_id, a.location_id))
           AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           AND {_DA_TRA_CHUA_LAM}
         ORDER BY v.checked_in_at, o.created_at, o.id
        """,
        clinic_id,
        room_id,
    )
    return [
        {
            "id": r["id"],
            "visit_id": r["visit_id"],
            "ten": r["service_name"],
            "khach": r["full_name"],
            "ma_khach": r["patient_code"],
            "routing_revision": int(r["routing_revision"]),
        }
        for r in await _loc_da_tra(conn, clinic_id, rows)
    ]


# ---------------------------------------------------------------------------
# Lệnh
# ---------------------------------------------------------------------------


class RoutingFinanceNotReadyError(LuotKhamConflictError):
    """409 SERVICE_FINANCE_NOT_READY kèm lý do CHI TIẾT của FinanceGate —
    Routing không chép luật tài chính, chỉ chuyển lý do (ROUTING §18)."""

    def __init__(self, finance_reason: str | None, cau: str | None = None) -> None:
        super().__init__(
            "SERVICE_FINANCE_NOT_READY",
            cau or f"Dịch vụ chưa đủ điều kiện tài chính ({finance_reason}).",
        )
        self.finance_reason = finance_reason


def _loi(code: str, cau: str) -> LuotKhamConflictError:
    return LuotKhamConflictError(code, cau)


def _can_khoa(key: str | None) -> str:
    if not key:
        raise LuotKhamValidationError(
            "IDEMPOTENCY_KEY_REQUIRED", "Thiếu Idempotency-Key."
        )
    if not 8 <= len(key) <= 200:
        raise LuotKhamValidationError(
            "IDEMPOTENCY_KEY_REQUIRED", "Khoá gửi lại phải dài từ 8 đến 200 ký tự."
        )
    return key


def _revision(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise LuotKhamValidationError(
            "ROUTING_REVISION_CONFLICT",
            "expected_routing_revision phải là số nguyên không âm.",
        )
    return value


def _ly_do(value: Any, cho_phep: frozenset[str]) -> str:
    if value not in cho_phep:
        raise LuotKhamValidationError(
            "ROUTING_REASON_INVALID", f"Mã lý do không hợp lệ: {value!r}."
        )
    if value == "OTHER":
        # Contract: OTHER cần ghi chú. Chưa có chỗ lưu ghi chú trong contract
        # (sự kiện chỉ mang mã) — từ chối thay vì tự đặt nơi lưu mới.
        raise LuotKhamValidationError(
            "ROUTING_REASON_NOTE_UNSUPPORTED",
            "Lý do OTHER cần ghi chú, nhưng chưa có chỗ lưu ghi chú — chọn mã cụ thể.",
        )
    return str(value)


_ORDER_SQL = """
SELECT id::text AS id, visit_id::text AS visit_id, exec_status, source,
       authorized_by::text AS authorized_by, hold_until_round, node_code,
       service_code, service_name,
       selection_status, routing_status, routing_revision, execution_status,
       room_id::text AS room_id, routing_nguon,
       phong_du_kien_id::text AS phong_du_kien_id
  FROM service_order
 WHERE clinic_id = $1::uuid AND id = $2::uuid
   FOR UPDATE
"""


def _routing_hieu_luc(o: asyncpg.Record) -> str:
    """Dòng lifecycle có routing_status NULL (fixture / cutover) coi như chưa xếp
    — KHÔNG suy phòng cũ thành phân phòng chính thức (Slice 4 §B)."""
    return str(o["routing_status"] or UNASSIGNED)


def _kiem_thuc_hien(o: asyncpg.Record) -> None:
    ex, cu = o["execution_status"], o["exec_status"]
    if ex in _DANG_LAM or cu in _DANG_LAM_CU:
        raise _loi(
            "SERVICE_ALREADY_IN_PROGRESS",
            "Dịch vụ đã bắt đầu — gặp sự cố thì dừng dịch vụ, không đổi phòng.",
        )
    if ex in _KET_THUC or cu in _KET_THUC_CU:
        raise _loi("SERVICE_EXECUTION_TERMINAL", "Dịch vụ đã kết thúc.")


def _nguon(value: Any) -> str:
    n = value if isinstance(value, str) and value else NGUON_KHAC
    if n not in NGUON_TU_NGUOI:
        raise LuotKhamValidationError("ROUTING_NGUON_INVALID", "Nguồn xếp phòng lạ.")
    return n


#: Ô chữ lý do chuyển phòng khi dịch vụ đang làm (Tuyền 29/09/2026: bắt buộc).
LY_DO_CHUYEN_TOI_THIEU = 3
LY_DO_CHUYEN_TOI_DA = 300


def ly_do_chuyen_phong(value: Any) -> str:
    """Lý do chuyển phòng khi đang làm — HÀM THUẦN. Rỗng / quá ngắn / quá dài /
    không phải chữ → lỗi kiểm tra có mã (không ném gì khác)."""
    ld = " ".join(value.split()) if isinstance(value, str) else ""
    if len(ld) < LY_DO_CHUYEN_TOI_THIEU:
        raise LuotKhamValidationError(
            "TRANSFER_REASON_REQUIRED",
            "Ghi lý do chuyển phòng (ít nhất vài chữ) — lý do hiện ở lịch sử lượt.",
        )
    if len(ld) > LY_DO_CHUYEN_TOI_DA:
        raise LuotKhamValidationError(
            "TRANSFER_REASON_TOO_LONG",
            f"Lý do chuyển phòng tối đa {LY_DO_CHUYEN_TOI_DA} ký tự.",
        )
    return ld


# ── Khối "Đổi phòng" dùng lối nào (Tuyền 29/09/2026) ────────────────────────
#
# Máy chủ quyết, màn chỉ đọc `che_do` của gợi ý phòng:
#   XEP             — khách đã chốt + chưa bắt đầu: lệnh xếp / đổi phòng (V10
#                     30/09/2026: CHƯA THU cũng xếp được — làm trước, thu sau);
#   DU_KIEN         — khách chưa chốt (hoặc tiền đang hoàn / sổ lệch): trưởng ca
#                     đặt PHÒNG DỰ KIẾN, chốt xong dây H4 xếp đúng phòng ấy;
#   CHUYEN_DANG_LAM — dịch vụ đang làm: CHỈ trưởng ca chuyển (dừng lần làm +
#                     chuyển phòng + chuyển hàng, bắt buộc lý do);
#   KHONG           — không đổi được (đã gọi vào, đã xong, khách về, không quyền).
CHE_DO_XEP = "XEP"
CHE_DO_DU_KIEN = "DU_KIEN"
CHE_DO_CHUYEN = "CHUYEN_DANG_LAM"
CHE_DO_KHONG = "KHONG"
CAU_DU_KIEN = (
    "Phòng dự kiến — xếp khi khách chốt và đã thu (hoặc tick Làm trước – thu sau)."
)


def che_do_doi_phong(
    *,
    execution_status: str | None,
    exec_status: str | None,
    selection_status: str | None,
    duoc_lam: bool,
    hang: str | None,
    dieu_phoi: bool,
    khach_ve: bool,
) -> str:
    """Lối đổi phòng cho MỘT chỉ định và MỘT người xem — hàm thuần.

    `dieu_phoi` = người xem có quyền Điều phối khách (`dispatch.manage`, trưởng
    ca). `hang` = trạng thái chỗ chờ sống của chỉ định (None = chưa có).
    `duoc_lam` = cửa làm của FinanceGate (V10: chưa thu vẫn True)."""
    ex, cu = execution_status or "", exec_status or ""
    if khach_ve or cu in ("draft", "cancelled"):
        return CHE_DO_KHONG
    if ex in _KET_THUC or cu in _KET_THUC_CU:
        return CHE_DO_KHONG
    if ex in _DANG_LAM or cu in _DANG_LAM_CU:
        return CHE_DO_CHUYEN if dieu_phoi else CHE_DO_KHONG
    if hang in ("called", "serving") or selection_status == "NOT_SELECTED":
        return CHE_DO_KHONG
    if selection_status == "SELECTED" and duoc_lam:
        return CHE_DO_XEP
    return CHE_DO_DU_KIEN if dieu_phoi else CHE_DO_KHONG


async def _reo_cho_xep_phong(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    nguoi_goi: str,
    cho_xep: Sequence[tuple[asyncpg.Record, str]],
) -> None:
    """Một chuông "chờ xếp phòng" cho mỗi chỉ định, gửi vai đứng quầy. Chuông
    đang mở cùng nguồn thì không tạo thêm (chạy lại không nhân đôi)."""
    # Nhập muộn: khối Chuông nằm ở tầng sự kiện, tránh vòng import.
    from clinicai.events.consumers.chuong import ghi_chuong_vai

    khach = await conn.fetchrow(
        "SELECT p.full_name, p.patient_code FROM visit v JOIN patient p"
        "    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id"
        " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
        clinic_id,
        visit_id,
    )
    ten = f"{khach['full_name']} ({khach['patient_code']})" if khach else "Khách"
    for o, ly_do in cho_xep:
        for vai in VAI_NHAN_CHO_XEP:
            await ghi_chuong_vai(
                conn,
                clinic_id=clinic_id,
                vai=vai,
                tieu_de=f"{ten} — chờ xếp phòng: {o['service_name']}",
                noi_dung=cau_cho_xep_phong(ly_do),
                nguon="hanh_trinh",
                nguon_id=f"cho_xep_phong:{o['id']}",
                duong_dan="/thu-ngan/dich-vu",
                nguoi_goi=nguoi_goi,
            )


class ServiceRoutingService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def recommend(
        self, *, order_id: Any, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Gợi ý phòng. Không ghi gì, không phát sự kiện, không gọi lệnh gán."""
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                QUYEN_XEM,
                cau="Bạn không có quyền xem gợi ý điều phối.",
            )
            o = await conn.fetchrow(
                f"""
                SELECT o.node_code, o.service_code, o.visit_id::text AS visit_id,
                       {DOI_TAC_LAM_TRON_SQL} AS doi_tac_lam,
                       o.execution_status, o.exec_status, o.selection_status,
                       o.phong_du_kien_id::text AS phong_du_kien_id,
                       r.name AS phong_hien_tai, v.closed_at,
                       (SELECT q.status FROM queue_entry q
                         WHERE q.clinic_id = o.clinic_id AND q.reason = 'SERVICE'
                           AND q.ref_id = o.id
                           AND q.status NOT IN ('done', 'left', 'cancelled')
                         ORDER BY q.created_at DESC LIMIT 1) AS hang,
                       (SELECT a.started_at FROM service_execution_attempt a
                         WHERE a.clinic_id = o.clinic_id
                           AND a.service_order_id = o.id
                           AND a.status = 'IN_PROGRESS') AS dang_lam_tu
                  FROM service_order o
                  JOIN visit v
                    ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
                  LEFT JOIN clinic_room r
                    ON r.id = o.room_id AND r.clinic_id = o.clinic_id
                   AND o.routing_status = 'ASSIGNED'
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                """,
                cid,
                oid,
            )
            if o is None:
                raise _loi("ORDER_NOT_FOUND", "Không tìm thấy chỉ định này.")
            che_do = CHE_DO_KHONG
            if not o["doi_tac_lam"]:
                tien = await finance_gate.can_start(conn, cid, oid)
                che_do = che_do_doi_phong(
                    execution_status=o["execution_status"],
                    exec_status=o["exec_status"],
                    selection_status=o["selection_status"],
                    duoc_lam=bool(tien and tien.duoc_lam),
                    hang=o["hang"],
                    dieu_phoi=await can(
                        conn, identity, QUYEN_THEO_NGUON[NGUON_TRUONG_CA]
                    ),
                    khach_ve=o["closed_at"] is not None,
                )
            ung_vien = (
                []
                if o["doi_tac_lam"]
                else rank_rooms(
                    await eligible_rooms(
                        conn,
                        cid,
                        str(o["node_code"]),
                        await co_so_cua_luot(conn, cid, order_id=oid),
                        tru_luot=o["visit_id"],
                        service_code=o["service_code"],
                    )
                )
            )
        luc = datetime.now(timezone.utc).isoformat()
        # Màn chỉ vẽ câu này và chỉ bày ô chọn phòng khi CO_PHONG (27/09/2026):
        # chụp phim ở quầy từng hiện "Chưa có phòng nào làm được…" + ô chọn rỗng.
        if o["doi_tac_lam"]:
            trang_thai, cau = GOI_Y_DOI_TAC_LAM, CAU_DOI_TAC_LAM
        elif not ung_vien:
            trang_thai, cau = GOI_Y_KHONG_CO_PHONG, CAU_KHONG_CO_PHONG
        else:
            trang_thai, cau = GOI_Y_CO_PHONG, None
        return {
            "advisor": ADVISOR,
            "generated_at": luc,
            "recommendation_ref": f"{ADVISOR}:{oid}:{luc}",
            "order_id": oid,
            "candidates": ung_vien,
            "trang_thai": trang_thai,
            "cau": cau,
            # Lối đổi phòng — máy chủ quyết (29/09/2026), màn chỉ vẽ theo đây.
            "che_do": che_do,
            "cau_che_do": CAU_DU_KIEN if che_do == CHE_DO_DU_KIEN else None,
            "phong_du_kien_id": o["phong_du_kien_id"],
            "phong_hien_tai": o["phong_hien_tai"],
            "dang_lam_tu": o["dang_lam_tu"].isoformat()
            if o["dang_lam_tu"] is not None
            else None,
        }

    async def assign(
        self,
        *,
        order_id: Any,
        room_id: Any,
        expected_routing_revision: Any,
        reason_code: Any,
        identity: StaffIdentity,
        idempotency_key: str | None,
        recommendation_ref: str | None = None,
        nguon: Any = None,
    ) -> dict[str, Any]:
        """AssignServiceRoom — lệnh DUY NHẤT xếp / đổi phòng chính thức.

        `nguon` = màn gọi lệnh (quầy thu / trưởng ca / khác): mỗi nguồn hỏi thêm
        quyền của lego ấy; trưởng ca đã xếp thì nguồn khác không đổi được (P3).
        """
        ng = _nguon(nguon)
        key = _can_khoa(idempotency_key)
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        rev = _revision(expected_routing_revision)
        ly_do = _ly_do(reason_code, ASSIGN_REASONS)
        ref = recommendation_ref if isinstance(recommendation_ref, str) else None
        if ref is not None and len(ref) > 300:
            raise LuotKhamValidationError(
                "RECOMMENDATION_REF_INVALID", "recommendation_ref quá dài."
            )
        payload = {
            "order_id": oid,
            "room_id": rid,
            "expected_routing_revision": rev,
            "reason_code": ly_do,
            "recommendation_ref": ref,
            "nguon": ng,
        }
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            # Kiểm quyền trong chính giao dịch của lệnh.
            await doi_quyen(
                conn, identity, QUYEN_XEP, cau="Bạn không có quyền xếp phòng."
            )
            if ng in QUYEN_THEO_NGUON:
                await doi_quyen(conn, identity, QUYEN_THEO_NGUON[ng])
            vid = await luot_cua(conn, "service_order", cid, oid)
            await khoa_luot(conn, cid, vid)
            cached = await bien_nhan_doc(conn, identity, ACTION_ASSIGN, key, payload)
            if cached is not None:
                return cached
            result = await self._gan(
                conn,
                identity,
                vid=vid,
                oid=oid,
                rid=rid,
                rev=rev,
                ly_do=ly_do,
                ref=ref,
                tu_dong=False,
                nguon=ng,
            )
            await bien_nhan_ghi(
                conn, identity, ACTION_ASSIGN, key, payload, oid, result
            )
        return result

    async def _gan(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        vid: str,
        oid: str,
        rid: str,
        rev: int,
        ly_do: str,
        ref: str | None,
        tu_dong: bool,
        nguon: str = NGUON_KHAC,
        du_kien_nguon: str | None = None,
    ) -> dict[str, Any]:
        """Lõi AssignServiceRoom — người gọi đã kiểm quyền và khoá lượt.

        Người bấm (``assign``) và khối Hành trình (``tu_xep_da_thu``, dây H4) đi
        CHUNG đường này: cùng mọi điều kiện, cùng một sự kiện. Không có lối tắt
        "hệ thống được xếp bừa".
        """
        cid = identity.clinic_id
        o = await conn.fetchrow(_ORDER_SQL, cid, oid)
        assert o is not None  # _visit_of đã thấy trong cùng giao dịch
        if int(o["routing_revision"]) != rev:
            raise _loi(
                "ROUTING_REVISION_CONFLICT",
                "Chỉ định vừa được điều phối bởi người khác — tải lại.",
            )
        if o["exec_status"] in ("draft", "cancelled") or not o["authorized_by"]:
            raise _loi(
                "SERVICE_ROUTING_NOT_ALLOWED",
                "Chỉ định chưa được bác sĩ duyệt hoặc đã huỷ.",
            )
        _kiem_thuc_hien(o)
        if o["selection_status"] != "SELECTED":
            raise _loi("SERVICE_NOT_SELECTED", "Khách chưa chọn làm dịch vụ này.")
        # V10 làm trước, thu sau: CHƯA THU không chặn xếp phòng — chỉ chặn tiền
        # đang hoàn / đã hoàn / sổ lệch (``finance_gate.CHO_LAM_STATES``).
        tai_chinh = await finance_gate.can_start(conn, cid, oid)
        if tai_chinh is None or not tai_chinh.duoc_lam:
            raise RoutingFinanceNotReadyError(
                tai_chinh.reason_code if tai_chinh else None,
                finance_gate.cau_chan_lam(tai_chinh),
            )
        flow = await khoa_flow(conn, cid, vid)
        closed = {
            int(r["round_no"])
            for r in await conn.fetch(
                "SELECT round_no FROM review_round WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND status = 'closed'",
                cid,
                vid,
            )
        }
        giu = rules.routing_hold_block(
            source=o["source"],
            route_decision=flow["route_decision"],
            vitals_recorded=flow["vitals_status"] == "recorded",
            hold_until_round=o["hold_until_round"],
            closed_rounds=closed,
        )
        if giu:
            raise _loi(giu, rules.cau_giu_dieu_phoi(giu))
        if await conn.fetchval(
            f"SELECT {DOI_TAC_LAM_TRON_SQL} FROM service_order o"
            f" WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid",
            cid,
            oid,
        ):
            raise _loi("SERVICE_PARTNER_PERFORMED", CAU_DOI_TAC_LAM)
        await self._kiem_phong(
            conn,
            cid,
            rid,
            o,
            await co_so_cua_luot(conn, cid, visit_id=vid),
        )

        hien = _routing_hieu_luc(o)
        q = await conn.fetchrow(
            """
            SELECT id::text AS id, status, room_id::text AS room_id
              FROM queue_entry
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND reason = 'SERVICE' AND ref_id = $3::uuid
               AND status NOT IN ('done', 'left', 'cancelled')
               FOR UPDATE
            """,
            cid,
            vid,
            oid,
        )
        if hien == ASSIGNED and o["room_id"] == rid:
            # Cùng phòng: không đổi gì, không tăng revision, không sự kiện.
            return self._ket_qua(
                oid,
                False,
                ASSIGNED,
                rid,
                int(o["routing_revision"]),
                q["status"] if q else None,
                ref,
            )
        queue_status = await self._xep_hang(conn, cid, vid, oid, rid, q)
        moi = await conn.fetchval(
            """
            UPDATE service_order
               SET routing_status = 'ASSIGNED', room_id = $3::uuid,
                   routing_revision = routing_revision + 1,
                   assigned_by = $4::uuid, assigned_at = now(),
                   routing_nguon = $5,
                   -- Hình chiếu cho reader cũ tới Slice 6; sự thật
                   -- routing là routing_status + routing_revision.
                   exec_status = 'assigned',
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND id = $2::uuid
            RETURNING routing_revision
            """,
            cid,
            oid,
            rid,
            identity.staff_id,
            nguon,
        )
        await cap_nhat_vi_tri(conn, cid, vid)
        tu_phong = o["room_id"] if hien == ASSIGNED else None
        # Sổ sự kiện nghiệp vụ (dòng thời gian, bảng hành trình) — cùng giao
        # dịch với việc xếp. Người gây ra là người bấm, hoặc người vừa thu tiền
        # khi khối Hành trình xếp thay (tu_dong).
        await emit_event(
            conn,
            ten="service.routed",
            clinic_id=cid,
            aggregate_id=oid,
            so_ke_tiep=True,
            payload=DaXepPhong(
                visit_id=vid,
                service_order_id=oid,
                room_id=rid,
                from_room_id=str(tu_phong) if tu_phong else None,
                routing_revision=int(moi),
                ly_do=ly_do,
                tu_dong=tu_dong,
                nguon=nguon,
                du_kien_nguon=du_kien_nguon,
            ),
            boi=nguoi(identity),
            correlation_id=vid,
        )
        await record_event(
            conn,
            event_type=EVENT_ROUTED,
            aggregate_type="service_order",
            aggregate_id=oid,
            identity=identity,
            origin=ORIGIN,
            payload={
                "visit_id": vid,
                "from_room_id": tu_phong,
                "to_room_id": rid,
                "routing_revision": int(moi),
                "reason_code": ly_do,
                "recommendation_ref": ref,
                "nguon": nguon,
                # Chỉ khi H4 xếp theo phòng dự kiến ai đó đặt trước.
                **({"du_kien_nguon": du_kien_nguon} if du_kien_nguon else {}),
            },
        )
        return self._ket_qua(oid, True, ASSIGNED, rid, int(moi), queue_status, ref)

    async def tu_xep_da_thu(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        staff_id: str | None,
        causation_id: str,
    ) -> list[str]:
        """Dây H4: xếp phòng vắng nhất THAY người vừa chốt dịch vụ / vừa thu.

        Tuyền chốt 24/09/2026: "thu tiền xong → hệ thống xếp phòng thay cho người
        vừa thu tiền, dùng quyền của người ấy; ai có quyền điều phối đổi lại
        được, lần sau đè lần trước". V10 (30/09/2026, "làm trước, thu sau"):
        chạy NGAY khi khách chốt (``service_selection.confirmed``), không chờ
        thu — mọi chỉ định khách đã chốt, chưa thu cũng xếp. Thu tiền sau đó vẫn
        gọi lại (vô hại: chỉ định đã có phòng thì bỏ). Tên hàm giữ như cũ.

        Chỉ xếp chỉ định CHƯA có phòng (UNASSIGNED). Phòng cũ bị huỷ
        (REASSIGNMENT_REQUIRED) là việc của một NGƯỜI — đã có việc
        OPS-ROUTING-REASSIGN, không tự đẩy khách sang phòng khác (ChatGPT tin
        112). Người chốt / người thu không có quyền xếp phòng, hay không phòng
        nào làm được → để nguyên, người có quyền xếp tay. Không bao giờ ném lỗi
        làm hỏng việc giao tin: mỗi chỉ định một điểm lưu (savepoint), hỏng cái
        nào bỏ cái ấy.

        Trả mã các chỉ định đã xếp. Chạy lại được: chỉ định đã có phòng thì bỏ.
        """
        if not staff_id:
            return []
        nguoi_thu = await danh_tinh_nhan_vien(
            conn, clinic_id=clinic_id, staff_id=staff_id
        )
        if nguoi_thu is None or not await can(conn, nguoi_thu, QUYEN_XEP):
            return []
        # Khoá lượt như mọi lệnh điều phối. Lượt đã đóng / khách đã về thì
        # thôi — không ném lỗi (ném là người đưa tin thử lại mãi một việc vô
        # nghĩa); chỉ định đã trả mà chưa làm sẽ được mang sang lượt sau (H2).
        luot = await conn.fetchrow(
            "SELECT status, closed_at FROM visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            clinic_id,
            visit_id,
        )
        # INCOMPLETE (khách bỏ về) / FINALIZED / AMENDED: không xếp phòng.
        # ĐÃ CHECK-OUT (closed_at) cũng thôi — lượt check-out vẫn giữ status
        # IN_PROGRESS, nên chỉ xét status thì thu tiền rồi về ngay vẫn bị tự xếp
        # phòng → khách ma trong hàng chờ phòng (kiểm toán chức năng 27/09/2026).
        if luot is None or luot["status"] not in ("OPEN", "IN_PROGRESS"):
            return []
        if luot["closed_at"] is not None:
            return []
        orders = await conn.fetch(
            f"""
            SELECT o.id::text AS id, o.node_code, o.service_code,
                   o.routing_revision,
                   o.service_name, o.phong_du_kien_id::text AS phong_du_kien,
                   o.routing_nguon
              FROM service_order o
             WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
               AND o.selection_status = 'SELECTED'
               AND coalesce(o.routing_status, 'UNASSIGNED') = 'UNASSIGNED'
               AND o.exec_status = 'authorized'
               AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
               -- Đối tác làm trọn: khách không xếp hàng ở phòng nào của phòng
               -- khám — không xếp, cũng không réo "chờ xếp phòng".
               AND NOT {DOI_TAC_LAM_TRON_SQL}
             ORDER BY o.created_at, o.id
            """,
            clinic_id,
            visit_id,
        )
        tai_chinh = await finance_gate.states_for_orders(
            conn, clinic_id, [o["id"] for o in orders]
        )
        da_xep: list[str] = []
        cho_xep: list[tuple[asyncpg.Record, str]] = []
        co_so = await co_so_cua_luot(conn, clinic_id, visit_id=visit_id)
        # Dây C9 (27/09/2026): BẬT = chỉ áp phòng lễ tân đã chọn, không tự chọn
        # phòng vắng nhất. Mặc định TẮT (hành vi cũ).
        chi_ap = bool(await doc_day(conn, clinic_id, "h4_chi_ap_phong_du_kien"))
        for o in orders:
            quyet = tai_chinh.get(o["id"])
            if quyet is None or not quyet.duoc_lam:
                continue
            ung_vien = rank_rooms(
                await eligible_rooms(
                    conn,
                    clinic_id,
                    o["node_code"],
                    co_so,
                    tru_luot=visit_id,
                    service_code=o["service_code"],
                )
            )
            # Phòng khách chọn ở quầy (phong_du_kien) thắng — nếu nó vẫn đủ điều
            # kiện (đúng cơ sở, còn nhận khách, làm được bước này). Không thì
            # phòng vắng nhất như cũ: ý định cũ không được làm khách kẹt.
            rid, ly_do_cho = chon_phong_h4(
                ung_vien, o["phong_du_kien"], chi_ap_phong_du_kien=chi_ap
            )
            if rid is None:
                # Không xếp được — KHÔNG im lặng: réo quầy "chờ xếp phòng".
                cho_xep.append((o, ly_do_cho or CHO_XEP_KHONG_CO_PHONG))
                continue
            # Phòng dự kiến do ai đặt (quầy thu / trưởng ca) — để lịch sử nói
            # "tự động xếp theo phòng trưởng ca chọn trước".
            du_kien_nguon = (
                o["routing_nguon"]
                if rid == o["phong_du_kien"]
                and o["routing_nguon"] in (NGUON_QUAY_THU, NGUON_TRUONG_CA)
                else None
            )
            try:
                async with conn.transaction():
                    kq = await self._gan(
                        conn,
                        nguoi_thu,
                        vid=visit_id,
                        oid=o["id"],
                        rid=rid,
                        rev=int(o["routing_revision"]),
                        ly_do="INITIAL_ASSIGNMENT",
                        ref=f"{ADVISOR}:hanh-trinh:{causation_id}",
                        tu_dong=True,
                        nguon=NGUON_TU_DONG,
                        du_kien_nguon=du_kien_nguon,
                    )
            except LuotKhamConflictError:
                continue
            if kq["changed"]:
                da_xep.append(o["id"])
        if cho_xep:
            await _reo_cho_xep_phong(
                conn,
                clinic_id=clinic_id,
                visit_id=visit_id,
                nguoi_goi=str(staff_id),
                cho_xep=cho_xep,
            )
        return da_xep

    async def dat_phong_du_kien(
        self,
        *,
        order_id: Any,
        room_id: Any,
        identity: StaffIdentity,
        nguon: Any = None,
    ) -> dict[str, Any]:
        """PlanServiceRoom — ghi phòng khách sẽ làm, TRƯỚC khi khách chốt.

        Khách chưa chốt: không xếp phòng chính thức, không vào hàng chờ phòng —
        chỉ là ý định cho dây H4 dùng khi khách chốt. Khách ĐÃ CHỐT (V10, chưa
        thu cũng vậy): xếp thật luôn qua `_gan`. Cùng quyền với xếp phòng.
        ``room_id`` rỗng = bỏ chọn (để hệ thống tự chọn).

        `nguon` = quầy thu (mặc định) hoặc trưởng ca (29/09/2026: trưởng ca đặt
        phòng được cả khi khách chưa trả tiền). Mỗi nguồn hỏi quyền lego của
        mình. Người đặt sau đè người đặt trước — không khoá (Tuyền 29/09).
        """
        ng = NGUON_QUAY_THU if nguon in (None, "") else _nguon(nguon)
        if ng not in QUYEN_THEO_NGUON:
            raise LuotKhamValidationError(
                "ROUTING_NGUON_INVALID",
                "Phòng dự kiến chỉ đặt ở quầy thu hoặc màn trưởng ca.",
            )
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rid = (
            None if room_id in (None, "") else _uuid(room_id, "Mã phòng không hợp lệ.")
        )
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn, identity, QUYEN_XEP, cau="Bạn không có quyền xếp phòng."
            )
            # Ô "Làm ở phòng" của quầy thu (lego Thanh toán dịch vụ) hoặc của
            # trưởng ca (lego Điều phối khách).
            await doi_quyen(conn, identity, QUYEN_THEO_NGUON[ng])
            vid = await luot_cua(conn, "service_order", cid, oid)
            await khoa_luot(conn, cid, vid)
            o = await conn.fetchrow(_ORDER_SQL, cid, oid)
            assert o is not None
            if o["exec_status"] in ("draft", "cancelled"):
                raise _loi("SERVICE_ROUTING_NOT_ALLOWED", "Chỉ định đã huỷ.")
            _kiem_thuc_hien(o)
            if _routing_hieu_luc(o) == ASSIGNED:
                # Quầy thu đổi phòng LÚC NÀO CŨNG ĐƯỢC (Tuyền 25/09/2026) — đã xếp
                # rồi thì đổi thẳng phòng thật (cùng lõi `_gan`, đúng nguồn gọi).
                # 29/09: kể cả khi trưởng ca đã xếp (bỏ khoá; lịch sử ghi lại).
                if rid is None:
                    raise _loi(
                        "ROUTING_ALREADY_ASSIGNED",
                        "Đã xếp phòng — chọn phòng khác để đổi, không bỏ trống được.",
                    )
                kq = await self._gan(
                    conn,
                    identity,
                    vid=vid,
                    oid=oid,
                    rid=rid,
                    rev=int(o["routing_revision"]),
                    ly_do="MANUAL_CORRECTION",
                    ref=None,
                    tu_dong=False,
                    nguon=ng,
                )
                await conn.execute(
                    "UPDATE service_order SET phong_du_kien_id = $3::uuid"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    oid,
                    rid,
                )
                return {**kq, "ok": True, "order_id": oid, "phong_du_kien_id": rid}
            if rid is not None:
                await self._kiem_phong(
                    conn,
                    cid,
                    rid,
                    o,
                    await co_so_cua_luot(conn, cid, visit_id=vid),
                )
            if rid is not None and o["selection_status"] == "SELECTED":
                # V10 làm trước, thu sau: khách ĐÃ CHỐT thì chọn phòng = xếp
                # thật luôn (cùng lõi `_gan`), không đợi thu tiền mới xếp. Không
                # xếp được (giữ chờ sinh hiệu, tiền đang hoàn…) thì ghi dự kiến
                # như cũ — điểm lưu để lỗi của `_gan` không làm hỏng lệnh.
                try:
                    async with conn.transaction():
                        kq_xep = await self._gan(
                            conn,
                            identity,
                            vid=vid,
                            oid=oid,
                            rid=rid,
                            rev=int(o["routing_revision"]),
                            ly_do="INITIAL_ASSIGNMENT",
                            ref=None,
                            tu_dong=False,
                            nguon=ng,
                        )
                        await conn.execute(
                            "UPDATE service_order SET phong_du_kien_id = $3::uuid"
                            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                            cid,
                            oid,
                            rid,
                        )
                except LuotKhamConflictError:
                    kq_xep = None
                if kq_xep is not None:
                    return {
                        **kq_xep,
                        "ok": True,
                        "order_id": oid,
                        "phong_du_kien_id": rid,
                    }
            # Chưa xếp: `routing_nguon` = ai đặt phòng dự kiến (bỏ chọn → NULL),
            # để dây H4 ghi "tự động theo phòng trưởng ca / quầy chọn trước".
            await conn.execute(
                "UPDATE service_order SET phong_du_kien_id = $3::uuid,"
                "       routing_nguon = CASE WHEN $3::uuid IS NULL THEN NULL"
                "                            ELSE $4 END"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                oid,
                rid,
                ng,
            )
        return {
            "ok": True,
            "order_id": oid,
            "phong_du_kien_id": rid,
            "nguon": ng,
            "cau": CAU_DU_KIEN if rid else None,
        }

    async def chuyen_phong_dang_lam(
        self,
        *,
        order_id: Any,
        room_id: Any,
        expected_routing_revision: Any,
        ly_do: Any,
        identity: StaffIdentity,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """TransferInProgressService — dịch vụ ĐÃ BẮT ĐẦU, trưởng ca chuyển sang
        phòng khác (Tuyền 29/09/2026). MỘT giao dịch:

          1. dừng lần làm đang chạy (INTERRUPTED, lý do ghi vào lần làm) — phiếu
             / tệp đã nhập gắn với CHỈ ĐỊNH nên không mất gì;
          2. chỉ định về "chờ làm" (PENDING) ở phòng mới, routing +1, nguồn
             trưởng ca;
          3. chỗ chờ của chỉ định chuyển sang hàng phòng mới (đang chờ, giữ tuổi
             chờ), các chỗ "đợi quay lại" của lượt mở ra, vị trí khách cập nhật;
          4. sự kiện `service.room_transferred` kèm LÝ DO (bắt buộc).

        CHỈ quyền Điều phối khách (`dispatch.manage`). Dịch vụ xong / huỷ / không
        làm vẫn chặn; chưa bắt đầu thì dùng lệnh xếp phòng thường.
        """
        key = _can_khoa(idempotency_key)
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        rev = _revision(expected_routing_revision)
        ld = ly_do_chuyen_phong(ly_do)
        payload = {
            "order_id": oid,
            "room_id": rid,
            "expected_routing_revision": rev,
            "ly_do": ld,
        }
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn,
                identity,
                QUYEN_THEO_NGUON[NGUON_TRUONG_CA],
                cau=(
                    "Dịch vụ đã bắt đầu — chỉ trưởng ca (quyền Điều phối khách)"
                    " chuyển phòng được."
                ),
            )
            vid = await luot_cua(conn, "service_order", cid, oid)
            await khoa_luot(conn, cid, vid)
            cached = await bien_nhan_doc(conn, identity, ACTION_TRANSFER, key, payload)
            if cached is not None:
                return cached
            o = await conn.fetchrow(_ORDER_SQL, cid, oid)
            assert o is not None
            if int(o["routing_revision"]) != rev:
                raise _loi(
                    "ROUTING_REVISION_CONFLICT",
                    "Chỉ định vừa được điều phối bởi người khác — tải lại.",
                )
            ex, cu = o["execution_status"], o["exec_status"]
            if ex in _KET_THUC or cu in _KET_THUC_CU or cu in ("draft", "cancelled"):
                raise _loi("SERVICE_EXECUTION_TERMINAL", "Dịch vụ đã kết thúc.")
            if ex not in _DANG_LAM and cu not in _DANG_LAM_CU:
                raise _loi(
                    "SERVICE_NOT_IN_PROGRESS",
                    "Dịch vụ chưa bắt đầu — dùng Đổi phòng thường.",
                )
            if o["room_id"] == rid:
                raise _loi("ROOM_SAME", "Khách đang làm ở chính phòng này.")
            await self._kiem_phong(
                conn,
                cid,
                rid,
                o,
                await co_so_cua_luot(conn, cid, visit_id=vid),
            )
            ten = {
                str(r["id"]): r["name"]
                for r in await conn.fetch(
                    "SELECT id::text AS id, name FROM clinic_room"
                    " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])",
                    cid,
                    [x for x in (o["room_id"], rid) if x],
                )
            }
            tu_phong = o["room_id"]
            ghi_chu = (
                f"Trưởng ca chuyển phòng {ten.get(tu_phong or '', '—')}"
                f" → {ten.get(rid, '—')}: {ld}"
            )
            lan = await conn.fetchrow(
                "SELECT id::text AS id, attempt_no FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND status = 'IN_PROGRESS' FOR UPDATE",
                cid,
                oid,
            )
            if lan is not None:
                # Lần làm đóng CÓ LÝ DO (mã OTHER + ghi chú — ràng buộc bảng đòi
                # ghi chú cho OTHER). Không xoá gì của lần làm.
                await conn.execute(
                    "UPDATE service_execution_attempt"
                    "   SET status = 'INTERRUPTED', interrupted_by = $3::uuid,"
                    "       interrupted_at = now(), interruption_reason_code = 'OTHER',"
                    "       interruption_reason_note = $4, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    lan["id"],
                    identity.staff_id,
                    ghi_chu,
                )
            moi = await conn.fetchrow(
                """
                UPDATE service_order
                   SET execution_status = 'PENDING',
                       execution_revision = execution_revision + 1,
                       routing_status = 'ASSIGNED', room_id = $3::uuid,
                       routing_revision = routing_revision + 1,
                       assigned_by = $4::uuid, assigned_at = now(),
                       routing_nguon = 'truong_ca',
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                RETURNING routing_revision, execution_revision
                """,
                cid,
                oid,
                rid,
                identity.staff_id,
            )
            # Chỗ chờ đi theo khách sang hàng phòng mới — đang chờ, GIỮ tuổi chờ
            # (khách đã chờ + đã làm dở, không đẩy xuống cuối hàng).
            da_chuyen = await conn.fetchval(
                """
                UPDATE queue_entry
                   SET room_id = $3::uuid, status = 'waiting',
                       called_at = NULL, serving_at = NULL,
                       eligible_at = coalesce(eligible_at, created_at, now()),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND reason = 'SERVICE'
                   AND ref_id = $2::uuid
                   AND status NOT IN ('done', 'left', 'cancelled')
                RETURNING id::text
                """,
                cid,
                oid,
                rid,
            )
            if da_chuyen is None:
                await self._xep_hang(conn, cid, vid, oid, rid, None)
            # Khách rời phòng cũ: các chỗ "đợi quay lại" của lượt mở ra (cùng
            # luật với Xong / Dừng), rồi con trỏ "khách đang ở đâu".
            await mo_cho_bi_chan(conn, cid, vid)
            await cap_nhat_vi_tri(conn, cid, vid)
            await emit_event(
                conn,
                ten="service.room_transferred",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DichVuDaChuyenPhong(
                    visit_id=vid,
                    service_order_id=oid,
                    from_room_id=str(tu_phong) if tu_phong else None,
                    room_id=rid,
                    attempt_id=lan["id"] if lan else None,
                    attempt_no=int(lan["attempt_no"]) if lan else None,
                    routing_revision=int(moi["routing_revision"]),
                    execution_revision=int(moi["execution_revision"]),
                    ly_do=ld,
                    nguon=NGUON_TRUONG_CA,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            await record_event(
                conn,
                event_type=EVENT_TRANSFERRED,
                aggregate_type="service_order",
                aggregate_id=oid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "from_room_id": tu_phong,
                    "to_room_id": rid,
                    "routing_revision": int(moi["routing_revision"]),
                    "ly_do": ld,
                    "nguon": NGUON_TRUONG_CA,
                },
            )
            result = {
                "ok": True,
                "order_id": oid,
                "changed": True,
                "routing_status": ASSIGNED,
                "room_id": rid,
                "routing_revision": int(moi["routing_revision"]),
                "execution_status": "PENDING",
                "execution_revision": int(moi["execution_revision"]),
                "queue_status": "waiting",
                "cau": ghi_chu,
            }
            await bien_nhan_ghi(
                conn, identity, ACTION_TRANSFER, key, payload, oid, result
            )
        return result

    async def invalidate(
        self,
        *,
        order_id: Any,
        expected_routing_revision: Any,
        reason_code: Any,
        identity: StaffIdentity,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """InvalidateServiceRouting — phân phòng mất hiệu lực TRƯỚC khi bắt đầu."""
        key = _can_khoa(idempotency_key)
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rev = _revision(expected_routing_revision)
        ly_do = _ly_do(reason_code, INVALIDATE_REASONS)
        payload = {
            "order_id": oid,
            "expected_routing_revision": rev,
            "reason_code": ly_do,
        }
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            # Kiểm quyền trong chính giao dịch của lệnh.
            await doi_quyen(
                conn, identity, QUYEN_HUY, cau="Bạn không có quyền huỷ xếp phòng."
            )
            vid = await luot_cua(conn, "service_order", cid, oid)
            await khoa_luot(conn, cid, vid)
            cached = await bien_nhan_doc(
                conn, identity, ACTION_INVALIDATE, key, payload
            )
            if cached is not None:
                return cached
            o = await conn.fetchrow(_ORDER_SQL, cid, oid)
            assert o is not None
            if int(o["routing_revision"]) != rev:
                raise _loi(
                    "ROUTING_REVISION_CONFLICT",
                    "Chỉ định vừa được điều phối bởi người khác — tải lại.",
                )
            hien = _routing_hieu_luc(o)
            if hien == REASSIGNMENT_REQUIRED:
                raise _loi(
                    "ROUTING_ALREADY_INVALIDATED", "Phân phòng này đã mất hiệu lực."
                )
            if hien != ASSIGNED:
                raise _loi("ROUTING_NOT_ASSIGNED", "Chỉ định chưa được xếp phòng.")
            _kiem_thuc_hien(o)
            q = await conn.fetchrow(
                """
                SELECT id::text AS id, status FROM queue_entry
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND reason = 'SERVICE' AND ref_id = $3::uuid
                   AND status NOT IN ('done', 'left', 'cancelled')
                   FOR UPDATE
                """,
                cid,
                vid,
                oid,
            )
            if q is not None and q["status"] == "serving":
                raise _loi(
                    "SERVICE_ALREADY_IN_PROGRESS",
                    "Khách đang được làm ở phòng — dừng dịch vụ thay vì huỷ phòng.",
                )
            if q is not None:
                # Chỗ chờ ở phòng cũ hết hiệu lực; GIỮ eligible_at để lần xếp
                # lại không đẩy khách xuống cuối hàng.
                await conn.execute(
                    "UPDATE queue_entry SET status = 'cancelled',"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    q["id"],
                )
            moi = await conn.fetchval(
                """
                UPDATE service_order
                   SET routing_status = 'REASSIGNMENT_REQUIRED', room_id = NULL,
                       routing_revision = routing_revision + 1,
                       assigned_by = NULL, assigned_at = NULL,
                       -- Hình chiếu cho reader cũ: chưa có phòng.
                       exec_status = 'authorized',
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                RETURNING routing_revision
                """,
                cid,
                oid,
            )
            await cap_nhat_vi_tri(conn, cid, vid)
            # Sổ sự kiện nghiệp vụ, cùng giao dịch: phòng vừa mất thì phải có
            # người xếp lại, và người ấy nhận việc qua đây chứ không qua ai nhớ.
            await emit_event(
                conn,
                ten="service.routing_invalidated",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=XepPhongDaHuy(
                    visit_id=vid,
                    service_order_id=oid,
                    from_room_id=str(o["room_id"]) if o["room_id"] else None,
                    routing_revision=int(moi),
                    ly_do=ly_do,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            await record_event(
                conn,
                event_type=EVENT_INVALIDATED,
                aggregate_type="service_order",
                aggregate_id=oid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "from_room_id": o["room_id"],
                    "routing_revision": int(moi),
                    "reason_code": ly_do,
                },
            )
            result = {
                "ok": True,
                "order_id": oid,
                "changed": True,
                "routing_status": REASSIGNMENT_REQUIRED,
                "room_id": None,
                "routing_revision": int(moi),
            }
            await bien_nhan_ghi(
                conn, identity, ACTION_INVALIDATE, key, payload, oid, result
            )
        return result

    @staticmethod
    async def _kiem_phong(
        conn: asyncpg.Connection,
        cid: str,
        rid: str,
        o: asyncpg.Record,
        co_so: str | None = None,
    ) -> None:
        """Phòng nhận được chỉ định ``o`` (dòng ``_ORDER_SQL``) không — cùng luật
        ``phong_lam_duoc`` với gợi ý phòng / dây H4."""
        r = await conn.fetchrow(
            """
            SELECT r.is_active, r.accepting, r.location_id::text AS location_id,
                   phong_lam_duoc(r.clinic_id, r.id, $3, $4) AS lam_duoc
              FROM clinic_room r
             WHERE r.clinic_id = $1::uuid AND r.id = $2::uuid
               FOR SHARE OF r
            """,
            cid,
            rid,
            str(o["node_code"]),
            o["service_code"],
        )
        if r is None:
            raise _loi("ROOM_NOT_FOUND", "Không tìm thấy phòng này.")
        if not r["is_active"]:
            raise _loi("ROOM_INACTIVE", "Phòng đã ngừng hoạt động.")
        if not r["accepting"]:
            raise _loi("ROOM_NOT_ACCEPTING", "Phòng đang tạm ngừng nhận khách.")
        if not r["lam_duoc"]:
            raise _loi(
                "ROOM_NOT_SERVING_SERVICE",
                cau_phong_khong_lam(
                    o["service_name"],
                    await phong_gan_dich_vu(conn, cid, o["service_code"]),
                ),
            )
        if co_so and r["location_id"] and r["location_id"] != co_so:
            raise _loi(
                "ROOM_OTHER_LOCATION",
                "Phòng này ở cơ sở khác với nơi khách đang khám.",
            )

    @staticmethod
    async def _xep_hang(
        conn: asyncpg.Connection,
        cid: str,
        vid: str,
        oid: str,
        rid: str,
        q: asyncpg.Record | None,
    ) -> str:
        """Đúng MỘT chỗ chờ sống cho chỉ định, ở phòng mới, GIỮ tuổi chờ."""
        if q is not None:
            if q["status"] in ("called", "serving"):
                raise _loi(
                    "ROOM_ALREADY_CALLED",
                    "Phòng hiện tại đã gọi khách vào — không chuyển phòng được nữa.",
                )
            # Đổi phòng tại chỗ: eligible_at / created_at giữ nguyên.
            await conn.execute(
                "UPDATE queue_entry SET room_id = $3::uuid, version = version + 1,"
                " updated_at = now() WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                q["id"],
                rid,
            )
            return str(q["status"])
        busy = await khach_dang_duoc_phuc_vu(conn, cid, vid)
        status = rules.initial_queue_status(visit_busy=busy)
        # Sau khi phân phòng cũ mất hiệu lực, chỗ chờ cũ đã huỷ nhưng giữ mốc
        # bắt đầu chờ — xếp lại phòng thì khách giữ tuổi chờ ấy.
        await conn.execute(
            """
            INSERT INTO queue_entry
                (clinic_id, visit_id, lane, room_id, reason, ref_id, status,
                 eligible_at)
            VALUES ($1::uuid, $2::uuid, 'ROOM', $3::uuid, 'SERVICE', $4::uuid, $5,
                    CASE WHEN $5 = 'waiting' THEN coalesce(
                        (SELECT q.eligible_at FROM queue_entry q
                          WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
                            AND q.reason = 'SERVICE' AND q.ref_id = $4::uuid
                            AND q.status = 'cancelled' AND q.eligible_at IS NOT NULL
                          ORDER BY q.updated_at DESC LIMIT 1),
                        now()) END)
            """,
            cid,
            vid,
            rid,
            oid,
            status,
        )
        return status

    @staticmethod
    def _ket_qua(
        oid: str,
        changed: bool,
        routing: str,
        rid: str | None,
        rev: int,
        queue_status: str | None,
        ref: str | None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": True,
            "order_id": oid,
            "changed": changed,
            "routing_status": routing,
            "room_id": rid,
            "routing_revision": rev,
            "queue_status": queue_status,
        }
        if ref is not None:
            out["recommendation_ref"] = ref
        return out
