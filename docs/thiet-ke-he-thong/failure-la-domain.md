---
title: "Failure là một phần của domain — im lặng không phải 'không có gì xảy ra'"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §16 · Catalog §13"
tags: [clinicai, lop2-kien-truc]
---

# Failure là một phần của domain — im lặng không phải 'không có gì xảy ra'

> [!abstract] IntegrationUnavailable, EventValidationFailed, NotificationDeliveryFailed… phải là event hiện trên operational health view.

> «Nếu LIS ngừng kết nối, dashboard không được tiếp tục hiển thị sự yên lặng như "không có result mới". Nó phải biểu diễn độ tin cậy của quan sát. ClinicAI không chỉ hiển thị state. ClinicAI phải hiển thị khi nó không còn đủ bằng chứng để tin state đó.» — *§16*

Failure event (*§16*): IntegrationUnavailable · EventValidationFailed · ResultMappingFailed · NotificationDeliveryFailed · WorkAssignmentFailed · ProjectionLagThresholdExceeded · AutomationBlockedByPolicy.

Catalog §13 thêm: IntegrationRestored · DuplicateEventDetected · EventQuarantined · ProjectionRebuilt · UnauthorizedCommandRejected · ManualOverrideApplied · PolicyVersionActivated · EventSchemaVersionActivated. «Reliability event phải xuất hiện trên operational health view; không chỉ nằm trong log kỹ thuật.»

### Code: có "health view", chưa có "failure event"

`ops_status.py` gộp DB probe + snapshot host (`/run/clinicai-ops/status.json`) → `healthy/degraded/critical`, có trạng thái `unknown` và câu «Chưa có snapshot host hợp lệ; không giả định hệ thống đang an toàn.» — đúng tinh thần §16 ở tầng hạ tầng. `worker.py` có heartbeat file để compose healthcheck bắt «loop stops turning» — bài học «Celery worker chết âm thầm» (Tổng-Quan §14.6).

Nhưng ở tầng **nghiệp vụ** thì im lặng đúng kiểu thesis cấm:
- Relay: Telegram lỗi 3 lần → `logger.error("relay_delivery_failed")`, event nằm lại `event_published = FALSE` — **không có event NotificationDeliveryFailed**, không ai thấy trên màn hình.
- `RealtimeRefresher`: LISTEN rớt → «màn hình rơi về nhịp làm mới dự phòng» 60s — người dùng không biết mình đang nhìn dữ liệu cũ (thesis §19.1 đòi *data freshness* trên card).
- Bài học đã trả giá (GIAI-THICH-CODE §9 bẫy 3): 4 bảng CSKH nằm trong publication đã bỏ suốt 5 ngày, «hai CSKH ngồi cạnh nhau gọi cho cùng một khách hai lần trong một buổi» — đúng chế độ thất bại im lặng.

Thiết kế: [[tk-reliability-playbook|Reliability playbook]] đưa 4 failure event vào `event_log` (stream `sys:`), và card ATC có `data_freshness` ([[tk-atc-ui|Giao diện]]).

## Nối tới
- [[gap-failure-domain|Khoảng cách 11]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tk-atc-ui|Giao diện]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[notification-relay|notification_relay]]

## Được dẫn từ
- [[event-catalog|Event Catalog v1]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[gap-failure-domain|Khoảng cách 11]]
- [[tk-reliability-playbook|Reliability playbook]]
