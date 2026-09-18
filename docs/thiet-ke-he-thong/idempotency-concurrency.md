---
title: "Bất biến ép ở Postgres — idempotency_key, advisory lock, CAS, version, RPC"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "ADR-0003 · api/idempotency.py · 20260714000002 · 20260717000002"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# Bất biến ép ở Postgres — idempotency_key, advisory lock, CAS, version, RPC

> [!abstract] Bậc thang UNIQUE/CHECK → CAS → trigger+lock → RPC; đây là phần thesis §15.1/15.3 đã đạt và thiết kế đích chỉ mở rộng.

> «**Luật 6.2** — Mọi bất biến có kẽ hở tranh chấp phải ép ở Postgres, theo bậc thang: ràng buộc UNIQUE/CHECK → `UPDATE … WHERE status IN (…)` một câu → trigger + khoá tư vấn → hàm RPC khi cần nhiều câu lệnh nguyên khối. Không tự cài khoá trong Python.» — *SO-LUAT*

Đang chạy:

| Bất biến | Cơ chế | Ở đâu |
|---|---|---|
| Bấm hai lần ≠ hai bản ghi | `idempotency_key (key, endpoint, actor_id)` DB-backed, TTL, trả khoá khi 4xx | `api/idempotency.py`; 17 dòng prod |
| Ghế 2+1 mỗi bác sĩ mỗi khung | trigger `enforce_slot_capacity` + `pg_advisory_xact_lock(doctor, bucket, kind)` | `20260714000002` (per-clinic từ `20260803000001`) |
| Một khách một lịch sống mỗi mốc | `uq_appointment_patient_slot_live` | `20260805000007` |
| Số thứ tự ngày VN không trùng | RPC `check_in_appointment` SECURITY DEFINER + advisory lock theo ngày | `20260717000002` |
| Work item không bị ghi đè | `version` + `UPDATE … WHERE status=$cur AND version=$exp` → 409 | `work_item_service.issue()` |
| Một vị trí một lượt | `move_visit_to_station` `FOR UPDATE` | `20260804000003` |
| Một tuyến hiệu lực/lượt | `uq_visit_route_one_active` | `20260804000002` |
| Một thông báo mở/nguồn/vai | `uq_thong_bao_dang_mo` partial unique | `20260807000006` |
| Hai relay không gửi trùng | `pg_try_advisory_lock(hashtextextended(event_id))` | `notification_relay.py` |
| Bộ kiểm dưới tranh chấp | `kiem-duong-ghi.py`: 15 người đua 2 ghế → đúng 2 thắng, 0×500; trùng khách ×5 → 1 lịch | DANG-LAM §0 (staging) |

Ràng buộc kèm theo (ADR-0003): backend nối qua session mode; relay dùng session-level lock nên «KHÔNG được chuyển transaction-mode nếu chưa refactor relay».

### Nghĩa cho thiết kế

Thesis §15.1 «idempotency key = event_id + policy_id + action_type» và §13 Work Item «Cùng origin_event + policy_version + work_type + subject chỉ tạo một Work Item» → đúng bậc thang này: **UNIQUE index** trên `work_item (origin_event_id, policy_id, node_code, subject)` ([[tk-work-item-protocol|Work Item Protocol trên kernel]]), và `expectation (registered_by_event_id, expected_event_type)` ([[tk-expectation-timer|expectation + đồng hồ]]). Không cần Redis lock, không cần dedup store — Postgres đủ, như ADR-0005.

## Nối tới
- [[reliability|Reliability semantics]]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[workflow-kernel|Workflow kernel]]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]

## Được dẫn từ
- [[reliability|Reliability semantics]]
- [[appointment-visit-tuongtac|Lời hứa · Sự việc · Lần chạm]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
