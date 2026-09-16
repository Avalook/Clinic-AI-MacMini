---
title: "Design for Humane Operations — không biến y đức thành điểm số"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §6 · v3 §2.13"
tags: [clinicai, lop1-hien-phap]
---

# Design for Humane Operations — không biến y đức thành điểm số

> [!abstract] Bảo vệ bệnh nhân, bảo vệ nhân viên, và điều kiện đạo đức để hệ thống được phép tồn tại trong y tế.

> «Một hệ thống vận hành tốt không chỉ tăng throughput. Nó phải giúp hành vi tử tế trở thành lựa chọn dễ nhất trong điều kiện làm việc hàng ngày.» — *Thesis v1 §6*

Bảo vệ bệnh nhân (*§6.1*): không để bị "quên"; không chờ mà không có chủ sở hữu; chuyển trạng thái nội bộ thành lời giải thích; **phân biệt chờ cần thiết và chờ do lỗi điều phối**; nhận diện bối cảnh lo âu cao; truy nguyên khi khiếu nại.

Bảo vệ nhân viên (*§6.2*): «Dashboard kiểu Air Traffic Control không chỉ hỏi "bệnh nhân nào gặp vấn đề?" mà còn phải hỏi "nhân viên nào đang bị quá tải?"» — cần thấy: số encounter active mỗi người · số chờ quá SLA · work item pending · escalation chưa xử lý · thời gian liên tục trên ngưỡng tải.

Không chấm điểm (*§6.3*):

> «ClinicAI không nên tạo chỉ số "Y đức bác sĩ A = 87/100". Một con số như vậy vừa giản lược đạo đức, vừa dễ trở thành công cụ trừng phạt.» — *v1 §6.3*

Điều kiện đạo đức (*v3 §2.13*): «Dùng visibility để sửa hệ thống; không dùng visibility để vắt kiệt con người.» — «Design for Humane Operations vì thế không chỉ là positioning. Nó là điều kiện đạo đức để ClinicAI nhận được quyền hoạt động trong healthcare.»

### Ràng buộc đưa vào thiết kế

- Work Item Protocol §17 lặp lại: «Không dùng số Work Completed đơn lẻ để chấm hiệu suất cá nhân.» → [[tk-metrics|Metric từ event stream]] chỉ định nghĩa metric **theo node/phòng/ca**, không theo người; metric theo người chỉ có trong *workload view* (tải hiện tại), không có trong báo cáo.
- Experience Spec §11: không hiển thị «bảng xếp hạng nhân viên theo số complaint risk» → [[tk-experience-state|experience_state]] không có cột "ai gây ra".
- Event Catalog §12: «Các event overload là Derived Event; không dùng để chấm điểm cá nhân.»
- Đang có sẵn trong code: `_STATIONS_SQL` tách `serving` và `waiting` («gộp hai số này lại thì Trưởng ca không biết phòng đang kẹt hay đang rảnh») — đúng tinh thần tìm bottleneck chứ không tìm người.

## Nối tới
- [[north-star|North Star]]
- [[tk-metrics|Metric từ event stream]]
- [[tk-experience-state|experience_state]]
- [[product-surface|Product surface sinh ra từ event model]]
- [[dispatch|Điều phối Trưởng ca]]

## Được dẫn từ
- [[north-star|North Star]]
- [[metrics-thesis|Bốn nhóm chỉ số]]
- [[experience-state|Experience State]]
- [[tk-experience-state|experience_state]]
- [[tk-metrics|Metric từ event stream]]
- [[cau-hoi-mo|Câu hỏi mở]]
