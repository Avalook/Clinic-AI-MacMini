---
title: "notification_delivery — trả nợ ADR-0002: mỗi kênh một dòng, attempts/backoff/DEAD, MessageSent ≠ PatientInformed"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "migration 202609xx_notification_delivery · notification_relay.py đọc bảng mới"
tags: [clinicai, lop5-thiet-ke]
---

# notification_delivery — trả nợ ADR-0002: mỗi kênh một dòng, attempts/backoff/DEAD, MessageSent ≠ PatientInformed

> [!abstract] Nhân khuôn pos_outbox; event_published thôi mang nghĩa 'đã gửi'; Zalo OA sau này = thêm channel.

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

**Ba mức**: `SENT` khi provider nhận (`provider_message_id`); `DELIVERED` khi callback (Telegram không có → giữ SENT; Zalo OA có); `READ` khi có `read_at` (in_app: bấm mở). **Không mức nào đóng work item.** Việc đóng chỉ bằng `issue('complete')` với completion contract — [[tk-work-item-protocol|Work Item Protocol trên kernel]].

**PatientInformed** = dòng `tuong_tac_cskh` với `ket_qua='DA_LIEN_HE'` + `chu_de` — structured attestation (Protocol §8), giữ nguyên cách CSKH đang làm. Khi Zalo OA có callback «khách đã đọc», đó là `PatientAcknowledged` (Catalog §10), vẫn **chưa** là PatientInformed nếu chủ đề không khớp.

**Zalo OA** (D010, kênh bệnh nhân): thêm `channel='zalo_oa'`, adapter theo khuôn `PosPort` (port + null adapter + test boundary). Không có gì khác phải đổi — đó là lợi ích của việc trả nợ ADR-0002 bây giờ.

### Kiểm

test relay với provider giả: lỗi 5 lần → DEAD + event; `dedup_key` trùng → một dòng; work_item không đổi trạng thái sau SENT (thử ngược: cho relay gọi complete → đỏ).

## Nối tới
- [[gap-communication|Khoảng cách 8]]
- [[gap-reliability|Khoảng cách 10]]
- [[notification-relay|notification_relay]]
- [[pos-outbox|pos_outbox]]
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tuong-tac-cskh|tuong_tac_cskh]]

## Được dẫn từ
- [[bat-dang-thuc|Sáu bất đẳng thức]]
- [[reliability|Reliability semantics]]
- [[anti-patterns|10 anti-pattern cần cấm]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[notification-relay|notification_relay]]
- [[pos-outbox|pos_outbox]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[gap-communication|Khoảng cách 8]]
- [[gap-reliability|Khoảng cách 10]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-experience-state|experience_state]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tk-governance|Governance ở cấp event]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[phase-a-closed-loop|Phase A]]
- [[cau-hoi-mo|Câu hỏi mở]]
