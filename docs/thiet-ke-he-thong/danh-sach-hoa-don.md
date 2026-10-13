# Danh sách hoá đơn

Màn `/hoa-don`, dưới Báo cáo, chỉ đọc chứng từ đã thanh toán của cả dịch vụ
và thuốc. Gom theo mã khách, không theo lượt khám. Dòng bị bỏ trước thanh toán
không vào sổ này. Popup dùng snapshot bill và phiếu hoàn, giữ người và thời gian
tạo, thu, huỷ, hoàn; trường không được lưu hiển thị không có dữ liệu.

API `/api/v1/hoa-don`: cùng ReportAccessService như Báo cáo; quản lý xem
toàn bộ, trưởng ca chỉ ngày/ca/cơ sở được phân công; nhân viên không có quyền
tài chính bị từ chối. Tenant luôn lấy từ danh tính đã xác minh. Không thêm lối ghi.

Ngày lọc theo sự kiện: đã thu theo paid_at, huỷ theo closed_at, hoàn thành theo
completed_at, chờ hoàn theo created_at. Bill gốc được giữ khi có sự kiện trong
kỳ, kể cả thu ở ngày trước. Tổng đầu màn là tiền trong kỳ; từng bill và khách
là số toàn chứng từ, được ghi nhãn riêng. VOIDED không tự trở thành tiền hoàn:
thu ròng = thu thật − hoàn COMPLETED; tiền huỷ và tiền chờ hoàn là cột riêng.
Không suy ra thất thoát. Không giới hạn cứng 3000 bản ghi.

Khoản hoàn FAILED/CANCELLED cũng hiện trong lịch sử, theo closed_at, người và
lý do đóng. Không tính vào tiền đã hoàn. Cảnh báo phiếu huỷ yêu cầu xác minh
tiền trả lại, không kết luận khoản nào đã mất hay chưa trả.

Giảm giá tổng bill: giữ `original_amount` trước giảm, `discount_amount` tiền
giảm, kiểu AMOUNT/PERCENT, giá trị nhập, lý do và người giảm. `amount` là tiền
đã thu sau giảm, có thể 0 khi giảm 100%; thu ròng vẫn lấy amount − tiền hoàn,
không cộng lại giảm giá. Từng dòng giữ line_total sau giảm và discount_allocated;
trước giảm của dòng = line_total + discount_allocated. Tổng giảm đầu màn chỉ
cộng bill được thu trong kỳ; không cộng lại khi bill cũ được hoàn hôm nay.

Đọc cột giảm bằng to_jsonb để chạy được trước và sau migration của nhánh giảm
giá. Không thêm, sửa hay áp migration giảm giá ở nhánh này. Bill cũ thiếu cột
được đọc là giảm 0; trước giảm là amount. Không sửa nguồn thu/hoàn.

Excel dữ liệu dùng XLSX Table chỉnh sửa được, đủ dòng và trường, không gộp ô;
cùng dataset và bộ lọc với màn hình. Không thay đổi nghiệp vụ thu/hoàn đang chạy.
Năm sheet: Trong kỳ, Theo khách, Chứng từ, Chi tiết, Hoàn tiền. Sheet không khóa,
tiền là số, ngày giờ là ngày giờ Excel. Export dùng cùng hàm và cổng kiểm quyền.
