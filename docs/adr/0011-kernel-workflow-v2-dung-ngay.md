# ADR-0011 — Dựng kernel workflow V2 (`node_definition` / `work_item`) ngay, thay `staff_task`

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-30 |
| **Deciders** | Quang — "dựng hết nhé" |
| **Liên quan** | `docs/ClinicAI-Tong-Quan-He-Thong.md` §4, §13 (37 node); ADR-0001, ADR-0002, ADR-0009 |

## Context
Tài liệu §4/§13 mô tả trái tim sản phẩm: 37 node nghiệp vụ, mỗi node có vai trò /
workspace / ưu tiên / dependency (FS, SS, FF, SF) + gate, điều khiển qua Command API.
Trong DB thật **chưa có** `node_definition`, `work_item`, `work_item_dependency`,
`follow_up_case`, `release_state`. Hệ đang chạy bằng `staff_task` — một bảng phẳng
không có dependency, không có gate, không có định nghĩa node.

Nghĩa là phần khiến ClinicAI khác một phần mềm phòng khám thường (workflow
orchestration, cấu hình được cho từng phòng khám) hiện chỉ tồn tại trên giấy.

## Decision
1. Dựng kernel V2 **ngay trong đợt này**, không chờ pilot:
   `node_definition`, `node_dependency`, `work_item`, `work_item_event`, `follow_up_case`.
2. **Node là dữ liệu, không phải code.** 37 node ở §13 được seed vào `node_definition`
   (mã, tên, vai trò, workspace, ưu tiên, gate). Phòng khám mới đổi luồng = sửa dữ liệu.
   Mọi bảng kernel mang `clinic_id` (ADR-0009).
3. **Command API là đường ghi duy nhất**: `start` / `complete` / `skip` / `cancel` trên
   `work_item`. Không UI nào `UPDATE` thẳng trạng thái.
4. **Chuyển trạng thái sinh event** vào outbox (ADR-0002); routing tạo work item kế tiếp
   từ `node_dependency` — không hard-code luồng trong Python.
5. **`staff_task` giữ nguyên và được migrate**, không xoá ngay: work item mới ghi cả hai
   trong một giai đoạn ngắn, màn `/tasks` đọc từ `work_item`, rồi mới bỏ `staff_task`.
6. Bất biến ép ở DB (ADR-0003): không `complete` khi còn dependency FS chưa xong;
   `work_item` không đổi trạng thái ngược.

## Alternatives
| | Ưu | Nhược |
|---|---|---|
| **A. Dựng ngay (chọn)** | đúng sản phẩm cuối; luồng cấu hình được cho tenant mới; không phải viết 2 lần | đợt việc lớn nhất trong roadmap; pilot chậm hơn |
| B. Giữ `staff_task` cho pilot rồi nâng | pilot sớm | phải viết logic luồng 2 lần, và lần 2 phải migrate dữ liệu lâm sàng thật |
| C. Chỉ thêm dependency vào `staff_task` | ít bảng hơn | vẫn không có định nghĩa node → không cấu hình được theo phòng khám = mất điểm bán hàng |

## Consequences
**Tích cực:** luồng khám trở thành cấu hình; onboard phòng khám mới không cần lập trình
viên; mọi bước có audit trail thật.
**Tiêu cực:** khối lượng lớn (5 bảng + Command API + routing + seed 37 node + màn
`/tasks` viết lại); giai đoạn ghi kép cần dọn dứt điểm, nếu để lâu sẽ thành nợ.
**Rủi ro:** over-engineering nếu 37 node chưa đúng thực tế → seed từ Notion (nguồn của
phòng khám) chứ không tự nghĩ ra, và cho phép sửa bằng dữ liệu.
