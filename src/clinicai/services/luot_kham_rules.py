"""Luật THUẦN của luồng khám lát 1 — không I/O, không await, không database.

Mỗi hàm là một câu trong contract (DANH-GIA-THIET-KE-CLAUDE-20260911-v2 §3)
viết thành code, để test được từng câu mà không cần dựng Postgres. Service
đọc dữ liệu, gọi các hàm này để QUYẾT, rồi ghi.

Hàm nhận dữ liệu người dùng (``parse_vitals``) trả câu lỗi thay vì ném —
cùng luật với mọi hàm nhận ngày/giờ trong repo: đầu vào rác là chuyện thường,
không phải lỗi máy chủ.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# D1 — đích tiếp theo sau check-in
# ---------------------------------------------------------------------------

PRIMARY = "PRIMARY"
SERVICES = "SERVICES"

PLAN_STATUSES = frozenset({"none", "pending", "applied", "rejected", "abandoned"})


def decide_route(
    *, vitals_recorded: bool, plan_status: str, current_route: str | None
) -> str | None:
    """Đích MỚI cần ghi, hoặc None khi chưa đủ điều kiện hay đã có đích.

    Chạy lại bao nhiêu lần cũng ra cùng kết quả. Đích chỉ ghi một lần (I10):
    kế hoạch hợp lệ đến muộn không kéo khách đã vào bác sĩ sang dịch vụ.

    SINH HIỆU KHÔNG CÒN LÀ CỬA (luồng chuẩn bước 6, Tuyền chốt 23/09/2026):
    *"có đo cũng chả sao, vẫn có event phát ra cho điều dưỡng, không làm cũng
    không sai"*. Đích quyết ngay lúc check-in; điều dưỡng vẫn thấy khách ở hàng
    đo sinh hiệu. `vitals_recorded` giữ trong chữ ký để người gọi cũ không vỡ.
    """
    _ = vitals_recorded
    if plan_status not in PLAN_STATUSES:
        raise ValueError(f"plan_check_status không hợp lệ: {plan_status!r}")
    if current_route is not None:
        return None
    if plan_status == "pending":
        return None
    if plan_status == "applied":
        return SERVICES
    return PRIMARY


# ---------------------------------------------------------------------------
# D2 — vòng đọc kết quả đã sẵn sàng chưa
# ---------------------------------------------------------------------------

NEEDS = frozenset({"PERFORMED", "VALID_RESULT"})
#: Mức thứ ba khi kết thúc phiên: KHÔNG giữ lượt chờ. Không thành yêu cầu của
#: vòng đọc mà thành một ``follow_up_case`` có người phụ trách và hạn (Slice 1).
FOLLOW_UP = "FOLLOW_UP"
PLAN_NEEDS = NEEDS | {FOLLOW_UP}
#: Chỉ định đã dừng mà không làm được — yêu cầu trỏ vào nó không bao giờ tự đạt.
KHONG_THUC_HIEN = frozenset({"not_performed", "cancelled"})


@dataclass(frozen=True)
class RequirementView:
    """Một yêu cầu của vòng đọc, kèm trạng thái THỰC HIỆN của chỉ định nó trỏ tới."""

    order_id: str
    need: str
    status: str
    exec_status: str
    has_valid_result: bool = False


def requirement_met(req: RequirementView) -> bool:
    """Yêu cầu đã thoả theo dữ liệu chưa. Miễn (waived) KHÔNG tính ở đây."""
    if req.need not in NEEDS:
        raise ValueError(f"need không hợp lệ: {req.need!r}")
    if req.exec_status != "performed":
        return False
    if req.need == "PERFORMED":
        return True
    return req.has_valid_result


def requirement_state(req: RequirementView) -> str:
    """Một yêu cầu đang ở đâu: ``satisfied`` | ``open`` | ``needs_decision`` |
    ``waived`` | ``follow_up``.

    ``needs_decision``: chỉ định trỏ tới đã KHÔNG THỰC HIỆN (hay bị huỷ). Nó
    không bao giờ tự đạt — bác sĩ phải miễn (có lý do) hoặc chuyển theo dõi.
    """
    if req.status in ("waived", "follow_up"):
        return req.status
    if req.exec_status in KHONG_THUC_HIEN:
        return "needs_decision"
    return "satisfied" if requirement_met(req) else "open"


def round_ready(reqs: Sequence[RequirementView]) -> bool:
    """Sẵn sàng khi không còn yêu cầu nào đang CHỜ (làm hoặc kết quả).

    Yêu cầu cần bác sĩ quyết (không thực hiện được) KHÔNG giữ vòng lại: khách
    quay về bác sĩ để bác sĩ quyết, thay vì kẹt mãi ở "đang thu" mà không ai
    thấy. Nhưng nó cũng không được tính là đạt — ``can_quyet`` chặn đóng vòng
    cho tới khi bác sĩ quyết.

    Tập rỗng KHÔNG BAO GIỜ sẵn sàng (I5). "Mọi phần tử của tập rỗng đều thoả"
    đúng về logic nhưng sai về nghiệp vụ: nó tự sinh một lần gọi bác sĩ không ai
    yêu cầu.
    """
    if not reqs:
        return False
    return all(requirement_state(r) != "open" for r in reqs)


def vong_khong_can_doc(reqs: Sequence[RequirementView]) -> bool:
    """Mọi yêu cầu đã được bác sĩ miễn hoặc chuyển theo dõi: không có gì để đọc.

    Khi ấy vòng đóng luôn, khách không phải quay lại bác sĩ — đúng nghĩa
    FOLLOW_UP "không giữ lượt chờ". Tập rỗng không tính.
    """
    return bool(reqs) and all(
        requirement_state(r) in ("waived", "follow_up") for r in reqs
    )


def can_quyet(reqs: Sequence[RequirementView]) -> list[str]:
    """Chỉ định mà bác sĩ còn phải quyết trước khi đóng vòng đọc."""
    return [r.order_id for r in reqs if requirement_state(r) == "needs_decision"]


def need_mac_dinh(*, lam_ben_ngoai: bool | None, flow_group: str | None) -> str:
    """Mức cần mặc định khi bác sĩ bấm "Đã khám xong" mà không chọn từng dịch vụ.

    Dịch vụ LÀM BÊN NGOÀI (lấy mẫu gửi đối tác, chụp chiếu ngoài) hoặc thuộc
    nhóm KẾT QUẢ (tinh dịch đồ…) cho ra kết quả SAU khi làm: lấy mẫu xong chưa
    có gì cho bác sĩ đọc, nên cần kết quả hợp lệ. Thủ thuật, siêu âm, DXA… ra
    kết quả ngay khi làm: làm xong là đủ.
    """
    if lam_ben_ngoai or flow_group == "ket_qua":
        return "VALID_RESULT"
    return "PERFORMED"


def tach_ke_hoach(
    items: Iterable[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[str]]:
    """(yêu cầu của vòng đọc, chỉ định chuyển theo dõi) từ kế hoạch bác sĩ chọn."""
    reqs: list[tuple[str, str]] = []
    theo_doi: list[str] = []
    for oid, need in items:
        if need not in PLAN_NEEDS:
            raise ValueError(f"need không hợp lệ: {need!r}")
        if need == FOLLOW_UP:
            theo_doi.append(oid)
        else:
            reqs.append((oid, need))
    return reqs, theo_doi


def doc_han_theo_doi(raw: Any) -> date | None:
    """Hạn theo dõi dạng YYYY-MM-DD, hoặc None khi rỗng/rác. Không ném."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def cyclic_orders(
    round_no: int, required: Iterable[tuple[str, int | None]]
) -> list[str]:
    """Chỉ định vừa là yêu cầu của vòng ``round_no`` vừa bị giữ tới vòng ấy đóng.

    Vòng chờ chỉ định, chỉ định chờ vòng: không bên nào đi tiếp (I6, T-V4).
    """
    return [oid for oid, hold in required if hold is not None and hold >= round_no]


