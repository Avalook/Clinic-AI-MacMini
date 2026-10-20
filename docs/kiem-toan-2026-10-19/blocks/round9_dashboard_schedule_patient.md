# Round 9 — Dashboard đặt lịch, tiếp đón và bệnh nhân

Trạng thái: hoàn tất trên snapshot tĩnh `956ba4f236b1c92f1280d2097018c199e90ce8c7` tại `/tmp/clinicai-audit-main-956ba4f2`. Đã đối chiếu SHA-256 và số dòng của cả 49 candidate trong `MAIN-PHAM-VI.json`. Bằng chứng source chỉ lấy từ snapshot ghim; không đọc working tree bẩn làm source evidence.

## Kết quả

Ghi nhận bốn ứng viên cần triage: (1) kết quả trùng bệnh nhân cũ vẫn thao tác được sau khi đổi truy vấn hoặc khi truy vấn mới lỗi; (2) response tải phường trả muộn có thể ghép phường của tỉnh trước vào payload tỉnh hiện tại; (3) màn ngoại lệ ca trực có thể giữ bản ghi của ngày cũ và huỷ theo ID mà không ràng buộc ngày; (4) gỡ roster vẫn tiến hành khi preview lỗi/không hợp lệ, và preview không được khoá với mutation thực tế. Kịch bản, ảnh hưởng, khuyến nghị, điều kiện chấp nhận và giới hạn được ghi trong `round9_dashboard_schedule_patient.findings.json`.

Các ID `CAND-R9-DASH-SCHED-*` chỉ là ID ứng viên trong block, chưa phải ID canonical.

## Cross-check duplicate

- `PatientListView.tsx` và `doctor/board/LuotKhamTruoc.tsx` giữ context lượt khám cũ khi đổi bệnh nhân; cùng bản chất với FE-007 nên không tạo finding mới.
- CLIN-028/CLIN-029 ở `AppointmentBooking.tsx`, CLIN-027 ở checkout, và FE-001/CLIN-013 trong form bệnh nhân đã được đối chiếu; không nhân đôi.
- FE-008 thuộc bảng quyết định ở `/ban-kham`, không phải hàng đợi đặt lịch ở lát cắt này.

## Độ phủ và giới hạn

`round9_dashboard_schedule_patient.coverage.json` liệt kê từng candidate với SHA-256, số dòng, range đọc và trạng thái. Hai file `AndrologyReview.tsx` và `ServiceFormEngine.tsx` được ghi nhận là đã cover ở round8, không tạo finding mới. Đã đọc toàn bộ `doctor/board/LuotKhamTruoc.tsx`; hành vi giữ lượt cũ trong lúc đổi bệnh nhân đã được đối chiếu với FE-007 và không tạo finding trùng. BFF/API/service/schema chỉ được đọc tại các đoạn được liệt kê trong `context`, để xác minh hành vi của bốn ứng viên.

Không chạy test, không truy cập DB/production/secrets/PHI, không sửa source/migration. Tác động runtime, dữ liệu thực tế và tần suất race chưa được xác minh.
