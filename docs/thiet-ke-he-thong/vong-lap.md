---
title: "Vòng lặp Reality → Event → State → Interpretation → Decision → Action"
lop: 1
lop_ten: Hiến pháp sản phẩm
tag_nguon: "Thesis v1 §5 · Care Model §1"
tags: [clinicai, lop1-hien-phap]
---

# Vòng lặp Reality → Event → State → Interpretation → Decision → Action

> [!abstract] Mô hình vận hành cốt lõi; Care Model v1 đảo lại thứ tự nhân quả so với cách code đang làm.

Thesis v1 §5 vẽ vòng lặp khép kín:

> «Reality → Event → State → Interpretation → Decision → Action → New Reality. AI nằm chủ yếu ở hai khâu Interpretation và Decision. AI không được rải khắp sản phẩm chỉ để tạo cảm giác "có AI".» — *Thesis v1 §1*

> «Một event chỉ có giá trị vận hành khi nó làm thay đổi nhận thức hoặc hành động của hệ thống.» — *Thesis v1 §5*

Care Model v1 §1 nói vì sao phải **viết lại theo event-first** — và đây là câu quan trọng nhất để soi code:

> «Bản Care Delivery Model trước […] về bản chất vẫn là mô hình trạng thái có thêm Event. Nó khiến người đọc có thể hiểu rằng: (1) UI hoặc workflow cập nhật một trạng thái; (2) hệ thống lưu trạng thái đó; (3) sau đó phát một event để các module khác biết. **Đó là "CRUD có message", chưa phải ClinicAI event-driven theo nghĩa mạnh.**» — *Care Model §1*

Thứ tự nhân quả mới, 7 bước:

> «(1) Một sự thật xảy ra […]; (2) ClinicAI ghi nhận sự thật đó dưới dạng event bất biến; (3) các projection diễn giải event để tạo ra trạng thái hiện tại; (4) policy và process manager quyết định phản ứng; (5) hệ thống phát command hoặc tạo Work Item; (6) hành động ngoài đời tạo ra outcome event mới; (7) **vòng lặp chỉ đóng khi outcome được quan sát.**» — *Care Model §1*

Và bài kiểm quyết định:

> «Nếu xóa tất cả dashboard và bảng trạng thái, ClinicAI phải có khả năng dựng lại chúng từ event history. Nếu không làm được, event chưa phải là nền tảng của hệ thống.» — *Care Model §1*

### Code hôm nay đứng ở bước nào

Code hiện tại làm đúng **(1)→(2)** ở mức "ghi vết trong cùng transaction" (ví dụ `episode_service.py:105`, `tuong_tac_cskh_service.py:249`), nhưng theo chiều **state trước, event sau** — đúng cái "CRUD có message" mà §1 gọi tên ([[gap-crud-roi-log|Khoảng cách 2]]). Bước (3) projection có thật ở [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]] và `visit.current_node_code`, nhưng dựng từ **bảng trạng thái**, không từ event. Bước (4)–(7) chưa có: không policy engine, không process manager, không outcome event đóng vòng ([[gap-process-manager|Khoảng cách 7]], [[gap-timer|Khoảng cách 4]]).

Thiết kế đích không đòi viết lại: nó đòi **đảo chỗ ngồi** — mọi thay đổi trạng thái đi qua một cửa ghi sự kiện ([[tk-emit-function|ghi_su_kien()]]), rồi projection/policy đọc từ đó ([[tk-policy-engine|policy + policy_case]], [[tk-projections|Projection có kỷ luật]]).

## Nối tới
- [[north-star|North Star]]
- [[event-first-dao-nhan-qua|Event-first]]
- [[gap-crud-roi-log|Khoảng cách 2]]
- [[gap-process-manager|Khoảng cách 7]]
- [[gap-timer|Khoảng cách 4]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[tk-emit-function|ghi_su_kien()]]
- [[tk-policy-engine|policy + policy_case]]
- [[3-muc-quyen-ai|Ba mức quyền hành động]]
- [[tk-projections|Projection có kỷ luật]]

## Được dẫn từ
- [[north-star|North Star]]
- [[3-muc-quyen-ai|Ba mức quyền hành động]]
- [[event-first-dao-nhan-qua|Event-first]]
