# Hướng dẫn quản lý: nhân sự · tài khoản · phòng · bảng giá · phân quyền

Dành cho **chị Hà** (người quản lý hệ thống). Mỗi việc dưới đây tự làm được ngay trên màn —
**không cần nhờ dev, không cần sửa code**. Viết đúng chữ trên màn (14/10/2026); chỗ nào màn đổi
chữ thì dev cập nhật file này cùng lúc.

Bốn nhóm việc, ba "lego" cần có (xem [mục 0](#0-cấp-quyền-để-thấy-các-màn)):

| Việc | Màn (thanh bên) | Lego cần bật |
|---|---|---|
| 1. Thêm nhân sự, sửa hồ sơ, cho nghỉ việc | **Quản lý nhân sự** | Nhân sự & phân quyền |
| 2. Tạo / đổi / gỡ tài khoản đăng nhập | **Thiết lập tài khoản cho nhân viên** | Nhân sự & phân quyền |
| 3. Cơ sở · phòng · phòng làm việc gì · lịch phòng | **Cấu trúc phòng khám** | Cài đặt phòng khám |
| 4. Giá dịch vụ · bên thu · phòng làm | **Bảng giá dịch vụ & phòng** | Bảng giá |
| 5. Ai được làm gì | **Phân quyền** | Nhân sự & phân quyền |

> **Nguyên tắc chung:** dịch vụ **không có nút Xoá** — chỉ thôi bán; phòng chỉ **tắt**; nhân sự
> chỉ **cho nghỉ**. Lịch sử khám, hoá đơn, báo cáo cũ giữ nguyên.

---

## 0. Cấp quyền để thấy các màn

Thanh bên chỉ hiện màn mà tài khoản có **lego**. Vai **Quản lý** có sẵn trong gói mẫu cả ba lego
dưới đây. Nếu không thấy màn nào:

1. Nhờ một Quản lý khác vào **Phân quyền** → tab **Quyền của từng người** ([mục 5](#5-ai-được-làm-gì--phân-quyền)).
2. Chọn chị trong danh sách → bật công tắc đúng lego:
   - **Nhân sự & phân quyền** → các màn Quản lý nhân sự, Thiết lập tài khoản, Phân quyền.
   - **Cài đặt phòng khám** → Cấu trúc phòng khám, Luật đặt lịch, Dây nối nghiệp vụ, Mẫu kết quả.
   - **Bảng giá** → Bảng giá dịch vụ & phòng.

Bật lego là có **cả** màn lẫn quyền sửa; máy chủ kiểm lại từng thao tác.

---

## 1. Thêm nhân sự · sửa hồ sơ · cho nghỉ việc — **Quản lý nhân sự**

### Thêm một người mới
1. Thanh bên → **Quản lý nhân sự**.
2. Bấm **+ Thêm nhân viên** (dưới danh sách bên trái).
3. Điền **Họ và tên**, chọn **Vai trò** (Bác sĩ · Bác sĩ siêu âm · Điều dưỡng siêu âm · Thư ký y khoa ·
   Lễ tân · CSKH · Thu ngân · Thu ngân thuốc · Thu ngân dịch vụ · Dược sĩ · Trưởng ca · Quản lý) và
   **Cơ sở làm việc**.
4. Bấm **Thêm** (**Huỷ** để bỏ). Người mới hiện trong danh sách, hồ sơ mở sẵn bên phải.
5. Màn ghi **"Đã thêm. Bước tiếp:"** kèm đường dẫn sang tạo tài khoản — làm tiếp ở
   [mục 2](#2-tạo--đổi--gỡ-tài-khoản-đăng-nhập--thiết-lập-tài-khoản-cho-nhân-viên) nếu người này cần đăng nhập.

### Sửa hồ sơ
Danh sách có ô **Tìm theo tên hoặc tên gọi…** và ô lọc theo vai trò. Chọn người, bên phải là hồ sơ:

| Ô | Ghi chú |
|---|---|
| Họ và tên · **Tên gọi trong phòng khám** | Tên gọi là chữ ghi chú "ví dụ: BS Thành" |
| Vai trò · **Cơ sở làm việc** · **Loại hợp đồng** | Hợp đồng: Toàn thời gian / Bán thời gian / Hợp đồng |
| Ngày sinh · Giới tính · Số điện thoại (9–11 chữ số) · Email | |
| **Số CCCD** (12 chữ số) | Chỉ Quản lý và Trưởng ca xem được |
| Số chứng chỉ hành nghề · Ngày cấp CCHN · Phạm vi hoạt động chuyên môn | Ghi theo chứng chỉ hành nghề |
| ☐ **Đang làm việc** · ☐ **Đang đào tạo** | |

Sửa xong bấm **Lưu hồ sơ** (màn báo **Đã lưu.**). Chưa bấm Lưu thì chưa ghi.

### Cho nghỉ việc
Mở hồ sơ → **bỏ tick "Đang làm việc"** → **Lưu hồ sơ**. Người đó hiện **"đã nghỉ"** trong danh sách;
hồ sơ và lịch sử giữ nguyên. Tick lại là đi làm trở lại.

- Việc này **không tự khoá đăng nhập**. Muốn khoá, **Gỡ tài khoản** ở mục 2. **Sau khi bản G2 lên** sẽ có nút
  **"Khoá & nghỉ việc"** làm cả hai bước một lần.
- Lịch trực đã xếp cho người nghỉ: kiểm ở **Cấu trúc phòng khám → Lịch của phòng** và gỡ nếu còn.

---

## 2. Tạo · đổi · gỡ tài khoản đăng nhập — **Thiết lập tài khoản cho nhân viên**

Mỗi người dùng **một tài khoản riêng** — không dùng chung (mọi thao tác ghi theo tên người làm). Hai người
hỗ trợ nhau (lễ tân ↔ thu ngân) thì bật thêm lego cho từng người ở mục 5.

Màn liệt kê mọi nhân viên: **Họ tên · Vai trò · Hợp đồng · Active · Login (Đã link / Chưa link) · Thao tác**.

### Tạo tài khoản
- Người **Chưa link**: bấm **Tạo tài khoản** ở dòng của họ; hoặc bấm **+ Thêm tài khoản** (đầu màn) rồi chọn người.
- Điền:
  - **Nhân viên** — chọn đúng người.
  - **Tên đăng nhập** — gõ tên trần, vd `bacsithanh`; hệ thống **tự gắn đuôi** `@dr4women.vn`. Nhân viên
    đăng nhập bằng đúng tên đã gõ.
  - **Mật khẩu tạm thời** — tối thiểu 8 ký tự. **Gửi cho người đó qua kênh an toàn**; họ nên đổi ở lần đăng nhập đầu.
- Bấm **Tạo tài khoản** → "Đã tạo tài khoản … và link với …".

### Với người đã có tài khoản (Đã link)
Ở dòng của họ có ba nút, làm ngay tại chỗ:
- **Đổi tên đăng nhập** — gõ tên mới → **Lưu** / **Huỷ**.
- **Đặt lại mật khẩu** — gõ mật khẩu mới (≥ 8 ký tự) → **Lưu** / **Huỷ**. Dùng khi người ấy quên.
- **Gỡ tài khoản** — hai bước (bấm, rồi xác nhận). Người đó **không đăng nhập được nữa**; hồ sơ và lịch sử vẫn
  còn. **Hoàn tác** = bấm **Tạo tài khoản** cho đúng người ấy.

> **Cẩn thận: hiện máy CHƯA chặn việc gỡ tài khoản của chính chị**, hay của Quản lý cuối cùng còn quyền cấp
> quyền. Gỡ nhầm là phải nhờ dev. Đừng bấm **Gỡ tài khoản** ở dòng của chính mình.
> **Sau khi bản G2 lên** (xem cuối file) máy sẽ chặn; lúc đó đoạn này được đổi thành "máy không cho gỡ".

---

## 3. Cơ sở · phòng · phòng làm việc gì — **Cấu trúc phòng khám**

Thanh bên → **Cấu trúc phòng khám**. Phần đầu là **Cơ sở & phòng**: mỗi cơ sở một khối, mỗi phòng
**một dòng**, chia theo tầng.

### Thêm / sửa cơ sở
- **+ Thêm cơ sở** → **Tên cơ sở**, **Địa chỉ**, ☐ **Đang hoạt động** → **Thêm cơ sở**.
- **Sửa** (cạnh tên cơ sở) → đổi tên, địa chỉ, bật/tắt hoạt động → **Lưu**.

### Thêm một phòng
1. Ở khối cơ sở đúng → **+ Thêm phòng**.
2. Điền **Tên phòng mới** (tên tự do), **Việc chính** (phòng làm việc gì chính), **Tầng**.
3. Bấm **Thêm phòng**. Mã nội bộ tự sinh, không cần quan tâm.

### Sửa phòng
Bấm vào dòng phòng để mở:
- Sửa **Tên phòng**, **Tầng** → **Lưu**. Đổi tên là **đổi theo ở mọi nơi** (lịch làm việc, bàn khám, phòng dịch vụ,
  trưởng ca).
- **Tắt phòng** / **Bật lại phòng**: tắt khi phòng nghỉ. **Máy chặn nếu còn khách đang chờ ở phòng** — xử lý khách
  xong rồi tắt.
- Khối **Phòng làm việc gì**: các chip **Nhóm việc** (✕ để bỏ) và **Dịch vụ riêng** (✕ để bỏ).
  - **+ Thêm việc** / **+ Thêm dịch vụ**: tìm theo tên hoặc mã; tick **Cả nhóm** để thêm cả nhóm, hoặc từng dịch vụ.
  - Việc có ★ là **việc chính**, không bỏ được.
- **Lịch của phòng**: bảng vị trí của phòng × 7 ngày (‹ tuần ›). Xếp người: chọn **Vị trí · Ngày · Ca · Người** →
  **Xếp vào lịch**; ✕ để bỏ người khỏi ca; **+ Thêm vị trí cho phòng** nếu thiếu chỗ. Ca chờ duyệt tô vàng.

> Dải cảnh báo **"bước chưa có phòng"** ở màn nghĩa là có việc chưa gắn được phòng nào. Thêm việc đó vào đúng
> phòng là hết.

---

## 4. Giá dịch vụ · bên thu · phòng làm — **Bảng giá dịch vụ & phòng**

Thanh bên → **Bảng giá dịch vụ & phòng**. **Sửa là dùng ngay cho lượt mới**: ô chỉ định của bác sĩ, quầy thu và
xếp phòng cùng đọc danh mục này.

> **Giá thuốc không sửa ở đây** — sửa ở **Kho thuốc → Danh mục thuốc**.

Đầu màn: ô **Tìm tên, mã, nhóm** (vd "PRP", "NIPT"), lọc **Mọi nhóm hàng**, các nút đếm (có **Đang bán N**). Mỗi dịch
vụ một dòng:

| Cột | Làm gì |
|---|---|
| **Dịch vụ · nhóm hàng** | Tên, nhóm hàng, mã phòng khám (mã KiotViet) |
| **Đơn giá** | Gõ giá rồi **Lưu**. Để trống = **chưa có giá** (không phải 0đ) |
| **Bên thu** | **Phòng khám thu** hoặc **Thu hộ đối tác** (khách trả thẳng cho đối tác) |
| **Nhóm việc** | Việc nào làm dịch vụ này (để xếp phòng) |
| **Phòng làm** | Tick phòng làm được → **Lưu N phòng**. Dịch vụ **chỉ** làm ở các phòng đã tick |
| **Đang bán** | Bỏ tick = **tạm ngưng**; tick lại = bán lại |

Chip **Giá tạm** = giá giả định chờ xác nhận — sửa / lưu lại đơn giá là chip biến mất.
Chip **Chưa có phòng** = dịch vụ chưa gắn phòng nào.

### Thêm dịch vụ mới
**+ Thêm dịch vụ mới** → **Tên dịch vụ**, **Nhóm hàng**, **Mã phòng khám (KiotViet, nếu có)**, **Đơn giá (đ)**
(trống = chưa có giá), **Nhóm việc (để xếp phòng)**, **Bên thu** → **Thêm dịch vụ**.

> **Không có nút Xoá.** Dịch vụ thôi bán → bỏ tick **Đang bán**.

---

## 5. Ai được làm gì — **Phân quyền**

Thanh bên → **Phân quyền**. Quyền theo **từng tài khoản**, không theo vai: cùng vai Lễ tân nhưng hai người có thể
có lego khác nhau. Có ba tab:

### Tab "Quyền của từng người" (hay dùng nhất)
1. Ô **Tìm tên…** → chọn người.
2. Danh sách **21 lego**, mỗi lego **một công tắc**, theo thứ tự thanh bên. Bật = người đó thấy màn và làm được việc
   của màn. **▾ Chi tiết** xem lego gồm những khối nào (chỉ xem).
3. Lego **Phòng dịch vụ** bật xong sẽ hiện **Phòng được làm**: tick **Tất cả phòng**, hoặc từng phòng.
4. Hai hàng **Luôn bật** (Trang chủ, Hành trình) không tắt được.
5. Người mới: bấm **+ Thêm gói mẫu <tên vai>** để bật sẵn bộ lego thường dùng của vai, rồi chỉnh thêm.

### Hai tab còn lại
- **Theo màn** — xem ngược: mỗi màn thì lego/gói nào vào được.
- **Nhóm quyền mẫu** — các gói mẫu theo vai.

> Từ màn **Quản lý nhân sự**, nút **Mở Phân quyền cho người này** nhảy thẳng tới người đó.

---

## Khi nào cần nhờ dev

| Tình huống | Làm gì |
|---|---|
| Màn báo lỗi đỏ khi bấm Lưu / Thêm | Chụp màn hình + ghi người, giờ, bước vừa làm |
| Muốn **xoá hẳn** một nhân sự / phòng / dịch vụ | Không có (cố ý). Cho nghỉ / tắt / thôi bán là đủ |
| Cần thêm vai hay lego mới | Báo dev — đây là cấu hình hệ thống, không làm trên màn |
| Lỡ gỡ tài khoản của chính mình / người quản lý cuối | Báo dev ngay, đừng tạo tài khoản mới thay |

## Đang làm — chưa có ở màn hiện tại

Nằm trong đợt 14/10 (`docs/KE-HOACH-DONG-TIEN-KHO-KE-TOAN-1410.md`); xong thì file này được cập nhật:

- Nhân viên **tự đổi mật khẩu**; nút **"Khoá & nghỉ việc"** gộp một lần; **chặn tự gỡ tài khoản của mình**.
- Sửa **đầy đủ hồ sơ khách** (địa chỉ, CCCD, email).
- Vai **Kế toán** và thuế GTGT theo dịch vụ.
