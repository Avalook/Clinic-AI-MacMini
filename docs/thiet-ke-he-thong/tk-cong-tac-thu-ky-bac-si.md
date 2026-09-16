# Thư ký nhập, bác sĩ kiểm tra và duyệt — 15/09/2026

## Quyết định của Tuyền

- Vẫn cho đặt lịch trực tiếp với bác sĩ siêu âm.
- Thư ký nhập theo lời bác sĩ; bác sĩ xem bản đã lưu trên màn đang mở.
- Chỉ bác sĩ duyệt chỉ định. Điều dưỡng chỉ nhận chỉ định đã duyệt.
- Duyệt chỉ định khác với ký kết thúc toàn bộ bệnh án.

## Cách sửa trên code hiện có

1. Dùng `service_order` có sẵn: nháp → đã duyệt → được phân phòng → đang làm → đã làm. Giữ riêng người nhập và bác sĩ duyệt.
2. Duyệt đúng các ID và phiên bản bác sĩ đang xem. Sai phiên bản, sai phiên khám, sai bác sĩ thì từ chối toàn bộ. Biên nhận idempotency nằm cùng transaction.
3. Form đang mở nghe kênh SSE dùng chung, tải lại sau thay đổi và khi quay lại tab. Form có nội dung chưa lưu giữ nguyên, báo có bản mới; không âm thầm ghi đè.
4. PostgreSQL NOTIFY chỉ gửi tên bảng và clinic, không gửi nội dung bệnh án. Bổ sung hai bảng clinical_record và patient_medical_profile vào nguồn thông báo.
5. Nháp thuốc nằm trong bệnh án nhưng cột đó bị thu quyền SELECT của authenticated; bác sĩ/thư ký lấy qua RPC có kiểm role + clinic. Điều dưỡng chỉ đọc các cột bệnh án được cấp, không truy vấn cột nháp trực tiếp được.
6. Lưu nháp bệnh án không tự đánh dấu “khám xong”; bác sĩ kết thúc phiên khám bằng lệnh riêng sau khi các chỉ định cần cho vòng này hoàn tất.
7. Đơn thuốc mang ID từng dòng từ GET qua form tới POST; không ghép dòng đã cấp theo tên thuốc khi có thể nhầm.

## Giới hạn phải thể hiện rõ

- Đồng bộ sau khi lưu khác với truyền từng phím gõ; chưa tự bật autosave bệnh án.
- Đơn thuốc cần cơ chế duyệt riêng trước khi cho thư ký tạo thuốc thực thi. Không dùng ký FINALIZED để thay cho duyệt đơn.
- Đơn vị thuốc cần khớp kho hoặc có hệ số đổi. Chưa được đoán “hộp” bằng “viên”.
- Migration mới chỉ kiểm ở PostgreSQL dùng thử; chưa áp vào dữ liệu thật.

## Kiểm tra

Hàng đợi/TV SQL thật trên bảng TEMP; sửa kết quả giữ thời điểm nhận đầu tiên; nhãn ưu tiên không vượt check-in. Duyệt chỉ định kiểm bác sĩ, phiên bản, tenant, retry và quyền xem nháp. Frontend kiểm typing không bị ghi đè, TypeScript/lint và luồng tương tác phù hợp trước khi báo hoàn tất.
