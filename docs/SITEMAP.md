# SITEMAP — bản đồ màn hình ClinicAI

> Lập 18/09/2026 từ code tại commit `228944f` (nhánh `lat-1-luot-kham`). **Chỉ
> quét code, chưa bấm thử từng trang.** Mọi dòng dưới đây đều có nguồn: quyền
> vào lấy từ `NAV_ROLES` trong `src/dashboard/lib/roles.ts`, nhãn thanh bên lấy
> từ `app/(dashboard)/nav-items.ts`, "ai dẫn tới" lấy từ grep đường dẫn trong
> `src/dashboard` và `src/clinicai`.
>
> **Tờ này là bản chuẩn.** Trước khi sửa giao diện, tra ở đây xem chức năng đó
> có mấy lối vào (mục B), rồi sửa **tất cả**. Thêm, xoá hay đổi một route thì
> sửa tờ này trong **cùng commit**.

Trạng thái đề xuất:
- **GIỮ**: màn chuẩn, đang dùng.
- **GỘP**: trùng việc với màn khác, đề xuất chuyển hướng sang màn chuẩn.
- **ĐÃ CHUYỂN HƯỚNG**: file chỉ còn `redirect()`, không có giao diện.
- **CẦN QUYẾT**: Tuyền chốt giúp.
- **DEV**: chỉ chạy ở máy dev; bị chặn trên prod.

⚠️ Công tắc `NEXT_PUBLIC_MO_QUYEN_TAM_THOI` đang **BẬT** (mặc định `"1"`, xem
`roles.ts`). Khi bật, **mọi vai trong phòng khám gõ URL là vào được mọi trang**
trong bảng này. Ngoại lệ: `/portal`, `/console`, `/ops*`, `/settings*`,
`/reports`, `/doi-tac`, `/display`. Cột "Ai vào" dưới đây là **luật gốc**, chưa
tính công tắc.

---

## A. Toàn bộ 66 trang

### Đăng nhập và điểm vào

| Route | Ai vào | Việc | Đề xuất | Ghi chú |
|---|---|---|---|---|
| `/login` · `/forgot-password` · `/reset-password` | chưa đăng nhập | Đăng nhập, quên và đặt lại mật khẩu | GIỮ | |
| `/` | mọi vai | Chuyển tới trang đích theo vai (`roleLanding`) | **GIỮ, SỬA** | ⚠️ Bác sĩ và thư ký đang bị đưa về **`/tasks` (màn cũ)**. Màn chính của họ là `/ban-kham`. |
| `/home` | mọi vai | Trang chủ: bảng lịch tuần, check-in, trạng thái buổi | GIỮ · **CẦN QUYẾT** | Đây cũng là lối vào thứ hai của **check-in** và **bệnh án**, xem mục B. |

### Lễ tân và điều dưỡng

| Route | Ai vào | Nhãn thanh bên | Đề xuất | Ghi chú |
|---|---|---|---|---|
| `/reception/queue` | Lễ tân, ĐD, QL | Tiếp đón khách | GIỮ | Màn chuẩn của hàng chờ đã check-in. |
| `/reception/checkout` | Lễ tân, QL | Check-out lượt khám | GIỮ | |
| `/do-sinh-hieu` | ĐD, Lễ tân, BS, QL | Đo sinh hiệu | GIỮ | **Nơi DUY NHẤT ghi sinh hiệu.** Máy chủ từ chối đường cũ từ `6976513`. |
| `/phong/[ma]` | theo từng phòng trong `NAV_ROLES` | Lấy mẫu XN · 3 phòng SA · 4 phòng thủ thuật/dịch vụ | GIỮ | Một component (`PhongDichVu`) cho mọi phòng. |
| `/queue` | **không vai nào** (`[]`) | Số thứ tự gọi khám | **GỘP → `/reception/queue`** | Quang ẩn từ 03/07, nhưng công tắc mở quyền làm nó **vào lại được bằng URL**. `/api/v1/queue` là hệ số cũ. |

### Bác sĩ và thư ký

