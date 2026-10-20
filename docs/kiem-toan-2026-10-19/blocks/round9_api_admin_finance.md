# Round 9 — FastAPI admin, finance and material workflows

Status: complete, read-only. Source evidence is from the pinned exact-main snapshot `956ba4f236b1c92f1280d2097018c199e90ce8c7` at `/tmp/clinicai-audit-main-956ba4f2`. The shared working checkout was used only to cross-check canonical finding IDs, never as code evidence.

## Kết quả

Không thấy lỗi mới đã đủ bằng chứng để gán ID canonical trong các luồng admin, tài chính, thuế, mẫu kết quả, log dịch vụ và vật tư đã đọc. Có một ứng viên mức thấp về ngữ cảnh cơ sở trong danh tính API: khi một nhân viên có membership ở nhiều clinic chọn clinic khác với cơ sở chính toàn cục của họ, thiếu header X-Location-ID và clinic được chọn chưa cấu hình cơ sở mặc định, backend giữ lại primary_location_id của clinic khác. Các luồng vật tư kiểm tra cặp clinic/location và từ chối thao tác không khớp; chưa thấy đọc hoặc ghi dữ liệu chéo clinic. Ứng viên này được ghi riêng để chủ audit quyết định có đưa vào registry hay không.

Ứng viên liên quan FE-009 nhưng không trùng: FE-009 là dashboard hiện chưa cho chọn clinic; ứng viên này là phép fallback location của FastAPI khi X-Clinic-ID đã được chọn. Dashboard hiện tại không gửi X-Clinic-ID, nên chưa chứng minh người dùng dashboard có thể kích hoạt tình huống đó.

## Ứng viên cần triage

- `src/clinicai/api/identity.py:456-483`: membership được lọc theo clinic được chọn; JOIN lấy tên primary location chỉ theo `l.id = s.primary_location_id`, không ràng buộc clinic.
- `src/clinicai/api/identity.py:529-549`: nếu không có X-Location-ID và clinic không có default location, `location_id` giữ giá trị primary_location_id toàn cục.
- `supabase/migrations/20260730000003_multi_tenant_foundation.sql:44-67`: mô hình cho phép một staff có membership ở nhiều clinic, với role theo từng membership.
- `supabase/migrations/20260803000007_staff_identity_completeness.sql:145-183`: trigger chỉ yêu cầu primary location thuộc một clinic mà staff là thành viên, không yêu cầu nó thuộc clinic đang được chọn.
- `src/clinicai/api/v1/routers/identity.py:53-63,85-129`: /me ghép clinic đã chọn với location fallback; /me/co-so trả danh sách theo clinic nhưng đưa location_id vào dang_chon mà không xác nhận nó nằm trong danh sách.
- `src/clinicai/services/vat_tu_nhap_duyet_service.py:148-155` và `src/clinicai/services/vat_tu_kho_service.py:167-174`: các thao tác nhập vật tư cần location tồn tại trong đúng clinic, nếu không thì dừng với NotFoundError. Migration yêu cầu nhập cũng kiểm tra cặp clinic/location tại `20261014200100_vat_tu_nhap_cho_duyet.sql:64-71`.

Kịch bản kích hoạt, ảnh hưởng, khuyến nghị, điều kiện chấp nhận và giới hạn được ghi đầy đủ trong `round9_api_admin_finance.findings.json`.

## Các kiểm soát đã xác nhận tĩnh

- Console chỉ chạy ngoài APP_ENV=production, mặc định thiếu biến môi trường là production; yêu cầu ops.view ở route. Dù dashboard này liệt kê tài khoản auth toàn cục, đường API tự từ chối trên production.
- Day-noi kiểm tra quyền config.wiring.manage ở service, giới hạn đọc/ghi theo clinic_id, kiểm tra phòng thuộc clinic và ghi audit event.
- Dọn dữ liệu khách thử yêu cầu permission.manage trong service, xem trước chạy hàm trong transaction rồi rollback; lệnh xoá khoá patient trong clinic, chặn khách có lượt đang mở hôm nay, và báo lỗi khi lock timeout.
- Hóa đơn công ty kiểm tra quyền bên trong service, gắn hồ sơ công ty với patient/payment cycle trong cùng clinic, lưu bản chụp hóa đơn và lịch sử thay đổi trong transaction.
- Luồng MISA kiểm tra quyền kế toán, dựng lại tập hóa đơn từ service phía server, rồi ghi snapshot theo clinic. FIN-006 là giới hạn phạm vi xuất hoá đơn khác, không phải lỗi mới của các route MISA đã xem.
- Thuế suất kiểm tra quyền xem/sửa; truy vấn và cập nhật lọc clinic_id, loại mặt hàng hợp lệ và kiểm tra số dòng cập nhật.
- Mẫu kết quả giới hạn dữ liệu theo clinic; lệnh gắn/gỡ/xuất bản kiểm capability tại service và chỉ chép mẫu đã xuất bản trong clinic.
- Làm thêm tại quầy dùng revision/idempotency, khoá lượt, giới hạn clinic cho lệnh; thao tác bỏ không cho bỏ đơn đã bắt đầu/đã thanh toán và ghi đảo trong cùng transaction.
- Vật tư chờ duyệt lưu ảnh chụp nội dung/giá, khoá yêu cầu theo clinic+location, kiểm capability và chỉ quyết định một lần; sổ kho kiểm clinic+location và phòng thuộc cặp đó.
- Các route service-log được đánh dấu ngừng dùng và trả 410; thư ký y khoa dùng capability và phạm vi khách theo clinic/bác sĩ. SEC-011 là finding canonical đã có về đường bệnh án, không nhân đôi ở lát cắt này.

## Cross-check và giới hạn

Canonical IDs đã soát để tránh lặp: FE-009, SEC-011, SEC-018, FIN-006. Không có finding canonical nào trùng trực tiếp với ứng viên location fallback; FE-009 chỉ là giới hạn selector ở dashboard. `round9_api_admin_finance.findings.json` dùng ID nội bộ CAND-R9-API-ADMIN-01, không cấp ID canonical.

Đây là kiểm toán tĩnh trên snapshot được ghim. Không chạy tests, không truy cập DB/production/secrets/PHI và không sửa source hoặc migration. Không xác nhận cấu hình clinic thực tế, người dùng production nào có nhiều membership, hay tần suất lỗi runtime.
