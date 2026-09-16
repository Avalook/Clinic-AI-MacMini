---
title: "event_catalog — danh mục sự kiện là bảng: nhãn Việt, tên canonical, loại, evidence, privacy, stream rule"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "migration 202609xx_event_catalog · thay audit_labels.py dần"
tags: [clinicai, lop5-thiet-ke]
---

# event_catalog — danh mục sự kiện là bảng: nhãn Việt, tên canonical, loại, evidence, privacy, stream rule

> [!abstract] Đưa ~80 tên trong EVENT_LABELS vào DB; ghi_su_kien() từ chối event_type không có trong catalog; slot_hold về telemetry.

```sql
CREATE TABLE IF NOT EXISTS public.event_catalog (
    clinic_id       uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,  -- NULL-less: catalog theo tenant, seed cho mọi clinic
    event_type      text NOT NULL,                       -- 'appointment.created' (tên đang chạy, KHÔNG đổi)
    canonical       text,                                -- 'AppointmentConfirmed' (tên thesis, để đối chiếu/xuất)
    nhan            text NOT NULL,                       -- 'Tạo lịch hẹn' (từ audit_labels)
    category        text NOT NULL CHECK (category IN ('observed','domain','derived','decision','outcome','reliability','telemetry')),
    is_domain       boolean GENERATED ALWAYS AS (category <> 'telemetry') STORED,
    stream_rule     text NOT NULL DEFAULT 'by_aggregate',-- cách suy stream_id khi caller không đưa
    default_privacy text[] NOT NULL DEFAULT '{}',
    schema_version  integer NOT NULL DEFAULT 1,
    payload_schema  jsonb,                               -- JSON Schema tối thiểu; NULL = chưa khai (chấp nhận trong giai đoạn chuyển)
    producer        text,                                -- 'booking_service' | 'sql:move_visit_to_station' …
    expected_outcome text,                               -- event_type đóng vòng, nếu đây là Derived/Command-like
    fhir_hint       text,
    is_active       boolean NOT NULL DEFAULT true,
    PRIMARY KEY (clinic_id, event_type)
);
```

Seed từ `audit_labels.EVENT_LABELS` (CROSS JOIN mọi clinic, như `luat_cskh`). Phân loại ban đầu (từ [[5-loai-event|Năm loại event]]): `slot_hold.*` → `telemetry`; `appointment.*`, `patient.*`, `visit.*`, `clinical.*`, `lab_result.*`, `payment.*`, `pharmacy.*`, `work_item.*`, `roster.*`, `episode.*` → `domain`; `dispatch.checkin/checkout/moved` → `observed`; `cskh.tuong_tac[TRA_KQ]`, `clinical.released` → `outcome` (tách sau bằng payload); `dispatch.route_applied`, `booking.doctor_rule_saved`, `visit_gate_override` → `decision`; `thong_bao.*` → giữ `domain` nhưng `canonical='CommunicationRequested'`.

### Ràng buộc

- `ghi_su_kien()` từ chối `event_type` không có trong catalog hoặc `is_active = false` → lỗi rõ, không im lặng. Trong giai đoạn chuyển, 29 INSERT cũ vẫn chạy (không đi qua hàm) — CI ratchet đưa chúng về 0.
- Drift test hai chiều: mọi literal `'x.y'` trong `src/clinicai` có trong catalog; mọi dòng catalog `is_active` có ít nhất một producer hoặc được đánh dấu `reserved`.
- `v_audit_log` đọc `nhan` từ catalog thay vì dict Python → nhãn có thể sửa không deploy, và **phòng khám thứ hai có thể có nhãn khác**.

### Vì sao theo tenant

Catalog §1: «Event Catalog là nơi xác định […] nghĩa nghiệp vụ.» Nghĩa là của phòng khám (`luat_cskh.nhan` đã theo tenant). Seed chung, sửa riêng. Thesis Catalog §15 versioning: `schema_version` ở đây; đổi nghĩa = event_type mới, không đổi dòng cũ.

## Nối tới
- [[event-catalog|Event Catalog v1]]
- [[audit-labels|audit_labels.EVENT_LABELS]]
- [[5-loai-event|Năm loại event]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[governance-event|Security, privacy, governance ở cấp event]]
- [[fhir-mapping|Quan hệ với chuẩn y tế]]

## Được dẫn từ
- [[5-loai-event|Năm loại event]]
- [[governance-event|Security, privacy, governance ở cấp event]]
- [[event-catalog|Event Catalog v1]]
- [[fhir-mapping|Quan hệ với chuẩn y tế]]
- [[event-log-table|event_log]]
- [[audit-labels|audit_labels.EVENT_LABELS]]
- [[ci-guards|CI]]
- [[gap-envelope|Khoảng cách 1]]
- [[tk-nguyen-tac|Nguyên tắc thiết kế đích]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-governance|Governance ở cấp event]]
- [[phase-0-nen|Phase 0]]
- [[cau-hoi-mo|Câu hỏi mở]]
