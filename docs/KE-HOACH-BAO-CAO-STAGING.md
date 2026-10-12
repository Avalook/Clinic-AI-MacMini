# Báo cáo để quản lý duyệt trên staging

Tách từ PR #396 theo yêu cầu ngày 12/10/2026: chỉ giao diện và các số báo cáo;
giữ nguyên report.view, không thêm thiết lập hoặc quyền theo ca. Nền là SHA
staging 741a85b6, có nội dung giống main 8e8495c2; giữ các thay đổi đang thử.

Màn cuối ngày: tổng thu, dịch vụ/thuốc, TM/CK, doanh thu/hoàn/nợ trong kỳ,
doanh thu thuần, phiếu thu. Bố cục hàng phẳng cho điện thoại, bộ lọc hiện sẵn,
mặc định Hào Nam; In/CSV chỉ các số đang hiện. Giảm giá chưa có nguồn nên
hiện Chưa có dữ liệu. Giữ định nghĩa hoàn và doanh thu trên dòng đã thu của
báo cáo hiện hành; không sửa lịch sử giao dịch, không migration.

PM thử ngày có khoản thu và không có khoản thu, đổi cơ sở/ca/loại, kiểm tổng
với quầy thu; thử In/CSV và điện thoại 375/desktop 1280. Chỉ sau PM duyệt và
đủ CI mới xem xét lên prod. Quyền theo ca và trang thiết lập để PR sau.

Nút/link đã đụng: ngày/cơ sở/ca/loại tiền, In và Xuất Excel (CSV). Bỏ nút
Tải lại, các nhóm tra cứu/khoản cần xử lý và dòng ghi chú lặp.
