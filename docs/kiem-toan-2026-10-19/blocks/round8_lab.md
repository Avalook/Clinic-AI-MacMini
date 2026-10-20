# Round 8 — kết quả xét nghiệm / file kết quả (checkpoint hoàn tất lát cắt)

Nguồn cố định: snapshot `main` SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7` tại `/tmp/clinicai-audit-main-956ba4f2`; căn cứ danh mục `MAIN-PHAM-VI.json`. Đây là audit tĩnh của luồng file kết quả CSKH/đối tác. Không dùng DB, production, secret hoặc dữ liệu bệnh nhân; không sửa ứng dụng hay migration. Không khẳng định đã đọc toàn bộ repository.

## Finding LAB-001 — kết quả có thể đã commit nhưng giao diện khẳng định “chưa được lưu”, khiến retry sinh file thứ hai

**Mức:** MEDIUM · **Độ chắc:** cao về đường code không idempotent; điều kiện mất phản hồi sau commit là tình huống phân tán hợp lý nhưng chưa tái hiện runtime ở lát cắt này.

Khi kết nối/response của BFF bị lỗi, `chuyenTiepTaiLen` reject trên `req` hoặc response error; route đổi mọi lỗi đó thành HTTP 502 với khẳng định file “CHƯA được lưu, hãy tải lại” (`src/dashboard/lib/chuyen-tiep-tai-len.ts:27–43`; `src/dashboard/app/api/cskh/ket-qua/route.ts:75–82`). Lỗi response không chứng minh FastAPI chưa commit: FastAPI nhận multipart rồi gọi service; service chuyển tệp sang đường cuối, insert dòng `tep_ket_qua` và emit `result_file.uploaded` trong transaction, chỉ sau đó mới trả ID (`src/clinicai/api/v1/routers/cskh.py:729–771`; `src/clinicai/services/tep_ket_qua_service.py:890–1000`). BFF không có reconciliation/read-after-uncertain-result.

UI không gửi idempotency/operation ID; khi 502 nó dừng vòng tải và hiện lỗi cho đúng tên file (`src/dashboard/app/(dashboard)/customers/TepKetQua.tsx:186–214`). Endpoint FastAPI không nhận `IdempotencyGuard`/key; service tạo khóa file mới bằng UUID cho mỗi lần gọi (`src/clinicai/services/media_service.py:282–292`) rồi tạo record mới, còn DB chỉ unique theo `(clinic_id, khoa)` chứ không theo upload intent/hash (`src/clinicai/services/tep_ket_qua_service.py:908–945`; `supabase/migrations/20260809000008_tep_ket_qua.sql:21–63`). Vì vậy nếu lần đầu commit nhưng receipt thất lạc, thao tác tải lại có thể tạo file thứ hai cùng nội dung, thêm sự kiện upload và cho thấy nhiều kết quả cho reviewer/CSKH.

Test tích hợp hiện có thực hiện lần upload thứ hai cùng bytes và ghi chú retry, nhưng chỉ xác nhận không sinh thêm consultation/queue; không assert số record file hoặc thử lỗi response sau commit (`src/tests/services/test_full_chi_dinh_slice_ab_db.py:636–658`). Đây là khoảng trống test cho receipt/file identity, không phải bằng chứng sự cố production.

**Cải tiến đề xuất:** tạo upload-intent ID bền ở client, chuyển qua BFF tới FastAPI và lưu receipt có unique `(clinic_id, actor_id, intent_id)` cùng kết quả file; cùng intent trả lại cùng file ID, khác hash trả conflict. Với trạng thái mạng không rõ, UI nói “chưa xác định đã lưu hay chưa” và tra cứu intent trước khi cho retry. Không dedupe chỉ bằng SHA-256 vì cùng nội dung có thể hợp lệ ở hai lần khám/ý định khác nhau.

**Controls/giới hạn đã kiểm:** quyền và clinic/patient/order association được kiểm tra; file được đặt khóa hệ thống và SHA-256; insert + outbox event ở cùng transaction; các hành động approve/revoke/delete/restore có kiểm trạng thái/quyền, lý do và actor audit; migration không cấp quyền ghi trực tiếp cho client. Các control này giảm nguy cơ sai bệnh nhân/ghi thiếu audit nhưng không làm upload retry idempotent. Chưa kiểm production incidence hoặc mô phỏng socket drop sau commit.

## Phạm vi đã đọc

- Đọc semantic toàn bộ `src/clinicai/services/tep_ket_qua_service.py` (1–1900): nhận file, quyền/liên kết khách-lịch-chỉ định, ghi file/DB/event, xác nhận/từ chối/thu hồi, danh sách/xóa mềm/khôi phục, xem/đánh dấu đã xem, cho phép gửi/đánh dấu gửi, queue chờ xác nhận.
- Đọc toàn bộ BFF `src/dashboard/app/api/cskh/ket-qua/route.ts` và `src/dashboard/lib/chuyen-tiep-tai-len.ts`; đọc các đoạn liên quan trong router CSKH, UI khách hàng, migration và tests được liệt kê trong `round8_lab.coverage.json`.
- Kết luận về H7/thu hồi partner result đã được ghi trong `scheduling-result-revoke-h7-followup.md` và không lặp thành finding ở block này.
- Chỉ lát cắt kết quả/file được đóng ở đây; coverage audit repository tổng thể vẫn phụ thuộc các block khác và kiểm kê `MAIN-PHAM-VI.json`.
