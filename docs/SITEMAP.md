# SITEMAP — bản đồ màn hình ClinicAI

> Lập 18/09/2026 (lượt 1, commit `6888633`). Cập nhật cùng ngày sau lượt 2:
> Tuyền chốt "1 ok, 2 bỏ ở home, 3 chỉ xem, 4 gộp hết".
>
> Mọi dòng đều có nguồn:
> - quyền vào lấy từ `NAV_ROLES` trong `src/dashboard/lib/roles.ts`;
> - nhãn thanh bên lấy từ `app/(dashboard)/nav-items.ts`;
> - "ai dẫn tới" lấy từ grep trong `src/dashboard` và `src/clinicai`.
>
> **Tờ này là bản chuẩn.** Trước khi sửa giao diện, tra ở đây xem chức năng đó
> có mấy lối vào (mục B), rồi sửa **tất cả**. Thêm, xoá hay đổi một route thì
> sửa tờ này trong **cùng commit**. Bài kiểm `tests/man-da-gop-boundary.test.mts`
> canh các màn đã gộp: chúng chỉ được còn chuyển hướng.

Trạng thái:
- **GIỮ**: màn chuẩn, đang dùng.
- **ĐÃ CHUYỂN HƯỚNG**: file trang chỉ còn `redirect()`, không có giao diện,
  không có mục thanh bên, không có dòng trong `NAV_ROLES`. Không sửa gì ở đây.
- **CẦN QUYẾT**: chưa chốt.
- **DEV**: chỉ chạy ở máy dev; bị chặn trên prod.

⚠️ Công tắc `NEXT_PUBLIC_MO_QUYEN_TAM_THOI` đang **BẬT** (mặc định `"1"`, xem
`roles.ts`). Khi bật, **mọi vai trong phòng khám gõ URL là vào được mọi trang**
trong bảng này. Ngoại lệ: `/console`, `/ops`, `/settings*`, `/reports`,
`/doi-tac`, `/display`. Cột "Ai vào" là **luật gốc**, chưa tính công tắc.

---

## A. Các trang

### Đăng nhập và điểm vào

| Route | Ai vào | Việc | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/login` · `/forgot-password` · `/reset-password` | chưa đăng nhập | Đăng nhập, quên và đặt lại mật khẩu | GIỮ | |
| `/` | mọi vai | Chuyển tới trang đích theo vai (`roleLanding`) | GIỮ | Bác sĩ và thư ký → `/ban-kham`. Bác sĩ siêu âm → `/phong/KN-SA-T1`. Đối tác → `/doi-tac`. Trưởng ca → `/truong-ca`. Còn lại → `/home`. |
| `/home` | mọi vai | Trang chủ: lịch tuần (**chỉ xem**), trạng thái buổi, lịch làm việc | GIỮ | **Không check-in ở đây** (18/09). Bấm tên khách mở biểu mẫu **chỉ xem**, có nút "Mở ở Bàn khám". Vai check-in thấy nút "Check-in ở Tiếp đón khách". |

### Lễ tân và điều dưỡng

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/reception/queue` | Lễ tân, ĐD, QL | Tiếp đón khách | GIỮ | **Nơi DUY NHẤT check-in.** Trên cùng là "Lịch hẹn hôm nay", có Check-in / Không đến / Hoàn tác. Bên dưới là hàng đợi người đã check-in. |
| `/reception/checkout` | Lễ tân, QL | Check-out lượt khám | GIỮ | |
| `/do-sinh-hieu` | ĐD, Lễ tân, BS, QL | Đo sinh hiệu | GIỮ | **Nơi DUY NHẤT ghi sinh hiệu.** Máy chủ từ chối đường cũ từ `6976513`. |
| `/phong/[ma]` | theo từng phòng trong `NAV_ROLES` | Lấy mẫu XN · 3 phòng SA · 4 phòng thủ thuật/dịch vụ | GIỮ | Một component (`PhongDichVu`) cho mọi phòng. |

