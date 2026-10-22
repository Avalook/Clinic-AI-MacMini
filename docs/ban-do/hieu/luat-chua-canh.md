# Luật tiền, kho và kế toán chưa có test canh trỏ trực tiếp

Đối chiếu từ ghi chú ở worktree PR #521 (`docs/ban-do/hieu/tep/*.json`, trường `luat`) với `docs/ban-do/hieu/test/*.json`, trường `canh`. Một luật được xem là đã có tham chiếu khi ít nhất một mục `canh.tep_code` nêu đúng đường dẫn tệp chứa luật đó. Vì vậy danh sách dưới đây là các luật chưa có tham chiếu trực tiếp theo tệp; test có thể đang canh gián tiếp qua helper nhưng không khai báo đường dẫn này, nên cần rà khi chọn test bổ sung.

**Tổng:** 156 luật ở 28 tệp; đã so với 4552 mục `canh` trong các ghi chú test. Ghi chú nguồn chứa 1.101 luật thuộc năm khối; các luật có tệp được nhắc ở `tep_code` không liệt kê ở đây.

> Mỗi số là dòng trong mã nguồn theo ghi chú hiện có; trước khi viết test hãy mở code trên nhánh `codex/test-canh-luat-tien-kho` và xác nhận số dòng còn đúng. Danh sách chưa hàm ý có lỗi trong code.

## payment — 82 luật

### `src/clinicai/services/hoa_don_excel.py`
- Dòng 21: Trên file, cả 'TRANSFER' và 'QR' đều hiện là 'Chuyển khoản' (không tách QR riêng). Hình thức lạ ngoài ba mã CASH/TRANSFER/QR thì in nguyên mã thô.
- Dòng 53: 'Đã tồn (ngày)' = số ngày trọn 24 giờ từ lúc phát sinh đến giờ xuất file, không bao giờ âm (việc có giờ ở tương lai thành 0). Không đọc được thời điểm thì để trống.
- Dòng 82: Cột 'Số việc tồn' ở sheet 'Theo khách' là số việc trong viec_ton của khách đó (đếm, không phải tiền). Sheet 'Việc còn tồn' lấy từ data['viec_ton'] chung, thiếu thì để trống.
- Dòng 113: Mỗi dòng của phiếu thu vào sheet 'Dòng phiếu' với cột Phiếu = 'Thu', có đủ Tổng tiền hàng, Giảm giá, Thành tiền; cột 'Bỏ sau thu' ghi 'Có' nếu dòng đã bị bỏ, không thì để trống.
- Dòng 128: Sheet 'Sau khi thu' lấy từ su_kien của từng phiếu. Mã loại sự kiện được đổi sang chữ (Đổi hình thức, Bỏ dịch vụ sau thu, Hoàn tiền, Huỷ phiếu); mã lạ in nguyên.
- Dòng 162: Dòng của phiếu hoàn nằm chung sheet 'Dòng phiếu' với cột Phiếu = 'Hoàn' (dòng 167); Tổng tiền hàng và Giảm giá để trống (None), chỉ có Thành tiền, cột 'Bỏ sau thu' để trống.

### `src/dashboard/app/(dashboard)/_lam-viec/KhoanNoKhiVe.tsx`
- Dòng 101: [TSX quyết] 'Thu ngay — dịch vụ/thuốc' chỉ hiện khi choThuNgay=true, lượt có dòng loại đó, máy chủ cho thu ngay loại đó VÀ có quyền payment.service.collect / payment.medicine.collect. Không có nút nào thì hiện 'Nhờ thu ngân thu, hoặc' (dòng 287).
- Dòng 110: Còn nợ thì máy chủ chặn check-out; khối chỉ vẽ cờ chặn. Nợ chặn riêng (chan_no), dữ liệu cũ thiếu chan_no thì dùng cờ chặn chung. Nút Thu ngay / Ghi nợ chỉ hiện khi chanNo đúng (dòng 280-294).
- Dòng 175: Đã ghi nợ mà phu_du=false (phát sinh khoản mới) → hiện 'Đã ghi nợ (chưa gồm khoản mới)'. Ví dụ ghi nợ 300.000đ, thêm chỉ định 200.000đ → cần ghi nợ lại cho đủ 500.000đ.
- Dòng 204: [TSX quyết] Nút Hoàn tiền thừa và Giữ lại chỉ hiện khi tt.chan=true (còn tiền thừa chưa xử lý) và không có hộp lý do đang mở (dòng 202). Hết chặn thì chỉ còn 'Huỷ giữ lại' nếu đã giữ.
- Dòng 252: [TSX quyết] Nút xác nhận Ghi nợ / Giữ lại / Huỷ ghi nợ bị khoá nếu lý do < 3 ký tự (sau cắt khoảng trắng). 'Huỷ giữ lại' không qua ô này.
- Dòng 295: [TSX quyết] Nút 'Huỷ ghi nợ' hiện bất cứ khi có bản ghi nợ (không phụ thuộc chanNo), mở hộp lý do.

