Người kiểm kê cuối ca cần xem toàn bộ phiếu dịch vụ và thuốc theo khách, nhận diện hoàn/hủy sau thanh toán và truy vết người thao tác. Thêm **Danh sách hoá đơn** ngay dưới **Báo cáo**, bảng thu/hoàn/chờ hoàn/thu ròng cùng cảnh báo và popup chi tiết chứng từ; đổi nút thu thành **Tạo bill**.

Toàn bộ 4 luồng xuất Excel hiện có dùng XLSX thật, bảng có thể lọc/sắp xếp/chỉnh sửa, số/ngày đúng kiểu. Màn hoá đơn xuất 5 sheet cùng bộ lọc và quyền ca/cơ sở.

Giảm giá hiển thị tổng gốc, phần giảm, lý do và người giảm. Tiền thực dùng amount/line_total sau giảm; giảm 100% vẫn là phiếu đã thu 0đ. Không tính giảm giá thành hoàn hay thất thoát. Không sửa migration 20261013100000.

**Phụ thuộc:** chờ claude/giam-gia-tong-hoa-don vào main rồi rebase và kiểm thử DB giảm giá thật. Đọc trường JSON tùy chọn để tương thích dữ liệu cũ trước migration. Chưa merge/deploy.

**Kiểm chứng:** kiểm thử PostgreSQL tenant/cơ sở/ca, head được phân công, hoàn khác ngày, giảm giá; bộ phận hoá đơn coverage 99%; Excel builder coverage 100%. E2E đăng nhập DEMO local thật và API dữ liệu hoá đơn giả lập ở 375/768/1280, popup/ESC/lọc/cảnh báo/giảm 100%. Real API local: manager200, cashier403 cho JSON và XLSX; tải XLSX mở lại bằng openpyxl.

**Kịch bản người thật:**
1. Mở Báo cáo rồi Danh sách hoá đơn; chọn ngày/ca/cơ sở.
2. Tìm khách có nhiều phiếu dịch vụ và thuốc; mở popup kiểm dòng, người/giờ, lý do hoàn/hủy.
3. Chọn Chỉ cần kiểm tra; xác nhận cảnh báo hiển thị ngay trên dòng.
4. Kiểm phiếu giảm AMOUNT/PERCENT/100%; thu thực không cộng lại phần giảm.
5. Hoàn hôm nay cho phiếu hôm trước: tổng trong kỳ chỉ ghi khoản trả ra hôm nay, popup giữ chứng từ gốc.
6. Xuất Excel từ hoá đơn, lịch sử thu, báo cáo, hàng hóa và kho; lọc/sort/SUM trực tiếp và so tổng cùng bộ lọc.

| Màn | Nút/link | Đích | Quyền |
|---|---|---|---|
| Sidebar | Danh sách hoá đơn | /hoa-don | quyền báo cáo tài chính/ca được phân công |
| Hoá đơn | Xem | popup chỉ đọc | cùng phạm vi backend |
| Popup | Xem/in phiếu, In phiếu hoàn | /print/phieu-thu/[id] | cửa in hiện có |
| Hoá đơn | Xuất Excel | /api/hoa-don?xuat=xlsx | cùng bộ lọc và quyền |
| Thu dịch vụ/thuốc | Tạo bill | payment API hiện có | quyền quầy hiện có |
| Lịch sử thu/báo cáo/kho | Xuất Excel | endpoint XLSX tương ứng | cùng quyền dữ liệu |
