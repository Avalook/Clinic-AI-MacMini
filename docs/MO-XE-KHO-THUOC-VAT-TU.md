# Mổ xẻ trang Kho thuốc và Kho vật tư (17/10/2026)

Bấm thật trên bản local của nhánh này (API 8281, web 3281), dữ liệu thử; không đụng
staging hay prod. Có bấm ở 1280 và 375, có thử ca lạ bằng cả giao diện lẫn API.

## 1. Hai trang gồm những gì

**Kho thuốc** (`/pharmacy/inventory`) — hai khu:

| Khu | Tab | Dùng để |
|---|---|---|
| KHO | Thuốc trong kho | xem từng lô: hạn, tồn, nhập, sửa lô, điều chỉnh, huỷ, in tem |
| KHO | Nhập thuốc | lập phiếu nhập nhiều dòng (nhà cung cấp, số hoá đơn) |
| KHO | Lịch sử kho | chọn một thuốc, xem mọi lần nhập, giao, điều chỉnh, huỷ |
| KHO | Danh mục & giá | thêm thuốc, giá bán, hướng dẫn, mức tồn tối thiểu |
| KHO | Kiểm đếm kho | đếm thực tế từng lô, ghi lệch |
| KHO | Chuyển ra quầy | chỉ hiện khi bật "tách kho / quầy" |
| QUẦY | Kiểm đầu ca / Kiểm cuối ca | đếm mù, chốt, điều chỉnh theo lệch, hoàn tác |
| QUẦY | Báo cáo cuối ngày | mở báo cáo hàng hoá |
| QUẦY | Đã giao, chưa trừ kho | thuốc đã giao nhưng chưa gắn lô nên kho chưa trừ |

**Kho vật tư** (`/kho-vat-tu`): Tồn theo nơi chứa · Phiếu (nhập, xuất phòng, trả kho,
chuyển phòng, kiểm, điều chỉnh, huỷ, hoàn tác) · Chờ duyệt · Tiêu hao · Danh mục.

## 2. Việc cần anh quyết (kèm ví dụ số)

**Câu 1 — Thuốc nhập theo hộp nhưng bán theo gói.** Androgel nhập 6 hộp, mỗi hộp 10 gói. Khách mua 2 gói.
Đã dựng lại trên giao diện: thu tiền được, giao được, **kho vẫn 6 hộp**, và dòng ở "Đã giao, chưa trừ kho" có **0 lô để gắn**, nên nằm đó mãi. Màn bán còn nói "Kho chưa có lô cho thuốc này", trong khi kho có 6 hộp.
- (a) Quy đổi: 1 hộp = 10 gói, bán 2 gói thì kho còn 5,8 hộp. Đúng lâu dài, phải sửa sâu (mức 3).
- (b) Bắt nhập lô theo gói (nhập 60 gói). Không cần sửa code, nhưng gõ tay dễ sai.

**Câu 2 — Vật tư có được âm không?** Phòng có 8 đầu dò, nhân viên "trả kho 9.999" từ phòng đó.
Hiện nay kho thuốc **chặn** ("chỉ còn 30, không bớt được 80") còn kho vật tư **cho qua** rồi cảnh báo.
Trên bản thử, phòng Sản/Siêu âm đang âm 19.990 và báo cáo tiêu hao ra −9.991. Xuất, huỷ, chuyển phòng, hoàn phiếu nhập đều qua được khi quá tồn.
- (a) Chặn như kho thuốc. (b) Giữ như bây giờ.

**Câu 3 — Phòng khám có dùng thuốc gây nghiện / hướng thần, hoặc thuốc phải bảo quản lạnh không?**
Nếu có, nơi khác làm sổ riêng, tủ khoá, báo cáo 48 giờ khi thất thoát, theo dõi nhiệt độ. Hệ thống mình **chưa có** gì cho hai loại này.

**Câu 4 — Thuốc khách trả.** Hiện về quầy rồi tính là tồn. Chuẩn quốc tế (WHO): vào "chờ kiểm", người có quyền quyết nhập lại hay huỷ. Mình đã ghi nhận việc này ở danh sách tồn đọng (màn xử lý thuốc khách trả).

## 3. Lỗi và điểm yếu đã tìm thấy

