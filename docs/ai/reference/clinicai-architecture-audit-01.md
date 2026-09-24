# CLINICAI ARCHITECTURE AUDIT 01
EVENT / STATE / COMMAND / WORK ITEM / OUTBOX

**Baseline (STEP 0)**  
- Path: `/Users/quangdang/Projects/Dr4Women-MacMini`  
- Branch: `codex/auto-lot-from-main`  
- HEAD: `0209df61a5b97906cb2d3f6b54e170ead3c13ae9`  
- Working tree: **DIRTY** (local mods + untracked docs/migrations; audit did not change any project file)  
- Scope: read-only. No Kafka/microservices pitch.

**Verdict ngắn:** ClinicAI đang **event-aware / outbox-lite**, không phải broker-centric event-driven. Lõi vận hành thật = DB state + `event_log` (audit + notification flag) + `work_item` command API + `pos_outbox` + LISTEN/NOTIFY realtime. RabbitMQ `event_bus` = skeleton / UNUSED in prod path.

---

## I. EVENT ARCHITECTURE HIỆN TẠI

```
[API / SQL function]
        |
        v
 +------------------+     same txn (typical via record_event)
 | Domain tables    |----------------------------------+
 | appointment,     |                                  |
 | visit, payment,  |                                  v
 | work_item, ...   |                        +------------------+
 +--------+---------+                        | event_log        |
          |                                  | MIXED_CONCERN:   |
          | FOR UPDATE + version             |  audit trail     |
          v                                  |  + notify outbox |
 +------------------+                        |  (event_published|
 | work_item_event  |<-- ATOMIC w/ work_item |   boolean)       |
 | (lifecycle log)  |                        +--------+---------+
 +------------------+                                 |
                                                      | poll / LISTEN
                      +-------------------------------+---------------+
                      v                               v               v
           +------------------+            +----------------+   +-----------+
           | notification_    |            | ChangeBroker   |   | (future)  |
           | relay (--relay)  |            | LISTEN/NOTIFY  |   | consumers |
           | Telegram (+Zalo) |            | → SSE UI       |   |  BLOCKED  |
           | flips published  |            +----------------+   | by 1 bool |
           +------------------+                                 +-----------+

[SEPARATE seam — ADR-0010]
 payment/stock txn → pos_outbox (PENDING/DEAD, attempts) → pos_relay → KiotViet

[UNUSED / STUB]
 InteractionEvent → EventService.record_and_publish → RabbitMQPublisher
 (tools/event_log/append + unit tests; RabbitMQ raises NotImplementedError)
```

---

## II. NHỮNG GÌ ĐANG LÀM ĐÚNG

1. **`record_event` transactional-by-design** — `audit.py` nhận `conn` của caller; docstring + INSERT cùng transaction với write nghiệp vụ (“commits with the write… or not at all”). Payload cố ý chỉ ID/field names, không PHI clinical text.

2. **Work-item = command API, không PATCH status** — `work_item_service.py` + `routers/work_items.py`: lệnh `start|complete|skip|cancel`; role gate; SQL `work_item_gate_blockers`; optimistic concurrency (`version` / `expected_version` → 409); `work_item` UPDATE + `work_item_event` INSERT **cùng transaction**. Idempotency-Key bắt buộc ở router.

3. **`pos_outbox` đúng transactional outbox** — `pos_outbox.py` enqueue trên `conn` caller; unique `(clinic_id, kind, subject_id)`; status `DEAD` khi void trước khi gửi; migration `20260730000007` ghi rõ vì sao **tách** khỏi `event_log` (một boolean không phục vụ hai consumer).

4. **Realtime không phụ thuộc Supabase replication** — `change_broker.py` LISTEN `clinicai_changes` (NOTIFY lúc COMMIT); phù hợp DB thuê không có REPLICATION privilege.

5. **Notification relay có claim tối thiểu** — `notification_relay.py`: advisory lock theo `event_id`, re-check `event_published`, retry ngắn trong poll; worker `--relay` / `--pos-relay` tách RabbitMQ.

6. **Schema đã dự phòng envelope** — `event_log` có `event_id`, `event_version`, `correlation_id`, `causation_id`, `occurred_at`, `recorded_at` (`20260714000001_baseline_schema.sql`).

---

## III. ARCHITECTURE GAPS

### G1. `event_log` mang nhiều trách nhiệm (MIXED)
- **Evidence:** `audit.py` = audit trail; `notification_relay.py` polls `event_published=FALSE` rồi Telegram; script `danh-dau-event-cu-truoc-khi-bat-telegram.sql` thừa nhận flag của notification-relay; audit UI đọc cùng bảng (`audit_log_service.py`).
- **Risk:** Bật consumer mới (AI/Analytics) tranh cùng flag → mất notify hoặc “đã published” sai nghĩa.
- **Cản mở rộng:** Module mới không subscribe an toàn; phải đụng producer hoặc cướp flag.
- **Severity:** HIGH

