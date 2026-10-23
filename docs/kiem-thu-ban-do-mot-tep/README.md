# Bản đồ ClinicAI một tệp — cách đọc và nghiệm thu

Bấm đúp `docs/ban-do-clinicai.html` để mở ngoại tuyến. Hoặc xem local:

```bash
python3 scripts/ban-do-mot-tep.py
python3 -m http.server 8790 --bind 127.0.0.1 -d docs
```

Chỉ HTML đầu ra cần mang đi. Các tệp `scripts/ban-do-assets/` là nguồn giao diện
lúc sinh; HTML đã nhúng toàn bộ chúng và toàn bộ dữ liệu. Không CDN.

## Cách đọc mới

- **Bắt đầu từ Tổng quan:** nút “Bắt đầu cùng bệnh nhân” dẫn vào một câu hỏi,
  một bước. Sáu câu hỏi đi từ bệnh nhân → một lần Thu → sự kiện → đông người →
  số đo 24 giờ → 10 việc cần sửa. Bấm Trước/Tiếp, chọn bước hoặc Tự chạy.
- **Tra một nút ở Lego:** lọc nhóm hoặc tìm không dấu. Đọc một bước, nhìn các
  khối tham gia. Mở dần API, bảng, bên nhận, giao dịch, thời gian, chuỗi sự kiện
  và đề xuất. Bấm bảng hoặc khối để hiểu tên và xem các thao tác liên quan.
- **Khi cần sâu hơn:** mở bản Lego gốc ở cuối mục; Hệ thống, Sổ học và hai báo
  cáo vẫn đầy đủ. Mục lục trong báo cáo giúp nhảy tới đúng đoạn.
- **Điều chỉnh cách nhìn:** sáng/tối, Chữ lớn hơn và tìm toàn bản đồ ở thanh
  trên. Điện thoại dùng nút Mục lục và ô chọn bước, không phải kéo một sơ đồ lớn.

## Kịch bản bấm thử cho người thật

1. Mở Tổng quan → Bắt đầu cùng bệnh nhân. Bấm Bước tiếp qua 8 chặng; quay lại,
   thử Tự chạy rồi Tạm dừng. Mỗi bước chỉ có một chỗ đang đọc. Mở Đọc kỹ để thấy
   đủ màn, thao tác và quy tắc. Sang câu hỏi Một nút đi đâu?, đọc đủ 8 bước Thu;
   phân biệt 0,13 giây cả lệnh ghi đã đo và ~7 giây chờ ước từ các lượt tải.
2. Đọc Vì sao màn đổi?: worker nghỉ 1 giây, giao từng bên nhận, rồi tin SSE
   nhắc màn đọc lại. Sang Đông người, chọn 1/11/101/1.000 và kiểm pool 20 chặn
   trước Postgres 100. Sang Một ngày thật, bấm cột 20h: 15.790 request; mở bảng
   24 giờ. Sang Sửa gì trước, mở 10 việc và thử nút tới khối liên quan.
3. Vào Lego, tìm “thu tien”, chọn Thu tiền dịch vụ. Bấm Sau đến cuối, mở phần
   bảng rồi bấm payment; mở các bên nhận; mở một khối hạ tầng. Trên điện thoại,
   dùng Trở về danh sách để chọn việc khác. Mở bản Lego gốc và thử 3 chế độ.
4. Vào Hệ thống, thử 5 phần và 8 trang Bảng điều khiển. Vào Sổ học, mở Đặt lịch,
   Thu ngân, Từ điển và lật Thẻ tự kiểm. Bấm nguồn Tốc độ để sang báo cáo trong
   tệp. Ở Việc cần làm / Tốc độ, mở mục lục và bấm một tiêu đề để nhảy đoạn.
5. Lặp ở 1280 và 375, sáng/tối; đổi Chữ lớn hơn rồi trở lại. Tìm tên code ở
   thanh tìm toàn bản đồ. Sao chép link có hash và mở lại. Bật giảm chuyển động
   rồi mở bằng file://: bản tĩnh vẫn đọc và đổi bước được, nút Tự chạy vô hiệu.

## Bảng nút/link đã đụng

Mọi người có tệp đều xem được; trang tài liệu không gọi API ứng dụng.

