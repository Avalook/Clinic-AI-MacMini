---
title: "Phase B — Ngoại lệ & thời gian (tuần 6–8): chờ vô định thành việc có chủ; rời cơ sở không rơi khỏi hệ"
lop: 6
lop_ten: Lộ trình & quyết định
tag_nguon: "Catalog §18 Phase B · tk-experience-state · tk-atc-ui · tk-reliability-playbook"
tags: [clinicai, lop6-lo-trinh]
---

# Phase B — Ngoại lệ & thời gian (tuần 6–8): chờ vô định thành việc có chủ; rời cơ sở không rơi khỏi hệ

> [!abstract] Ba experience state, coverage, ATC card đủ 9 trường, failure event; đo unexplained waiting minutes so baseline.

**Migration `202609xx_phase_b.sql`**: `experience_state` + `experience_config` · `tuong_tac_cskh.chu_de/hieu_luc_den` + hàm `co_coverage` · `patient.khong_lam_phien_den` · `follow_up_case` writer qua policy · `event_quarantine` · seed policy UNEXPLAINED_WAIT, CONTINUITY_ON_CHECKOUT, HANDOFF_UNCERTAINTY (đổi ACK_TIMEOUT thành experience có state) · `station_load_sample`.

**PR**:
1. `engine/trai_nghiem.py`: lifecycle + commands confirm/dismiss + auto resolve/expire; event `experience.*`.
2. Policy 3 state + `policy_case` cho từng nhánh Spec §7 (điều kiện kích hoạt **và** 4 điều kiện không kích hoạt).
3. ATC card 9 trường + cảnh báo có id/ack/why; `/display` bước tiếp theo.
4. `tin_nhan` + `ops_status` + failure event; freshness chip.
5. Attestation form «Đã giải thích cho khách» (chủ đề + nội dung tối thiểu) — **ô nhập duy nhất thêm mới** trong cả lộ trình.
6. Metric Phase B + rollup đồng hồ.

**Kịch bản bấm thử**: (1) Trưởng ca chuyển khách vào SA2, cấu hình ngưỡng 2′; (2) sau 2′ card đỏ «chưa được giải thích», việc GIAI_THICH_CHO đến CSKH; (3) CSKH ghi attestation chủ đề «chờ» → risk resolved, card xanh «đã báo lúc 10:05, hiệu lực 15′»; (4) qua 15′ chưa xong → risk mở lại (informed_wait hết hạn); (5) checkout khi còn kết quả chưa xem → `follow_up_case` + việc THEODOI-01 cho CSKH có hạn; (6) rút token Telegram trên staging → `/ops` báo degraded + DEAD, không ai phải mở Kuma.

**Cổng sang C** (Pilot §13.3–4): unexplained waiting minutes giảm ≥ 20% so baseline Phase 0 (hoặc: đo được và có xu hướng, vì baseline có thể là 0 nếu chưa ai chuyển phòng — nói thật trong báo cáo); false alarm (dismissed/detected) ≤ 30%; notification burden ≤ N/vai/ca thoả thuận; 0 privacy incident; nhân viên không quay lại Zalo cho việc «đã giải thích» (đếm attestation/ngày > 0).

## Nối tới
- [[lo-trinh-tong|Lộ trình]]
- [[phase-a-closed-loop|Phase A]]
- [[phase-c-intelligence|Phase C]]
- [[tk-experience-state|experience_state]]
- [[tk-atc-ui|Giao diện]]
- [[tk-reliability-playbook|Reliability playbook]]
- [[tk-metrics|Metric từ event stream]]
- [[experience-state|Experience State]]

## Được dẫn từ
- [[event-catalog|Event Catalog v1]]
- [[lo-trinh-tong|Lộ trình]]
- [[phase-a-closed-loop|Phase A]]
- [[phase-c-intelligence|Phase C]]
