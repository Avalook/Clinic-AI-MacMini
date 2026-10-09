"""FinanceGate — về mặt TÀI CHÍNH, chỉ định này đã được phép bắt đầu làm chưa?

Contract: docs/ai/lifecycle-v1/ClinicAI-FINANCE-GATE-v1.md (frozen) — SỬA ở V10
(Tuyền 30/09/2026, "làm trước, thu sau"): chưa thu KHÔNG còn chặn xếp phòng hay
bắt đầu làm. Cửa làm là ``duoc_lam`` (``CHO_LAM_STATES``); ``financially_ready``
chỉ còn nghĩa "tiền đã xong" để hiện nhãn. Đã làm mà chưa thu = DUE (thu ở quầy
như thường), không còn là "bất thường cần đối soát".
SỬA lần nữa (Tuyền 30/09/2026 tối, "thu trước, trừ khi tick"): dây nối
``thu_truoc_khi_lam`` (mặc định BẬT) — DUE / thiếu giá chỉ ``duoc_lam`` khi lượt
được tick "Làm trước – thu sau" (``visit.lam_truoc_thu_sau_luc``). Dây TẮT = V10.

Không thu tiền, không hoàn tiền, không xếp phòng, không bắt đầu dịch vụ, không
gọi AI hay đối tác. Không có cột ``billing_status``: trạng thái tài chính SUY RA
từ lựa chọn của khách, cấu hình giá hiện hành, và SỔ tiền bất biến
(payment_cycle + payment_bill_line + payment_refund[_line]).

Hai phần tách rời:
  * ``states_for_orders`` — MỘT câu truy vấn cho cả lô chỉ định (không N+1);
  * ``derive_finance_state`` — hàm thuần, không chạm DB.
``can_start`` dùng chính đường lô với một phần tử, không có logic thứ hai.

Giá / bên thu dùng ĐÚNG luật của hoá đơn (``bill_service.giai_gia``). Đã có dấu
vết tiền thì ảnh chụp lịch sử thắng — không diễn giải lại bằng bảng giá mới.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.services.bill_service import (
    BEN_THU_MAU_THUAN,
    CLINIC,
    EXTERNAL,
    giai_gia,
)
from clinicai.services.day_noi import giai_gia_tri

NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_REQUIRED = "NOT_REQUIRED"
DUE = "DUE"
PENDING_VERIFICATION = "PENDING_VERIFICATION"
PAID = "PAID"
REFUND_PENDING = "REFUND_PENDING"
REFUNDED = "REFUNDED"
FINANCIAL_DATA_INCOMPLETE = "FINANCIAL_DATA_INCOMPLETE"
FINANCIAL_REVIEW_REQUIRED = "FINANCIAL_REVIEW_REQUIRED"
#: ĐỐI TÁC TỰ THU (Tuyền chốt 27/09/2026, Q1: "khách trả trực tiếp cho đối
#: tác"). Trước đây là EXTERNAL_PAYMENT_UNRESOLVED — chặn xếp phòng, chặn bắt
#: đầu và đối tác không bao giờ nhận việc, mà không có lệnh nào gỡ. Nay: về
#: phía PHÒNG KHÁM không có gì phải thu → sẵn sàng. Đối tác đã thu hay chưa là
#: sổ riêng của khối Đối tác (`doi_tac_thanh_toan`), không chặn luồng khách.
PARTNER_COLLECTS = "PARTNER_COLLECTS"

#: Tiền đã XONG về phía phòng khám (FINANCE-GATE §3 + đối tác tự thu 27/09/2026).
#: Từ V10 (30/09/2026) đây chỉ còn là NHÃN hiển thị ("đã thu / chưa thu") — không
#: còn là cửa xếp phòng hay bắt đầu làm; cửa ấy là ``CHO_LAM_STATES``.
READY_STATES = frozenset({PAID, NOT_REQUIRED, PARTNER_COLLECTS})

#: LÀM TRƯỚC, THU SAU (V10 — Tuyền 30/09/2026: "chỉ định rồi mà chưa thu tiền
#: cũng vẫn cho thực hiện đi rồi cuối buổi thu cũng được"). Khách đã chốt làm là
#: được xếp phòng / vào hàng / bắt đầu / làm xong — kể cả khi CHƯA THU (DUE),
#: chuyển khoản đang chờ xác minh, hay bảng giá còn thiếu (thu sau khi sửa giá).
#: Còn chặn: khách chưa chốt (NOT_APPLICABLE), tiền ĐÃ THU đang hoàn / đã hoàn
#: (khách đã lấy lại tiền — làm tiếp là cho không), và sổ tiền lệch cần người
#: đối soát (FINANCIAL_REVIEW_REQUIRED) — hướng "mở hết" chỉ giữ chặn ở tiền đã
#: thu và dữ liệu hỏng.
CHO_LAM_STATES = READY_STATES | frozenset(
    {DUE, PENDING_VERIFICATION, FINANCIAL_DATA_INCOMPLETE}
)

#: THU TRƯỚC KHI LÀM (Tuyền 30/09/2026 tối): dây ``thu_truoc_khi_lam`` BẬT và
#: lượt KHÔNG tick "Làm trước – thu sau" → chỉ những trạng thái này được làm
#: (như trước V10: tiền đã xong, hoặc chuyển khoản đang chờ xác minh).
THU_TRUOC_STATES = READY_STATES | frozenset({PENDING_VERIFICATION})

#: Mã dây nối (``services/day_noi.py``) — đọc trong CHÍNH câu truy vấn lô.
DAY_THU_TRUOC = "thu_truoc_khi_lam"

#: Câu chặn khi chưa thu mà lượt không tick — màn hiện nguyên câu này.
CAU_CHUA_THU = "Chưa thu tiền — thu trước hoặc tick Làm trước – thu sau."

#: Mã lỗi cho StartService (FINANCE-GATE §6).
START_REASON = {
    NOT_APPLICABLE: "SERVICE_NOT_SELECTED",
    DUE: "SERVICE_PAYMENT_REQUIRED",
    PENDING_VERIFICATION: "SERVICE_PAYMENT_PENDING_VERIFICATION",
    REFUND_PENDING: "SERVICE_REFUND_PENDING",
    REFUNDED: "SERVICE_PAYMENT_REFUNDED",
    FINANCIAL_DATA_INCOMPLETE: "SERVICE_FINANCIAL_DATA_INCOMPLETE",
    FINANCIAL_REVIEW_REQUIRED: "SERVICE_FINANCIAL_REVIEW_REQUIRED",
}


@dataclass(frozen=True)
class Footprint:
    """Một dòng PHÒNG KHÁM thu của chỉ định, trong một lần thu đã từng giữ phủ."""

    line_id: str
    cycle_id: str
    cycle_status: str
    paid: bool
    quantity: Decimal
    refund_pending_qty: Decimal
    refund_completed_qty: Decimal


@dataclass(frozen=True)
class OrderFinanceFacts:
    order_id: str
    selection_status: str | None
    exec_status: str
    execution_status: str | None
    gia: tuple[Any, ...]
    ben_thu: tuple[str | None, ...]
    footprints: tuple[Footprint, ...]
    visit_allocation_unknown: bool
    #: Dây ``thu_truoc_khi_lam`` (mặc định False ở đây để hàm thuần giữ nghĩa
    #: V10 khi người gọi không nói gì; đường DB luôn điền giá trị thật).
    thu_truoc_khi_lam: bool = False
    #: Lượt đã tick "Làm trước – thu sau".
    lam_truoc_thu_sau: bool = False
    #: Buổi liệu trình dùng tiền TRẢ TRƯỚC (08/10/2026) — đã thu ở lần trả trước.
    phu_lieu_trinh: bool = False


@dataclass(frozen=True)
class FinanceDecision:
    order_id: str
    finance_state: str
    payment_required_by_clinic: bool
    financially_ready: bool
    reason_code: str | None
    coverage_cycle_id: str | None
    needs_human_review: bool
    #: V10: được xếp phòng / bắt đầu làm chưa (``CHO_LAM_STATES``). Khác
    #: ``financially_ready`` (= tiền đã xong, chỉ để hiện nhãn "chưa thu").
    duoc_lam: bool = False

    def cho_api(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "finance_state": self.finance_state,
            "payment_required_by_clinic": self.payment_required_by_clinic,
            "financially_ready": self.financially_ready,
            "reason_code": self.reason_code,
            "coverage_cycle_id": self.coverage_cycle_id,
            "needs_human_review": self.needs_human_review,
            "duoc_lam": self.duoc_lam,
        }


def _quyet(
    f: OrderFinanceFacts,
    state: str,
    *,
    required: bool,
    reason: str | None = None,
    cycle: str | None = None,
) -> FinanceDecision:
    return FinanceDecision(
        order_id=f.order_id,
        finance_state=state,
        payment_required_by_clinic=required,
        financially_ready=state in READY_STATES,
        reason_code=reason if reason is not None else START_REASON.get(state),
        coverage_cycle_id=cycle,
        needs_human_review=state == FINANCIAL_REVIEW_REQUIRED,
        duoc_lam=cua_lam(
            state,
            thu_truoc_khi_lam=f.thu_truoc_khi_lam,
            lam_truoc_thu_sau=f.lam_truoc_thu_sau,
        ),
    )


def cua_lam(state: str, *, thu_truoc_khi_lam: bool, lam_truoc_thu_sau: bool) -> bool:
    """Cửa làm (xếp phòng / bắt đầu / hàng chờ phòng / đối tác nhận việc).

    Dây TẮT hoặc lượt đã tick → V10 (``CHO_LAM_STATES``: chưa thu vẫn làm).
    Dây BẬT + không tick → phải thu trước (``THU_TRUOC_STATES``). Hàm thuần."""
    if thu_truoc_khi_lam and not lam_truoc_thu_sau:
        return state in THU_TRUOC_STATES
    return state in CHO_LAM_STATES


def cau_chan_lam(q: FinanceDecision | None) -> str:
    """Câu cho người bấm khi cửa làm đóng — máy chủ quyết, màn hiện nguyên."""
    if q is not None and q.finance_state in (DUE, FINANCIAL_DATA_INCOMPLETE):
        return CAU_CHUA_THU
    return (
        "Tiền của dịch vụ này đang hoàn / đã hoàn hoặc sổ tiền cần đối soát — xử"
        " lý ở quầy trước khi làm."
    )


def derive_finance_state(f: OrderFinanceFacts) -> FinanceDecision:
    """Thứ tự ưu tiên đúng FINANCE-GATE §4. Hàm thuần."""
    # 0. Buổi liệu trình đã TRẢ TRƯỚC (08/10/2026, #6/#20): khách đã trả tiền
    #    buổi này = đã chốt làm — cổng mở như đã thu, kể cả khi quầy chưa bấm
    #    chốt lựa chọn (lượt Điều trị: phòng làm ngay, không cần tick). Postgres
    #    cấm dòng thu lẻ cho buổi phủ, nên không có dấu vết tiền nào cạnh tranh.
    if (
        f.phu_lieu_trinh
        and f.selection_status != "NOT_SELECTED"
        and not any(fp.cycle_status != "VOIDED" for fp in f.footprints)
    ):
        return _quyet(f, PAID, required=True)
    # 1. Khách chưa chọn làm → chưa tới bước tài chính.
    if f.selection_status != "SELECTED":
        return _quyet(f, NOT_APPLICABLE, required=False)
    # 2. Dấu vết tiền bất thường / không đủ chắc.
    if f.visit_allocation_unknown:
        return _quyet(
            f, FINANCIAL_REVIEW_REQUIRED, required=True, reason="ALLOCATION_UNKNOWN"
        )
    # Phiếu đã HUỶ chỉ còn là bản lưu để đối chiếu — không giữ phủ; bản mới
    # nhất thắng (Tuyền chốt 24/09/2026: thu nhầm → huỷ → thu lại được). Phiếu
    # đã có hoàn tiền thì không huỷ được (``void_payment``), nên ở đây không có
    # phiếu huỷ nào mang khoản hoàn.
    song = tuple(fp for fp in f.footprints if fp.cycle_status != "VOIDED")
    if len(song) > 1:
        return _quyet(
            f,
            FINANCIAL_REVIEW_REQUIRED,
            required=True,
            reason="MULTIPLE_SERVICE_COVERAGE",
        )
    if song:
        fp = song[0]
        # 3. Có khoản hoàn đang chờ.
        if fp.refund_pending_qty > 0:
            return _quyet(f, REFUND_PENDING, required=True, cycle=fp.cycle_id)
        # 4–5. Hoàn xong một phần / đủ.
        if fp.refund_completed_qty > 0:
            if fp.refund_completed_qty < fp.quantity:
                return _quyet(
                    f,
                    FINANCIAL_REVIEW_REQUIRED,
                    required=True,
                    reason="PARTIAL_REFUND",
                    cycle=fp.cycle_id,
                )
            return _quyet(f, REFUNDED, required=True, cycle=fp.cycle_id)
        # 6. (Bỏ 24/09/2026) "đã thu rồi huỷ → bắt đối soát": phiếu huỷ nay
        #    không giữ phủ, khoản quay lại DUE theo giá hiện hành bên dưới.
        # 7. Đang chờ xác minh.
        if fp.cycle_status == PENDING_VERIFICATION:
            return _quyet(f, PENDING_VERIFICATION, required=True, cycle=fp.cycle_id)
        # 8. Đã thu sạch.
        return _quyet(f, PAID, required=True, cycle=fp.cycle_id)
    # 9–12. Chưa có dấu vết tiền: theo cấu hình giá hiện hành.
    ben, don_gia, van_de = giai_gia(list(f.gia), list(f.ben_thu))
    if van_de == BEN_THU_MAU_THUAN:
        # Không chứng minh được là KHÔNG phải thu — coi như phải thu.
        return _quyet(f, FINANCIAL_DATA_INCOMPLETE, required=True)
    if ben == EXTERNAL:
        return _quyet(f, PARTNER_COLLECTS, required=False)
    if van_de or don_gia is None:
        return _quyet(f, FINANCIAL_DATA_INCOMPLETE, required=True)
    if don_gia == 0:
        return _quyet(f, NOT_REQUIRED, required=False)
    # V10 (30/09/2026) — LÀM TRƯỚC, THU SAU: đang làm / đã làm xong mà chưa có
    # tiền là CHUYỆN THƯỜNG, không còn là bất thường — vẫn là khoản phải thu
    # (DUE), vào hoá đơn quầy như mọi dịch vụ (``bill_service._CON_TINH_TIEN``).
    # Riêng DỪNG GIỮA CHỪNG mà chưa thu: chưa biết có làm tiếp hay không — để
    # người quyết (làm lại → chờ làm → lại là DUE); không tự đòi tiền khách.
    if f.execution_status == "INTERRUPTED":
        return _quyet(
            f,
            FINANCIAL_REVIEW_REQUIRED,
            required=True,
            reason="EXECUTED_WITHOUT_PAYMENT",
        )
    assert ben == CLINIC
    return _quyet(f, DUE, required=True)


#: MỘT câu cho cả lô: chỉ định + cấu hình giá hiện hành + dấu vết tiền (dòng
#: phòng khám thu trong lần thu đã từng giữ phủ) + luỹ kế hoàn từng dòng + cờ
#: lượt có tiền cũ không truy được.
_FACTS_SQL = """
WITH o AS (
    SELECT id, clinic_id, visit_id, selection_status, exec_status,
           execution_status, service_code
      FROM public.service_order
     WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])
),
gia AS (
    -- Buổi liệu trình: đơn giá CHỐT của liệu trình (cùng luật hoá đơn).
    SELECT o.id,
           CASE WHEN lt.id IS NOT NULL THEN ARRAY[lt.don_gia]
                ELSE coalesce(array_agg(pr.unit_price)
                              FILTER (WHERE pr.unit_price IS NOT NULL), '{}')
           END AS gia,
           CASE WHEN lt.id IS NOT NULL THEN ARRAY['CLINIC']::text[]
                ELSE coalesce(array_agg(DISTINCT pr.billing_owner)
                              FILTER (WHERE pr.billing_owner IS NOT NULL), '{}')
           END AS ben_thu,
           coalesce(bool_or(lb.tra_truoc), false) AS phu
      FROM o
      LEFT JOIN public.lieu_trinh_buoi lb
        ON lb.clinic_id = o.clinic_id AND lb.service_order_id = o.id
       AND lb.go_luc IS NULL
      LEFT JOIN public.lieu_trinh lt
        ON lt.clinic_id = lb.clinic_id AND lt.id = lb.lieu_trinh_id
      LEFT JOIN public.service_price pr
        ON pr.clinic_id = o.clinic_id AND pr.service_code = o.service_code
       AND pr.active AND pr."group" = 'dich_vu'
     GROUP BY o.id, lt.id, lt.don_gia
),
dau_vet AS (
    SELECT bl.source_id,
           json_agg(json_build_object(
               'line_id', bl.id,
               'cycle_id', c.payment_cycle_id,
               'cycle_status', c.status,
               'paid', c.paid_at IS NOT NULL,
               'quantity', bl.quantity,
               'refund_pending', coalesce(h.cho, 0),
               'refund_completed', coalesce(h.xong, 0))
               ORDER BY c.created_at, c.payment_cycle_id) AS fps
      FROM public.payment_bill_line bl
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
      LEFT JOIN LATERAL (
          SELECT sum(rl.quantity) FILTER (WHERE r.status = 'PENDING') AS cho,
                 sum(rl.quantity) FILTER (WHERE r.status = 'COMPLETED') AS xong
            FROM public.payment_refund_line rl
            JOIN public.payment_refund r
              ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
           WHERE rl.clinic_id = bl.clinic_id AND rl.payment_bill_line_id = bl.id
      ) h ON true
     WHERE bl.clinic_id = $1::uuid
       AND bl.source_type = 'service_order'
       AND bl.source_id IN (SELECT id::text FROM o)
       AND bl.billing_owner = 'CLINIC'
       AND (c.status = 'PENDING_VERIFICATION' OR c.paid_at IS NOT NULL)
     GROUP BY bl.source_id
),
luot_mo_ho AS (
    SELECT v.visit_id
      FROM (SELECT DISTINCT visit_id FROM o) v
     WHERE EXISTS (
               SELECT 1 FROM public.payment_cycle c
                WHERE c.clinic_id = $1::uuid AND c.visit_id = v.visit_id
                  AND c.kind = 'dich_vu'
                  AND c.status IN ('PENDING_VERIFICATION', 'PAID')
                  AND NOT EXISTS (
                      SELECT 1 FROM public.payment_bill_line bl
                       WHERE bl.clinic_id = c.clinic_id
                         AND bl.payment_cycle_id = c.payment_cycle_id))
        OR EXISTS (
               SELECT 1 FROM public.payment p
                WHERE p.clinic_id = $1::uuid AND p.visit_id = v.visit_id
                  AND p.kind = 'dich_vu'
                  AND NOT EXISTS (
                      SELECT 1 FROM public.payment_bill_line bl
                       WHERE bl.clinic_id = p.clinic_id
                         AND bl.payment_cycle_id = p.payment_cycle_id))
)
SELECT o.id::text AS id, o.selection_status, o.exec_status, o.execution_status,
       g.gia, g.ben_thu, g.phu, d.fps,
       (m.visit_id IS NOT NULL) AS mo_ho,
       (v.lam_truoc_thu_sau_luc IS NOT NULL) AS lam_truoc,
       (SELECT dn.gia_tri FROM public.day_nghiep_vu dn
         WHERE dn.clinic_id = $1::uuid AND dn.ma = $3) AS thu_truoc
  FROM o
  JOIN gia g ON g.id = o.id
  LEFT JOIN dau_vet d ON d.source_id = o.id::text
  LEFT JOIN luot_mo_ho m ON m.visit_id = o.visit_id
  LEFT JOIN public.visit v
    ON v.clinic_id = $1::uuid AND v.visit_id = o.visit_id