| Màn | Nút/link | Kết quả |
|---|---|---|
| Thanh trái / Mục lục điện thoại | 7 mục | Đổi mục và hash, báo đang ở đâu |
| Thanh trên | Tìm toàn bản đồ | Tìm thao tác, khối, từ điển; bấm đi đúng nội dung |
| Tuỳ chỉnh | Sáng/tối; Chữ lớn hơn | Đổi shell và ba khung gốc, lưu lựa chọn local |
| Trợ năng | Đến nội dung | Focus nội dung, giữ mục đang đọc |
| Tổng quan | Bắt đầu cùng bệnh nhân | Đi thẳng vào bước đầu |
| Tổng quan | 6 câu hỏi; Câu hỏi trước/tiếp | Mỗi lần hiện một chương |
| Tổng quan | Bước trước/tiếp; ô chọn bước; Tự chạy/Tạm dừng; Về đầu | Điều khiển từng luồng |
| Tổng quan | Thanh 1/11/101/1.000 | Đổi mô hình sức chứa, giải thích hàng chờ |
| Tổng quan | 24 cột giờ; bảng số | Hiện số đúng giờ, nguyên dữ liệu đã đo |
| Tổng quan | 10 thẻ → khối; kế hoạch đầy đủ | Mở giải thích khối hoặc đúng đoạn báo cáo |
| Lego mới | Lọc nghiệp vụ/hạ tầng, nhóm, tìm, xoá lọc | Tra đủ 74 thao tác |
| Lego mới | Chọn thao tác, Trước/Sau, phím mũi tên, mục lục bước | Đủ 537 bước từ nguồn |
| Lego mới | Bấm khối / bảng; đóng giải thích | Hiện tên dễ hiểu, cấu hình, nguồn, mọi thao tác liên quan |
| Lego mới | 7 phần tra cứu mở rộng | Giữ toàn bộ API, bảng, sự kiện, giao dịch, thời gian, quy tắc, đề xuất |
| Lego gốc | Mở bản gốc; 3 chế độ; thao tác nổi bật | Giữ khối/dây, phân tích 1.000 người |
| Hệ thống | 5 phần; 8 trang bảng điều khiển | Nội dung nguyên nguồn, chữ lớn hơn |
| Sổ học | Khối, từ điển, thẻ, tốc độ, cách đọc | Học và tra cứu bằng hash |
| Báo cáo | Mục lục trong từng mục | Nhảy tới tiêu đề, không mất mục hiện tại |

## Bằng chứng kiểm tra

- Ruff 0.11.10 format/check xanh; 9 bài kiểm Python xanh, độ phủ generator 94%.
- JavaScript của ba giao diện mới qua `node --check`.
- Chromium bấm thật 1280/375 × sáng/tối: 7 mục, 6 chương, 20 bước Tổng quan,
  10 nút khối, thanh 4 mốc, biểu đồ 24 giờ, 5 tab/8 trang Hệ thống, 2 khối Sổ
  học/từ điển/lật thẻ, bản Lego gốc. Không lỗi console, request ngoài hoặc tràn
  ngang. Kiểm thêm file://, reduced motion và deep link.
- Riêng Lego mới đối chiếu đủ 74 thao tác / 537 bước, 23 nhóm và 23 khối,
  bảng và các đề xuất, tìm không dấu, trạng thái tìm rỗng, mobile.
- CI máy lần đầu trên 8986d0be: 4/5 nhóm xanh; backend có 1 lỗi tại
  test_partner_two_types_of_orders (kỳ vọng SafetyGateError không phát sinh).
  Lần cải tiến cách đọc chưa chạy lại CI đầy đủ vì ngoài khung 08:00–23:00
  được phép trong đề bài. Trạng thái này được ghi rõ trong PR draft.

## Số đo và ước

- Tự chạy có nhịp kể chuyện để đọc được, không mô phỏng thời gian thực của
  từng tầng. Bước nào có số đo thì giữ nguyên ngày và nhãn nguồn.
- 0,13 giây là cả lệnh ghi đã đo; ~7 giây chờ Thu là ước từ 2 × p95 3,4 giây
  tải bảng đã đo. Không coi nhãn tổng của đoạn có cả hai loại là “đã đo”.
- Hàng chờ đông người lấy cấu hình và phân tích trong Lego, chưa thử tải.
  Chỉ riêng API vào Postgres tối đa 20 kết nối, còn các bên khác có pool riêng.
- Worker nghỉ 1 giây là hành vi code. Request 24 giờ là ảnh chụp số đo đã lưu,
  không phải số bệnh nhân và không phải bảng giám sát đang cập nhật.
- Nội dung, tên code và phát hiện giữ nguyên nguồn; không đo lại prod trong
  phiên này. Những phần chưa có trong nguồn đều ghi rõ khi đọc sâu.
