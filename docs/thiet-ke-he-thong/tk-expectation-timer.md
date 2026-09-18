---
title: "expectation + đồng hồ — bảng kỳ vọng, trigger MET khi event tới, vòng lặp FIRED trong worker có sẵn"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "ADR-0016 (đề xuất) · migration 202609xx_expectation · worker.py --dong-ho"
tags: [clinicai, lop5-thiet-ke]
---

# expectation + đồng hồ — bảng kỳ vọng, trigger MET khi event tới, vòng lặp FIRED trong worker có sẵn

> [!abstract] 'Sự kiện không xảy ra' thành sự kiện: ExpectedEventDeadlineReached, idempotent, huỷ được, 0 hạ tầng mới.

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

Cùng tiến trình relay (nguyên tắc 7 của [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]): mỗi 30s hoặc khi được đánh thức, và **không** cần LISTEN riêng:

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

- **Policy** ([[tk-policy-engine|policy + policy_case]]) khi tạo work item: `acknowledge_by` → expectation `work_item.acknowledge` on `time.ack_timeout`; `complete_by` → `work_item.complete` on `time.sla_exceeded`.
- **Move**: `move_visit_to_station` → expectation «rời node này» (`dispatch.moved` với `from_node = X`) deadline = `dispatch_threshold.wait_minutes` → `time.wait_threshold` — đây chính là WaitingThresholdExceeded thành *event* thay vì màu trên bảng.
- **Check-in**: expectation `lab_result.entered` sau `lab_result.ordered` deadline `luat_cskh.CHO_KQ_XN`.
- **Nhắc tái khám**: thay `sinh_viec_nhac_tai_kham` lúc mở màn bằng expectation `FollowupWindowOpened` đăng ký lúc `episode`/`nhac_tai_kham` sinh → sinh việc đúng ngày dù không ai mở màn.

### Kiểm

SQL test: đăng ký expectation, INSERT event khớp → MET, không FIRED; đăng ký deadline quá khứ, chạy câu FIRED → đúng một event `time.*`, chạy lại → 0 (idempotent). pytest cho vòng worker với pool giả. «Thử ngược»: bỏ `SKIP LOCKED` → test song song đỏ.

## Nối tới
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[gap-timer|Khoảng cách 4]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[notification-relay|notification_relay]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[dispatch|Điều phối Trưởng ca]]
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]

## Được dẫn từ
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[timer-expected-event|Thời gian và 'sự kiện không xảy ra']]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]
- [[gap-timer|Khoảng cách 4]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-experience-state|experience_state]]
- [[tk-atc-ui|Giao diện]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[phase-a-closed-loop|Phase A]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[cau-hoi-mo|Câu hỏi mở]]
