---
title: "North Star — quan sát được · điều phối được · có tính người"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §1 · v2 §1 · v3 §1"
tags: [clinicai, lop1-hien-phap]
---

# North Star — quan sát được · điều phối được · có tính người

> [!abstract] Câu định vị gốc của toàn bộ hệ thống, và câu hỏi duy nhất ClinicAI phải trả lời khác HIS/CRM/ERP.

Ba bản Thesis v1→v3 mở đầu bằng cùng một câu, không đổi một chữ:

> «ClinicAI không số hóa quy trình của phòng khám. ClinicAI số hóa **trạng thái vận động** của phòng khám — để hệ thống có thể nhìn thấy điều đang xảy ra, hiểu điều gì cần xảy ra tiếp theo, điều phối người chịu trách nhiệm và tạo ra điều kiện cho việc chăm sóc tốt hơn.» — *Thesis v1, Core thesis*

Và câu phân biệt với mọi phần mềm y tế khác:

> «HIS/EHR hỏi: Hồ sơ bệnh nhân và dữ liệu lâm sàng là gì? · CRM hỏi: Quan hệ với bệnh nhân là gì? · ERP hỏi: Nguồn lực và giao dịch là gì? · Workflow software hỏi: Quy trình đã được định nghĩa phải chạy thế nào? · **ClinicAI hỏi: Ngay lúc này đang xảy ra chuyện gì, điều gì đáng lẽ phải xảy ra tiếp theo, và ai hoặc hệ thống nào chịu trách nhiệm để nó xảy ra?**» — *Thesis v1 §1*

North Star:

> «Make the clinic observable, coordinated, and humane. — Làm cho phòng khám có thể quan sát được, được điều phối tốt và vận hành có tính người.» — *Thesis v1 §1*

### Nghĩa là gì với code

Ba tính từ ấy là ba bài kiểm cho mọi tính năng. Đối chiếu code hôm nay:

| | Câu hỏi | Code trả lời được chưa |
|---|---|---|
| **Observable** | Bệnh nhân này đang ở đâu, chờ gì, bao lâu? | Một phần — `visit.current_node_code/current_room_id` + bảng Trưởng ca (xem [[dispatch|Điều phối Trưởng ca]]). Nhưng chỉ **1 lượt khám** trên prod từng đi qua kernel ([[workflow-kernel|Workflow kernel]]). |
| **Coordinated** | Ai chịu trách nhiệm bước tiếp theo, đã nhận chưa, quá hạn chưa? | Chưa — `work_item` không có acknowledge/SLA/escalation ([[gap-work-item|Khoảng cách 3]]). |
| **Humane** | Bệnh nhân có bị chờ mà không được giải thích không? | Chưa — không có khái niệm *communication coverage* hay Experience State ([[gap-experience-state|Khoảng cách 5]]). |

Thesis cũng nói thẳng câu sâu hơn North Star: «Better operational conditions → Better human behavior → Better care» (*v1 §1*). Tức là mục tiêu không phải throughput; [[humane-ops|Design for Humane Operations]] là điều kiện đạo đức để hệ được phép tồn tại trong y tế (*v3 §2.13*).

## Nối tới
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[ontology-9|Ontology]]
- [[humane-ops|Design for Humane Operations]]
- [[wedge|Wedge]]
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[gap-work-item|Khoảng cách 3]]
- [[gap-experience-state|Khoảng cách 5]]
- [[dispatch|Điều phối Trưởng ca]]
- [[workflow-kernel|Workflow kernel]]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[6-lop-san-pham|Product map 6 lớp]]
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[wedge|Wedge]]
- [[humane-ops|Design for Humane Operations]]
