# Bấm thật kho thuốc + quầy trên staging — 22/10/2026

Người bấm: Claude, tài khoản Quản lý hệ thống, https://staging.dr4women.io.vn
(staging = code giống prod + dữ liệu bản sao prod đêm 21/10, đã che tên khách).
Đã ghi lên staging đúng **một** thao tác: giao 6 hộp Utrogestan 100mg cho Khách 6715
(KHACH-12241) lúc 10:08. Staging tự nạp lại lúc 03:30 nên không cần dọn.

## Tóm tắt

1. **Gốc lớn nhất là DỮ LIỆU, không phải code:** 55/107 thuốc đang bán **không có lô nào**
   trong kho. Đó lại là các thuốc kê nhiều nhất (Utrogestan 100mg, Usartestos, DHEA Avemos,
   Dermolivo viên đặt, Fluconazole). Lô hiện có là lô mẫu `DEMO1709-*` (tồn 20) gắn vào
   **sản phẩm cũ tên khác** ("Utrogestan (Đ; 1v/2v; U)", "usatestos (Đ)", "DHEA (U)"…), không
   phải sản phẩm đang bán → mọi lần giao các thuốc này rơi vào "Đã giao, chưa trừ kho", và kho
   không bao giờ giảm.
2. **Prod (bản sao) có ~40 đơn "Đã thu — giao thuốc" chưa ai bấm Giao.** Danh sách
   "Đã giao, chưa trừ kho" chỉ có 1 dòng (dòng mình vừa giao). Nghĩa là ở quầy, nhân viên đưa
   thuốc cho khách nhưng **không bấm Giao** trên hệ thống → đơn treo mãi ở "Đang xử lý (50)".
3. **Bác sĩ không nhập số lượng** khi kê → Thu ngân thuốc thấy "0đ", phải gõ tay từng dòng.
   Danh sách "Hôm nay" có **59 khách chờ thu**, phần lớn 0đ, lẫn cả lượt ngày cũ (hôm nay mới có
   18 lịch).

## Lỗi / chỗ chưa ổn (theo màn)

| # | Màn | Thấy gì | Mức | Loại |
|---|---|---|---|---|
| 1 | Kho → Danh mục & giá | 55/107 thuốc đang bán có "Số lượng trong kho 0"; lô mẫu nằm ở sản phẩm cũ tên khác | Cao | Dữ liệu — nạp tồn thật + gộp sản phẩm trùng |
| 2 | Kho → Quầy → Đã giao, chưa trừ kho | Utrogestan 100mg: "Chưa có lô gán được" dù kho có lô "Utrogestan (Đ…)" 20 hộp (khác sản phẩm) | Cao | Dữ liệu (hệ quả #1) |
| 3 | Cấp thuốc | ~40 đơn đã thu chưa bấm Giao; không hiện ngày của đơn nên không biết đơn treo từ bao giờ | Cao | Thói quen + giao diện |
| 4 | Thu ngân thuốc | Bác sĩ kê không có số lượng → 0đ, quầy gõ tay từng dòng | Vừa | Luồng kê đơn |
| 5 | Thu ngân thuốc | "Hôm nay" hiện 59 khách chờ, lẫn lượt cũ 0đ (khách không mua) — không có nút đóng "khách không lấy thuốc" | Vừa | Giao diện + luật |
| 6 | Cấp thuốc | Dòng "Đã giao đủ" vẫn hiện ô Lý do + "Chốt — không giao thêm" | Thấp | Giao diện |
| 7 | Cấp thuốc | Không thấy nút Hoàn tác ngay trên dòng vừa giao (luật: mọi thao tác hoàn tác được) — cần kiểm trong "Xem chi tiết lượt & lịch sử cấp" | Vừa | Cần kiểm |
| 8 | Cấp thuốc ở ~800px (máy tính bảng) | Bấm đơn không hiện khung chi tiết, chỉ tô dòng | Vừa | Giao diện |
| 9 | Kho → Quầy → Đã giao, chưa trừ kho | Hướng dẫn ghi "nhập lô ở tab Tồn theo lô" — tab thật tên "Thuốc trong kho" | Thấp | Chữ |
| 10 | Thu ngân thuốc | "Danh mục thuốc (108)" vs Kho "Danh mục & giá (107)" lệch 1 | Thấp | Cần kiểm |
| 11 | Thu ngân thuốc | Khối "THUỐC ĐÃ KÊ" lặp lại đúng danh sách "KHÁCH LẤY THUỐC NÀO?" | Thấp | Giao diện |
| 12 | Kho → Quầy → Kiểm đầu ca | 81 dòng phải đếm tay, không lọc "chỉ thuốc có bán/giao hôm nay" | Thấp | Giao diện |

## Đề xuất cho tiện người dùng

**Gộp nút / bớt bấm**
- Cấp thuốc: thêm **"Giao hết phần đã thu"** một nút cho cả đơn (giờ 10 thuốc = 7 lần bấm), vẫn
  giao từng dòng được; sau khi giao có **Hoàn tác** ngay trên dòng.
- Thu ngân thuốc: nút **"Lấy đủ như kê"** điền sẵn số lượng (khi bác sĩ đã kê số lượng), và nút
  **"Khách không lấy thuốc"** đóng lượt khỏi hàng chờ (hoàn tác được).
- Gộp "Thu tiền" + "Giao thuốc" khi một người làm cả hai (quầy nhỏ): sau khi thu xong hỏi
  "Giao luôn?" — không bắt sang màn Cấp thuốc.

**Hiện thêm**
- Mỗi đơn ở Cấp thuốc / Thu ngân thuốc: **ngày + giờ kê** và **tuổi đơn** ("treo 3 ngày");
  tách nhóm "Hôm nay" và "Ngày trước".
- Danh mục: cột **"Có lô?"** + bộ lọc "Thuốc đang bán mà kho = 0".

**Bảng / màn mới nên có**
- **Màn ghép sản phẩm trùng** (một lần): ghép "Utrogestan (Đ; 1v/2v; U)" → "Utrogestan 100mg",
  chuyển lô sang sản phẩm đang bán. Đây là việc gỡ lỗi #1/#2 nhanh nhất, không cần đổi luật kho.
- **Nạp tồn đầu kỳ** từ Excel kiểm kê thật (đang chờ mẫu Excel anh Thắng) thay cho lô DEMO.
- Bắt bác sĩ nhập số lượng khi kê (hoặc gợi ý từ "cách dùng × số ngày").

## Việc cần Tuyền quyết

1. Ghép sản phẩm trùng + nạp tồn thật: làm trước khi sửa code kho (khuyên: **có**, vì code đang
   đúng luật nhưng dữ liệu làm mọi lần giao không trừ kho).
2. #499 quy đổi hộp ↔ gói: mở lại hay nhập lô theo đơn vị bán.
3. Ở quầy thật, ai bấm "Giao" — dược sĩ hay thu ngân? (giải thích 40 đơn treo).