# ---------------------------------------------------------------------------
# C7 — chỉ định này điều phối được chưa
# ---------------------------------------------------------------------------

DISPATCHABLE = frozenset({"authorized", "assigned"})


def dispatch_block(
    *,
    exec_status: str,
    source: str,
    authorized_by: str | None,
    plan_applied: bool,
    route_decision: str | None,
    vitals_recorded: bool,
    hold_until_round: int | None,
    closed_rounds: set[int],
) -> str | None:
    """Mã lý do chặn, hoặc None khi điều phối được.

    Thứ tự kiểm có chủ ý: chỉ định chưa được bác sĩ duyệt thì nói điều đó trước
    mọi thứ khác (I1); sinh hiệu kiểm TRƯỚC đích, nên kế hoạch áp trước khi đo
    huyết áp vẫn bị chặn bằng đúng lý do người dùng cần nghe (T-P9).
    """
    if exec_status == "draft" or authorized_by is None:
        return "NO_VALID_ORDER"
    if exec_status not in DISPATCHABLE:
        return "ORDER_NOT_DISPATCHABLE"
    if source == "PRIOR_PLAN" and not plan_applied:
        return "PLAN_NOT_APPLIED"
    return routing_hold_block(
        source=source,
        route_decision=route_decision,
        vitals_recorded=vitals_recorded,
        hold_until_round=hold_until_round,
        closed_rounds=closed_rounds,
    )


