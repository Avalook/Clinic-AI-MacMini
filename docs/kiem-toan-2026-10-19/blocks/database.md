# Kiểm toán database — đang làm

Đã kiểm kê phạm vi; chưa có kết luận. Đang kiểm chuỗi migration, tenant/RLS, bất biến và bootstrap.

## Checkpoint
Bước kế tiếp: quét cấu trúc 391 SQL/config, dựng danh sách định nghĩa cuối và ưu tiên quyền/tiền/lịch.
Runtime: chưa chạy.

## Root checkpoint 2026-10-19T17:46:43.192198+07:00

Khối chưa hoàn tất. Nội dung agent ban đầu là baseline543b9787+WIP; ưu tiên PHAT-HIEN.json/main_validation cho kết luận mới.
- DB-001: partially_addressed_on_main — Đã tái hiện trên DB tạm: giả lập GRANT EXECUTE authenticated từ restore cũ, áp migration ACL main trong transaction rồi rollback; anon=false nhưng authenticated=true cho lieu_trinh_go_buoi. Bản vá thu quyền PUBLIC/anon nhưng không thu quyền authenticated đã cấp trực tiếp cho helper này. Không gọi RPC ghi hay kiểm prod.
- DB-002: partially_addressed_on_main — Main bỏ blanket GRANT EXECUTE và chạy lại migration ACL hàm/kho sau restore; vẫn GRANT ALL TABLES cho authenticated. Hai bước ACL mới không tái lập hạn chế cột clinical_record.prescription_draft/clinic.settings. Phần quyền cột còn cần sửa/kiểm role.
- DB-003: addressed_on_main — Main cùng tên migration đã dùng DROP CONSTRAINT IF EXISTS rồi ADD; đây là lỗi của WIP khác nội dung trên nhánh đang mở. Không yêu cầu sửa lại bản main từ finding này.
- DB-004: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
Tiếp theo: TIEP-TUC.md và MAIN-PHAM-VI.json. Không tự nâng scan thành đọc sâu.

## Round 40 — migration ledger atomicity

INF-008 mở rộng sang `apply-pending-migrations.sh`: runner bọc file+ledger trong transaction, nhưng structural scan trên SHA ghim thấy 23 migration có standalone `BEGIN;`/`COMMIT;`; `COMMIT` nội bộ có thể kết thúc wrapper trước row ledger. Chỉ ghi nhận cửa sổ retry nếu bị dừng; chưa fault-inject và không chứng minh migration hiện tại làm hỏng dữ liệu. Xem `blocks/round40.md` và coverage.
