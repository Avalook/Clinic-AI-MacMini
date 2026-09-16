---
title: "13 ADR + Sổ luật — quyết định đã chốt, cái nào đã thi hành"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "docs/adr/ · docs/SO-LUAT.md Phần 9"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# 13 ADR + Sổ luật — quyết định đã chốt, cái nào đã thi hành

> [!abstract] Bảng trạng thái thi hành đo 13/08: modular monolith ❌, outbox/bỏ RabbitMQ ❌, còn lại ✅ — thiết kế đích không đè lên ADR nào.

| ADR | Quyết định | Thi hành (SO-LUAT Phần 9, 13/08) |
|---|---|---|
| 0001 | Modular monolith + manifest 7 mục + import-linter | ❌ «không có thư mục `modules/`, không manifest, `services/` vẫn phẳng» |
| 0002 | Outbox polling là đường async duy nhất; xoá RabbitMQ; bảng `notification_delivery` | ❌ «`event_bus/` vẫn còn, `RabbitMQPublisher.publish()` vẫn `raise NotImplementedError`, `notification_delivery` chưa có migration» |
| 0003 | Bất biến concurrency ở Postgres | ✅ |
| 0004 | Auth 2 lớp fail-closed; RLS chỉ đọc | ✅ Accepted 30/07 |
| 0005 | Không hạ tầng stateful mới; LLM qua API | ✅ |
| 0006 | Ngân sách RAM; voice tách | ⚠️ phần Mac lỗi thời |
| 0007 | LangGraph checkpointer schema riêng | ✅ |
| 0008 | Đính chính bệnh án qua RPC + event_log | ✅ |
| 0009 | Multi-tenant từ đầu | ✅ |
| 0010 | KiotViet: port + adapter, outbox | ✅ (NullPosAdapter) |
| 0011 | Kernel workflow V2 ngay | ✅ dựng; «Chưa có routing tự động» (sau đó có ở `20260731000003`) |
| 0012 | Backend sở hữu hợp đồng | ⚠️ «42 route vẫn chạm thẳng database» |
| 0013 | Chạy Mac, sẵn sàng VPS | ✅ đã lên VPS |

Sổ luật, những luật thiết kế này phải tuân: **2.1** chỉ `main`; **3.1** không luật nghiệp vụ chỉ ở frontend; **4.1** ratchet 42 route; **4.4** một bảng một người ghi («Cách khai: mỗi tính năng một trang […] máy cũng đọc được» — chính là manifest ADR-0001); **5.1** một màn hình một lượt gọi; **6.2** bất biến ở Postgres; **7.1/7.2** không hạ tầng mới nếu không có phép đo; **8.1** ghi vết cùng transaction; **8.2** trong vết chỉ mã số; **11.2** code chạy phải có bản sao ngoài máy; **12.2** vá phải liệt kê mọi chỗ cùng mẫu, test phải đếm; **12.5** quy tắc chỉ đáng tin khi nằm trong CI.

### Thiết kế đích đối với ADR

- Thi hành nốt **0001** ([[tk-modular-monolith|Thi hành ADR-0001]]) và **0002** ([[tk-communication-delivery|notification_delivery]]) — hai ADR còn nợ chính là hai mảnh thesis cần.
- Không ADR nào bị supersede. Sẽ cần **ADR-0014** (event envelope v2 + một cửa ghi), **ADR-0015** (Work Item Protocol), **ADR-0016** (expectation timer trong tiến trình relay) — [[lo-trinh-tong|Lộ trình]] ghi thời điểm.

## Nối tới
- [[stack|Stack đang chạy]]
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[tk-communication-delivery|notification_delivery]]
- [[lo-trinh-tong|Lộ trình]]
- [[ci-guards|CI]]
- [[macro-v3|Thesis v3]]

## Được dẫn từ
- [[decision-checklist|Decision checklist cho mọi feature]]
- [[macro-v3|Thesis v3]]
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[stack|Stack đang chạy]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]
- [[multi-tenant-rls|Multi-tenant thật]]
- [[ci-guards|CI]]
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]
- [[tk-governance|Governance ở cấp event]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
