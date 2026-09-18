---
title: "Kiến trúc logic tối thiểu — 12 capability trên modular monolith, và cái nào đã có"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §21 · §23"
tags: [clinicai, lop2-kien-truc]
---

# Kiến trúc logic tối thiểu — 12 capability trên modular monolith, và cái nào đã có

> [!abstract] Không cần distributed event platform; phiên bản đầu = 1 DB + event table + outbox + projector + timer + idempotency + state machine + policy versioning.

Sơ đồ (*§21*): Sources & Human Actions → Ingestion + Validation → **Event Ledger** → Projectors → Operational Read Models; Ledger → Policy / Process Managers → Commands & Work Items → Humans / Systems → (vòng về Sources).

12 capability (*§21*) ↔ code:

| # | Capability | Có gì |
|---|---|---|
| 1 | Ingestion adapters: UI, HIS/EHR, LIS, CRM, device, messaging | UI (FastAPI router) ✅; còn lại ❌ (`PosPort` là mẫu adapter) |
| 2 | Identity/correlation: map patient, encounter, order, external IDs | `patient`/`visit`/`appointment` FK ✅; `mpi_service` dò trùng ✅; correlation_id ❌ |
| 3 | Event validation: schema, permission, duplication, timestamp | permission (JWT + role) ✅; schema/dup ❌ |
| 4 | Event ledger: append-only, partitioned streams, versioning | append-only ✅; stream/version ❌ |
| 5 | Projectors | view SQL ✅ (không cần worker) |
| 6 | Policy engine: rule có version và audit | rule là dữ liệu ✅; version/audit ❌ |
| 7 | Process managers: journey, timer, compensation, commitment | ❌ |
| 8 | Work orchestration: assignment, acknowledgement, SLA, escalation | gate + transition ✅; 4 thứ kia ❌ |
| 9 | Command gateway: kiểm authority trước action | `require_role` + `actor_roles` theo node ✅ (ADR-0004) |
| 10 | Observability: lag, failure, replay, freshness | `ops_status`, heartbeat ✅; lag/freshness ❌ |
| 11 | Governance: access, privacy, retention, audit | RLS tenant/role ✅, redaction ✅ |
| 12 | Analytics sink với pseudonymization | `reports_service` đọc trực tiếp; không sink |

Phạm vi phiên bản đầu (*§23*):

> «Không cần xây distributed event platform quy mô lớn ngay. Phiên bản đầu nên là modular monolith với semantic event backbone: một transactional database đáng tin cậy; append-only domain event table; transactional outbox; projector workers; durable job/timer mechanism; idempotency store; Work Item state machine; policy versioning; event timeline; replay có kiểm soát; adapters qua webhook/API; analytics export tách biệt.»

> «Điều cần bảo vệ từ ngày đầu không phải "scale hạ tầng", mà là: event semantics; correlation/causation; ordering boundary; immutable history; projection discipline; completion/outcome semantics.» — *§23*

Câu này **khớp từng chữ** với ADR-0001/0002/0005 và SO-LUAT Phần 7 («Postgres là hạ tầng có trạng thái duy nhất»). Nghĩa là thesis và sổ luật **không mâu thuẫn về hạ tầng** — mâu thuẫn chỉ ở *nghĩa* của dữ liệu. Toàn bộ [[tk-nguyen-tac|Nguyên tắc thiết kế đích]] xây trên điểm gặp nhau này.

## Nối tới
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[stack|Stack đang chạy]]
- [[workflow-kernel|Workflow kernel]]
- [[gap-timer|Khoảng cách 4]]

## Được dẫn từ
- [[stack|Stack đang chạy]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
