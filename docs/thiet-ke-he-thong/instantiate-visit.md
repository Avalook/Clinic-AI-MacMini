---
title: "Check-in sinh việc — instantiate_visit_workflow đi ngược node_dependency, không danh sách cứng"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "20260731000003_visit_workflow_instantiation.sql"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# Check-in sinh việc — instantiate_visit_workflow đi ngược node_dependency, không danh sách cứng

> [!abstract] Phản xạ Level 4 đầu tiên đã có: PatientArrived → tạo encounter + work item; và lý do LUOTKHAM-01 sinh ra ở COMPLETED.

> «node_definition has had 37 rows and work_item has had ZERO since W4. The kernel could transition items and evaluate gates, but nothing ever created one […]. This is the missing writer.» — *migration header*

Cơ chế: CTE đệ quy từ node có `config->>'spawn_on' = 'visit.checkin'` (đặt trên `LUOTKHAM-01` — **là dữ liệu**, «so a clinic can move its own starting node without a deploy») đi theo `node_dependency` → INSERT `work_item` cho cả xương sống 7 node, `ON CONFLICT (clinic_id, visit_id, node_code) WHERE status <> 'CANCELLED' DO NOTHING` (idempotent qua `uq_work_item_visit_node_live`) → INSERT `work_item_event 'create'` → INSERT `work_item_dependency` từ template.

Ba quyết định ghi trong file đáng giữ:

> «WHY THE WHOLE SPINE, not one node at a time. […] Creating each node lazily needs a second write that can fail after the first commits, and its failure mode is a visit with no open work and no error anywhere, which is the worst outcome available in a clinic.»

> «LUOTKHAM-01 is born COMPLETED when an actor is supplied, because pressing check-in IS performing "tiếp nhận người bệnh". Leaving it PENDING would hold a blocking FS gate shut in front of the nurse until somebody clicked to assert a fact the database already stores.»

> «KHAM-* and DICHVU-* are the OUTPUT of LUOTKHAM-05 — a clinical decision the seed leaves unlinked on purpose; stamping them at check-in would invent clinical intent nobody expressed.»

`cancel_visit_workflow()` — undo check-in: CANCELLED (không SKIPPED — «SKIPPED means "this step will not happen" and opens the downstream gates; an undone or cancelled arrival means the whole visit is off»), COMPLETED giữ nguyên («history is not rewritten because the front desk changed its mind»).

### Đối chiếu thesis

Đây là **Expected Journey** (Care Model §9) được vật chất hoá đúng cách: template (`node_dependency`) → instance (`work_item_dependency`) có đóng băng phiên bản (`node_version_id NOT NULL`). Và là phản xạ Level 4 số 1: «PatientArrived → tạo encounter và work item tiếp đón» (*v1 §10*).

Hai điều thesis đòi thêm mà ở đây chưa có: (a) mỗi work item sinh ra phải có `origin_event_id` (§13 Work Item: «Reason: event/policy nào tạo ra việc») — hiện `work_item_event.metadata` ghi `spawn_on` chứ không trỏ event; (b) sinh việc là *policy* (trigger = PatientArrived) — hiện là hàm được `booking_service._open_visit` gọi thẳng. [[tk-policy-engine|policy + policy_case]] chuyển nó thành policy đầu tiên trong bảng `policy`, giữ nguyên hàm SQL làm *action*.

## Nối tới
- [[workflow-kernel|Workflow kernel]]
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[tk-policy-engine|policy + policy_case]]
- [[7-tieu-chi-event-source|Bảy tiêu chí cho mọi nguồn event]]

## Được dẫn từ
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[journey-process-manager|Patient Journey là Process Manager]]
- [[workflow-kernel|Workflow kernel]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-sensing|Sensing]]
