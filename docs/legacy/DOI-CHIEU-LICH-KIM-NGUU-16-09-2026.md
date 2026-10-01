> LỖI THỜI (chuyển legacy 01/10/2026): đối chiếu lịch 16/09, đã bị lịch tuần 28/09 thay — đừng làm theo.

# Đối chiếu: lịch làm việc thật của PK Kim Ngưu ↔ hệ thống đang chạy

Nguồn: `[Dr4women] PK Kim Ngưu - Lịch làm việc nhân sự theo tuần.xlsx` (Tuyền gửi
16/09/2026, hai tuần 10–16/08 và 17–23/08) + trang Notion *Kế hoạch xây dựng hệ
thống hoàn chỉnh v1.0.0* (sửa lần cuối 11/09/2026).

Viết ra vì Tuyền nói đúng một câu đáng sợ: *"tôi thiết kế mà lại quên không xem
notion"*. Tài liệu này là chỗ để kiểm lại xem cái đã dựng lệch bao nhiêu so với
cái phòng khám thật đang làm — **trước** khi viết thêm dòng mã nào.

---

## 1. Ba phát hiện làm thay đổi cách nghĩ

### ① Không ai làm một vai. Người ta đứng VỊ TRÍ, và vị trí đổi theo ca.

Đếm trên 300 ô có tên trong hai tuần:

| Người | Số ca | Số vị trí khác nhau |
|---|---:|---:|
| Hải Yến | 12 | **8** |
| Phương Anh | 13 | 6 |
| Huế | 10 | 5 |
| Hương Linh | 8 | 5 |
| Quỳnh Anh | 7 | 5 |

Hải Yến trong hai tuần: Điều dưỡng Sàn chậu, Điều dưỡng Bio, Điều dưỡng Sản,
Xếp thuốc, Lễ tân, Đo chỉ số, Điều dưỡng siêu âm 2, Điều dưỡng thủ thuật ngoài
giờ. **Tám vị trí, ở ba tầng.**

Hệ thống đang gán **một vai cố định cho một người** (`clinic_membership.role`),
và mọi màn hình mở/đóng theo vai ấy. Theo mô hình đó thì Hải Yến phải là tám
người, hoặc là một người không bao giờ mở được bảy màn mình đang làm việc.

Chỉ **một** người gần như chuyên một vị trí: Thanh Phương, 7/7 ca đều Thư ký y
khoa.

### ② "Thư ký y khoa" là một VỊ TRÍ, không phải một nghề.

Danh sách nhân sự chỉ có bốn nhóm: **BS Nội tiết (3) · BS.YHDP (1) · BS Sản (5)
· BS Siêu âm (5) · ĐIỀU DƯỠNG (21)**. Không có mục Lễ tân, Thu ngân, hay Thư ký
y khoa — vì đó là những **chỗ ngồi** mà điều dưỡng luân phiên vào.

Huế làm Thư ký y khoa hôm này, Điều dưỡng Sàn chậu hôm khác. Vân Anh cũng vậy.

⇒ Tuyền nói đúng: *"việc điền song song là từ phía mình đang nghĩ vậy"*. Cái
**tính năng** điền song song (thư ký nhập – bác sĩ duyệt) vẫn đúng và **giữ
nguyên, không xoá**. Cái **sai** là giả định đứng sau nó: rằng có một lớp nhân
viên tên là "thư ký y khoa" tách khỏi điều dưỡng.

### ③ Phòng khám chạy BUỔI TỐI trong tuần, cả ngày cuối tuần.

| Thứ | Ca có người |
|---|---|
| Hai → Sáu | **chỉ Tối** |
| Bảy, Chủ nhật | Sáng · Chiều · Tối |

Hệ thống đang có ca `SANG` / `CHIEU` / `FULL`. Giá trị `FULL` (cả ngày) **không
tồn tại trong thực tế của Kim Ngưu**, còn ca `TOI` — ca duy nhất của năm ngày
trong tuần — thì hệ thống **chưa có**.

Ăn khớp với luật sức chứa trong Notion: mọi mốc đều là 18h00 / 18h15 / 18h30 /
18h45. Đấy không phải ví dụ; đấy là toàn bộ giờ khám ngày thường.

---

## 2. Cấu trúc thật: Tầng → Phòng → Vị trí

