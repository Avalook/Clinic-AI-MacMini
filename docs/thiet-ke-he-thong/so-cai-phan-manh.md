---
title: "Bảy sổ cái rời — event_log, work_item_event, tuong_tac_cskh, visit_route, visit_gate_override, inventory_txn, pos_outbox"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "kiểm kê lược đồ prod"
trang_thai: Một phần
tags: [clinicai, lop3-code]
---

# Bảy sổ cái rời — event_log, work_item_event, tuong_tac_cskh, visit_route, visit_gate_override, inventory_txn, pos_outbox

> [!abstract] Mỗi sổ đúng cho việc của nó; nhưng 'timeline của một lượt khám' phải join 5 khoá — thesis đòi một stream.

| Sổ | Ghi gì | Append-only? | Vào `event_log`? |
|---|---|---|---|
| `event_log` | 17 loại nghiệp vụ + slot_hold | ✅ trigger | — |
| `work_item_event` | create/start/complete/skip/cancel/reassign | ✅ (không trigger, theo thiết kế) | ❌ (chỉ `audit_labels` có nhãn `work_item.*`) |
| `tuong_tac_cskh` | mọi lần chạm khách + mốc quầy | ✅ + `huy_luc` | ✅ `cskh.tuong_tac` |
| `visit_route` | tuyến áp cho lượt, superseded_at | ✅ | ✅ `dispatch.route_applied` |
| `visit_gate_override` | bỏ qua luật, lý do, người | ✅ | ❌ (chỉ log) |
| `inventory_txn` | xuất nhập kho theo lô | ✅ `inventory_txn_append_only` | ✅ `pharmacy.*` |
| `pos_outbox` | đẩy POS, attempts, DEAD | ❌ (trạng thái) | — |
| `thong_bao` | gọi bộ phận, đã đọc/đã xử lý | ❌ | ✅ lúc tạo, ❌ lúc xử lý |
| `visit_amendment` | (retired, còn ở prod) | | |
| `v_audit_log` | view đọc event_log có nhãn | | |

Điểm mạnh: mỗi sổ có ràng buộc đúng cho câu hỏi của nó (ví dụ `huy_luc` cặp; `visit_route` unique một hiệu lực). `v_dispatch_history` đọc lại từ `event_log` — «Không tạo bảng log thứ hai: hai nguồn sự thật cho cùng một câu chuyện là cách chắc chắn để chúng lệch nhau» — nguyên tắc đúng nhưng chưa áp toàn bộ.

Điểm yếu theo thesis §6: không có `stream_id` nên không trả lời được «mọi thứ xảy ra với lượt khám X theo thứ tự» bằng một câu SELECT; `work_item_event` — sổ quan trọng nhất cho ownership — **không** vào ledger chung; `visit_gate_override` (một Decision event đúng nghĩa) cũng không.

Thiết kế [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]: **giữ nguyên bảy sổ** (chúng là bảng chuyên biệt có CHECK riêng), thêm trigger AFTER INSERT ở `work_item_event`, `visit_gate_override`, `thong_bao` (xử lý) đổ vào `event_log` với `stream_id` + `causation_id` — cùng transaction, không hàng chờ (Luật 8.1).

## Nối tới
- [[stream-boundary|Năm stream]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[event-log-table|event_log]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[workflow-kernel|Workflow kernel]]
- [[gap-projection-rebuild|Khoảng cách 6]]

## Được dẫn từ
- [[stream-boundary|Năm stream]]
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
