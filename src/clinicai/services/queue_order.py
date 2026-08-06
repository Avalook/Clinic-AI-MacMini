"""Luật THỨ TỰ GỌI của phòng khám — nguồn sự thật duy nhất.

Trước đây luật này có HAI bản: bản Python ở đây và một bản TypeScript chép lại ở
`src/dashboard/lib/queue.ts` mà ba màn nhân viên đang dùng. Hôm nay chúng giống
nhau, nhưng không có gì ràng buộc — sửa một bên là hai bảng nói khác nhau mà
không ai biết. Bản TypeScript đã bị xoá; mọi thứ tự đều tính ở đây.

Hàm trong module này THUẦN: không I/O, không await, không chạm database. Cấu
hình đi vào bằng tham số. Cách hỏng dễ nhất là ai đó thêm một lượt tra chính
sách vào `call_rank` cho tiện — `test_queue_order.py` có bài canh chặn đúng việc
đó.

Luật (Model ②, chốt 2026-06-26): SỐ VÉ ĐỊNH DANH NGƯỜI BỆNH, KHÔNG QUYẾT THỨ TỰ
GỌI. Bốn làn:

  -2  ƯT (người quen)                        xếp theo số vé
  -1  Kết quả XN/SA đã về → vào lại          xếp theo GIỜ ĐẾN
   0  Có hẹn và đến trong khung của mình     xếp theo GIỜ HẸN
   1  Vãng lai, hoặc có hẹn nhưng đến muộn   xếp theo GIỜ ĐẾN

(Dòng chưa check-in rơi về thứ tự số vé thuần.)

CỬA SỔ "ĐẾN ĐÚNG GIỜ" DÀI BẰNG KHUNG GIỜ, KHÔNG PHẢI MỘT HẰNG SỐ. Trước đây nó
là `LATE_GRACE_MS = 10 phút` viết cứng. Với khung 15 phút, người check-in ở phút
thứ 12 — vẫn đang trong khung 18:00–18:15 của chính mình — bị đẩy xuống làn vãng
lai. Với khung 30 phút thì lệch tới 20 phút. Độ dài khung do Quản lý cấu hình
(`clinic.settings->booking->slot_minutes`, đè được theo bác sĩ qua
`doctor_booking_override`), nên cửa sổ phải đi theo nó.

`grace_ms` KHÔNG CÓ GIÁ TRỊ MẶC ĐỊNH, và nằm trên TỪNG DÒNG chứ không phải một
tham số chung cho cả danh sách. Hai lý do:

  · Không có con số nào hợp lý để đoán "khung dài bao lâu". Một mặc định ở đây
    là một cách im lặng để xếp sai hàng khi ai đó quên nối dây.
  · `doctor_booking_override` cho phép hai bác sĩ có độ dài khung khác nhau
    trong cùng một buổi, nên một con số cho cả bảng sẽ sai cho ít nhất một
    người.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

_UT_RE = re.compile(r"(?:Ư|U)\s*T\s*0*(\d*)", re.IGNORECASE)
_INT_RE = re.compile(r"[+-]?\d+")

# Lý do một người đứng ở vị trí đó — để màn hình NÓI ĐƯỢC, không chỉ xếp được.
# Màn tivi phải giải thích cho người ngồi chờ vì sao ai đó vượt lên trước mình.
REASON_UU_TIEN = "UU_TIEN"  # vé ƯT
REASON_CHO_DOC_KQ = "CHO_DOC_KQ"  # xét nghiệm/siêu âm đã về, vào lại
REASON_DAT_TRUOC_DUNG_GIO = "DAT_TRUOC_DUNG_GIO"  # có hẹn, đến trong khung
REASON_DEN_TRUC_TIEP = "DEN_TRUC_TIEP"  # vãng lai
REASON_DEN_TRE = "DEN_TRE"  # có hẹn nhưng đến sau khung
REASON_CHUA_DEN = "CHUA_DEN"  # chưa check-in


def _ms(d: datetime) -> int:
    return int(d.timestamp() * 1000)


def _iso(d: datetime | None) -> str:
    return d.isoformat() if d else ""


def _ut_num(queue_number: str | None) -> int | None:
    """ƯT ticket → its number (0 if bare 'ƯT'); None if not a ƯT ticket."""
    s = (queue_number or "").strip()
    m = _UT_RE.match(s)
    if m:
        return int(m.group(1)) if m.group(1) else 0
    return None


def queue_rank(queue_number: str | None, slot_iso: str) -> tuple[int, int, str]:
    """Plain ticket ordering: ƯT first, then numeric tickets, then the rest."""
    n = _ut_num(queue_number)
    if n is not None:
        return (0, n, slot_iso)
    m = _INT_RE.match((queue_number or "").strip())
    if m:
        return (1, int(m.group()), slot_iso)
    return (2, 0, slot_iso)


@dataclass(frozen=True)
class QueueEntry:
    appointment_id: str
    doctor_id: str | None
    queue_number: str | None
    slot_start: datetime
    checked_in_at: datetime | None
    booking_channel: str | None
    # Cửa sổ "đến đúng giờ" của CHÍNH lượt này, tính bằng mili giây — bằng độ
    # dài khung giờ mà Quản lý cấu hình cho bác sĩ đó vào thời điểm đó.
    #
    # KHÔNG CÓ MẶC ĐỊNH, và đứng trước các trường có mặc định. Cố ý: người thêm
    # một nơi gọi mới sẽ bị TypeError ngay, thay vì lặng lẽ xếp hàng theo một
    # con số đoán mò.
    grace_ms: int
    b3_ready: bool = False
    visit_status: str | None = None


@dataclass(frozen=True)
class QueueDecision:
    """Một dòng trong hàng chờ, kèm LỜI GIẢI THÍCH vì sao nó đứng ở đó.

    Bảng gọi số không chỉ cần xếp đúng — nó phải trả lời được câu hỏi của người
    ngồi chờ: *"vì sao người kia vào trước tôi?"*. Không có `call_reason` thì
    câu trả lời duy nhất màn hình đưa ra được là im lặng.
    """

    entry: QueueEntry
    call_order: int  # vị trí trong hàng, 0 là người được gọi tiếp theo
    call_tier: int  # làn: -2 ƯT · -1 chờ đọc KQ · 0 đúng hẹn · 1 đến sau
    call_reason: str  # một trong các REASON_* ở đầu module
    # "Được đẩy lên" = có ít nhất một người ĐẾN TRƯỚC mình mà bị xếp SAU mình.
    # Đây đúng là tình huống cần giải thích trên tivi, và cũng đúng là tình
    # huống duy nhất khiến người đến trước thấy khó hiểu.
    promoted: bool
    promoted_over: int


def _classify(e: QueueEntry) -> tuple[tuple[int, float, str], str]:
    """Khoá sắp xếp VÀ lý do, sinh ra cùng một lúc.

    Hai thứ này phải đi cùng nhau. Tách thành hai hàm là mở đường cho việc màn
    hình dán một câu giải thích không khớp với thứ tự thật — thứ sai lầm mà
    không bài kiểm nào bắt được vì cả hai đều "chạy đúng".
    """
    slot_iso = _iso(e.slot_start)

    # -1: kết quả xét nghiệm/siêu âm đã về → vào lại trước hàng mới.
    if e.b3_ready:
        in_ms = _ms(e.checked_in_at) if e.checked_in_at else _ms(e.slot_start)
        return (-1, in_ms, _iso(e.checked_in_at) or slot_iso), REASON_CHO_DOC_KQ

    # Dòng chưa check-in, chưa có kênh đặt → thứ tự số vé thuần.
    if e.booking_channel is None and e.checked_in_at is None:
        return queue_rank(e.queue_number, slot_iso), REASON_CHUA_DEN

    # -2: ƯT (người quen).
    n = _ut_num(e.queue_number)
    if n is not None:
        return (-2, n, slot_iso), REASON_UU_TIEN

    slot_ms = _ms(e.slot_start)
    is_booked = bool(e.booking_channel) and e.booking_channel != "WALK_IN"

    # 0: có hẹn và đến TRONG KHUNG CỦA MÌNH → xếp theo giờ hẹn.
    if is_booked and e.checked_in_at is not None:
        in_ms = _ms(e.checked_in_at)
        if in_ms <= slot_ms + e.grace_ms:
            return (0, float(slot_ms), _iso(e.checked_in_at)), (
                REASON_DAT_TRUOC_DUNG_GIO
            )

    # 1: vãng lai, hoặc có hẹn nhưng đến sau khung → xếp theo giờ đến.
    arrive_ms = _ms(e.checked_in_at) if e.checked_in_at else slot_ms
    key = (1, float(arrive_ms), _iso(e.checked_in_at) or slot_iso)
    return key, (REASON_DEN_TRE if is_booked else REASON_DEN_TRUC_TIEP)


def call_rank(e: QueueEntry) -> tuple[int, float, str]:
    """Khoá sắp xếp cho một người ĐÃ check-in (nhỏ hơn = gọi sớm hơn)."""
    return _classify(e)[0]


def call_reason(e: QueueEntry) -> str:
    """Vì sao người này đứng ở làn đó — một trong các REASON_*."""
    return _classify(e)[1]


def explain_queue(entries: list[QueueEntry]) -> list[QueueDecision]:
    """Xếp hàng VÀ giải thích, trong một lượt.

    `promoted_over` đếm số người đến trước mà bị xếp sau mình. Chỉ tính những
    người ĐÃ check-in: người chưa đến thì chưa "đến trước" ai cả, và đếm họ vào
    sẽ dán nhãn "được đẩy lên" cho gần như mọi người.
    """
    ranked = sorted(entries, key=call_rank)

    out: list[QueueDecision] = []
    for i, e in enumerate(ranked):
        key, reason = _classify(e)
        over = 0
        if e.checked_in_at is not None:
            mine = _ms(e.checked_in_at)
            over = sum(
                1
                for other in ranked[i + 1 :]
                if other.checked_in_at is not None and _ms(other.checked_in_at) < mine
            )
        out.append(
            QueueDecision(
                entry=e,
                call_order=i,
                call_tier=key[0],
                call_reason=reason,
                promoted=over > 0,
                promoted_over=over,
            )
        )
    return out


def order_queue(entries: list[QueueEntry]) -> list[QueueEntry]:
    """Return entries sorted by call order (stable)."""
    return sorted(entries, key=call_rank)


def b3_ready_appt_ids(labs: list[dict[str, object]]) -> set[str]:
    """Appointment ids with ≥1 resulted lab and 0 pending (ready to re-enter).

    A lab is 'resulted' when it has a result_value or an external_ref.
    """
    resulted: dict[str, int] = {}
    pending: dict[str, int] = {}
    for lab in labs:
        appt = str(lab.get("appointment_id") or "")
        if not appt:
            continue
        has_result = bool(str(lab.get("result_value") or "").strip()) or bool(
            str(lab.get("external_ref") or "").strip()
        )
        (resulted if has_result else pending)[appt] = (
            resulted if has_result else pending
        ).get(appt, 0) + 1
    return {appt for appt, n in resulted.items() if n > 0 and pending.get(appt, 0) == 0}
