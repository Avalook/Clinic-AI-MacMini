---
title: "Projection có kỷ luật — 8 projection thesis ↔ view/bảng, checkpoint, và bài rebuild"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "view SQL + projection_checkpoint"
tags: [clinicai, lop5-thiet-ke]
---

# Projection có kỷ luật — 8 projection thesis ↔ view/bảng, checkpoint, và bài rebuild

> [!abstract] Không projector worker; view là projection; hai view đối chứng (từ bảng vs từ event) làm bài kiểm 'ledger đáng tin'.

| Projection (Care Model §8.1) | Hiện thực | Nguồn | Rebuild |
|---|---|---|---|
| Encounter Board | `dispatch_service._OVERVIEW_SQL` (giữ) + thêm cột từ `work_item` mở, `experience_state` mở, `expectation` gần nhất, `last_event_at` | bảng trạng thái + ledger | view |
| Work Queue | `list_worklist` (giữ) + `v_viec_cskh` (giữ) + cột ack/due/owner/why | bảng | view |
| Patient Journey | `v_timeline_luot_kham` ([[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]) + `route_derivation` | ledger | view |
| Experience Monitor | `v_experience_mo` = `experience_state` mở + coverage | bảng mới | view |
| Resource Load | `_STATIONS_SQL` (giữ) + overload event từ policy | bảng | view |
| Patient View | `/display` (giữ) + «bước tiếp theo» từ `next_step_of` + thông báo chờ đã duyệt | bảng | — |
| Management Analytics | `metric_daily` ([[tk-metrics|Metric từ event stream]]) | ledger | rollup tính lại được |
| Audit View | `v_audit_log` (giữ, đọc nhãn từ catalog) | ledger | view |

**Checkpoint** chỉ cho consumer có trạng thái (không phải view). ⚠ Bản phác cũ dùng một con trỏ `consumer_checkpoint (consumer, last_seq)` và tính lag bằng `max(seq) − last_seq`. **Cả hai đều chưa an toàn** vì `seq` là thứ tự cấp phát chứ không phải thứ tự commit, và sequence có khoảng trống — xem hộp cảnh báo trong [[tk-event-envelope-v2|Envelope v2]]. Hình thay thế phải chứng minh trước khi cài: xác nhận theo từng event (`(consumer, event_id)`) + consumer idempotent; số việc tồn thì đếm event chưa có dòng xác nhận, không lấy hiệu hai con số. Ngưỡng cảnh báo (`ProjectionLagThresholdExceeded` — Catalog §13) giữ nguyên ý nghĩa nhưng phải tính lại theo cách đếm ấy.

**Hai view đối chứng** — bài kiểm §26.3 và §22.9:

```sql
-- trạng thái encounter fold từ ledger (không đọc visit.status/current_node_code)
CREATE VIEW public.v_visit_state_tu_su_kien AS
SELECT visit_id,
       (array_agg(payload->>'to_node' ORDER BY seq DESC) FILTER (WHERE event_type='dispatch.moved'))[1] AS current_node_code,
       max(occurred_at) FILTER (WHERE event_type IN ('dispatch.checkin','appointment.checked_in')) AS checked_in_at,
       bool_or(event_type IN ('dispatch.checkout','visit.closed_incomplete','clinical.signed')) AS closed
  FROM public.event_log WHERE visit_id IS NOT NULL GROUP BY clinic_id, visit_id;
```

SQL test trong CI (fixture chạy check-in → move → checkout): `SELECT count(*) FROM visit v JOIN v_visit_state_tu_su_kien s USING (visit_id) WHERE v.current_node_code IS DISTINCT FROM s.current_node_code` = 0. Trên staging: cron trong worker so mỗi giờ, lệch → `ghi_su_kien('projection.drift', reliability)`. Khi drift = 0 liên tục 2 tuần, ledger được coi là đáng tin để policy đọc — đó là **cổng** vào Phase B (TAM-NHIN luật 1).

**Rebuild**: view không cần. `metric_daily`: script `rebuild-metric.py --from 2026-09-01` chạy lại từ ledger, ghi `projection.rebuilt`.

## Nối tới
- [[state-la-projection|State chỉ là projection]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[tk-metrics|Metric từ event stream]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[tk-reliability-playbook|Reliability playbook]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[dispatch|Điều phối Trưởng ca]]
- [[tk-event-envelope-v2|Envelope v2]]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[state-la-projection|State chỉ là projection]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[tk-atc-ui|Giao diện]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tk-metrics|Metric từ event stream]]
- [[phase-0-nen|Phase 0]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