### `src/dashboard/app/(dashboard)/_lam-viec/NutHoanTienThua.tsx`
- Dòng 48: [TSX quyết] Chữ trên nút: đã chọn hình thức thì hiện toàn bộ số thừa (tong) theo hình thức đó, ví dụ 150.000đ chuyển khoản; chưa chọn thì liệt kê từng hình thức có số >0 (100.000đ chuyển khoản · 50.000đ tiền mặt), thiếu dữ liệu thì ghi 'theo hình thức khách đã trả'.
- Dòng 54: [TSX quyết] Hiện lời nhắc 'Chờ chuyển' khi hình thức chọn khác tiền mặt; nếu chưa chọn thì hiện khi không có số theo hình thức (không biết) hoặc có hình thức khác tiền mặt.
- Dòng 64: Số tiền hoàn do máy chủ quyết (đúng số còn thừa); màn chỉ gửi hanh_dong, visit_id, hinh_thuc, không gửi số tiền.
- Dòng 66: Không chọn hình thức thì màn gửi hinh_thuc = null; máy chủ tự hoàn theo hình thức từng lần thu gốc (việc chia do máy chủ làm, màn chỉ hiển thị số theoHinhThuc máy chủ đưa). Chọn 'Tiền mặt' hoặc 'Chuyển khoản' thì gửi đúng giá trị đó.
- Dòng 99: Màn chỉ nhắc: hoàn chuyển khoản là khoản 'Chờ chuyển', chuyển xong phải xác nhận kèm mã giao dịch ở mục Hoàn tiền của phiếu thu (việc tạo khoản chờ do máy chủ).

### `src/dashboard/app/(dashboard)/reports/KhoiChotCa.tsx`
- Dòng 84: [TSX quyết] Dòng 'Sau khi chốt có thêm' chỉ hiện khi thu, huỷ hoặc hoàn sau chốt có ít nhất một khoản khác 0; số do máy chủ tính, huỷ/hoàn sau chốt tính vào ca đang làm.
- Dòng 87: [TSX quyết] Dòng 'Điều chỉnh ca trước' hiện khi có ít nhất 1 phiếu của ca đã chốt bị huỷ trong khoảng xem, kể cả khi không xem đúng một ca. Ví dụ: 2 phiếu, tổng -500.000đ.
- Dòng 93: [TSX quyết] Chỉ hiện phần chốt/mở khoá khi máy chủ báo xem_mot_ca. Nếu không, ẩn hẳn. Nếu đã có bản chốt thì hiện trạng thái đã chốt, ngược lại hiện nút 'Chốt ca'.
- Dòng 111: [TSX quyết] Nút 'Mở khoá ca' chỉ hiện khi quanLy = true (cờ từ máy chủ); người khác chỉ thấy trạng thái đã chốt.
- Dòng 116: Mở khoá gửi id lần chốt + lý do (chu nguyên văn, chưa cắt khoảng trắng); máy chủ quyết quyền và việc mở.
- Dòng 119: [TSX quyết] Mở khoá ca bắt lý do tối thiểu 3 ký tự (sau khi cắt khoảng trắng hai đầu) mới cho bấm đồng ý.
- Dòng 141: Chốt ca gửi ngày + ca + cơ sở + ghi chú; ghi chú không bắt buộc nên có thể gửi chuỗi rỗng. Máy chủ quyết quyền và chặn chốt trùng.

### `src/dashboard/app/(dashboard)/thu-ngan/AnhChuyenKhoan.tsx`
- Dòng 26: Ảnh thu nhỏ về cạnh dài ≤ 1600px trước khi gửi, không phóng to ảnh nhỏ hơn (tỉ lệ tối đa 1). Dòng 31 chuyển JPEG chất lượng 0,85, nên ảnh điện thoại vài MB còn vài trăm KB, HEIC thành JPEG.
- Dòng 31: Nếu canvas không tạo được ảnh (toBlob trả null) hoặc trình duyệt không đọc được ảnh (dòng 33-35) thì gửi nguyên tệp gốc, để máy chủ tự kiểm kiểu.
- Dòng 43: Ảnh luôn gửi với tên 'chuyen-khoan.jpg' cùng payment_cycle_id, kể cả khi là tệp gốc không phải JPEG.
- Dòng 71: Không có ảnh và không cho thêm (choThem=false) thì không vẽ gì cả (trả null).
- Dòng 116: Chế độ chỉ xem (chiXem) thì ẩn nút Gỡ ảnh; dòng 123 cũng ẩn ô thêm ảnh. Ô thêm còn phụ thuộc choThem.
- Dòng 130: Trong lúc đang tải hoặc gỡ (dang=true), ô chọn ảnh và nút Gỡ ảnh bị khoá để tránh bấm trùng.

