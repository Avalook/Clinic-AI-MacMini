---
title: "Khoảng cách 6 — Projection: view rebuild được, nhưng từ bảng trạng thái chứ không từ event"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "state-la-projection ↔ v_*, visit.current_*"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 6 — Projection: view rebuild được, nhưng từ bảng trạng thái chứ không từ event

> [!abstract] Bất biến 9 đạt một nửa; bài kiểm §26.3 'rebuild một projection từ lịch sử' hôm nay không chạy được cho visit.

Có 9 view: `patient_summary · v_audit_log · v_clinical_status · v_consultation_duration(_stats) · v_dispatch_history · v_slot_hold_active · v_trang_thai_cskh · v_viec_cskh`. View = projection rebuild tức thì ✓. `visit.current_node_code` do trigger nuôi từ `work_item` ✓ (§20.8 không mắc ở đây).

Nhưng nguồn fold là **bảng trạng thái** (`appointment.status`, `lab_result.reviewed_at`, `work_item.status`), không phải `event_log`. Nên: (a) không có "projection lag" để đo — vì không có projector; (b) nếu `work_item` bị sửa tay, `visit.current_node_code` theo, và `event_log` không biết; (c) muốn xem «trạng thái lúc 10:20 hôm qua» thì không có cách — không temporal query.

Thesis §7 cho phép Appointment ở mức state machine + events và master data CRUD — nên **không phải mọi bảng** cần fold từ event. Domain phải fold được: Encounter, Work Item, Communication, Experience (§2). Trong bốn cái, code hôm nay không fold được cái nào.

Cái cần: không phải viết projector worker (view đủ nhanh ở 1 RPS, DB cùng máy <1ms), mà là **đảm bảo event_log chứa đủ để fold** — tức [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]] + [[tk-event-envelope-v2|Envelope v2]] — rồi viết **view đối chứng** `v_visit_state_from_events` và test «view từ bảng == view từ event» ([[chung-minh-event-driven|12 bằng chứng 'event-driven thật']] mục 3). Khi hai view bằng nhau trên staging vài tuần, ledger mới đáng tin làm nguồn cho policy.

## Nối tới
- [[state-la-projection|State chỉ là projection]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[tk-projections|Projection có kỷ luật]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[tk-event-envelope-v2|Envelope v2]]

## Được dẫn từ
- [[ontology-9|Ontology]]
- [[state-la-projection|State chỉ là projection]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[so-cai-phan-manh|Bảy sổ cái rời]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[tk-projections|Projection có kỷ luật]]
