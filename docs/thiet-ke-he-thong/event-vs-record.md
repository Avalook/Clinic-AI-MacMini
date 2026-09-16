---
title: "Event khác record — lịch hẹn là ý định, PatientArrived là sự thật"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §4.2"
tags: [clinicai, lop1-hien-phap]
---

# Event khác record — lịch hẹn là ý định, PatientArrived là sự thật

> [!abstract] Bốn loại thứ hay bị gộp làm một: record, event quan sát, thay đổi state, event suy ra, event xác nhận hành động.

> «Record trả lời: "Thông tin đã được lưu là gì?" Event trả lời: "Điều gì đã xảy ra, khi nào, với ai, ở đâu và do nguồn nào xác nhận?"» — *Thesis v1 §4.2*

Ví dụ nguyên văn — năm dòng, năm bản chất khác nhau:

> «Lịch hẹn 10:00 là record về ý định. · PatientArrived lúc 10:17 là event về reality. · EncounterCreated là thay đổi state của hệ thống. · WaitingThresholdExceeded là event được suy ra. · PatientInformed là event xác nhận một hành động chăm sóc đã được thực hiện.» — *Thesis v1 §4.2*

> «Event phải đủ bất biến để tạo lịch sử tin cậy. State là kết quả hiện tại được dựng từ chuỗi event. Work Item là cam kết rằng một actor cụ thể sẽ biến state hiện tại thành state mong muốn.» — *Thesis v1 §4.2*

### Code đã hiểu đúng một nửa

Phần code hiểu đúng — và hiểu từ một lỗi thật: `appointment` ≠ `visit` ≠ `tuong_tac_cskh`. `docs/GIAI-THICH-CODE.md §0.4` gọi ba thứ là **lời hứa · sự việc · lần chạm**, và chép lại sự cố 06/08: khách về giữa chừng, cách duy nhất là huỷ lịch hẹn, «hồ sơ trông như người ấy chưa từng đến» → sinh trạng thái `INCOMPLETE` (`20260806000004_luot_kham_do.sql`). Đó chính là "record về ý định ≠ event về reality" nói bằng tiếng Việt.

Phần chưa: **event bất biến** hiện là *phụ phẩm* của việc đổi cột trạng thái — `booking_service.apply_action()` UPDATE `appointment.status` rồi mới INSERT `event_log` (cùng transaction, nhưng chiều nhân quả ngược). Và ba loại event còn lại của ví dụ trên — *event suy ra* (WaitingThresholdExceeded), *event xác nhận hành động* (PatientInformed) — không tồn tại như event: cảnh báo chờ lâu được **tính lúc đọc** trong `dispatch_service.build_alerts()` và biến mất khi đóng tab; "đã trả kết quả" là một dòng `tuong_tac_cskh` loại `TRA_KQ` chứ chưa được coi là outcome event đóng một commitment.

Nút [[5-loai-event|Năm loại event]] mở rộng năm bản chất này thành bảng phân loại chính thức.

## Nối tới
- [[ontology-9|Ontology]]
- [[5-loai-event|Năm loại event]]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[tuong-tac-cskh|tuong_tac_cskh]]

## Được dẫn từ
- [[ontology-9|Ontology]]
- [[5-loai-event|Năm loại event]]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
