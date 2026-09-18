---
title: "event_log — 14 cột, 17 loại, 449 dòng, 29 chỗ ghi"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "supabase/migrations · đo prod 05/09/2026"
trang_thai: Một phần
tags: [clinicai, lop3-code]
---

# event_log — 14 cột, 17 loại, 449 dòng, 29 chỗ ghi

> [!abstract] Sổ sự kiện append-only có thật, nhưng 62% là nhiễu slot_hold, 0% correlation, actor chìm trong JSON, không cửa ghi duy nhất.

### Lược đồ (prod)

`event_id uuid · event_type text · event_version int · aggregate_type text · aggregate_id uuid · payload jsonb · metadata jsonb · correlation_id uuid · causation_id uuid · source text · occurred_at timestamptz · recorded_at timestamptz · event_published bool · clinic_id uuid`

Trigger: `trg_event_log_no_update`, `trg_event_log_no_delete` (append-only thật), `trg_notify_event_log` **chỉ AFTER INSERT** («Nghe cả UPDATE là relay tự đánh thức mình sau mỗi lần gửi» — `20260815000003`). RLS: MANAGEMENT trong tenant.

### Đo trên prod 05/09/2026

| event_type | số | từ → đến |
|---|---|---|
| `slot_hold.created` / `.released` | 175 / 106 | 17/08 → 01/09 |
| `patient.created` | 67 | 19/08 → 01/09 |
| `appointment.created` | 66 | |
| `cskh.tuong_tac` / `_hoan_tac` | 16 / 6 | |
| `roster.shift_added_cho_xep`, `roster.week_applied` | 2 / 2 | |
| `appointment.checked_in`, `.completed`, `.rescheduled` | 1 / 1 / 1 | |
| `dispatch.checkin`, `.checkout` | 1 / 1 | |
| `thong_bao.hen_goi_lai`, `.tuan_lich_truc` | 1 / 1 | |
| `patient.phone_added`, `.phone_removed` | 1 / 1 | |

- **281/449 = 62,6%** là `slot_hold` — giữ chỗ khung giờ 10 phút trên giao diện: telemetry của thao tác đặt lịch, không phải mốc chăm sóc.
- `correlation_id` khác NULL: **0**. `causation_id` khác NULL: **0**. `event_version` distinct: **1**.
- `recorded_at − occurred_at`: max **0 giây** trong ảnh chụp cũ. Đây **không** phải bằng chứng "chưa từng có ghi bù/ghi trễ ngoài đời": cả hai cột đều `DEFAULT now()` (`baseline_schema.sql:539-540`) và đường ghi truyền thẳng `now()` (`tuong_tac_cskh_service.py:249-256`), nên chúng bằng nhau **do cấu tạo**. Điều đọc được chỉ là: chưa đường ghi nào truyền `occurred_at` thật của sự việc. Độ trễ thực tế (khách đến 10:17, nhân viên bấm 10:40) hiện **không đo được**.
- `metadata` có `clinic_staff_id`: 424/449; `actor_auth_user_id`: 421; 24 dòng để `by_staff_id` trong **payload** (một số service ghi actor sai chỗ).
- `event_published = TRUE`: 449/449 — **cờ này KHÔNG chứng minh relay đã chạy hay tin đã tới nơi.** Có ít nhất hai cơ chế đặt được cờ này, và số đo không nói cơ chế nào đã đặt dòng nào: `scripts/danh-dau-event-cu-truoc-khi-bat-telegram.sql` UPDATE hàng loạt mọi dòng `FALSE` thành `TRUE` mà **không gửi gì** (bản thân tệp ghi ~1.164 dòng ở thời điểm 15/08 — nhiều hơn 449 dòng tôi đếm được, nên hai con số này thuộc hai phạm vi khác nhau và chưa đối chiếu được), và `notification_relay` đặt cờ ở **hai nhánh khác nhau**: nhánh không có template (`notification_relay.py:205-214`) đánh dấu rồi `continue` — **không gửi gì cả** — còn nhánh gửi được mới đánh dấu sau khi nhà cung cấp trả `ok` (`:238`). Bốn thứ phải tách: `processed` trong log (`:256`, cộng cả hai nhánh) · không có template (đặt cờ, không gửi) · nhà cung cấp trả ok · người nhận đã biết (không có gì trong hệ biểu diễn điều này). Nhánh thiếu cấu hình nhà cung cấp (`result["skipped"]`) thì **không** đặt cờ, để lại cho vòng sau. Muốn biết relay thật sự đưa tin thì phải đọc log `relay_poll_complete`/`relay_delivery_failed` hoặc lịch sử nhóm Telegram, không phải đọc cờ. *Chưa xác minh lại ở vòng này.*
- `source`: 12 chuỗi tự do (`api:booking` 281, `api:patient-intake` 67, `cskh.customers` 23, `config.roster` 3, `api` 2…).

### Ai ghi

`grep "INSERT INTO event_log"` trong `src/clinicai`: **29 chỗ** ở 21 file service (`booking_service.py:2019`, `patient_service.py:185/578/640`, `payment_service.py:387`, `dispatch_service.py:345`, `tuong_tac_cskh_service.py:249/380`, `config_service.py:265/614/694`, `lab_safety_service.py:331`…). Cộng 2 hàm SQL (`move_visit_to_station`, check-in). Có `services/audit.py:record_event()` — một cửa chung — nhưng chỉ vài nơi dùng.

