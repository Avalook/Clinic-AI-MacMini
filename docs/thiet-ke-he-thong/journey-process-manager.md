---
title: "Patient Journey là Process Manager — expected vs actual, rẽ nhánh theo event thật"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §9"
tags: [clinicai, lop2-kien-truc]
---

# Patient Journey là Process Manager — expected vs actual, rẽ nhánh theo event thật

> [!abstract] Journey không phải sơ đồ tuyến tính hay cột current_step; nó giữ timer, so sánh, phát command, quản ngoại lệ.

> «Patient Journey không nên là một sơ đồ tuyến tính cố định, cũng không phải một cột current_step.» — *§9*

Ba lớp: **Expected Journey** (policy/template) · **Actual Journey** (event stream) · **Journey Process Manager** («so sánh expected với actual, giữ timer, phát command và quản lý ngoại lệ»).

Ví dụ nguyên văn: «Expected: Check-in → Consultation → Lab → Doctor review → Payment → Follow-up. Actual: Check-in → Consultation → Lab → Waiting → **Patient left facility**. Process Manager thấy PatientLeftFacility trong khi DoctorReviewCompleted chưa xảy ra. Nó chuyển nhánh: tạo PostVisitResultReviewWork; yêu cầu kênh liên hệ phù hợp; đặt deadline; theo dõi acknowledgement và completion.»

```
[*] → Active
Active → AwaitingResult: LabOrderPlaced
AwaitingResult → AwaitingReview: LabResultReady
AwaitingReview → InClinicFollowup: PatientStillOnsite
AwaitingReview → PostVisitFollowup: PatientLeftFacility
InClinicFollowup → Completed: ReviewCompleted
PostVisitFollowup → Completed: PatientInformed
```

> «Journey vì thế không "chạy từng bước". Nó phản ứng với event và giữ các cam kết còn mở.» — *§9*

### Code có gì cho từng lớp

- **Expected**: `node_dependency` (18 cạnh FS) + `instantiate_visit_workflow` đóng dấu 7 bước xương sống lúc check-in; `route_template` (3 tuyến sau khám). Điểm hay: KHAM/DICHVU cố ý **không** sinh sớm — «stamping them at check-in would invent clinical intent nobody expressed» (`20260731000003`).
- **Actual**: `work_item` transitions + `visit.current_*` + `event_log dispatch.*`.
- **Process Manager**: **không có**. `dispatch_service.next_step_of()` chỉ đọc `visit_route` (0 dòng trên prod). `route_derivation.derive_route()` suy tuyến từ chỉ định — là "expected" động, tốt — nhưng không ai *phản ứng* khi actual lệch. Kịch bản «PatientLeftFacility khi còn kết quả chưa xem»: `checkout_service` đóng lượt, `follow_up_case` (0 dòng) không bao giờ được ghi.

Thiết kế: process manager **không cần là một engine mới** — nó là tập policy trong [[tk-policy-engine|policy + policy_case]] có trigger = event, điều kiện = trạng thái stream, hành động = tạo Work Item/expectation. Ba policy đầu tiên ở [[tk-experience-state|experience_state]] chính là ba nhánh process manager của pilot.

## Nối tới
- [[patient-journey-4-chang|Patient Journey]]
- [[instantiate-visit|Check-in sinh việc]]
- [[dispatch|Điều phối Trưởng ca]]
- [[gap-process-manager|Khoảng cách 7]]
- [[tk-policy-engine|policy + policy_case]]
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[tk-experience-state|experience_state]]

## Được dẫn từ
- [[patient-journey-4-chang|Patient Journey]]
- [[instantiate-visit|Check-in sinh việc]]
- [[dispatch|Điều phối Trưởng ca]]
- [[gap-process-manager|Khoảng cách 7]]
- [[tk-policy-engine|policy + policy_case]]
