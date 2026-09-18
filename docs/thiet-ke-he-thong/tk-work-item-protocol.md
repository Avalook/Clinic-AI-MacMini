---
title: "Work Item Protocol trên kernel — 8 trạng thái, 8 lệnh mới, 4 mốc SLA, completion contract, hai trục ưu tiên"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "ADR-0015 (đề xuất) · migration 202609xx_work_item_protocol · work_item_service.py"
tags: [clinicai, lop5-thiet-ke]
---

# Work Item Protocol trên kernel — 8 trạng thái, 8 lệnh mới, 4 mốc SLA, completion contract, hai trục ưu tiên

> [!abstract] Mở rộng work_item đúng Protocol v1 mà không đụng gate SQL và 4 lệnh đang có; thong_bao trở thành role-queue assignment.

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

`escalation_policy` là dòng trong bảng `policy` ([[tk-policy-engine|policy + policy_case]]) loại `escalation`: `{grace_min, recipient_queue, priority_bump, repeat_after_min, stop_on}`. Timer ([[tk-expectation-timer|expectation + đồng hồ]]) phát `AcknowledgementTimeoutOccurred` → policy → `escalate` (system) → dòng `thong_bao` cho `recipient_queue` với `work_item_id`. «Escalation không thay thế owner» — `assigned_to` giữ, `escalated_to` thêm.

### `thong_bao` và `nhac_tai_kham` sau đây

- `thong_bao` = kênh hiển thị của work item có `owner_type='role_queue'`: thêm cột `work_item_id`; `da_xu_ly` gọi `issue('complete')`; `da_doc` **không** phải ack — ack là nút riêng («Không tự động chuyển Active chỉ vì người dùng mở màn hình»).
- `nhac_tai_kham` giữ nguyên bảng (33 dòng thật), nhưng mỗi dòng `CHO_GOI` được policy vật chất hoá thành một `work_item` node `THEODOI-03` với `completion_criteria = required_event cskh.tuong_tac[loai=NHAC_HEN|XAC_NHAN_LICH]` — đó là cách «bảng mỏng để nhận việc» mà chính migration `20260809000005` dự trù.

### Kiểm

pytest cho `_TRANSITIONS` mới (hàm thuần); SQL test `work_item_open_needs_owner` sau VALIDATE; test «duplicate origin_event → một work item»; test «complete bị từ chối khi required_event chưa có; tự complete khi có».

## Nối tới
- [[work-item-commitment|Work Item là commitment]]
- [[gap-work-item|Khoảng cách 3]]
- [[workflow-kernel|Workflow kernel]]
- [[thong-bao|thong_bao]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-communication-delivery|notification_delivery]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]

## Được dẫn từ
- [[wedge|Wedge]]
- [[work-item-commitment|Work Item là commitment]]
- [[workflow-kernel|Workflow kernel]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[thong-bao|thong_bao]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]
- [[gap-work-item|Khoảng cách 3]]
- [[gap-atc|Khoảng cách 12]]
- [[gap-wedge-mismatch|Khoảng cách 15]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-experience-state|experience_state]]
- [[tk-communication-delivery|notification_delivery]]
- [[tk-atc-ui|Giao diện]]
- [[tk-metrics|Metric từ event stream]]
- [[tk-ai-placement|AI đúng chỗ]]
- [[phase-a-closed-loop|Phase A]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
