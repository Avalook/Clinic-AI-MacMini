---
title: "Luật là dữ liệu — kiểm kê 9 bảng luật và 4 tầng cấu hình"
lop: 3
lop_ten: Code đang chạy
tag_nguon: "docs/kien-truc-nhieu-phong-kham.md §3 · đo prod 05/09"
trang_thai: Đã có
tags: [clinicai, lop3-code]
---

# Luật là dữ liệu — kiểm kê 9 bảng luật và 4 tầng cấu hình

> [!abstract] Tài sản lớn nhất so với thesis: Policy/SLA đã là bảng theo tenant; thiếu version, effective_from, owner, và 'luật phản ứng'.

Bốn tầng cấu hình (`docs/kien-truc-nhieu-phong-kham.md` §3): **Tầng 0** hằng số sản phẩm (bệnh án khoá sau ký, một người không ở hai phòng, RLS) · **Tầng 1** danh mục của tenant (cơ sở, tầng, phòng, chuyên khoa, dịch vụ, giá, nhân sự, vai) · **Tầng 2** luật vận hành (quản lý chỉnh, không cần dev) · **Tầng 3** ngoại lệ có ghi lý do.

Kiểm kê tầng 2 trên prod:

| Bảng | Luật | Dòng | Thi hành |
|---|---|---|---|
| `luat_cskh` | 11 loại việc CSKH: số ngày, nhãn, bật/tắt | 11 | view (lúc đọc) |
| `doctor_booking_override` / `slot_booking_override` | sức chứa 3 tầng theo bác sĩ/khung, theo phút | 6 / 0 | trigger (lúc ghi) |
| `clinic.settings` | `hours`, `booking`, `ca_lam_viec` (3 ca), `display`, `feature_mode` | 1 | service (lúc ghi/đọc) |
| `luat_bac_si_bat_buoc` | dịch vụ X + khách mới → bác sĩ Y; 3 cách tính "mới"; `chan_han` | 2 | booking (lúc ghi) |
| `dispatch_threshold` | ngưỡng chờ/số người theo phòng | 1 | `build_alerts` (lúc đọc) |
| `visit_gate_rule` (+`_override`) | thứ tự bắt buộc 4 ô | 0 | `gate_enforce` (lúc ghi) |
| `route_template` | tuyến sau khám | 3 | `apply_route` (tay) |
| `node_definition` (+`_version`) / `node_dependency` | luồng khám, vai, gate | 41 / 18 | kernel |
| `clinic_room` / `clinic_room_node` / `vai_duoc_vao_tram` / `staff_node` | phòng ↔ node, vai ↔ trạm | 12 / 28 | dispatch |

Tầng 3 có ghi lý do: `visit_route.reason`, `visit_gate_override.reason`, `ly_do_huy_ma`, `ly_do_lam_lai` (`20260817000001`), `ly_do_vuot_khung_gio` (CD). TAM-NHIN luật 2: «Case ngoại lệ là thức ăn của lv5; ngoại lệ không ghi lại là bài học vứt đi.»

### Đối chiếu thesis

Care Model §10 đòi policy có **version, owner, test case, audit**. Chỉ `node_definition_version` có version. Không bảng nào có `effective_from`/`owner_role`. Đổi `luat_cskh` không sinh event (`PolicyVersionActivated` — Catalog §13). Test có nhưng là test *hàm* (gate_rule 100% thuần), không phải test *dòng luật*.

Và cả 9 bảng là luật **tĩnh** (điều kiện trên trạng thái) — không có luật loại «event X xảy ra → làm Y → đóng bằng Z». [[tk-policy-engine|policy + policy_case]] thêm đúng một bảng cho loại ấy và bốn cột version cho các bảng cũ; không gộp 9 bảng thành một (chúng có hình khác nhau vì câu hỏi khác nhau — `luat_bac_si_service` docstring: «Hai câu hỏi khác nhau, hai bảng khác nhau»).

## Nối tới
- [[policy-engine|Policy Engine]]
- [[gate-rule|visit_gate_rule]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[tk-policy-engine|policy + policy_case]]
- [[ontology-9|Ontology]]
- [[4-tang-truong-thanh|Bốn tầng trưởng thành của thesis và thang lv1→lv5 của Quang]]

## Được dẫn từ
- [[ontology-9|Ontology]]
- [[macro-v3|Thesis v3]]
- [[policy-engine|Policy Engine]]
- [[gate-rule|visit_gate_rule]]
- [[cskh-views|v_viec_cskh · v_trang_thai_cskh · luat_cskh]]
- [[gap-policy|Khoảng cách 9]]
