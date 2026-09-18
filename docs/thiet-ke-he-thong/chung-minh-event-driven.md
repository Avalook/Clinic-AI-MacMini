---
title: "12 bằng chứng 'event-driven thật' — mỗi cái một test trong CI hoặc một kịch bản staging"
lop: 6
lop_ten: Lộ trình & quyết định
tag_nguon: "Care Model §26 · SO-LUAT Luật 12.5"
tags: [clinicai, lop6-lo-trinh]
---

# 12 bằng chứng 'event-driven thật' — mỗi cái một test trong CI hoặc một kịch bản staging

> [!abstract] Pilot chỉ được gọi event-driven nếu 12 điều này chứng minh được; đây là bảng nghiệm thu kỹ thuật của toàn thiết kế.

| # | Bằng chứng (Care Model §26) | Test | Phase |
|---|---|---|---|
| 1 | Một event nguồn cập nhật nhiều projection nhất quán | SQL: sau `dispatch.moved`, `v_timeline`, `_OVERVIEW_SQL`, `v_visit_state_tu_su_kien` cùng node | 0 |
| 2 | Mở event timeline của một encounter và hiểu vì sao state hiện tại tồn tại | Kịch bản staging: timeline có causation liền từ `appointment.created` → `checked_in` → `work_item.create` × 7 | 0 |
| 3 | Rebuild một projection từ lịch sử | `v_visit_state_tu_su_kien` == `visit` (drift 0); `rebuild-metric.py` cho cùng số | 0 / C |
| 4 | Duplicate event không tạo duplicate work | pytest: gọi policy hai lần cùng event → 1 work item (`uq_work_item_origin`) | A |
| 5 | Event đến trễ được xử lý mà không phá lịch sử | pytest: `ghi` với `occurred_at` quá khứ → `stream_version` mới, `recorded_at` = now, projection recompute; outcome đã đóng không tự mở | A |
| 6 | Timeout phát hiện một expected event bị thiếu | SQL: expectation quá hạn → sau một vòng đồng hồ có `time.*` event; chạy lại → 0 | A |
| 7 | Work Item không đóng ở "notification sent" | pytest: relay SENT → work_item vẫn ASSIGNED (thử ngược đỏ) | A |
| 8 | Journey rẽ nhánh dựa trên event thực tế | pytest policy_case: `dispatch.checkout` + lab chưa review → follow_up_case + THEODOI-01 | B |
| 9 | Experience Risk có evidence và resolution event | SQL CHECK `es_resolved_needs_event`; pytest resolve tự động khi attestation tới | B |
| 10 | Integration failure được nhìn thấy | pytest: provider 401 → DEAD + `integration.unavailable` + ops degraded | B |
| 11 | Policy change có version và không viết lại lịch sử | SQL: UPDATE `luat_cskh` → `policy.version_activated`; work item cũ giữ `policy_version` cũ | A |
| 12 | Một ca vận hành có thể replay để học | script dry-run replay không tạo delivery; trang xem lại ca đọc được «bottleneck bắt đầu từ event nào» | C |

Cộng bốn bất biến của repo giữ nguyên: tenant audit ceiling 0 · service-role allowlist 2 · route chạm DB ratchet 42↓ · coverage ≥ 80.

Mỗi test mới **thử ngược trước khi tin** (Luật 12.5): cố ý bỏ trigger/unique/guard → phải đỏ đúng chỗ.

## Nối tới
- [[lo-trinh-tong|Lộ trình]]
- [[ci-guards|CI]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]
- [[tk-projections|Projection có kỷ luật]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-experience-state|experience_state]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[pilot-scope|Partner Pilot Proposal]]

## Được dẫn từ
- [[pilot-scope|Partner Pilot Proposal]]
- [[selective-event-sourcing|Selective event sourcing]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]
- [[ci-guards|CI]]
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-projections|Projection có kỷ luật]]
- [[lo-trinh-tong|Lộ trình]]
- [[phase-c-intelligence|Phase C]]
