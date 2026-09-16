---
title: "Khoảng cách 2 — CRUD rồi log: state trước, event sau, 29 cửa ghi, độ phủ thưa"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "anti-pattern §20.1 ↔ services/*.py"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 2 — CRUD rồi log: state trước, event sau, 29 cửa ghi, độ phủ thưa

> [!abstract] Event là phụ phẩm của UPDATE; nhiều thay đổi trạng thái không có event nào; không cửa ghi bắt buộc điền envelope.

Mẫu phổ biến trong 21 file service — ví dụ `episode_service.set_status()`: UPDATE `care_episode.status` → INSERT `event_log episode.closed` (cùng transaction ✓). Chiều nhân quả: **cột trạng thái là chính, event là ghi chú**. Thesis §1: «Đó là "CRUD có message"».

Độ phủ đo được trên prod:
- 66 `appointment.created`, 1 `appointment.checked_in`. **Đây không phải bằng chứng mất event** — xem [[event-log-table|event_log]]: mốc quầy CSKH và lễ tân dùng CHUNG một máy trạng thái, chung một event; 66 là lịch đã tạo chứ không phải khách đã đến. Phép đo đúng để kết luận **không phải** so hai tổng `count(*)`: phải đối soát từng cặp `(clinic_id, appointment_id)` giữa lịch từng đạt `CHECKED_IN` và dòng `appointment.checked_in` tương ứng, có xét hoàn tác (`appointment.checkin_undone`) và thứ tự thời gian, vì một lịch có thể check-in rồi hoàn tác rồi check-in lại. *Chưa chạy.*
- `visit`: `move_visit_to_station` **có** ghi `event_log` (`20260804000013_room_serves_many_nodes.sql:227`, hàm khai từ dòng 122, `p_event_type` mặc định `dispatch.moved`) và chính nó lật `visit.status` OPEN → IN_PROGRESS trong cùng hàm. Chỗ hụt là **tên**, không phải chuyện thiếu ghi: bước ngoặt vòng đời đi lậu bên trong một event "chuyển phòng", nên projection chỉ suy ra "encounter đã bắt đầu" bằng cách đoán từ lần chuyển đầu tiên. `INCOMPLETE` có `visit.closed_incomplete`, FINALIZED có `clinical.signed`, không có `EncounterCompleted`.
- `work_item`: 7 `create`, và toàn bộ vòng đời nằm ở `work_item_event`, **không** vào `event_log`.
- `lab_result`, `payment`: 0 dòng prod nên chưa đo được, nhưng code có `lab_result.*`, `payment.recorded/voided`.

Hệ quả: bài kiểm «xoá dashboard, dựng lại từ event history» (§1) thất bại ngay ở `visit` — không dựng lại được `current_node_code` từ `event_log` vì `dispatch.moved` chỉ có 2 dòng còn `work_item` chuyển trạng thái không ghi vào đó.

29 câu `INSERT INTO event_log` viết tay = 29 cơ hội quên `metadata`, quên `source`, quên `correlation`. `services/audit.py:record_event()` là cửa chung có sẵn nhưng ít nơi dùng.

Đóng bằng: [[tk-emit-function|ghi_su_kien()]] (hàm SQL `ghi_su_kien` là cửa duy nhất, CI ceiling 29 → 0) + [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]] (trigger đổ các sổ chuyên biệt vào ledger) + bất biến «mỗi UPDATE status = một event» trong [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']].

## Nối tới
- [[anti-patterns|10 anti-pattern cần cấm]]
- [[event-log-table|event_log]]
- [[so-cai-phan-manh|Bảy sổ cái rời]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[ontology-9|Ontology]]
- [[event-vs-record|Event khác record]]
- [[anti-patterns|10 anti-pattern cần cấm]]
- [[event-log-table|event_log]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