### `src/dashboard/app/(dashboard)/thu-ngan/ChiaHinhThuc.tsx`
- Dòng 42: [TSX quyết] Bỏ tick cả Tiền mặt lẫn Chuyển khoản thì không hợp lệ, nhắc 'Chọn hình thức thu.' và không có phần nào để gửi.
- Dòng 48: [TSX quyết] Tick cả hai: số chuyển khoản phải > 0 và < tổng, nếu không thì báo lỗi. Phần tiền mặt = tổng − CK. Ví dụ tổng 700.000đ, CK 200.000đ → TM 500.000đ; CK 700.000đ hoặc để trống → báo lỗi.
- Dòng 58: [TSX quyết] Chỉ tick một hình thức thì toàn bộ tổng đi vào hình thức đó (chỉ TM: phần TM = tổng; chỉ CK: phần CK = tổng), không cần gõ số.
- Dòng 63: [TSX quyết] Chỉ khi khách đưa > 0 mà ít hơn phần tiền mặt thì chặn thu. Ví dụ TM 500.000đ, khách đưa 300.000đ → 'còn thiếu 200.000đ'. Để trống hoặc 0 thì không chặn.
- Dòng 76: [TSX quyết] 'Khách đưa' chỉ gắn vào phần CASH và chỉ khi lớn hơn phần tiền mặt (đưa đúng số thì không gửi). Tiền trả lại (dòng 101) chỉ hiển thị, sổ ghi đúng số thu.
- Dòng 80: [TSX quyết] coChuyenKhoan = true khi có phần chuyển khoản > 0 (cha coi lần thu chờ xác minh). Nhánh nhắc lỗi khi tick CK cũng báo true theo lựa chọn.
- Dòng 105: Ảnh chuyển khoản chỉ báo lên cha khi đang tick Chuyển khoản; bỏ tick CK thì ảnh gửi đi là null (state ảnh vẫn giữ).

### `src/dashboard/app/(dashboard)/thu-ngan/DoiHinhThuc.tsx`
- Dòng 92: Máy chủ quyết đổi được không (doi.duoc). Không có dữ liệu `doi`, hoặc không đổi được mà chưa từng đổi, thì ẩn cả khối. Không đổi được nhưng đã có lịch sử thì vẫn hiện lịch sử (dòng 139), chỉ ẩn nút (dòng 146).
- Dòng 96: [TSX quyết] Chia chỉ hợp lệ khi 0 < chuyển khoản < tổng. Lựa chọn chia chỉ có khi tổng > 1đ (dòng 97). Ví dụ phiếu 500.000đ, CK 150.000đ → TM 350.000đ (dòng 115).
- Dòng 113: Chọn Chia thì gửi hinhThuc = null kèm tienMat và chuyenKhoan; chọn một hình thức thì gửi hinhThuc, còn tienMat và chuyenKhoan là null (dòng 115-116).
- Dòng 114: Gửi kèm hình thức đang hiện (hinhThucCu) để máy chủ phát hiện người khác vừa đổi (409). Lỗi máy chủ trả về được hiện nguyên văn (dòng 123).
- Dòng 117: Đổi sang Tiền mặt thì không gửi mã giao dịch. Chuyển khoản hoặc Chia thì gửi mã đã cắt khoảng trắng, rỗng thì null.
- Dòng 202: [TSX quyết] Nút Lưu bị khoá khi đang gửi, chưa chọn hình thức mới, hoặc chọn Chia mà số chuyển khoản chưa hợp lệ.

### `src/dashboard/app/(dashboard)/thu-ngan/GiamGia.tsx`
- Dòng 63: [TSX quyết] Chưa bật giảm, hoặc tổng hoá đơn ≤ 0, hoặc chưa nhập giá trị (dòng 64) → coi như không giảm, thu nguyên giá, không báo lỗi.
- Dòng 66: [TSX quyết] Giá trị giảm không phải số hoặc ≤ 0 thì báo lỗi; giảm % quá 100 báo lỗi (dòng 67); làm tròn ra 0đ cũng báo lỗi (dòng 69).
- Dòng 68: [TSX quyết] Giảm tiền: làm tròn về đồng. Giảm %: tính trên PHẦN ĐƯỢC GIẢM (tran = giamDuoc, thiếu thì cả tổng), không trên tổng. Ví dụ: hoá đơn 1.000.000đ, 400.000đ trả trước liệu trình → giảm 10% = 60.000đ.
- Dòng 70: [TSX quyết] Giảm vượt phần được giảm thì chặn thu. Ví dụ trên, gõ giảm 700.000đ → 'vượt phần giảm được (600.000đ)'. Nếu phần giảm được = cả tổng thì báo 'vượt tổng hoá đơn'.
- Dòng 81: [TSX quyết] Có giảm thì bắt buộc ghi lý do (cắt khoảng trắng); trống → báo lỗi, params = null, chặn nút thu. Lý do tối đa 500 ký tự (dòng 176).
- Dòng 92: Tổng hoặc phần giảm được ≤ 0 thì không vẽ ô giảm giá (nhưng effect ở dòng 56 vẫn chạy).
- Dòng 100: Bỏ tick giảm giá thì xoá giá trị và lý do đã gõ; đổi loại tiền/% cũng xoá giá trị (dòng 120, 133).

