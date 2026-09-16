---
title: "Khoảng cách 13 — Metric: đo được flow, không đo được coordination hay experience"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "metrics-thesis ↔ reports_service / v_consultation_duration"
trang_thai: Chưa có
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 13 — Metric: đo được flow, không đo được coordination hay experience

> [!abstract] Không có dữ liệu ack/owner/coverage thì 0/5 metric coordination và 0/5 metric humane tính được.

Từ [[metrics-thesis|Bốn nhóm chỉ số]]: tính được wait/total minutes, consultation duration, no-show/huỷ theo lý do, giây phản hồi thông báo. Không tính được: Unowned Work Time · Acknowledgement Time · Handoff Failure Rate · Escalation Resolution Time · Coordination Debt · Unexplained Waiting Time · Patient Forgotten Risk · Communication Debt · Staff Overload Minutes · Event Coverage · State Freshness.

Vì sao quan trọng ngay bây giờ: Pilot §13 khoá success criteria **sau baseline**; v2 §3.9 proof plan cần «giảm unowned work, handoff failure». Không có metric = không có baseline = không có kết luận go/no-go. Và Luật 7.2/5.3 «đo trước khi tối ưu» là luật của chính repo.

Thêm: `reports_service` gộp 8 lượt PostgREST thành 1 GROUP BY (Luật 5.1 ✓) — hình thức đúng, nội dung là báo cáo kinh doanh (lịch, doanh thu), không phải vận hành.

Đóng bằng: [[tk-metrics|Metric từ event stream]] — mỗi metric = một view SQL trên `event_log` (sau [[tk-event-envelope-v2|Envelope v2]]) hoặc trên `work_item`/`experience_state`; bảng `metric_daily` rollup; và nêu rõ metric nào chỉ có nghĩa sau phase nào (Acknowledgement Time cần Phase A; Unexplained Waiting cần Phase B).

## Nối tới
- [[metrics-thesis|Bốn nhóm chỉ số]]
- [[tk-metrics|Metric từ event stream]]
- [[tk-event-envelope-v2|Envelope v2]]
- [[kill-criteria|Kill criteria, proof plan và baseline Excel + Zalo]]
- [[pilot-scope|Partner Pilot Proposal]]

## Được dẫn từ
- [[10-principles|10 nguyên tắc sản phẩm]]
- [[metrics-thesis|Bốn nhóm chỉ số]]
- [[15-invariant|15 bất biến cấp 'hiến pháp']]
- [[tk-metrics|Metric từ event stream]]
