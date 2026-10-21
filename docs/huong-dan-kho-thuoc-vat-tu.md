# Hướng dẫn nhanh: Kho thuốc và Kho vật tư

> Hướng dẫn theo giao diện đang chạy trên staging, chụp ngày 19/10/2026. Staging dùng dữ liệu thử đã che. Mở [Kho thuốc staging](https://staging.dr4women.io.vn/pharmacy/inventory) hoặc [Kho vật tư staging](https://staging.dr4women.io.vn/kho-vat-tu). Ảnh giao diện thật đã chụp và gửi trong cuộc trò chuyện này.

## Quản lý thuốc

### 1. Nhập thuốc

1. Vào **Kho thuốc → KHO → Nhập thuốc**.
2. Điền nhà cung cấp, số hóa đơn và ngày chứng từ.
3. Ở mỗi dòng, chọn thuốc rồi điền **số lô, hạn dùng, số lượng, đơn vị, giá nhập**.
4. Kiểm tra lại với hóa đơn và bấm **Lưu phiếu nhập**. Xem lại ở **Thuốc trong kho**.

### 2. Xem thuốc sắp hết hạn hoặc sắp hết hàng

- **Sắp hết hạn:** vào **Thuốc trong kho**. Xem ngưỡng cảnh báo ngày, rồi chọn **Sắp hết hạn** hoặc **Hết hạn**. Ngưỡng staging đang đặt 60 ngày.
- **Sắp hết hàng:** vào **Danh mục & giá**. Bấm **Sửa** thuốc, đặt **Tồn tối thiểu**, lưu rồi chọn bộ lọc **Sắp hết hàng**.

### 3. Chỉnh giá bán

Vào **Danh mục & giá → Sửa** đúng thuốc → sửa **Giá bán** → kiểm tra **Đơn vị bán** → lưu. Giá nhập là giá mua, không phải giá bán.

### 4. Kiểm đầu ca, cuối ca

1. Chọn **QUẦY → Kiểm đầu ca** hoặc **Kiểm cuối ca**.
2. Chọn đúng ngày và ca; nếu đã có phiếu **đang nhập**, mở phiếu đó để làm tiếp.
3. Đếm thuốc trên quầy và nhập số lượng. Đầu ca có thể bấm **Dùng số cuối ca trước**, rồi đối chiếu lại thực tế.
4. Bấm **Lưu nháp** để làm tiếp sau hoặc **Chốt kiểm kê** khi đã kiểm xong.

## Quản lý vật tư

### 1. Nhập thêm vật tư

1. Nếu là mặt hàng mới, thêm trước trong tab **Danh mục**.
2. Vào **Tồn kho → Kho → + Nhập hàng**.
3. Chọn vật tư, nơi cất, số lượng và giá mua; ghi chú nếu cần.
4. Bấm **Ghi nhận nhập hàng vào kho**.

### 2. Kiểm kê đầu ca, cuối ca theo phòng

1. Vào **Tồn kho → Theo phòng**, chọn phòng.
2. Ở dòng vật tư, mở **Thao tác → Kiểm kê** và nhập số đếm thực tế.
3. Chọn **Chỉ lưu số đếm** để ghi nhận chênh lệch; chọn **Cập nhật tồn theo số đếm** chỉ sau khi đã xác nhận số thực tế.
4. Ghi rõ **đầu ca/cuối ca** trong lý do rồi lưu. Lặp lại ở thời điểm còn lại.
Nếu phòng chưa có vật tư, cấp từ kho trước. Trang staging hiện không có tồn tại phòng Bàn xét nghiệm máu nên chưa có dòng để kiểm kê ở phòng đó.

### 3. Duyệt vật tư

Mặt hàng bật **Cần duyệt nhập** sẽ tạo yêu cầu chờ duyệt khi nhân viên nhập. Người có quyền vào **Chờ duyệt** để kiểm tra rồi **Duyệt** hoặc **Từ chối**; yêu cầu đang chờ chưa cộng vào tồn kho. Trang staging hiện không có yêu cầu chờ.

