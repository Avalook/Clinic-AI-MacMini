---
title: "Năm loại event — Observed · Domain · Derived · Decision · Outcome"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §3 · Catalog §4"
tags: [clinicai, lop2-kien-truc]
---

# Năm loại event — Observed · Domain · Derived · Decision · Outcome

> [!abstract] Phân loại theo nguồn và vai trò; Derived phải ghi độ chắc chắn, không được giả dạng Observed.

Quy tắc đặt tên (*Care Model §3.1*): «Một domain event phải được viết ở thì quá khứ và có ý nghĩa nghiệp vụ rõ ràng. […] Tên tốt: LabResultReady · Tên yếu: LabResultUpdated · Tên sai nghĩa: SendLabResult.»

> «Ontology truyền thống thường bắt đầu bằng danh từ: Patient, Appointment, Encounter, Task. ClinicAI vẫn cần các entity này, nhưng event-driven model bắt đầu bằng **động từ đã xảy ra**.» — *§3.2*

| Loại | Nguồn | Ví dụ | Vai trò |
|---|---|---|---|
| **Observed** | Cảm biến, thao tác, hệ thống nguồn | PatientArrived, DoorOpened, LabResultReceived | Bằng chứng trực tiếp về reality |
| **Domain** | Domain service xác nhận ý nghĩa nghiệp vụ | EncounterStarted, SpecimenAccepted | Sự thật có nghĩa trong ClinicAI |
| **Derived** | Rule, temporal engine hoặc AI suy ra | UnexplainedWaitRiskDetected, StaffOverloadDetected | Biến tín hiệu thành điều cần chú ý |
| **Decision** | Policy/human/AI có thẩm quyền | EscalationApproved, RoutingDecisionMade | Lưu dấu quyết định và lý do |
| **Outcome** | Người hoặc hệ thống thực hiện | PatientInformed, ReviewCompleted | Chứng minh vòng lặp đã đóng |

> «Một Derived Event phải ghi rõ mức độ chắc chắn. Nó không được giả dạng Observed Event.» — *§3.3*

Catalog §4 thêm loại thứ sáu: **Reliability** — «Khả năng quan sát/hoạt động của hệ thống thay đổi», ví dụ IntegrationUnavailable.

### Phân loại 17 loại event đang có trên prod

| Loại code | Số | Xếp vào | Ghi chú |
|---|---|---|---|
| `slot_hold.created/released` | 281 | *Không phải domain event* | Là giữ chỗ UI 10 phút (Luật 6.1 «tư vấn, không phải khoá»). Catalog §14: «UI analytics event có thể tồn tại ở telemetry riêng, không trộn vào domain event ledger.» |
| `appointment.created/rescheduled/checked_in/completed` | 69 | Domain | Tên snake_case theo thì quá khứ — đúng tinh thần, chỉ khác quy ước chữ. |
| `patient.created/phone_*` | 69 | Domain (CRUD+audit) | Đúng §7: master data chỉ cần audit. |
| `cskh.tuong_tac` / `_hoan_tac` | 22 | **Outcome** (TRA_KQ, XAC_NHAN_LICH) hoặc Observed (mốc quầy) | Gần PatientInformed nhất trong code. |
| `dispatch.checkin/checkout` | 2 | Observed | Vị trí, nguồn `staff`. |
| `thong_bao.*` | 2 | *Command/notification* | Catalog §14: «NotificationCreated nếu điều cần biết là communication request» → không phê duyệt. |
| `roster.*` | 4 | Resource | Đúng §12 Catalog (ShiftStarted…). |

Không có **Derived**, không có **Decision**, không có **Reliability** event nào. Đây là bằng chứng số cho [[gap-envelope|Khoảng cách 1]] và lý do [[tk-event-catalog-table|event_catalog]] cần cột `category` + `evidence_level`.

## Nối tới
- [[event-vs-record|Event khác record]]
- [[event-envelope|Event envelope chuẩn]]
- [[event-catalog|Event Catalog v1]]
- [[gap-envelope|Khoảng cách 1]]
- [[tk-event-catalog-table|event_catalog]]
- [[event-log-table|event_log]]

## Được dẫn từ
- [[event-vs-record|Event khác record]]
- [[event-catalog|Event Catalog v1]]
- [[audit-labels|audit_labels.EVENT_LABELS]]
- [[tuong-tac-cskh|tuong_tac_cskh]]
- [[tk-event-catalog-table|event_catalog]]
