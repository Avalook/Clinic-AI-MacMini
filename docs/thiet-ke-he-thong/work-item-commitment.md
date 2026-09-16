---
title: "Work Item là commitment — 10 bất biến, 8 trạng thái, 4 mốc SLA, completion contract"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §13 · Work Item Protocol v1"
tags: [clinicai, lop2-kien-truc]
---

# Work Item là commitment — 10 bất biến, 8 trạng thái, 4 mốc SLA, completion contract

> [!abstract] Không có owner thì chưa phải việc; không có completion criteria thì chưa biết thế nào là xong; không có outcome event thì vòng chưa khép.

> «Work Item là một commitment có thể kiểm chứng: một kết quả cần xảy ra, có lý do, người chịu trách nhiệm, thời hạn và bằng chứng hoàn thành. Work Item không phải một dòng trong danh sách việc và không được đóng chỉ vì đã gửi notification.» — *Protocol, mở đầu*

**10 bất biến** (*§2*): Purpose · Reason (event/policy) · Subject · Owner (người/role/queue) · Priority (clinical và operational **tách**) · Deadline/SLA · Completion criteria · Expected outcome event · Escalation policy · Authority. «Không đủ các trường này thì chỉ là reminder, không phải Work Item.»

**Vòng đời** (*§4*): Open → Assigned → Acknowledged → Active → Blocked ⇄ Active → Completed; Assigned → Escalated (AcknowledgementTimeout); Active → Escalated (CompletionSLAExceeded); Escalated → Assigned (Reassigned); Open/Assigned → Cancelled.

> «4.3 Acknowledged: Người hoặc queue có thẩm quyền xác nhận đã nhận. Acknowledgement phải có actor và timestamp. · 4.4 Active: Việc thực sự bắt đầu. **Không tự động chuyển Active chỉ vì người dùng mở màn hình.** · 4.6 Escalated: Escalation không thay thế owner; nó mở một vòng chịu trách nhiệm mới.»

**Assignment** (*§5*): Direct user (có fallback) · Role queue (claim + queue owner) · Team queue · System agent (idempotency, audit, human fallback) · External system (callback + timeout). «Claim: một người lấy work từ shared queue. Acknowledge: người nhận xác nhận commitment.»

**Priority** (*§6*): clinical (routine/priority/urgent/emergency — do clinical policy) **tách** operational (normal/elevated/high/critical). «AI không tự nâng clinical priority nếu không có governance.»

**SLA** (*§7*): claim_by · acknowledge_by · start_by · complete_by; timer phát ClaimTimeoutOccurred · AcknowledgementTimeoutOccurred · StartSLAExceeded · CompletionSLAExceeded.

**Completion contract** (*§8*): Required domain event · Structured attestation · External callback («có thể chưa đủ cho informed outcome») · Human approval · Compound criteria.

**Escalation** (*§11*) ví dụ: assigned → 5' chưa ack → nhắc queue → 10' → trưởng ca → urgent → clinical escalation riêng → owner ack → đóng ack-escalation, «Completion timer vẫn tiếp tục». «Không tạo escalation chỉ để gửi thêm notification. Escalation phải thay đổi accountability.»

**Idempotency** (*§13*): «Cùng origin_event + policy_version + work_type + subject chỉ tạo một Work Item»; mọi command có expected version; reassignment được optimistic concurrency bảo vệ.

**Anti-patterns** (*§18*), những cái chạm code: «auto-complete ngay sau NotificationSent · giao mọi việc trực tiếp cho một cá nhân không có fallback · cho phép sửa owner/status không tạo event · đóng parent khi child commitment còn mở · biến mọi click nhỏ thành Work Item.»

### Kernel hôm nay đứng ở đâu

`work_item`: 5 trạng thái PENDING/IN_PROGRESS/COMPLETED/SKIPPED/CANCELLED; 4 lệnh start/complete/skip/cancel; `version` optimistic lock ✅; gate FS/SS/FF/SF trong SQL ✅ (`work_item_gate_blockers`); `work_item_event` append-only ✅; `assigned_to`/`assigned_role`/`due_at`/`priority (P0-P2)` có cột nhưng **không có lệnh assign, không ai đặt due_at, priority một trục**. `follow_up_case` có bảng, 0 dòng, không writer. Chi tiết [[gap-work-item|Khoảng cách 3]]; thiết kế [[tk-work-item-protocol|Work Item Protocol trên kernel]].

Điểm cộng của kernel mà Protocol không nói tới: **SKIPPED mở gate, CANCELLED thì không** và «skip/cancel không bao giờ bị gate — đó chính là cách gỡ một luồng bị kẹt» (ADR-0011). Giữ nguyên.

## Nối tới
- [[workflow-kernel|Workflow kernel]]
- [[gap-work-item|Khoảng cách 3]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[experience-state|Experience State]]

## Được dẫn từ
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[experience-state|Experience State]]
- [[workflow-kernel|Workflow kernel]]
- [[thong-bao|thong_bao]]
- [[gap-work-item|Khoảng cách 3]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
