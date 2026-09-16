---
title: "Phase C — Năng lực & trí tuệ (tuần 9+): overload thành event, Recommend có người duyệt, replay để học"
lop: 6
lop_ten: Lộ trình & quyết định
tag_nguon: "Catalog §18 Phase C · tk-ai-placement · tk-metrics · tk-modular-monolith"
tags: [clinicai, lop6-lo-trinh]
---

# Phase C — Năng lực & trí tuệ (tuần 9+): overload thành event, Recommend có người duyệt, replay để học

> [!abstract] Chỉ bắt đầu khi B có số; mọi thứ ở đây tắt được bằng UPDATE; kết thúc = 12 bằng chứng event-driven đều xanh.

**Mảnh**: `StaffOverloadDetected`/`NodeCongestionDetected`/`CapacityRestored` từ `station_load_sample` (derived, theo **phòng**) · policy `RECOMMEND_REDISTRIBUTION` (authority recommend, shadow 2 tuần) · lab triage phát derived event có confidence · replay review script + trang «xem lại ca» đọc timeline theo ca trực · metric đủ 4 nhóm · dời nốt `services/` vào `modules/` + import-linter + manifest checker · `event_log` partition ngưỡng.

**Cổng kết thúc pilot** (Pilot §16 Go/Iterate/No-go): observability + adoption gate đạt · ≥ 1 outcome cải thiện đáng tin · không vi phạm guardrail · «phần lớn capability có thể reuse cho journey tiếp theo» — kiểm bằng cách **seed tenant giả thứ hai** với catalog/policy/threshold khác và chạy `policy_case` của nó xanh mà không sửa code (v3 §2.9 «chứng minh ontology có khả năng cấu hình»).

**Nếu C không tăng giá trị so với B** (v2 §3.10): tắt `authority_level` về `observe`, giữ B — «nên bỏ bớt AI chứ không nhất thiết bỏ ClinicAI».

**Sau C** (ngoài phạm vi thiết kế này, ghi để không quên): Zalo OA channel (D010) · LIS adapter theo khuôn PosPort · ký số EMR + CCCD (TT13/2025, hạn 31/12/2026 — Tổng-Quan §14.1) · cơ sở thứ hai Hào Nam khi có mô tả vận hành (`kien-truc-nhieu-phong-kham.md` §5 «Chưa nên làm: đa cơ sở đầy đủ»).

## Nối tới
- [[lo-trinh-tong|Lộ trình]]
- [[phase-b-exceptions|Phase B]]
- [[tk-ai-placement|AI đúng chỗ]]
- [[tk-metrics|Metric từ event stream]]
- [[tk-modular-monolith|Thi hành ADR-0001]]
- [[chung-minh-event-driven|12 bằng chứng 'event-driven thật']]
- [[macro-v3|Thesis v3]]
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]

## Được dẫn từ
- [[event-catalog|Event Catalog v1]]
- [[gap-ai|Khoảng cách 14]]
- [[tk-ai-placement|AI đúng chỗ]]
- [[lo-trinh-tong|Lộ trình]]
- [[phase-b-exceptions|Phase B]]