| Route | Ai vào | Nhãn thanh bên | Đề xuất | Ghi chú |
|---|---|---|---|---|
| `/ban-kham` · `/ban-kham/[phong]` | BS, TKYK, QL | Bàn khám (khách của tôi) · Bàn khám · Phòng … | GIỮ | Màn khám chuẩn. |
| `/duyet-ket-qua` | BS, BS SA, QL | Duyệt kết quả | GIỮ | |
| `/tasks` | QL, thu ngân, TKYK, ĐD, BS | Công việc của tôi | **GỘP, CẦN QUYẾT** | Màn cũ, 5 nhánh theo vai (`tasks/page.tsx:206-230`), xem mục C. Vẫn nằm trên thanh dưới của TKYK (`THANH_DUOI.TKYK`). |
| `/patient-list` | gần như mọi vai trong phòng | Danh sách bệnh nhân | GIỮ | Tra cứu chung. Mở được bệnh án (lối vào thứ ba). |
| `/patients/[id]` | theo quyền trong trang | (không có mục) | GIỮ | Hồ sơ một bệnh nhân. |
| `/patients/new` | Lễ tân, QL | Tạo bệnh nhân / Thêm khách hàng / Nhập thông tin khách hàng mới | GIỮ | Cùng `NewPatientForm` với tab "Thêm" trong `/appointments`, nên không lệch. **Một nút mang 3 tên theo vai** (`navLabelFor`). |

### Thu ngân và nhà thuốc

| Route | Ai vào | Nhãn thanh bên | Đề xuất | Ghi chú |
|---|---|---|---|---|
| `/thu-ngan/dich-vu` · `/thu-ngan/thuoc` | Lễ tân, thu ngân, QL | Thu tiền dịch vụ · Thu tiền thuốc | GIỮ | Màn thu tiền chuẩn (`QuayThuNgan`, nút **"Đã nhận đủ"**). |
| `/cashier/board` | thu ngân, QL | (không có mục) | **GỘP → `/thu-ngan/dich-vu`** | Cùng `QuayThuNgan`, là bản thứ ba của cùng một màn. |
| `/cashier` | | | ĐÃ CHUYỂN HƯỚNG → `/cashier/thuoc` | |
| `/cashier/thuoc` · `/cashier/dich-vu` | Lễ tân, thu ngân, QL | Bảng giá thuốc · Bảng giá dịch vụ | GIỮ | Là **bảng giá**, không phải thu tiền; đường dẫn dễ nhầm. Sẽ đụng khi làm lại kho thuốc (hai nguồn giá). |
| `/pharmacy` | Lễ tân, dược sĩ, QL | Cấp thuốc | GIỮ | Sẽ làm lại trong đợt kho thuốc. |
| `/pharmacy/inventory` | Lễ tân, dược sĩ, QL | Kho thuốc | GIỮ | Như trên. |
| `/pharmacy/history` · `/pharmacy/consult` | dược sĩ, QL | Lịch sử bàn giao · Tư vấn dùng thuốc | CẦN QUYẾT | Còn gắn badge "Mới". |

### CSKH và lịch hẹn

| Route | Ai vào | Nhãn thanh bên | Đề xuất | Ghi chú |
|---|---|---|---|---|
| `/customers` | CSKH, QL, trưởng ca, thu ngân | Quản lý khách hàng | GIỮ | Màn chuẩn của CSKH. |
| `/appointments` | CSKH, Lễ tân, QL | Đặt lịch | GIỮ | |
| `/appointments/cho-xep-bac-si` | QL, CSKH | Chờ xếp bác sĩ | GIỮ | Thông báo từ máy chủ trỏ vào đây. |
| `/nhac-tai-kham` | QL | Nhắc tái khám | GIỮ | Cùng API với khối nhắc tái khám trong `/customers`. |
| `/cskh-tasks` | QL | Nhiệm vụ chăm sóc | **CẦN QUYẾT (đề xuất GỘP → `/customers`)** | Theo chú thích `roles.ts:305-314`, màn này đọc `cskh_action` đang rỗng; việc thật nằm ở `/customers`. |
| `/episodes` | QL | Đóng đợt khám | CẦN QUYẾT | Luồng EPI-01 (29/06). Chưa rõ còn dùng với luồng khám mới không. |
| `/lich-do-ve` | QL | Lịch đổ về | GIỮ | |

### Trưởng ca, đối tác, màn TV

