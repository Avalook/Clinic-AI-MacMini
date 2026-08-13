# Checklist test ClinicAI

Người test: **Tuyền** · Lập ngày **13/08/2026** · Môi trường: **staging trên máy chủ, cổng `:8080`**

Bản Word để điền tay: `Checklist test ClinicAI - Tuyen - 13.08.2026.docx`

> Tài liệu *Hướng dẫn kiểm thử Dashboard ver2* đang trỏ vào link Vercel cũ với tài
> khoản `@gmail.com`. Đó là bản khác, không phải hệ thống đang chạy. Test trên
> staging `:8080` với tài khoản `@dr4women.vn`.

---

## Ưu tiên 1 — Thao tác công việc thực tế của CSKH
*Nguồn: Recap meeting 8/5/26*

| | Việc cần test | Kỳ vọng / đã đo được |
|---|---|---|
| ☐ | Nhận lịch từ nhiều nguồn (Pancake, giới thiệu, bác sĩ hẹn tái khám) | Đặt được cho cả ba nguồn |
| ☐ | Đặt lịch khách **mới** | Tạo hồ sơ + lịch trong một luồng |
| ☐ | Đặt lịch **tái khám** từ Danh sách bệnh nhân | Nút Tái khám mở cửa sổ đặt lịch |
| ☐ | Gọi xác nhận trước 7–10 ngày rồi cập nhật lịch | Sửa/xoá được, có ghi vết |
| ☐ | Đặt trùng khung giờ với CSKH khác | Người thứ hai thấy "đang có người giữ" (10 phút) |
| ☐ | Phân biệt khách mới / khách cũ trên màn hình | Thứ Google Sheet không làm được |
| ☐ | Thống kê theo nhân sự CSKH (tính KPI) | Chị Hoa nêu đây là insight cần có |
| ☐ | Lễ tân check-in khách đặt online | Ngay trên Lịch hẹn khám |
| ☐ | Lễ tân thêm khách vãng lai | Khách trong ngày tự động check-in |
| ☐ | Hành trình bệnh nhân theo thời gian thực | Đổi ở máy này, máy khác thấy ngay |

## Ưu tiên 2 — Feedback ver1 (18 mục)
*Sheet ghi tất cả "chưa thực hiện" — đó là trạng thái tháng 5. Quét mã nguồn 13/08 thấy phần lớn đã có. "Có trong mã nguồn" chưa chắc "chạy đúng".*

| | Mục | Đã đo được |
|---|---|---|
| ☐ | 1 · Tài khoản riêng cho Trưởng ca | đã có |
| ☐ | 2 · Quyền bác sĩ tra cứu / cập nhật hồ sơ | đã có |
| ☐ | 3 · Tài khoản Thư ký Y khoa | đã có |
| ☐ | 4 · Tìm kiếm không dấu tiếng Việt | dấu vết mỏng — test kỹ |
| ☐ | 5 · Quản lý lịch làm việc | đã có |
| ☐ | 6 · Giới tính "Khác" | **chưa có** |
| ☐ | 7 · Nhiều bệnh nhân trong một khung giờ | đã có — xem Ưu tiên 3 |
| ☐ | 8 · "Vấn đề khiến BN đi khám" + "Lĩnh vực" | cần xác minh |
| ☐ | 9 · Cảnh báo ngay khi trùng số điện thoại | đã có |
| ☐ | 10 · Dropdown địa chỉ hành chính | đã có, sau sáp nhập |
| ☐ | 11 · Nhập ngày tháng dễ hơn | nhìn bằng mắt |
| ☐ | 12 · Bỏ bước "Bác sĩ duyệt" khi check-in | cần xác minh |
| ☐ | 13 · Lễ tân sửa thông tin bệnh nhân | sheet ghi Phase 2 |
| ☐ | 14 · Tóm tắt quá trình điều trị | đã có |
| ☐ | 15 · Điều dưỡng sửa "Lý do khám bệnh" | test theo vai |
| ☐ | 16 · Bắt buộc điền chỉ số sinh tồn | đã có |
| ☐ | 17 · Hồ sơ khám riêng theo chuyên khoa | đã có 5 form: PK · SK · NT · NK · HMVS |
| ☐ | 18 · Tài khoản TKYK | trùng mục 3 |

