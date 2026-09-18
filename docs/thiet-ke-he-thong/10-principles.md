---
title: "10 nguyên tắc sản phẩm — và nguyên tắc nào code đang vi phạm"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §7"
tags: [clinicai, lop1-hien-phap]
---

# 10 nguyên tắc sản phẩm — và nguyên tắc nào code đang vi phạm

> [!abstract] Từ Reality before workflow tới Learn from every loop; mỗi nguyên tắc chấm điểm code hiện tại.

Nguyên văn mười nguyên tắc (*Thesis v1 §7*), kèm đối chiếu:

1. **Reality before workflow** — «Quy trình là giả định về tương lai. Event là bằng chứng về điều đã xảy ra. Khi hai thứ xung đột, ClinicAI ưu tiên reality và làm rõ sai lệch.» → Code: kernel sinh 7 bước xương sống lúc check-in (`instantiate_visit_workflow`) = *expected journey*; nhưng không có gì so sánh expected với actual ([[gap-process-manager|Khoảng cách 7]]).
2. **Every important state must be observable** — «…hệ thống phải nhìn thấy hoặc **biết rằng mình chưa nhìn thấy**.» → Code không biểu diễn "không biết": `ops_status.py` có `unknown`, còn màn điều phối thì im lặng khi thiếu dữ liệu ([[gap-failure-domain|Khoảng cách 11]]).
3. **Every next action must have ownership** — «Không có "hệ thống đã thông báo" nếu không xác định được ai chịu trách nhiệm, đã acknowledge chưa và khi nào cần escalation.» → Vi phạm trực tiếp: relay Telegram coi `event_published = TRUE` là xong, mà cờ ấy được đặt ở hai nhánh — sự kiện **không có template** thì đánh dấu mà không gửi gì (`notification_relay.py:205-214`), sự kiện gửi được thì đánh dấu khi nhà cung cấp trả ok (`:238`). Cả hai đều khác "người đã nhận và đã hiểu"; `thong_bao` có `da_xu_ly_luc` nhưng không escalation ([[gap-communication|Khoảng cách 8]], [[gap-work-item|Khoảng cách 3]]).
4. **Exception is first-class** — → Code làm tốt ở đặt lịch (5 mã lý do huỷ, `BAC_SI_DOI_LICH`, cờ mất bác sĩ) và điều phối (`visit_route.is_exception` bắt lý do). Điểm cộng thật.
5. **Human attention is a scarce resource** — «ClinicAI không đẩy thêm notification. Nó phải lọc, ưu tiên, gom ngữ cảnh…» → `v_trang_thai_cskh` chọn *một việc gấp nhất* mỗi khách — đúng tinh thần. `thong_bao` chống bấm hai lần bằng unique index — đúng. Nhưng chưa có ngân sách cảnh báo (Tổng-Quan §14.4: «tối đa 1 cảnh báo chặn/lượt khám»).
6. **Transparency is care** — → Chưa có kênh nào nói với *bệnh nhân* (Zalo OA chưa xây; `/display` chỉ gọi số).
7. **Optimize the system, not the individual** — → Báo cáo hiện tại không chấm điểm cá nhân — nhưng cũng chưa đo coordination debt ([[gap-metrics|Khoảng cách 13]]).
8. **AI must be accountable** — → `lab_result.triage_model`, `triage_reason`, `triage_classified_at` có sẵn cột provenance ✅; GROUP_C hard-block ✅ ([[ai-hien-co|AI đang có]]).
9. **Interoperate, do not replace by default** — → `PosPort` + `NullPosAdapter` (ADR-0010) là mẫu đúng; lab/LIS chưa có adapter.
10. **Learn from every loop** — «Event history không chỉ phục vụ audit.» → `event_log` hôm nay 62% là `slot_hold`. Nó vẫn đang được đọc làm nhật ký thao tác, nhưng chưa học được gì từ nó vì thiếu correlation và thiếu event vòng đời — không phải vì tỷ lệ nhiễu ([[gap-envelope|Khoảng cách 1]]).

Điểm số thô: **3 làm tốt (4, 8, 9)**, 2 làm một phần (5, 1), **5 chưa đạt (2, 3, 6, 7, 10)** — và cả 5 cái chưa đạt đều quy về một gốc: thiếu vòng lặp *ownership → ack → outcome* trên một sổ sự kiện đủ nghĩa.

## Nối tới
- [[north-star|North Star]]
- [[gap-process-manager|Khoảng cách 7]]
- [[gap-failure-domain|Khoảng cách 11]]
- [[gap-communication|Khoảng cách 8]]
- [[gap-work-item|Khoảng cách 3]]
- [[gap-metrics|Khoảng cách 13]]
- [[gap-envelope|Khoảng cách 1]]
- [[ai-hien-co|AI đang có]]
- [[pos-outbox|pos_outbox]]

## Được dẫn từ
- [[gate-rule|visit_gate_rule]]
- [[pos-outbox|pos_outbox]]
- [[ai-hien-co|AI đang có]]
