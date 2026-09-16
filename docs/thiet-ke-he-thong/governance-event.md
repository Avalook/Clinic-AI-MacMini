---
title: "Security, privacy, governance ở cấp event — payload tối thiểu, privacy_tags, replay có audit"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §17 · Catalog §15–16"
tags: [clinicai, lop2-kien-truc]
---

# Security, privacy, governance ở cấp event — payload tối thiểu, privacy_tags, replay có audit

> [!abstract] Immutable không phải lý do lưu thừa dữ liệu cá nhân; 13 yêu cầu và những gì RLS + redaction đã phủ.

> «Event log làm audit mạnh hơn nhưng cũng tạo rủi ro tích lũy dữ liệu nhạy cảm.» — *§17*

13 yêu cầu: payload tối thiểu · tách reference khỏi content · field-level classification · role/purpose-based access · encryption · immutable audit cho read/export/action nhạy cảm · retention theo loại event · pseudonymization cho analytics · consent/purpose tags · event schema review · quyền replay bị giới hạn và ghi audit · không sensitive payload vào log kỹ thuật · model inference lưu model/rule version + input references.

> «"Immutable" không phải lý do để lưu thừa dữ liệu cá nhân.» — *§17*

Versioning (*Catalog §15*): additive giữ major; xoá/đổi nghĩa field → version mới; «Không đổi nghĩa của một event đã phát hành»; «Event history cũ không bị migrate chỉ để trông giống schema mới; dùng upcaster khi replay.»

Quy trình phê duyệt event mới (*Catalog §16*) — 10 câu, và **DoD cho một event** (*§17*) 12 ô: tên thì quá khứ · definition/non-definition · producer/authority · stream/subject/correlation/causation · payload schema có version · privacy classification · idempotency & ordering test · happy/duplicate/late/correction test · consumer liệt kê · monitoring có owner · example payload · ba bên phê duyệt.

### Đã có

- **Payload tối thiểu**: `event_log.payload` «cố ý chỉ mang ID» — relay làm giàu lúc gửi (`_lam_giau`). ✅
- **Không PII qua Telegram**: `notification_templates` docstring: «KHÔNG BAO GIỜ đưa số điện thoại / CCCD / địa chỉ vào tin» — có test. ✅
- **Access**: RLS `event_log` chỉ MANAGEMENT trong tenant (`20260717000001` + `20260730000004`). ✅
- **Log kỹ thuật**: `core/logging.py` redaction; `src/dashboard/lib/event-log-redaction.ts`. ✅
- **Retention**: SO-LUAT Phần 7: «Không xoá được, và đó là chủ ý […] chia bảng theo tháng rồi tách ra kho lạnh, không bao giờ xoá.» ✅ chính sách; chưa partition.
- **Model provenance**: `lab_result.triage_model/triage_reason/triage_classified_at` ✅.

### Chưa có

- `privacy_tags` / classification trên từng event.
- Replay: không có công cụ, nên không có audit replay.
- Schema review: `audit_labels.EVENT_LABELS` + `test_audit_labels_drift.py` là *một nửa* — nó bắt nhãn tiếng Việt, không bắt payload schema. [[tk-event-catalog-table|event_catalog]] đưa danh mục vào DB kèm `privacy_class`, `schema_version`; [[tk-governance|Governance ở cấp event]] phần còn lại.

## Nối tới
- [[tk-governance|Governance ở cấp event]]
- [[tk-event-catalog-table|event_catalog]]
- [[multi-tenant-rls|Multi-tenant thật]]
- [[audit-labels|audit_labels.EVENT_LABELS]]
- [[event-envelope|Event envelope chuẩn]]

## Được dẫn từ
- [[event-envelope|Event envelope chuẩn]]
- [[multi-tenant-rls|Multi-tenant thật]]
- [[ai-hien-co|AI đang có]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-governance|Governance ở cấp event]]
