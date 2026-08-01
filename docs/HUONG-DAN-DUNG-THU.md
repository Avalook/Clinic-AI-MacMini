# Hướng dẫn dùng thử ClinicAI

Dành cho người muốn **bấm hết mọi thứ để tìm lỗi**. Viết theo thứ tự một ngày làm
việc thật, không theo thứ tự menu.

Đọc kèm: mục **[Biết trước để khỏi mất công](#biết-trước-để-khỏi-mất-công)** —
liệt kê những chỗ đã biết là chưa xong, để anh không tốn thời gian báo lại.

---

## 0. Khởi động

```bash
scripts/dev-up.sh            # dựng cả stack, tự kiểm, tự tạo 3 lượt khám để bấm
scripts/dev-up.sh --reset    # xoá sạch, làm lại từ đầu (khi dữ liệu rối)
scripts/dev-up.sh --down     # dừng
```

| | |
|---|---|
| Dashboard | http://127.0.0.1:3100 |
| API docs (Swagger) | http://127.0.0.1:8100/docs |
| Supabase Studio (xem thẳng DB) | http://127.0.0.1:54323 |
| Log | `.dev-logs/api.log`, `.dev-logs/web.log` |

**Mật khẩu chung cho mọi tài khoản: `clinic-test-pw-123`**

| Vai | Email |
|---|---|
| Lễ tân | `letan@dr4women.local` |
| Bác sĩ | `bs.a@dr4women.local` |
| Điều dưỡng siêu âm | `dd.sa@dr4women.local` |
| Thu ngân | `thungan@dr4women.local` |
| Quản lý | `ql@dr4women.local` |
| CSKH | `cskh@dr4women.local` |
| Bác sĩ siêu âm | `bs.sa@dr4women.local` |

> **Mẹo:** mở mỗi vai ở **một cửa sổ ẩn danh riêng**. Đăng nhập vai này sẽ đá vai
> kia ra nếu dùng chung cửa sổ.

---

## 1. Luồng chính — đi trọn một lượt khám (15 phút)

Đây là phần đáng thử nhất, vì nó là thứ mới và là xương sống của hệ.

### Bước 1 — Lễ tân tiếp nhận

Đăng nhập `letan@` → **Hàng đợi tiếp nhận**.

Sẽ thấy 3 người bệnh đang chờ. Chọn người đầu → panel phải hiện:
- Số thứ tự, điện thoại, thời gian chờ
- **Trạng thái xử lý** — dãy bước ngang
- Nút **Bắt đầu xử lý** / **Hoàn tất bước này**

**Thử:** bấm *Bắt đầu xử lý* → chip đổi sang *Đang thực hiện*. Bấm *Hoàn tất* →
người đó biến khỏi hàng đợi.

**Nên soi:** ô KPI trên cùng có tự trừ đi không? Có phải tải lại trang mới đổi
không?

### Bước 2 — Bác sĩ bị chặn (đây là phần hay nhất)

Đăng nhập `bs.a@` → **Bàn khám**.

Người bệnh vừa rồi nằm ở nhóm **"Chờ bước trước"**, và panel phải ghi rõ:

> **Chưa thao tác được** — Đang chờ bước LUOTKHAM-03 hoàn tất.

**Không có nút nào để bấm** — cố ý. Bác sĩ chưa khám được vì **chưa đo sinh
hiệu**, và màn hình nói ra điều đó thay vì đưa một cái nút xám.

> Điều đáng chú ý: **không ai lập trình luật "bác sĩ phải đợi điều dưỡng" vào màn
> hình này.** Nó là một dòng phụ thuộc trong bảng `node_dependency`. Đổi dòng đó
> là cả ba màn đổi theo.

### Bước 3 — Điều dưỡng đo sinh hiệu

Đăng nhập `dd.sa@` → **Hàng đợi tiếp nhận** (cùng màn với lễ tân, nhưng điều
dưỡng thấy bước *Đo sinh hiệu*).

Chọn đúng người bệnh đó → **Bắt đầu** → **Hoàn tất**.

### Bước 4 — Bác sĩ mở khoá

Quay lại `bs.a@` → **Bàn khám** → **tải lại trang**.

Người bệnh đã **nhảy từ "Chờ bước trước" sang "Sẵn sàng khám"**, KPI đổi `0 → 1`,
và nút **Bắt đầu khám** hiện ra rõ ràng.

**Thử:** bấm *Bắt đầu khám*.

### Bước 5 — Bác sĩ ra chỉ định

Vào thẳng URL (chưa có link trên menu — xem phần Biết trước):

```
http://127.0.0.1:3100/doctor/orders/<visit_id>
```

Lấy `visit_id` ở Supabase Studio → bảng `visit`, hoặc:

```bash
psql postgresql://postgres:postgres@127.0.0.1:54322/postgres \
  -c "SELECT visit_id FROM work_item WHERE node_code='LUOTKHAM-05' AND status='IN_PROGRESS'"
```

Màn *Chỉ định dịch vụ*: 29 dịch vụ **gom theo PHÒNG THỰC HIỆN**, không theo bảng
giá — vì gom theo phòng thì mới thấy 4 thứ cùng làm ở phòng siêu âm là **một lượt
đi** cho bệnh nhân.

**Thử:**
- Tích **2 dịch vụ siêu âm + 1 xét nghiệm máu** → **Gửi chỉ định**
- Thông báo phải nói **gửi tới 2 phòng** (2 siêu âm gộp thành 1 việc)
- Tích lại đúng dịch vụ vừa gửi → phải hiện **cảnh báo trùng trong 30 ngày**
- Thử tích **"Khám phụ khoa"** → nó bị **khoá**, chip *"Chưa gắn phòng thực hiện"*.
  Đúng: đó là *khám*, không phải chỉ định cho người khác làm.

### Bước 6 — Thu ngân đối soát

Đăng nhập `thungan@` → **Bàn thu ngân**.

Chọn lượt khám đó → thấy **đúng những dịch vụ bác sĩ vừa chỉ định**, mỗi dòng kèm
trạng thái *Sẵn sàng / Đang thực hiện / Hoàn thành*.

Và một banner vàng: **"Chưa tính được thành tiền — 3/3 dịch vụ chưa có giá."**

> Cố ý không hiện `0 đ`. Số 0 sẽ bị đọc thành *"không phải trả gì"*.
> Bảng giá của phòng khám đang trống hoàn toàn — xem phần Biết trước.

---

## 2. Thử phá — những chỗ tôi muốn anh cố làm hỏng

| Thử | Mong đợi |
|---|---|
| Hai cửa sổ cùng mở một người bệnh, cả hai bấm *Hoàn tất* | Cửa sổ thứ hai phải **báo lỗi**, không được ghi đè |
| Lễ tân gõ thẳng `/ops/telemetry` | Phải thấy *"chỉ dành cho vai Quản lý"*, không phải trang vỡ |
| Bác sĩ mở *Bàn thu ngân* | Menu không có, nhưng gõ URL vào xem sao |
| Tắt API (`pkill -f uvicorn`) rồi tải *Hàng đợi tiếp nhận* | Phải hiện **banner đỏ**, KHÔNG được hiện "hàng đợi trống" |
| Bấm *Hoàn tất* trên bước đang bị chặn (qua API) | Phải bị từ chối 409 |
| Chỉ định 1 dịch vụ 3 lần liên tiếp | Phải **cộng dồn vào 1 việc**, không tạo 3 việc |

Cái thứ tư quan trọng nhất: **mất kết nối không được trông giống phòng chờ trống**.

Ba dòng đầu tôi đã tự kiểm trước khi viết hướng dẫn này — nếu anh thấy khác thì
đó là lỗi thật, báo ngay:

| Thử | Kết quả đo được |
|---|---|
| Hai người cùng bấm | lần 1 → `200`, lần 2 (version cũ) → **`409`** |
| Bấm bước đang bị chặn | **`409`** |
| Tắt API rồi mở hàng đợi | hiện *"Không tải được hàng đợi"* + *"ĐỪNG coi đây là hàng đợi trống"*; **không** hiện *"Hàng đợi trống"* |

---

## 3. Các màn cũ (chạy trên `staff_task`, chưa nối kernel)

Vẫn dùng được, nhưng là **hệ cũ chạy song song**. Mọi màn mới đều có badge
**"Mới"** trên menu để phân biệt.

| Màn | Vai | Ghi chú |
|---|---|---|
| **Trang chủ** | tất cả | Check-in nhanh, tiến trình buổi khám, lịch tuần |
| **Công việc của tôi** (`/tasks`) | bác sĩ, TKYK, ĐD, lễ tân (chỉ xem) | Bảng khám cũ — ghi bệnh án, sinh hiệu, kê đơn |
| **Hàng đợi** (`/queue`) | tất cả | Thứ tự gọi khám, có lane B3 (BN quay lại đọc kết quả) |
| **Thông tin khách hàng** | CSKH, lễ tân, thu ngân, QL | Danh bạ + tra cứu |
| **Danh sách bệnh nhân** | hầu hết | BN đã khám, mở được hồ sơ |
| **Tạo bệnh nhân** | CSKH, lễ tân, QL | Có phát hiện trùng SĐT |
| **Cần làm hôm nay** (`/cskh-today`) | CSKH, QL | Nhắc gọi xác nhận, tái khám |
| **ĐD siêu âm** (`/sono`) | ĐD/BS siêu âm | Nhập kết quả siêu âm |
| **Hàng đợi xét nghiệm** | TKYK | Nhập kết quả XN, có gate duyệt |
| **Thu ngân thuốc / dịch vụ** | thu ngân | Màn thu tiền cũ |
| **Trưởng ca** | trưởng ca, QL | Theo dõi buổi |
| **Lịch làm việc** | tất cả | Đăng ký ca |
| **Báo cáo** | QL | Thống kê |
| **Vận hành** (`/ops`) | QL | Trạng thái container |
| **Sức khoẻ API** (`/ops/telemetry`) | QL | **Mới** — p50/p95, lỗi 5xx |

---

## Biết trước để khỏi mất công

Những chỗ **đã biết là chưa xong**. Anh gặp thì không cần báo — trừ khi biểu hiện
khác mô tả ở đây.

### Chặn hẳn

| | |
|---|---|
| **Bảng giá trống hoàn toàn** | `service_price` và `drug_catalog` không có giá nào, ở cả production. Nên **không thu tiền được**, tạm tính luôn là `—`, báo cáo doanh thu bằng 0. Cần anh cung cấp bảng giá. |
| **Chỉ định dịch vụ chưa có link menu** | Phải gõ URL kèm `visit_id`. Đang chờ quyết định đặt nút ở đâu trên Bàn khám. |

### Chưa làm

- **Ghi chẩn đoán, kê đơn, ký duyệt kết quả** trên Bàn khám — là các node riêng
  (`KHAM-*`, `DICHVU-DUYET-KETQUA`) mà check-in chưa sinh ra.
- **Bộ chỉ định gợi ý** ("Bộ khám phụ khoa cơ bản"…) — chưa có bảng bundle. Không
  hard-code vào giao diện vì đó là phác đồ lâm sàng.
- **Điều phối quầy, gọi số, màn TV phòng chờ** — chưa có bảng quầy trong DB.
- **`visit` không bao giờ đóng** — không chỗ nào đặt `FINALIZED`. Kéo theo: luồng
  đính chính và toàn bộ vòng tái khám (`/cskh-today`) trả về rỗng.
- **Hai hệ việc song song** — `staff_task` (cũ) và `work_item` (mới) cùng chạy.

### Đã biết là lệch

- **Route không chặn theo vai** — menu ẩn đúng, nhưng gõ thẳng URL vẫn mở được
  trang; chặn nằm ở tầng API. Các màn mới xử lý êm (hiện thông báo), màn cũ thì
  chưa rà hết. **Chỗ này đáng thử.**
- **Tên bệnh nhân trong bản demo đều là "BN của Dr4Women"** — fixture chỉ có 1
  bệnh nhân. Không phải lỗi.
- **`dev-up.sh --reset` xoá sạch** rồi tạo lại 3 lượt khám mới.

### Production

Bản đang chạy cho phòng khám **không phải** bản này — repo khác, schema cũ.
Chi tiết: `docs/prod-cutover-findings.md`. Còn 2 việc chờ quyết định (hotfix
`f_unaccent`, và 5 dòng payment 0đ).

---

## Báo lỗi thế nào cho tôi sửa nhanh

```
Vai:        thu ngân
Màn:        Bàn thu ngân
Tôi làm:    bấm Hoàn tất bước này trên BN thứ 2
Mong đợi:   biến khỏi danh sách
Thực tế:    không có gì xảy ra, F5 thì vẫn còn
```

Kèm được thì tốt:
- Ảnh chụp màn hình
- `tail -30 .dev-logs/api.log`
- Console trình duyệt (F12 → Console) nếu bấm mà không phản ứng

**Loại lỗi đáng giá nhất:** *"tôi nhìn không hiểu màn này đang nói gì"*. Đó là lỗi
thiết kế của tôi, không phải anh đọc chậm — và nó khó tìm hơn lỗi kỹ thuật nhiều.
