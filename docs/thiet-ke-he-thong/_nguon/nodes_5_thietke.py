# -*- coding: utf-8 -*-
"""Lớp 5 — THIẾT KẾ ĐÍCH: từng mảnh có lược đồ, hàm, ràng buộc CI, và
lý do không làm cách khác. Tuân Luật 7.1 (chỉ Postgres), 8.1 (vết cùng
transaction), ADR-0003 (bất biến ở DB)."""

L = 5

NODES = [
{
 "id": "tk-nguyen-tac", "layer": L, "order": 1100,
 "title": "Nguyên tắc thiết kế đích — 8 điều chốt trước khi vẽ bảng",
 "tag": "tổng hợp thesis §23 × SO-LUAT × ADR",
 "summary": "Không hạ tầng mới; mọi thứ là dữ liệu; một cửa ghi; migration cộng thêm; DB trước code; CI canh mọi bất biến; một tiến trình nền; rule trước AI.",
 "body": """
1. **Không hạ tầng mới.** Luật 7.1/7.2 + ADR-0005 + Care Model §23 đồng ý: «Điều cần bảo vệ từ ngày đầu không phải scale hạ tầng mà là event semantics; correlation/causation; ordering boundary; immutable history; projection discipline; completion/outcome semantics.» Mọi mảnh dưới đây là bảng Postgres + hàm SQL + một vòng lặp trong `worker.py` đã có.
2. **Mọi thứ là dữ liệu** (ADR-0011, `kien-truc-nhieu-phong-kham.md`): catalog event, policy, SLA, ngưỡng, intervention — đều là dòng có `clinic_id`. Phòng khám thứ hai khai, không đợi deploy.
3. **Một cửa ghi sự kiện.** 29 → 1. Hàm SQL `ghi_su_kien()` điền envelope, cấp `stream_version`, kiểm catalog. Python chỉ gọi.
4. **Migration cộng thêm, không đổi tên.** Không đổi `event_type` đang chạy (view/relay/test đọc chúng); thêm cột, thêm bảng, thêm trigger. Tên canonical thesis nằm ở cột `canonical` của catalog.
5. **DB trước code, code sau DB** (DANG-LAM cạm bẫy). Mỗi phase = 1 migration idempotent (áp hai lần trong CI) → 1–3 PR code → 1 SQL test khẳng định.
6. **Luật không có người canh không phải luật** (SO-LUAT §3). Mỗi bất biến thesis được đưa vào [[chung-minh-event-driven]] thành một test có "thử ngược".
7. **Một tiến trình nền** làm ba việc: relay (có sẵn) + đồng hồ expectation + policy engine. Cùng LISTEN, cùng poll 30s, cùng heartbeat. Tách tiến trình chỉ khi có phép đo (Luật 7.2).
8. **Rule trước, AI sau** (Spec §13, v2 §3.10 «Nếu thất bại tập trung ở AI nhưng coordination loop vẫn tạo giá trị, nên bỏ bớt AI»). Mọi derived state đầu tiên là rule SQL/Python thuần, test bằng bảng tình huống như `gate_rule_service`.

Điều **không** làm, và vì sao:
- Không full event sourcing (§20.6). Bảng trạng thái giữ nguyên để CHECK/CAS/trigger (ADR-0003) tiếp tục làm việc.
- Không message broker (ADR-0002). `pg_notify` + poll đủ ở 1 RPS; relay đã chứng minh.
- Không đổi tên event sang PascalCase tiếng Anh ngay. Đổi tên là đổi hợp đồng với `audit_labels`, template, view, test — rủi ro không mua được gì; catalog ánh xạ là đủ.
- Không viết lại `booking_service`. Nó là state machine + events đúng mô hình §7; chỉ đổi cửa ghi.
- Không projector worker. View đủ; DB cùng máy <1 ms/query.
""",
 "links": ["kien-truc-toi-thieu", "adr-so-luat", "tk-emit-function", "tk-event-catalog-table", "chung-minh-event-driven", "tk-modular-monolith", "stack"],
},
{
 "id": "tk-event-envelope-v2", "layer": L, "order": 1110,
 "title": "Envelope v2 — một migration cộng thêm 14 cột, trigger cấp stream_version, backfill từ dữ liệu có sẵn",
 "tag": "ADR-0014 (đề xuất) · migration 202609xx_event_envelope_v2",
 "summary": "Đưa event_log lên đủ 17 trường thesis mà không vỡ đường nào đang chạy.",
 "body": """
### Cột thêm vào `event_log`

```sql
ALTER TABLE public.event_log
  ADD COLUMN IF NOT EXISTS seq            bigserial,                 -- ⚠ thứ tự CẤP PHÁT, không phải thứ tự commit; xem cảnh báo dưới
  ADD COLUMN IF NOT EXISTS stream_id      text,                      -- 'enc:<visit>' | 'work:<id>' | 'epi:<id>' | 'res:<id>' | 'comm:<patient>' | 'sys:<clinic>'
  ADD COLUMN IF NOT EXISTS stream_version integer,                   -- trigger cấp, tăng dần trong stream
  ADD COLUMN IF NOT EXISTS actor_type     text,                      -- 'staff' | 'system' | 'patient' | 'integration'
  ADD COLUMN IF NOT EXISTS actor_staff_id uuid REFERENCES public.staff(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS actor_role     text,
  ADD COLUMN IF NOT EXISTS patient_id     uuid,                      -- clinic_patient_id, denormalised cho timeline
  ADD COLUMN IF NOT EXISTS visit_id       uuid,
  ADD COLUMN IF NOT EXISTS episode_id     uuid,
  ADD COLUMN IF NOT EXISTS evidence_level text NOT NULL DEFAULT 'observed'
      CHECK (evidence_level IN ('observed','self_reported','inferred','decision','outcome','reliability')),
  ADD COLUMN IF NOT EXISTS confidence     numeric(4,3)
      CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  ADD COLUMN IF NOT EXISTS privacy_tags   text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS policy_id      uuid,                      -- luật nào sinh event (cho Derived/Decision)
  ADD COLUMN IF NOT EXISTS policy_version integer;
-- inferred bắt buộc confidence (Care Model §3.3 «Derived Event phải ghi rõ mức độ chắc chắn»)
ALTER TABLE public.event_log ADD CONSTRAINT event_log_inferred_needs_confidence
  CHECK (evidence_level <> 'inferred' OR confidence IS NOT NULL);
CREATE INDEX IF NOT EXISTS idx_event_log_stream ON public.event_log (clinic_id, stream_id, stream_version);
CREATE INDEX IF NOT EXISTS idx_event_log_visit  ON public.event_log (clinic_id, visit_id, occurred_at) WHERE visit_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_log_seq    ON public.event_log (seq);
```

> [!warning] `seq` KHÔNG dùng làm con trỏ tiêu thụ được nếu chưa sửa giao thức
> `bigserial` cấp số **lúc INSERT**, không phải lúc commit. Tài liệu PostgreSQL:
> «the value obtained by `nextval` is not reclaimed for re-use if the calling
> transaction later aborts […] transaction aborts or database crashes can result
> in gaps», và «PostgreSQL sequence objects cannot be used to obtain "gapless"
> sequences» ([functions-sequence](https://www.postgresql.org/docs/current/functions-sequence.html)).
> FAQ nói thẳng về thứ tự: «it is *not* guaranteed that id n+1 was inserted after
> id n except when both were generated within the same transaction» và «you should
> not […] make assumptions about their order» ([FAQ](https://wiki.postgresql.org/wiki/FAQ)).
>
> Hệ quả cụ thể, mất event thật: T1 lấy `seq = 1` nhưng commit muộn; T2 lấy `seq = 2`
> và commit trước; consumer đọc thấy 2, nâng `last_seq := 2`; T1 commit sau, và
> `seq = 1` **không bao giờ vào lại** điều kiện `seq > last_seq`. Vì cùng lý do,
> `max(seq) − last_seq` **không** phải số việc còn tồn: khoảng trống do rollback
> cũng đếm vào đó.
>
> Vì vậy giao thức "consumer đọc `seq > last_seq`" trong bản này được đánh dấu
> **chưa an toàn, chưa kiểm chứng**, và là *đề xuất bị chặn* chứ không phải thiết
> kế đã chốt. Trước khi triển khai phải có, và phải chứng minh bằng test:
> xác nhận **theo từng event** (bảng đã-xử-lý theo `(consumer, event_id)`) thay cho
> một con trỏ đơn; consumer **idempotent** để xử lý lại một event không đổi kết quả;
> test **commit đảo thứ tự** (mở hai transaction, cấp seq ngược với thứ tự commit)
> và test **crash rồi chạy lại** giữa lúc xử lý. Vòng này **không cài** cơ chế nào.

```sql
```

`event_version` giữ nguyên = `schema_version` của thesis (chỉ đổi nghĩa trong catalog, không đổi tên cột).

### Trigger BEFORE INSERT `event_log_fill_envelope()`

- Nếu `stream_id` NULL: suy từ `aggregate_type/aggregate_id` theo bảng ánh xạ trong `event_catalog.stream_rule` (ví dụ `appointment → 'enc:'||visit_id nếu có, else 'appt:'||id`; `patient → 'comm:'||id` cho `cskh.*`).
- `stream_version := coalesce((SELECT max(stream_version) FROM event_log WHERE clinic_id=NEW.clinic_id AND stream_id=NEW.stream_id), 0) + 1` — dưới `pg_advisory_xact_lock(hashtext(stream_id))` để hai event cùng stream cùng lúc không trùng số (đúng bậc thang ADR-0003).
- `actor_*` từ `metadata` nếu cột trống (giữ tương thích 29 chỗ ghi cũ trong giai đoạn chuyển).
- `patient_id/visit_id/episode_id` denormalise từ aggregate qua lookup nhỏ.
- `recorded_at := now()`; `occurred_at` giữ giá trị caller đưa → từ đây hai mốc **tách được** (ghi bù = `occurred_at` quá khứ).

### Backfill (một lần, trong migration)

449 dòng prod: `actor_staff_id ← metadata->>'clinic_staff_id'`; `patient_id/visit_id` qua join; `stream_id` theo quy ước; `stream_version` đánh số theo `occurred_at, event_id`. `slot_hold.*` gắn `privacy_tags = '{telemetry}'` và loại khỏi timeline view.

### Vì sao không tạo bảng mới `domain_event`

`event_log` đã có trigger append-only, RLS, `trg_notify_event_log`, relay, `v_audit_log`, `v_dispatch_history`, drift test. Bảng mới = hai sổ trong giai đoạn chuyển = đúng thứ `v_dispatch_history` đã từ chối. Cộng thêm cột là đường ngắn nhất và rollback = không dùng cột.

### Kiểm

SQL test: sau migration, `count(*) WHERE stream_id IS NULL` = 0; `stream_version` unique trong `(clinic_id, stream_id)`; `inferred` không confidence bị từ chối. CI đếm: `correlation_id IS NOT NULL` ratchet **chỉ được tăng** (bắt đầu đo từ 0%).
""",
 "links": ["event-envelope", "gap-envelope", "tk-emit-function", "tk-event-catalog-table", "tk-mot-so-cai", "idempotency-concurrency", "chung-minh-event-driven"],
},
{
 "id": "tk-event-catalog-table", "layer": L, "order": 1120,
 "title": "event_catalog — danh mục sự kiện là bảng: nhãn Việt, tên canonical, loại, evidence, privacy, stream rule",
 "tag": "migration 202609xx_event_catalog · thay audit_labels.py dần",
 "summary": "Đưa ~80 tên trong EVENT_LABELS vào DB; ghi_su_kien() từ chối event_type không có trong catalog; slot_hold về telemetry.",
 "body": """
```sql
CREATE TABLE IF NOT EXISTS public.event_catalog (
    clinic_id       uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,  -- NULL-less: catalog theo tenant, seed cho mọi clinic
    event_type      text NOT NULL,                       -- 'appointment.created' (tên đang chạy, KHÔNG đổi)
    canonical       text,                                -- 'AppointmentConfirmed' (tên thesis, để đối chiếu/xuất)
    nhan            text NOT NULL,                       -- 'Tạo lịch hẹn' (từ audit_labels)
    category        text NOT NULL CHECK (category IN ('observed','domain','derived','decision','outcome','reliability','telemetry')),
    is_domain       boolean GENERATED ALWAYS AS (category <> 'telemetry') STORED,
    stream_rule     text NOT NULL DEFAULT 'by_aggregate',-- cách suy stream_id khi caller không đưa
    default_privacy text[] NOT NULL DEFAULT '{}',
    schema_version  integer NOT NULL DEFAULT 1,
    payload_schema  jsonb,                               -- JSON Schema tối thiểu; NULL = chưa khai (chấp nhận trong giai đoạn chuyển)
    producer        text,                                -- 'booking_service' | 'sql:move_visit_to_station' …
    expected_outcome text,                               -- event_type đóng vòng, nếu đây là Derived/Command-like
    fhir_hint       text,
    is_active       boolean NOT NULL DEFAULT true,
    PRIMARY KEY (clinic_id, event_type)
);
```

Seed từ `audit_labels.EVENT_LABELS` (CROSS JOIN mọi clinic, như `luat_cskh`). Phân loại ban đầu (từ [[5-loai-event]]): `slot_hold.*` → `telemetry`; `appointment.*`, `patient.*`, `visit.*`, `clinical.*`, `lab_result.*`, `payment.*`, `pharmacy.*`, `work_item.*`, `roster.*`, `episode.*` → `domain`; `dispatch.checkin/checkout/moved` → `observed`; `cskh.tuong_tac[TRA_KQ]`, `clinical.released` → `outcome` (tách sau bằng payload); `dispatch.route_applied`, `booking.doctor_rule_saved`, `visit_gate_override` → `decision`; `thong_bao.*` → giữ `domain` nhưng `canonical='CommunicationRequested'`.

### Ràng buộc

- `ghi_su_kien()` từ chối `event_type` không có trong catalog hoặc `is_active = false` → lỗi rõ, không im lặng. Trong giai đoạn chuyển, 29 INSERT cũ vẫn chạy (không đi qua hàm) — CI ratchet đưa chúng về 0.
- Drift test hai chiều: mọi literal `'x.y'` trong `src/clinicai` có trong catalog; mọi dòng catalog `is_active` có ít nhất một producer hoặc được đánh dấu `reserved`.
- `v_audit_log` đọc `nhan` từ catalog thay vì dict Python → nhãn có thể sửa không deploy, và **phòng khám thứ hai có thể có nhãn khác**.

### Vì sao theo tenant

Catalog §1: «Event Catalog là nơi xác định […] nghĩa nghiệp vụ.» Nghĩa là của phòng khám (`luat_cskh.nhan` đã theo tenant). Seed chung, sửa riêng. Thesis Catalog §15 versioning: `schema_version` ở đây; đổi nghĩa = event_type mới, không đổi dòng cũ.
""",
 "links": ["event-catalog", "audit-labels", "5-loai-event", "tk-emit-function", "tk-event-envelope-v2", "governance-event", "fhir-mapping"],
},
{
 "id": "tk-emit-function", "layer": L, "order": 1130,
 "title": "ghi_su_kien() — cửa ghi duy nhất: hàm SQL + wrapper Python, CI đưa 29 INSERT về 0",
 "tag": "migration + src/clinicai/su_kien.py + test ceiling",
 "summary": "Điền envelope, kiểm catalog, cấp stream_version, trả event_id để làm causation cho bước sau; Python không tự INSERT nữa.",
 "body": """
### Hàm SQL

```sql
CREATE OR REPLACE FUNCTION public.ghi_su_kien(
    p_clinic_id   uuid,
    p_event_type  text,
    p_aggregate_type text, p_aggregate_id uuid,
    p_payload     jsonb DEFAULT '{}',
    p_actor_staff_id uuid DEFAULT NULL, p_actor_role text DEFAULT NULL, p_actor_type text DEFAULT 'staff',
    p_source      text DEFAULT 'api',
    p_occurred_at timestamptz DEFAULT now(),       -- ghi bù: đưa giờ thật
    p_correlation uuid DEFAULT NULL, p_causation uuid DEFAULT NULL,
    p_stream_id   text DEFAULT NULL,               -- NULL = suy theo catalog.stream_rule
    p_evidence    text DEFAULT NULL,               -- NULL = catalog.category
    p_confidence  numeric DEFAULT NULL,
    p_policy_id   uuid DEFAULT NULL, p_policy_version integer DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public AS $$
DECLARE v_cat public.event_catalog; v_id uuid; BEGIN
    SELECT * INTO v_cat FROM public.event_catalog
     WHERE clinic_id = p_clinic_id AND event_type = p_event_type AND is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Sự kiện % chưa có trong danh mục của phòng khám', p_event_type
            USING ERRCODE = 'check_violation';
    END IF;
    -- correlation mặc định = correlation của causation, để cả chuỗi cùng một mã
    IF p_correlation IS NULL AND p_causation IS NOT NULL THEN
        SELECT correlation_id INTO p_correlation FROM public.event_log WHERE event_id = p_causation;
    END IF;
    INSERT INTO public.event_log (clinic_id, event_type, aggregate_type, aggregate_id, payload,
        metadata, source, occurred_at, correlation_id, causation_id, stream_id,
        actor_type, actor_staff_id, actor_role, evidence_level, confidence, privacy_tags,
        policy_id, policy_version, event_published)
    VALUES (p_clinic_id, p_event_type, p_aggregate_type, p_aggregate_id, p_payload,
        jsonb_build_object('clinic_staff_id', p_actor_staff_id, 'clinic_role', p_actor_role), -- tương thích relay/view cũ
        p_source, p_occurred_at, coalesce(p_correlation, gen_random_uuid()), p_causation, p_stream_id,
        p_actor_type, p_actor_staff_id, p_actor_role, coalesce(p_evidence, v_cat.category), p_confidence,
        coalesce(v_cat.default_privacy, '{}'), p_policy_id, p_policy_version, FALSE)
    RETURNING event_id INTO v_id;
    RETURN v_id;
END $$;
```

Trigger BEFORE INSERT ([[tk-event-envelope-v2]]) vẫn lo `stream_id`/`stream_version`/denormalise — hàm không lặp việc đó.

### Wrapper Python `src/clinicai/su_kien.py`

```python
async def ghi(conn, *, identity: StaffIdentity, event_type: str, aggregate_type: str,
              aggregate_id: str, payload: dict, source: str, occurred_at=None,
              causation: str | None = None, correlation: str | None = None, **kw) -> str:
    return await conn.fetchval("SELECT public.ghi_su_kien($1::uuid,$2,$3,$4::uuid,$5::jsonb,$6::uuid,$7,'staff',$8,$9,$10::uuid,$11::uuid, ...)",
        identity.clinic_id, event_type, aggregate_type, aggregate_id, json.dumps(payload),
        identity.staff_id, identity.role.value, source, occurred_at or datetime.now(CLINIC_TZ), correlation, causation, ...)
```

Nhận `conn` (không pool) để **luôn nằm trong transaction của người gọi** — Luật 8.1. Trả `event_id` để bước sau đưa vào `causation`: `apply_action('checkin')` → `ghi(appointment.checked_in)` → `instantiate_visit_workflow(…, causation=event_id)` → `work_item.create` events có causation. Đó là cách `correlation_id` từ 0% lên 100% mà không ai phải "nhớ".

### Chuyển 29 chỗ

Cơ học: mỗi `INSERT INTO event_log` → `await su_kien.ghi(conn, …)`. `services/audit.py:record_event` trở thành alias. Hai hàm SQL (`move_visit_to_station`, check-in) gọi thẳng `ghi_su_kien`. Làm theo cụm (booking → cskh → dispatch → clinical → config), mỗi cụm một PR, ratchet trong CI: `grep -c "INSERT INTO event_log\\|INSERT INTO public.event_log" src/clinicai` **chỉ được giảm** (mẫu Luật 4.1).

### Kiểm

- `test_ghi_su_kien_tu_choi_event_la.py`: event_type lạ → `check_violation`.
- SQL test: `ghi_su_kien` hai lần cùng stream trong hai session đồng thời → `stream_version` 1 và 2, không trùng.
- Ratchet grep INSERT trực tiếp.
""",
 "links": ["gap-crud-roi-log", "event-log-table", "tk-event-envelope-v2", "tk-event-catalog-table", "tk-mot-so-cai", "ci-guards", "idempotency-concurrency"],
},
{
 "id": "tk-mot-so-cai", "layer": L, "order": 1140,
 "title": "Một sổ cái, nhiều bảng chuyên biệt — trigger đổ work_item_event / gate_override / thong_bao vào event_log cùng transaction",
 "tag": "migration 202609xx_mot_so_cai · bất biến 1",
 "summary": "Giữ nguyên 7 sổ; mọi thay đổi trạng thái của 4 domain event-centric để lại một dòng event_log có stream_id — timeline một lượt khám thành một SELECT.",
 "body": """
### Quy ước stream_id

| Stream | `stream_id` | Event vào |
|---|---|---|
| Encounter | `enc:<visit_id>` | `visit.*`, `dispatch.*`, `work_item.*` (của visit), `clinical.*`, `lab_result.*`, `payment.*`, `appointment.checked_in/completed` |
| Appointment (trước encounter) | `appt:<appointment_id>` | `appointment.created/rescheduled/cancelled/...`; khi có visit, event sau đó dùng `enc:` |
| Work Item | `work:<work_item_id>` **và** cũng ghi `visit_id` để lọc theo encounter | `work_item.*` |
| Episode | `epi:<care_episode_id>` | `episode.*`, `nhac_tai_kham.*` |
| Resource | `res:staff:<id>` / `res:room:<id>` | `roster.*`, overload |
| Communication | `comm:<clinic_patient_id>` | `cskh.tuong_tac*`, `notification.*`, `thong_bao.*` |
| System | `sys:<clinic_id>` | reliability |

Một event thuộc **một** stream (`stream_version` đếm theo đó), nhưng mang `visit_id/patient_id` để timeline theo lượt khám gom cả `work:` và `comm:`.

### Trigger đổ vào ledger

```sql
-- work_item_event → event_log (cùng transaction, không hàng chờ — Luật 8.1)
CREATE OR REPLACE FUNCTION public.work_item_event_to_ledger() RETURNS trigger ... AS $$
BEGIN
  PERFORM public.ghi_su_kien(NEW.clinic_id, 'work_item.' || NEW.command, 'work_item', NEW.work_item_id,
      jsonb_build_object('from', NEW.from_status, 'to', NEW.to_status, 'reason', NEW.reason) || NEW.metadata,
      NEW.actor_staff_id, NEW.actor_role, 'staff', 'kernel', NEW.occurred_at,
      NULL, (NEW.metadata->>'causation_id')::uuid, 'work:' || NEW.work_item_id);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_work_item_event_ledger AFTER INSERT ON public.work_item_event FOR EACH ROW EXECUTE FUNCTION public.work_item_event_to_ledger();
```

Tương tự: `visit_gate_override` → `dispatch.gate_overridden` (category `decision`); `thong_bao` UPDATE `da_xu_ly_luc` → `thong_bao.da_xu_ly` (outcome); `visit_route` INSERT đã có event (giữ); `inventory_txn` đã có `pharmacy.*` (giữ).

`work_item.*` đã có nhãn trong `audit_labels` (`work_item.create/start/complete/skip`) → thêm `cancel/reassign/assign/acknowledge/block/resume/escalate`.

### Bất biến 1 làm thành test

«Mọi operational state quan trọng phải truy được về event.» SQL test trên fixture: sau khi chạy `apply_action('checkin')` + `issue('start')` + `move_visit_to_station` + `checkout`, đếm `event_log WHERE visit_id = X` phải bằng số lần `status` của `appointment/visit/work_item` đổi (đọc từ `work_item_event` + so `updated_at`). Thử ngược: xoá một `ghi_su_kien` trong một service → đỏ.

### Timeline view

```sql
CREATE VIEW public.v_timeline_luot_kham WITH (security_invoker = true) AS
SELECT e.clinic_id, e.visit_id, e.seq, e.occurred_at, e.recorded_at, e.event_type, c.nhan, c.category,
       e.evidence_level, e.confidence, e.actor_staff_id, s.full_name AS actor_name, e.stream_id, e.stream_version,
       e.causation_id, e.correlation_id, e.policy_id, e.payload
  FROM public.event_log e
  JOIN public.event_catalog c ON c.clinic_id = e.clinic_id AND c.event_type = e.event_type AND c.is_domain
  LEFT JOIN public.staff s ON s.id = e.actor_staff_id
 WHERE e.visit_id IS NOT NULL;
```

Đây là Care Model §19.2 Event Timeline với filter theo `category` — và là nguồn cho «Replayable operations review» §19.4 mà không cần công cụ mới.
""",
 "links": ["stream-boundary", "so-cai-phan-manh", "gap-crud-roi-log", "gap-projection-rebuild", "tk-emit-function", "tk-projections", "15-invariant"],
},
{
 "id": "tk-work-item-protocol", "layer": L, "order": 1150,
 "title": "Work Item Protocol trên kernel — 8 trạng thái, 8 lệnh mới, 4 mốc SLA, completion contract, hai trục ưu tiên",
 "tag": "ADR-0015 (đề xuất) · migration 202609xx_work_item_protocol · work_item_service.py",
 "summary": "Mở rộng work_item đúng Protocol v1 mà không đụng gate SQL và 4 lệnh đang có; thong_bao trở thành role-queue assignment.",
 "body": """
### Trạng thái và lệnh

Giữ 5 trạng thái, thêm 3: `ASSIGNED`, `ACKNOWLEDGED`, `BLOCKED`, `ESCALATED` (thesis Open = `PENDING` chưa owner).

```
PENDING ──assign──▶ ASSIGNED ──acknowledge──▶ ACKNOWLEDGED ──start──▶ IN_PROGRESS ──complete──▶ COMPLETED
   │                   │  ack_timeout                       │ block ⇄ resume        │ sla_exceeded
   │                   └────────▶ ESCALATED ◀───────────────┴── BLOCKED             └──▶ ESCALATED
   │                                  │ reassign → ASSIGNED
   └── skip / cancel (mọi trạng thái chưa kết) ──▶ SKIPPED / CANCELLED
claim: PENDING(queue) → ASSIGNED(người bấm)          reject_completion: COMPLETED → IN_PROGRESS (có lý do)
```

Tương thích: `start` vẫn chấp nhận từ `PENDING` (đường cũ, cho node không đòi ack) **nếu** `node_definition.config->>'require_ack' IS DISTINCT FROM 'true'`. Node đòi ack (giao việc chéo bộ phận) thì `start` từ `PENDING` = 409 «Chưa nhận việc». Gate SQL không đổi. `work_item_event.command` CHECK mở rộng.

### Cột thêm

```sql
ALTER TABLE public.work_item
  ADD COLUMN origin_event_id  uuid REFERENCES public.event_log(event_id),   -- Reason: event nào sinh việc
  ADD COLUMN policy_id        uuid, ADD COLUMN policy_version integer,      -- hoặc policy nào
  ADD COLUMN purpose          text,                                         -- 'Giải thích lý do chờ và ETA cho khách'
  ADD COLUMN owner_type       text CHECK (owner_type IN ('user','role_queue','team_queue','system','external')),
  ADD COLUMN assigned_queue   text,                                         -- 'CSKH' | 'NURSE_ULTRASOUND' | 'TRUONG_CA'
  ADD COLUMN clinical_priority text CHECK (clinical_priority IN ('routine','priority','urgent','emergency')) DEFAULT 'routine',
  -- priority (P0–P2) hiện có = operational_priority; giữ nguyên tên cột
  ADD COLUMN claim_by timestamptz, ADD COLUMN acknowledge_by timestamptz, ADD COLUMN start_by timestamptz,
  -- due_at hiện có = complete_by
  ADD COLUMN acknowledged_at timestamptz, ADD COLUMN acknowledged_by uuid,
  ADD COLUMN completion_criteria jsonb,           -- {"type":"required_event","event_type":"cskh.tuong_tac","filter":{"loai":"TRA_KQ"}} | {"type":"attestation"} | {"type":"compound",...}
  ADD COLUMN expected_outcome_event text,
  ADD COLUMN escalation_policy_id uuid,
  ADD COLUMN blocked_reason text, ADD COLUMN blocker_ref text, ADD COLUMN next_review_at timestamptz,
  ADD COLUMN escalated_at timestamptz, ADD COLUMN escalated_to text;
-- Bất biến Protocol §2: việc ở trạng thái mở phải có owner hoặc queue (sau Phase A, kích hoạt bằng CHECK NOT VALID → VALIDATE)
ALTER TABLE public.work_item ADD CONSTRAINT work_item_open_needs_owner
  CHECK (status IN ('COMPLETED','SKIPPED','CANCELLED') OR assigned_to IS NOT NULL OR assigned_queue IS NOT NULL) NOT VALID;
-- Idempotency §13: cùng origin + policy + node + subject chỉ một
CREATE UNIQUE INDEX uq_work_item_origin ON public.work_item (clinic_id, origin_event_id, policy_id, node_code, coalesce(visit_id, clinic_patient_id))
  WHERE origin_event_id IS NOT NULL AND status <> 'CANCELLED';
```

SLA mặc định theo node: `node_definition.config->'sla'` = `{"acknowledge_min":5,"complete_min":30}` — dữ liệu, theo tenant. Policy có thể đè.

### Completion contract trong `issue('complete')`

`completion_criteria.type`:
- `manual` (mặc định, như hôm nay — bấm là xong; node nội bộ như sinh hiệu).
- `required_event`: `complete` bị từ chối nếu chưa có event khớp trong stream **sau** `created_at` — ví dụ việc «trả kết quả» đóng bằng `cskh.tuong_tac[loai=TRA_KQ, appointment_id=…]`. Ngược lại, khi event ấy tới, policy engine tự `complete` (system actor) — «CheckboxTicked ≠ OutcomeObserved».
- `attestation`: bắt body `{method, subject, note}` → ghi `tuong_tac_cskh` rồi mới COMPLETED.
- `compound`: mọi child (`work_item_dependency` non-blocking) đã kết — Protocol §9.

### Escalation

`escalation_policy` là dòng trong bảng `policy` ([[tk-policy-engine]]) loại `escalation`: `{grace_min, recipient_queue, priority_bump, repeat_after_min, stop_on}`. Timer ([[tk-expectation-timer]]) phát `AcknowledgementTimeoutOccurred` → policy → `escalate` (system) → dòng `thong_bao` cho `recipient_queue` với `work_item_id`. «Escalation không thay thế owner» — `assigned_to` giữ, `escalated_to` thêm.

### `thong_bao` và `nhac_tai_kham` sau đây

- `thong_bao` = kênh hiển thị của work item có `owner_type='role_queue'`: thêm cột `work_item_id`; `da_xu_ly` gọi `issue('complete')`; `da_doc` **không** phải ack — ack là nút riêng («Không tự động chuyển Active chỉ vì người dùng mở màn hình»).
- `nhac_tai_kham` giữ nguyên bảng (33 dòng thật), nhưng mỗi dòng `CHO_GOI` được policy vật chất hoá thành một `work_item` node `THEODOI-03` với `completion_criteria = required_event cskh.tuong_tac[loai=NHAC_HEN|XAC_NHAN_LICH]` — đó là cách «bảng mỏng để nhận việc» mà chính migration `20260809000005` dự trù.

### Kiểm

pytest cho `_TRANSITIONS` mới (hàm thuần); SQL test `work_item_open_needs_owner` sau VALIDATE; test «duplicate origin_event → một work item»; test «complete bị từ chối khi required_event chưa có; tự complete khi có».
""",
 "links": ["work-item-commitment", "gap-work-item", "workflow-kernel", "thong-bao", "nhac-tai-kham", "tk-policy-engine", "tk-expectation-timer", "tk-communication-delivery", "idempotency-concurrency"],
},
{
 "id": "tk-expectation-timer", "layer": L, "order": 1160,
 "title": "expectation + đồng hồ — bảng kỳ vọng, trigger MET khi event tới, vòng lặp FIRED trong worker có sẵn",
 "tag": "ADR-0016 (đề xuất) · migration 202609xx_expectation · worker.py --dong-ho",
 "summary": "'Sự kiện không xảy ra' thành sự kiện: ExpectedEventDeadlineReached, idempotent, huỷ được, 0 hạ tầng mới.",
 "body": """
### Bảng

```sql
CREATE TABLE IF NOT EXISTS public.expectation (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id),
    stream_id        text NOT NULL,                    -- stream phải chứa event mong đợi
    expected_event_type text NOT NULL,                 -- 'cskh.tuong_tac' | 'work_item.acknowledge' | 'lab_result.entered' …
    expected_filter  jsonb NOT NULL DEFAULT '{}',      -- {"loai":"TRA_KQ"} — khớp payload @>
    subject_type     text, subject_id uuid,            -- work_item / visit / appointment
    deadline_at      timestamptz NOT NULL,
    registered_by_event_id uuid NOT NULL REFERENCES public.event_log(event_id),
    policy_id        uuid, policy_version integer,
    on_deadline      text NOT NULL,                    -- event_type phát khi tới hạn: 'time.ack_timeout' | 'time.wait_threshold' | 'time.expected_missing'
    status           text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','MET','FIRED','CANCELLED')),
    met_by_event_id  uuid, fired_event_id uuid, closed_at timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT expectation_closed_when_terminal CHECK ((status = 'OPEN') = (closed_at IS NULL))
);
CREATE INDEX idx_expectation_due  ON public.expectation (deadline_at) WHERE status = 'OPEN';
CREATE INDEX idx_expectation_stream ON public.expectation (clinic_id, stream_id, expected_event_type) WHERE status = 'OPEN';
CREATE UNIQUE INDEX uq_expectation_once ON public.expectation (registered_by_event_id, expected_event_type, coalesce(subject_id, '00000000-0000-0000-0000-000000000000'::uuid))
  WHERE status = 'OPEN';  -- Care Model §11 «idempotent nếu bị kích hoạt lại»
```

### MET — trigger trên `event_log` (huỷ timer khi outcome tới sớm)

```sql
CREATE OR REPLACE FUNCTION public.expectation_met_on_event() RETURNS trigger ... AS $$
BEGIN
  UPDATE public.expectation e
     SET status = 'MET', met_by_event_id = NEW.event_id, closed_at = now()
   WHERE e.clinic_id = NEW.clinic_id AND e.status = 'OPEN'
     AND e.stream_id = NEW.stream_id AND e.expected_event_type = NEW.event_type
     AND NEW.payload @> e.expected_filter;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_expectation_met AFTER INSERT ON public.event_log FOR EACH ROW EXECUTE FUNCTION public.expectation_met_on_event();
```

### FIRED — vòng "đồng hồ" trong `worker.py`

Cùng tiến trình relay (nguyên tắc 7 của [[tk-nguyen-tac]]): mỗi 30s hoặc khi được đánh thức, và **không** cần LISTEN riêng:

```sql
WITH due AS (
  SELECT id FROM public.expectation
   WHERE status = 'OPEN' AND deadline_at <= now()
   ORDER BY deadline_at LIMIT 100
   FOR UPDATE SKIP LOCKED                       -- hai worker không bắn trùng
)
UPDATE public.expectation e SET status = 'FIRED', closed_at = now(),
       fired_event_id = public.ghi_su_kien(e.clinic_id, e.on_deadline, e.subject_type, e.subject_id,
            jsonb_build_object('expected', e.expected_event_type, 'deadline_at', e.deadline_at, 'expectation_id', e.id),
            NULL, NULL, 'system', 'dong-ho', now(), NULL, e.registered_by_event_id, e.stream_id, 'inferred', 1.0, e.policy_id, e.policy_version)
  FROM due WHERE e.id = due.id
RETURNING e.id;
```

Event `time.*` được ghi với `causation = registered_by_event_id` → chuỗi nhân quả liền. Catalog §11 tách hai bước: `on_deadline` = `time.deadline_reached` (không kết luận), policy recheck rồi phát `time.expected_missing` (derived). Cho ba trường hợp pilot, gộp làm một là đủ (deadline_reached đã có `expected_filter` để recheck ngay trong SQL).

Heartbeat, healthcheck, LISTEN: dùng chung với relay. Đo: 100 expectation/ngày × 1 UPDATE mỗi 30s = không đáng kể (Luật 7.2 — nếu vượt 10k OPEN thì tách tiến trình).

### Ai đăng ký expectation

- **Policy** ([[tk-policy-engine]]) khi tạo work item: `acknowledge_by` → expectation `work_item.acknowledge` on `time.ack_timeout`; `complete_by` → `work_item.complete` on `time.sla_exceeded`.
- **Move**: `move_visit_to_station` → expectation «rời node này» (`dispatch.moved` với `from_node = X`) deadline = `dispatch_threshold.wait_minutes` → `time.wait_threshold` — đây chính là WaitingThresholdExceeded thành *event* thay vì màu trên bảng.
- **Check-in**: expectation `lab_result.entered` sau `lab_result.ordered` deadline `luat_cskh.CHO_KQ_XN`.
- **Nhắc tái khám**: thay `sinh_viec_nhac_tai_kham` lúc mở màn bằng expectation `FollowupWindowOpened` đăng ký lúc `episode`/`nhac_tai_kham` sinh → sinh việc đúng ngày dù không ai mở màn.

### Kiểm

SQL test: đăng ký expectation, INSERT event khớp → MET, không FIRED; đăng ký deadline quá khứ, chạy câu FIRED → đúng một event `time.*`, chạy lại → 0 (idempotent). pytest cho vòng worker với pool giả. «Thử ngược»: bỏ `SKIP LOCKED` → test song song đỏ.
""",
 "links": ["timer-expected-event", "gap-timer", "tk-policy-engine", "tk-work-item-protocol", "notification-relay", "realtime-sse", "nhac-tai-kham", "dispatch"],
},
{
 "id": "tk-policy-engine", "layer": L, "order": 1170,
 "title": "policy + policy_case — luật phản ứng là dữ liệu: trigger event → điều kiện → hành động → outcome; version, owner, test theo dòng",
 "tag": "migration 202609xx_policy · src/clinicai/engine/policy.py · worker.py",
 "summary": "Bảng thứ mười cho loại luật thesis đòi; đọc event_log qua checkpoint; ba policy đầu cho pilot; process manager = tập policy.",
 "body": """
### Bảng

```sql
CREATE TABLE IF NOT EXISTS public.policy (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       uuid NOT NULL REFERENCES public.clinic(id),
    code            text NOT NULL,                     -- 'UNEXPLAINED_WAIT' | 'ACK_TIMEOUT_ESCALATE' | 'CONTINUITY_ON_CHECKOUT' | 'SPAWN_SPINE_ON_CHECKIN'
    version         integer NOT NULL DEFAULT 1,
    name            text NOT NULL,
    kind            text NOT NULL CHECK (kind IN ('reaction','escalation','experience','journey')),
    trigger_event_type text NOT NULL,                  -- câu (1)
    trigger_filter  jsonb NOT NULL DEFAULT '{}',       -- payload @>
    condition       jsonb NOT NULL DEFAULT '{}',       -- câu (2): DSL nhỏ, xem dưới
    action          jsonb NOT NULL,                    -- câu (4): create_work_item | register_expectation | detect_experience | notify_queue | complete_work_item | open_follow_up
    outcome_event_type text,                           -- câu (5)
    authority_level text NOT NULL DEFAULT 'observe' CHECK (authority_level IN ('observe','recommend','act')),
    owner_role      text NOT NULL DEFAULT 'MANAGEMENT',
    effective_from  timestamptz NOT NULL DEFAULT now(), effective_to timestamptz,
    is_active       boolean NOT NULL DEFAULT true,
    created_by      uuid, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (clinic_id, code, version)
);
CREATE TABLE IF NOT EXISTS public.policy_case (          -- test case theo dòng luật, chạy trong CI
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL, policy_code text NOT NULL,
    name text NOT NULL, given jsonb NOT NULL, event jsonb NOT NULL, expect jsonb NOT NULL
);
```

DSL điều kiện — cố ý nhỏ, thuần, không LLM (Spec §13): `all/any` của các mệnh đề `{"stream_has": {"event_type":"cskh.tuong_tac","filter":{"loai":"HOI_THAM"},"within_min":15}}`, `{"stream_lacks": …}`, `{"visit": {"status_in":["OPEN","IN_PROGRESS"]}}`, `{"work_item": {"status":"ASSIGNED"}}`, `{"threshold": {"table":"dispatch_threshold","field":"wait_minutes"}}`. Evaluator Python `engine/policy.py` là hàm thuần nhận (event, facts) → (decision, actions) — test bằng bảng tình huống như `gate_rule_service`.

### Vòng chạy

Cùng tiến trình worker, đánh thức bởi `clinicai_changes` (t = event_log): đọc `event_log WHERE seq > consumer_checkpoint('policy') ORDER BY seq LIMIT 200`, với mỗi event tìm policy `trigger_event_type` khớp và `is_active` và `now() BETWEEN effective_from AND coalesce(effective_to,'infinity')`, load facts, đánh giá, thực thi action **trong một transaction** cùng với `ghi_su_kien('policy.decided', …, evidence='decision', policy_id, policy_version, causation=event_id)`, rồi tiến checkpoint. Idempotency: action `create_work_item` nhờ `uq_work_item_origin`; `register_expectation` nhờ `uq_expectation_once`; `notify_queue` nhờ `uq_thong_bao_dang_mo`. Consumer lỗi → checkpoint không tiến, event vào `event_quarantine` sau N lần ([[tk-reliability-playbook]]).

### Bốn policy đầu (seed cho Dr4Women, theo tenant)

1. **SPAWN_SPINE_ON_CHECKIN** (journey, act): trigger `appointment.checked_in` → action `sql:instantiate_visit_workflow` (hàm có sẵn), causation = event. Chỉ chuyển "ai gọi" từ code sang bảng.
2. **ACK_TIMEOUT_ESCALATE** (escalation, act): trigger `time.ack_timeout` → điều kiện `work_item.status = 'ASSIGNED'` → action `escalate` + `notify_queue TRUONG_CA` → outcome `work_item.acknowledge`. Grace 5′ → 10′ (Protocol §11).
3. **UNEXPLAINED_WAIT** (experience, observe→act): trigger `time.wait_threshold` → điều kiện `visit active AND onsite AND stream_lacks(cskh.tuong_tac[loai∈{HOI_THAM,KHAC} & subject='cho'] within valid_until)` → action `detect_experience(unexplained_wait_risk)` + `create_work_item(node THEODOI-03 | 'GIAI_THICH_CHO', owner_queue CSKH, ack 5′, complete 15′, completion required_event cskh.tuong_tac[subject='cho'])` → outcome `cskh.tuong_tac`.
4. **CONTINUITY_ON_CHECKOUT** (journey, act): trigger `dispatch.checkout` → điều kiện `open commitments: work_item PENDING/IN_PROGRESS OR lab_result unreviewed` → action `open_follow_up` (writer đầu tiên của `follow_up_case`) + `create_work_item(THEODOI-01, owner_queue CSKH)` → outcome `work_item.acknowledge`.

### Version/owner cho 6 bảng luật cũ (migration nhỏ)

`ALTER TABLE luat_cskh, dispatch_threshold, visit_gate_rule, luat_bac_si_bat_buoc, route_template, doctor_booking_override ADD COLUMN version int DEFAULT 1, ADD COLUMN effective_from timestamptz DEFAULT now(), ADD COLUMN owner_role text` + trigger AFTER UPDATE ghi `policy.version_activated` (Catalog §13 PolicyVersionActivated). Pilot §14: «Mọi thay đổi policy trong live pilot phải có version và ngày hiệu lực để số liệu không bị trộn.»

### Vì sao không nhét vào view như `luat_cskh`

View trả lời «bây giờ ai cần gì» — tốt và giữ. Policy trả lời «**khi** X xảy ra thì làm Y và đóng bằng Z» — có thời điểm, có owner, có outcome. Hai loại luật, hai chỗ (đúng lý lẽ `luat_bac_si_service`: hai câu hỏi khác nhau, hai bảng).
""",
 "links": ["policy-engine", "gap-policy", "gap-process-manager", "journey-process-manager", "tk-expectation-timer", "tk-work-item-protocol", "tk-experience-state", "tk-reliability-playbook", "instantiate-visit", "gate-rule"],
},
{
 "id": "tk-experience-state", "layer": L, "order": 1180,
 "title": "experience_state — bảng đúng Spec §4, ba state pilot, communication coverage từ tuong_tac_cskh, intervention contract",
 "tag": "migration 202609xx_experience_state · policy kind='experience'",
 "summary": "Bắt đầu bằng UnexplainedWaitRisk / HandoffUncertaintyRisk / ContinuityRisk — ba cái có intervention khả thi với đội hôm nay; rule, không AI.",
 "body": """
### Bảng (theo Spec §4 từng trường)

```sql
CREATE TABLE IF NOT EXISTS public.experience_state (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id),
    type             text NOT NULL CHECK (type IN ('informed_wait','unexplained_wait_risk','repeated_delay_risk','needs_explanation',
                                                    'handoff_uncertainty_risk','abandonment_risk','continuity_risk','high_anxiety_context')),
    clinic_patient_id uuid NOT NULL, visit_id uuid, appointment_id uuid,
    status           text NOT NULL DEFAULT 'detected' CHECK (status IN ('detected','confirmed','intervening','escalated','resolved','dismissed','expired')),
    detected_at      timestamptz NOT NULL DEFAULT now(),
    evidence_level   text NOT NULL CHECK (evidence_level IN ('observed','self_reported','inferred')),
    confidence       numeric(4,3) NOT NULL,
    evidence_event_ids uuid[] NOT NULL,
    rule_or_model    text NOT NULL, rule_version integer NOT NULL,
    severity         text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    owner_queue      text, work_item_id uuid REFERENCES public.work_item(id),
    recommended_intervention text NOT NULL,
    review_at        timestamptz NOT NULL, expires_at timestamptz NOT NULL,
    resolved_by_event_id uuid, resolution_note text,
    dismissed_by uuid, dismiss_reason text,
    closed_at        timestamptz,
    CONSTRAINT es_closed_when_terminal CHECK ((status IN ('resolved','dismissed','expired')) = (closed_at IS NOT NULL)),
    CONSTRAINT es_dismiss_needs_reason CHECK (status <> 'dismissed' OR (dismissed_by IS NOT NULL AND dismiss_reason IS NOT NULL)),
    CONSTRAINT es_resolved_needs_event CHECK (status <> 'resolved' OR resolved_by_event_id IS NOT NULL)   -- Spec §2.6 «Resolution cần outcome event, không chỉ notification»
);
CREATE UNIQUE INDEX uq_experience_open ON public.experience_state (clinic_id, type, coalesce(visit_id, appointment_id, clinic_patient_id))
  WHERE status IN ('detected','confirmed','intervening','escalated');    -- một risk mở mỗi loại mỗi lượt
```

Lifecycle bằng Command API nhỏ: `confirm` (vai được phép — cấu hình `experience_config.confirm_roles`), `dismiss` (bắt lý do), `start_intervention` (tự khi work item ack), `resolve` (tự khi outcome event khớp — trigger giống `expectation_met_on_event`), `expire` (đồng hồ, khi `expires_at` qua mà chưa resolved — «Expired không đồng nghĩa Resolved»), `escalate` (đồng hồ + policy).

Mỗi chuyển trạng thái → `ghi_su_kien('experience.<status>', …, evidence='inferred'/'outcome', confidence, policy_id)` → stream `enc:` → hiện trên timeline.

### Communication coverage

Thêm hai cột vào `tuong_tac_cskh`: `chu_de text` (`'cho' | 'ket_qua' | 'lich' | 'huong_dan' | 'khac'` — chủ đề coverage, tách khỏi `loai`) và `hieu_luc_den timestamptz` (valid_until, mặc định `xay_ra_luc + luat_cskh.coverage_min` — cấu hình). Hàm SQL `co_coverage(patient, chu_de, tai_thoi_diem)` = tồn tại dòng `huy_luc IS NULL AND chu_de = $2 AND xay_ra_luc <= $3 AND hieu_luc_den >= $3 AND ket_qua = 'DA_LIEN_HE'`. Đúng Spec §8 sáu điều kiện (đúng bệnh nhân, đúng chủ đề, đúng vai qua `nhan_vien_staff_id`, trong window, nội dung tối thiểu qua `noi_dung NOT NULL` cho chủ đề `cho`, evidence = attestation).

### Ba state pilot và intervention contract

| State | Trigger/điều kiện (policy) | Work item | Completion evidence | Severity |
|---|---|---|---|---|
| `unexplained_wait_risk` | `time.wait_threshold` (từ move) ∧ onsite ∧ ¬coverage('cho') ∧ ¬suppression | GIAI_THICH_CHO → queue CSKH, ack 5′, complete 15′ | `cskh.tuong_tac{chu_de:'cho', ket_qua:'DA_LIEN_HE'}` | medium; high nếu > 2× ngưỡng |
| `handoff_uncertainty_risk` | `time.ack_timeout` ∧ work_item ASSIGNED | escalate → TRUONG_CA | `work_item.acknowledge` hoặc `.reassign` | medium |
| `continuity_risk` | `dispatch.checkout` ∧ open commitment | THEODOI-01 → CSKH | `work_item.acknowledge` (post-visit owner nhận) | high |

Suppression (Spec §7.1 «Không kích hoạt nếu»): `experience_config` theo tenant: `khong_lam_phien` flag trên `patient` (chưa có — thêm cột `khong_lam_phien_den`), clinical safety = có `lab_result.triage_group='GROUP_C'` chưa review → nhường clinical policy, presence không tin cậy = `visit.current_node_since` cũ hơn X giờ (freshness).

### Không làm (theo Spec)

`complaint_risk` (§6 «chưa nên dùng ở pilot nếu chỉ dựa trên mô hình dự đoán»), `high_anxiety_context` (cần self-report hoặc sensitive-service tag — có thể bật cho HMVS sau), không AI, không «bảng xếp hạng nhân viên» (§11).

### Metric (Spec §14) tính từ bảng này

precision qua `confirmed/(confirmed+dismissed)` · dismissal rate · detection latency (`detected_at − evidence occurred_at`) · % có owner · time-to-ack/intervention/resolution · unexplained waiting minutes = tổng `(coalesce(closed_at, now()) − detected_at)` của `unexplained_wait_risk` · false alarm rate.
""",
 "links": ["experience-state", "gap-experience-state", "tk-policy-engine", "tk-work-item-protocol", "tk-expectation-timer", "tuong-tac-cskh", "tk-communication-delivery", "humane-ops", "tk-metrics"],
},
{
 "id": "tk-communication-delivery", "layer": L, "order": 1190,
 "title": "notification_delivery — trả nợ ADR-0002: mỗi kênh một dòng, attempts/backoff/DEAD, MessageSent ≠ PatientInformed",
 "tag": "migration 202609xx_notification_delivery · notification_relay.py đọc bảng mới",
 "summary": "Nhân khuôn pos_outbox; event_published thôi mang nghĩa 'đã gửi'; Zalo OA sau này = thêm channel.",
 "body": """
```sql
CREATE TABLE IF NOT EXISTS public.notification_delivery (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic(id),
    event_id      uuid NOT NULL REFERENCES public.event_log(event_id),
    channel       text NOT NULL CHECK (channel IN ('telegram','zalo_oa','in_app','sms')),
    recipient_kind text NOT NULL CHECK (recipient_kind IN ('staff_group','staff','patient','role_queue')),
    recipient_ref text NOT NULL,                  -- chat_id | staff_id | clinic_patient_id | role
    dedup_key     text NOT NULL,                  -- event_id || channel || recipient_ref
    status        text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','SENT','DELIVERED','READ','FAILED','DEAD','SKIPPED')),
    attempts      integer NOT NULL DEFAULT 0, max_attempts integer NOT NULL DEFAULT 5,
    next_attempt_at timestamptz NOT NULL DEFAULT now(), last_error text,
    provider_message_id text, sent_at timestamptz, delivered_at timestamptz, read_at timestamptz,
    work_item_id  uuid,                           -- nếu tin này là 'nhắc việc' — KHÔNG đóng việc khi gửi
    created_at    timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dedup_key)
);
CREATE INDEX idx_nd_due ON public.notification_delivery (next_attempt_at) WHERE status = 'PENDING';
CREATE INDEX idx_nd_dead ON public.notification_delivery (clinic_id, updated_at) WHERE status = 'DEAD';
```

**Ai tạo dòng**: trigger AFTER INSERT `event_log` đọc `notification_route (clinic_id, event_type, channel, recipient_kind, recipient_ref, template)` — bảng cấu hình thay cho `TEMPLATES` dict + `TELEGRAM_CHAT_ID` env (theo tenant; hôm nay một dòng Telegram nhóm vận hành). Event không có route → **không** tạo dòng (thay vì «không template = đã xử lý»). Event có route nhưng template lỗi → `SKIPPED` với lý do — nhìn thấy được, không im lặng.

**Relay** (`notification_relay.py`) đổi câu SELECT sang `notification_delivery WHERE status='PENDING' AND next_attempt_at <= now()` với `FOR UPDATE SKIP LOCKED` (bỏ advisory lock thủ công), giữ `_lam_giau` và `render`, backoff 1′→5′→25′→125′ như `pos_relay`, hết attempts → `DEAD` + `ghi_su_kien('notification.failed', evidence='reliability')` → hiện ở ops view và Telegram-of-last-resort (Kuma). `event_log.event_published` **không còn được relay ghi** — cột giữ để không vỡ view cũ, nghĩa mới: «đã có ít nhất một delivery được tạo» (trigger set), và bị bỏ trong bản sau.

**Ba mức**: `SENT` khi provider nhận (`provider_message_id`); `DELIVERED` khi callback (Telegram không có → giữ SENT; Zalo OA có); `READ` khi có `read_at` (in_app: bấm mở). **Không mức nào đóng work item.** Việc đóng chỉ bằng `issue('complete')` với completion contract — [[tk-work-item-protocol]].

**PatientInformed** = dòng `tuong_tac_cskh` với `ket_qua='DA_LIEN_HE'` + `chu_de` — structured attestation (Protocol §8), giữ nguyên cách CSKH đang làm. Khi Zalo OA có callback «khách đã đọc», đó là `PatientAcknowledged` (Catalog §10), vẫn **chưa** là PatientInformed nếu chủ đề không khớp.

**Zalo OA** (D010, kênh bệnh nhân): thêm `channel='zalo_oa'`, adapter theo khuôn `PosPort` (port + null adapter + test boundary). Không có gì khác phải đổi — đó là lợi ích của việc trả nợ ADR-0002 bây giờ.

### Kiểm

test relay với provider giả: lỗi 5 lần → DEAD + event; `dedup_key` trùng → một dòng; work_item không đổi trạng thái sau SENT (thử ngược: cho relay gọi complete → đỏ).
""",
 "links": ["gap-communication", "gap-reliability", "notification-relay", "pos-outbox", "bat-dang-thuc", "tk-work-item-protocol", "tk-reliability-playbook", "tuong-tac-cskh"],
},
{
 "id": "tk-projections", "layer": L, "order": 1200,
 "title": "Projection có kỷ luật — 8 projection thesis ↔ view/bảng, checkpoint, và bài rebuild",
 "tag": "view SQL + projection_checkpoint",
 "summary": "Không projector worker; view là projection; hai view đối chứng (từ bảng vs từ event) làm bài kiểm 'ledger đáng tin'.",
 "body": """
| Projection (Care Model §8.1) | Hiện thực | Nguồn | Rebuild |
|---|---|---|---|
| Encounter Board | `dispatch_service._OVERVIEW_SQL` (giữ) + thêm cột từ `work_item` mở, `experience_state` mở, `expectation` gần nhất, `last_event_at` | bảng trạng thái + ledger | view |
| Work Queue | `list_worklist` (giữ) + `v_viec_cskh` (giữ) + cột ack/due/owner/why | bảng | view |
| Patient Journey | `v_timeline_luot_kham` ([[tk-mot-so-cai]]) + `route_derivation` | ledger | view |
| Experience Monitor | `v_experience_mo` = `experience_state` mở + coverage | bảng mới | view |
| Resource Load | `_STATIONS_SQL` (giữ) + overload event từ policy | bảng | view |
| Patient View | `/display` (giữ) + «bước tiếp theo» từ `next_step_of` + thông báo chờ đã duyệt | bảng | — |
| Management Analytics | `metric_daily` ([[tk-metrics]]) | ledger | rollup tính lại được |
| Audit View | `v_audit_log` (giữ, đọc nhãn từ catalog) | ledger | view |

**Checkpoint** chỉ cho consumer có trạng thái (không phải view). ⚠ Bản phác cũ dùng một con trỏ `consumer_checkpoint (consumer, last_seq)` và tính lag bằng `max(seq) − last_seq`. **Cả hai đều chưa an toàn** vì `seq` là thứ tự cấp phát chứ không phải thứ tự commit, và sequence có khoảng trống — xem hộp cảnh báo trong [[tk-event-envelope-v2]]. Hình thay thế phải chứng minh trước khi cài: xác nhận theo từng event (`(consumer, event_id)`) + consumer idempotent; số việc tồn thì đếm event chưa có dòng xác nhận, không lấy hiệu hai con số. Ngưỡng cảnh báo (`ProjectionLagThresholdExceeded` — Catalog §13) giữ nguyên ý nghĩa nhưng phải tính lại theo cách đếm ấy.

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
""",
 "links": ["state-la-projection", "gap-projection-rebuild", "tk-mot-so-cai", "tk-metrics", "chung-minh-event-driven", "tk-reliability-playbook", "cskh-views", "dispatch"],
},
{
 "id": "tk-atc-ui", "layer": L, "order": 1210,
 "title": "Giao diện — không thêm màn; thêm trường vào card, cảnh báo thành việc có id, 'Vì sao tôi thấy cảnh báo này'",
 "tag": "/truong-ca/* · /tasks · /display · /audit-log · DESIGN.md",
 "summary": "ATC card 9 trường, My Work có ack + why, Team Queue có unclaimed/overdue, Timeline có filter loại; mọi bậc kích thước theo DESIGN.md.",
 "body": """
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

Thêm cột từ [[tk-work-item-protocol]]: `owner_type/assigned_queue`, `acknowledge_by/due_at` (→ «Quá SLA» overlay đã có logic), `origin_event` nhãn («Vì sao tôi nhận việc này?» — Protocol §15), `completion_criteria.type` → nút primary đúng nghĩa («Đã giải thích cho khách» mở form attestation thay vì tick). Team Queue: tab unclaimed / assigned / blocked / overdue; **không** sort theo mới nhất mặc định («không che giấu work cũ»).

### Patient panel (`/display`)

Thêm «bước tiếp theo» (`next_step_of`) và dòng thông báo chờ đã duyệt (`experience_config.thong_bao_cho` theo phòng) — QUEUE-03: không tên đầy đủ, không chẩn đoán.

### Timeline (`/patients/[id]` → VungLamViecKhach, `/audit-log`)

Đọc `v_timeline_luot_kham`, filter theo `category` (clinical/operational/communication/decision/reliability) — §19.2. Dòng `inferred` vẽ khác `observed` (đúng Spec §3 «Không được hiển thị một suy luận như sự thật»): cùng bậc màu nhưng viền đứt + confidence — chọn từ thang DESIGN.md, không tự chế px (ratchet 102).

### Nghiệm thu

Kịch bản bấm thử theo Luật 12.4 (không code): (1) chuyển khách vào SA1, đợi quá `wait_minutes` giả 1′ → card hiện risk + việc GIAI_THICH_CHO cho CSKH; (2) CSKH bấm Nhận → chip «đã nhận» ở Trưởng ca; (3) không nhận 5′ → Trưởng ca có thông báo; (4) CSKH ghi «Đã giải thích» → risk resolved, timeline có đủ 6 dòng theo thứ tự. Đủ ba cỡ 375/768/1280 (DESIGN.md).
""",
 "links": ["product-surface", "gap-atc", "man-hinh-theo-vai", "tk-work-item-protocol", "tk-experience-state", "tk-expectation-timer", "tk-projections", "tk-reliability-playbook", "dispatch"],
},
{
 "id": "tk-reliability-playbook", "layer": L, "order": 1220,
 "title": "Reliability playbook — seq + checkpoint, quarantine, DEAD, failure event vào ledger, replay có guard",
 "tag": "migration 202609xx_reliability · scripts/phat-lai-su-kien.py",
 "summary": "Trả lời §15.6 và §16 bằng ba bảng nhỏ và một quy tắc: side effect ngoài không bao giờ chạy trong replay.",
 "body": """
### Ba bảng

- `consumer_checkpoint (consumer PK, last_seq, updated_at, clinic_id NULL = toàn hệ)` — ⚠ **chưa an toàn dưới dạng này**: đọc `event_log.seq > last_seq` bỏ sót event của transaction cấp seq sớm mà commit muộn (xem [[tk-event-envelope-v2]]). Phải đổi sang xác nhận theo từng event và consumer idempotent trước khi thay cờ `event_published`. Ghi ở đây như *yêu cầu*, không phải thiết kế đã chốt.
- `event_quarantine (id, event_id, consumer, reason, attempts, first_at, last_at, resolved_at, resolved_by, resolution)` — consumer lỗi N lần trên một event → ghi vào đây, **checkpoint vẫn tiến** (không kẹt cả hàng vì một event hỏng), `ghi_su_kien('event.quarantined', reliability)`. «dead-letter item phải có owner và resolution event» (§15.6) → `resolved_by` bắt buộc khi đóng.
- `notification_delivery.DEAD` (xem [[tk-communication-delivery]]).

### Failure event nghiệp vụ (stream `sys:<clinic>`, category `reliability`)

| Event | Ai phát | Khi |
|---|---|---|
| `notification.failed` | relay | delivery → DEAD |
| `integration.unavailable` / `.restored` | relay (Telegram 401/403), adapter POS, sau này LIS | lần lỗi đầu / lần thành công đầu sau lỗi |
| `projection.lag_exceeded` | đồng hồ | số event chưa được consumer xác nhận > 200, hoặc checkpoint cũ > 2′ (⚠ **không** dùng `max(seq) − last_seq`: sequence có khoảng trống) |
| `projection.drift` | đồng hồ (giờ) | `v_visit_state_tu_su_kien` ≠ `visit` |
| `automation.blocked_by_policy` | policy engine | authority không đủ, hoặc lab GROUP_C chặn |
| `event.validation_failed` | `ghi_su_kien` (RAISE) → caller ghi vào quarantine với payload | event_type lạ / schema sai |

`ops_status.collect()` đọc thêm: số `sys:` event 24h theo loại, DEAD/quarantine đang mở → `degraded` nếu > 0 chưa resolved. Kuma monitor `GET /health/features` (design v5 §5.6 đã đề xuất: «báo từng nhánh real|stub|disabled»).

### Replay có guard

`scripts/phat-lai-su-kien.py --consumer policy --from-seq N --dry-run` (⚠ phụ thuộc giao thức con trỏ đang bị chặn ở trên) : đặt `consumer_checkpoint` lùi lại **trong một transaction** với biến session `SET LOCAL clinicai.replay = on`; mọi action có side effect ngoài (`notify_queue` tạo delivery, adapter POS) kiểm `current_setting('clinicai.replay', true) = 'on'` → **không** tạo dòng delivery mới (chỉ ghi `policy.decided` với `payload.replay = true`). «replay không được lặp lại external side effect nếu không có guard» (§15.6). Ghi `ghi_su_kien('projection.rebuilt', …)` cuối. Quyền: MANAGEMENT + audit (§17).

### Ordering

`stream_version` cho đúng đắn trong stream; `occurred_at` cho reality. `seq` chỉ dùng để **sắp xếp khi đọc**, không dùng làm con trỏ tiêu thụ chừng nào giao thức xác nhận theo từng event chưa có và chưa có test commit đảo thứ tự (xem [[tk-event-envelope-v2]]). Late event (ghi bù với `occurred_at` quá khứ): policy đọc `recorded_at` để biết là tin muộn và **không** tự đảo outcome đã đóng (Protocol §13) — chỉ ghi `experience.reevaluate` nếu cần.

### Kiểm

test consumer: event gây exception 3 lần → quarantine + checkpoint tiến; replay dry-run → 0 dòng `notification_delivery` mới; ops_status với 1 DEAD → `degraded`.
""",
 "links": ["reliability", "gap-reliability", "gap-failure-domain", "failure-la-domain", "tk-communication-delivery", "tk-projections", "tk-policy-engine", "pos-outbox"],
},
{
 "id": "tk-metrics", "layer": L, "order": 1230,
 "title": "Metric từ event stream — mỗi chỉ số một view, rollup ngày, và phase nào mới có nghĩa",
 "tag": "view v_metric_* + metric_daily",
 "summary": "Baseline đo được từ Phase 0; coordination từ Phase A; experience từ Phase B. Không metric nào theo cá nhân trong báo cáo.",
 "body": """
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
""",
 "links": ["metrics-thesis", "gap-metrics", "kill-criteria", "tk-experience-state", "tk-work-item-protocol", "tk-projections", "humane-ops", "pilot-scope"],
},
{
 "id": "tk-ai-placement", "layer": L, "order": 1240,
 "title": "AI đúng chỗ — Interpretation/Decision, derived event có confidence/expiry, allowlist system-agent, Recommend là Decision event có người duyệt",
 "tag": "graphs/lab_triage · policy.authority_level · TAM-NHIN 3 câu",
 "summary": "Không xây AI mới ở Phase 0–A; Phase B đóng provenance; Phase C Recommend cho redistribution — rule đã chứng minh giá trị trước.",
 "body": """
Ba câu TAM-NHIN trước mọi thứ «thông minh»: *nó đọc bảng lv3 nào — bảng đó đáng tin chưa — người nào duyệt đầu ra?* Trước Phase B, `event_log`/`work_item`/`experience_state` chưa đáng tin → **không** thêm AI vận hành.

### Giữ nguyên

Lab triage (persist → hard_block GROUP_C → `staff_task` URGENT), static routing, Anthropic API 2-tier, D012/D013, checkpointer disposable. Khi `work_item` Protocol có: `create_review_tasks` tạo `work_item` node `DICHVU-DUYET-KETQUA` với `clinical_priority='urgent'`, `owner_type='role_queue' DOCTOR`, ack 15′, completion `required_event clinical.released|lab_result.finalized` — thay `staff_task` (0 dòng).

### Thêm ở Phase B — provenance đủ theo §20.10 và Spec §4

`ghi_su_kien('lab.triage_classified', evidence='inferred', confidence=<từ model>, policy_id=<rule/model version>)` khi classify xong → vào timeline, vẽ khác observed. `lab_result` thêm `triage_confidence numeric`, `triage_expires_at` (kết quả cũ phải phân loại lại nếu reference range đổi).

### Phase C — Recommend

`policy.authority_level = 'recommend'`: action `recommend_redistribution` (khi `room_overloaded` critical ∧ phòng cùng node `accepting` và rảnh) → ghi `policy.recommended` (Decision event, `evidence='decision'`, payload `{suggestion, evidence_event_ids, confidence}`) + `thong_bao` cho TRUONG_CA với hai nút **Áp dụng** (→ `move_visit_to_station` với `reason='theo đề xuất #id'`) / **Bỏ qua** (lý do). Cả hai ghi `policy.recommendation_resolved`. Đây là «lưu được: tín hiệu đầu vào, lý do, đề xuất, người phê duyệt, kết quả» (v1 §5.2). Chạy **shadow** 2 tuần (Tổng-Quan §9): ghi đề xuất, không hiện — đo precision bằng «Trưởng ca có tự làm đúng thế không».

LLM chỉ vào khi rule không đủ (v1 §5.1): tóm tắt evidence cho nhân viên («chị Lan chờ SA2 27′, đã được báo lúc 10:05 về máy siêu âm hỏng, chưa có cập nhật mới») — Spec §13 «tóm tắt evidence», «đề xuất cách diễn đạt». Không tự gửi (Spec §13 «AI không được tự gửi nội dung lâm sàng chưa duyệt»).

### System agent trong Work Item

`owner_type='system'` chỉ cho work type trong allowlist `policy.action.system_allowed = true` (Protocol §16 «AI/system agent chỉ nhận Work Type đã được allowlist»); ack = command accepted; completion vẫn cần outcome (§5 «với automated agent, acknowledgement có thể là command accepted; completion vẫn cần outcome riêng»).

### Kill switch

v2 §3.10: nếu Phase C không tăng precision so với rule, tắt `authority_level` về `observe` — một UPDATE, không deploy. Cost guard theo ngày (design v5 §6.3) giữ.
""",
 "links": ["3-muc-quyen-ai", "ai-hien-co", "gap-ai", "tk-policy-engine", "tk-work-item-protocol", "4-tang-truong-thanh", "phase-c-intelligence"],
},
{
 "id": "tk-sensing", "layer": L, "order": 1250,
 "title": "Sensing — thứ tự nguồn event theo 7 tiêu chí: thao tác có sẵn → một chạm → callback → thiết bị (sau pilot)",
 "tag": "Thesis v2 §3.4 · Pilot §7 · Catalog §6",
 "summary": "Không thêm ô nhập nào ở Phase 0–A; mọi event suy từ thao tác đang có; PatientLocationObserved để dành cho cảm biến.",
 "body": """
Xếp hạng theo «Value per unit of data-entry burden»:

| Hạng | Nguồn | Event sinh ra | Thao tác thêm | Trạng thái |
|---|---|---|---|---|
| 1 | Chuyển trạng thái lịch hẹn (`apply_action`) | appointment.* | 0 | có, đổi cửa ghi |
| 1 | Mốc quầy `tuong_tac_cskh` (CHECK_IN/OUT/THANH_TOAN/MUA_THUOC) | PatientArrived/Left, PaymentCompleted | 0 (đã bấm) | có |
| 1 | `move_visit_to_station` | QueueEntered/Exited, PatientLocationObserved{method:'staff'} | 0 (Trưởng ca đã bấm) | có |
| 1 | Ký/duyệt bệnh án, nhập kết quả, thu tiền | clinical.signed, lab_result.entered, payment.recorded | 0 | có |
| 2 | Work item start/complete | ServiceStarted/Completed | 1 chạm/bước | có API, chưa ai bấm |
| 2 | Attestation «đã giải thích» | PatientInformed | 1 form ngắn | thêm ở Phase B |
| 3 | Đồng hồ | time.* | 0 | Phase A |
| 4 | Callback Zalo OA | MessageDelivered/PatientAcknowledged | 0 | sau pilot |
| 5 | LIS/HIS callback | ResultReady | 0 (tích hợp) | chưa có đối tác |
| 6 | Thiết bị (BLE/camera) | PatientLocationObserved{method:'ble', confidence} | 0 vận hành / đắt tích hợp + pháp lý (NĐ13 biometric) | **ngoài pilot** (Pilot §5) |

Hai luật sensing đưa vào code:
1. **Không đòi nhân viên bấm để xác nhận điều DB đã biết** (bài học `LUOTKHAM-01 born COMPLETED`). Policy `SPAWN_SPINE` đánh dấu `LUOTKHAM-02` COMPLETED khi lễ tân check-in *và* hồ sơ đã xác minh (có CCCD) — suy, không hỏi.
2. **Tín hiệu thủ công phải ghi `evidence_level='self_reported'` khi là lời khách** (Zalo «tôi đã đến»), `observed` khi là thao tác nhân viên, `inferred` khi là đồng hồ/policy. Card ATC hiện khác nhau (Spec §3).

Fallback (Pilot §7): mỗi tín hiệu có nguồn ưu tiên + fallback một chạm; bảng `signal_source (clinic_id, signal, primary, fallback, reliability_note)` là tài liệu sống — có thể chỉ là mục trong `event_catalog.producer`.

Cảm biến khi nào: theo 7 tiêu chí — khi pilot cho thấy `presence không tin cậy` là lý do suppression nhiều nhất của `unexplained_wait_risk` (đo `dismiss_reason`), lúc đó mới có phép đo để mở lại (Luật 7.2).
""",
 "links": ["7-tieu-chi-event-source", "pilot-scope", "event-catalog", "tuong-tac-cskh", "instantiate-visit", "tk-experience-state", "fhir-mapping"],
},
{
 "id": "tk-governance", "layer": L, "order": 1260,
 "title": "Governance ở cấp event — privacy_tags, RLS cho bảng mới, partition theo tháng, replay có audit",
 "tag": "Care Model §17 · ADR-0009 · SO-LUAT 7/8",
 "summary": "Mọi bảng mới đi đúng khuôn tenant; event_log chia tháng khi > 1 triệu dòng; không PII trong tin, không PII trong log.",
 "body": """
- **Khuôn tenant** (ADR-0009, GIAI-THICH-CODE §9.7): `event_catalog`, `policy`, `policy_case`, `expectation`, `experience_state`, `notification_delivery`, `notification_route`, `event_quarantine`, `metric_daily`, `station_load_sample` — tất cả `clinic_id NOT NULL` + FK + index dẫn đầu + policy `%_select_own_clinic` (hoặc RLS bật 0 policy cho bảng chỉ-backend: `consumer_checkpoint`, `event_quarantine`, `notification_delivery`). Test `multi_tenant_foundation.sql` đếm 69 → 79; ghi lý do đổi số trong comment test (luật của file đó).
- **`privacy_tags`** mặc định từ catalog: `clinical` cho `clinical.*`/`lab_result.*`, `financial` cho `payment.*`, `contact` cho `cskh.*`, `telemetry` cho `slot_hold.*`. `v_audit_log` cho vai vận hành **loại** `clinical` (Luật 8.2 «trong vết chỉ có mã số»); MANAGEMENT xem đủ như hiện nay.
- **Payload tối thiểu** giữ nguyên nguyên tắc «chỉ ID» (relay làm giàu lúc gửi). Catalog `payload_schema` từ chối field tên `phone*`, `national_id*`, `address*` — test.
- **Retention**: SO-LUAT 7: không xoá. Khi `event_log` > 1 triệu dòng (~3 năm ở 2.400/ngày): `PARTITION BY RANGE (occurred_at)` theo tháng qua bảng mới + view gộp — ghi là **ngưỡng**, không làm trước.
- **Replay**: chỉ MANAGEMENT, script ghi `projection.rebuilt` với `actor_staff_id`; log kỹ thuật không chứa payload (redaction hiện có).
- **Consent** (Catalog §17 privacy classification): `clinical_data_consent` đã có bảng + trigger; event `clinical_data_consent.granted/revoked` đã có nhãn — policy `notify patient` kiểm consent trước khi tạo delivery channel `zalo_oa`.
- **Không PII qua Telegram** — test hiện có giữ; mở rộng cho mọi `channel` trong `notification_delivery` (render trước khi ghi `payload_rendered`? Không — không lưu bản render, chỉ lưu `provider_message_id`).
- **Model provenance**: `policy_id/policy_version` trên event; với LLM: `rule_or_model = 'claude-haiku-4-5@prompt-v3'`, không lưu prompt chứa dữ liệu thô (§17).
""",
 "links": ["governance-event", "multi-tenant-rls", "tk-event-catalog-table", "tk-reliability-playbook", "tk-communication-delivery", "adr-so-luat"],
},
{
 "id": "tk-modular-monolith", "layer": L, "order": 1270,
 "title": "Thi hành ADR-0001 — thư mục theo 6 lớp thesis: engine/ (su_kien, viec, dong_ho, luat, chieu) · modules/ · ledgers/ · platform/",
 "tag": "ADR-0001 · Luật 4.4 · import-linter",
 "summary": "Ranh giới nằm trong code: engine không biết nghiệp vụ, module không ghi chéo, manifest 7 mục máy đọc được; dời dần, mỗi cụm một PR.",
 "body": """
```
src/clinicai/
  engine/                 # Lớp 2–3 thesis: không biết 'khám', 'siêu âm'
    su_kien.py            # ghi(), catalog, timeline          ← tk-emit-function
    viec.py               # Work Item state machine (dời từ services/work_item_service.py)
    dong_ho.py            # expectation loop                    ← tk-expectation-timer
    luat.py               # policy evaluator (hàm thuần) + runner
    trai_nghiem.py        # experience_state lifecycle
    chieu.py              # projection helpers, checkpoint, drift
    tin_nhan.py           # notification_delivery relay (dời notification_relay.py)
  modules/                # Lớp nghiệp vụ, mỗi module một manifest.py
    dat_lich/   (booking_service, booking_override_service, slot_hold_service, luat_bac_si_service, config_service phần roster)
    tiep_nhan/  (check-in, visit_progress, dispatch_service, gate_rule_service, route_derivation)
    kham/       (clinical_record, clinical_form, clinical_sign, ultrasound, service_order)
    ket_qua/    (lab_order, lab_safety, tep_ket_qua, graphs/lab_triage)
    thu_ngan/   (payment, checkout, cashier_board, pos_*)
    nha_thuoc/  (pharmacy)
    cskh/       (tuong_tac_cskh, cskh_service, recall_*, phan_hoi_khach, thong_bao, man_khach_hang)
  ledgers/    (patient_service, mpi_service, staff_service, clinic_settings_service, clinic_config_service)
  platform/   (identity, idempotency, change_broker, ops_status, telegram/zalo providers, llm, voice)
```

**Manifest 7 mục** (ADR-0001) mỗi module: `owns_tables` (writer duy nhất — Luật 4.4) · `api` · `nodes` (node_code module đăng ký) · `form_schema` · `events` (emit/listen — **đọc từ `event_catalog.producer`**) · `provides/consumes` · `permissions`. CI: `import-linter` chặn `modules/a` import `modules/b` (chỉ qua `engine`/`ledgers`); checker «mỗi bảng đúng một `owns_tables`» đọc manifest + grep `INSERT/UPDATE` → ceiling như tenant-audit.

**Vì sao làm bây giờ chứ không sau**: các mảnh mới (su_kien, dong_ho, luat, trai_nghiem) **chưa có chỗ** trong `services/` phẳng; đặt chúng vào `engine/` từ đầu là thi hành ADR-0001 với chi phí gần 0, và cho 69 file cũ một đích để dời dần (mỗi cụm một PR, đúng nhánh ≤ 2 ngày).

**worker.py** thành `engine/nen.py`: một tiến trình, ba vòng (`tin_nhan`, `dong_ho`, `luat`) chia sẻ pool + LISTEN + heartbeat; `--pos-relay` giữ profile riêng. RabbitMQ mode + `event_bus/` **xoá** (ADR-0002 phần chưa làm; `RabbitMQPublisher.publish()` vẫn `raise NotImplementedError`).

Đây cũng là bản đồ sản phẩm 6 lớp (v1 §8) nhìn thấy được trong `ls`: engine = Operational State + Coordination + Intelligence; modules = Sensing + Human Interfaces theo nghiệp vụ; platform = Governance.
""",
 "links": ["adr-so-luat", "kien-truc-toi-thieu", "6-lop-san-pham", "tk-emit-function", "tk-expectation-timer", "tk-policy-engine", "tk-communication-delivery", "ci-guards", "stack"],
},
]