## Ưu tiên 3 — Feedback ver2

| | Việc cần test | Kỳ vọng / đã đo được |
|---|---|---|
| ☐ | Giao diện lịch làm việc có gây hiểu nhầm không | HR tưởng đăng ký khung nào là hệ thống tự xếp theo |
| ☐ | BS Thành 18h00–18h15 | Chị yêu cầu **10**. Đang cài **10 online + 1 trực tiếp = 11** |
| ☐ | BS Thành từ 18h15 | Chị yêu cầu **4**. Đang cài **4 + 1 = 5** |
| ☐ | Bác sĩ khác, mỗi 15 phút | Chị yêu cầu **3**. Đang cài 18h00→4 · 18h15→5 · 18h30→6 · từ 18h45→4 |
| ☐ | Khách mới phải qua BS Thành lần đầu | **CHƯA CÓ** — không tìm thấy luật này trong hệ thống |

**Logic không sai, số nhập sai.** Trigger đếm **hai làn độc lập**: khách đặt online theo ô "thường", khách tới thẳng quầy theo ô "ưu tiên"; tổng = cộng hai ô. Muốn "8 online + 2 trực tiếp = 10" thì phải cài **8 và 2** — hiện cài **10 và 1** nên thành 11. Sửa bằng cấu hình, không phải sửa code.

## Ưu tiên 4A — Mười tình huống phát sinh
*Nguồn: ảnh chị gửi (chị nói 4 ảnh, thực tế có 3)*

| | Tình huống · cách kiểm tra | Kết quả mong đợi / đã đo được |
|---|---|---|
| ☐ | 1 · Nhập thiếu trường bắt buộc rồi lưu | Báo rõ trường thiếu, **không mất dữ liệu đã nhập**. Đã đo: có chặn; phần "không mất dữ liệu" phải test tay |
| ☐ | 2 · Nhập sai định dạng (SĐT có chữ, ngày sai) | Cảnh báo dễ hiểu. Đã đo: SĐT kiểm ở máy chủ; ngày sai trước 13/08 cho lỗi khó hiểu — **đã vá hôm nay** |
| ☐ | 3 · Bấm nút lưu / đặt lịch nhiều lần | Không tạo trùng. Đã đo: **đặt lịch** có khoá chống bấm hai lần · **thu tiền** an toàn nhờ ràng buộc `UNIQUE(visit_id, kind)` · **tạo hồ sơ** chặn trùng CCCD + cảnh báo trùng SĐT · **các màn còn lại chưa có khoá — phải test tay** |
| ☐ | 4 · Mất mạng hoặc F5 khi đang nhập | Không tạo dữ liệu dở dang, biết đã lưu hay chưa. **Đã đo: CHƯA CÓ** — không lưu nháp, không cảnh báo rời trang. Đang gõ bệnh án mà F5 hoặc mất điện là **mất trắng** |
| ☐ | 5 · Hệ thống phản hồi chậm khi đông người dùng | Có trạng thái đang xử lý, không phải bấm lại |
| ☐ | 6 · Hai nhân sự cùng sửa một hồ sơ | Nhất quán; cảnh báo xung đột **hoặc** ghi nhận lịch sử. **Đã đo: không cảnh báo xung đột** — người lưu sau đè người trước; **có ghi vết** đầy đủ ai sửa gì lúc nào |
| ☐ | 7 · Tài khoản không đúng quyền | Ẩn hoặc chặn rõ. Đã đo: **42/42** đường ghi đều kiểm vai |
| ☐ | 8 · Không tìm thấy hồ sơ dù khách nói đã khám | Tìm được bằng tên, SĐT, mã bệnh nhân. Đã đo: có cả ba |
| ☐ | 9 · Lịch bác sĩ đổi sau khi khách đã đặt | Nhận biết lịch khách bị ảnh hưởng. **Đã đo: chưa tìm thấy cơ chế này** — nhiều khả năng chưa có |
| ☐ | 10 · Người dùng chưa hiểu tên trạng thái | Tên trạng thái + việc tiếp theo đủ rõ, không cần nhớ hướng dẫn |

