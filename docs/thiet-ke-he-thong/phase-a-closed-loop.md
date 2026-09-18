---
title: "Phase A — Vòng khép kín (tuần 3–5): việc có chủ, có nhận, có hạn, có leo thang"
lop: 6
lop_ten: Lộ trình & quyết định
tag_nguon: "Catalog §18 Phase A · tk-work-item-protocol · tk-expectation-timer · tk-policy-engine · tk-communication-delivery"
tags: [clinicai, lop6-lo-trinh]
---

# Phase A — Vòng khép kín (tuần 3–5): việc có chủ, có nhận, có hạn, có leo thang

> [!abstract] Kết thúc khi WorkAssigned ≠ WorkAcknowledged tồn tại thật trong dữ liệu và ack timeout tự leo thang mà không ai mở màn.

**Migration `202609xx_phase_a.sql`**: cột/trạng thái Work Item Protocol (`work_item_open_needs_owner NOT VALID`) · `expectation` + trigger MET · `policy` + `policy_case` + seed 2 policy (SPAWN_SPINE_ON_CHECKIN, ACK_TIMEOUT_ESCALATE) · `notification_delivery` + `notification_route` (seed 1 dòng Telegram nhóm) · version/effective_from cho 6 bảng luật · SLA mặc định vào `node_definition.config` cho 41 node (từ Notion §13 ưu tiên P0 → ack 5′/complete 30′, P1 → 10′/60′, P2 → 30′/240′ — **con số để quản lý sửa**, không phải hằng).

**PR**:
1. `engine/viec.py`: 8 lệnh, completion contract, `uq_work_item_origin`; API `commands/{assign|claim|acknowledge|block|resume|reassign|escalate|reject_completion}`; `list_worklist` thêm trường. Test transition thuần + SQL owner.
2. `engine/dong_ho.py` trong `worker.py`: FIRED loop + đăng ký expectation từ `viec.assign()` (ack/complete) và từ `move_visit_to_station` (wait_threshold — chưa dùng cho experience, chỉ ghi event). Test idempotent.
3. `engine/luat.py`: evaluator thuần + runner đọc checkpoint; 2 policy; `policy_case` chạy trong pytest (`test_policy_cases.py` load từ seed).
4. `engine/tin_nhan.py`: relay đọc `notification_delivery`; DEAD; `notification.failed`. Bỏ `event_published` khỏi relay.
5. Giao diện: `/tasks` nút **Nhận việc** + «Vì sao tôi nhận»; `/work-items` tab overdue/unclaimed; `thong_bao` mang `work_item_id`; `work-item-status.ts` thêm từ vựng.
6. **CSKH**: policy thứ 3 `NHAC_TAI_KHAM_THANH_VIEC` — mỗi `nhac_tai_kham CHO_GOI` → work item THEODOI-03 owner queue CSKH, completion `required_event cskh.tuong_tac[NHAC_HEN|XAC_NHAN_LICH]`; expectation thay `sinh_viec` lúc mở màn. Đây là mảnh cho người dùng đang có (5 CSKH) thấy khác biệt ngay: việc **xuất hiện dù không ai mở màn**, và Trưởng ca thấy ai chưa nhận.

**Kịch bản bấm thử (Luật 12.4)**: (1) tạo nhắc tái khám cho ngày mai → sáng mai việc có trong `/tasks` CSKH với hạn; (2) CSKH A bấm Nhận → B thấy «A đã nhận»; (3) không ai nhận 5′ (giả lập bằng cấu hình 1′) → Trưởng ca có thông báo + việc ESCALATED; (4) A ghi «Đã gọi nhắc» → việc tự COMPLETED, timeline khách có 5 dòng đúng thứ tự, không dòng nào trùng khi bấm hai lần.

**Cổng sang B** (Pilot §13.2): ≥ 80% ack trong SLA · ≥ 90% có owner · ≥ 85% completion có evidence (`required_event`/`attestation`) · không tăng thao tác tuyến đầu (đếm click qua telemetry `slot_hold`-style riêng) · `VALIDATE CONSTRAINT work_item_open_needs_owner` chạy được.

## Nối tới
- [[lo-trinh-tong|Lộ trình]]
- [[phase-0-nen|Phase 0]]
- [[phase-b-exceptions|Phase B]]
- [[tk-work-item-protocol|Work Item Protocol trên kernel]]
- [[tk-expectation-timer|expectation + đồng hồ]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-communication-delivery|notification_delivery]]
- [[nhac-tai-kham|nhac_tai_kham + hen_goi_lai + follow_up_case]]
- [[gap-wedge-mismatch|Khoảng cách 15]]

## Được dẫn từ
- [[event-catalog|Event Catalog v1]]
- [[gap-wedge-mismatch|Khoảng cách 15]]
- [[lo-trinh-tong|Lộ trình]]
- [[phase-0-nen|Phase 0]]
- [[phase-b-exceptions|Phase B]]