| # | Mức | Chuyện | Ví dụ |
|---|---|---|---|
| 1 | cao | Lô lệch đơn vị: giao không trừ kho, dòng kẹt | câu 1 ở trên |
| 2 | cao | Vật tư âm không chặn | câu 2 |
| 3 | vừa | **Lỗi máy chủ 500** khi gõ số quá lớn: số lượng nhập thuốc 1 nghìn tỷ, giá nhập 99.999.999.999.999, số đếm kiểm kho 1e15. Luật repo cấm "ném lỗi khi nhập rác" | gõ thừa nhiều số 0 |
| 4 | vừa | Vật tư nhập **1 nghìn tỷ cái** được chấp nhận, màn hiện 999.999.999.566,5 | gõ thừa số 0 |
| 5 | vừa | Hạn dùng gõ sai qua phiếu nhập bị **lưu im lặng thành "chưa có hạn"** (kể cả 31/12/2027, 2027-02-31, "sắp tới"). Giao diện dùng ô chọn ngày nên chặn được, các đường khác thì không | lô vào kho không hạn, không bị cảnh báo hết hạn |
| 6 | vừa | Kiểm kê ca nhận **đơn vị lạ** ("tấn"). Điều chỉnh xong phiếu hiện "đã điều chỉnh" nhưng không cộng gì, rồi **hoàn tác báo "Không tìm thấy dòng sổ"**: kẹt cả hai chiều. Chỉ xảy ra qua API, bấm tay không ra | xem trên màn Quầy |
| 7 | nhẹ | Màn bán lẻ: nhập số lượng sai thì thông báo lỗi nằm **cao hơn nút 895px**, người dùng trên điện thoại bấm xong tưởng không có gì | gõ "-2" rồi bấm Thêm |
| 8 | nhẹ | Ô "Tổng tồn (đơn vị)" **cộng lẫn hộp, viên, gói** (442; sau khi thử là 1.574,5) | không có nghĩa |
| 9 | nhẹ | Ở 375px, bảng "Thuốc trong kho" giấu cột Tồn và các nút sau thanh vuốt ngang | cần vuốt mới thấy |
| 10 | nhẹ | Nhập lô số lượng âm chỉ báo "Máy chủ từ chối.", không nói vì sao | |
| 11 | nhẹ | "Kiểm đếm kho" hiện tồn hệ thống cạnh ô đếm; "Kiểm kê ca" thì đếm mù. Hai cách khác nhau | đếm có số sổ trước mắt dễ lệch theo |
| 12 | nhẹ | Gửi lại **cùng khoá nhưng khác số lượng**: máy chủ trả im lặng kết quả cũ (người dùng tưởng đã nhập 99, thực ra 5). Bấm tay không gặp vì mỗi lần bấm có khoá mới | |

**Đã kiểm, KHÔNG phải lỗi:** hoàn huỷ lô lần hai không cộng đôi tồn; chốt kiểm kê trống bị giao diện chặn; SĐT trùng được cảnh báo; trùng số lô khác hạn bị từ chối; huỷ/điều chỉnh quá tồn bị chặn ở kho thuốc; lô hết hạn bị gắn cờ và có nút huỷ lô hết hạn; gợi ý lô sắp theo hạn gần nhất trước.

## 4. So với cách các nơi thật làm

Nguồn: bản tra cứu của agent nền (GSP/GPP của Bộ Y tế, WHO TRS 1025 Annex 7, kế toán kho).
Nhiều điều ghi "chưa kiểm chứng"; đừng trích số điều khi làm việc với người khác.

| Nơi thật thường làm | Mình |
|---|---|
| Xuất theo hạn gần nhất trước | Có gợi ý, chọn tay không ghi lý do |
| Chặn xuất thuốc hết hạn | Có |
| Mọi biến động ghi sổ, không sửa đè, hoàn bằng bút toán ngược | Có, mạnh hơn nhiều nơi |
| Kiểm kê đếm độc lập, có biên bản, điều chỉnh có lý do và người làm | Có ở kiểm kê ca; **chưa** ở Kiểm đếm kho |
| Hai người cùng kiểm | Chưa |
| Hàng khách trả vào chờ kiểm trước | Chưa (câu 4) |
| Quy đổi hộp ↔ gói/viên | Chưa (câu 1) |
| Thuốc kiểm soát đặc biệt có sổ riêng, tủ khoá | Chưa (câu 3) |
| Bảo quản lạnh có theo dõi nhiệt độ | Chưa (câu 3) |
| Thu hồi lô, tra lô đã giao cho ai | Có dữ liệu (lô gắn dòng giao); **chưa kiểm** có màn tra không |
| Cảnh báo sắp hết hạn | Có (mặc định 60 ngày, sửa được) |
| Trả hàng nhà cung cấp | Chưa thấy màn riêng |

## 5. Chưa kiểm được

- Phân quyền thật: trên bản thử mọi tài khoản đều có cùng 38 quyền nên chưa so được ai làm được gì.
- Camera quét mã, in tem, xuất Excel; hai máy thao tác cùng lô cùng lúc trên giao diện (test tự động đã kiểm tranh chấp ở tầng máy chủ).
- Mạng chậm / mất mạng giữa chừng.

## 6. Đề xuất sửa (chưa làm)

1. Mức 1, một PR nhỏ: lỗi 500 → trả câu tiếng Việt (3); chặn trần hợp lý số lượng nhập vật tư (4); hạn dùng gõ sai → báo lỗi rõ thay vì im lặng (5); kiểm kê ca bỏ qua đơn vị không có thật (6); thông báo lỗi bán lẻ đặt cạnh nút (7); bỏ hoặc tách theo đơn vị ô "Tổng tồn" (8); thông báo lỗi nhập lô nói rõ (10).
2. Mức 3, cần anh quyết trước: câu 1, 2, 4. Câu 3 là hỏi nghiệp vụ.
