---
title: "Kill criteria, proof plan và baseline Excel + Zalo"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v2 §3.3 · §3.9 · §3.10"
tags: [clinicai, lop1-hien-phap]
---

# Kill criteria, proof plan và baseline Excel + Zalo

> [!abstract] Thesis là giả thuyết có điều kiện bác bỏ; pilot phải so với một baseline đủ mạnh chứ không so với hỗn loạn.

> «Bài kiểm tra bắt buộc: Pilot phải so ClinicAI với một baseline đủ mạnh — ví dụ Excel + quy tắc vận hành được cải tiến — chứ không so với hiện trạng hỗn loạn. Nếu một giải pháp đơn giản tạo gần như toàn bộ giá trị với chi phí thấp hơn, không nên xây một hệ thống phức tạp.» — *Thesis v2 §3.3*

Bảy đặc điểm khiến thủ công không bền (*v2 §3.3*): nhiều state đổi đồng thời · nhiều actor phụ thuộc · ngoại lệ thường xuyên · tốc độ phản ứng ảnh hưởng outcome · không thấy toàn cảnh từ bảng tĩnh · chi phí "hỏi nhau" tăng theo quy mô · lịch sử tạo năng lực dự báo.

Proof plan (*v2 §3.9*) — 7 giả thuyết, mỗi cái có tín hiệu ủng hộ/bác bỏ. Hai dòng đáng nhớ nhất cho kỹ thuật:

| Giả thuyết | Ủng hộ | Bác bỏ |
|---|---|---|
| Reality có thể quan sát | State đủ mới với ít thao tác thêm | Nhiều state sai hoặc phải nhập kép |
| Coordination tốt hơn | Giảm unowned work, handoff failure | **Chỉ chuyển việc sang notification** |

Kill criteria (*v2 §3.10*), trích những điều chạm thẳng vào thiết kế:

> «không quan sát được phần lớn encounter mà không tăng đáng kể thao tác nhập liệu; · event đến quá chậm hoặc không đủ tin cậy để điều phối; · […] · AI không tạo thêm giá trị đáng kể so với rule và dashboard; · việc tăng visibility làm tăng giám sát, áp lực hoặc hành vi đối phó nhiều hơn chất lượng chăm sóc.»

> «Nếu thất bại tập trung ở AI nhưng coordination loop vẫn tạo giá trị, nên bỏ bớt AI chứ không nhất thiết bỏ ClinicAI. Nếu thất bại ở việc thu nhận reality hoặc adoption, core thesis cần được xem xét lại.» — *v2 §3.10*

### Hệ quả cho thiết kế

1. Mọi thứ trong [[lo-trinh-tong|Lộ trình]] phải **đo được trước/sau** — vì thế [[tk-metrics|Metric từ event stream]] không phải việc cuối mà là việc đi kèm từng phase.
2. Thiết kế phải chịu được kết luận "bỏ AI": mọi mảnh trong [[tk-policy-engine|policy + policy_case]] và [[tk-experience-state|experience_state]] chạy bằng **rule** trước; AI là lớp cắm thêm.
3. "Chỉ chuyển việc sang notification" là chế độ thất bại **đang xảy ra** trên code (relay = sent = done) — [[gap-communication|Khoảng cách 8]] phải đóng trước khi đo bất cứ gì.

## Nối tới
- [[lo-trinh-tong|Lộ trình]]
- [[tk-metrics|Metric từ event stream]]
- [[tk-policy-engine|policy + policy_case]]
- [[tk-experience-state|experience_state]]
- [[gap-communication|Khoảng cách 8]]
- [[7-tieu-chi-event-source|Bảy tiêu chí cho mọi nguồn event]]

## Được dẫn từ
- [[7-tieu-chi-event-source|Bảy tiêu chí cho mọi nguồn event]]
- [[gap-metrics|Khoảng cách 13]]
- [[tk-metrics|Metric từ event stream]]
- [[lo-trinh-tong|Lộ trình]]
- [[phase-c-intelligence|Phase C]]
