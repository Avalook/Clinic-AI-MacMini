---
title: "Governance ở cấp event — privacy_tags, RLS cho bảng mới, partition theo tháng, replay có audit"
lop: 5
lop_ten: Thiết kế đích
tag_nguon: "Care Model §17 · ADR-0009 · SO-LUAT 7/8"
tags: [clinicai, lop5-thiet-ke]
---

# Governance ở cấp event — privacy_tags, RLS cho bảng mới, partition theo tháng, replay có audit

> [!abstract] Mọi bảng mới đi đúng khuôn tenant; event_log chia tháng khi > 1 triệu dòng; không PII trong tin, không PII trong log.

- **Khuôn tenant** (ADR-0009, GIAI-THICH-CODE §9.7): `event_catalog`, `policy`, `policy_case`, `expectation`, `experience_state`, `notification_delivery`, `notification_route`, `event_quarantine`, `metric_daily`, `station_load_sample` — tất cả `clinic_id NOT NULL` + FK + index dẫn đầu + policy `%_select_own_clinic` (hoặc RLS bật 0 policy cho bảng chỉ-backend: `consumer_checkpoint`, `event_quarantine`, `notification_delivery`). Test `multi_tenant_foundation.sql` đếm 69 → 79; ghi lý do đổi số trong comment test (luật của file đó).
- **`privacy_tags`** mặc định từ catalog: `clinical` cho `clinical.*`/`lab_result.*`, `financial` cho `payment.*`, `contact` cho `cskh.*`, `telemetry` cho `slot_hold.*`. `v_audit_log` cho vai vận hành **loại** `clinical` (Luật 8.2 «trong vết chỉ có mã số»); MANAGEMENT xem đủ như hiện nay.
- **Payload tối thiểu** giữ nguyên nguyên tắc «chỉ ID» (relay làm giàu lúc gửi). Catalog `payload_schema` từ chối field tên `phone*`, `national_id*`, `address*` — test.
- **Retention**: SO-LUAT 7: không xoá. Khi `event_log` > 1 triệu dòng (~3 năm ở 2.400/ngày): `PARTITION BY RANGE (occurred_at)` theo tháng qua bảng mới + view gộp — ghi là **ngưỡng**, không làm trước.
- **Replay**: chỉ MANAGEMENT, script ghi `projection.rebuilt` với `actor_staff_id`; log kỹ thuật không chứa payload (redaction hiện có).
- **Consent** (Catalog §17 privacy classification): `clinical_data_consent` đã có bảng + trigger; event `clinical_data_consent.granted/revoked` đã có nhãn — policy `notify patient` kiểm consent trước khi tạo delivery channel `zalo_oa`.
- **Không PII qua Telegram** — test hiện có giữ; mở rộng cho mọi `channel` trong `notification_delivery` (render trước khi ghi `payload_rendered`? Không — không lưu bản render, chỉ lưu `provider_message_id`).
- **Model provenance**: `policy_id/policy_version` trên event; với LLM: `rule_or_model = 'claude-haiku-4-5@prompt-v3'`, không lưu prompt chứa dữ liệu thô (§17).

## Nối tới
- [[governance-event|Security, privacy, governance ở cấp event]]
- [[multi-tenant-rls|Multi-tenant thật]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tk-communication-delivery|notification_delivery]]
- [[adr-so-luat|13 ADR + Sổ luật]]

## Được dẫn từ
- [[governance-event|Security, privacy, governance ở cấp event]]
- [[multi-tenant-rls|Multi-tenant thật]]