### Bác sĩ và thư ký

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/ban-kham` · `/ban-kham/[phong]` | BS, TKYK, QL | Bàn khám (khách của tôi) · Bàn khám · Phòng … | GIỮ | **Nơi DUY NHẤT sửa bệnh án.** |
| `/duyet-ket-qua` | BS, BS SA, QL | Duyệt kết quả | GIỮ | Thông báo "có kết quả về" trỏ thẳng vào đây (`bao_ket_qua_ve.py`). |
| `/patient-list` | gần như mọi vai trong phòng | Danh sách bệnh nhân | GIỮ | Tra cứu chung. Bệnh án mở ở đây **chỉ xem** (`readOnly`). |
| `/patients/[id]` | theo quyền trong trang | (không có mục) | GIỮ | Hồ sơ một bệnh nhân. |
| `/patients/new` | Lễ tân, QL | Tạo bệnh nhân / Thêm khách hàng / Nhập thông tin khách hàng mới | GIỮ | Cùng `NewPatientForm` với tab "Thêm" trong `/appointments`. Một nút mang 3 tên theo vai (`navLabelFor`). |

### Thu ngân và nhà thuốc

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/thu-ngan/dich-vu` · `/thu-ngan/thuoc` | Lễ tân, thu ngân, QL | Thu tiền dịch vụ · Thu tiền thuốc | GIỮ | **Màn thu tiền duy nhất.** `thu-ngan/QuayThuNgan.tsx`, nút "Đã nhận đủ". |
| `/cashier/thuoc` · `/cashier/dich-vu` | Lễ tân, thu ngân, QL | Bảng giá thuốc · Bảng giá dịch vụ | GIỮ | Là **bảng giá**, không phải thu tiền. Sẽ đụng khi làm lại kho thuốc (hai nguồn giá). |
| `/pharmacy` | Lễ tân, dược sĩ, QL | Cấp thuốc | GIỮ | Sẽ làm lại trong đợt kho thuốc. |
| `/pharmacy/inventory` | Lễ tân, dược sĩ, QL | Kho thuốc | GIỮ | Như trên. |
| `/pharmacy/history` · `/pharmacy/consult` | dược sĩ, QL | Lịch sử bàn giao · Tư vấn dùng thuốc | CẦN QUYẾT | Còn gắn badge "Mới". |

### CSKH và lịch hẹn

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/customers` | CSKH, QL, trưởng ca, thu ngân | Quản lý khách hàng | GIỮ | Màn chuẩn của CSKH. |
| `/appointments` | CSKH, Lễ tân, QL | Đặt lịch | GIỮ | Đặt "Trực tiếp" hôm nay thì tự check-in (luật máy chủ). |
| `/appointments/cho-xep-bac-si` | QL, CSKH | Chờ xếp bác sĩ | GIỮ | Thông báo từ máy chủ trỏ vào đây. |
| `/nhac-tai-kham` | QL | Nhắc tái khám | GIỮ | Cùng API với khối nhắc tái khám trong `/customers`. |
| `/lich-do-ve` | QL | Lịch đổ về | GIỮ | |

### Trưởng ca, đối tác, màn TV

| Route | Ai vào | Nhãn thanh bên | Trạng thái |
|---|---|---|---|
| `/truong-ca` | trưởng ca, QL | Điều phối ca | GIỮ |
| `/truong-ca/hang-doi` | trưởng ca, QL | Hàng đợi theo trạm | GIỮ |
| `/truong-ca/lich-su` | trưởng ca, QL | Lịch sử điều phối | GIỮ |
| `/truong-ca/tv` | trưởng ca, QL | TV phòng chờ | GIỮ |
| `/doi-tac` | đối tác, QL | Việc của đối tác | GIỮ |
| `/display` | DISPLAY (máy TV) | (không có mục) | GIỮ |

### Quản lý và hệ thống

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/schedule` | mọi vai trừ CSKH, đối tác, TV | Lịch làm việc | GIỮ | |
| `/reports` | QL | Báo cáo | GIỮ | |
| `/audit-log` | CSKH, QL | Lịch sử thao tác | GIỮ | |
| `/nhan-su` | QL | Quản lý nhân sự | GIỮ | |
| `/settings` | QL | Cài đặt | GIỮ | |
| `/settings/booking-policy` | QL | Luật đặt lịch | GIỮ | |
| `/settings/clinic-config` | QL | Cấu trúc phòng khám | GIỮ | |
| `/settings/tai-khoan` | QL | Thiết lập tài khoản cho nhân viên | GIỮ | |
| `/settings/new-user` | QL | (không có mục; mở từ `/settings/tai-khoan`) | GIỮ | |
| `/ops` | QL | Vận hành hệ thống | GIỮ | **Ba tab:** Hệ thống (`OpsCenter`) · Sức khoẻ API (`SucKhoeApi`, `?tab=api`) · Toàn cảnh (`ToanCanh` → `PortalBoard`, `?tab=toan-canh`; tiêu đề trong tab cũng là "Toàn cảnh"). Thanh trên cùng của trang không có tiêu đề riêng lấy tên nút thanh bên (`GlobalHeader` ← `NAV`). |
| `/console` | | | DEV | `notFound()` khi `APP_ENV=production`. |
| `/design-system` | | | DEV | `notFound()` khi không phải `development`. |
| `/print/[appointmentId]` | | (nút In phiếu) | GIỮ | |
| `/print/sono/[id]` | | | CẦN QUYẾT | **Không chỗ nào dẫn tới** (grep 0 kết quả). |