### G2. Một boolean `event_published` ≠ per-consumer delivery
- **Evidence:** Migration POS: “One flag cannot serve two consumers.” Relay `_mark_published` sau Telegram **hoặc** khi không có template (skip cũng mark TRUE).
- **Risk:** “Published” = “đã xử lý bởi relay notify”, không phải “domain event đã phát cho mọi subscriber”.
- **Cản mở rộng:** Telegram + Zalo + AI + Analytics không biểu diễn được bằng 1 bit.
- **Severity:** HIGH

### G3. RabbitMQ event bus chưa production
- **Evidence:** `RabbitMQPublisher.publish` → `NotImplementedError`; `EventService` chỉ wire qua `tools/event_log/append` + tests; `worker` default RabbitMQ mode opt-in; prod path khuyến nghị `--relay`.
- **Risk:** Tưởng hệ “đã có event bus” trong khi runtime thật là poll DB.
- **Cản mở rộng:** Không có broker subscribe thật; adapter/golden_record gắn InteractionEvent gần như unused operationally.
- **Severity:** MEDIUM (nếu chấp nhận outbox-poll là chiến lược chính thì là gap tài liệu/expectancy, không phải bug)

### G4. Không có dead-letter / inbox cho `event_log` notify path
- **Evidence:** Relay: fail → để `event_published=FALSE` retry poll sau; không bảng quarantine; không consumer inbox/idempotency key per delivery. POS có `DEAD`/`attempts` — `event_log` thì không.
- **Risk:** Poison event / Telegram down kéo backlog; double-send nếu hai worker race trước khi flip (mitigate một phần bằng advisory lock, không phải inbox).
- **Cản mở rộng:** Khó SLA multi-consumer.
- **Severity:** MEDIUM

### G5. Envelope “đầy đủ” trên schema nhưng code phụ thuộc ít
- **Evidence:** `causation_id` chỉ thấy trong schema/FK, **không** thấy write path Python; `correlation_id` optional trên `record_event`; `InteractionEvent` dùng `trace_id`/`entity_*` khác naming `event_log.aggregate_*`.
- **Risk:** Hai “event models” (DB audit vs InteractionEvent) lệch contract.
- **Cản mở rộng:** Consumer mới không biết field nào là truth.
- **Severity:** MEDIUM

### G6. Lego modules vẫn hay phải gọi vào service cũ
- **Evidence:** `tep_ket_qua_service` sau upload gọi `bao_ket_qua_ve` → `ThongBaoService` (imperative), không emit `ResultReady` chuẩn cho subscriber; AI chờ khách phải đọc state/queue hoặc hook flow.
- **Risk:** Mỗi module mới = chỉnh producer.
- **Severity:** HIGH cho mục tiêu “chỉ subscribe”

---

## IV. MIXED CONCERNS

| Artifact | Roles mixed |
|----------|-------------|
| `event_log` | **B AUDIT** + **D NOTIFICATION outbox** (+ thỉnh thoảng mang tín hiệu domain trong `event_type`) — **MIXED_CONCERN** |
| `event_published` | Delivery ack cho notification-relay (và skip-no-template), **không** phải “đã publish domain event” |
| `work_item_event` | **C WORK_ITEM_EVENT** sạch (lifecycle command history) |
| `pos_outbox` | **F TECHNICAL** reliability outbox (POS) — tách đúng |
| `clinicai_changes` NOTIFY + ChangeBroker | **E REALTIME_SIGNAL** (UI refresh), không phải domain bus |
| `InteractionEvent` / `event_bus/*` | Intended **A DOMAIN_EVENT** bus — **UNUSED/STUB** in prod |

Phân loại nhanh các “event” đang gọi:
- `record_event` / INSERT `event_log` từ booking, payment, luot_kham, clinical_*, pharmacy, … → chủ yếu **B**, flag **D**
- `work_item_event` → **C**
- NOTIFY/SSE → **E**
- `pos_outbox` → **F**
- `InteractionEvent` → intended **A**, runtime gần như không

---

## V. LEGO TEST

### A. AI phát hiện khách chờ lâu
- **Hôm nay:** PARTLY_COUPLED → thiên **TIGHTLY_COUPLED** nếu muốn “chỉ subscribe”. Không có stream domain wait-time; phải poll `appointment`/`work_item`/queue projections hoặc chèn hook vào check-in / vitals / room services (`luot_kham_service`, board/phòng).
- **Pluggable path gần nhất:** cron/worker đọc projection + tạo work_item/follow_up — **không** cần sửa domain nếu chấp nhận polling state (không phải event subscribe).

### B. Gửi Zalo sau ResultReady
- **Hôm nay:** PARTLY_COUPLED. Kết quả đi `tep_ket_qua_service` → `bao_ket_qua_ve` / `ThongBaoService` (imperative). Relay chỉ render template theo `event_type` có trong `notification_templates`; mark published kể cả khi không template.
- Muốn Zalo độc lập: hoặc mở rộng relay (vẫn 1 flag — conflict với G1/G2), hoặc tách delivery table — **phải đổi** outbox semantics, không chỉ subscribe.