"""


def _footprints(raw: Any) -> tuple[Footprint, ...]:
    if raw is None:
        return ()
    items = json.loads(raw) if isinstance(raw, str) else raw
    return tuple(
        Footprint(
            line_id=str(x["line_id"]),
            cycle_id=str(x["cycle_id"]),
            cycle_status=str(x["cycle_status"]),
            paid=bool(x["paid"]),
            quantity=Decimal(str(x["quantity"])),
            refund_pending_qty=Decimal(str(x["refund_pending"])),
            refund_completed_qty=Decimal(str(x["refund_completed"])),
        )
        for x in items
    )


def _lua_chon(selection_status: str | None, *, gia_su_chon: bool) -> str | None:
    """Lựa chọn đưa vào luật tiền. ``gia_su_chon``: chỉ định còn CHỜ khách quyết
    tính như khách đã chốt làm — "nếu chốt hộ thì cửa tiền ra sao" (09/10/2026);
    khách đã chọn KHÔNG làm thì giữ nguyên."""
    if gia_su_chon and selection_status != "NOT_SELECTED":
        return "SELECTED"
    return selection_status


async def states_for_orders(
    conn: asyncpg.Connection,
    clinic_id: str,
    order_ids: Sequence[str],
    *,
    gia_su_chon: bool = False,
) -> dict[str, FinanceDecision]:
    """Trạng thái tài chính của cả lô chỉ định — ĐÚNG MỘT truy vấn.

    Gọi trong ``StartService`` thì giao dịch đã khoá lượt trước. Chỉ định không
    thuộc phòng khám này không có trong kết quả.

    ``gia_su_chon=True``: chỉ định chờ khách quyết tính như đã chốt (cửa
    "chốt hộ" khi phòng / bàn khám bắt đầu làm — ``cua_tien_chot_ho``).
    """
    ids = sorted({str(i) for i in order_ids})
    if not ids:
        return {}
    rows = await conn.fetch(_FACTS_SQL, clinic_id, ids, DAY_THU_TRUOC)
    return {
        r["id"]: derive_finance_state(
            OrderFinanceFacts(
                order_id=r["id"],
                selection_status=_lua_chon(
                    r["selection_status"], gia_su_chon=gia_su_chon
                ),
                exec_status=r["exec_status"],
                execution_status=r["execution_status"],
                gia=tuple(r["gia"]),
                ben_thu=tuple(r["ben_thu"]),
                footprints=_footprints(r["fps"]),
                visit_allocation_unknown=bool(r["mo_ho"]),
                thu_truoc_khi_lam=bool(giai_gia_tri(DAY_THU_TRUOC, r["thu_truoc"])),
                lam_truoc_thu_sau=bool(r["lam_truoc"]),
                phu_lieu_trinh=bool(r["phu"]),
            )
        )
        for r in rows
    }


async def can_start(
    conn: asyncpg.Connection, clinic_id: str, order_id: str
) -> FinanceDecision | None:
    """ "Về tài chính có được Start chưa?" — chính đường lô, một phần tử."""
    return (await states_for_orders(conn, clinic_id, [order_id])).get(str(order_id))
