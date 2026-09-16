---
title: "10 anti-pattern cần cấm — và 4 cái code đang mắc"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §20"
tags: [clinicai, lop2-kien-truc]
---

# 10 anti-pattern cần cấm — và 4 cái code đang mắc

> [!abstract] CRUD rồi EntityUpdated · event là notification · UI status là truth · generic payload · choreography không owner · full ES · phát trước commit · ghi thẳng projection · sent = done · AI không provenance.

| # | Anti-pattern | Code | Ghi chú |
|---|---|---|---|
| 20.1 | **CRUD rồi phát EntityUpdated** — «Một row đổi trạng thái rồi phát event generic không giữ được nghĩa nghiệp vụ và quan hệ nhân quả.» | 🟡 **mắc một nửa** | Event có tên nghiệp vụ (không generic) ✓, nhưng chiều nhân quả là CRUD-trước-event-sau, và 0% có causation. |
| 20.2 | Event là notification — «Event tồn tại dù không ai subscribe. Notification là một phản ứng có thể thất bại.» | 🟡 | `event_published` gộp hai nghĩa; `thong_bao.*` event thực chất là notification request. |
| 20.3 | UI status là source of truth | ✅ không mắc | ADR-0012: 0 policy ghi cho client; Command API. |
| 20.4 | Generic event payload `{before, after}` | ✅ không mắc | payload có tên trường nghiệp vụ. |
| 20.5 | Choreography không ownership — «không có process manager, journey phức tạp sẽ không ai sở hữu end-to-end completion» | ❌ **mắc** | Không process manager; trigger `update_visit_current_node` + view + relay là choreography rời. |
| 20.6 | Full event sourcing cho mọi bảng | ✅ không mắc | và thiết kế này cũng không. |
| 20.7 | Phát event trước khi transaction chắc chắn | ✅ không mắc | event ghi cùng transaction; relay đọc sau commit. (`EventService.record_and_publish` publish *sau* commit, đúng.) |
| 20.8 | Direct write vào projection | 🟡 | các cột `status` được UPDATE thẳng — xem [[state-la-projection|State chỉ là projection]]. |
| 20.9 | **Coi "sent" là "done"** — «Một trong những lỗi nguy hiểm nhất của workflow software.» | ❌ **mắc** | relay `_mark_published` sau `send_telegram`. |
| 20.10 | AI inference không provenance | ✅ không mắc | `triage_model/reason/classified_at`; nhưng chưa có expiry/confidence. |

Bốn cái mắc (20.1, 20.2, 20.5, 20.9) đóng bằng ba việc: cửa ghi sự kiện duy nhất có causation ([[tk-emit-function|ghi_su_kien()]]), tách delivery khỏi ledger ([[tk-communication-delivery|notification_delivery]]), và policy/process manager ([[tk-policy-engine|policy + policy_case]]).

## Nối tới
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[gap-communication|Khoảng cách 8]]
- [[gap-process-manager|Khoảng cách 7]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-policy-engine|policy + policy_case]]
- [[state-la-projection|State chỉ là projection]]

## Được dẫn từ
- [[event-first-dao-nhan-qua|Event-first]]
- [[notification-relay|notification_relay]]
- [[gap-crud-roi-log|Khoảng cách 2]]
