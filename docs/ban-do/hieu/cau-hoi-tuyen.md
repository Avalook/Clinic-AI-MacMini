# Câu hỏi cần Tuyền chốt

Các câu dưới đây là quyết định nghiệp vụ hoặc ưu tiên bảo trì, không tự đổi luật trong code.

## 1. Phí tái khám

Luồng thu thật đang dùng `dong_kham_theo_chon`; mức 150.000đ trong `dong_kham` không thấy được gọi ở đường đó, còn mức 400.000đ có thể đang được lễ tân chọn theo danh mục.

**Ví dụ:** khách tái khám, màn đang chọn phí 400.000đ nhưng quy tắc cũ gợi 150.000đ. Mức nào là đúng?

- A. Tái khám luôn 150.000đ, máy chủ tự xác định theo lịch sử khách.
- B. Tái khám 400.000đ theo danh mục hiện tại.
- C. Không có mức riêng; lễ tân chọn dịch vụ/mức thu và ghi lý do nếu khác.
- D. Quy tắc khác: ghi rõ điều kiện và mức tiền.

## 2. Bỏ dịch vụ sau khi đã thu

**Ví dụ:** khách đã trả 500.000đ cho hai dịch vụ 300.000đ + 200.000đ, sau đó bỏ dịch vụ 200.000đ. Hệ thống coi 200.000đ là tiền thừa để hoàn hoặc giữ lại.

- A. Cho bỏ; tạo tiền thừa và bắt buộc hoàn hoặc giữ lại có lý do trước check-out.
- B. Không cho bỏ dịch vụ đã thu; phải dùng quy trình huỷ/hoàn riêng.
- C. Cho bỏ nhưng chỉ thu lại phần còn làm; kế toán xử lý số dư theo quy trình khác.
- D. Quy tắc khác: ghi rõ thời điểm và người có quyền quyết định.

## 3. Khoá kết quả thai kỳ và thuốc khách trả

Hiện có test cho thấy hai quyết định này không hoàn tác được.

**Ví dụ:** đánh dấu kết cục thai kỳ nhầm; hoặc phân loại thuốc trả là huỷ nhưng sau đó phát hiện thuốc còn nguyên.

- A. Giữ khoá cứng; nếu sai thì lập bản ghi điều chỉnh mới, không sửa quyết định cũ.
- B. Cho người có quyền hoàn tác bằng lý do, ghi người làm và thời điểm vào nhật ký.
- C. Chỉ cho hoàn tác trong một khoảng thời gian / trước một bước nghiệp vụ xác định.
- D. Quy tắc khác: ghi rõ vai trò và giới hạn.

## 4. Bốn tệp test integration bị CI bỏ qua

CI hiện bỏ qua thư mục `src/tests/integration`; có bốn tệp cho bệnh nhân, đặt lịch, nhân sự và RabbitMQ, trong đó một tệp gọi route cũ.

**Ví dụ:** chạy lại bốn tệp sẽ mất khoảng 10 phút, nhưng một test có thể cần sửa theo API hiện tại.

- A. Khôi phục cả bốn vào CI; sửa test theo hành vi hiện tại rồi chạy.
- B. Chỉ khôi phục các test còn kiểm luồng đang dùng; xoá test đã thay thế.
- C. Giữ bỏ qua, nhưng ghi rõ lý do và nơi có test thay thế.
- D. Quy tắc khác: cho biết tệp nào cần giữ/bỏ.

## 5. Công cụ `/traffic`

Trang `/traffic` đang lưu tên đăng nhập và mật khẩu nguyên văn trong `sessionStorage`.

**Ví dụ:** người dùng đăng nhập trên máy dùng chung; thông tin còn trong tab đến khi tab/phiên trình duyệt kết thúc.

- A. Gỡ `/traffic` khỏi sản phẩm.
- B. Giữ nhưng giới hạn cho tài khoản/nhóm vận hành, đồng thời chuyển xác thực sang cơ chế không lưu mật khẩu trong trình duyệt.
- C. Giữ như công cụ nội bộ tạm thời, không cấp cho tài khoản phòng khám.
- D. Quy tắc khác: nêu người dùng và yêu cầu bảo vệ.

## 6. Đơn thuốc trong bệnh án

Code hiện cho phép thư ký y khoa/điều dưỡng đủ quyền ghi đơn trực tiếp; nháp cũ vẫn có đường để bác sĩ duyệt. Cần xác nhận đây là quyết định đang áp dụng.

**Ví dụ:** thư ký nhập 2 thuốc; đơn có xuất hiện ngay ở quầy thuốc hay phải chờ bác sĩ xác nhận?

- A. Ghi trực tiếp theo quyền hiện tại; không cần bước bác sĩ duyệt.
- B. Mọi đơn do người không phải bác sĩ nhập phải thành nháp, chỉ gửi quầy thuốc sau khi bác sĩ duyệt.
- C. Chỉ một số nhóm thuốc/ca cần duyệt; nêu nhóm và điều kiện.
- D. Quy tắc khác: ghi rõ ai kê, ai duyệt, và thời điểm nhà thuốc được thấy đơn.

## 7. Cảnh báo trùng số điện thoại

Route cũ `/api/patients/check-phone` bị proxy chặn 410; màn tạo khách hiện gọi `/api/patients/check-duplicate`, đối chiếu điện thoại, họ tên và năm sinh. Cần chốt việc giữ route cũ/test cũ hay dọn hẳn.

**Ví dụ:** khách cũ đổi số, nhập đúng họ tên + năm sinh nhưng không nhập SĐT cũ — endpoint mới có thể cảnh báo theo tên/năm sinh.

- A. Giữ cảnh báo qua `check-duplicate`; cập nhật test và xoá route cũ khỏi cây nguồn nếu không cần.
- B. Khôi phục `/check-phone` như đường riêng chỉ kiểm SĐT.
- C. Chỉ cảnh báo theo đủ SĐT + họ tên + năm sinh; không cảnh báo khi thiếu trường.
- D. Quy tắc khác: nêu trường tối thiểu và khi nào được tạo hồ sơ mới.