### `src/dashboard/app/(dashboard)/thu-ngan/LichSuThu.tsx`
- Dòng 153: Khi restricted, ẩn hai ô chọn Từ–Đến; khoảng ngày giữ theo ngày của quầy.
- Dòng 243: Lần thu có tao_luc khác luc hiện 'Lập … · Thu …' (luôn kèm ngày); còn lại chỉ hiện giờ.
- Dòng 248: Lần thu có so_tien = 0 và có giảm giá (discount_amount > 0) hiện '0đ (Miễn phí)'; số tiền âm hiện '−…đ' màu cảnh báo (dòng 247, 250–251).
- Dòng 266: Lần huỷ không có link In; thu và hoàn có link In, hoàn mở phiếu loại 'hoan', còn lại loại 'thu' (dòng 268).
- Dòng 276: Nút Đổi hình thức chỉ hiện khi có thaoTac, là lần 'thu' và máy chủ trả doi_hinh_thuc (máy chủ quyết).
- Dòng 289: Khối ảnh CK hiện cho lần 'thu' nếu đã có ảnh, hoặc nếu còn hoàn tác được và có phần chuyển khoản (TRANSFER). Không có thaoTac thì chỉ xem (chiXem, dòng 292).
- Dòng 295: Chỉ thêm được ảnh chuyển khoản khi có quyền thao tác (thaoTac) và lần thu còn hoàn tác được (hoan_tac.duoc).
- Dòng 300: Nút Hoàn tác chỉ hiện khi có thaoTac, là lần 'thu' và hoan_tac.duoc.

### `src/dashboard/app/api/payment/anh-ck/route.ts`
- Dòng 19: GET và POST: chưa cấu hình CLINIC_API_URL thì trả 503, không gọi backend.
- Dòng 23: GET và POST: không có thông tin đăng nhập thì trả 401 'Chưa đăng nhập'.
- Dòng 25: GET: thiếu tham số id (rỗng hoặc chỉ có khoảng trắng) thì trả 400, không gọi backend.
- Dòng 37: GET: ảnh trả về luôn kèm 'private, no-store' và nosniff nên trình duyệt hoặc proxy không giữ lại ảnh chuyển khoản. Chỉ chuyển tiếp content-type và content-length từ backend.
- Dòng 43: GET: giữ nguyên status của backend (403, 404…) và truyền thẳng thân phản hồi, không đổi sang JSON.
- Dòng 67: POST: nếu mất kết nối giữa chừng thì trả 502 kèm thông báo 'ảnh CHƯA được lưu, hãy tải lại'.
- Dòng 75: POST: nếu backend trả thân không phải JSON thì bọc thành {error: nội dung}, rồi trả lại với đúng status của backend.

### `src/dashboard/app/api/visits/[id]/charges/route.ts`
- Dòng 15: Mã lượt khám không đúng dạng UUID thì trả 400 ngay, không gọi backend.
- Dòng 18: Chưa cấu hình CLINIC_API_URL thì trả 503, không gọi backend.
- Dòng 25: Không lấy được header đăng nhập của người gọi thì trả 401 'Chưa đăng nhập'.
- Dòng 33: Trả nguyên thân JSON và mã trạng thái của backend (kể cả lỗi 4xx/5xx), proxy không tự tính tiền hay lọc gì.
- Dòng 34: Lỗi khi gọi backend hoặc đọc JSON thì trả 502 'Không kết nối được máy chủ'.

### `src/dashboard/app/print/hoa-don-thuoc/[visitId]/InHoaDonThuoc.tsx`
- Dòng 17: [TSX quyết] Chỉ lấy phiếu của lượt đang xem (visit) và chỉ loại thuốc (kind=thuoc); thu tiền dịch vụ không hiện ở đây.
- Dòng 26: [TSX quyết] Nếu gọi API lỗi hoặc không có dữ liệu thì hiện thông báo lỗi của máy chủ (message/error), không có thì dùng câu mặc định.
- Dòng 40: [TSX quyết] Nút In / tải PDF chỉ bật khi lượt có ĐÚNG một phiếu thu thuốc; 0 phiếu hoặc nhiều phiếu thì nút bị khoá (nhiều phiếu phải mở từng phiếu).
- Dòng 47: [TSX quyết] Lượt chưa có lần thu tiền thuốc nào thì hiện dòng 'chưa có lần thu tiền thuốc nào', không có phiếu để in.
- Dòng 52: [TSX quyết] Đúng một phiếu thì in thẳng phiếu đó bằng PhieuThuGiay.
- Dòng 53: [TSX quyết] Nhiều phiếu thì liệt kê mã phiếu và tổng tiền (ví dụ 150.000đ), mỗi dòng có nút mở phiếu riêng trong tab mới để in.