| Route | Ai vào | Nhãn thanh bên | Đề xuất |
|---|---|---|---|
| `/truong-ca` | trưởng ca, QL | Điều phối ca | GIỮ |
| `/truong-ca/hang-doi` | trưởng ca, QL | Hàng đợi theo trạm | GIỮ |
| `/truong-ca/lich-su` | trưởng ca, QL | Lịch sử điều phối | GIỮ |
| `/truong-ca/tv` | trưởng ca, QL | TV phòng chờ | GIỮ |
| `/doi-tac` | đối tác, QL | Việc của đối tác | GIỮ |
| `/display` | DISPLAY (máy TV) | (không có mục) | GIỮ |

### Quản lý và hệ thống

| Route | Ai vào | Nhãn thanh bên | Đề xuất | Ghi chú |
|---|---|---|---|---|
| `/schedule` | mọi vai trừ CSKH, đối tác, TV | Lịch làm việc | GIỮ | |
| `/work-sessions` | QL | Buổi làm việc | CẦN QUYẾT | Chưa rõ còn cần khi đã có `/schedule`. |
| `/reports` | QL | Báo cáo | GIỮ | |
| `/audit-log` | CSKH, QL | Lịch sử thao tác | GIỮ | |
| `/nhan-su` | QL | Quản lý nhân sự | GIỮ | |
| `/settings` | QL | Cài đặt | GIỮ | |
| `/settings/booking-policy` | QL | Luật đặt lịch | GIỮ | |
| `/settings/clinic-config` | QL | Cấu trúc phòng khám | GIỮ | |
| `/settings/tai-khoan` | QL | Thiết lập tài khoản cho nhân viên | GIỮ | |
| `/settings/new-user` | QL | (không có mục; mở từ `/settings/tai-khoan`) | GIỮ | |
| `/portal` · `/ops` · `/ops/telemetry` | QL | Command Center · Vận hành hệ thống · Sức khoẻ API | **CẦN QUYẾT (đề xuất gộp)** | Ba màn kỹ thuật cho một người. `/portal` và `/ops` cùng đọc `/api/ops/summary`. Nhãn "Command Center" là tiếng Anh. |
| `/console` | | | DEV | `notFound()` khi `APP_ENV=production`. |
| `/design-system` | | | DEV | `notFound()` khi không phải `development`. |
| `/print/[appointmentId]` | | (nút In phiếu) | GIỮ | |
| `/print/sono/[id]` | | | CẦN QUYẾT | **Không chỗ nào dẫn tới** (grep 0 kết quả). |

### Đã chuyển hướng (không còn giao diện)

| Route cũ | Chuyển tới | Còn ai dẫn tới |
|---|---|---|
| `/doctor/board` · `/doctor/orders/[visitId]` · `/kham/[loai]` · `/luot-kham` | `/ban-kham` | `app/console` (DEV) |
| `/lab-queue` | `/phong/KN-LAYMAU` | — |
| `/service-queue` | `/phong/KN-THUTHUAT` | — |
| `/sieu-am` · `/sono` | `/phong/KN-SA-T1` | — |
| `/result-review` | `/duyet-ket-qua` | ⚠️ **Máy chủ vẫn gửi thông báo trỏ vào đây** (`services/bao_ket_qua_ve.py:77,89`). |

Đề xuất: sửa `bao_ket_qua_ve.py` sang `/duyet-ket-qua` trước. Sau đó giữ các file
chuyển hướng thêm một thời gian cho bookmark cũ, rồi mới xoá.

---

## B. Một chức năng, mấy lối vào (bảng tra trước khi sửa)

Sửa một chức năng thì phải sửa **đủ các lối trong hàng của nó**. Đây là chỗ các
lần sửa trước hay sót.

