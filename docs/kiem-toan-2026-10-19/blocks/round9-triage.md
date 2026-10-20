# Round 9 — triage exact-main

Ngày: 19/10/2026. Nguồn: snapshot `956ba4f236b1c92f1280d2097018c199e90ce8c7` tại `/tmp/clinicai-audit-main-956ba4f2`. Mọi kết luận mới trong vòng này là static, trừ khi nêu rõ phép thử. Không đọc dữ liệu bệnh nhân, secrets hay production; không sửa app/migration.

## Đã tích hợp vào ledger

- `INF-018`: event delivery và `hen_gio` tăng số lần thử khi claim, nhưng lease reclaimer luôn đưa việc trở lại `RETRY`/`CHO` sau khi worker chết; nhánh này không áp retry cap hoặc tạo trạng thái dead-letter. Đây là static control-flow finding, chưa mô phỏng crash. Nó khác `INF-005` (fencing callback cũ) và `INF-017` (cửa sổ metric DEAD), dù cùng thuộc vận hành worker.
- `API-001..API-003`: ba thiếu sót location/tenant ở lệnh kéo hàng chờ, chi tiết workflow của lượt và quản lý ca trực. Ghi nhận trong phạm vi cùng clinic hoặc lỗi toàn vẹn tham chiếu; không kết luận vượt clinic khi evidence không cho thấy điều đó.
- `FE-012..FE-015`: candidate bệnh nhân trùng có thể giữ hành động của kết quả cũ; response tải phường có thể về sai thứ tự (`FE-013`, hạ xuống LOW vì chỉ làm sai cặp địa chỉ); ngoại lệ ca trực cũ có thể bị huỷ theo ID; và gỡ roster tiếp tục dù preview lỗi hoặc không còn khớp snapshot.
- `DB-006`: bảy migration tháng 10 tự kết thúc transaction trước khi runner ghi ledger. Impact là trạng thái schema/ledger và thông báo phục hồi có thể lệch khi lỗi xảy ra đúng cửa sổ này; chưa có bằng chứng dữ liệu hỏng.
- `DB-007`: schema không buộc `clinic_patient_id` trong `cong_no`/`so_no` trùng bệnh nhân của visit. Hai writer hiện hành được đối chiếu: `cong_no_service` lấy bệnh nhân từ visit đã khóa theo clinic; `so_no_service` lấy patient ID từ truy vấn visit theo clinic. Không có miswrite hiện tại được chứng minh; giữ ở mức LOW `design_gap` để DB chốt bất biến tài chính.
- `FIN-010`: CHECK huỷ thanh toán đối tác cho phép `ly_do_huy = NULL` do semantics UNKNOWN của PostgreSQL CHECK; trigger không bổ sung kiểm tra này.
- `SEC-019`: `form_instance_lich_su` và `luot_ghi_chu` chứa nội dung lâm sàng, nhưng authenticated có SELECT trực tiếp với policy chỉ lọc clinic. Đây là HIGH static access-boundary finding; chưa thử JWT/PostgREST hoặc DB runtime và chưa xác nhận ma trận vai với chủ nghiệp vụ.

Coverage của các slice đã nhập vào `MAIN-PHAM-VI.json`. Tổng số đọc/traced/scanned vẫn là coverage theo file, không phải phần trăm ngữ nghĩa đã kiểm.

## Candidate giữ lại để xác minh tiếp

- Identity fallback ở API admin: location mặc định có thể thuộc clinic khác khi chọn multi-clinic mà clinic mới không có default. Endpoint vật tư hiện đối chiếu clinic+location và dừng; chưa tìm thấy đọc/ghi chéo. Giữ LOW ngoài risk count đến khi kiểm đủ mọi consumer của identity.
- Trigger số điện thoại tổng hợp chỉ làm tươi một hồ sơ khi đổi `clinic_patient_id` trên `patient_sdt_them`. API hiện có thêm/xoá và kiểm parent theo clinic; chưa thấy đường ứng dụng chuyển số giữa hai hồ sơ. Cần xác nhận DB write contract và kiểm tra bản ghi hiện có trước khi nâng.
- `inventory_txn.reason` không bị DB bắt buộc với `ADJUST`; luồng kiểm kho hiện ghi lý do tự động. Giữ là hardening gap vì chưa thấy đường API hiện hành tạo ADJUST thiếu lý do.
- Một số CHECK ở migration tháng 8 cho phép marker bằng chứng từng phần khi trạng thái nghiệp vụ chưa hoàn tất. Các bảng có lifecycle khác nhau; cần đọc consumer/UI và xác định marker từng phần có phải trạng thái nháp hợp lệ không trước khi gọi là lỗi.
- `patient_sdt_them` không có composite constraint buộc clinic của hàng con trùng clinic của patient; service thêm số kiểm hồ sơ bằng `(clinic_patient_id, identity.clinic_id)`. Chưa chứng minh API tạo được hàng sai; giữ là defense-in-depth.
- `phieu_kho_dong` không có constraint so khớp thuốc/lô/transaction tham chiếu. Service kho hiện khóa lô theo clinic/location và truyền chính lô, transaction trả về vào dòng phiếu. Chưa có đường ghi đang được chứng minh tạo mismatch; giữ ở mức schema-hardening.
- `cong_no`/`so_no` hiện writer chọn patient từ visit như nêu ở `DB-007`; finding được ghi low để giữ bất biến ở DB, không phải tuyên bố có misattribution đang diễn ra.

## Đã xử lý ở exact main; không tính là lỗi mở

- Migration tháng 9 từng cấp SELECT authenticated cho `phieu_kho` và `phieu_kho_dong`. `20261019120000_restrict_stock_postgrest_reads.sql` trên exact main drop các SELECT policy và thu hồi privilege của `anon, authenticated`, cấp SELECT cho `service_role`. Candidate block tháng 9 đã cũ sau migration này.
- Migration dispatch ban đầu từng cấp EXECUTE authenticated trên `move_visit_to_station` và `place_visit_at_first_station`. `20261019100000_harden_public_function_acl.sql` trên exact main thu hồi EXECUTE authenticated và cấp cho `service_role`. Candidate tháng 7 được xem là đã sửa ở chuỗi hiện tại.

`round9_migrations_202609.findings.json` giữ nguyên ID ứng viên của slice ban đầu; hai candidate ACL/kho trong file đó chỉ là lịch sử block, không phải ID canonical. ID `SEC-019` trong `PHAT-HIEN.json` chỉ là finding lâm sàng của migration tháng 10.

## Trình tự tiếp tục

1. Mở rộng API/dashboard còn lại theo call chain, ưu tiên authorization, location/tenant, mutation và vòng đời trạng thái.
2. Rà các migration và schema chưa được semantic read; chỉ nâng candidate khi đối chiếu writer, consumer, migration sửa sau đó và test contract.
3. Bổ sung test DB tạm mô phỏng crash sau claim và thu hồi lease lặp qua retry cap cho event delivery lẫn `hen_gio`.
4. Sau mỗi lần thay canonical ledger, dựng `BAO-CAO.html`, chạy `validate_report.py -v`, `verify_browser.cjs`, tạo ZIP bằng `package_audit.py` rồi xác minh bằng `verify_bundle.py`.
5. Giữ `STATE.json.status = in_progress` cho đến khi mọi file in-scope được đọc hoặc có lý do loại trừ được giải thích; không gọi kiểm kê/quét là đọc hết code.