### C. Analytics check-in → service start
- **Hôm nay:** PARTLY_COUPLED. Có thể đọc `appointment.checked_in` timestamps + `work_item`/`service.started` / `started_at` từ DB (projection). Event types tồn tại trong `audit_labels` (`appointment.checked_in`, `service.started`, `vitals.*`) nhưng không có analytics consumer/outbox riêng.
- Pluggable nếu analytics = batch SQL trên state/event_log; **không** pluggable nếu muốn realtime subscribe không đụng schema delivery.

| Module | Rating |
|--------|--------|
| A AI wait | PARTLY_COUPLED (poll state) / TIGHTLY_COUPLED (pure event) |
| B Zalo ResultReady | PARTLY_COUPLED |
| C Analytics duration | PARTLY_COUPLED (batch) |

---

## VI. TOP 5 VIỆC NÊN CHỐT VỀ THIẾT KẾ (KHÔNG CODE)

1. **Tách trách nhiệm `event_log`:** audit append-only vs notification/outbox delivery — một bảng một việc, hoặc audit im + delivery table riêng (đã học từ `pos_outbox`).

2. **Per-consumer delivery state** thay cho một `event_published` boolean (Telegram / Zalo / AI / Analytics / realtime projection mỗi cái một cursor/inbox).

3. **Chốt chiến lược bus:** (a) DB outbox + relay là production truth, RabbitMQ/`InteractionEvent` là future — hoặc (b) invest broker; đừng để cả hai “có vẻ tồn tại”.

4. **Chuẩn hóa contract runtime:** field nào bắt buộc trên mọi write (`event_type`, `clinic_id`, actor metadata, `aggregate_*`); `correlation_id`/`causation_id` dùng hay bỏ; thống nhất naming InteractionEvent vs `event_log`.

5. **Public integration seam cho module Lego:** “sau ResultReady / CheckedIn / ServiceStarted, module ngoài được phép làm gì mà không sửa service cũ” — subscribe delivery | read projection | tạo work_item/command — và cấm hook vào giữa transaction nghiệp vụ trừ khi ADR cho phép.

---

## Phụ lục nhanh — STEP 3 transactional integrity (tóm tắt)

| Flow | Kết luận | Evidence ngắn |
|------|----------|----------------|
| appointment / check-in | ATOMIC (typical) | transition + event_log cùng path `booking_service` / SQL `check_in_appointment` |
| vitals | ATOMIC | `luot_kham_service` `record_event` trong txn (`vitals.*`) |
| clinical record | ATOMIC | `clinical_record_service` + `record_event` |
| service order | ATOMIC | `service_order_service` txn + `record_event` |
| payment | ATOMIC (+ POS outbox) | payment + `event_log` + `pos_outbox.enqueue` cùng `conn` |
| service execution / work item | ATOMIC | `work_item` + `work_item_event` một txn |
| result (`tep_ket_qua`) | ATOMIC audit; notify path imperative/after | `record_event` + `bao_ket_qua_ve` |
| pharmacy | ATOMIC (typical) | txn + INSERT `event_log` |
| staff capability | UNKNOWN/PARTIAL | capability CRUD; `record_event` có trên staff writes — verify từng path khi cần |

## Phụ lục — STEP 7 event bus rating

| Piece | Rating |
|-------|--------|
| publisher (RabbitMQ) | STUB |
| publisher (Mock) | PRODUCTION_READY for tests only |
| consumer | PARTIAL skeleton / UNUSED in recommended deploy |
| broker | UNUSED (infra pending) |
| retry (MQ) | STUB/absent |
| ack (MQ `message.process`) | PARTIAL in skeleton |
| idempotency (MQ) | UNUSED |
| notification relay | PARTIAL→usable PRODUCTION_READY for single-consumer notify |
| pos_outbox+relay | PRODUCTION_READY pattern |

## Phụ lục — STEP 5 envelope (thực tế phụ thuộc)

| Field | Schema | Code phụ thuộc? |
|-------|--------|-----------------|
| event_id | yes | yes (relay mark/lock; EventService) |
| event_type | yes | yes (templates, labels, filters) |
| event_version / schema_version | `event_version` default 1 | hầu như không đọc trong app paths |
| occurred_at / recorded_at | yes | yes (ordering poll, UI) |
| clinic_id | yes (tenant) | yes |
| actor | via `metadata` JSON | yes (`clinic_staff_id`, roles) |
| subject | `aggregate_type`/`aggregate_id` | yes |
| correlation_id | yes | optional write; ít dùng |
| causation_id | yes FK | **không thấy write** |
| stream_id / stream_version | no | no |
| privacy metadata | implicit (no PHI in payload policy) | convention in `audit.py` |
| payload | yes | yes |
| event_published | yes | **critical** for relay |

InteractionEvent fields used by stub path: `event_id`, `clinic_id`, `event_type`, `entity_type`, `entity_id`, `payload`, `trace_id`, `occurred_at`, `source_channel` — parallel vocabulary, not the audit writer path.

---

**DỪNG REVIEW.** Không patch, không đề xuất Kafka.
