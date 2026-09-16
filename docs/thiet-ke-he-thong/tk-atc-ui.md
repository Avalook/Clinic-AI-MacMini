---
title: "Giao diện — không thêm màn; thêm trường vào card, cảnh báo thành việc có id, 'Vì sao tôi thấy cảnh báo này'"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "/truong-ca/* · /tasks · /display · /audit-log · DESIGN.md"
tags: [clinicai, lop5-thiet-ke]
---

# Giao diện — không thêm màn; thêm trường vào card, cảnh báo thành việc có id, 'Vì sao tôi thấy cảnh báo này'

> [!abstract] ATC card 9 trường, My Work có ack + why, Team Queue có unclaimed/overdue, Timeline có filter loại; mọi bậc kích thước theo DESIGN.md.

Nguyên tắc: **màn cũ, dữ liệu mới**. Backend đã có endpoint gói một vòng cho mỗi màn (Luật 5.1); thêm trường vào response, không thêm endpoint. Giao diện chỉ vẽ (Luật 3.1), mọi nhãn/màu trạng thái lấy từ `work-item-status.ts` (đã tồn tại: «The status vocabulary, reconciled» — thêm `assigned`, `acknowledged`, `blocked`, `escalated` đúng chỗ đó, không đẻ từ vựng mới).

### Card ATC (`/truong-ca`, `_overview_row`)

| Trường thesis §19.1 | Nguồn |
|---|---|
| current projected state | có |
| state age | có (`wait_minutes`) |
| event gần nhất + thời điểm | `v_timeline_luot_kham` `max(seq)` → `last_event_type`, `last_event_at` |
| commitment đang mở | `work_item` PENDING/ASSIGNED/ACKNOWLEDGED/IN_PROGRESS/BLOCKED của visit: `[{node_name, status, owner, due_at}]` |
| owner | `assigned_to` (tên) hoặc `assigned_queue` (vai) của việc **đang chặn bước tiếp theo** |
| SLA/timer | `expectation` OPEN gần nhất: `deadline_at`, `on_deadline` → «còn 8 phút» / «quá hạn 12 phút» (dùng `minutesPastDue` sẵn có) |
| experience risk | `experience_state` mở: chip theo `severity`, nhãn từ `experience_config.nhan` |
| data freshness | `now() − last_event_at`; > `experience_config.freshness_stale_min` (mặc định 20′) → chip «Chưa có tin mới N phút» (Care Model §16) |
| đề xuất action + lý do | từ `policy.decided` gần nhất: `action` + «vì»: `trigger event nhãn` + `rule name v.N` |

### Cảnh báo (`/truong-ca/canh-bao`)

`build_alerts()` giữ nguyên cho `room_overloaded`/`no_route` (tính lúc đọc — chúng là *tình trạng*, không phải commitment). `wait_too_long` và `missing_next_step` **đổi nguồn** sang `experience_state` + `work_item` mở → có `id`, có nút **Nhận** (ack), **Bỏ qua** (dismiss, bắt lý do), **Gọi bộ phận** (đã có → `thong_bao` mang `work_item_id`). Mỗi cảnh báo có nút «Vì sao?» mở panel §19.3: event kích hoạt (nhãn + giờ), luật (tên + version), bằng chứng (`evidence_event_ids` → dòng timeline), confidence, hành động đề xuất, ai được quyết (`override_roles`/`confirm_roles`).

### My Work (`/tasks`) và Team Queue (`/work-items?workspace=`)

Thêm cột từ [[tk-work-item-protocol|Work Item Protocol trên kernel]]: `owner_type/assigned_queue`, `acknowledge_by/due_at` (→ «Quá SLA» overlay đã có logic), `origin_event` nhãn («Vì sao tôi nhận việc này?» — Protocol §15), `completion_criteria.type` → nút primary đúng nghĩa («Đã giải thích cho khách» mở form attestation thay vì tick). Team Queue: tab unclaimed / assigned / blocked / overdue; **không** sort theo mới nhất mặc định («không che giấu work cũ»).

### Patient panel (`/display`)

Thêm «bước tiếp theo» (`next_step_of`) và dòng thông báo chờ đã duyệt (`experience_config.thong_bao_cho` theo phòng) — QUEUE-03: không tên đầy đủ, không chẩn đoán.

### Timeline (`/patients/[id]` → VungLamViecKhach, `/audit-log`)

Đọc `v_timeline_luot_kham`, filter theo `category` (clinical/operational/communication/decision/reliability) — §19.2. Dòng `inferred` vẽ khác `observed` (đúng Spec §3 «Không được hiển thị một suy luận như sự thật»): cùng bậc màu nhưng viền đứt + confidence — chọn từ thang DESIGN.md, không tự chế px (ratchet 102).

### Nghiệm thu

Kịch bản bấm thử theo Luật 12.4 (không code): (1) chuyển khách vào SA1, đợi quá `wait_minutes` giả 1′ → card hiện risk + việc GIAI_THICH_CHO cho CSKH; (2) CSKH bấm Nhận → chip «đã nhận» ở Trưởng ca; (3) không nhận 5′ → Trưởng ca có thông báo; (4) CSKH ghi «Đã giải thích» → risk resolved, timeline có đủ 6 dòng theo thứ tự. Đủ ba cỡ 375/768/1280 (DESIGN.md).

## Nối tới
- [[product-surface|Product surface sinh ra từ event model]]
- [[gap-atc|Khoảng cách 12]]
- [[man-hinh-theo-vai|55 màn theo 13 vai]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-experience-state|experience_state]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-projections|Projection có kỷ luật]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[dispatch|Điều phối Trưởng ca]]

## Được dẫn từ
- [[failure-la-domain|Failure là một phần của domain]]
- [[product-surface|Product surface sinh ra từ event model]]
- [[dispatch|Điều phối Trưởng ca]]
- [[man-hinh-theo-vai|55 màn theo 13 vai]]
- [[gap-failure-domain|Khoảng cách 11]]
- [[gap-atc|Khoảng cách 12]]
- [[phase-b-exceptions|Phase B]]
