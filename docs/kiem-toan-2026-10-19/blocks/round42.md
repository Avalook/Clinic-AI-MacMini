# Round 42 — consent authorization, tenant relations và timeline projection

Nguồn code là Git main ghim `956ba4f236b1c92f1280d2097018c199e90ce8c7` qua `git show`; checkout chính có WIP và không phải bằng chứng. Chỉ audit artifacts được sửa. Không chạy ClinicAI tests/API/DB/runtime/provider/production, không đọc secrets hoặc PHI.

## SEC-010 — mở rộng cùng ranh giới guard, không tạo ID mới

Router consent có hai đường đọc dùng `get_current_identity`: `/patients/{patient_id}/shared-form` và `/patients/{patient_id}/links`. SEC-010 đã bao phủ đường shared-form: caller tự truyền hai patient ID, nhánh cùng ID qua `may_surface`, sau đó service có thể trả tối đa 20 `form_data`. Lát này bổ sung `/links`: service lọc `clinic_id` cùng UUID được truyền nhưng trả quan hệ, ID/tên/mã người kia và form-code consent hai chiều. Nó không trả `form_data`.

Policy DB của `clinical_data_consent` giới hạn RLS cho DOCTOR, ULTRASOUND_DOCTOR, TKYK và NURSE_ULTRASOUND; migration nói MANAGEMENT không có quyền đọc lâm sàng mặc định. `get_current_identity` chỉ từ chối DISPLAY/PARTNER. Backend lấy kết nối qua `DATABASE_URL`, còn `.env.prod.example` dùng user `postgres`; không đọc cấu hình runtime/secret. Vì vậy đây là khoảng trống tĩnh với điều kiện DB role chuẩn, UUID cùng clinic đã biết và không phải chứng cứ có người khai thác. Exact evidence và SHA ở `round42.coverage.json`. Reviewer bảo mật độc lập khuyến nghị gộp vào SEC-010 vì cùng router/guard boundary; không tạo SEC-036.

Test service IO kiểm tra metadata được trả nhưng không kiểm quyền vai ở route; test chỉ được đọc. Không tìm thấy chuỗi caller `/links`, `ConsentService` hoặc `linked_partners` trong dashboard; grep không loại trừ caller dựng động.

## Candidate được rà nhưng không mở finding

- **Timeline projection/PostgREST:** migration cấp SELECT theo clinic và `chi_tiet` chứa whitelist theo loại sự kiện. Tuy vậy API hành trình lượt thường dùng `cua_noi_bo` và trả projection cho nội bộ; dashboard dùng API để nạp và bảng chỉ để refresh. Vì không chứng minh phạm vi quyền tăng thêm so với luồng thường, không mở finding riêng. Nhật ký `/ops/nhat-ky` là route khác có `ops.view`; không gộp nhầm hai bề mặt. Chưa chạy PostgREST/JWT.
- **Hóa đơn công ty:** FK không ghép clinic/patient ở schema, nhưng service kiểm tra patient và company theo clinic; test đọc có ca company của bệnh nhân khác bị loại. Đây là defense-in-depth gần DB-007, không có đường ghi hiện tại sai đã chứng minh.
- **Kho thuốc:** FK staff toàn cục nhưng FK request–transaction giữ clinic + batch; writer lấy actor từ identity. Staff có thể làm nhiều clinic; chưa có chứng cứ mismatch nên giữ ngoài register.
- **Thai kỳ/clinical forms:** full read hai router cho thấy clinical forms khai guard y khoa; ThaiKyService kiểm quyền ghi, patient/visit clinic. Không thêm finding trong lát này.

Coverage path/ranges/hashes và giới hạn được lưu trong `round42.coverage.json`. Đây là lát rà mục tiêu, không phải đọc hết repository; full source audit vẫn đang mở.
