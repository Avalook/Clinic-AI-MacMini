---
title: "Bốn nhóm chỉ số — visibility · coordination · humane · business"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §9 · Care Model §25"
tags: [clinicai, lop1-hien-phap]
---

# Bốn nhóm chỉ số — visibility · coordination · humane · business

> [!abstract] Danh sách metric chính thức; hôm nay code tính được 0 trong 5 metric coordination.

Nguyên văn (*Thesis v1 §9*):

**9.1 Operational visibility** — Observable Encounter Rate · Unknown State Duration · Event Coverage · State Freshness.

**9.2 Coordination quality** — Unowned Work Time · Acknowledgement Time · Handoff Failure Rate · Escalation Resolution Time · Coordination Debt («tổng số work item cần phối hợp nhưng đang thiếu owner, context hoặc next action»).

**9.3 Humane operations** — Unexplained Waiting Time · Patient Forgotten Risk · Communication Debt · Staff Overload Minutes · Prevented Complaints / Early Interventions.

**9.4 Business outcomes** — thời gian hoàn tất encounter · throughput · no-show/conversion · utilization · chi phí/encounter · retention, follow-up completion · lỗi, rework, khiếu nại.

> «Business metrics là kết quả cần thiết, nhưng không được tối ưu tách rời khỏi patient safety, staff wellbeing và care quality.» — *v1 §9.4*

Care Model §25 nói các metric này «sinh ra tự nhiên từ event stream» và thêm nhóm **System quality**: ingestion latency · projection lag · duplicate rate · unmatched event rate · late/out-of-order rate · failed side-effect rate · replay success · % warning có provenance.

### Tính được gì từ dữ liệu hôm nay

| Metric | Tính được? | Từ đâu |
|---|---|---|
| Thời gian chờ ở bước hiện tại, tổng thời gian trong phòng khám | ✅ | `dispatch_service._OVERVIEW_SQL` (`wait_minutes`, `total_minutes`) |
| Thời gian khám (consultation duration) | ✅ | `v_consultation_duration`, `v_consultation_duration_stats` |
| No-show, huỷ theo lý do | ✅ | `appointment.status`, `ly_do_huy_ma` (5 mã) |
| Giây phản hồi khi Trưởng ca gọi bộ phận | ✅ | `thong_bao.da_xu_ly` trả `giay_phan_hoi` |
| Acknowledgement Time, Unowned Work Time | ❌ | không có trạng thái ack, không có owner bắt buộc |
| Unexplained Waiting Time | ❌ | không có communication coverage |
| Event Coverage, State Freshness | ❌ | Hai cột cùng `DEFAULT now()` và đường ghi truyền `now()`, nên `recorded_at = occurred_at` là tất yếu → **độ trễ thật chưa từng được đo**, không phải bằng 0 |

Thiết kế: [[tk-metrics|Metric từ event stream]] định nghĩa từng metric bằng SQL trên [[tk-event-envelope-v2|Envelope v2]] và ghi rõ metric nào chỉ có nghĩa sau phase nào.

## Nối tới
- [[tk-metrics|Metric từ event stream]]
- [[gap-metrics|Khoảng cách 13]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[humane-ops|Design for Humane Operations]]

## Được dẫn từ
- [[thong-bao|thong_bao]]
- [[gap-work-item|Khoảng cách 3]]
- [[gap-metrics|Khoảng cách 13]]
- [[tk-metrics|Metric từ event stream]]