## Ưu tiên 4B — Mười lăm tình huống nghiệp vụ CSKH

| | Tình huống | Ghi chú |
|---|---|---|
| ☐ | 1 · Khách mới liên hệ qua Facebook, muốn đặt lịch | |
| ☐ | 2 · Khách mới chỉ hỏi thông tin, chưa chốt ngày | Lưu được mà chưa cần tạo lịch? |
| ☐ | 3 · Khách đặt trong ngày nhưng chưa chọn bác sĩ | Đặt được khi chưa gán bác sĩ |
| ☐ | 4 · Khách đặt xa, lịch bác sĩ tuần đó chưa có | BS đăng ký từ thứ 3, public muộn nhất thứ 6 |
| ☐ | 5 · Khách cũ đặt tái khám | |
| ☐ | 6 · Khách cũ khám **dịch vụ khác**, không phải tái khám | |
| ☐ | 7 · Khách liên hệ lại bằng SĐT đã có | Nhận ra khách cũ, không tạo hồ sơ mới |
| ☐ | 8 · Hai CSKH cùng nhận một yêu cầu đặt lịch | Đã đo: có giữ chỗ 10 phút |
| ☐ | 9 · Khách đổi ngày/giờ sau khi đã đặt | |
| ☐ | 10 · Khách đổi dịch vụ sau khi đã cho thông tin | |
| ☐ | 11 · Tìm khách khi chỉ nhớ tên / SĐT / mã | Đã đo: có cả ba |
| ☐ | 12 · Phát hiện sai tên, ngày sinh, liên hệ | Sửa được, có ghi vết |
| ☐ | 13 · Khách chưa xác nhận lịch, cần gọi lại | Có việc "hẹn gọi lại" và nhắc đúng giờ |
| ☐ | 14 · Khách đã xác nhận / CSKH đã xử lý xong | Không hiện lại như việc tồn |
| ☐ | 15 · Quản lý cập nhật lịch bác sĩ trong tuần | Nối với mục 4A-9 |

## Thêm — tìm được khi soi hệ thống

| | Việc cần test | Ghi chú |
|---|---|---|
| ☐ | Gõ URL hỏng `/home?weekAppt=abc` | Trang chủ phải mở được. Trước 13/08 trang này sập — **đã vá** |
| ☐ | Gõ URL hỏng `/schedule?week=abc` | Trang lịch phải mở được — **đã vá** |
| ☐ | Đặt lịch với giờ hẹn sai định dạng | Báo lỗi tiếng Việt rõ ràng — **đã vá** |
| ☐ | Trưởng ca bấm "Sửa lịch" xếp cho người khác | Phải báo lỗi rõ, không im lặng nuốt thao tác |
| ☐ | Việc bị bỏ quên trong màn công việc | Staging có **19 việc "đang làm"** và **95 việc "chờ"** tồn quá 1 ngày; không có gì tự đóng |
| ☐ | Lỗi hệ thống có báo về không | **Hiện không** — thư viện báo lỗi chưa được cài |

## Ba điều cần hỏi lại chị

1. **"Ca ưu tiên" có phải khách đến thẳng quầy không?** Hệ thống hiểu vậy và cộng thêm ngoài hạn mức. Nếu chị muốn 8 online + 2 trực tiếp = 10 thì cài 8 và 2.
2. **Mốc 18h15 (5 ca) và 18h30 (6 ca) cho bác sĩ khác** — không có trong feedback ver2. Quy định mới sau 08/08 hay cài sai?
3. **Khách mới phải qua BS Thành** — chưa làm. Có làm không, và chặn cứng hay chỉ cảnh báo?
