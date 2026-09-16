---
title: "ghi_su_kien() — cửa ghi duy nhất: hàm SQL + wrapper Python, CI đưa 29 INSERT về 0"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "migration + src/clinicai/su_kien.py + test ceiling"
tags: [clinicai, lop5-thiet-ke]
---

# ghi_su_kien() — cửa ghi duy nhất: hàm SQL + wrapper Python, CI đưa 29 INSERT về 0

> [!abstract] Điền envelope, kiểm catalog, cấp stream_version, trả event_id để làm causation cho bước sau; Python không tự INSERT nữa.

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

Trigger BEFORE INSERT ([[tk-event-envelope-v2|Envelope v2]]) vẫn lo `stream_id`/`stream_version`/denormalise — hàm không lặp việc đó.

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

Cơ học: mỗi `INSERT INTO event_log` → `await su_kien.ghi(conn, …)`. `services/audit.py:record_event` trở thành alias. Hai hàm SQL (`move_visit_to_station`, check-in) gọi thẳng `ghi_su_kien`. Làm theo cụm (booking → cskh → dispatch → clinical → config), mỗi cụm một PR, ratchet trong CI: `grep -c "INSERT INTO event_log\|INSERT INTO public.event_log" src/clinicai` **chỉ được giảm** (mẫu Luật 4.1).

### Kiểm

- `test_ghi_su_kien_tu_choi_event_la.py`: event_type lạ → `check_violation`.
- SQL test: `ghi_su_kien` hai lần cùng stream trong hai session đồng thời → `stream_version` 1 và 2, không trùng.
- Ratchet grep INSERT trực tiếp.

## Nối tới
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[event-log-table|event_log]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[ci-guards|CI]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[selective-event-sourcing|Selective event sourcing]]
- [[anti-patterns|10 anti-pattern cần cấm]]
- [[event-log-table|event_log]]
- [[ci-guards|CI]]
- [[gap-envelope|Khoảng cách 1]]
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[phase-0-nen|Phase 0]]
