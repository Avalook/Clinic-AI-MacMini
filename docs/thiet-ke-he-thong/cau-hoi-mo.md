---
title: "Câu hỏi mở — 8 quyết định không phải kỹ thuật, cần Quang/Tuyền chốt trước Phase A"
lop: 6
lop_ten: Lộ trình & quyết định
tag_nguon: "để debate, không tự trả lời"
tags: [clinicai, lop6-lo-trinh]
---

# Câu hỏi mở — 8 quyết định không phải kỹ thuật, cần Quang/Tuyền chốt trước Phase A

> [!abstract] Wedge · tên canonical · ai sở hữu luật · ngưỡng · Zalo · journey pilot · Hào Nam · KPI cá nhân.

1. **Wedge trước: CSKH hay in-visit?** Thesis nói in-visit; người dùng thật là CSKH; kiến trúc trung lập. Đề xuất: Phase A bật policy cho **cả hai** nhưng đo CSKH trước (có dữ liệu ngay). Cần Quang gật vì nó đổi câu chuyện với chị Thu/Sáng Ý.
2. **Tên event canonical**: giữ `appointment.created` (tiếng Anh snake, đang chạy) + cột `canonical` PascalCase, hay đổi hẳn sang thesis ngay? Tôi chọn giữ + ánh xạ (rủi ro 0). Quang có muốn tài liệu đối tác dùng tên thesis không?
3. **Ai sở hữu luật?** `policy.owner_role` mặc định MANAGEMENT; Trưởng ca được sửa ngưỡng (`dispatch_threshold` đã cho) nhưng có được sửa SLA ack không? Pilot §11 nói Operational Owner sở hữu policy — là ai ở Dr4Women?
4. **Ngưỡng ban đầu**: ack 5′/10′ leo thang (Protocol §11 ví dụ), chờ 20′/8 người (`dispatch_threshold` mặc định), coverage 15′ — số nào là của Dr4Women? Cần workshop theo Journey §11 với Trưởng ca thật.
5. **Zalo OA**: bao giờ có? Trước đó, «PatientInformed» chỉ có bằng attestation của CSKH — chấp nhận ở pilot (Tuyền đã chốt 14/08), nhưng nói rõ trong báo cáo pilot.
6. **Journey pilot** (Pilot §4.2): chọn 1–2 loại encounter tần suất cao — Phụ khoa + siêu âm? Ảnh hưởng node nào được seed SLA và policy nào bật.
7. **Hào Nam**: `is_active=false`, chưa mô tả vận hành. Không thiết kế gì cho đa cơ sở ngoài `location_id` đã có — đúng chưa?
8. **KPI cá nhân**: Pilot §5 và Protocol §17 cấm chấm điểm bằng số task. Quản lý phòng khám có đồng ý *không* có bảng «ai làm nhiều việc nhất» không? Nếu không đồng ý, đó là kill criterion §3.10 cuối («tăng visibility làm tăng giám sát») và phải nói trước.

Hai câu kỹ thuật tôi **đã tự quyết** và ghi lý do (đảo được nếu Tuyền không đồng ý): (a) không tạo bảng `domain_event` mới — cộng cột vào `event_log` ([[tk-event-envelope-v2|Envelope v2]]); (b) đồng hồ + policy engine chạy **trong tiến trình relay** chứ không tiến trình riêng ([[tk-expectation-timer|expectation + đồng hồ]]) — tách khi có phép đo.

## Nối tới
- [[gap-wedge-mismatch|Khoảng cách 15]]
- [[wedge|Wedge]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-communication-delivery|notification_delivery]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[humane-ops|Design for Humane Operations]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[lo-trinh-tong|Lộ trình]]

## Được dẫn từ
- [[wedge|Wedge]]
- [[gap-wedge-mismatch|Khoảng cách 15]]
- [[lo-trinh-tong|Lộ trình]]
