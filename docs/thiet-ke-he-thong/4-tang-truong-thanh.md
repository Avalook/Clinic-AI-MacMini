---
title: "Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §10 · docs/TAM-NHIN.md"
tags: [clinicai, lop1-hien-phap]
---

# Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang

> [!abstract] Hai thang đo cùng một thứ; ClinicAI đang xây nền lv3 (= Level 2 digital record) và thesis đòi Level 4.

Thesis (*v1 §10*):

| Tầng | Đặc điểm | Giới hạn |
|---|---|---|
| Level 1 — Human-memory operation | Reality nằm trong đầu người; ai nhớ thì việc chạy | Phụ thuộc cá nhân, lỗi vô hình |
| Level 2 — Digital record | SaaS ghi lại dữ liệu; con người nhìn dashboard và tự điều phối | **Có dữ liệu nhưng chưa tạo closed loop** |
| Level 3 — AI-assisted operation | Hệ thống hiểu state, phát hiện bất thường và đề xuất hành động | Con người vẫn là bottleneck điều phối |
| Level 4 — Event-driven intelligent organization | Reality tự kích hoạt coordination trong guardrail rõ ràng | Đòi hỏi event coverage, governance và niềm tin cao |

Thang của Quang chốt 24/08 (`docs/TAM-NHIN.md`): lv1 người+quan hệ · lv2 quy trình · lv3 SaaS (record) · lv4 AI đọc state → khuyến nghị · lv5 tự cải thiện từ ngoại lệ. Hai thang khớp nhau lệch một bậc: **Level 2 thesis = lv3 Quang; Level 3 = lv4; Level 4 ≈ lv5**.

Định vị hôm nay (TAM-NHIN): «Phòng khám Dr4Women: lv1–2 · ClinicAI: đang xây nền lv3.» Nợ lv3 có số: «42/63 route dashboard còn chạm thẳng database».

Thesis mô tả Level 4 bằng 6 phản xạ — đây là **bảng kiểm hành vi** cho thiết kế đích:

> «PatientArrived → tạo encounter và work item tiếp đón. · LabResultReady → bác sĩ được đưa đúng context và journey tiếp tục. · WaitingThresholdExceeded → CSKH nhận task giải thích. · StaffOverloaded → trưởng ca nhận đề xuất redistribution. · PatientLeftClinic → follow-up workflow bắt đầu. · MissingExpectedEvent → hệ thống chủ động hỏi hoặc escalation thay vì giả định mọi thứ bình thường.» — *Thesis v1 §10*

Đối chiếu code: phản xạ 1 **có** (check-in → `instantiate_visit_workflow` sinh work item). Năm phản xạ còn lại **không có**, và cả năm đều cần cùng ba mảnh: sự kiện đủ nghĩa ([[tk-event-envelope-v2|Envelope v2]]), bộ hẹn giờ phát hiện "chưa xảy ra" ([[tk-expectation-timer|expectation + đồng hồ]]), policy phản ứng ([[tk-policy-engine|policy + policy_case]]).

Luật rút ra từ TAM-NHIN mà thiết kế này tuân theo: «Tính năng lv4 phải chỉ được tên bảng lv3 nó đọc, và bảng đó phải đã đáng tin.» Vì thế [[lo-trinh-tong|Lộ trình]] bắt đầu từ sổ sự kiện, không từ AI.

## Nối tới
- [[north-star|North Star]]
- [[lo-trinh-tong|Lộ trình]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-policy-engine|policy + policy_case]]
- [[instantiate-visit|Check-in sinh việc]]
- [[3-muc-quyen-ai|Ba mức quyền hành động]]

## Được dẫn từ
- [[north-star|North Star]]
- [[instantiate-visit|Check-in sinh việc]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]
- [[gap-ai|Khoảng cách 14]]
- [[tk-ai-placement|AI đúng chỗ]]
- [[lo-trinh-tong|Lộ trình]]
