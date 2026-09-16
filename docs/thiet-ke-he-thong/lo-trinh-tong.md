---
title: "Lộ trình — nền trước, ownership sau, ngoại lệ rồi mới thông minh; mỗi phase một cổng đo"
lop: 6
lop_ten: Lộ trình & quyết định
tag_nguon: "Thesis v1 §11.1 · Catalog §18 · TAM-NHIN · Pilot §8"
tags: [clinicai, lop6-lo-trinh]
---

# Lộ trình — nền trước, ownership sau, ngoại lệ rồi mới thông minh; mỗi phase một cổng đo

> [!abstract] Phase 0 (2 tuần) → A (3 tuần) → B (3 tuần) → C (sau khi B đo được); tổng ≈ 8–10 tuần khớp Pilot Proposal; không phase nào cần hạ tầng mới.

Thứ tự lấy từ ba nguồn cùng nói một điều: v1 §11.1 («1 Nhìn thấy reality · 2 Tạo ownership · 3 Situational awareness · 4 Đóng communication loop · 5 Intelligence · 6 Tự động hoá có kiểm soát · 7 Học xuyên cơ sở»), Catalog §18 (Phase A closed-loop core → B exceptions & time → C capacity & intelligence), TAM-NHIN («lv4 chỉ đọc được state mà lv3 đã bắt đầy đủ và đáng tin»).

| Phase | Tuần | Mảnh | Cổng để sang phase sau (đo, không ước) |
|---|---|---|---|
| **0 — Nền** | 1–2 | envelope v2 · catalog · `ghi_su_kien` · một sổ cái · timeline view · baseline metric | `correlation_id` ≥ 95% event mới; INSERT trực tiếp = 0; `v_visit_state_tu_su_kien` drift = 0 trên staging 7 ngày; baseline 2 tuần đã ghi |
| **A — Vòng khép kín** | 3–5 | Work Item Protocol · expectation + đồng hồ · policy engine + 2 policy (spawn, ack-escalate) · notification_delivery · My Work/Team Queue có ack | ≥ 80% work item ack trong SLA; ≥ 90% có owner (Pilot §13.2); duplicate event → 0 việc trùng; ack timeout → escalation trong ≤ 60s (đo trên staging) |
| **B — Ngoại lệ & thời gian** | 6–8 | experience_state (3 state) · coverage · wait_threshold thành event · ContinuityRisk + follow_up_case · ATC card đủ 9 trường · failure event · freshness | false alarm ≤ ngưỡng thoả thuận; unexplained waiting minutes đo được và giảm so baseline; 0 privacy incident |
| **C — Năng lực & trí tuệ** | 9–10+ | overload event · metric đầy đủ · Recommend redistribution (shadow) · replay review · modules/ dời xong | Recommend precision > rule; Trưởng ca dùng «Vì sao» (Pilot §2 câu 2) |

Mỗi phase: **1 migration idempotent** (áp hai lần trong CI) → **2–4 PR** (nhánh ≤ 2 ngày, Luật 4.2) → **1 SQL test + 1 pytest thử ngược** ([[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]) → staging tự động → prod bấm 1h–4h → **kiểm hậu-deploy chỉ đọc** (DANG-LAM). ADR-0014/15/16 viết cùng migration của phase tương ứng.

Ba luật giữ trong suốt lộ trình:
1. **Không thêm ô nhập** cho tuyến đầu ở Phase 0–A (v2 §3.4). Chỉ Phase B thêm một form attestation ngắn.
2. **Baseline trước policy** (v2 §3.3): Phase 0 đo 2 tuần *trước khi* Phase A bật policy nào.
3. **Kill switch bằng dữ liệu**: `policy.is_active`, `authority_level` — tắt một luật là một UPDATE, không rollback deploy.

Về wedge ([[gap-wedge-mismatch|Khoảng cách 15]]): lộ trình **không chọn hộ**. Phase A áp Protocol lên node CSKH (`THEODOI-*`, nhắc tái khám) *và* node in-visit (`LUOTKHAM-*`) cùng lúc vì cùng bảng; policy nào bật trước là quyết định trong [[cau-hoi-mo|Câu hỏi mở]].

Nhân sự: 1 dev + AI. Ước công theo phase (không phải cam kết): Phase 0 ≈ 6–8 ngày làm việc, A ≈ 10–12, B ≈ 10–12, C mở. Song song vẫn phải trả nợ lv3 (42 route) — mỗi phase kèm 3–5 route dời về backend theo ratchet.

## Nối tới
- [[phase-0-nen|Phase 0]]
- [[phase-a-closed-loop|Phase A]]
- [[phase-b-exceptions|Phase B]]
- [[phase-c-intelligence|Phase C]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[cau-hoi-mo|Câu hỏi mở]]
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[gap-wedge-mismatch|Khoảng cách 15]]

## Được dẫn từ
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[macro-v3|Thesis v3]]
- [[pilot-scope|Partner Pilot Proposal]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]
- [[adr-so-luat|13 ADR + Sổ luật]]
- [[phase-0-nen|Phase 0]]
- [[phase-a-closed-loop|Phase A]]
- [[phase-b-exceptions|Phase B]]
- [[phase-c-intelligence|Phase C]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[cau-hoi-mo|Câu hỏi mở]]
