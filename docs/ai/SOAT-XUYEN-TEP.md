# Soát xuyên tệp — thiết kế và giới hạn

Ngày 18/10/2026. Theo yêu cầu của Quang: đánh giá các mối nối trong hệ thống,
thay vì chỉ tìm lỗi trong từng đoạn 330 dòng độc lập.

## Mục tiêu

Cho người đọc và người phản biện cùng nhận mã của các tệp liên quan đến một
luồng, có đường dẫn và số dòng thật. Lần theo giao diện → route chuyển tiếp →
router → service → SQL/sự kiện khi liên kết phân giải được từ mã. Chỉ đọc,
không sửa nghiệp vụ và không thay người duyệt quyết định một phát hiện là lỗi.

## Quyết định

- Bổ sung chế độ riêng trong bộ soát hiện có; giữ cách quét từng đoạn để đối chiếu.
- Dựng ngữ cảnh từ liên kết có chứng cứ trong mã. Tên gần giống hoặc từ khóa
  nghiệp vụ không đủ để coi hai tệp có quan hệ gọi nhau.
- Giới hạn kích thước và độ sâu ngữ cảnh. Ghi rõ phần bị cắt, cạnh chưa phân
  giải và tệp chưa đọc; không biến giới hạn token thành kết luận hệ thống sạch.
- Phản biện phải dùng cùng ngữ cảnh xuyên tệp; trích dẫn sang tệp liên quan
  cũng phải được mở lại xác minh.
- Sổ đọc xuyên tệp tách khỏi lượt cũ. Dấu nội dung bao gồm các phụ thuộc trong
  gói, để thay đổi tệp phụ buộc đọc lại. Lỗi gọi model không được tính đã đọc.
- Độ phủ tách số đã chọn, hoàn tất và lỗi. Đọc đủ một gói chỉ chứng minh đã
  gửi đủ ngữ cảnh được kê khai, không chứng minh model hiểu hết hoặc tìm hết lỗi.

## Ranh giới

Đây là chế độ hỗ trợ soát kiến trúc bằng ngữ cảnh liên quan, không phải một
kiến trúc sư tự xác minh toàn bộ hệ thống. Cạnh import chỉ chứng minh phụ thuộc
module; chuỗi bảng/sự kiện chỉ chứng minh tham chiếu hợp đồng. Muốn kết luận
luồng chạy thực tế phải kiểm caller, nhánh điều kiện và bằng chứng chạy/test.

Giữ cổng mạng `khach.py`, bộ che mã và giới hạn chi phí hiện có. Không gửi dữ
liệu database, không đọc khóa bằng công cụ khác, không tự gỡ `ket-qua/DUNG`.
Không chạy model trả phí trong lúc triển khai và kiểm thử. Chỉ Quang cho chạy
tiếp trên trang tiến độ; trước lượt chạy thật cần biết phạm vi và tổng chi phí.

Lời gọi động, SQL động, ràng buộc database đã áp thực tế và hành vi tranh chấp
cần kiểm chứng riêng. Phân tích tĩnh không phải ảnh chụp schema đang chạy.

## Kiểm chứng

Fixture nhỏ có liên kết xuyên tệp và nhánh không phân giải được; kiểm giới hạn
ngữ cảnh, lọc tệp cấm, trích dẫn tệp phụ, thay đổi phụ thuộc làm mất cache và
lỗi model không thành công giả. Giả lập cổng model để kiểm cả đọc lẫn phản
biện mà không tiêu tiền. Chạy lại bộ test an toàn của agent, lint và kiểm kiểu.

## Hoàn tác

Chế độ mới là tùy chọn. Có thể quay về quét từng đoạn và giữ nguyên toàn bộ
kết quả cũ; không có migration hay thay đổi prod/staging.
