# Round 8 — tenant/RLS (static source audit)

**Phạm vi ghim:** exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7` tại `/tmp/clinicai-audit-main-956ba4f2`. Chỉ đọc source/migration/test tĩnh; không kết nối DB, PostgREST, staging hoặc production; không đọc secrets/PHI và không sửa source ứng dụng/migration.

## SEC-018 — contact và thân nhân bệnh nhân chỉ được giới hạn theo clinic, chưa theo vai

**Mức đề xuất: MEDIUM · xác nhận tĩnh, chưa probe runtime.** Migration tạo `patient_contact_channel` và `patient_next_of_kin`, bật RLS, tạo SELECT policy cho `authenticated` dựa trên `clinic_id IN current_clinic_ids()`, rồi GRANT SELECT cho `authenticated`. Chính migration ghi contact/next-of-kin là dữ liệu hành chính cần cho Reception và CSKH; helper `current_clinic_ids()` chỉ lọc membership active, không lọc role. Các role khác (ví dụ DOCTOR, CASHIER, MANAGEMENT) tồn tại trong role enum.

PostgREST khai báo schema `public`; Caddy chuyển `/rest/v1/*` tới Supabase gateway. Vì vậy đường truy cập trực tiếp theo cấu hình là một token `authenticated` hợp lệ gọi GET `/rest/v1/patient_contact_channel?select=*` hoặc `/rest/v1/patient_next_of_kin?select=*`. Đây là suy luận tĩnh từ cấu hình + GRANT + RLS, chưa xác nhận request thành công ở runtime. RLS vẫn giới hạn hàng theo clinic hiện hành; bằng chứng này **không** cho thấy đọc chéo tenant. Rủi ro là người dùng có role ít cần biết có thể đọc hàng loạt kênh liên hệ của bệnh nhân và dữ liệu thân nhân trong clinic của mình.

**Khác SEC-005:** SEC-005 là hồ sơ định danh/pháp lý của đồng nghiệp (CCCD, ngày sinh, giấy phép) qua API staff. SEC-018 là PII liên hệ bệnh nhân/người thân qua bảng được client đọc trực tiếp bằng PostgREST. Cùng chủ đề least privilege nhưng khác chủ thể dữ liệu, bảng, đường truy cập và nhóm tác động; ghi candidate độc lập để chủ hệ thống quyết định có gộp khi tổng hợp hay không.

**Controls phủ định đã đối chiếu:**

- Policy có tenant predicate `clinic_id` qua `current_clinic_ids()`; không tìm thấy bằng chứng cho phép đọc clinic khác từ lát cắt này.
- RLS được bật trên cả hai bảng và grant ở migration là SELECT, không phải DML.
- Bài test tenant hai clinic kiểm `patient`, `patient_summary`, `clinic_location`, không kiểm hai bảng contact/kin. Bài test contract tenant ghi ba bảng này được đưa vào phạm vi có `clinic_id` (dòng 251–255), nhưng chỉ là kiểm cấu trúc/tenant, không phải role boundary.
- Bài test role-scoped kiểm `clinical_record`, `clinical_form_response` và một phần `patient`; không kiểm role trên contact/kin. Migration role-scoped nói phạm vi của nó là hồ sơ lâm sàng, không tự chứng minh contact/kin đã được duyệt cho mọi role.
- Backend invoice có truy vấn email contact trong scope clinic/cycle; vì vậy phương án sửa cần giữ đường nghiệp vụ có chủ đích này, không xóa dữ liệu hoặc làm hỏng xuất hóa đơn.

**Đề xuất:** Chủ sản phẩm/chủ phòng khám xác nhận ma trận role cần contact/kin. Sau đó giới hạn policy theo role (ví dụ helper clinic+role đã có, với allowlist được phê duyệt) hoặc bỏ SELECT trực tiếp của `authenticated` và cung cấp FastAPI projection có guard + audit. Giữ predicate clinic. Bổ sung test tổng hợp hai clinic và nhiều role: Reception/CSKH cùng các role được phê duyệt đọc được đúng clinic; role không được duyệt không lấy được cả bảng qua SQL session và PostgREST; kiểm tra không thay đổi invoice projection cần thiết.

**Điều kiện nghiệm thu:** Với fixture synthetic, role không được cấp quyền nhận 0 hàng/403 phù hợp trên cả hai bảng qua direct REST; Reception/CSKH chỉ đọc clinic thuộc membership active; token có membership ở clinic A không thể đọc hàng clinic B; kiểm tra endpoint/backend cần thiết cho invoice vẫn trả contact email trong scope giao dịch; test được chạy trên disposable DB và ghi rõ schema/migration state.

**Giới hạn:** Không chạy probe role, không nạp migration vào DB disposable và không gọi endpoint. Chưa kiểm chứng ACL hiệu lực sau toàn bộ lịch sử migration hoặc trạng thái production. Ý định chỉ cho Reception/CSKH lấy từ comment migration, cần người sở hữu nghiệp vụ xác nhận. Finding không kết luận đã có khai thác, lộ dữ liệu thực, hoặc cross-tenant access.

## Coverage của lát cắt

Đã full semantic read migration `20260801000003_adopt_prod_only_tables.sql` (154 dòng). Đã theo predicate/helper và quyền function ở các dòng liên quan của migration multi-tenant foundation; cấu hình PostgREST/Caddy; enum role; grants nền; và đoạn test tenant/role. Các migration/test khác được chọn đối chiếu với coverage ledger để xác định controls và vùng chưa test; chỉ các đoạn liệt kê trong JSON coverage được xem là targeted read, không tính là full review.

Ledger toàn repo là inventory của exact tree, không phải bằng chứng đã đọc tay: snapshot ghi 2,890 entries với 22 `read`, 319 `traced`, 1,993 `scanned`, 548 `inventoried`, 8 `excluded`. Phạm vi round này hoàn tất cho một lát cắt tenant/contact và danh sách đối chiếu nêu trong coverage; **không** có nghĩa đã đọc hết migrations hay toàn bộ repository. Đã tìm toàn bộ tên hai bảng trong cây migrations/tests/backend và tìm grant/revoke diện rộng; không thấy migration sau sửa ACL/policy tường minh cho hai bảng. Migration harden ACL muộn chỉnh EXECUTE function, không chỉnh table grants. Đây chỉ là text search, không thay catalog query. Không chạy test/DB/HTTP.

Hash SHA-256 và line evidence chi tiết nằm trong `round8_tenant.findings.json`; coverage, lệnh tra cứu và giới hạn nằm trong `round8_tenant.coverage.json`.