def vitals_routing_block(*, vitals_recorded: bool) -> str | None:
    """SEAM có tên cho luật "sinh hiệu có chặn điều phối không".

    ĐÃ CHỐT 23/09/2026 — Tuyền: **KHÔNG chặn**. Chưa đo sinh hiệu vẫn đưa khách
    vào phòng dịch vụ được; màn hình chỉ nhắc.

    Vì sao đổi: code cũ chặn khi chưa đo huyết áp, nhưng đó là giả định của phần
    mềm chứ không phải luật của phòng khám — khách đi thẳng làm siêu âm hay thủ
    thuật là chuyện thường ngày, và chặn ở đây biến một lời nhắc thành một cánh
    cửa khoá giữa giờ cao điểm.

    Hàm giữ nguyên (không xoá) vì nó là chỗ DUY NHẤT trả lời câu hỏi ấy: ngày nào
    phòng khám muốn chặn lại thì sửa đúng một chỗ này, không phải đi tìm những
    lần kiểm sinh hiệu rải rác.
    """
    _ = vitals_recorded  # giữ chữ ký: người gọi vẫn truyền, luật đổi ở đây
    return None


def routing_hold_block(
    *,
    source: str,
    route_decision: str | None,
    vitals_recorded: bool,
    hold_until_round: int | None,
    closed_rounds: set[int],
) -> str | None:
    """Chốt giữ (hold) chuyên môn / vận hành trước khi xếp phòng — MỘT chính sách
    có tên, dùng chung cho điều phối cũ và AssignServiceRoom (ROUTING §5).

    Thứ tự giữ như ``dispatch_block``: sinh hiệu (seam) → đích của lượt → kế
    hoạch trước → dặn làm sau vòng đọc.
    """
    vitals = vitals_routing_block(vitals_recorded=vitals_recorded)
    if vitals:
        return vitals
    if route_decision is None:
        return "ROUTE_NOT_DECIDED"
    if source == "PRIOR_PLAN" and route_decision != SERVICES:
        return "PLAN_NOT_APPLIED"
    if hold_until_round is not None and hold_until_round not in closed_rounds:
        return "HELD_UNTIL_ROUND"
    return None


# ---------------------------------------------------------------------------
# Hàng chờ
# ---------------------------------------------------------------------------

LIVE_QUEUE_STATUSES = ("blocked", "waiting", "called", "serving")
_STATUS_RANK = {"serving": 0, "called": 1, "waiting": 2, "blocked": 3}


@dataclass(frozen=True)
class QueueView:
    id: str
    status: str
    eligible_at: datetime | None
    created_at: datetime


def initial_queue_status(*, visit_busy: bool) -> str:
    """Vào hàng khi khách đang ở chỗ khác thì CHỜ MỞ, chưa gọi được (I9)."""
    return "blocked" if visit_busy else "waiting"


