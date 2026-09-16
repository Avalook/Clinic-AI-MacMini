---
title: "Partner Pilot Proposal — 8–10 tuần, in/out scope, 7 tín hiệu tối thiểu, 4 tầng gate"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Pilot Proposal v1"
tags: [clinicai, lop1-hien-phap]
---

# Partner Pilot Proposal — 8–10 tuần, in/out scope, 7 tín hiệu tối thiểu, 4 tầng gate

> [!abstract] Bản đề xuất pilot là bản 'định nghĩa xong' cụ thể nhất cho toàn bộ thiết kế: journey, node, exception, tín hiệu, cổng đánh giá.

**Journey tham chiếu** (*§4.2*): «Có lịch → bệnh nhân đến → tiếp nhận → chờ bác sĩ → khám → phát sinh siêu âm/xét nghiệm → bác sĩ xem kết quả → tư vấn → thanh toán → follow-up.» Khớp gần hết xương sống kernel `LUOTKHAM-01→02→03→05→13→14→15` + `DICHVU-*` + `THEODOI-*`.

**Exception trong phạm vi** (*§4.4*): đến muộn · chờ vượt ngưỡng · chưa có communication coverage · kết quả sẵn sàng chưa review · Work Item chưa acknowledge · node/nhân sự quá tải · rời cơ sở khi còn việc mở · hệ thống nguồn mất kết nối.

**Ngoài phạm vi** (*§5*): thay HIS/EHR · bệnh án điện tử hoàn chỉnh · AI tự chẩn đoán · automation clinical decision · toàn cơ sở cùng lúc · **chấm KPI cá nhân bằng số task** · tích hợp mọi legacy · **camera/IoT diện rộng** · mobile app hoàn chỉnh · revenue cycle · cam kết business trước baseline.

**7 tín hiệu tối thiểu** (*§7*) — mỗi cái có nguồn ưu tiên và fallback:

| Tín hiệu | Nguồn ưu tiên | Fallback | Code hôm nay |
|---|---|---|---|
| Lịch được xác nhận | Appointment/CRM API | CSKH xác nhận trên ClinicAI | ✅ `tuong_tac_cskh.XAC_NHAN_LICH` |
| Bệnh nhân đã đến | Check-in/POS/HIS | Lễ tân một chạm | ✅ `check_in_appointment` RPC, mốc `CHECK_IN` |
| Vào/rời hàng đợi | Workflow integration | Nhân viên chuyển node | ✅ `move_visit_to_station` |
| Dịch vụ bắt đầu/kết thúc | HIS/LIS/device | Vai trò cung cấp dịch vụ xác nhận | 🟡 `work_item start/complete` (chưa ai bấm) |
| Kết quả sẵn sàng | LIS/HIS callback | Người được phân quyền ghi nhận | 🟡 `lab_result.result_received_at` nhập tay |
| Work đã nhận/hoàn tất | ClinicAI | «Không dùng kênh ngoài nếu cần đo» | ❌ không có *nhận* |
| Bệnh nhân được thông tin | ClinicAI/messaging callback | Structured attestation | 🟡 `TRA_KQ` là attestation nhưng chưa gắn subject/valid_until |
| Bệnh nhân rời cơ sở | Checkout/presence | Lễ tân/trưởng ca xác nhận | ✅ `dispatch.checkout`, mốc `CHECK_OUT` |

> «Không cần tín hiệu hoàn hảo từ ngày đầu. Cần biết rõ tín hiệu nào tự động, tín hiệu nào thủ công và độ tin cậy của chúng.» — *§7*

**Bốn tầng gate** (*§13*): Data & observability (≥90% encounter dựng lại được journey; ≥95% event có timestamp/source hợp lệ; integration failure hiển thị; projection lag trong ngưỡng) → Adoption & coordination (≥80% Work Item ack trong SLA; ≥90% có owner; ≥85% completion có evidence; không tăng thao tác) → Outcome (giảm ≥20% unexplained waiting; ≥30% open commitments không owner; ≥20% result-ready-to-review; ≥25% manual status-check) → Guardrails (0 safety incident; false alert trong ngưỡng; 0 privacy incident).

> «Nếu không qua gate này, chưa dùng outcome để kết luận.» — *§13.1*

Bốn tầng gate này là **tiêu chí nghiệm thu** của [[lo-trinh-tong|Lộ trình]]; [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']] chuyển chúng thành test.

## Nối tới
- [[wedge|Wedge]]
- [[7-tieu-chi-event-source|Bảy tiêu chí cho mọi nguồn event]]
- [[lo-trinh-tong|Lộ trình]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[patient-journey-4-chang|Patient Journey]]
- [[tk-sensing|Sensing]]

## Được dẫn từ
- [[wedge|Wedge]]
- [[7-tieu-chi-event-source|Bảy tiêu chí cho mọi nguồn event]]
- [[patient-journey-4-chang|Patient Journey]]
- [[gap-policy|Khoảng cách 9]]
- [[gap-metrics|Khoảng cách 13]]
- [[gap-wedge-mismatch|Khoảng cách 15]]
- [[tk-metrics|Metric từ event stream]]
- [[tk-sensing|Sensing]]
- [[lo-trinh-tong|Lộ trình]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[cau-hoi-mo|Câu hỏi mở]]
