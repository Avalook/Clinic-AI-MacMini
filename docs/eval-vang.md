# Bộ eval vàng — cổng hồi quy cho các flow sống còn

> Lập 23/08/2026 (Track A · Phase 4 của `~/Projects/LO-TRINH-CTO.md`).
> Chạy: `bash scripts/kiem-vang.sh` (backend, nhanh) · `bash scripts/kiem-vang.sh --full` (kèm frontend).
> Nguyên tắc: **lỗi production/lỗi bị người dùng bắt được → thành case mới ở đây, vĩnh viễn.**

## Vì sao tồn tại

1400+ test của repo chạy hết trong CI, nhưng khi làm việc nhanh cần một **tập nhỏ, chạy < 1 phút,
phủ đúng các flow mà hỏng là phòng khám đứng**: đặt lịch/sức chứa, hàng đợi, đăng nhập/phân quyền,
thanh toán, trạng thái lượt khám. `/nghiem-thu` gọi bộ này trước mọi bàn giao.

## Tập vàng v1 (test ĐÃ CÓ, gom theo flow)

| Flow | File |
|---|---|
| Đặt lịch & sức chứa | `test_booking_service.py`, `unit/test_booking_override_minutes.py`, `unit/test_capacity_cell_state.py`, `services/test_capacity_roster_gate.py`, `services/test_capacity_quote_params.py`, `services/test_slot_hold.py` |
| Hàng đợi gọi khám | `test_queue_order.py`, `test_no_queue_rule_in_dashboard.py` |
| Danh tính & quyền | `test_identity.py`, `test_api_auth.py`, `unit/test_auth_service.py`, `test_me_contract.py`, `test_vai_man_hinh.py`, `test_nav_role_drift.py` |
| Phạm vi tenant | `test_tenant_scope_audit.py` |
| Thanh toán | `test_payment_service.py`, `services/test_checkout_blockers.py` |
| Trạng thái lượt khám | `test_trang_thai_luot_kham_khong_bo_sot.py`, `services/test_gate_rule.py` |

Loại trừ marker `db` và `integration` (cần DB/dịch vụ ngoài) để bộ vàng chạy được ở mọi máy.

## Lỗ hổng đã biết — case CẦN VIẾT THÊM (nguồn: quét 73 lần người dùng bắt lỗi, 23/08/2026)

| # | Case còn thiếu | Nguồn gốc lỗi thật |
|---|---|---|
| G1 | Bác sĩ KHÔNG đánh dấu "khám xong" được khi lễ tân chưa check-in (thứ tự trạng thái bị ép ở server, không chỉ UI) | "lễ tân chưa checkin mà bác sĩ đã có thể đánh dấu khám xong? sai rồi nha" |
| G2 | Validation input ngày sinh/ngày hẹn: ngày 1-31, tháng 1-12, năm 1900-nay, chặn ở cả client lẫn API | "sao bạn để ngày linh tinh vậy" |
| G3 | Đặt lịch liên tiếp cùng khung giờ: lịch người trước phải HIỆN ngay cho người đặt sau (mọi vai trò) | "đặt xong rồi, đặt cho người khác thì không hiện lịch của người trước" |
| G4 | Mỗi vai trò chỉ đọc được đúng scope của mình qua REST (RLS thật, không phải chỉ ẩn nút UI) | các vụ vá "3 lỗ phân quyền URL" |
| G5 | Hai request đặt cùng slot cuối đồng thời → đúng 1 thắng (advisory lock/trigger 2+1) — đã có ở migration test, cần bản chạy-nhanh trong bộ vàng | bug race overbook đã từng vá |

Quy trình: mỗi khi vào repo làm việc thật, nhặt 1 case G* viết thành test, gạch khỏi bảng.

## Nối vào CI (đề xuất — CHƯA áp)

Thêm job `eval-vang` chạy `scripts/kiem-vang.sh` trước job test đầy đủ để fail-fast trong ~1 phút.
Làm thành PR riêng khi quay lại làm ClinicAI; không sửa workflow CI ngoài phiên có review.
