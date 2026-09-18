---
title: "Metric từ event stream — mỗi chỉ số một view, rollup ngày, và phase nào mới có nghĩa"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "view v_metric_* + metric_daily"
tags: [clinicai, lop5-thiet-ke]
---

# Metric từ event stream — mỗi chỉ số một view, rollup ngày, và phase nào mới có nghĩa

> [!abstract] Baseline đo được từ Phase 0; coordination từ Phase A; experience từ Phase B. Không metric nào theo cá nhân trong báo cáo.

| Nhóm (v1 §9) | Metric | SQL nguồn | Có nghĩa từ |
|---|---|---|---|
| Visibility | Event Coverage = % encounter có ≥ 1 event mỗi node đã đi qua | `v_timeline_luot_kham` × `work_item` | Phase 0 |
| | State Freshness = p50/p95 `recorded_at − occurred_at`; và `now() − last_event_at` của visit mở | `event_log` | Phase 0 |
| | Unknown State Duration = tổng phút visit mở không có event trong > X phút | ledger | Phase 0 |
| Coordination | Time-to-assign / -acknowledge / -start / -outcome | `work_item.created_at → assigned_at (event) → acknowledged_at → started_at → finished_at` | Phase A |
| | Unowned Work Time = Σ phút `PENDING` không owner/queue | `work_item` + events | Phase A |
| | Handoff Failure Rate = ack timeout / assigned | `time.ack_timeout` / `work_item.assign` | Phase A |
| | Escalation Resolution Time | `work_item.escalate → acknowledge` | Phase A |
| | Coordination Debt (snapshot) = số việc mở thiếu owner ∨ due ∨ completion_criteria | `work_item` | Phase A |
| Humane | Unexplained Waiting Minutes = Σ tuổi `unexplained_wait_risk` (mở + đã đóng) | `experience_state` | Phase B |
| | Time-to-first-update = `detected_at → resolved_by_event.occurred_at` | | Phase B |
| | Communication Debt = risk mở chưa intervening | | Phase B |
| | Patient Forgotten Risk = visit mở không event > 2× ngưỡng | ledger | Phase 0 (thô) / B |
| | Staff Overload Minutes = phút phòng ở `critical` (theo **phòng**, không theo người) | `_STATIONS_SQL` snapshot mỗi 5′ → `station_load_sample` | Phase B |
| System | duplicate rate, quarantine, DEAD, projection lag, % warning có provenance (= % `experience_state` có `evidence_event_ids`) | reliability | Phase A |
| Business | lead time check-in → checkout; result-ready-to-review; no-show; huỷ theo lý do (đã có) | có sẵn | Phase 0 |

**Rollup**: `metric_daily (clinic_id, ngay, metric, chieu jsonb, gia_tri, n)` do đồng hồ ghi lúc 23:59 VN và có script rebuild từ ledger. `/reports` đọc bảng này (Luật 5.1 một lượt).

**Guardrail theo Spec §14 / Pilot §13.4**: notification burden (delivery/ngày/vai), false alarm rate (dismissed/detected), staff interruption (thong_bao/người/ca — **chỉ để phát hiện quá tải hệ thống**, không xuất trong báo cáo hiệu suất). Humane-ops §6.3: không có metric «theo người» ngoài workload view.

**Baseline** (Pilot §9): chạy các view Phase 0 trên 2 tuần dữ liệu **trước** khi bật policy nào — đó là số để so. Không có baseline thì mọi kết luận sau đều là cảm giác (v2 §3.3).

## Nối tới
- [[metrics-thesis|Bốn nhóm chỉ số]]
- [[gap-metrics|Khoảng cách 13]]
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[tk-experience-state|experience_state]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-projections|Projection có kỷ luật]]
- [[humane-ops|Design for Humane Operations]]
- [[pilot-scope|Partner Pilot Proposal]]

## Được dẫn từ
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[humane-ops|Design for Humane Operations]]
- [[metrics-thesis|Bốn nhóm chỉ số]]
- [[gap-metrics|Khoảng cách 13]]
- [[tk-experience-state|experience_state]]
- [[tk-projections|Projection có kỷ luật]]
- [[phase-b-exceptions|Phase B]]
- [[phase-c-intelligence|Phase C]]
