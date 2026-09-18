---
title: "15 bất biến cấp 'hiến pháp' — chấm từng điều trên code"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §22"
tags: [clinicai, lop2-kien-truc]
---

# 15 bất biến cấp 'hiến pháp' — chấm từng điều trên code

> [!abstract] Danh sách bất biến kiến trúc; mỗi dòng: đạt / một phần / chưa, kèm bằng chứng.

| # | Bất biến (nguyên văn) | Code | Bằng chứng |
|---|---|---|---|
| 1 | Mọi operational state quan trọng phải truy được về event | 🟡 | `appointment` mọi transition có event ✅; `visit.status` đổi ở nhiều chỗ, `visit.checkin` chỉ ghi trong SQL; `work_item` có `work_item_event` nhưng không vào `event_log` |
| 2 | Event đã xảy ra không bị sửa; sai được hiệu chỉnh bằng event mới | ✅ | trigger `trg_event_log_no_update/no_delete`; `huy_luc` + `cskh.tuong_tac_hoan_tac` |
| 3 | Derived fact phải được phân biệt với observed fact | ❌ | không có `evidence_level`; không có derived event |
| 4 | Mọi Work Item phải có owner, reason, completion criteria và expected outcome | ❌ | `work_item` có `assigned_to` nullable (1/7 prod), không reason/criteria/outcome |
| 5 | Notification không đóng workflow | ❌ | relay đánh dấu xong khi gửi; `thong_bao` đóng bằng `da_xu_ly` (đúng) nhưng không nối với work item nào |
| 6 | Journey không phải một status; nó là process manager trên event stream | 🟡 | `visit_route` + `next_step_of` là status-ish; không process manager |
| 7 | Experience State là temporal projection có evidence, confidence và expiry | ❌ | không có |
| 8 | Không có autonomy nếu thiếu policy và authority rõ | ✅ | lab GROUP_C hard-block; relay chỉ gửi nội bộ; AI không ghi trạng thái |
| 9 | Projection phải rebuild được | 🟡 | view rebuild tức thì ✅; nhưng từ bảng trạng thái, không từ event |
| 10 | Consumer phải idempotent | ✅ | relay advisory lock + recheck `still_unpublished`; `idempotency_key`; `uq_work_item_visit_node_live` |
| 11 | Không che giấu integration failure thành "không có gì xảy ra" | ❌ | relay lỗi chỉ log; SSE rớt im lặng |
| 12 | Mọi escalation phải có người hoặc queue chịu trách nhiệm | ❌ | không có escalation |
| 13 | Event schema là product contract, không chỉ là chi tiết backend | 🟡 | `audit_labels` + drift test là contract tên; không contract payload |
| 14 | Event payload tuân thủ data minimization | ✅ | payload chỉ ID; relay làm giàu lúc gửi |
| 15 | ClinicAI đo outcome của coordination, không chỉ activity | ❌ | không metric coordination |

**Đạt 5 · một phần 4 · chưa 6.** Sáu cái chưa (3, 4, 5, 7, 12, 15) là cùng một cụm — và [[lo-trinh-tong|Lộ trình]] Phase A đóng 4, 5, 12; Phase B đóng 3, 7; Phase C đóng 15.

## Nối tới
- [[lo-trinh-tong|Lộ trình]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[gap-work-item|Khoảng cách 3]]
- [[gap-experience-state|Khoảng cách 5]]
- [[gap-failure-domain|Khoảng cách 11]]
- [[gap-metrics|Khoảng cách 13]]
- [[reliability|Reliability semantics]]

## Được dẫn từ
- [[state-la-projection|State chỉ là projection]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