def order_queue(entries: Iterable[QueueView]) -> list[QueueView]:
    """Thứ tự gọi của MỘT hàng: đang phục vụ, đã gọi, rồi chờ theo ``eligible_at``.

    Không làn ưu tiên tự động, không xếp theo giờ hẹn (S4). Khách quay lại sau
    dịch vụ có ``eligible_at`` là lúc quay lại, nên đứng sau người đang chờ và
    trước người vào sau (T-A14).
    """
    live = [e for e in entries if e.status in _STATUS_RANK]
    return sorted(
        live,
        key=lambda e: (
            _STATUS_RANK[e.status],
            e.eligible_at or e.created_at,
            e.created_at,
            e.id,
        ),
    )


# ---------------------------------------------------------------------------
# Phiên khám
# ---------------------------------------------------------------------------

OUTCOMES_BY_KIND = {
    "PRIMARY": frozenset({"NO_SERVICES", "SERVICES"}),
    "REVIEW": frozenset({"DONE", "MORE_SERVICES"}),
}
OUTCOMES_OPENING_ROUND = frozenset({"SERVICES", "MORE_SERVICES"})


def outcome_allowed(kind: str, outcome: str) -> bool:
    return outcome in OUTCOMES_BY_KIND.get(kind, frozenset())


# ---------------------------------------------------------------------------
# Sinh hiệu
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Vitals:
    systolic: int
    diastolic: int
    pulse: int | None = None
    temperature: Decimal | None = None
    weight_kg: Decimal | None = None
    height_cm: Decimal | None = None
    # Bốn chỉ số thêm 16/09/2026 — trước đó có ô nhập trên màn nhưng không có
    # cột, nên chúng rơi vào JSONB hồ sơ và không vào lịch sử đo được.
    respiratory_rate: int | None = None
    spo2: int | None = None
    bmi: Decimal | None = None
    pain_score: int | None = None


_RANGES: dict[str, tuple[str, Decimal, Decimal]] = {
    "systolic": ("Huyết áp tâm thu", Decimal(50), Decimal(260)),
    "diastolic": ("Huyết áp tâm trương", Decimal(30), Decimal(180)),
    "pulse": ("Mạch", Decimal(20), Decimal(250)),
    "temperature": ("Nhiệt độ", Decimal(34), Decimal(43)),
    "weight_kg": ("Cân nặng", Decimal(1), Decimal(300)),
    "height_cm": ("Chiều cao", Decimal(30), Decimal(230)),
    # Cùng khoảng với CHECK ở database (20260916000003). Hai nơi phải khớp:
    # rộng hơn ở đây là để người đo gõ xong mới bị máy chủ từ chối.
    "respiratory_rate": ("Nhịp thở", Decimal(4), Decimal(80)),
    "spo2": ("SpO₂", Decimal(50), Decimal(100)),
    "pain_score": ("Mức độ đau", Decimal(0), Decimal(10)),
}

#: Chỉ số phải là số nguyên — đo bằng máy đếm, không có phần thập phân.
_NGUYEN: tuple[str, ...] = (
    "systolic",
    "diastolic",
    "pulse",
    "respiratory_rate",
    "spo2",
    "pain_score",
)


