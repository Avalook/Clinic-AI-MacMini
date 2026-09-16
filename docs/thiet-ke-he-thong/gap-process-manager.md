---
title: "Khoảng cách 7 — Không process manager: rời cơ sở khi còn việc mở thì việc biến mất"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "journey-process-manager ↔ dispatch/checkout"
trang_thai: Chưa có
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 7 — Không process manager: rời cơ sở khi còn việc mở thì việc biến mất

> [!abstract] Expected có, actual có, nhưng không ai so sánh và phản ứng; visit_route 0 dòng; follow_up_case không writer.

Kịch bản thesis §9: PatientLeftFacility khi DoctorReviewCompleted chưa xảy ra → tạo PostVisitResultReviewWork + kênh liên hệ + deadline + theo dõi ack/completion.

Code: `checkout_service` đóng lượt (`dispatch.checkout`, `CHECK_OUT` mốc quầy, `visit.closed_incomplete` nếu chưa khám xong). `work_item` PENDING còn lại → `cancel_visit_workflow` hoặc để nguyên. `follow_up_case` — bảng được tạo đúng cho việc này («Non-blocking work that was still open when the visit closed») — **không có INSERT nào trong toàn repo**. `lab_result` chưa review sau checkout → chỉ hiện ở `v_viec_cskh` nhánh CHO_BAC_SI/KQ_CHUA_GUI (tốt, nhưng không owner).

Đến muộn (Journey §5.1: «không chỉ đổi trạng thái "muộn"; đánh giá lịch và công suất; phương án tiếp nhận hoặc đổi lịch; ai quyết định»): code có `walkin` seat, `is_priority_slot`, `queue_order` — nhưng không phản ứng tự động khi `now() > slot_start + X` mà chưa check-in (không timer).

Kết quả bất thường (§5.6): lab GROUP_C → `staff_task` URGENT — có, nhưng `staff_task` 0 dòng và không nối kernel.

`visit_route`: 0 dòng; `route_derivation` suy được nhưng «bảng Trưởng ca có cột "bước kế tiếp" […] trống với mọi bệnh nhân». `docs/kien-truc-nhieu-phong-kham.md` §2c: «Không có tuyến nào cho người chỉ khám rồi về.»

Đóng bằng: process manager = **policy phản ứng với event** trong [[tk-policy-engine|policy + policy_case]]; ba policy đầu (UnexplainedWait, HandoffUncertainty, ContinuityRisk) là ba nhánh rẽ; `follow_up_case` có writer đầu tiên từ policy ContinuityRisk.

## Nối tới
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[dispatch|Điều phối Trưởng ca]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-experience-state|experience_state]]
- [[patient-journey-4-chang|Patient Journey]]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[patient-journey-4-chang|Patient Journey]]
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[anti-patterns|10 anti-pattern cần cấm]]
- [[tk-policy-engine|policy + policy_case]]