| Chức năng | Lối vào (file) | Màn chuẩn |
|---|---|---|
| **Mở / sửa bệnh án** (`ClinicalRecordForm`) | `ban-kham/BanKham.tsx` · `home/HomeCheckin.tsx` · `home/WeeklyAppointmentsTable.tsx` · `patient-list/PatientListView.tsx` · `tasks/DoctorWorkBoard.tsx` | `/ban-kham` |
| **Phiếu khám theo dịch vụ** (`ServiceFormEngine`) | `ban-kham/BanKham.tsx` · `tasks/ClinicalRecordForm.tsx` | `/ban-kham` |
| **Check-in** | `home/WeeklyAppointmentsTable.tsx` (cột thao tác, Lễ tân) · `home/HomeCheckin.tsx` (Quản lý) · đặt lịch "Trực tiếp" hôm nay (tự check-in, `/appointments`) | CẦN QUYẾT |
| **Hàng chờ tiếp đón** (`QueueBoard`) | `/reception/queue` · `/queue` (hai file `QueueBoard` **khác nhau**) | `/reception/queue` |
| **Ghi sinh hiệu** | `/do-sinh-hieu`. Biểu mẫu bệnh án chỉ còn **xem** + nút dẫn sang. | `/do-sinh-hieu` |
| **Thu tiền** (`POST /api/payment`) | `cashier/board/QuayThuNgan.tsx` (3 route) · `tasks/CashierWorkBoard.tsx` (`/tasks` cho vai thu ngân) | `/thu-ngan/*` |
| **Tạo bệnh nhân** (`NewPatientForm`) | `/patients/new` · tab "Thêm" trong `/appointments` | cùng một component |
| **Đặt / sửa lịch** (`AppointmentBooking`) | `customers/AppointmentEditModal.tsx` · `customers/DatLichModal.tsx` · `patients/[id]/PatientBooking.tsx`. `/appointments` dùng `BookingHub` riêng. | CẦN QUYẾT |
| **Nhắc tái khám** (`/api/recall-jobs`) | `customers/NhacTaiKham.tsx` · `customers/VungLamViecKhach.tsx` · `nhac-tai-kham/ViecGoiNhac.tsx` | cùng API |
| **Tệp kết quả** (`/api/cskh/ket-qua`) | `customers/TepKetQua.tsx` · `_lam-viec/KhungTep.tsx` · `tasks/TepCuaLuotKham.tsx` | |

---

## C. `/tasks` — màn cũ còn sống lớn nhất

`tasks/page.tsx` rẽ 5 nhánh theo vai:

| Vai | Hiện gì | Trùng với | Đề xuất chuyển tới |
|---|---|---|---|
| Thu ngân | `CashierWorkBoard` | `/thu-ngan/*` (`QuayThuNgan`) | `/thu-ngan/dich-vu` |
| TKYK, bác sĩ | `DoctorWorkBoard` | `/ban-kham` | `/ban-kham` |
| Điều dưỡng | `DoctorWorkBoard` (chỉ sinh hiệu) | `/do-sinh-hieu` | `/do-sinh-hieu` |
| Lễ tân (chỉ đọc) | `DoctorWorkBoard` read-only | `/reception/queue` | `/reception/queue` (Lễ tân đã bị gỡ khỏi `NAV_ROLES["/tasks"]`) |
| Quản lý / còn lại | `ConfirmBoard` + `CskhActionBoard` | `/customers`, `/cskh-tasks` | CẦN QUYẾT |

**Bài học có thật (17/09):** nút QR demo được gỡ ở `CashierWorkBoard`, tức
**bản cũ ở `/tasks`**. Màn thu tiền đang dùng (`QuayThuNgan`, nút "Đã nhận đủ")
vốn không có QR. Hai màn thu tiền còn đặt hai tên khác nhau cho cùng một nút:
"Đã thanh toán" và "Đã nhận đủ".

---

## D. Số đo giao diện (18/09, để đo tiến bộ)

| Hạng mục | Số |
|---|---|
| Trang (`page.tsx`) | 66, trong đó 10 file chỉ còn chuyển hướng, cộng `/` chuyển theo vai |
| Mục thanh bên (`NAV`) | 53, không mục nào trỏ tới trang không tồn tại |
| `<button>` viết tay | 337 chỗ / 97 file, 53 kiểu class khác nhau |
| Dùng `<Button>` / `buttonClass()` chung | 6 chỗ |
| `<button>` thiếu `type=` | 80 |
| `style={{…}}` | 145 chỗ / 18 file |
| Màu hex viết cứng | 13 chỗ / 4 file |
| `window.confirm` | 5 |
| `href="#"` | 0 |
