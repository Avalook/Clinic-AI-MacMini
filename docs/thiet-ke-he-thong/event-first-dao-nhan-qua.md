---
title: "Event-first — đảo thứ tự nhân quả, và bài kiểm 'xoá dashboard dựng lại được không'"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §1–2"
tags: [clinicai, lop2-kien-truc]
---

# Event-first — đảo thứ tự nhân quả, và bài kiểm 'xoá dashboard dựng lại được không'

> [!abstract] Ba luận đề của Care Model (architectural, human) và định nghĩa 'event-driven' ở ba cấp độ.

Ba luận đề mở đầu Care Model:

> «**Core thesis:** Reality không được "nhập vào một trạng thái". Reality biểu lộ qua các sự kiện.» · «**Architectural thesis:** Event stream là bằng chứng gốc của hoạt động. Encounter state, Patient Journey, Experience State, work queue, dashboard và analytics là các projection được dựng từ cùng một dòng bằng chứng.» · «**Human thesis:** Event-driven không nhằm biến phòng khám thành máy. Nó giúp hệ thống nhận phần việc "nhớ, theo dõi, nối ngữ cảnh và phát hiện quên sót", để con người dành sự chú ý cho chăm sóc và phán đoán.»

> «Điểm khác biệt không nằm ở việc có Kafka, queue hay webhook. Nó nằm ở **nguồn sự thật và mô hình nhân quả**.» — *§1*

Ba cấp độ không được trộn (*§2*):

| Cấp độ | Ý nghĩa | Áp dụng |
|---|---|---|
| Event notification | Một module báo cho module khác rằng có thay đổi | «Dùng cho integration đơn giản, nhưng **không đủ làm domain model**» |
| Event-driven architecture | Các thành phần phản ứng bất đồng bộ với event | «Nền tảng cho orchestration, projection và automation» |
| Event sourcing | Event log là lịch sử chuẩn; state được fold/replay từ event | «Áp dụng có chọn lọc cho domain cần temporal truth và audit mạnh» |

> «ClinicAI theo hướng **event-driven architecture + selective event sourcing**.» — *§2*

Domain phải event-centric (*§2*): Encounter · Work Item · Journey/process execution · handoff và acknowledgement · communication · escalation · Experience State derivation · resource load và operational exceptions. Còn «Patient profile, staff directory, service catalog hay cấu hình tĩnh có thể dùng CRUD với audit log.»

### Code đang ở cấp độ nào

Cấp độ **1 — event notification**, làm khá tốt: `notify_row_change()` → `pg_notify('clinicai_changes')` → `ChangeBroker` → SSE ([[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]). Nhưng tin "cố ý nghèo" (chỉ tên bảng + clinic_id) nên nó là *notification*, không phải domain event — đúng như thesis phân loại.

Cấp độ **2** chỉ có một consumer thật: `notification_relay.py` đọc `event_log` gửi Telegram. Không projector, không policy consumer.

Cấp độ **3**: không có. Không domain nào fold state từ event.

Vì vậy điều quan trọng nhất của [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]: không chọn "full event sourcing" (§20.6 cấm), mà **đưa 4 domain lên cấp 2–3**: Encounter (visit), Work Item, Communication, Expectation — đúng danh sách §2, và đúng Luật 7.1 (chỉ Postgres).

## Nối tới
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[selective-event-sourcing|Selective event sourcing]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[notification-relay|notification_relay]]
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]
- [[anti-patterns|10 anti-pattern cần cấm]]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[selective-event-sourcing|Selective event sourcing]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
