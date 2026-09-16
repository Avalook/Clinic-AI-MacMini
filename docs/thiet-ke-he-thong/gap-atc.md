---
title: "Khoảng cách 12 — ATC: có bảng toàn cảnh và cảnh báo, thiếu commitment/owner/SLA/risk/freshness/why"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "product-surface ↔ /truong-ca/*"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 12 — ATC: có bảng toàn cảnh và cảnh báo, thiếu commitment/owner/SLA/risk/freshness/why

> [!abstract] Khung màn đúng; card thiếu 5/9 trường thesis; cảnh báo không có nút nhận/lý do/nguồn.

Card thesis §19.1 (9 trường) vs `_overview_row()`:

| Trường | Có |
|---|---|
| current projected state | ✅ `current_node_name`, `room`, `floor`, `visit_status` |
| state age | ✅ `wait_minutes` (từ `current_node_since`) |
| event gần nhất + thời điểm | ❌ (chỉ suy từ `done_steps`) |
| commitment đang mở | ❌ (chỉ `next_step` nếu có tuyến) |
| owner | 🟡 `doctor_name` = bác sĩ lượt, không phải owner bước |
| SLA/timer | 🟡 `threshold_minutes` là ngưỡng, không phải deadline của một việc |
| experience risk | ❌ |
| data freshness | ❌ |
| đề xuất action + lý do | 🟡 alert `message` có câu, không có rule_id/evidence |

Cảnh báo (`build_alerts`): 4 loại đúng tinh thần khách hàng, có `patients` bị ảnh hưởng ✓; nhưng không có `id` ổn định (tính lại mỗi lần), không ack, không «vì sao tôi thấy» theo §19.3 (event nào, rule nào, evidence, confidence, ai quyết).

`thong_bao` là nút «gọi bộ phận» từ cảnh báo — vòng đóng một nửa: có `da_xu_ly` và `giay_phan_hoi` ✓, không escalation nếu không ai xử lý.

Team Queue/My Work: `/tasks` + `GET /work-items?workspace=` có `actionable_by_me`, `blocked`, blockers endpoint ✓; thiếu acknowledge, due, «vì sao tôi nhận việc này».

Timeline: `v_dispatch_history` chỉ `dispatch.*`; `v_audit_log` chỉ MANAGEMENT.

Đóng bằng: [[tk-atc-ui|Giao diện]] — không thêm màn, thêm trường từ [[tk-work-item-protocol|Work Item Protocol trên kernel]] + [[tk-experience-state|experience_state]] + [[tk-reliability-playbook|Reliability playbook]]; cảnh báo trở thành derived event có id.

## Nối tới
- [[product-surface|Product surface sinh ra từ event model]]
- [[dispatch|Điều phối Trưởng ca]]
- [[man-hinh-theo-vai|55 màn theo 13 vai]]
- [[tk-atc-ui|Giao diện]]
- [[thong-bao|thong_bao]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-experience-state|experience_state]]
- [[tk-reliability-playbook|Reliability playbook]]

## Được dẫn từ
- [[product-surface|Product surface sinh ra từ event model]]
- [[dispatch|Điều phối Trưởng ca]]
- [[man-hinh-theo-vai|55 màn theo 13 vai]]
- [[tk-atc-ui|Giao diện]]
