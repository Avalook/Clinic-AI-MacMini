# Rà soát migrations 07–08/2026 — round 9

Nguồn duy nhất: snapshot `/tmp/clinicai-audit-main-956ba4f2`, SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Phạm vi gồm **119 migration, 17.714 dòng logic theo splitlines()** có tiền tố 202607/202608; từng file đã đọc hết. Baseline 20260714000001 được đọc thành ba đoạn liên tục. Danh sách hash, số dòng, trạng thái ledger ban đầu và dải dòng đã đọc nằm trong `round9_migrations_20260708.coverage.json`.

Đây là audit tĩnh. Không truy cập DB/HTTP/production, không đọc secrets/PHI, không chạy migration hoặc SQL test và không sửa source. Canonical `PHAT-HIEN.json` được đọc chỉ để tránh trùng ID. Năm candidate dưới đây chưa phải kết luận runtime; toàn bộ evidence path/line/hash nằm trong `round9_migrations_20260708.findings.json`.

## Candidate mới cần triage

| ID | Vấn đề | Tác động khi kích hoạt | Độ chắc chắn / giới hạn |
|---|---|---|---|
| CAND-R9-MIG-01 | UPDATE chuyển patient_sdt_them sang bệnh nhân khác chỉ làm tươi hồ sơ NEW; hồ sơ OLD giữ số trong sdt_tim_kiem. | Tìm theo số có thể tiếp tục trả hồ sơ cũ sau khi số đã chuyển. | Cao về trigger; chưa xác minh dữ liệu/runtime. |
| CAND-R9-MIG-02 | ADJUST chấp nhận reason NULL/rỗng dù comment yêu cầu ghi lý do. | Điều chỉnh tồn thiếu giải thích trong sổ cái. | Cao về schema; chưa xem write service hoặc dữ liệu. |
| CAND-R9-MIG-03 | Bốn CHECK dùng trạng thái = conjunction của metadata; khi trạng thái chưa xong, một tập con marker vẫn qua CHECK. | Hàng chờ/chưa xử lý có thể mang dấu vết một phần, không phân biệt draft với update lỗi. | Cao về truth table; cần owner chốt có cho phép draft không. |
| CAND-R9-MIG-04 | patient_sdt_them không buộc clinic_id khớp clinic của patient cha; policy đọc theo clinic_id hàng con. | Nếu backend ghi tổ hợp sai, clinic A có thể đọc số của patient B. | Cao về thiếu ràng buộc; không có bằng chứng dữ liệu sai hay đường ghi gây ra. |
| CAND-R9-MIG-05 | Hai helper dispatch SECURITY DEFINER được grant EXECUTE cho authenticated trong tranche; cleanup table-only không thu hồi function grants. | Nếu grant còn hiệu lực, có thể gọi ghi dispatch ngoài FastAPI và tự truyền actor. | Cao về GRANT trong tranche; trạng thái ACL cuối không rõ vì không kiểm tháng ngoài phạm vi hoặc catalog. |

### Quan hệ với phát hiện đã có

Migrations đã được đối chiếu với toàn bộ ID trong canonical `PHAT-HIEN.json`. Không tạo ID trùng. Migrations `20260815000002_nhieu_so_dien_thoai.sql` thêm bảng số điện thoại có SELECT cho authenticated theo current_clinic_ids(); đây là **mở rộng phạm vi dữ liệu của SEC-018**, không phải bản sao finding đó. CAND-R9-MIG-04 tách riêng bất biến quan hệ tenant giữa bảng con và bệnh nhân cha. CAND-R9-MIG-01 cùng vùng dữ liệu CLIN-013 nhưng là lỗi cột tổng hợp cũ khi đổi chủ hàng con, không phải lỗi phát hiện trùng số.

## Thứ tự migration và khả năng replay

