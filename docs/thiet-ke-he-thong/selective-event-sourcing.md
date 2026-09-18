---
title: "Selective event sourcing — bảng nào event-source, bảng nào CRUD + audit"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §7 · §20.6"
tags: [clinicai, lop2-kien-truc]
---

# Selective event sourcing — bảng nào event-source, bảng nào CRUD + audit

> [!abstract] Bảng quyết định lưu trữ theo domain; 'event-source nơi thời gian và nhân quả tạo giá trị; không event-source vì thời thượng'.

| Domain | Mô hình lưu trữ đề xuất | Lý do (thesis) | Code hôm nay |
|---|---|---|---|
| Patient master data | CRUD + audit | Cần snapshot hiện tại | ✅ `patient` + `patient.created/phone_*` |
| Staff/service/catalog/config | CRUD + versioning | Dữ liệu tham chiếu và policy | 🟡 `node_definition_version` có; các bảng luật khác không version |
| Appointment | State machine + domain events | «Cần lịch sử booking/reschedule/no-show nhưng không nhất thiết full event sourcing ban đầu» | ✅ đúng mô hình: 8 trạng thái, 11 action, event mỗi transition |
| **Encounter** | **Event-sourced hoặc event-centric ledger** | «Temporal truth, audit và reconstruction là cốt lõi» | ❌ `visit` là 5 cột trạng thái; `visit.checkin` chỉ ghi trong SQL check-in |
| **Work Item** | **Event-sourced** | «Ownership, SLA và acknowledgement cần lịch sử chính xác» | 🟡 `work_item_event` append-only có, nhưng vòng đời nghèo |
| Patient Journey | Projection + process manager | «Journey là cách diễn giải stream, không phải nguồn sự thật riêng» | 🟡 `visit_route` là *bản ghi*, không phải projection |
| Experience State | Temporal projection | Suy từ event, thời gian, communication coverage | ❌ |
| Dashboard/analytics | Read model / warehouse | Tối ưu truy vấn; rebuild được | ✅ view (`v_viec_cskh`, `v_dispatch_history`, `v_consultation_duration`) |

> «Nguyên tắc: event-source nơi thời gian và quan hệ nhân quả tạo ra giá trị; không event-source vì thời thượng.» — *§7*

> «20.6 Full event sourcing cho mọi bảng — Tăng độ phức tạp mà không tạo giá trị. Selective event sourcing là chủ đích.» — *§20*

### Quyết định thiết kế rút ra

Không viết lại `visit`/`work_item` thành bảng chỉ-có-event. Cách rẻ hơn và khớp cả thesis lẫn ADR-0003 (net cứng ở Postgres): **bảng trạng thái vẫn là bảng trạng thái, nhưng mọi thay đổi trạng thái của 4 domain event-centric bắt buộc đi qua hàm ghi sự kiện trong cùng transaction**, và `event_log` giữ đủ trường để fold lại được ([[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]], [[tk-emit-function|ghi_su_kien()]]). Bài kiểm "xoá projection dựng lại" ([[chung-minh-event-driven|12 bằng chứng 'event-driven thật']] mục 3) chạy trên **view** — vì view rebuild tức thì.

## Nối tới
- [[event-first-dao-nhan-qua|Event-first]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[tk-emit-function|ghi_su_kien()]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
- [[workflow-kernel|Workflow kernel]]

## Được dẫn từ
- [[event-first-dao-nhan-qua|Event-first]]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
