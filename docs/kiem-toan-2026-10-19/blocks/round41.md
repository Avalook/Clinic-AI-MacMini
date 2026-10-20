# Round 41 — replay migration, POS retry và ranh giới release V5

Nguồn là Git main ghim `956ba4f236b1c92f1280d2097018c199e90ce8c7`; chỉ đọc source và test. Không chạy ClinicAI test/runtime/API/DB/provider/production.

## INF-008 — mở rộng tác động replay

Exact-main structural scan xác nhận 23 migration có dòng standalone `BEGIN;` và `COMMIT;`. Runner thường nối migration vào transaction rồi ghi ledger; COMMIT bên trong có thể tách schema commit khỏi ledger. Round này đọc mục tiêu 8 migration có DML cấu hình. Ví dụ cụ thể: `20260821000001_ba_ca_lam_viec.sql:68–76` ghi lại tất cả giờ mở/đóng thành 07:00–22:00 cho clinic có cấu hình hours; `20260916000008_vi_tri_lam_viec_kim_nguu.sql:91–95,136–142` áp danh mục qua clinic và cập nhật lại hàng trùng bằng seed. Nếu runner dừng giữa commit và ledger, retry có thể ghi lại cấu hình được quản lý. Đây là khả năng có điều kiện từ static code; không chứng minh clinic nào đã bị ghi đè hay có incident.

## INF-011 — cổng chống gửi POS trùng trước khi bật adapter

Relay giữ row PENDING trong lúc gọi adapter và chỉ ghi SENT sau khi adapter trả về. Nếu provider đã nhận giao dịch nhưng worker dừng trước UPDATE SENT, row có thể được poll lại sau khi advisory lock/session kết thúc. PosPort yêu cầu adapter idempotent theo `clinic_reference`; KiotViet hiện là stub fail-closed, chưa có adapter ngoài được xác minh. Vì vậy đây là readiness gate, không phải lỗi gửi trùng hiện hành. Test được đọc nhưng không chạy và chưa mô phỏng provider-accepted/crash.

## CLIN-020 — policy hold về release V5

Nếu `clinical_release` bao gồm phiếu V5, đường autosave sau RELEASED hiện dùng `luu_luot`/`CHE_DO_MO`; nó không đi qua amendment để thu hồi release và tạo việc CSKH báo lại. Tuy nhiên `QUYET-DINH.md` chưa chốt V5 thuộc release scope hay không. Giữ câu hỏi này làm policy gate, không tạo finding mới và không khẳng định vi phạm lâm sàng.

Coverage, line range và source hash exact-main ở `round41.coverage.json`. Full source audit vẫn chưa hoàn tất.
