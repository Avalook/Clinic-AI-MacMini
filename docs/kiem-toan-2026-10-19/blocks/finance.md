# Kiểm toán tiền, thuốc, kho

Trạng thái: đang kiểm toán static working tree 19/10/2026; chưa kiểm prod/runtime.

## Checkpoint

- Đã đọc hướng dẫn, tạo ledger 27 file finance từ manifest.
- Tiếp theo: payment/bill/refund/tiền thừa, SQL constraints, kê/bán/cấp thuốc và tests.
- Không sửa code ứng dụng. Working tree WIP giảm giá cần tách khỏi prod.

## Checkpoint 2

- FIN-001 tái hiện hàm thuần phân bổ giảm giá WIP hụt tổng; chưa chạy DB.
- FIN-002 xác nhận static LIMIT300 dòng prescription cắt trước nhóm; UI không dùng bi_cat.
- Bác bỏ cách suy luận audit cũ rằng void thuốc tự là lần rút tiền thứ2: contract phân biệt void/refund/return. Dịch vụ còn có chặn void sau refund.
- Tiếp: kho nhập/điều chỉnh/thuốc, quyền giảm giá, retry discount; kiểm chứng claims void dịch vụ/addon checkout với agent clinical.

## Root checkpoint 2026-10-19T17:46:43.192198+07:00

Khối chưa hoàn tất. Nội dung agent ban đầu là baseline543b9787+WIP; ưu tiên PHAT-HIEN.json/main_validation cho kết luận mới.
- FIN-001: addressed_on_main — Main dùng largest remainder; probe độc lập trả [100,99,1], tổng200. Lỗi tái hiện chỉ thuộc WIP nhánh đang mở. Cần tránh mang WIP cũ đè implementation main.
- FIN-002: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- FIN-003: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
Tiếp theo: TIEP-TUC.md và MAIN-PHAM-VI.json. Không tự nâng scan thành đọc sâu.

## Root checkpoint 2026-10-19 — finance round 4

- FIN-004: đọc trọn `hoan_tien_service.py` và đường trigger/endpoint được chọn; đã xác nhận số học không giảm có thể hoàn 100002đ cho khoản thu 100001đ với hai lần hoàn 0,5 trên DB tổng hợp.
- FIN-005: static trace `QuayThuService.lich_su` → `CashierScopeService`/`doc_khoang_ngay` → cashier API → `LichSuThu` và CSV/XLSX. Mỗi tập thu/hoàn LIMIT 3000; chỉ warning log; UI/export dùng subset. Quản lý tối đa 92 ngày; nhân viên quầy một ngày/ca. Chưa seed vượt ngưỡng hoặc kiểm dữ liệu production.
- Root đã đọc các luồng PaymentService/routers, invoice, history/export được chọn; các file được đánh dấu `traced` trong `MAIN-PHAM-VI.json` chỉ cho những đoạn nêu tại `method`, không phải toàn module.
- Còn lại: cash reconciliation/reporting, payment callers not reviewed, clinic-level billing configuration, payment concurrency/retry, migration + restore chain and pharmacy return/correction paths.
- Kiểm ứng viên CSV formula-injection: `PatientCreateDTO.full_name` và service catalog chuẩn hoá whitespace, lý do hoàn tiền strip; XLSX export ghi string cells ở kiểu text. Không tạo finding mới; chưa thử spreadsheet app hoặc locale-specific formula prefixes.


## FIN-006 — cắt kỳ xuất hoá đơn, 19/10/2026

- Trên exact main, LichKhoangNgay cho chọn hai mốc không giới hạn; XuatHoaDon gửi nguyên tu/den. XuatHoaDonService đi qua DanhSachHoaDonService.xem, nơi dùng doc_khoang_ngay; helper cắt đầu kỳ về den trừ 92 ngày, tương đương 93 ngày inclusive. Preview và XLSX chỉ dùng dữ liệu đã cắt; UI chỉ hiện tổng/đếm và không đọc data.tu/data.den.
- AST thực thi đúng helper từ source với stdlib: kỳ 01/01–19/10/2026 bị rút còn 19/07–19/10, 199 ngày bị bỏ; kỳ 19/10/2025–19/10/2026 bỏ 273 ngày. Đây không phải kiểm thử route/DB/UI.
- FIN-006 là MEDIUM/confirmed_static, không chứng minh đã có file thật hoặc hồ sơ kê khai thiếu. Đã đưa vào PHAT-HIEN.json; 5 file mới thành `traced` một phần trong main ledger. Tiếp tục test API/UI và các luồng reconciliation trước khi kết luận finance hoàn tất.

- Mở rộng FIN-006 sau khi đọc caller: `BaoCaoCuoiNgayService.doc_khoang` dùng cùng helper; JSON/CSV/XLSX cuối ngày cũng truy vấn kỳ hiệu lực đã rút. UI giữ bộ lọc requested; khối summary/link dùng loc từ state, còn bản in và tên file có thể thể hiện ngày effective. Chỉ trace tĩnh ngoài phép chạy helper; chưa gọi báo cáo/export runtime.

## v0.23 — giữ tiền thừa

FIN-009: giu_lai không kiểm closed_at dù huy_giu_lai có; static, cần xác nhận luồng tăng dư sau checkout. Hoàn theo created_at được ghi rõ trong module, nên không nâng thành defect.

## Round 36
FIN-003 được mở rộng sang thêm vật tư có tính tiền với retry làm tăng số lượng; FIN-005 thêm tab giao dịch có cap 1.000 và tổng chỉ tính trên subset. Chi tiết exact-main ở blocks/round36.coverage.json; không phát sinh ID mới, không có production occurrence evidence.

## Round 39

FIN-018 LOW: hai hóa đơn song song của cùng khách có thể tạo hồ sơ công ty trùng vì chỉ khóa payment_cycle, không khóa identity profile; migration hiện chỉ có index thường clinic+patient. Static only, chưa chạy concurrency, không khẳng định production; chốt identity/upsert contract. FE-022 cũng mở rộng sang history LIMIT 100.
