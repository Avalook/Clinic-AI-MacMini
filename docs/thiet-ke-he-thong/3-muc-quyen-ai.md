---
title: "Ba mức quyền hành động — Observe · Recommend · Act"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §5.2 · Care Model §14"
tags: [clinicai, lop1-hien-phap]
---

# Ba mức quyền hành động — Observe · Recommend · Act

> [!abstract] AI chỉ ở Interpretation/Decision; quyền tự hành động tuỳ rủi ro, khả năng hoàn tác và trách nhiệm chuyên môn.

> «AI không được tự động hóa một quyết định chỉ vì quyết định đó có thể được mô hình dự đoán. Quyền tự động phải phụ thuộc vào mức rủi ro, khả năng hoàn tác và trách nhiệm chuyên môn.» — *Thesis v1 §5.1*

| Mức | Vai trò hệ thống | Ví dụ (thesis) |
|---|---|---|
| Observe | Nhìn thấy và cảnh báo | Phát hiện bệnh nhân chờ quá SLA |
| Recommend | Đề xuất, con người phê duyệt | Đề xuất chuyển encounter sang bác sĩ khác |
| Act | Tự hành động trong guardrail rõ ràng | Gửi cập nhật trạng thái đã được phê duyệt trước |

> «ClinicAI phải luôn lưu được: tín hiệu đầu vào, lý do, đề xuất hoặc hành động, người phê duyệt và kết quả.» — *Thesis v1 §5.2*

Care Model §14 nêu 7 yếu tố quyết định mức quyền: clinical risk · reversibility · confidence · data sensitivity · policy của cơ sở · vai trò chịu trách nhiệm · khả năng audit và rollback. Và: «AI có thể diễn giải signal, nhưng clinical decision không được ngầm chuyển thành automation nếu chưa có governance tương ứng.»

Khi nào AI phù hợp (*v1 §5.1*): state không xác định được bằng rule đơn giản · cần tổng hợp nhiều tín hiệu · cần dự báo · nhiều phương án điều phối · diễn giải ngôn ngữ tự nhiên · học từ lịch sử nhưng người chịu trách nhiệm cuối.

### Code hôm nay xếp vào mức nào

- **Observe**: `dispatch_service.build_alerts()` (4 loại cảnh báo), `v_viec_cskh` (11 loại việc suy ra). Đây là *rule*, đúng như Experience Spec §13 khuyên cho pilot: «ưu tiên rule-based inference vì dễ giải thích và đo».
- **Recommend**: chưa có gì. `route_derivation.derive_route()` gợi ý tuyến từ chỉ định — gần nhất với Recommend, nhưng không ghi lại "đề xuất/ai duyệt/kết quả".
- **Act có guardrail**: lab triage GROUP_C → `hard_block` + tạo `staff_task` URGENT SLA 4h (`graphs/lab_triage/graph.py`). Đây là Act ở mức *chặn* (an toàn), không phải Act ở mức *gửi đi*. Relay Telegram là Act không guardrail — nó gửi mọi `appointment.*` có template (`notification_templates.TEMPLATES`, 5 mẫu) cho *nhóm nội bộ*, không cho bệnh nhân — nên rủi ro thấp, chấp nhận được.

Lằn ranh cấm đã có trong repo và thiết kế này giữ nguyên: **D012** không chatbot tư vấn lâm sàng cho bệnh nhân; **D013** không risk-scoring AI (design v5 §5.7). Chi tiết vị trí AI trong thiết kế đích: [[tk-ai-placement|AI đúng chỗ]].

## Nối tới
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[ai-hien-co|AI đang có]]
- [[tk-ai-placement|AI đúng chỗ]]
- [[experience-state|Experience State]]
- [[dispatch|Điều phối Trưởng ca]]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[ai-hien-co|AI đang có]]
- [[gap-ai|Khoảng cách 14]]
- [[tk-ai-placement|AI đúng chỗ]]
