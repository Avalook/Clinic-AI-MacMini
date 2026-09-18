---
title: "Product surface sinh ra từ event model — ATC card, Event Timeline, 'Why am I seeing this', Replay"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §19 · Pilot §6 · Work Item §15"
tags: [clinicai, lop2-kien-truc]
---

# Product surface sinh ra từ event model — ATC card, Event Timeline, 'Why am I seeing this', Replay

> [!abstract] Event-driven phải đổi sản phẩm, không chỉ backend: 9 trường trên mỗi card, timeline có filter, mọi cảnh báo giải thích được.

> «Event-driven architecture phải thay đổi sản phẩm, không chỉ backend.» — *§19*

**Air Traffic Control** (*§19.1*) — mỗi card encounter: current projected state · state age · event gần nhất và thời điểm · commitment đang mở · owner · SLA/timer · experience risk · **data freshness** · đề xuất action và lý do.

**Event Timeline** (*§19.2*) — mỗi encounter, filter: clinical · operational · communication · decision · automation · correction · integration failure.

**"Why am I seeing this?"** (*§19.3*) — mọi cảnh báo/đề xuất giải thích: event nào kích hoạt · rule/model nào · evidence · confidence · action đề xuất · ai có quyền quyết định.

**Replayable operations review** (*§19.4*) — xem lại một ca: bottleneck bắt đầu từ event nào · ai nhận ownership · ack trễ bao lâu · communication có bao phủ thời gian chờ không · intervention nào tạo outcome · policy nào cần sửa.

Work Item §15 thêm ba màn: **My Work** (ưu tiên theo authority/urgency/deadline; một primary action; ack/claim nhanh; «Vì sao tôi nhận việc này?»; dấu hiệu clinical/operational tách) · **Team Queue** (unclaimed/assigned/blocked/overdue; «không che giấu work cũ vì sort theo việc mới») · **ATC** (open commitments; unowned/unacknowledged; approaching SLA; overload; escalation; history reassignment).

Pilot §6.3 **Patient panel**: số thứ tự/tên hoặc mã · bước hiện tại · hướng dẫn vị trí · dự kiến bước tiếp theo · thông báo chờ đã được phê duyệt.

### Màn hình hiện có, và thiếu trường nào

| Màn | Có | Thiếu so với thesis |
|---|---|---|
| `/truong-ca` (overview) — `dispatch_service._OVERVIEW_SQL` | current node, room, floor, wait/total minutes, threshold, done_steps, route_steps, next_step, queue_number, doctor | commitment đang mở + owner, SLA, experience risk, **freshness**, lý do đề xuất |
| `/truong-ca/canh-bao` — `build_alerts` | 4 loại, severity 2 mức, patients affected, câu tiếng Việt | «why» có sẵn trong message ✓ nhưng không event_id/rule_id; không ack/owner |
| `/truong-ca/hang-doi` — `_STATIONS_SQL` | serving/waiting/max/avg wait, capacity, accepting, floor | overload là màu, không phải event |
| `/truong-ca/lich-su` — `v_dispatch_history` | ai chuyển ai từ đâu tới đâu vì sao | chỉ `dispatch.*`, không phải timeline đủ loại |
| `/tasks`, `/work-items` — `list_worklist` | `actionable_by_me`, `blocked`, blockers endpoint («so the UI can say why a button is disabled» ✓) | acknowledge, due_at trống, không "why assigned" |
| `/display` — TV gọi số | số + phòng | bước tiếp theo, thông báo chờ |
| `/audit-log` — `v_audit_log` | event_log có nhãn Việt | không filter theo stream/loại; MANAGEMENT-only |

Thiết kế: [[tk-atc-ui|Giao diện]].

## Nối tới
- [[tk-atc-ui|Giao diện]]
- [[man-hinh-theo-vai|55 màn theo 13 vai]]
- [[dispatch|Điều phối Trưởng ca]]
- [[workflow-kernel|Workflow kernel]]
- [[gap-atc|Khoảng cách 12]]

## Được dẫn từ
- [[humane-ops|Design for Humane Operations]]
- [[stream-boundary|Năm stream]]
- [[dispatch|Điều phối Trưởng ca]]
- [[man-hinh-theo-vai|55 màn theo 13 vai]]
- [[gap-atc|Khoảng cách 12]]
- [[tk-atc-ui|Giao diện]]