Hai cách ghi metadata khác nhau cùng tồn tại: `{"actor_auth_user_id","clinic_staff_id","clinic_role"}` (đa số) và `{"trace_id"}` (`EventService.record_and_publish`, đường tool/orchestrator).

### Đọc ra được gì

1. Bảng **đúng hình** (append-only, có correlation/causation, có hai mốc giờ) nhưng **không ai điền phần hình ấy** — vì không có cửa ghi bắt buộc điền.
2. Nhiễu 62% **không** làm `event_log` vô dụng — nó đang được đọc thật: `AuditLogService.events()` (`audit_log_service.py:191`) đọc `v_audit_log`, UNION với `work_item_event`, giải nghĩa actor/subject/action rồi trả cho màn `/audit-log`. Ba việc phải tách bạch: (a) **lọc telemetry** — `v_audit_log` không lọc `slot_hold` (migration `20260805000001` còn ép bất biến "một dòng vào, một dòng ra"), nên dòng giữ chỗ **có thể lấn** cửa sổ `LIMIT 200` chung cho hai nguồn. Tỷ lệ 62% là của **toàn bộ lịch sử**, không suy ra được thành phần của 200 dòng mới nhất — hai thứ khác nhau, và mẫu hiện tại chưa đo *(phép đo còn thiếu: đếm `event_type` trong 200 dòng đầu của chính câu SQL ấy)*; (b) **độ đầy đủ/ngữ nghĩa domain event** — thiếu envelope và thiếu event vòng đời, đây mới là khoảng cách thật; (c) **replay** — chưa dựng lại được projection từ stream, vì (b) chứ không vì (a).
3. Độ phủ: **1 dòng `appointment.checked_in` trên 66 lịch đã tạo — con số này KHÔNG chứng minh mất event.** Mẫu số sai: 66 là số lịch *đã tạo*, không phải số khách *đã thật sự đến*; lịch tương lai, huỷ và no-show không bao giờ sinh `checked_in`. Và mốc quầy CSKH **không** phải một đường riêng: nó gọi `_doi_trang_thai_lich` (`tuong_tac_cskh_service.py:188-191`) → `BookingService.apply_action(action="checkin")` (`tuong_tac_cskh_service.py:437-446`) → chuyển trạng thái `CHECKED_IN` + `_log(event_type="appointment.checked_in")` + `_open_visit`, tất cả trong một transaction (`booking_service.py:273-274` định nghĩa chuyển tiếp, `booking_service.py:819-840` ghi event rồi mở lượt khám). Nút lễ tân (`booking.py:482`) hội tụ vào đúng hàm ấy. **Có một nhánh thứ hai cùng phát event này**, không đi qua `apply_action`: đặt lịch kênh `WALK_IN` trong ngày bật `auto_checkin` (`booking_service.py:464`) và tự ghi `appointment.checked_in` kèm `auto_walk_in: True` rồi mở lượt khám (`booking_service.py:623-637`). Mẫu đo 0 khách vãng lai **không** cho biết nhánh ấy đã từng chạy hay chưa: nó là ảnh chụp một thời điểm của bảng lịch hẹn, không phải lịch sử thực thi. Muốn biết thì phải đi đúng đường dữ liệu: `_log` ghi `origin` vào **cột `source`** *và* vào `metadata->>'origin'` (`booking_service.py:2019-2036`) — **không có cột tên `origin`**. Phép đo: đếm `event_log` có `source = 'api:appointment-walkin-autocheckin'` hoặc `metadata->>'origin'` bằng chuỗi ấy (hoặc `payload->>'auto_walk_in'`), lọc theo `clinic_id` và một khoảng thời gian rõ ràng. *Chưa chạy.* Nên phát biểu đúng phạm vi là *hai nhánh đã biết, cùng một tên event*, không phải "một cửa ghi duy nhất toàn hệ". Nếu lịch đã ở `CHECKED_IN`/`COMPLETED` thì hàm trả `False` và **cố ý** không ghi gì — đó là chống bấm trùng, không phải mất event. Cái đo được thật là: `visit` gần như không có event vòng đời.

Thiết kế: [[tk-event-envelope-v2|Envelope v2]] (cột), [[tk-emit-function|ghi_su_kien()]] (cửa ghi), [[tk-event-catalog-table|event_catalog]] (đuổi slot_hold sang telemetry).

## Nối tới
- [[event-envelope|Event envelope chuẩn]]
- [[gap-envelope|Khoảng cách 1]]
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-event-catalog-table|event_catalog]]
- [[audit-labels|audit_labels.EVENT_LABELS]]
- [[notification-relay|notification_relay]]

## Được dẫn từ
- [[5-loai-event|Năm loại event]]
- [[event-envelope|Event envelope chuẩn]]
- [[audit-labels|audit_labels.EVENT_LABELS]]
- [[notification-relay|notification_relay]]
- [[so-cai-phan-manh|Bảy sổ cái rời]]
- [[gap-envelope|Khoảng cách 1]]
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[tk-emit-function|ghi_su_kien()]]