| Tầng | Phòng | Vị trí |
|---|---|---|
| 1 | Quầy tiếp đón | Lễ tân · Thu ngân · Đo chỉ số sức khoẻ · Lấy mẫu (máu) |
| 1 | Phòng Nội tiết | BS Nội tiết · Hỏi bệnh ban đầu · **Thư ký y khoa** |
| 1 | Phòng thủ thuật | BS · Điều dưỡng |
| 1 | Phòng Siêu âm | BS · Điều dưỡng |
| 1 | Thủ thuật ngoài giờ | BS · Điều dưỡng 1 · Điều dưỡng 2 |
| 2 | Quầy thuốc | Xếp thuốc + Giải thích thuốc · **Tạo đơn thuốc + Thu ngân** |
| 4 | Phòng Sàn chậu | BS Sàn chậu · BS Thủ thuật · Điều dưỡng Sàn chậu |
| 4 | Phòng Sản – Biofeedback | BS Sản · Điều dưỡng Sản · Điều dưỡng Bio |
| 4 | Phòng siêu âm | BS 1 · Điều dưỡng 1 · BS 2 · Điều dưỡng 2 |

Không có tầng 3. Ghi chú trong Notion nói *"Cần lấy thêm thông tin về cấu trúc
phòng ở Hào Nam"* — tệp này là **Kim Ngưu**, nên câu hỏi ấy vẫn còn treo cho cơ
sở kia.

