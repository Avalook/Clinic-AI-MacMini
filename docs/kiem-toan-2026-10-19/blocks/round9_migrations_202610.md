# Round 9 — kiểm toán migration tháng 10 (static)

**Nguồn ghim:** exact SHA 956ba4f236b1c92f1280d2097018c199e90ce8c7, snapshot tại /tmp/clinicai-audit-main-956ba4f2. Đã xác minh 101 migration 202610 trong snapshot byte-identical với worktree Git sạch ở SHA này. Đã đọc toàn văn cả 101 file, tổng 12.835 dòng. Chỉ kết luận về tranche 01–19/10/2026; ledger chi tiết, SHA-256 và phạm vi đọc nằm trong coverage JSON.

**Giới hạn:** chỉ đọc source và bài kiểm SQL liên quan; không kết nối DB, PostgREST, staging hay production; không đọc secrets/PHI; không chạy harness; không sửa app, migration hay test. Runner được đọc tĩnh vì nó quyết định transaction boundary và ghi ledger.

## Ứng viên phát hiện

### DB-006 — migration tự COMMIT trước khi runner ghi sổ

Bảy migration tháng 10 tự chứa BEGIN/COMMIT: 20261010100001, 20261016400000, 20261018200000, 20261019100000, 20261019120000, 20261019130000 và 20261019140000. Runner lại ghép theo thứ tự BEGIN → nội dung file → INSERT vào supabase_migrations.schema_migrations → COMMIT. Với một file có COMMIT riêng, giao dịch chứa phần DDL kết thúc trước khi runner ghi version. Nếu phiên hỏng hoặc INSERT ledger lỗi sau mốc đó, DDL đã được commit nhưng ledger chưa có version; nhánh lỗi của runner lại nói toàn migration đã rollback. Nhiều bước trong các file này có thể chạy lại, nên bằng chứng hiện tại là ledger và thông báo lỗi có thể sai sự thật, không phải dữ liệu chắc chắn đã hỏng.

**Tác động theo mục tiêu:** trạng thái migration không còn là bằng chứng đầy đủ của schema, kéo dài thời gian chưa biết và làm việc phục hồi/đối soát dễ bị gián đoạn.

**Đề xuất:** chỉ định một nơi sở hữu transaction boundary. Nếu runner sở hữu thì bỏ BEGIN/COMMIT khỏi migration; nếu migration tự quản thì runner phải ghi sổ trong cùng transaction đó và không mở transaction bao ngoài. Thêm bài kiểm có lỗi sau khi DDL kết thúc nhưng trước ghi ledger.

### DB-007 — hai sổ công nợ không buộc bệnh nhân trùng với lượt

Cả cong_no ngày 01/10 và so_no ngày 14/10 đều giữ clinic_patient_id bằng FK riêng tới patient, còn visit được ràng buộc bằng khóa (clinic_id, visit_id). Không có kiểm tra INSERT buộc clinic_patient_id bằng bệnh nhân đang gắn với visit. Trigger cong_no chỉ bảo vệ định danh khi UPDATE/DELETE; trigger so_no kiểm phép cộng số dư và khóa theo lượt. Vì vậy backend có thể ghi một nợ với visit hợp lệ nhưng patient_id của người khác mà các FK riêng vẫn hợp lệ.

**Tác động theo mục tiêu:** số nợ có thể bị gắn nhầm người trong lịch sử hoặc phép chiếu tài chính, làm sai phần “thực tế nhìn thấy được” và khiến quyết định đối soát dựa trên chủ thể sai. Đây là khả năng schema cho phép; chưa có bằng chứng backend đã ghi dòng sai.

**Đề xuất:** ép quan hệ patient–visit–debt ngay trong DB, rồi thêm test SQL tổng hợp cho cả sổ cũ và sổ hai chiều với patient đúng, patient sai cùng clinic và sai khác clinic.

### SEC-019 — lịch sử biểu mẫu và ghi chú lượt đọc được theo clinic, chưa theo vai

form_instance_lich_su lưu JSON của phiên bản biểu mẫu cũ; luot_ghi_chu lưu nội dung tự do theo visit. Cả hai bật RLS, nhưng policy cho authenticated chỉ lọc clinic_id bằng current_clinic_ids() và grant SELECT trực tiếp cho authenticated. Policy không kiểm vai lâm sàng hay assignment bệnh nhân. Bài kiểm role hiện có chỉ chứng minh Reception, cashier và management không đọc clinical_record; nó không nêu hai bảng lịch sử/ghi chú này.

**Tác động theo mục tiêu:** thành viên trong cùng clinic nhưng ngoài nhóm lâm sàng có khả năng đọc nội dung y khoa/lịch sử ngoài phạm vi cần dùng. Chính sách tiếp tục giới hạn clinic; không có bằng chứng đọc chéo tenant hoặc dữ liệu thật đã bị truy cập.

**Đề xuất:** chủ nghiệp vụ xác nhận ma trận vai; sau đó bỏ quyền đọc trực tiếp hoặc áp role + patient-assignment guard, và bổ sung test role/assignment qua SQL và PostgREST. Giữ đường FastAPI mà các màn được duyệt cần dùng.

## Đối chiếu trùng lặp và câu hỏi thiết kế

Đã so với PHAT-HIEN.json và không dùng lại ID. DB-003 nói migration giảm giá WIP không idempotent nhưng trạng thái trên exact pinned main đã được đánh dấu addressed; không mở lại. DB-005 là vấn đề provision tenant, khác liên kết bệnh nhân–lượt của DB-007. SEC-011 là thiếu assignment trong các API FastAPI; SEC-019 là quyền đọc bảng trực tiếp, độc lập với router. SEC-018 có cùng mẫu clinic-only policy nhưng áp dụng cho contact/kin PII, khác bảng và loại dữ liệu với SEC-019.

**Câu hỏi thiết kế tách riêng:** vai nào được phép đọc lịch sử form_instance và ghi chú tự do của lượt? Migration không nêu danh sách vai. Cần chủ nghiệp vụ chốt trước khi chọn policy đích; ứng viên SEC-019 chỉ mô tả quyền hiện tại và khoảng trống kiểm thử.

## Kiểm soát và giới hạn

Các test SQL đã đọc gồm inventory_write_guards, multi_tenant_foundation, stock_postgrest_read_acl, tenant_scoped_rls, public_function_acl, payment_audit và role_scoped_clinical_read. Chúng cho thấy các guard tenant, kho và clinical hiện có nhưng không có bài kiểm SQL chuyên biệt cho quan hệ patient–visit trong cong_no/so_no; bài kiểm role không bao phủ hai bảng October nêu trên. Không chạy các test này.

Coverage JSON liệt kê toàn bộ 101 migration, SHA-256, số dòng, range đã đọc, tình trạng full read, các test SQL và runner đã đọc tĩnh. Kết quả không xác nhận schema hiệu lực hoặc hành vi runtime ở bất kỳ môi trường nào.

