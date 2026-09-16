---
title: "Event envelope chuẩn — 17 trường, mỗi trường một vai"
lop: 2
lop_ten: Kiến trúc hướng sự kiện
tag_nguon: "Care Model §5 · Catalog §3"
tags: [clinicai, lop2-kien-truc]
---

# Event envelope chuẩn — 17 trường, mỗi trường một vai

> [!abstract] Bao thư bắt buộc trước khi có hàng trăm loại event; đối chiếu từng trường với 14 cột event_log hiện tại.

Nguyên văn (*Care Model §5*):

```json
{
  "event_id": "evt_01...",           "event_type": "LabResultReady",
  "schema_version": 1,
  "occurred_at": "2026-09-03T10:18:42+07:00",
  "recorded_at": "2026-09-03T10:18:44+07:00",
  "source":  {"type": "LIS", "id": "lis_main"},
  "actor":   {"type": "system", "id": "lis_main"},
  "subject": {"type": "lab_result", "id": "lr_2841"},
  "patient_id": "pat_...", "episode_id": "epi_...", "encounter_id": "enc_...",
  "correlation_id": "cor_...", "causation_id": "evt_...",
  "stream_id": "enc_enc_...", "stream_version": 27,
  "evidence_level": "observed", "confidence": 1.0,
  "privacy_tags": ["clinical", "sensitive"],
  "payload": {}
}
```

> «occurred_at: lúc reality xảy ra · recorded_at: lúc ClinicAI biết · correlation_id: nối toàn bộ một vòng nghiệp vụ · causation_id: event/command nào gây ra event này · stream_version: bảo vệ thứ tự và optimistic concurrency · evidence_level: observed, inferred hoặc self-reported · confidence: bắt buộc với suy luận · schema_version: cho phép nâng cấp event an toàn · privacy_tags: giúp áp policy truy cập, retention và export.» — *§5*

Catalog §3 nói bắt buộc với mọi event: event_id/type/schema_version · occurred/recorded · source/actor/subject · correlation/causation khi có · stream_id/version · evidence_level · privacy classification · payload tối thiểu.

### Đối chiếu `event_log` prod (14 cột, đo 05/09/2026)

| Trường thesis | Cột hiện có | Dùng thật? |
|---|---|---|
| event_id, event_type | `event_id`, `event_type` | ✅ |
| schema_version | `event_version` | 1 giá trị duy nhất trên 449 dòng |
| occurred_at, recorded_at | `occurred_at`, `recorded_at` | có cả hai, nhưng **bằng nhau ở 100% dòng** vì cùng `DEFAULT now()` và đường ghi truyền `now()` — chưa ai truyền mốc thật (max chênh 0s) → chưa bao giờ ghi trễ/ghi bù |
| source | `source` (text: `api:booking`, `cskh.customers`…) | ✅ nhưng là chuỗi tự do, 12 giá trị |
| actor | `metadata.actor_auth_user_id / clinic_staff_id / clinic_role` (JSON) | 424/449 có `clinic_staff_id` — nhưng chìm trong JSON, «không truy vấn hay ràng buộc được» (DANG-LAM §4, PR #8) |
| subject | `aggregate_type` + `aggregate_id` | ✅ tương đương |
| patient_id / episode_id / encounter_id | — | ❌ chỉ suy được qua join `aggregate_id` |
| correlation_id, causation_id | có cột | **0/449** từng khác NULL |
| stream_id, stream_version | — | ❌ |
| evidence_level, confidence | — | ❌ |
| privacy_tags | — | ❌ (có `event-log-redaction.ts` phía dashboard, không ở ledger) |
| payload | `payload` | ✅ «cố ý chỉ mang ID» (`notification_relay._lam_giau` docstring) — đúng §17 data minimization |

Kết luận: **9/17 có chỗ, 5/17 có cột nhưng chưa dòng nào điền tại thời điểm đo, 6/17 thiếu hẳn.** Migration cộng thêm là đủ — [[tk-event-envelope-v2|Envelope v2]].

## Nối tới
- [[event-log-table|event_log]]
- [[gap-envelope|Khoảng cách 1]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[stream-boundary|Năm stream]]
- [[governance-event|Security, privacy, governance ở cấp event]]

## Được dẫn từ
- [[5-loai-event|Năm loại event]]
- [[stream-boundary|Năm stream]]
- [[governance-event|Security, privacy, governance ở cấp event]]
- [[event-log-table|event_log]]
- [[gap-envelope|Khoảng cách 1]]
- [[tk-event-envelope-v2|Envelope v2]]
