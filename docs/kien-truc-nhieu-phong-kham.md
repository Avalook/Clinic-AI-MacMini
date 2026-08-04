# Xây sản phẩm, không xây riêng cho Dr4Women

Đọc lại Notion ngày 04/08/2026, đối chiếu với những gì đang chạy trong hệ thống.

---

## 1. Phòng khám thật đang trông như thế nào

Từ báo cáo onsite 23/04/2026 (cơ sở Kim Ngưu):

| | |
|---|---|
| **Tầng** | T1: Tiếp đón · Lấy mẫu XN · Chỉ định · Khám · Thuốc<br>T2: Siêu âm<br>T4: Siêu âm |
| **Tải** | 40–60 bệnh nhân/buổi, 18–20 nhân sự/buổi |
| **Bác sĩ** | BS Thành: **40–55 BN/buổi** (18h–23h)<br>Bác sĩ phụ: **5–10 BN/buổi** |
| **Giờ mở** | T2–T6: 18h–22h · T7–CN: 8h–11h và 14h–17h |
| **Nút nghẽn (họ tự nói)** | Kho thuốc chờ tới 15 phút; trợ lý nhập liệu chạy 3 tab cùng lúc; bác sĩ phải hỏi lại bệnh sử mỗi lần |

Chuyên khoa có hồ sơ riêng trên Notion: **Phụ khoa · Sản khoa · Nam khoa ·
Nội tiết · Hiếm muộn–Vô sinh**.

## 2. Hệ thống đang khai gì

| | Trong hệ thống | Khớp với thực tế? |
|---|---|---|
| Cơ sở | Kim Ngưu, Hào Nam | Notion mới khảo sát **1/2 cơ sở** |
| Phòng | 12 phòng | **Không có khái niệm tầng** |
| Dịch vụ | 14 loại | Có 3 dòng rác: `FREE`, `***#Thủ thuật`, `NPĐH` |
| Bảng giá | 29 dòng | **0 dòng có giá** |

### Ba chỗ lệch đáng kể

**a) Hệ thống không biết phòng khám có tầng.** `clinic_room` không có cột tầng.
Nhưng siêu âm nằm ở **T2 và T4**, còn mọi thứ khác ở T1 — nên "cho bệnh nhân
lên tầng mấy" là một quyết định thật, lặp 40–60 lần mỗi buổi, mà Trưởng ca đang
phải tự nhớ. Bảng điều phối cũng không xếp phòng theo tầng được.

**b) Bốn phòng khám đều gắn cứng vào `KHAM-PHUKHOA`.** KB01–04 cùng một node,
trong khi phòng khám có 5 chuyên khoa. Nghĩa là một ca Nam khoa hay Nội tiết
vẫn được hệ thống xếp vào bước "khám phụ khoa".

**c) Ba tuyến điều phối là ba HOÁN VỊ của cùng một danh sách** (siêu âm + lấy
máu + duyệt KQ + thuốc + kết thúc). Không có tuyến nào cho người chỉ khám rồi
về. Đã vá tạm bằng cách suy tuyến từ chỉ định của bác sĩ, nhưng gốc là danh mục
tuyến chưa phản ánh các đường đi thật.

---

## 3. Nguyên tắc: luật là DỮ LIỆU, không phải code

Đây là chỗ quyết định sản phẩm này bán được cho phòng khám thứ hai hay không.

Ví dụ Quang đưa ra: *"đặt lịch để BS Thành là người mà khách nào đến cũng gặp
đầu tiên rồi mới được chỉ định gặp bác sĩ khác"*, và *"thay vì fix cứng 15' có
9 ca thì cho quản lý phòng khám tự chỉnh"*.

Cùng một nhu cầu, ba cách làm — chỉ một cách đúng:

| Cách | Hệ quả |
|---|---|
| Viết `if (doctor == 'Thành') slots = 9` | Phòng khám thứ hai phải sửa code. Không bán được. |
| Thêm cột `is_gatekeeper` vào `staff` | Đỡ hơn, nhưng phòng khám sau muốn "điều dưỡng sàng lọc trước" thì lại thêm cột nữa. Mỗi khách hàng một cột. |
| **Khai thành LUẬT có phạm vi tenant** | Dr4Women khai BS Thành. Phòng khám khác khai điều dưỡng. **Không ai đụng code, không ai đụng nhau.** |

### Bốn tầng cấu hình

**Tầng 0 — Hằng số sản phẩm.** Không tenant nào sửa được: bệnh án khoá sau khi
ký (TT13/2011/TT-BYT), một người không ở hai phòng cùng lúc, RLS chia theo
tenant. Đây là thứ khiến sản phẩm này là *phần mềm y tế* chứ không phải một cái
bảng tính.