### Đã chuyển hướng (không còn giao diện)

| Route cũ | Chuyển tới | Gộp ngày |
|---|---|---|
| `/tasks` | **theo vai:** thu ngân → `/thu-ngan/dich-vu` · BS SA → `/phong/KN-SA-T1` · BS/TKYK → `/ban-kham` · ĐD → `/do-sinh-hieu` · Lễ tân → `/reception/queue` · QL/CSKH → `/customers` · còn lại → `/home` | 18/09 |
| `/queue` | `/reception/queue` | 18/09 |
| `/cashier/board` | `/thu-ngan/dich-vu` | 18/09 |
| `/cskh-tasks` | `/customers` (bảng `cskh_action` 0 dòng trên prod) | 18/09 |
| `/episodes` | `/customers` (0 đợt `PENDING_CLOSE` trên prod; không code nào còn tạo trạng thái ấy) | 18/09 |
| `/work-sessions` | `/schedule` (bảng `work_session` 0 dòng trên prod) | 18/09 |
| `/portal` | `/ops?tab=toan-canh` | 18/09 |
| `/ops/telemetry` | `/ops?tab=api` | 18/09 |
| `/doctor/board` · `/doctor/orders/[visitId]` · `/kham/[loai]` · `/luot-kham` | `/ban-kham` | 16/09 |
| `/lab-queue` | `/phong/KN-LAYMAU` | 16/09 |
| `/service-queue` | `/phong/KN-THUTHUAT` | 16/09 |
| `/sieu-am` · `/sono` | `/phong/KN-SA-T1` | 16/09 |
| `/result-review` | `/duyet-ket-qua` | 16/09 |
| `/cashier` | `/cashier/thuoc` | |

Thư mục `app/(dashboard)/tasks/` vẫn giữ **component dùng chung**:
`ClinicalRecordForm`, `ServiceFormEngine`, `DoctorApptRow`… Chỉ `page.tsx` là
chuyển hướng.

---

## B. Một chức năng, mấy lối vào (bảng tra trước khi sửa)