### `src/dashboard/lib/hinh-thuc-thu.ts`
- Dòng 29: [TSX quyết] Mã QR cũ vẫn hiển thị là 'Chuyển khoản'; mã lạ hiển thị nguyên mã, rỗng thì ra chuỗi rỗng (dòng 33).
- Dòng 42: [TSX quyết] Nhãn nhiều phần bỏ qua phần không có hình thức; 1 phần chỉ hiện tên, ≥2 phần hiện tên kèm số tiền nối bằng ' + '.
- Dòng 51: [TSX quyết] Tiền thừa = khách đưa − phần tiền mặt, chỉ khi khách đưa > phần tiền mặt. Ví dụ tiền mặt 430.000đ, khách đưa 500.000đ → trả lại 70.000đ. Chỉ hiển thị; không có phần tiền mặt hợp lệ thì trả null.
- Dòng 68: [TSX quyết] Đuôi 'k' = nghìn đồng, dấu phẩy thành dấu chấm thập phân: '500k' = 500.000đ, '1,5k' = 1.500đ.
- Dòng 70: [TSX quyết] Không có đuôi k thì mọi dấu . và , bị xoá (phân cách nghìn): '500.000' hoặc '500,000' = 500.000đ.
- Dòng 71: [TSX quyết] Số âm hoặc không phải số (rác) → null; chuỗi rỗng → null (dòng 66). Kết quả làm tròn về số nguyên đồng (dòng 72).

## pharmacy — 51 luật

### `src/clinicai/services/phan_lo_service.py`
- Dòng 136: Mỗi dòng đơn phải có tổng số lô ĐÚNG BẰNG số cần bán, lệch bên nào cũng chặn. Vd kê 10 viên mà mới chọn lô cho 6 → 'mới chọn lô cho 6/10 — dược sĩ chọn đủ lô'. Chọn thừa (12/10) cũng báo cùng câu.
- Dòng 159: Lô có hạn dùng trước ngày `hom_nay` (do người gọi truyền vào) thì không bán được, phải chọn lô khác. Hàm này không tự tính múi giờ.
- Dòng 161: Khả dụng của lô lấy từ hàm SQL drug_batch_kha_dung. Nếu phân lô đang là phần giữ của chính lần thu này (da_giu) thì cộng lại phần ấy trước khi so. Khả dụng nhỏ hơn số cần thì chặn (dòng 162). Vd cần 5, khả dụng 3 → chặn.
- Dòng 195: Phần thuốc đã cấp theo luồng cũ (trước khi bắt thu tiền trước) không cần lô nữa: cần lô = số bán − dispensed_qty; còn ≤ 0 thì bỏ dòng.
- Dòng 208: Gắn lần thu chỉ áp cho phân lô CHƯA gắn lần thu nào và chưa nhả; phân lô đã gắn lần khác hoặc đã nhả thì bỏ qua, không báo lỗi.
- Dòng 233: Mỗi (lần thu, phân lô) chỉ có một dòng SALE — gọi lại không ghi thêm (ON CONFLICT DO NOTHING). SALE chỉ là cam kết bán, không trừ tồn vật lý.
- Dòng 277: Khi nhả phân lô, chỉ chép lại kế hoạch cho dòng đơn chưa chốt (closed_at rỗng, dòng 277), chưa đính chính (removed_at rỗng, dòng 280) và còn cùng thuốc (dòng 281). Dòng không đạt thì nhả hẳn, không chép.
- Dòng 304: Huỷ phiếu thuốc: dòng đơn đã giao dù một phần (handed_over_qty > 0) thì KHÔNG đảo kho, không gỡ phân lô, chỉ trả prescription_id về để xử lý trả thuốc. Dòng chưa giao gì thì đảo SALE_REVERSAL, bỏ qua SALE đã đảo rồi (dòng 319), rồi nhả và chép lại phân lô chưa gắn (dòng 330).
- Dòng 386: Phần 'cần hoàn' = chưa giao − (số đã hoàn tiền xong − số đã đảo bán), không âm. Phiếu VOIDED thì 0. Vd chưa giao 4, đã hoàn tiền 3, đã đảo 1 → cần hoàn 4 − (3 − 1) = 2.

