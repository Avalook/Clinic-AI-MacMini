---
title: "Wedge — In-visit Operational Coordination, không phải đặt lịch"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §11.2 · v2 §12.2"
tags: [clinicai, lop1-hien-phap]
---

# Wedge — In-visit Operational Coordination, không phải đặt lịch

> [!abstract] Thesis chọn điểm cắm là điều phối TRONG buổi khám; code hiện dày nhất ở TRƯỚC buổi khám (CSKH đặt lịch).

> «Wedge nên là In-visit Operational Coordination cho phòng khám tư nhân nhiều cơ sở: quan sát toàn bộ encounter đang hoạt động; quản lý node và bước tiếp theo; queue và Work Item theo vai trò; phát hiện chờ quá SLA và patient forgotten risk; workload view cho trưởng ca; timeline sự kiện để audit và handoff; communication trigger cho CSKH.» — *Thesis v1 §11.2*

> «Đây là nơi đau vận hành rõ, dữ liệu có tần suất cao, ROI có thể đo, và ClinicAI khác biệt rõ nhất so với appointment/CRM/HIS thông thường. Appointment, onboarding và post-visit follow-up sẽ nối vào hai đầu của cùng một encounter lifecycle.» — *Thesis v1 §11.2*

Thứ tự ưu tiên roadmap (*v1 §11.1*), nguyên văn 7 bước: (1) Nhìn thấy reality · (2) Tạo ownership · (3) Situational awareness · (4) Đóng patient communication loop · (5) Operational intelligence · (6) Tự động hoá có kiểm soát · (7) Học xuyên cơ sở.

### Chỗ lệch lớn nhất giữa thesis và code

Đo trên prod 04–05/09/2026:
- 65 lịch hẹn thật, **100% do 5 tài khoản CSKH** đặt; 0 lịch kênh walk-in tại thời điểm đo; 1 lượt khám đi qua kernel.
- Module dày nhất: `booking_service.py` (2.037 dòng), `tuong_tac_cskh_service.py` (883), `booking_override_service.py` (852) — toàn *trước* buổi khám.
- Điều phối trong buổi (`dispatch_service.py` 633 dòng, 5 màn `/truong-ca/*`) có, nhưng lúc đo **`visit_route` 0 dòng** và `visit_gate_rule` 0 dòng *(số đo 04–05/09, chưa đo lại)*.

Tức là **sản phẩm đang bán cho CSKH cái thesis gọi là "hai đầu"**, còn cái thesis gọi là *wedge* thì xây rồi để đó. Không phải lỗi ai: người dùng thật hôm nay là 10 CSKH của Dr4Women, và họ đặt lịch. Nhưng đây là quyết định phải nói ra, không để trôi — [[cau-hoi-mo|Câu hỏi mở]] câu 1.

Hai đường khả dĩ: (A) giữ CSKH làm bãi thử lv4 (đúng TAM-NHIN: «CSKH là bãi thử lv4 tự nhiên») và áp *cùng khuôn* Work Item/ownership/SLA lên việc CSKH trước; (B) chuyển trọng tâm sang in-visit theo đúng Pilot Proposal. Thiết kế đích ([[tk-work-item-protocol|Work Item Protocol trên kernel]]) cố ý **trung lập**: khuôn Work Item dùng được cho cả hai — chỉ khác node nào sinh việc.

## Nối tới
- [[north-star|North Star]]
- [[6-lop-san-pham|Product map 6 lớp]]
- [[gap-wedge-mismatch|Khoảng cách 15]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[cau-hoi-mo|Câu hỏi mở]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[dispatch|Điều phối Trưởng ca]]

## Được dẫn từ
- [[north-star|North Star]]
- [[6-lop-san-pham|Product map 6 lớp]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[gap-wedge-mismatch|Khoảng cách 15]]
- [[cau-hoi-mo|Câu hỏi mở]]
