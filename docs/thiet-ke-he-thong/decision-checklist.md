---
title: "Decision checklist cho mọi feature — 11 câu hỏi"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 Phụ lục A · §12 Guardrails"
tags: [clinicai, lop1-hien-phap]
---

# Decision checklist cho mọi feature — 11 câu hỏi

> [!abstract] Bộ câu hỏi chặn feature rời rạc; nên trở thành mẫu PR description.

Guardrails (*v1 §12*): chỉ build khi trả lời "có" ít nhất một: «Nó làm reality observable hơn? · next action rõ hơn? · ownership tốt hơn? · giảm coordination debt? · bảo vệ bệnh nhân hoặc nhân viên tốt hơn? · đóng một feedback loop đang hở? · tạo dữ liệu đáng tin để hệ thống học?»

Trì hoãn nếu: «chỉ sao chép module phổ biến của HIS/CRM · tạo thêm nơi nhập liệu nhưng không làm state chính xác hơn · tạo thêm dashboard nhưng không dẫn tới quyết định hoặc action · dùng AI ở nơi rule đơn giản minh bạch hơn · tăng throughput bằng cách chuyển áp lực sang nhân viên · không có owner cho dữ liệu, policy và hậu quả của tự động hóa.»

Phụ lục A — 11 câu:
1. Reality nào feature này giúp hệ thống nhìn thấy?
2. Event nào tạo hoặc cập nhật reality đó?
3. State nào bị thay đổi?
4. Next action nào được tạo ra?
5. Ai sở hữu action?
6. SLA và escalation là gì?
7. Người dùng cần thấy ngữ cảnh nào để quyết định?
8. AI có thực sự cần thiết không? Nếu có, tại sao rule không đủ?
9. Rủi ro nếu AI sai là gì? Có hoàn tác và audit được không?
10. Patient, staff và business metric nào sẽ thay đổi?
11. Feedback loop được đóng ở đâu?

### Đề xuất dùng ngay, không cần code

`SO-LUAT.md` Phần 12 đã có luật «giao việc theo TÌNH HUỐNG, không theo tính năng» và mẫu 5 dòng cho prompt báo lỗi. Ghép hai thứ: **PR template** thêm 4 câu bắt buộc (2, 4, 5, 11) — event nào · việc nào · ai sở hữu · vòng đóng ở đâu. Không trả lời được là PR đang thêm màn hình, không thêm năng lực. Đây là chốt rẻ nhất trong toàn bộ thiết kế và có thể áp trong tuần này ([[phase-0-nen|Phase 0]]).

## Nối tới
- [[phase-0-nen|Phase 0]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[ci-guards|CI]]

## Được dẫn từ
- [[ci-guards|CI]]
- [[phase-0-nen|Phase 0]]