### `src/dashboard/app/(dashboard)/pharmacy/consult/ConsultBoard.tsx`
- Dòng 37: [TSX quyết] Đơn đang chọn lấy theo id từ danh sách gốc, không phải danh sách đã lọc. Nên gõ tìm làm đơn đang chọn biến mất khỏi danh sách trái nhưng chi tiết bên phải vẫn hiện.
- Dòng 42: [TSX quyết] Ô tìm kiếm lọc ngay trên máy theo tên bệnh nhân, tên thuốc hoặc mã đơn (không phân biệt hoa/thường). Ô trống thì hiện hết. Không tìm theo số điện thoại dù placeholder chỉ ghi 'tên BN / thuốc'.
- Dòng 124: [TSX quyết] Dòng 'Liều dùng' chỉ hiện khi có hướng dẫn liều. Khung 'Lưu ý' màu cảnh báo chỉ hiện khi dòng thuốc có caution (dòng 135).
- Dòng 149: [TSX quyết] Bốn gạch đầu dòng 'Hướng dẫn tư vấn' là chữ cố định, giống nhau cho mọi đơn, không lấy từ dữ liệu.

### `src/dashboard/app/(dashboard)/pharmacy/consult/page.tsx`
- Dòng 25: Phải qua kiểm quyền menu "/pharmacy/consult" (requireNavAccess) trước khi đọc dữ liệu; không có quyền thì không vào được trang.
- Dòng 29: Nếu backend không trả dữ liệu (máy chủ không trả lời hoặc tài khoản không có quyền xem nhà thuốc) thì chỉ hiện dòng báo lỗi màu đỏ, không vẽ bảng tư vấn.
- Dòng 37: [TSX quyết] Tách full_name và phone_primary khỏi mỗi dòng và gói vào object patient để ConsultBoard dùng. Việc lọc dòng chưa chốt/chưa đính chính do backend làm, trang không lọc lại.

### `src/dashboard/app/(dashboard)/pharmacy/history/HistoryBoard.tsx`
- Dòng 50: [TSX quyết] Ô tìm chỉ lọc phía giao diện trên danh sách đã tải: khớp tên bệnh nhân, tên thuốc bác sĩ gõ, tên thuốc kho hoặc mã đơn, không phân biệt hoa thường. Không tìm theo số điện thoại hay liều dùng.
- Dòng 109: [TSX quyết] Cột Thuốc ưu tiên tên thuốc kho (thuốc thật đã giao), không có thì dùng chữ bác sĩ gõ. Nếu hai tên khác nhau thì thêm dòng nhỏ 'Bác sĩ ghi: …' (dòng 110).
- Dòng 118: [TSX quyết] Cột 'Bác sĩ kê' dùng số quantity_num nếu có, không thì rơi về chuỗi quantity; kèm ghi chú quantity_note trong ngoặc nếu có.
- Dòng 123: [TSX quyết] Tô đậm màu cảnh báo ô 'Khách mua' khi có số khách mua và khác số bác sĩ kê (so với quantity_num); khách mua trống (null) thì ghi 'như kê' và không tô (dòng 133).
- Dòng 140: [TSX quyết] Cột 'Thời điểm' hiện ngày giao; chưa có ngày giao thì dùng ngày tạo; cả hai trống thì '—'.

### `src/dashboard/app/(dashboard)/pharmacy/history/page.tsx`
- Dòng 31: Phải qua requireNavAccess('/pharmacy/history') mới xem được trang; không có quyền thì bị chặn trước khi gọi backend.
- Dòng 33: Backend không trả lời hoặc tài khoản không có quyền xem nhà thuốc (fetchFromBackend trả rỗng) thì chỉ hiện thông báo lỗi đỏ, không vẽ bảng.
- Dòng 41: [TSX quyết] Mỗi dòng backend trả được tách full_name, phone_primary ra, gói thành patient {full_name, phone_primary}; các trường còn lại giữ nguyên.

### `src/dashboard/app/(dashboard)/pharmacy/inventory/DanhSachPhieu.tsx`
- Dòng 121: [TSX quyết] Tổng tiền phiếu nhập tự cộng ở màn = Σ số lượng × giá nhập; dòng thiếu số lượng hoặc giá tính như 0. Ví dụ 10 hộp × 45.000đ + 5 hộp × 30.000đ = 600.000 đ. Chỉ hiện ở tab NHẬP (dòng 148).
- Dòng 143: [TSX quyết] Số 'lệch' của phiếu kiểm = số dòng có lệch khác 0, chỉ hiện ở tab KIỂM. Dòng lệch null bị Number(null)=0 nên không tính là lệch.
- Dòng 163: [TSX quyết] Mỗi lần chỉ mở được một phiếu: bấm 'Xem dòng' đặt mo = id phiếu, bấm lại thì thu gọn.
- Dòng 179: [TSX quyết] Khi xem dòng phiếu kiểm: hiện 'máy X → thực tế Y (lệch ±Z)', dấu + chỉ thêm khi lệch dương; lệch âm tự có dấu trừ.

