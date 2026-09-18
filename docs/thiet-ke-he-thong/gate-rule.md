---
title: "visit_gate_rule — luật thứ tự bắt buộc 4 ô, ngoại lệ có lý do, hàm thuần kiểm được"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "20260804000014_gate_rule.sql · services/gate_rule_service.py"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# visit_gate_rule — luật thứ tự bắt buộc 4 ô, ngoại lệ có lý do, hàm thuần kiểm được

> [!abstract] Mẫu chuẩn 'luật là dữ liệu có phạm vi tenant': áp cho ai · bắt buộc qua · chặn gì · ai bỏ qua được — 0 dòng trên prod.

> «BA CÁCH LÀM, CHỈ MỘT CÁCH ĐÚNG. (1) `if (doctor == 'Thành')` trong code → phòng khám thứ hai phải sửa code. Không bán được. (2) Thêm cột `is_gatekeeper` vào `staff` → […] Mỗi khách một cột. (3) Khai thành LUẬT có phạm vi tenant → ba khách hàng, ba luật khác nhau, cùng một dòng code.» — *migration header*

Bốn ô: **ÁP CHO AI** (`patient_kind` NEW/RETURN, `service_type_id`, `location_id`; NULL = mọi) · **BẮT BUỘC QUA** (`required_node_code(s)`, `required_staff_id`) · **CHẶN CÁI GÌ** (`blocked_node_codes[]`, `only_when_other_staff`) · **AI BỎ QUA ĐƯỢC** (`override_roles`, mặc định TRUONG_CA/MANAGEMENT).

> «Ô thứ tư không phải phần phụ. Phòng khám thật luôn có ca ngoại lệ; hệ thống nào không cho ngoại lệ sẽ bị vượt mặt bằng giấy tay, và lúc đó nó mất luôn khả năng biết chuyện gì đã xảy ra. Nên ngoại lệ được PHÉP, nhưng bắt ghi lý do và sinh event.»

`visit_gate_override` ghi riêng «để hỏi "tháng này luật nào bị bỏ qua nhiều nhất" chỉ là một câu SELECT». Trigger `visit_gate_rule_nodes_exist` chặn mã node gõ sai («Gõ sai một mã ở đây thì luật lặng lẽ không chặn gì — đúng loại hỏng tệ nhất với một luật an toàn»).

`gate_rule_service.py`: `applies_to / satisfied / blocks / first_block / may_override` là **hàm thuần** («Đây là một chốt an toàn: nó nói "không" với một thao tác mà con người đang muốn làm, giữa ca trực, với bệnh nhân đang đứng đó. […] Cả hai đều phải kiểm được bằng bảng tình huống»). `satisfied()` kiểm **tập** node — «BS Thành phụ trách cả năm chuyên khoa, nên "đã gặp BS Thành" có năm hình dạng».

Cảnh báo dữ liệu ghi trong code: «hôm nay mới 1/7 work_item có assigned_to. Nên một luật đòi ĐÍCH DANH người sẽ coi là chưa qua bước — tức là chặn nhiều hơn thực tế.»

### Vì sao nút này quan trọng với thiết kế đích

Đây là **khuôn mẫu policy** đúng nhất trong repo: trigger (một nước đi) · điều kiện (facts của visit) · quyết định (chặn/cho) · hành động (từ chối hoặc ghi override) · audit. Thiếu duy nhất: **version/effective_from** và không phản ứng với *event* (chỉ với lệnh move). [[tk-policy-engine|policy + policy_case]] lấy đúng cấu trúc 4 ô + override này làm hình dạng cho bảng `policy`, và `docs/kien-truc-nhieu-phong-kham.md` §3 (4 tầng cấu hình) làm khung phân loại luật.

## Nối tới
- [[dispatch|Điều phối Trưởng ca]]
- [[policy-engine|Policy Engine]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]
- [[tk-policy-engine|policy + policy_case]]
- [[10-principles|10 nguyên tắc sản phẩm]]

## Được dẫn từ
- [[policy-engine|Policy Engine]]
- [[dispatch|Điều phối Trưởng ca]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]
- [[gap-policy|Khoảng cách 9]]
- [[tk-policy-engine|policy + policy_case]]