**Tầng 1 — Danh mục của tenant.** Cơ sở, **tầng**, phòng, chuyên khoa, dịch vụ,
giá, nhân sự, vai. Quản lý phòng khám khai. *Đã có, thiếu tầng.*

**Tầng 2 — Luật vận hành của tenant.** Quản lý chỉnh, không cần lập trình viên:

| Luật | Trạng thái |
|---|---|
| Sức chứa theo khung giờ, theo bác sĩ, theo ngày | ✅ **đã có 3 tầng** (`doctor_booking_override` + `slot_booking_override`, đều theo `clinic_id`) |
| Giờ mở cửa theo thứ | ✅ `clinic.settings.hours` |
| Ngưỡng cảnh báo chờ theo phòng | ✅ `dispatch_threshold` |
| Tuyến đi theo loại dịch vụ | ⚠️ có bảng, nhưng danh mục chưa đúng thực tế |
| **Luật thứ tự bắt buộc (cửa ngõ)** | ❌ **chưa có** ← ví dụ BS Thành |

**Tầng 3 — Ngoại lệ có ghi lý do.** Trưởng ca quyết tại chỗ: đổi tuyến, đóng
lượt khi còn vướng, đặt vượt sức chứa. ✅ Đã có, và **đều bắt ghi lý do**.

> **Điểm quan trọng:** tầng 2 đã có sẵn cái khuôn đúng. Luật đặt lịch làm trong
> tuần này — base 15'/3+1 cho cả phòng khám, rồi BS Thành 18:00–18:15 là 8+1,
> áp cho thứ Ba, áp mãi mãi — **chính là mô hình Quang mô tả**, đã chạy thật.
> Việc còn lại là áp cùng khuôn đó cho hai luật nữa, chứ không phải nghĩ lại từ
> đầu.

---

## 4. Giải ví dụ "BS Thành gặp đầu tiên" theo đúng nguyên tắc

Không thêm cột `is_gatekeeper`. Khai thành một luật có phạm vi:

```
  ÁP CHO AI      : bệnh nhân mới (hoặc: mọi bệnh nhân / một dịch vụ / một cơ sở)
  BẮT BUỘC QUA   : bước "Khám sàng lọc"  ·  người đảm nhiệm: BS Thành
  TRƯỚC KHI ĐƯỢC : chỉ định sang bác sĩ khác
  NGOẠI LỆ       : Trưởng ca bỏ qua được, phải ghi lý do
```

Bốn ô đó là bốn cột trong một bảng theo `clinic_id`. Dr4Women khai một dòng.
Phòng khám khác khai *"mọi bệnh nhân → điều dưỡng sàng lọc → trước khi gặp bác
sĩ"*. Phòng khám thứ ba khai *"bệnh nhân BHYT → quầy bảo hiểm → trước khi khám"*.

**Ba khách hàng, ba luật khác nhau, cùng một dòng code.** Đó là core value:
không phải "phần mềm cho Dr4Women", mà là **bộ khung để mỗi phòng khám tự khai
cách mình vận hành** — với những chốt chặn y tế mà không ai được phép tắt.

Ô "ngoại lệ có ghi lý do" không phải phần phụ. Phòng khám thật luôn có ca ngoại
lệ; hệ thống nào không cho ngoại lệ sẽ bị vượt mặt bằng giấy tay, và lúc đó nó
mất luôn khả năng biết chuyện gì đã xảy ra.

---

## 5. Thứ tự nên làm

**Trước hết — cho hệ thống biết phòng khám có tầng.**
Thêm `floor` vào `clinic_room`, khai T1/T2/T4 cho Kim Ngưu. Bảng điều phối xếp
phòng theo tầng, câu chuyển phòng nói rõ *"lên tầng 2, phòng SA1"*. Nhỏ, không
rủi ro, và bỏ được một việc Trưởng ca đang phải tự nhớ 40–60 lần mỗi buổi.

**Rồi — tách phòng khám theo chuyên khoa.**
KB01–04 đang cùng một node. Cho mỗi phòng khai được nhiều chuyên khoa nó phục
vụ, thay vì một node cứng.

**Rồi — luật thứ tự bắt buộc.**
Đúng ví dụ BS Thành. Làm sau hai việc trên vì nó cần "bước" và "phòng" đã đúng
thì mới khai luật lên trên được.

**Song song, việc của phòng khám chứ không phải của code:**
dọn 3 dòng dịch vụ rác, và **nhập bảng giá** — 29 dịch vụ đang không có giá nào,
nên màn thu ngân có cột tiền mà luôn trống.

**Chưa nên làm:** đa cơ sở đầy đủ. Notion mới khảo sát Kim Ngưu; Hào Nam có
trong hệ thống nhưng chưa ai mô tả nó vận hành ra sao. Xây cho một nơi chưa biết
gì là cách chắc chắn nhất để xây sai.