### `src/dashboard/app/(dashboard)/pharmacy/inventory/TheKho.tsx`
- Dòng 97: [TSX quyết] Chỉ khi tên gõ khớp CHÍNH XÁC một thuốc trong danh sách thì mới gọi onChon và tải thẻ kho; gõ dở thì giữ nguyên bảng đang xem.
- Dòng 125: [TSX quyết] Tồn hiện tại được ghép từ danh sách tồn theo từng đơn vị (hộp, viên không cộng chung); giao cho hàm tonTheoDonVi định dạng.
- Dòng 144: [TSX quyết] Thuốc chưa có biến động nào thì hiện dòng 'chưa có biến động kho nào' thay cho bảng trống.
- Dòng 162: [TSX quyết] Số lượng âm (xuất, huỷ, bán) tô đỏ, còn lại tô xanh; số dương có thêm dấu '+'. Số 0 tô xanh và không có dấu. Ví dụ -5 viên hiện đỏ, +10 hộp hiện xanh.
- Dòng 169: [TSX quyết] Cột tồn trước → sau kèm đơn vị của lô. Các số do máy chủ tính sẵn, giao diện chỉ định dạng bằng soKho.

### `src/dashboard/app/(dashboard)/reports/ThuocTheoKhach.tsx`
- Dòng 89: [TSX quyết] Khách đang xem = khách được bấm; chưa bấm, hoặc khách đã chọn không còn trong danh sách, thì tự mở khách đầu tiên; danh sách rỗng thì không có khung chi tiết.
- Dòng 98: [TSX quyết] Thẻ 'Khách lệch kê / bán' đổi sang màu cảnh báo khi số khách lệch > 0, ngược lại màu trung tính.
- Dòng 103: [TSX quyết] Không có khách nào thì chỉ hiện câu 'Không có khách nào có đơn thuốc trong khoảng này', không vẽ danh sách và khung chi tiết.
- Dòng 126: [TSX quyết] Khách có so_lech khác 0 thì hiện chip 'Lệch N' ở danh sách bên trái.
- Dòng 143: [TSX quyết] Tiêu đề phụ: khách bán lẻ ghi 'Bán lẻ'; nếu không thì ghi 'Bác sĩ kê: …' khi có bác sĩ; thêm 'Thu: …' khi có người thu.
- Dòng 169: [TSX quyết] Mỗi dòng thuốc hiện chip trạng thái: Đã bán (xanh), Khách không lấy (xám), Chưa thu (vàng). Chip 'Quầy thêm' khi nguon = QUAY (dòng 170); chip 'Khách trả N' khi so_tra khác 0 (dòng 171).
- Dòng 179: [TSX quyết] Cột Chênh in đậm màu cảnh báo khi chênh khác 0 và khác null; chênh null hiện '—'.
- Dòng 190: [TSX quyết] Dòng Tổng chi tiết dùng tien của khách do máy chủ trả về, không tự cộng các dòng thuốc.

### `src/dashboard/app/api/quay-thuoc/route.ts`
- Dòng 26: Cả GET lẫn POST đều chặn khi chưa đăng nhập (không có phiên Supabase): trả 401 Unauthorised, không gọi FastAPI.
- Dòng 28: GET: visit_id phải đúng dạng UUID (36 ký tự hex và dấu gạch), sai thì trả 400 'Mã lượt khám không hợp lệ'.
- Dòng 51: POST thao_tac 'them': id lượt khám phải là chuỗi UUID hợp lệ, sai thì trả 400. Hai thao tác 'chon' và 'so-luong' không kiểm tra id vì mã lượt nằm trong du_lieu.
- Dòng 56: thao_tac khác chon/so-luong/them thì trả 400 'Thao tác không hợp lệ'.

### `src/dashboard/app/print/tem-lo/InTemLo.tsx`
- Dòng 19: [TSX quyết] Nếu mã tem không mã hoá được Code128B thì không vẽ vạch, chỉ còn dòng chữ mã tem bên dưới.
- Dòng 57: [TSX quyết] Cỡ tem rộng 20–200mm (mặc định 50), cao 15–200mm (mặc định 30); gõ 300 thì thành 200, gõ 5 thì thành 20. Ô không phải số thì về mặc định; dấu phẩy được đổi thành dấu chấm.
- Dòng 59: [TSX quyết] Số tem mỗi lô làm tròn rồi giới hạn 1–20; mỗi lô nhân thành đúng chừng đó tem (3 lô × 2 = 6 tem).
- Dòng 66: [TSX quyết] Khổ decal: mỗi tem một trang cỡ w×h, không lề, ngắt trang sau mỗi tem. Khổ A4: lề 10mm, tem xếp lưới và không bị cắt đôi giữa hai trang.
- Dòng 132: [TSX quyết] Lô không có tên thuốc thì in dấu '—'; tên dài bị cắt còn 2 dòng.
- Dòng 134: [TSX quyết] Lô không có hạn dùng thì in 'HSD chưa có'.

## kho_vat_tu — 10 luật