def _number(value: Any) -> Decimal | None:
    """Số từ đầu vào người dùng, hoặc None nếu không đọc được. Không ném."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        raw = str(value)
    elif isinstance(value, str):
        raw = value.strip().replace(",", ".")
        if not raw:
            return None
    else:
        return None
    try:
        num = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    return num if num.is_finite() else None


def thieu_sinh_hieu_khi_co_thai(vitals: Vitals, *, co_thai: bool) -> str | None:
    """Câu nhắc khi khách đang có thai mà thiếu chiều cao/cân nặng; đủ → None.

    Luật PM (CONTEXT v1.0): khách có thai đo thêm chiều cao và cân nặng.
    "Báo sốt thì đo nhiệt độ" CHƯA ép: chưa có dữ kiện "khách báo sốt" có cấu
    trúc, và không đoán từ chữ lý do khám.
    """
    if not co_thai:
        return None
    thieu = [
        nhan
        for gia_tri, nhan in (
            (vitals.height_cm, "chiều cao"),
            (vitals.weight_kg, "cân nặng"),
        )
        if gia_tri is None
    ]
    if not thieu:
        return None
    return "Khách đang có thai — sinh hiệu cần thêm " + " và ".join(thieu) + "."


def parse_vitals(raw: Any) -> tuple[Vitals | None, str | None]:
    """(Vitals, None) khi hợp lệ; (None, câu lỗi tiếng Việt) khi không.

    Huyết áp bắt buộc cho MỌI lượt (I8, tiêu chí "100% BN đc đo huyết áp").
    Các chỉ số khác tuỳ chọn; bộ bắt buộc theo dịch vụ còn chờ chốt (O5).
    """
    if not isinstance(raw, dict):
        return None, "Dữ liệu sinh hiệu không đúng dạng."
    values: dict[str, Decimal | None] = {}
    for field, (label, low, high) in _RANGES.items():
        given = raw.get(field)
        num = _number(given)
        if given not in (None, "") and num is None:
            return None, f"{label} phải là một con số."
        if num is not None and not (low <= num <= high):
            return None, f"{label} phải trong khoảng {low}–{high}."
        values[field] = num
    systolic, diastolic = values["systolic"], values["diastolic"]
    if systolic is None or diastolic is None:
        return None, "Phải đo huyết áp (tâm thu và tâm trương) cho mọi lượt khám."
    for field in _NGUYEN:
        num = values[field]
        if num is not None and num != num.to_integral_value():
            return None, f"{_RANGES[field][0]} phải là số nguyên."
    if systolic <= diastolic:
        return None, "Huyết áp tâm thu phải lớn hơn tâm trương."

    def _int(ten: str) -> int | None:
        num = values[ten]
        return int(num) if num is not None else None

    # BMI CHỈ TÍNH RA, không nhận từ client (S0-3, 18/09/2026). Trước đó màn đo
    # cho gõ tay BMI và số gõ tay thắng số tính — BMI 99 với 54 kg/160 cm vẫn
    # vào hồ sơ. Khoảng 5–100 khớp CHECK ở database (20260916000003).
    bmi: Decimal | None = None
    can, cao = values["weight_kg"], values["height_cm"]
    if can is not None and cao is not None and cao > 0:
        tinh = (can / ((cao / 100) ** 2)).quantize(Decimal("0.1"))
        if Decimal(5) <= tinh <= Decimal(100):
            bmi = tinh

    return (
        Vitals(
            systolic=int(systolic),
            diastolic=int(diastolic),
            pulse=_int("pulse"),
            temperature=values["temperature"],
            weight_kg=values["weight_kg"],
            height_cm=values["height_cm"],
            respiratory_rate=_int("respiratory_rate"),
            spo2=_int("spo2"),
            bmi=bmi,
            pain_score=_int("pain_score"),
        ),
        None,
    )


# ---------------------------------------------------------------------------
# Đổi phòng dịch vụ — ai có quyền điều phối cũng làm được (23/09/2026)
# ---------------------------------------------------------------------------

_DA_LAM_HOAC_XONG = frozenset(
    {"in_progress", "performed", "not_performed", "cancelled"}
)
_THUC_HIEN_KHONG_DOI = frozenset(
    {"IN_PROGRESS", "COMPLETED", "CANCELLED", "NOT_PERFORMED"}
)


def doi_phong_duoc(
    *,
    selection_status: str | None,
    execution_status: str | None,
    exec_status: str | None,
    doi_tac: bool,
) -> bool:
    """Chỉ định này đổi phòng được không — để màn hình biết có bày nút.

    Luồng chuẩn bước 7 (Tuyền chốt 23/09/2026): khách trả tiền dịch vụ thực làm
    xong, phòng còn ổn thì đi, đầy thì lễ tân (hay điều dưỡng, thư ký, bác sĩ —
    ai có quyền điều phối) đổi sang phòng vắng hơn cùng chức năng.

    Chỉ là GỢI Ý hiển thị: lệnh `AssignServiceRoom` vẫn tự kiểm đủ (đã chọn, đã
    qua cổng tiền, chưa bắt đầu, revision) và nói lý do nếu từ chối.
    """
    if doi_tac:
        return False  # đối tác làm — không có phòng của phòng khám để xếp
    if selection_status != "SELECTED":
        return False  # khách chưa chọn làm dịch vụ này (chưa qua quầy)
    if (execution_status or "") in _THUC_HIEN_KHONG_DOI:
        return False
    return (exec_status or "") not in _DA_LAM_HOAC_XONG
