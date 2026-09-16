---
title: "Workflow kernel — node_definition (41) · node_dependency (18) · work_item · gate SQL · Command API"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "20260730000005 · ADR-0011 · services/work_item_service.py"
trang_thai: Một phần
tags: [clinicai, lop3-code]
---

# Workflow kernel — node_definition (41) · node_dependency (18) · work_item · gate SQL · Command API

> [!abstract] Luồng khám là dữ liệu; gate FS/SS/FF/SF chạy trong SQL; nhưng prod mới có 7 work_item từ 1 lượt khám.

### Bảy bảng (`20260730000005_workflow_kernel.sql`)

`node_definition` (code, name, flow_group, workspace, actor_roles[], priority P0–P2, is_group, config jsonb, current_version) · `node_definition_version` (snapshot đóng băng) · `node_dependency` (predecessor/successor, FS/SS/FF/SF, is_blocking, gate_group, gate_operator AND/OR/XOR, condition) · `work_item` · `work_item_dependency` · `work_item_event` (append-only: command ∈ create/start/complete/skip/cancel/reassign) · `follow_up_case`.

> «This is the part of ClinicAI that makes it a workflow product rather than another clinic CRUD app: what happens in the clinic is DATA (node_definition), not Python.» — *migration header*

Prod 05/09: **41 node** (37 seed + 4 `THUOC-01..04`), 9 flow_group; **18 cạnh** FS (`LUOTKHAM-01→02→03→05→13→14→15`, `DATLICH-01→…→04`, `THEODOI-01→…→04`, `NGUONLUC`, `KETQUA-XETNGHIEM→DUYET-KETQUA`). KHAM-* và DICHVU-* **cố ý không nối** («which service follows which exam is a clinical decision, not something to infer from a table»).

### Gate trong SQL — `work_item_gate_blockers(work_item_id, phase)`

`start` ← FS/SS · `complete` ← FF/SF. Predecessor "xong" = COMPLETED **hoặc SKIPPED**; CANCELLED không thoả. Nhóm AND/OR/XOR; XOR đóng khi cả hai nhánh đều xong — và hàm trả về *các nhánh đã xong* «vì chính chúng là vấn đề» (ADR-0011). Rỗng = mở.

### Command API — `POST /work-items/{id}/commands/{start|complete|skip|cancel}`

`work_item_service.issue()` trong **một transaction**: `SELECT … FOR UPDATE` + join `clinic_membership` (khác tenant → 404, không 403) → kiểm transition (`_TRANSITIONS`) → kiểm vai theo `node_definition.actor_roles` (rỗng = «nobody yet», fail-closed) → gate → `UPDATE … WHERE status = $current AND version = $expected` → INSERT `work_item_event`. Bắt buộc `Idempotency-Key`; khoá được trả lại khi 4xx (`tra_khoa_neu_bi_tu_choi`).

`GET /work-items?workspace=` — worklist theo `node_definition.workspace` («a clinic that adds a node to its reception desk gets it on the board without a deploy»), **không lọc theo ngày mặc định** («a queue that resets at midnight loses the patient who is still sitting there»). `GET /visits/{id}/work-items` — thứ tự theo độ sâu `node_dependency` (CTE đệ quy). `GET …/blockers` — «What is still in the way — so the UI can say why a button is disabled.»

### Đo prod

`work_item`: **7 dòng, 1 visit** — LUOTKHAM-01 COMPLETED, 02/03/05/13/14 **CANCELLED**, 15 COMPLETED. `work_item_event`: 7 dòng, toàn `create`. Không `start`/`complete` nào từng được bấm. `follow_up_case`: 0. `staff_task`: 0 (đã không dùng). Tức là kernel **chạy được nhưng chưa được dùng** — vì Dr4Women hôm nay mới dùng CSKH đặt lịch ([[gap-wedge-mismatch|Khoảng cách 15]]).

### Khoảng cách với Work Item Protocol

Xem [[gap-work-item|Khoảng cách 3]]. Ngắn gọn: có transition + gate + version + event, **không có** owner bắt buộc / acknowledge / SLA / escalation / completion criteria / origin event / hai trục ưu tiên.

## Nối tới
- [[work-item-commitment|Work Item là commitment]]
- [[gap-work-item|Khoảng cách 3]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[instantiate-visit|Check-in sinh việc]]
- [[dispatch|Điều phối Trưởng ca]]
- [[gap-wedge-mismatch|Khoảng cách 15]]
- [[ontology-9|Ontology]]

## Được dẫn từ
- [[north-star|North Star]]
- [[ontology-9|Ontology]]
- [[6-lop-san-pham|Product map 6 lớp]]
- [[selective-event-sourcing|Selective event sourcing]]
- [[work-item-commitment|Work Item là commitment]]
- [[kien-truc-toi-thieu|Kiến trúc logic tối thiểu]]
- [[product-surface|Product surface sinh ra từ event model]]
- [[instantiate-visit|Check-in sinh việc]]
- [[dispatch|Điều phối Trưởng ca]]
- [[idempotency-concurrency|Bất biến ép ở Postgres]]
- [[so-cai-phan-manh|Bảy sổ cái rời]]
- [[gap-work-item|Khoảng cách 3]]
- [[gap-wedge-mismatch|Khoảng cách 15]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