### `src/dashboard/app/(dashboard)/kho-vat-tu/bao-cao-vat-tu.ts`
- Dòng 58: [TSX quyết] Tuần tính từ thứ Hai: lấy ngày hôm nay theo giờ VN, lùi (thứ + 6) % 7 ngày. Ví dụ Chủ nhật lùi 6 ngày, thứ Hai lùi 0 ngày.
- Dòng 61: [TSX quyết] Mặc định 'đến' là hôm nay, nên tuần mới chỉ có số liệu từ thứ Hai tới hôm nay, không phải đủ 7 ngày.
- Dòng 77: [TSX quyết] Báo cáo chỉ hợp lệ khi HTTP ok và JSON có mảng items. Nếu không, trả {loi} với thông báo error của server hoặc câu mặc định.
- Dòng 82: [TSX quyết] Lỗi mạng hoặc fetch bị ngắt trả {loi} 'Mất kết nối'. Hàm không phân biệt abort chủ động với mất mạng.

### `src/dashboard/app/(dashboard)/kho-vat-tu/page.tsx`
- Dòng 23: [TSX quyết] Vào trang phải qua requireNavAccess('/kho-vat-tu'); mã lego cụ thể do hàm đó quyết, không nằm ở tệp này.
- Dòng 32: [TSX quyết] Không đọc được gói tồn (null) thì chỉ hiện thông báo lỗi, không vẽ kho.
- Dòng 49: [TSX quyết] Phiếu đọc hỏng (null) thì coi là danh sách rỗng, tab Phiếu trống, không chặn màn.
- Dòng 54: [TSX quyết] Số thực tế kiểm kê null giữ null (chưa kiểm), còn lại ép Number.
- Dòng 58: Gói chờ duyệt truyền nguyên (có thể null); tab Chờ duyệt tự báo lỗi.
- Dòng 59: [TSX quyết] Cho sửa giá/danh mục (suaGiaDuoc) khi tài khoản có quyền price.service.manage.

## ke_toan — 13 luật

### `src/clinicai/api/v1/routers/hoa_don_cong_ty.py`
- Dòng 23: Cửa theo quyền lego QUYEN_CONG_TY (khai ở HoaDonCongTyService), không theo vai.
- Dòng 29: ten_cong_ty không có giá trị mặc định nên bắt buộc phải gửi, thiếu là lỗi 422 trước khi vào service.
- Dòng 31: ma_so_thue chỉ giới hạn độ dài 200 ký tự, không ràng buộc định dạng — MST sai dạng vẫn qua được, service chỉ nhắc chứ không chặn.
- Dòng 42: luu_vao_ho_so mặc định true — ghi hoá đơn công ty sẽ tự lưu/cập nhật công ty vào hồ sơ khách luôn, trừ khi client gửi false.
- Dòng 52: ca_da_an mặc định false — đọc danh sách công ty của khách chỉ trả về công ty chưa ẩn, phải gọi với true mới thấy công ty đã ẩn.
- Dòng 90: an=true thì ẩn công ty khỏi hồ sơ khách, an=false thì khôi phục lại; AnRequest.an mặc định true (dòng 46) nên không gửi body coi như ẩn.
- Dòng 133: Bỏ chọn công ty trên hoá đơn không xoá dòng nào, chỉ gọi service bo_hoa_don; muốn khôi phục phải PUT lại /hoa-don/cong-ty/phieu/{id}.

### `src/clinicai/api/v1/routers/hoa_don_misa.py`
- Dòng 21: Cổng quyền dựng từ QUYEN_MISA (docstring nói là accounting.finance.full); cả 5 route đều gắn Depends(_CUA) nên đều cần quyền này, không xét vai.
- Dòng 27: Body đánh dấu: tu/den bắt buộc, tối đa 40 ký tự; loai tối đa 20, co_so tối đa 64, ghi_chu mặc định rỗng tối đa 2000. Vượt giới hạn → pydantic báo 422. Tệp này không kiểm định dạng ngày.
- Dòng 48: Router không tự kiểm luật nào: chỉ chuyển identity và tham số sang HoaDonMisaService. loai/co_so để None thì ý nghĩa do service quyết.

### `src/clinicai/api/v1/routers/ke_toan.py`
- Dòng 19: Router chỉ chặn thuế suất dài quá 20 ký tự (hoặc để trống/null). Không kiểm định dạng '8', '8,5', 'KCT', 'KKKNT' ở đây; luật định dạng và 'rỗng = bỏ đặt' nếu có thì nằm ở ThueSuatService, chưa thấy trong tệp này.
- Dòng 23: Đặt thuế theo mặt hàng bắt buộc có 'loai' (tối đa 10 ký tự) và 'id' (tối đa 64 ký tự). Ý nghĩa của 'loai' do service quyết, router không kiểm giá trị.
- Dòng 30: Cả 3 route chỉ đòi đăng nhập (get_current_identity) rồi chuyển identity cho ThueSuatService. Router không có cửa quyền riêng; việc kiểm quyền (nếu có) nằm ở service.

## cong_no — 0 luật