| Chức năng | Lối vào (file) | Ghi / xem |
|---|---|---|
| **Bệnh án** (`ClinicalRecordForm`) | `ban-kham/BanKham.tsx` | **ghi** |
| | `home/WeeklyAppointmentsTable.tsx` | chỉ xem (`readOnly` + `vitalsOnly`) |
| | `patient-list/PatientListView.tsx` | chỉ xem (`readOnly`) |
| **Phiếu khám theo dịch vụ** (`ServiceFormEngine`) | `ban-kham/BanKham.tsx` · `tasks/ClinicalRecordForm.tsx` | ghi ở Bàn khám |
| **Check-in / Không đến / Hoàn tác** | `reception/queue/page.tsx` → `WeeklyAppointmentsTable` với `choCheckIn` | chỉ ở đây |
| | đặt lịch "Trực tiếp" hôm nay (`/appointments`) | máy chủ tự check-in |
| **Bảng lịch hẹn** (`WeeklyAppointmentsTable` + `home/lich-hen-ngay.ts`) | `/home` (cả tuần, xem) · `/reception/queue` (hôm nay, check-in) | cùng một phép dựng |
| **Hàng chờ tiếp đón** (`QueueBoard`) | `/reception/queue` | |
| **Ghi sinh hiệu** | `/do-sinh-hieu` | biểu mẫu bệnh án chỉ xem + nút dẫn sang |
| **Thu tiền** (`POST /api/payment`) | `thu-ngan/QuayThuNgan.tsx` (qua `/thu-ngan/dich-vu`, `/thu-ngan/thuoc`) | chỉ ở đây |
| **Tạo bệnh nhân** (`NewPatientForm`) | `/patients/new` · tab "Thêm" trong `/appointments` | cùng component |
| **Đặt / sửa lịch** (`AppointmentBooking`) | `customers/AppointmentEditModal.tsx` · `customers/DatLichModal.tsx` · `patients/[id]/PatientBooking.tsx` | `/appointments` dùng `BookingHub` riêng — CẦN QUYẾT |
| **Nhắc tái khám** (`/api/recall-jobs`) | `customers/NhacTaiKham.tsx` · `customers/VungLamViecKhach.tsx` · `nhac-tai-kham/ViecGoiNhac.tsx` | cùng API |
| **Tệp kết quả** (`/api/cskh/ket-qua`) | `customers/TepKetQua.tsx` · `_lam-viec/KhungTep.tsx` · `tasks/TepCuaLuotKham.tsx` | |
| **Chỉ định dịch vụ / cận lâm sàng** (`service_order`) | `ban-kham/BanKham.tsx` → `ChiDinhPanel` (thư ký ghi nháp, bác sĩ duyệt) | **chỉ ở đây.** Ô "Chỉ định CLS" gõ tự do trong bệnh án (ghi `lab_result`) đã gỡ 18/09 — Slice 1 |
| **Bác sĩ quyết kết quả chờ / dịch vụ không làm được** (`/luot-kham/cho-quyet`, `quyet-yeu-cau`) | `ban-kham/ChoBacSiQuyet.tsx` | bác sĩ quyết; thư ký chỉ xem — Slice 1 |
| **Xem lại một lượt khám** (`/xem-luot/{visit}`, chỉ đọc, máy chủ cắt theo vai) | `_lam-viec/XemLuot.tsx` (+ `NutXemLuot.tsx`) mở từ: `ban-kham/BanKham.tsx` · `do-sinh-hieu/BangDoSinhHieu.tsx` · `phong/[ma]/PhongDichVu.tsx` · `truong-ca/ChiDinhHomNay.tsx` · `reception/queue/QueueBoard.tsx` · `thu-ngan/GiaoDich.tsx` · `pharmacy/PharmacyBoard.tsx` | batch pilot 18/09 |
| **Thai kỳ** (`/api/thai-ky`) | `ban-kham/ThaiKy.tsx` (cạnh phiếu Sản) | bác sĩ ghi; vai lâm sàng khác chỉ xem |
| **Giao dịch thu ngân đã ghi** (`/api/cashier?xem=giao-dich`) | `thu-ngan/TabThuNgan.tsx` → `GiaoDich.tsx` (tab Đã thanh toán hôm nay · Lịch sử) | chỉ đọc |
| **Chuyển phòng** | `truong-ca/ChiDinhCuaBacSi.tsx` (từng chỉ định — luồng mới) · `truong-ca/OverviewClient.tsx` (cả lượt — chỉ lượt đời cũ; lượt luồng mới bị ẩn + máy chủ từ chối) | Slice 1 |

---

## C. Bài học dẫn tới tờ này

Ngày 17/09, nút QR demo được gỡ ở `tasks/CashierWorkBoard.tsx`. Đó là **bản
cũ** ở `/tasks`. Màn thu tiền đang dùng (`QuayThuNgan`) vốn không có QR. Hai
màn còn đặt hai tên cho cùng một nút: "Đã thanh toán" và "Đã nhận đủ".

Ngày 18/09, `/tasks` và 5 component của nó đã gỡ:
`DoctorWorkBoard`, `CashierWorkBoard`, `ConfirmBoard`, `CskhActionBoard`,
`TasksRealtime`.

---

## D. Số đo giao diện (để đo tiến bộ)

| Hạng mục | 18/09 trước lượt 2 | Sau lượt 2 |
|---|---|---|
| Mục thanh bên (`NAV`) | 53 | 46 |
| `[..px]` tự chế (ratchet `px-tu-che`) | 85 | 64 |
| `<button>` viết tay | 337 / 97 file | chưa đo lại |
| Dùng `<Button>` / `buttonClass()` chung | 6 | chưa đo lại |
| `window.confirm` | 5 | chưa đo lại |
