# Bấm thử bản đồ một tệp — 23/10/2026

Mở `http://127.0.0.1:8790/ban-do-clinicai.html` sau khi chạy:

```bash
python3 scripts/ban-do-mot-tep.py
python3 -m http.server 8790 --bind 127.0.0.1 -d docs
```

Tệp cũng mở trực tiếp bằng bấm đúp, không cần máy chủ hoặc mạng.
Ảnh trong thư mục này là bằng chứng local; không đưa bản đồ lên dịch vụ web công khai.

## Kịch bản cho người thật

1. Ở Tổng quan, bấm Chạy lại hành trình, quan sát đủ 8 chặng. Chạy minh hoạ Thu,
   Tạm dừng rồi Chạy tiếp: phần ghi phát chậm để thấy từng tầng, đồng hồ giữ số nguồn.
   Chạy sự kiện, quan sát worker nghỉ 1 giây. Kéo thanh số người qua 1/11/101/1.000.
   Cuộn xuống biểu đồ 24 giờ và mở các thẻ trong 10 việc; bấm nút trong thẻ phải mở
   đúng khối nghiệp vụ hoặc hạ tầng ở Lego.
2. Vào Lego: chọn Thu tiền dịch vụ, Check-in khách, Bác sĩ chỉ định thêm dịch vụ,
   Gõ đơn thuốc. Đổi cả 3 chế độ. Khối và dây đi qua sáng cam, chi tiết có nhãn
   đã đo/ước. Bấm link Hệ thống trong Lego.
3. Ở Hệ thống: bấm đủ 5 tab; trong Bảng điều khiển bấm đủ 8 trang.
   Bấm link Sổ học. Mở Đặt lịch và Thu ngân, về Hành trình, vào Từ điển,
   lật một Thẻ tự kiểm. Trong Tốc độ của Sổ học, mở báo cáo: phải chuyển sang mục
   Tốc độ trong tệp gộp.
4. Bấm Việc cần làm, Tốc độ và Mục lục: bảng, code, danh sách đọc được, không lộ
   dấu Markdown. Sao chép địa chỉ có `#he-thong/luong` hoặc
   `#lego/nv/thu-ngan-01`, mở lại và kiểm đúng mục/thao tác.
5. Lặp ở 1280 và 375, đổi sáng/tối. Bật giảm chuyển động của hệ điều hành:
   các minh hoạ thành bản tĩnh, nút chạy vô hiệu. Mở bằng `file://` và kiểm ba
   bản đồ vẫn có dữ liệu. Không có thanh cuộn ngang của trang hoặc lỗi console.

## Ma trận đã kiểm bằng Chromium trên máy

| Kiểm | 1280 sáng | 1280 tối | 375 sáng | 375 tối |
|---|---|---|---|---|
| 7 mục; không tràn ngang; đồng bộ màu các khung | Đạt | Đạt | Đạt | Đạt |
| 4 thao tác Lego; 3 chế độ | Đạt | Đạt | Đạt | Đạt |
| 5 tab Hệ thống; 8 trang bảng điều khiển | Đạt | Đạt | Đạt | Đạt |
| 2 khối Sổ học; từ điển; lật thẻ; link Tốc độ | Đạt | Đạt | Đạt | Đạt |
| 5 animation: chạy lại, tạm dừng, chạy tiếp; slider 4 mốc | Đạt | Đạt | Đạt | Đạt |
| 10 thẻ → đúng khối Lego; không lỗi console/request ngoài | Đạt | Đạt | Đạt | Đạt |

Kiểm thêm: `file://`, giảm chuyển động, deep link thao tác Lego và khối Sổ học.
Script sinh chạy hai lần cho cùng nội dung trong cùng ngày/commit. Ruff 0.11.10
format/check xanh; 8 bài kiểm tự động trong `scripts/tests/test_ban_do_mot_tep.py`
xanh, độ phủ script sinh 94%. Kết quả CI máy ghi trong thân PR.

## Nút/link đã đụng

Trang chỉ là tài liệu, mọi người có tệp đều xem được; không gọi API ứng dụng.

| Màn | Nút/link | Kết quả / nơi tới |
|---|---|---|
| Thanh cố định | 7 mục | Đổi nội dung, cập nhật hash, giữ trong một tệp |
| Thanh cố định | Đổi sáng/tối | Đổi màu shell và ba khung đang mở |
| Tổng quan | Chạy/Tạm dừng/Chạy tiếp/Chạy lại × 5 | Điều khiển từng minh hoạ |
| Tổng quan | Thanh 1/11/101/1.000 | Đổi mô hình hàng chờ; ghi rõ ước |
| Tổng quan | Số liệu 24 giờ | Mở bảng số theo giờ, nguồn JSON đã đo |
| Tổng quan | 10 thẻ + Xem khối Lego | Mở khối liên quan, tự chọn chế độ nghiệp vụ/hạ tầng |
| Việc cần làm / Tốc độ / Mục lục | Liên kết bản đồ đã gộp | Sang mục tương ứng bằng hash |
| Lego | 4 thao tác nêu trên | Hiện dây, bước và nguồn; không mất dữ liệu đã làm giàu |
| Lego | 3 chế độ | Nghiệp vụ / hạ tầng / 1.000 người |
| Lego / Hệ thống / Sổ học | Link qua lại | Đổi mục ở trang mẹ, không tải trang rỗng trong khung |
| Hệ thống | 5 tab | Môi trường, lượng request, bảo mật, bảng điều khiển, hàng chờ |
| Hệ thống | 8 trang bảng điều khiển | Hiện trang tương ứng |
| Sổ học | Hành trình; Đặt lịch; Thu ngân | Điều hướng nội bộ khối bằng hash |
| Sổ học | Từ điển; Thẻ tự kiểm | Tra tên và lật thẻ |
| Sổ học | Tốc độ → báo cáo | Sang mục Tốc độ của tệp gộp |

## Chỗ dùng ước và giới hạn

- Thời gian hành trình bệnh nhân và tốc độ chuyển động dùng để kể chuyện, không
  phải thời gian chờ khám. Phần ghi của minh hoạ Thu phát chậm; đồng hồ không tuyến tính.
- Ghi tiền khoảng 0,13 giây là cả lệnh đã đo. Khoảng 7 giây chờ Thu là **ước từ
  2 lượt tải × p95 3,4 giây đã đo**, không phải số đo riêng từng tầng Caddy/Next/API.
- Mô hình đông người và hàng chờ lấy cấu hình/các ước tính của chế độ 1.000 người
  trong Lego; chưa thử tải thực tế. Postgres không tự nhiên nhận 1.000 kết nối:
  pool API chặn trước ở 20, ngoài ra còn các khách kết nối khác.
- Worker nghỉ 1 giây là hành vi code; thời gian minh hoạ bên nhận xử lý chưa phải
  đo thực tế. Số request theo giờ là ảnh chụp JSON nguồn, không cập nhật trực tiếp.
- Link đến tệp không nằm trong phạm vi gộp giữ tên nguồn để tra trong repo.
  Link HTTPS tham khảo giữ nguyên; bộ kiểm chỉ bấm các điều hướng nội bộ được liệt kê.