Hệ thống đang có 12 phòng, **`floor` để trống hết**, và tên phòng là "Khám 1…4",
"Siêu âm SA1…3" — không khớp tên thật ("Phòng Sàn chậu", "Phòng Sản –
Biofeedback", "Phòng Nội tiết").

### Sheet 3 — thứ quý nhất trong tệp

`Sheet3` là **định mức nhân sự theo loại buổi khám**, bốn loại:

1. **Buổi khám BS Thành** — 19 vị trí phải có người (trưởng ca, tiếp đón, đo chỉ
   số, lấy mẫu, hỏi bệnh, nội tiết + thư ký, thuốc ×2, sàn chậu ×2, sản ×2, siêu
   âm ×6).
2. **Buổi khám BS Sản** — 7 vị trí.
3. **Buổi khám BS Sản + BS Sàn chậu** — 11 vị trí.
4. **Buổi khám BS Sản + BS Sàn chậu + BS Nam khoa** — 13 vị trí.

Tức là buổi khám **có hình dạng chuẩn**, và xếp lịch là điền vào khung ấy. Đây
chính là thứ để máy kiểm "ca tối nay thiếu người ở đâu" — việc mà hôm nay chưa
màn nào làm được.

> ⚠️ Excel đã **nuốt mất dữ liệu**: các ô ghi "1-2 người" bị đổi thành ngày
> `2026-02-01`. Có 5 ô như vậy (điều dưỡng phụ thủ thuật, lễ tân + thu ngân,
> điều dưỡng sàn chậu ×3). Phải hỏi lại chứ đừng đoán.

---

## 3. Dữ liệu người: bẩn đúng kiểu dữ liệu thật

- **35 người** trong danh sách điện thoại · **74 cách gọi tên** trong lịch.
- **Dò ra 50/74**. 24 tên không có trong danh sách nhân sự, trong đó những người
  đi làm nhiều: **Phạm Hà (9 ca) · Trang Lê (6) · Thanh Huyền (5+3) · Hồng Thơm
  (4) · Phương Liên (3) · Anh Vũ (4)**.
- **10 tên mơ hồ**: `Vân Anh` có thể là **Nguyễn Vân Anh** hoặc **Vũ Hoàng Vân
  Anh** — và trong lịch còn có cả `N. Vân Anh` lẫn `V. Vân Anh`, nghĩa là người
  xếp lịch **cũng biết là hai người** nhưng không phải lúc nào cũng phân biệt.
  Tương tự `Huế` = Vũ Thị Huế hay Trần Thị Thu Huế; `BS Tiến`, `BS Linh`, `BS
  Hằng` đều hai người.
- **Khoảng trắng thừa** tạo ra người ma: `"Hải Yến"` và `"Hải Yến "` là hai khoá
  khác nhau; `"Thanh Huyền"` / `"Thanh Huyền "`; `"Huyền Trang"` / `"Huyền Trang "`.
- **Một ô, nhiều người**: `"Hồng Thơm\nHuế"`, `"Hồng Thơm, Hà Phạm"`,
  `"Phương Liên\nHuế"`, `"Bs Nam + HSS"`.
- **`Green Lab`** đứng ở ô *Lấy mẫu (máu)* chiều Thứ Bảy — **đối tác đứng trong
  lịch trực như một nhân sự**. Vai `PARTNER` dựng hôm nay hợp đúng chỗ này.
- **`Ngát - CSKH`** đứng quầy *Tạo đơn thuốc + Thu ngân*: CSKH cũng vào ca vận hành.
- **`NGHỈ`** là một giá trị ô hợp lệ.

### Tải của bác sĩ

112 ca bác sĩ trong hai tuần, 29 cách gọi (thực tế ~14 người sau khi gộp
`BS Tiến`/`BS. Tiến`, `BS Giáp`/`BS. Giáp`…).

**BS Thành: 27 ca — 24% toàn bộ ca bác sĩ**, gấp 2,7 lần người thứ hai (BS Dương,
10 ca). Và ông là người duy nhất có **"Buổi khám BS Thành"** làm một loại buổi
riêng trong Sheet3, với 19 vị trí — gấp gần ba lần buổi khám thường.

Khớp với luật đặt lịch trong Notion: BS Thành 18h00–18h15 nhận **10 ca**, bác sĩ
khác cùng mốc nhận **3**. Nút nghẽn của phòng khám là một con người, và phòng
khám đã biết điều đó đủ rõ để viết thành luật riêng.

---

## 4. Lệch giữa hệ thống và thực tế

| | Kim Ngưu (thật) | Hệ thống hôm nay | Nặng? |
|---|---|---|---|
| Ca | T2–T6 chỉ **Tối**; T7/CN Sáng·Chiều·Tối | `SANG` `CHIEU` `FULL` — **không có `TOI`** | 🔴 |
| Vị trí | ~20 vị trí gắn Tầng+Phòng | 8 mã phẳng (`LE_TAN`, `PHU_BS_SA`…), không gắn phòng | 🔴 |
| Quyền màn hình | theo **vị trí của ca** | theo **vai cố định của người** | 🔴 |
| Phòng | tên thật, 3 tầng | 12 phòng, `floor` rỗng, tên không khớp | 🟡 |
| Định mức buổi khám | Sheet3, 4 loại buổi | **chưa có khái niệm** | 🟡 |
| Nhân sự | 35 người thật (21 ĐD + 14 BS) | 54 dòng, phần lớn tên rút gọn/bịa | 🟡 |
| Đối tác trong lịch | `Green Lab` là một ô trực | `PARTNER` có tài khoản, **chưa có ô trực** | 🟢 |
| Thư ký y khoa | vị trí luân phiên | vai riêng, 4 người | 🟡 |

**Tin tốt, và nó lớn hơn vẻ ngoài:** bảng `work_roster` đã đúng hình dạng cần có
— `(work_date, shift, station, staff_id, staff_name)`. Đúng là ngày × ca × vị
trí. `clinic_room` đã có sẵn cột `floor`. `staff_capability` đã cho một người
mang nhiều năng lực. Nghĩa là **không phải đập đi xây lại lược đồ**; phải
(a) nạp đúng tập giá trị, và (b) chuyển chỗ quyết định quyền từ *vai của người*
sang *vị trí của ca*.

---

## 5. Notion nói gì mà hệ thống chưa có

Đọc lại DOD trong *Kế hoạch v1.0.0*, những mục **chưa từng làm**:

- **Quét QR check-in/check-out từng khâu** (team chốt PA3, chi phí 0đ) — đây là
  hạng mục "Cập nhật web cho QR", deadline **16/09**, tức hôm nay.
- **Cảnh báo chờ quá 15 phút** đẩy về màn Trưởng ca.
- **Luật điều phối**: vừa đủ = 1 khám + ≤3 chờ · báo tắc > 3 chờ.
- **TV theo TẦNG** (mỗi tầng một màn, liệt kê phòng của tầng ấy) — màn TV hiện
  tại không biết tầng.
- **Sơ đồ vị trí phòng**.
- **Sức chứa theo mốc 15 phút** của riêng từng bác sĩ (BS Thành 10/4; người khác
  3/4/5/3).
- **Đặt lịch giữ chỗ 10 phút** rồi tự xoá.
- **Nút xuất QR thanh toán** cho cả hai quầy thu ngân.
- **Tự trích text từ PDF** kết quả của đối tác.
- **Form lịch trực trong hệ thống phải "làm giống hệt"** tệp Excel này.

Và một dòng đáng chú ý trong bảng thứ tự triển khai: *"Sync back-end — 16/09 —
Tuyền — Chưa làm"*.

---

## 6. Việc đang dở, để không rơi

Trước khi Tuyền gửi tệp này, phiên đang làm dở:

- ✅ Vai `PARTNER` + màn gửi kết quả: xong, đã lên final cloud, đã dựng 2 khách
  chờ kết quả (Đoàn Thị Thu Thuỷ – xét nghiệm máu, Lâm Thị Cẩm Tú – nước tiểu).
- ✅ 5 tài khoản vai còn thiếu: `truong-ca`, `thu-ngan-thuoc`, `thu-ngan-dich-vu`,
  `doi-tac-pk`, `man-hinh-phong-cho`.
- ✅ 7 khách mới cho hai quầy thu ngân, đã đóng lượt để quầy hiện ra.
- ⏳ **Còn dở:** thu tiền cho khách nhóm K; và một **phát hiện chưa điều tra**:
  quầy thu ngân trả `price: null` cho dịch vụ khám "Phụ khoa" — bảng giá dò theo
  TÊN, và tên dịch vụ khám không khớp dòng giá nào. Thu ngân sẽ thấy ô giá trống.
