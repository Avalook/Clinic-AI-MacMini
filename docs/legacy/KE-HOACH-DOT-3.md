> LỖI THỜI (chuyển legacy 01/10/2026): đợt 3 đã xong, lên prod 27–30/09 — đừng làm theo.

# Kế hoạch đợt 3 — góp ý phòng khám sau bản deploy a7711b7 (27/09/2026)

Nguồn: hai bản góp ý của phòng khám (chung / CSKH / BS–TKYK / thu ngân; "cần làm
rõ" / "cần thảo luận" / "feedback cũ") + bảng việc Notion. Soát bằng code + DB
local + số đếm prod (chỉ đọc). Mỗi việc: gói code → kiểm → bấm thật.

Ký hiệu: ✅ xong · ⏳ đang code · ❓ chờ phòng khám/Tuyền trả lời · — không làm.

## Gói code

| Gói | Nhánh | Góp ý | Trạng thái |
|---|---|---|---|
| 1 Danh mục chỉ định | `claude/dot3-danh-muc` | Soi âm hộ không thấy khi chỉ định thêm; tick trương lực cơ ra mẫu soi âm hộ; ký hiệu `*` `•` `-` | ⏳ |
| 2 Tự lưu chắc chắn | `claude/dot3-tu-luu` | "save liên tục có đảm bảo không"; lỗi phải hiện cạnh nút Save + tô vùng lỗi | ⏳ |
| 3 Phiếu khám gọn | `claude/dot3-phieu-gon` | Tiền sử chọn rồi mới hiện; dị ứng Có/Không → Chi tiết; CLS gần đây; "thu lại dạng toggle" | ⏳ |
| 4 Sinh hiệu theo buổi | `claude/dot3-buoi-kham` | Đăng ký thêm dịch vụ lần 2 bị đẩy về Đo sinh hiệu | ⏳ |
| 5 Sinh hiệu trên điện thoại | `claude/dot3-sinh-hieu-dt` | Bảng việc: "Giao diện PWA cho điện thoại đối với sinh hiệu" | ⏳ |
| 6 Ảnh + bản in | `claude/dot3-anh-in` | In phiếu vẫn báo "chưa hoàn tất"; Doppler âm vật / SA không hiện ảnh | ⏳ |
| 7a Gác quyền theo lego | `claude/dot3-quyen-lego` | Bảng việc: "thừa thiếu nút như ở bác sĩ tư vấn"; mọi vai xem hành trình; "Việc cần xử lý" lỗi; lễ tân + thu ngân hỗ trợ nhau | ⏳ |
| 7b Thoát / trang chủ / check-out | `claude/dot3-thoat-trang-chu` | Nút Thoát góc trên phải; trang chủ đặt lịch theo ngày; check-out đang ở bước nào | ⏳ |
| 7c Tầng / lịch trực / sắp xếp | `claude/dot3-lich-tang` | Ẩn số tầng; đổi tên phòng Thủ thuật; lịch trực kèm tên + vai; danh sách BN gần nhất lên trên | ⏳ |
| 9 Đối tác tự thu + giá tạm | `claude/dot3-doi-tac-tu-thu` | Q1: khách trả thẳng đối tác, màn đối tác ghi nhận thanh toán; Q2: quản lý sửa phí khám sau (chip "giá tạm") | ⏳ |
| 8 Quầy / xếp phòng / kho / dọn | `claude/dot3-quay-kho` | Thêm khách hàng lên trước; không xếp được phòng; tự động điều phối (dây bật/tắt); đầu dò; chụp phim 0đ; làm sạch dữ liệu + 17 lượt treo | ⏳ |

## Phát hiện khi soát (gốc rễ)

- **Hai hệ gác quyền song song**: lệnh hỏi lego, còn bảng đọc (hàng chờ, Xem lượt,
  Hành trình) + nút giao diện hỏi VAI → tài khoản chỉ lego Tư vấn bị 403 hàng chờ.
- **Danh mục chỉ định vẫn trích từ HTML v5 cũ**, chưa theo bản mẫu M / phiếu giấy →
  Soi âm hộ sai khối, gợi ý mẫu sai, nhãn thô, 2 dòng tiêu đề thu tiền được.
- **Sinh hiệu tính theo lượt, không theo buổi** → lễ tân mở lượt mới để thêm dịch vụ
  thì khách bị đo lại.
- **Tự lưu mất chữ** khi đổi khách/đóng tab trong 1,5 giây; Hoàn tất bấm được khi chưa lưu.
- **Bản in lấy mọi phiếu của chỉ định** kể cả phiếu nháp bị bỏ khi đổi mẫu → "BẢN NHÁP"
  dù đã Hoàn tất (prod có ca thật: SA 4D TC-BT).
- Ảnh Doppler âm vật trên prod: CÓ, gắn đúng chỉ định, tải được — hiện được ở bản
  a7711b7. Vẫn sửa: quyền xem ảnh theo lego, DICOM, ảnh tải ở Khách hàng không gắn chỉ định.

## Tuyền đã chốt 27/09

- **Chỉ dùng lego** để gác mọi màn và nút — bỏ gác theo vai (gói 7a mở rộng).
- **Q1:** dịch vụ đối tác khách **trả trực tiếp đối tác**; bill phòng khám không cộng; màn đối tác ghi nhận thanh toán (gói 9). Gói 8 bỏ việc "chụp phim 0đ".
- **Q2:** giá phí khám để **quản lý tự điều chỉnh** sau (gói 9 gắn chip "giá tạm").
- **Q5:** khách check-out rồi quay lại trong ngày → **thu phí khám mới** (giữ hoá đơn như hiện tại).
- **Q9:** làm sạch = **xoá hết để bàn giao mới tinh** (script `scripts/don-prod-truoc-ban-giao.sh --that`, Tuyền chạy lúc bàn giao; gói 8 vá bảng thiếu).

## Chờ phòng khám / Tuyền trả lời (chưa code)

| # | Câu hỏi | Vì sao |
|---|---|---|
| Q1 | Dịch vụ đối tác (XN máu, HPV, ThinPrep, chụp phim…): khách trả **quầy Dr4Women** hay trả **thẳng đối tác**? Nếu quầy thu: là doanh thu phòng khám hay **thu hộ**? Danh sách chính xác dịch vụ đối tác? | "Bill không tính chi phí từ đối tác" có 2 nghĩa; hiện 25 dịch vụ đối tác cộng đủ giá bán vào bill |
| Q2 | Phí khám loại nào sai, giá đúng? Hiện: Nội tiết 500k, Thủ thuật 300k, Sàn chậu 300k là **giá giả định**; Hiếm muộn chỉ có giá lần đầu 400k (KiotViet có tái khám 150k) | "Phí khám sai giá" |
| Q3 | Bảng giá chi tiết từng XN máu / nội tiết (theo đối tác nào)? 9 mã KiotViet đối tác chưa có giá (NIPT…) — chọn là khoá cả lượt thu | "Giá XN cần chi tiết hơn" |
| Q4 | "Kho mở điền mua chưa cần đối soát" = cho **nhập hàng** không cần số lô/hạn dùng, hay cho **bán/giao** khi kho chưa nhập? (39/91 mặt hàng prod chưa có lô) | Hiện kho chặn âm (luật thiết kế) |
| Q5 | Khách khoa lõi quay lại cùng ngày đi thẳng dịch vụ: **có thu lại phí khám** không? | Gói 4 chưa đụng hoá đơn |
| Q6 | "Thủ thuật → Thủ thuật/Sàn chậu" là **tên phòng** (quản lý tự đổi ở Cấu hình phòng khám) hay **loại khám** khi đặt lịch? | Hai thứ cùng tên |
| Q7 | Tắt hẳn 2 dịch vụ "XN dịch âm đạo" (300k) và "Laser sàn chậu" (7tr) — vốn là dòng tiêu đề trên phiếu giấy? | Gói 1 chỉ gỡ khỏi danh sách tick |
| Q8 | "Cận lâm sàng gần đây" = các bảng CLS gõ tay trong phiếu? "Thu lại dạng toggle" = gập từng mục phiếu? | Gói 3 làm theo cách hiểu này |
| Q9 | Làm sạch dữ liệu: xoá hết để bàn giao mới tinh, hay giữ khách thật chỉ xoá nháp/thừa? | Script hiện chỉ xoá TOÀN BỘ |
| Q10 | Đầu dò thu ở quầy thuốc hay quầy dịch vụ? Có bán TPCN cho khách không khám không? | Gói 8 đặt đầu dò ở quầy thuốc |

## Không làm (có lý do)

- **Dùng chung 1 tài khoản lễ tân + thu ngân** — mất người chịu trách nhiệm thu/hoàn
  tiền. Thay bằng bật thêm lego cho từng tài khoản ở /phan-quyen (gói 7a cho thanh bên
  không gập lego đang bật).
- **Tự động điều phối** — bảng việc ghi "dùng lễ tân chỉ định phòng". Gói 8 thêm
  dây bật/tắt "chỉ áp phòng lễ tân chọn" (mặc định tắt = như hiện tại); Tuyền bật ở
  /settings/day-noi khi muốn.
- **Nút Lưu thường trực** — Tuyền đã chốt không cần; thay bằng tự lưu chắc chắn +
  nút [Lưu ngay] chỉ hiện khi còn chữ chưa lưu / lưu lỗi.

## Đã xong từ các đợt trước (bảng Notion)

Cấu trúc 3 phần màn khám; chỉ định thêm; giao diện (màu nút xem KQ, chỗ cho cách
dùng thuốc, dòng tổng tiền thừa, số booking + check-in); in phiếu 2 trang 3 mục.
