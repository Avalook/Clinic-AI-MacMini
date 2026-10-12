# Báo cáo cuối ngày cho chủ phòng khám

Phạm vi đã được Tuyền duyệt ngày 12/10/2026: chỉ đọc, sửa giao diện và nguồn
backend; chuẩn bị PM bấm thử trước khi staging và prod.

## Cách đọc

1. Theo mẫu điện thoại đã gửi: thực thu tổng, thực thu dịch vụ, thực thu
   thuốc/vật tư; tiếp theo Phương thức thanh toán. Nhãn trái, số phải;
   nhóm nền xám, không xếp các thẻ KPI. Huỷ, hoàn và thống kê lượt thu gọn
   phía dưới; không chiếm màn chính của chủ phòng khám.
   Giữ số liệu sẵn có; ngày/cơ sở ở đầu, bộ lọc nâng cao thu gọn.
2. Chỉ hiện thông báo thu gọn Có khoản cần xử lý khi có số tiền tồn dương:
   lần thu chờ xác minh, hoàn chờ chuyển, tiền thừa
   chưa xử lý và công nợ đã ghi nhận chưa thu. Các khoản tồn không bị bộ lọc
   ngày/ca che mất; ghi rõ phạm vi loại và cơ sở.
3. Gom tra cứu và giải thích vào một mục Chi tiết giao dịch phía dưới;
   bỏ nhóm thống kê lượt lặp lại ở phần tóm tắt.

Rà theo ảnh và trao đổi PM: mục tiêu là đọc tổng hợp trên cùng một mặt
phẳng. Giữ số phiếu thu trong tóm tắt (không gọi là hoá đơn). Bỏ khỏi màn
này kiểm tra thuốc kê so với bán và lượt chưa chọn dịch vụ khám; giữ phân
tích dịch vụ bán được trong chi tiết, ghi rõ tiền gộp chưa trừ hoàn.
Không thêm ví/thẻ/điểm/voucher khi hệ thống chưa hỗ trợ; không hiển thị
tổng chi hoặc lãi dưới dạng 0 khi thiếu sổ chi.

Không trình bày lợi nhuận hay tổng chi vì chưa có sổ chi đầy đủ. Lần thu chờ
xác minh không cộng vào thực thu. Giữ định nghĩa hoàn theo ngày tạo khoản
hoàn của báo cáo hiện hành; không đổi lịch sử hay CSV ngầm.

Phạm vi UI chốt lại: bỏ Chi tiết giao dịch và Có khoản cần xử lý khỏi màn
cuối ngày; việc xử lý ở thu ngân. In chỉ trang tóm tắt. Xuất Excel dùng CSV
mở bằng Excel, chỉ các dòng đang hiển thị cùng ngày/cơ sở/ca/loại; không
gọi bản CSV chi tiết cũ. Nút In/Xuất đặt ngoài phần chọn ngày và bộ lọc.

## Nguồn và ranh giới

Giữ endpoint báo cáo, quyền report.view và hợp đồng cũ; thêm can_xu_ly.
Mọi truy vấn khóa clinic_id, cơ sở lấy từ lượt khám rồi dự phòng lịch hẹn.
Tổng tiền phải tính trên toàn bộ tập, độc lập giới hạn danh sách chi tiết.
Giao diện chỉ định dạng số; thiếu dữ liệu hoặc lỗi không thay thành số 0.
Không migration, không ghi dữ liệu thật, không thay luật thanh toán.

## Kiểm

Kiểm khoản tồn ngày cũ, xác minh/hoàn/huỷ hết tồn, cơ sở và tenant, tiền
thừa giữ lại và tổng khi danh sách bị cắt. Bấm DEMO ở 375 và 1280; kiểm tải,
lỗi, bộ lọc, in và xuất file. CI đầy đủ một lần khi xong.

PM duyệt bố cục và ý nghĩa số; staging bấm thử đúng SHA trước khi Tuyền
thực hiện quy trình lên prod. Chưa được coi là sẵn sàng prod khi CI chưa xanh.

## Kịch bản PM bấm thử

- Mở báo cáo ở điện thoại: nhìn thấy nhóm tổng thu và thanh toán ngay, không
  phải cuộn qua hàng dài nút chọn ngày/ca.
- Mở Đổi ngày / bộ lọc / xuất báo cáo, chọn ngày và cơ sở; các số đổi đúng,
  lỗi tải phải báo lỗi và không giữ số của bộ lọc cũ.
- Mở Các khoản cần xử lý: thấy phạm vi đến hiện tại, tên/mã khách và số tiền.
- Mở chi tiết lượt và bảng đối soát để so số với quầy thu. In/xuất vẫn dùng
  dữ liệu khoảng đang chọn. Xuất CSV giữ hợp đồng cũ, chưa gồm tồn hiện tại.

Nút/link đã đụng: chọn ngày, cơ sở, loại tiền, ca, tải lại, in, xuất CSV;
thêm mở/đóng khoản tồn, thống kê lượt và bảng đối soát. Không nút ghi tiền mới.
