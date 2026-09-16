---
title: "Envelope v2 — một migration cộng thêm 14 cột, trigger cấp stream_version, backfill từ dữ liệu có sẵn"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "ADR-0014 (đề xuất) · migration 202609xx_event_envelope_v2"
tags: [clinicai, lop5-thiet-ke]
---

# Envelope v2 — một migration cộng thêm 14 cột, trigger cấp stream_version, backfill từ dữ liệu có sẵn

> [!abstract] Đưa event_log lên đủ 17 trường thesis mà không vỡ đường nào đang chạy.

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

## Nối tới
- [[event-envelope|Event envelope chuẩn]]
- [[gap-envelope|Khoảng cách 1]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]

## Được dẫn từ
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[metrics-thesis|Bốn nhóm chỉ số]]
- [[event-envelope|Event envelope chuẩn]]
- [[event-log-table|event_log]]
- [[gap-envelope|Khoảng cách 1]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[gap-reliability|Khoảng cách 10]]
- [[gap-metrics|Khoảng cách 13]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-projections|Projection có kỷ luật]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[phase-0-nen|Phase 0]]
- [[cau-hoi-mo|Câu hỏi mở]]
