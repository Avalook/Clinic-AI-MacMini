---
title: "Khoảng cách 9 — Policy: là dữ liệu (mạnh), nhưng không version, không owner, không phản ứng với event"
lop: 4
lop_ten: Khoảng cách
tag_nguon: "policy-engine ↔ 9 bảng luật"
trang_thai: Một phần
tags: [clinicai, lop4-khoang-cach]
---

# Khoảng cách 9 — Policy: là dữ liệu (mạnh), nhưng không version, không owner, không phản ứng với event

> [!abstract] Điểm mạnh nhất của code so với thesis; việc còn lại nhỏ và rẻ: version/effective_from + một bảng cho luật phản ứng.

Thesis §10 đòi 4 thứ: **version · owner · test case · audit**. Đo:

| | version | effective_from | owner | event khi đổi | test theo dòng |
|---|---|---|---|---|---|
| `node_definition` | ✅ `_version` snapshot | ❌ | ❌ | ❌ | SQL test kernel ✓ |
| `luat_cskh` | ❌ | ❌ | ❌ | ❌ | ❌ |
| `dispatch_threshold` | ❌ (`updated_by/at`) | ❌ | 🟡 `updated_by` | ❌ | ❌ |
| `visit_gate_rule` | ❌ | ❌ (`is_active`) | ❌ | ❌ (override có bảng riêng ✓) | pytest hàm thuần ✓ |
| `luat_bac_si_bat_buoc` | ❌ | ❌ | ❌ | ✅ `booking.doctor_rule_saved` | `xem_thu()` đếm hậu quả ✓ |
| `*_booking_override` | ❌ (`slot_superseded` event ✓) | ✅ có ngày áp | ❌ | ✅ | test race ✓ |
| `clinic.settings` | ❌ (`hours_truoc_13_08` là "version" bằng tay!) | ❌ | ❌ | ✅ `clinic_settings.*` | ✓ |

Thiếu lớn nhất không phải version — là **loại luật thứ ba**: «Event nào kích hoạt? → … → Outcome Event nào đóng vòng?» Không bảng nào trả lời câu 1 và 5. Mọi luật hôm nay hoặc chặn lúc ghi hoặc tô màu lúc đọc.

Pilot §14: «Mọi thay đổi policy trong live pilot phải có version và ngày hiệu lực để số liệu không bị trộn.» → không có thì baseline/outcome không so được.

Đóng bằng: [[tk-policy-engine|policy + policy_case]] — thêm cột `version, effective_from, effective_to, owner_role` cho 6 bảng cũ (migration nhỏ) + event `PolicyVersionActivated` từ trigger; bảng `policy` mới cho luật phản ứng; bảng `policy_case` để test theo dòng luật chạy trong CI.

## Nối tới
- [[policy-engine|Policy Engine]]
- [[policy-as-data-hien-co|Luật là dữ liệu]]
- [[tk-policy-engine|policy + policy_case]]
- [[gate-rule|visit_gate_rule]]
- [[pilot-scope|Partner Pilot Proposal]]

## Được dẫn từ
- [[tk-policy-engine|policy + policy_case]]
