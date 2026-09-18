---
title: "LISTEN/NOTIFY → ChangeBroker → SSE — 'event notification' làm đúng, và cố ý nghèo"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "20260806000001 · core/change_broker.py · api/v1/routers/events.py · RealtimeRefresher.tsx"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# LISTEN/NOTIFY → ChangeBroker → SSE — 'event notification' làm đúng, và cố ý nghèo

> [!abstract] Bỏ Supabase Realtime vì DB thuê không cấp REPLICATION; trigger bắn tên bảng + clinic_id; màn hình tự đọc lại; tab ẩn không giữ kết nối.

> «Realtime đọc nhật ký WAL qua một replication slot, và tạo slot cần quyền REPLICATION. Database cho thuê không cấp quyền đó — đã đo trên Viettel IDC 06/08/2026 […]. `LISTEN`/`NOTIFY` thì là SQL thường: KHÔNG đòi quyền nào.» — *change_broker.py*

Đường đi: trigger `notify_row_change()` (AFTER INSERT/UPDATE/DELETE, 16 bảng + `event_log` chỉ INSERT) → `pg_notify('clinicai_changes', {t: bảng, c: clinic_id})` → `ChangeBroker` (một kết nối LISTEN riêng, «mượn nó từ bể là vĩnh viễn bớt một chỗ»; hàng đợi mỗi màn 8 tin, đầy thì bỏ — «tin sau cũng nói đúng điều ấy») → `GET /events/stream` SSE («SSE CHỨ KHÔNG PHẢI WEBSOCKET. Việc cần làm ở đây là một chiều») → `RealtimeRefresher` debounce 250ms → `router.refresh()`.

Tin cố ý nghèo — hai lý do trong migration: «NOTIFY có trần 8000 byte, một hàng bệnh án có thể vượt → HỎNG CẢ GIAO DỊCH GHI»; và «đẩy dữ liệu qua đường này là mở lối đọc nằm ngoài mọi lớp kiểm quyền của API».

`RealtimeRefresher.tsx`: «TAB KHÔNG AI NHÌN THÌ KHÔNG GIỮ KẾT NỐI» — trình duyệt chỉ cho 6 kết nối/origin trên HTTP/1.1, «tới tab thứ SÁU là hết sạch, trang không tải nổi (treo 300 giây) trong lúc CPU máy chủ 0.03%». Nhịp dự phòng 60s. `slot_hold` cố ý **không** vào `LIVE_TABLES` (tránh «trận mưa render»).

Relay Telegram nghe cùng kênh và chỉ thức khi `t == 'event_log' && c == clinic_id` (`nen_danh_thuc`).

### Đối chiếu thesis

Đúng cấp độ 1 «Event notification» của Care Model §2 — và làm rất sạch. Nó **không phải** và không cần là event bus: Luật 6.3 «Database bắn tin lúc ghi xong → backend đẩy về màn hình (SSE) → màn hình chỉ làm mới đúng phần bị ảnh hưởng. Hiện trạng: nửa đầu đã xong; nửa sau chưa — mỗi tin về là dựng lại cả trang.»

Với thiết kế đích, kênh này là **xương sống đánh thức** cho cả ba consumer mới (relay đã dùng; đồng hồ expectation và policy engine dùng cùng cách — [[tk-expectation-timer|expectation + đồng hồ]], [[tk-policy-engine|policy + policy_case]]). Không hạ tầng mới.

## Nối tới
- [[event-first-dao-nhan-qua|Event-first]]
- [[notification-relay|notification_relay]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-policy-engine|policy + policy_case]]
- [[failure-la-domain|Failure là một phần của domain]]
- [[stack|Stack đang chạy]]

## Được dẫn từ
- [[event-first-dao-nhan-qua|Event-first]]
- [[failure-la-domain|Failure là một phần của domain]]
- [[stack|Stack đang chạy]]
- [[gap-failure-domain|Khoảng cách 11]]
- [[tk-expectation-timer|expectation + đồng hồ]]