- Nhiều file dùng `IF NOT EXISTS`, `CREATE OR REPLACE`, hoặc DROP/CREATE trigger/constraint để hỗ trợ object đã có. Điều này làm thao tác tên object lặp lại an toàn hơn, nhưng không chứng minh một schema partial hoặc khác định nghĩa sẽ được tự sửa đúng.
- Chuỗi `20260804000003` → `04` → `05` → `06` liên tục thay định nghĩa dispatch. `04` tạo function hợp lệ về cú pháp nhưng predicate `ON CONFLICT` không khớp unique index ở đường re-entry; `05` mới sửa. Nếu rollout bị ngắt sau migration 04, đường re-entry vẫn có thể lỗi cho tới migration 05. Đây là rủi ro giữa các file, không phải lỗi còn mở sau khi cả chuỗi áp dụng thành công.
- `20260821000001` có transaction BEGIN/COMMIT. Phần seed ca chỉ chạy khi ca chưa có, nhưng UPDATE `settings.hours` áp cho mọi clinic có hours và ghi cố định 07:00–22:00. Replay sau khi quản lý đã chỉnh giờ sẽ ghi đè cấu hình ấy; bình thường migration được đánh dấu đã áp dụng nên đây là lưu ý recovery/replay, không tự kết luận migration sai policy.
- Không đánh giá rollback trên PostgreSQL. Mọi rollback claim bị giới hạn ở SQL source; không có kiểm tra transaction behavior hay migration registry.

## Bằng chứng test và chốt tích cực

- `supabase/tests/nhieu_so_dien_thoai.sql` kiểm insert, đổi số chính, delete số con, duplicate và format; chưa thử UPDATE đổi clinic_patient_id.
- `supabase/tests/inventory_write_guards.sql` kiểm tồn, append-only, actor và clinic của lô; chưa thử ADJUST với reason NULL/rỗng.
- `supabase/tests/cap_phat_thuoc_mot_phan.sql` và `nhac_tai_kham_hai_luot_goi.sql` kiểm một số trạng thái hoàn tất/thiếu dấu vết; chưa kiểm marker đơn lẻ khi trạng thái còn chưa hoàn tất. Search các SQL test cho phan_hoi_khach và gui_luc/gui_boi_staff_id không thấy assertion cho tổ hợp một phần.
- `supabase/tests/public_function_acl.sql` mong authenticated không execute được `move_visit_to_station` và `place_visit_at_first_station`, đồng thời service_role được execute. Đây là hợp đồng tĩnh; test chưa chạy. Không thể từ phạm vi tháng 07–08 kết luận effective ACL cuối.
- Chuỗi dispatch có một sửa lỗi nội bộ: 20260804000004 dùng predicate ON CONFLICT chưa khớp unique index; 20260804000005 thêm phần predicate còn thiếu. Ghi nhận đây là correction đã có trong tranche, không báo như lỗi còn mở.
- 20260804000016 thu hồi ghi trực tiếp trên các bảng được liệt kê. Nó không thu hồi EXECUTE function, nên cần rà ACL riêng như candidate 05.

## Câu hỏi policy cần owner trả lời

1. 20260821000001 thay giờ cho **mọi key đang tồn tại** trong settings.hours thành 07:00–22:00. Ý định là bao đủ ba ca; cần xác nhận ngày nghỉ/giờ ngắn theo thứ trong tuần có bị mở rộng như vậy không. Chưa có SQL test cho chính sách này.
2. 20260806000004 chỉ bắt incomplete_reason khi visit ở trạng thái INCOMPLETE; chưa ghép incomplete_at và incomplete_by vào CHECK. Cần xác nhận timestamp và actor có bắt buộc, hay chỉ reason mới là điều kiện hoàn tất.
3. Các CHECK metadata có thể cần state draft rõ ràng nếu sản phẩm cho phép nhập từng phần; comment migration hiện mô tả dấu vết all-or-none.

## Giới hạn

Không kiểm effective PostgreSQL ACL/RLS, không replay migration để xác nhận thứ tự/rollback, không chạy SQL test và không xác minh trạng thái DB. Static absence không chứng minh không có dữ liệu sai; candidate ACL dispatch không chứng minh người dùng hiện có thể gọi. Các nội dung phụ thuộc sản phẩm được giữ là câu hỏi, không nâng thành lỗi chắc chắn.
