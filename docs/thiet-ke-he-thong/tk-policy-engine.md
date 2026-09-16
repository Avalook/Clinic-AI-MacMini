---
title: "policy + policy_case — luật phản ứng là dữ liệu: trigger event → điều kiện → hành động → outcome; version, owner, test theo dòng"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "migration 202609xx_policy · src/clinicai/engine/policy.py · worker.py"
tags: [clinicai, lop5-thiet-ke]
---

# policy + policy_case — luật phản ứng là dữ liệu: trigger event → điều kiện → hành động → outcome; version, owner, test theo dòng

> [!abstract] Bảng thứ mười cho loại luật thesis đòi; đọc event_log qua checkpoint; ba policy đầu cho pilot; process manager = tập policy.

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

Cùng tiến trình worker, đánh thức bởi `clinicai_changes` (t = event_log): đọc `event_log WHERE seq > consumer_checkpoint('policy') ORDER BY seq LIMIT 200`, với mỗi event tìm policy `trigger_event_type` khớp và `is_active` và `now() BETWEEN effective_from AND coalesce(effective_to,'infinity')`, load facts, đánh giá, thực thi action **trong một transaction** cùng với `ghi_su_kien('policy.decided', …, evidence='decision', policy_id, policy_version, causation=event_id)`, rồi tiến checkpoint. Idempotency: action `create_work_item` nhờ `uq_work_item_origin`; `register_expectation` nhờ `uq_expectation_once`; `notify_queue` nhờ `uq_thong_bao_dang_mo`. Consumer lỗi → checkpoint không tiến, event vào `event_quarantine` sau N lần ([[tk-reliability-playbook|Reliability playbook]]).

### Bốn policy đầu (seed cho Dr4Women, theo tenant)

1. **SPAWN_SPINE_ON_CHECKIN** (journey, act): trigger `appointment.checked_in` → action `sql:instantiate_visit_workflow` (hàm có sẵn), causation = event. Chỉ chuyển "ai gọi" từ code sang bảng.
2. **ACK_TIMEOUT_ESCALATE** (escalation, act): trigger `time.ack_timeout` → điều kiện `work_item.status = 'ASSIGNED'` → action `escalate` + `notify_queue TRUONG_CA` → outcome `work_item.acknowledge`. Grace 5′ → 10′ (Protocol §11).
3. **UNEXPLAINED_WAIT** (experience, observe→act): trigger `time.wait_threshold` → điều kiện `visit active AND onsite AND stream_lacks(cskh.tuong_tac[loai∈{HOI_THAM,KHAC} & subject='cho'] within valid_until)` → action `detect_experience(unexplained_wait_risk)` + `create_work_item(node THEODOI-03 | 'GIAI_THICH_CHO', owner_queue CSKH, ack 5′, complete 15′, completion required_event cskh.tuong_tac[subject='cho'])` → outcome `cskh.tuong_tac`.
4. **CONTINUITY_ON_CHECKOUT** (journey, act): trigger `dispatch.checkout` → điều kiện `open commitments: work_item PENDING/IN_PROGRESS OR lab_result unreviewed` → action `open_follow_up` (writer đầu tiên của `follow_up_case`) + `create_work_item(THEODOI-01, owner_queue CSKH)` → outcome `work_item.acknowledge`.

### Version/owner cho 6 bảng luật cũ (migration nhỏ)

`ALTER TABLE luat_cskh, dispatch_threshold, visit_gate_rule, luat_bac_si_bat_buoc, route_template, doctor_booking_override ADD COLUMN version int DEFAULT 1, ADD COLUMN effective_from timestamptz DEFAULT now(), ADD COLUMN owner_role text` + trigger AFTER UPDATE ghi `policy.version_activated` (Catalog §13 PolicyVersionActivated). Pilot §14: «Mọi thay đổi policy trong live pilot phải có version và ngày hiệu lực để số liệu không bị trộn.»

### Vì sao không nhét vào view như `luat_cskh`

View trả lời «bây giờ ai cần gì» — tốt và giữ. Policy trả lời «**khi** X xảy ra thì làm Y và đóng bằng Z» — có thời điểm, có owner, có outcome. Hai loại luật, hai chỗ (đúng lý lẽ `luat_bac_si_service`: hai câu hỏi khác nhau, hai bảng).

## Nối tới
- [[policy-engine|Policy Engine]]
- [[gap-policy|Khoảng cách 9]]
- [[gap-process-manager|Khoảng cách 7]]
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-experience-state|experience_state]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[instantiate-visit|Check-in sinh việc]]
- [[gate-rule|visit_gate_rule]]

## Được dẫn từ
- [[vong-lap|Vòng lặp Reality → Event → State → Interpretation → Decision → Action]]
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[policy-engine|Policy Engine]]
- [[anti-patterns|10 anti-pattern cần cấm]]
- [[instantiate-visit|Check-in sinh việc]]
- [[gate-rule|visit_gate_rule]]
- [[realtime-sse|LISTEN/NOTIFY → ChangeBroker → SSE]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]
- [[gap-process-manager|Khoảng cách 7]]
- [[gap-policy|Khoảng cách 9]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-experience-state|experience_state]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tk-ai-placement|AI đúng chỗ]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[phase-a-closed-loop|Phase A]]
- [[cau-hoi-mo|Câu hỏi mở]]
