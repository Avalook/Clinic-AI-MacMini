---
title: "Policy Engine — 5 câu hỏi mỗi policy, có version, owner, test case, audit"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §10"
tags: [clinicai, lop2-kien-truc]
---

# Policy Engine — 5 câu hỏi mỗi policy, có version, owner, test case, audit

> [!abstract] Policy không nằm rải rác trong UI; ví dụ LabResultReady với 4 điều kiện → 4 phản ứng → 4 outcome kỳ vọng.

> «Mỗi policy phải trả lời năm câu: (1) Event nào kích hoạt? (2) Điều kiện/ngữ cảnh nào cần đọc? (3) Decision nào được đưa ra? (4) Command hoặc Work Item nào được phát? (5) Outcome Event nào dùng để đóng vòng?» — *§10*

Ví dụ LabResultReady:

| Điều kiện | Phản ứng | Outcome kỳ vọng |
|---|---|---|
| Patient onsite, encounter active | RequestDoctorReview | DoctorReviewCompleted |
| Patient đã rời cơ sở | StartPostVisitResultFlow | PatientInformed hoặc FollowupBooked |
| Kết quả có cờ urgent | EscalateClinicalReview | UrgentReviewAcknowledged rồi UrgentReviewCompleted |
| Không map được encounter | QuarantineUnmatchedResult | ResultMatched hoặc IntegrationIncidentResolved |

> «Policy không nên nằm rải rác trong UI. Nó cần version, owner, test case và audit.» — *§10*

### Policy hiện đang nằm ở đâu trong code

Thực ra khá nhiều — và **là dữ liệu**, đúng hướng (`docs/kien-truc-nhieu-phong-kham.md` §3: «luật là DỮ LIỆU, không phải code», 4 tầng cấu hình). Nhưng chúng **được thi hành theo ba cách khác nhau**:

| Luật | Bảng | Thi hành lúc | Câu (1)–(5) |
|---|---|---|---|
| Việc CSKH (11 loại) | `luat_cskh` | **lúc đọc** (view) | có (1)(2)(4), không (3)(5) |
| Ngưỡng chờ phòng | `dispatch_threshold` | lúc đọc (`build_alerts`) | có (1)(2), không (4)(5) |
| Thứ tự bắt buộc | `visit_gate_rule` | **lúc ghi** (`gate_rule_service.enforce`) | có (1)(2)(3), override có audit ✅ |
| Bác sĩ bắt buộc | `luat_bac_si_bat_buoc` | lúc ghi (booking) | có |
| Sức chứa 3 tầng | `*_booking_override` + trigger | lúc ghi (DB) | có |
| Giờ ca, giờ mở | `clinic.settings` | lúc ghi | có |

Thiếu chung: **không version, không effective_from, không owner, không test case theo bảng** (test hiện là pytest cho hàm thuần như `gate_rule_service.blocks()` — tốt nhưng không gắn với dòng luật cụ thể). Và không luật nào **phản ứng với event** — cái thứ ba thesis đòi.

Thiết kế [[tk-policy-engine|policy + policy_case]] không thay các bảng này; nó thêm **một bảng `policy` cho loại luật thứ ba — luật phản ứng** — và thêm version/owner cho các bảng cũ theo cách rẻ nhất (cột `version`, `effective_from`, ghi event `PolicyVersionActivated` khi đổi).

## Nối tới
- [[policy-as-data-hien-co|Luật là dữ liệu]]
- [[gate-rule|visit_gate_rule]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[tk-policy-engine|policy + policy_case]]
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]

## Được dẫn từ
- [[gate-rule|visit_gate_rule]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]
- [[gap-policy|Khoảng cách 9]]
- [[tk-policy-engine|policy + policy_case]]
