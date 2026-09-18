---
title: "Event Catalog v1 — ngôn ngữ chung, ~80 event canonical, 3 phase pilot"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Event Catalog v1"
tags: [clinicai, lop2-kien-truc]
---

# Event Catalog v1 — ngôn ngữ chung, ~80 event canonical, 3 phase pilot

> [!abstract] Tên canonical theo domain; event nào không được tồn tại; Definition of Done cho một event; Phase A/B/C.

> «Nếu mỗi module gọi cùng một sự việc bằng một tên khác nhau, ClinicAI sẽ nhanh chóng trở thành tập hợp workflow rời rạc.» — *§1*

Quy tắc đặt tên (*§2*): thì quá khứ (PatientArrived, không ArrivePatient) · ngôn ngữ domain (ConsultationCompleted, không EncounterRowUpdated; **cấm** EntityChanged, DataSaved) · một event một ý nghĩa (tách AppointmentUpdated thành Confirmed/Rescheduled/Cancelled) · phân biệt mức hoàn thành.

Danh mục theo domain (§5–13), tóm tắt:

- **Booking & Pre-visit**: CareRequestOpened · CareRequestQualified · AppointmentProposed · AppointmentConfirmed · AppointmentRescheduled · AppointmentCancelled · PreVisitInstructionSent · AppointmentNoShowConfirmed. Mỗi cái có cột «Không đồng nghĩa» (AppointmentConfirmed ≠ «Bệnh nhân đã đến»).
- **Encounter & presence**: PatientArrived{location, arrival_method} · IdentityVerified · EncounterStarted · QueueEntered{node, queue, priority} · QueueExited{reason, next_node} · **PatientLocationObserved{location, method, confidence}** · PatientLeftFacility{method, open_commitments} · EncounterCompleted{completion_policy, open_followups} · EncounterCancelled.
- **Service node**: ServiceRequested · ServiceAccepted · ServiceStarted · ServicePaused · ServiceResumed · ServiceCompleted · ServiceUnableToComplete.
- **Orders & results**: OrderPlaced · OrderCancelled · SpecimenCollected · DiagnosticServiceStarted · ResultReady · ResultFlaggedUrgent · ResultReviewed · ResultCommunicated · ResultAssociationFailed.
- **Work**: WorkCreated · WorkAssigned · WorkAcknowledged · WorkStarted · WorkBlocked · WorkResumed · WorkReassigned · WorkEscalated · WorkCompleted · WorkCompletionRejected · WorkCancelled — mỗi cái một invariant («WorkAssigned: Không đồng nghĩa đã nhận»).
- **Communication**: CommunicationRequested · MessageSent{provider message ID} · MessageDeliveryConfirmed · PatientAcknowledged · PatientInformed{actor, method, subject} · CommunicationFailed · CommunicationRetryScheduled.
- **Time/expectation/experience**: ExpectationRegistered · ExpectedEventDeadlineReached · MissingExpectedEventDetected · WaitingThresholdExceeded · AcknowledgementTimeoutOccurred · NoRecentPatientUpdateDetected · ExperienceRiskDetected/Confirmed/InterventionStarted/Resolved/Expired.
- **Resource**: ShiftStarted/Ended · StaffAvailabilityChanged · ResourceOccupied/Released/Unavailable · QueueCapacityChanged · StaffOverloadDetected · NodeCongestionDetected · CapacityRestored.
- **Reliability**: 12 event (xem [[failure-la-domain|Failure là một phần của domain]]).

Không phê duyệt (*§14*): EntityUpdated · StatusChanged không nghĩa domain · ButtonClicked · NotificationCreated · PatientHappy · AICompleted · WorkflowFinished · «event chứa nguyên record nhạy cảm không cần thiết». «UI analytics event có thể tồn tại ở telemetry riêng, không trộn vào domain event ledger.»

**Ưu tiên pilot** (*§18*): **Phase A** closed-loop core (PatientArrived, EncounterStarted, QueueEntered, ServiceStarted/Completed, ResultReady, WorkCreated/Assigned/Acknowledged/Completed, PatientInformed, EncounterCompleted) → **Phase B** exceptions & time (WaitingThresholdExceeded, AcknowledgementTimeoutOccurred, MissingExpectedEventDetected, WorkBlocked, WorkEscalated, PatientLeftFacility, CommunicationFailed) → **Phase C** capacity & intelligence.

> «Không thêm event vì một màn hình cần dữ liệu. Chỉ thêm event khi một sự thật có ý nghĩa đã xảy ra và tổ chức cần có khả năng nhớ, hiểu hoặc phản ứng với nó.» — *§19*

### Ánh xạ sang tên đang có

Code dùng `<aggregate>.<verb>` snake_case tiếng Anh/Việt lẫn (`appointment.created`, `cskh.tuong_tac`, `dispatch.moved`, `thong_bao.hen_goi_lai`). ~80 tên trong `audit_labels.EVENT_LABELS` — đó là **catalog de-facto**. [[tk-event-catalog-table|event_catalog]] không đổi tên đang chạy (đổi là vỡ relay/view/test); nó thêm cột `canonical` ánh xạ sang tên thesis, ví dụ `appointment.checked_in → PatientArrived`, `dispatch.moved → QueueEntered/QueueExited`, `cskh.tuong_tac[TRA_KQ] → ResultCommunicated`, `slot_hold.* → (telemetry, không phải domain)`.

## Nối tới
- [[5-loai-event|Năm loại event]]
- [[audit-labels|audit_labels.EVENT_LABELS]]
- [[tk-event-catalog-table|event_catalog]]
- [[failure-la-domain|Failure là một phần của domain]]
- [[phase-a-closed-loop|Phase A]]
- [[phase-b-exceptions|Phase B]]
- [[phase-c-intelligence|Phase C]]

## Được dẫn từ
- [[7-tieu-chi-event-source|Bảy tiêu chí cho mọi nguồn event]]
- [[5-loai-event|Năm loại event]]
- [[audit-labels|audit_labels.EVENT_LABELS]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-sensing|Sensing]]
