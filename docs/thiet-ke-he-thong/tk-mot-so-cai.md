---
title: "Một sổ cái, nhiều bảng chuyên biệt — trigger đổ work_item_event / gate_override / thong_bao vào event_log cùng transaction"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "migration 202609xx_mot_so_cai · bất biến 1"
tags: [clinicai, lop5-thiet-ke]
---

# Một sổ cái, nhiều bảng chuyên biệt — trigger đổ work_item_event / gate_override / thong_bao vào event_log cùng transaction

> [!abstract] Giữ nguyên 7 sổ; mọi thay đổi trạng thái của 4 domain event-centric để lại một dòng event_log có stream_id — timeline một lượt khám thành một SELECT.

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

## Nối tới
- [[stream-boundary|Năm stream]]
- [[so-cai-phan-manh|Bảy sổ cái rời]]
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-projections|Projection có kỷ luật]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]

## Được dẫn từ
- [[stream-boundary|Năm stream]]
- [[selective-event-sourcing|Selective event sourcing]]
- [[so-cai-phan-manh|Bảy sổ cái rời]]
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[gap-projection-rebuild|Khoảng cách 6]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-projections|Projection có kỷ luật]]
- [[phase-0-nen|Phase 0]]
