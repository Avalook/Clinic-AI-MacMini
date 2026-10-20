# Round 21 — patient PostgREST, dashboard freshness, finance dates, prescription amendments

Checkpoint on exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`.

## Kết quả

- Thêm **SEC-029 MEDIUM**: bảng `patient` được cấp `SELECT` cho role `authenticated`; policy kiểm membership/cơ sở dữ liệu ở clinic, nhưng không kiểm capability/role hoặc giới hạn cột. Caddy chuyển tiếp `/rest/v1/*` tới Supabase gateway; login tạo phiên Supabase cho nhân viên. Đây là đường trực tiếp khác với các endpoint FastAPI ở SEC-027. Chưa gửi PostgREST request, chưa kiểm JWT/gateway runtime, không kết luận truy cập chéo clinic hoặc sự cố production.
- Mở rộng **FE-002** bằng luồng phản hồi thuốc trong khung khách: lần refresh lỗi sau lần tải thành công giữ data và summary cũ, không hiện lỗi. Không tạo finding thứ hai vì cùng pattern stale data không có nhãn freshness.
- Bộ chọn lượt gắn phản hồi thuốc có giới hạn 20 lượt không báo còn dữ liệu; giữ là `PHARMACY-RESPONSE-VISIT-CAP-001` ở STATE vì mức LOW, phụ thuộc ngưỡng dữ liệu và cùng họ list-cap đã lặp.
- Hoàn chuyển khoản được nhóm theo ngày tạo yêu cầu trong báo cáo dù trạng thái tiền thực trả được ghi ở lúc xác nhận; sổ nợ dùng thời điểm event. Giữ `FIN-REFUND-ACCOUNTING-DATE-001` cho tới khi chủ sản phẩm/kế toán chốt ghi nhận theo ngày yêu cầu, ngày chuyển tiền, hay tách pending/completed.
- Đọc trọn `clinic_policy.py` và `dinh_chinh_don.py`. Fallback policy rộng được kiểm tra theo transaction, DB capacity guard, API policy và caller hiện có; chưa đủ căn cứ về sai quyết định vì lỗi DB khiến transaction đặt lịch thất bại và dashboard hiện không gửi doctor/date. Giữ CLINIC-POLICY-001 là câu hỏi độ tin cậy, không nâng thành finding.
- Ba lát chuyên biệt rà tiếp patient/PostgREST, dashboard contract/caller và finance reconciliation. Các test lân cận được đọc, không chạy.

## Coverage và số liệu

Risk register: **158 hồ sơ** — 26 HIGH, 118 MEDIUM, 14 LOW. Trên main ghim: 154 còn hiện diện, 2 xử lý một phần, 2 đã có sửa trong phạm vi đối chiếu.

Ledger 2.890 path: 727 read, 370 traced một phần, 1.257 scanned, 528 inventoried, 8 excluded. Nhóm code-like 2.334 path: 706 read, 351 traced, 1.256 scanned, 21 inventoried. Đây là số lượng path theo cấp độ xem; không phải phần trăm logic đã được hiểu hoặc kiểm thử.

Coverage round 21: 32 path được đọc/trace, gồm 2 full-file reads tại root. Chi tiết exact range, hash và mức đọc nằm trong `round21_coverage.json`. Code ứng dụng, migration và dữ liệu không bị sửa; không dùng DB/API/PostgREST/provider/production, secrets hoặc PHI.

## Tiếp tục

Ưu tiên kiểm ma trận role × capability × clinic/location cho API và PostgREST bằng Supabase disposable từ migration ghim; xác định role nào thực sự cần đọc patient, trường nào cần cho quầy/Realtime, và thêm deny assertions cho vai thiếu capability. Tiếp tục các luồng event/provider/recovery và vùng source còn scanned/inventoried. Sau khi chốt policy kế toán, dùng fixture hai ngày kiểm báo cáo refund, lịch sử thu, sổ nợ và chốt ca. Full source audit vẫn đang làm; HTML/ZIP v0.42 cần rebuild và QA sau checkpoint này.
