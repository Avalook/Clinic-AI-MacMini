"""Luật THỨ TỰ GỌI của phòng khám — nguồn sự thật duy nhất.

Trước đây luật này có HAI bản: bản Python ở đây và một bản TypeScript chép lại ở
`src/dashboard/lib/queue.ts` mà ba màn nhân viên đang dùng. Hôm nay chúng giống
nhau, nhưng không có gì ràng buộc — sửa một bên là hai bảng nói khác nhau mà
không ai biết. Bản TypeScript đã bị xoá; mọi thứ tự đều tính ở đây.

Hàm trong module này THUẦN: không I/O, không await, không chạm database. Cấu
hình đi vào bằng tham số. Cách hỏng dễ nhất là ai đó thêm một lượt tra chính
sách vào `call_rank` cho tiện — `test_queue_order.py` có bài canh chặn đúng việc
đó.

Luật: SỐ VÉ ĐỊNH DANH NGƯỜI BỆNH, KHÔNG QUYẾT THỨ TỰ GỌI.

  0  Đã check-in (có hẹn hay đến thẳng)     xếp theo GIỜ CHECK-IN
  ↩  Quay lại đọc kết quả                   CHÈN SAU mọi người đã chờ lúc kết
                                            quả về, TRƯỚC người vào hàng sau
  1  Chưa check-in                          theo giờ hẹn (chỉ để hiển thị)

(Dòng chưa check-in rơi về thứ tự số vé thuần.)

ĐỔI 15/09/2026 theo CONTEXT v1.0 — hai làn tự vượt của Model ② (26/06) bị bỏ:

  · Vé ƯT KHÔNG còn tự lên đầu. [CHỐT-TUYỀN] "VIP/ưu tiên có lý do; … không tự
    biến thành quyền vượt hàng." Vé ƯT giờ chỉ là NHÃN (`uu_tien` trên
    QueueDecision) — người đó xếp theo làn của chính họ. Đẩy ai lên phải là
    thao tác của nhân viên, có lý do, có vết (chưa có — việc riêng).
  · Kết quả về KHÔNG còn vượt mọi người. [CHỐT-TUYỀN] "Quay lại đọc kết quả xếp
    sau người đã chờ tại hàng đó và trước người đủ điều kiện vào hàng sau; không
    tự chen ngang." Mốc "đủ điều kiện" = lúc kết quả cuối cùng về
    (`b3_ready_at`); việc chèn là của CẢ DANH SÁCH nên nằm ở `explain_queue`,
    không ở khoá từng dòng.

  · Khách có hẹn KHÔNG còn đứng trước khách đến thẳng. CONTEXT v1.0 §6 từng ghi
    [CHƯA RÕ] (PM v1.0.0: có hẹn phát số trước khi trùng khung); Tuyền CHỐT
    15/09/2026: "không phân biệt nữa, cứ ai đến check-in trước thì người đó
    khám trước". Làn "đúng hẹn theo giờ hẹn" bị bỏ; giờ hẹn và độ dài khung
    (`grace_ms`) chỉ còn dùng để GỌI TÊN lý do (đúng giờ / đến trễ / vãng lai)
    trên màn hình, không quyết định chỗ đứng.

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

_INT_RE = re.compile(r"[+-]?\d+")

# Lý do một người đứng ở vị trí đó — để màn hình NÓI ĐƯỢC, không chỉ xếp được.
# Màn tivi phải giải thích cho người ngồi chờ vì sao ai đó vượt lên trước mình.
# Vé ƯT. Từ 15/09 KHÔNG còn là một làn — không `_classify` nào trả mã này nữa;
# giữ hằng số vì màn hình/bài kiểm cũ còn tham chiếu. Nhãn ưu tiên nằm ở
# `QueueDecision.uu_tien`.
REASON_UU_TIEN = "UU_TIEN"
REASON_CHO_DOC_KQ = "CHO_DOC_KQ"  # xét nghiệm/siêu âm đã về, vào lại
REASON_DAT_TRUOC_DUNG_GIO = "DAT_TRUOC_DUNG_GIO"  # có hẹn, đến trong khung
REASON_DEN_TRUC_TIEP = "DEN_TRUC_TIEP"  # vãng lai
REASON_DEN_TRE = "DEN_TRE"  # có hẹn nhưng đến sau khung
REASON_CHUA_DEN = "CHUA_DEN"  # chưa check-in

# Trạng thái LƯỢT KHÁM có nghĩa là "người này không còn ngồi chờ nữa".
#
# Một nguồn duy nhất, vì cùng một danh sách phải đúng ở ba chỗ: hàng chờ của Lễ
# tân, bảng gọi số trên tivi, và bảng điều phối. Sót một chỗ là người đã ra về
# vẫn nằm trong hàng và vẫn được gọi tên.
#
# INCOMPLETE nằm ở đây dù nó KHÔNG phải trạng thái cuối: khách về giữa chừng thì
# không còn chờ, kể cả khi hồ sơ của họ vẫn ghi tiếp được lúc quay lại.
VISIT_DA_RA_VE: frozenset[str] = frozenset({"INCOMPLETE", "FINALIZED", "AMENDED"})


def _ms(d: datetime) -> int:
    return int(d.timestamp() * 1000)


def _iso(d: datetime | None) -> str:
    return d.isoformat() if d else ""


def queue_rank(queue_number: str | None, slot_iso: str) -> tuple[int, int, str]:
    """Plain ticket ordering: numeric tickets first, then the rest.

    Vé "ƯT…" không còn hạng riêng (Tuyền chốt 15/09/2026: bỏ ghế/vé ưu tiên —
    ưu tiên là cờ trên hồ sơ khách, lễ tân tự kéo thứ tự).
    """
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
    # Lúc kết quả CUỐI CÙNG về (mọi xét nghiệm của lượt đã có kết quả). Là mốc
    # "đủ điều kiện quay lại hàng". Thiếu thì dùng giờ check-in — tức là coi như
    # đã chờ từ lúc đến, không bao giờ đẩy người đó lên trước người đến trước.
    b3_ready_at: datetime | None = None
    # Mốc lễ tân KÉO TAY (epoch ms) — thay giờ check-in khi xếp (20260915000016).
    thu_tu_tay_ms: float | None = None
    # Cờ ưu tiên/VIP trên HỒ SƠ khách: chỉ là nhãn cho lễ tân, không đổi thứ tự.
    khach_uu_tien: bool = False


@dataclass(frozen=True)
class QueueDecision:
    """Một dòng trong hàng chờ, kèm LỜI GIẢI THÍCH vì sao nó đứng ở đó.

    Bảng gọi số không chỉ cần xếp đúng — nó phải trả lời được câu hỏi của người
    ngồi chờ: *"vì sao người kia vào trước tôi?"*. Không có `call_reason` thì
    câu trả lời duy nhất màn hình đưa ra được là im lặng.
    """

    entry: QueueEntry
    call_order: int  # vị trí trong hàng, 0 là người được gọi tiếp theo
    # Nhóm của dòng: -1 quay lại đọc KQ · 0 đã check-in · 1 chưa đến.
    # -1 KHÔNG còn nghĩa là "gọi trước" — vị trí thật nằm ở `call_order`.
    call_tier: int
    call_reason: str  # một trong các REASON_* ở đầu module
    # "Được đẩy lên" = có ít nhất một người ĐẾN TRƯỚC mình mà bị xếp SAU mình.
    # Đây đúng là tình huống cần giải thích trên tivi, và cũng đúng là tình
    # huống duy nhất khiến người đến trước thấy khó hiểu.
    promoted: bool
    promoted_over: int
    # Khách ưu tiên/VIP (cờ hồ sơ, Tuyền chốt 15/09/2026): nhãn để màn hình hiện,
    # KHÔNG ảnh hưởng thứ tự. Thay nhãn vé "ƯT…" — không còn ghế/vé ưu tiên.
    uu_tien: bool = False


def _classify(e: QueueEntry) -> tuple[tuple[int, float, str], str]:
    """Khoá sắp xếp VÀ lý do, sinh ra cùng một lúc.

    Hai thứ này phải đi cùng nhau. Tách thành hai hàm là mở đường cho việc màn
    hình dán một câu giải thích không khớp với thứ tự thật — thứ sai lầm mà
    không bài kiểm nào bắt được vì cả hai đều "chạy đúng".
    """
    slot_iso = _iso(e.slot_start)

    # Quay lại đọc kết quả: khoá là MỐC ĐỦ ĐIỀU KIỆN. Khoá này chỉ dùng để xếp
    # những người quay lại VỚI NHAU; chỗ đứng trong cả hàng do `explain_queue`
    # chèn (sau mọi người đã chờ trước mốc đó).
    if e.b3_ready and e.checked_in_at is not None:
        return (-1, float(_du_dieu_kien_ms(e)), _iso(e.checked_in_at)), (
            REASON_CHO_DOC_KQ
        )

    # Dòng chưa check-in, chưa có kênh đặt → giữ thứ tự số vé, nhưng tất cả
    # đều ở làn chưa đến.
    if e.booking_channel is None and e.checked_in_at is None:
        ticket_tier, ticket_number, _ = queue_rank(e.queue_number, slot_iso)
        ticket_order = float(ticket_number) if ticket_tier < 2 else float("inf")
        return (1, ticket_order, slot_iso), REASON_CHUA_DEN

    slot_ms = _ms(e.slot_start)
    # CHỈ 'WALK_IN' mới là khách vãng lai. Mọi giá trị khác — KỂ CẢ TRỐNG — là
    # khách đã đặt lịch.
    #
    # Trước đây điều kiện là `bool(booking_channel) and != 'WALK_IN'`, nên một
    # lịch KHÔNG GHI KÊNH bị coi là vãng lai. Trên máy chủ thật hôm nay có 16
    # lịch như vậy (ONLINE 21 · TRỐNG 16 · WALK_IN 7 · HOTLINE 4) — tức là gần
    # một phần ba số lịch bị TƯỚC MẤT quyền ưu tiên mà người bệnh đã có bằng
    # cách đặt trước, và không có gì trên màn hình cho thấy điều đó.
    #
    # Trống nghĩa là "không ai ghi lại kênh", không nghĩa là "người này tự đến".
    # Khách vãng lai được tạo với kênh WALK_IN rõ ràng (và tự vào thẳng trạng
    # thái đã đến — xem booking_service). Một dòng trong bảng lịch hẹn mà không
    # phải WALK_IN thì chính nó đã là một cái hẹn.
    #
    # Và hai kiểu đoán sai không ngang giá nhau: đoán nhầm người đặt lịch thành
    # vãng lai thì họ mất lượt đã giành được; đoán nhầm vãng lai thành người đặt
    # lịch thì gần như vô hại, vì lịch của khách vãng lai được tạo ngay lúc họ
    # tới nên giờ hẹn xấp xỉ giờ đến.
    is_booked = (e.booking_channel or "").strip().upper() != "WALK_IN"

    # 1: chưa check-in → đứng sau mọi người đã có mặt, theo giờ hẹn.
    if e.checked_in_at is None:
        return (1, float(slot_ms), slot_iso), REASON_CHUA_DEN

    # 0: ĐÃ CHECK-IN → xếp theo GIỜ CHECK-IN, có hẹn hay đến thẳng như nhau
    # (Tuyền chốt 15/09/2026). Lý do chỉ để màn hình nói đúng người này là ai.
    # Lễ tân kéo tay thì mốc kéo tay thay giờ check-in (20260915000016).
    in_ms = _ms(e.checked_in_at)
    moc = e.thu_tu_tay_ms if e.thu_tu_tay_ms is not None else float(in_ms)
    key = (0, moc, _iso(e.checked_in_at))
    if not is_booked:
        return key, REASON_DEN_TRUC_TIEP
    if in_ms <= slot_ms + e.grace_ms:
        return key, REASON_DAT_TRUOC_DUNG_GIO
    return key, REASON_DEN_TRE


def _du_dieu_kien_ms(e: QueueEntry) -> int:
    """Mốc người này BẮT ĐẦU CHỜ ở hàng hiện tại.

    Người quay lại: lúc kết quả cuối cùng về, nhưng không sớm hơn lúc check-in
    (dữ liệu lệch giờ không được đẩy ai lên trước người đến trước mình).
    Người khác: lúc check-in.
    """
    assert e.checked_in_at is not None
    den = _ms(e.checked_in_at)
    if e.b3_ready and e.b3_ready_at is not None:
        return max(den, _ms(e.b3_ready_at))
    return den


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
    ranked = _xep_hang(entries)

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
                uu_tien=e.khach_uu_tien,
            )
        )
    return out


def _xep_hang(entries: list[QueueEntry]) -> list[QueueEntry]:
    """Xếp cả hàng: người đang chờ theo làn, rồi CHÈN người quay lại.

    Người quay lại đứng ngay sau người CUỐI CÙNG (theo thứ tự hàng) đã bắt đầu
    chờ không muộn hơn mốc đủ điều kiện của họ. Mọi ai vào hàng sau mốc ấy đứng
    sau họ. Người quay lại xử lý theo mốc tăng dần, nên hai người quay lại cũng
    xếp đúng "ai đủ điều kiện trước thì trước".
    """
    quay_lai = sorted(
        (e for e in entries if e.b3_ready and e.checked_in_at is not None),
        key=call_rank,
    )
    ids_quay_lai = {id(e) for e in quay_lai}
    hang = sorted((e for e in entries if id(e) not in ids_quay_lai), key=call_rank)

    for r in quay_lai:
        moc = _du_dieu_kien_ms(r)
        vi_tri = 0
        for i, e in enumerate(hang):
            if e.checked_in_at is not None and _du_dieu_kien_ms(e) <= moc:
                vi_tri = i + 1
        hang.insert(vi_tri, r)
    return hang


def order_queue(entries: list[QueueEntry]) -> list[QueueEntry]:
    """Return entries in call order (stable)."""
    return _xep_hang(entries)


def b3_ready_times(labs: list[dict[str, object]]) -> dict[str, datetime | None]:
    """Lượt đã đủ kết quả → lúc kết quả cuối cùng về (``result_received_at``).

    Cùng định nghĩa "đủ" với `b3_ready_appt_ids`; giá trị None khi dòng không
    mang mốc giờ (người gọi cũ).
    """
    ready = b3_ready_appt_ids(labs)
    moc: dict[str, datetime | None] = {a: None for a in ready}
    for lab in labs:
        appt = str(lab.get("appointment_id") or "")
        t = lab.get("result_received_at")
        if appt in moc and isinstance(t, datetime):
            cu = moc[appt]
            moc[appt] = t if cu is None or t > cu else cu
    return moc


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
