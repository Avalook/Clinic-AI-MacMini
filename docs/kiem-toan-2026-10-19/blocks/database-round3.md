# Database — vòng kiểm chéo 3, exact main

Nguồn: `956ba4f236b1c92f1280d2097018c199e90ce8c7`, worktree audit-main-1910.
Chỉ đọc; không app change, không migration apply, không truy cập production trong vòng này.
Hash/độ sâu từng file ở `database-round3.coverage.json`.

## Kết luận

Không tạo finding độc lập mới. DB-004 giữ là khoảng trống đóng gói thương mại có bằng chứng local về hiệu ứng của **function hiện hành**, không suy rằng runner thông thường tự chạy lại migration lịch sử.
Có một mặt truy cập PostgREST cần bổ sung vào SEC-011 khi sửa phạm vi TKYK.

## DB-004 — phạm vi chính xác và điểm phủ nhận đã kiểm

- Migration 25/09 `chuan_hoa_danh_muc_thuoc_kiotviet` L44–54: không tham số tenant; loop mọi clinic đã có drug_catalog. L617–643 insert/update danh mục riêng Dr4Women, tắt item không thuộc tập và service_price nhóm thuốc. L653–654 gate chỉ có staff bất kỳ trong DB; không kiểm clinic đích.
- Probe sẵn có `probes/catalog-tenants-main-run.txt`: DB tạm đủ 42 migration còn thiếu, 2 clinic giả, mỗi clinic 1 item độc lập. Sau gọi function, mỗi bên 92 row, item gốc false. Test RED; outer transaction rollback. Vòng này đọc và kiểm chéo probe, không chạy lại.
- `supabase/seed.sql` L3729 gọi hàm thuốc; L3731 gọi chuẩn hóa dịch vụ; L3745 đồng bộ nguồn kiot_0110.
- **Giới hạn quan trọng:** `apply-pending-migrations.sh` L90–100 chỉ nhận version chưa ghi sổ. `dev-up.sh` L263–274 chỉ seed nhánh DB mới; DB existing áp pending. Do đó không có bằng chứng mỗi deploy/nâng cấp hiện tại luôn ghi đè giá. Probe trực tiếp gọi helper không tương đương replay runner.
- Nguy cơ thực: bootstrap dùng seed Dr4Women trên DB có tenant khác; chạy lại helper/data import chung; nâng từ trạng thái chưa áp các migration này nhưng có dữ liệu clinic độc lập; hoặc restore ledger sai (đã có INF-006/DB-002, không đếm thêm).
- Hardening ACL 19/10 đã thu PUBLIC/anon EXECUTE; hàm catalog này là SECURITY INVOKER. Không coi đây là anonymous mutation RPC. Người vận hành/owner hoặc seed là đường liên quan.

## Cùng gốc nhưng không đếm thêm finding

1. `20260926000001_danh_muc_dich_vu_kiotviet.sql` L85–93 UPDATE service_code CLS theo bộ giá/mã Dr4Women trên mọi clinic, không tenant predicate. L142–157 thêm KV dịch vụ cho mọi clinic đã có mã CLS. Gate L166 là EXISTS staff toàn DB.
2. `20261002100000_danh_muc_dich_vu_chuan_0110.sql` L189–204 matching tên/mã trên mọi clinic; L247–267 đặt tên/giá/nhóm/bên thu từ nguồn; L272–299 thêm nguồn kiot_0110 cho mọi clinic có service_price. Không cần gọi lại thuốc để gặp cùng kiến trúc dữ liệu.
3. `20260930900000_mo_full_lego.sql` L23–51 là quyết định nghiệp vụ đã ghi rõ: mở quyền và tắt quyen_theo_lich. Có phạm vi rộng khi dùng lại cho khách khác nhưng không gọi đó là bug độc lập hay trái ý người dùng hiện tại.

Thiết kế cần tách: schema migration; reference catalog versioned; tenant configuration/data import có clinic đích, preview diff và source provenance. Không sửa migration lịch sử để chữa bootstrap tương lai.

## Bổ sung SEC-011 — RPC bản nháp thuốc

- `20260915000007_prescription_draft_column_privacy.sql` L25–42: `read_prescription_draft(uuid)` SECURITY DEFINER, lọc clinic theo các vai DOCTOR/ULTRASOUND_DOCTOR/TKYK. Không gọi `thu_ky_duoc_xem_khach`, không lọc bác sĩ phân công.
- `20260915000021_thu_ky_rls_theo_bac_si.sql` L103–114 gắn restrictive policy vào clinical_record, nhưng body definer đọc theo owner bỏ qua policy hàng.
- `20261019100000_harden_public_function_acl.sql` L38–39 vẫn GRANT RPC cho authenticated.
- Kịch bản static: TKYK cùng clinic biết visit UUID ngoài bác sĩ được phân có đường `/rest/v1/rpc/read_prescription_draft` đọc draft dù raw table đã có restrictive policy. Đây là mặt truy cập bổ sung cùng vấn đề object-scope của SEC-011; không tạo ID mới.
- Chắc chắn: confirmed_static; chưa gọi role query/HTTP cho nhánh draft này, không khẳng định khai thác production.
- Nghiệm thu cần bao gồm RPC, không chỉ các route FastAPI: TKYK ngoài phân công bị từ chối/không nhận draft; bác sĩ và thư ký đúng phạm vi vẫn đọc hợp lệ.

## Vùng đã khép ở độ sâu chọn lọc

- Grant/RLS mới 14–19/10: không thấy client write policy mới trong pattern scan; stock policies/ACL cũ được migration 19/10 thu lại. Không kết luận mọi ràng buộc kho đã an toàn.
- `clinic_floor`: composite FK đảm bảo floor cùng clinic/location; trigger invoker có search_path và explicit deny execute client; no new SECURITY DEFINER. Backfill role scope là lựa chọn nghiệp vụ, chưa thấy app path gây vượt quyền độc lập.
- `so_no`: trigger khóa advisory theo clinic+visit trước khi kiểm balance; append-only; RLS/grants đọc service_role. Không nâng nhận xét thiếu patient composite FK thành lỗ hổng khi chưa có app path đưa sai bệnh nhân.
- Company invoice/MISA/hide notification: service-role-only read policies hiện tại; không báo policy service_role có current_clinic_ids là chốt tenant thực, vì role bypass RLS. App query scope vẫn cần audit riêng.
- `drug_ma_vach` và `thuoc_quy_doi`: authenticated đọc reference tenant-scoped; chưa thấy trả số tồn/giá vốn hay mutation qua RPC từ các đoạn đã đọc, không đếm lại stock exposure đã được vá.

## Giới hạn và bàn giao

Chưa semantic-read toàn bộ migration mới; coverage đánh scanned trung thực. Không chạy DB/probe thêm ở vòng này. Không kiểm cấu hình ACL runtime/prod mới. Bước tiếp nếu cần: tái hiện RPC draft bằng TKYK synthetic trên DB tạm; kiểm provisioning contract và non-Dr4Women bootstrap như một acceptance suite, không chạy lại lịch sử trên DB thật.
