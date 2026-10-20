# Frontend — checkpoint 19/10/2026

Trạng thái: đang kiểm chứng chéo; đã quét pattern toàn khối, chưa đọc thủ công toàn bộ 806 file. Không browser/runtime test.

## Phát hiện đã ghi

- FE-001 MEDIUM: draft định danh bệnh nhân còn localStorage sau logout (đã gửi security kiểm chéo).
- FE-002 MEDIUM: bảng hành trình giấu lỗi refresh khi có dữ liệu cũ.
- FE-003 MEDIUM: tìm kiếm không với ngoài 300 lượt nhưng nhãn hướng dẫn sai.
- FE-004 MEDIUM: riêng KPI endpoint hỏng thành không ai đặt lịch, không có error banner.

## Đã bác / gửi kiểm chéo

- E2E intake-day-simulation có guard host production cũ, nhưng main hiện không thực thi các phase ghi: không tính thành lỗi ghi prod hiện hành.
- PhieuKhamLuot/onLuu bỏ qua hen_tai_kham.trang_thai=LOI: đã gửi clinical để ghi một finding xuyên lớp, không duplicate.
- guiDon lưu xong rồi napDon lỗi trả ok:true có thể để dòng mới thiếu ID và lần sau tạo trùng: đã gửi finance kiểm backend, chưa kết luận.

## Điểm mạnh đã đọc

- API proxy chuyển tiếp token, X-Location-ID, Idempotency-Key khi caller cung cấp; proxy mutation gắn request ID và log bỏ query có thể chứa PII.
- admin/users hỏi quyền account.manage và target staff qua backend, thay vì tin cookie vai.
- WorklistResult phân biệt chưa có phiên/bị từ chối/không kết nối; BangViecCanXuLy có expected_version và không giả vờ complete khi API thất bại.
- SSE chung có visibility catch-up, debounce, chỉ báo kết nối; autosave HangDoiLuu tuần tự và retry, tránh thêm dịch vụ hạ tầng.

## Chưa kiểm / bước kế tiếp

1. Chốt phản hồi security/finance; kiểm số dòng và hash mọi finding.
2. Rà useTuLuu và recipe ID/retry, screens thu tiền/phòng dịch vụ, API proxy manual còn lại.
3. Runtime browser có network fault injection, logout storage, concurrent responses theo ngày chưa chạy.
4. Productization: metadata/manifest/print còn Dr4Women; ma-vi-tri chuẩn hoá về mã mẫu là coupling cấu hình cần thiết kế lại, chưa kết luận bug.

## Giới hạn

Quét pattern không tương đương đọc full hay chứng minh không có lỗi. Không kiểm production/deployed SHA; tests có tên tương ứng chưa được thực thi bởi khối này.

## Root checkpoint 2026-10-19T17:46:43.192198+07:00

Khối chưa hoàn tất. Nội dung agent ban đầu là baseline543b9787+WIP; ưu tiên PHAT-HIEN.json/main_validation cho kết luận mới.
- FE-001: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- FE-002: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- FE-003: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- FE-004: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
Tiếp theo: TIEP-TUC.md và MAIN-PHAM-VI.json. Không tự nâng scan thành đọc sâu.


## Round3 — FE-006 đã truy vết độc lập trên main

Candidate MEDIUM, confirmed_static: lỗi request ghi `da_xem_luc` không được thử lại khi component cùng visit còn mounted. Chỉ chốt cho actor đúng vai và response thất bại trước commit/HTTP non-success; không gọi false-seen hoặc tự đóng việc. SSE làm mới props nhưng Set giữ nguyên; reload/remount mới clear. Không có runtime test trong khối. Chi tiết source/hash/caller/limit ở `frontend-round3.md` và `PHAT-HIEN.json`; coverage vòng này đã merge vào main ledger sau đối SHA.


## v0.18 — bổ sung trace

FE-007: patient history/phản hồi thuốc có thể còn từ A khi chọn B và mở visit cũ trong ngữ cảnh B; read-only path, chưa browser fault-test. FE-008: endpoint cho-quyet lỗi làm panel bác sĩ quyết trả null/ẩn, dù backend item chưa mất; chưa fault-injection. Cả hai exact main 956ba4f2, canonical evidence ở PHAT-HIEN.json; không kết luận production incident.

## v0.22 — trạng thái nhận phòng và hàng chờ duyệt

- FE-010: UI dùng nhan_duoc làm nguồn hành động, trong khi helper bỏ qua accepting=false; count lọc accepting nhưng grouped tinh_so không lọc. Lệnh ghi vẫn chặn ROOM_NOT_ACCEPTING. Pure-helper probe RUN-045 tái hiện nhan_duoc=true nhưng count=0; chưa HTTP/browser test.
- CLIN-023 UI hiển thị count từ mảng đã nhận mà không biết query bị giới hạn 200/60 ngày.
- Cần HTTP/browser tests với phòng tạm ngừng và fault/data-cap tests cho hàng duyệt.

## v0.23 — sửa lịch

CLIN-028: doctorId không thuộc dirty check. CLIN-029: location dropdown có thể đổi nhưng không qua dirty check/PATCH/proxy; success đóng modal. Static, cần browser/API regression.

## Round 36
FE-023 được mở rộng với xóa/khôi phục tệp và checkout: UI khẳng định lỗi sau exception trong khi backend có nhánh already-state. Giữ mức LOW, không kết luận duplicate side effect; không chạy UI fault injection.

## Round 38 — appointment classification

CLIN-055 bổ sung rủi ro state bất đồng bộ: response service-history null/lỗi không reset patientKind, còn canBook không chờ lookup và POST gửi state hiện hành. Đọc exact-main; không chạy browser/UI/API hoặc fault injection. Khuyến nghị gắn lookup với cặp patient-service/request generation và chặn submit khi pending/unknown. Coverage: `blocks/round38.coverage.json`.

## Round 39

FE-004 mở rộng: lịch sử công ty trên hóa đơn gom non-OK/JSON lỗi thành empty state “Chưa có thay đổi nào”. FE-022 mở rộng: lịch sử này LIMIT 100 mà UI không có paging. Exact-main, chưa probe HTTP/browser hoặc seed >100; xem `blocks/round39.coverage.json`.
