---
title: "Năm stream — Encounter · Work Item · Episode · Resource · Communication"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §6"
tags: [clinicai, lop2-kien-truc]
---

# Năm stream — Encounter · Work Item · Episode · Resource · Communication

> [!abstract] Event phải thuộc một stream có ownership và invariant; không có 'global stream' vô cấu trúc.

> «Không nên tạo một "global stream" vô cấu trúc rồi mong analytics tự hiểu. Event cần được tổ chức theo stream có ownership và invariant.» — *§6*

| Stream | Nội dung (thesis) | Khoá tự nhiên trong code | Đang ghi ở đâu |
|---|---|---|---|
| **Encounter** | check-in · node · order/result · handoff · delay · completion · cancellation · checkout | `visit.visit_id` | `event_log` (`dispatch.*`, `visit.checkin`), `work_item_event`, `visit_route` |
| **Work Item** | created · assigned · claimed · acknowledged · started · blocked · reassigned · completed · expired · cancelled · escalated | `work_item.id` | `work_item_event` (chỉ 6 lệnh, prod chỉ có `create`) |
| **Episode** | opened · follow-up expected · contacted · booked · adherence · closed | `care_episode.id` | `event_log episode.closed/reopened`; `nhac_tai_kham` |
| **Resource** | shift started · available · room occupied · equipment unavailable · capacity changed · overload · restored | `staff.id` / `clinic_room.id` | `event_log roster.*`; tải phòng tính lúc đọc (`_STATIONS_SQL`) |
| **Communication** | requested · sent · delivery confirmed · patient acknowledged · explanation recorded · failed · retry | `patient.clinic_patient_id` (+ appointment) | `tuong_tac_cskh` (append-only), Telegram relay không để lại vết per-message |

> «Work Item không chỉ là một row có status = done; nó là một commitment có lịch sử ownership.» — *§6.2*

### Vì sao stream quan trọng với thiết kế

Hai thứ cần stream: **ordering** (§15.2: «Chỉ bảo đảm thứ tự trong boundary hợp lý, ví dụ một Encounter Stream») và **timeline cho người đọc** (§19.2: mỗi encounter có timeline với filter clinical/operational/communication/decision…).

Hôm nay muốn xem "mọi thứ đã xảy ra với lượt khám X" phải join 5 bảng theo 5 khoá khác nhau. `v_audit_log` (migration `20260805000001`) là view gộp — hình dạng gần với timeline, nhưng đọc `event_log` thôi.

Thiết kế: [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]] đặt quy ước `stream_id` = `enc:<visit_id>` · `work:<work_item_id>` · `epi:<episode_id>` · `res:<staff|room id>` · `comm:<patient_id>` và **cột `stream_version` do trigger cấp** — mọi sổ chuyên biệt vẫn giữ, nhưng đều đổ về `event_log` với `stream_id`.

## Nối tới
- [[event-envelope|Event envelope chuẩn]]
- [[so-cai-phan-manh|Bảy sổ cái rời]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[reliability|Reliability semantics]]
- [[product-surface|Product surface sinh ra từ event model]]

## Được dẫn từ
- [[event-envelope|Event envelope chuẩn]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[so-cai-phan-manh|Bảy sổ cái rời]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
