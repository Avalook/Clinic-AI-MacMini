---
title: "Phase 0 — Nền (tuần 1–2): sổ sự kiện đáng tin trước mọi thứ"
lop: 6
lop_ten: Lộ trình & quyết định
tag_nguon: "tk-event-envelope-v2 · tk-event-catalog-table · tk-emit-function · tk-mot-so-cai"
tags: [clinicai, lop6-lo-trinh]
---

# Phase 0 — Nền (tuần 1–2): sổ sự kiện đáng tin trước mọi thứ

> [!abstract] Không tính năng nào người dùng thấy; kết thúc bằng timeline một lượt khám đọc được và baseline 2 tuần.

**Migration `202609xx_phase0_nen.sql`** (một file, idempotent): cột envelope v2 + trigger fill + backfill 449 dòng · `event_catalog` + seed từ `EVENT_LABELS` · `ghi_su_kien()` · trigger ledger cho `work_item_event`/`visit_gate_override`/`thong_bao.da_xu_ly` · `v_timeline_luot_kham` · `v_visit_state_tu_su_kien`. **Không** dựng `consumer_checkpoint` ở đợt này: giao thức con trỏ `seq > last_seq` đang bị chặn vì chưa an toàn (xem [[tk-event-envelope-v2|Envelope v2]]) — cần giao thức xác nhận theo từng event và test commit đảo thứ tự trước đã. Áp staging → chạy `kiem-vang.sh` + `kiem-duong-ghi.py` (6/6) → prod trong khung.

**PR** (mỗi cái ≤ 2 ngày):
1. `engine/su_kien.py` + đổi cụm **booking** (`booking_service`, `slot_hold_service`, `booking_override_service`) sang `su_kien.ghi` với `causation` xuyên chuỗi create → hold release → checked_in → spine. Ratchet INSERT 29 → ~20.
2. Cụm **cskh + dispatch** (`tuong_tac_cskh`, `thong_bao`, `phan_hoi_khach`, `dispatch_service`, hai hàm SQL). Ratchet → ~10.
3. Cụm **clinical + config + patient + payment + pharmacy**. Ratchet → 0. `audit_labels.py` đọc từ DB (giữ dict làm fallback test).
4. `v_audit_log` đọc `event_catalog.nhan`; `/audit-log` thêm filter `category`; `VungLamViecKhach` đọc `v_timeline_luot_kham`.
5. Metric Phase 0: `v_metric_coverage`, `v_metric_freshness`, `metric_daily` + đồng hồ rollup **chưa cần** (chạy tay cuối ngày bằng script trong 2 tuần baseline).

**Xoá**: `event_bus/`, RabbitMQ mode trong `worker.py`, service `rabbitmq` trong compose (ADR-0002).

**PR template** thêm 4 câu của [[decision-checklist|Decision checklist cho mọi feature]] (event nào · việc nào · ai sở hữu · vòng đóng ở đâu).

**Cổng sang A**: `correlation_id IS NOT NULL` ≥ 95% event 7 ngày gần nhất · INSERT trực tiếp = 0 · drift `v_visit_state_tu_su_kien` = 0 trên staging 7 ngày liên tục (chạy `kiem-duong-ghi` mỗi đêm) · `slot_hold.*` không còn trong timeline · baseline metric 14 ngày ghi ra file trong `docs/`.

**Rủi ro**: trigger fill làm chậm INSERT? Đo: `pg_advisory_xact_lock` + 1 SELECT max — ở 2.400 dòng/ngày không đo được (Luật 5.2 «cuối bảng»); vẫn đo p95 `/appointments` trước/sau trên staging bằng `tai.py` sẵn có.

## Nối tới
- [[lo-trinh-tong|Lộ trình]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[tk-event-catalog-table|event_catalog]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-mot-so-cai|Một sổ cái, nhiều bảng chuyên biệt]]
- [[tk-projections|Projection có kỷ luật]]
- [[decision-checklist|Decision checklist cho mọi feature]]
- [[phase-a-closed-loop|Phase A]]

## Được dẫn từ
- [[decision-checklist|Decision checklist cho mọi feature]]
- [[lo-trinh-tong|Lộ trình]]
- [[phase-a-closed-loop|Phase A]]
