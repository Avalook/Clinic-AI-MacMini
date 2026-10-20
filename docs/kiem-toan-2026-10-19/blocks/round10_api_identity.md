# Round 10 — Audit identity/authorization FastAPI (static)

**Snapshot:** /tmp/clinicai-audit-main-956ba4f2 · SHA theo chỉ định: 956ba4f236b1c92f1280d2097018c199e90ce8c7  
**Kết quả:** không xác nhận được candidate mới trong lát audit này. findings.json rỗng. Các mục đã có trong ledger chỉ được đối chiếu để khử trùng, không sửa ledger.

## Phạm vi và phương pháp

Đã rà lớp xác minh JWT → staff → clinic membership → clinic/location selection và cache identity; các cửa capability, cache quyền và quyền theo lịch/phòng; route me, login, display/partner; service phân quyền/kỹ năng; và kiểm kê endpoint/router FastAPI để tìm dependency identity trực tiếp, guard tuỳ biến hoặc route không gắn dependency trực tiếp. Static inventory bằng AST phủ **619 route decorator** trong src/clinicai/api/v1; gồm 213 route có get_current_identity trực tiếp, 2 route có get_display_identity, 15 route có get_partner_identity, 387 route có dependency guard tuỳ biến, và 2 route không có dependency trực tiếp trong handler. Hai route cuối đã nhận diện là GET /display/config (public config có chủ ý) và GET /phan-quyen/danh-muc (danh mục capability/preset tĩnh); không thấy phản hồi chứa dữ liệu nhân viên/bệnh nhân từ riêng các handler đó.

Đã đọc trực tiếp các dải control-flow ở identity provider, quyền capability, cache và các route allowlist đặc biệt. Đối với toàn bộ router còn lại, kết quả AST/grep chỉ là kiểm kê đường vào, không phải rà từng câu SQL/service bên trong; vì vậy kết luận “không có candidate mới” chỉ áp dụng cho lát review được nêu và không phải xác nhận tuyệt đối mọi endpoint an toàn.

## Nhận định

- **JWT và identity:** _resolve_identity xác minh bearer token trước khi tra dữ liệu; clinic selector chỉ chọn active membership của đúng subject; nhiều membership mơ hồ bị từ chối. Location selector được ràng buộc với clinic và trạng thái active; không có header thì chọn location mặc định theo logic hiện hành. Cả clinic/location đều đi vào cache key. get_current_identity từ chối DISPLAY và PARTNER; route TV và đối tác dùng dependency chuyên biệt.
- **Capability:** cua_quyen gọi can; câu tra quyền ràng buộc clinic_id, staff_id, capability và scope. Quyền phủ định không được cache; quyền dương theo clinic có TTL và có đường invalidation trong cùng process. Quyền theo phòng đi DB trực tiếp. Không xác nhận được lỗi mới trong các đường chung đã đọc.
- **Vị trí/ca:** doi_lich_phong fail-closed khi công tắc bật, có phòng đích, caller không có quyền điều phối và không có ca tương ứng. Nó dùng clinic identity và vị trí trong lịch; ngoại lệ cho lệnh cũ/ngày cũ được biểu thị rõ. Không thấy đường lấy location_id do client chọn làm thẩm quyền trong các helper đã rà.
- **Ngoại lệ có chủ ý:** /display/config public chỉ đọc clinic.settings->display; /display/queue yêu cầu identity DISPLAY-compatible và service giới hạn theo clinic/location, loại định danh bệnh nhân ngoài tên cấu hình cho phép. Các endpoint đối tác đi qua get_partner_identity, kiểm partner.work; không thấy handler đối tác dùng get_current_identity để lách ranh giới.
- **Caller/router:** inventory nhận diện các endpoint đã có phát hiện về shared-form, phân công bệnh nhân, scope cơ sở và tenant reference. Những trigger/call chain trùng được loại khỏi candidate mới theo ledger bên dưới. Router dùng get_current_identity không tự động được xem là lỗi: một số route cố ý là endpoint dữ liệu của người hiện tại, số khác gọi service/guard ở dưới; kiểm kê dependency một mình không đủ kết luận thiếu authorization.

## Khử trùng ledger

Đọc docs/kiem-toan-2026-10-19/PHAT-HIEN.json trong workspace canonical **chỉ để khử trùng**. SHA-256 tại lúc đọc: f4c89cd370978fdb57b4e8e30945a56c8639f90b9ac018f2213a29cb0a66c426. Các mục gần nhất đã so trigger/call chain: SEC-001, SEC-002, SEC-005–SEC-007, SEC-010–SEC-012, SEC-014, SEC-016–SEC-019, FE-009, CLIN-014, API-001–API-003, DB-001, DB-005. Đây là các mục đã tồn tại; không được báo lại là finding round 10.

## Giới hạn

Không chạy test, không gọi DB/runtime/production, không đọc secrets hoặc PHI, không sửa source/migration, không xác minh hành vi sau deploy. Snapshot thư mục không có metadata .git; SHA commit là giá trị được task cung cấp và được các artifact round 9 trong snapshot ghi cùng SHA. Hash evidence dưới đây được tính trực tiếp trên các tệp snapshot hiện có. Static inventory có thể nhận diện dependency nhưng không chứng minh mọi nhánh runtime hoặc policy database.
