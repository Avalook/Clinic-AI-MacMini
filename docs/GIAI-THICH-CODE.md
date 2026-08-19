# ClinicAI — Giải thích code từ A tới Z

Tài liệu này đi từ **ý tưởng nghiệp vụ → kiến trúc → từng thư mục, từng file, từng hàm, từng dòng
quan trọng** của hệ thống quản lý phòng khám ClinicAI (Dr4Women). Đọc theo thứ tự sẽ hiểu được
toàn bộ hệ thống mà không cần ai giảng thêm.

**Viết cho:** người chủ hệ thống — hiểu nghiệp vụ phòng khám, đọc được code nhưng không muốn phải
tự dò từng dòng để đoán ý.

**Quy mô được giải thích:** khoảng 100.000 dòng mã (≈40.000 dòng Python phía máy chủ,
≈61.000 dòng TypeScript phía giao diện), 117 tệp migration cơ sở dữ liệu, 13 biên bản quyết định
kiến trúc (ADR), 5 cổng kiểm tự động.

> **Nguyên tắc của tài liệu:** mỗi chỗ đều trả lời **"vì sao"** chứ không chỉ **"làm gì"**.
> Code thì đọc lại lúc nào cũng được; còn lý do một dòng code trông kỳ quặc thì mất đi vĩnh viễn
> nếu không ai ghi lại.

---

## MỤC LỤC

| Phần | Nội dung | Đọc khi nào |
|---|---|---|
| **0** | Hệ thống này làm gì — nghiệp vụ, vai trò, ba khái niệm dễ nhầm | Đọc đầu tiên, bắt buộc |
| **1** | Sơ đồ luồng dữ liệu (request, realtime, triển khai, thông báo) | Đọc đầu tiên, bắt buộc |
| **2** | Cấu trúc thư mục + danh sách 13 ADR | Khi cần tìm "code nằm ở đâu" |
| **3** | Cấu hình và môi trường (prod ≠ staging) | Trước khi đụng vào máy chủ |
| **4** | Nền backend — cấu hình, kết nối, danh tính & quyền | Khi gặp lỗi 401/403 |
| **5** | `booking_service.py` — **trái tim của hệ thống** | Khi đụng tới lịch hẹn |
| **6** | Ca trực bác sĩ, sức chứa và điều phối | Khi đụng tới lịch làm việc |
| **7** | Hồ sơ bệnh nhân và chăm sóc khách hàng | Khi đụng tới màn CSKH |
| **8** | Tầng API — bảng tổng mọi endpoint | Tra cứu hằng ngày |
| **9** | Cơ sở dữ liệu — lược đồ, view, trigger, RLS | Trước khi viết migration |
| **10** | Frontend — nền tảng, phiên đăng nhập, tầng BFF | Khi gặp lỗi đăng nhập |
| **11** | Ba màn hình lớn nhất (nơi người dùng ngồi cả ngày) | Khi sửa giao diện |
| **12** | Realtime, thông báo Telegram và vận hành | Khi màn không tự làm tươi |
| **13** | ⚠️ **Những bẫy đã cắn thật** | Đọc trước khi sửa bất cứ gì |
| **14** | Mười câu hay được hỏi — và câu trả lời ngắn | Khi cần giải thích cho người khác |
| **15** | Lộ trình đọc code đề xuất — 7 buổi | Đọc ngay sau phần 0 |

---

## CÁCH ĐỌC TÀI LIỆU NÀY

1. **Đừng đọc một mạch từ đầu tới cuối.** Đọc Phần 0–2 trước để có bản đồ, rồi nhảy tới phần
   tương ứng với việc đang làm.
2. **Phần 13 nên đọc sớm.** Nó là danh sách những sự cố đã xảy ra thật — đọc trước sẽ tránh
   được việc lặp lại.
3. **Ký hiệu dùng trong tài liệu:**
   - `>` khối trích dẫn = ý cốt lõi, đáng nhớ.
   - ⚠️ = bẫy, chỗ dễ hiểu sai, hoặc rủi ro cần biết.
   - `file.py:123` = vị trí chính xác trong mã nguồn, mở thẳng tới đó mà đọc.
4. **Khi tài liệu và code mâu thuẫn nhau, tin code.** Tài liệu được viết theo trạng thái nhánh
   chính tại thời điểm ghi ở cuối file; code thì đi tiếp mỗi ngày.

---
# ClinicAI (Dr4Women) — Giải thích code từ A tới Z

Tài liệu này đi từ **nghiệp vụ → kiến trúc → từng thư mục, từng file, từng dòng quan trọng**.
Đọc theo thứ tự sẽ hiểu được toàn bộ hệ thống đang phục vụ bệnh nhân thật.

Người đọc mục tiêu: **chủ hệ thống** — hiểu phòng khám vận hành thế nào, nhưng không
đọc code hằng ngày. Vì vậy mỗi chỗ đều trả lời **"vì sao"** trước, rồi mới tới "làm gì".

> **Nguồn sự thật khi tài liệu mâu thuẫn nhau:** code + migration đang chạy → `docs/SO-LUAT.md`
> → ADR → tài liệu tổng quan → chat. Trong repo có những tài liệu viết từ tháng 7/2026 còn
> nói "chạy trên Mac mini + Supabase cloud". **Đó là dấu vết lịch sử**, không phải hiện trạng.
> Hiện trạng: chạy trên **VPS Vietnix**, Postgres **tự dựng trên chính máy đó** (từ 07/08/2026).

---

## PHẦN 0. HỆ THỐNG NÀY LÀM GÌ (đọc kỹ trước)

### 0.1. Bài toán nghiệp vụ

**Dr4Women** là phòng khám **sản phụ khoa** tại Kim Ngưu, 12 phòng, một cơ sở đang mở.
Quy mô thật (đo được, `docs/SO-LUAT.md` Phần 1):

| | |
|---|---|
| Lượt khám | ~50–80 bệnh nhân/ngày |
| Người dùng | 40 nhân sự, đỉnh vài chục thao tác/phút |
| Tải đo được | **~1 lượt gọi/giây** |
| Máy chủ | 1 VPS Vietnix · 4 lõi · 8 GB · 50 GB đĩa |
| Đội phát triển | **1 người + AI** |

> **Hai con số ấy quyết định gần hết kiến trúc: 1 lượt gọi/giây và 1 người vận hành.**
> Mỗi thứ thêm vào là một thứ phải sao lưu, canh chừng, vá lỗi, và khôi phục lúc 7h sáng
> khi phòng khám mở cửa. Đây là lý do bạn sẽ thấy hệ thống **cố tình từ chối** những thứ
> "best practice" như Redis, Kafka, microservices — xem `docs/SO-LUAT.md` Phần 7.

ClinicAI **không phải** phần mềm riêng của Dr4Women. Nó là nền tảng **multi-tenant**
(nhiều phòng khám dùng chung một hệ), Dr4Women là phòng khám số 1. Điều đó có hậu quả
kỹ thuật nặng: **27 bảng nghiệp vụ đều mang cột `clinic_id`**, và mọi câu truy vấn đều
phải tự lọc theo nó (ADR-0009).

**Năm dịch vụ khám** — 5 chuyên khoa, mỗi cái một biểu mẫu bệnh án riêng. Chú ý **ba bộ mã
khác nhau** cho cùng một thứ (`supabase/migrations/20260807000007_nam_dich_vu_kham.sql`):

| Mã node | `service_type.code` | Tên hiển thị | Mã biểu mẫu | Ưu tiên |
|---|---|---|---|---|
| `KHAM-PHUKHOA` | `PHU_KHOA` | Phụ khoa | `PK` | P0 |
| `KHAM-SANKHOA` | `SAN_1` | Sản khoa | `SK` | P0 |
| `KHAM-NOITIET` | `NOI_TIET_TINH_DUC` | Nội tiết | `NT` | P0 |
| `KHAM-HIEMMUON-VOSINH` | `HIEM_MUON` | Hiếm muộn / Vô sinh | `HMVS` | P0 |
| `KHAM-NAMKHOA` | `NAM_KHOA` | Nam khoa | `NK` | P1 |

Biểu mẫu nằm ở `src/dashboard/lib/form-schemas/{pk,sk,nt,hmvs,nk}.ts`; danh mục biểu mẫu là
bảng `clinical_form_catalogue` — có trigger bắt buộc mã phiếu **phải tồn tại trong danh mục
của chính phòng khám đó**, không cho gõ bừa.

⚠️ **Bẫy đã cắn một lần:** "Sản 1 / Sản 2 / Sản 3" và "SA1 / SA2 / SA3" **không phải dịch vụ**
— chúng là **tầng/phòng**. Chỉ có đúng 5 dịch vụ = 5 biểu mẫu.

⚠️ **Dịch vụ cũ bị ẩn, KHÔNG xoá** (`is_active = FALSE`). Vì sao: `FREE` còn **29 lịch hẹn**
trỏ vào nó. Xoá là làm hỏng dữ liệu lịch sử.

⚠️ **Một dịch vụ có thể cần HAI phiếu.** `service_type` có cả `form_code` lẫn `form_code_nam`:
khám **tiền hôn nhân** thì nữ dùng `PK`, nam dùng `NK`. Mô hình "một dịch vụ ⇒ một phiếu" là
sai ngay từ đầu. Trước khi có hai cột này, hệ thống **đoán phiếu bằng từ khoá trong tên dịch
vụ** — 8/14 dịch vụ dò ra, **6 cái KHÔNG** (Hồ sơ sinh, Tiền hôn nhân, Tư vấn chuyên sâu,
NPĐH, Thủ thuật, FREE). Bác sĩ mở lượt khám thì **không thấy phiếu nào**, màn hình ẩn hẳn,
**không báo lỗi**.

### 0.2. Ai ngồi ở đâu — bản đồ vai trò

Vai trò không phải nhãn trang trí: nó quyết định **thấy màn hình nào** và **được ghi gì**.
Nguồn: `src/dashboard/lib/roles.ts` (13 mã) + `src/clinicai/api/identity.py`.

| Mã trong code | Nhãn tiếng Việt | Làm gì | Màn hình chính |
|---|---|---|---|
| `RECEPTION` | Lễ tân | Nhập khách, **check-in**, đưa vào hàng chờ | `/home`, `/patients/new`, `/patient-list` |
| `CSKH` | CSKH | Gọi/nhắn khách, đặt–đổi–huỷ lịch, nhắc hẹn, trả kết quả | `/customers`, `/cskh-tasks`, `/nhac-tai-kham` |
| `DOCTOR` / `ULTRASOUND_DOCTOR` | Bác sĩ / Bác sĩ Siêu âm | Khám, **chỉ định**, duyệt & **ký** kết quả | `/tasks`, `/sieu-am`, `/result-review` |
| `TKYK` | Thư ký Y khoa | **Nhập hộ** bệnh án cho bác sĩ (bản nháp) | `/tasks` |
| `NURSE_ULTRASOUND` | Điều dưỡng / Phụ siêu âm | Sinh hiệu, lấy mẫu, thủ thuật, phụ SA | `/lab-queue`, `/service-queue`, `/sono` |
| `CASHIER` · `CASHIER_THUOC` · `CASHIER_DV` | Thu ngân (chung / thuốc / dịch vụ) | Đối soát, thu tiền, đóng lượt | `/cashier/thuoc`, `/cashier/dich-vu` |
| `PHARMACIST` | Dược sĩ | Nhà thuốc: soạn, kiểm, tư vấn, bàn giao thuốc; tồn kho | `/pharmacy`, `/pharmacy/inventory` |
| `TRUONG_CA` | Trưởng ca | Toàn cảnh hàng đợi, gỡ nghẽn, duyệt điều phối | `/truong-ca/*` (5 màn) |
| `MANAGEMENT` | Quản lý | Tài khoản, luật đặt lịch, bảng giá, báo cáo | `/settings`, `/ops`, `/reports` |
| `DISPLAY` | Màn hình phòng chờ | **Không phải người** — cái TV treo tường | `/display` |

⚠️ **Tài liệu `docs/ClinicAI-Tong-Quan-He-Thong.md` §7.1 vẫn ghi "11 mã".** `PHARMACIST` và
`DISPLAY` là hai vai thêm sau. `DISPLAY` có ghi chú thẳng trong `roles.ts`: *backend từ chối
vai này ở **mọi** endpoint trừ bảng gọi số.*

⚠️ **Ma trận màn hình trong tài liệu §7.1 đã lệch nặng so với `NAV_ROLES` hiện tại.** Ba khác
biệt đáng nhớ nhất: `/queue` nay là **`[]`** (tạm ẩn 03/07 — không vai nào thấy, gõ URL bị đá
về `/home`); Trưởng ca bị siết từ **28/36 mục xuống còn 5 màn điều phối** (Quang, 04/08);
CSKH bị gỡ khỏi `/schedule` vì lịch đã nằm sẵn trên trang chủ của họ (09/08). **Đọc `roles.ts`,
đừng đọc bảng trong tài liệu.**

Ba ranh giới quan trọng nhất, đọc kỹ vì vi phạm là sai nghiệp vụ chứ không chỉ sai code:

- **`canWriteClinical` = Bác sĩ + Điều dưỡng + TKYK.** Lễ tân và Quản lý **không** ghi lâm sàng.
- **Chỉ bác sĩ được KÝ.** TKYK gõ hộ được, nhưng chữ ký là của bác sĩ. Sửa sau khi ký =
  **bản mới + lý do**, không đè lên bản cũ (ADR-0008).
- **CSKH không tự phát hành kết quả.** Kết quả chỉ ra khỏi hệ khi bác sĩ chọn `release_now`;
  chọn `sensitive_hold` thì **chặn cứng ở backend, không tự hết hạn**.

> **`departmentToRole` không bao giờ tin vai trò do trình duyệt gửi lên** — vai trò luôn
> được suy ra ở máy chủ từ bảng `staff`. Ẩn nút trên giao diện **không phải** phân quyền.

### 0.3. Vòng đời một khách

```
                      ┌──────────────────────────────────────────────┐
                      │  1. ĐẶT LỊCH            (CSKH / khách tự đặt) │
                      │     → tạo dòng `appointment` SCHEDULED        │
                      └────────────────────┬─────────────────────────┘
                                           │
                      ┌────────────────────▼─────────────────────────┐
                      │  2. GỌI XÁC NHẬN         (CSKH, trước 1–2 ngày)│
                      │     → dòng `tuong_tac_cskh` loai=XAC_NHAN_LICH│
                      │     → appointment.status = CSKH_CONFIRMED      │
                      └────────────────────┬─────────────────────────┘
                                           │  khách nói "không đến"
                                           │  → CANCELLED (giải phóng slot)
                                           │  → tuong_tac loai=HOI_LY_DO_HUY
                      ┌────────────────────▼─────────────────────────┐
                      │  3. CHECK-IN                        (Lễ tân)  │
                      │     appointment → CHECKED_IN                   │
                      │     ★ SINH RA dòng `visit` (OPEN)              │
                      └────────────────────┬─────────────────────────┘
                                           │
                      ┌────────────────────▼─────────────────────────┐
                      │  4. SINH HIỆU                   (Điều dưỡng)  │
                      │     gắn vào `visit`; bất thường → cảnh báo    │
                      └────────────────────┬─────────────────────────┘
                                           │  ← CỔNG CHẶN: bác sĩ chưa
                                           │    khám được cho tới khi
                                           │    điều dưỡng xong
                      ┌────────────────────▼─────────────────────────┐
                      │  5. KHÁM (1 trong 5 chuyên khoa)     (Bác sĩ) │
                      │     visit → IN_PROGRESS                        │
                      │     `clinical_record` + `clinical_form_response`│
                      └────────────────────┬─────────────────────────┘
                                           │
                      ┌────────────────────▼─────────────────────────┐
                      │  6. CHỈ ĐỊNH → THỰC HIỆN → KẾT QUẢ           │
                      │     SA / xét nghiệm / thủ thuật / DXA         │
                      │     `service_log`, `lab_result`,              │
                      │     `ultrasound_record`                       │
                      │     ★ bác sĩ duyệt: release_now | sensitive_hold│
                      └────────────────────┬─────────────────────────┘
                                           │
                      ┌────────────────────▼─────────────────────────┐
                      │  7. ĐƠN THUỐC                (Bác sĩ → Dược) │
                      │     `prescription` → nhà thuốc cấp            │
                      └────────────────────┬─────────────────────────┘
                                           │
                      ┌────────────────────▼─────────────────────────┐
                      │  8. THANH TOÁN + ĐÓNG LƯỢT      (Thu ngân)   │
                      │     `payment`; visit → FINALIZED               │
                      │     ★ CHỈ dịch vụ ĐÃ THỰC HIỆN mới tính tiền  │
                      │     việc phụ còn treo → `follow_up_case`       │
                      └────────────────────┬─────────────────────────┘
                                           │
                      ┌────────────────────▼─────────────────────────┐
                      │  9. NHẮC TÁI KHÁM                    (CSKH)  │
                      │     `nhac_tai_kham` — HAI lượt gọi:           │
                      │       lượt 1: trước hẹn 5–7 ngày → MỜI ĐẶT   │
                      │       lượt 2: sáng ngày hẹn      → NHẮC ĐI    │
                      │     mỗi cuộc gọi = 1 dòng `tuong_tac_cskh`    │
                      └───────────────────────────────────────────────┘
```

Ba chỗ đáng nhìn kỹ trong sơ đồ trên:

**1. Bước 3 là ranh giới sống còn** giữa "lời hứa" và "sự việc". Trước check-in mọi thứ còn
có thể huỷ; sau check-in là hồ sơ y tế, và hồ sơ y tế thì **không xoá được**.

Check-in không phải một câu `UPDATE`. Nó là RPC `check_in_appointment(...)` — `SECURITY DEFINER`,
**chỉ `service_role` gọi được**, bên trong `SELECT … FOR UPDATE` + `pg_advisory_xact_lock`
khoá theo **ngày Việt Nam** để cấp `queue_number` không trùng. Đó là **bậc thang thứ 4** của
nguyên tắc (3) ở mục 0.5: cần nhiều câu lệnh nguyên khối thì mới dùng RPC.

**2. Check-in cũng là lúc hệ thống tự đẻ ra danh sách việc.** Hàm `instantiate_visit_workflow(...)`
**đi ngược danh mục `node_dependency`** để dựng đúng 7 bước xương sống
`LUOTKHAM-01 → 02 → 03 → 05 → 13 → 14 → 15`. Không có danh sách cứng nào trong Python.

⚠️ Node khám (`KHAM-*`) và node dịch vụ (`DICHVU-*`) **cố ý KHÔNG được sinh lúc check-in** —
lý do ghi thẳng trong migration: đóng dấu chúng lúc check-in là *"bịa ra một ý định lâm sàng
mà chưa ai nói ra"*. Bác sĩ quyết định khám gì, chỉ định gì — không phải cái máy.

**3. Bước 5 có một cổng chặn thật.** Bác sĩ không bấm khám được cho tới khi điều dưỡng hoàn
tất sinh hiệu, và màn hình **nói rõ bước nào đang chặn**. Không ai lập trình điều đó vào màn
hình — nó là cổng **FS** (`finish → start`) trong bảng `node_dependency`. Đây chính là điểm
khiến ClinicAI khác một phần mềm phòng khám thường: **luồng khám là dữ liệu, không phải code**
(ADR-0011). Phòng khám mới muốn đổi luồng thì sửa dữ liệu, không sửa code.

Chi tiết nhỏ nhưng quan trọng của cổng: `COMPLETED` **và** `SKIPPED` đều thoả cổng — bỏ qua
là một quyết định tường minh, không được làm kẹt mọi thứ phía sau. Chỉ `CANCELLED` là không thoả.

> **37 node, và nay là 41.** Bốn node nhà thuốc `THUOC-01…04` (soạn thuốc → kiểm trước bàn
> giao → tư vấn dùng thuốc → bàn giao) được thêm cùng vai `PHARMACIST` và khu làm việc
> `khu_nha_thuoc`. Tài liệu §13 vẫn ghi "37" — đó là con số của bản seed gốc.

### 0.4. Ba khái niệm dễ nhầm nhất

Đây là chỗ hiểu sai gây hậu quả đắt nhất. Ba bảng, ba câu hỏi **hoàn toàn khác nhau**.

#### `appointment` — LỜI HỨA

> Một dòng `appointment` trả lời: *"ai định đến, lúc mấy giờ, với bác sĩ nào, khám gì."*
> Nó là một **lời hẹn** — có thể huỷ, có thể dời, có thể không ai đến.

`supabase/migrations/20260714000001_baseline_schema.sql` — cột quan trọng:
`clinic_patient_id`, `doctor_id` (**cho phép NULL**), `service_type_id`,
`slot_start` / `slot_end`, `is_priority_slot`, `is_walkin`, `status`.

Tám trạng thái, và chúng kể đúng câu chuyện ở mục 0.3:
`SCHEDULED` → `CSKH_CONFIRMED` → `CONFIRMED` → `CHECKED_IN` → `COMPLETED`,
rẽ nhánh sang `NO_SHOW`, `CANCELLED`, `DOCTOR_DECLINED`.

⚠️ **Bẫy `doctor_id` NULL.** Sức chứa (`enforce_slot_capacity`) đếm **ghế của MỘT bác sĩ**,
và chỉ kiểm lúc **xếp bác sĩ**. Nên một lịch chưa phân bác sĩ **luôn được nhận**, kể cả khi
mọi bác sĩ đã kín — nó vào hàng chờ xếp. Đây là hành vi **đúng**, nhưng nó khiến hai phép
đo ngây thơ cho kết quả sai: đặt lịch không chọn bác sĩ rồi kết luận "vượt sức chứa", và
đọc `/quote` không kèm `doctor_id` rồi tưởng con số đó là trần của cả phòng khám
(`docs/SO-LUAT.md` Luật 6.5).

#### `visit` — SỰ VIỆC

> Một dòng `visit` trả lời: *"người này đã thật sự tới, và đây là hồ sơ của lần tới đó."*
> Nó **sinh ra lúc check-in**, không sớm hơn.

Cột quan trọng: **`visit_id`** (khoá chính tên là `visit_id`, **không phải `id`** như
`appointment` — chỗ này hay gõ nhầm), `clinic_patient_id`, **`appointment_id` (NULL được)**,
`attending_doctor_id`, `checked_in_at` / `checked_in_by`, `exam_completed_at`,
`finalized_at` / `finalized_by`, `current_node`, `status`.

Trạng thái: `OPEN` → `IN_PROGRESS` → `FINALIZED` → `AMENDED`, cộng **`INCOMPLETE`**.

**Vì sao `appointment_id` được phép NULL:** khách **vãng lai** (walk-in) đi thẳng vào
phòng khám, không hẹn trước. Họ có `visit` mà không có `appointment`. Ngược lại, một
`appointment` bị `NO_SHOW` thì **không bao giờ** sinh ra `visit`.

> **Quan hệ đúng: `appointment` 0..1 ↔ 0..1 `visit`.** Không phải 1-1.
> Đếm doanh thu theo `appointment` là **sai** (đếm cả người không đến).
> Đếm lịch trống theo `visit` cũng **sai** (không thấy người đã hẹn mà chưa đến).

⚠️ **`INCOMPLETE` sinh ra từ một thiệt hại thật.** Khách đang khám thì có việc phải về.
Trước 06/08 hệ thống không có chỗ nào ghi điều đó — cách duy nhất làm được là **huỷ lịch hẹn**,
và khi đó hồ sơ trông như người ấy **chưa từng đến**: mất dấu vết họ đã lấy số, đã đo sinh
hiệu, đã được chỉ định dịch vụ. Đo trên máy chủ ngày 06/08: **35 lượt khám còn `OPEN`/`IN_PROGRESS`,
trong đó 18 lượt check-in từ những ngày trước** — không màn hình nào chạm tới 18 dòng ấy, vì
màn "lượt đang mở" chỉ nhìn trong ngày.

`INCOMPLETE` **không phải trạng thái cuối**: hồ sơ vẫn ghi được và vẫn ký lên `FINALIZED` được.
Hai trạng thái cuối là `FINALIZED` và `AMENDED`.

⚠️ **`FINALIZED` là bất biến.** Hồ sơ đã chốt **không được UPDATE thẳng** — trigger chặn
hoàn toàn. Đính chính chỉ đi qua một cửa duy nhất: RPC `amend_visit(visit_id, reason, changes)`,
trong **một transaction** ghi vết `visit.amended` vào `event_log` (kèm diff trước/sau,
lý do, người ký) *rồi mới* chuyển sang `AMENDED`. Đây là yêu cầu pháp lý TT13, không phải
sở thích kỹ thuật (ADR-0008).

#### `tuong_tac_cskh` — LẦN CHẠM

> Một dòng `tuong_tac_cskh` trả lời: *"CSKH đã chạm tới khách này lần nào, khi nào, kết quả ra sao."*
> Đây là một **cuốn sổ CHỈ THÊM**: gọi bao nhiêu lần thì bấy nhiêu dòng.

`supabase/migrations/20260809000003_so_tuong_tac_cskh.sql`. Cột: `clinic_patient_id`,
`appointment_id` (gắn vào lịch nào, NULL được), `loai`, `kenh`, `ket_qua`,
`khach_xac_nhan`, `noi_dung`, `nhan_vien_staff_id`, `xay_ra_luc`, `trang_thai_ma`.

| Trường | Giá trị hợp lệ |
|---|---|
| `loai` | `XAC_NHAN_LICH` · `NHAC_HEN` · `CHECK_XN` · `TRA_KQ` · `HOI_LY_DO_HUY` · `HOI_THAM` · `KHAC` |
| `kenh` | `GOI` · `ZALO` · `SMS` · `TRUC_TIEP` · `KHONG_LIEN_HE` |
| `ket_qua` | `DA_LIEN_HE` · `CHUA_NGHE_MAY` · `CAN_BAC_SI` · `TU_CHOI` · `BO_QUA` · `KHONG_LIEN_LAC_DUOC` · `HEN_GOI_LAI` |

Ba ràng buộc `CHECK` đáng nhớ, mỗi cái đóng một lỗ hổng ghi sai:

- `(ket_qua = 'BO_QUA') = (kenh = 'KHONG_LIEN_HE')` — *"bỏ qua" và "không liên hệ" là **hai
  nửa của một việc***. Tách ra được thì sẽ có dòng ghi "đã gọi điện" mà kết quả là "bỏ qua".
- `khach_xac_nhan` chỉ có nghĩa với `XAC_NHAN_LICH` và `NHAC_HEN`; mọi loại khác phải NULL.
- Ba loại `XAC_NHAN_LICH` / `NHAC_HEN` / `HOI_LY_DO_HUY` **bắt buộc có `appointment_id`** —
  chúng luôn nói về **một lịch cụ thể**. Thiếu cột này thì không phân biệt được đã gọi cho
  lịch tuần trước hay lịch tuần sau.

**`nhan_vien_staff_id` LẤY TỪ PHIÊN ĐĂNG NHẬP, KHÔNG NHẬN TỪ CLIENT.** Và bảng chỉ cấp
`GRANT SELECT` cho trình duyệt — ghi phải đi qua FastAPI. *Vì sao:* client tự ghi được nghĩa
là client tự khai được "đã gọi rồi" cho một cuộc gọi **chưa hề xảy ra**.

⚠️ **`loai` không phải trạng thái — đó là bài học phải sửa bằng một cột mới.** Ban đầu
`loai='KHAC'` gánh cả ba việc khác nhau ("chờ phản hồi chuyên môn", "đã trả kết quả",
"không cần theo dõi nữa"). Hậu quả: bấm "Đã hỏi bác sĩ" thì mốc "Đã trả kết quả" **cũng tích
xanh theo**. Cột `trang_thai_ma` sinh ra để tách hai khái niệm; dòng thời gian đọc cột này,
**không đọc `loai`**.

**Vì sao phải đẻ bảng này thay vì dùng ba bảng đã có** (chép nguyên lý do trong migration):

- `cskh_action` là hàng nhập khẩu từ Notion — người ghi là một **chuỗi tên gõ tay**.
  Không giao việc được, không lọc theo người được. *("Những cuộc gọi của chị Điều" là câu
  không trả lời được.)*
- `cskh_log` là bản chụp một tháng từ file cũ: **mỗi bệnh nhân một dòng**, không phải một
  dòng cho mỗi lần gọi.
- `nhac_tai_kham` là **VIỆC** mời tái khám, mỗi việc chứa đúng **MỘT** cuộc gọi. Gọi lần
  hai là ghi đè lần một.

⚠️ **Cái nút đã lừa mọi người suốt nhiều tháng:** nút "📞 Gọi nhắc hẹn" từng chỉ là một thẻ
`<a href="tel:…">`. Nó quay số, và **không để lại gì**. Gọi xong không ai biết đã gọi;
gọi lần hai không ai biết là lần hai. Ba cột "Tương tác gần nhất / Bước tiếp theo / Hạn xử lý"
hiển thị "—" cho mọi khách — và không phải vì chưa ai gọi.

#### Ba câu hỏi, ba bảng — bảng đối chiếu

| Câu hỏi | Đọc bảng | KHÔNG đọc bảng |
|---|---|---|
| Hôm nay có bao nhiêu người **hẹn**? | `appointment` | `visit` |
| Hôm nay có bao nhiêu người **thật sự khám**? | `visit` | `appointment` |
| Lịch này **đã gọi xác nhận chưa**? | `tuong_tac_cskh` (vắng dòng = chưa gọi) | `appointment.confirmed_at` |
| Tỷ lệ **không đến** (no-show)? | `appointment.status='NO_SHOW'` | — |
| Doanh thu? | `payment` gắn `visit` | `appointment` |
| Việc CSKH **hôm nay phải làm**? | view `v_trang_thai_cskh` | `cskh_action` (rỗng) |

**Số nhiều nằm ở đâu:**

```
patient  1 ── N  appointment          một người, nhiều lần hẹn
patient  1 ── N  visit                một người, nhiều lượt khám
patient  1 ── N  tuong_tac_cskh       một người, rất nhiều lần chạm

appointment 0..1 ── 0..1 visit        ★ KHÔNG PHẢI 1-1
     · walk-in         → visit KHÔNG có appointment
     · no-show / huỷ   → appointment KHÔNG có visit

appointment 1 ── N tuong_tac_cskh     ★ gọi 3 lần = 3 dòng
visit       1 ── N payment            thu nhiều lần cho một lượt
visit       1 ── N work_item          các đầu việc của lượt đó
```

⚠️ **Bẫy cuối, và nó đã hiện sai trên màn hình thật.** Anh Cường có 3 lịch hẹn. Màn hình đang
mở lượt **tái khám** của anh, nhưng cột trạng thái lại nhận `DA_CHECKIN` của một lượt **khác** —
vì view trạng thái trả về **một dòng cho một KHÁCH**, không phải một dòng cho một LƯỢT. Kết quả:
mốc "Đã check-in" sáng chữ *"đang ở đây"* trên một lượt khách **chưa từng đến**.

> **Trạng thái phải nói về LƯỢT đang xem (`appointment_id`), không phải về cả con người.**

> **Một câu để nhớ:** `appointment` là **lời hứa**, `visit` là **sự việc**,
> `tuong_tac_cskh` là **lần chạm**. Ba thứ ấy có thể lệch nhau, và **chính chỗ lệch đó
> mới là thông tin vận hành đáng giá nhất**.

#### Còn hai họ hàng nữa, để khỏi nhầm tiếp

| Bảng | Là gì | Khác `tuong_tac_cskh` ở chỗ |
|---|---|---|
| `nhac_tai_kham` | **VIỆC PHẢI LÀM** — mời một người quay lại | Là *việc*, không phải *sự việc*. Mỗi việc chứa đúng **một** cuộc gọi |
| `v_trang_thai_cskh` | **TRẠNG THÁI SUY RA** — một VIEW, không lưu gì | Tính lại mỗi lần đọc, theo bảng luật `luat_cskh` (11 loại việc, ngưỡng ngày cấu hình được) |

**Vì sao trạng thái CSKH là VIEW chứ không phải bảng việc sinh sẵn:** dự án **không có bộ hẹn
giờ** (không apscheduler, không cron). Một bảng việc mà không có cron thì việc chỉ ra đời khi
có người mở màn — và từ giây đó nó là **bản sao của sự thật, tự do lệch**.

Trong 11 loại việc, `DA_CHECKIN` được cho **ưu tiên 0 — cao hơn mọi việc khác**, vì:
*khách có mặt tại chỗ là sự thật gấp nhất về người đó; mọi cuộc gọi đều đợi được, còn người
đang đứng đấy thì không.*

### 0.5. Nguyên tắc kiến trúc chốt hạ

Bốn điều dưới đây không phải gu thẩm mỹ. Mỗi điều đều có một lần hỏng thật đứng sau nó.

**(1) Frontend chỉ là giao diện. Mọi *quyết định* nằm ở FastAPI hoặc SQL.**

Nhưng đây là luật **hay bị hiểu sai nhất** — không phải "mọi thứ ở backend":

| Loại logic | Ví dụ | Ở đâu |
|---|---|---|
| **Quyết định** | còn chỗ không · vai này đặt lịch được không · giá bao nhiêu · ai mở được bệnh án | **Backend + database. Không ngoại lệ.** |
| **Kiểm cho mượt tay** | ngày kín thì mờ nút · nhập sai định dạng báo đỏ ngay | **Cả hai nơi.** Frontend báo sớm, backend vẫn kiểm lại từ đầu |
| **Trình bày** | sắp xếp · gộp nhóm · định dạng ngày · ẩn hiện cột | **Frontend.** Đúng việc của nó |
| **Nhớ tạm dữ liệu ít đổi** | 5 dịch vụ · danh sách bác sĩ · bảng giá | **Frontend**, tải một lần mỗi phiên |

*Vì sao:* trình duyệt sửa được, nên không bao giờ tin. Và kiểm ở frontend là **đếm rồi mới
quyết định** — giữa lúc đếm và lúc quyết định thì người thứ hai chen vào được.

Frontend chỉ nói chuyện thẳng với Supabase cho đúng **hai** việc: **đăng nhập** và
**tin thời gian thực**. Mọi đọc/ghi nghiệp vụ đi qua FastAPI (ADR-0012).

⚠️ *Hiện trạng:* `docs/SO-LUAT.md` (13/08) ghi **42/63 route giao diện còn chạm thẳng
database**, có ràng buộc "chỉ được phép giảm". `src/dashboard/lib/backend-proxy.ts` lại
ghi "cutover đã xong, mọi route nghiệp vụ proxy vô điều kiện". **Chưa rõ con số hiện tại
— cần kiểm** bằng cách đếm lại lời gọi Supabase trực tiếp trong `src/dashboard/app/api/`.

**(2) Modular monolith, không microservices.**

Một FastAPI + một Postgres. Module = thư mục, ranh giới ép bằng CI chứ không bằng hạ tầng.
*Vì sao:* ở **1 lượt gọi/giây** và **1 người vận hành**, microservices mua ranh giới cứng
bằng cái giá ops gấp 10 lần, cộng saga/2PC cho một luồng khám vốn dĩ là **một transaction**.
Lối thoát vẫn để mở: nếu có bằng chứng (>500 BN/ngày, đa cơ sở) thì tách theo đúng ranh
giới đã khai (ADR-0001).

⚠️ ADR-0001 đo trên code 13/08/2026: **CHƯA thi hành** — chưa có thư mục `modules/`,
chưa có manifest, `services/` vẫn phẳng 65 file. **Đọc ADR đừng tưởng ranh giới đã có
người canh.**

**(3) Mọi bất biến có kẽ hở tranh chấp phải ép ở Postgres.**

Theo bậc thang: ràng buộc `UNIQUE`/`CHECK` → `UPDATE … WHERE status IN (…)` một câu →
trigger + khoá tư vấn (`pg_advisory_xact_lock`) → hàm RPC khi cần nhiều câu lệnh nguyên khối.
**Không tự cài khoá trong Python.**

*Vì sao:* khoá trong Python chỉ đúng trong **một** tiến trình. Database thì đúng dưới mọi
client — Next, FastAPI, hay một người gõ `psql` lúc 2h sáng. Hai race đã gặp thật: đặt trùng
slot 2+1, và trùng số thứ tự (ADR-0003).

**(4) Một nhánh dài hạn duy nhất: `main`.**

Nhánh việc → PR → `main` → xoá nhánh. Nhánh sống tối đa **2 ngày** (đây là luật về *kích
thước một lần làm*, không phải về thời gian).

*Vì sao — đã hỏng hai lần:* lần đầu `main` tụt **63 commit** sau `staging` và không ai biết;
toàn bộ nền multi-tenant chỉ sống trên `staging`. Lần hai (02–13/08) một nhánh `codex/…`
sống 11 ngày, đi trước `main` **204 commit** và đi sau **122** — và **79 commit của prod
chỉ nằm trên ổ đĩa VPS**, không có bản sao ở đâu cả.

> **Luật 11.2 — Code đang chạy phải có bản sao ngoài máy chạy nó.** Ổ đĩa hỏng là không
> dựng lại được thứ đang phục vụ bệnh nhân.

---

## PHẦN 1. SƠ ĐỒ LUỒNG DỮ LIỆU

### 1.1. Một request: từ trình duyệt tới database và ngược lại

```
  TRÌNH DUYỆT (nhân viên phòng khám)
        │  GET /appointments  ·  cookie phiên `clinicai-auth`
        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ CADDY  (cổng 80/443 — thứ DUY NHẤT mở ra ngoài)                │
  │  caddy/Caddyfile                                                │
  │   · gắn header bảo mật (HSTS, nosniff, DENY khung, …)          │
  │   · /health              → trả "ok" ngay, không đi đâu cả       │
  │   · /auth/v1/token*      → auth_guard  (canh đăng nhập)        │
  │   · /auth|rest|realtime/v1/* → cổng Supabase tự dựng           │
  │   · còn lại              → dashboard:3000                       │
  └───────────────────────────────┬─────────────────────────────────┘
                                  ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ DASHBOARD — Next.js  (container `dashboard`, cổng 3000)         │
  │  KHÔNG mở cổng ra host. Chỉ Caddy gọi tới được.                │
  │                                                                 │
  │  proxy.ts        → làm mới token, đặt lại cookie                │
  │  app/(dashboard) → server component dựng HTML                   │
  │  app/api/*/route.ts (64 route) → chuyển tiếp sang FastAPI       │
  │       lib/backend-proxy.ts đính kèm HAI thứ:                    │
  │         Authorization: Bearer <token của chính người dùng>       │
  │         X-API-Key:     <BACKEND_API_KEY>                        │
  └───────────────────────────────┬─────────────────────────────────┘
                                  ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ API — FastAPI  (container `api`, cổng 8000, KHÔNG mở ra host)   │
  │                                                                 │
  │  ① api/auth.py        X-API-Key. Thiếu khoá ở production →     │
  │                        KHÔNG CHO KHỞI ĐỘNG (fail-closed)        │
  │  ② api/identity.py    JWT → staff.auth_user_id → vai + clinic_id│
  │                        Vai LUÔN suy ở máy chủ, không nhận từ client│
  │  ③ api/idempotency.py Bấm hai lần = một hành động               │
  │  ④ api/rate_limit.py  Chặn gọi dồn (đếm trong RAM 1 tiến trình) │
  │  ⑤ api/v1/routers/*   Router MỎNG — chỉ nhận, gọi, trả          │
  │  ⑥ services/*.py      65 file: TOÀN BỘ luật nghiệp vụ           │
  └───────────────────────────────┬─────────────────────────────────┘
                                  │  asyncpg — mọi câu SQL tự lọc clinic_id
                                  ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ POSTGRES 17  (tự dựng trên chính VPS)                           │
  │  117 migration · trigger · advisory lock · RPC                  │
  │  ⚠️ Backend nối bằng CHỦ database → RLS KHÔNG bảo vệ backend.   │
  │     Chốt chặn thật là mệnh đề WHERE của chính câu lệnh, và một  │
  │     cổng CI (`tenant-scope-audit.py`, ngưỡng 0) canh việc đó.   │
  └─────────────────────────────────────────────────────────────────┘

  ĐI VỀ: JSON ngược đúng đường trên. Với server component thì Next dựng
  sẵn HTML rồi mới trả — trình duyệt nhận trang đã có dữ liệu.
```

**Giá của mỗi chặng** (đo trên staging 13/08/2026, 60 lượt):

| | p50 | p95 |
|---|---|---|
| Một lượt gọi backend, **không** chạm database | 4,13 ms | 6,81 ms |
| Một lượt gọi backend, **có** chạm database | 4,94 ms | 7,64 ms |

> **Một truy vấn tốn ~0,8 ms. Một lượt đi hỏi tốn ~4 ms. Đi hỏi đắt gấp năm lần việc trả lời.**
> Đó là lý do **Luật 5.1 — một màn hình, một lượt gọi**: backend viết riêng cho từng màn,
> gộp mọi thứ màn đó cần vào **một** câu SQL. *(Trang chủ hiện vẫn 11 truy vấn mỗi lần dựng
> lại — đó là phần lớn cảm giác chậm.)*

⚠️ Và đây là lý do **Luật 3.2**: một route frontend hoặc chỉ chuyển tiếp, hoặc biến mất.
Vừa chuyển tiếp vừa tự truy vấn thì đường đi thành **hai lượt HTTP** thay vì một.

### 1.2. Luồng realtime — vì sao màn hình tự tươi

Bài toán: CSKH A đang giữ một khung giờ, CSKH B phải thấy ngay, **không phải bấm F5**.

```
  ai đó GHI vào database
   (đặt lịch, giữ chỗ, xong sinh hiệu, …)
        │
        ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ TRIGGER `notify_row_change()` — AFTER INSERT/UPDATE/DELETE    │
  │ supabase/migrations/20260806000001_notify_change_for_live…    │
  │                                                              │
  │   pg_notify('clinicai_changes', {"t":"appointment","c":<uuid>})│
  │                                                              │
  │ ⚠️ Payload CỐ TÌNH NGHÈO — chỉ tên bảng + clinic_id.         │
  │    Hai lý do: NOTIFY chặn ở 8000 byte (vượt là HỎNG CẢ        │
  │    TRANSACTION ĐANG GHI), và nhét dữ liệu hàng vào đây là đi  │
  │    vòng qua lớp phân quyền của API.                           │
  │                                                              │
  │ Gắn trên 17 bảng: appointment, visit, work_item, payment,     │
  │ lab_result, service_log, prescription, work_roster,           │
  │ tuong_tac_cskh, slot_hold, hen_goi_lai, event_log (CHỈ INSERT)│
  └───────────────────────────┬──────────────────────────────────┘
                              ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ ChangeBroker — src/clinicai/core/change_broker.py             │
  │  · một kết nối asyncpg RIÊNG (không lấy từ pool)             │
  │  · LISTEN clinicai_changes; rớt thì nối lại sau 3 giây        │
  │  · chia tin vào hàng đợi từng người xem (8 chỗ, đầy thì bỏ)   │
  │  · khởi động/tắt trong main.py (lifespan)                     │
  └───────────────────────────┬──────────────────────────────────┘
                              ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ SSE — GET /api/v1/events/stream                               │
  │  src/clinicai/api/v1/routers/events.py                        │
  │  · text/event-stream, X-Accel-Buffering: no                   │
  │  · ★ LỌC THEO clinic_id LẤY TỪ TOKEN, không lấy từ trình duyệt│
  │  · nhịp tim `: nhip` mỗi 20 giây để đường không bị cắt        │
  └───────────────────────────┬──────────────────────────────────┘
                              ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ Proxy Next — app/api/events/stream/route.ts                   │
  │  Tồn tại vì EventSource của trình duyệt KHÔNG gắn header được.│
  │  Next gắn hộ Bearer token + X-API-Key rồi nối ống thẳng qua.  │
  └───────────────────────────┬──────────────────────────────────┘
                              ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ TRÌNH DUYỆT — hai người nghe, độc lập nhau                    │
  │  · RealtimeRefresher.tsx (gắn 1 lần cho cả layout)            │
  │      lọc theo tên bảng → gộp 250ms → router.refresh()         │
  │      lưới an toàn: tự làm mới mỗi 60 giây                     │
  │  · BookingHub.tsx mở ống RIÊNG, chỉ nghe `slot_hold`,         │
  │      nạp lại đúng phần giữ chỗ — vì dựng lại cả cây server    │
  │      component cho 8 CSKH cùng lúc là quá đắt. Lưới: 5 giây.  │
  └──────────────────────────────────────────────────────────────┘
```

**Độ trễ thật người dùng cảm nhận** (đo 14/08/2026, ba tài khoản CSKH thật):

| chặng | thời gian |
|---|---|
| máy chủ ghi xong → máy bên kia **đọc được** | **27–40 ms** |
| nhịp màn hình bên kia hỏi lại | 0–5 s |
| **người bên cạnh thực sự thấy** | ~2,5 s trung bình, ~5,4 s chậm nhất |

> **Máy chủ chiếm dưới 1% con số ấy.** Độ trễ người dùng cảm nhận là **nhịp hỏi**, không
> phải máy chủ. Đây là lý do tối ưu SQL ở đây sẽ không ai thấy khác gì.

⚠️ Luật 6.3 mới xong **nửa đầu**: database đã bắn tin, backend đã đẩy về — nhưng màn hình
vẫn **dựng lại cả trang** mỗi lần có tin, thay vì chỉ phần bị ảnh hưởng. Xong nửa sau thì
bỏ được hẳn nhịp hỏi lại.

### 1.3. Luồng triển khai — từ máy Quang tới khách

```
1. Viết code ở nhánh riêng, tên tiếng Việt nói ra việc
   (bat-sentry, bang-gia-qua-api, fix-gach-ngang)
        │
2. Mở PR vào `main` → CI chạy 5 CHẶNG SONG SONG → đỏ thì KHÔNG GỘP ĐƯỢC
   ┌─────────────────┬────────────────────────────────────────────────┐
   │ backend         │ ruff check · ruff format --check · mypy ·      │
   │                 │ tenant-scope-audit (ngưỡng 0) ·                 │
   │                 │ pytest (cov ≥ 80%)                              │
   ├─────────────────┼────────────────────────────────────────────────┤
   │ frontend        │ tsc --noEmit · eslint (0 cảnh báo) ·            │
   │                 │ bộ test ranh giới an toàn · next build         │
   ├─────────────────┼────────────────────────────────────────────────┤
   │ infra-safety    │ scripts/tests/test-infra-safety.sh             │
   ├─────────────────┼────────────────────────────────────────────────┤
   │ portability     │ ✗ đường dẫn /Users/ hay /home/<ai> trong config │
   │  (ADR-0013)     │ docker compose config với CẢ .env.prod.example  │
   │                 │   lẫn .env.staging.example                      │
   │                 │ build ảnh linux/amd64 · khẳng định kiến trúc    │
   │                 │ dựng thật api + dashboard → /health, /health/db │
   ├─────────────────┼────────────────────────────────────────────────┤
   │ database        │ chặn cú pháp chỉ psql hiểu (\restrict, FROM stdin)│
   │                 │ áp TOÀN BỘ migration theo thứ tự trên PG 17     │
   │                 │ ÁP LẠI LẦN HAI (kiểm tính chạy-lại-được)       │
   │                 │ chạy ~24 bộ khẳng định supabase/tests/*.sql     │
   └─────────────────┴────────────────────────────────────────────────┘
        │
3. Gộp vào `main` → CI dựng ĐÚNG MỘT ảnh Docker (amd64), dán nhãn bằng mã commit
        │
4. Đẩy tag `staging-<ngày><chữ>` → CD chạy TỰ ĐỘNG → staging cổng 8080
   (CD tự kiểm "ref có xê dịch chưa" trước khi deploy, để không lùi bản trong im lặng)
        │
5. Vào xem thật. Ưng → bấm nút "đưa lên prod" trên GitHub (workflow_dispatch)
        │
6. ⏰ CHỈ CHẠY TRONG 1h–4h SÁNG giờ Việt Nam. Ngoài khung thì bị từ chối,
   trừ khi điền `ly_do_vuot_khung_gio` — và lý do ấy được GHI VÀO LOG lần chạy.
        │
7. scripts/deploy-backend.sh — 6 bước:
   [1] kiểm nguồn: đúng SHA? đúng ref? (prod=main, staging=tag) · khoá máy
   [2] CHỤP ẢNH CŨ: lưu image id + thư mục bản trước vào .active-state-<env>
   [3] build   [4] compose up (lỗi thì KHÔNG thoát — để bước 6 còn chạy)
   [5] chờ khoẻ ~120 giây
   [6] không khoẻ → DÁN LẠI NHÃN ảnh cũ, quay về thư mục cũ, up lại, exit 1
        │
   ✅ khoẻ → ghi .active-state mới (ghi file tạm rồi mv — nguyên tử)
```

Ba điều đáng nhớ về luồng này:

- **Luật 2.4 — Lùi bản là trỏ lại ảnh cũ, không phải dựng lại code cũ.** Dựng lại thì ảnh
  nền có thể đã đổi giữa hai lần.
- **Migration KHÔNG chạy trong lúc deploy.** Script chỉ *cảnh báo* nếu database tụt sau
  file. Đổi lược đồ là một bước riêng, có người xem (`supabase db push`).
- ⚠️ **Bẫy giờ:** máy chủ chạy giờ quốc tế; "1h sáng" của nó là **8h sáng** của mình —
  đúng giờ đông khách nhất. Giờ vì thế bị ghim `Asia/Ho_Chi_Minh` trong chính workflow.

⚠️ **Hiện trạng CD:** file `cd.yml` đã viết đúng, nhưng đang `disabled_manually` **vì chưa
đăng ký runner** trên VPS (`docs/DANG-LAM.md`). Deploy thật hiện làm tay qua SSH.
Đây **không phải bug**.

### 1.4. Luồng thông báo Telegram

Kênh báo cho **nhân viên nội bộ** (không phải bệnh nhân — bệnh nhân chỉ nhận qua Zalo OA).

```
  Service ghi một dòng vào `event_log`
   (booking_service.py → appointment.created, config_service.py → roster.…)
   ★ GHI VÀO CÙNG TRANSACTION với dữ liệu nó mô tả — hoặc cả hai cùng vào,
     hoặc không cái nào. Đây là Luật 8.1, và là lý do KHÔNG đẩy audit qua hàng chờ.
        │
        ▼
  TRIGGER `trg_notify_event_log` — AFTER INSERT ON event_log ⚠️ CHỈ INSERT
        │   pg_notify('clinicai_changes', {"t":"event_log", "c":<clinic>})
        │
        │   ⚠️ VÌ SAO CHỈ INSERT: relay gửi xong sẽ `UPDATE event_log SET
        │      event_published = TRUE`. Nghe cả UPDATE thì relay TỰ ĐÁNH THỨC
        │      CHÍNH NÓ, mãi mãi. Đây là chỗ mong manh nhất của thiết kế.
        ▼
  notification-relay  (cùng ảnh với api, chạy `python -m clinicai.worker --relay`)
   · LISTEN cùng kênh, bằng một kết nối giữ ngoài pool
   · thức dậy → ngủ gộp 300 ms → quét
   · ⚠️ 30 giây KHÔNG phải đường chính — nó là lưới đỡ khi LISTEN rớt
        │
        ▼
  poll_and_deliver()  — services/notification_relay.py
   · SELECT … WHERE clinic_id=$1 AND event_published=FALSE ORDER BY occurred_at LIMIT 50
   · mỗi dòng: pg_try_advisory_lock → kiểm lại chưa gửi → làm giàu nội dung
   · _lam_giau(): nối sang appointment/patient/staff/service_type lấy TÊN và GIỜ
     ★ KHÔNG BAO GIỜ lấy số điện thoại (Luật 8.2 — trong vết chỉ có mã số)
   · gửi, tối đa 3 lần, giãn 0,5s → 1,0s → đánh dấu đã gửi → mở khoá
        │
        ▼
  providers/telegram.py → POST api.telegram.org/bot<token>/sendMessage
   · `TELEGRAM_CHAT_ID` là DANH SÁCH ngăn bởi dấu phẩy — gửi lần lượt từng kênh
   · "ok" nghĩa là MỌI kênh nhận được; một kênh hỏng thì để nguyên chưa-gửi
     → chấp nhận thỉnh thoảng trùng tin, hơn là một kênh im lặng
   · thiếu token/chat_id → bỏ qua có ghi nhận, KHÔNG thử lại trong vòng đó
        │
        ▼
  Kênh Telegram "Theo dõi Clinic" (bot @chat_Tuyen_bot):
   một tin nhắn riêng + một nhóm
```

⚠️ **Chỉ 5 loại sự kiện thật sự sinh tin nhắn** (`notification_templates.py`):
`roster.shift_added_cho_xep`, `appointment.created`, `appointment.cancelled`,
`appointment.rescheduled`, `appointment.doctor_removed`. Loại khác được đánh dấu "đã gửi"
mà không gửi gì — cố ý, để hàng chờ không nghẽn vì một mẫu tin còn thiếu.

⚠️ **Trước khi bật lần đầu phải chạy** `scripts/danh-dau-event-cu-truoc-khi-bat-telegram.sql`
(đánh dấu toàn bộ sự kiện cũ là đã gửi). Không làm thì ~1.164 dòng tồn đọng đổ ập vào kênh.

Chiều ngược lại: `services/telegram_bot.py` chạy cùng tiến trình relay, nhận ba lệnh
`/trangthai`, `/homnay`, `/giupdo`. **Chỉ trả lời các chat ID đã khai**, và `/homnay` chỉ
trả về **con số**, không tên, không số điện thoại.

---

## PHẦN 2. CẤU TRÚC THƯ MỤC

### 2.1. Cây thư mục có chú thích

```
.
├── CLAUDE.md              ★ ĐỌC ĐẦU TIÊN — kiến trúc + luật, bản rút gọn
├── docs/SO-LUAT.md        ★ SỔ LUẬT — mọi luật của hệ thống, kèm ngưỡng để lật lại
├── README.md              Chạy thử trong 1 lệnh + tài khoản mẫu
├── DESIGN.md              "Hiến pháp giao diện" — thang kích thước/màu/bo góc (15/08)
├── AGENTS.md · HANDOFF.md · CHANGELOG.md
│
├── docker-compose.yml           10 service của ứng dụng (xem Phần 3)
├── docker-compose.supabase.yml  Supabase TỰ DỰNG: db · auth · rest · realtime · gateway
├── Dockerfile.api               ảnh backend (dùng chung cho api/worker/relay)
├── pyproject.toml · poetry.lock · pytest.ini · .ruff.toml
├── .env.example · .env.prod.example · .env.staging.example   ← chỉ TÊN biến, không bí mật
│
├── caddy/Caddyfile        Cửa vào duy nhất: TLS, header bảo mật, chia đường
├── docker/                Caddyfile của cổng Supabase · init DB · cấu hình RabbitMQ · plist
│
├── src/
│  ├── clinicai/           ← BACKEND FastAPI. MỌI LUẬT NGHIỆP VỤ Ở ĐÂY
│  │  ├── main.py             dựng app, gắn router, bật/tắt ChangeBroker
│  │  ├── worker.py           chạy nền: --relay (Telegram) · --pos-relay
│  │  ├── api/
│  │  │  ├── auth.py          LỚP 1 — X-API-Key, thiếu là không cho khởi động
│  │  │  ├── identity.py      LỚP 2 — JWT → staff → vai + clinic_id
│  │  │  ├── idempotency.py   bấm hai lần = một hành động
│  │  │  ├── rate_limit.py · middleware.py · runaway_guard.py
│  │  │  └── v1/routers/      34 router MỎNG (booking, cashier, lab, pharmacy, …)
│  │  ├── services/        ★ 65 file — TRÁI TIM. Python thuần, test được
│  │  ├── core/               clock (ghim Asia/Ho_Chi_Minh) · change_broker ·
│  │  │                       database · logging · telemetry · sentry · phone
│  │  ├── graphs/ · orchestrator/ · llm/ · tools/   AI (LangGraph + Anthropic API)
│  │  ├── adapters/ · ports/  cổng tích hợp ngoài (KiotViet — mặc định RỖNG)
│  │  ├── schemas/            kiểu dữ liệu vào/ra (Pydantic)
│  │  ├── voice/              nhận dạng giọng nói (ngoại lệ on-prem duy nhất)
│  │  └── event_bus/ · golden_record/   ⚠️ DI SẢN — ADR-0002 nói xoá, chưa xoá
│  │
│  ├── dashboard/          ← FRONTEND Next.js. CHỈ GIAO DIỆN
│  │  ├── proxy.ts            làm mới token, đặt lại cookie cho MỌI request
│  │  ├── app/(dashboard)/    29 màn: home · tasks · customers · cashier ·
│  │  │                       pharmacy · sieu-am · truong-ca · reports · settings …
│  │  ├── app/api/            64 route handler → chuyển tiếp sang FastAPI
│  │  ├── app/display/        màn hình TV phòng chờ (vai DISPLAY)
│  │  ├── lib/             ★ roles.ts (phân quyền) · backend-proxy.ts ·
│  │  │                       supabase-cookie.ts · datetime.ts · form-schemas/
│  │  ├── components/ · types/ · tests/ · e2e/
│  │  └── Dockerfile.dashboard · next.config.ts
│  │
│  └── tests/              pytest — api · core · services · graphs · migrations · integration
│
├── supabase/
│  ├── migrations/         ★ 117 file .sql — NGUỒN SỰ THẬT DUY NHẤT của lược đồ
│  ├── tests/              ~24 bộ khẳng định SQL (RLS, multi-tenant, kernel, payment)
│  ├── fixtures/           dữ liệu mẫu: roster, tài khoản, một ngày khám demo
│  └── hotfix/             vá khẩn cấp cho prod (đọc kỹ trước khi dùng)
│
├── scripts/                 ~45 script vận hành
│  ├── deploy-backend.sh   ★ deploy 6 bước + tự lùi bản
│  ├── dev-up.sh              dựng cả stack ở máy mình rồi tự kiểm
│  ├── backup-db.sh · restore-db.sh · restore-drill.sh · verify-backup.sh
│  ├── tests/              ★ tenant-scope-audit.py (cổng CI ngưỡng 0) ·
│  │                          test-infra-safety.sh · e2e-*.sh · do-*.py (đo độ trễ)
│  └── systemd/ · launchdaemons/ · scheduler/ · maintenance/
│
├── monitoring/monitors.json  cấu hình Uptime Kuma dạng file (gắn read-only vào container)
├── docs/
│  ├── SO-LUAT.md · DANG-LAM.md · spec-clinic.md · OPS-RUNBOOK.md
│  ├── ClinicAI-Tong-Quan-He-Thong.md   tổng quan theo vai (⚠️ có phần đã cũ)
│  ├── adr/                ★ 13 quyết định kiến trúc — xem 2.3
│  ├── database/ERD.md · design/ · forms/
├── context/                 trạng thái đang làm giữa các phiên
├── final_canon/             12 tài liệu thiết kế gốc (nhiều chỗ đã bị ADR thay)
└── .github/workflows/       ci.yml (5 job) · cd.yml
```

### 2.2. Khi nào bạn cần mở thư mục nào

| Thư mục | Vai trò | Khi nào bạn cần mở nó |
|---|---|---|
| `docs/SO-LUAT.md` | Sổ luật — mọi luật + ngưỡng lật lại | **Trước mọi việc.** Đặc biệt khi định thêm hạ tầng mới |
| `docs/adr/` | 13 quyết định kiến trúc, có bối cảnh | Khi hỏi "vì sao lại làm thế này?" |
| `docs/DANG-LAM.md` | Trạng thái giữa các phiên | Bắt đầu một phiên làm việc |
| `src/clinicai/services/` | **Luật nghiệp vụ.** 65 file Python thuần | Đổi cách hệ thống *quyết định* điều gì |
| `src/clinicai/api/v1/routers/` | Router mỏng: nhận, gọi, trả | Thêm/đổi một đường API |
| `src/clinicai/api/identity.py` | Suy vai + `clinic_id` từ token | Ai đó "vào được màn mà bị 403" |
| `src/clinicai/core/` | Đồng hồ, kết nối, log, realtime | Lỗi múi giờ, mất tin realtime, thiếu log |
| `src/dashboard/lib/roles.ts` | Ma trận vai ↔ màn hình | Một vai không thấy màn hình đáng ra phải thấy |
| `src/dashboard/app/(dashboard)/` | 29 màn hình | Sửa hiển thị — **không** sửa luật ở đây |
| `src/dashboard/app/api/` | 64 route chuyển tiếp | Nối một màn mới vào backend |
| `src/dashboard/lib/form-schemas/` | Cấu trúc 5 biểu mẫu khám | Thêm/bớt trường trong bệnh án một chuyên khoa |
| `supabase/migrations/` | **Nguồn sự thật của lược đồ** | Mọi thay đổi database. **Không bao giờ sửa tay trên giao diện** |
| `supabase/tests/` | Khẳng định SQL chạy trong CI | Thêm một bất biến phải được database canh |
| `scripts/tests/` | Cổng CI + kịch bản đo | Thêm một luật muốn "có người canh" |
| `scripts/` | Deploy, backup, khôi phục | Vận hành máy chủ |
| `caddy/` + `docker-compose*.yml` | Hình dạng hạ tầng | Đổi cổng, thêm service, đổi giới hạn RAM |
| `.github/workflows/` | CI 5 job + CD | Thêm một cổng chặn hoặc đổi cách deploy |
| `final_canon/` | Thiết kế gốc | ⚠️ Đọc **cùng** ADR — nhiều chỗ đã bị ADR thay thế |

### 2.3. Mười ba ADR — quyết định gì, vì sao

> ADR = **Architecture Decision Record**, một trang ghi lại: bối cảnh, quyết định, các
> phương án đã cân nhắc, và hậu quả. Giá trị của nó là **"đã cân nhắc và loại rồi"** — để
> người sau không đề xuất lại từ best-practice chung.
>
> ⚠️ **"Đã quyết" và "đã làm" là hai chuyện.** Mỗi ADR có ô *Thi hành* ghi trạng thái đo
> trên code. Đọc ADR đừng tưởng luật ấy đã có người canh.

| # | Quyết định | Vì sao | Trạng thái |
|---|---|---|---|
| **0001** | **Modular monolith** + manifest khai bảng sở hữu; **không** microservices, **không** event-bus single-writer | Ở 1 RPS/1 người, cái cần là *ranh giới nghiệp vụ rõ*, không phải scale độc lập. Microservices = ops ×10 + saga cho một luồng vốn là 1 transaction | ❌ **Chưa** — không có `modules/`, không manifest, CI chưa kiểm |
| **0002** | **Bỏ RabbitMQ**; outbox polling relay là đường async duy nhất; thêm bảng `notification_delivery` | Đường RabbitMQ **chết end-to-end**: hàm publish còn `raise NotImplementedError`. Cần sửa 3 mảnh + thêm 150MB + 1 điểm chết, để làm việc mà relay đã làm được | ❌ **Chưa** — `rabbitmq` vẫn khởi động cùng stack, `event_bus/` vẫn còn |
| **0003** | **Mọi bất biến tranh chấp ép ở Postgres** (constraint → CAS → trigger+advisory lock → RPC); app chỉ dịch mã lỗi | Hai race đã gặp thật: overbook slot 2+1, trùng số thứ tự. Khoá Python chỉ đúng trong 1 tiến trình; database đúng dưới mọi client | ✅ Đang chạy cho 2+1 và số thứ tự |
| **0004** | **Auth 2 lớp fail-closed**: X-API-Key (dịch vụ↔dịch vụ) + JWT từng nhân viên (vai **suy ở máy chủ**); RLS chỉ cho đọc | Khảo sát 18/07: middleware **fail-open** khi thiếu khoá, và cả loạt router **không có** guard vai — ai cầm API key gọi được `DELETE /staff` | ✅ Đang chạy |
| **0005** | **Không thêm hạ tầng có trạng thái** (không Redis, không vector DB riêng, không LLM chạy tại chỗ); Postgres làm tất; LLM qua Anthropic API 2 tầng | Mỗi hệ stateful thêm vào là một thứ phải backup/monitor/vá — với đội 1 người. Tiền LLM thật chỉ $1–5/ngày | ✅ Đang giữ đúng |
| **0006** | **Ngân sách RAM từng container**; tách nhận dạng giọng nói khỏi tiến trình api | Không có `mem_limit` nào ⇒ **một container rò rỉ ăn cả máy và đè prod**. Model giọng nói nạp 1–3GB vào chính tiến trình api | ⚠️ Phần giới hạn RAM ✅; phần "Mac mini" đã lỗi thời (đã lên VPS) |
| **0007** | Bộ nhớ hội thoại LangGraph nằm ở **lược đồ riêng `langgraph`** — ngoại lệ có rào của luật "lược đồ chỉ qua migration" | Thư viện tự tạo bảng lúc khởi động, không phát hành file SQL. Rào: `public` không bị đụng, không JOIN sang, mất cũng **không mất nghiệp vụ** | ✅ |
| **0008** | Sửa hồ sơ đã chốt: **`FINALIZED → AMENDED` qua RPC có vết trong `event_log`**, bỏ bảng `visit_amendment` | Đang tồn tại một đường UPDATE hợp lệ mà **không bắt buộc ghi vết** — rủi ro pháp lý thật (TT13). `event_log` append-only đã là xương sống audit sẵn có | ✅ |
| **0009** | **Multi-tenant thật ngay từ đầu**: `clinic` + `clinic_membership` + `clinic_id` trên 27 bảng | Thêm tenant *sau khi* có dữ liệu thật = backfill 30+ bảng + viết lại mọi policy. Chi phí đó chỉ tăng theo thời gian | ✅ — và **RLS không bảo vệ backend**, nên có cổng CI `tenant-scope-audit.py` ngưỡng 0 (đưa từ 71 → 0) |
| **0010** | **KiotViet: mở sẵn cổng, không phụ thuộc.** ClinicAI là nguồn sự thật; POS ngoài chỉ được đồng bộ **tới**, không ghi ngược | Phòng khám có thể đã dùng KiotViet — không đóng cửa. Nhưng KiotViet sập **không được** làm hỏng luồng thu ngân | ✅ (đang dùng bộ nối rỗng, `POS_ADAPTER=none`) |
| **0011** | **Dựng kernel workflow V2 ngay** (`node_definition` / `work_item`), thay `staff_task`. **Node là dữ liệu, không phải code** | Phần khiến ClinicAI khác phần mềm phòng khám thường (điều phối cấu hình được) khi ấy **chỉ tồn tại trên giấy**. `staff_task` là bảng phẳng, không dependency, không cổng | ✅ — 41 node trong `node_definition`, sinh việc tự động lúc check-in đã chạy; ⚠️ `staff_task` vẫn chạy song song, chưa gỡ |
| **0012** | **Backend sở hữu hợp đồng**: OpenAPI có phiên bản (`/api/v1`) là mặt tiếp xúc duy nhất; khoá service-role **rời khỏi** frontend | Mục tiêu: đổi/vứt frontend mà backend không hỏng. Đang vi phạm ở 2 chỗ: dashboard đọc/ghi Supabase thẳng, và luật nghiệp vụ còn nằm trong TSX | ⚠️ Một phần — xem cảnh báo ở mục 0.5 (1) |
| **0013** | **Chạy được ở đâu cũng được**: khác biệt máy chủ nằm ở compose override + `.env`, không nằm trong code. Kiểm bằng **CI Linux**, không bằng niềm tin | Hạ tầng "tạm" ăn sâu vào code (đường dẫn macOS, `launchd`, cổng cứng) rồi lúc chuyển phải viết lại | ✅ **Đã chuyển VPS thật** — job `portability` là bằng chứng sống |

Ánh xạ sang tên tiếng Việt trong `SO-LUAT.md` Phần 9: một-khối = 0001 · gửi-tin = 0002 ·
tranh-chấp = 0003 · cửa-vào = 0004 · không-máy-mới = 0005 · ngân-sách = 0006 ·
bộ-nhớ-hội-thoại = 0007 · đính-chính = 0008 · nhiều-phòng-khám = 0009 · cổng-bán-hàng = 0010 ·
luồng-là-dữ-liệu = 0011 · hợp-đồng = 0012 · chạy-đâu-cũng-được = 0013.

---

## PHẦN 3. CẤU HÌNH VÀ MÔI TRƯỜNG

### 3.1. Hai môi trường chạy song song trên cùng một máy chủ

Trên VPS (`ssh clinic-vps`) có **hai bộ container chạy cùng lúc**, hoàn toàn tách nhau:

| | **prod** — đang đón bệnh nhân | **staging** — chỗ để thử |
|---|---|---|
| Thư mục | `/home/clinicai/clinicai` | `/home/clinicai/staging` |
| Đứng ở | nhánh `main` | tag `staging-*` |
| Tên project Docker | `clinicai_prod` | `clinicai_staging` |
| `APP_ENV` | `production` | `staging` |
| Nhãn ảnh (`IMAGE_TAG`) | `prod` | `staging` |
| File môi trường | `.env.prod` | `.env.staging` |
| Cổng Caddy (HTTP/HTTPS) | **80 / 443** | **8080 / 8443** |
| Caddy nghe ở | `0.0.0.0` (ra ngoài) | **`127.0.0.1`** (chỉ trong máy) |
| Uptime Kuma / Dozzle | 3001 / 8888 | 3002 / 8889 |
| Database | Postgres riêng | Postgres riêng — **chỉ dữ liệu giả** |
| RAM cấp cho api | 1 GB | 768 MB |
| **Tên cookie phiên** | `clinicai-auth` | **`clinicai-auth-8080`** |
| Lên bản mới | người bấm, **chỉ 1h–4h sáng** | tự động khi CI xanh |

**Hai thư mục dùng chung một kho `.git`** (git worktree): tách hẳn nguồn của hai môi trường
mà không nhân đôi dung lượng. Trước 13/08 cả hai dùng chung một thư mục — **một lần
`git checkout` là đổi luôn nguồn của prod**, và không ai thấy cho tới lần deploy sau.

#### Vì sao tên cookie phải khác — và vì sao nó không phải chuyện nhỏ

> **COOKIE KHÔNG PHÂN BIỆT CỔNG.** Đây là quy định của chính chuẩn cookie (RFC 6265 §8.5),
> và là chỗ ai cũng đoán sai: `http://IP:80` và `http://IP:8080` là hai **origin** khác nhau
> với mọi thứ khác — nhưng dùng **chung một hũ cookie**.

Chưa có tên miền riêng nên hai môi trường đang nằm đúng như thế. Nếu để chung một tên cookie:
đăng nhập staging là **ghi đè phiên prod**. Tệ hơn — hai môi trường có hai máy chủ xác thực
riêng với hai khoá ký khác nhau, nên tab prod cầm token của staging sẽ bị từ chối. Người dùng
thấy mình vừa **bị đăng xuất khỏi prod mà không hiểu vì sao**.

Cách giải: `src/dashboard/lib/supabase-cookie.ts` suy hậu tố **từ cổng** trong
`NEXT_PUBLIC_SUPABASE_URL`. Cổng mặc định (rỗng/80/443) → **không hậu tố**.

⚠️ **Prod giữ nguyên tên cũ, có chủ ý:** đổi tên cookie là **đăng xuất tất cả mọi người**.
Prod không có cổng trong URL nên rơi vào nhánh không hậu tố. Chỉ staging đổi tên — và ở
staging thì đăng xuất một lần là cái giá đúng phải trả.

#### Mười service trong `docker-compose.yml`

| Service | Cổng ra host | RAM mặc định | Profile | Ghi chú |
|---|---|---|---|---|
| `caddy` | **80 / 443** — thứ duy nhất mở ra ngoài | 128m | — | chờ `dashboard` khoẻ |
| `dashboard` | *không mở* | 512m | — | chờ `api` khoẻ |
| `api` | *không mở* | 1g | — | `/health/db` mới là kiểm thật (chạm database) |
| `worker` | *không mở* | 256m | `workers` | khoẻ = file nhịp tim mới hơn 180s |
| `notification-relay` | *không mở* | 256m | `workers`,`notifications` | đường Telegram (mục 1.4) |
| `pos-relay` | *không mở* | 256m | `pos` | đẩy sang POS ngoài |
| `rabbitmq` | *không mở* | 512m | `workers` | ⚠️ **ADR-0002 nói xoá, chưa xoá** |
| `uptime-kuma` | **127.0.0.1**:3001 | 256m | — | chỉ mở trong máy |
| `dozzle` | **127.0.0.1**:8888 | 128m | — | chỉ mở trong máy, mạng riêng |
| `cloudflared` | *không mở* | 128m | `cloudflare` | đường hầm ra Internet |

> **Vì sao chỉ Caddy mở cổng:** mọi thứ khác chỉ gọi được từ trong mạng nội bộ của Docker.
> Một lỗ hổng ở dashboard cũng không cho ai gọi thẳng vào `api:8000`. Kuma và Dozzle thì
> ghim `127.0.0.1` — muốn xem phải vào máy (qua SSH/Tailscale), không mở ra Internet.

### 3.2. Bảng biến môi trường quan trọng

> **Tuyệt đối không có giá trị bí mật nào trong tài liệu này.** Chỉ **tên biến** và ý nghĩa.
> Bí mật chỉ nằm trong `.env.prod` / `.env.staging` (đã gitignore) và GitHub Actions secrets.
> **Không bao giờ trong code.** Muốn xem khuôn mẫu: `.env.prod.example` / `.env.staging.example`.

**Nhận dạng môi trường & triển khai**

| Biến | Ý nghĩa |
|---|---|
| `APP_ENV` | `development` / `staging` / `production`. Cũng chọn thư mục gắn kèm |
| `COMPOSE_PROJECT_NAME` | Không gian tên Docker (`clinicai_prod` / `clinicai_staging`) — script deploy kiểm lại |
| `IMAGE_TAG` | Nhãn dán lên ảnh `clinicai-api` / `clinicai-dashboard` |
| `CLINIC_ENV_FILE` | Đường dẫn file env container nạp. **Phải khớp** `--env-file` — đây là cái chặn staging nạp nhầm bí mật prod |
| `COMPOSE_PROFILES` | Danh sách profile bật kèm: `workers`, `notifications`, `pos`, `cloudflare` |
| `LOG_LEVEL` | Mức log Python |

**Cửa vào & cổng**

| Biến | Ý nghĩa |
|---|---|
| `SITE_ADDRESS` | Khối site của Caddy: `:80` khi đứng sau đường hầm, hoặc tên miền để Caddy tự xin chứng chỉ. **Bắt buộc** |
| `CADDY_BIND_ADDRESS` | Địa chỉ Caddy nghe: `0.0.0.0` (prod) vs `127.0.0.1` (staging) |
| `CADDY_HTTP_PORT` / `CADDY_HTTPS_PORT` | 80/443 (prod) · 8080/8443 (staging) |
| `SUPABASE_GATEWAY_HOST` | Máy chủ Caddy chuyển `/auth/v1`, `/rest/v1`, `/realtime/v1` tới |
| `SUPABASE_NETWORK` | Tên mạng Docker ngoài của bộ Supabase thuộc môi trường đó |
| `TUNNEL_TOKEN` | Vé đường hầm Cloudflare. Có giá trị → tự bật profile `cloudflare` |

⚠️ `SUPABASE_NETWORK` và `SUPABASE_GATEWAY_HOST` mặc định trỏ về **prod**. Staging **phải
ghi đè** — không thì trình duyệt staging đi thẳng vào **database phòng khám thật**. Lần dựng
staging đầu tiên tránh được chuyện này **do may**: nó báo 502 vì chưa nối vào mạng của prod.

**Database & Supabase**

| Biến | Ý nghĩa |
|---|---|
| `SUPABASE_URL` | Địa chỉ Supabase phía **máy chủ** (container gọi container) |
| `PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_URL` | Địa chỉ phía **trình duyệt** — khác cái trên, và chính chỗ khác nhau này sinh ra bài toán tên cookie ở 3.1 |
| `SUPABASE_ANON_KEY` | Khoá công khai, được nung vào bundle trình duyệt |
| `SUPABASE_SERVICE_ROLE_KEY` | Khoá **bỏ qua RLS**. Chỉ ở phía máy chủ. ADR-0012: phải rời khỏi frontend |
| `SUPABASE_JWT_SECRET` | Backend dùng để xác minh token |
| `DATABASE_URL` | Chuỗi nối Postgres của môi trường (asyncpg) |
| `DATABASE_URL_TEST` | Database dùng-rồi-bỏ cho `pytest -m db`. Không đặt = bỏ qua nhóm test đó |
| `CHECKPOINTER_BACKEND` | Bộ nhớ hội thoại: `postgres` (sống qua restart) vs `memory` |

**Xác thực**

| Biến | Ý nghĩa |
|---|---|
| `BACKEND_API_KEY` | Khoá dịch vụ↔dịch vụ, canh **mọi** đường API trừ `/health`. Thiếu ở production → **fail-closed**, app không phục vụ |

**Trí tuệ nhân tạo**

| Biến | Ý nghĩa |
|---|---|
| `ANTHROPIC_API_KEY` | Khoá Claude API cho LangGraph + các dịch vụ LLM |
| `ENABLE_AI_ORCHESTRATOR` | Cờ bật/tắt. **`false` ở cả prod lẫn staging** — bề mặt thử nghiệm |

**Thông báo**

| Biến | Ý nghĩa |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Vé bot lấy từ @BotFather |
| `TELEGRAM_CHAT_ID` | **Danh sách kênh nhận, ngăn bởi dấu phẩy** |
| `TELEGRAM_CLINIC_ID` | UUID phòng khám relay phục vụ. Thiếu/sai → worker **từ chối chạy** ("từ chối một relay chạy chéo phòng khám") |
| `NOTIFICATION_RELAY_ENABLED` | Phải đúng chữ `true`, không thì relay tự thoát |
| `ZALO_ZNS_ACCESS_TOKEN` | Vé Zalo OA — **kênh dành cho bệnh nhân** (hết hạn định kỳ) |
| `ZALO_ZNS_TEMPLATE_NHAC_HEN` / `..._TRA_KET_QUA` | Mã mẫu tin đã được duyệt. Để trống thì nút vẫn hiện nhưng **bị khoá kèm lời giải thích** |

**Hàng chờ (chỉ cần khi bật profile `workers`)**

`RABBITMQ_URL`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`, `RABBITMQ_VHOST` — ⚠️ mật khẩu rỗng
thì broker **thoát mã 78** thay vì khởi động bằng mật khẩu mặc định ai cũng biết.

**Theo dõi & ngân sách tài nguyên**

| Biến | Ý nghĩa |
|---|---|
| `KUMA_PORT` / `DOZZLE_PORT` | Cổng ghim `127.0.0.1` cho hai màn theo dõi |
| `DOZZLE_AUTH_PROVIDER` | Chế độ đăng nhập Dozzle (`none` — vì đã ghim localhost) |
| `OPS_KUMA_PUBLIC_URL` · `OPS_DOZZLE_PUBLIC_URL` · `OPS_SENTRY_PUBLIC_URL` | Đường dẫn màn `/ops` hiển thị |
| `SENTRY_DSN` | Nơi nhận báo lỗi. ⚠️ **Chưa cài `sentry-sdk`** ⇒ lỗi của người dùng thật hiện **không báo về đâu cả** (`SO-LUAT` Luật 8.3) |
| `API_MEMORY_LIMIT` · `DASHBOARD_MEMORY_LIMIT` · `CADDY_MEMORY_LIMIT` · `WORKER_MEMORY_LIMIT` · `NOTIFICATION_RELAY_MEMORY_LIMIT` · `POS_RELAY_MEMORY_LIMIT` · `RABBITMQ_MEMORY_LIMIT` · `KUMA_MEMORY_LIMIT` · `DOZZLE_MEMORY_LIMIT` · `CLOUDFLARED_MEMORY_LIMIT` | Trần RAM từng container (ADR-0006). **Vì sao:** không có trần thì **một container rò rỉ ăn cả máy và đè prod** |

**Tích hợp khác**

| Biến | Ý nghĩa |
|---|---|
| `POS_ADAPTER` | Bộ nối POS. `none` mặc định — thà dồn vào thư chết còn hơn **giả vờ đã gửi** |
| `CLINIC_API_URL` | Địa chỉ FastAPI mà dashboard gọi. Compose đặt sẵn `http://api:8000`. **Không có = triển khai hỏng**, và nó báo to chứ không âm thầm |

**Múi giờ — cố ý KHÔNG phải biến môi trường**

> ClinicAI chỉ bán trong Việt Nam. Múi giờ **ghim cứng** trong code:
> `src/clinicai/core/clock.py` → `CLINIC_TZ = ZoneInfo("Asia/Ho_Chi_Minh")`,
> và phía frontend ở `src/dashboard/lib/datetime.ts`.
>
> **Vì sao ghim mà không cho cấu hình:** một biến môi trường đặt sai là cả phòng khám lệch
> giờ mà không ai báo lỗi. Và nhớ cái bẫy ở 1.3 — "1h sáng" của máy chủ chạy giờ quốc tế
> chính là **8h sáng** giờ Việt Nam, đúng lúc đông khách nhất.

---

*(Hết Phần 0–3. Phần 4 trở đi đi vào từng thư mục, từng file, từng hàm.)*


---

## PHẦN 4. NỀN BACKEND — CẤU HÌNH, KẾT NỐI, DANH TÍNH & QUYỀN

Đây là tầng mà mọi request đi qua trước khi chạm vào nghiệp vụ phòng khám: nó trả lời
*bây giờ là mấy giờ theo giờ phòng khám*, *nói chuyện với database bằng đường nào*,
*người gọi là ai và làm ở phòng khám/cơ sở nào*, *vai đó được làm gì*, và *khi hỏng thì
người trực đọc được câu gì*. Sai ở đây không hiện ra thành màn hình đỏ — nó hiện ra
thành một lịch hẹn nằm sai cơ sở, một ca trực bị bỏ qua, hoặc một cái tivi phòng chờ đọc
được hồ sơ bệnh nhân. Gần như mọi hằng số trong phần này đều có một sự cố thật đứng sau,
và các chú thích tiếng Việt trong repo ghi lại chúng — phần giảng dưới đây chắt từ đó.

> **KHÔNG CÓ `core/config.py`.** Repo này không có lớp Settings tập trung: mỗi module tự
> đọc `os.environ` tại điểm dùng (`database.py:43`, `identity.py:190`, `auth.py:78`,
> `logging.py:151`, `sentry.py:27`). Danh sách biến đầy đủ ở mục 4.17.

---

### 4.1. `core/clock.py` — một múi giờ, khai đúng một chỗ (51 dòng)

| Hàm / hằng | Giải thích |
|---|---|
| `CLINIC_TZ` | `ZoneInfo("Asia/Ho_Chi_Minh")` — vùng IANA, dùng cho mọi phép tính datetime |
| `CLINIC_TZ_NAME` | Chuỗi `"Asia/Ho_Chi_Minh"` cho nơi cần chuỗi: tham số SQL, JSON trả về API |
| `now_vn()` | `datetime.now(CLINIC_TZ)` — thay cho `datetime.now()` trần |

**VÌ SAO MỘT FILE CHO MỘT HẰNG SỐ.** Chú thích ở `clock.py:9-17` kể: cùng sự thật ấy
từng được khai lại **năm chỗ trong Python, tám chỗ trong TypeScript**, và tệ nhất là
`visit_progress_service` dùng `timezone(timedelta(hours=7))` — một **offset cố định**,
không phải một vùng IANA.

> Với Việt Nam hai thứ đó cho cùng kết quả (nước này chưa từng dùng giờ mùa hè), nên sai
> lệch chưa bao giờ lộ ra. Nó chỉ lộ vào ngày ai đó copy dòng ấy sang một chỗ có DST.

Và `now_vn()` không phải trang trí: máy chủ chạy UTC, nên `datetime.now()` không mang múi
giờ sẽ **lệch bảy tiếng đúng ở các phép so sánh ranh giới ngày** — đủ để "hôm nay" thành
"hôm qua" suốt ca tối, tức chính khung giờ phòng khám làm việc (`clock.py:46-49`).

**Còn cột `clinic.timezone`?** Nó có trong schema và **không ai đọc**. Một cột cấu hình
mà hệ thống bỏ qua là một lời hứa suông — người vận hành đổi nó, không có gì xảy ra và
không có gì báo. Migration `20260803000012` thêm `CHECK` ghim nó về đúng giá trị này, để
việc đổi bị **từ chối kèm giải thích** thay vì được nhận rồi lặng lẽ vô hiệu.

---

### 4.2. `core/shifts.py` — ca SÁNG/CHIỀU/CẢ NGÀY thành khoảng phút (75 dòng)

| Hàm | Giải thích |
|---|---|
| `MORNING_END_MIN` | `12*60 = 720`. Mốc 12:00 là **quyết định của phòng khám** (Quang, 2026-08-04), không suy ra từ dữ liệu — nên nó nằm đúng một chỗ vì "sẽ là thứ đầu tiên phòng khám thứ hai muốn đổi" |
| `Window` | Alias `tuple[int, int]` — khoảng phút nửa mở `[lo, hi)` |
| `shift_window(shift, open_min, close_min)` | Nhãn ca → khoảng phút, cắt theo **giờ mở cửa hôm đó**; `None` nếu ca rỗng |
| `merge_windows(windows)` | Gộp các khoảng chồng/kề, trả danh sách rời nhau đã sắp xếp |
| `covers(windows, minute)` | Mốc phút có nằm trong ca nào không (`lo <= minute < hi`) |
| `describe(windows)` | Thành câu `"08:00–12:00, 13:30–17:00"` để đưa thẳng vào thông báo cho người dùng |

**Vấn đề nghiệp vụ nó giải:** `work_roster.shift` chỉ có ba nhãn `FULL`/`SANG`/`CHIEU`.
Ba nhãn ấy nói về thời gian, nhưng **không chỗ nào trong hệ thống nói sáng kết thúc lúc
mấy giờ** — nên luật lịch trực trước đây chỉ dừng ở mức NGÀY, và *một bác sĩ chỉ trực ca
sáng vẫn được mời đặt lịch lúc 18:00* (`shifts.py:5-6`).

```python
    if shift == "FULL":
        lo, hi = open_min, close_min
    elif shift == "SANG":
        lo, hi = open_min, min(close_min, MORNING_END_MIN)
    elif shift == "CHIEU":
        lo, hi = max(open_min, MORNING_END_MIN), close_min
    else:
        lo, hi = open_min, close_min      # nhãn lạ → coi như cả ngày
    return (lo, hi) if hi > lo else None
```

1. Đầu/cuối ngày lấy theo **giờ mở cửa của phòng khám hôm đó**, không phải 00:00–24:00.
   Ca sáng của một ngày mở cửa lúc 17:00 là một khoảng rỗng, và nói ra điều đó đúng hơn
   là lặng lẽ cho phép đặt lúc 8 giờ sáng.
2. `min`/`max` là chỗ cắt: SÁNG không bao giờ vượt quá 12:00, CHIỀU không bao giờ bắt đầu
   trước 12:00 **hoặc trước giờ mở cửa** — cái nào muộn hơn thắng.
3. Nhánh `else` **cố ý sai theo hướng rộng**: nhãn lạ được coi là cả ngày.
   > Một ca không đọc được mà biến mất sẽ khoá lịch của một bác sĩ đang thật sự đi làm —
   > sai theo hướng đó tệ hơn hẳn (`shifts.py:39-41`).
4. `hi > lo` mới trả về — khoảng rỗng trả `None`, và **đó không phải lỗi**, chỉ là một ca
   không có giờ nào.

`merge_windows` tồn tại vì một bác sĩ có thể có **nhiều dòng lịch trực cùng một ngày** ở
nhiều trạm khác nhau, ca khác nhau (SÁNG ở trạm này, CHIỀU ở trạm kia). Bác sĩ đó có mặt
trong **hợp** của các ca, nên phải gộp trước khi hỏi `covers`.

---

### 4.3. `core/database.py` — bể kết nối asyncpg (87 dòng)

| Hàm / hằng | Giải thích |
|---|---|
| `POOL_MIN_SIZE=2`, `POOL_MAX_SIZE=10` | Kích thước bể |
| `COMMAND_TIMEOUT=15` | Timeout **mỗi truy vấn**, chặn truy vấn chạy hoang giữ chỗ trong bể |
| `STARTUP_RETRIES=3`, `STARTUP_BACKOFF=2.0` | Thử lại lúc khởi động, backoff tuyến tính `2s, 4s` |
| `normalize_dsn(dsn)` | Cắt hậu tố `+asyncpg` kiểu SQLAlchemy: `postgresql+asyncpg://` → `postgresql://` |
| `_normalize_dsn` | Bí danh cũ, giữ cho các chỗ gọi nội bộ đã có |
| `create_pool()` | Tạo bể từ `DATABASE_URL`, thử lại 3 lần rồi `RuntimeError` để container thoát |
| `close_pool(pool)` | Đóng bể lúc shutdown |
| `get_db_pool(request)` | Dependency FastAPI, `yield request.app.state.db_pool` |

`normalize_dsn` **là hàm công khai chứ không phải hàm nội bộ**, và chú thích ở
`database.py:23-28` nói rõ vì sao:

> CÔNG KHAI vì có hai nơi mở kết nối, không phải một. […] bộ nghe LISTEN
> (`change_broker`) mở một kết nối RIÊNG và lúc đầu đọc thẳng `DATABASE_URL` — nên nó
> chết ngay khi khởi động với `invalid DSN: scheme is expected to be either "postgres"…`
> […] **Một hàm chuẩn hoá mà chỉ một trong hai chỗ gọi thì chưa phải chuẩn hoá.**

Vòng thử lại chỉ bắt `asyncpg.PostgresConnectionError` và `OSError` — tức lỗi *mạng/kết
nối*, không phải lỗi sai mật khẩu. Hết ba lần thì `raise RuntimeError` **có chủ ý**: cho
container chết để Docker khởi động lại, thay vì chạy tiếp với `app.state.db_pool = None`
và hỏng ở request đầu tiên (`database.py:73-76`).

---

### 4.4. `core/change_broker.py` — LISTEN/NOTIFY thay Supabase Realtime (149 dòng)

| Thành phần | Giải thích |
|---|---|
| `CHANNEL = "clinicai_changes"` | Tên kênh, **phải khớp hàm trigger trong migration** |
| `QUEUE_SIZE = 8` | Hàng đợi mỗi màn hình — nhỏ có chủ ý (xem dưới) |
| `RECONNECT_DELAY_S = 3.0` | Nối lại sau bao lâu khi kết nối nghe bị rớt |
| `ChangeBroker.__init__(dsn)` | Gọi `normalize_dsn`, khởi tạo `_subs: dict[clinic_id, set[Queue]]` |
| `.start()` | Tạo task nền `_run()` tên `change-broker` |
| `.stop()` | Bật cờ `_stopping`, huỷ task, đóng kết nối |
| `._run()` | Vòng lặp giữ một kết nối LISTEN, tự nối lại khi rớt |
| `._on_notify(conn, pid, channel, payload)` | Callback **đồng bộ** của asyncpg: parse JSON, lấy `c` = clinic_id, `put_nowait` vào từng hàng đợi |
| `.subscribe(clinic_id)` | Trả một `asyncio.Queue` mới, đăng ký vào bucket của phòng khám |
| `.unsubscribe(clinic_id, q)` | Gỡ hàng đợi; bucket rỗng thì xoá luôn key |
| `.listener_count` | Tổng số màn hình đang nghe (quan sát vận hành) |

**VÌ SAO BỎ SUPABASE REALTIME** (`change_broker.py:3-12`): Realtime đọc WAL qua một
*replication slot*, mà tạo slot cần quyền `REPLICATION`. Database cho thuê không cấp —
**đã đo trên Viettel IDC 06/08/2026: `pg_create_logical_replication_slot` bị từ chối**.
Không phải trục trặc cấu hình, là chính sách; AWS RDS và Azure cũng vậy. `LISTEN`/`NOTIFY`
là SQL thường, không đòi quyền nào.

> Đường cũ: ghi → WAL → dịch vụ Realtime giải mã → websocket. Đường này: ghi → NOTIFY
> (bắn đúng lúc COMMIT) → SSE. **Thứ đang ghi dữ liệu chính là thứ biết có gì đổi**; bản
> cũ để nó im lặng rồi cử một dịch vụ khác đi đọc lại nhật ký để đoán ra điều đó.

Ba quyết định thiết kế đáng nhớ:

1. **Kết nối riêng, không lấy từ bể chung** (`_run`, dòng 87-89). Một kết nối đang LISTEN
   bị giữ suốt đời tiến trình; mượn từ bể là vĩnh viễn bớt một chỗ của truy vấn thật, và
   asyncpg cũng không hứa trả lại đúng kết nối ấy.
2. **Hàng đợi nhỏ và bỏ tin khi đầy.** `_on_notify` được asyncpg gọi **đồng bộ trên event
   loop** — không được `await` gì cả:
   ```python
        for q in self._subs.get(clinic_id, ()):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass
   ```
   Bỏ tin ở đây vô hại vì nội dung mỗi tin không quan trọng: màn hình chỉ cần biết "có gì
   đó đổi" rồi tự đọc lại, nên **tin sau cũng nói đúng điều ấy**. Đổi lại, một màn hình
   chậm không được phép làm nghẽn các màn khác.
3. **Mất broker không được làm chết app.** `_run` nuốt mọi `Exception` (trừ
   `CancelledError`) và log `change_broker_lost` — database khởi động lại hay mạng chớp
   thì màn hình rơi về **nhịp làm mới dự phòng** của riêng nó, chứ không ai đăng nhập hỏng
   (`main.py:86-88`).

Nhiều bản API chạy song song vẫn đúng: NOTIFY phát tới **mọi** kết nối đang LISTEN, nên
mỗi bản tự nhận và tự phát cho màn hình nối vào nó — không cần Redis/RabbitMQ ở giữa.
Router tiêu thụ nó là `events.py:52/64` (`subscribe`/`unsubscribe` quanh dòng SSE).

---

### 4.5. `core/exceptions.py` + `api/exceptions.py` — cây lỗi có mã HTTP (40 + 36 dòng)

| Lớp | Ở đâu | HTTP | `error_code` |
|---|---|---|---|
| `ClinicAIBaseException(message)` | core | 400 | `BAD_REQUEST` |
| `ResourceNotFoundError` | core | 404 | `NOT_FOUND` |
| `ValidationError` (core) | core | 422 | `VALIDATION_ERROR` |
| `SafetyGateError` | core | 403 | `SAFETY_GATE_ERROR` |
| `ExternalServiceError` | core | 502 | `EXTERNAL_SERVICE_ERROR` |
| `NotFoundError` | api | 404 | `NOT_FOUND` |
| `ValidationError` (api) | api | 422 | `VALIDATION_ERROR` |
| `ConflictError` | api | 409 | `CONFLICT_ERROR` |
| `PatientNotFoundError` | api | 404 | `PATIENT_NOT_FOUND` |
| `WorkSessionNotFoundError` | api | 404 | `WORK_SESSION_NOT_FOUND` |

Ý tưởng: **mã HTTP là thuộc tính lớp**, không phải tham số lời gọi. Service chỉ `raise
ValidationError("...")`, còn `clinicai_exception_handler` ở `main.py:386` đọc
`exc.status_code` + `exc.error_code` và dựng JSON. Nhờ vậy service **không import
FastAPI** — đúng luật "logic là Python thuần, test được" trong `CLAUDE.md`.

> ⚠️ Có **hai** `ValidationError` và **hai** lớp 404 (`ResourceNotFoundError` ở core vs
> `NotFoundError` ở api) trùng nhiệm vụ. Chúng cùng kế thừa `ClinicAIBaseException` nên
> handler bắt được cả hai, nhưng import nhầm file thì `except` sẽ trượt. Đây là điểm dễ
> hiểu sai, không phải lỗi chạy.

---

### 4.6. `core/logging.py` — log JSON và bộ xoá dữ liệu nhạy cảm (196 dòng)

| Hàm / hằng | Giải thích |
|---|---|
| `REDACTED` | Chuỗi `"[REDACTED]"` thay cho giá trị bị xoá |
| `_SENSITIVE_KEYS` | ~30 tên khoá bị xoá thẳng: `phone`, `patient_name`, `patient_id`, `full_name`, `address`, `authorization`, `transcript`, `message`… |
| `_SENSITIVE_KEY_SUFFIXES` | Hậu tố: `_phone`, `_email`, `_token`, `_secret`, `_patient_id`, `_prompt`… |
| `_EMAIL_RE`, `_VN_PHONE_RE`, `_BEARER_RE`, `_SECRET_ASSIGNMENT_RE` | 4 regex quét **văn bản tự do** |
| `_redact_text(value)` | Áp lần lượt 4 regex lên một chuỗi |
| `_is_sensitive_key(key)` | Chuẩn hoá `-`/`.` thành `_`, hạ chữ thường rồi so khớp tên + hậu tố |
| `_redact_value(value)` | Đệ quy qua `str` / `Mapping` / `list` / `tuple` |
| `redact_sensitive_data(...)` | Processor structlog: xoá theo khoá **và** theo nội dung, không sửa payload gốc |
| `rename_event_to_message(...)` | Đổi tên trường `event` của structlog thành `message` cho đúng chuẩn JSON log |
| `add_static_fields(...)` | Chèn `service="clinicai-api"` + `environment=APP_ENV` vào mọi dòng |
| `setup_logging()` | Cấu hình structlog + logging chuẩn, cướp handler của `uvicorn*`/`fastapi` |

Hai lớp bảo vệ, và thứ tự giữa chúng quan trọng:

1. **Theo khoá** — `patient_name=...` biến mất bất kể giá trị là gì.
2. **Theo nội dung** — một chuỗi tự do lỡ chứa số điện thoại/email/bearer token vẫn bị
   quét sạch. Đây là lưới thứ hai cho những chỗ lập trình viên không kịp nghĩ tới.

`event` (tên sự kiện vận hành) được **giữ lại** nhưng vẫn đi qua `_redact_value`; còn một
trường `message` có cấu trúc thì bị coi là **nội dung bệnh nhân** và bị xoá. Đó là lý do
khắp `main.py` các handler log bằng `reason=` chứ không phải `message=` — xem bẫy ở cuối
phần.

`setup_logging()` chạy **ở mức module** trong `main.py:75`, trước cả khi `FastAPI()` được
tạo, nên dòng log đầu tiên của tiến trình đã là JSON.

---

### 4.7. `core/telemetry.py` — bộ đệm vòng đo độ trễ và lỗi (195 dòng)

| Thành phần | Giải thích |
|---|---|
| `MAX_SAMPLES=4096`, `MAX_ERRORS=200` | Sức chứa hai `deque` — "~4k request là một buổi chiều bận của phòng khám" |
| `SLOW_REQUEST_MS=1000.0` | Ngưỡng "chậm đáng để người ta để ý" |
| `Sample` | dataclass frozen+slots: `route, method, status, duration_ms, at` |
| `ErrorEntry` | Thêm `request_id, kind, detail` |
| `Telemetry.__init__` | Hai ring buffer + một `threading.Lock` |
| `.record(...)` | Ghi một mẫu; **chỉ 5xx** mới vào feed lỗi, `detail` cắt còn 300 ký tự |
| `.snapshot(window_s)` | Tổng hợp: đếm theo nhóm `2xx/3xx/4xx/5xx`, p50/p95/p99, top 40 route, 50 lỗi mới nhất |
| `percentile(values, pct)` | Nearest-rank percentile |
| `route_template(request)` | Trả **mẫu route**, không bao giờ trả path đã điền |
| `telemetry` | Instance dùng chung toàn tiến trình |

**VÌ SAO ĐỂ TRONG BỘ NHỚ, KHÔNG PHẢI MỘT BẢNG** (`telemetry.py:7-14`): một bảng
`request_log` đặt **một lượt ghi không giới hạn lên đường nóng của database lâm sàng**, nó
phình mãi, và mỗi request chậm lại làm database chậm thêm. Cái giá của lựa chọn này được
nói thẳng: **số liệu reset khi API khởi động lại và chỉ mô tả một tiến trình**. Ngày chạy
nhiều bản thì cần một metrics sink thật, "và đó là một phần việc khác chứ không phải một
bộ đệm to hơn".

Ba chi tiết dễ bỏ qua:

- **4xx không vào feed lỗi** (`record`, dòng 92-95): "4xx là việc client bị nói *không* —
  một phần bình thường của API có cửa gác, không phải sự cố." Nếu cho vào, feed đầy những
  lời từ chối đúng đắn và không ai đọc nữa.
- **`percentile` dùng nearest-rank, không nội suy.** Bản cũ dùng `round()` trả *phần tử
  thứ 96 trên 100* cho p95 — cao một bậc, tức **sai theo hướng che giấu cái đuôi chậm**
  (`telemetry.py:166-171`).
- **`route_template` không bao giờ trả path thật.** `/api/v1/patients/3f2b…` định danh một
  bệnh nhân; `/api/v1/patients/{id}` thì không, mà lại còn gom nhóm được. Không khớp route
  nào thì trả `"<unmatched>"` — một 404 không có template, và một path không khớp cũng
  không mang được id có nghĩa với hệ này.

---

### 4.8. `core/sentry.py` — báo lỗi ra ngoài mà không mang theo bệnh án (88 dòng)

| Hàm | Giải thích |
|---|---|
| `init_sentry()` | Đọc `SENTRY_DSN`; rỗng → log `sentry_disabled` và thoát êm. Thiếu gói → `sentry_import_failed`. Lỗi khác → `sentry_init_error`, **không bao giờ làm chết app** |

Tham số đáng học nằm ở đây, và đều là quyết định về **quyền riêng tư của bệnh nhân**:

```python
            send_default_pii=False,
            include_local_variables=False,
            max_request_body_size="never",
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
```

1. `send_default_pii=False` — không header, cookie, IP, thân request. Thân request ở hệ
   này chứa tên bệnh nhân, số điện thoại, chẩn đoán.
2. `include_local_variables=False` — **đây mới là chỗ rò thật sự**, và nó *không* do
   `send_default_pii` lo. SDK Python mặc định đính kèm **biến cục bộ của từng khung ngăn
   xếp**; lúc nổ lỗi biến cục bộ thường đang giữ nguyên một hàng `patient` hoặc
   `clinical_record`.
   > Một báo lỗi không được phép trở thành đường xuất dữ liệu bệnh án (`sentry.py:56-66`).
3. `max_request_body_size="never"` — chốt thứ hai, phòng trường hợp sau này ai đó bật
   `send_default_pii`.
4. `release=f"clinicai@{IMAGE_TAG}"` — nối lỗi về đúng ảnh Docker đã deploy.

Chú thích ở dòng 52-54 còn ghi lại một bài học về **chú thích nói ngược code**: bản cũ ghi
"Send PII … acceptable for internal clinic tool" trong khi code đặt `False` — và "người
đọc sau có thể sửa code cho khớp chú thích".

---

### 4.9. `core/phone.py` — chuẩn hoá số điện thoại Việt Nam (45 dòng)

| Hàm | Giải thích |
|---|---|
| `_VN_MOBILE_PREFIXES` | `{"03","05","07","08","09"}` — đầu số di động hợp lệ |
| `normalize_vn_phone(value)` | Trả dạng chuẩn 10 số `0xxxxxxxxx`, hoặc `None` nếu không hợp lệ |
| `phone_variants(value)` | Trả 3 cách viết cùng một số: `090…`, `8490…`, `+8490…` |

Nhận được cả `090…`, `8490…`, `+8490…`, `0084…` và dạng 9 số thuê bao; dấu cách/ngoặc/gạch
bị bỏ qua, nhưng **ký tự lạ (chữ cái) thì trả `None` ngay** (`phone.py:17`) chứ không cố
đoán. `phone_variants` tồn tại cho **MPI dedup** — tìm trùng bệnh nhân phải hỏi cả ba cách
viết vì dữ liệu cũ nhập lẫn lộn.

---

### 4.10. `api/identity.py` — ai đang gọi, ở phòng khám nào, vai gì (491 dòng)

Đây là file trung tâm của phần này. Nguyên tắc ghi ở đầu file: **không tin gì từ client —
không tin vai, không tin danh tính**. Nó thay mô hình cũ nơi frontend tự đặt cookie
`clinic_role` và tự chọn `staff_id` ở một màn "role-picker" (giả mạo được).

| Thành phần | Giải thích |
|---|---|
| `SUPABASE_AUDIENCE` | `"authenticated"` — `aud` bắt buộc của token Supabase |
| `ClinicRole` | Enum 13 vai, gương của mã vai trên `clinic_membership` |
| `_VALID_ROLES` | Tập chuỗi vai hợp lệ, dùng để kiểm tra dữ liệu từ DB |
| `CLINICAL_WRITE_ROLES` | Được ghi hồ sơ lâm sàng: DOCTOR, ULTRASOUND_DOCTOR, TKYK, NURSE_ULTRASOUND |
| `PHYSICIAN_ROLES` | **Có bằng hành nghề**: DOCTOR, ULTRASOUND_DOCTOR |
| `DOCTOR_DESK_ROLES` | **Làm ở bàn bác sĩ**: thêm TKYK |
| `CASHIER_ROLES` | CASHIER, CASHIER_THUOC, CASHIER_DV |
| `role_from_department(dept)` | Chuỗi vai → `ClinicRole`; không hợp lệ/None → **403**, không fallback |
| `StaffIdentity` | dataclass frozen: `staff_id, auth_user_id, full_name, department, role, clinic_id, location_id, location_name, short_name="", clinic_name=""` |
| `.can_write_clinical()` / `.is_doctor()` / `.is_cashier()` | Ba câu hỏi thường gặp, hỏi qua ba tập ở trên |
| `_jwk_client()` | `PyJWKClient` tới `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, `@lru_cache(1)` |
| `verify_supabase_jwt(token)` | Xác thực JWT; HS256 nếu có `SUPABASE_JWT_SECRET`, ngược lại ES256/RS256 qua JWKS |
| `_bearer_token(request)` | Bóc header `Authorization: Bearer …`, thiếu → 401 |
| `_requested_clinic_id(request)` | Đọc `X-Clinic-ID`, ép về UUID chuẩn; sai định dạng → 400 |
| `_IDENTITY_TTL_SECONDS=30`, `_IDENTITY_CACHE_MAX=512`, `_identity_cache` | Cache tra cứu membership |
| `invalidate_identity_cache(auth_user_id=None)` | Xoá cache — tất cả, hoặc của một login |
| `_cache_get` / `_cache_put` | Đọc/ghi cache, hết hạn thì tự bỏ; đầy thì **xoá sạch** thay vì đuổi khéo |
| `_resolve_identity(request, pool)` | JWT → staff → **một** membership đang hoạt động |
| `get_current_identity(...)` | Danh tính của một **người thật** — từ chối vai DISPLAY |
| `get_display_identity(...)` | Danh tính cho bảng gọi số phòng chờ — **nhận** cả DISPLAY |
| `RoleGuard(allowed)` | Dependency dạng lớp, đọc lại được `allowed_roles` |
| `require_role(*allowed)` | Factory trả `RoleGuard`; **46 chỗ** trong `api/v1/**` dùng nó |

#### `_resolve_identity` — từng bước

```python
    claims = verify_supabase_jwt(_bearer_token(request))
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject")
    requested_clinic_id = _requested_clinic_id(request)
    cache_key = (str(sub), requested_clinic_id)
    now = monotonic()
    cached = _cache_get(cache_key, now)
    if cached is not None:
        return cached
```

1. **Xác thực JWT trước, luôn luôn.** Cache nằm *sau* bước này nên "cache không bao giờ
   kéo dài được một phiên" — token hết hạn/giả bị loại trước khi cache được hỏi
   (`identity.py:267-271`).
2. **Khoá cache là `(sub, X-Clinic-ID)`.** Một người làm hai phòng khám có hai mục riêng.
3. Truy vấn `staff LEFT JOIN clinic_membership … LIMIT 2` — lấy 2 dòng **để phát hiện mơ
   hồ**, không phải để chọn dòng đầu.
4. `rows` rỗng → **403** "No active staff membership is linked to this login and clinic".
5. `len(rows) > 1` → **403**, log `ambiguous_clinic_membership`. Đây là *hoặc* login đa
   phòng khám mà thiếu `X-Clinic-ID`, *hoặc* dữ liệu cấp quyền hỏng (nhiều vai đang hoạt
   động trong cùng một phòng khám). Cả hai đều là mơ hồ về quyền → **fail closed**.
6. `clinic_id is None` → 403 "Tài khoản chưa được gán vào phòng khám nào". Trigger
   `staff_ensure_default_membership` lẽ ra luôn tạo membership, nên đây là hàng cũ trước
   W3 hoặc trigger bị bỏ qua.
7. `location_id is None` → 403 "Tài khoản chưa được gán cơ sở khám". Migration
   `20260803000007` đã đặt `NOT NULL`.
8. Chỉ **đường thành công** mới được cache — 403 không cache, để nhân viên vừa được cấp
   membership vào được ngay ở request kế tiếp thay vì phải đợi hết TTL.

**Vì sao `clinic_id` và `location_id` là bắt buộc, không `| None`.** Chú thích ở
`identity.py:136-160` là một bài học kiến trúc:

> Trong khi trường này còn khai `str | None`, mọi truy vấn phía dưới đều mang theo một
> `COALESCE(..., default_clinic_id())` cho một trường hợp **không thể xảy ra** — và chính
> cái fallback ấy mới là thứ lặng lẽ nhét bản ghi vào một phòng khám đoán mò.

Với `location_id` còn cụ thể hơn: vì nó **không** nằm trên danh tính, mọi nơi cần nó phải
lấy từ *thân request* — và đó là cách BookingHub gửi `locations[0].id`, tức "cơ sở đầu
tiên trong dropdown", làm nơi bệnh nhân sẽ được khám.

#### Cache membership — vì sao TTL 30 giây

`identity.py:253-271` ghi số đo: mỗi lời gọi đã xác thực chạy truy vấn membership sang
**Supabase Cloud ở Seoul, khoảng 60–90ms từ Việt Nam**, trước khi endpoint làm việc của
nó. Một cú bấm nút đã trả `supabase.auth.getUser()` cộng chặng sang FastAPI; đây là chân
thứ ba.

> Lựa chọn trung thực là TTL ngắn **hoặc** một kênh LISTEN/NOTIFY vô hiệu hoá cache trên
> `clinic_membership`. Cái thứ hai tốt hơn hẳn và cũng nhiều bộ máy hơn hẳn. 30 giây được
> chọn để một tài khoản bị khoá hoặc một vai bị đổi ngừng hoạt động **trong khoảng thời
> gian đi bộ tới quầy lễ tân** — đó mới là kiểu hỏng đang cần chặn.

Và cache có cửa thoát: `staff_service.py:354,404` gọi `invalidate_identity_cache()` sau
khi đổi vai/khoá tài khoản, nên thay đổi có hiệu lực ở request kế tiếp.

#### Vai `DISPLAY` — cái tivi phòng chờ

Đây là vai **không phải người**. Chú thích `identity.py:59-70` nói lý do là **an toàn**,
không phải tiện: nếu tivi đăng nhập bằng tài khoản Lễ tân, bất kỳ ai đứng cạnh chỉ cần mở
một tab mới là đọc được hồ sơ bệnh nhân.

Cơ chế chặn rất đáng học — nó là **danh sách cấm ở một chỗ, không phải danh sách cho phép
ở trăm chỗ**:

```python
async def get_current_identity(identity=Depends(_resolve_identity)) -> StaffIdentity:
    if identity.role is ClinicRole.DISPLAY:
        raise HTTPException(403, detail="Tài khoản màn hình chỉ được xem bảng gọi số")
    return identity
```

> Mọi endpoint trong hệ đều đi qua dependency này (có RoleGuard hay không), nên chặn ở đây
> nghĩa là cái tivi bị chặn ở khắp nơi **mà không phải liệt kê chỗ nào**. Bản kiểm kê
> 06/08 đếm được **26/119 endpoint chưa có RoleGuard** — một danh sách cho phép sẽ bỏ sót
> đúng những chỗ ấy (`identity.py:435-439`).

`get_display_identity` là ngoại lệ **có kiểm soát**: chỉ hai chỗ dùng nó
(`routers/identity.py:30` cho `/api/v1/me`, `routers/display.py:69` cho bảng gọi số), và
`src/tests/test_vai_man_hinh.py:79-94` có một bài kiểm **đếm số chỗ dùng** để chặn việc
mở rộng âm thầm.

#### `role_from_department` — vì sao không có fallback

```python
    if dept and dept in _VALID_ROLES:
        return ClinicRole(dept)
    logger.error("invalid_membership_role", department=dept)
    raise HTTPException(403, detail="Tài khoản có vai trò không hợp lệ")
```

Bản trước rơi về `CSKH` khi gặp giá trị lạ. Nhưng **CSKH không phải một vai vô hại để
hiển thị**: nó đọc được thông tin bệnh nhân và ghi được tương tác chăm sóc khách hàng. Một
lỗi gõ hoặc một membership NULL là **dữ liệu phân quyền hỏng**, nên fail closed
(`identity.py:117-119`).

#### `PHYSICIAN_ROLES` vs `DOCTOR_DESK_ROLES` — hai cái tên vì là hai câu hỏi

`identity.py:86-101` kể sự cố: tên cũ `DOCTOR_ROLES` đọc thành "mọi người ở bàn bác sĩ",
tức một tập **rộng hơn**. Trình duyệt hiểu theo nghĩa rộng và vẽ nút "Chỉ định XN" /
"Duyệt kết quả" cho TKYK (thư ký y khoa), người sau đó **nhận 403** từ `_ORDER_GUARD` /
`_REVIEW_GUARD` ở `lab.py:47,57`.

> Chỉ định xét nghiệm và duyệt kết quả là hành vi mà một thư ký y khoa không được làm, nên
> TKYK **cố ý vắng mặt** trong `PHYSICIAN_ROLES`.

#### `RoleGuard` là lớp, không phải closure

`identity.py:461-467`: viết thành lớp để **đọc lại được cửa gác** — test kiểm được một
router cho phép những vai nào mà không phải chạy HTTP, và tập ấy vẫn đối chiếu được với
`roles.ts` bên frontend. Toàn hệ có 46 lời gọi `require_role(...)` trong `api/v1/**`, ví
dụ `_CONSOLE_GUARD = require_role(ClinicRole.MANAGEMENT)` (`console.py:25`),
`_SIGN_GUARD = require_role(ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR)`
(`clinical_sign.py:30`).

---

### 4.11. `api/auth.py` — cửa gác API key cho toàn ứng dụng (124 dòng)

| Thành phần | Giải thích |
|---|---|
| `EXEMPT_PATHS` | `/health`, `/health/db`, `/docs`, `/openapi.json`, `/redoc` |
| `API_KEY_HEADER` / `ENV_VAR_NAME` / `APP_ENV_VAR_NAME` | `X-API-Key` / `BACKEND_API_KEY` / `APP_ENV` |
| `UNPROTECTED_DEV_ENVIRONMENTS` | `{dev, development, local, test, testing}` |
| `_is_exempt(path)` | Khớp danh sách, cộng thêm mọi thứ dưới `/docs/`, `/redoc/` (Swagger tải asset ở sub-path) |
| `api_key_middleware(request, call_next)` | Chặn mọi route không miễn trừ trên header `X-API-Key` |

Hợp đồng, theo đúng thứ tự trong code:

1. Path miễn trừ → qua thẳng (load balancer, healthcheck của Docker không mang secret).
2. `BACKEND_API_KEY` **chưa đặt** và `APP_ENV` **không** nằm trong danh sách dev/test →
   trả **503 `SERVER_MISCONFIGURED`**.
   > Một sai sót khi triển khai không bao giờ được phép lặng lẽ tắt xác thực
   > (`auth.py:16`). Chú ý: môi trường **rỗng hoặc không rõ** cũng bị coi là production.
3. Chưa đặt nhưng đúng là dev/test → cho qua kèm log WARNING `auth_middleware_disabled`.
4. Đã đặt: thiếu header → **401**; sai giá trị → **403**; đúng → đi tiếp.

So sánh bằng `hmac.compare_digest` (`auth.py:117`) — **thời gian hằng định**, để không dò
được khoá qua kênh phụ thời gian.

---

### 4.12. `api/middleware.py` — bốn lớp bọc quanh mọi request (266 dòng)

| Lớp / hàm | Giải thích |
|---|---|
| `CSKH_UPLOAD_MAX_BODY_BYTES` | `MAX_BYTES_KET_QUA_UPLOAD + 1MB` — chừa chỗ cho boundary multipart và các field UUID |
| `CskhUploadSizeLimitMiddleware` | Middleware ASGI thuần: chặn body quá cỡ **ngay khi đang nhận** |
| `._reject(...)` | Trả 413 `PAYLOAD_TOO_LARGE` |
| `.__call__(scope, receive, send)` | Chỉ can thiệp đúng `POST /api/v1/cskh/ket-qua/tep`; kiểm `Content-Length` rồi đếm byte thật |
| `request_id_ctx` / `current_request_id()` | ContextVar giữ request id cho các middleware bên trong |
| `RequestIdMiddleware` | Nhận hoặc sinh `X-Request-ID`, bind vào structlog, echo lại ở response |
| `DbErrorMiddleware` | Bắt lỗi **kết nối** DB → 503 kèm `Retry-After: 5` |
| `TimingMiddleware` | Đo thời gian + status, ghi vào ring buffer telemetry |

#### Thứ tự middleware — bài học đắt nhất của file này

`middleware.py:15-28` và `main.py:132-149` kể cùng một chuyện. `Starlette.add_middleware`
làm `user_middleware.insert(0, …)`, nên **cái thêm SAU CÙNG lại nằm NGOÀI CÙNG**. Suốt ba
tháng `main.py` thêm theo thứ tự đọc xuôi và nhận đúng ngăn xếp ngược:

```
DbErrorMiddleware → api_key → Timing → RequestId → routes     # SAI
```

Hậu quả: Timing nằm **bên trong** cửa gác API key, nên đúng thứ nó sinh ra để nhìn — cơn
lũ request bị từ chối — lại là thứ duy nhất nó không thấy; và RequestId nằm trong cùng,
nên **mọi 401/403/503 đi ra không có header `X-Request-ID`** và mọi dòng log xác thực
không có `request_id`.

Bản đúng, đăng ký **ngược** ở `main.py:144-149`, cho ngăn xếp ngoài → trong:

```
RequestIdMiddleware → TimingMiddleware → CskhUploadSizeLimitMiddleware
  → api_key_middleware → DbErrorMiddleware
```

**Vì sao `DbError` trong cùng chứ không ngoài cùng:** nó biến một kết nối chết thành một
*response* 503. Nằm trong cùng, Timing thấy `status=503` và ghi đúng. Nằm ngoài cùng,
ngoại lệ vẫn đang bay khi khối `finally` của Timing chạy, và bộ đệm sẽ ghi 500 cho thứ mà
client nhận được là 503.

`test_middleware_order` ghim ngăn xếp này lại, "để người tiếp theo thêm middleware biết
được từ một bài kiểm đỏ chứ không phải từ một buổi dò lỗi".

#### `request_id_ctx` — vì sao phải là ContextVar

Telemetry trước đây đọc `request.headers.get("X-Request-ID")`, mà header đó chỉ có khi có
proxy phía trước gửi. Chạy cục bộ và sau Caddy thì **không ai gửi**, nên mọi mục trong
feed lỗi mang `request_id=None` — trong khi màn ops in "dùng mã này để tra trong log" ngay
cạnh một giá trị nó chưa từng có. Id sinh ra không nhét ngược vào `request.headers` được
(bất biến), nên nó đi bằng ContextVar; `BaseHTTPMiddleware` chạy app phía dưới trong một
task con **kế thừa contextvars**, nên middleware trong đọc được thứ middleware ngoài đặt
(`middleware.py:143-150`).

#### `CskhUploadSizeLimitMiddleware` — chặn trước khi parse

Code endpoint chỉ chạy **sau khi** Starlette đã parse xong toàn bộ multipart vào một file
đệm. Vì thế trần dung lượng phải nằm ở đây: bọc `receive`, đếm byte, quá ngưỡng thì trả
`{"type": "http.disconnect"}` để dừng parser ngay. Starlette sẽ biến sự kiện ấy thành 400,
nên middleware **đệm response lại** (`buffered_send`) rồi thay bằng **413 đúng sự thật**.

#### `TimingMiddleware` — bắt cả ngoại lệ chưa xử lý

```python
        except Exception as exc:
            kind = type(exc).__name__
            detail = str(exc)
            raise
        finally:
            telemetry.record(route=route_template(request), ..., status=status, ...)
```

`status` khởi tạo bằng 500 và chỉ được ghi đè khi có response. Nhánh `except` không nuốt
lỗi (nó `raise` lại ngay) — nó chỉ ở đó để **ghi lại** loại ngoại lệ, vì "một ngoại lệ
chưa xử lý là thứ quan trọng nhất bộ đệm này có thể giữ, mà lại là thứ nếu không có nhánh
này sẽ không bao giờ được ghi: response không bao giờ được dựng, nên đường bình thường
phía trên không chạy".

---

### 4.13. `api/rate_limit.py` — hạn mức cho các thao tác đắt tiền (141 dòng)

| Thành phần | Giải thích |
|---|---|
| `InMemoryRateLimiter(scope, limit, window_seconds, max_buckets=10_000, clock=monotonic)` | Cửa sổ trượt theo **từng nhân viên, từng phòng khám** |
| `.bucket_count` | Số bucket đang giữ (quan sát) |
| `.reset()` | Xoá sạch — chỉ cho test và thao tác vận hành có chủ đích |
| `.__call__(identity)` | Dependency: tiêu một lượt hoặc từ chối trước khi làm việc tốn kém |
| `._consume(identity, now)` | Trả `retry_after` (giây) nếu vượt, `None` nếu còn quota |
| `._drop_expired_buckets(cutoff)` | Dọn bucket đã hết hạn |

Khoá bucket là `f"{identity.clinic_id}:{identity.staff_id}"` — **một tenant không tiêu
được hạn mức của tenant khác, và một NAT dùng chung của phòng khám không làm cả phòng bị
phạt** (`rate_limit.py:5-6`).

**Fail CLOSED khi hết chỗ:** bảng bucket đầy → 429 `rate_limit_capacity_exhausted`, không
cho qua. Lý do nêu ở `rate_limit.py:8-11`: ở đây mỗi lời gọi lọt lưới là **tiền thật**
(LLM, phiên âm giọng nói). Đây là điểm đối lập có chủ ý với `runaway_guard` (mục 4.14) —
hãy đọc hai mục cạnh nhau.

Lỗi nội bộ của chính bộ hạn mức (kể cả đồng hồ trả giá trị không hữu hạn) → **503**, không
phải 500, và có log `rate_limit_internal_failure`.

---

### 4.14. `api/runaway_guard.py` — trần rộng, để LỘ ra bug chứ không để chặn người (266 dòng)

| Thành phần | Giải thích |
|---|---|
| `DEFAULT_CEILING = 400` | Trần request/phút cho mỗi nhân viên |
| `DEFAULT_WINDOW_SECONDS = 60` | Cửa sổ đếm |
| `_WARN_EVERY_SECONDS = 60.0` | Mỗi actor chỉ cảnh báo một lần trong một cửa sổ |
| `RunawayRequestGuard(ceiling, window_seconds, max_buckets=4096, clock)` | Bộ đếm theo `clinic_id:staff_id` |
| `.bucket_count`, `.reset()` | Như ở rate_limit |
| `.__call__(request, identity)` | Đếm; cảnh báo ở **nửa trần**; 429 khi **vượt** trần |
| `._record(key, now)` | Trả `(count, should_warn)` |
| `._evict_expired(cutoff)` | Dọn bucket cũ |
| `_guard` | **Một** instance dùng chung toàn tiến trình |
| `runaway_guard(request, identity)` | Dependency chuẩn — danh tính qua `get_current_identity` |
| `runaway_guard_cho_ca_man_hinh(request, identity)` | Bản **không** chặn vai DISPLAY — danh tính qua `_resolve_identity` |

**Vì sao đây không phải "thêm một rate limiter".** `rate_limit` bảo vệ thứ tốn tiền/CPU
mỗi lời gọi; các endpoint nghiệp vụ là bài toán khác mặc cùng bộ đồ: mạng nội bộ, có xác
thực, khoảng 35 người mỗi người chạm màn hình vài lần một phút.

> Một con người không thể tạo ra một trăm request mỗi phút. Thứ làm được điều đó là một
> **bug** — gần như luôn là một `useEffect` bắn lại trên chính dependency nó vừa set, hoặc
> một vòng retry không có backoff (`runaway_guard.py:9-13`).

Và từ đó ra thiết kế: **trần chặt sẽ CHE bug đi.** Vòng lặp vẫn chạy, server lặng lẽ từ
chối phần lớn, màn hình nửa chạy nửa không, và không ai đi điều tra vì chẳng có gì trông
đủ hỏng. Phòng khám chỉ *cảm thấy chậm*. Nên trần được đặt **rất xa mức người dùng**, và
vượt trần được coi là **bằng chứng**, không phải hành vi lạm dụng.

**Con số 400 có lịch sử** (`runaway_guard.py:68-82`):

> ĐO LẠI 10/08/2026 — TRẦN CŨ 120 CHẶN NGƯỜI THẬT. Quang bấm các nút dưới bước check-in và
> nhận "lỗi 429" giữa chừng; log staging đếm được **28 lượt bị từ chối trong 40 phút**,
> riêng lúc 09:43:13 có **BẢY lời gọi `/api/v1/me` trong 0,4 giây**.

Sai lầm của con số cũ nằm ở tiền đề "một người làm 20 request/phút" — đúng với **người**,
sai với **màn hình**: mỗi cú bấm ở màn CSKH ghi một dòng rồi gọi `router.refresh()`, và
một lượt dựng lại cây server component kéo theo `/me`, `/appointments/policy`,
`/cskh/recall-jobs`, `/appointments/week`, `/visits/progress`… Một thao tác của người hoá
ra sáu bảy lượt gọi. Chú thích còn dặn: **nếu vẫn gặp 429 khi dùng bình thường thì ĐỪNG
nâng tiếp** — lúc ấy đúng là có vòng lặp, và dòng cảnh báo ở nửa trần đã ghi sẵn tên đường
dẫn gây ra nó.

**Fail OPEN khi hết bucket** — ngược hẳn `rate_limit`:

```python
                if len(self._hits) >= self.max_buckets:
                    logger.error("runaway_guard_capacity_exhausted")
                    return 0, False
```

> Bộ đếm này tồn tại để *lộ ra* một bug, không phải để đứng giữa một điều dưỡng và một hồ
> sơ bệnh nhân — từ chối một request lâm sàng vì một bảng sổ sách đầy sẽ là sự cố tệ hơn
> cái nó ngăn được. (`rate_limit.py` fail **CLOSED** vì lý do ngược lại và cũng đúng: ở
> đó, cho qua là mất tiền thật ở mỗi lời gọi.) — `runaway_guard.py:175-180`

**Cảnh báo ở NỬA trần**, không phải ở trần: tới lúc chạm trần thì vòng lặp đã đang bị từ
chối rồi, còn khoảnh khắc hữu ích để phát hiện là **sớm hơn — khi các lượt ghi còn đang
lọt xuống database**.

#### Hai cái bẫy FastAPI được ghi lại ngay trong file

**(a) Dependency phải là HÀM, không phải instance** (`runaway_guard.py:216-234`).
`Depends(_guard)` trông tương đương nhưng không phải. Module có
`from __future__ import annotations`, nên mọi annotation là **chuỗi** lúc chạy. Để giải
chúng FastAPI cần globals của module định nghĩa, lấy qua `call.__globals__` — một thuộc
tính mà **instance của lớp không có**. Annotation `request: Request` do đó vẫn là chuỗi
`"Request"`, FastAPI không nhận ra nó là request ASGI và coi là **query parameter**. Mọi
endpoint có guard trả về:

```
422 {"detail":[{"loc":["query","request"],"msg":"Field required"}]}
```

`RoleGuard` là dependency dạng instance nhưng sống sót, chỉ vì tham số duy nhất của nó
mang sẵn `Depends(...)` làm giá trị mặc định — FastAPI định tuyến được mà không cần kiểu.

**(b) Vì sao phải có `runaway_guard_cho_ca_man_hinh`** (`runaway_guard.py:249-264`).
`runaway_guard` lấy danh tính qua `get_current_identity`, mà hàm đó **từ chối vai
DISPLAY**. Vì bộ đếm gắn ở **tầng router** (`_GUARDED` trong `main.py:162`), nó chạy trước
mọi endpoint — nên `/api/v1/me` trả **403 cho cái tivi** dù chính endpoint ấy đã khai
`get_display_identity`.

> Rất khó lần ra: nhìn vào mã của endpoint không thấy gì sai, thứ từ chối nằm ở **tham số
> mặc định của một dependency khai ở file khác**.

Bản thứ hai dựng danh tính bằng `_resolve_identity` — đủ để **đếm** (bộ đếm hỏi "ai đang
gọi", không hỏi "ai được phép"), phần phân quyền để endpoint tự lo. Và chú thích dặn
**đừng sửa `runaway_guard` gốc**: hàng chục bài kiểm ghi đè `get_current_identity` và sẽ
ngừng có tác dụng.

---

### 4.15. `api/idempotency.py` — chống bấm hai lần (274 dòng)

| Thành phần | Giải thích |
|---|---|
| `HEADER_NAME` | `Idempotency-Key` — **tuỳ chọn**; không gửi thì request chạy bình thường |
| `KEY_TTL_HOURS=24` | Bao lâu thì một khoá đã hoàn tất hết hiệu lực |
| `PROCESSING_TTL_MINUTES=5` | Hợp đồng thuê của một chỗ giữ đang xử lý |
| `MAX_KEY_LENGTH=200` | Khoá dài hơn → `ConflictError` |
| `IdempotencyGuard` | dataclass frozen: `key, endpoint, actor_id, cached_response, _acquired` |
| `.is_replay` | `cached_response is not None` |
| `.acquire(pool, actor_id)` | Chiếm khoá **nguyên tử**, hoặc nạp lại response đã hoàn tất |
| `.save(pool, body, status_code)` | Ghi response, chuyển `PROCESSING → COMPLETED` |
| `.release(pool)` | **Trả khoá lại** khi thao tác bị từ chối |
| `tra_khoa_neu_bi_tu_choi(idem, pool)` | Context manager bọc thân handler, tự `release` khi lỗi 4xx |
| `idempotency_guard(request)` | Dependency dựng guard từ header; `endpoint = f"{method} {path}"` |

`acquire` đi ba nước, theo đúng thứ tự:

1. `INSERT … ON CONFLICT (key, endpoint, actor_id) DO NOTHING RETURNING key` — chiếm chỗ
   nguyên tử ở trạng thái `PROCESSING`. Có `RETURNING` nghĩa là ta là người đầu tiên.
2. `UPDATE … WHERE (PROCESSING và quá 5 phút) OR (COMPLETED và quá 24 giờ)` — **thu hồi**
   một chỗ giữ do tiến trình chết bỏ lại, hoặc một cache đã hết hạn.
3. Còn lại thì `SELECT`: nếu `COMPLETED` → trả `cached_response` (đây là replay); nếu vẫn
   đang `PROCESSING` → `ConflictError` 409.

`actor_id` là **một phần của phạm vi duy nhất** — cùng một chuỗi khoá do hai người gửi là
hai chỗ giữ khác nhau.

#### `release` — sự cố staging 13/08/2026

Khoá bị chiếm **trước khi** handler chạy. Nếu handler từ chối vì lý do nghiệp vụ, chỗ giữ
ấy không còn mô tả điều gì đang xảy ra, nhưng vẫn nằm đó tới hết 5 phút. Chú thích
`idempotency.py:206-215` chép nguyên nhật ký:

```
08:08:23  422  "Chưa có tệp kết quả nào được xác nhận đã gửi…"
08:08:30  422  cùng lý do
08:08:35  409  "Idempotency-Key này đang được xử lý; vui lòng thử lại"
08:08:41  409  cùng câu
```

> Từ lần thứ ba trở đi, câu người dùng **cần** nghe bị thay bằng câu nói về cơ chế bên
> trong. Người trực đọc thành "máy đang bận" rồi bấm lại, và mỗi lần bấm lại chỉ nhận đúng
> câu ấy cho tới khi hết 5 phút. Lúc đo có **8 khoá kẹt** ở chính đường này, cái lâu nhất
> **1 ngày 5 giờ**.

Và ranh giới quan trọng: **chỉ trả khoá khi lỗi 4xx**. 5xx nghĩa là không ai biết handler
đã ghi tới đâu — giữ khoá lại mới đúng, vì lần gửi lại có thể tạo bản thứ hai. Đó là ranh
giới giữa *"máy chủ từ chối"* và *"máy chủ hỏng"*.

`tra_khoa_neu_bi_tu_choi` gói đúng luật ấy thành một context manager, đặt ở đây thay vì
lặp `try/except` trong từng router — bốn đường đang dùng khoá (đặt lịch, thanh toán, work
item, sổ chạm CSKH) có cùng hình dạng, "và đường nào quên bọc thì lỗi quay lại y như cũ mà
không ai thấy".

---

### 4.16. `main.py` — dựng app, gắn router, dịch lỗi database (419 dòng)

| Thành phần | Giải thích |
|---|---|
| `setup_logging()` / `init_sentry()` | Gọi **ở mức module**, trước khi tạo `FastAPI()` (dòng 75, 77) |
| `lifespan(app)` | Vòng đời: bể DB → change broker → checkpointer → LLM client → transcriber → orchestrator |
| `app` | `FastAPI(title="ClinicAI", version="0.1.0", lifespan=lifespan)` |
| Khối `add_middleware` | Đăng ký **ngược** (dòng 144-149) — xem mục 4.12 |
| `_GUARDED` | `[Depends(runaway_guard)]`, gắn cho **mọi router đã xác thực** |
| `exclusion_violation_handler` | `ExclusionViolationError` → 409, câu chữ theo **tên ràng buộc** |
| `unique_violation_handler` | `UniqueViolationError` → 409, mặc định mơ hồ có chủ ý |
| `clinicai_exception_handler` | Mọi `ClinicAIBaseException` → `exc.status_code` + `exc.error_code` |
| `unhandled_exception_handler` | Mọi `Exception` → 500, stack trace **chỉ vào log**, không ra client |

#### `lifespan` — thứ tự dựng và tháo

```python
    app.state.db_pool = await create_pool()
    app.state.change_broker = ChangeBroker(os.environ["DATABASE_URL"])
    await app.state.change_broker.start()
    try:
        async with AsyncExitStack() as stack:
            checkpointer = await stack.enter_async_context(make_checkpointer())
            llm_client = AnthropicClient()
            stack.push_async_callback(llm_client.close)
            ...
    finally:
        await app.state.change_broker.stop()
        await close_pool(app.state.db_pool)
```

1. Bể DB trước — mọi thứ còn lại phụ thuộc vào nó.
2. `AsyncExitStack` để **một chỗ tháo cho nhiều tài nguyên**, tháo theo thứ tự ngược.
3. `PhoWhisperTranscriber()` dựng nhẹ — model nạp lazy ở lần transcribe đầu, "nên app boot
   được kể cả khi chưa cài model" (dòng 99-101).
4. Khối `finally` nằm **ngoài** `AsyncExitStack`, nên broker và bể DB được đóng kể cả khi
   dựng orchestrator hỏng.

#### Gắn router — ba trường hợp ngoại lệ đáng nhớ

- **`auth_router`: không có `_GUARDED`.** Đây là endpoint duy nhất không đòi token, vì nó
  là nơi *cấp* token. `runaway_guard` đếm **theo nhân viên**, mà ở đây chưa biết người gọi
  là ai — đó chính là việc endpoint này đang làm. Chống dò mật khẩu nằm trong
  `auth_service` (đếm lần sai + khoá tạm, lưu ở database) — `main.py:165-171`.
- **`identity_router`: dùng `runaway_guard_cho_ca_man_hinh`.** `/api/v1/me` phải trả lời
  được cho tài khoản màn hình TV, nếu không nó đăng nhập xong bị đá về trang đăng nhập.
- **`consent_router` đăng ký TRƯỚC `patients_router`.** `patients.py` dùng `{id:uuid}` nên
  literal không bị nuốt, "nhưng lần trước `/appointments/policy` đã biến mất đúng theo
  kiểu này — đăng ký đường dẫn cụ thể trước đường dẫn có tham số không tốn gì".
- **Ba router cố ý mở** (không `_GUARDED`): `health_router`, `catalog_router` (danh mục
  phường/xã toàn quốc), `display_router` (bảng gọi số phòng chờ).

Về `events_router`, chú thích `main.py:180-189` giải thích một quyết định bảo mật: trình
duyệt **không** gọi thẳng vào đây, vì `EventSource` không đặt được header. Nó gọi route
Next `/api/events/stream`, route ấy chạy trên máy chủ và gắn Bearer token + `X-API-Key` rồi
truyền dòng về.

> ĐÃ CÂN NHẮC VÀ BỎ: cho token đi qua query string. Làm thế là ghi token vào log truy cập
> của mọi proxy trên đường — một thứ đọc được, sống lâu, và đủ để đóng giả người dùng.

#### `exclusion_violation_handler` — một câu cho mọi ràng buộc là một câu sai cho gần hết

```python
    constraint = getattr(exc, "constraint_name", None) or ""
    known = {
        "slot_override_no_overlap": "Đã có một điều chỉnh khác phủ khung giờ này — …",
        "doctor_override_no_overlap": "Đã có một luật khác phủ khung giờ này — …",
    }
    message = known.get(constraint, "Bản ghi xung đột với một bản ghi khác"
        + (f" (ràng buộc {constraint})" if constraint else "") + ".")
```

Handler này **từng luôn** trả "Lịch hẹn xung đột khung giờ với appointment khác". Đúng cho
`appointment_no_doctor_overlap`, và sai cho ba ràng buộc EXCLUDE còn lại — trong đó có hai
ràng buộc **luật đặt lịch**.

> Trưởng ca lưu một luật cho BS Thành nhận về một câu nói về LỊCH HẸN, rồi đi tìm một lịch
> hẹn không tồn tại. Chúng tôi mất một buổi vì đúng câu này (`main.py:293-299`).

Tên ràng buộc là thứ **duy nhất** phân biệt được, nên nó quyết định câu trả lời. Ràng buộc
lạ thì nói thẳng là không nhận ra, kèm tên — *mơ hồ mà đúng còn hơn cụ thể mà bịa*.

Và `appointment_no_doctor_overlap` **không còn** trong danh sách, có kiểm chứng: đo bằng
`pg_constraint` ngày 05/08 chỉ còn hai ràng buộc EXCLUDE, cả hai trên bảng override. Nó
cũng **không nên** được dựng lại: EXCLUDE cấm **mọi** cặp chồng lấn, tức trần bằng 1, trong
khi luật phòng khám là **2 chỗ đặt + 1 vãng lai** mỗi bác sĩ mỗi khung
(`clinic_policy.py:31-32`) — ba lịch cùng bác sĩ cùng giờ là **hợp lệ**. Trần theo số đếm
phải là trigger, và đã có: `enforce_slot_capacity`.

#### `unique_violation_handler` — mặc định mơ hồ có chủ ý

Tên một ràng buộc UNIQUE thường **lộ cấu trúc bảng và cả cách định danh**
(`staff_phone_key` nói rằng nhân viên được phân biệt bằng số điện thoại). Khác với ràng
buộc chồng lấn — nơi chi tiết giúp người dùng xử lý được — ở đây chi tiết không giúp thêm
gì. Ngoại lệ duy nhất là `uq_appointment_patient_slot_live`, thứ chỉ bắn khi hai request
thật sự đồng thời đặt cùng một bệnh nhân vào cùng một giờ (tức cú bấm hai lần đã lọt qua
cả chốt trình duyệt lẫn `Idempotency-Key`); người bấm cần biết **lịch đã có**, không cần
biết tên chỉ mục.

---

### 4.17. Biến môi trường backend đọc thật sự

Đọc từ `os.environ` trong `src/clinicai/**` (không có lớp Settings tập trung):

| Biến | Ai đọc | Bắt buộc? | Ghi chú |
|---|---|---|---|
| `DATABASE_URL` | `database.py:43`, `main.py:89` | **Có** (`KeyError` nếu thiếu) | Chấp nhận cả `postgresql+asyncpg://`, được `normalize_dsn` cắt |
| `APP_ENV` | `auth.py:80`, `logging.py:144`, `sentry.py:37` | Không, mặc định `development` | Rỗng/không rõ ⇒ `auth.py` coi như **production** |
| `BACKEND_API_KEY` | `auth.py:78` | Có ở prod/staging | Thiếu ở môi trường không-dev ⇒ **503 toàn API** |
| `SUPABASE_URL` | `identity.py:190` | Có khi dùng JWKS | Chỉ đọc khi **không** có `SUPABASE_JWT_SECRET` |
| `SUPABASE_JWT_SECRET` | `identity.py:196` | Không | Có ⇒ HS256; không ⇒ ES256/RS256 qua JWKS |
| `LOG_LEVEL` | `logging.py:151` | Không, mặc định `INFO` | |
| `SENTRY_DSN` | `sentry.py:27` | Không | Rỗng ⇒ tắt Sentry êm |
| `IMAGE_TAG` | `sentry.py:38` | Không, mặc định `unknown` | Thành `release=clinicai@<tag>` |
| `DEFAULT_LOCATION_ID` | `main.py:103` | Không | UUID cơ sở mặc định cho orchestrator scheduling |
| `OPS_STATUS_FILE`, `MEDIA_ROOT`, `MEDIA_*` | ops/media service | Đặt trong compose | `/run/clinicai-ops/status.json`, `/var/lib/clinicai/media` |
| `CHECKPOINTER_BACKEND` | orchestrator | Không, compose đặt `postgres` | |
| `ENABLE_AI_ORCHESTRATOR`, `POS_ADAPTER`, `NOTIFICATION_RELAY_ENABLED` | các dịch vụ tuỳ chọn | Không | Cờ bật/tắt tính năng |
| `RABBITMQ_URL`, `WORKER_QUEUE`, `WORKER_HEARTBEAT_FILE` | `worker` | Chỉ khi `--profile workers` | |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_CLINIC_ID`, `ZALO_ZNS_ACCESS_TOKEN` | thông báo | Không | |

Phía `docker-compose.yml`, dịch vụ `api` nạp toàn bộ secret qua
`env_file: ["${CLINIC_ENV_FILE:?…}"]` — biến **bắt buộc phải khai tên file rõ ràng**, để
"một lệnh staging không nạp nhầm secret production từ một file `.env` dùng chung". Chỉ ba
biến được đặt trực tiếp trong `environment:` của `api`: `CHECKPOINTER_BACKEND`,
`OPS_STATUS_FILE`, `MEDIA_ROOT`. Healthcheck của `api` gọi **`/health/db`** chứ không phải
`/health` — "readiness, không chỉ liveness: deploy phải rollback khi backend không thật sự
chạm được Postgres".

---

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

1. **`add_middleware` đăng ký NGƯỢC.** Cái thêm sau cùng nằm ngoài cùng. Suốt ba tháng
   ngăn xếp chạy ngược ý định: Timing mù trước cơn lũ 401, và mọi 401/403/503 không có
   `X-Request-ID` (`middleware.py:15-28`, `main.py:132-149`). `test_middleware_order` ghim
   lại.
2. **`Depends(<instance>)` + `from __future__ import annotations` = 422.** Instance không
   có `__globals__` nên FastAPI không giải được annotation `request: Request` và biến nó
   thành **query param**. Phải bọc bằng một **hàm mức module**
   (`runaway_guard.py:216-234`).
3. **Guard ở tầng router chạy TRƯỚC dependency của endpoint.** `_GUARDED` dùng
   `get_current_identity`, vốn từ chối DISPLAY — nên `/api/v1/me` trả 403 cho tivi dù
   endpoint đã khai `get_display_identity`. Thứ từ chối nằm ở **tham số mặc định của một
   dependency ở file khác** (`runaway_guard.py:249-256`).
4. **Trần 120 request/phút chặn người thật.** Tiền đề "20 request/phút mỗi người" đúng với
   *người*, sai với *màn hình*: một cú bấm ở CSKH kéo theo 6–7 lời gọi qua
   `router.refresh()`. 28 lượt 429 trong 40 phút trên staging (10/08/2026). Nâng lên 400 —
   và **đừng nâng tiếp** nếu còn gặp (`runaway_guard.py:68-82`).
5. **Khoá idempotency không được trả khi handler từ chối.** Từ lần bấm thứ ba, người dùng
   nhận "Idempotency-Key đang được xử lý" thay cho lý do thật, kẹt 5 phút. Có khoá kẹt
   **1 ngày 5 giờ**. Phải dùng `tra_khoa_neu_bi_tu_choi`, và **chỉ trả khi 4xx** —
   5xx thì giữ, vì không ai biết handler đã ghi tới đâu (`idempotency.py:198-219`).
6. **Log bằng `message=` sẽ bị `[REDACTED]`.** `core/logging` coi trường `message` có cấu
   trúc là nội dung bệnh nhân. Handler `main.py` từng log
   `{"error_code": …, "message": "[REDACTED]"}` — xoá sạch đúng câu nói ràng buộc nào đã
   bắn. Dùng `reason=` (`main.py:330-334`).
7. **`normalize_dsn` phải được gọi ở CẢ HAI nơi mở kết nối.** `change_broker` lúc đầu đọc
   thẳng `DATABASE_URL`, chết ngay khi khởi động vì scheme `postgresql+asyncpg://`, và màn
   hình lặng lẽ rơi về nhịp làm mới dự phòng — không ai thấy (`database.py:23-28`,
   `change_broker.py:55-59`).
8. **`include_local_variables` mới là chỗ rò PII lên Sentry, không phải
   `send_default_pii`.** Biến cục bộ lúc nổ lỗi thường đang giữ nguyên một hàng `patient`
   (`sentry.py:56-66`).
9. **Một câu lỗi cho mọi ràng buộc EXCLUDE là sai cho gần hết.** Mất một buổi vì trưởng ca
   được báo "xung đột lịch hẹn" khi đang lưu một *luật đặt lịch* (`main.py:293-299`).
10. **`appointment_no_doctor_overlap` đừng dựng lại.** EXCLUDE ⇒ trần bằng 1, còn luật
    phòng khám là 2 đặt + 1 vãng lai. Trần theo số đếm phải là trigger
    `enforce_slot_capacity` (`main.py:306-315`).
11. **`role_from_department` không có fallback CSKH.** CSKH đọc được thông tin bệnh nhân —
    một membership NULL phải là 403, không phải một vai mặc định (`identity.py:117-124`).
12. **`PHYSICIAN_ROLES` ≠ `DOCTOR_DESK_ROLES`.** Đọc nhầm ⇒ frontend vẽ nút "Chỉ định XN"
    cho TKYK, rồi backend trả 403 (`identity.py:86-101`).
13. **Hai bộ đếm, hai hướng fail ngược nhau — có chủ ý.** `rate_limit` fail **CLOSED** (mỗi
    lời gọi là tiền thật); `runaway_guard` fail **OPEN** (không đứng giữa điều dưỡng và hồ
    sơ bệnh nhân). Đừng "thống nhất" hai chỗ này.
14. **Cả hai bộ đếm và telemetry đều PROCESS-LOCAL.** Ngày chạy nhiều bản API, trần thành
    per-replica và số liệu telemetry chỉ mô tả một tiến trình. Cả ba file đều nói thẳng
    giới hạn này thay vì để người sau tự phát hiện.
15. **`APP_ENV` rỗng bị coi là production trong `auth.py`.** Đúng theo hướng an toàn (503
    thay vì mở toang), nhưng dễ làm người mới tưởng "app hỏng" khi chạy cục bộ mà quên đặt
    biến (`auth.py:80-93`).
16. **Có hai `ValidationError` và hai lớp 404** (`core/exceptions.py` vs
    `api/exceptions.py`). Cùng gốc nên handler bắt được cả hai, nhưng `except` import nhầm
    file sẽ trượt.


---

## PHẦN 5. `booking_service.py` — TRÁI TIM CỦA HỆ THỐNG

1970 dòng, và là file duy nhất trong repo mà một dòng sai sẽ tạo ra một cái hẹn
không ai khám. Nó được port từ `src/dashboard/app/api/appointments/route.ts` —
route dày luật nhất của dashboard — và giữ nguyên cả các vết sẹo: gần như mọi
khối chú thích trong file đều ghi lại **một sự cố có thật, có ngày tháng**.

> **Câu mở đầu quan trọng nhất của cả file nằm ở docstring:** những gì
> `booking_service.py` kiểm TRƯỚC khi ghi **không phải là lưới an toàn**. Lưới
> thật là Postgres. Python kiểm sớm chỉ để đẻ ra một **câu tiếng Việt lễ tân
> hành động được** — "khung 09:15–09:30 đã đủ 2 chỗ" — thay vì một tên ràng
> buộc. (`booking_service.py:9-24`)

Hai lưới thật đó là:

| Lưới | Ở đâu | Bảo đảm gì |
|---|---|---|
| `uq_appointment_patient_slot_live` | chỉ mục duy nhất bán phần, `20260805000007` | một bệnh nhân chỉ có **một lịch còn sống** ở mỗi mốc `slot_start` |
| `enforce_slot_capacity` (trigger) | `20260714000002`, gắn lại `20260803000010` | trần số chỗ mỗi bác sĩ × khung, có `pg_advisory_xact_lock` nên **nguyên tử** |

Và một lưới **không tồn tại**, dù docstring cũ từng khai là có:
`appointment_no_doctor_overlap`. Nó bị DROP ở migration 057 và cố ý **không**
dựng lại — `EXCLUDE` cấm mọi cặp chồng lấn, tức trần bằng 1, trong khi phòng
khám cho 2 chỗ đặt + 1 vãng lai mỗi bác sĩ mỗi khung. Trần theo **số đếm** là
việc của trigger.

---

### 5.1. Hai cửa vào, và bản đồ file

Cả file chỉ có **hai** hàm công khai:

| Cửa | Hàm | Việc |
|---|---|---|
| Đặt lịch | `create(...)` (`:374`) | ghi một lịch hẹn mới |
| Vòng đời | `apply_action(...)` (`:659`) | máy trạng thái 11 hành động |

Mọi thứ còn lại là chốt chặn, dựng câu, hoặc lớp phủ. Router
(`api/v1/routers/booking.py:260`, `:453`) chỉ chuyển tham số — **không có luật
nào ở router**, đúng theo CLAUDE.md "router mỏng".

#### Nhóm hàm thuần (kiểm được không cần database)

| Hàm | Giải thích |
|---|---|
| `initial_status(auto_checkin)` (`:173`) | Lịch mới sinh ra ở trạng thái nào. Trả `CHECKED_IN` nếu vãng lai hôm nay, còn lại `CONFIRMED`. **Tách khỏi `create()` cố ý**: `create()` cần mười thứ mới chạy được, còn luật này phải kiểm được mà không cần dựng cả phòng khám |
| `resolve_action(action)` (`:327`) | Tra `TRANSITIONS`, `KeyError` → `ValidationError`. Thuần, nên **máy trạng thái kiểm được bằng một dict** thay vì bằng một Postgres |
| `is_walkin(channel)` (`:335`) | `channel.strip().upper() == "WALK_IN"`. Khoan dung với khoảng trắng/hoa thường — bài kiểm `test_walkin_detection_is_forgiving` canh đúng chỗ này |
| `is_dead(status)` (`:339`) | Trạng thái này còn giữ ghế không |
| `_chan_dat_vao_qua_khu(slot_end)` (`:221`) | Chặn đặt vào khung đã qua. Xem 5.4 |
| `_hhmm(moment)` (`:362`) | `datetime` → `"09:15"` theo giờ phòng khám. Mọi câu tiếng Việt trong file đi qua đây |
| `_log(conn, …)` (`:1941`) | Ghi `event_log`: `payload` (việc), `metadata` (ai + vai + `auth_user_id`), `source` (đường vào). Quy tắc của Quang: *"làm gì cũng sinh ra event có route này kia"* |
| `Transition` (dataclass, `:191`) | `to_status`, `from_statuses`, `allowed_roles`, `event_type`, `owner_only` |

#### `_chan_dat_vao_qua_khu` — một hàm 3 dòng, ba quyết định

```python
def _chan_dat_vao_qua_khu(slot_end: datetime) -> None:
    if slot_end <= datetime.now(timezone.utc):
        raise ValidationError("Khung giờ này đã qua — chọn một khung còn ở phía trước.")
```

1. **Trước đây KHÔNG có chốt nào** — không backend, không trình duyệt. Đo ngày
   06/08: lúc 16:40 vẫn đặt được lịch cho 16:20, server trả **201**. Lịch ấy rơi
   vào lưới hôm nay như một cái hẹn bình thường, và bảng gọi số đưa người đó vào
   làn "đến muộn" — **một người chưa bao giờ đến**.
2. **Đo bằng `slot_end`, không phải `slot_start`.** Khung 18:00–18:15 lúc 18:05
   thì CHƯA qua: khách vãng lai bước vào giữa khung phải xếp được vào chính
   khung đang chạy, và lịch của họ tạo với `slot_start = bây giờ`. Chặn theo
   `slot_start` sẽ giết đường đó mỗi khi đồng hồ máy chủ nhanh vài giây.
3. **So bằng giờ có múi.** `slot_end` là `timestamptz`; một mốc giờ trần sẽ được
   hiểu theo múi giờ của tiến trình — đúng ở máy này, lệch bảy tiếng ở máy khác.

⚠️ Bài kiểm `test_ca_dat_moi_lan_doi_lich_deu_di_qua_chot_nay` đếm số lần chuỗi
`_chan_dat_vao_qua_khu(` xuất hiện trong module phải `>= 3` (định nghĩa + 2 nơi
gọi). Vì **khoá cửa trước mà quên cửa sau** thì vẫn dời được một lịch về hôm qua
bằng `reschedule`.

---

### 5.2. Máy trạng thái lịch hẹn

#### 5.2.1. Các tập trạng thái

| Tập | Thành viên | Ý nghĩa |
|---|---|---|
| `_ALIVE` (`:203`) | `SCHEDULED`, `CSKH_CONFIRMED`, `CONFIRMED`, `CHECKED_IN` | còn giữ ghế |
| `_PRE_ARRIVAL` (`:204`) | `SCHEDULED`, `CSKH_CONFIRMED`, `CONFIRMED` | chưa tới nơi |
| `_AWAITING_DOCTOR` (`:209`) | `SCHEDULED`, `CSKH_CONFIRMED` | bác sĩ chưa nhận |
| `_DECLINABLE` (`:212`) | `_AWAITING_DOCTOR` + `CONFIRMED` | bác sĩ từ chối được |
| `DEAD_STATUSES` (`:116`) | `CANCELLED`, `NO_SHOW`, `DOCTOR_DECLINED` | **không giữ ghế nữa** |

> `SCHEDULED` và `CSKH_CONFIRMED` là **trạng thái CŨ, không phải trạng thái
> chết**. Lịch mới vào thẳng `CONFIRMED`, nhưng prod còn **23 dòng `SCHEDULED` +
> 2 dòng `CSKH_CONFIRMED`** đặt từ trước, và chúng vẫn phải khám được, đổi được,
> huỷ được. Xoá khỏi các tập này là làm 25 lịch hẹn thật **kẹt cứng**.
> (`:205-208`)

`DEAD_STATUSES` là con số ba xuất hiện ở **năm** nơi và phải khớp nhau: Python
(`:116`), trigger `enforce_slot_capacity`, `slot_seats_used`, chỉ mục duy nhất
bán phần, và `_patient_double_booked`. Lệch một mã ở một nơi là ghế bị đếm hai
lần hoặc không bao giờ được trả lại.

#### 5.2.2. Bảng `TRANSITIONS` đầy đủ (`:243-324`)

| Hành động | Từ trạng thái | → Đích | Vai được làm | `owner_only` | `event_type` |
|---|---|---|---|---|---|
| `confirm` | `SCHEDULED`, `CSKH_CONFIRMED` | `CONFIRMED` | `DOCTOR_ROLES` | ✅ | `appointment.confirmed` |
| `decline` | `SCHEDULED`, `CSKH_CONFIRMED`, `CONFIRMED` | `DOCTOR_DECLINED` | `DOCTOR_ROLES` | ✅ | `appointment.declined` |
| `complete` | **chỉ** `CHECKED_IN` | `COMPLETED` | `DOCTOR_ROLES` ∪ `MANAGE_ROLES` | ✅ | `appointment.completed` |
| `checkin` | `SCHEDULED`, `CSKH_CONFIRMED`, `CONFIRMED` | `CHECKED_IN` | `CHECKIN_ROLES` | — | `appointment.checked_in` |
| `undo_checkin` | `CHECKED_IN` | `CONFIRMED` | `CHECKIN_ROLES` | — | `appointment.checkin_undone` |
| `cskh_confirm` | **chỉ** `SCHEDULED` | `CSKH_CONFIRMED` | `INTAKE_ROLES` | — | `appointment.cskh_confirmed` |
| `cancel` | `_ALIVE` (4) | `CANCELLED` | `MANAGE_ROLES` | — | `appointment.cancelled` |
| `no_show` | `_PRE_ARRIVAL` (3) | `NO_SHOW` | `CHECKIN_ROLES` | — | `appointment.no_show` |
| `reassign` | **chỉ** `DOCTOR_DECLINED` | `CONFIRMED` | `MANAGE_ROLES` | — | `appointment.reassigned` |
| `assign_doctor` | `_ALIVE` (4) | `__keep__` (giữ nguyên) | `MANAGE_ROLES` | — | `appointment.doctor_assigned` |
| `reschedule` | `_ALIVE` (4) | `__keep__` (giữ nguyên) | `MANAGE_ROLES` | — | `appointment.rescheduled` |

Thành phần các nhóm vai:

| Nhóm | Thành viên | Vì sao |
|---|---|---|
| `DOCTOR_ROLES` (`:141`) | = `DOCTOR_DESK_ROLES` = `DOCTOR`, `ULTRASOUND_DOCTOR`, `TKYK` | Hành động lịch hẹn là **việc bàn giấy** — thư ký xác nhận và đóng hộ bác sĩ. Trước đây tập này được khai lại tại chỗ, lệch đúng một phần tử (`TKYK`) so với `identity.py`. **Hai hằng số cùng tên là cách một quyền trôi mà không bài kiểm nào đỏ** |
| `MANAGE_ROLES` (`:142`) | `CSKH`, `MANAGEMENT`, `TRUONG_CA` | |
| `CHECKIN_ROLES` (`:149`) | `RECEPTION`, `MANAGEMENT`, `CSKH` | CSKH check-in được (Quang 08/08): *"sản phẩm MVP này là cskh thao tác được hết mà"* — và đi **đúng đường thật** (`_check_in` + `_open_visit`), không phải một cờ riêng chỉ màn CSKH thấy |
| `INTAKE_ROLES` (`:160`) | `CSKH`, `RECEPTION`, `MANAGEMENT`, `TRUONG_CA` | |
| `PHYSICIAN_ONLY_OWNER_CHECK` (`:146`) | `DOCTOR`, `ULTRASOUND_DOCTOR` | Xem 5.2.4 |

#### 5.2.3. Những đường MỘT CHIỀU, và vì sao chúng một chiều

Đọc cột "Từ trạng thái" ngược lại thì thấy ngay: **không hành động nào nhận
`COMPLETED`, `CANCELLED`, `NO_SHOW` làm trạng thái nguồn.**

| Trạng thái | Có lối về không | Lý do |
|---|---|---|
| `COMPLETED` | **KHÔNG. Tuyệt đối.** | Lượt khám đã đóng. `complete` sinh event, mở nhắc tái khám, đóng `work_item`. "Mở lại" một lượt đã đóng là hỏi hệ thống nói dối về một việc đã xảy ra. Muốn khám tiếp thì **đặt một lịch mới** |
| `CANCELLED` | KHÔNG | Ghế đã trả lại cho khung. Người khác có thể đã đặt vào đó. Đặt lại = một lịch mới (và đúng như thế thì `_patient_double_booked` mới cho qua — xem 5.6) |
| `NO_SHOW` | KHÔNG | Khách không đến. Đến muộn thật thì check-in bình thường **trước khi** ai bấm `no_show`; `no_show` chỉ nhận `_PRE_ARRIVAL` |
| `DOCTOR_DECLINED` | **CÓ — đúng một lối**: `reassign` | Đây là ngoại lệ có chủ ý, và là lý do `DOCTOR_DECLINED` nằm trong `DEAD_STATUSES` mà vẫn hồi được |

Hai chi tiết dễ bỏ sót của bảng:

- **`complete` chỉ nhận `CHECKED_IN`** (`:255`): *"một bệnh nhân chưa bao giờ đến
  thì không thể đã được khám, dù bác sĩ bấm gì"*. Bài
  `test_a_patient_who_never_arrived_cannot_be_completed` canh đúng câu đó.
- **`decline` nhận cả `CONFIRMED`, nhưng `confirm` thì không** (`:211`). Bác sĩ
  từ chối được cả lịch đã chắc; "nhận" thêm lần nữa thì vô nghĩa — lịch mới sinh
  ra đã `CONFIRMED` rồi, `confirm` chỉ còn để dọn 23 dòng cũ.
- **`reassign` đưa về `CONFIRMED`, không về `SCHEDULED`** (`:296-298`): *"thoả
  thuận với bệnh nhân không mất đi khi một bác sĩ bận. Đổi bác sĩ là việc nội bộ,
  không phải lý do gọi lại bệnh nhân"*.

#### 5.2.4. `owner_only` — luật GIỮA CÁC BÁC SĨ, không phải luật chung

```python
if (
    transition.owner_only
    and identity.role in PHYSICIAN_ONLY_OWNER_CHECK
    and str(appt["doctor_id"] or "") != identity.staff_id
):
    raise SafetyGateError("Lịch hẹn này không thuộc bác sĩ")
```
(`:758-763`)

Vế giữa là bản vá, và nó đắt: **`owner_only` chỉ so `staff_id` với người CÓ ca
của mình** — tức bác sĩ thật. TKYK nhập hộ, hay nhóm vận hành đóng lượt trong
MVP tay, **không có "ca của mình" để so**; so `staff_id` với họ chỉ chặn sạch mọi
thứ. Đo được trên bản thật: **tài khoản Quản lý bấm check-out ăn ngay "Lịch hẹn
này không thuộc bác sĩ"** (`:752-757`).

> `complete` là ví dụ hoàn hảo của một quyền có **hai chiều rộng khác nhau**:
> rộng ở `allowed_roles` (`DOCTOR_ROLES | MANAGE_ROLES`, vì CSKH bấm "khách
> check-out" và lượt phải ĐÓNG THẬT, không đóng thì nhắc tái khám không bao giờ
> sinh), nhưng hẹp ở `owner_only` (bác sĩ vẫn chỉ đóng được ca của chính mình).

⚠️ Bản đầu của bản vá này chỉ mở cho `CSKH`, và **người đầu tiên ăn 403 chính là
tài khoản Quản lý đang chạy thử** (`:258-264`). Nên nay là `MANAGE_ROLES`.

---

### 5.3. `create()` — đặt một lịch hẹn (`:374`)

Thứ tự **là** luật ở đây: mọi chốt phải chạy xong trước `INSERT`, và tất cả nằm
trong **một** `conn.transaction()`.

1. **`location_id = location_id or identity.location_id`** (`:403`) — không nói
   cơ sở thì lấy **cơ sở CỦA NGƯỜI ĐẶT**, không phải cơ sở đầu tiên trong một
   danh sách. Chỉ định cơ sở khác vẫn được, chỉ là phải **cố ý**.
2. `slot_end > slot_start`, rồi `_chan_dat_vao_qua_khu(slot_end)`.
3. **Kiểm `lich_truoc_id`** (`:415-432`) — lịch tái khám phải trỏ về lịch của
   **chính khách này, chính phòng khám này**. Khoá ngoại chỉ bảo đảm id ấy *tồn
   tại*; nó không cấm trỏ sang lịch của người khác. Một mã đoán được là **một
   chuỗi lịch sử khám bị nối vào nhầm bệnh nhân**, và nó hiện ra ở ô "lịch sử các
   lần khám" như thể là sự thật. Kiểm ở đây chứ không ở màn hình: *màn hình nào
   cũng có thể quên, còn đường ghi thì chỉ có một*.
4. **`channel = raw_channel or None`** (`:449`) — xem khối chú thích `:435-448`,
   đây là một trong những bug đắt nhất file:

   > Dòng này từng là `raw_channel or "WALK_IN"`. BookingHub — màn CSKH đặt gần
   > như mọi thứ — **không gửi channel**, nên mọi lịch nó tạo được lưu là vãng
   > lai. Vãng lai rút từ pool nhỏ (`walkin_cap` = 1 ghế), nên lưới lấp đầy pool
   > ấy và để pool đặt hẹn (`regular_cap` = 2 ghế) **trống vĩnh viễn**: luật ghế
   > chạy **ngược** trên màn bận nhất phòng khám, và người thật sự bước vào thì
   > không còn ghế.

   `NULL` nói đúng một điều: "một nhân viên nhập lịch này" = ghế đặt hẹn. Cả hai
   trigger sức chứa đều coi mọi thứ khác `'WALK_IN'` là regular, nên **pre-check
   và cái net nay nói cùng một câu**.
5. **`auto_checkin`** (`:462`) = `raw_channel.upper() == "WALK_IN"` **và**
   `_is_today(slot_start)`. Hai vế, cả hai đều cần: chỉ khi WALK_IN được chọn
   **tường minh** và khung là **hôm nay**. Nếu không, một lịch tương lai, hoặc
   một lịch gọi điện không kèm channel, sẽ được check-in cho một người không có
   mặt.
6. **Mở transaction.** Từ đây tới hết bước 13 là một khối tất-cả-hoặc-không.
7. `_validate_booking_refs` — 4 câu `EXISTS` trong **một** round-trip: bệnh nhân,
   cơ sở, dịch vụ, bác sĩ có thuộc phòng khám này không.
8. **`_patient_double_booked`** → `ConflictError`. Xem 5.6.
9. Nếu có bác sĩ: `_doctor_conflict` (trần 6), rồi `_roster_warning`. Cảnh báo
   ca trực **có thể chặn hẳn** nếu `_roster_is_required` trả `True` (mặc định
   CÓ) — nếu không thì đẩy vào `warnings`.
10. **`_luat_bac_si_bat_buoc`** — trả `(câu, chặn_hẳn)`. Cùng một luật, hai mức
    độ: `chan_han=True` → `ConflictError`, ngược lại → cảnh báo.
11. `load_effective_policy(...)` → `_slot_full(...)` → `ConflictError`. Xem 5.5.
12. **`INSERT`**, bọc trong hai handler SQLSTATE (`:573-581`):
    - `ExclusionViolationError` → "Bác sĩ đã có lịch trùng khung giờ này."
    - `CheckViolationError` chứa `"Khung giờ đã đầy"` → `ConflictError` với
      **chính câu của trigger**. Nghĩa là: *trigger nguyên tử đã thắng cuộc đua
      với chúng ta*. Bất kỳ `CheckViolationError` nào khác được `raise` lại
      nguyên — nuốt nó là giấu một lỗi lược đồ.
13. `release_on_booking` (thả chỗ giữ) → `_attach_episode` → `_log` →
    nếu `auto_checkin` thì `_log` lần nữa + `_open_visit`.

Trả về `{"appointment_id", "status", "warnings"}`. `warnings` **không phải lỗi** —
lịch đã được ghi — nhưng *người đặt phải thấy điều bất thường ngay lúc đặt, không
phải lúc bệnh nhân đến* (`:652-654`).

---

### 5.4. `apply_action()` — máy trạng thái chạy (`:659`)

1. `resolve_action(action)` → `Transition` (hoặc `ValidationError`).
2. **Kiểm vai TRƯỚC KHI chạm database** (`:675`) — `SafetyGateError`. Không đọc
   lịch hẹn thì không rò rỉ cả sự tồn tại của nó cho một vai không được phép.
3. Mở transaction, `SELECT` một dòng mang theo **bốn cờ `EXISTS`** tính sẵn:
   `patient_in_clinic`, `location_in_clinic`, `service_in_clinic`,
   `doctor_in_clinic` (`:682-729`). Một round-trip cho cả năm câu hỏi.
4. Bốn câu kiểm đa-phòng-khám, **với một ngoại lệ tinh tế** (`:744-750`):
   ```python
   repairs_doctor = action in {"cancel", "reassign"} or (
       action == "reschedule" and doctor_id_provided
   )
   if not appt["doctor_in_clinic"] and not repairs_doctor:
       raise ValidationError("Bác sĩ của lịch hẹn không thuộc phòng khám này")
   ```
   > Nếu dữ liệu đã lệch (bác sĩ rời phòng khám), **cấm luôn cả đường sửa nó** là
   > khoá cứng lịch hẹn ấy vĩnh viễn. Ba hành động **đang đi sửa chính chỗ hỏng**
   > được miễn kiểm.
5. `owner_only` (5.2.4).
6. **Kiểm trạng thái nguồn** (`:765`) → `ConflictError` nói rõ trạng thái hiện
   tại, không phải "không hợp lệ".
7. `new_status` = giữ nguyên nếu `to_status == KEEP_STATUS`.
8. **Rẽ hai nhánh:**
   - `checkin` → `_check_in()` (hàm SQL có advisory lock)
   - còn lại → `_build_patch()` → `_update()`
9. `if not updated: raise ConflictError("Lịch hẹn vừa được người khác cập
   nhật…")` — `_update` có `WHERE status = ANY(from_statuses)`, nên **0 dòng
   nghĩa là ai đó đã đổi trạng thái giữa lúc ta đọc và lúc ta ghi**. Đây là
   optimistic concurrency, và câu tiếng Việt nói đúng việc phải làm: tải lại.
10. `_log(...)`.
11. Hậu quả kéo theo:
    - `checkin` → `_open_visit`
    - `action in _WORKFLOW_CANCELLING` (`undo_checkin`, `cancel`) →
      `_cancel_visit_workflow`. **`no_show` cố ý vắng mặt** (`:216-218`): khách
      chưa bao giờ đến thì chưa bao giờ có lượt khám được mở, nên không có gì để
      huỷ.
    - `doctor_id` đi từ **NULL → có người** → `_xep_vao_lich_truc(...)`
      **trong cùng transaction**.
12. **Sau khi commit**: `_bao_cskh_da_co_bac_si(...)`.

> Ranh giới ở bước 11 và 12 là chỗ đáng học nhất của hàm này. `_xep_vao_lich_truc`
> nằm **trong** transaction vì *"gán được bác sĩ mà không xếp được ca là để lại
> đúng cái mâu thuẫn vừa nói"* — lịch hẹn ghi "BS. X khám" còn Lịch làm việc hôm
> ấy trống trơn, và `capacity_service` đọc chính lịch trực để trả lời "bác sĩ này
> có đi làm hôm đó không". `_bao_cskh_da_co_bac_si` nằm **ngoài** vì *"giao dịch
> cuộn lại mà thông báo đã bay đi là báo một việc chưa xảy ra"*. (`:844-874`)

#### Hai hàm hậu-hành-động

| Hàm | Giải thích |
|---|---|
| `_xep_vao_lich_truc` (`:891`) | Quản lý gán bác sĩ → cấp cho bác sĩ ấy một dòng `work_roster` ngày đó. **Ba quyết định nói rõ vì không suy ra được**: (1) ca lấy theo giờ của chính lịch hẹn, mốc 12:00 dùng chung `core.shifts.MORNING_END_MIN` — *xếp cả ngày cho một lịch 18:00 là tự ý tuyên bố bác sĩ đi làm từ sáng*; (2) trạm là `LICH_KHAM`; (3) **KHÔNG áp dụng tuần** — `roster_week` là chữ ký của quản lý, tự áp hộ là thay quản lý tuyên bố những ngày còn lại không ai đi làm. Không ghi đè, không nhân bản: đã có dòng `APPROVED` phủ ca ấy (`FULL` hoặc đúng ca) thì thôi |
| `_bao_cskh_da_co_bac_si` (`:1004`) | Nhắn vai CSKH "lịch này xếp được bác sĩ rồi". **Nuốt lỗi có chủ ý** (`except Exception` + log): việc chính đã commit, ném lỗi ở đây làm người gọi thấy một lời từ chối cho hành động ĐÃ thành công, rồi họ bấm lại, gán lại, và tưởng hệ thống hỏng. Đường dẫn trỏ tới **đúng việc, không chỉ đúng trang**: `?selected=<kh>&viec=CHO_XAC_NHAN&luot=<appt>` — thiếu `luot` thì khách nhiều lịch sẽ mở nhầm lượt |

---

### 5.5. Sức chứa — luật ba tầng (CAP-01 / C.3 / C.4)

#### 5.5.1. Luật ghế, bằng lời của phòng khám

> Mỗi **bác sĩ × khung** có vài ghế: một phần cho khách đặt hẹn, phần còn lại
> **để dành** cho khách vãng lai. Dòng chưa có bác sĩ là một hàng chờ riêng với
> cùng giới hạn.

Dr4Women đọc ra **15 phút / 2 + 1**. Ba con số đó **không nằm trong file này** —
chúng là cấu hình của một khách hàng, đọc từ `clinic.settings` qua
`clinic_policy.py`. *Trigger đọc cùng một dòng, nên một phòng khám đổi số của mình
là đổi cả câu tiếng Việt lẫn cái bảo đảm sau lưng nó bằng một `UPDATE`, không cần
deploy.* (`:29-34`)

#### 5.5.2. Ba tầng, giải theo thứ tự cụ-thể-nhất → chung-nhất

`load_effective_policy()` (`clinic_policy.py:167`) gọi hàm SQL
`resolve_effective_cap()` (`20260803000009:199`):

| Tầng | Bảng | Độ mịn | Ý nghĩa cho người vận hành |
|---|---|---|---|
| **3** | `slot_booking_override` | phòng khám × (bác sĩ **hoặc** mọi bác sĩ) × **khoảng ngày** × **khoảng PHÚT trong ngày** | "tuần này BS bận" — luật **tạm**, hết hạn thì thôi |
| **2** | `doctor_booking_override` | phòng khám × bác sĩ × (thứ **hoặc** mọi thứ) × `effective_from/to` | luật **thường trực**, lặp mãi |
| **1** | `clinic.settings.booking` | phòng khám | mặc định |

Thứ tự ưu tiên (`booking_override_service.py` docstring): luật **có ngày** thắng
luật **mãi mãi**; luật ghi rõ **bác sĩ** thắng luật "tất cả bác sĩ"; luật ghi rõ
**thứ** thắng "mọi thứ"; không luật nào phủ → mặc định.

⚠️ **Người dùng không thấy ba tầng.** Bản trước phơi tầng 2 và 3 thành hai tab
riêng, và Quang hỏi đúng câu phải hỏi: *"tại sao không cho vào một khung thiết
lập chung?"* — **ba tầng là cách LƯU, không phải cách NGHĨ**.

#### 5.5.3. Tính theo KHOẢNG PHÚT, không theo giờ

Luật khách hàng nêu (Notion) là **bốn con số khác nhau bên trong MỘT giờ**: BS
Thành 18:00 → 10 ca, còn 18:15/18:30/18:45 → 4 ca; các bác sĩ khác 3/4/5/3.
`slot_booking_override` chỉ có `hour_start/hour_end` (smallint 0–23) nên **không
có chỗ để nhập** điều đó — ba dòng override trên prod đều là `18 → 19`, một con
số cho cả tiếng. Migration `20260803000009` đổi sang `minute_start/minute_end`
(0..1440, nửa mở), và nó làm **ba** việc, việc thứ ba mới quan trọng:
1. đổi độ mịn sang phút;
2. dọn các dòng đang chồng lấn (giữ dòng **mới nhất** = ý định gần đây nhất, ghi
   các dòng bị bỏ vào `event_log` — *một luật sức chứa biến mất không dấu vết là
   thứ không được phép, kể cả khi nó đang mâu thuẫn*);
3. **cấm chồng lấn** bằng ràng buộc `EXCLUDE`.

> Sửa (1) mà không có (3) chỉ đổi một luật mơ hồ theo giờ thành một luật mơ hồ
> theo phút. Trước đó resolver sắp `ORDER BY date_start DESC LIMIT 1` mà cả ba
> dòng cùng `date_start` ⇒ **Postgres chọn dòng nào là KHÔNG XÁC ĐỊNH**. Sức chứa
> thật của khung 18h phụ thuộc vào thứ tự đọc trang đĩa.

#### 5.5.4. Luật MỚI cắt luật CŨ

Có `EXCLUDE` rồi thì lưu luật mới đè lên luật cũ sẽ **nổ**. Trưởng ca lưu "BS
Thành 18:00–18:15, 9 ca" và nhận về *"Lịch hẹn xung đột khung giờ với appointment
khác"* — cấu hình phòng khám trở thành thứ **chỉ ghi được đúng một lần**.

`plan_window_trim(old_start, old_end, new_start, new_end)`
(`booking_override_service.py`) là hàm thuần, bốn nhánh, toàn số nguyên:

| Quan hệ cũ vs mới | `action` | Giữ lại |
|---|---|---|
| cũ nằm **trọn** trong mới | `deleted` | không gì |
| mới nằm **giữa** cũ | `split` | `(old_start, new_start)` **và** `(new_end, old_end)` |
| cũ thò đầu **bên trái** | `trimmed` | `(old_start, new_start)` |
| cũ thò đuôi **bên phải** | `trimmed` | `(new_end, old_end)` |

Mọi khoảng **nửa mở `[start, end)`** — cùng quy ước với `int4range` trong
`EXCLUDE` và với `resolve_effective_cap` (`>= start AND < end`). Nhờ vậy hai
khung liền kề (18:00–18:15 và 18:15–18:30) **không** coi là chồng lấn, và luật cũ
bị cắt tới đúng mốc luật mới **không để lại phút hở**.

⚠️ *"mỗi nhánh lệch một phút là một khoảng giờ không luật nào phủ, và khoảng hở
đó KHÔNG BÁO LỖI — nó chỉ âm thầm rơi về số chỗ mặc định."*

#### 5.5.5. `_slot_full` — luật ghế thành một câu (`:1670`)

```python
begin, end = policy.bucket(slot_start)
seats = await conn.fetchrow(
    """
    SELECT slot_seats_used($1::uuid, $2::uuid, $3, $4, FALSE, $5::uuid) AS regular,
           slot_seats_used($1::uuid, $2::uuid, $3, $4, TRUE,  $5::uuid) AS walkin
    """,
    identity.clinic_id, doctor_id, begin, end, exclude_id,
)
```

Ba điều then chốt:

1. **`policy` được TRUYỀN VÀO, không đọc tại chỗ** (`:1682-1684`) — để câu tiếng
   Việt và cái trigger sắp từ chối lệnh ghi **nhìn cùng một bộ số**, cả hai đến
   từ đúng một dòng đọc ở đầu transaction.
2. **Đếm bằng CHÍNH hàm mà trigger gọi** (`slot_seats_used`, `20260807000001`).
   Vòng lặp Python cũ đếm ghế vãng lai bằng đúng số dòng `booking_channel =
   'WALK_IN'` — **nay thiếu một nửa**: khách có hẹn **đến muộn** cũng chiếm ghế
   vãng lai của khung họ thật sự có mặt. *Câu tiếng Việt và cái net phải nói cùng
   một con số, nếu không lễ tân sẽ đọc "còn chỗ" rồi bấm và bị từ chối.*
3. **Hai câu trả lời khác nhau cho hai loại khách**: vãng lai chỉ hỏi
   `walkin_cap`; mọi thứ khác chỉ hỏi `regular_cap`. Câu từ chối cho khách đặt
   hẹn còn nói rõ ghế còn lại **để dành**: *"2 chỗ đặt hẹn đã đủ — 1 chỗ còn lại
   chỉ dành cho khách vãng lai"*.

`policy.bucket()` (`clinic_policy.py:103`) làm tròn xuống **trên epoch UTC**,
cùng phép tính với trigger. Và `__post_init__` bắt buộc `60 % slot_minutes == 0`:
giờ Việt Nam lệch một số giờ chẵn, nên **lưới UTC trùng lưới địa phương khi và
chỉ khi khung chia hết 60**. Khung 45 phút trượt dần qua từng giờ, và **ô lễ tân
nhìn thấy không còn là ô database đếm**.

#### 5.5.6. `_doctor_conflict` và `DOCTOR_OVERLAP_CAP = 6` (`:113`, `:1491`)

> **Trần này không phải lưới, và thực tế không bao giờ chạm tới.**

Chú thích cũ viết nó "phản chiếu `appointment_no_doctor_overlap`, một ràng buộc
DB" — **ràng buộc đó không tồn tại**. Thứ thật sự chặn là trigger: tối đa
`regular_cap + walkin_cap` (mặc định 3). **Sáu luôn lớn hơn ba**, nên câu "đã đạt
giới hạn 6 lịch" gần như không bao giờ hiện ra — trigger đã từ chối từ lịch thứ
tư.

Giữ lại vì nó vẫn là **lưới cuối cho lịch DÀI HƠN MỘT KHUNG**: trigger gom theo
mốc bắt đầu, nên một lịch 60 phút lúc 9:00 **không chặn được** lịch 9:15. Câu
`WHERE slot_start < $4 AND slot_end > $3` là phép chồng-lấn khoảng thật sự.

⚠️ `_doctor_conflict` loại `['CANCELLED', 'NO_SHOW']` — **hai** mã, không phải ba
như `DEAD_STATUSES`. Nghĩa là một lịch `DOCTOR_DECLINED` vẫn được đếm vào trần 6
ở đây, trong khi `slot_seats_used` thì không đếm. Không thấy chú thích nào giải
thích chủ ý — **chưa rõ, cần kiểm**.

#### 5.5.7. Ca trực: `_roster_warning` + `_roster_is_required`

| Hàm | Giải thích |
|---|---|
| `_roster_warning` (`:1541`) | Câu cảnh báo nếu bác sĩ không trực lúc đó |
| `_roster_is_required` (`:1637`, staticmethod) | Cảnh báo ấy có **chặn hẳn** không. Đọc `settings.booking.require_roster`, **mặc định `true`** |

Hai điểm mấu chốt của `_roster_warning`:

- **Chỉ lên tiếng khi ngày đó ĐÃ xếp ca.** CSKH đặt lịch trước cả tháng, lúc đó
  lịch trực chưa xếp. *Cảnh báo mọi lịch tương lai sẽ biến cảnh báo thành tiếng
  ồn, và tiếng ồn thì bị bỏ qua đúng vào lần nó nói thật.*
- **"Đã xếp ca" nghĩa là TUẦN ĐÃ ĐƯỢC ÁP DỤNG**, không phải "có dòng trong
  bảng" — nên `EXISTS (SELECT 1 FROM roster_week …)` lồng bên trong. Ngày 07/08
  có **26 tuần** được trải ra từ một mẫu và ghi thẳng `APPROVED` tới 31/01/2027 —
  toàn bộ là **bản nháp**. Chỉ hỏi "có dòng không" thì mọi lịch tương lai bỗng
  có cảnh báo dựa trên bản nháp chưa ai duyệt.

Có tên trong ngày **vẫn có thể sai giờ** — nên phần cuối dùng `core/shifts.py`:

| Hàm (`core/shifts.py`) | Giải thích |
|---|---|
| `MORNING_END_MIN = 720` | Mốc 12:00. **Quyết định của phòng khám** (Quang 04/08), không suy ra được từ dữ liệu. Nằm ở đúng một chỗ vì *nó sẽ là thứ đầu tiên phòng khám thứ hai muốn đổi* |
| `shift_window(shift, open_min, close_min)` | `FULL/SANG/CHIEU` → khoảng phút, **cắt theo giờ mở cửa của ngày đó** chứ không phải 00:00–24:00. Trả `None` khi ca ấy không còn phút nào (ca SÁNG của ngày mở cửa từ 17:00). Nhãn lạ → coi như cả ngày: *một ca không đọc được mà biến mất sẽ khoá lịch của một bác sĩ đang thật sự đi làm* |
| `merge_windows(windows)` | Gộp khoảng chồng/kề. Một bác sĩ có nhiều dòng cùng ngày ở nhiều trạm, ca khác nhau — họ có mặt trong **HỢP** của các ca |
| `covers(windows, minute)` | Nửa mở `[lo, hi)` |
| `describe(windows)` | `"07:00–12:00, 13:00–20:00"` — đưa thẳng vào câu cho người dùng |

`_roster_is_required` mặc định **CÓ chặn**, và docstring giải thích vì sao đổi:
hàm này **chỉ quyết định đúng một tình huống** — ngày đã có lịch trực, và bác sĩ
được chọn **chắc chắn không đi làm hôm ấy**. Để mặc định cho qua tình huống đó là
tạo một cái hẹn không ai khám, *sai lầm chỉ vỡ ra lúc bệnh nhân đã tới nơi, và
người chịu là bệnh nhân*. Quyết định của Quang: **lịch của bác sĩ là luật cao
nhất**. Muốn quay lại kiểu chỉ-cảnh-báo thì đặt cờ — *một cờ, không phải một bản
build khác*.

---

### 5.6. Chống đặt trùng — `_patient_double_booked` (`:1436`)

Tên trong đầu bài là `_patient_conflict`; **trong code nó tên
`_patient_double_booked`**. Đây là hàm hay bị hiểu sai nhất file.

#### 5.6.1. Chuyện đã xảy ra

> Prod 04/08: **một bệnh nhân có BA lịch hẹn cùng khung 17:15**, tạo cách nhau 10
> và 5 giây — tức một người bấm "Đặt lịch hẹn" ba lần. Khung đó sức chứa 3, nên
> **một người chiếm trọn khung của cả phòng khám**, và không luật nào trong hệ
> chặn lại: bảng `appointment` khi ấy không có ràng buộc duy nhất nào.

Nặng hơn kể từ khi bỏ bước xác nhận: trước đây lịch thừa còn nằm ở "chờ xác nhận"
nên có người rà; giờ nó **chắc ngay** (`:478-488`).

#### 5.6.2. Câu truy vấn, và bốn quyết định trong nó

```sql
SELECT slot_start, status
  FROM appointment
 WHERE clinic_id = $1::uuid
   AND clinic_patient_id = $2::uuid
   AND slot_start = $3
   AND status <> ALL ($4::text[])   -- DEAD_STATUSES
 LIMIT 1
```

| Vế | Quyết định | Vì sao |
|---|---|---|
| `slot_start = $3` | **Bằng đúng mốc bắt đầu**, không phải chồng lấn khoảng | Khám 17:15 rồi **siêu âm 17:45** là hai lịch hợp lệ trong một buổi. Chặn theo khoảng sẽ cấm luôn chuyện đó. Bài `test_it_matches_on_the_exact_start_time_only` canh chuỗi `"slot_start = $3"` |
| `status <> ALL DEAD_STATUSES` | Lịch đã chết **không** chặn | Huỷ rồi đặt lại đúng khung cũ là chuyện thường ngày. Bài `test_a_cancelled_appointment_does_not_block_rebooking` canh chuỗi `"DEAD_STATUSES"` |
| **không lọc `doctor_id`** | Một người **không ngồi hai chỗ cùng lúc** | Đây là gốc của hiểu nhầm ở 5.6.4 |
| **không lọc `location_id`, `service_type_id`** | như trên | |

#### 5.6.3. Câu từ chối phải NÓI RÕ ĐÂY LÀ LẦN THỨ HAI

```python
return (
    f"Đây là lần đặt thứ hai — bệnh nhân này ĐÃ có lịch lúc {hhmm} "
    f"({status_cu}). Lần bấm trước đã thành công, không cần đặt lại. "
    "Muốn đổi giờ thì vào Quản lý khách hàng → Lịch hẹn sắp tới."
)
```
(`:1485-1489`)

Quang: *"cùng 1 khách mà giờ đặt 2 lần thì hệ thống phải thông báo đây là lần
2"*.

> **Một câu từ chối trống làm người ta tưởng thao tác trước đó hỏng và thử lại
> lần nữa — đúng vòng lặp sinh ra ba lịch trùng hôm 04/08.** Câu này không chỉ
> chặn; nó **dập tắt vòng lặp** bằng cách nói ra rằng lần bấm trước ĐÃ thành công.

`status_cu` dịch mã trạng thái sang tiếng người (`SCHEDULED` → "chờ xác nhận",
`CHECKED_IN` → "đã đến phòng khám") — vì lễ tân không đọc `CSKH_CONFIRMED`.

#### 5.6.4. Vì sao ô lịch báo "0/2" mà vẫn không đặt được

Đây là điều **phải hiểu đúng, nếu không sẽ đi sửa nhầm chỗ**. Ô lưới đặt lịch và
`_patient_double_booked` **trả lời hai câu hỏi khác nhau**:

| | Câu hỏi | Đếm theo |
|---|---|---|
| Ô "0/2" trên lưới | *khung này còn ghế của **bác sĩ này** không* | `slot_seats_used(clinic, **doctor_id**, …)` — theo bác sĩ, và có lọc **cơ sở** |
| `_patient_double_booked` | *bệnh nhân này đã có lịch **ở mốc giờ này** chưa* | theo **bệnh nhân**, **mọi** bác sĩ, **mọi** cơ sở, **mọi** dịch vụ |

Nên một ô hoàn toàn trống (0/2) vẫn từ chối, khi bệnh nhân đã có một lịch còn
sống ở **đúng mốc `slot_start` ấy** dưới:
- một **bác sĩ khác**, hoặc
- **chưa có bác sĩ** (hàng chờ xếp người — dòng này còn được trigger sức chứa
  **miễn kiểm** hoàn toàn, nên nó không xuất hiện ở tử số của bất kỳ ô nào), hoặc
- một **cơ sở khác** với cơ sở lưới đang vẽ, hoặc
- một **dịch vụ khác** ở cùng giờ (khám + siêu âm cùng 9:00).

Ba nguồn "khoảng vênh giữa cái mắt thấy và cái tay bấm" khác, đều có thật và đều
được ghi trong repo:

1. **`slot_seats_used` lọc theo cơ sở, trigger thì không** — chú thích ngay trong
   `20260807000001`: *"HAI CON SỐ ẤY CÓ THỂ LỆCH NHAU — lưới nói còn chỗ trong
   khi trigger từ chối, nếu bác sĩ đã kín ở cơ sở khác. Đó là chuyện có từ trước
   migration này; ghi ra đây để nó không còn im lặng."*
2. **Khách có hẹn đến muộn** chiếm một ghế **vãng lai** của khung họ có mặt, chứ
   không phải ghế đặt hẹn — nên một ô có thể "còn chỗ đặt hẹn" mà hết chỗ vãng
   lai, và ngược lại.
3. **Giữ chỗ (`slot_hold`)** tô một ô là "đang giữ" mà **không** hề chiếm ghế —
   xem 5.8.

⚠️ Nghĩa là: **"0/2 mà không đặt lại được" gần như luôn là câu trả lời cho một
câu hỏi khác, không phải một ô ma.** Cách xác minh: đọc **nguyên văn** câu lỗi.
"Đây là lần đặt thứ hai…" → `_patient_double_booked`. "Khung … đã đủ N chỗ" →
`_slot_full`. "Khung giờ đã đầy: tối đa …" → **trigger** (tức pre-check đã cho
qua và ta thua cuộc đua, hoặc lưới đang nhìn một cơ sở khác).

#### 5.6.5. Vì sao chốt này KHÔNG đủ, và chỉ mục mới là lưới

Docstring tự thú nhận (`:1450-1453`): *"Nó không chống được hai request thật sự
đồng thời — nhưng cái đang xảy ra là một người bấm ba lần cách nhau 5 giây, và
với chuyện đó thì câu này đủ."* `SELECT` rồi `INSERT`, **không khoá**.

Migration `20260805000007` liệt kê đủ bốn lớp đã có và vì sao cả bốn đều thủng:

| Lớp | Chặn được gì | Thủng ở đâu |
|---|---|---|
| Nút bị vô hiệu khi đang gửi | người | không chặn hai request đã rời trình duyệt |
| `Idempotency-Key` | gửi lại **cùng một** yêu cầu | không chặn hai yêu cầu **khác nhau** cùng nội dung; và header là **TUỲ CHỌN** |
| `_patient_double_booked` | bấm lặp cách nhau vài giây | SELECT-rồi-INSERT, không khoá |
| — | | **`SchedulingService.create_appointment` cũng ghi vào bảng này và KHÔNG hề gọi `_patient_double_booked`** |

> **Chốt đặt ở tầng service chỉ che được cửa nào có người nhớ đặt chốt; chỉ mục
> thì che mọi cửa.** Theo ADR-0003, đây là bậc 1 của bậc thang (UNIQUE/CHECK
> trước, advisory lock sau) và là lý do **không** cài khoá trong Python cho việc
> này.

Chỉ mục là **bán phần** — `WHERE status <> ALL (…)` với đúng ba mã của
`DEAD_STATUSES` — và **chỉ khoá `slot_start`, không khoá cả khoảng**, đúng cùng
hai lý do ở 5.6.2.

⚠️ Migration ấy còn có **cổng chặn**: nếu còn nhóm trùng thì `RAISE EXCEPTION`
kèm sẵn câu SQL đi dò — thay vì để `CREATE UNIQUE INDEX` đổ với một lỗi khó đọc.
Và nó được làm **lúc bảng có 2 dòng**: *"thêm ràng buộc vào bảng 2 dòng là chuyện
một giây; thêm vào bảng đã chạy vài năm là phải dọn dữ liệu thật trước."*

---

### 5.7. `_build_patch` và các vết dữ liệu (`:1083`)

Hàm dựng dict `patch` mà `_update` sẽ ghi. Bốn nhánh theo hành động, rồi **một
khối chung ở đuôi**.

| Nhánh | Ghi gì | Chốt riêng |
|---|---|---|
| `cancel` | `cancelled_at`, `cancellation_reason`, `ly_do_huy_ma`, `cancelled_by_staff_id` | bắt buộc có mã; mã phải nằm trong `LY_DO_HUY`; `KHAC` phải kèm chữ |
| `reassign` | `doctor_id` | `_guard_slot(...)` với `exclude_id = chính nó` |
| `assign_doctor` | `doctor_id` | bắt buộc có người; **từ chối nếu lịch đã có bác sĩ**; `_luat_bac_si_bat_buoc`; `_guard_slot` |
| `reschedule` | `slot_start`, `slot_end`, (tuỳ chọn) `doctor_id` | `slot_end > slot_start`; `_chan_dat_vao_qua_khu`; `_guard_slot` |

Ba chi tiết đáng dừng lại:

**(a) `cancelled_by_staff_id` lấy từ PHIÊN, không nhận từ client** (`:1115-1117`).
Trước đây không lưu ai huỷ, nên **một lịch huỷ nhầm không truy được về ai**.

**(b) `assign_doctor` từ chối lịch đã có bác sĩ** (`:1136-1141`): *"Lịch này đã có
bác sĩ. Dùng Đổi lịch nếu cần đổi người."* Vì đổi người là việc **có ghi lý do**,
còn `assign_doctor` là **xếp lần đầu**. Và trần số chỗ áp **ở đây**, *"đúng lúc
câu hỏi trở thành thật: trước đó lịch chưa chiếm ghế của ai"* (migration
`20260808000002` miễn kiểm cho dòng chưa phân bác sĩ).

**(c) Ba trạng thái của trường `doctor_id` trong `reschedule`** (`:1182-1190`):

```python
if doctor_id_provided:
    patch["doctor_id"] = (doctor_id or "").strip() or None
```

| Client gửi | `doctor_id_provided` | Nghĩa |
|---|---|---|
| không có trường | `False` | **giữ nguyên** bác sĩ |
| trường = `null`/rỗng | `True` | **bỏ** bác sĩ (về hàng chờ) |
| trường = một id | `True` | **đổi** bác sĩ |

Một trường vắng mặt và một trường rỗng là **hai ý định khác nhau**; gộp chúng là
mất đường "bỏ bác sĩ".

#### 5.7.1. Xoá vết `bac_si_da_go_id` / `bo_bac_si_luc`

```python
if patch.get("doctor_id"):
    patch["bac_si_da_go_id"] = None
    patch["bo_bac_si_luc"] = None
return patch
```
(`:1215-1219`)

**Vết ấy từ đâu ra.** `RosterService.remove` (`config_service.py:584-588`) khi xoá
một ca trực sẽ, cho mỗi lịch không còn khung nào phủ:

```sql
SET doctor_id       = NULL,
    bac_si_da_go_id = doctor_id,   -- NHỚ người vừa bị gỡ
    bo_bac_si_luc   = now(),
    status          = 'CANCELLED',
    ly_do_huy_ma    = 'BAC_SI_DOI_LICH',
```

`bac_si_da_go_id` tồn tại để màn hình còn nói được **"đổi từ ai"**, và
`bo_bac_si_luc` tách riêng chứ **không suy từ `updated_at`** — vì một lịch còn
được sửa vì nhiều lý do khác sau đó.

**Vì sao phải xoá khi gán lại được người.** Trước 15/08/2026 **không đường gán bác
sĩ nào xoá vết ấy**, nên sau khi CSKH đã xử lý **XONG** — gán người mới qua
`assign_doctor` / `reassign` / `reschedule` — bảng lịch tuần
(`week_appointments_service.py:141`) và màn khách hàng vẫn đỏ *"X đã nghỉ — gọi
khách xếp bác sĩ khác"* **vĩnh viễn**.

> **Một cảnh báo không bao giờ tắt dạy người trực bỏ qua mọi cảnh báo, kể cả cái
> đúng.** Đây là lý do thật, và nó lớn hơn "một ô đỏ thừa".

**Vì sao đặt ở ĐUÔI hàm, không lặp trong từng nhánh** (`:1211-1214`): *"nhánh ghi
`doctor_id` thứ tư thêm sau này cũng tự được phủ"*. Bài kiểm
`test_moi_duong_ghi_doctor_id_deu_qua_khoi_xoa_vet` là một **bài kiểm quan hệ**:
nó đọc mã nguồn `_build_patch` và khẳng định hàm **kết thúc bằng `return patch`**,
rồi khối xoá vết nằm sau `if patch.get("doctor_id")` cuối cùng. Ai chuyển khối ấy
vào một nhánh riêng thì **bài này đỏ trước khi cảnh báo thành lời nói dối trên
màn**.

**Vì sao `if patch.get("doctor_id")` chứ không `if "doctor_id" in patch`**: chỉ
xoá khi gán **ĐƯỢC** người (giá trị thật). `reschedule` mà **bỏ trống** bác sĩ thì
khách **vẫn đang chờ xếp** — vết phải ở lại để màn hình còn nói được "đổi từ ai".
Bài `test_doi_lich_bo_trong_bac_si_thi_vet_o_lai` khẳng định
`"bac_si_da_go_id" not in patch`.

---

### 5.8. `LY_DO_HUY` — danh mục lý do huỷ (`:80-94`)

| Mã | Câu hiện trên màn | Ý nghĩa thật |
|---|---|---|
| `BAO_KHI_XAC_NHAN` | Gọi xác nhận trước 7 ngày — khách báo không đến được | **Thời điểm 1.** Rẻ nhất: chỗ đó còn **bán lại được** |
| `BAO_KHI_NHAC_HEN` | Đã xác nhận sẽ đến, tới lúc nhắc hẹn thì báo không đến | **Thời điểm 2.** Còn kịp lấp, nhưng gấp |
| `BAO_VAO_GIO_KHAM` | Đúng giờ khám, lễ tân gọi khách mới báo không đến | **Thời điểm 3.** Đắt nhất: **bác sĩ ngồi không** |
| `DAT_TRUNG` | Đặt trùng — khách có nhiều lịch, bỏ bớt giữ lại một | **DỌN DẸP**, không phải một thời điểm |
| `BAC_SI_DOI_LICH` | Bác sĩ đổi lịch làm việc — phòng khám huỷ để đặt lại | **Phòng khám chủ động huỷ** |
| `KHAC` | Lý do khác (tự viết) | Bắt buộc kèm chữ |

Ba khối chú thích giải thích cấu trúc này, và cả ba đều là **luận điểm về đo
lường**:

> **Ba mã đầu là BA THỜI ĐIỂM trong vòng đời lịch hẹn, không phải ba cách nói của
> "khách bận"** — và mỗi thời điểm tốn của phòng khám một khoản khác nhau. *Đếm
> được ba con số ấy mới biết nên siết khâu nào.*

- `DAT_TRUNG` **tách riêng** vì gộp nó vào ba mã kia sẽ **bơm phồng con số "khách
  báo không đến"**. Khách không huỷ gì cả; **phòng khám tự đặt trùng rồi tự bỏ
  bớt**.
- `BAC_SI_DOI_LICH` tách riêng vì đếm chung với `BAO_*` là **đổ lỗi cho khách một
  chuyện của phòng khám**. `RosterService.remove()` ghi mã này **bằng máy**;
  người cũng chọn được khi huỷ tay vì đúng lý do ấy.
- **Không tự điền `KHAC` cho im chuyện** (`:1104-1107`): *"Mặc định âm thầm là
  cách cột này thành 100% 'khác' trong ba tháng, và lúc đó nó vô dụng đúng bằng ô
  chữ tự do mà nó thay thế."* Nên `ma is None` → `ValidationError("Chọn lý do
  huỷ.")`.

⚠️ **Chữ ở đây phải khớp `src/dashboard/lib/ly-do-huy.ts`.** Ba màn cùng vẽ danh
sách này (Quản lý khách hàng, Công việc của tôi, API tác nhân), nên chép tay là
**sớm muộn ba màn nói ba kiểu về cùng một lần huỷ**. Bài chống lệch:
`src/tests/unit/test_ly_do_huy_drift.py`.

---

### 5.9. Giữ chỗ, idempotency, và ranh giới giao dịch

#### 5.9.1. Ba cơ chế, ba tầng, không cái nào thay được cái nào

| Cơ chế | Ở đâu | Chặn gì | KHÔNG chặn gì |
|---|---|---|---|
| `slot_hold` | `slot_hold_service.py`, bảng `slot_hold` | hai CSKH cùng nhắm một khung, **về mặt hiển thị** | không chặn ai cả — **tư vấn thuần** |
| `Idempotency-Key` | `api/idempotency.py` | **gửi lại cùng một** request (retry, double-click, mạng chập) | hai request **khác nhau** cùng nội dung; header **tuỳ chọn** |
| Transaction + trigger + unique index | Postgres | **mọi thứ**, nguyên tử | — |

#### 5.9.2. Giữ chỗ — `slot_hold`

> **GIỮ CHỖ LÀ TƯ VẤN, KHÔNG PHẢI KHOÁ.** Chốt chặn thật vẫn là trigger sức chứa
> lúc `INSERT`. Một dòng giữ chỗ bị rò (đóng trình duyệt giữa chừng) làm phiền
> người khác **tối đa 10 phút** chứ không chặn được ai — và **không bao giờ làm
> một lịch hẹn hợp lệ bị từ chối**. (`slot_hold_service.py:13-16`)

Quyết định của Quang (04/08): *"cái đếm 10' chỉ sinh event khi mà CSKH đang chọn
khung giờ khám để CSKH khác được hiện là khung này đang được giữ để đặt để tránh
đặt trùng, **chứ không phải đã ấn đặt lịch rồi lại còn giữ 10' làm gì**"*.

Cái đang chạy trước đó làm sai đúng chỗ này: màn đặt lịch dán nhãn "Đang giữ" lên
ô nào **có lịch hẹn** ở `WAITING/CSKH_CONFIRMED` — tức nó gọi **một lịch đã đặt
xong** là "đang giữ". *Ghế đã bán và ghế đang có người đứng cạnh là hai thứ khác
nhau, và gộp lại thì CSKH thứ hai không biết khung nào thật sự còn chỗ.*

| Hàm | Giải thích |
|---|---|
| `hold(...)` | `INSERT … ON CONFLICT DO UPDATE` gia hạn 10 phút. **Thả lần giữ trước** (`_release_mine(keep=slot_start)`) — nếu không, một CSKH bấm lướt qua năm khung để lại **năm chỗ "đang giữ"** mà họ không định đặt, và màn hình người bên cạnh đầy **cảnh báo giả** |
| `release(...)` | Thả mọi chỗ người này giữ |
| `active(...)` | **Bỏ chỗ do chính người đang xem giữ** — hiện "đang giữ" trên ô mình vừa bấm là tự nói với mình rằng có người khác đang tranh chỗ |
| `release_on_booking(conn, …)` | Đặt xong thì thả, **trong CÙNG transaction** |

**Điểm giao với `booking_service`** là `:586`:

```python
await release_on_booking(conn, identity=identity,
                         appointment_id=str(appointment_id), slot_start=slot_start)
```

Nó nhận `conn` — **không phải `pool`**. Đó là toàn bộ ý nghĩa: *"đặt lịch thành
công mà thả chỗ thất bại sẽ để lại một chỗ 'đang giữ' vĩnh viễn ở đúng khung vừa
đặt"*, và *"để dòng giữ chỗ sống tiếp sau khi đã thành lịch hẹn là **đếm cùng một
ghế hai lần** trên màn hình CSKH bên cạnh"*.

#### 5.9.3. Idempotency ở cửa vào

`booking.py:260-298`:

```python
idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
if idem.is_replay:
    return idem.cached_response
async with tra_khoa_neu_bi_tu_choi(idem, pool):
    result = await BookingService(pool).create(...)
    payload = {"ok": True, **result}
    await idem.save(pool, payload, status_code=201)
return payload
```

Ba cái bẫy đã được vá ở đây:

1. **`acquire()` trả về một guard MỚI.** `IdempotencyGuard` là `frozen`, nên
   không gán lại `idem` sẽ **âm thầm tắt chống-phát-lại** rồi làm `save()` nổ.
2. **`tra_khoa_neu_bi_tu_choi`** — bị từ chối vì lý do nghiệp vụ (4xx) thì **trả
   khoá lại ngay**, kẻo lần bấm lại sau khi sửa vẫn nhận 409 suốt 5 phút và **câu
   giải thích thật biến mất**. Đặt ở `idempotency.py` chứ không lặp trong từng
   router, vì bốn đường đang dùng khoá có cùng hình dạng và *"đường nào quên bọc
   thì lỗi quay lại y như cũ mà không ai thấy"*.
3. **`actor_id`** — khoá gắn với người gọi, không phải toàn cục.

⚠️ `apply_action` (`PATCH`, `booking.py:453`) **không** có idempotency guard. Nó
không cần: `_update` có `WHERE status = ANY(from_statuses)`, nên lần gọi thứ hai
**tự nhiên** không khớp trạng thái nguồn và trả `ConflictError` — đó chính là
idempotency bằng chính máy trạng thái.

#### 5.9.4. Cái gì phải cùng thành công

**`create()` — một transaction, 7 việc** (`:466`–`:640`):

```
validate refs → double-book → doctor conflict → roster → luật BS → sức chứa
→ INSERT appointment
→ release_on_booking          (thả chỗ giữ)
→ _attach_episode             (nối đợt chăm sóc + UPDATE appointment.episode_id)
→ _log appointment.created
→ [nếu auto_checkin] _log checked_in + _open_visit
```

**`apply_action()` — một transaction**:

```
SELECT appointment (+4 cờ EXISTS) → kiểm vai/chủ/trạng thái
→ _check_in()  HOẶC  _build_patch() + _update()
→ _log
→ [checkin] _open_visit  |  [undo_checkin/cancel] _cancel_visit_workflow
→ [doctor NULL→có] _xep_vao_lich_truc
```

**Nằm NGOÀI transaction, cố ý**: `_bao_cskh_da_co_bac_si` (`:875`) và
`logger.info`.

#### 5.9.5. `_check_in` — chuyển tiếp DUY NHẤT không phải optimistic update

```python
rows = await conn.fetch(
    "SELECT * FROM check_in_appointment($1::uuid, $2::text[])",
    appointment_id, list(transition.from_statuses),
)
return bool(rows)
```
(`:1368-1380`)

Vì sao khác mọi hành động khác: **cấp số thứ tự trong ngày và chuyển trạng thái
phải là một giao dịch được tuần tự hoá**. Hàm SQL `check_in_appointment`
(`20260717000002`) làm ba việc trong một lượt: `SELECT … FOR UPDATE`, rồi
`pg_advisory_xact_lock('clinicai:queue:' || ngày)`, rồi `max(queue_number)+1` và
`UPDATE`. **Hai lễ tân check-in cùng lúc không được phát ra cùng một số.** Khoá
là **cùng một advisory lock mà đường vãng lai dùng**, khoá theo **ngày phòng khám
giờ Việt Nam**.

Hàm trả 0 dòng nếu trạng thái không khớp `p_from_statuses` → `_check_in` trả
`False` → `apply_action` ném "Lịch hẹn vừa được người khác cập nhật".

#### 5.9.6. `_open_visit` — vì sao `ON CONFLICT` chứ không `try/except`

Khối chú thích `:1808-1828` là bài học đắt nhất về giao dịch trong repo:

> Bắt `UniqueViolationError` **trông có vẻ tương đương và không hề tương đương**:
> tới lúc asyncpg ném ra, **Postgres đã huỷ transaction rồi**, nên nuốt exception
> để lại một transaction chết mà `COMMIT` **âm thầm hạ cấp thành `ROLLBACK`**.
> Hàm này chạy **CUỐI** trong transaction check-in, nên **thay đổi trạng thái, số
> thứ tự, và event kiểm toán đều biến mất theo** — trong khi API trả về
> `{"ok": true, "status": "CHECKED_IN"}`.

Tái hiện được từ đầu tới cuối: check-in → hoàn tác → check-in lại
(`undo_checkin` chỉ vá `appointment`, nên dòng `visit` sống sót). Lần check-in
thứ hai **trả 200 và để lịch hẹn ở `CONFIRMED`**. *Lễ tân được báo bệnh nhân đã
đến, và bệnh nhân không bao giờ lên bảng.*

Ba việc `_open_visit` làm, theo thứ tự:
1. `INSERT … ON CONFLICT (appointment_id) … DO NOTHING RETURNING visit_id`; nếu
   `NULL` thì `SELECT` lại (ai đó — điều dưỡng đo sinh hiệu, kỹ thuật viên siêu
   âm — đã mở lượt trước).
2. `instantiate_visit_workflow(...)` — dựng danh sách bước. Trả 0 là **bình
   thường** khi check-in lại, nhưng **cũng là** thứ một phòng khám chưa seed danh
   mục node trả về — nên ghi log để thấy trước, thay vì phát hiện khi bảng trống.
3. `place_visit_at_first_station(...)` — **mắt xích còn thiếu giữa Lễ tân và bảng
   điều phối**. Đo trên prod trước thay đổi này: **24 lượt đã check-in, con trỏ
   `current_node_code` NULL ở cả 24** — bảng điều phối không thấy ai, dù bệnh
   nhân đã đứng trong phòng khám. Hàm SQL tự bỏ qua nếu lượt đã có vị trí, nên
   bấm check-in lần hai **không kéo bệnh nhân từ phòng siêu âm về quầy sinh
   hiệu**.

> **Cả hai đường check-in — vãng lai tự động trong `create()` và hành động
> `checkin` — đều chảy qua đúng hàm này.** Treo kernel vào một chỗ duy nhất là
> phủ được vãng lai **theo cấu trúc**, thay vì theo trí nhớ của người thêm lời
> gọi thứ hai.

---

### 5.10. Các hàm còn lại

| Hàm | Giải thích |
|---|---|
| `__init__(pool)` (`:369`) | Giữ `asyncpg.Pool`. Service **không** giữ connection — mỗi thao tác `acquire()` riêng |
| `_guard_slot(...)` (`:1221`) | Gói ba chốt dùng lại cho `reassign`/`assign_doctor`/`reschedule`: `_validate_doctor_ref` → `_doctor_conflict` → `load_effective_policy` → `_slot_full`. Luôn truyền `exclude_id = chính lịch này` để **nó không tự chặn mình** |
| `_validate_booking_refs(...)` (`:1248`) | 4 `EXISTS` (bệnh nhân / cơ sở / dịch vụ / bác sĩ) trong **một** round-trip, mỗi cái kèm `is_active` và `clinic_id`. Fail **trước** `INSERT` để câu lỗi nói đúng trường nào sai |
| `_validate_doctor_ref(...)` (`:1311`) | Bác sĩ có thuộc phòng khám này không. **Nối qua `clinic_membership`**, không qua `staff.clinic_id` — cột đó **không tồn tại** (nền tảng đa phòng khám, `20260730000003`) |
| `_update(...)` (`:1336`) | Dựng `SET` động từ khoá của `patch`, `WHERE id = $1 AND status = ANY($2) AND clinic_id = $N`. Trả `bool`. Bọc **cùng hai handler SQLSTATE** như `create()` — vì `reschedule` cũng có thể đụng trigger sức chứa của khung mới |
| `_check_in(...)` (`:1368`) | Xem 5.9.5 |
| `_luat_bac_si_bat_buoc(...)` (`:1382`) | Trả `(câu, chặn_hẳn)` hoặc `None`. **Bỏ qua khi chưa chọn bác sĩ** — lịch chờ xếp người chưa có gì để đối chiếu, và chặn ở đây là chặn luôn cả hàng chờ. **"Khách mới" SUY TỪ LỊCH SỬ** qua `la_khach_moi_cua_dich_vu(...)`, **không** đọc `appointment.patient_kind` — ô đó do lễ tân gõ tay, nullable, và màn đặt lịch tự điền theo "có đợt chăm sóc đang mở không", nên một khách gõ nhầm là luật bỏ lọt |
| `_patient_double_booked(...)` (`:1436`) | Xem 5.6 |
| `_doctor_conflict(...)` (`:1491`) | Xem 5.5.6 |
| `_roster_warning(...)` (`:1541`) | Xem 5.5.7 |
| `_roster_is_required(...)` (`:1637`) | Xem 5.5.7 |
| `_slot_full(...)` (`:1670`) | Xem 5.5.5 |
| `_attach_episode(...)` (`:1724`) | Nối lịch vào một **đợt chăm sóc**. `NEW` **đóng** đợt đang mở (`close_reason='new_problem'`) và mở đợt mới — *một vấn đề mới là một liệu trình mới*. `RETURN` (hoặc không khai kèm đợt đang sống) **nhập vào đợt cũ**, và **mở lại** đợt `PENDING_CLOSE` — *bệnh nhân quay lại thì rõ ràng vẫn đang được chăm sóc* |
| `_open_visit(...)` (`:1799`) | Xem 5.9.6 |
| `_cancel_visit_workflow(...)` (`:1903`) | Huỷ các bước **còn mở** của lượt khám. **Bước đã hoàn tất thì ở nguyên**: *bệnh nhân thật sự đã đến và thật sự đã được đo sinh hiệu, và hoàn tác một cú bấm nhầm không làm điều đó thành không thật* |
| `_is_today(moment)` (`:1936`) | So **ngày theo giờ phòng khám**, không theo UTC. Dùng đúng một chỗ: quyết định `auto_checkin` |

Và một hàm **đã bị gỡ**, để lại 18 dòng bia mộ (`:343-359`): `suggest_load()` trả
về một bảng phút viết cứng (khách mới 15', tái khám 5', siêu âm +12'/+8') và
**bốn con số đó không đến từ phép đo nào**. Chúng được gõ vào một lần rồi thành
"sự thật": ô lịch tô màu theo chúng, cảnh báo "khung sắp đầy" tính theo chúng, và
**không ai từng kiểm** xem một khách mới lúc 18:00 thứ Ba có thật sự mất 15 phút.
Hai việc vốn khác nhau nay tách hẳn: **GIỚI HẠN** đặt lịch = SỐ CHỖ mỗi khung
(quản lý đặt, trigger thi hành); **THỜI LƯỢNG** khám = **ĐO** từ
`work_item.started_at → finished_at` (view `v_consultation_duration`).
`thanh_min`/`sono_min` từ đó chỉ nhận **giá trị nhập tay**, `NULL` khi không ai
ước lượng — *chứ không phải một con số hệ thống tự bịa rồi tự tin*.

---

### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

1. **"Pre-check là lưới an toàn."** Không. Mọi chốt Python trong file là
   *best-effort và fail open*; chúng tồn tại để đẻ ra một câu tiếng Việt. Nếu bạn
   sửa một chốt Python mà không sửa hàm SQL tương ứng, bạn vừa tạo ra một màn hình
   nói dối. (`:9-24`)
2. **`raw_channel or "WALK_IN"`** — mặc định bịa ra làm **luật ghế chạy ngược**
   trên màn bận nhất phòng khám suốt một thời gian. Bài học chung: *"NO INVENTED
   DEFAULT"*.
3. **Nuốt `UniqueViolationError` để "cho êm"** — Postgres đã huỷ transaction từ
   trước, `COMMIT` hạ cấp thành `ROLLBACK`, API trả `200` trong khi **không có gì
   được ghi**. Dùng `ON CONFLICT`. (`:1810-1816`)
4. **`owner_only` áp cho mọi vai** → Quản lý bấm check-out ăn `SafetyGateError`.
   "Ca của chính mình" chỉ có nghĩa **giữa các bác sĩ**. (`:752-763`)
5. **Hai hằng số cùng tên `DOCTOR_ROLES`**, lệch đúng một phần tử `TKYK` — *cách
   một quyền trôi mà không bài kiểm nào đỏ*. Nay import từ `identity.py`.
   (`:132-141`)
6. **Xoá `SCHEDULED`/`CSKH_CONFIRMED` khỏi `_ALIVE` cho gọn** = làm 25 lịch hẹn
   thật trên prod **kẹt cứng**, không khám được, không huỷ được. (`:205-208`)
7. **"0/2 mà không đặt được"** không phải ô ma: ô đếm theo **bác sĩ + cơ sở**,
   `_patient_double_booked` hỏi theo **bệnh nhân + mốc giờ**, và
   `slot_seats_used` với `p_location_id = NULL` (trigger) đếm **mọi cơ sở**. Đọc
   nguyên văn câu lỗi trước khi sửa. (5.6.4)
8. **Dòng chưa phân bác sĩ được trigger MIỄN kiểm hoàn toàn** — hệ quả phải nhìn
   thẳng: *hàng chờ không có trần, nên có thể dồn nhiều hơn số ghế thật*. Đó là
   vấn đề **xếp lịch của quản lý** và phải nhìn thấy được trên màn hàng chờ, không
   phải lý do từ chối khách ngay lúc họ gọi. (`20260808000002`)
9. **Khách vãng lai cũng `doctor_id IS NULL`** nhưng **vẫn bị kiểm trần** — bản
   đầu của migration ấy miễn cho cả hai và làm `walkin_cap` thành vô nghĩa. *Một
   bên là lịch hẹn THÁNG SAU chưa xếp người, một bên là người ĐANG ĐỨNG ở quầy.*
10. **`slot_minutes` không chia hết 60** → lưới UTC trượt khỏi lưới địa phương, và
    ô lễ tân nhìn **không còn là ô database đếm**. `ClinicPolicyError` chặn ngay
    lúc dựng policy. (`clinic_policy.py:82-85`)
11. **Chặn theo `slot_start` thay vì `slot_end`** ở `_chan_dat_vao_qua_khu` sẽ
    giết đường vãng lai giữa khung mỗi khi đồng hồ máy chủ nhanh vài giây.
12. **Khối xoá vết chuyển vào một nhánh** của `_build_patch` → cảnh báo "bác sĩ đã
    nghỉ" đỏ vĩnh viễn. Có bài kiểm quan hệ canh vị trí khối đó ở **đuôi hàm**.
13. **`_doctor_conflict` loại 2 mã, `DEAD_STATUSES` có 3.** `DOCTOR_DECLINED` vẫn
    được đếm vào trần 6. Không có chú thích nào nói đây là chủ ý — **chưa rõ, cần
    kiểm**.
14. **Tham chiếu dòng đã cũ:** migration `20260805000007` viết *"ba trạng thái
    trong mệnh đề WHERE là đúng ba trạng thái mà `DEAD_STATUSES` bên Python liệt
    kê (`booking_service.py:68`)"* — nay `DEAD_STATUSES` ở **dòng 116**. Nội dung
    vẫn đúng, chỉ số dòng đã trôi. Nhắc để đừng đi tìm nhầm chỗ.


---

## PHẦN 6. CA TRỰC BÁC SĨ, SỨC CHỨA VÀ ĐIỀU PHỐI

Đây là phần nghiệp vụ khó nhất của hệ. Ba câu hỏi tưởng đơn giản mà mỗi câu đã
từng làm hỏng lịch hẹn của khách thật:

1. **Bác sĩ có mặt lúc mấy giờ?** → `core/shifts.py` + `work_roster`
2. **Khung giờ ấy nhận được mấy khách?** → `booking_override_service.py` + `resolve_effective_cap()`
3. **Khách đang đứng ở đâu trong phòng khám?** → `dispatch_service.py`

Sợi chỉ xuyên suốt: **mọi thứ đều quy về KHOẢNG PHÚT TRONG NGÀY, nửa mở `[lo, hi)`.**
Nhờ cùng một đơn vị đo mà ba tầng luật so sánh được với nhau, và nhờ **nửa mở** mà
hai khung liền kề (11:45–12:00 và 12:00–12:15) không bao giờ vừa chồng nhau vừa để hở.

> **Luật cao nhất là LỊCH TRỰC, không phải luật sức chứa.** Một luật *"BS Thành
> 18:00–18:15 tám chỗ"* không có nghĩa gì vào ngày bác sĩ ấy không đi làm
> (`capacity_service.py:84-100`).

---

### 6.1. `src/clinicai/core/shifts.py` — ba nhãn ca thành khoảng phút (76 dòng)

`work_roster.shift` chỉ có ba nhãn: `FULL`, `SANG`, `CHIEU`. Ba nhãn đó nói về
thời gian nhưng **không có chỗ nào trong hệ thống nói sáng kết thúc lúc mấy giờ**
— nên trước đây luật lịch trực chỉ dừng ở mức NGÀY, và một bác sĩ chỉ trực ca
sáng vẫn được lưới mời đặt lúc 18:00 (`shifts.py:1-15`).

| Hàm / hằng | Giải thích |
|---|---|
| `MORNING_END_MIN = 12 * 60` (`shifts.py:21`) | Mốc sáng kết thúc **cũng là** lúc chiều bắt đầu. Đây là **quyết định của phòng khám (Quang, 2026-08-04)**, không phải con số suy ra được từ dữ liệu → nằm ở đúng một chỗ, vì nó sẽ là thứ đầu tiên phòng khám thứ hai muốn đổi |
| `Window = tuple[int, int]` (`shifts.py:23`) | Một khoảng phút-trong-ngày `(lo, hi)` |
| `shift_window(shift, open_min, close_min)` (`shifts.py:26`) | Nhãn ca + giờ mở cửa hôm đó → khoảng phút. `FULL` = cả giờ mở cửa; `SANG` = `open → min(close, 12:00)`; `CHIEU` = `max(open, 12:00) → close`. Trả `None` khi ca đó **không còn phút nào** |
| `merge_windows(windows)` (`shifts.py:46`) | Gộp các khoảng chồng/kề nhau thành danh sách rời, đã sắp xếp. Một bác sĩ có thể có nhiều dòng lịch trực cùng ngày ở nhiều trạm, ca khác nhau → **bác sĩ có mặt trong HỢP các ca** |
| `covers(windows, minute)` (`shifts.py:64`) | Mốc phút này có nằm trong ca nào không, nửa mở `lo <= minute < hi` |
| `describe(windows)` (`shifts.py:69`) | `[(480, 720)]` → `"08:00–12:00"`, để đưa thẳng vào thông báo cho người dùng |

**Vì sao đầu/cuối ngày lấy theo giờ mở cửa chứ không phải 00:00–24:00?** Vì ca
SÁNG của một ngày chỉ mở cửa từ 17:00 là một khoảng rỗng — và **nói ra điều đó
đúng hơn là lặng lẽ cho phép đặt lúc 8 giờ sáng** (`shifts.py:12-14`). Đó là lý do
`shift_window` trả `None` chứ không trả một khoảng ngược `(17*60, 12*60)`, thứ mà
`covers` sẽ lặng lẽ coi là rỗng ở chỗ này và có thể coi là cả ngày ở chỗ khác
(`test_shift_windows.py:50-54`).

Nhãn lạ thì sai theo hướng **cho phép**:

```python
else:
    # Nhãn lạ: coi như cả ngày thay vì lặng lẽ bỏ qua. Một ca không đọc
    # được mà biến mất sẽ khoá lịch của một bác sĩ đang thật sự đi làm —
    # sai theo hướng đó tệ hơn hẳn.
    lo, hi = open_min, close_min
```
`shifts.py:38-42`

> Hai ca kề nhau đúng mốc 12:00 **phải gộp thành MỘT khoảng liền**, nếu không thì
> đúng khung 12:00 rơi vào khe giữa hai khoảng — `merge_windows` dùng điều kiện
> `lo <= out[-1][1]` (dấu bằng), chứ không phải `<` (`shifts.py:57`,
> `test_shift_windows.py:70-76`).

---

### 6.2. `src/clinicai/services/config_service.py` — lịch trực và bảng giá (911 dòng)

Hai lớp trong một file: `RosterService` (lịch trực) và `PriceListService` (bảng giá).
Cùng một nguyên tắc phân quyền: **quản lý xếp lịch cho mọi người; người khác chỉ
tự đăng ký và chỉ gỡ ca của chính mình** — và điều đó được thi hành bằng cách **bỏ
qua `staff_id` của client** chứ không phải bằng cách kiểm tra nó. *Không có gì để
giả mạo nếu giá trị ấy không bao giờ được đọc* (`config_service.py:6-9`).

| Hàm | Giải thích |
|---|---|
| `week_start_of(work_date)` (`:68`) | Thứ Hai của tuần chứa ngày đó. **Suy ra, không bao giờ nhận từ client**: form lịch giữ tuần người dùng vừa xem, nên một `week_start` gửi lên sẽ xếp ca vào tuần họ không hề sửa |
| `parse_price(raw)` (`:78`) | Số nguyên đồng, `None` cho ô trống, ném lỗi cho `-5`. Giữ *"chưa đặt giá"* và *"giá sai"* tách nhau — route cũ gộp cả hai vào một `undefined` |
| `RosterService.__init__(pool)` (`:100`) | Giữ pool |
| `.add_shift(...)` (`:103`) | Thêm một ô lịch trực, trả id. Xem 6.2.1 |
| `._bao_lich_cho_xep(...)` (`:203`) | Ca mới vào mà có lịch đang chờ xếp bác sĩ → ghi sự kiện `roster.shift_added_cho_xep`. Xem 6.2.2 |
| `._kiem_pham_vi_tram(...)` (`:280`) | Chức danh này có được xếp vào vị trí đó không (bảng `vai_duoc_vao_tram`). **Fail-open có chủ ý** khi ma trận chưa khai |
| `.tram_cho_nhan_vien(...)` (`:327`) | Danh sách mã vị trí mà một nhân viên được xếp vào — màn xếp lịch dựng ô "Vị trí" từ **cùng một nguồn** với chỗ thi hành, nên giao diện không hứa một đằng rồi backend từ chối một nẻo |
| `.ma_tran_vi_tri(...)` (`:365`) | Cả ma trận vai × vị trí, cho màn cấu hình của quản lý |
| `.dat_vi_tri_cho_vai(...)` (`:375`) | Bật/tắt một ô ma trận. **Không xoá dòng khi tắt**: một ô từng bật rồi tắt là một QUYẾT ĐỊNH |
| `.decide(...)` (`:415`) | Duyệt / từ chối một ca tự đăng ký. Duyệt thì **xoá luôn lý do từ chối cũ**, phòng khi quản lý đổi ý |
| `.remove(...)` (`:448`) | Gỡ ca trực + huỷ những lịch **không còn khung nào phủ**. Trái tim của phần này — xem 6.2.3 |
| `.apply_week(...)` (`:635`) | Quản lý **chốt** lịch trực một tuần. Tuần trống thì từ chối, vì "áp dụng tuần trống" = tuyên bố cả tuần không ai đi làm → khoá mọi lượt đặt |
| `._bao_cskh_tuan_da_co_lich(...)` (`:734`) | Nhắn vai CSKH rằng tuần đã chốt lịch. Nuốt lỗi: lịch trực ĐÃ commit rồi |
| `.applied_weeks(...)` (`:787`) | Tuần nào đã áp dụng — phần còn lại giao diện hiển thị là "dự kiến" |
| `PriceListService.list(...)` (`:809`) | Bảng giá một nhóm. **Trả cả dòng đã tắt**, để thu ngân biết mã cũ đã ngừng dùng thay vì tạo lại trùng mã |
| `PriceListService.add(...)` (`:832`) | Thêm dòng giá; mã trùng → `ConflictError` 409, không phải một dòng thứ hai không ai thấy |
| `PriceListService.update(...)` (`:866`) | Vá từng cột. `unit_price_provided` tách *"không sửa giá"* khỏi *"đặt giá về rỗng"* |
| `PriceListService.remove(...)` (`:902`) | Xoá một dòng giá |

#### 6.2.1. `add_shift` — tên lấy từ database, không lấy từ trình duyệt

Các bước:

1. Chuẩn hoá `station`, thiếu thì `ValidationError`.
2. Xác định **ai được xếp**: chỉ quản lý mới được nêu tên người khác.

```python
is_admin = identity.role in ROSTER_ADMIN_ROLES
# Only management may name somebody else. For everyone else the client's
# value is ignored entirely rather than checked.
assigning_other = is_admin and bool(staff_id)
target_id = staff_id if assigning_other else identity.staff_id
```
`config_service.py:119-123`

Dòng `target_id = ...` là toàn bộ cơ chế phân quyền: người thường gửi `staff_id`
của ai cũng được, giá trị ấy **không bao giờ được đọc**.

3. Tra `staff` **JOIN `clinic_membership`** để lấy tên thật (`:135-145`). Comment
   ngay trên đó (`:128-134`) ghi hai lý do: `staff_name` trước đây **đi thẳng từ
   client vào bảng**, nghĩa là một lời gọi API tự chế ghi được *"Giám đốc Sở Y tế"*
   vào lịch trực và cả phòng khám nhìn thấy y như vậy; và câu truy vấn này là **chỗ
   duy nhất** kiểm được người được xếp có thuộc phòng khám này không.
4. `_kiem_pham_vi_tram` — chức danh có được vào vị trí đó không (`:151`).
5. `INSERT INTO work_roster` với `week_start = week_start_of(work_date)`, trạng thái
   `"APPROVED" if is_admin else "PENDING"` (`:176`). Quản lý tự duyệt mình, vì *khâu
   duyệt sinh ra để chặn nhân viên tự ghi mình vào lịch, không phải để bắt quản lý
   duyệt chính mình* (`:12-14`).
6. Nếu là ca khám do quản lý xếp → gọi `_bao_lich_cho_xep`.

**`_kiem_pham_vi_tram` — fail-open khi chưa khai.** Chỗ dễ bị chê nhất mà lại đúng:

```python
# CHƯA KHAI THÌ CHO QUA, có ghi log.
#
# Phòng khám mới cài đặt chưa có dòng nào trong ma trận. Chặn hết ở đó
# nghĩa là màn xếp lịch chết câm ngay ngày đầu, và người dùng không có
# cách nào tự gỡ. Bỏ sót một ca xếp nhầm nhẹ hơn nhiều.
if not rows:
    logger.warning("roster_station_scope_empty", ...)
    return
```
`config_service.py:306-318`

Một trường hợp bị chặn cứng: `ClinicRole.DISPLAY` — *"Màn hình phòng chờ là cái
tivi treo tường, không phải người"*, và vì nó chưa bao giờ có trong ma trận nên
nhánh fail-open sẽ cho nó qua nếu không chặn riêng (`:296-298`).

#### 6.2.2. `_bao_lich_cho_xep` — ca mới vào thì ai được báo?

Câu hỏi của Đặng Dương 17/08/2026: *"có cơ chế thông báo tự động cho CSKH khi
lịch làm việc của bác sĩ được cập nhật không?"* Màn hình đã tự tươi qua realtime,
nhưng **màn chỉ nói với người ĐANG NHÌN** — tin Telegram mới gọi được người đang
làm việc khác quay lại xếp (`config_service.py:179-184`).

Các bước:

1. Lấy giờ mở cửa hôm đó: `clinic_hours_for_date($clinic, $date)` (`:217`).
   Không có dòng nào = đóng cửa → thoát.
2. Đổi nhãn ca thành khoảng phút: `w = shift_window(shift, open, close)` (`:225`).
3. Đếm lịch **chờ xếp bác sĩ** trong ngày: `doctor_id IS NULL`, `slot_start > now()`,
   trạng thái còn sống (`:228-246`).
4. Lọc lại bằng chính thước đo khung giờ — bác sĩ nhận ca CHIỀU thì không có lý do
   gì đánh thức CSKH vì một lịch 08:00:

```python
trong_ca = [r for r in cho_xep if covers([w], r["phut"])]
if not trong_ca:
    return
```
`config_service.py:247-249`

5. Ghi `event_log` với `event_type = 'roster.shift_added_cho_xep'`,
   `event_published = FALSE` (`:250-276`). Payload mang sẵn tên bác sĩ, ngày, ca,
   số lịch và **tối đa 6 giờ đầu** — đủ để soạn tin mà không phải đi làm giàu dữ
   liệu lần nữa (`notification_templates.py:82-95`).

Điều kiện gọi hàm này rất hẹp, và cả hai vế đều có lý do:

```python
if station == "LICH_KHAM" and is_admin:
```
`config_service.py:185`

- `station == "LICH_KHAM"`: ca thủ thuật ngoài giờ không liên quan tới lịch khám.
- `is_admin`: chỉ ca **ĐÃ DUYỆT** — *"đăng ký PENDING chưa phải ca trực"* (`:184`).

Toàn bộ thân hàm nằm trong `try/except Exception` (`:277-278`) — **best-effort có
chủ ý**: *đếm/ghi tin hỏng không được làm hỏng cú xếp ca — ca trực là việc chính,
tin là việc phụ* (`:213-215`).

#### 6.2.3. `remove()` — huỷ theo KHUNG GIỜ, không huỷ mù

Đây là hàm đáng đọc nhất phần này. Lịch sử của nó (`config_service.py:451-477`):

- **14/08** Tuyền chốt: gỡ ca thì lịch của ca ấy phải có kết thúc — **huỷ hẳn**,
  mã `BAC_SI_DOI_LICH`.
- **17/08** Tuyền bắt tiếp cái tinh hơn: *"xoá ca sáng để thêm cả ngày thì sao —
  về bản chất bác sĩ vẫn khám"*.

Bản cũ hỏi thô *"còn ca nào TRONG NGÀY không"* nên **sai cả hai chiều**:

| Thao tác | Bản cũ (mức NGÀY) | Hậu quả |
|---|---|---|
| Xoá SÁNG khi còn CHIỀU | thấy còn ca → không huỷ gì | Lịch 08:00 **sống sót mồ côi** dưới tên một bác sĩ sáng đó không đến — và cờ mất-bác-sĩ (cũng dò theo ngày) **không hề kêu** |
| Xoá SÁNG rồi thêm CẢ NGÀY | thấy hết ca → huỷ sạch | Lịch sáng **bị huỷ oan** trước khi ca mới kịp vào |

Luật mới: **chỉ huỷ những lịch mà giờ hẹn rơi RA NGOÀI hợp các ca CÒN LẠI của
chính bác sĩ ấy hôm đó** — cùng thước đo `core/shifts` với đường đặt lịch.

Các bước trong một transaction (`:479`):

1. Đọc ca sắp gỡ (`staff_id`, `work_date`, `station`), không có → `NotFoundError`.
2. Kiểm quyền: không phải quản lý thì chỉ xoá được ca của chính mình (`:489-492`).
3. `DELETE FROM work_roster` — **chỉ khi không phải dry_run** (`:494-500`).
4. Không phải ca khám (`station != 'LICH_KHAM'`) hoặc ca trống người → trả 0 ngay
   (`:502-503`). Gỡ ca thủ thuật không đụng lịch hẹn khám.
5. **Hợp các ca còn lại** — truy vấn `work_roster` cùng bác sĩ, cùng ngày, cùng
   trạm `LICH_KHAM`, kèm giờ mở cửa từ `clinic_hours_for_date` (`:510-529`). Hai
   mệnh đề then chốt:

```sql
AND w.id <> $4::uuid
AND coalesce(w.status, 'APPROVED') = 'APPROVED'
```

- `w.id <> $4` — **tự loại ca đang xoá**, vì ở chế độ `dry_run` nó vẫn còn trong bảng.
- `coalesce(w.status, 'APPROVED') = 'APPROVED'` — chỉ ca đã duyệt mới được tính là
  phủ. Comment ở `:506-509` nói rõ: *giữ lịch của khách trên một quyết định chưa
  ai duyệt là treo họ vào một lời hứa chưa có thật* (`NULL` đời cũ coi như đã duyệt).

6. Nhãn ca → khoảng phút → gộp (`:532-545`):

```python
windows = merge_windows([
    w for r in con_lai
    if (w := shift_window(r["shift"], r["open_minute"], r["close_minute"]))
       is not None
])
```

7. Lấy **ứng viên** — lịch của bác sĩ ấy, ngày ấy, còn cứu được:
   `slot_start > now()` và `status IN ('SCHEDULED','CSKH_CONFIRMED','CONFIRMED')`
   (`:547-569`). Không viết lại quá khứ, không lấy bác sĩ ra khỏi phòng đang khám.
8. Lọc theo khung:

```python
# Khung nào còn được phủ thì lịch ở yên — chỉ huỷ phần rơi ra
# ngoài. Không còn khung nào (windows rỗng) thì huỷ cả, như #117.
se_huy = [uv for uv in ung_vien if not covers(windows, uv["phut"])]
```
`config_service.py:570-572`

> **Hệ quả tự nhiên, không cần cơ chế hồi sinh nào:** muốn đổi sáng → cả ngày thì
> **THÊM ca mới TRƯỚC rồi mới xoá ca cũ**. Mọi lịch nằm trong khung còn phủ được
> giữ nguyên. Hộp xác nhận trên giao diện dạy đúng câu đó cho người dùng
> (`RosterRegisterTable.tsx:306-307`).

#### 6.2.4. `dry_run` — đo trước khi cắt

`dry_run=True` **đo mà không cắt**: bỏ qua `DELETE` ở bước 3, và thoát sớm ngay
trước câu `UPDATE`:

```python
if dry_run or not se_huy:
    return {
        "so_lich_huy": len(se_huy),
        "gio": [uv["gio"] for uv in se_huy],
    }
```
`config_service.py:574-578`

Đây đúng chỗ xứng đáng có hộp xác nhận: **cái giá là lịch hẹn của khách, không
lấy lại được** — ngược với hoàn tác rẻ tiền đã bỏ hộp xác nhận hôm 10/08
(`:470-473`).

Đường đi trọn vẹn của cơ chế này:

| Tầng | Việc |
|---|---|
| `RosterRegisterTable.tsx:287-311` | Gọi DELETE với `dry_run: true`, nếu `so_lich_huy > 0` thì `window.confirm` liệt kê **số lịch + giờ cụ thể** và chỉ đường đổi ca an toàn |
| `app/api/roster/route.ts:303-304` | Chuyển thành query string `?dry_run=true` |
| `api/v1/routers/config.py:212-227` | `dry_run: bool = False` → truyền thẳng vào service |
| `config_service.py:574` | Thoát sớm, không để lại dấu vết |

Bài kiểm khoá đúng chữ "không để lại dấu vết": `dry_run` trả `{"so_lich_huy": 1,
"gio": ["08:00"]}` **và** `conn.da_xoa_ca is False`, `conn.ids_huy is None`,
`conn.so_event == 0` (`test_huy_theo_khung_gio.py:143-150`).

#### 6.2.5. Vết `bac_si_da_go_id` và sự kiện `appointment.doctor_removed`

Khi thật sự huỷ, một câu `UPDATE` làm cả sáu việc:

```python
UPDATE public.appointment
   SET doctor_id = NULL,
       bac_si_da_go_id = doctor_id,
       bo_bac_si_luc = now(),
       status = 'CANCELLED',
       cancelled_at = now(),
       ly_do_huy_ma = 'BAC_SI_DOI_LICH',
       cancelled_by_staff_id = $3::uuid
 WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])
```
`config_service.py:580-596`

Từng dòng:

- `bac_si_da_go_id = doctor_id` — **chép tên cũ sang trước khi xoá**. Đặt
  `doctor_id = NULL` rồi thôi là **xoá mất một sự thật**: khách đã được hẹn với
  một người cụ thể, và CSKH sắp phải gọi giải thích (`test_go_ca_truc_go_bac_si.py:59-62`).
  Cột do migration `20260814000002_lich_hen_nho_bac_si_da_go.sql:24` thêm vào.
- `status = 'CANCELLED'` + `ly_do_huy_ma = 'BAC_SI_DOI_LICH'` — huỷ **hẳn**, mang
  mã lý do riêng để đếm được và để tin nhắn nói đúng nguyên nhân.
- `cancelled_by_staff_id` — huỷ nhầm phải truy được về ai.
- `ANY($2::uuid[])` — huỷ theo **danh sách id đã lọc**, không theo điều kiện ngày
  (nên câu này không còn `RETURNING`, và bài kiểm phải cắt cửa sổ 700 ký tự quanh nó
  thay vì neo vào `RETURNING` — `test_khoi_phuc_lich_khi_xep_lai_ca.py:33-35`).

Sau đó, **mỗi lịch một dòng `event_log`** với `event_type = 'appointment.doctor_removed'`
(`:597-623`) — payload gồm `ly_do: "ca_truc_bi_go"`, `bac_si_da_go_id`, `work_date`.
Sự kiện ấy đi tiếp tới đâu:

| Nơi đọc | Việc |
|---|---|
| `notification_templates.py:64-73` (`xoa_ca_bac_si`) | Soạn tin Telegram: *"⚠️ Xoá ca bác sĩ X · lịch HH:MM đã huỷ — gọi khách đặt lịch mới"*. Được gọi là **tin đáng gọi nhất** |
| `notification_relay.py:101` | `LEFT JOIN staff bs_go ON bs_go.id = a.bac_si_da_go_id` để tin có tên bác sĩ cũ |
| `week_appointments_service.py:141-170` | Lưới tuần dùng vết này để nói "đổi từ ai" |
| `audit_labels.py:44` | Nhãn tiếng Việt trong nhật ký: *"Gỡ bác sĩ khỏi lịch (ca trực bị xoá)"* |
| `booking_service.py:1203-1216` | Đặt lại lịch thì **xoá vết** (`patch["bac_si_da_go_id"] = None`) — vết chỉ tồn tại tới khi vấn đề được giải quyết |

**Cơ chế "xếp lại ca thì lịch tự quay về" đã bị GỠ, và có bia mộ.**
PR #115 từng dạy `add_shift` tự gắn lại những lịch mà `remove()` đã gỡ; nó **sống
đúng nửa ngày**. Cùng chiều 15/08 Tuyền gặp mặt còn lại của vấn đề: lịch bị gỡ là
một lịch **còn sống không bác sĩ**, đứng nguyên ở khung giờ cũ, và
`_patient_conflict` (*"khách đã có lịch giờ này"*) chặn chính con đường sửa nó
(`test_khoi_phuc_lich_khi_xep_lai_ca.py:3-14`). Luật mới: một sự kiện phải có KẾT
THÚC. Bài kiểm khoá luôn việc cơ chế cũ không lặng lẽ quay lại —
`assert "_khoi_phuc_lich_bi_go" not in ma` và `assert "CANCELLED" not in them_ca`,
*"add_shift mà đụng tới lịch đã huỷ là làm sống lại quá khứ"*
(`test_khoi_phuc_lich_khi_xep_lai_ca.py:54-59`).

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai — ca trực

- **Huỷ mù theo NGÀY sai cả hai chiều.** Đây là bug hiếm ở chỗ nó vừa quá mạnh
  vừa quá yếu cùng lúc. Test `test_huy_theo_khung_phu_con_lai_khong_theo_ngay`
  khoá bằng cách khẳng định `"con_ca" not in src` — *"phép kiểm mức-ngày đã bị
  thay, không được về"* (`test_go_ca_truc_go_bac_si.py:51`).
- **`dry_run` phải tự loại ca đang xoá.** Vì chưa `DELETE`, nếu quên `w.id <> $4`
  thì ca sắp gỡ tự tính là "còn phủ" → dry_run luôn báo 0.
- **`PENDING` không phải ca trực.** Bài kiểm chèn assert ngay trong connection
  giả để bắt việc điều kiện này bị bỏ (`test_huy_theo_khung_gio.py:77-79`).
- **Ẩn nút không phải là siết quyền.** Luồng tự đăng ký ca bị đóng ở
  `ROSTER_ROLES = ROSTER_ADMIN_ROLES` (`config_service.py:52`) chứ không chỉ ẩn
  bảng: để nguyên đường ghi thì ai cũng POST thẳng vào `/api/v1/roster/shifts`
  được, và ca họ ghi rơi vào `PENDING` — **vô hình với cả người xếp lịch lẫn màn
  chính thức, treo vĩnh viễn** (`:44-51`).
- **"Tuần đã xếp" ≠ "tuần đã chốt".** Trước `apply_week`, một bản nháp trải sẵn
  từ mẫu tuần cũng khoá được ô đặt lịch (`:638-642`).
- **Thông báo trỏ vào tường còn tệ hơn không thông báo.** `_bao_cskh_tuan_da_co_lich`
  cố ý trỏ `/customers` chứ không trỏ `/appointments/cho-xep-bac-si`, vì `roles.ts`
  không mở màn ấy cho CSKH — bấm vào là bị đá về `/home`, và *"người dùng học được
  rằng cái chuông này nói dối"* (`:761-777`).

---

### 6.3. `src/clinicai/services/booking_override_service.py` — sức chứa 3 tầng (852 dòng)

**MỘT LUẬT LÀ MỘT CÂU:** *"ai — thứ mấy — khung giờ nào — mấy chỗ — áp dụng tới
bao giờ"*. Người vận hành chỉ thấy một bảng; bên dưới có hai bảng database và
`save_rule()` chọn hộ (`booking_override_service.py:1-20`).

| Tầng | Bảng | Đặc điểm |
|---|---|---|
| **3** | `slot_booking_override` | **Có khoảng NGÀY** → luật tạm, hết hạn thì thôi. Cao nhất |
| **2** | `doctor_booking_override` | Không có ngày → luật thường trực, lặp mãi |
| **1** | `clinic.settings.booking` | Mặc định phòng khám |

> **Vì sao người dùng không nên thấy ba tầng.** Bản trước phơi tầng 2 và tầng 3
> thành hai tab riêng, và Quang hỏi đúng câu phải hỏi: *"tại sao không cho vào
> một khung thiết lập chung?"* — **Ba tầng là cách LƯU, không phải cách NGHĨ.**
> Bắt người vận hành chọn tab nghĩa là bắt họ học cấu trúc bảng trước khi đặt được
> một con số (`:17-20`).

| Hàm / hằng | Giải thích |
|---|---|
| `MAX_CAP = 100`, `MAX_SLOT_RANGE_DAYS = 90` (`:54-56`) | Trần an toàn, **soi gương CHECK trong database** |
| `WindowTrim` (`:62`) | Dataclass đóng băng: `action` (`deleted`/`trimmed`/`split`), `keep`, `keep_extra` |
| `plan_window_trim(old_start, old_end, new_start, new_end)` (`:71`) | Phần nào của luật cũ sống sót. Hàm thuần, xem 6.3.1 |
| `validate_rule(...)` (`:102`) | Một luật có nói được thành câu không — cùng luật với CHECK nhưng **trả câu tiếng Việt thay vì tên ràng buộc** |
| `BookingOverrideService.save_rule(...)` (`:168`) | Đường ghi duy nhất. Chọn tầng 2 hay 3 theo việc có `date_start`/`date_end` |
| `.list_rules(...)` (`:261`) | Hai tầng **gộp làm một danh sách**, kèm cờ `shadowed` |
| `._write_standing(...)` (`:335`) | Ghi tầng 2 — **luật mới thắng**, cắt luật cũ |
| `._write_temp(...)` (`:446`) | Ghi tầng 3 — chồng lấn thì báo lỗi, không cắt |
| `._assert_doctor_in_clinic(...)` (`:528`) | Bác sĩ có thuộc phòng khám này không |
| `.delete_doctor_override(...)` (`:549`) / `.delete_slot_override(...)` (`:586`) | Hai đường xoá vì hai bảng. Danh sách luật mang theo `kind` nên giao diện gọi đúng đường mà **người dùng vẫn chỉ thấy một nút "Xoá"** |
| `._clear_minute_window(...)` (`:623`) | Dọn đúng khoảng phút luật mới sắp chiếm, giữ nguyên phần còn lại |
| `._find_shadowing_exceptions(...)` (`:731`) | Luật tạm nào đang đè lên khung vừa lưu — **chỉ đọc** |
| `._find_overlap(...)` (`:776`) | Mô tả luật đang chiếm khung, để câu lỗi gọi được tên nó |
| `._log_event(...)` (`:824`) | Ghi `event_log` với `source = 'api:booking-override'` |

#### 6.3.1. `plan_window_trim` — bốn nhánh, toàn số nguyên

Tách khỏi phần chạy SQL vì đây là **chỗ dễ sai nhất và cũng dễ kiểm nhất**: ghép
chung với INSERT/UPDATE thì muốn thử một trường hợp biên phải dựng cả một phòng
khám (`:76-79`).

```python
if old_start >= new_start and old_end <= new_end:
    return WindowTrim(action="deleted", keep=None)          # nằm trọn bên trong
if old_start < new_start and old_end > new_end:
    return WindowTrim(action="split",
                      keep=(old_start, new_start),
                      keep_extra=(new_end, old_end))        # khung mới nằm giữa
if old_start < new_start:
    return WindowTrim(action="trimmed", keep=(old_start, new_start))  # thò đầu trái
return WindowTrim(action="trimmed", keep=(new_end, old_end))          # thò đuôi phải
```
`booking_override_service.py:85-99`

Ví dụ nhánh `split` (`:361-363`):

```
cũ  18:00 ─────────────── 19:00   (4 ca)
mới        18:15 ─ 18:30          (9 ca)
⇒   18:00 ─ 18:15 (4)  18:15 ─ 18:30 (9)  18:30 ─ 19:00 (4)
```

Mọi khoảng đều **nửa mở** `[start, end)` — cùng quy ước với `int4range` trong ràng
buộc EXCLUDE và với `resolve_effective_cap` (`>= start AND < end`). Nhờ vậy hai
khung liền kề 18:00–18:15 và 18:15–18:30 **không** coi là chồng lấn, và luật cũ bị
cắt tới đúng mốc của luật mới **không để lại phút hở** (`:80-83`).

> Mỗi nhánh lệch một phút là một khoảng giờ không luật nào phủ, và **khoảng hở đó
> không báo lỗi — nó chỉ âm thầm rơi về số chỗ mặc định** (`test_window_trim.py:8-11`).

#### 6.3.2. "Luật mới cắt luật cũ" — vì sao không phải là lỗi 409

`_write_standing` **không phải một hàm "create"**. Trưởng ca nói *"BS Thành,
18:00–18:15, 9 ca"* và điều đó **phải trở thành sự thật**, kể cả khi đã có luật
khác phủ khung ấy.

Bản trước chỉ INSERT, nên lần lưu thứ hai đụng ràng buộc `doctor_override_no_overlap`
và — qua handler toàn cục — trả về *"Lịch hẹn xung đột khung giờ với appointment
khác"*: **một câu nói về LỊCH HẸN cho người đang sửa LUẬT**, và không có lịch hẹn
nào để đi tìm. Cấu hình phòng khám trở thành thứ chỉ ghi được đúng một lần
(`:350-355`, `test_window_trim.py:3-6`).

Sửa đúng **không phải** là bỏ ràng buộc EXCLUDE: *hai luật cùng phủ một khung thì
không phải "luật nào thắng" mà là **không có luật nào**.* Chỗ sai là bắt người
dùng tự dọn (`:357-359`).

`_clear_minute_window` chạy trước INSERT (`:370`), và câu `SELECT … FOR UPDATE` của
nó (`:652-674`) rất kỷ luật về phạm vi:

- `coalesce(doctor_id, '000…0') = coalesce($2, '000…0')` — **NULL chỉ chồng với
  NULL**: luật "tất cả bác sĩ" không cắt luật của BS Thành và ngược lại. Hai luật đó
  cùng tồn tại, và `resolve_effective_cap` chọn cái cụ thể hơn (`:365-367`).
- `coalesce(weekday, -1)` — cùng lý lẽ cho trục thứ.
- **Chỉ cắt theo TRỤC PHÚT, không theo trục ngày** (`:642-645`): giao diện luôn ghi
  luật thường trực từ hôm nay và không có ngày kết thúc, nên trục ngày không có gì
  để cắt; làm cả hai trục sẽ sinh **tới chín mảnh cho một thao tác** và không ai
  đọc nổi bảng luật sau đó.

Mảnh thứ hai của một luật bị cắt đôi được tạo bằng `INSERT … SELECT` từ **chính
dòng vừa thu hẹp** (`:699-713`) để mọi cột khác (số chỗ, hiệu lực, lý do, người tạo)
đi theo — *"liệt kê tay ở đây là chỗ để quên một cột"*. Mọi thứ bị cắt/xoá gói vào
`replaced` và ghi `event_log` (`:432-435`): *"Không có nút nào tạo ra dòng này, nên
nếu không ghi ở đây thì nó biến mất không dấu vết."*

Ngược lại, **tầng 3 KHÔNG cắt gì cả** — chồng lấn thì bắt `ExclusionViolationError`,
gọi `_find_overlap` để **nêu tên luật đang chiếm chỗ**, rồi ném `ValidationError`
(`:482-501`). Phải bắt **ở đây** chứ không ở handler toàn cục, vì *tên ràng buộc
không mang theo dòng mà nó va phải* (`:483-486`, `:788-791`).

#### 6.3.3. `shadowed` — một luật đúng vẫn có thể không có tác dụng hôm nay

Sau khi ghi tầng 2, `_write_standing` hỏi tầng 3 xem có luật tạm nào đang phủ
khung vừa lưu không (`:410-416`). Lý do ghi thẳng trong comment (`:401-409`):

> Luật có ngày đè lên luật thường trực. Nên nếu còn một luật tạm phủ đúng khung
> vừa lưu, Trưởng ca sẽ lưu thành công, quay ra lưới, và **KHÔNG THẤY GÌ ĐỔI** —
> rồi kết luận là chức năng hỏng. Prod đang có đúng một dòng như thế cho BS Thành
> (18:00–19:00, hết hạn 09/08). **Không tự xoá nó**: một luật tạm có lý do và có
> người chịu trách nhiệm. Chỉ nói ra.

`list_rules` tính cùng một cờ cho cả danh sách bằng `EXISTS` trong SQL (`:300-311`),
**thay vì để giao diện tự suy ra thứ tự ưu tiên và nói lệch với backend** (`:266-269`).
Và nó chỉ gắn cờ khi luật tạm phủ **đúng tập bác sĩ ấy**: bản đầu còn gắn cờ khi
luật thường trực là "tất cả bác sĩ" mà luật tạm chỉ của MỘT người — sai, vì luật ấy
vẫn đang chạy cho những bác sĩ còn lại. *"Một nhãn cảnh báo sai chỗ dạy người dùng
bỏ qua mọi nhãn cảnh báo"* (`:273-277`).

#### 6.3.4. Ai thực sự quyết định con số? `resolve_effective_cap()` trong SQL

Python **ghi** luật; **đọc** luật là việc của một hàm SQL, để lưới đặt lịch và
trigger chặn quá tải không bao giờ nói hai điều khác nhau. Trong tầng 2, `ORDER BY`
**nói ra thứ tự cụ-thể-dần thay vì để nó phụ thuộc dòng nào được đọc trước**:

```sql
ORDER BY d.doctor_id IS NULL,      -- luật riêng trước luật chung
         d.weekday IS NULL,        -- luật theo thứ trước luật mọi thứ
         d.minute_start IS NULL,   -- luật theo khung trước luật cả ngày
         d.effective_from DESC
LIMIT 1
```
`supabase/migrations/20260803000011_standing_rules_and_clinic_hours.sql:219-223`

Kết quả cuối là ba lần `coalesce(v_slot…, v_doc…, v_cl…)` (`…sql:230-233`) — tầng 3
→ tầng 2 → tầng 1, đúng thứ tự docstring Python hứa.

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai — sức chứa

- **Mốc giờ phải là bội số 5.** `validate_rule` từ chối 18:07 vì *mọi độ dài khung
  hợp lệ (chia hết 60) là bội số của 5, nên một mốc lẻ chắc chắn cắt ngang một
  khung và để lại vùng không luật nào phủ — một khoảng hở âm thầm, không báo lỗi*
  (`:127-131`).
- **Tầng 3 không có cột `weekday`.** Gửi kèm `weekday` với khoảng ngày là lỗi chứ
  không phải bị lờ đi: *"một ô người dùng điền mà hệ thống lờ đi là dạng sai tệ
  nhất"* (`:148-154`).
- **Nhiều bác sĩ = nhiều DÒNG, một GIAO DỊCH.** Gộp họ vào một dòng sẽ khiến "bỏ BS
  Hoa ra" thành thao tác không làm được; còn ghi ngoài transaction thì *"chọn hai
  bác sĩ mà chỉ ghi được một là trạng thái tệ hơn không ghi được gì"* (`:186-195`).
- **`doctor_ids` rỗng ≠ không làm gì** — nó nghĩa là *mọi bác sĩ*, một dòng
  `doctor_id NULL` (`:207-208`).
- **CHECK trong database mới là chốt chặn thật**; `validate_rule` chỉ kiểm sớm để
  một con số sai thành câu tiếng Việt thay vì tên ràng buộc (`:33-35`).

---

### 6.4. `src/clinicai/services/dispatch_service.py` — bảng điều phối của Trưởng ca (633 dòng)

Hai nguyên tắc mở đầu file (`dispatch_service.py:1-14`):

> **NGUỒN DỮ LIỆU LÀ MỘT.** Bảng toàn cảnh, hàng đợi từng phòng, TV phòng chờ và
> cảnh báo đều đọc từ `visit.current_node_code/current_room_id`. *"Bốn màn hình đọc
> bốn nơi là cách chắc chắn nhất để chúng nói bốn điều khác nhau."*
>
> **MỌI ĐƯỜNG GHI ĐI QUA ĐÚNG MỘT HÀM SQL** (`move_visit_to_station`). Đóng bước cũ,
> mở bước mới, cập nhật con trỏ, ghi nhật ký — bốn việc trong một giao dịch có khoá
> dòng. Làm bốn việc đó ở Python thì một lần mất kết nối giữa chừng để lại bệnh nhân
> ở **hai hàng đợi**.

| Hàm / hằng | Giải thích |
|---|---|
| `LIVE_VISIT_STATUSES` (`:31`) | `("OPEN", "IN_PROGRESS")` — lượt đã đóng không còn là việc của Trưởng ca |
| `_OVERVIEW_SQL` (`:35`) | Mỗi bệnh nhân đang trong phòng khám là một dòng |
| `_STATIONS_SQL` (`:97`) | Tải của từng phòng: đang phục vụ / đang chờ / chờ lâu nhất |
| `DispatchService.overview(...)` (`:157`) | Chạy `_OVERVIEW_SQL`, map qua `_overview_row` |
| `.stations(...)` (`:163`) | Chạy `_STATIONS_SQL`; `location_id = None` = bảng tổng của quản lý |
| `.alerts(...)` (`:207`) | Tính từ **chính hai truy vấn trên**, không từ bảng cảnh báo riêng |
| `.move(...)` (`:221`) | Chuyển bệnh nhân sang bước/phòng khác |
| `.apply_route(...)` (`:279`) | Chọn tuyến điều phối cho một lượt khám |
| `.routes(...)` (`:387`) | Danh sách mẫu tuyến đang bật |
| `.history(...)` (`:399`) | Nhật ký điều phối từ view `v_dispatch_history` |
| `.set_threshold(...)` (`:430`) | Đặt ngưỡng chờ cho một phòng hoặc mặc định cả phòng khám |
| `_station_state(...)` (`:481`) | Màu của một phòng: `ok` / `warning` / `critical`. Hàm thuần |
| `build_alerts(patients, rooms)` (`:499`) | Bốn loại cảnh báo, xếp theo mức độ. Hàm thuần |
| `next_step_of(route, done, current)` (`:582`) | Bước đầu tiên trong tuyến chưa xong và không phải bước hiện tại |
| `_overview_row(r)` (`:599`) | Record → dict cho giao diện |
| `_json(value)` (`:630`) | `json.dumps(..., ensure_ascii=False)` — giữ tiếng Việt đọc được trong `event_log` |

Bốn chỗ đáng đọc trong SQL:

- **`wait_minutes` ≠ `total_minutes`** (`:63-70`): đợi ở BƯỚC HIỆN TẠI tính từ
  `current_node_since`, tổng thời gian trong phòng khám tính từ `checked_in_at`.
  *"Trộn chúng làm một sẽ khiến người vừa được chuyển phòng trông như vừa mới đến."*
- **Một phòng phục vụ nhiều bước** (`:100-106`): `node_code` chỉ là bước CHÍNH, danh
  sách thật ở `clinic_room_node` → `serves_nodes`. Đọc cột đơn thì *"một ca Nam khoa
  sẽ không thấy phòng khám nào"*.
- **`serving` vs `waiting`** (`:110-115`): `IN_PROGRESS` là đang phục vụ, `PENDING`
  là đang chờ. Gộp lại thì Trưởng ca không biết phòng đang kẹt hay đang rảnh.
- **Lọc cơ sở bằng `coalesce`, không bằng `OR`** (`:133-141`):
  `AND r.location_id = coalesce($3::uuid, r.location_id)` — cùng nghĩa với
  `($3 IS NULL OR col = $3)` nhưng **không có nhánh OR nào để bộ lọc tenant lọt qua**.
  Không lọc thì nhân sự Hào Nam bấm chuyển bệnh nhân sang phòng của Kim Ngưu.

**`move()` — luật thứ tự chạy TRƯỚC, trong cùng transaction** (`:234-257`):
`gate_enforce()` chạy trước `move_visit_to_station()`, vì *"chạy sau thì bệnh nhân đã
bị chuyển rồi mới báo 'không được' — và không có nút hoàn tác nào cho một người đang
đi bộ sang phòng khác"*. Luật bị bỏ qua được trả về `gate_overridden` để **màn hình
nói rõ vừa bỏ qua luật nào, chứ không im lặng cho qua** (`:275-276`). Lỗi từ hàm SQL
đưa thẳng lên người dùng, chỉ lấy dòng đầu (`:258-262`) — nó đã là câu tiếng Việt
đúng vấn đề (*"Phòng đã chọn không phục vụ bước …"*).

**`_station_state` — vượt CẢ HAI ngưỡng mới là `critical`**, vượt một là `warning`
(`:490-496`): *"Coi mọi lần vượt là critical sẽ làm cả màn hình đỏ vào giờ cao điểm,
và một màn hình đỏ toàn bộ không nói cho Trưởng ca biết nên xử lý phòng nào trước."*
`build_alerts` sinh bốn loại — `room_overloaded`, `wait_too_long` (critical khi vượt
**gấp đôi** ngưỡng), `missing_next_step`, `no_route` — mỗi cảnh báo kèm **danh sách
bệnh nhân bị ảnh hưởng** và một câu dễ hiểu, không phải mã kỹ thuật (`:499-579`).

---

### 6.5. Các bài kiểm — hành vi, không phải chuỗi ký tự

| File | Khoá điều gì |
|---|---|
| `src/tests/test_huy_theo_khung_gio.py` | Chạy **chính** `RosterService.remove` với connection giả định tuyến theo nội dung SQL. Bốn tình huống: xoá SÁNG còn CHIỀU → chỉ huỷ 08:00; thêm CẢ NGÀY trước rồi xoá SÁNG → **không huỷ gì**; hết ca → huỷ cả hai; `dry_run` → đo mà không để lại vết |
| `src/tests/test_khoi_phuc_lich_khi_xep_lai_ca.py` | **Bia mộ** của cơ chế "xếp lại ca thì lịch tự quay về". Khoá luật mới (huỷ hẳn + mã lý do + vết `bac_si_da_go_id`) và khoá luôn việc cơ chế cũ không lặng lẽ quay lại |
| `src/tests/services/test_go_ca_truc_go_bac_si.py` | Bốn ranh giới đọc được từ mã nguồn: cùng transaction, `DELETE` trước `UPDATE`, chỉ `LICH_KHAM`, chỉ lịch còn cứu được |
| `src/tests/services/test_window_trim.py` | Bốn nhánh `plan_window_trim` + hai khung liền kề không đụng nhau |
| `src/tests/unit/test_shift_windows.py` | Mốc 12:00, nửa mở, ca sáng của ngày mở cửa 17:00 là `None`, nhãn lạ = cả ngày, ba dòng FULL vẫn là một khoảng |

> **Luật 12.5** (`test_khoi_phuc_lich_khi_xep_lai_ca.py:17`, `test_go_ca_truc_go_bac_si.py:40`):
> quyết định bị đảo thì bài kiểm được **viết lại kèm lý do**, không bị xoá — nên đọc
> test là đọc được cả lịch sử vì sao luật hiện tại trông như thế.

---

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai — toàn phần 6

1. **"Bác sĩ có trực hôm đó" là câu hỏi SAI.** Câu đúng là *"khung phút này có nằm
   trong ca nào của bác sĩ ấy không"*. Mọi lỗi nặng nhất phần này đều sinh ra từ
   việc hỏi ở mức NGÀY: lịch mồ côi, lịch huỷ oan, và bác sĩ trực ca sáng bị mời đặt
   lúc 18:00.
2. **Ba tầng sức chứa KHÔNG phải là ba màn hình.** Chúng là cách lưu. Người dùng chỉ
   chọn "Mãi mãi" hay một khoảng ngày.
3. **Tầng 2 cắt luật cũ; tầng 3 từ chối.** Hai hành vi khác nhau có chủ ý: luật
   thường trực là thứ Trưởng ca sửa hằng ngày, luật tạm là ngoại lệ có người chịu
   trách nhiệm nên phải xoá tay.
4. **Nửa mở `[lo, hi)` là hợp đồng xuyên hệ.** `core/shifts.covers`, `int4range` của
   EXCLUDE, `>= start AND < end` của `resolve_effective_cap`, và `plan_window_trim`
   đều dùng cùng quy ước. Đổi một chỗ mà quên chỗ khác thì mốc 12:00 hoặc thuộc về
   cả hai ca, hoặc không thuộc ca nào.
5. **`dry_run` không phải tính năng phụ** — nó là điều kiện để hộp xác nhận nói được
   con số thật. Hộp không có con số chỉ dạy người dùng bấm "OK" theo phản xạ; đó là
   lý do hộp cho *hoàn tác* đã bị bỏ hôm 10/08, còn hộp này thì giữ.
6. **Vết `bac_si_da_go_id` là để GỌI ĐIỆN, không phải để hoàn tác.** Nó trả lời
   *"khách này trước hẹn với ai"* cho CSKH rồi bị xoá khi lịch được đặt lại
   (`booking_service.py:1216`). Làm sống lại một lịch đã `CANCELLED` là viết lại quá
   khứ — khách có thể đã được gọi báo huỷ rồi.
7. **Sự kiện là đường duy nhất đánh thức người không nhìn màn hình.** Realtime lo
   người đang mở tab; `roster.shift_added_cho_xep` và `appointment.doctor_removed`
   lo người đang làm việc khác. Cả hai ghi với `event_published = FALSE` để relay
   nhặt lên sau, và cả hai đường ghi đều **nuốt lỗi có chủ ý** — việc chính đã xong,
   tin là việc phụ.


---

## PHẦN 7. HỒ SƠ BỆNH NHÂN VÀ CHĂM SÓC KHÁCH HÀNG

Phần này gồm hai nửa dính chặt vào nhau:

- **Hồ sơ** — ai là khách của phòng khám: `patient_service.py`, `mpi_service.py`, cùng bảng
  số-thêm `patient_sdt_them` và cột tìm kiếm gộp `patient.sdt_tim_kiem`.
- **Chăm sóc (CSKH)** — phòng khám đã CHẠM tới khách những lần nào:
  `tuong_tac_cskh_service.py` (sổ tương tác + hoàn tác), `recall_service.py` /
  `recall_job_service.py` (nhắc tái khám), `cskh_service.py`, `phan_hoi_khach_service.py`.

> Một câu xuyên suốt cả phần: **hồ sơ thì được sửa, sổ chạm thì không.** Hồ sơ bệnh nhân
> là *trạng thái hiện tại* (số điện thoại mới thì ghi đè số cũ). Sổ tương tác là *chuỗi sự
> việc đã xảy ra* — chỉ thêm, không sửa, không xoá. Hai thứ này dùng hai cơ chế "rút lại"
> hoàn toàn khác nhau, và đó là gốc của mọi thắc mắc ở mục 7.6.

---

### 7.1. `src/clinicai/core/phone.py` — chuẩn hoá số điện thoại

Chỉ 45 dòng nhưng là **hợp đồng** cho mọi chỗ đụng tới số điện thoại: form nhập, dò trùng,
tra cứu, ràng buộc CHECK của database.

| Hàm | Giải thích |
|---|---|
| `normalize_vn_phone(value)` (`phone.py:10`) | Trả **dạng chuẩn 10 số bắt đầu bằng 0**, hoặc `None` nếu không hợp lệ. Nhận được cả `090…`, `8490…`, `+8490…`, `0084…` và dạng 9 số thuê bao. Dấu cách, ngoặc, gạch nối bị bỏ qua; **chữ cái thì bị loại thẳng** (`re.search(r"[^\d\s()+.\-]")` ở `phone.py:17`) |
| `phone_variants(value)` (`phone.py:39`) | Trả **ba cách viết** của cùng một số: `0903333333`, `84903333333`, `+84903333333` |

Vì sao cần cả hai:

- `normalize_vn_phone` dùng khi **GHI** — mọi số đi vào database đều về đúng một dạng.
- `phone_variants` dùng khi **ĐỌC** — vì dữ liệu cũ đã lỡ có cả ba cách viết trong bảng, nên
  câu tra phải hỏi `= ANY($1::text[])` với cả ba, chứ không thể chỉ hỏi dạng chuẩn.

```python
_VN_MOBILE_PREFIXES = frozenset({"03", "05", "07", "08", "09"})
national = f"0{subscriber}"
if (len(national) != 10 or not national.isdigit()
        or national[:2] not in _VN_MOBILE_PREFIXES):
    return None
```

Lưu ý một chỗ **lệch có chủ ý**: `PHONE_RE` trong `patient_service.py:31` còn chấp nhận đầu
số `02` (số cố định), còn `normalize_vn_phone` thì không — nó chỉ nhận di động. Nghĩa là số
bàn ghi được vào `phone_primary` nhưng **không** thêm được vào bảng số-thêm. Đúng ý đồ: bảng
số-thêm sinh ra để gọi/nhắn cho khách.

---

### 7.2. `src/clinicai/services/patient_service.py` — tạo và sửa hồ sơ

| Hàm | Giải thích |
|---|---|
| `validate_phone(value, label)` (`:34`) | Ném `ValidationError` **bằng tiếng Việt** khi số sai định dạng. Kiểm ở server vì "form không phải người gọi duy nhất" (comment `:29`) |
| `_INSERT_COLUMNS` (`:44`) | 22 cột nhân khẩu học ghi lúc INSERT, theo đúng thứ tự. `patient_code` và `clinic_id` được nối thêm ở chỗ dựng câu |
| `_generate_patient_code(attempt)` (`:70`) | Sinh mã người đọc được `BN-YYYY-XXXXXX`. Hậu tố lấy từ **micro giây**; `attempt * 7919` (số nguyên tố) làm lệch mã ở lần thử lại. Cột có UNIQUE làm lưới an toàn cuối |
| `_record_to_dto(record)` (`:82`) | `asyncpg.Record` → `PatientDTO` |
| `create_patient(data, identity)` (`:99`) | Đăng ký khách mới — 5 bước, xem bên dưới |
| `_insert_patient(conn, data, clinic_id)` (`:225`) | INSERT + thử lại tối đa 5 lần khi đụng mã trùng |
| `_mpi_autoqueue(dto, data, clinic_id)` (`:276`) | Chạy dò trùng MPI **best-effort**, nuốt mọi lỗi |
| `get_by_id(clinic_patient_id, clinic_id)` (`:302`) | Đọc một hồ sơ; `None` nếu không có |
| `get_summary_data(...)` (`:316`) | Tóm tắt cho tầng tool: hồ sơ + có thai đang theo dõi (`pregnancy.outcome='ONGOING'`) + lần khám COMPLETED gần nhất. Trả **dict thô**, không nặn hình — việc nặn để tầng trên làm |
| `get_by_phone(phone, clinic_id)` (`:353`) | Mọi hồ sơ có số này ở **chính / người nhà / số thêm** |
| `find_phone_duplicates(phone, clinic_id)` (`:373`) | Như trên nhưng chỉ trả 3 trường tối thiểu, tối đa 10 dòng, **không ghi log số lẫn tên** |
| `update_patient(...)` (`:414`) | Sửa từng phần + **khoá lạc quan** |
| `them_so_dien_thoai(...)` (`:511`) | Gắn thêm một số vào hồ sơ có sẵn |
| `xoa_so_dien_thoai(...)` (`:602`) | Gỡ một số THÊM (xoá thật, không soft-delete) |

#### 7.2.1. `create_patient` — thứ tự các chốt là cố ý

Năm bước, và **thứ tự** mới là phần đáng đọc (`patient_service.py:102-223`):

1. **Cơ sở phải có thật và đang hoạt động** (`:129-141`). Thêm vào sau buổi nghiệm thu
   11/08/2026, vì hai lỗi cùng một chỗ: `location_id` không tồn tại → khoá ngoại nổ ở tầng
   DB → người dùng nhận **HTTP 500**; `location_id` trỏ cơ sở đã đóng cửa → khoá ngoại hợp
   lệ nên **đi lọt trong im lặng**, tạo hồ sơ ở một chi nhánh không còn ai làm việc.
2. **CCCD — chặn cứng** (`:144-156`). Cột UNIQUE, `force` KHÔNG vượt được. Ném `ConflictError`
   kèm mã hồ sơ và tên hồ sơ cũ để người trực biết đi tìm ở đâu.
3. **Số điện thoại — chặn mềm** (`:159-174`). Trùng thì **trả về `duplicate=True` và KHÔNG
   insert**, để người trực quyết định. Bấm lại với `force=True` là qua.
4. **INSERT** qua `_insert_patient`.
5. **Ghi `event_log` trong CÙNG transaction với dòng hồ sơ** (`:183-219`).

```python
if data.phone_primary and not data.force:
    variants = _phone_variants(data.phone_primary)
    dupes = await conn.fetch(
        "SELECT clinic_patient_id, patient_code, full_name, "
        "date_of_birth FROM patient "
        "WHERE (phone_primary = ANY($1::text[]) "
        "OR phone_secondary = ANY($1::text[])) "
        "AND clinic_id = $2::uuid LIMIT 5;",
        variants, clinic_id,
    )
    if dupes:
        return PatientCreateResult(duplicate=True, matches=[...])
```

**Vì sao chặn mềm chứ không cứng:** mẹ đăng ký bằng số của mình cho con là hợp lệ. Chặn cứng
số điện thoại sẽ khoá đúng ca hợp lệ hay gặp nhất.

Về bước 5, comment ở `:179-182` nói rõ vì sao audit phải nằm trong cùng transaction: bản
trước dashboard ghi audit **sau đó** bằng khoá service-role, nên một cú crash ở giữa để lại
một bệnh nhân **không ai giải trình được** — và đó là lần ghi cuối cùng của frontend còn
vượt RLS.

> Bước 5 ở trong transaction, nhưng bước dò trùng MPI (`:222`) thì ở **ngoài** — cố ý. MPI
> hỏng không được làm hỏng việc đăng ký khách.

#### 7.2.2. `_insert_patient` — savepoint cho mỗi lần thử lại

```python
for attempt in range(5):
    patient_code = _generate_patient_code(attempt)
    try:
        async with conn.transaction():          # ← SAVEPOINT
            row = await conn.fetchrow(query, patient_code, *values)
    except asyncpg.UniqueViolationError as exc:
        constraint = (exc.constraint_name or "") + " " + str(exc)
        if "national_id" in constraint.lower():
            raise ConflictError("CCCD này vừa được tạo cho hồ sơ khác.") from exc
        logger.warning("patient_code_clash", patient_code=patient_code)
        continue
```

Ba điểm then chốt:

- `async with conn.transaction()` **lồng bên trong** transaction của `create_patient` chính
  là một **SAVEPOINT**. Không có nó thì sau một UNIQUE violation, cả transaction ngoài bị
  Postgres đánh dấu aborted và mọi câu tiếp theo đều lỗi — vòng lặp thử lại vô nghĩa.
- Phân biệt hai loại đụng UNIQUE: đụng `national_id` là **đua với một request khác** → báo
  rõ, KHÔNG thử lại (thử lại cũng vẫn đụng). Đụng `patient_code` → sinh mã khác và thử lại.
- Hết 5 lần → `ValidationError("Không tạo được mã BN, thử lại.")` chứ không treo.

#### 7.2.3. `update_patient` — khoá lạc quan `sua_luc`

```python
sua_luc = updates.pop("sua_luc", None)   # thẻ khoá, KHÔNG phải cột
...
khoa_sql = ""
if sua_luc is not None:
    values.append(sua_luc)
    khoa_sql = f"AND updated_at = ${len(values)} "
```

- `sua_luc` là **mốc `updated_at` mà máy khách đã đọc**, không phải một cột để ghi. Dòng
  `updates.pop(...)` ở `:433` phải chạy trước khi dựng câu SET, nếu không nó biến thành
  `sua_luc = $n` và câu lệnh nổ.
- Nếu ai đó chen vào giữa, `updated_at` dưới database đã đổi → UPDATE khớp **0 hàng** →
  người bấm sau bị từ chối thay vì lặng lẽ xoá công của người bấm trước.
- Khớp 0 hàng có **hai nguyên nhân rất khác nhau**, nên `:483-499` đọc lại một lần nữa: nếu
  hồ sơ vẫn tồn tại thì ném `ConflictError` ("vừa được người khác sửa"), chỉ khi hồ sơ thật
  sự không có mới ném `ResourceNotFoundError`. Trả nhầm "không tìm thấy" cho một hồ sơ đang
  hiện trên màn hình là nói dối người dùng.
- Bộ lọc tenant `AND clinic_id = $n::uuid` là **vô điều kiện** (`:455-460`). Backend nối
  bằng quyền chủ database nên **RLS không áp dụng**; một câu UPDATE quên `clinic_id` sẽ với
  tới mọi phòng khám. Bản trước chỉ thêm bộ lọc *khi có identity* — và đúng cái "khi không
  có" ấy là lỗ hổng.

---

### 7.3. Nhiều số điện thoại cho một bệnh nhân

Đây là tính năng Tuyền chốt ngày 15/08/2026. Vấn đề: khách dùng 2–3 số, mà hồ sơ chỉ có hai
ô (`phone_primary`, `phone_secondary` = số người nhà). Số thứ ba **không có chỗ ghi**, nên
người trực hoặc ghi đè số cũ (mất lịch sử liên lạc) hoặc tạo hồ sơ mới (**tách đôi bệnh án**).

#### 7.3.1. Thiết kế hai tầng (`supabase/migrations/20260815000002_nhieu_so_dien_thoai.sql`)

**Tầng 1 — `patient_sdt_them`** (`:20-38`): nguồn sự thật, mỗi dòng một số, biết ai thêm và
lúc nào.

```sql
so_dien_thoai text NOT NULL CHECK (so_dien_thoai ~ '^0[0-9]{9}$'),
loai text NOT NULL DEFAULT 'CHINH' CHECK (loai IN ('CHINH', 'NGUOI_NHA')),
UNIQUE (clinic_patient_id, so_dien_thoai)
```

- CHECK ép **đúng dạng mà `normalize_vn_phone` trả ra**. Một số `+84 90…` lọt vào đây là cột
  tìm kiếm chứa một dạng mà không ai gõ để tra.
- UNIQUE là **(hồ sơ, số)**, KHÔNG unique toàn cục: hai mẹ con dùng chung một số là hợp lệ.
- Bảng có RLS + `GRANT SELECT` cho `authenticated` (`:47-64`) — client **chỉ đọc**, mọi
  đường ghi đi qua backend.

**Tầng 2 — `patient.sdt_tim_kiem`** (`:68-117`): cột **GỘP MỌI SỐ** do trigger nuôi.

```sql
CREATE OR REPLACE FUNCTION public.tinh_sdt_tim_kiem(
    p_benh_nhan uuid, p_chinh text, p_nguoi_nha text
) RETURNS text LANGUAGE sql STABLE AS $$
    SELECT nullif(concat_ws(' ', p_chinh, p_nguoi_nha,
        (SELECT string_agg(t.so_dien_thoai, ' ' ORDER BY t.created_at)
           FROM public.patient_sdt_them t
          WHERE t.clinic_patient_id = p_benh_nhan)), '')
$$;
```

Ba trigger/lời gọi dùng **chung một hàm** này để không bao giờ tính ba kiểu:

| Thành phần | Vai trò |
|---|---|
| `tinh_sdt_tim_kiem()` (`:73`) | Công thức duy nhất: nối số chính + số người nhà + mọi số thêm, cách nhau bằng dấu cách |
| `patient_lam_tuoi_sdt()` + trigger BEFORE trên `patient` (`:88-99`) | Mọi INSERT/UPDATE trên `patient` tự làm tươi cột gộp |
| `sdt_them_lam_tuoi_patient()` + trigger AFTER trên `patient_sdt_them` (`:104-117`) | Thêm/sửa/xoá một số thì **chạm hồ sơ mẹ** bằng một `UPDATE … SET clinic_patient_id = clinic_patient_id` rỗng — đủ để trigger BEFORE ở trên chạy. **Không chép công thức lần hai** |
| Backfill (`:120-124`) | Hồ sơ cũ tra được bằng cột mới ngay từ giây đầu |

> **VÌ SAO PHẢI LÀ MỘT CỘT GỘP, không phải join.** Comment `:13-18` nói thẳng: mọi đường tìm
> kiếm hiện có đều là một câu `or(…ilike…)` **phẳng** của PostgREST trên chính bảng `patient`.
> Bắt từng đường tự join sang bảng con thì mỗi đường một kiểu và sớm muộn lệch nhau — màn
> này tra ra, màn kia không. Đổi **một cột** trong câu `or()` thì "tra số nào cũng ra" đúng ở
> mọi màn bằng cùng một cách.

Còn ba đường tra ở tầng backend (asyncpg, không đi qua PostgREST) thì dùng `EXISTS` sang bảng
con — `get_by_phone` (`patient_service.py:363`), `find_phone_duplicates` (`:396`), và
`MPIService.find_candidates` (`mpi_service.py:106`). Bài kiểm `test_nhieu_so_dien_thoai.py:141`
canh **cả ba** bằng `inspect.getsource`, với lời giải thích: *"Một đường mù là 'tra số nào
cũng ra' đúng ở màn này sai ở màn kia."*

#### 7.3.2. `them_so_dien_thoai` — chuẩn hoá, chặn trùng, che số trong log

Các bước (`patient_service.py:511-600`):

1. `loai` phải là `CHINH` hoặc `NGUOI_NHA`.
2. `normalize_vn_phone` — số rác dừng **trước** khi chạm database.
3. Đọc hồ sơ theo `(clinic_patient_id, clinic_id)`; không có → `ResourceNotFoundError`.
4. Trùng với `phone_primary`/`phone_secondary` của **chính hồ sơ này** → `ConflictError`.
   Trùng với số của hồ sơ **khác** thì **vẫn cho** — hai mẹ con dùng chung số là hợp lệ.
5. `INSERT … ON CONFLICT (clinic_patient_id, so_dien_thoai) DO NOTHING RETURNING id`. Trả
   `None` = bấm trùng → `ConflictError`, và **không ghi event cho một lần chèn không xảy ra**.
6. Ghi `event_log` — nhưng payload chỉ mang **4 số cuối**:

```python
json.dumps({"loai": loai, "duoi": chuan[-4:]}),
```

> Comment `:573-575`: *"`event_log` sống lâu hơn mọi màn hình, 4 số cuối đủ để đối chiếu khi
> cần mà không thành một bản sao danh bạ."*

`xoa_so_dien_thoai` (`:602`) là ảnh gương: **xoá thật**, không soft-delete, vì "số gỡ rồi mà
còn tra ra là gọi nhầm người theo một số không còn của họ". Vết "đã từng có, ai gỡ, lúc nào"
nằm ở `event_log`, cũng chỉ 4 số cuối. Cột gộp tự tươi nhờ trigger AFTER.

---

### 7.4. `src/clinicai/services/mpi_service.py` — dò trùng bệnh nhân

MPI = Master Patient Index. Công việc: khi tạo hồ sơ mới, tìm xem **người này đã có hồ sơ
chưa**, và nếu điểm giống đủ cao thì **xếp vào hàng chờ cho người xét**.

| Thành phần | Giải thích |
|---|---|
| `MPI_THRESHOLD = 70.0` (`:22`) | Ngưỡng vào hàng chờ gộp |
| `_PHONE_WEIGHT = 50.0` (`:26`) | Trùng `phone_primary` (sau chuẩn hoá) |
| `_NATIONAL_ID_WEIGHT = 40.0` (`:27`) | Trùng CCCD, **cả hai phải khác NULL** |
| `_NAME_WEIGHT = 10.0` (`:28`) | Tên giống mờ, 0–10 điểm |
| `score(candidate, existing)` (`:37`) | Cộng ba thành phần, kẹp trần 100 |
| `find_candidates(pool, data, clinic_id)` (`:84`) | Tìm ứng viên bằng 3 vế OR |
| `auto_queue_if_needed(...)` (`:172`) | Chấm điểm từng ứng viên, ≥70 thì INSERT vào `mpi_merge_queue` với `status='PENDING'` |
| `get_pending_queue(pool, clinic_id, limit)` (`:246`) | Đọc hàng chờ, sắp theo điểm giảm dần |

#### 7.4.1. Ba vế của `find_candidates`

```python
if data.phone_primary:       # vế 1 — số chính / người nhà / SỐ THÊM
if data.national_id_number:  # vế 2 — CCCD
if data.full_name and data.date_of_birth:   # vế 3 — họ tên + NĂM sinh
```

Vế thứ ba (`:140-149`) là vế **duy nhất bắt được người khai số điện thoại khác**, và nó có
hai chi tiết đáng học:

```python
conditions.append(
    f"(full_name_unaccent = lower(replace(replace("
    f"f_unaccent(${idx}), 'đ', 'd'), 'Đ', 'D'))"
    f" AND coalesce(birth_year, date_part('year', date_of_birth))"
    f" = ${idx + 1})"
)
```

- **Dùng cột GENERATED `full_name_unaccent`, không gọi `unaccent()` lúc truy vấn.** Tự tính
  lại ở vế trái vẫn ra kết quả đúng nhưng **bỏ qua chỉ mục** `idx_patient_full_name_unaccent`,
  và mở đường cho hai công thức chuẩn hoá lệch nhau (một bên đổi `đ`→`d`, một bên không).
  Vế phải dùng **đúng biểu thức của cột** để hai bên không bao giờ khác cách hiểu "Nguyễn" và
  "Nguyen". Bài kiểm `test_mpi_name_birthyear.py:73` canh đúng chỗ này.
- **Không tin cột `birth_year`**: đo trên prod, nó chỉ được điền **25/49** hồ sơ (ứng dụng
  ghi, không phải cột sinh tự động). `coalesce(birth_year, date_part('year', date_of_birth))`
  lấy nó khi có, còn lại tính từ ngày sinh. Chỉ dựa vào cột đó thì **một nửa số hồ sơ âm thầm
  không bao giờ báo trùng** — một lỗ hổng không có triệu chứng nào.
- So **NĂM** chứ không so **NGÀY**: ngày sinh hay bị nhập lệch.
- **Tên đơn thuần KHÔNG đủ** để vào `matches` (`test_mpi_name_birthyear.py:97`): "Nguyễn Thị
  Hoa" là hàng nghìn người, cảnh báo mỗi cái tên phổ biến sẽ bị bấm bỏ qua theo phản xạ, và
  lần nó nói thật cũng bị bỏ qua nốt.

Toàn bộ truy vấn **khoá trong một phòng khám** (`:158-161`): trùng ở phòng khám khác không
phải là trùng, và gộp qua ranh giới đó vừa sai vừa là rò rỉ dữ liệu.

#### 7.4.2. Quy tắc gộp — hệ thống KHÔNG tự gộp

Đây là điểm hay bị hiểu nhầm nhất:

> `auto_queue_if_needed` chỉ INSERT một dòng `mpi_merge_queue` với `status = 'PENDING'`.
> **Không có hàm nào trong service này gộp hồ sơ.** Bảng chỉ có 4 trạng thái
> (`PENDING / MERGED / REJECTED / REVIEW`) cùng `reviewed_by`, `reviewed_at` — nghĩa là quyết
> định gộp thuộc về **con người có quyền**.

Yêu cầu gốc (Notion §2 Lễ tân, trích trong `test_mpi_name_birthyear.py:3-5`): *"kiểm tra khả
năng trùng theo SĐT đã chuẩn hoá, kết hợp họ tên và năm sinh; chỉ cảnh báo để người có quyền
xử lý, **không tự động gộp hồ sơ**."*

Ba tầng cảnh báo, ba mức mạnh yếu khác nhau:

| Tầng | Lúc nào | Hành vi |
|---|---|---|
| `check_duplicate` (`api/v1/patients.py:104`) | Gõ chưa lưu | Cảnh báo sớm, gọi **đúng hàm** `find_candidates` của đường lưu nên hai bên không thể lệch |
| `trung_ten` (`patients.py:158-186`) | Gõ chưa lưu | Tín hiệu **yếu**, ô xám, tách riêng khỏi `matches` — cố ý không nhét vào để hai bên không lệch trở lại |
| `_mpi_autoqueue` (`patient_service.py:276`) | Sau khi lưu | Xếp hàng chờ gộp, chạy nền |

`_mpi_autoqueue` bọc **toàn bộ trong `try/except Exception`** và chỉ ghi `logger.warning`.
Bài kiểm `test_mpi_service.py:430` khẳng định: MPI ném lỗi thì `create_patient` **vẫn thành
công**. Dò trùng là tiện ích; đăng ký khách là nghiệp vụ chính.

---

### 7.5. `src/clinicai/services/tuong_tac_cskh_service.py` — sổ tương tác CSKH

File 883 dòng, chứa ba lớp. Docstring đầu file nói vì sao nó tồn tại: nút "📞 Gọi nhắc hẹn"
xưa là một thẻ `<a href="tel:…">` — **nó quay số rồi thôi**. Gọi xong không ai biết đã gọi,
gọi lần hai không ai biết là lần hai, ba cột "Tương tác gần nhất / Bước tiếp theo / Hạn xử
lý" hiện "—" cho mọi khách.

#### 7.5.1. Một "lần chạm" gồm những gì

Bảng `tuong_tac_cskh` (`supabase/migrations/20260809000003_so_tuong_tac_cskh.sql:30`):

| Cột | Ý nghĩa | Bộ từ |
|---|---|---|
| `loai` | **Việc gì** | `XAC_NHAN_LICH`, `NHAC_HEN`, `CHECK_XN`, `TRA_KQ`, `HOI_LY_DO_HUY`, `HOI_THAM`, `KHAC` + 4 **mốc quầy** `CHECK_IN`, `CHECK_OUT`, `THANH_TOAN`, `MUA_THUOC` (`service:65`) |
| `kenh` | **Chạm bằng đường nào** | `GOI`, `ZALO`, `SMS`, `TRUC_TIEP`, `KHONG_LIEN_HE` (`service:84`) |
| `ket_qua` | **Chạm xong ra sao** | `DA_LIEN_HE`, `CHUA_NGHE_MAY` (KNM), `KHONG_LIEN_LAC_DUOC` (KLLD), `HEN_GOI_LAI` (Hẹn GLS), `CAN_BAC_SI`, `TU_CHOI`, `BO_QUA`, `GHI_NHAN` (`service:87`) |
| `appointment_id` | **Nói về lượt khám nào** | NULL được, trừ 5 loại ở `CAN_LICH_HEN` (`service:81`) |
| `trang_thai_ma` | **Lần chạm này ĐÓNG trạng thái nào** | `CHO_XAC_NHAN`, `DA_CHECKIN`, `CHO_KQ_XN`… (migration `20260810000002`) |
| `khach_xac_nhan` | Khách có nói sẽ đến không | Chỉ có nghĩa với `XAC_NHAN_LICH` / `NHAC_HEN` |
| `nhan_vien_staff_id` | Ai chạm | **Lấy từ phiên đăng nhập, không nhận từ client** |
| `huy_luc` / `huy_boi_staff_id` | Đã hoàn tác lúc nào, bởi ai | Xem 7.5.3 |

**Vì sao ba giá trị gọi hụt phải TÁCH RA** (`test_so_tuong_tac_cskh.py:133`): gộp KNM + KLLD +
Hẹn GLS vào một "chưa nghe máy" thì báo cáo cuối tháng nói phòng khám gọi hụt 30% khách,
trong khi một phần ba số đó là **khách chủ động hẹn giờ khác**.

**Vì sao có `trang_thai_ma` bên cạnh `loai`** (migration `20260810000002:4-21`): timeline tích
xanh một node khi tìm thấy dòng "ứng với" node ấy. Dò theo `loai` **không phân biệt được** —
`loai='KHAC'` đang gánh ba trạng thái khác hẳn nhau ("chờ phản hồi chuyên môn", "đã trả kết
quả", "không cần follow up"). Hệ quả đo được: bấm "Đã hỏi bác sĩ" thì node "Đã trả kết quả"
cũng tích xanh theo. Dò bằng cách so chuỗi trong `noi_dung` đã cân nhắc và loại — *"một tính
năng chỉ đúng khi người dùng không gõ gì là một tính năng sẽ hỏng trong tuần đầu."*

#### 7.5.2. Vì sao phải gắn vào LƯỢT KHÁM (`appointment_id`)

```python
CAN_LICH_HEN = frozenset(
    {"XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY", "CHECK_IN", "CHECK_OUT"}
)
```

Hai lý do khác nhau cho hai nhóm:

1. **Ba loại gọi điện** (`XAC_NHAN_LICH`, `NHAC_HEN`, `HOI_LY_DO_HUY`): trạng thái CSKH được
   **suy ra từ sự VẮNG MẶT của một dòng**. Xem `v_viec_cskh` trong
   `20260810000009_hoan_tac_mot_lan_cham.sql:209-212`:
   ```sql
   AND NOT EXISTS (
         SELECT 1 FROM public.tuong_tac_cskh t
          WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH'
            AND t.huy_luc IS NULL)
   ```
   Không có `appointment_id` thì câu này không viết được, và *"lần sau mở ra không ai biết đã
   gọi cho lịch tuần trước hay tuần sau"* (`test_so_tuong_tac_cskh.py:76`).
2. **Hai mốc quầy** (`CHECK_IN`, `CHECK_OUT`): chúng **đổi trạng thái của chính lịch đó**.
   Không có lịch thì đổi cái gì?

Bảng còn có CHECK ở tầng database cho ba loại đầu (`20260809000003:80-82`), nhưng service
kiểm trước để người dùng nhận một câu tiếng Việt thay vì một lỗi 500.

#### 7.5.3. `ghi()` — mười một chốt trước một dòng INSERT

Trình tự trong `ghi()` (`:107-273`):

1. **Từ điển đóng** — `loai` / `kenh` / `ket_qua` phải nằm trong ba `frozenset` (`:121-126`).
2. `TRA_KQ` bắt buộc `ket_qua = "DA_LIEN_HE"` (`:127-135`). View coi **mọi** dòng `TRA_KQ` là
   đóng việc `KQ_CHUA_GUI`, không xét kết quả cuộc gọi; cho một lần gọi hụt mang loại ấy sẽ
   làm việc **biến mất**. Gọi hụt vẫn ghi được, bằng `loai="KHAC"`.
3. `BO_QUA` ⇔ `KHONG_LIEN_HE` (`:138-141`) — hai nửa của một việc, tách ra được thì sẽ có
   dòng "đã gọi điện" mà kết quả là "bỏ qua".
4. Mốc quầy ⇔ `GHI_NHAN` ⇔ `TRUC_TIEP` (`:142-147`). Mốc quầy chỉ có "đã xảy ra"; cho nó mượn
   `DA_LIEN_HE` là **bịa ra một cuộc gọi chưa từng có** (`:96-98`).
5. `khach_xac_nhan` chỉ có nghĩa ở hai loại (`:148-151`).
6. Năm loại phải có `appointment_id` (`:152-153`).
7. **Kiểm ownership** — bệnh nhân thuộc phòng khám này, và lịch hẹn thuộc bệnh nhân này
   (`:158-176`).
8. Nếu là `CHECK_IN`/`CHECK_OUT` → gọi `_doi_trang_thai_lich` **TRƯỚC**.
9. INSERT dòng sổ + INSERT `event_log`, cùng transaction (`:224-264`).

Chốt 7 và 8 có một comment đắt giá (`:155-157`):

```python
# Mọi kiểm tra ownership phải xong TRƯỚC side effect. Đặc biệt CHECK_IN,
# CHECK_OUT và Zalo có thể đổi lịch/gửi tin ra ngoài; kiểm sau đó thì
# request 422 vẫn có thể đã làm hỏng lịch của một khách khác.
```

Và thứ tự chốt 8 trước chốt 9 (`:184-187`): hành động lịch thất bại (khách chưa check-in mà
bấm check-out) thì **không được để lại dòng sổ nói việc đã xảy ra**. Chiều ngược lại — hành
động xong mà ghi sổ hỏng — **chấp nhận được**: trạng thái lịch vẫn đúng.

Một nhánh nữa ở `:188-195`: nếu `_doi_trang_thai_lich` trả `False` (mốc đã được vai khác
thực hiện, ví dụ Lễ tân check-in trước), hàm trả `{"ok": True, "already_applied": True,
"id": None}` và **không tạo dòng sổ nào**. Vì sao: một dòng no-op vẫn có nút Hoàn tác, và bấm
nút ấy có thể **đảo transition thật của người khác**.

#### 7.5.4. Các hàm còn lại của `TuongTacCskhService`

| Hàm | Giải thích |
|---|---|
| `ghi(...)` (`:107`) | Ghi một lần chạm. Xem 7.5.3 |
| `hoan_tac(...)` (`:275`) | Rút lại một lần chạm bấm nhầm. Xem 7.6 |
| `_doi_trang_thai_lich(...)` (`:411`) | Chạy hành động lịch tương ứng mốc quầy. `CHECK_IN` khi lịch đã `CHECKED_IN`/`COMPLETED` → trả `False` (no-op, không phải lỗi); trạng thái khác `SCHEDULED`/`CSKH_CONFIRMED`/`CONFIRMED` → `ValidationError` |
| `_checkout_atomically(...)` (`:451`) | `SELECT … FOR UPDATE` khoá dòng lịch, rồi đóng `visit` và `complete` lịch **trong MỘT transaction** |
| `_dong_luot_kham(...)` (`:488`) | Gọi `CheckoutService.close` để đóng dòng `visit` |
| `lich_su(...)` (`:579`) | `UNION ALL` sổ tương tác + `nhac_tai_kham` đã gọi xong → **một dòng thời gian**. CSKH không cần biết cuộc gọi nào lưu ở bảng nào |
| `_BorrowedConnection` / `_ConnectionBoundPool` (`:28`, `:41`) | "Pool giả" bọc **một connection đã acquire**, để `BookingService` và `CheckoutService` chạy transaction lồng thành **savepoint** dưới cùng một transaction ngoài, thay vì tự acquire và commit độc lập |

**`_dong_luot_kham` — hai mốc "kết thúc lượt" từng không nói chuyện với nhau** (`:497-536`):

`apply_action("complete")` chỉ đặt `appointment.status = COMPLETED`; dòng `visit` do quầy
đóng qua `CheckoutService.close`. Nên nút Checkout ở màn CSKH xưa nay đóng **đúng một nửa**.

> Đo trên staging 10/08/2026: **12 trên 15** dòng `visit` chưa đóng có lịch hẹn đã COMPLETED.
> Hệ quả không nằm ở màn CSKH — `work_item` còn PENDING, `current_node_code` vẫn trỏ một
> phòng, nên **bệnh nhân đã về nhà vẫn nằm trong hàng đợi của bảng điều phối**.

Vì sao gọi thẳng `CheckoutService` chứ không tự viết một câu UPDATE: nó là đường **duy nhất**
dọn đủ ba thứ — đóng bước `LUOTKHAM-15`, bỏ con trỏ phòng, ghi `closed_at`/`closed_by`. *"Tự
viết một câu UPDATE ở đây là dựng bản thứ hai của một quy trình, và bản thứ hai sẽ quên đúng
cái thứ ba."*

Và luật đã **đảo** ngày 14/08/2026 (Tuyền chốt lần hai): ba nút "Kết thúc lượt khám" phải
LUÔN bấm được. Bản trước gọi `close()` **không** kèm lý do ngoại lệ, nên còn một việc dở là
cả thao tác dừng với dòng đỏ *"phải ghi lý do ngoại lệ"* — mà màn CSKH **không có ô nào để gõ
lý do ấy**. Đó không phải một chốt, đó là một ngõ cụt. Cách sửa: truyền `ly_do_tu_dong`, để
`close()` tự dựng câu đầy đủ từ **chính lần đọc blockers của nó** — đọc lại ở đây là hai vòng
mạng cho một thứ, và hai kết quả có thể lệch nhau.

#### 7.5.5. `HenGoiLaiService` (`:621`) — việc CSKH tự hẹn cho mình

| Hàm | Giải thích |
|---|---|
| `tao(...)` (`:639`) | Tạo lời hẹn "gọi lại ngày…". `ly_do` **bắt buộc** — *"một việc không có lý do là một việc mà tuần sau không ai biết vì sao nó ở đó, và người trực sẽ đóng nó cho gọn màn hình"*. Ngày ở quá khứ bị từ chối |
| `_bao_hen_goi_lai(...)` (`:705`) | Dựng một thông báo đứng sẵn trong chuông cho vai CSKH. **Nuốt lỗi** có chủ ý |
| `dong(...)` (`:757`) | Đóng việc, nhưng chỉ khi **mốc ngày + giờ đã tới** |

Hai chỗ đáng đọc:

- **Vì sao gõ tay** (`:626-633`): không cột nào chứa ngày sinh con thật (`edd_date` là ngày
  *dự* sinh, lệch hai tuần là gọi chúc mừng vào tuần thứ sáu), và "thủ thuật" chưa phải một
  khái niệm. *"Một nút để người gõ thì có việc THẬT. Một tab tự sinh từ ngày dự sinh thì có
  việc SAI, và không ai biết nó sai cho tới lúc gọi nhầm."*
- **Một giới hạn nói thẳng ra** (`:718-723`): dự án **chưa có bộ hẹn giờ nào**. Nên thông báo
  ra đời NGAY lúc đặt hẹn, mang mốc giờ trong tiêu đề, nằm đó tới khi có người bấm "đã xử
  lý". *"Nó là một mẩu giấy dán màn hình, không phải đồng hồ báo thức — và nói thẳng như vậy
  còn hơn hứa một tiếng chuông sẽ không bao giờ kêu."*
- Đường dẫn thông báo mang `&viec=HEN_GOI_LAI` chứ không chỉ `?selected=` (`:743-752`):
  `?selected=` một mình mở đúng khách rồi buông tay, cột phải vẫn chạy theo việc gấp nhất do
  view suy ra — và lời hẹn này (ưu tiên 6) thường **thua** một việc khác.

#### 7.5.6. `GuiZaloService` (`:798`) — chỗ dễ nói dối nhất

```python
if not ket_qua.get("da_gui"):
    # KHÔNG ghi sổ. Một dòng "đã liên hệ" cho một tin chưa gửi là đúng
    # thứ tính năng này phải chống.
    return {"da_gui": False, **ket_qua}
```

Thứ tự bắt buộc: **gọi Zalo → đọc kết quả → CHỈ KHI thành công mới ghi sổ**. Vì *"một dòng
'đã liên hệ' ghi trước khi biết kết quả sẽ khiến người trực ca sau tin rằng khách đã được báo
— và không ai gọi nữa."*

Hai chi tiết nữa:

- **ZNS không gửi được tệp** — nó gửi template chữ đã duyệt. Nên khi `loai_tin="TRA_KET_QUA"`,
  dòng sổ ghi `loai="KHAC"` chứ **không** phải `TRA_KQ` (`:876-878`): ghi `TRA_KQ` sẽ làm việc
  `KQ_CHUA_GUI` biến mất dù chưa ai gửi ảnh/PDF/video.
- Ownership của `appointment_id` kiểm **trước** khi gọi Zalo (`:848-851`) — không gửi giờ hẹn
  của khách B vào số điện thoại của khách A rồi mới báo 422.

---

### 7.6. HOÀN TÁC (`hoan_tac`) — mục đọc kỹ

Đây là chỗ người dùng thắc mắc nhiều nhất, nên tách riêng.

#### 7.6.1. Vì sao KHÔNG xoá dòng

Yêu cầu gốc, Quang 10/08/2026 (`migration 20260810000009:3-5`): *"thêm khả năng nhấn vào nút
tròn của các sự kiện để hoàn tác (**tất nhiên là log không được xoá**, mà là hoàn tác lại tác
vụ đó) để phòng trường hợp người ta ấn nhầm"*.

Hai vế nghe như mâu thuẫn, và chính chỗ ấy quyết định thiết kế:

- `tuong_tac_cskh` là **sổ CHỈ THÊM**. Một cú DELETE ở đây là **xoá bằng chứng ai đã chạm
  tới bệnh nhân lúc mấy giờ**.
- Nhưng "ấn nhầm" là chuyện có thật, và hậu quả của nó **không nằm ở dòng sổ** — nó nằm ở
  chỗ dòng sổ ấy **ĐÓNG một việc**. Bấm nhầm một cái là việc "gọi xác nhận lịch" biến mất
  khỏi hàng đợi, và **không ai gọi cho khách ấy nữa**.

Nên: **dòng Ở LẠI, chỉ THÔI ĐƯỢC TÍNH.**

```sql
ALTER TABLE public.tuong_tac_cskh
    ADD COLUMN IF NOT EXISTS huy_luc timestamptz,
    ADD COLUMN IF NOT EXISTS huy_boi_staff_id uuid
        REFERENCES public.staff(id) ON DELETE SET NULL;
```

Kèm CHECK `tuong_tac_huy_du_doi`: `(huy_luc IS NULL) = (huy_boi_staff_id IS NULL)` — hoàn tác
mà không biết ai hoàn thì không truy lại được.

**Vì sao không dùng "bút toán đảo"** (thêm một dòng phủ định thay vì một lá cờ)? Comment
`20260810000009:23-27` trả lời: nghe thuần khiết hơn, nhưng **mọi câu `NOT EXISTS` trong view
sẽ phải đếm cặp ghi/huỷ** để biết cái nào còn hiệu lực — mười nhánh, mỗi nhánh một câu con,
và chỉ cần một nhánh quên là một trạng thái sai âm thầm. *"Một lá cờ đọc được bằng `IS NULL`
thì mười nhánh nói cùng một câu."*

Migration ấy phải sửa `v_viec_cskh` ở **bốn chỗ** đọc sổ (`cham_cuoi` + ba câu `NOT EXISTS`)
và `v_trang_thai_cskh` ở nhánh `da_xac_nhan`. *"Bỏ sót MỘT chỗ là một trạng thái không bao
giờ mở lại được sau khi hoàn tác, và nó hỏng trong im lặng."*

#### 7.6.2. Hoàn tác KHÔNG chỉ là một lá cờ

Hai mốc quầy còn **đổi trạng thái lịch hẹn thật**. Rút lại dòng sổ mà để lịch nguyên trạng là
nói dối theo chiều ngược lại: **sổ bảo chưa check-in, lịch hẹn vẫn CHECKED_IN**.

Trình tự trong `hoan_tac` (`tuong_tac_cskh_service.py:275-409`):

1. Đọc dòng theo `(id, clinic_id)`; không có → `NotFoundError`.
2. `huy_luc` đã khác NULL → trả `{"ok": True, "da_hoan_tac_truoc_do": True}`. **Idempotent**:
   hai người cùng bấm, hoặc bấm lại sau khi mạng lag, không phải lỗi.
3. `loai == "CHECK_OUT"` → **từ chối** (xem 7.6.3).
4. `loai == "CHECK_IN"` → ba chốt rồi mới `undo_checkin`.
5. `UPDATE … SET huy_luc = now(), huy_boi_staff_id = $2 WHERE id = $1 AND huy_luc IS NULL`.
6. INSERT `event_log` sự kiện `cskh.tuong_tac_hoan_tac`.

Thứ tự 4 trước 5 là bắt buộc, và có bài kiểm canh (`test_so_tuong_tac_cskh.py:372`, khẳng
định `events == ["undo", "void", "event"]`): *"gạch sổ trước mà máy trạng thái từ chối sẽ làm
timeline nói khách chưa đến trong khi appointment vẫn CHECKED_IN."*

Ba chốt của nhánh CHECK_IN (`:319-360`):

| Chốt | Câu từ chối |
|---|---|
| Lịch đã `COMPLETED` | "Khách đã khám xong rồi, không rút lại check-in được nữa." |
| Lịch không còn `CHECKED_IN` | "Lịch không còn ở trạng thái CHECKED_IN nên không thể hoàn tác mốc check-in này." |
| Quy trình đã tiến | "Khách đã tiếp tục quy trình sau check-in; không thể hoàn tác từ màn CSKH." |

Chốt thứ ba có một chi tiết tinh tế:

```sql
AND w.node_code <> 'LUOTKHAM-01'
-- Trạm đầu được tự mở IN_PROGRESS ngay lúc check-in;
-- đó chưa phải tiến triển của người dùng. Chỉ một bước
-- phía sau đã COMPLETED mới làm undo trở nên nguy hiểm.
AND w.status = 'COMPLETED'
```

Nếu không loại `LUOTKHAM-01`, **mọi** check-in đều có vẻ "đã tiến triển" và nút Hoàn tác sẽ
không bao giờ bấm được.

#### 7.6.3. Vì sao CHECK_IN đảo được mà CHECK_OUT thì KHÔNG

Câu trả lời nằm ở **máy trạng thái lịch hẹn**, `booking_service.TRANSITIONS`:

```
SCHEDULED / CSKH_CONFIRMED / CONFIRMED
        │  checkin
        ▼
   CHECKED_IN  ──── undo_checkin ────►  CONFIRMED     ← CÓ đường về
        │  complete
        ▼
    COMPLETED   ────  ???  ────►  (không có)          ← KHÔNG có đường ra
```

- **CHECK_IN đảo được** vì `undo_checkin` **tồn tại** như một transition: nó đưa `CHECKED_IN`
  về `CONFIRMED`, và huỷ luôn các bước còn mở của lượt khám (`_WORKFLOW_CANCELLING`).
- **CHECK_OUT không đảo được** vì máy trạng thái **không có transition nào ra khỏi
  `COMPLETED`**. Và đó là **chủ ý**, không phải thiếu sót.

> Vì sao chủ ý: "đã khám xong" là mốc mà **nhiều thứ khác đọc vào** — nhắc tái khám, thu
> tiền, hồ sơ bệnh án. Mở một đường quay lại từ `COMPLETED` nghĩa là mọi thứ đọc mốc ấy phải
> biết cách xử lý việc mốc bị rút. Chưa kể `CHECK_OUT` còn kéo theo `CheckoutService.close`:
> bước `LUOTKHAM-15` đã đóng, con trỏ phòng đã bỏ, `closed_at`/`closed_by` đã ghi — đảo được
> dòng sổ mà không đảo được ba thứ kia là để lại một trạng thái nửa vời tệ hơn cả trạng thái
> sai.

Nên `hoan_tac` từ chối ngay, **kèm câu chỉ đường** (`:312-317`):

```python
if row["loai"] == "CHECK_OUT":
    raise ValidationError(
        "Không hoàn tác được lần đóng lượt khám. Lượt đã COMPLETED và "
        "máy trạng thái không có đường quay lại — nhờ Quản lý mở lại "
        "lượt, hoặc đặt một lịch mới cho khách."
    )
```

Điểm đáng học ở đây không phải luật, mà là **cách từ chối**: nói ra *vì sao* (máy trạng thái
không có đường quay lại) và *làm gì tiếp* (nhờ Quản lý, hoặc đặt lịch mới). So với việc âm
thầm gỡ cờ `huy_luc` và để lịch hẹn nói một đằng sổ nói một nẻo — thứ mà comment `:284-296`
gọi là "nói dối theo chiều ngược lại".

---

### 7.7. Nhắc tái khám — hai file, hai vai trò khác nhau

#### 7.7.1. `recall_service.py` — PHÉP CHIẾU

| Thành phần | Giải thích |
|---|---|
| `_LOOKBACK_DAYS = 183` (`:14`) | Chỉ nhìn lại 6 tháng |
| `_UPCOMING_DAYS = 7` (`:15`) | Đến hạn trong 7 ngày tới |
| `RecallFollowup` (`:19`) | Dataclass frozen: bệnh nhân, ngày đến hạn, xét nghiệm cần lặp, lời dặn, `last_called_date` |
| `_DUE_FOLLOWUPS_SQL` (`:36`) | Đọc `soap_plan #>> '{tai_kham,ngay}'` của phiếu khám **đã chốt** (`FINALIZED`/`AMENDED`) của lượt **COMPLETED**, loại người **đã có lịch hẹn tương lai** |
| `_parse_due_date(value)` (`:114`) | Parse một ngày JSON **không tin cậy** mà không làm hỏng cả lô: sai định dạng → `None` → bỏ qua dòng đó |
| `due_followups(clinic_id, today)` (`:130`) | Trả danh sách đã lọc và sắp theo (ngày đến hạn, tên) |

Chi tiết đáng đọc — `last_called_date` (`:27-33`): gọi xong **KHÔNG** làm bệnh nhân rời danh
sách; họ chỉ rời khi **có lịch hẹn mới**. Thiếu trường này thì màn hình không nhớ được ai đã
gọi: *"hai người trực cùng ca gọi trùng nhau, và tải lại trang là mất sạch dấu vết."*

`RecallService` cố ý là "least-privilege projection" — nó chỉ trả **lời dặn tái khám** mà
CSKH cần, không trả cả phiếu khám.

#### 7.7.2. `recall_job_service.py` — VIỆC

Docstring `:3-11` giải thích vì sao cần file thứ hai: phép chiếu tính lại từ đầu mỗi lần mở
trang, **không có dòng nào trong database**. Nên: không ai mở trang thì không ai biết có
người cần gọi; không giao được cho một người cụ thể; trưởng ca không đối soát được; và "ai đã
gọi lượt một, ai còn thiếu lượt hai" là câu không trả lời được.

**Hai lượt là hai việc khác nhau:**

```
Lượt 1 — bác sĩ dặn quay lại ngày X, khách CHƯA đặt lịch.  Gọi T−7, để MỜI ĐẶT LỊCH.
Lượt 2 — khách ĐÃ có lịch hẹn hôm nay.                     Gọi sáng, để NHẮC ĐI KHÁM.
```

| Hàm | Giải thích |
|---|---|
| `sinh(identity, ngay)` (`:63`) | Gọi hàm SQL `sinh_viec_nhac_tai_kham()`. **Idempotent** — chạy lại bao nhiêu lần cũng như một |
| `danh_sach(identity, sinh_truoc=True)` (`:82`) | Đọc việc `CHO_GOI` đã tới hạn, tách theo lượt. **Mặc định sinh việc trước khi đọc** |
| `tao_thu_cong(...)` (`:138`) | CSKH gõ tay ngày tái khám → sinh **HAI mốc** T−7 và T−1 bằng một `INSERT … SELECT FROM (VALUES …)` với `ON CONFLICT DO NOTHING` |
| `ghi_ket_qua(...)` (`:218`) | Đóng việc + ghi `cskh_log`, **cùng transaction** |
| `bo_qua(...)` (`:313`) | Không cần gọi nữa; `ly_do` bắt buộc |

**Ai chạy bộ sinh việc** (`:23-29`): dự án chưa có bộ hẹn giờ nào (đã tìm: không apscheduler,
không croniter, không repeat_every). Nên đường chắc chắn nhất hôm nay là **sinh ngay lúc CSKH
mở màn**. Vì hàm sinh idempotent, cắm thêm cron vào ngày mai không phải đổi gì.

`ghi_ket_qua` có một nhánh xử lý bấm trùng đáng học (`:262-280`): UPDATE khớp 0 hàng → đọc
lại `trang_thai` để phân biệt ba trường hợp — không có việc (`NotFoundError`), việc chưa tới
hạn (`ValidationError`), việc đã ghi từ trước (`{"da_ghi_tu_truoc": True}`). *"Đừng trả 'ok'
trống khiến người dùng tưởng vừa ghi được."*

#### 7.7.3. `cskh_service.py` — nhật ký CSKH nền

| Hàm | Giải thích |
|---|---|
| `clinic_today(now)` (`:59`) | Hôm nay theo **giờ phòng khám** (`Asia/Ho_Chi_Minh`), dạng `YYYY-MM-DD`. Cố ý không dùng UTC: một cuộc gọi 20h ở Hà Nội là UTC-ngày-mai, và danh sách quá hạn sẽ sai **mỗi tối** |
| `manual_source_ref()` (`:69`) | `cskh_action.source_ref` là UNIQUE NOT NULL và **do đường nhập khẩu sở hữu**. Việc gõ tay cần khoá riêng, dùng `secrets` chứ không `Math.random` để hai cú bấm cùng mili giây không đụng nhau |
| `record_action(...)` (`:86`) | Ghi một việc CSKH gõ tay. `patient_code` tuỳ chọn, nhưng **sai mã thì fail** chứ không xếp việc cho không ai |
| `record_followup_call(...)` (`:163`) | Ghi một cuộc gọi nhắc tái khám vào `cskh_log`, có `ket_qua` và `luot_goi` |
| `_log(conn, ...)` (`:243`) | Helper ghi `event_log` với đủ `clinic_role` / `clinic_staff_id` / `actor_auth_user_id` |

`FOLLOWUP_KIND = "Nhắc gọi tái khám"` (`:56`) là chuỗi mà `RecallService` dùng để tính
`last_called_date` (`recall_service.py:95`) — khai một chỗ, hai file dùng chung, để không gõ
lệch.

#### 7.7.4. `phan_hoi_khach_service.py` — phản hồi / khiếu nại

| Hàm | Giải thích |
|---|---|
| `LOAI_HOP_LE` (`:23`) | `KHEN`, `GOP_Y`, `KHIEU_NAI`. **KHEN cũng đáng ghi: nó nói khâu nào đang đúng** |
| `ghi(...)` (`:30`) | Ghi phản hồi mới. Người tiếp nhận **lấy từ phiên**, không nhận từ client. Nội dung rỗng bị từ chối |
| `cap_nhat(...)` (`:88`) | Chuyển trạng thái `MOI` → `DANG_XU_LY` → `DA_XU_LY`. Đóng thì **bắt buộc** ghi `huong_xu_ly` |

**Vì sao không nằm trong sổ tương tác** (docstring `:3-7`): sổ tương tác là dòng chảy một
chiều — ghi rồi thôi. Một khiếu nại là một **VIỆC MỞ**: có trạng thái, có người xử lý, ba
tuần sau vẫn phải tìm lại được theo "cái nào chưa xong". *"Nhồi hai thứ vào một bảng thì hoặc
mọi cuộc gọi phải mang một trạng thái vô nghĩa, hoặc khiếu nại không đóng được."*

Và vì sao đóng thì phải nói cách xử lý (`:100-103`): *"'Đã xử lý' mà không nói xử lý ra sao
thì ba tuần sau khách gọi lại và không ai biết lần trước đã hứa gì."*

---

### 7.8. Quy tắc riêng tư — dữ liệu nào không bao giờ ra khỏi hệ thống

Không có một file "privacy.py" tập trung; luật nằm rải trong code nhưng **nhất quán**. Tổng
hợp lại:

| Đường ra | Được mang gì | Bị cấm mang gì | Ở đâu |
|---|---|---|---|
| **`event_log`** (sổ thao tác, sống lâu hơn mọi màn hình) | `loai`, **4 số cuối** của SĐT, id nhân viên | **Số điện thoại đầy đủ** | `patient_service.py:586`, `:648` |
| **Sentry** (máy chủ nước ngoài) | Loại lỗi, tệp, số dòng | Header/cookie/IP (`send_default_pii=False`), **biến cục bộ** (`include_local_variables=False`), **thân request** (`max_request_body_size="never"`) | `test_sentry_privacy.py:57-66` |
| **API `check-duplicate`** | `clinic_patient_id`, `full_name`, `patient_code`, `birth_year` | **CCCD, địa chỉ, số điện thoại đầy đủ** | `api/v1/patients.py:191-203` |
| **API `check-phone`** | `full_name`, `patient_code`, `birth_year` | Mọi thứ khác; và **không ghi log số lẫn tên** | `patient_service.py:376-382` |
| **Ranh giới phòng khám** | Chỉ dữ liệu của `identity.clinic_id` | Mọi thứ của tenant khác — kể cả khi "trùng" | `mpi_service.py:155-161` |
| **Bảng `patient_sdt_them` qua PostgREST** | `GRANT SELECT` cho `authenticated`, kèm RLS theo `current_clinic_ids()` | Mọi đường **GHI** — client tự ghi được nghĩa là client tự khai được | migration `:47-64` |
| **Bảng `tuong_tac_cskh` qua PostgREST** | `GRANT SELECT` | Ghi — *"client tự ghi được nghĩa là client tự khai được 'đã gọi rồi' cho một cuộc gọi chưa hề xảy ra"* | migration `20260809000003:114-116` |

Ba nguyên tắc rút ra:

1. **Sổ vĩnh viễn thì mang ít nhất có thể.** `event_log` không có ngày hết hạn, nên nó chỉ
   giữ 4 số cuối — đủ đối chiếu, không thành một bản sao danh bạ.
2. **Cảnh báo trùng chỉ cần trả lời "có phải người này không".** Không cần CCCD, không cần
   địa chỉ. Người trực nhìn tên + năm sinh là nhận ra khách.
3. **Chốt riêng tư quan trọng nhất cũng là chốt dễ quên nhất** (`test_sentry_privacy.py:60-63`):
   `include_local_variables` **mặc định BẬT** trong SDK Python, và lúc nổ lỗi thì biến cục bộ
   thường đang giữ nguyên một hàng bệnh nhân hoặc một hồ sơ khám.

---

### 7.9. Bộ kiểm của phần này

| Tệp | Canh gì |
|---|---|
| `src/tests/test_nhieu_so_dien_thoai.py` | Chuẩn hoá số, chặn trùng trong chính hồ sơ, event_log không chứa số đầy đủ; và **ba đường tra số đều thấy bảng số-thêm** (kiểm bằng `inspect.getsource`) |
| `src/tests/unit/test_so_tuong_tac_cskh.py` | 30+ bài: từ điển đóng, các cặp ràng buộc, thứ tự ownership-trước-side-effect, bốn nhánh hoàn tác, checkout nguyên tử, Zalo thất bại không ghi sổ |
| `src/tests/unit/test_mpi_service.py` | Chấm điểm (50/40/10), ngưỡng 70, và **MPI hỏng không chặn create** |
| `src/tests/services/test_mpi_name_birthyear.py` | Ba vế của `find_candidates`, dùng cột GENERATED, fallback `birth_year`, khoá trong một phòng khám |
| `src/tests/unit/test_recall_service.py`, `test_recall_callback_consistency.py` | Phép chiếu nhắc tái khám |
| `src/tests/unit/test_phan_hoi_khach.py` | Vòng đời phản hồi |
| `src/tests/test_sentry_privacy.py` | Ba chốt riêng tư của Sentry |

Một kiểu kiểm đặc biệt hay xuất hiện ở phần này: **đọc mã nguồn bằng `inspect.getsource`**.
Nó dùng khi thứ cần canh là *"hai lời gọi có còn đi cùng nhau không"* hoặc *"câu SQL này còn
nhìn thấy bảng kia không"* — những thứ mypy không biết và test hành vi không chạm tới. Ví dụ
`test_so_tuong_tac_cskh.py:967` quét **mọi** câu `INSERT INTO event_log` trong file bằng regex
để bắt `aggregate_id = NULL`.

---

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

1. **"Hoàn tác = xoá dòng"** — Sai. `hoan_tac` chỉ đặt `huy_luc` + `huy_boi_staff_id`. Dòng ở
   lại vĩnh viễn; view bỏ qua nó bằng `AND t.huy_luc IS NULL`. Lịch sử đọc được đủ hai vế: đã
   bấm, rồi đã rút lại, **cả hai đều có tên người**.

2. **"CHECK_OUT không hoàn tác được là do quên viết"** — Sai, là **chủ ý**.
   `booking_service.TRANSITIONS` không có đường ra khỏi `COMPLETED`, vì mốc "đã khám xong"
   được nhắc tái khám / thu tiền / hồ sơ đọc vào. Cách xử lý đúng: nhờ Quản lý mở lại lượt,
   hoặc đặt lịch mới.

3. **`aggregate_id = NULL` → 500 cho MỌI cú hoàn tác** (10/08/2026). Câu `ghi()` ngay bên trên
   đã dùng đúng `clinic_patient_id`; **chép sai một tham số là đủ**. mypy không biết ràng buộc
   NOT NULL của database, và câu INSERT chỉ nổ lúc chạy thật. Nay có bài kiểm regex canh.

4. **Quên savepoint trong vòng lặp thử lại** (`_insert_patient`). Sau một UNIQUE violation,
   Postgres đánh dấu **cả transaction ngoài** là aborted; không có `async with
   conn.transaction()` lồng thì mọi lần thử lại đều lỗi.

5. **`sua_luc` lọt vào câu SET.** Nó là thẻ khoá lạc quan, không phải cột. Không `pop` ra
   trước là câu lệnh nổ (`patient_service.py:431-433`).

6. **Trả "không tìm thấy" cho một xung đột ghi đồng thời** là nói dối — người dùng đang nhìn
   thẳng vào hồ sơ ấy trên màn hình. Phải đọc lại để phân biệt hai nguyên nhân (`:483-499`).

7. **Chỉ tin cột `birth_year`** — trên prod nó chỉ điền 25/49 hồ sơ. Đúng một nửa số hồ sơ sẽ
   **âm thầm không bao giờ báo trùng**, và lỗ hổng ấy không có triệu chứng nào.

8. **Gọi `unaccent()` ở vế trái thay vì dùng cột GENERATED** — vẫn ra kết quả đúng nhưng bỏ
   qua chỉ mục và mở đường cho hai công thức chuẩn hoá lệch nhau.

9. **Một đường tra số mù bảng `patient_sdt_them`** — "tra số nào cũng ra" đúng ở màn này, sai
   ở màn kia. Bốn đường phải cùng thấy: cột gộp `sdt_tim_kiem` (PostgREST) + ba câu `EXISTS`
   (asyncpg).

10. **Ghi `TRA_KQ` cho một tin ZNS** — ZNS không gửi được tệp, nó chỉ báo "đã có kết quả".
    Ghi `TRA_KQ` sẽ làm việc `KQ_CHUA_GUI` biến mất dù chưa ai gửi ảnh/PDF/video. Nên
    `GuiZaloService` ghi `loai="KHAC"` (`:876-878`).

11. **CSKH check-out mà chỉ `complete` lịch hẹn** — dòng `visit` vẫn mở, `work_item` còn
    PENDING, và **bệnh nhân đã về nhà vẫn nằm trong hàng đợi bảng điều phối**. Đo được: 12/15
    dòng visit chưa đóng có lịch hẹn đã COMPLETED.

12. **Một chốt mà màn hình không cho cách đáp ứng là một ngõ cụt, không phải một chốt.**
    `close()` đòi "ghi lý do ngoại lệ" trong khi màn CSKH không có ô nhập lý do. Cách sửa
    đúng: **không xoá chốt, mà đáp ứng nó** bằng `ly_do_tu_dong` dựng từ chính lần đọc
    blockers của `close()`.

13. **Từ điển của service và cửa Pydantic của router phải là MỘT bộ từ**
    (`test_so_tuong_tac_cskh.py:658`). Ngày 08/08 hai lần mở rộng từ điển chỉ sửa service, nên
    CSKH chọn "không liên lạc được" trên màn là **ăn 422**: service nhận mà cửa Pydantic đã
    đóng. Không lớp kiểm nào bắt được — service test không đi qua Pydantic, còn người thử tay
    chỉ thử hai giá trị cũ.

14. **RLS chỉ GIẤU dòng đi, không ngăn nó ra đời** (`test_so_tuong_tac_cskh.py:145`). Backend
    nối bằng quyền chủ database nên RLS **không áp dụng trong tiến trình này** — mọi câu phải
    tự mang `clinic_id`.


---

## PHẦN 8. TẦNG API (FastAPI) — MỌI CỬA VÀO HỆ THỐNG

Đây là **toàn bộ** bề mặt mà thế giới bên ngoài chạm được vào ClinicAI: 189 endpoint,
36 router, một tiến trình FastAPI. Không có đường vòng — dashboard Next.js chỉ vẽ giao
diện; mọi luật nghiệp vụ đều nằm sau một trong 189 cửa dưới đây.

> **Nguyên tắc bao trùm cả phần này:** *router mỏng, service dày*. Một hàm endpoint chỉ
> làm ba việc — nhận DTO đã được Pydantic kiểm, hỏi `Depends` xem "ai đang gọi và có
> được phép không", rồi gọi đúng một service. Bất kỳ câu `if` nào mang tính nghiệp vụ
> nằm trong router đều là một luật mà bài kiểm không với tới được.

---

### 8.1. Bản đồ tầng: một yêu cầu đi qua những gì

```
HTTP request
  ↓ RequestIdMiddleware      gắn X-Request-ID, bind vào structlog   (ngoài cùng)
  ↓ TimingMiddleware         ghi thời gian + status vào ring buffer
  ↓ CskhUploadSizeLimit      chặn body tải tệp quá lớn ngay khi ASGI còn đang nhận
  ↓ api_key_middleware       X-API-Key: thiếu→401, sai→403, chưa cấu hình→503
  ↓ DbErrorMiddleware        lỗi KẾT NỐI database → 503 (không phải 500)  (trong cùng)
  ↓ dependencies=[runaway_guard]   đếm request theo NHÂN VIÊN, trần 400/phút
  ↓ Depends(RoleGuard)       xác minh JWT → staff → clinic_membership → vai
  ↓ hàm endpoint             gọi service
```

`main.py:132-149` đăng ký middleware **theo thứ tự NGƯỢC**, vì `Starlette.add_middleware`
làm `user_middleware.insert(0, …)` — cái thêm **sau cùng** nằm **ngoài cùng**. Suốt ba
tháng file này viết theo thứ tự trực giác và nhận đúng ngăn xếp ngược lại:
`TimingMiddleware` nằm *bên trong* cửa API-key nên không thấy được chính cơn lũ request bị
từ chối mà nó sinh ra để hiển thị; `RequestIdMiddleware` nằm trong cùng nên mọi phản hồi
401/403/503 đi ra **không có** header `X-Request-ID` (`middleware.py:15-33`). Bài
`test_middleware_order` giờ ghim thứ tự này.

`DbErrorMiddleware` cố ý nằm **trong cùng** (`middleware.py:30-33`): nó biến một kết nối
chết thành *response* 503, và chỉ khi ở trong cùng thì `TimingMiddleware` mới ghi được
`status=503`. Đặt ngoài cùng thì ngoại lệ vẫn đang bay lúc `finally` của Timing chạy, và
buffer sẽ ghi 500 cho thứ mà khách nhận được là 503.

---

### 8.2. Quy ước chung — bốn thứ lặp lại ở mọi router

| Quy ước | Giải thích |
|---|---|
| **`Depends(get_db_pool)`** | Không router nào tự mở kết nối. Pool asyncpg do `lifespan` tạo (`main.py:85`) và tiêm vào bằng dependency → test thay pool giả không cần vá gì |
| **`Depends(RoleGuard)`** | Trả về `StaffIdentity` **đã xác minh** thay vì `True/False`. Endpoint vừa được gác vừa nhận luôn `identity.clinic_id` / `identity.location_id` — nên không truy vấn nào phải đoán "phòng khám nào" |
| **DTO Pydantic** | Mọi body là một `BaseModel` có `Field(min_length/max_length/ge/le)`. Sai kiểu → **422 tự động**, không tới được service |
| **Không bắt exception** | Router **không** có `try/except`. `NotFoundError`/`ValidationError`/`ConflictError` bay thẳng lên 4 handler toàn cục ở `main.py:287-419` |

**Khai kiểu ở query param không phải chuyện thẩm mỹ.** `booking.py:331` khai
`week_start: date_cls` chứ không phải `str`, để FastAPI phân tích và trả **422** cho
chuỗi hỏng — thay vì để chuỗi rơi xuống asyncpg thành **500**. Đúng lỗi này từng làm
`/appointments/quote` trả 500 triền miên (`booking.py:341-343`).

#### Ý nghĩa mã lỗi với NGƯỜI DÙNG CUỐI

| Mã | Ai sinh ra | Người trực đọc thành |
|---|---|---|
| **400** | `X-Clinic-ID` không phải UUID (`identity.py:243`) | "gửi sai định dạng" — lỗi lập trình, không phải lỗi thao tác |
| **401** | thiếu `X-API-Key` (`auth.py:107`) hoặc thiếu/hết hạn Bearer token (`identity.py:214`) | **"phiên đăng nhập hết hạn — đăng nhập lại"** |
| **403** | sai API key; hoặc `RoleGuard` từ chối; hoặc tài khoản chưa gán phòng khám/cơ sở (`identity.py:359-408`) | **"vai của bạn không được làm việc này"** — không phải máy hỏng |
| **404** | `NotFoundError`; hoặc `/console/*` và `/tools/*` khi chạy ở production (cố ý giả vờ không tồn tại) | "không tìm thấy bản ghi" |
| **409** | `ConflictError`, `UniqueViolation`, `ExclusionViolation` | **"đã có bản ghi khác chặn"** — thường là thao tác đã thành công từ trước |
| **413** | body tải tệp vượt trần (`middleware.py:78`) | "tệp quá lớn" |
| **422** | Pydantic từ chối; hoặc `ValidationError` của service | **"thiếu/sai một ô nhập"** |
| **429** | `runaway_guard` (>400/phút) hoặc `InMemoryRateLimiter` (LLM/voice) | "màn hình đang lặp — tải lại trang" |
| **503** | chưa cấu hình `BACKEND_API_KEY`; database mất kết nối; AI orchestrator tắt | "máy chủ chưa sẵn sàng, thử lại" |
| **500** | ngoại lệ chưa bắt | **"máy chủ hỏng"** — mọi 500 là một con bug |

> **Ranh giới 4xx / 5xx là ranh giới "máy chủ TỪ CHỐI" và "máy chủ HỎNG".** Nó không
> phải chuyện thẩm mỹ: `IdempotencyGuard.release` (§8.4) quyết định trả hay giữ khoá
> dựa **đúng** vào ranh giới này.

**Handler 409 — một câu cho mọi ràng buộc là một câu sai.** `main.py:287-343` **từng** luôn
nói "Lịch hẹn xung đột khung giờ với appointment khác" — đúng cho một ràng buộc, sai cho
ba cái còn lại, trong đó có hai ràng buộc **luật đặt lịch**. Trưởng ca lưu một luật cho BS
Thành nhận về một câu nói về LỊCH HẸN rồi đi tìm một lịch hẹn không tồn tại; mất một buổi
vì đúng câu này. Nay tên ràng buộc quyết định câu trả lời, ràng buộc lạ thì **nói thẳng là
không nhận ra, kèm tên** — mơ hồ mà đúng còn hơn cụ thể mà bịa. Và log ở
`main.py:330-334` dùng `reason=` chứ không phải `message=`, vì `core.logging` coi trường
`message` là nội dung bệnh nhân và thay bằng `[REDACTED]` — nó đã bôi trắng đúng câu nói
ràng buộc nào bắn.

---

### 8.3. Bốn lớp gác, và vì sao phải là bốn

**① `api_key_middleware`** (`api/auth.py`) — cửa chặn người lạ hoàn toàn. Dùng
`hmac.compare_digest` để không dò được bằng thời gian. Điểm thiết kế: khi biến
`BACKEND_API_KEY` **chưa đặt**, nó chỉ cho qua ở môi trường dev/test khai tường minh;
production hay môi trường không rõ → **503**. *Một lỗi triển khai không bao giờ được âm
thầm tắt xác thực.* `EXEMPT_PATHS` chỉ có `/health`, `/health/db`, `/docs`,
`/openapi.json`, `/redoc` (`auth.py:44-52`).

**② `runaway_guard`** (`api/runaway_guard.py`) — **không phải** rate limiter. Nó tồn tại
để **CHO THẤY một con bug**, không phải để chặn một con người:

> Một con người **không thể** sinh ra hàng trăm request một phút. Thứ làm được điều đó là
> một `useEffect` tự kích lại, hoặc một vòng thử lại không backoff. *Đặt trần chặt sẽ CHE
> con bug đó đi*: vòng lặp vẫn chạy, máy chủ lặng lẽ từ chối phần lớn, màn hình nửa chạy
> nửa không, và phòng khám chỉ thấy "hơi chậm".

Trần **400/phút**, cảnh báo ở **một nửa trần** (`runaway_guard.py:191-199`). Con số 400 là
kết quả đo lại 10/08/2026: trần cũ 120 **chặn người thật** — log staging đếm 28 lượt bị
từ chối trong 40 phút, riêng 09:43:13 có **bảy** lời gọi `/api/v1/me` trong 0,4 giây. Tiền
đề "một người = 20 request/phút" đúng với NGƯỜI nhưng sai với MÀN HÌNH: mỗi cú bấm ở màn
CSKH ghi một dòng rồi `router.refresh()`, kéo theo `/me`, `/appointments/policy`,
`/cskh/recall-jobs`, `/appointments/week`, `/visits/progress`… một thao tác hoá sáu bảy
lượt gọi. Guard gắn ở **tầng router** (`main.py:162`) chứ không rải xuống từng endpoint —
thứ nó đo là *per NGƯỜI*, và rải thì endpoint tiếp theo ai đó thêm sẽ lặng lẽ nằm ngoài
bộ đếm.

**③ `_resolve_identity`** (`identity.py:313`) — xác minh JWT Supabase → tra `staff` theo
`auth_user_id` → lấy **một** `clinic_membership` đang hoạt động. Vai và phòng khám đến từ
**cùng một dòng membership**; không tin gì từ client. Nhiều membership mà không gửi
`X-Clinic-ID` → **403 fail-closed**, không đoán. Cache 30 giây
(`identity.py:253-274`) vì mỗi lời gọi từng tốn một vòng tới Supabase Seoul (~60–90ms) cho
một câu trả lời đổi vài lần một năm; nhưng **JWT vẫn xác minh ở MỌI request** (cache không
kéo dài được phiên) và **403 không được cache** (người vừa được cấp membership vào ngay).

**④ `RoleGuard`** (`identity.py:461-491`) — viết thành **lớp** chứ không phải closure, để
đọc ngược được: `guard.allowed_roles` cho phép test khẳng định router nhận vai nào mà
không phải chạy HTTP.

#### Vai `DISPLAY` — cái tivi phòng chờ

```python
async def get_current_identity(identity=Depends(_resolve_identity)):
    if identity.role is ClinicRole.DISPLAY:
        raise HTTPException(403, "Tài khoản màn hình chỉ được xem bảng gọi số")
```

`identity.py:430-446` — chốt quan trọng nhất của cả hệ phân quyền: **mọi** endpoint đi qua
dependency này, có `RoleGuard` hay không, nên chặn ở đây nghĩa là cái tivi bị chặn **ở
khắp nơi mà không phải liệt kê chỗ nào**. Bản kiểm kê 06/08 đếm 26/119 endpoint chưa có
`RoleGuard` — một danh sách cho phép sẽ bỏ sót đúng những chỗ ấy. Hai đường duy nhất nhận
vai này dùng `get_display_identity`: `GET /me` và `GET /display/queue`.

---

### 8.4. `Idempotency-Key` — vì sao có, và bốn đường đang dùng

**Sự cố:** một bệnh nhân bị tạo lịch trùng. Hai phép đo trên staging ghi ở
`cskh.py:333-343`:

- Bấm nút hai lần thật nhanh → **hai** dòng, cách nhau 0,35ms. Giao diện có khoá nút,
  nhưng máy chủ **không có chốt nào**.
- Ngắt mạng ở mốc 90ms sau khi bấm → màn hình báo **LỖI MẠNG** trong khi dữ liệu **đã
  vào**. Người trực nhập lại, và lần nhập lại tạo dòng thứ hai.

Ca thứ hai hay xảy ra ở phòng khám nơi wifi chập chờn, và nó không hỏng ở chỗ dễ thấy:
hai dòng "Đã gọi nhắc hẹn" làm người đọc tưởng đã gọi hai lần.

| Hàm (`api/idempotency.py`) | Giải thích |
|---|---|
| `idempotency_guard(request)` | Dependency. Đọc header `Idempotency-Key`; **không có thì cho qua** (bật dần theo từng màn, không làm chết lời gọi cũ). Dài >200 ký tự → 409 |
| `.acquire(pool, actor_id=)` | `INSERT … ON CONFLICT DO NOTHING` với khoá `(key, endpoint, actor_id)`. Chiếm được → chạy tiếp. Đã `COMPLETED` → trả **response cũ**. Đang `PROCESSING` → **409** |
| `.save(pool, body, status_code)` | Ghi phản hồi vào bảng, `state='COMPLETED'`. Gọi trước `acquire` → `RuntimeError` |
| `.release(pool)` | **Trả khoá vì thao tác bị TỪ CHỐI.** Chỉ khi 4xx |
| `tra_khoa_neu_bi_tu_choi(idem, pool)` | Context manager bọc thân handler — bốn đường có cùng hình dạng, viết một chỗ |

`.acquire()` trả về một guard **MỚI** (dataclass `frozen=True`). Không gán lại thì
**âm thầm tắt chống lặp** rồi làm `save()` ném lỗi — cảnh báo này lặp ở cả ba router dùng
nó (`booking.py:268`, `work_items.py:180`, `payment.py:70`).

**Vì sao phải có `release()`** — `idempotency.py:197-219`, staging 13/08/2026:

```
08:08:23  422  "Chưa có tệp kết quả nào được xác nhận đã gửi…"
08:08:30  422  cùng lý do
08:08:35  409  "Idempotency-Key này đang được xử lý; vui lòng thử lại"
08:08:41  409  cùng câu
```

Từ lần thứ ba, câu người dùng **cần** nghe bị thay bằng câu nói về cơ chế bên trong. Người
trực đọc thành "máy đang bận" rồi bấm lại, và mỗi lần bấm lại chỉ nhận đúng câu ấy cho tới
hết 5 phút. Lúc đo có 8 khoá kẹt ở chính đường này, cái lâu nhất **1 ngày 5 giờ**.

> **Chỉ trả khoá khi 4xx.** Lỗi 5xx nghĩa là không ai biết handler đã ghi tới đâu — giữ
> khoá lại mới đúng, vì lần gửi lại có thể tạo bản thứ hai.

**Bốn đường đang dùng:** `POST /appointments/bookings` · `POST /payments` · bốn lệnh
`POST /work-items/{id}/commands/*` · `POST /cskh/tuong-tac`. Lưới thứ hai nằm ở database:
`uq_appointment_patient_slot_live` chỉ bắn khi hai request **thật sự đồng thời** đặt một
bệnh nhân vào một giờ — tức cú bấm đôi đã lọt qua **cả** chốt trình duyệt **lẫn**
Idempotency-Key; `main.py:364-370` trả một câu người bấm dùng được: *"Lần bấm trước đã
thành công — không cần đặt lại."*

---

### 8.5. BẢNG TỔNG — 189 endpoint

**Ký hiệu vai:** `BS`=DOCTOR · `BS-SA`=ULTRASOUND_DOCTOR · `ĐD-SA`=NURSE_ULTRASOUND ·
`LT`=RECEPTION · `CSKH` · `QL`=MANAGEMENT · `TC`=TRUONG_CA · `TKYK` · `TN`=CASHIER ·
`TN-T`=CASHIER_THUOC · `TN-DV`=CASHIER_DV · `DS`=PHARMACIST · `TV`=DISPLAY.

**Nhóm vai đặt tên:** `INTAKE` = CSKH+LT+QL+TC · `LÂM SÀNG` = BS+BS-SA+TKYK+ĐD-SA ·
`BÁC SĨ` = BS+BS-SA · `THU NGÂN` = TN+TN-T+TN-DV · `SIÊU ÂM` = BS-SA+ĐD-SA+TKYK+TC+QL.
**`mọi vai`** = bất kỳ nhân viên nào đã đăng nhập (`get_current_identity` — đã loại TV).
Tiền tố `/api/v1` bị lược trừ hai đường `/health*`.

| Method | Đường dẫn | Vai được phép (guard) | Gọi service nào | Ý nghĩa nghiệp vụ |
|---|---|---|---|---|
| GET | `/health` | **công khai** | — | Liveness — không chạm phụ thuộc ngoài |
| GET | `/health/db` | **công khai** | pool | Readiness — `SELECT 1`, trả latency |
| POST | `/auth/login` | **công khai** | `AuthService` | Cửa cấp token duy nhất; chống dò mật khẩu ở service |
| GET | `/me` | mọi vai **+ TV** | — | Danh tính đã xác minh + 3 câu trả lời `can_write_clinical/is_doctor/is_cashier` |
| GET | `/events/stream` | mọi vai | `ChangeBroker` | SSE: báo "có gì đó vừa đổi" cho màn hình |
| GET | `/queue` | mọi vai | `queue_order` + `queue_rows` | Thứ tự GỌI của người đã check-in hôm nay |
| GET | `/display/config` | **công khai** | — | Cấu hình khu/nhãn cho TV phòng chờ |
| GET | `/display/queue` | mọi vai **+ TV** | `DisplayBoardService` | Bảng gọi số — **không tên, không mã, không SĐT** |
| POST | `/patients` | INTAKE | `PatientService` + `MPIService` | Đăng ký khách; 3 kết cục: 201 / 200 trùng SĐT / 409 trùng CCCD |
| GET | `/patients/check-phone` | mọi vai | `PatientService` | Cảnh báo sớm SĐT đã có — **tư vấn, không chặn** |
| GET | `/patients/check-duplicate` | mọi vai | `PatientService` | Cảnh báo trùng hồ sơ, **cùng một luật** với lúc lưu |
| POST | `/patients/sdt-them` | INTAKE | `PatientService` | Thêm số phụ cho khách có sẵn |
| DELETE | `/patients/sdt-them` | INTAKE+BS+BS-SA+TKYK | `PatientService` | Gỡ một số phụ (xoá số = sửa hồ sơ) |
| GET | `/patients/{id:uuid}` | mọi vai | `PatientService` | Đọc một hồ sơ |
| GET | `/patients` | mọi vai | `PatientService` | Tra khách theo số điện thoại |
| PATCH | `/patients/{id:uuid}` | INTAKE+BS+BS-SA+TKYK | `PatientService` | Sửa thông tin hành chính |
| POST | `/appointments/bookings` | INTAKE | `BookingService` | **Đặt lịch** — có Idempotency-Key |
| PATCH | `/appointments/{id}` | LÂM SÀNG+LT+CSKH+TC+QL | `BookingService` | Chuyển trạng thái lịch (bảng chuyển tiếp quyết định) |
| GET | `/appointments/cho-xep-bac-si` | LÂM SÀNG+LT+CSKH+TC+QL | SQL trực tiếp | Lịch cần xếp bác sĩ: `CHUA_XEP` và `MAT_BAC_SI` |
| POST | `/appointments/{id}/bao-xep-bac-si` | INTAKE | `ThongBaoService` | CSKH báo quản lý một lịch thiếu bác sĩ |
| GET | `/appointments/quote` | INTAKE | `CapacityService` | Sức chứa theo giờ để lưới tô màu (CAP-01) |
| GET | `/appointments/week` | mọi vai | `WeekAppointmentsService` | Lịch 7 ngày, kèm phân loại Tái khám/Lần đầu |
| GET | `/appointments/doctor-board` | mọi vai | `DoctorBoardService` | Bảng khám của bác sĩ (mặc định **gồm cả lịch huỷ**) |
| GET | `/appointments/policy` | mọi vai | `clinic_policy` | Độ dài khung + số chỗ + giờ mở cửa, giải 3 tầng |
| POST | `/appointments/slot-hold` | INTAKE | `SlotHoldService` | Giữ khung giờ 10 phút — **tư vấn, không khoá** |
| DELETE | `/appointments/slot-hold` | INTAKE | `SlotHoldService` | Thả mọi chỗ người này đang giữ |
| GET | `/appointments/slot-hold` | INTAKE | `SlotHoldService` | Chỗ NGƯỜI KHÁC đang giữ trong ngày |
| GET | `/appointments/ly-do-huy` | LÂM SÀNG+LT+CSKH+TC+QL | `booking_service.LY_DO_HUY` | Danh mục lý do huỷ — một nguồn cho mọi màn |
| GET | `/appointments/{id:uuid}` | mọi vai | `SchedulingService` | Đọc một lịch hẹn |
| GET | `/work-sessions` | QL, TC | `SchedulingService` | Ca trực gần nhất của phòng khám |
| POST | `/work-sessions` | QL, TC | `SchedulingService` | Tạo ca trực |
| GET | `/work-sessions/{id}` | QL, TC | `SchedulingService` | Ca trực + danh sách nhân sự |
| POST | `/work-sessions/{id}/staff` | QL, TC | `SchedulingService` | Gán người vào ca |
| POST | `/work-items/{id}/commands/start` | 12 vai vận hành | `WorkItemService` | **Bắt đầu** bước — chặn nếu FS/SS chưa xong |
| POST | `/work-items/{id}/commands/complete` | 12 vai vận hành | `WorkItemService` | **Kết thúc** bước — chặn nếu FF/SF chưa xong |
| POST | `/work-items/{id}/commands/skip` | 12 vai vận hành | `WorkItemService` | Bỏ bước — **không bao giờ bị chặn**, để gỡ kẹt luồng |
| POST | `/work-items/{id}/commands/cancel` | 12 vai vận hành | `WorkItemService` | Huỷ bước — khác skip: hậu duệ **vẫn** bị chặn |
| GET | `/work-items` | 12 vai + kiểm workspace | `WorkItemService` | Hàng việc của một khu (không lọc ngày = không mất người còn ngồi đó) |
| GET | `/visits/{id}/work-items` | 12 vai + kiểm lượt khám | `WorkItemService` | Các bước của một lượt, theo thứ tự luồng |
| GET | `/work-items/{id}/blockers` | 12 vai vận hành | `WorkItemService` | Còn vướng gì — để UI nói vì sao nút bị khoá |
| GET | `/service-catalogue` | BS, BS-SA, TKYK | `ServiceOrderService` | Dịch vụ chỉ định được + phòng thực hiện |
| POST | `/visits/{id}/service-orders` | BS, BS-SA, TKYK | `ServiceOrderService` | Chỉ định dịch vụ → sinh việc ở phòng tương ứng |
| POST | `/visits/{id}/service-orders/duplicates` | BS, BS-SA, TKYK | `ServiceOrderService` | Cái nào khách đã làm trong 30 ngày (POST vì danh sách mã dài) |
| GET | `/visits/{id}/charges` | THU NGÂN+TC+QL+**BS** | `ServiceOrderService` | Lượt khám nợ gì, đã thu gì |
| GET | `/visits/progress` | mọi vai | `VisitProgressService` | 4 cờ tiến độ/khách — **trả câu trả lời, không trả bằng chứng** |
| GET | `/visits/{id}/workflow` | mọi vai | `VisitProgressService` | Toàn bộ trạng thái luồng của một lượt |
| GET | `/visits/active` | mọi vai | `VisitProgressService` | Mọi lượt đang hoạt động + vị trí khách |
| POST | `/payments` | THU NGÂN + QL | `PaymentService` | **Thu tiền** — Idempotency-Key |
| DELETE | `/payments` | THU NGÂN + QL | `PaymentService` | Huỷ khoản thu — **không xoá** lịch sử tài chính |
| GET | `/cashier/board` | THU NGÂN | `CashierBoardService` | Bảng thu ngân hôm nay — một đường, một vòng mạng |
| POST | `/lab/orders` | **BÁC SĨ** | `LabOrderService` | Chỉ định xét nghiệm (TKYK **cố ý** không có) |
| PATCH | `/lab/results/{id}` | LÂM SÀNG | `LabOrderService` | Nhập kết quả về — **không bao giờ** chốt |
| POST | `/lab/results/{id}/review` | **BÁC SĨ** | `LabSafetyService` | Bác sĩ duyệt + chốt kết quả (giao dịch) |
| POST | `/lab/triage/{id}` | LÂM SÀNG (30/phút) | graph `lab_triage` | Phân nhóm A/B/C; **GROUP_C chưa duyệt → 403** |
| GET | `/lab/results/{id}/release` | LÂM SÀNG | SQL trực tiếp | Được báo BN chưa — chỉ GROUP_A + đã chốt, còn lại **fail closed** |
| POST | `/clinical-records` | LÂM SÀNG + **LT** | `ClinicalRecordService` | Ghi bệnh án (LT chỉ tới được với `vitals_only=true`) |
| GET | `/clinical-forms` | LÂM SÀNG | `ClinicalFormService` | Đọc một phiếu khám chuyên khoa |
| GET | `/clinical-forms/history` | LÂM SÀNG | `ClinicalFormService` | Các lượt khám trước, đủ nội dung phiếu |
| PUT | `/clinical-forms` | LÂM SÀNG | `ClinicalFormService` | Lưu phiếu — **từ chối khi lượt đã FINALIZED** (ADR-0008) |
| POST | `/clinical-forms/andrology-review` | LÂM SÀNG | `AndrologyReviewService` | Cờ dưới ngưỡng WHO + gợi ý XN di truyền + BMI (form NK) |
| GET | `/clinical/{visit_id:uuid}/status` | mọi vai | `ClinicalSignService` | Còn thiếu gì để ký được |
| POST | `/clinical/{visit_id:uuid}/sign` | **BÁC SĨ** | `ClinicalSignService` | **Ký bệnh án** — sau đó nội dung bị khoá (TT13/2011/TT-BYT) |
| POST | `/clinical/{visit_id:uuid}/release` | **BÁC SĨ** | `ClinicalSignService` | Bước hai: cho phép CSKH gửi kết quả cho khách |
| POST | `/clinical/{visit_id:uuid}/amend` | **BÁC SĨ** | `ClinicalSignService` | Đính chính — bản cũ giữ nguyên |
| POST | `/clinical/ultrasound/{id:uuid}/sign` | **BÁC SĨ** | `ClinicalSignService` | Bác sĩ siêu âm ký kết quả **của mình** |
| POST | `/ultrasound/measurements` | **BS-SA** | `UltrasoundService` | 7 số đo thai; EFW **do bác sĩ gõ**, không suy ra |
| GET | `/ultrasound/queue` | SIÊU ÂM | `UltrasoundBoardService` | Hàng chờ siêu âm hôm nay |
| GET | `/ultrasound/rooms` | SIÊU ÂM | `UltrasoundBoardService` | Ba phòng SA — lọc theo cơ sở người đang đứng |
| GET | `/ultrasound/records` | SIÊU ÂM | `UltrasoundBoardService` | Bản ghi SA; tab đã ký gom theo **BỆNH NHÂN** |
| POST | `/ultrasound/draft` | SIÊU ÂM | `UltrasoundService` | Lưu bản nháp kết quả |
| POST | `/ultrasound/{id}/image` | SIÊU ÂM | `MediaService` | Gắn ảnh vào bản ghi |
| GET | `/ultrasound/image` | SIÊU ÂM | `MediaService` | Đọc ảnh — khoá phải thuộc phòng khám người hỏi |
| POST | `/service-log` | LÂM SÀNG | `ServiceLogService` | Thêm một dịch vụ/thủ thuật vào sổ việc |
| PATCH | `/service-log/{row_id}` | LÂM SÀNG | `ServiceLogService` | Bắt đầu / kết thúc một dòng việc |
| POST | `/sono/queue` | ĐD-SA, QL | `ServiceLogService` | Thêm dòng vào hàng chờ của điều dưỡng SA |
| PATCH | `/sono/queue/{row_id}` | ĐD-SA, QL | `ServiceLogService` | Đẩy dòng SA, hoặc bật/tắt mốc của dòng XN |
| DELETE | `/sono/queue/{row_id}` | ĐD-SA, QL | `ServiceLogService` | Xoá dòng — `service_log` không chỉ-thêm |
| POST | `/voice/transcribe` | LÂM SÀNG (10/phút) | `PhoWhisperTranscriber` | Audio → transcript **NHÁP**; **không** ghi bệnh án |
| POST | `/brief/{clinic_patient_id}` | BÁC SĨ + TKYK (20/phút) | LLM + `PatientContextService` | Tóm tắt trước khám |
| GET | `/dispatch/overview` | mọi vai | `DispatchService` | Mỗi khách đang trong phòng khám là một dòng |
| GET | `/dispatch/alerts` | mọi vai | `DispatchService` | Cảnh báo vận hành đã xếp theo mức độ |
| GET | `/dispatch/routes` | mọi vai | `DispatchService` | Các tuyến điều phối đã cấu hình |
| GET | `/dispatch/history` | mọi vai | `DispatchService` | Ai chuyển ai, từ đâu sang đâu, vì sao |
| GET | `/dispatch/tv` | mọi vai | `DispatchService` | Dữ liệu TV — **che ở backend**, chỉ số thứ tự |
| POST | `/dispatch/move` | TC, QL | `DispatchService` | Sang bước khác / đổi phòng trong cùng bước |
| POST | `/dispatch/transfer-room` | TC, QL | `DispatchService` | Đổi phòng — **đồng hồ chờ không được đặt lại** |
| POST | `/dispatch/route` | TC, QL | `DispatchService` | Chọn tuyến sau khám; đổi giữa chừng phải có lý do |
| POST | `/dispatch/alerts/call` | TC, QL | `ThongBaoService` | Gọi một bộ phận; bấm lại khi chưa xử lý **không nhân đôi** |
| PUT | `/dispatch/threshold` | TC, QL | `DispatchService` | Ngưỡng cảnh báo theo phòng hoặc mặc định |
| GET | `/thong-bao` | mọi vai | `ThongBaoService` | Thông báo chưa xử lý của **vai mình** |
| POST | `/thong-bao/da-doc` | mọi vai | `ThongBaoService` | Tắt chấm đỏ — **không** đóng việc |
| POST | `/thong-bao/{id:uuid}/da-xu-ly` | mọi vai | `ThongBaoService` | Bên nhận đóng việc; trả thời gian phản hồi |
| GET | `/reception/checkout` | LT, TC, QL | `CheckoutService` | Lượt khám hôm nay chưa đóng + vướng mắc |
| GET | `/reception/checkout/ton-dong` | LT, TC, QL | `CheckoutService` | Lượt còn mở **từ những ngày trước** — 18 dòng không ai thấy |
| GET | `/reception/checkout/chi-tiet/{visit_id:uuid}` | LT, TC, QL | `CheckoutService` | Toàn cảnh một lượt để đối soát |
| GET | `/reception/checkout/{visit_id:uuid}` | LT, TC, QL | `CheckoutService` | Lượt này đóng được chưa |
| POST | `/reception/checkout` | LT, TC, QL | `CheckoutService` | **Đóng lượt** — không đụng `visit.status` |
| GET | `/pharmacy/queue` | DS, TN-T, TC, QL | `PharmacyService` | Đơn chưa chốt, gồm cả đã cấp một phần |
| GET | `/pharmacy/inventory` | DS, TN-T, TC, QL | `PharmacyService` | Tồn theo lô + hạn dùng + cờ hết hạn |
| POST | `/pharmacy/receive` | DS, QL | `PharmacyService` | Nhập lô vào kho |
| POST | `/pharmacy/dispense` | DS, QL | `PharmacyService` | Cấp thuốc — cấp một phần là bình thường |
| POST | `/pharmacy/refuse` | DS, QL | `PharmacyService` | Khách không lấy thuốc — **lý do bắt buộc** |
| POST | `/pharmacy/close-line` | DS, QL | `PharmacyService` | Không cấp thêm nữa ("lấy 5 rồi thôi") |
| POST | `/pharmacy/adjust` | DS, QL | `PharmacyService` | Kiểm kê lệch; số lượng mang dấu |
| POST | `/pharmacy/discard` | DS, QL | `PharmacyService` | Huỷ thuốc hỏng/hết hạn — ra khỏi kho, không ra khỏi sổ |
| GET | `/cskh/recalls` | CSKH, QL, TC | `RecallService` | Phép chiếu nhắc tái khám — **không bao giờ** trả SOAP note |
| GET | `/cskh/recall-jobs` | CSKH, QL, TC | `RecallJobService` | Việc gọi hôm nay, tách lượt 1 / lượt 2 |
| POST | `/cskh/recall-jobs/generate` | CSKH, QL, TC | `RecallJobService` | Sinh việc gọi hôm nay (idempotent, chờ cắm cron) |
| POST | `/cskh/recall-jobs/{viec_id}/ket-qua` | CSKH, QL, TC | `RecallJobService` | Đã gọi xong — kết quả bắt buộc kể cả không ai nghe |
| POST | `/cskh/recall-jobs/{viec_id}/bo-qua` | CSKH, QL, TC | `RecallJobService` | Không cần gọi nữa |
| POST | `/cskh/nhac-tai-kham` | CSKH, QL, TC | `RecallJobService` | Hẹn tái khám gõ tay → sinh 2 mốc gọi (−7 ngày, −1 ngày) |
| POST | `/cskh/actions` | INTAKE | `CskhService` | Ghi một việc chăm sóc làm bằng tay |
| POST | `/cskh/followup-calls` | INTAKE | `CskhService` | Ghi một cuộc gọi nhắc quay lại |
| POST | `/cskh/tuong-tac` | INTAKE | `TuongTacCskhService` | **Sổ chạm khách** — Idempotency-Key |
| POST | `/cskh/tuong-tac/{id}/hoan-tac` | INTAKE | `TuongTacCskhService` | Rút lại lần chạm bấm nhầm — **không xoá dòng sổ** |
| GET | `/cskh/tuong-tac/{clinic_patient_id}` | INTAKE | `TuongTacCskhService` | Dòng thời gian của một khách |
| POST | `/cskh/hen-goi-lai` | INTAKE | `HenGoiLaiService` | Tự hẹn một việc gọi lại |
| PATCH | `/cskh/hen-goi-lai/{hen_id}` | INTAKE | `HenGoiLaiService` | Đóng việc đã gọi xong |
| POST | `/cskh/phan-hoi` | INTAKE | `PhanHoiKhachService` | Ghi khen / góp ý / khiếu nại |
| PATCH | `/cskh/phan-hoi/{id}` | INTAKE | `PhanHoiKhachService` | Chuyển trạng thái xử lý — đóng phải ghi hướng xử lý |
| POST | `/cskh/ket-qua/tep` | INTAKE | `TepKetQuaService` | **Tải tệp kết quả** — tên do hệ thống đặt, kiểu kiểm bằng byte đầu |
| GET | `/cskh/ket-qua/{clinic_patient_id}` | INTAKE | `TepKetQuaService` | Tệp kết quả của một khách + đã gửi chưa |
| GET | `/cskh/ket-qua/tep/{tep_id}/noi-dung` | INTAKE | `TepKetQuaService` | Đọc tệp **theo luồng**, hiểu HTTP `Range` (206/416) |
| POST | `/cskh/ket-qua/tep/{tep_id}/da-gui` | INTAKE | `TepKetQuaService` | CSKH xác nhận đã gửi cho khách |
| GET | `/cskh/zalo/trang-thai` | INTAKE | `providers.zalo` | Zalo đủ cấu hình chưa, **thiếu gì** |
| POST | `/cskh/zalo/gui` | INTAKE | `GuiZaloService` | Gửi ZNS — chỉ ghi sổ khi Zalo thật sự nhận |
| PATCH | `/episodes/{episode_id}` | CSKH, QL, TC | `EpisodeService` | Đóng/mở lại một đợt chăm sóc |
| GET | `/patients/{patient_id}/links` | mọi vai | `ConsentService` | Ai liên kết với khách này, mỗi chiều chia sẻ form nào |
| GET | `/patients/{patient_id}/shared-form` | mọi vai | `ConsentService` | Hồ sơ A hiện trong buổi khám của B |
| POST | `/patients/links` | QL,BS,LT,CSKH,TKYK | `ConsentService` | Ghi quan hệ — **liên kết KHÔNG mở quyền đọc** |
| POST | `/patients/consents` | QL,BS,LT,CSKH,TKYK | `ConsentService` | Cấp bản đồng ý chia sẻ |
| POST | `/patients/consents/{id}/revoke` | QL,BS,LT,CSKH,TKYK | `ConsentService` | Thu hồi đồng ý |
| POST | `/staff` | QL | `StaffService` | Tạo nhân sự |
| GET | `/staff/{id}` | mọi vai | `StaffService` | Đọc một nhân sự |
| GET | `/staff` | mọi vai | `StaffService` | Danh sách nhân sự (lọc theo cơ sở) |
| PATCH | `/staff/{id}` | QL | `StaffService` | Sửa nhân sự (đổi vai → xoá cache danh tính) |
| DELETE | `/staff/{id}` | QL | `StaffService` | **Xoá mềm** — 204 |
| GET | `/clinic-config/overview` | mọi vai | `ClinicConfigService` | Cơ sở → tầng → phòng, kèm bước mỗi phòng phục vụ |
| GET | `/clinic-config/staff` | **QL** | `ClinicConfigService` | Ai làm được bước nào |
| GET | `/clinic-config/services` | mọi vai | `ClinicConfigService` | Dịch vụ nào dùng phiếu nào |
| PUT | `/clinic-config/service-form` | **QL** | `ClinicConfigService` | Gán phiếu khám cho một dịch vụ |
| PUT | `/clinic-config/room-floor` | **QL** | `ClinicConfigService` | Đặt tầng cho một phòng |
| PUT | `/clinic-config/room-nodes` | **QL** | `ClinicConfigService` | Phòng này phục vụ những bước nào |
| PUT | `/clinic-config/staff-nodes` | **QL** | `ClinicConfigService` | Người này làm được những bước nào |
| POST | `/roster/shifts` | **QL** | `ConfigService` | Xếp ca (luồng tự đăng ký đang **đóng**) |
| PATCH | `/roster/shifts/{roster_id}` | **QL** | `ConfigService` | Duyệt / từ chối một ca |
| DELETE | `/roster/shifts/{roster_id}` | **QL** | `ConfigService` | Gỡ một ca |
| GET | `/roster/stations` | **QL** | `ConfigService` | Nhân viên này được xếp vào vị trí nào |
| GET | `/roster/station-scope` | **QL** | `ConfigService` | Ma trận vai × vị trí |
| PUT | `/roster/station-scope` | **QL** | `ConfigService` | Bật/tắt một ô của ma trận |
| POST | `/roster/weeks/apply` | **QL** | `ConfigService` | **Chốt** lịch trực một tuần |
| GET | `/roster/weeks/applied` | **QL** | `ConfigService` | Tuần nào đã áp dụng (còn lại là dự kiến) |
| GET | `/service-prices` | THU NGÂN, TC, QL | `ConfigService` | Bảng giá thuốc / dịch vụ |
| POST | `/service-prices` | THU NGÂN, TC, QL | `ConfigService` | Thêm dòng bảng giá |
| PATCH | `/service-prices/{price_id}` | THU NGÂN, TC, QL | `ConfigService` | Đổi giá / đổi tên / tắt dòng |
| DELETE | `/service-prices/{price_id}` | THU NGÂN, TC, QL | `ConfigService` | Xoá dòng bảng giá |
| PATCH | `/booking-policy` | TC, QL | `ClinicSettingsService` | Đổi luật đặt lịch của phòng khám (C.3) |
| POST | `/booking-rules` | TC, QL | `BookingOverrideService` | Ghi một luật số chỗ (C.4) |
| GET | `/booking-rules` | TC, QL | `BookingOverrideService` | Mọi luật còn hiệu lực, hai tầng gộp một |
| DELETE | `/booking-overrides/doctor/{id}` | TC, QL | `BookingOverrideService` | Xoá override theo bác sĩ |
| DELETE | `/booking-overrides/slot/{id}` | TC, QL | `BookingOverrideService` | Xoá override theo khung giờ |
| GET | `/booking-rules/doctor` | TC, QL | `LuatBacSiService` | Luật bắt buộc bác sĩ của phòng khám |
| PUT | `/booking-rules/doctor` | TC, QL | `LuatBacSiService` | Đặt/sửa luật một dịch vụ (PUT vì mỗi dịch vụ một luật) |
| GET | `/booking-rules/doctor/xem-thu` | TC, QL | `LuatBacSiService` | Cách tính này coi bao nhiêu khách hiện có là "mới" |
| DELETE | `/booking-rules/doctor/{luat_id}` | TC, QL | `LuatBacSiService` | Gỡ hẳn một luật |
| PATCH | `/display-settings` | TC, QL | `ClinicSettingsService` | Bật/tắt khu trên bảng gọi số, cách hiện tên |
| GET | `/feature-mode` | 12 vai (đọc) | `ClinicSettingsService` | `CSKH_ONLY` hay `FULL_CLINIC` |
| PUT | `/feature-mode` | **QL** | `ClinicSettingsService` | Đổi chế độ phòng khám |
| GET | `/catalog/wards` | **công khai** | SQL trực tiếp | Danh mục phường/xã — `Cache-Control: public, 1h` |
| GET | `/catalog/service-types` | mọi vai | SQL trực tiếp | Dịch vụ của phòng khám mình — `private, no-store` |
| GET | `/catalog/booking-channels` | mọi vai | SQL trực tiếp | Kênh đặt lịch của phòng khám mình — `private, no-store` |
| GET | `/audit/events` | QL, TC, CSKH | `AuditLogService` | Nhật ký thao tác, đã giải tên người + tên khách |
| GET | `/reports/booking-channels` | **QL** | `ReportsService` | Lịch theo nguồn đặt — một truy vấn thay 8 lượt đếm |
| GET | `/reports/kpi-dat-lich` | **QL** | `ReportsService` | Mỗi người đặt được bao nhiêu lịch |
| GET | `/ops/status` | **QL** | `OpsStatusService` | Trạng thái dịch vụ |
| GET | `/ops/telemetry` | **QL** | `telemetry` ring buffer | Thời gian phản hồi + lỗi gần đây |
| GET | `/console/overview` | **QL**, **≠production** | `ConsoleService` | Bảng điều khiển chủ sản phẩm |
| POST | `/console/feedback` | **QL**, **≠production** | `ConsoleService` | Ghi phản hồi kèm ảnh |
| POST | `/orchestrator/chat` | **QL**, cần bật cờ (20/phút) | `OrchestratorService` | Endpoint gỡ lỗi luồng AI |
| POST | `/tools/patient/get-summary` | **QL**, **chỉ dev/test** | `tools.patient` | Bề mặt curl/OpenAPI cho tầng tools |
| POST | `/tools/scheduling/find-oncall` | **QL**, **chỉ dev/test** | `tools.scheduling` | — |
| POST | `/tools/event-log/append` | **QL**, **chỉ dev/test** | `tools.event_log` | — |
| POST | `/tools/kb/read-policy` | **QL**, **chỉ dev/test** | `tools.kb` | — |
| POST | `/tools/communication/send-zalo` | **QL**, **chỉ dev/test** | `tools.communication` | — |
| POST | `/tools/lab/classify` | **QL**, **chỉ dev/test** | `tools.lab` + LLM | — |
| POST | `/tools/task/create` | **QL**, **chỉ dev/test** | `tools.task` | — |
| POST | `/tools/task/query` | **QL**, **chỉ dev/test** | `tools.task` | — |
| POST | `/tools/task/update-status` | **QL**, **chỉ dev/test** | `tools.task` | — |
| GET | `/tools/task/check-sla/{task_id}` | **QL**, **chỉ dev/test** | `tools.task` | — |

---

### 8.6. `routers/booking.py` — đặt lịch và vòng đời lịch hẹn

`/appointments/cho-xep-bac-si` là ví dụ tốt nhất về "vì sao" trong file này. Nó trả về
**hai** lý do, không phải một (`booking.py:108-130`): `CHUA_XEP` (`doctor_id IS NULL`,
lịch chưa từng xếp ai) và `MAT_BAC_SI` (**có** bác sĩ, nhưng bác sĩ ấy không còn ca trực
ngày khám). Lý do thứ hai thêm 11/08/2026 sau một phép thử: gỡ **một** ca trực làm **hai**
lịch mất bác sĩ, và màn hình thấy **không cái nào**. Không dòng mã nào khác trong hệ đi tìm
loại lịch này — khi bác sĩ nghỉ đột xuất, đường duy nhất để biết là khách đến quầy rồi mới
vỡ lẽ.

Trong truy vấn ấy, `WHERE w.clinic_id = a.clinic_id` xuất hiện **lần nữa** ở truy vấn con
(`booking.py:177-188`): backend chạy bằng quyền chủ database nên **RLS không áp**, và một
truy vấn con thiếu `clinic_id` nhìn thấy ca trực của **mọi** cơ sở — bác sĩ trực Hào Nam
sẽ làm câu này kết luận lịch bên Kim Ngưu "vẫn có người".

`/appointments/policy` và `/appointments/week` cố ý **không** dùng `_BOOKING_GUARD`
(`booking.py:400-404`): bảng lịch tuần ở trang chủ vẽ cho mọi vai, và ba con số slot/cap
không phải dữ liệu bệnh nhân — *"giấu chúng khỏi một nửa phòng khám chỉ làm lưới vẽ sai,
không làm ai an toàn hơn."* Cùng tinh thần, `BookingRequest.location_id` là **tuỳ chọn**,
mặc định `identity.location_id` (`booking.py:62-71`): bắt buộc nó nghĩa là trình duyệt
phải nghĩ ra một cơ sở, và cái nó nghĩ ra là `locations[0].id` — "cơ sở đầu tiên trong
danh sách", không phải "nơi buổi khám diễn ra".

### 8.7. `routers/work_items.py` — Command API của nhân lõi luồng

Bốn lệnh, mỗi lệnh một URL. **Cố ý không có endpoint nào nhận vào một status**: frontend
nêu *ý định*, backend quyết định có được phép không. Phân quyền chạy **hai lần**, có chủ
đích (`work_items.py:8-11`): `require_role` loại những vai không bao giờ chạm luồng ra khỏi
router; rồi service kiểm người gọi có nằm trong `node_definition.actor_roles` của **nút cụ
thể** — đó là *cấu hình*, không sống được trong decorator. Hai hàm gác riêng đáng đọc:

| Hàm | Giải thích |
|---|---|
| `require_workspace_read_access` (`:67`) | Một hàng việc là một bề mặt dữ liệu bệnh nhân. Vai được mở một khu **khi nó là actor của ít nhất một nút ở khu đó** — hỏi thẳng `node_definition`. `{}` cố ý nghĩa là "chưa ai", nên danh sách rỗng **không** cấp quyền |
| `require_visit_work_items_read_access` (`:100`) | Chặn UUID lượt khám trở thành *oracle định danh*: vai thường phải sở hữu một nút **đang sẵn sàng hoặc đang làm** trên lượt ấy. Lượt không tồn tại và lượt không được phép trả **cùng một 403** |

`CommandRequest.expected_version` (`:162`) biến một lần sửa đồng thời thành **409** thay
vì ghi đè im lặng. `skip` **không bao giờ bị chặn** — nó là cái van gỡ kẹt luồng; `cancel`
thì hậu duệ vẫn bị chặn. Hai động tác khác nhau, không gộp.

`WorklistItem.service_code` phải khai **ở Pydantic model** chứ không chỉ ở SQL
(`work_items.py:319-322`): `response_model` **lọc bỏ mọi khoá không có trong model, im
lặng** — service trả đúng dữ liệu mà API vẫn ra `null`. Đã mất một lượt deploy vì chuyện
này.

### 8.8. `routers/cskh.py` — 21 cửa của chăm sóc khách hàng

Router lớn nhất (661 dòng). Hai bộ gác: `_INTAKE_GUARD` (CSKH+LT+QL+TC — *"ai ghi được hồ
sơ hành chính của khách thì ghi được 'đã gọi cho khách'"*) và `_RECALL_GUARD` (CSKH+QL+TC).

| Hàm | Giải thích |
|---|---|
| `_doc_upload_co_gioi_han` (`:54`) | Đọc tệp tải lên **theo từng khối có trần**. `UploadFile.read()` không tham số nuốt trọn một body do kẻ tấn công điều khiển. Đọc 512 byte đầu để **nhận kiểu thật**, rồi đọc tối đa `limit + 1` byte — **byte cuối cùng đó chứng minh tệp quá lớn mà không phải nuốt phần còn lại** |
| `doc_tep_ket_qua` (`:541`) | Trả nội dung theo **luồng** và hiểu `Range` → 206/416. Không phải tối ưu để sau: không có nó thì trình duyệt phải tải trọn tệp trước khi phát giây đầu, và container API giới hạn 1GB |
| `ghi_tuong_tac` (`:325`) | Sổ chạm khách — đường thứ tư dùng Idempotency-Key (§8.4) |

`TuongTacRequest.ket_qua` là một `Literal` **phải khớp** `KET_QUA_HOP_LE` trong
`tuong_tac_cskh_service`, và có bài kiểm `test_router_literal_khop_service` canh
(`cskh.py:299-303`). Hai lần mở rộng trước chỉ sửa service mà trượt chỗ này **trong im
lặng**: suốt một buổi, CSKH chọn "không liên lạc được" là ăn 422 — service nhận, nhưng cửa
Pydantic đã đóng. Còn `/cskh/zalo/trang-thai` (`:623`) là một mẫu giao diện đáng học: *ẩn
hẳn nút thì người dùng không biết tính năng tồn tại; hiện nút mà bấm vào báo lỗi thì họ
tưởng hệ thống hỏng.* Đường thứ ba là **hiện nút + nói thiếu gì**.

### 8.9. `routers/dispatch.py` — điều phối, thông báo, và quầy check-out

Ba nhóm trong một file, ba mức gác: đọc điều phối mở cho **mọi vai** (Lễ tân và điều
dưỡng cũng cần biết khách đang ở đâu); ghi điều phối chỉ **TC + QL**; quầy check-out là
**LT + TC + QL**. `/dispatch/tv` che dữ liệu **ở backend** (`dispatch.py:99-103`): *"một
màn hình công cộng mà dữ liệu nhạy cảm vẫn đi qua đường mạng thì chỉ cần mở công cụ nhà
phát triển là đọc được."* Và `dispatch.py:349-351` giải thích vì sao đường tham số phải
khai `{visit_id:uuid}` chứ không phải `{visit_id}` trần — đường literal
`/reception/checkout` ngay trên sẽ **bị nuốt**.

### 8.10. `routers/lab.py` — cổng an toàn y khoa

Bốn bộ gác **khác nhau** trên năm endpoint, và sự khác nhau là điểm chính: **chỉ định** và
**duyệt/chốt** dùng `PHYSICIAN_ROLES` (BS, BS-SA) — **TKYK cố ý vắng mặt**, vì chỉ định
một xét nghiệm và ký duyệt một kết quả là hành vi một thư ký y khoa không được làm
(`identity.py:86-95`); **nhập kết quả** dùng `CLINICAL_WRITE_ROLES` (rộng hơn, có TKYK và
ĐD-SA) nhưng loại rõ Lễ tân và Quản lý.

Tên `PHYSICIAN_ROLES` (thay vì `DOCTOR_ROLES`) sinh ra từ một lỗi thật: tên cũ đọc thành
"mọi người ngồi bàn bác sĩ", trình duyệt hiểu theo nghĩa rộng và **vẽ nút "Chỉ định XN"
cho TKYK**, người này bấm vào và ăn 403. Nay có **hai** hằng số vì đó là **hai câu hỏi**:
`PHYSICIAN_ROLES` (có bằng hành nghề) và `DOCTOR_DESK_ROLES` (làm việc ở bàn bác sĩ).

Cổng an toàn cứng ở `lab.py:201-210`: `GROUP_C` mà `reviewed_at IS NULL` → **403
SafetyGateError**. Graph phân loại thì *không* ném lỗi — nó luôn kết thúc và tạo task
`LAB_REVIEW` khẩn; **router** mới là nơi thi hành ranh giới. Và `/lab/results/{id}/release`
**fail closed** cho mọi giá trị lạ: chỉ `GROUP_A` + đã chốt mới được báo bệnh nhân.

### 8.11. `routers/config.py` + `clinic_config.py` — 31 endpoint cấu hình

Một bài học phân quyền đáng chép:

```python
_WRITE_GUARD = require_role(ClinicRole.MANAGEMENT)
# Cùng mức nhưng là hằng RIÊNG: hai câu hỏi khác nhau tình cờ cùng đáp án hôm nay.
_STAFF_READ_GUARD = require_role(ClinicRole.MANAGEMENT)
```

(`clinic_config.py`) — *dùng chung một hằng thì ngày nới một bên sẽ nới luôn bên kia mà
không ai thấy.*

`ROSTER_ROLES` = **chỉ QL** (`config_service.py:42-52`). Luồng tự đăng ký ca đang **đóng**,
và phải siết ở service chứ không chỉ ẩn bảng: ẩn nút mà để nguyên đường ghi thì ai cũng
còn `POST /api/v1/roster/shifts` được, và ca họ ghi rơi vào `PENDING` — **vô hình với cả
người xếp lịch lẫn màn chính thức. Treo vĩnh viễn, không ai thấy.**

### 8.12. Router có điều kiện môi trường

| Router | Điều kiện | Vì sao |
|---|---|---|
| `console.py` | `APP_ENV != production`, mặc định **coi là production** khi không đặt (`:28-36`) | Trang này liệt kê **mọi tài khoản đăng nhập được** — trên hệ đang phục vụ bệnh nhân đó là một bản đồ tấn công. Chặn ở API, vì trang bị ẩn vẫn gọi được API |
| `tools.py` | chỉ `dev/development/local/test/testing`, ngoài ra **404** (`:139-149`) | Bề mặt curl/OpenAPI cho lập trình viên graph, không phải orchestration production |
| `orchestrator.py` | cần `ENABLE_AI_ORCHESTRATOR=true`, ngoài ra **503** (`:22-28`) | Luồng AI chưa xong là opt-in |

Cả ba đều trả **404** hoặc **503** chứ không phải 403 — không xác nhận sự tồn tại.

---

### 8.13. Các service router gọi tới mà chưa mục nào phụ trách

#### `services/checkout_service.py` (643 dòng) — đóng lượt ở quầy Lễ tân

> **Đóng lượt KHÔNG phải là ký bệnh án, và đây là chỗ suýt sai.** `visit.status =
> 'FINALIZED'` trông như "lượt khám đã xong", nhưng nó là **khoá hồ sơ bệnh án** theo
> TT13/2011/TT-BYT: trigger `visit_finalized_block_update` chặn mọi UPDATE sau đó. Nếu Lễ
> tân bấm "Hoàn tất check-out" mà hệ thống đặt FINALIZED thì **một thao tác hành chính vừa
> khoá vĩnh viễn một hồ sơ y tế**.

Nên `close()` hoàn tất bước `LUOTKHAM-15` và **không đụng** `visit.status`. Chỉ nhánh
`incomplete=True` (khách về giữa chừng) ghi `INCOMPLETE` — trạng thái **không-cuối**, bác
sĩ vẫn ký lên FINALIZED được sau.

| Hàm | Giải thích |
|---|---|
| `readiness(visit_id)` | Lượt này đóng được chưa, còn vướng gì |
| `pending_list()` | Lượt **hôm nay** chưa đóng + vướng mắc từng lượt |
| `chi_tiet(visit_id)` | Toàn cảnh để đối soát: dịch vụ đã làm · đã thu · hồ sơ sẽ trả · theo dõi sau khám · dòng thời gian |
| `stale_list()` | Lượt còn mở **từ những ngày trước** — 18 dòng không màn hình nào thấy |
| `close(...)` | Đóng lượt; còn vướng thì **phải có lý do ngoại lệ** |
| `build_blockers(...)` | Hàm thuần: biến vướng mắc thành câu đọc được |

#### `services/pharmacy_service.py` (657 dòng) — kho thuốc và cấp phát

> **Vì sao file này được viết:** nhà thuốc là một cái kho **xây xong vỏ mà chưa có cửa
> vào**. Lược đồ đầy đủ và chặt (`drug_batch`, `inventory_txn` chỉ-thêm, trigger cộng dồn,
> CHECK chặn tồn âm), bốn màn hình chạy được, vai PHARMACIST có tài khoản thật. Nhưng đo
> trên production 07/08/2026: **không một dòng Python nào chạm tới ba bảng ấy.** Dược sĩ
> mở màn kho thấy bảng rỗng và **không có nút nào để nhập hàng**.

Ba tình huống thật → **một mô hình**: khách mua / không mua / mua một phần đều đi qua
`cap_phat()`, cộng vào `prescription.dispensed_qty` và ghi một dòng `DISPENSE`; "không
mua" là `tu_choi()`, "lấy 5 rồi thôi" là cấp 5 rồi `chot()`.

| Hàm | Giải thích |
|---|---|
| `hang_doi()` / `ton_kho()` | Đọc. Lô hết sạch **vẫn hiện** — nó là lịch sử |
| `nhap_lo()` | Tạo lô nếu chưa có + ghi `RECEIVE` |
| `cap_phat()` | Cấp (một phần là bình thường) |
| `tu_choi()` | Khách không mua — **lý do bắt buộc**, CSKH còn gọi lại hỏi |
| `chot()` | Không cấp thêm nữa |
| `dieu_chinh()` | Kiểm kê lệch; `so_luong` **mang dấu** |
| `huy()` | Huỷ thuốc hỏng/hết hạn — ra khỏi kho, **không ra khỏi sổ** |

#### `services/tep_ket_qua_service.py` (295 dòng) — tệp kết quả khám

Ba điều thi hành **ở đây, không phải ở giao diện**: ① tên tệp do hệ thống đặt (tên client
gửi có thể là `../../../etc/passwd`, chỉ giữ làm nhãn); ② kiểu kiểm **bằng nội dung**, không
bằng đuôi (một tệp `kq.mp4` chứa HTML sẽ được trình duyệt *chạy* nếu phục vụ sai kiểu);
③ đọc lại **phải chứng minh quyền** — đoán một UUID không được phép đủ để mở tệp của bệnh
nhân khác. Cộng một điều về trí nhớ: video đọc theo **luồng**, vì container API giới hạn
1GB và ba người cùng xem một video 80MB kiểu `read_bytes()` là 240MB tức thời — đủ để tiến
trình bị giết giữa giờ khám.

| Hàm | Giải thích |
|---|---|
| `tai_len()` | Nhận tệp, cất lên đĩa với tên hệ thống đặt |
| `danh_sach()` | Tệp của một khách, mới nhất trước |
| `duong_dan_de_doc()` | `(đường dẫn, mime, số byte, tên)` — **sau khi** chứng minh quyền |
| `danh_dau_da_gui()` | CSKH xác nhận đã gửi (hệ thống chưa tự gửi được) |

#### `services/lab_order_service.py` + `lab_safety_service.py`

`LabOrderService` chuyển từ `dashboard/app/api/lab-result/route.ts` sang, để luật thôi
sống trong một Next route đang cầm service-role key. Giữ 1:1 các luật; `is_finalized`
**không bao giờ** đặt ở đây. `normalize_link()` biến một link dán vào thành thứ `href` mở
được. `LabSafetyService` sở hữu các **sự thật giao dịch**: `persist_classification()` chỉ
ghi kết quả **giữ nguyên hoặc tăng mức nặng** — một bộ phân loại **không được** ghi đè kết
quả mà bác sĩ vừa chốt giữa lúc fetch và persist; `finalize_review()` làm duyệt + chốt
trong **một** giao dịch ràng theo tenant và bệnh nhân.

#### `services/visit_progress_service.py` (173 dòng)

Tồn tại vì `/home` vẽ thanh tiến độ mỗi khách (đến → đo sinh hiệu → khám → thanh toán) và
**đã đọc `clinical_record` + `prescription` bằng phiên của chính người gọi** — nghĩa là Lễ
tân, người mở `/home` cả ngày, phải đọc được bệnh án của bác sĩ. Đúng một lượt đọc ấy chặn
cả việc siết RLS theo vai (ROLE-02).

> Nay lượt đọc chuyển vào đây, và thứ trả về là **câu trả lời, không phải bằng chứng**:
> bốn boolean cộng danh sách khoản đã thu. *Lễ tân biết sinh hiệu đã được đo; không biết
> huyết áp bao nhiêu.* Đó là ranh giới một policy không vẽ được còn một endpoint thì có.

#### `services/queue_order.py` + `queue_rows.py` — luật thứ tự gọi

`queue_order.py` là **nguồn sự thật duy nhất** cho thứ tự gọi, và mọi hàm trong nó **thuần**
— không I/O, không `await`, không chạm database. Trước đây luật này có hai bản (Python ở
đây + TypeScript chép lại ở `dashboard/lib/queue.ts` mà ba màn đang dùng); bản TS đã bị xoá.

Luật (Model ②, chốt 26/06/2026) — **số vé định danh người bệnh, KHÔNG quyết thứ tự gọi**.
Bốn làn: `-2` ưu tiên (theo số vé) · `-1` kết quả XN/SA đã về, vào lại (theo **giờ đến**) ·
`0` có hẹn và đến trong khung (theo **giờ hẹn**) · `1` vãng lai.

| Hàm | Giải thích |
|---|---|
| `call_rank()` | Khoá sắp xếp — nhỏ hơn = gọi sớm hơn |
| `call_reason()` | **Vì sao** người này đứng ở làn đó. Bảng gọi số phải trả lời được câu của người ngồi chờ: *"vì sao người kia vào trước tôi?"* |
| `explain_queue()` | Xếp **và** giải thích trong một lượt |
| `b3_ready_appt_ids()` | Lịch có ≥1 kết quả về và 0 cái chờ → đủ điều kiện vào lại |
| `entry_from_row()` (`queue_rows.py`) | Cầu nối hàng SQL → `QueueEntry`, để `queue_order` giữ được tính thuần |

Cách hỏng dễ nhất là ai đó thêm một lượt tra chính sách vào `call_rank` cho tiện —
`test_queue_order.py` có bài canh đúng việc đó.

#### `services/service_order_service.py` + `work_item_service.py`

`ServiceOrderService`: bác sĩ chọn dịch vụ; mỗi dịch vụ do một nút thực hiện
(`service_price.node_code`), và chỉ định sinh việc ở phòng của nút đó. Luật "phòng nào",
"có được chỉ định không", "nhiều siêu âm gộp thành một lượt vào phòng SA" **nằm trong SQL**
(`order_services`), vì chúng phải giữ **bất kể ai gọi** và backend bỏ qua RLS. Chỉ định
**cố ý không** hoàn tất `LUOTKHAM-05`: bác sĩ thường chỉ định, xem một thứ, rồi chỉ định
tiếp — đóng bước ngay lần gửi đầu buộc cô phải mở lại, mà **không có lệnh mở lại**.

`WorkItemService.issue()` là nơi quyết định "được phép": chuyển tiếp hợp lệ với trạng thái
hiện tại · vai người gọi nằm trong actor list của nút · cổng phụ thuộc mở
(`work_item_gate_blockers` **trong SQL**, để không ai đi vòng) · không ai khác vừa động vào
(UPDATE mang theo `version` người gọi đã đọc; thua cuộc đua = **409**, không phải ghi đè im
lặng). Đổi trạng thái và dòng `work_item_event` ghi trong **một** giao dịch, nên lịch sử
không thể mâu thuẫn với trạng thái.

---

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

| # | Bẫy | Chuyện gì đã xảy ra |
|---|---|---|
| 1 | **`add_middleware` đăng ký NGƯỢC** — cái thêm sau cùng nằm ngoài cùng | Ba tháng chạy với ngăn xếp ngược: Timing mù trước cơn lũ 401 nó sinh ra để hiển thị, và mọi 401/403/503 đi ra không có `X-Request-ID` (`main.py:132-149`, `test_middleware_order`) |
| 2 | **`Depends(instance)` hỏng, `Depends(hàm)` chạy** | Module có `from __future__ import annotations` nên annotation là chuỗi lúc chạy; FastAPI giải chúng qua `call.__globals__` — thuộc tính một **instance** không có. `request: Request` ở lại dạng chuỗi và bị coi là **query parameter**: mọi endpoint được gác trả `422 {"loc":["query","request"]}` (`runaway_guard.py:216-234`) |
| 3 | **`idem.acquire()` trả guard MỚI** | `IdempotencyGuard` là `frozen=True`. Không gán lại thì chống lặp **âm thầm tắt**, rồi `save()` ném `RuntimeError` ở một chỗ khác hẳn |
| 4 | **Không trả khoá khi 4xx = câu lỗi thật biến mất 5 phút** | Đo staging 13/08: từ lần bấm thứ ba, "chưa gửi tệp kết quả cho khách" bị thay bằng "đang được xử lý, thử lại". 8 khoá kẹt, cái lâu nhất 1 ngày 5 giờ. Đường nào quên bọc `tra_khoa_neu_bi_tu_choi` là lỗi quay lại y như cũ |
| 5 | **`response_model` lọc bỏ khoá lạ TRONG IM LẶNG** | Service trả đúng dữ liệu, API vẫn ra `null`. Mất một lượt deploy vì `service_code` không khai trong `WorklistItem` (`work_items.py:319-322`) |
| 6 | **Đường literal bị đường tham số nuốt** | `/appointments/policy` biến mất rất lâu vì `{id}` trần. Cách chữa **không** phải "khai trước" mà là bộ chuyển đổi `{id:uuid}` — ràng buộc dựa vào thứ tự vài dòng ở chỗ khác chính là thứ gây lỗi (`patients.py:81-85`, `dispatch.py:349-351`) |
| 7 | **Backend bỏ qua RLS** | Mỗi truy vấn con phải **tự** lọc `clinic_id`. Thiếu một chỗ là thấy dữ liệu của mọi cơ sở, và nó **trả lời sai mà không báo lỗi** (`booking.py:177-188`) |
| 8 | **`Literal` ở router lệch với hằng ở service** | Service nhận giá trị mới, cửa Pydantic thì không → 422 khó hiểu. Một buổi CSKH không chọn được "không liên lạc được" (`cskh.py:299-303`) |
| 9 | **`Cache-Control: public` cho dữ liệu theo phòng khám** | Đúng khi danh mục còn toàn cục, sai từ lúc nó thành của-từng-clinic: một cache dùng chung trước API có thể **trao bảng giá của phòng khám này cho phòng khám kia** (`catalog.py:48-61`) |
| 10 | **Log dùng `message=` bị `[REDACTED]`** | `core.logging` coi `message` là nội dung bệnh nhân. Mọi lỗi nghiệp vụ từng ghi `{"error_code": …, "message": "[REDACTED]"}` và nói với người vận hành **đúng con số không**. Dùng `reason=` (`main.py:330-334`) |
| 11 | **Chặn ở giao diện không phải là chặn** | Ẩn bảng đăng ký ca mà để nguyên đường ghi: ai cũng còn POST được, ca ghi ra rơi vào `PENDING` — vô hình với **cả hai** phía, treo vĩnh viễn (`config_service.py:44-51`). Cùng logic với `console.py`, `tools.py` |
| 12 | **Guard tầng router chặn cả vai `DISPLAY`** | `runaway_guard` gọi `get_current_identity`, mà hàm đó từ chối DISPLAY → `/api/v1/me` trả 403 cho tivi **dù endpoint đã khai `get_display_identity`**. Phải dùng `runaway_guard_cho_ca_man_hinh`; nhìn mã endpoint không thấy gì sai, thứ từ chối nằm ở tham số mặc định của một dependency ở file khác (`runaway_guard.py:243-266`) |


---

## PHẦN 9. CƠ SỞ DỮ LIỆU — LƯỢC ĐỒ, VIEW, TRIGGER, RLS

> Lược đồ là **nguồn sự thật duy nhất** của hệ thống. Không có click-ops trên
> dashboard Supabase: mọi thay đổi là một tệp `.sql` có trong git, áp bằng
> `supabase db push` (`supabase/README.md`).

Thư mục `supabase/` gồm bốn phần:

| Thư mục/tệp | Vai trò |
|---|---|
| `migrations/*.sql` | 117 tệp, đặt tên `<timestamp>_<mô_tả>.sql`. Áp theo thứ tự tên tệp |
| `tests/*.sql` | 23 tệp khẳng định chạy trên **Postgres thật**, mỗi tệp tự `BEGIN … ROLLBACK` |
| `seed.sql` | Dữ liệu tra cứu, **không có PII**: `service_type` (14), `drug_catalog` (64), `province` (34), `ward` (3321)… |
| `config.toml` | Cấu hình Supabase CLI |

---

### 9.1. 117 tệp migration — đọc theo CHỦ ĐỀ, không đọc theo tệp

Liệt kê 117 tệp là vô ích. Chúng chia thành chín đợt, mỗi đợt là một câu hỏi
nghiệp vụ được trả lời; các đợt sau **sửa** giả định của đợt trước.

| Đợt | Tệp tiêu biểu | Dựng lên cái gì |
|---|---|---|
| **① Nền móng** (14/07) | `20260714000000_extensions.sql`, `20260714000001_baseline_schema.sql` | 4 extension (`unaccent`, `pg_trgm`, `btree_gist`, `pgcrypto`) + **32 bảng** gộp từ 62 migration lịch sử. Baseline được đóng băng bằng `pg_dump --schema-only` rồi tối ưu: bỏ 3 bảng chết, gộp mọi `ALTER` vào `CREATE` |
| **② Chốt an toàn đầu tiên** (14–17/07) | `..._slot_capacity_guard.sql`, `..._idempotency_key.sql`, `..._atomic_queue_checkin.sql`, `..._event_log_least_privilege.sql` | Lưới 2+1 bằng advisory lock, chống phát lại request, cấp số thứ tự nguyên tử, `event_log` chỉ MANAGEMENT đọc |
| **③ Đa phòng khám + kernel** (30/07, 18 tệp) | `20260730000003_multi_tenant_foundation.sql`, `20260730000004_tenant_scoped_rls.sql`, `20260730000005_workflow_kernel.sql` | Bảng `clinic` + `clinic_membership`, cột `clinic_id` xuyên mọi bảng nghiệp vụ, thay toàn bộ `USING (true)`, dựng 37 node quy trình |
| **④ Vận hành lượt khám** (31/07–02/08) | `20260731000003_visit_workflow_instantiation.sql`, `20260801000002_order_services.sql`, `20260802000001_pharmacy_inventory.sql` | Check-in sinh `work_item` cho cả xương sống 7 node; chỉ định dịch vụ; kho thuốc theo lô |
| **⑤ Luật đặt lịch** (03/08, 12 tệp) | `20260803000001_clinic_booking_policy.sql`, `20260803000009_slot_override_minute_granularity.sql`, `20260803000012_pin_clinic_timezone.sql` | Sức chứa 3 tầng theo khoảng phút, giờ mở cửa, ghim `Asia/Ho_Chi_Minh` bằng CHECK |
| **⑥ Điều phối + chốt hồ sơ** (04/08, 21 tệp) | `20260804000003_dispatch_move.sql`, `20260804000007_clinical_sign_release.sql`, `20260804000014_gate_rule.sql` | Phòng/tuyến/di chuyển, bác sĩ ký cho phép gửi kết quả, luật thứ tự bắt buộc giữa các bước |
| **⑦ Realtime & tiền** (05–06/08) | `20260805000005_clinic_secret.sql`, `20260806000001_notify_change_for_live_screens.sql`, `20260806000004_luot_kham_do.sql` | Credential ra khỏi `clinic.settings`, bỏ Supabase Realtime → `pg_notify`, trạng thái `INCOMPLETE` cho lượt khám dở |
| **⑧ CSKH** (07–12/08, ~25 tệp) | `20260809000003_so_tuong_tac_cskh.sql`, `20260809000005_trang_thai_cskh_suy_ra.sql`, `20260810000008_viec_cskh_theo_tung_luot.sql`, `20260810000009_hoan_tac_mot_lan_cham.sql` | Sổ chỉ-thêm cho mỗi lần chạm khách, hai view suy việc, hoàn tác không xoá dấu vết |
| **⑨ Vá cuối** (14–17/08) | `20260814000001_notify_cho_man_cskh_va_giu_cho.sql`, `20260815000002_nhieu_so_dien_thoai.sql`, `20260815000003_notify_event_log_cho_relay.sql` | Nối 5 bảng bị bỏ quên vào đường notify, một khách nhiều SĐT, đánh thức relay Telegram |

Điều đáng chú ý: **đợt sau thường là bản vá cho một giả định sai của đợt trước**,
và tệp vá luôn mở đầu bằng một khối comment kể lại sự cố thật. Ví dụ
`20260814000001` mở đầu: *"ĐÂY LÀ MỘT BẢN VÁ NỐI VÀO CƠ CHẾ ĐÃ BỎ"* — bốn bảng
CSKH được thêm vào `PUBLICATION supabase_realtime` ngày 09/08, trong khi
publication ấy đã bị thay bằng LISTEN/NOTIFY từ 06/08. Nghe một thứ không phát
thì **im lặng**: không lỗi, không cảnh báo, chỉ là màn hình tự mới sau 60 giây.

---

### 9.2. BẢN ĐỒ THỰC THỂ

Gốc của mọi thứ là `clinic` (tenant). Mũi tên `──>` đọc là "khoá ngoại trỏ tới".

```
clinic  (tenant — id cố định a0000000-…-0001 = Dr4Women)
│
├── clinic_membership ──> staff          (clinic_id, staff_id, role)  UNIQUE(clinic,staff,role)
│      · staff KHÔNG có clinic_id: một bác sĩ làm ở nhiều phòng khám
│      · role đúng 11 mã: DOCTOR, CSKH, RECEPTION, MANAGEMENT, TRUONG_CA…
│
├── clinic_location ──> clinic_room ──> clinic_room_node
│
├── patient  (clinic_patient_id PK)
│   ├── patient_sdt_them        · nhiều SĐT phụ, ON DELETE CASCADE
│   ├── patient_medical_profile / pregnancy
│   └── care_episode            · UNIQUE(clinic, patient, service_type) WHERE status<>'CLOSED'
│
├── appointment  (LỊCH HẸN — dự định)
│   │   clinic_patient_id ──> patient      location_id ──> clinic_location
│   │   doctor_id ──> staff                service_type_id ──> service_type
│   │   work_session_id ──> work_session   episode_id ──> care_episode
│   │   slot_start / slot_end  CHECK (slot_end > slot_start)
│   │   status ∈ SCHEDULED, CSKH_CONFIRMED, CONFIRMED, CHECKED_IN,
│   │            COMPLETED, NO_SHOW, CANCELLED, DOCTOR_DECLINED
│   │
│   └── visit  (LƯỢT KHÁM — đã xảy ra)   appointment_id NULLABLE ─┘
│       │  status ∈ OPEN, IN_PROGRESS, INCOMPLETE, FINALIZED, AMENDED
│       ├── clinical_record / clinical_form_response / ultrasound_record
│       ├── lab_result        (visit_id, appointment_id đều nullable)
│       ├── prescription / service_log
│       ├── payment           (visit_id NOT NULL)
│       └── work_item ──> work_item_event      (kernel quy trình)
│
├── tuong_tac_cskh   · sổ CHỈ THÊM
│      clinic_patient_id ──> patient  (CASCADE)
│      appointment_id   ──> appointment (SET NULL)
│      loai · kenh · ket_qua · khach_xac_nhan · huy_luc · huy_boi_staff_id
│
├── hen_goi_lai · nhac_tai_kham · phan_hoi_khach · tep_ket_qua
├── luat_cskh        (clinic_id, loai_viec) PK — số ngày + NHÃN hiển thị
│
├── work_roster ──> roster_week          (lịch trực: đã xếp ≠ đã chốt)
└── event_log        (sổ sự kiện, chỉ thêm; MANAGEMENT mới đọc được)
```

**Ba luật `ON DELETE` lặp lại khắp lược đồ** — chúng nói lên triết lý dữ liệu:

| Kiểu | Dùng ở đâu | Vì sao |
|---|---|---|
| `ON DELETE RESTRICT` | mọi `clinic_id`, `hen_goi_lai.tao_boi_staff_id` | Không được xoá phòng khám (hay người tạo việc) khi còn dữ liệu treo bên dưới |
| `ON DELETE CASCADE` | `clinic_patient_id` của bảng con, `clinic_membership.staff_id` | Bảng con **thuộc về** hồ sơ mẹ, không có nghĩa khi đứng riêng |
| `ON DELETE SET NULL` | `tuong_tac_cskh.appointment_id`, `*_by_staff_id` | Sự việc đã xảy ra thì vẫn còn giá trị dù lịch hẹn hay nhân sự biến mất |

---

### 9.3. `appointment` ≠ `visit` — vì sao PHẢI tách

| | `appointment` | `visit` |
|---|---|---|
| Nghĩa | **Dự định**: khách sẽ đến lúc mấy giờ, gặp ai, làm dịch vụ gì | **Sự thật**: khách đã bước vào, đã được khám |
| Khoá | `id` | `visit_id` |
| Thời gian | `slot_start`, `slot_end` (dự kiến) | `checked_in_at`, `exam_completed_at`, `finalized_at` |
| Vòng đời | SCHEDULED → CONFIRMED → CHECKED_IN → COMPLETED | OPEN → IN_PROGRESS → FINALIZED |
| Có thể không có cái kia? | Có: lịch bị `CANCELLED`/`NO_SHOW` → **không sinh visit nào** | Có: `appointment_id` là **NULLABLE** — khách vãng lai đi thẳng vào |

```sql
CREATE TABLE public.visit (
    visit_id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_patient_id uuid NOT NULL,
    appointment_id uuid,            -- ← NULL được: khách vãng lai
    attending_doctor_id uuid,
    status text DEFAULT 'OPEN'::text NOT NULL,
    checked_in_at timestamp with time zone,
    finalized_at timestamp with time zone,
    CONSTRAINT visit_status_check CHECK ((status = ANY (ARRAY[
        'OPEN','IN_PROGRESS','FINALIZED','AMENDED'])))
);
```
*(`supabase/migrations/20260714000001_baseline_schema.sql`, dòng 684)*

**Vì sao không gộp làm một.** Ba lý do, cả ba đều là chuyện có thật:

1. **Quan hệ không phải 1–1.** Một lịch hẹn có thể bị huỷ (không có lượt khám
   nào), và một lượt khám có thể không có lịch hẹn (khách vãng lai). Gộp vào một
   bảng thì mỗi trường hợp là một nửa hàng rỗng.
2. **Hai vòng đời khác nhau, hai bảng luật khác nhau.** `appointment.status`
   nói về việc **đặt chỗ**; `visit.status` nói về việc **ký hồ sơ**. Trigger
   `visit_finalized_block_update` chặn mọi UPDATE khi `OLD.status='FINALIZED'`
   — hồ sơ đã ký là bất biến theo Thông tư 13. Lịch hẹn thì sửa được đến phút cuối.
3. **Sự cố đo được ngày 06/08.** `20260806000004_luot_kham_do.sql` ghi lại:

   > *"Khách đang khám thì có việc phải về. […] Cách duy nhất đang làm được là
   > HUỶ LỊCH HẸN — và khi đó hồ sơ trông như người ấy CHƯA TỪNG ĐẾN: mất dấu
   > vết họ đã lấy số, đã đo sinh hiệu, đã được chỉ định dịch vụ."*

   Đo trên máy chủ hôm ấy: 35 lượt `OPEN`/`IN_PROGRESS`, **18 lượt check-in từ
   những ngày trước** mà không màn hình nào chạm tới. Trạng thái `INCOMPLETE`
   được thêm vào như một trạng thái **KHÔNG-CUỐI**: khác `FINALIZED`/`AMENDED`
   (đã ký, bất biến), `INCOMPLETE` nghĩa là **khách còn quay lại** — bác sĩ vẫn
   ghi tiếp và vẫn ký lên `FINALIZED` được.

> Nếu chỉ có một bảng, việc "huỷ lịch" và việc "khách về giữa chừng" là cùng
> một thao tác, và bệnh án của người đã đến bị xoá theo dự định chưa xảy ra.

---

### 9.4. Hai VIEW của CSKH — việc là **hàm của dữ liệu**, không phải cột ai bấm

#### 9.4.1. Vì sao là VIEW chứ không phải bảng việc

`20260809000005_trang_thai_cskh_suy_ra.sql` mở đầu bằng đúng lý do:

> *"Dự án không có bộ hẹn giờ […]. Một bảng việc mà không có cron thì việc chỉ
> ra đời khi có người mở màn — và từ giây đó nó là BẢN SAO của sự thật, tự do
> lệch: lịch bị huỷ mà việc 'gọi nhắc hẹn' vẫn nằm đó."*

Đó đúng là bệnh bảng `cskh_action` đang mắc: 0 dòng, và hai câu `INSERT` duy
nhất ghi vào nó còn không có cột `step` lẫn `deadline_at`. View thì **không lệch
được**: xoá một cuộc gọi thì trạng thái tự lùi về đúng chỗ.

Đánh đổi được nói thẳng ra: view **không giữ được "ai nhận việc này"** — cột
"phụ trách" hiện người tương tác gần nhất.

#### 9.4.2. `luat_cskh` — luật là dữ liệu

```sql
CREATE TABLE IF NOT EXISTS public.luat_cskh (
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    loai_viec    text NOT NULL,
    bat          boolean NOT NULL DEFAULT true,
    so_ngay      integer NOT NULL DEFAULT 1 CHECK (so_ngay BETWEEN 0 AND 365),
    cua_so_ngay  integer CHECK (cua_so_ngay IS NULL OR cua_so_ngay BETWEEN 1 AND 365),
    nhan         text NOT NULL,
    PRIMARY KEY (clinic_id, loai_viec)
);
```

"Gọi xác nhận trước 7 ngày" là con số của Dr4Women. Ghim vào SQL thì mỗi lần
đổi là một lần deploy. Bảng này giữ **cả số ngày lẫn chữ hiển thị** (`nhan`), và
cờ `bat` để tắt một loại việc mà không cần sửa view. `cua_so_ngay` chỉ dùng cho
việc có **khoảng** (gọi lại sau huỷ: từ ngày 1 tới ngày 14).

#### 9.4.3. `v_viec_cskh` — MỌI việc đang mở, mỗi việc một dòng

View là `UNION ALL` của **mười nhánh**, mỗi nhánh một câu hỏi nghiệp vụ:

| `uu_tien` | `loai` | Suy từ đâu |
|---|---|---|
| 0 | `DA_CHECKIN` | `appointment.status = 'CHECKED_IN'` |
| 1 | `CHO_BAC_SI` | `lab_result` có kết quả, `requires_doctor_review`, `reviewed_at IS NULL` |
| 2 | `KQ_CHUA_GUI` | có kết quả đã duyệt **mà chưa có** dòng `TRA_KQ` sau `created_at` |
| 3 | `CHO_KQ_XN` | `lab_result.result_value IS NULL` |
| 4 | `GOI_LAI` | lần chạm gần nhất trả `CHUA_NGHE_MAY` / `KHONG_LIEN_LAC_DUOC` / `HEN_GOI_LAI` |
| 5 | `HOI_LY_DO_HUY` | lịch `CANCELLED` trong cửa sổ 1–14 ngày, chưa ai gọi hỏi |
| 6 | `HEN_GOI_LAI` | `hen_goi_lai.dong_luc IS NULL AND ngay_goi <= hôm nay` |
| 7 / 9 | `NHAC_DI_KHAM` / `MOI_TAI_KHAM` | `nhac_tai_kham.trang_thai = 'CHO_GOI'`, phân theo `luot_goi` |
| 8 | `NHAC_HEN_MAI` | lịch ngày mai chưa có dòng `NHAC_HEN` |
| 10 | `CHO_XAC_NHAN` | lịch trong N ngày tới chưa có dòng `XAC_NHAN_LICH` |

**Cách "đóng" một nhánh việc.** Không có cột `da_xong`. Việc biến mất khỏi hàng
đợi khi **sổ có một dòng đúng loại**:

```sql
SELECT a.clinic_id, a.clinic_patient_id, 'CHO_XAC_NHAN', 10,
       (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, a.id
  FROM public.appointment a
  JOIN public.luat_cskh l ON l.clinic_id = a.clinic_id
                         AND l.loai_viec = 'CHO_XAC_NHAN' AND l.bat
 CROSS JOIN hom_nay h
 WHERE a.status NOT IN ('CANCELLED','NO_SHOW','DOCTOR_DECLINED',
                        'COMPLETED','CHECKED_IN')
   AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
         BETWEEN h.d AND h.d + l.so_ngay
   AND NOT EXISTS (
         SELECT 1 FROM public.tuong_tac_cskh t
          WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH'
            AND t.huy_luc IS NULL);
```
*(`supabase/migrations/20260810000009_hoan_tac_mot_lan_cham.sql`)*

> Ghi một dòng vào sổ **là** hành động đóng việc. Không có bước thứ hai để quên.

Nhánh `CHO_XAC_NHAN` còn dạy một điều: nó suy từ **sự VẮNG MẶT của một cuộc
gọi**, KHÔNG từ `appointment.status`. Lý do ghi ngay trong file: lịch mới vào
thẳng `CONFIRMED` (`booking_service.py`), nên `status` không bao giờ nói được
"đã gọi cho khách chưa".

#### 9.4.4. `huy_luc IS NULL` — vì sao view phải lọc

Quang 10/08: *"thêm khả năng nhấn vào nút tròn của các sự kiện để hoàn tác (tất
nhiên là log không được xoá…)"*. Hai vế nghe như mâu thuẫn, và chính chỗ ấy
quyết định thiết kế.

`tuong_tac_cskh` là sổ **chỉ thêm** — một cú `DELETE` là xoá bằng chứng ai đã
chạm tới bệnh nhân lúc mấy giờ. Nhưng "ấn nhầm" là chuyện thật, và hậu quả không
nằm ở dòng sổ: nó nằm ở chỗ dòng sổ ấy **đóng một việc**. Bấm nhầm một cái thì
"gọi xác nhận lịch" biến mất khỏi hàng đợi và không ai gọi cho khách ấy nữa.

```sql
ALTER TABLE public.tuong_tac_cskh
    ADD COLUMN IF NOT EXISTS huy_luc timestamptz,
    ADD COLUMN IF NOT EXISTS huy_boi_staff_id uuid
        REFERENCES public.staff(id) ON DELETE SET NULL;

ALTER TABLE public.tuong_tac_cskh
    ADD CONSTRAINT tuong_tac_huy_du_doi
    CHECK ((huy_luc IS NULL) = (huy_boi_staff_id IS NULL));

CREATE INDEX IF NOT EXISTS idx_tuong_tac_con_hieu_luc
    ON public.tuong_tac_cskh (appointment_id, loai)
    WHERE huy_luc IS NULL;
```

Dòng **ở lại**, chỉ **thôi được tính**. Lịch sử vẫn đọc được đủ: đã bấm, rồi đã
rút lại, cả hai đều có tên người. `CHECK ((huy_luc IS NULL) = (huy_boi_staff_id
IS NULL))` là cùng một khuôn với `hen_goi_lai_dong_du_doi`: **đóng việc mà không
biết ai đóng thì không truy lại được**.

Vì sao không dùng "bút toán đảo" (thêm một dòng phủ định)? File nói thẳng: nghe
thuần khiết hơn, nhưng khi ấy **mọi câu `NOT EXISTS` phải đếm cặp ghi/huỷ** —
mười nhánh, mỗi nhánh một câu con, chỉ cần một nhánh quên là một trạng thái sai
âm thầm. Một lá cờ đọc bằng `IS NULL` thì mười nhánh nói cùng một câu.

`huy_luc IS NULL` phải có ở **năm chỗ**: CTE `cham_cuoi` + bốn câu `NOT EXISTS`
(`KQ_CHUA_GUI`, `HOI_LY_DO_HUY`, `NHAC_HEN_MAI`, `CHO_XAC_NHAN`) + biểu thức
`da_xac_nhan` của `v_trang_thai_cskh`. Bỏ sót một chỗ là một trạng thái **không
bao giờ mở lại được** sau khi hoàn tác.

#### 9.4.5. `v_trang_thai_cskh` — việc gấp nhất của mỗi khách

```sql
CREATE OR REPLACE VIEW public.v_trang_thai_cskh
WITH (security_invoker = true) AS
WITH dem AS (
    SELECT clinic_id, clinic_patient_id,
           count(*) AS so_viec_mo, bool_or(qua_han) AS co_viec_qua_han
      FROM public.v_viec_cskh GROUP BY 1, 2
),
gap_nhat AS (
    SELECT DISTINCT ON (clinic_id, clinic_patient_id) *
      FROM public.v_viec_cskh
     ORDER BY clinic_id, clinic_patient_id, qua_han DESC, uu_tien, han_xu_ly
)
SELECT v.clinic_id, v.clinic_patient_id, v.trang_thai, v.nhan,
       v.han_xu_ly, v.qua_han, d.so_viec_mo, d.co_viec_qua_han, v.appointment_id,
       EXISTS (SELECT 1 FROM public.tuong_tac_cskh t
                WHERE t.appointment_id = v.appointment_id
                  AND t.khach_xac_nhan AND t.huy_luc IS NULL) AS da_xac_nhan
  FROM gap_nhat v
  JOIN dem d USING (clinic_id, clinic_patient_id);
```

| Chi tiết | Vì sao |
|---|---|
| `qua_han DESC` **trước** `uu_tien` | Đảo hai vế này là việc trễ ba ngày nằm im sau một việc chưa tới hạn (`20260809000010_viec_qua_han_khong_bi_che.sql`) |
| `dem` đọc `v_viec_cskh` | Trước đó `so_viec_mo` được đếm bằng một CTE riêng — hai phép tính song song cho một sự thật. Nay chỉ còn một chỗ đếm |
| `security_invoker = true` | Thiếu cờ này view chạy bằng quyền **người tạo** và trả dữ liệu của mọi phòng khám — rò rỉ im lặng, không lỗi nào báo |
| `appointment_id` có thể NULL | NULL = việc **không thuộc một lượt cụ thể** (kết quả xét nghiệm gắn với `lab_result`). Màn hình phải hiểu NULL là "đúng với mọi lượt", không phải "không đúng lượt nào" |

**Vì sao phải tách `v_viec_cskh` ra khỏi `v_trang_thai_cskh`.** Quang 10/08, ca
của Cường: khách có ba lịch, một lịch hôm qua đang `CHECKED_IN`. View cũ là
`DISTINCT ON (clinic_id, clinic_patient_id)` — **một dòng cho một khách** — nên
màn hình mở lượt tái khám ngày mai lại nhận trạng thái `DA_CHECKIN` của lượt hôm
qua, và nút "Check-in cho khách" sáng lên trên một lượt khách chưa từng đến.

Cách chữa **không phải** viết lại luật ưu tiên bằng TypeScript:

> *"Luật ấy gồm mười nhánh, mỗi nhánh một câu hỏi nghiệp vụ, và số ngày lấy từ
> `luat_cskh` […]. Chép sang trình duyệt là dựng bản thứ hai của một thứ đã có,
> và bản thứ hai luôn là bản trôi đi."*

---

### 9.5. TRIGGER

#### 9.5.1. `notify_row_change()` → `pg_notify('clinicai_changes')`

**Vì sao bỏ Supabase Realtime.** Realtime đọc WAL qua một replication slot, và
tạo slot cần quyền `REPLICATION`. Đo trên Viettel IDC 06/08/2026:
`pg_create_logical_replication_slot` **bị từ chối** — không phải trục trặc cấu
hình mà là **chính sách**, và AWS RDS hay Azure cũng vậy. `NOTIFY` thì là SQL
thường, không đòi quyền nào.

```sql
CREATE OR REPLACE FUNCTION public.notify_row_change()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public' AS $$
DECLARE v_clinic uuid;
BEGIN
    v_clinic := CASE WHEN TG_OP = 'DELETE' THEN OLD.clinic_id ELSE NEW.clinic_id END;
    IF v_clinic IS NOT NULL THEN
        PERFORM pg_notify('clinicai_changes',
            json_build_object('t', TG_TABLE_NAME, 'c', v_clinic)::text);
    END IF;
    RETURN NULL;   -- AFTER trigger: giá trị trả về không được dùng
END; $$;
```
*(`supabase/migrations/20260806000001_notify_change_for_live_screens.sql`)*

| Quyết định | Vì sao |
|---|---|
| Đặt ở **trigger**, không ở tầng dịch vụ | Gọi `pg_notify` trong từng service đúng cho tới lần đầu có người thêm đường ghi mới mà quên — và cái quên đó **im lặng**: màn hình chỉ đơn giản không cập nhật nữa |
| `TG_OP = 'DELETE' THEN OLD` | Không có dòng này thì mọi lần xoá mất tin báo, và màn hình **giữ lại một hàng vừa biến mất** |
| **Tin nghèo có chủ ý** (chỉ tên bảng + `clinic_id`) | (1) `NOTIFY` có trần **8000 byte**, một hàng bệnh án có thể vượt → **hỏng cả giao dịch ghi**, biến một tính năng hiển thị thành lỗi mất bệnh án; (2) đẩy dữ liệu qua đường này là mở lối đọc **nằm ngoài mọi lớp kiểm quyền của API** |
| Gắn vào **đúng** danh sách bảng có màn vẽ live | Thừa một bảng là mỗi lần ghi lại đánh thức mọi màn hình cho thay đổi không ai đang nhìn |

Vòng `DO $$` gắn trigger có **hai cửa kiểm** trước khi `CREATE TRIGGER`: bảng
phải tồn tại, và bảng phải có cột `clinic_id` (tin báo lọc theo phòng khám).
Không đạt thì `RAISE NOTICE` rồi `CONTINUE` — bỏ qua thay vì làm đứt cả chuỗi
migration trên một nhánh triển khai cũ.

**Danh sách bảng** (16 bảng, gộp hai đợt): `appointment`, `visit`, `work_item`,
`work_item_event`, `payment`, `lab_result`, `service_log`, `prescription`,
`cskh_action`, `staff_task`, `work_roster` *(06/08)* + `tuong_tac_cskh`,
`tep_ket_qua`, `phan_hoi_khach`, `hen_goi_lai`, `slot_hold` *(14/08)*.

Ghi chú đáng giá trong `20260814000001`: `slot_hold` **cố ý không** vào
`LIVE_TABLES` của `RealtimeRefresher.tsx`, vì component ấy gọi `router.refresh()`
cho mọi tin — tám CSKH bấm lướt qua các khung giờ sẽ thành một trận mưa render
trên mọi tab đang mở. Màn đặt lịch tự nghe lấy và chỉ hỏi lại một endpoint nhẹ.

#### 9.5.2. Trigger trên `event_log` — CHỈ `INSERT`

```sql
DROP TRIGGER IF EXISTS trg_notify_event_log ON public.event_log;
CREATE TRIGGER trg_notify_event_log
    AFTER INSERT ON public.event_log
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
```
*(`supabase/migrations/20260815000003_notify_event_log_cho_relay.sql`)*

Chú ý: **không có** `OR UPDATE OR DELETE` như 16 bảng kia. File tự nhận đây là
chỗ dễ hỏng nhất nếu ai "dọn dẹp" cho giống các bảng khác:

> *"relay xử lý xong thì UPDATE `event_published = TRUE` lên chính bảng này.
> Nghe cả UPDATE là relay tự đánh thức mình sau mỗi lần gửi — một vòng lặp poll
> rỗng vô tận, mỗi tin gửi đi kèm một cú quét thừa."*

Nhịp poll 30 giây của relay **vẫn giữ**: nó là lưới an toàn cho lúc connection
`LISTEN` rớt. Notify là tối ưu độ trễ, không phải chỗ dựa duy nhất.

#### 9.5.3. Cặp trigger nuôi `patient.sdt_tim_kiem`

Khách dùng 2–3 số là chuyện thường. Trước `20260815000002_nhieu_so_dien_thoai.sql`
mỗi hồ sơ chỉ có `phone_primary` + `phone_secondary`, nên số thứ ba **không có
chỗ ghi**: người trực hoặc ghi đè số cũ (mất lịch sử liên lạc) hoặc tạo hồ sơ
mới (**tách đôi bệnh án**).

Thiết kế hai tầng: bảng con `patient_sdt_them` là nguồn sự thật; cột
`patient.sdt_tim_kiem` là **bản gộp mọi số** do trigger nuôi.

```sql
CREATE OR REPLACE FUNCTION public.tinh_sdt_tim_kiem(
    p_benh_nhan uuid, p_chinh text, p_nguoi_nha text
) RETURNS text LANGUAGE sql STABLE AS $$
    SELECT nullif(concat_ws(' ', p_chinh, p_nguoi_nha,
        (SELECT string_agg(t.so_dien_thoai, ' ' ORDER BY t.created_at)
           FROM public.patient_sdt_them t
          WHERE t.clinic_patient_id = p_benh_nhan)), '')
$$;
```

| Thành phần | Giải thích |
|---|---|
| `tinh_sdt_tim_kiem()` | **Một công thức, ba nơi gọi** (trigger `patient`, trigger bảng con, backfill) — tách thành hàm để ba nơi không bao giờ tính ba kiểu |
| `trg_patient_sdt_tim_kiem` (BEFORE INSERT OR UPDATE) | Mọi ghi vào `patient` tự làm tươi cột gộp |
| `trg_sdt_them_lam_tuoi` (AFTER trên bảng con) | Chạm hồ sơ mẹ bằng `UPDATE patient SET clinic_patient_id = clinic_patient_id` — **UPDATE rỗng** đủ để trigger BEFORE chạy, không chép công thức lần hai |
| `CHECK (so_dien_thoai ~ '^0[0-9]{9}$')` | Chuẩn hoá **ngay từ ràng buộc**, cùng dạng `normalize_vn_phone` của backend trả ra. Một số `+84 90…` lọt vào là cột tìm kiếm chứa dạng không ai gõ để tra |
| `UNIQUE (clinic_patient_id, so_dien_thoai)` — **không** unique toàn cục | Hai mẹ con dùng chung một số là hợp lệ |

**Vì sao gộp vào một cột** thay vì join sang bảng con: mọi đường tìm kiếm hiện có
là một câu `or(...ilike...)` phẳng của PostgREST trên chính bảng `patient`. Sửa
**một** cột trong câu `or()` thì "tra số nào cũng ra" đúng ở mọi màn bằng cùng
một cách; bắt từng đường join là mỗi đường một kiểu và sớm muộn lệch nhau.

---

### 9.6. RLS và tính đa phòng khám

#### 9.6.1. Trước W2: lược đồ **không có** khái niệm tenant

`20260730000003_multi_tenant_foundation.sql` mở đầu: `grep -c clinic_id` trên
baseline trả về **0**. `clinic_location` là **cơ sở/chi nhánh**, không phải
tenant. Onboard phòng khám thứ hai đồng nghĩa mọi người đọc dữ liệu của mọi người.

#### 9.6.2. Ba hàm danh tính — xương sống của mọi policy

```sql
CREATE OR REPLACE FUNCTION public.current_clinic_ids()
RETURNS SETOF uuid LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp AS $$
    SELECT m.clinic_id FROM public.clinic_membership m
    WHERE m.staff_id = public.current_staff_id() AND m.is_active
$$;
```

| Hàm | Vai trò |
|---|---|
| `current_staff_id()` | `auth.uid()` → `staff.auth_user_id` → `staff.id` |
| `current_clinic_ids()` | `staff.id` → mọi `clinic_id` có membership **đang hoạt động** |
| `current_clinic_roles(clinic)` | Chức danh của người này **tại phòng khám ấy** |
| `current_staff_department()` | Bản cũ hơn (`20260717000001`), dùng cho policy `event_log` |

`SECURITY DEFINER` là **bắt buộc**: nếu không, policy trên `clinic_membership`
phải đọc `clinic_membership` để quyết định quyền đọc `clinic_membership` — đệ
quy. `STABLE` cũng bắt buộc: nếu không planner tính lại từng hàng. Cả hai đều
read-only và **không nhận tham số**, nên không có gì để inject.

#### 9.6.3. Luật chung — một dòng, lặp trên 23 bảng

```sql
CREATE POLICY <bảng>_select_own_clinic ON public.<bảng>
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));
```

Trước W3, **26 bảng** mang `<bảng>_select_authenticated … USING (true)`: bất kỳ
ai cầm anon key cộng một JWT hợp lệ đọc được mọi dòng lâm sàng trong database.
W3 cũng đóng luôn tài khoản cổng chung của phòng khám (`CLINIC_SHARED_EMAIL`) —
tài khoản ấy **không có dòng `staff`**, nên nay đọc 0 dòng ở mọi nơi thay vì đọc tất cả.

Ba ngoại lệ đáng chú ý:

| Bảng | Luật riêng | Vì sao |
|---|---|---|
| `staff` | `id = current_staff_id() OR EXISTS(membership cùng clinic)` | `staff` **không có** `clinic_id` (bác sĩ làm nhiều nơi). Nhánh "tự đọc mình" đảm bảo người dùng luôn phân giải được dòng của chính mình — thiếu nó, một trục trặc membership là **đăng xuất cả hệ thống** |
| `event_log` | `current_staff_department() = 'MANAGEMENT'` **và** trong clinic của mình | Payload audit không được để mọi trình duyệt đã đăng nhập đọc |
| `idempotency_key`, `clinic_secret`, `mpi_merge_queue`, `staff_capability`, `pos_outbox` | **RLS bật, KHÔNG policy nào** | Chỉ `service_role` (bỏ qua RLS) chạm được — credential POS/Zalo, thân request đã phát lại, định danh bệnh nhân chờ trộn |

#### 9.6.4. Vì sao mọi truy vấn phải mang `clinic_id`

Ba lý do chồng lên nhau:

1. **Đúng đắn.** Policy chỉ trả dòng có `clinic_id ∈ current_clinic_ids()`. Câu
   truy vấn không lọc thì Postgres vẫn lọc — nhưng sau khi đã quét.
2. **Tốc độ.** Bất biến của `multi_tenant_foundation`: **mọi bảng tenant phải có
   một chỉ mục DẪN ĐẦU bằng `clinic_id`**. Chỉ mục `(clinic_id, so_dien_thoai)`
   dùng được cho câu lọc phòng khám + tra số; chỉ mục `(so_dien_thoai, clinic_id)`
   thì không dùng được cho câu chỉ lọc phòng khám.
3. **Khoá tự nhiên.** Mọi mã người-đọc-được đã đổi thành unique **theo tenant**:
   `UNIQUE (clinic_id, patient_code)`, `UNIQUE (clinic_id, code)` cho
   `service_type` / `clinic_location` / `booking_channel`… Cùng CCCD ở hai phòng
   khám = **hai hồ sơ**, và điều đó đúng: mỗi phòng khám sở hữu bệnh án của mình.

**Default chuyển tiếp** — một chi tiết tinh tế:

```sql
CREATE OR REPLACE FUNCTION public.default_clinic_id()
RETURNS uuid LANGUAGE sql STABLE
SET search_path = public, pg_temp AS $$
    SELECT c.id FROM public.clinic c
    WHERE (SELECT count(*) FROM public.clinic) = 1
$$;
```

Hàm trả về phòng khám duy nhất **khi và chỉ khi** có đúng một, và `NULL` ngay
khi phòng khám thứ hai xuất hiện. Vì `clinic_id` là `NOT NULL`, giây phút có
tenant thứ hai thì mọi câu ghi thiếu `clinic_id` **hỏng thành lỗi rõ ràng** thay
vì gán nhầm âm thầm.

> Không có `INSERT`/`UPDATE`/`DELETE` policy ở **bất kỳ đâu** (ADR-0012). Backend
> sở hữu mọi đường ghi, nên frontend không phải là thứ đáng tin.

---

### 9.7. BẤT BIẾN mà CI đếm

Job `database` trong `.github/workflows/ci.yml` dựng một `postgres:17` dùng một
lần, áp toàn bộ chuỗi migration, rồi chạy 22 tệp khẳng định. Đây là các con số
bị **ghim** — chúng bắt **cả hai chiều**: bảng mới quên `clinic_id`, và bảng cũ
đánh mất nó.

| Bất biến | Giá trị | Nguồn |
|---|---|---|
| Số bảng có `clinic_id` (trừ `clinic_membership`) | **69** | `tests/multi_tenant_foundation.sql` |
| `clinic_id` phải `NOT NULL` ở mọi bảng | 0 ngoại lệ | nt |
| Mọi `clinic_id` phải có FK tới `clinic` | 0 ngoại lệ | nt |
| `clinic_id` phải là **cột dẫn đầu** của ít nhất một index | 0 ngoại lệ | nt |
| Bảng dùng chung phải **không** có `clinic_id` | 7 bảng: `province`, `ward`, `staff`, `staff_capability`, `idempotency_key`, `schema_migrations`, `clinic` | nt |
| Ràng buộc unique toàn cục cũ đã bị gỡ | 5 tên (`patient_patient_code_key`…) | nt |
| Ràng buộc unique **theo tenant** | 5 | nt |
| Unique **index** theo tenant | 4 | nt |
| `current_staff_id` / `current_clinic_ids` phải `STABLE SECURITY DEFINER` | bắt buộc | nt |
| Policy `%_select_own_clinic` | **45** | `tests/tenant_scoped_rls.sql` |
| Policy có `cmd <> 'SELECT'` | **0** | nt |
| Bảng chỉ-backend (RLS bật, 0 policy) | 5 | nt |
| Còn `USING (true)` | **0** | nt |

Con số 69 và 45 **di chuyển có chủ ý**, và mỗi lần di chuyển được ghi lại thành
một dòng comment trong chính tệp test. Đọc khối comment ấy là đọc lịch sử tính
năng: `64 → 66` là `luat_cskh` + `hen_goi_lai`; `68 → 69` là `patient_sdt_them`.

Hai bước kiểm nữa của job `database`:

```yaml
- name: Migrations and seed must be plain SQL
  run: |
    if grep -nE '^\\(un)?restrict|FROM stdin' \
         supabase/migrations/*.sql supabase/seed.sql; then
      echo "::error::psql-only syntax — the Supabase CLI cannot execute it"
      exit 1
    fi
```

Meta-command của `psql` (`\restrict`, `COPY … FROM stdin`) là **cú pháp phía
client**: `psql` chạy được, Supabase CLI thì không — nên một tệp sinh từ
`pg_dump` có thể **qua mọi bài test ở đây mà vẫn làm `db push` chết ở dòng 1**.

Bước còn lại áp **lần thứ hai** mọi migration từ `20260730000000` trở đi.

---

### 9.8. Quy tắc migration

| Quy tắc | Chi tiết |
|---|---|
| **Chỉ THÊM, không sửa ngược** | Migration đã lên production **không được sửa lại**. `README.md`: *"Earlier migrations are already in production and are not edited retroactively."* Sửa một tệp cũ nghĩa là database đã áp và database mới dựng không còn giống nhau |
| **Idempotent từ `20260730` trở đi** | `db push` có retry và diễn tập restore sẽ chạy lại. CI khẳng định bằng cách **áp mỗi tệp hai lượt**. Nên `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `DROP POLICY IF EXISTS` trước `CREATE POLICY`, và bọc `CREATE POLICY` trong `DO $$ … IF NOT EXISTS (SELECT 1 FROM pg_policies …)` |
| **`DROP VIEW` trước, không `CREATE OR REPLACE`** khi bỏ cột | `20260809000005` phải `DROP VIEW IF EXISTS public.v_trang_thai_cskh;` vì ở lượt hai nó gặp một view **đã có nhiều cột hơn** (`20260809000010` chèn `so_viec_mo`/`co_viec_qua_han` vào giữa) và `CREATE OR REPLACE VIEW` không bỏ được cột: `cannot drop columns from view` |
| **DB đi trước code** | Áp mọi migration đang chờ **trước** khi deploy bản ứng dụng tương ứng. UI *fail closed* khi hàm database vắng mặt |
| **PostgREST phải reload sau khi đổi lược đồ** | PostgREST giữ lược đồ **trong bộ nhớ**. Triệu chứng khi quên: `Could not find a relationship between 'appointment' and 'patient'` — số đếm vẫn ra nên trông như lỗi dữ liệu. Chữa: `NOTIFY pgrst, 'reload schema'`. Đã có trong `scripts/dung-staging.sh` và `deploy-backend.sh`; **prod phải nhớ chạy tay** sau mỗi migration đổi bảng/khoá ngoại |
| **Migration ≠ deploy** | Đổi lược đồ là một `db push` được review riêng, không chạy lẫn trong script deploy |
| **Test phải tự dọn** | Mọi tệp trong `supabase/tests/` mở `BEGIN` và đóng `ROLLBACK`; fixture (`auth.users`, `clinic` thứ hai, hai `staff`) đều là transaction-local |

Cách thêm một thay đổi:

```bash
supabase migration new <mo_ta_thay_doi>   # tạo tệp rỗng có timestamp
# sửa SQL, commit, rồi:
supabase db push
psql "$DB" -c "NOTIFY pgrst, 'reload schema'"   # nếu đổi bảng/khoá ngoại
```

---

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

1. **View thiếu `security_invoker = true` là rò rỉ im lặng.** View chạy bằng
   quyền **người tạo** và trả dữ liệu của **mọi phòng khám**. Không lỗi nào báo.
   Đây là lý do `patient_summary` phải có riêng một migration
   (`20260730000015_patient_summary_security_invoker.sql`).

2. **`RLS ENABLE` mà không có policy nào = bảng rỗng, không phải bảng mở.**
   `20260730000001_care_episode_select_policy.sql` và `…000002` tồn tại chỉ vì
   `/episodes` trả về rỗng: RLS bật, **zero policy**. Cùng lớp lỗi ấy lặp lại
   trên các bảng tra cứu. Nhưng đúng tính chất ấy lại được **dùng có chủ ý** cho
   `clinic_secret` và bốn bảng chỉ-backend khác.

3. **Nghe một kênh không ai phát thì im lặng.** Bốn bảng CSKH nằm trong
   `PUBLICATION supabase_realtime` (cơ chế đã bỏ) suốt 5 ngày, `RealtimeRefresher`
   vẫn nghe đủ, và không ai thấy lỗi — chỉ là màn hình tự mới sau 60 giây, và hai
   CSKH ngồi cạnh nhau gọi cho cùng một khách hai lần trong một buổi.

4. **Nghe cả `UPDATE` trên `event_log` là vòng lặp vô tận.** Relay UPDATE
   `event_published = TRUE` lên chính bảng nó nghe. Đừng "dọn dẹp cho giống các
   bảng khác".

5. **Gửi dữ liệu hàng qua `pg_notify` làm HỎNG GIAO DỊCH GHI.** Trần 8000 byte;
   một hàng bệnh án có thể vượt. Một tính năng hiển thị biến thành lỗi mất bệnh án.

6. **Bỏ sót MỘT chỗ `huy_luc IS NULL`** là một trạng thái không bao giờ mở lại
   được sau khi hoàn tác — hỏng trong im lặng, đúng loại lỗi mà migration ấy sinh
   ra để chữa.

7. **`DISTINCT ON (clinic_id, clinic_patient_id)` gộp mọi lượt của một khách.**
   Màn hình mở lượt ngày mai lại nhận trạng thái của lượt hôm qua. Cột
   `appointment_id` đã nói rõ việc thuộc lịch nào từ đầu — chỉ là bị `DISTINCT ON`
   ném đi trước khi tới màn hình.

8. **`appointment_id IS NULL` trong `v_viec_cskh` nghĩa là "đúng với mọi lượt"**,
   không phải "không đúng lượt nào". Hiểu ngược là giấu mất việc trả kết quả
   xét nghiệm.

9. **`auth.uid()` bản rút gọn trong `bootstrap_plain_postgres.sql`** chỉ đọc
   `request.jwt.claim.sub`, còn PostgREST v12 chỉ đặt `request.jwt.claims`.
   Staging thừa hưởng bản rút gọn → **mọi lượt đọc trả `[]` cho MỌI tài khoản**,
   không lỗi, không cảnh báo (`docs/DANG-LAM.md`). Cùng họ với nó: quên
   `NOTIFY pgrst, 'reload schema'` → `Could not find a relationship between…`,
   và `all healthy ✓` **không** có nghĩa là lược đồ đã vào (`/health` không chạm
   bảng của tính năng).

10. **Seed bằng tên người là seed 0 dòng.** `20260805000006` từng seed theo
    `full_name = 'TS.BS. Phan Chí Thành'` và khớp **0 dòng ở mọi nơi**. Bản sau
    gieo `luat_cskh` bằng `CROSS JOIN` với **mọi** `clinic` đang có.

11. **`CREATE OR REPLACE VIEW` không bỏ được cột.** Ở lượt áp thứ hai của CI,
    một migration cũ gặp view đã có nhiều cột hơn và chết với `cannot drop columns
    from view`. Dùng `DROP VIEW IF EXISTS` rồi `CREATE`, và **cấp lại `GRANT`**.


---

## PHẦN 10. FRONTEND — NỀN TẢNG, PHIÊN ĐĂNG NHẬP, TẦNG BFF

Phần này giải thích tầng nền của `src/dashboard`: các tiện ích trong `lib/`, cổng
kiểm phiên `proxy.ts`, đường đăng nhập, và 64 route handler đóng vai trò BFF
(Backend-For-Frontend) chuyển tiếp xuống FastAPI.

---

### 10.1. BA TẦNG — VÀ VÌ SAO TẦNG GIỮA KHÔNG THỪA

```
trình duyệt  ──fetch("/api/...")──▶  route handler Next (BFF)  ──fetch(CLINIC_API_URL)──▶  FastAPI
   cookie phiên                         cookie → access token                 Bearer + X-API-Key
```

Trình duyệt **không bao giờ** gọi thẳng FastAPI. Ba lý do, mỗi lý do là một thứ
không thể làm ở phía client:

1. **Khoá dùng chung không được lộ.** `BACKEND_API_KEY` là bí mật server→server.
   Nếu trình duyệt tự gắn `X-API-Key` thì nó phải có khoá trong bundle, tức là
   ai mở DevTools cũng lấy được.
2. **Token nằm trong cookie `httpOnly`.** JavaScript phía trình duyệt không đọc
   được cookie phiên (đó là cái giữ cho XSS không cướp được phiên). Chỉ máy chủ
   mới đổi cookie → access token → header `Authorization: Bearer …`.
3. **Địa chỉ mạng của FastAPI là địa chỉ nội bộ container.** `CLINIC_API_URL`
   trỏ vào mạng Docker; trình duyệt không phân giải nổi tên đó.

> Tầng giữa không phải để "thêm logic". Nó tồn tại để **cầm bí mật** và **dịch
> cookie thành header**. Nghiệp vụ vẫn nằm trọn ở FastAPI — route Next chỉ kiểm
> hình dạng đầu vào rồi chuyển tiếp.

Có ba lối đi ra ngoài Next, tất cả nằm trong `lib/backend-proxy.ts`:

| Hàm | Dùng ở đâu | Trả về |
|---|---|---|
| `proxyJsonToBackend(method, path, body, idempotencyKey?)` | route handler (`app/api/**/route.ts`) | `NextResponse` — **giữ nguyên** mã trạng thái + câu lỗi backend |
| `getCallerAuthHeaders()` | nơi cần tự `fetch` (tải tệp, dòng sự kiện) | `Record<string,string>` hoặc `null` |
| `fetchFromBackend<T>(path)` | server component muốn **dữ liệu** | `T` hoặc `null` (nuốt mọi lỗi) |

---

### 10.2. `lib/backend-proxy.ts` — trạm chuyển tiếp

| Hàm | Giải thích |
|---|---|
| `API_BASE` (hằng, `:17`) | `CLINIC_API_URL` đã cắt dấu `/` cuối. Rỗng = **triển khai hỏng**, không phải "chế độ chạy không backend" |
| `refreshQuietly(supabase)` `:41` | Gọi `auth.getUser()` để làm mới token, **nuốt riêng lỗi xác thực**, ném tiếp mọi lỗi khác |
| `proxyJsonToBackend(...)` `:57` | Chuyển tiếp JSON, gắn Bearer + `X-API-Key` (+ `Idempotency-Key` nếu có), phản chiếu nguyên mã trạng thái |
| `getCallerAuthHeaders()` `:165` | Chỉ dựng header xác thực của **chính người đang gọi**; `null` khi chưa đăng nhập |
| `fetchFromBackend<T>(path)` `:194` | GET phía máy chủ, trả `T | null`. Dùng cho thông tin phụ trợ — mất thì trang vẫn dựng |

#### Vì sao KHÔNG được nuốt lỗi thành 503

`lib/backend-proxy.ts:58-66` ghi lại nguyên sự cố:

```ts
// `fetchFromBackend` tiện cho server component vì nó trả `T | null`. Nhưng
// `null` XOÁ MẤT mã trạng thái và câu lỗi: route `/api/roster?staff_id=` gọi
// nó, thấy null, rồi trả 503 "Không đọc được phạm vi vị trí" — trong khi
// backend đã trả 404 kèm câu "Không tìm thấy nhân viên này".
```

- `fetchFromBackend` **thu mọi hỏng hóc về một giá trị**: hết phiên, 404, 500,
  đứt mạng đều ra `null`. Chỗ gọi chỉ còn một lựa chọn: bịa ra một câu lỗi.
- Câu bịa ấy là **503** — nghĩa là "máy chủ không phục vụ được". Nhưng máy chủ
  đang chạy tốt, chỉ là `staff_id` không tồn tại. Người dùng đọc thành "hệ thống
  hỏng" và đi báo kỹ thuật; log ghi 503 giữa lúc mọi thứ bình thường, nên khi có
  sự cố thật thì dấu vết ấy **dẫn sai**.
- Vì thế `"GET"` được đưa vào danh sách method của `proxyJsonToBackend`, dù
  nghe có vẻ thừa: route đọc dữ liệu nay chuyển tiếp nguyên văn 404 + câu tiếng
  Việt của backend.

Phần phản chiếu lỗi (`:138-148`):

```ts
if (!res.ok && payload && typeof payload === "object" && "message" in payload) {
  const msg = (payload as { message?: string }).message;
  return NextResponse.json({ error: msg ?? "Lỗi xử lý" }, { status: res.status });
}
return NextResponse.json(payload, { status: res.status });
```

- FastAPI trả lỗi nghiệp vụ dạng `{ error: "CONFLICT_ERROR", message: "Khung giờ
  đã đầy…" }`. Ở đó `error` là **mã cho máy**, `message` mới là câu cho người.
- Route dịch lại thành hình dạng `{ error: <câu tiếng Việt> }` mà giao diện chờ
  — nhưng **`res.status` giữ nguyên**. 409 vẫn là 409, 403 vẫn là 403.
- Thân không phải JSON (backend chết giữa chừng, proxy chèn HTML) thì
  `payload = { error: text }` — vẫn còn chữ để đọc, không mất im lặng.

Ba mã trạng thái do **chính route này** sinh ra, tất cả đều nói rõ nguyên nhân:

| Mã | Khi nào | Câu |
|---|---|---|
| 503 | `CLINIC_API_URL` chưa cấu hình | "CLINIC_API_URL chưa được cấu hình trên server." |
| 401 | không lấy được access token | "Chưa đăng nhập" |
| 502 | `fetch` ném (DNS, container chết) | "Không kết nối được máy chủ xử lý" |

#### `Idempotency-Key` — tham số thứ tư, tuỳ chọn, đặt cuối

Ghi chú `:70-81` là một bài học thiết kế API nội bộ:

- Backend **đã có sẵn** cơ chế chống gửi hai lần (`api/idempotency.py`: giữ chỗ
  khoá, phát lại phản hồi đã lưu, TTL 24h) và booking router **đã gọi**
  `idem.acquire()`. Nhưng header là *tuỳ chọn*, và tầng proxy chưa bao giờ gửi.
- Kết quả: chốt an toàn nằm đó **không chạy ngày nào**. Ngày 04/08 một bệnh nhân
  có ba lịch cùng khung 17:15, tạo cách nhau 10 và 5 giây.
- Vì sao đặt **cuối** và **tuỳ chọn**: 40 lời gọi trên 30 file đang dùng hàm
  này. Đổi chữ ký thành bắt buộc là sửa 30 file cho một tính năng mà 29 chỗ
  không cần.
- Nơi bơm khoá vào: `app/api/appointments/route.ts:257` đọc header client gửi
  lên, cắt 200 ký tự, rồi truyền xuống.

#### `refreshQuietly` — vì sao nuốt lỗi ở đây là ĐÚNG

```ts
async function refreshQuietly(supabase): Promise<void> {
  try {
    await supabase.auth.getUser();
  } catch (err) {
    if ((err as { __isAuthError?: boolean } | null)?.__isAuthError) return;
    throw err;
  }
}
```

Bốn điều cần hiểu, theo đúng thứ tự trong khối chú thích `:19-40`:

1. **`getSession()` không làm mới token.** Nó chỉ đọc cookie. Token Supabase
   sống một tiếng, nên sau một tiếng nó trả `null` dù người dùng vẫn đăng nhập
   hợp lệ.
2. **`getUser()` thì có** — nó đổi refresh token lấy access token mới. Nên thứ
   tự đúng luôn là `getUser()` **rồi mới** `getSession()`.
3. **Supabase XOAY refresh token**: dùng một lần là hỏng. Trên một lần bấm "Đặt
   lịch hẹn" có ít nhất hai chỗ cùng đổi — `proxy.ts` chạy cho mọi request, rồi
   `router.refresh()` kéo server component render lại. Chỗ về sau cầm đúng token
   vừa bị xoay và nhận `AuthApiError: refresh_token_not_found`.
4. **Ném lỗi đó = màn đen.** Server component ném thì Next dựng trang lỗi kèm
   nút thử lại — người dùng thấy nó **sau khi lịch đã lưu thành công**, tưởng
   hỏng, bấm lại, và chỉ có khoá idempotency chặn được lịch thứ hai.

> Nuốt lỗi ở đây không phải giấu bệnh: mục đích **duy nhất** của lời gọi này là
> làm mới token *nếu làm được*. Không làm được thì `getSession()` ngay dưới vẫn
> đọc cookie mà `proxy.ts` vừa đặt. Phiên hỏng thật thì `token` ra `null`, và
> các chỗ gọi đã xử lý sẵn (401 / `null`) — tức là đá về `/login`, chứ không
> phải một trang lỗi không nói gì. **Chỉ nuốt lỗi xác thực**; lỗi mạng/DNS vẫn
> ném để còn thấy mà sửa.

`getCallerAuthHeaders()` `:151-163` ra đời vì **bảy chỗ đã chép lại đoạn này, và
cả bảy đều chép thiếu** — họ gọi thẳng `getSession()`. Hậu quả: mỗi tiếng một
lần, ở đúng bảy màn, người dùng thấy "Chưa đăng nhập" trong khi mọi trang khác
chạy bình thường.

---

### 10.3. Phiên đăng nhập — cookie, tên cookie, và bẫy RFC 6265 §8.5

#### `lib/supabase-cookie.ts`

| Xuất | Giải thích |
|---|---|
| `hauToTheoCong(url)` `:47` | Suy hậu tố phân biệt môi trường từ **CỔNG** trong URL. Cổng mặc định (rỗng/80/443) → `""`. URL hỏng → `""` |
| `SUPABASE_COOKIE_NAME` `:67` | `"clinicai-auth" + hauToTheoCong(process.env.NEXT_PUBLIC_SUPABASE_URL)` |

**Bẫy thứ nhất — để `@supabase/ssr` tự đặt tên là hỏng.** Mặc định nó suy tên
cookie ra từ hostname của URL Supabase. Mà hai phía dùng hai URL **bắt buộc phải
khác nhau**:

```
máy chủ     SUPABASE_URL              http://clinicai_supabase_gateway:8000
trình duyệt NEXT_PUBLIC_SUPABASE_URL  http://222.255.215.219
```

Để mặc định thì server action đăng nhập ghi cookie
`sb-clinicai_supabase_gateway-auth-token`, còn proxy và trình duyệt đi tìm
`sb-222-255-215-219-auth-token`. Đăng nhập báo **thành công**, rồi bị đá thẳng về
`/login` — **không thông báo lỗi nào**, vì không bên nào coi đó là lỗi.

**Bẫy thứ hai — COOKIE KHÔNG PHÂN BIỆT CỔNG.** Đây là chỗ hầu như ai cũng đoán
sai, và nó là quy định của chính chuẩn cookie (RFC 6265 §8.5):

- Với **mọi thứ khác** — CORS, `localStorage`, `postMessage`, Same-Origin Policy
  — `http://IP:80` và `http://IP:8080` là **hai origin khác nhau**.
- Với **cookie thì không**: định danh cookie gồm `(domain, path, name)`. **Cổng
  không nằm trong đó.** Hai môi trường trên cùng một IP dùng **chung một hũ
  cookie**.

Hai môi trường của dự án nằm đúng như thế:

```
prod     http://222.255.215.219          (cổng 80)
staging  http://222.255.215.219:8080
```

Nên nếu ghim cứng **một** tên cookie:

1. Đăng nhập staging ⇒ **ghi đè** cookie phiên của prod (cùng tên, cùng domain).
2. Tệ hơn: hai môi trường có **hai máy chủ xác thực riêng với hai khoá ký khác
   nhau**. Tab prod nay cầm token do staging ký ⇒ bị từ chối.
3. Người dùng thấy mình **vừa bị đăng xuất khỏi prod** mà không hiểu vì sao —
   chỉ vì mở thêm một tab. Nguyên văn báo cáo của Tuyền (14/08/2026): *"chưa có
   tên miền nên nếu mở 2 tab thì nó bị trùng"*.

Cách chữa: tách bằng **tên cookie**, và cổng là thứ duy nhất phân biệt được hai
môi trường ở đây.

```ts
export function hauToTheoCong(url: string | undefined): string {
  if (!url) return "";
  let cong = "";
  try { cong = new URL(url).port; } catch { return ""; }
  if (!cong || cong === "80" || cong === "443") return "";
  return `-${cong}`;
}
```

- **Prod giữ nguyên tên cũ, có chủ ý**: đổi tên cookie là đăng xuất tất cả mọi
  người. Prod không có cổng trong URL nên rơi vào nhánh `return ""`, tên ra đúng
  bằng chuỗi lịch sử `clinicai-auth`. Chỉ staging đổi thành `clinicai-auth-8080`
  — và ở staging thì đăng xuất một lần là cái giá đúng phải trả.
- **URL hỏng cũng trả `""`**: thà hai môi trường trùng nhau như cũ, còn hơn sinh
  ra một tên mà phía kia không đoán được (quay lại bẫy thứ nhất).
- Có tên miền riêng thì hết trùng, vì **khác host = khác hũ**. Hàm này là giải
  pháp cho giai đoạn chưa có tên miền.

**Bẫy thứ ba — phải viết nguyên văn `process.env.NEXT_PUBLIC_SUPABASE_URL`.**
Next chỉ thay giá trị vào bundle trình duyệt khi thấy đúng dạng truy cập thuộc
tính này. Gán qua biến trung gian thì phía trình duyệt nhận `undefined`, tên
cookie hai bên lệch nhau, và ta quay về đúng lỗi "đăng nhập xong bị đá về
/login". Giá trị phải có ở **cả hai nơi**: build arg (nung vào bundle) và
`env_file` lúc chạy (cho phía máy chủ).

#### `lib/supabase-server.ts` / `supabase-browser.ts` / `supabase-service.ts`

| Hàm | Giải thích |
|---|---|
| `getSupabaseServer()` (server) `:21` | Client ANON + cookie của request. `cookieOptions: { name: SUPABASE_COOKIE_NAME }`. `setAll()` bọc `try/catch` vì server component **không ghi được** cookie — đường ghi là `proxy.ts` |
| `getSupabaseBrowser()` (browser) | Client ANON cho client component, **cùng tên cookie**. Tuyệt đối không đưa `service_role` vào đây |
| `getSupabaseService()` | Client `service_role`, **CHỈ server**, bỏ qua RLS. Trả `null` nếu chưa cấu hình khoá |
| `hasServiceRoleKey()` | Trả yes/no để trang cảnh báo mà **không phải tự đọc biến** — ADR-0012 đếm mọi file nhắc tên khoá |
| `SERVICE_ROLE_ENV` | Tên biến môi trường, để câu thông báo cho người vận hành không phải gõ tay |

Điểm then chốt của `SERVER_SUPABASE_URL` (`supabase-server.ts:18-19`): **một
biến không phục vụ được cả hai vị trí mạng.** Trong container, `127.0.0.1` là
chính container đó nên đăng nhập chết với `ECONNREFUSED`; còn
`host.docker.internal` thì trình duyệt không phân giải nổi. Sửa một đầu là hỏng
đầu kia — đã xảy ra đúng như vậy. Nên `SUPABASE_URL` (container tới được) đứng
trước, `NEXT_PUBLIC_SUPABASE_URL` là dự phòng khi chạy ngoài container.

#### `proxy.ts` — cổng kiểm phiên (Next 16 đổi tên từ `middleware`)

| Thành phần | Giải thích |
|---|---|
| `PUBLIC_PATHS` `:10` | `/login`, `/auth`, `/forgot-password`, `/reset-password`. Thêm `/design-system` chỉ khi `NODE_ENV === "development"` |
| `proxy(request)` `:17` | Làm mới cookie phiên cho **mọi** request; chặn trang HTML khi chưa đủ điều kiện |
| `config.matcher` `:96` | Bỏ qua `_next/static`, `_next/image`, favicon, ảnh. Còn lại đi hết qua đây |

Trình tự trong `proxy()`:

1. Dựng client Supabase với **`SUPABASE_URL` trước** `:32-34`. Đây là chỗ đã
   cắn: proxy chạy *trong* container và gọi Supabase cho **mọi** request. Prod
   sống sót vì địa chỉ công cộng của nó ở cổng 80 và cổng 80 đi vòng được;
   staging ở cổng 8080 thì **không** — đo 07/08/2026, từ trong container gọi
   `IP:80` OK còn `IP:8080` hết giờ chờ. Hậu quả: mọi request trên staging không
   kiểm được phiên → đá về `/login` → không ai đăng nhập được, mà trang đăng
   nhập vẫn hiện bình thường nên **trông như gõ sai mật khẩu**.
2. `setAll()` ở đây **ghi thật** vào `response.cookies` — đây là đường ghi mà
   `supabase-server.ts` không có.
3. `pathname.startsWith("/api")` → **trả về ngay**, chỉ làm mới cookie. Route API
   tự gác quyền của mình và không bao giờ được chuyển hướng sang trang HTML
   (một `fetch` nhận về HTML `/login` là một lỗi parse khó hiểu).
4. Trang công khai đi thẳng — chặn ở đây thì người chưa đăng nhập bị đá vòng
   tròn về chính nó.
5. **Cổng duy nhất, hai vế** `:77-91`: phải có phiên, **và** phiên ấy phải gắn
   với một dòng `staff` đang hoạt động.

```ts
const { data: staff } = await supabase
  .from("staff").select("id")
  .eq("auth_user_id", user.id).eq("is_active", true).maybeSingle();
if (!staff) return redirectTo("/login");
```

Trước đây truy vấn này chạy rồi **vứt kết quả đi**, vì cổng phòng khám dùng
chung mới là thứ chặn ở vòng ngoài. Bỏ cổng ấy (05/08/2026) thì đây là chốt duy
nhất còn lại: một tài khoản Supabase không có dòng `staff` — tài khoản dùng
chung cũ, hay một tài khoản tự đăng ký — nay dừng ở `/login` thay vì đi tiếp vào
giao diện rồi mới rỗng dữ liệu ở từng màn.

#### `app/(auth)/login/actions.ts`

| Hàm | Giải thích |
|---|---|
| `loginStaff(prev, formData)` `:18` | Server action: tên trần → email → `signInWithPassword` → kiểm `staff` → kiểm **đúng một** `clinic_membership` → đặt cookie tương thích → `redirect(roleLanding(role))` |
| `logout()` `:87` | `signOut()` + xoá cả hai cookie tương thích + về `/login` |

Bốn cửa ải, và **mỗi lần trượt đều `signOut()` trước khi trả lỗi** — không để
lại một phiên nửa vời:

| Điều kiện | Câu lỗi |
|---|---|
| Sai tài khoản/mật khẩu | "Tên đăng nhập hoặc mật khẩu không đúng." |
| Không có `staff` gắn `auth_user_id` (`resolveLinkedStaffAuthority`) | "Tài khoản chưa gắn với nhân viên. Liên hệ quản lý." |
| Không có **đúng một** membership đang hoạt động (`resolveSingleActiveMembership`) | "Tài khoản phải có đúng một phòng khám đang hoạt động. Liên hệ quản lý." |
| `membership.role` không thuộc `ClinicRole` | "Vai trò nhân viên không hợp lệ. Liên hệ quản lý." |

`logout()` xoá cả `ROLE_COOKIE` và `STAFF_COOKIE`: quầy lễ tân dùng chung máy,
người sau ngồi vào phải đăng nhập lại từ đầu chứ không thừa hưởng vai người
trước.

#### `lib/identity-authority.ts` — luật thuần, không chạm mạng

| Hàm | Giải thích |
|---|---|
| `resolveLinkedStaffAuthority(userId, staff)` `:20` | Chỉ chấp nhận `staff` khi nó **đang hoạt động** và `auth_user_id` **khớp đúng** user đã xác thực. Một `staff_id` gửi lên từ form, hay một cookie vai, **không bao giờ là thẩm quyền** |
| `resolveSingleActiveMembership(memberships)` `:52` | Trả membership khi và chỉ khi có **đúng một** cái đang hoạt động; mập mờ thì từ chối |
| `resolveSingleManagementClinic(memberships)` `:40` | Như trên, cộng thêm điều kiện `role === "MANAGEMENT"` — dùng cho thao tác Auth-admin |

Vì sao "đúng một" chứ không phải "lấy cái đầu tiên": dashboard **chưa có bộ chọn
phòng khám đang làm việc**. Tự chọn hộ một cái trong hai là ghi dữ liệu vào sai
cơ sở mà không ai được hỏi.

#### `lib/clinic-session.ts` — đọc danh tính phía máy chủ

| Hàm | Giải thích |
|---|---|
| `ROLE_COOKIE`, `STAFF_COOKIE` | Cookie **tương thích ngược**. Được ghi lúc đăng nhập nhưng **không bao giờ là thẩm quyền** |
| `getClinicRole()` `:18` | `getCurrentStaff()` → `departmentToRole(staff.clinic_role)` |
| `requireNavAccess(href)` `:26` | Gác **một trang** theo href. Không có quyền → `redirect("/home")` |
| `requireClinicRole()` `:36` | Gác trang **ngoài** nhóm `(dashboard)` (vd `/print/*`) nơi layout không chạy: phải có phiên Supabase thật **và** vai hợp lệ |
| `requireClinicalRole()` `:48` | Như trên + `canReadClinical` — cho màn hiện **bệnh án**, không chỉ PII hành chính |
| `getClinicStaffId()` `:55` | `staff.id` của người đang đăng nhập |
| `getClinicId()` `:65` | Tenant hiện tại — **chỉ là gợi ý lọc** cho realtime, không cấp quyền gì |
| `getActiveStaff()` `:77` | Bốn trường hiển thị: `id`, `full_name`, `short_name`, `primary_department` |

`requireNavAccess` sinh ra vì trước đây các route **chỉ ẩn ở sidebar** — gõ
thẳng URL vẫn vào và lộ PII/kết quả lab. Nó tra **chính xác href**, không so
tiền tố (xem cảnh báo trong `roles.ts:315-317`).

#### `lib/current-staff.ts` — "tôi là ai" chỉ có MỘT câu trả lời

| Hàm | Giải thích |
|---|---|
| `getCurrentStaff()` `:71` | `cache()` của React, gọi `GET /api/v1/me`, ánh xạ sang `CurrentStaff` |

Bản trước tự truy vấn Supabase: đọc `staff` theo `auth_user_id`, nhúng
`clinic_membership`, lấy vai từ đó — **đúng bằng luật của `get_current_identity`
bên FastAPI, viết hai lần bằng hai ngôn ngữ**. Hai bản ấy đã lệch đúng ở chỗ
quan trọng nhất: gặp mã vai lạ thì backend rơi về CSKH (quyền thấp nhất nhưng
vẫn là một phiên làm việc được), còn bản TypeScript trả `null` — người dùng bị
đá về `/login` mà không hiểu vì sao. Cùng một dòng dữ liệu, hai câu trả lời.

> **Không có đường lùi về Supabase, có chủ ý.** Một đường lùi chính là bản sao
> thứ hai mọc lại — và nó vô ích: mọi route nghiệp vụ đã proxy thẳng xuống
> FastAPI không điều kiện, nên khi api chết thì mọi nút bấm đã hỏng rồi. Giữ
> được danh tính trên một ứng dụng không bấm được gì chỉ khiến hỏng hóc **trông
> giống bình thường**.

Ghi chú `:56-68` còn lưu một xác chết đáng nhớ: ba helper `isDoctorRole`,
`isAdminRole`, `roleLanding` từng tồn tại **cả ở đây lẫn ở `lib/roles.ts` với
thân hàm KHÁC NHAU** — bản ở đây loại TKYK, bản kia gồm TKYK; `roleLanding` một
bên đưa bác sĩ tới `/appointments?scope=me`, bên kia tới `/tasks`. Hai hàm cùng
tên, câu trả lời khác nhau, phân biệt **chỉ bằng đường import bạn tình cờ gõ**.
TypeScript không bắt được — nó kiểm kiểu cả hai đều hoàn hảo.

---

### 10.4. Tên đăng nhập trần — `lib/ten-dang-nhap.ts`

| Xuất | Giải thích |
|---|---|
| `DUOI_TEN_DANG_NHAP` `:18` | `NEXT_PUBLIC_DUOI_TEN_DANG_NHAP` hoặc `"dr4women.vn"`. Đổi được để phòng khám khác không phải sửa code |
| `emailTuTenDangNhap(nick)` `:26` | Tên trần → địa chỉ GoTrue. Có sẵn `@` thì **giữ nguyên**. Rỗng → `""` |
| `loiTenDangNhap(nick)` `:36` | `null` = hợp lệ. Chặn rỗng, chặn dấu cách, chặn `@` sai số lượng |
| `tenHienThi(email)` `:57` | Địa chỉ → tên **để hiển thị**: cắt đuôi mặc định, giữ nguyên mọi đuôi khác |

Quyết định gốc — Quang, 09/08/2026: *"tạm thời cứ bỏ @ đuôi mail đã, để tên đăng
nhập sửa như nào cũng được"*.

**Vì sao đuôi vẫn phải tồn tại.** GoTrue (tầng đăng nhập của Supabase) lưu danh
tính trong cột `email` và **tự kiểm định dạng email**. Gửi `"cskhdieuhoa"` lên
là nó trả **422**, dù ta có bỏ mọi kiểm ở phía mình. Nên đuôi không bỏ được —
chỉ là **không ai phải gõ nó nữa**.

**Vì sao phải là MỘT hàm dùng cho CẢ HAI đầu.** Màn quản trị (đặt tên) và màn
đăng nhập (gõ tên) cùng gọi `emailTuTenDangNhap`, nên `"cskhdieuhoa"` ở ô đổi
tên và `"cskhdieuhoa"` ở ô đăng nhập ra **cùng một địa chỉ**. Nếu chỉ nới ở màn
quản trị, quản lý đặt được nick trần rồi nhân viên gõ **đúng nick ấy** vào màn
đăng nhập và bị từ chối — tệ hơn hẳn so với trước khi nới.

Hai chi tiết dễ bỏ sót:

- `if (s.includes("@")) return s;` — trên prod đang có **cả** `@dr4women.vn` lẫn
  `@dr4women.local`. Ép mọi thứ về một đuôi là **khoá cửa** những tài khoản đuôi
  kia.
- `tenHienThi` chỉ cắt **đuôi mặc định**. Cắt luôn `@dr4women.local` thì hai tài
  khoản khác nhau hiện ra cùng một tên, và người ta **đặt lại mật khẩu nhầm
  người**.
- `loiTenDangNhap` cố tình **không** kiểm "trông có giống email không" — đó đúng
  là cái luật vừa bỏ. Nó chỉ chặn những thứ GoTrue chắc chắn từ chối.

---

### 10.5. Vai trò — `lib/roles.ts`

File **thuần**: không import `next/headers`, nên dùng được từ cả Server Component
lẫn Client Component (`Nav.tsx`, `BottomNav.tsx`).

| Hàm / hằng | Giải thích |
|---|---|
| `ClinicRole` `:7` | 13 vai đóng. `DISPLAY` **không phải người** — là cái tivi treo tường |
| `ALL_ROLES` `:25` | Mảng đủ 13 vai, dùng để tính danh sách bằng code thay vì chép tay |
| `departmentToRole(dept)` `:43` | Chuỗi → enum. Mã lạ → `null` (**fail-close**; fallback CSKH cũ là fail-open) |
| `isClinicRole(v)` `:49` | Type guard |
| `isDoctorRole(role)` `:75` | **Làm việc ở bàn bác sĩ**: DOCTOR, ULTRASOUND_DOCTOR, **TKYK** |
| `isPhysicianRole(role)` `:84` | **Có bằng hành nghề**: DOCTOR, ULTRASOUND_DOCTOR |
| `isAdminRole(role)` `:89` | MANAGEMENT |
| `isUltrasoundDoctorRole` / `isNurseRole` / `isThuKyRole` / `isTruongCaRole` | Kiểm một vai đơn lẻ |
| `isCashierRole(role)` `:189` | CASHIER + CASHIER_THUOC + CASHIER_DV |
| `isOpsAdmin(role)` `:155` | MANAGEMENT + TRUONG_CA (quản trị **vận hành**, thấp hơn quản trị hệ thống) |
| `canWriteClinical(role)` `:112` | Bác sĩ desk + Điều dưỡng + TKYK |
| `canReadClinical(role)` `:117` | **Bằng đúng** `canWriteClinical` (ROLE-02) |
| `canWriteIntake(role)` `:125` | CSKH, RECEPTION, MANAGEMENT, TRUONG_CA |
| `canOperateCustomerCare(role)` `:140` | Bằng `canWriteIntake` — khớp `cskh_service.INTAKE_ROLES` |
| `canCheckin(role)` `:161` | RECEPTION, MANAGEMENT |
| `canManageAppt(role)` `:167` | CSKH, MANAGEMENT, TRUONG_CA — **huỷ lịch + phân lại bác sĩ** |
| `canEditPatient(role)` `:174` | `canWriteIntake` **+** bác sĩ desk |
| `isTasksReadOnly(role)` `:196` | RECEPTION + thu ngân: xem board bác sĩ nhưng khoá mọi nút |
| `roleLanding(role)` `:203` | Bác sĩ desk → `/tasks`; TRUONG_CA → `/truong-ca`; còn lại → `/home` |
| `ROLE_LABEL` `:210` | Nhãn tiếng Việt của 13 vai |
| `canSeeNav(role, href)` `:462` | **Gác cửa trang**. Href không có trong `NAV_ROLES` = ai cũng vào |
| `hienTrenThanhBen(role, href)` `:453` | **Chỉ giao diện**: `canSeeNav` **và** không nằm trong `AN_KHOI_THANH_BEN` |

#### Bảng vai — quyền và màn đích

| Vai | Nhãn | Landing | Ghi lâm sàng | Nhập/tạo BN | Quản lý lịch | CSKH |
|---|---|---|---|---|---|---|
| `DOCTOR` | Bác sĩ | `/tasks` | ✅ | — | — | — |
| `ULTRASOUND_DOCTOR` | Bác sĩ Siêu âm | `/tasks` | ✅ | — | — | — |
| `TKYK` | Thư ký Y khoa | `/tasks` | ✅ | — | — | — |
| `NURSE_ULTRASOUND` | Điều dưỡng / Phụ siêu âm | `/home` | ✅ | — | — | — |
| `CSKH` | CSKH | `/home` | — | ✅ | ✅ | ✅ |
| `RECEPTION` | Lễ tân | `/home` | — | ✅ | — | ✅ |
| `TRUONG_CA` | Trưởng ca | `/truong-ca` | — (chỉ xem) | ✅ | ✅ | ✅ |
| `MANAGEMENT` | Quản lý | `/home` | — | ✅ | ✅ | ✅ |
| `CASHIER` | Thu ngân | `/home` | — | — | — | — |
| `CASHIER_THUOC` | Thu ngân thuốc | `/home` | — | — | — | — |
| `CASHIER_DV` | Thu ngân dịch vụ | `/home` | — | — | — | — |
| `PHARMACIST` | Dược sĩ | `/home` | — | — | — | — |
| `DISPLAY` | Màn hình phòng chờ | `/display` | — | — | — | — |

Ba điểm dễ hiểu sai trong bảng trên:

1. **`isDoctorRole` ≠ `isPhysicianRole`.** "Làm ở bàn bác sĩ" **gồm** thư ký y
   khoa: TKYK mở cùng board, gõ hộ bệnh án, chuyển cùng lịch hẹn. "Có bằng hành
   nghề" thì **không**: chỉ định xét nghiệm và duyệt kết quả là hành vi thư ký
   không được làm, và `lab.py` luôn gác cả hai bằng `{DOCTOR, ULTRASOUND_DOCTOR}`.
   Suốt nhiều tháng trình duyệt hỏi nhầm `isDoctorRole` trước khi vẽ "Chỉ định
   XN" và "Duyệt kết quả" ⇒ thư ký thấy nút, bấm, và nhận 403 mà không biết hệ
   thống hỏng hay mình sai. **Máy chủ đúng; màn hình nói dối.**
2. **Điều dưỡng ghi lâm sàng nhưng KHÔNG tạo BN, KHÔNG check-in** (feedback PM
   23/6). `canWriteClinical` của họ không đi qua `canWriteIntake`.
3. **Thu ngân là MỘT vai, không phải ba** (Quang, 03/08/2026). Migration
   `20260803000007` gộp mọi membership về `CASHIER`. `CASHIER_THUOC` /
   `CASHIER_DV` **được giữ trong kiểu** vì `event_log` cũ có chứa chúng — một
   bản ghi kiểm toán không đọc lại được là một bản ghi vô dụng. **Đừng gán chúng
   cho người mới.**

#### `NAV_ROLES` — bảng làm HAI việc

`NAV_ROLES` `:253-421` vừa dựng thanh bên **vừa gác cửa trang** (`requireNavAccess`
gọi chính `canSeeNav`). Đó là lý do phải có bảng thứ hai `AN_KHOI_THANH_BEN`
`:439`: Quang muốn thanh bên của Quản lý gọn lại, nhưng gỡ Quản lý khỏi
`/customers` là gỡ luôn **quyền mở** trang đó — mà nút "Xác nhận lịch trước 7
ngày →" ở màn Chờ xếp bác sĩ đi thẳng tới đấy. Người dùng bấm một nút do chính
hệ thống bày ra rồi bị đá về `/home`, không lời giải thích.

> Hai câu hỏi khác nhau: **"có được vào không"** (`NAV_ROLES`) và **"có bày ra
> trên thanh bên không"** (`AN_KHOI_THANH_BEN`).

Nguyên tắc viết `NAV_ROLES`:

- **Danh sách vai phải khớp guard của backend.** `/nhan-su` chỉ MANAGEMENT vì
  `routers/staff.py` gác mọi thao tác ghi bằng `require_role(MANAGEMENT)`;
  `/sieu-am` phải khớp `ULTRASOUND_ROLES` trong `ultrasound_board_service.py`.
  Lệch nhau thì có người thấy nút mà bấm vào bị 403 — hoặc tệ hơn: vào được màn
  mà backend mới là nơi từ chối.
- **Tra chính xác href, không so tiền tố.** Năm màn Trưởng ca phải liệt kê từng
  đường (`/truong-ca`, `/truong-ca/hang-doi`, …); thiếu một dòng là màn đó đá
  người dùng về `/home` mà không báo gì.
- **Tính bằng code khi có thể**: `"/schedule": ALL_ROLES.filter(r => r !== "CSKH")`
  thay vì chép tay 12 vai.
- `[]` = **ẩn hẳn nhưng giữ đường quay lại** (vd `/queue` tạm ẩn 03/07): không
  vai nào thấy sidebar, gõ URL bị redirect. Mở lại chỉ là khôi phục danh sách.

#### `lib/feature-mode.ts` / `feature-mode-client.ts`

| Xuất | Giải thích |
|---|---|
| `getFeatureMode()` | `cache()` đọc `clinic.settings.feature_mode`; lỗi/không hợp lệ → `FULL_CLINIC` |
| `isCskhOnly` / `isFullClinic` | Kiểm chế độ |
| `CLINICAL_HREFS` (client) | Tập href **ẩn khi ở `CSKH_ONLY`**. File này **không có import server**, nên `"use client"` dùng được |

---

### 10.6. Múi giờ — `lib/datetime.ts`

Vì sao phải ghim: **timestamp lưu ở UTC, còn máy chủ cũng chạy UTC.** Nên mọi
định dạng hiển thị và mọi ranh giới "hôm nay" **bắt buộc** phải nói rõ múi giờ,
nếu không nó trôi **7 tiếng**. Dồn hết vào một file để không ai suy lại một cách
khác. Ràng buộc "chỉ bán trong VN" khiến `Asia/Ho_Chi_Minh` là hằng chứ không
phải cấu hình.

| Hàm / hằng | Giải thích |
|---|---|
| `VN_TZ` `:6` | `"Asia/Ho_Chi_Minh"` |
| `VN_OFFSET` `:12` | `"+07:00"` — **một bản duy nhất**. Trước đó chuỗi này gõ tay ở **mười một chỗ** |
| `giuaTruaVn(ymd)` `:18` | `Date` lúc **12:00** giờ VN của ngày đó |
| `mocMs(ts)` `:30` | Chuỗi/`Date` → mốc ms. **Luôn so mốc, không bao giờ so chuỗi** |
| `daQua(ts, now?)` `:36` | Đã trôi qua chưa. Không đọc được → `false` (không dám khẳng định) |
| `conToi(ts, now?)` `:42` | Còn ở phía trước không |
| `nowMs()` `:49` | `Date.now()` gói ngoài component để né rule `react-hooks/purity` |
| `fmtDateTime` `:62` | `"dd/MM/yyyy HH:mm"` giờ VN |
| `isVnMidnight(ts)` `:79` | Đúng 00:00 giờ VN = dấu hiệu lịch **chỉ có ngày** |
| `fmtTimeOrNone` `:93` | Giờ VN, hoặc `"Chưa có giờ"` |
| `fmtDateTimeOrDate` `:98` | Ngày+giờ, hoặc chỉ ngày nếu 00:00 |
| `fmtTime` `:103` / `fmtDate` `:145` / `fmtDayTime` `:116` | `"HH:mm"` / `"dd/MM/yyyy"` / `"dd/MM HH:mm"` |
| `ngayVN(ts)` `:139` | `"yyyy-MM-dd"` **theo giờ VN** — cùng dạng `work_roster.work_date` |
| `vnToday(now?)` `:162` | Hôm nay VN, trả `Date` nửa đêm **giờ máy** |
| `vnYmd(now?)` `:221` | Hôm nay VN dạng `"YYYY-MM-DD"` — cùng mốc `clinic_today` của backend |
| `fmtVietnameseFullDate` `:171` | `"Ngày D tháng M năm YYYY"` |
| `slotRange(hhmm, minutes)` `:186` | `("17:00", 15)` → `"17:00 - 17:15"` |
| `vnLocalToUtcISO(date, time)` `:198` | Ngày+giờ người VN **gõ** → mốc UTC đúng, bất kể múi giờ trình duyệt |
| `vnTodayRangeUtc(now?)` `:204` | `[đầu ngày, cuối ngày)` VN dưới dạng ISO UTC |
| `vnMonthStartUtc(now?)` `:226` | Đầu tháng VN dưới dạng ISO UTC |

Bốn cái bẫy đã cắn, ghi ngay trong file:

1. **So chuỗi thay vì so mốc.** PostgREST trả `"2026-08-09T08:15:00+07:00"`, còn
   `toISOString()` cho `"…T05:48:00.000Z"`. So hai chuỗi ấy là so **ký tự**:
   `"08" > "05"`, nên một lịch **đã qua bốn tiếng** vẫn được coi là sắp tới.
   Xảy ra thật trên prod ngày 09/08. Cách chữa: mọi so sánh đi qua `mocMs`.
2. **Nửa đêm để lấy thứ trong tuần.** `new Date("…T00:00:00+07:00")` rơi vào
   17:00 UTC **hôm trước**, nên `getUTCDay()` trả thứ của ngày hôm trước. Vì thế
   có `giuaTruaVn` — giữa trưa cách cả hai biên 12 tiếng.
3. **`toISOString().slice(0,10)` để lấy "ngày".** Nó cho ngày theo giờ **quốc
   tế**. Lịch 07:30 sáng VN (00:30 UTC cùng ngày) thì đúng, còn lịch **06:00
   sáng** (23:00 UTC **hôm trước**) ra ngày hôm trước — và phép tra ca trực hỏi
   nhầm ngày. Giờ mở cửa vừa đổi thành 07:00 nên vùng sát ranh giới ấy **giờ có
   lịch thật**. Cách chữa: `ngayVN` dùng `toLocaleDateString("en-CA", {timeZone})`
   — đúng dạng `yyyy-MM-dd` mà không phải tự ghép chuỗi.
4. **`slotRange` không có mặc định 15 phút.** Độ dài khung là cấu hình từng
   phòng khám (`clinic.settings.booking.slot_minutes`). Một mặc định ở đây chỉ
   có tác dụng duy nhất: để một chỗ gọi thiếu tham số **dán nhãn sai giờ lên
   đúng cái ô mà server sẽ từ chối**. Thiếu thì báo lỗi biên dịch.

`lib/roster.ts` giữ nhóm ngày/tuần cho lịch trực (`weekStartOf` `:178`,
`weekDates` `:185`, `shiftWeek` `:195`, `currentWeekStartVn` `:202`, `todayVn`
`:210`, `dayLabel` `:128`, `dayShort` `:135`, `fmtDayMonth` `:140`), cộng cấu
hình trạm (`STATIONS`, `STATION_SEGMENTS`, `FLOOR_BORDER`, `STATION_LABEL`), giờ
mở cửa (`clinicHoursForDate` `:228`, `clinicHoursError` `:242`) và hai hàm đọc
bảng Excel (`chiaHaiHang` `:90`, `demBacSiTruc` `:99`).

`weekStartOf` là chỗ đáng đọc nhất:

```ts
export function weekStartOf(dateStr: string): string | null {
  const d = new Date(dateStr + "T00:00:00Z");
  if (Number.isNaN(d.getTime())) return null;
  return mondayOfUtc(d);
}
```

Chuỗi này đến **thẳng từ thanh địa chỉ** (`/home?weekAppt=…`, `/schedule?week=…`).
Bản cũ dựng `Invalid Date`, đi tiếp bình thường, rồi `toISOString()` ném
`RangeError: Invalid time value`. Server component ném thì **cả trang chủ** rơi
vào `error.tsx`: một link hỏng là màn hình đầu ngày của mọi nhân viên không mở
được. Đây là **con thứ ba cùng một họ** (trước đó là `/api/roster?date=99-99-9999`
và `/api/appointments` thiếu `date`), và hai lần trước đều vá **tại chỗ nó nổ**
nên bản dùng chung trong `lib` sống sót qua cả hai.

> Luật rút ra: hàm nhận ngày từ người dùng phải **trả giá trị rỗng thay vì ném**,
> và chỗ kiểm phải nằm ở **BIÊN** (nơi chuỗi đi vào), không rải rác ở từng nơi
> gọi. `mondayOfUtc` bên dưới vẫn ném nếu bị đưa `Date` hỏng — **cố ý**: tới đó
> thì đó là lỗi lập trình, không phải dữ liệu người dùng.

---

### 10.7. Lưu nháp — `lib/luu-nhap.ts`

Yêu cầu gốc (bảng "tình huống phát sinh", mục 4): *"Mất mạng hoặc tải lại trang
khi đang nhập → hệ thống không tạo dữ liệu dở dang; người dùng biết dữ liệu đã
được lưu hay chưa"*. Trước file này, màn bệnh án không giữ gì: bác sĩ gõ xong một
tờ dài, lỡ F5 hay mất điện là gõ lại từ đầu, **và không có dấu hiệu nào cho biết
đã mất**.

| Xuất | Giải thích |
|---|---|
| `KhoNhap` `:26` | Interface kho tối thiểu (`getItem`/`setItem`/`removeItem`/`key`/`length`) — để **test được mà không cần trình duyệt** |
| `HAN_MS` `:35` | 24 giờ |
| `khoaNhap(staffId, man, id)` `:38` | `clinicai:nhap:<staffId>:<màn>:<id>`. Thiếu `staffId` hoặc `id` → `null` = **không lưu** |
| `donNhapCu(kho, now)` `:53` | Quét toàn kho, bỏ mọi bản quá hạn hoặc hỏng. Trả số bản đã bỏ |
| `ghiNhap(kho, khoa, giaTri, now)` `:69` | Ghi `{ luc, giaTri }`. **Không bao giờ ném** |
| `docNhap(kho, khoa, now)` `:80` | Đọc nháp **còn hạn**; hết hạn thì xoá luôn rồi trả `null` |
| `xoaNhap(kho, khoa)` `:94` | Xoá; thất bại thì hạn 24h dọn hộ |
| `moTaLuc(luc, now)` `:103` | `"vừa xong"` / `"2 phút trước"` / `"3 giờ trước"` |

**Vì sao `localStorage` chứ không `sessionStorage`.** `sessionStorage` chết cùng
tab — tức là **đúng những tình huống cần cứu nhất** (mất điện, trình duyệt sập,
đóng nhầm tab) thì nó không còn gì. Cái giá phải trả là dữ liệu bệnh nhân nằm
trên đĩa máy trạm, nên bốn chốt sau **không phải trang trí**:

1. **Khoá gắn với người đang đăng nhập.** Quầy lễ tân dùng chung một máy; nháp
   của người trước không được hiện ra cho người sau. Đây là lý do `khoaNhap` trả
   `null` khi `staffId` rỗng.
2. **Hạn 24 giờ.** Bỏ khi đọc (`docNhap`) **và** dọn khi ghi (`donNhapCu`) —
   không tích tụ bệnh án của cả tháng trên máy.
3. **Xoá ngay khi lưu thành công.** Nháp chỉ tồn tại trong lúc còn rủi ro mất.
4. **Chỉ lưu thứ người dùng gõ**, không lưu hồ sơ tải từ máy chủ về.

`ghiNhap` nuốt lỗi có chủ ý:

```ts
try {
  kho.setItem(khoa, JSON.stringify({ luc: now, giaTri } satisfies BanNhap<T>));
} catch {
  // Hết chỗ hoặc trình duyệt chặn (chế độ riêng tư). Không lưu được thì thôi:
  // form vẫn dùng bình thường, chỉ là mất lưới an toàn. Không được ném ở đây —
  // ném trong lúc gõ sẽ làm hỏng chính cái nó định cứu.
}
```

`donNhapCu` cũng bỏ luôn bản **parse hỏng** (`catch { bo.push(k) }`) — một bản
nháp không đọc được thì vô dụng, giữ lại chỉ chiếm chỗ.

> **NHÁP KHÔNG PHẢI BẢN LƯU.** Nó không đi đâu cả, không ai khác đọc được, và
> không thay thế việc bấm Lưu. Màn hình phải nói đúng điều đó khi mời khôi phục
> — người dùng cần biết "cái này chưa được lưu", chứ không phải tưởng đã xong.
> Đó là việc của `moTaLuc`: câu mời phải nói rõ nháp cũ tới mức nào.

---

### 10.8. Các tiện ích còn lại trong `lib/`

| File | Xuất chính | Giải thích |
|---|---|---|
| `validation.ts` | `PHONE_RE`, `CCCD_RE`, `digitsOnly`, `normalizePhoneVi`, `toTitleCaseVi`, `unaccentVi`, `phoneError`, `cccdError`, `daysInMonth`, `dmyToIso`, `birthYearError`, `dobError`, `dobErrorIso`, `homNayVn`, `TEN_TOI_DA`, `tenError` | Luật nhập liệu **dùng chung client + server**, một nguồn sự thật |
| `loi-api.ts` | `ThanLoi`, `nhanLoi(d, macDinh)` | Rút câu đọc được từ **mọi** hình dạng lỗi backend |
| `loi-doc-duoc.ts` | `loiDocDuoc(than, mac_dinh)` | Bản dùng cho thân lỗi thô (đọc `message` → `detail` → `error`) |
| `url.ts` | `toHref(raw)` | Link người dùng dán thiếu scheme → thêm `https://` |
| `identity-authority.ts` | (xem §10.3) | Luật thẩm quyền thuần |
| `feature-mode.ts` / `feature-mode-client.ts` | (xem §10.5) | Chế độ tính năng |

Ba chi tiết đáng nhớ:

- **`toTitleCaseVi` áp lúc rời ô (`onBlur`), không lúc đang gõ** — ép lúc gõ sẽ
  **phá bộ gõ Telex/VNI**.
- **`unaccentVi` khớp đúng cột `patient.full_name_unaccent`** (migration 039:
  `lower` + `f_unaccent` + `đ→d`), nên lọc phía client và query Supabase cho
  cùng kết quả.
- **`dobErrorIso` không chép lại luật, nó tách chuỗi rồi gọi `dobError`.** Vì
  nghiệm thu 11/08/2026 phát hiện `POST /api/patients` nhận ngày sinh
  `2099-01-01` và `1850-01-01` **và tạo hồ sơ thật** — không phải thiếu luật,
  mà là luật đúng chỉ được nối vào ô nhập ba khung dd/mm/yyyy, còn đường API đi
  vòng qua nó.

> Đây là **dạng lỗi lặp lại của dự án**: LUẬT ĐÚNG, KHÔNG NỐI VÀO ĐƯỜNG THẬT.
> `loi-api.ts` có `doDetail()` cùng hình dạng, cùng ngày — viết đúng cho mảng
> Pydantic nhưng **gắn vào sai ô**, nên không bao giờ chạy tới. Hậu quả không
> phải hiện sai chữ mà là **nổ**: `chu` nhận nguyên mảng rồi `.trim()` trên
> `Array` → `TypeError`. Trình xử lý lỗi tự nó chết, nên nhân viên gõ sai ngày
> sinh bấm Lưu và thấy **KHÔNG GÌ CẢ**. Bản hiện tại cho **mọi** ứng viên đi
> qua `doCau()`, và `doCau()` chỉ trả chuỗi hoặc `undefined` — thêm ô thứ tư
> cũng không nổ được.

`nhanLoi` còn dịch lỗi Pydantic sang tiếng Việt **kèm tên ô**: `loc:
["body","date_of_birth"]` + `"Input should be a valid date"` →
`"Ngày sinh: ngày không hợp lệ."` (bảng `TEN_O` `:50`, `doiCauQuen` `:109`).
Câu gốc bằng tiếng Anh và không nói ô nào — người trực không biết sửa chỗ nào.

---

### 10.9. Tầng BFF — quy ước chung của `app/api/**/route.ts`

64 route handler. Khuôn mẫu chung, theo đúng thứ tự:

1. **Xác thực**: `getSupabaseServer()` → `auth.getUser()`; không có user → 401.
2. **Uỷ quyền theo vai** (nếu có luật riêng ở tầng UI): `getClinicRole()` +
   helper trong `roles.ts` → 403 kèm câu tiếng Việt.
3. **Đọc và kiểm hình dạng đầu vào**: `request.json()` bọc `try/catch` → 400
   `"Invalid JSON"`; thiếu trường bắt buộc → 400 kèm tên trường.
4. **Chuyển tiếp**: `return proxyJsonToBackend(method, "/api/v1/…", body)`.
   Không xử lý phản hồi — mã trạng thái và câu lỗi của backend **đi thẳng ra**.

Ba ngoại lệ có lý do rõ ràng:

| Route | Vì sao khác |
|---|---|
| `api/events/stream/route.ts` | **SSE**. `EventSource` không đặt được header nên không tự gắn Bearer — phải đi vòng qua đây. **Không dùng** `proxyJsonToBackend`: hàm ấy gọi `res.text()` đọc trọn thân, mà một dòng SSE không bao giờ kết thúc ⇒ treo mãi. Chỗ này chuyền thẳng `res.body`, đặt `maxDuration = 0`, và truyền `request.signal` lên FastAPI để tab đóng không để lại dòng treo |
| `api/wards/route.ts` | Dữ liệu tham chiếu hành chính **tĩnh, công khai**. Đọc thẳng Supabase bằng phiên người gọi; từng phải dùng service-role vì `ward` bật RLS mà không có policy SELECT — migration `20260730000002` đã thêm nên không cần bypass nữa (ADR-0012) |
| `api/admin/users/route.ts` | Thao tác **Auth admin** của Supabase — thứ duy nhất còn cần `service_role` |
| `api/roster/route.ts` | Lai: nhánh đọc `roster_week`/`work_roster` dùng phiên người gọi (có RLS SELECT), nhánh ghi và nhánh `staff_id` proxy xuống FastAPI |

**Vì sao SSE không cho trình duyệt gọi thẳng FastAPI với token trong query
string** (đã cân nhắc và bỏ): làm thế là **ghi token vào log truy cập của mọi
proxy trên đường** — đọc được, sống lâu, đủ để đóng giả người dùng.

#### Bảng route → endpoint FastAPI

| Route Next | Method | Endpoint FastAPI |
|---|---|---|
| `/api/admin/users` | GET, POST, PATCH | Supabase Auth admin (service-role) |
| `/api/appointments` | GET, POST, PATCH | `/api/v1/appointments/bookings`, `/api/v1/appointments/{id}` |
| `/api/appointments/cho-xep-bac-si` | GET, POST | `/api/v1/appointments/cho-xep-bac-si`, `/api/v1/appointments/{id}` |
| `/api/appointments/quote` | GET | `/api/v1/appointments/quote` |
| `/api/appointments/slot-hold` | POST | `/api/v1/appointments/slot-hold` |
| `/api/appointments/service-history` | GET | (đọc trực tiếp) |
| `/api/booking-policy` | PATCH | `/api/v1/booking-policy`, `/api/v1/appointments/policy` |
| `/api/booking-rules` | POST | `/api/v1/booking-rules` |
| `/api/booking-rules/doctor` | GET, PUT, DELETE | `/api/v1/booking-rules/doctor[/{id}|/xem-thu]` |
| `/api/booking-overrides/doctor/[id]` | DELETE | `/api/v1/booking-overrides/doctor/{id}` |
| `/api/booking-overrides/slot/[id]` | DELETE | `/api/v1/booking-overrides/slot/{id}` |
| `/api/brief/[id]` | POST | `/api/v1/brief/{id}` |
| `/api/catalog`, `/api/wards`, `/api/patients/check-phone` | GET | (đọc trực tiếp Supabase) |
| `/api/clinic-config` | GET, PUT | `/api/v1/clinic-config/{overview,services,staff,room-floor,room-nodes,staff-nodes,service-form}` |
| `/api/clinical-form` | GET, PUT | `/api/v1/clinical-forms` |
| `/api/clinical-form/andrology-review` | POST | `/api/v1/clinical-forms/andrology-review` |
| `/api/clinical-forms/history` | GET | `/api/v1/clinical-forms/history` |
| `/api/clinical-record` | GET, POST | `/api/v1/clinical-records` |
| `/api/clinical/[visit_id]/[action]` | GET, POST | `/api/v1/clinical/{visit_id}/{action}` |
| `/api/config/feature-mode` | GET, PUT | `/api/v1/feature-mode` |
| `/api/console/feedback` | POST | `/api/v1/console/feedback` |
| `/api/cskh-action` | POST | `/api/v1/cskh/actions` |
| `/api/cskh-followup` | POST | `/api/v1/cskh/followup-calls` |
| `/api/cskh/hen-goi-lai` | POST, PATCH | `/api/v1/cskh/hen-goi-lai[/{id}]` |
| `/api/cskh/ket-qua` | GET, POST, PATCH | `/api/v1/cskh/ket-qua/tep[/{id}]` |
| `/api/cskh/ket-qua/[tepId]/noi-dung` | GET | `/api/v1/cskh/ket-qua/tep/{id}` |
| `/api/cskh/nhac-tai-kham` | POST | `/api/v1/cskh/nhac-tai-kham` |
| `/api/cskh/phan-hoi` | POST, PATCH | `/api/v1/cskh/phan-hoi[/{id}]` |
| `/api/cskh/tuong-tac` | GET, POST | `/api/v1/cskh/tuong-tac[/{id}]` |
| `/api/cskh/tuong-tac/[id]/hoan-tac` | POST | `/api/v1/cskh/tuong-tac/{id}/hoan-tac` |
| `/api/cskh/zalo` | GET, POST | `/api/v1/cskh/zalo/{trang-thai,gui}` |
| `/api/recall-jobs/[id]/ket-qua` | POST | `/api/v1/cskh/recall-jobs/{id}/…` |
| `/api/dispatch-read` | GET | `/api/v1/dispatch/{overview,routes,alerts,history}` |
| `/api/dispatch/[action]` | POST | `/api/v1/dispatch/{move,route,threshold,transfer-room}` |
| `/api/dispatch/alerts-call` | POST | `/api/v1/dispatch/alerts/call` |
| `/api/episodes` | PATCH | `/api/v1/episodes/{id}` |
| `/api/events/stream` | GET | `/api/v1/events/stream` (**SSE, chuyền dòng**) |
| `/api/lab-result` | POST, PATCH | `/api/v1/lab/orders`, `/api/v1/lab/results/{id}` |
| `/api/lab-result/[id]/review` | POST | `/api/v1/lab/results/{id}/review` |
| `/api/lab-result/[id]/triage` | POST | `/api/v1/lab/triage/{id}` |
| `/api/ops/summary` | GET | `/api/v1/ops/status` |
| `/api/patients` | POST, PATCH | `/api/v1/patients[/{id}]` |
| `/api/patients/check-duplicate` | GET | `/api/v1/patients/check-duplicate` |
| `/api/patients/sdt-them` | POST, DELETE | `/api/v1/patients/sdt-them` |
| `/api/payment` | POST, DELETE | `/api/v1/payments` |
| `/api/pharmacy/[action]` | POST | `/api/v1/pharmacy/{dispense,refuse,receive,adjust,discard,close-line}` |
| `/api/reception/checkout` | GET, POST | `/api/v1/reception/checkout[/chi-tiet/{id}]` |
| `/api/roster` | GET, POST, PATCH, DELETE | `/api/v1/roster/{shifts,stations,weeks/apply}` |
| `/api/roster/pham-vi` | GET, PUT | `/api/v1/roster/station-scope` |
| `/api/service-log` | POST, PATCH | `/api/v1/service-log[/{id}]` |
| `/api/service-price` | POST, PATCH, DELETE | `/api/v1/service-prices[/{id}]` |
| `/api/sono` | POST, PATCH, DELETE | `/api/v1/sono/queue[/{id}]` |
| `/api/staff` | GET, PATCH | `/api/v1/staff[/{id}]` |
| `/api/thong-bao` | GET, POST | `/api/v1/thong-bao[/da-doc]` |
| `/api/thong-bao/[id]/da-xu-ly` | POST | `/api/v1/thong-bao/{id}/da-xu-ly` |
| `/api/ultrasound` | GET, POST | `/api/v1/ultrasound/{queue,rooms,records,draft}` |
| `/api/ultrasound/image` | GET, POST | `/api/v1/ultrasound/image`, `/api/v1/ultrasound/{id}/image` |
| `/api/visits/[id]/charges` | GET | `/api/v1/visits/{id}/charges` |
| `/api/visits/[id]/service-orders` | POST | `/api/v1/visits/{id}/service-orders` |
| `/api/visits/[id]/service-orders/duplicates` | POST | `/api/v1/visits/{id}/service-orders/duplicates` |
| `/api/work-items/[id]/blockers` | GET | `/api/v1/work-items/{id}/blockers` |
| `/api/work-items/[id]/commands/[command]` | POST | `/api/v1/work-items/{id}/commands/{command}` |

> Cuộc chuyển đổi đã **xong**: mọi route nghiệp vụ proxy **không điều kiện**,
> các cờ `*_VIA_BACKEND` theo từng route đã bị gỡ, và **không route nào còn giữ
> nhánh dự phòng gọi thẳng Supabase**. `CLINIC_API_URL` không được đặt nay là
> một **triển khai hỏng**, chứ không phải một chế độ chạy được hỗ trợ — nên nó
> báo lỗi to tiếng.

---

### 10.10. `app/(dashboard)/layout.tsx` — điều hướng theo vai

| Bước | Giải thích |
|---|---|
| `getClinicRole()` → `null` | `redirect("/login")` |
| `role === "DISPLAY"` | `redirect("/display")` — tài khoản của **cái tivi** không có việc gì trong bảng điều khiển; backend đã từ chối vai này ở mọi endpoint nên vào đây cũng chỉ thấy trang lỗi |
| `getCurrentStaff()` | Một truy vấn cho **cả** vai, tên, phòng khám, cơ sở (`cache()` theo lượt render) |
| `identity` | `"<Vai> · <Tên> · <Phòng khám · Cơ sở>"` hiện góc trên |
| `Promise.all([...])` | Ba việc **độc lập** chạy song song |
| `<Shell role identity featureMode leaveAction={logout}>` | `Nav`/`BottomNav` lọc mục bằng `hienTrenThanhBen` + `CLINICAL_HREFS` |

**Vì sao phòng khám + cơ sở đi kèm tên, không phải tuỳ chọn.** Yêu cầu "tài
khoản nào cũng phải có id phòng khám, cơ sở khám để không bị nhầm nữa" chỉ có
tác dụng **nếu người dùng ĐỌC được nó**. Lưu đúng trong database mà không hiện
ra thì đúng cái nhầm đó vẫn xảy ra — lễ tân đặt lịch cho cơ sở khác mà **không
có gì trên màn hình mâu thuẫn với họ**.

**Vì sao `Promise.all`.** Layout chạy lại ở **mọi** lần chuyển trang. Trước đây
nó chờ ba lượt mạng nối đuôi nhau; Supabase ở Seoul, phòng khám ở Việt Nam, đo
được ~180ms mỗi lượt ⇒ riêng khối này tốn ~540ms **trước khi trang bắt đầu làm
việc của nó**. Đo trực tiếp 04/08: **4 truy vấn tuần tự 830ms → song song
213ms**. `getClinicId()` cũng đã bị **bỏ hẳn** khỏi khối này (06/08) — nó chỉ
tồn tại để làm bộ lọc cho `RealtimeRefresher`, mà nay máy chủ tự lọc theo token.

Chuỗi điều hướng đầy đủ, từ lúc gõ địa chỉ:

```
proxy.ts        có phiên? có staff đang làm việc?      → không thì /login
layout.tsx      có vai? có phải DISPLAY?               → không thì /login | /display
page.tsx        requireNavAccess(href) → canSeeNav     → không thì /home
Nav.tsx         hienTrenThanhBen(role, href)           → chỉ ẩn khỏi thanh bên
FastAPI         require_role(...) / identity.py        → chốt cuối, 403
```

---

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

1. **Cookie không phân biệt cổng (RFC 6265 §8.5).** `IP:80` và `IP:8080` là hai
   origin với mọi thứ khác nhưng **dùng chung một hũ cookie**. Đăng nhập staging
   ghi đè phiên prod, và vì hai môi trường ký token bằng hai khoá khác nhau,
   người dùng bị "đăng xuất" khỏi prod mà không hiểu vì sao. Tách bằng **tên
   cookie** cho tới khi có tên miền riêng. **Prod phải giữ nguyên tên cũ** —
   đổi tên cookie là đăng xuất tất cả mọi người.
2. **`getSession()` không làm mới token.** Nó chỉ đọc cookie; sau một tiếng nó
   trả `null` dù phiên vẫn hợp lệ. Luôn `getUser()` trước. Bảy chỗ đã chép thiếu
   dòng này — đó là lý do có `getCallerAuthHeaders()`.
3. **Refresh token bị XOAY.** Hai lời gọi song song trong một lần bấm ⇒ chỗ sau
   nhận `refresh_token_not_found`. Nếu để lỗi ném qua render server component,
   người dùng thấy màn đen **sau khi dữ liệu đã lưu thành công**, bấm lại, và
   chỉ khoá idempotency chặn được bản ghi thứ hai.
4. **Đừng gộp lỗi backend thành 503.** `fetchFromBackend` trả `null` cho mọi
   hỏng hóc; dùng nó ở route handler là xoá mất 404 + câu tiếng Việt của
   backend. Route đọc dữ liệu vẫn phải đi qua `proxyJsonToBackend("GET", …)`.
5. **`Idempotency-Key` phải được GỬI.** Backend có sẵn cơ chế, booking router có
   sẵn `idem.acquire()` — nhưng header tuỳ chọn không ai gửi thì chốt ấy không
   chạy ngày nào. 04/08: một bệnh nhân, ba lịch cùng khung 17:15.
6. **`NEXT_PUBLIC_*` phải viết nguyên văn.** Gán qua biến trung gian thì bundle
   trình duyệt nhận `undefined`, tên cookie hai bên lệch, và đăng nhập xong bị
   đá về `/login` — không lỗi nào để thấy.
7. **`SUPABASE_URL` phải đứng TRƯỚC `NEXT_PUBLIC_SUPABASE_URL` phía server.**
   Prod sống sót vì địa chỉ công cộng của nó ở cổng 80 và cổng 80 đi vòng được;
   staging ở 8080 thì hết giờ chờ. **Prod đang đúng nhờ may, không nhờ thiết
   kế** — một luật tường lửa là nó hỏng y như staging.
8. **`isDoctorRole` ≠ `isPhysicianRole`.** Vẽ nút "Chỉ định XN" bằng
   `isDoctorRole` là mời thư ký y khoa bấm một nút chắc chắn 403.
9. **`NAV_ROLES` vừa dựng menu vừa gác cửa.** Muốn ẩn mà vẫn cho vào thì dùng
   `AN_KHOI_THANH_BEN`. Và nó tra **chính xác href**, không so tiền tố — thiếu
   một dòng cho màn con là màn đó đá người dùng về `/home` không báo gì.
10. **Không so chuỗi thời gian.** `"08:15+07:00"` vs `"05:48Z"` là so ký tự;
    lịch đã qua bốn tiếng vẫn được coi là sắp tới (prod, 09/08). Đi qua `mocMs`.
11. **`toISOString().slice(0,10)` không phải "ngày VN".** Lịch 06:00 sáng ra
    ngày hôm trước. Dùng `ngayVN` / `vnYmd`.
12. **Hàm nhận ngày từ URL phải trả `null`, không được ném.** `toISOString()`
    trên `Invalid Date` ném `RangeError`, và server component ném là cả trang
    chủ vào `error.tsx`. Đã cắn **ba lần** cùng một họ; hai lần đầu vá tại chỗ
    nổ nên bản dùng chung trong `lib` sống sót.
13. **Nháp không phải bản lưu.** Câu mời khôi phục phải nói rõ "chưa được lưu",
    kèm `moTaLuc` để người dùng biết nháp cũ tới mức nào.
14. **`ghiNhap` không được ném.** Ném trong lúc gõ sẽ làm hỏng chính cái nó định
    cứu.
15. **Đuôi `@dr4women.vn` không bỏ được**, chỉ giấu đi. GoTrue kiểm định dạng
    email và trả 422. Và **cả hai đầu** (đặt tên + đăng nhập) phải gọi cùng một
    hàm, nếu không quản lý đặt được nick mà nhân viên không đăng nhập được.
16. **Luật đúng, không nối vào đường thật** là dạng lỗi lặp lại của dự án này:
    `dobError` chỉ nối vào form nên API nhận ngày sinh 2099; `doDetail()` viết
    đúng nhưng gắn sai ô nên trình xử lý lỗi tự nó chết. Khi thêm một luật, hãy
    hỏi: **đường API có đi qua nó không?**


---

## PHẦN 11. BA MÀN HÌNH LỚN NHẤT

Ba màn dưới đây là nơi người dùng thật ngồi cả ngày: **Quản lý khách hàng** (`/customers`), **Đặt lịch hẹn** (`/appointments`), **Tạo hồ sơ khách mới** (`/patients/new`). Chúng chiếm hơn 12.000 dòng, và phần lớn khối lượng ấy không phải giao diện — nó là **luật nghiệp vụ viết ra dưới dạng chú thích**, ghi cả sự cố thật lẫn nguyên văn câu người dùng nói. Đọc code mà bỏ comment là bỏ mất phần giá trị nhất.

> **Một câu tóm cả phần này:** màn Quản lý khách hàng không hiển thị "một khách" —
> nó hiển thị **một cặp (khách, LƯỢT KHÁM)**. Gần như mọi lỗi từng xảy ra ở đây
> đều là một chỗ nào đó quên mất vế thứ hai.

---

### 11.1. `customers/page.tsx` — SERVER COMPONENT (1184 dòng chỉ để dựng dữ liệu)

Server component (`force-dynamic`, `page.tsx:48`). Nó không vẽ gì ngoài một khung `<div>` và lời gọi `<CustomersView …/>` ở `page.tsx:1156`. Toàn bộ phần còn lại làm đúng một việc: **hỏi database rồi dựng các bản đồ tra cứu**.

| Hàm / hằng | Giải thích |
|---|---|
| `vnNextMonthStartUtc()` (`51`) | Đầu tháng SAU theo giờ VN → UTC ISO, chặn cuối cửa sổ "Tháng này" |
| `windowFor(period)` (`64`) | `today/week/month` → `[start,end)` UTC; `all` → `null` |
| `pick1<T>()` (`83`) | Supabase join trả **object HOẶC array** tuỳ quan hệ; lấy phần tử đầu |
| `SELECT` (`106`) | Danh sách cột PostgREST cho bảng `patient` |
| `buildPatientQuery(useUnaccent)` (`181`) | `false` = đường lùi khi chưa migrate cột `full_name_unaccent` |
| `ngayVn(iso)` (`463`) | ISO → `yyyy-mm-dd` **theo giờ phòng khám** (đi qua `Intl`, không cắt chuỗi) |
| `apptSelectAll` (`263`) | Hai bộ cột: vai `canManage` lấy đủ để điền modal đổi lịch, vai khác lấy bản gọn |
| `apptByPatient` (`498`) | **Lịch đại diện** mỗi khách + các cờ suy ra từ nó |
| `grouped` (`502`) | Toàn bộ lịch theo khách — khai ngoài khối vì khối "lịch sử khám" cuối file cũng đọc |
| `coCaTruc` / `doCaTruc` (`506`) | Tập `staff_id\|work_date` trạm `LICH_KHAM`; `doCaTruc` là **chốt an toàn** |
| `trangThaiByPatient` (`835`) | Một dòng `v_trang_thai_cskh` cho một KHÁCH (view là `DISTINCT ON`) |
| `viecMoByPatient` (`836`) | **Mọi** việc đang mở từ `v_viec_cskh`, kèm `appointment_id` |
| `tuongTacByPatient` (`873`) | Sổ chăm sóc, mới nhất trước — nguồn cột "Tương tác gần nhất" |
| `visitTheoLich` (`973`) | `appointment_id` → `{batDau, ketThuc}` từ bảng `visit` |
| `lichSuKhamByPatient` (`966`) | Các **ĐỢT** khám (`ChuoiKham[]`), mỗi đợt là chuỗi lượt nối nhau |

#### Chuỗi `SELECT` không phải SQL — và câu chú thích đã giết chính nó

```ts
// KHÔNG ĐƯỢC ĐẶT CHÚ THÍCH BÊN TRONG CHUỖI NÀY.
// Nó trông như SQL nhưng KHÔNG PHẢI SQL: đây là tham số `select` của PostgREST,
// một danh sách cột phân cách bằng dấu phẩy. `--` không phải chú thích ở đây.
```
`page.tsx:88-92`. Ngày 11/08/2026 có người thêm hai dòng `-- …` vào giữa chuỗi. PostgREST trả `failed to parse select parameter` và **cả màn trắng**. Nó lọt qua vì người sửa nghiệm thu bằng `PATCH /api/patients` mà không mở lại trang tiêu thụ dữ liệu (`100-102`).

Cùng loại bẫy ở `427-440`: `tuong_tac_cskh` vốn chỉ có **một** khoá ngoại sang `staff`. Migration `20260810000009` thêm cái thứ hai (`huy_boi_staff_id`, phục vụ hoàn tác) và PostgREST từ chối **cả câu**: *"more than one relationship was found"* — 400 cho toàn bộ truy vấn, tức trắng màn.

> Thêm một khoá ngoại thứ hai sang cùng một bảng đủ làm hỏng một câu `select`
> viết đúng từ trước. Phòng bằng cách **gọi tên cột khoá ngoại**
> (`staff:nhan_vien_staff_id ( full_name )`), đừng để PostgREST tự đoán.

#### Chọn "lịch đại diện": `live` → `upcoming` → `repr`

```ts
const live = list
  .filter((a) => !DEAD.includes(a.status))
  .sort((x, y) => mocMs(x.slot_start) - mocMs(y.slot_start));
const upcoming = live.find(
  (a) => conToi(a.slot_start, bayGio) && CHUA_DONG.includes(a.status),
);
const repr = upcoming ?? live[live.length - 1] ?? list[list.length - 1];
```
`page.tsx:567-577`.

- `DEAD` = `CANCELLED / NO_SHOW / DOCTOR_DECLINED` (`548`) — huỷ xong khách không còn "có hẹn".
- `CHUA_DONG` = `SCHEDULED / CSKH_CONFIRMED / CONFIRMED / CHECKED_IN` (`561`). **Cố ý không có `COMPLETED`**: `DEAD` không chứa nó (để bộ đếm vẫn đếm lượt đã khám), nhưng nếu `upcoming` cũng nhận thì *"một lượt checkout lúc 12:25 mà giờ hẹn là 18:15 vẫn thắng vai lịch sắp tới"* — và thắng luôn lượt tái khám vừa đặt. Người dùng thấy: đặt tái khám xong màn không đổi, đọc thành **"nút không ấn được"**.
- Nhánh thứ ba là mới: trước đây khách chỉ còn lịch đã huỷ thì bị `continue` bỏ qua, vùng làm việc trống trơn — **đúng lúc CSKH cần gọi hỏi vì sao huỷ**.

Lỗi so sánh đáng nhớ ở `534-543`: chỗ này từng là `a.slot_start >= new Date().toISOString()`. PostgREST trả `"2026-08-09T08:15:00+07:00"`, `toISOString()` cho `"…T05:48:00.000Z"` — so **hai chuỗi** là so ký tự, `"08" > "05"`, nên lịch đã qua bốn tiếng vẫn "sắp tới". Nay dùng `mocMs()` / `conToi()` / `daQua()`.

#### `id` của lượt tách khỏi quyền sửa lượt

```ts
apptByPatient[pid] = {
  id: repr.id ?? null,   // ĐỊNH DANH LƯỢT
  ...
  appt,                  // CHỈ có khi lượt còn đổi/huỷ được
};
```
`page.tsx:615-628`. Trước 10/08/2026 `id` chỉ tồn tại **bên trong** `appt`. Lượt `COMPLETED` không dựng `appt` ⇒ `lich.id` xuống client là `null` trong khi `lich.status` vẫn `COMPLETED`. Prop `lich` thành **một vật lai: trạng thái của lượt này, id của không lượt nào** — và ở `VungLamViecKhach`, `lich.id` null làm bộ lọc sổ chăm sóc theo lượt tự huỷ, quay về sổ CẢ KHÁCH, nên lượt vừa sinh ra đã tích xanh đủ tám bước bằng dữ liệu lượt trước.

> **"Lượt nào" và "sửa được không" là hai câu hỏi khác nhau.**

#### Ba cờ cảnh báo suy ở server

| Cờ | Điều kiện | Vì sao chặt như thế |
|---|---|---|
| `qua_gio_hen` (`638`) | `daQua(slot_start)` **và** status ∈ `SCHEDULED/CSKH_CONFIRMED/CONFIRMED` | Đã check-in / khám xong thì giờ trôi qua là bình thường; tô đỏ ở đó là **dạy người dùng bỏ qua màu đỏ** |
| `mat_bac_si` (`652`) | `doCaTruc` **và** có `doctor_id` **và** chưa qua giờ **và** chưa check-in **và** không có ca `LICH_KHAM` ngày ấy | Truy vấn hỏng ⇒ tập rỗng, và tập rỗng **không được đọc thành "mọi bác sĩ đều nghỉ"** — báo nhầm hàng loạt tệ hơn không báo |
| `sapToi` (`708`) | Trùng = **cùng dịch vụ, cùng ngày**; bỏ lịch có `lich_truoc_id` | Quang 10/08: một lịch Nội tiết đã khám xong và một lịch Phụ khoa sắp tới là **hai đợt khác nhau**, không phải đặt nhầm |

`mat_bac_si` còn một tầng nữa (`292-301`): bản đầu hỏi "bác sĩ này có dòng ca trực nào ngày ấy không". Nhưng một bác sĩ còn có thể nằm ở `THU_THUAT_NGOAI_GIO`, `PHU_BS_KHAM`, `TLYK`… — **mười mã trạm đang dùng trên prod**. Gỡ đúng ca KHÁM mà còn ca trạm khác thì phép kiểm vẫn đọc ra "có đi làm".

> Câu hỏi thật không phải *"hôm ấy có mặt ở phòng khám không"* mà *"hôm ấy có
> ngồi bàn khám không"*.

#### Dựng "Lịch sử các lần khám": gom theo `appointment`, rồi mới ghép `visit`

```ts
const chiSo = luot.lich_truoc_id !== null
    ? chuoiCuaLuot[luot.lich_truoc_id] : undefined;
if (chiSo !== undefined) {
  chuoi[chiSo]!.luot.push(luot);        // nối vào chuỗi cũ
  chuoiCuaLuot[luot.id] = chiSo;
} else {
  chuoiCuaLuot[luot.id] = chuoi.length;
  chuoi.push({ luot: [luot] });         // mở chuỗi mới
}
```
`page.tsx:1098-1113`. Duyệt theo thời gian nên lượt trước **luôn đã có chỗ** khi tới lượt sau. `lich_truoc_id` trỏ tới lượt không có trong danh sách cũng rơi vào `else` — mở chuỗi mới còn hơn ném lượt ấy đi.

Vì sao gom theo `appointment` chứ không theo `visit` (`962-965`): lịch chưa check-in **không có** dòng `visit`. Dựng theo `visit_id` sẽ làm mọi lịch đã huỷ, khách không đến, và lịch còn ở tương lai **biến mất** — đúng những lượt CSKH cần nhìn lại nhất.

`ket_thuc` có **ba mốc ưu tiên theo độ chắc chắn** (`986-989`, `1080`): `visit.closed_at` → `visit.finalized_at` → dòng `CHECK_OUT` của CSKH. Không có mốc nào thì để `null` và **nói ra là "chưa đóng" — đừng bịa giờ**.

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

- **Nuốt `error` của PostgREST** (`512-519`): select một cột không tồn tại hoặc chưa được GRANT trả 400 cho CẢ CÂU → `appts` null, `grouped` rỗng, **mọi khách mất sạch lịch hẹn**, không một dòng đỏ nào. TypeScript không canh được vì client Supabase ở đây không gắn generic.
- **Nuốt lỗi có chủ ý, và chỉ một chỗ** (`924-930`): `v_viec_cskh` là view mới; máy chủ chưa migrate trả 404, khi ấy màn phải **lùi về hành vi cũ** chứ không được sập — nhưng vẫn `console.error`.
- **`recallPromise` trông thừa nhưng phải giữ** (`347-365`, `1124-1139`): endpoint chạy `sinh_viec_nhac_tai_kham()` **trước khi trả về**, và dự án chưa có bộ hẹn giờ nào. Bỏ nó thì hàng đợi nhắc vĩnh viễn rỗng — và **không ai báo lỗi**.
- **Hai vòng lặp đắp `checked_in_at` giống hệt nhau** (`998-1002` và `1008-1012`) — trùng lặp thật, vô hại nhưng nên gộp.

---

### 11.2. `CustomersView.tsx` — CLIENT, và nơi ở của "LƯỢT ĐANG XEM"

| Hàm / hằng | Giải thích |
|---|---|
| `homNayVn()` (`131`) · `tomTatTuongTac()` (`136`) | Ngày hôm nay giờ VN; dòng tóm tắt cột "Tương tác gần nhất" |
| `LUOT_CHUA_DONG` (`272`) | 4 trạng thái "lượt còn diễn ra" — **bản sao có chủ ý** của `CHUA_DONG` ở `page.tsx:561` (một chạy server, một chạy browser) |
| `EMPTY_LUOT` (`294`) | Khách chưa có lịch. Khai **một lần** để React không dựng vật mới mỗi lượt vẽ |
| `nhanChiTiet(tt, lichSu)` (`325`) | Tách nhánh `GOI_LAI` thành 3 câu khác nhau |
| `nhanLuot(l)` (`349`) | "Lượt đang khám" / "Lượt đã khám xong" / "Lượt đã đóng" / "Lịch hẹn sắp tới" |
| `luotMacDinh(cac)` (`358`) | **Luật chọn lượt khi người dùng chưa bấm** |
| `goTim(chuMoi)` (`786`) · `go(...)` (`796`) | Lọc tại chỗ + hoãn 350ms hỏi máy chủ; ghi bộ lọc + `selected/luot/viec` vào URL |
| `hopVoiTab(row, key)` (`843`) | **MỘT vị từ** cho cả 4 ô số lẫn phép lọc bảng |
| `visibleRows` (`886`) | Đưa khách đang xem lên **đầu danh sách** (chỉ đổi chỗ, không lọc) |
| `cacLuotCuaKhach` (`907`) | Phẳng hoá `lichSuKhamByPatient`, sớm trước |
| `luotDangXem` (`927`) | **Trung tâm của cả màn** |
| `viecCuaLuot` (`971`) | Việc đang mở **thuộc lượt đang xem**, gấp nhất trước |
| `tepKetQuaCuaLuot` (`990`) | Tệp đúng lượt — `clinic_patient_id` chưa đủ làm biên dữ liệu |
| `apptSuaDuoc` (`999`) | Lượt đang xem còn đổi/huỷ được không |
| `chonLuot(id)` (`1005`) · `chonKhach(id)` (`746`) | Chọn lượt (ghi URL); đổi khách = **đổi toàn bộ ngữ cảnh ghi dữ liệu** |
| `customerStatus(row)` (`1052`) | Chip trạng thái ở danh sách — mục 11.3 |
| `customerNextStep` / `customerDeadline` (`1218` / `1223`) | Cột "Việc tiếp" và "Hạn xử lý" |

#### `luotMacDinh` — bốn nhánh, và nhánh 2 là chỗ đã cắn

```ts
function luotMacDinh(cac: LuotKham[]): LuotKham | undefined {
  if (!cac.length) return undefined;
  const bayGio = nowMs();
  const dangKham = cac.find((l) => l.status === "CHECKED_IN");
  if (dangKham) return dangKham;
  const sapToi = cac.find(
    (l) => LUOT_CHUA_DONG.includes(l.status) && conToi(l.slot_start, bayGio),
  );
  if (sapToi) return sapToi;
  const conDo = [...cac].reverse().find((l) => LUOT_CHUA_DONG.includes(l.status));
  return conDo ?? cac[cac.length - 1];
}
```
`CustomersView.tsx:358-371`. Đọc theo chú thích `279-291`:

1. **Khách đang có mặt** ⇒ lượt duy nhất đáng quan tâm.
2. **Lượt sắp diễn ra gần nhất** — việc phải chuẩn bị.
3. **Lượt chưa đóng mới nhất** — việc còn dở.
4. **Lượt mới nhất, kể cả đã xong** — xem lại chuyện vừa rồi.

Nhánh 2 **chỉ nhận lượt chưa đóng**. Đây là lỗi Quang gặp: lượt checkout lúc 12:25 nhưng giờ hẹn 18:15 vẫn "còn tới", nên nó chiếm chỗ của lượt tái khám vừa đặt và màn hình **không bao giờ chuyển**.

#### `luotDangXem` — thứ trước 10/08/2026 không tồn tại

```ts
const luotDangXem: MocLich | null = useMemo(() => {
  const daChon =
    luotChon && luotChon.pid === selected?.clinic_patient_id
      ? cacLuotCuaKhach.find((l) => l.id === luotChon.id)
      : undefined;
  const luot = daChon ?? luotMacDinh(cacLuotCuaKhach);
  if (luot) return { id: luot.id, status: luot.status, /* … */ };
  if (!selectedAppt) return null;
  return { id: selectedAppt.id, status: selectedAppt.status, /* … */ };
}, [luotChon, selected, cacLuotCuaKhach, selectedAppt]);
```
`CustomersView.tsx:927-960`. **Ba tầng:** lượt người dùng **CHỌN** → `luotMacDinh` → **lịch đại diện của server**. Nhánh cuối giữ cho vai không nạp được `lichSuKhamByPatient` (Thu ngân, Điều dưỡng); bỏ nó là cột giữa trống trơn với họ — *"một lỗi tệ hơn lỗi đang chữa"*.

`luotChon` là **cặp `{pid, id}`, không phải mỗi id** (`724-736`): đổi khách mà chỉ giữ id lượt thì lượt người trước dính sang người sau.

##### VÌ SAO ĐỔI TRẠNG THÁI LÀM LƯỢT MẶC ĐỊNH NHẢY — gốc lỗi "F5 xong không hoàn tác được"

Đây là điểm rối nhất của cả màn:

- `luotMacDinh` **không đọc `luotChon`** — nó chỉ đọc `status` các lượt.
- `status` **thay đổi khi người trực bấm nút**: Check-in → `CHECKED_IN`; Checkout → `COMPLETED`.
- Nếu `luotChon === null` (người dùng **chưa tự bấm** lượt nào), mỗi lần `router.refresh()` xong, `luotMacDinh` tính lại trên **dữ liệu mới** và có thể trả về một lượt **khác hẳn**.

**Ví dụ đủ số.** Khách Huyền có hai lượt:

| | Lượt A | Lượt B |
|---|---|---|
| Giờ hẹn | hôm nay 09:00 | ngày mai 15:00 |
| Trước khi bấm | `CHECKED_IN` | `CONFIRMED` |

Người trực mở hồ sơ, **không bấm chọn lượt nào**. Nhánh 1 thấy `CHECKED_IN` ⇒ chọn **lượt A**. Bấm "Checkout": `ghiCheckout()` gọi `apply_action("complete")`, lượt A sang `COMPLETED`, rồi `router.refresh()` (`VungLamViecKhach.tsx:979`).

Tính lại: nhánh 1 không còn `CHECKED_IN`; nhánh 2 tìm lượt chưa đóng và còn tới ⇒ **lượt B**. Màn nhảy sang lượt B.

Dòng `CHECK_OUT` vừa ghi thuộc **lượt A**, nhưng `lichSuLuotNay` đang lọc theo `lich.id` = **lượt B** (`VungLamViecKhach.tsx:907-909`). Nút tròn của node ấy không còn `lan?.id` ⇒ `hoanTacDuoc = false` ⇒ vòng tròn trở lại là biểu tượng tĩnh, **bấm không làm gì**. Người dùng mô tả đúng như họ thấy: *"F5 xong không hoàn tác được"*.

Hai thứ trong code chống lại chuyện này — **lượt đi theo URL**:

```ts
if (selectedId && luotChon?.pid === selectedId) params.set("luot", luotChon.id);
```
`CustomersView.tsx:804-805`, và trong `chonLuot` (`1016-1020`): `params.set("luot", id)` + `router.replace(..., { scroll: false })`. Server đọc lại ở `page.tsx:153-154` rồi truyền xuống làm `initialLuot`; `useState` khởi tạo `luotChon` từ đó (`732-736`).

> **Quy tắc rút ra:** chừng nào `luotChon` còn `null`, lượt đang xem là một **giá
> trị suy ra** và có quyền nhảy bất cứ lúc nào dữ liệu đổi. Chỉ khi bấm **"Làm
> việc ở lượt này"** (hoặc mở bằng đường dẫn có `?luot=`) thì lượt mới được
> **ghim**. Muốn hoàn tác chắc chắn: chọn lượt trước, rồi mới bấm nút tròn.

Hệ quả kèm theo: `CustomersView.tsx:1609` đặt `key={`${…patient_id}-${luotDangXem?.id ?? "khong-co-luot"}`}`. Lượt mặc định nhảy ⇒ `key` đổi ⇒ React **unmount rồi mount lại** `VungLamViecKhach`, xoá sạch state cục bộ (ghi chú đang gõ, ô lý do huỷ đang mở). Đó là chủ ý, nhưng nó khuếch đại cảm giác "màn hình tự nhiên reset".

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

- **Ô tìm chỉ lọc thứ đã tải** (`756-772`): `rows` là kết quả `.limit(300)`. Đường tìm phía máy chủ đã tồn tại và chạy đúng, nhưng chỉ được kích hoạt khi đổi bộ lọc — **tình cờ**. Và vì sao **luôn** hỏi máy chủ chứ không chỉ khi lọc ra rỗng: *"kết quả MỘT PHẦN nguy hiểm hơn kết quả rỗng"* — hiện 2 trong 5 người trùng tên thì trông hoàn toàn bình thường.
- **Ô số và bảng phải cùng một vị từ** (`843`): bản cũ tính hai chỗ bằng hai đoạn mã. Đo 08/08: ô "Quá SLA" và "Chờ xác nhận" hiện **0 vĩnh viễn** trong khi bảng dưới đang đỏ, vì hai ô ấy còn đọc nguồn cũ (`cskh_action.deadline_at` — bảng 0 dòng; `status === "SCHEDULED"` — lịch mới vào thẳng `CONFIRMED`).
- **`qua_sla` phải cộng `qua_gio_hen`** (`861-863`): `co_viec_qua_han` của view đo theo **NGÀY**, còn chip đo theo **PHÚT**.

---

### 11.3. Chip trạng thái ở danh sách — `customerStatus()`

`CustomersView.tsx:1052-1215`. Thứ tự đọc:

| # | Nhánh | Điều kiện | Dòng |
|---|---|---|---|
| 0 | **Lượt đang xem thắng tất cả** | chỉ khi người trực **TỰ CHỌN** lượt | `1062-1075` |
| 1 | **Đã huỷ lịch** | `CANCELLED` và `cancelled_at >=` lần chạm cuối | `1126-1137` |
| 2 | **Đã check-in** | `CHECKED_IN` và `checked_in_at >=` lần chạm cuối | `1144-1151` |
| 3 | **Đã đặt lịch** | `created_at` của lượt chưa đóng `>=` lần chạm cuối | `1167-1179` |
| 4 | **Lần chạm cuối** | `nhanLanChamCuoi(chamCuoiRow)` | `1181-1187` |
| 5 | **Việc còn phải làm** | `nhanChiTiet(tt, …)` từ `v_trang_thai_cskh` | `1189-1198` |
| 6–8 | Đường lùi | `cskh_action.status` → `appointmentStatus()` → `"Khách mới"` | `1199-1214` |

#### Vì sao KHÔNG xếp thứ tự cứng mà so MỐC THỜI GIAN

Ba nhánh 1–3 cùng hình dạng:

```ts
const huyLuc =
  apptRow?.status === "CANCELLED" ? (apptRow.cancelled_at ?? null) : null;
if (huyLuc && (!chamCuoiRow || mocMs(huyLuc) >= mocMs(chamCuoiRow.xay_ra_luc))) {
  const ly = nhanLyDoHuy(apptRow?.ly_do_huy_ma);
  return { label: ly ? `Đã huỷ lịch · ${ly}` : "Đã huỷ lịch", tone: "overdue" };
}
```
`CustomersView.tsx:1126-1137`.

Ba nhánh này là **cùng một lỗ hổng, ba chiều khác nhau** (`1105-1117`, `1139-1143`, `1153-1166`): `booking_service` ghi thẳng vào bảng `appointment` — huỷ ghi `cancelled_at`, đặt mới ghi `created_at`; Lễ tân check-in ở màn khác ghi `visit.checked_in_at`. **Không sự kiện nào đi qua sổ `tuong_tac_cskh`.** Nên nếu chip chỉ kể "lần chạm cuối của CSKH", khách vừa bị huỷ lịch vẫn hiện cuộc gọi hôm kia.

> **So mốc thời gian chứ không xếp thứ tự cứng: cái nào xảy ra SAU thì cái ấy là
> chuyện của khách này bây giờ.**

Xếp cứng sai theo cả hai chiều. Để "đã đặt lịch" luôn thắng thì một cuộc gọi xác nhận **sau** khi đặt lịch không bao giờ hiện. Để "lần chạm cuối" luôn thắng thì lịch vừa huỷ 30 giây trước bị che bởi cuộc gọi hôm kia. Phép so `>=` giải quyết cả hai — chú thích `1164-1166` nói đúng điều đó.

Nhánh 0 có điều kiện rất hẹp — **chỉ khi người trực tự chọn lượt** (`1062-1066`). Vì sao (`1053-1061`): cú bấm chọn lượt là **state trong trình duyệt**, không có sự kiện database nào để realtime mang về, nên "đồng bộ" đúng nghĩa ở đây là **đọc thẳng state ấy trong cùng lượt vẽ**. Chưa chọn gì thì chip giữ vai cũ: kể chuyện của **cả KHÁCH**.

`chamCuoiRow` bỏ qua dòng đã hoàn tác (`1123-1125`): `find((d) => !d.huy_luc)` — view DB đã lọc `huy_luc IS NULL` từ `20260810000009`, đây là **phía frontend của cùng một luật** (Tuyền 17/08: *"không được delay"*).

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

- **Một ca đọc được là cũ, và code nói thẳng** (`1100-1104`): lễ tân check-in ở màn khác **không sinh dòng nào** trong sổ CSKH. Nhánh 2 chữa được nhờ `checked_in_at`, nhưng mốc ấy **chỉ có ở vai quản-lý-được-lịch** (`apptSelectAll`, `page.tsx:263`).
- **Nhánh `GOI_LAI` của view gộp ba kết quả thành một nhãn.** `nhanChiTiet` (`325-336`) là lớp hiển thị nói thêm điều view **cố ý** không đủ mịn để nói: không nghe máy → gọi lại ngay; không liên lạc được → tìm số khác; khách hẹn gọi lại → **ĐỪNG gọi bây giờ**.

---

### 11.4. `VungLamViecKhach.tsx` — TIMELINE TRẠNG THÁI (1610 dòng)

| Hàm / hằng | Giải thích |
|---|---|
| `TRUOC_KHAM` (`56`) · `SAU_KHAM_TANG` (`530`) | Trước khám; **sơ đồ nhánh** sau khám: 1 node → 3 nhánh xét nghiệm song song → 1 node chụm → 3 việc theo dõi |
| `KHONG_GAP_DUOC` (`486`) | Ba lối ra cuộc gọi không gặp, **viết đủ chữ** — không "KNM / KLLD / Hẹn GLS" |
| `KET_QUA_GOI_NHAC` (`333`) | Bốn kết quả gọi nhắc; trường tên `ketQua` **không phải `ma`** (`329-332`) |
| `SUY_THEO_LOAI_CU` (`638`) | Đường lùi cho dòng ghi **trước** migration `20260810000002` |
| `MocLich` (`650`) | Hình dạng "lượt đang xem" mà cột giữa cần |
| `VongTron` (`283`) | Vòng tròn node — **là nút hoàn tác khi và chỉ khi có dòng để rút** |
| `lichSuLuotNay` (`907`) | **Sổ chăm sóc riêng lượt đang xem, đã bỏ dòng hoàn tác** |
| `cacLan(loai)` (`1100`) · `xongTheoLich(ma)` (`1110`) · `dangO(ma)` (`1116`) · `lanCuoi(ma)` (`1132`) | Bốn phép hỏi khác nhau về một node |
| `Node({tt, cuoi})` (`1147`) | Một node timeline |
| `ghiMotCham(...)` (`795`) · `ghiCheckout()` (`933`) · `hoanTac(id)` (`1007`) · `ketThucRoiDatLich()` (`1088`) | Bốn đường ghi |

#### `lichSuLuotNay` — hai phép lọc chồng nhau

```ts
const lichSuLuotNay = (
  lich.id ? lichSu.filter((d) => d.appointment_id === lich.id) : []
).filter((d) => !d.huy_luc);
const khongGanDuocLuot = !lich.id && lichSu.length > 0;
```
`VungLamViecKhach.tsx:907-910`.

1. **Lọc theo `appointment_id`** — chữa lỗi Quang tìm ra 10/08 (`881-893`): `lichSu` là sổ của cả KHÁCH; `lanCuoi` dò `trang_thai_ma` trên toàn sổ, nên mọi bước làm ở lượt tháng trước **vẫn tích xanh ở lượt hôm nay**.
2. **Bỏ dòng có `huy_luc`** — đúng như `v_viec_cskh` làm ở server. *"Hai bên phải cùng luật, nếu không node tích xanh mà chip bên trái mở lại"* (`905-906`).

`: []` ở nhánh không có `lich.id` cũng là quyết định. Bản 10/08 sáng viết `: lichSu` — *"thà tích thừa còn hơn một màn trắng"*. Nhưng nó tích thừa **trong im lặng**, đúng lúc `lich.id` hay null nhất: ngay sau checkout. **Rỗng kèm một dòng chữ** (`khongGanDuocLuot`) thì người đọc biết mình đang thiếu gì.

#### `lanCuoi` / `dangO` / `xongTheoLich` — ba câu hỏi khác nhau

```ts
function lanCuoi(ma: string): DongLichSu | undefined {
  const theoMa = lichSuLuotNay.find((d) => d.trang_thai_ma === ma);
  if (theoMa) return theoMa;
  const loai = SUY_THEO_LOAI_CU[ma];
  return loai ? lichSuLuotNay.find((d) => loai.includes(d.loai)) : undefined;
}
```
`1132-1137`. Dò theo `trang_thai_ma` — cột ghi **thẳng mã trạng thái**. Trước đây dò theo `loai` và **sai ở cả hai chiều**: ba trạng thái cùng ghi loại `KHAC` nên bấm cái này tích xanh cái kia, còn "không cần follow up" thì không tích được cái nào.

```ts
function dangO(ma: string): boolean {
  if (viecCuaLuot.some((v) => v.trang_thai === ma)) return true;
  if (ma === "DA_CHECKIN") return daCheckin;
  if (ma === "HOI_LY_DO_HUY") return daHuy;
  if (ma === "DA_TRA_KQ") return cacLan("TRA_KQ").some((d) => d.ket_qua === "DA_LIEN_HE");
  return false;
}
```
`1116-1124`. `dangO` = "khách **ĐANG** ở trạng thái này" (đèn xanh đậm, chữ "đang ở đây"). `lanCuoi` = "đã có một dòng **ĐÓNG** trạng thái này" (tích xanh). `xongTheoLich` (`1110-1113`) là trường hợp thứ ba: `DA_CHECKIN` xong khi lịch hẹn đã `COMPLETED` — **lễ tân đóng lượt từ màn khác**, không có dòng sổ nào ở đây.

Trong `Node` (`1154-1157`): `const dang = dangO(tt.ma); const lan = lanCuoi(tt.ma); const xong = Boolean(lan) || xongTheoLich(tt.ma);` — ba biến, ba nguồn.

#### Nút tròn hoàn tác

```tsx
<VongTron
  xong={xong}
  dang={dang}
  hoanTacDuoc={Boolean(lan?.id)}
  dangHoanTac={dangHoanTac === lan?.id}
  onHoanTac={() => lan?.id && void hoanTac(lan.id)}
/>
```
`1169-1175`. Chú thích ngay trên (`1163-1168`):

> Không có `lan` thì nó vẫn là một biểu tượng như cũ: **rút một thứ chưa từng ghi
> là một cái nút không làm gì**, và người dùng sẽ tưởng mình vừa làm hỏng cái gì đó.

`VongTron` (`283-325`) tự đổi hình: `Undo2` khi đang hoàn tác, `Check` khi xong, `Phone` khi đang ở, `CircleDashed` khi chưa. Chỉ khi `hoanTacDuoc` mới render thành `<button>`; ngược lại là `<span>` tĩnh.

**Không hỏi lại** (`996-1006`). Quang 10/08: *"click vào nút tròn là tự back lại, không cần xác nhận kiểu vậy"*. Lý lẽ đáng chép lại:

> Cái giá của một cú rút nhầm THẤP: bấm "Làm bước này" là ghi lại ngay, và dòng
> cũ vẫn nằm nguyên trong sổ. Một hộp thoại chặn đường cho một việc rẻ như thế thì
> người ta bấm OK theo phản xạ — tức nó **không bảo vệ được gì**. Hộp thoại xứng
> đáng ở chỗ mất mát KHÔNG lấy lại được — chỗ đó là `CHECK_OUT`, và ở đấy backend
> từ chối hẳn.

#### `ghiCheckout` đi vòng có chủ ý

`933-981`. Không gọi `/api/v1/dispatch/checkout` (gác bằng `_RECEPTION_GUARD`, CSKH không có quyền) mà ghi một dòng `loai = "CHECK_OUT"`; backend thấy loại ấy thì gọi `BookingService.apply_action("complete")` — **đi đúng máy trạng thái**. Chú thích cảnh báo: **điều này KHÔNG đóng dòng `visit`** — `visit.closed_at` chỉ do `checkout_service` ghi, đó là việc của quầy.

`ketThucRoiDatLich` (`1088-1094`) gói ba nút thành một sự thật: *"khi ấn tái khám hay checkout hay đặt lịch mới thì bản chất chúng nó đều là khám xong rồi"*. Chỉ đóng khi đang `CHECKED_IN`; **đóng hỏng thì không mở form**.

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

- **`SAU_KHAM_TANG` không phải hàng dọc** (`492-504`): bản cũ vẽ tám node nối nhau bằng một sợi kẻ — hình dạng nói khách đi qua tám bước theo thứ tự. Ba nhánh xét nghiệm là **ba tình huống loại trừ nhau**. *"Thứ tự cũ vốn đã đúng topo — chỉ có cách vẽ là sai."*
- **Lệch một chữ `loai` là node tích xanh mà trạng thái không đóng** (`515-517`) — đúng lỗi đã vá ở `DA_TRA_KQ`, nơi hai nút ghi `"KHAC"` trong khi `dangO` dò `"TRA_KQ"`.
- **4xx bỏ khoá idempotency, 5xx giữ** (`860-870`, `968-972`, `HanhDongTrangThai.tsx:338-348`). 4xx nghĩa là **chắc chắn chưa ghi gì**; giữ khoá thì lần bấm lại đâm vào hàng `PROCESSING` và nhận 409 *"đang được xử lý"* — kẹt 5 phút, câu giải thích THẬT biến mất. Đo staging 13/08: 422, 422, rồi 409, 409 mãi. Cơ chế khoá nằm ở `khoa-mot-lan.ts:32-53` — khoá theo **THAO TÁC**, không theo lần bấm.

---

### 11.5. `HanhDongTrangThai.tsx` — CỘT PHẢI, mỗi trạng thái một bộ nút

| Hàm / hằng | Giải thích |
|---|---|
| `HanhDongViec` (`39`) | `tieuDe` / `loai` / `goiKhach` / `zalo` / `nhacNho` / `oKhoiKhac` |
| `HANH_DONG` (`53`) · `HANH_DONG_THEM` (`125`) | 9 trạng thái **view suy ra được**; 5 trạng thái **CSKH chọn tay** |
| `tieuDeHanhDong(ma)` (`177`) | Để `CustomersView` dựng tiêu đề **từ cùng một bảng** với các nút |
| `coBoNut(ma)` (`189`) | Kiểm `?viec=` trên URL **trước khi dùng** — mã cũ từ chuông thông báo tuần trước sẽ mở ra khối trống |
| `MAC_DINH` (`194`) · `LY_DO_HUY_SAN` (`211`) | Bộ nút chung; lý do huỷ lấy từ danh mục chung `LY_DO_HUY_THU_TU` |
| `ghi(ma, loai, ketQua, noiDung?)` (`266`) | Đường ghi chính — `POST /api/cskh/tuong-tac` |
| `henTaiKham()` (`383`) · `henGoiLai()` (`418`) | Sinh **hai** mốc gọi; đường **duy nhất** sinh `hen_goi_lai` |
| `NutChinh` / `NutPhu` / `than()` (`466` / `490` / `541`) | Dựng nút và thân khối theo trạng thái |

Ba chi tiết trong `ghi()` (`320-330`):

```ts
kenh: mocQuay ? "TRUC_TIEP"
    : ketQua === "BO_QUA" ? "KHONG_LIEN_HE" : "GOI",
ket_qua: mocQuay ? "GHI_NHAN" : ketQua,
trang_thai_ma: trangThai,
```

1. **`BO_QUA ⟺ KHONG_LIEN_HE`.** Cả backend lẫn CHECK `tuong_tac_bo_qua_thi_khong_lien_he` đều đòi cặp này. Chỗ này từng gửi cứng `"GOI"`, nên nút "Ghi nhận: không cần gọi" **chưa từng ghi được lần nào** — bấm là dòng đỏ, bước trên timeline không bao giờ tích xanh. Luật nay viết một chỗ: `kenhCho()` ở `mot-cham.ts:127-131`.
2. **`appointment_id` luôn gắn khi có** (`292-307`). Chỗ này từng chỉ gắn cho năm loại thuộc `CAN_LICH_HEN` — đúng theo nghĩa "không vi phạm ràng buộc" nhưng **vứt đi thông tin lượt khám**. Khi timeline bắt đầu lọc sổ theo lượt thì bấm mấy nút ấy ghi thật nhưng **không tích xanh**, vì chính màn hình loại dòng vừa ghi ra.
3. **`trang_thai_ma`** là thứ timeline dò để tích xanh.

`goiKhach = false` **không ẩn ô ghi kết quả** — việc vẫn phải được ghi. Nó chỉ bỏ **nút quay số nhầm người**: bước "Hỏi đơn vị xét nghiệm" từng bày nút quay máy KHÁCH HÀNG, tức gọi khách để nói *"em chưa có kết quả"* (`26-37`).

`henTaiKham()` từng **mất hẳn đường vào** (`364-382`): endpoint sống từ lâu, khối `NhacTaiKham` bị gỡ 09/08/2026, từ đó không nút nào gọi tới — trong khi **sáu chỗ** trên chính giao diện vẫn bảo *"gõ ngày ở khối Nhắc tái khám"*.

---

### 11.6. Các file nhỏ

| File | Vai trò |
|---|---|
| `so-tuong-tac.ts` (31) | Kiểu `DongLichSu` dùng chung server ↔ client. Tách file riêng vì trước đây export từ `GhiTuongTac.tsx` — xoá component ấy là **ba file khác gãy theo** |
| `mot-cham.ts` (203) | `MOT_CHAM` (`27`), `laMotCham` (`111`), `kenhCho` (`127`), `NHAN_DA_LAM` (`154`), `nhanLanChamCuoi` (`193`) |
| `LichSuCacLanKham.tsx` (300) | Vẽ các ĐỢT; `MotLuot` (`92`) là một lượt; nút "Làm việc ở lượt này" (`152-160`) |
| `DemNguocKham.tsx` (85) | Đồng hồ đếm ngược tới giờ hẹn, **có luật dừng** |

`mot-cham.ts` ở file riêng vì **hai cột hỏi hai câu ngược nhau trên cùng danh sách** (`6-10`): cột giữa cần nó để **BẤM LÀ GHI**; cột phải cần nó để **BỎ ĐI** nút ghi trùng — *"bỏ ô đã xác nhận cuộc gọi vì bên kia ấn là được rồi mà"*. Mỗi bên giữ một bản là sớm muộn người trực ghi **hai dòng cho một cuộc gọi**.

`DemNguocKham` có ba điều kiện dừng (`6-13`), trả lời câu Tuyền hỏi 17/08 *"có bị vô hạn thời gian không"*: chỉ đếm khi lịch chưa-tới; **tới giờ là interval tự clear ngay trong tick** (`57-61`), không đếm âm; unmount/đổi lượt là clear. Nhịp 30 giây vì đơn vị nhỏ nhất là **phút**. `nowMs` khởi tạo `null` để **server không có "bây giờ"**, tránh lệch hydration (`46`).

---

### 11.7. Nguyên tắc chốt hạ: HOÀN TÁC ảnh hưởng phép ĐẾM, không ảnh hưởng phép KỂ

Luật xuyên suốt cả màn, viết nguyên văn ở `page.tsx:1020-1025`:

```ts
// GIỮ NGUYÊN cả dòng đã hoàn tác (`huy_luc`): "Lịch sử các lần khám" vẽ chúng
// gạch ngang — bằng chứng "đã ghi rồi rút lại" phải còn nhìn thấy được (Tuyền
// 18/08/2026: PR 139 lọc mất từ nguồn, dòng gạch ngang biến mất hẳn). Hoàn tác
// chỉ được phép ảnh hưởng phép ĐẾM — không được phép ảnh hưởng phép KỂ.
```

Gốc là câu Quang nói 10/08/2026: *"nhấn vào nút tròn của các sự kiện để hoàn tác… tất nhiên là **log không được xoá**, mà là hoàn tác lại tác vụ đó"*. Backend đặt `huy_luc` trên **chính dòng ấy** — dòng **ở lại**, chỉ thôi được tính (`so-tuong-tac.ts:13-15`). Từ đó hai họ phép toán tách hẳn:

**Phép ĐẾM (bỏ dòng `huy_luc`):**

| Chỗ | Trích dẫn |
|---|---|
| `lichSuLuotNay` — cơ sở của tích xanh | `VungLamViecKhach.tsx:907-909` |
| Mốc checkout của một lượt | `page.tsx:1032` — `buoc.find((d) => d.loai === "CHECK_OUT" && !d.huy_luc)` |
| `chamCuoiRow` — chip danh sách | `CustomersView.tsx:1123-1125` |
| `nhanChiTiet` nhánh `GOI_LAI` | `CustomersView.tsx:333` |
| View DB `v_viec_cskh` | migration `20260810000009` lọc `huy_luc IS NULL` |

**Phép KỂ (giữ nguyên, chỉ gạch ngang):**

```tsx
<span className={b.huy_luc ? "line-through" : undefined}>
  <span className="font-mono text-ink-muted">{gio(b.luc)}</span>
  {" · "}
  {NHAN_BUOC[b.trang_thai_ma ?? ""] ?? NHAN_BUOC[b.loai] ?? b.trang_thai_ma ?? b.loai}
</span>
{b.huy_luc && <span className="…">đã hoàn tác</span>}
```
`LichSuCacLanKham.tsx:213-228`. Dòng vẫn hiện, chữ mờ (`text-ink-faint`, `202`), gạch ngang, kèm chip nhỏ "đã hoàn tác".

> **Giấu nó đi là đúng thứ câu ấy cấm — lịch sử phải đọc được cả hai vế: đã bấm,
> rồi đã rút lại.** (`LichSuCacLanKham.tsx:209-212`)

Đây cũng là chỗ PR 139 đã cắn: nó lọc `huy_luc` **ngay từ nguồn** (lúc `page.tsx` dựng `buoc`), nên dòng gạch ngang biến mất hẳn. Phép ĐẾM đúng, phép KỂ mất. Cách đúng là **lọc ở nơi tiêu thụ, không lọc ở nguồn**.

Hệ quả kèm theo: `CHECK_OUT` **không hoàn tác được** — `TuongTacCskhService.hoan_tac` từ chối vì máy trạng thái không có đường ra khỏi `COMPLETED` (`VungLamViecKhach.tsx:991-994`). `CHECK_IN` thì được: backend gọi thêm `undo_checkin` đưa lịch hẹn về `CONFIRMED`.

---

### 11.8. `appointments/BookingHub.tsx` — LƯỚI SLOT (2355 dòng)

Bố cục 3 cột (`3-6`): trái = khách đang chọn + tìm khách; giữa = **lưới giờ**; phải = panel xác nhận có ô "Sức chứa x/y".

| Hàm / hằng | Giải thích |
|---|---|
| `nhanLanKham(o)` (`88`) | "tái khám" / "khám lần N" — **cùng luật** với màn Quản lý khách hàng |
| `vnToday()` (`103`) | **Không** dùng `toISOString().slice(0,10)` — từ 00:00–07:00 giờ VN nó trả ngày HÔM QUA |
| `weekOf(anchor, offset)` (`113`) | Bảy ngày T2→CN. Trước đây là **hằng số cứng 11/05–17/05/2026** |
| `LichThang` (`162`) · `tuanLechSoVoiHomNay` (`146`) | Lịch tháng để nhảy ngày xa |
| `generateSlotsForDate(...)` (`257`) | Sinh mốc giờ theo giờ mở cửa của **đúng thứ trong tuần** |
| `SlotTone` (`284`) · `MocDatLich` (`330`) | `available/few/full/holding/selected/loading`; ô lưới |
| `gridLocked` (`400`) | `!policy` ⇒ lưới vẫn vẽ nhưng **mọi ô khoá** |
| `bayGio` (`417`) | Mốc "bây giờ" trong **state**, tick 30s |
| `activeDoctors` (`669`) | Chỉ hiện bác sĩ có ca ngày đang xem — và hiện **hết** |
| `chuaXepCa` / `cotLuoi` (`696` / `699`) | Ngày chưa xếp ca ⇒ đúng **một cột "Khung giờ mong muốn"**, không tên ai |
| `usageByCell` (`1056`) · `heldByOthers` (`892`) | `docId\|ngày\|giờ` → lịch chiếm chỗ / tên người **đang giữ** |
| `khungDaQua(time)` (`1078`) | So bằng **giờ KẾT THÚC**, không phải giờ bắt đầu |
| `getCellStatus(docId, time)` (`1096`) | **Máy quyết định màu và nhãn của một ô** |
| `selectedCellStatus` (`1246`) · `handleConfirmBooking()` (`1274`) | Tóm tắt panel phải; ba lớp chống đặt trùng |

#### `getCellStatus` — thứ tự các luật, cao xuống thấp

```
1. !time                 → "Chưa chọn khung giờ"          (1099)
2. khungDaQua(time)      → "Đã qua giờ"          tone full (1114)
3. offDuty[doc|ngày]     → "Không có lịch"       tone full (1128)
4. !cell && capLoaded    → "Ngoài ca trực"       tone full (1143)
5. gridLocked            → "Chưa có luật"        tone full (1158)
6. dateLoading           → "Đang tải…"        tone loading (1169)
7. isSelected            → "Còn N chỗ" / "Đã đầy — chọn khung khác" (1193)
8. bookedCount >= maxCap → "Đã đầy"              tone full (1209)
9. holder                → "<tên> đang chọn"  tone holding (1218)
10. bookedCount > 0      → "Còn N chỗ"           tone few  (1227)
11. mặc định             → "Có thể đặt"     tone available (1236)
```

- **Luật 2 trên cả luật 3** (`1108-1113`): không ai đặt được vào thời điểm đã đi qua dù bác sĩ có rảnh hay không. *"Trước khi có cả hai lớp, lúc 16:40 vẫn đặt được lịch cho 16:20 và server trả 201."*
- **Luật 3 trên sức chứa** (`1123-1127`): *"Một luật '18:00–18:15 tám chỗ' không có nghĩa gì vào ngày bác sĩ không đi làm."*
- **Luật 6 phải có tone RIÊNG** (`1170-1174`): xanh dương ở lưới này có đúng một nghĩa — *"một CSKH khác đang chọn ô đó"*. Cho ô "đang tải" mượn cùng màu là **dạy người dùng rằng màu ấy đôi khi chẳng nghĩa gì**.
- **Luật 7 vẫn phải nói SỰ THẬT** (`1189-1192`): bản cũ trả cứng `bookedCount: 1` cho ô được chọn, nên bấm vào khung **đã đầy** thì nhãn đổi thành "Còn N chỗ" — *"giao diện tự trấn an người dùng ngay trước khi server từ chối"*.

#### Sức chứa `x/y` — con số ấy tới từ đâu

`y` (`maxCap`, `1152-1155`) = `cell.regular + cell.walkin` nếu đã đọc được luật riêng của ô, ngược lại `dynamicCap = policy.regularCap + policy.walkinCap` (`383`). **Không có mặc định cứng** (`379-382`): bản cũ là `(policy?.regularCap ?? 3) + …`, và **số 3 không trùng mặc định 2 ở bất kỳ chỗ nào khác** — backend im lặng thì lưới mời đặt vào chỗ thứ ba mà trigger sẽ từ chối. Thiếu luật ⇒ `dynamicCap = 0` ⇒ `gridLocked`.

`x` (`bookedCount`) đếm từ `usageByCell` (`1056-1070`), nơi chữa **hai lỗi im lặng** (`873-885`):
1. Bản cũ làm `a.slot_start.slice(11, 16)` — **cắt chuỗi ISO UTC** rồi so với nhãn giờ VN. Lịch 18:00 VN trong DB là 11:00Z ⇒ phép so **không bao giờ đúng** ⇒ mọi ô luôn "Có thể đặt · 0/N", CSKH chỉ biết đặt trùng khi trigger trả 409.
2. Bản cũ **không lọc theo NGÀY** — lịch 18:00 thứ Ba đếm vào ô 18:00 thứ Năm.

#### Cách hỏi backend — ba đường, ba nhịp

| Đường | Endpoint | Khi nào |
|---|---|---|
| Lịch của ngày | `GET /api/appointments?date=` (`793`) | Đổi sang ngày ≠ hôm nay và `fetchedByDate` chưa có |
| Sức chứa | `GET /api/appointments/quote?date=&doctor_id=` (`820`) | Đổi ngày / lọc bác sĩ / `bookingSeq` / `doiCa` |
| Chỗ đang giữ | `GET /api/appointments/slot-hold?date=` (`899`) | Nhịp 5s + `visibilitychange` + SSE `change` |

Ba điểm tinh tế: (1) **`undefined` ≠ `[]`** (`785-788`) — *"coi 'chưa tải xong' là 'còn chỗ' thì lưới mời đặt vào một khung có thể đã kín"*, nên fetch hỏng thì **để nguyên `undefined`** (`801-804`); (2) **quote hỏi cả chuỗi rỗng** (`813-816`) — chuỗi rỗng = **sức chứa chung**, cần cho cột "Khung giờ mong muốn" của ngày chưa xếp ca; (3) **`capLoaded` phân biệt "hỏng" với "ngoài ca"** (`839-841`) — `d === null` ⇒ **không** đánh dấu đã tải, để lưới nói "đang tải" thay vì kết luận cả ngày ngoài ca trực.

#### Làm tươi khi CA TRỰC ĐỔI

```ts
const doiCa = useDoiCa();
useEffect(() => {
  if (doiCa === 0) return;
  const t = setTimeout(() => setFetchedByDate({}), 0);
  return () => clearTimeout(t);
}, [doiCa]);
```
`772-781`. Xoá ca là **lịch hẹn của ca ấy bị HUỶ theo** — cache lịch của-ngày-khác đang giữ những dòng vừa chết. Hoãn qua `setTimeout(0)` vì luật nhà cấm setState đồng bộ trong effect.

`doiCa` cũng nằm trong deps effect quote (`869`), cùng `bookingSeq`. Vì sao cần `bookingSeq` (`757-768`): `router.refresh()` **chỉ nạp lại prop từ server, mà prop đó CHỈ CHỨA LỊCH HÔM NAY**. Lịch ngày khác nằm trong `fetchedByDate` — state trình duyệt, nó không biết vừa có lịch mới, nên ô vừa đặt **vẫn vẽ "0/8" ngay sau dòng "Đã đặt lịch hẹn thành công"**.

Nhịp `slot_hold` hạ từ 15s xuống 5s ngày 14/08, **giá đã đo chứ không ước lượng** (`920-931`): một nhịp tốn 4,8ms cả chuỗi; bốn CSKH cùng mở màn = 0,8 lượt/giây = **0,4% một lõi**; ngưỡng xem lại khoảng 30 người. SSE (`961-979`) mở **dòng riêng**, không nhờ `RealtimeRefresher` — bộ ấy gọi `router.refresh()` cho mọi tin, tám CSKH bấm lướt sẽ thành **mưa render trên mọi tab**. Nhịp 5s giữ làm **lưới an toàn** vì dòng SSE có thể rớt.

Thả chỗ khi rời màn (`990-1015`): `DELETE` với `keepalive: true` — **không dùng `sendBeacon`** vì beacon chỉ POST được. Deps rỗng, **chỉ chạy lúc gỡ component**: đổi khung thì `SlotHoldService.hold()` đã tự thả cái cũ trong cùng transaction; gọi thêm `DELETE` sẽ **đua với POST mới**.

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

- **`khungDaQua("")` từng làm vỡ cả màn** (`1079-1090`): `vnLocalToUtcISO(ngày, "")` → `"2026-08-29T:00+07:00"` → Invalid Date → `.toISOString()` **ném RangeError**. Hàm chạy **trong lúc render**, nên React bỏ cả cây. Và `selectedSlot.time` rỗng ở hai lúc **rất thường**: vừa đổi ngày, vừa đặt lịch xong — *"đường đi bình thường của mọi lần đặt lịch"*.
- **`selectedCellStatus` cố ý bỏ `getCellStatus` khỏi deps** (`1248-1262`): nó là hàm thường, dựng lại mọi lần render, đưa vào deps thì `useMemo` **không còn là memo**. Nhưng `capByCell`, `selectedDateIso`, `apptsForDate` **phải** có — thiếu là thẻ "Sức chứa" giữ nguyên con số của **ngày trước**.
- **`Date.now()` không được gọi lúc render** (`408-416`): đọc đồng hồ lúc render thì lưới **chỉ đúng tại khoảnh khắc tải trang** — mở màn 17:55 rồi tư vấn tới 18:20 vẫn thấy khung 18:00 xanh.
- **Bỏ chọn phải là bỏ chọn thật** (`472-481`): bản cũ rơi về `patients[0]`, nên ba nút "Hủy chọn" / "Đặt cho khách khác" / "+ Đặt lịch cho khách mới" **không bỏ chọn được** — bấm "Đặt cho khách khác" rồi bấm "Đặt lịch hẹn" là đặt cho một người mình không hề chọn.
- **Không rơi về `cleanServices[0]`** (`444-449`, `1287-1293`): đặt vào một dịch vụ chưa chọn là **ghi sai hồ sơ mà không ai biết cho tới lúc khách tới nơi**.
- **Ba lớp chống đặt trùng** (`1295-1317`): (1) `submittingRef` — `useRef` đổi giá trị NGAY, còn `setBookingLoading(true)` chỉ có hiệu lực sau render nên double-click ~150ms vẫn lọt qua `disabled`; (2) `Idempotency-Key` sinh **một lần cho một lần đặt**; (3) chốt database — **chưa có**, vì prod còn 5 dòng trùng nên chỉ mục duy nhất chưa dựng được.

---

### 11.9. `patients/new/NewPatientForm.tsx` — TẠO HỒ SƠ (1719 dòng)

Form **một bước**: hồ sơ + (tuỳ chọn) lịch hẹn đầu tiên. Một submit tạo bệnh nhân (kiểm trùng MPI) rồi đặt lịch nếu đã điền đủ dịch vụ + ngày + giờ.

| Hàm / kiểu | Giải thích |
|---|---|
| `DupMatch` (`77`) · `PhoneMatch` (`86`) | Trùng theo đường **LƯU**; trùng cảnh báo **SỚM** (kèm `clinic_patient_id`) |
| `ThemSdtChoKhach` (`112`) | **Lối đi thứ ba** của ô cảnh báo trùng |
| `findServiceIdByLinhVuc` (`224`) | Chọn lĩnh vực → gợi ý dịch vụ khám |
| `nhapDo` (`361`) | Bản nháp đọc từ `localStorage` lúc mount |
| `phoneDupes` / `trungTen` (`603` / `594`) | Hai mức cảnh báo, **cố ý tách rời** |
| `bookFor(id)` (`686`) · `proceed()` (`817`) · `save(force)` (`838`) | Đặt lịch sau khi tạo hồ sơ; kiểm hợp lệ rồi gửi |
| `khoiPhucNhap()` / `boNhap()` (`762` / `786`) · `goToProfile()` (`793`) | Khôi phục / bỏ nháp; điều hướng theo vai và **xoá nháp** trước khi đi |

#### Cảnh báo trùng — HAI mức, và vì sao không gộp

```ts
const coTen = fullName.trim().length >= 3;
const coNam = nam >= 1900 && nam <= CUR_YEAR;
if (digits.length !== 10 && !coTen) { setPhoneDupes([]); setTrungTen([]); return; }
const qs = new URLSearchParams();
if (digits.length === 10) qs.set("phone", phone);
if (coTen) { qs.set("full_name", fullName.trim()); if (coNam) qs.set("birth_year", String(nam)); }
const res = await fetch(`/api/patients/check-duplicate?${qs}`);
```
`NewPatientForm.tsx:623-644`, debounce 450ms.

- **Hỏi khi có đủ MỘT TRONG HAI** (`609-614`): bản cũ chỉ hỏi khi gõ xong 10 chữ số, nên người khai SĐT mới — hoặc không khai SĐT — **không bao giờ được cảnh báo**, dù hồ sơ cũ nằm ngay đó với đúng tên và đúng năm sinh.
- **Tên 3 ký tự là đủ hỏi** (Tuyền 15/08, `619-622`): khách cũ đọc số mới, người trực gõ tên trước khi kịp hỏi năm sinh — trước đây nhánh này đòi cả năm nên **đúng ca hay gặp nhất không bao giờ được cảnh báo**.
- **MỘT LUẬT DUY NHẤT** (`634-637`): endpoint này gọi đúng hàm mà đường LƯU gọi (`MPIService.find_candidates`). Bản cũ dùng `/check-phone` với truy vấn riêng chỉ so SĐT — nên **màn hình nói "không trùng", Lễ tân bấm lưu, rồi hồ sơ rơi vào hàng chờ gộp**.

Hai khối cảnh báo vẽ **khác nhau có chủ ý**:

| | `phoneDupes` (`1135-1176`) | `trungTen` (`1181-1207`) |
|---|---|---|
| Màu | `bg-warning-bg`, có ⚠ | `bg-surface-muted`, không màu cảnh báo |
| Nghĩa | Đường LƯU **cũng** coi là trùng (SĐT / CCCD / tên+năm) | Chỉ trùng tên |
| Câu kết | "Kiểm tra xem có phải người nhà dùng chung số không. Vẫn tạo mới được." | "Trùng tên là chuyện thường — chỉ nhắc để kiểm lại năm sinh có gõ nhầm không." |

> Trùng tên ở Việt Nam là chuyện thường, nên **không được trộn vào khối kia** —
> gộp lại thì người trực sẽ học cách bỏ qua **cả hai** (`588-593`, `1177-1180`).

Khối `phoneDupes` còn **nói đúng thứ đã khớp** (`1137-1153`): bản trước luôn mở đầu "Số này đã có trong hệ thống", kể cả khi thứ khớp là TÊN + NĂM SINH — nên một cảnh báo trùng tên trôi qua như không có. Nay suy ngược: luật khớp mạnh chỉ có ba nhánh, mà form này không gửi CCCD ⇒ khớp cả tên lẫn năm sinh thì là nhánh tên, còn lại là nhánh số điện thoại.

#### Thêm số điện thoại — lối đi thứ ba

`ThemSdtChoKhach` (`112-222`). Hai lối cũ của ô cảnh báo là "vẫn tạo hồ sơ mới" (**tách đôi bệnh án**) và "bỏ dở". Tuyền 15/08: khách cũ gọi từ số mới là chuyện hằng ngày — phải gắn được số mới vào hồ sơ **CŨ** ngay tại đây.

- **Ở CẤP MODULE, không lồng trong form** (`108-111`): component lồng bị React dựng lại mỗi lượt vẽ, **mất chữ đang gõ**.
- **`goiY` chỉ truyền cho khối `trungTen`** (`1198` có, `1167` không): ở khối trùng SỐ, số đang gõ **đã là của hồ sơ này rồi** — thứ cần nhập là số KHÁC. Ở khối trùng TÊN, số đang gõ chưa thuộc về ai nên điền sẵn là đúng.
- Hỏi luôn `CHINH` hay `NGUOI_NHA` (`185-201`) vì hồ sơ vẽ hai loại ở hai dòng khác nhau — **phải hỏi ngay lúc ghi, không đoán**.

#### Lưu nháp

```ts
const hienTai = JSON.stringify(giaTri);
if (mocNhapRef.current === "") { mocNhapRef.current = hienTai; return; }
if (hienTai === mocNhapRef.current) return;
const coGiCuu = fullName.trim() || phone || cccd || vanDe;
if (!coGiCuu) return;
const t = setTimeout(() => {
  ghiNhap(window.localStorage, khoaNhapKhach, giaTri, Date.now());
  mocNhapRef.current = hienTai;
}, 1000);
```
`743-754`. `mocNhapRef` khởi tạo `""`; **lần chạy đầu chỉ ghi mốc rồi thoát** — form trống hoặc prefill từ URL thì "chưa ai gõ". `coGiCuu` chặn ghi nháp rỗng. Khoá `khoaNhap(staffId, "khach-moi", "form")` (`360`) — **theo người đăng nhập**, hạn 24h, `donNhapCu` dọn bản quá hạn lúc mount (`366`).

**Chỉ giữ phần HÀNH CHÍNH** (`353-359`): ngày/giờ/bác sĩ của lịch hẹn **không** khôi phục — chúng thường tới từ URL, và một khung giờ cũ khôi phục lại **có thể đã bị người khác giữ mất**. *"Bịa lại lựa chọn thời gian là sai hơn bắt chọn lại."*

Banner chỉ **NHẮC**, không tự đổ vào form (`1024-1026`): *"người trực có thể đang cố tình nhập một khách KHÁC."* Và `goToProfile` **xoá nháp trước khi điều hướng** (`794-798`): để lại thì lần mở sau mời khôi phục một khách đã nằm trong hệ thống, và người trực **tạo trùng**.

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai

- **Bác sĩ KHÔNG bắt buộc** (`902-910`): khách gọi đặt trước 2–3 tuần, lúc ấy lịch trực chưa công bố. Bắt chọn nghĩa là lễ tân phải **bịa một cái tên**, và cái tên bịa ấy **trông y hệt một quyết định thật** ở mọi màn sau.
- **Đặt lịch lỗi thì hồ sơ VẪN ĐÃ TẠO** (`723-729`): câu lỗi phải nói đúng điều đó — *"Đã tạo hồ sơ nhưng đặt lịch lỗi: … Mở hồ sơ để đặt lại."* `proceed` giữ người dùng ở lại form (`819-823`).
- **Cơ sở mặc định tính ra, không đặt bằng effect** (`828-836`): bản cũ dùng `useEffect` nhét `locations[0]` vào state — có **một nhịp** form ở trạng thái "chưa chọn cơ sở" dù danh sách đã có, bấm Lưu trúng nhịp đó rơi vào nhánh "Chưa chọn cơ sở khám". `onProvinceChange` chạy trong handler cũng vì lý do này (`376-378`).
- **Năm sinh bị KẸP về năm nay** (`1090-1096`) để không nhập được 3245; `< 1900` vẫn báo lỗi inline chứ không kẹp.

---

### 11.10. Bảy điều rút ra từ ba màn này

1. **Đơn vị làm việc là (khách, LƯỢT)**, không phải khách. Mọi biến, mọi prop, mọi truy vấn phải mang được vế thứ hai.
2. **Suy ra ≠ ghim.** `luotMacDinh` là suy ra và có quyền nhảy; `luotChon` là ghim và sống qua F5 nhờ URL.
3. **So mốc thời gian, đừng xếp thứ tự cứng** — cho chip trạng thái, cho "lịch sắp tới", cho `ket_thuc` của lượt.
4. **Hoàn tác ảnh hưởng phép ĐẾM, không ảnh hưởng phép KỂ.** Lọc ở nơi tiêu thụ, không lọc ở nguồn.
5. **Chưa biết ≠ trống.** `undefined` ≠ `[]`; "đang tải" phải có tone riêng; tập ca trực rỗng không được đọc thành "mọi bác sĩ đều nghỉ".
6. **Cảnh báo sai còn tệ hơn không cảnh báo** — nó dạy người dùng bỏ qua đúng loại cảnh báo ấy, rồi bỏ qua luôn lần thật.
7. **Sửa truy vấn của trang nào thì phải MỞ trang đó.** Gọi API của nó không phải là nghiệm thu.


---

## PHẦN 12. REALTIME, THÔNG BÁO VÀ VẬN HÀNH

Ba mảng trong phần này thật ra là **một đường ống duy nhất**: một hàng vừa được ghi
vào Postgres, và hai loại "người nghe" cần biết ngay — màn hình của nhân viên
(realtime) và nhóm Telegram của người trực (thông báo). Phần C và D là những gì giữ
cho đường ống ấy còn sống sau mỗi lần deploy.

---

### 12.0. Đường đi một sự kiện — từ ngón tay tới màn hình người khác

```
   [Người dùng bấm "Xác nhận đặt lịch"]
                │
                ▼
   Next.js route / server action ── ghi 2 hàng trong CÙNG một giao dịch
                │                     ├─ INSERT appointment
                │                     └─ INSERT event_log (event_published=FALSE)
                ▼
   ╔═══════════════════ POSTGRES ═══════════════════╗
   ║  trigger trg_notify_appointment (I/U/D)        ║
   ║  trigger trg_notify_event_log   (CHỈ INSERT)   ║
   ║        └─► notify_row_change()                 ║
   ║             PERFORM pg_notify(                 ║
   ║               'clinicai_changes',              ║
   ║               {"t":"<bảng>","c":"<clinic_id>"})║  ← bắn lúc COMMIT
   ╚════════════════════════╤═══════════════════════╝
                            │  MỘT kênh, HAI người nghe
            ┌───────────────┴────────────────┐
            ▼                                ▼
  ┌────────────────────┐          ┌──────────────────────────┐
  │ FastAPI            │          │ worker --relay           │
  │ ChangeBroker       │          │ conn.add_listener(...)   │
  │ .add_listener()    │          │ nen_danh_thuc(payload)?  │
  │ lọc theo clinic_id │          │  t=="event_log" && c==mình│
  │ → Queue(maxsize=8) │          │      → danh_thuc.set()   │
  └─────────┬──────────┘          └────────────┬─────────────┘
            │ GET /api/v1/events/stream        │ thức sớm (thay vì chờ 30s)
            │ text/event-stream                ▼
            ▼                        poll_and_deliver()
  ┌────────────────────┐             ├─ SELECT event_published=FALSE
  │ Next route handler │             ├─ pg_try_advisory_lock(event_id)
  │ /api/events/stream │             ├─ _lam_giau()  ← tra tên/giờ/dịch vụ
  │ gắn Bearer token   │             ├─ templates.render()
  │ chuyền res.body    │             ├─ send_telegram() (×3, backoff)
  └─────────┬──────────┘             └─ UPDATE event_published=TRUE
            ▼                                     │ (UPDATE này KHÔNG bắn notify)
  ┌────────────────────┐                          ▼
  │ EventSource        │                  📱 Nhóm Telegram
  │ addEventListener   │                     "📅 Lịch mới · 07:00 19/08"
  │ ("change")         │
  │ debounce 250ms     │
  │ → router.refresh() │  ⇢ nếu t=="work_roster" thì rung thêm CustomEvent
  └────────────────────┘     "clinicai:doi-ca" cho hai lưới đặt chỗ
            ▼
   [Màn hình đồng nghiệp bên cạnh tự cập nhật]
```

> **Ý cốt lõi:** chỉ có **một** kênh `pg_notify` cho cả hệ. Màn hình và relay Telegram
> nghe **cùng một tiếng chuông**, chỉ khác nhau ở bộ lọc. Không có RabbitMQ, không có
> Redis, không có dịch vụ Realtime nào ở giữa.

---

### A. REALTIME

### 12.1. `supabase/migrations/20260806000001_notify_change_for_live_screens.sql`

Đây là **gốc** của cả đường realtime. Trước đó hệ dùng Supabase Realtime.

```sql
PERFORM pg_notify(
    'clinicai_changes',
    json_build_object('t', TG_TABLE_NAME, 'c', v_clinic)::text
);
```

| Chi tiết | Giải thích |
|---|---|
| `SECURITY DEFINER` + `SET search_path` | Trigger chạy dưới quyền chủ hàm, và ghim `search_path` để không bị chiếm quyền qua một schema giả |
| `v_clinic := CASE WHEN TG_OP='DELETE' THEN OLD.clinic_id ELSE NEW.clinic_id END` | DELETE thì dữ liệu nằm ở `OLD`. Thiếu dòng này **mọi lần xoá đều mất tin báo** và màn hình giữ lại một hàng vừa biến mất (`...20260806000001...sql:27`) |
| `IF v_clinic IS NOT NULL` | Không có phòng khám thì không ai cần nghe |
| `RETURN NULL` | AFTER trigger — giá trị trả về không được dùng |
| Vòng `DO $$ ... FOREACH t IN ARRAY bang` | Gắn trigger cho **đúng 11 bảng có màn vẽ live**, bỏ qua bảng chưa tồn tại hoặc không có cột `clinic_id` thay vì làm hỏng cả chuỗi migration |

**VÌ SAO đổi khỏi Supabase Realtime.** Realtime đọc WAL qua một *replication slot*, mà tạo
slot cần quyền `REPLICATION` — database cho thuê **không cấp**. Đo trên Viettel IDC
06/08/2026: `pg_create_logical_replication_slot` bị từ chối. "Không phải trục trặc cấu hình
mà là chính sách, và AWS RDS hay Azure cũng vậy" (`...20260806000001...sql:3-6`).
`LISTEN/NOTIFY` là SQL thường, không đòi quyền nào → chạy được ở mọi nơi.

**VÌ SAO đặt ở trigger, không ở tầng dịch vụ.** Gọi `pg_notify` trong từng service thì đúng
cho tới lần đầu có người thêm một đường ghi mới mà quên gọi — và cái quên đó **im lặng**:
màn hình chỉ đơn giản là không cập nhật nữa, không ai thấy lỗi.

**VÌ SAO tin nghèo (chỉ tên bảng + clinic_id).** (1) `NOTIFY` có **trần 8000 byte**; một
hàng bệnh án có thể vượt → làm **HỎNG CẢ GIAO DỊCH GHI**, tức biến một tính năng hiển thị
thành lỗi mất bệnh án; (2) đẩy dữ liệu qua đây là mở một lối đọc **ngoài mọi lớp kiểm quyền
của API**.

### 12.2. `src/clinicai/core/change_broker.py` — một kết nối LISTEN, nhiều màn hình

| Thành phần | Giải thích |
|---|---|
| `CHANNEL = "clinicai_changes"` | Phải khớp tên trong migration — lệch một chữ là realtime chết trong im lặng |
| `QUEUE_SIZE = 8` | Hàng đợi mỗi màn hình. **Nhỏ có chủ ý**: nội dung tin không quan trọng, đầy thì bỏ tin mới — một màn chậm không được làm nghẽn màn khác |
| `RECONNECT_DELAY_S = 3.0` | Nối lại khi kết nối nghe rớt |
| `__init__(dsn)` | Gọi `normalize_dsn(dsn)` — xem bẫy bên dưới |
| `start()` / `stop()` | Tạo/huỷ task `change-broker`, đóng connection |
| `_run()` | Vòng giữ kết nối: `asyncpg.connect` → `add_listener` → ngồi im 1s/lần cho tới khi bị huỷ hoặc kết nối chết → `sleep(3)` → nối lại |
| `_on_notify(conn, pid, channel, payload)` | asyncpg gọi **ĐỒNG BỘ trên event loop** → không được `await` gì; dùng `put_nowait` và **bỏ qua khi đầy** |
| `subscribe(clinic_id)` | Tạo `asyncio.Queue(maxsize=8)`, bỏ vào `_subs[clinic_id]` |
| `unsubscribe(clinic_id, q)` | Bỏ hàng đợi, dọn key rỗng |
| `listener_count` | Đếm số màn đang mở — dùng cho ops |

```python
while not self._stopping:
    try:
        self._conn = await asyncpg.connect(self._dsn)
        await self._conn.add_listener(CHANNEL, self._on_notify)
```

`_run()` mở **kết nối RIÊNG, không lấy từ bể chung**: một kết nối đang LISTEN bị giữ
suốt đời tiến trình; mượn nó từ pool là vĩnh viễn bớt một chỗ của truy vấn thật, và
asyncpg cũng không hứa trả lại đúng kết nối ấy (`change_broker.py:87-89`).

> **Nhiều bản API chạy song song vẫn đúng.** `NOTIFY` phát tới MỌI kết nối đang LISTEN,
> nên mỗi bản API tự nhận và tự phát cho màn hình nối vào nó — khác hẳn cách đẩy tin
> trong bộ nhớ một tiến trình, thứ chỉ đúng khi có đúng một bản (`change_broker.py:19-22`).

### 12.3. `src/clinicai/api/v1/routers/events.py` — đầu ra SSE

| Thành phần | Giải thích |
|---|---|
| `HEARTBEAT_S = 20.0` | Proxy hay cắt kết nối im lặng sau 30–60s; một dòng bình luận rỗng `: nhip` đủ giữ, tốn vài byte |
| `stream(request, identity)` | Phụ thuộc `get_current_identity` → **máy chủ tự biết clinic_id từ token** |
| `yield b": mo dong\n\n"` | Báo mở dòng **ngay**, trước tin đầu tiên: trình duyệt biết kết nối sống, và proxy nào đệm sẵn đầu ra cũng bị đẩy đi |
| `if broker is None: return` | Không có bộ nhận tin thì **đóng luôn** cho trình duyệt rơi về nhịp dự phòng — "im lặng giữ một dòng chết là cách tệ hơn" (`events.py:47-50`) |
| `asyncio.wait_for(q.get(), timeout=HEARTBEAT_S)` | Có tin thì đẩy; hết 20s không tin thì đẩy nhịp |
| `finally: broker.unsubscribe(...)` | Đóng tab là hàng đợi được dọn |
| Header `X-Accel-Buffering: no` | Tắt đệm của nginx/Caddy — "đệm một dòng sự kiện là biến thứ tức thời thành thứ đến theo lô" |

**VÌ SAO SSE chứ không WebSocket** (`events.py:3-8`): việc cần làm ở đây là **một
chiều**. SSE đi trên HTTP thường nên qua được Caddy và mọi proxy mà không cần nâng cấp
giao thức, **tự nối lại khi rớt** (trình duyệt lo), và nhẹ hơn. WebSocket là công cụ cho
hội thoại hai chiều — dùng ở đây là trả giá cho một chiều mình không dùng.

### 12.4. `src/dashboard/app/api/events/stream/route.ts` — cầu nối bắt buộc

```ts
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 0;   // Next mặc định cắt route handler sau 15s
```

**VÌ SAO phải đi vòng qua đây:** trình duyệt mở SSE bằng `EventSource`, mà `EventSource`
**không đặt được header** — không gắn được `Authorization: Bearer`. Route này chạy trên
máy chủ nên gắn được (`route.ts:3-7`).

**ĐÃ CÂN NHẮC VÀ BỎ:** cho trình duyệt gọi thẳng FastAPI với token trong query string —
"làm thế là ghi token vào log truy cập của mọi proxy trên đường: đọc được, sống lâu, đủ
để đóng giả người dùng" (`route.ts:9-11`).

| Điểm | Giải thích |
|---|---|
| `await supabase.auth.getUser()` trước `getSession()` | `getSession()` chỉ đọc cookie; `getUser()` đổi refresh token lấy access token còn hạn |
| Không dùng `proxyJsonToBackend` | Hàm ấy đọc trọn body (`res.text()`) — đúng cho JSON, **treo mãi** với SSE. Phải chuyền thẳng `res.body` |
| `signal: request.signal` | Đóng tab → huỷ request → tín hiệu truyền tiếp lên FastAPI, không thì mỗi tab đóng để lại một dòng treo bên đó |

### 12.5. `src/dashboard/app/(dashboard)/RealtimeRefresher.tsx` — MỘT kênh, MỘT nhịp

| Hằng / hàm | Giải thích |
|---|---|
| `DEBOUNCE_MS = 250` | Gộp một chuỗi thay đổi của cùng thao tác thành một lần render. Bản cũ là 1200ms — "hơn một giây thuần chờ trên MỌI cập nhật" |
| `POLL_MS = 60_000` | Lưới an toàn khi dòng sự kiện rớt. Bản cũ 25s "tự nó là nguồn tải đều đặn lớn nhất của hệ thống" |
| `LIVE_TABLES` (15 bảng) | **Phải khớp** danh sách trong migration; subscribe thừa thì im lặng vô dụng, publish thừa thì Postgres phát cho thứ không ai nhìn |
| `bump()` | Xoá timer cũ, đặt timer mới gọi `router.refresh()` |
| `rungChuongCa()` | Debounce **riêng** rồi `dispatchEvent(SU_KIEN_DOI_CA)` |
| `es.addEventListener("change", ...)` | Parse `{t}`; `wanted.has(t)` → `bump()`; `t === "work_roster"` → rung chuông thêm |
| `catch { bump(); }` | Tin méo thì **cứ làm mới** — thà thừa một lượt render còn hơn để người dùng nhìn dữ liệu cũ |
| cleanup | `clearTimeout` + `clearInterval` + `es.close()` |

```tsx
const wanted = new Set(tables);
const es = new EventSource("/api/events/stream");
```

> **LỌC BẢNG Ở CLIENT, LỌC PHÒNG KHÁM Ở MÁY CHỦ.** Prop `clinicId` đã bị **bỏ**
> (06/08/2026): "một giá trị do trình duyệt gửi lên thì không phải là cái lọc, chỉ là một
> lời khai". Giữ lại một prop không còn tác dụng sẽ khiến người đọc sau tin rằng có một
> lớp lọc ở đây, và **tin sai theo hướng nguy hiểm** (`RealtimeRefresher.tsx:82-88`).

Comment đầu file còn ghi hai sự thật khó chịu: (1) trước đây **bốn** thứ cùng gọi
`router.refresh()` trên một trang, một tab để yên vẫn gõ vào Supabase **~30 truy vấn mỗi 25
giây** — "đó là phần lớn cảm giác *hệ thống chậm*"; (2) bản cũ **chưa từng thật sự là
realtime** — 20 bảng được subscribe không nằm trong publication `supabase_realtime`, mà
subscribe một bảng chưa publish thì **không báo lỗi, chỉ im lặng không bao giờ bắn**.

### 12.6. `src/dashboard/app/(dashboard)/dung-doi-ca.ts` — chuông cho dữ liệu client-fetch

```ts
export const SU_KIEN_DOI_CA = "clinicai:doi-ca";

export function useDoiCa(): number {
  const [seq, setSeq] = useState(0);
  ...
  return seq;   // bỏ vào deps của effect fetch là đủ
}
```

`router.refresh()` chỉ vẽ lại **server component**. Hai lưới đặt chỗ (`BookingHub`,
`CinemaSlotPicker`) sống bằng dữ liệu **trình duyệt tự hỏi** (`/api/appointments/quote`,
`/api/roster`) và giữ cache — nên quản lý xoá một ca xong, màn CSKH đã nhảy mà lưới đặt
lịch **vẫn vẽ ca cũ** cho tới khi đổi ngày hoặc F5 (Tuyền nghiệm thu 17/08/2026). Máy chủ
vẫn chặn cứng lúc đặt thật nên không đặt nhầm được — "đây là chuyện lớp vẽ nói dối, không
phải lỗ nghiệp vụ" (`dung-doi-ca.ts:11-12`).

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai (Realtime)

- **DSN sai scheme làm bộ nghe chết im lặng.** `.env` ghi `postgresql+asyncpg://` (dạng
  SQLAlchemy); `asyncpg.connect()` từ chối scheme ấy. Pool vẫn chạy vì nó có gọi
  `normalize_dsn`, còn `ChangeBroker` lúc đầu thì không → bộ nghe **chết ngay khi khởi
  động** và màn hình lặng lẽ rơi về nhịp dự phòng. Bắt được lúc chạy thử trên VPS
  (`change_broker.py:55-59`).
- **Hai danh sách bảng phải khớp nhau ở ba nơi**: migration gắn trigger, publication, và
  `LIVE_TABLES`. Lệch nhau là "cách realtime chết trong im lặng".
- **Không tự viết vòng nối lại trong `RealtimeRefresher`** — `EventSource` đã tự làm; viết
  thêm là hai vòng chạy song song.
- **Debounce chỉ giấu được độ trễ của người khác.** Muốn 0ms cho **chính người vừa bấm**
  thì vẫn phải cập nhật lạc quan tại chỗ bấm, không phải chờ tin quay về.

---

### B. THÔNG BÁO

### 12.7. `src/clinicai/worker.py` — ba chế độ trong một entrypoint

| Hàm / hằng | Giải thích |
|---|---|
| `main()` | `--pos-relay` → `_run_pos_relay`; `--relay` → `_run_relay`; còn lại → `_run_rabbitmq` (`worker.py:289-295`) |
| `HEARTBEAT_PATH` | Mặc định `/tmp/worker-alive` — file nhịp tim compose healthcheck đọc |
| `_beat()` | Ghi timestamp. **Không bao giờ fatal**: "một worker không được chết vì không ghi nổi file liveness; healthcheck đi cũ đã là tín hiệu đúng" |
| `RELAY_POLL_INTERVAL = 30` | Nhịp poll relay thông báo |
| `POS_RELAY_POLL_INTERVAL = 60` | "POS không nằm trên đường tới hạn, nên có thể báo thưa hơn" |
| `_run_relay()` | Chốt cờ → kiểm `TELEGRAM_CLINIC_ID` → mở pool → LISTEN → chạy bot lệnh song song → vòng poll |
| `_run_pos_relay()` | Vòng poll `pos_outbox`; "một POS hỏng không được kéo relay chết theo" |
| `_run_rabbitmq()` | Consumer cũ; nhịp tim riêng = "kết nối broker còn mở" |

**VÌ SAO healthcheck là file chứ không phải PID** (`worker.py:45-56`): `restart:
unless-stopped` chỉ khởi động lại worker có **tiến trình chết**. Nó không thấy kiểu hỏng
thật của một poll loop — tiến trình còn sống mà **vòng lặp ngừng quay**: một connection
không bao giờ timeout, một task chờ thứ sẽ không tới, một exception bị nuốt. "Container
báo healthy, Uptime Kuma xanh, và **không ai biết bệnh nhân ngừng nhận tin cho tới khi
một người trong số họ nói ra**."

**CHỐT CỨNG relay** (`worker.py:82-100`):

```python
if os.environ.get("NOTIFICATION_RELAY_ENABLED", "").strip().lower() != "true":
    raise SystemExit("notification-relay đang TẮT có chủ ý ...")
```

`profiles` của compose **không đủ** để coi là đã tắt: `--profile workers` bật một lúc cả
`worker`, `pos-relay` **và** `notification-relay`. Ai bật worker cho việc khác là relay đi
theo — và ngay lúc đó nó gặp **208 dòng `event_log` chưa publish còn tồn**, bắn cả 208 tin
trong mấy vòng poll đầu, gồm sự kiện từ nhiều ngày trước.

**Vòng LISTEN + đánh thức** (`worker.py:119-169`):

```python
nghe = await pool.acquire()
await nghe.add_listener("clinicai_changes", _khi_notify)
...
done, pending = await asyncio.wait(
    {cho_thuc, cho_dung}, timeout=RELAY_POLL_INTERVAL,
    return_when=asyncio.FIRST_COMPLETED)
if cho_thuc in done:
    danh_thuc.clear()
    await asyncio.sleep(0.3)      # nhịp thở gộp lô
```

- Connection LISTEN được **giữ riêng khỏi pool cho tới `finally`** — "listener sống bằng
  connection, trả về pool là điếc".
- `sleep(0.3)` sau khi thức: một thao tác đụng nhiều sự kiện thành **MỘT** lượt poll.
- Nhịp 30s vẫn giữ — nó là **lưới an toàn cho lúc connection LISTEN rớt**, không phải chỗ
  dựa duy nhất.
- Bot lệnh chạy **cùng process, cùng pool, cùng vòng đời**: `stop` là cả hai cùng về.

### 12.8. `supabase/migrations/20260815000003_notify_event_log_cho_relay.sql` — CHỈ INSERT

```sql
DROP TRIGGER IF EXISTS trg_notify_event_log ON public.event_log;
CREATE TRIGGER trg_notify_event_log
    AFTER INSERT ON public.event_log
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
```

> **ĐÂY LÀ CHỖ DỄ HỎNG NHẤT NẾU AI "DỌN DẸP" CHO GIỐNG CÁC BẢNG KHÁC.** Mọi bảng live khác
> đều gắn `AFTER INSERT OR UPDATE OR DELETE`. Riêng `event_log` **chỉ INSERT** — vì relay
> xử lý xong thì `UPDATE event_published = TRUE` lên **chính bảng này**. Nghe cả UPDATE là
> relay **tự đánh thức mình sau mỗi lần gửi**: một vòng lặp poll rỗng vô tận, mỗi tin gửi
> đi kèm một cú quét thừa (`...20260815000003...sql:7-10`).

Luật này có **test canh** (`src/tests/unit/test_notification_relay.py:263`): đọc thẳng file
SQL, khẳng định có `AFTER INSERT ON public.event_log` và **không có chữ `UPDATE`** trong
phần sau `CREATE TRIGGER`.

### 12.9. `nen_danh_thuc()` — bộ lọc đánh thức

```python
def nen_danh_thuc(payload: str, clinic_id: str) -> bool:
    try:
        d = json.loads(payload)
    except (ValueError, TypeError):
        return True                      # tin méo → thức cho chắc
    return d.get("t") == "event_log" and str(d.get("c")) == clinic_id
```

Kênh `clinicai_changes` chở thay đổi của **mọi** bảng live (màn hình cũng nghe kênh này);
relay chỉ quan tâm `event_log` của **đúng phòng khám mình**. Tin méo thì đánh thức — "một
cú quét thừa rẻ hơn một sự kiện nằm chờ 30s chỉ vì payload lạ", cùng triết lý với `catch {
bump() }` bên `RealtimeRefresher` (`notification_relay.py:48-60`).

Test canh cả bốn ca: đúng bảng đúng phòng khám → `True`; `appointment` → `False`; phòng
khám khác → `False`; chuỗi không phải JSON → `True`.

### 12.10. `src/clinicai/services/notification_relay.py`

| Hàm / hằng | Giải thích |
|---|---|
| `BATCH_SIZE = 50` | Số sự kiện chưa publish xử lý mỗi vòng |
| `MAX_RETRIES = 3` | Số lần gửi tối đa mỗi sự kiện trong một vòng |
| `RETRY_BACKOFF_SECONDS = 0.5` | Chờ giữa hai lần thử, **nhân đôi**: 0.5s rồi 1.0s |
| `nen_danh_thuc(payload, clinic_id)` | Bộ lọc đánh thức — §12.9 |
| `_lam_giau(conn, ...)` | Đắp tên/giờ/dịch vụ vào payload **trước khi** soạn tin — §dưới |
| `poll_and_deliver(pool, clinic_id)` | Vòng chính: SELECT → khoá → làm giàu → render → gửi → đánh dấu |
| `_mark_published(conn, event_id, clinic_id)` | `UPDATE event_log SET event_published = TRUE` (có `clinic_id` — không bao giờ chạm phòng khám khác) |

**`_lam_giau` — vì sao tra database NGAY LÚC GỬI.** `event_log.payload` cố ý chỉ mang ID
(nó là **sổ sự kiện**, không phải bản sao hồ sơ) — nhưng một tin nhắn toàn UUID thì không
ai đọc được. Tra ngay lúc gửi thay vì lúc ghi có hai cái lợi: **tin kể trạng thái mới
nhất**, và người ghi sự kiện không phải gánh thêm nghĩa vụ "nhớ đủ cột cho Telegram"
(`notification_relay.py:72-81`).

```python
return {**{k: v for k, v in dap.items() if v is not None}, **payload}
```

Dòng cuối `_lam_giau`: **payload thắng** — sự kiện nói gì thì giữ nguyên, chỉ đắp chỗ
trống. Truy vấn `LEFT JOIN` sang `patient`, `staff` (hai lần: bác sĩ hiện tại và
`bac_si_da_go`), `service_type`; giờ được đổi sang `CLINIC_TZ` rồi `strftime("%H:%M %d/%m")`.
Và **KHÔNG đắp số điện thoại** — comment trỏ thẳng sang `notification_templates`.

**Chống hai relay gửi trùng** (`notification_relay.py:160-186`):

```python
event_id = str(row["event_id"])          # ép về chuỗi MỘT LẦN ở đây
claimed = await conn.fetchval(
    "SELECT pg_try_advisory_lock(hashtextextended($1::text, 0))", event_id)
if not claimed:
    continue
```

Sau khi giành được khoá còn **đọc lại** `NOT event_published`: một relay khác có thể đã
hoàn tất **sau** lần `SELECT` gom lô nhưng **trước** lúc mình lấy được khoá. `finally` luôn
`pg_advisory_unlock`.

> **Sự cố thật:** cột `event_id` là `uuid`, asyncpg trả về `UUID` object, mà cả ba câu SQL
> đều bind nó vào `$1::text` → `DataError "expected str, got UUID"`. Lỗi nằm sẵn từ Bài 23
> và **chỉ lộ ra ở lần chạy THẬT đầu tiên (15/08/2026)** — mọi test trước đó mock
> `fetchval` nên không con đường nào chạm tới encoder của asyncpg (`notification_relay.py:154-159`).

**VÌ SAO có backoff** (`notification_relay.py:36-44`): *"BA LẦN THỬ LIÊN TIẾP KHÔNG NGHỈ LÀ
MỘT LẦN THỬ."* Vòng cũ gọi `send_telegram()` ba lần trong vài mili-giây. Thứ làm hỏng lần
một — mạng chớp, Telegram trả 429, provider đang khởi động lại — vẫn còn nguyên ở lần hai
và ba, nên chúng chỉ **đẩy thêm request vào đúng chỗ đang quá tải**. Với `SEND_TIMEOUT =
10s`, một sự cố kéo dài làm mỗi sự kiện ngốn tới **30 giây** của vòng poll. Backoff cố ý
để ngắn: hỏng lâu thì sự kiện nằm lại chờ vòng sau — "đó mới là chỗ retry thuộc về".

Hai chi tiết nhỏ mà đáng: `if attempt < MAX_RETRIES` mới ngủ (không ngủ sau lần cuối), và
`result.get("skipped")` thì **break ngay** — thiếu cấu hình provider không thể tự lành
trong một vòng poll.

### 12.11. `src/clinicai/services/notification_templates.py` — 5 loại tin

| Hàm | Giải thích |
|---|---|
| `_LY_DO_HUY_NGAN` | 6 nhãn lý do huỷ, **rút gọn** cho một dòng tin. Cố ý **không import** từ `booking_service.LY_DO_HUY`: tin nhắn cần câu ngắn, danh mục gốc là câu đầy đủ cho ô chọn — hai nhu cầu khác nhau |
| `_khach(payload)` | `"Tên (MÃ)"`, thiếu tên thì `"—"` |
| `_gio(payload)` | `gio_kham` hoặc `"—"` |
| `lich_moi` | `📅 Lịch mới · giờ` + khách · dịch vụ · BS |
| `huy_lich` | `❌ Huỷ lịch` + khách · lý do rút gọn |
| `doi_lich` | `🔁 Đổi lịch · giờ mới` |
| `xoa_ca_bac_si` | `⚠️ Xoá ca bác sĩ X · lịch … đã huỷ` + **"gọi khách đặt lịch mới"** — tin đáng gọi nhất |
| `ca_moi_cho_xep` | `🩺 BS X có ca sáng ngày …` + số lịch đang chờ xếp. Payload **đủ ngay từ lúc ghi**, không đi qua đường làm giàu của lịch hẹn |
| `TEMPLATES` | Registry `event_type → hàm`. 5 khoá |
| `render(event_type, payload)` | Không có trong registry → **`None`** |

Sự kiện ngoài registry trả `None` → relay đánh dấu đã-xử-lý và đi tiếp. **Im lặng có chủ
ý**: "nhóm nhận đủ những tin đáng nhấc máy, không nhận nhật ký hệ thống"
(`notification_templates.py:76-78`).

> ### 🔒 LUẬT TUYỆT ĐỐI
> **KHÔNG BAO GIỜ đưa số điện thoại / CCCD / địa chỉ vào tin.** "Telegram là máy chủ bên
> thứ ba, tin nhắn sống **ngoài tầm RLS**. Tên + mã hồ sơ là đủ để người trực mở đúng khách
> trong hệ thống — tra cứu thật diễn ra Ở TRONG hệ thống" (`notification_templates.py:14-16`).

Luật này **có test canh** (`test_notification_templates.py:79`) — và nó canh bằng cách
đọc **mã nguồn** chứ không phải đầu ra:

```python
ma = inspect.getsource(mau)
assert "phone" not in ma.replace("KHÔNG BAO GIỜ đưa số điện thoại", ""), (
    "mẫu tin chạm tới trường phone — Telegram là bên thứ ba, cấm")
```

Đọc source thay vì render một payload mẫu là đúng: một payload mẫu chỉ chứng minh **một**
đường đi không rò; đọc source chặn **mọi** đường, kể cả nhánh chưa ai gọi tới.

**LỊCH SỬ ĐÁNG NHỚ.** Bản đầu (Bài 23) soạn tin cho **KHÁCH** ("Xin chào Quý khách…") nhưng
cấu hình chỉ có **một** `TELEGRAM_CHAT_ID` — một nhóm nội bộ, nên ai đọc cũng thấy sai vai;
và payload thật chỉ mang ID nên "ngày `<b></b>` lúc `<b></b>`" render ra **chuỗi rỗng** (đo
staging 15/08/2026). Nay tin viết cho **NGƯỜI TRỰC**, thiếu khoá thì `"—"` chứ **không bịa**.

### 12.12. `src/clinicai/services/providers/telegram.py` — lớp gửi

| Thành phần | Giải thích |
|---|---|
| `TELEGRAM_API`, `SEND_TIMEOUT = 10.0` | Endpoint + timeout mỗi lần gửi |
| `send_telegram(message)` | **Không raise** — trả dict, caller lo retry |
| Thiếu token/chat_id | `{"ok": False, "skipped": True}` — relay để sự kiện lại chờ lần chạy đã sửa cấu hình |
| `cac_kenh = chat_id.split(",")` | **Nhiều kênh**: chat riêng của Tuyền + nhóm "MVP2: Clinic AI" |
| `ket_cuoi` | Chỉ `ok` khi **tất cả** kênh cùng nhận |
| `parse_mode: "HTML"` | Vì template dùng `<b>` |

> "Thiếu một kênh là relay giữ sự kiện lại thử tiếp, chấp nhận **hiếm hoi trùng tin** ở
> kênh đã nhận còn hơn một kênh **lặng lẽ không bao giờ được báo**" (`telegram.py:33-37`).

### 12.13. `src/clinicai/services/telegram_bot.py` — nửa kia của kênh

Relay đẩy tin **ra**; module này nghe lệnh **vào** (Tuyền 15/08/2026: *"mọi thông tin về
hệ thống tích hợp vào bot"*).

| Hàm / hằng | Giải thích |
|---|---|
| `POLL_TIMEOUT = 25` | Long-poll `getUpdates`: Telegram **giữ kết nối tới 25s** → gần như realtime mà không quay tít |
| `MENU_LENH` | 3 lệnh, đăng ký lại **mỗi lần khởi động** |
| `_HEALTH` | `http://api:8000/health/db` và `http://dashboard:3000/health` — endpoint **nội bộ trong mạng compose**, cùng nguồn Uptime Kuma theo dõi |
| `_token()` / `_chat_ids()` | Đọc env; `TELEGRAM_CHAT_ID` là danh sách phẩy |
| `doc_lenh(text)` | `"/trangthai@ten_bot arg"` → `"trangthai"`; chữ thường → `None` |
| `_kham_suc_khoe(pool, clinic_id)` | Gọi 2 endpoint + đếm `event_log` chưa publish |
| `_con_so_hom_nay(pool, clinic_id)` | 5 con số theo **ngày VN** (`AT TIME ZONE 'Asia/Ho_Chi_Minh'`) |
| `_giup_do()` | Danh sách lệnh |
| `_tra_loi(...)` | Router lệnh; lệnh lạ → `None` (im lặng) |
| `_gui(client, chat_id, text)` | Trả lời về **đúng kênh vừa hỏi** — "hỏi trong nhóm mà đáp vào chat riêng thì cả nhóm tưởng bot chết" |
| `_dang_ky_menu(client)` | `setMyCommands` — dọn menu rác của project cũ, tự lành sau mỗi deploy |
| `_offset_bo_ton_dong(client)` | Bỏ qua lệnh gõ **trước** khi bot khởi động |
| `bot_lenh_loop(pool, clinic_id, stop)` | Vòng long-poll chính |

```python
chat = str((msg.get("chat") or {}).get("id", ""))
if chat not in kenh_duoc_phep:
    logger.warning("bot_lenh_nguoi_la", chat_id=chat)   # lờ đi, chỉ ghi vết
    continue
```

**AN NINH** (`telegram_bot.py:15-18`): chỉ trả lời đúng `TELEGRAM_CHAT_ID` đã cấu hình.
"Bot đọc được con số vận hành của phòng khám, không phải chỗ cho người lạ hỏi." Và: **chữ
người dùng gõ là DỮ LIỆU** — chỉ so khớp tên lệnh, **không bao giờ đem đi thực thi**.

`_offset_bo_ton_dong` giải quyết một lỗi tinh vi: "trả lời một câu hỏi của **hôm qua** bằng
số liệu **hôm nay** là đưa tin sai mà không ai biết".

`/homnay` **chỉ con số — không tên, không SĐT**: cùng luật với `notification_templates`.
Có test canh (`test_telegram_bot.py:52` — `test_hom_nay_chi_con_so_khong_danh_tinh`).

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai (Thông báo)

- **Hai người gác nói hai chuyện.** Đo 15/08: Kuma nói *Up*, bot phán ❌ **cùng một
  endpoint** — chỉ vì dashboard `/health` trả **307** rồi mới tới 200 và bot không đi theo
  chuyển hướng. Sửa: `follow_redirects=True` + nhận cả họ 2xx (`telegram_bot.py:84-87`).
  Cùng lỗi lặp lại ở healthcheck của Uptime Kuma trong compose — `curl -f` coi 3xx là hỏng.
- **`profiles` không phải là công tắc tắt.** Xem `NOTIFICATION_RELAY_ENABLED` §12.7.
- **Mock che mất lỗi encoder.** Test mock `fetchval` không bao giờ chạm asyncpg thật → bug
  `UUID vs str` sống tới lần chạy production đầu tiên.
- **Trigger `event_log` nghe UPDATE = vòng vô hạn.** Đã có test canh, nhưng luật này phải
  nằm trong đầu người sửa migration.

---

### C. VẬN HÀNH

### 12.14. `docker-compose.yml` — một file, hai môi trường

```
PROD    : docker compose --env-file .env.prod    -p clinicai_prod    up -d
STAGING : docker compose --env-file .env.staging -p clinicai_staging up -d
```

| Dịch vụ | Profile | Vai trò |
|---|---|---|
| `caddy` | (mặc định) | **Dịch vụ DUY NHẤT gắn cổng công cộng**. TLS/ingress |
| `dashboard` | (mặc định) | Next.js standalone, UI only. `depends_on: api (healthy)` |
| `api` | (mặc định) | FastAPI — toàn bộ logic. Healthcheck `/health/db` |
| `worker` | `workers` | Consumer RabbitMQ (legacy) |
| `pos-relay` | `pos` | Đẩy hoá đơn/kho sang POS (ADR-0010) |
| `notification-relay` | `workers`, `notifications` | Relay Telegram |
| `rabbitmq` | `workers` | Broker (opt-in) |
| `uptime-kuma` | (mặc định) | Giám sát, bind `127.0.0.1` |
| `dozzle` | (mặc định) | Xem log, bind `127.0.0.1`, mạng **monitoring** riêng |
| `cloudflared` | `cloudflare` | Tunnel ra Internet |

**`x-clinic-service-defaults`** (anchor YAML dùng chung): giới hạn log `10m × 5` ("bound
log growth protects the single host from an incident filling its SSD"),
`no-new-privileges:true`, và `init: true` để dọn tiến trình con mồ côi.

**Healthcheck của ba relay** đều là cùng một dòng shell:

```yaml
test: ["CMD-SHELL", "test $$(( $$(date +%s) - $$(cat /tmp/worker-alive 2>/dev/null || echo 0) )) -lt 180"]
```

Cửa sổ 180s = **6 lần** `RELAY_POLL_INTERVAL` (30s) — "đủ rộng để một lần poll chậm không
báo động, đủ hẹp để một relay đứng hình bị phát hiện trong vài phút". `pos-relay` dùng 300s
vì nhịp của nó là 60s.

**Ba chi tiết đã cắn, nay là comment trong file:**

1. **`NEXT_PUBLIC_SUPABASE_URL` bị nung vào bundle.** Trước dùng thẳng `${SUPABASE_URL}` — ở
   staging là `host.docker.internal:54321`, chỉ phân giải **bên trong container**. Nung vào
   bundle JS nên **mọi trình duyệt** không gọi nổi Supabase: realtime không cập nhật, nút
   Thoát không ăn, quên mật khẩu hỏng. **Đăng nhập vẫn chạy vì là server action — nên lỗi
   này im lặng** (`docker-compose.yml:89-96`).
2. **Ổ bind phải dùng đường dẫn tương đối** (ADR-0013): `/Users/...` viết cứng làm `up` hỏng
   trên VPS hoặc **âm thầm mount một thư mục rỗng thuộc root**.
3. **Biến trong env-file không tự vào container** — nó chỉ **nội suy trong chính file
   compose**; muốn vào trong phải liệt kê ở `environment:`. Thiếu bước này Caddy nhận chuỗi
   rỗng rồi **chết ngay**: *"basic_auth: username and password cannot be empty"*.

**Mạng `supabase` khai `external: true`** vì do compose file **khác** tạo, và **tên theo
biến** `SUPABASE_NETWORK` — để staging nối vào bộ Supabase riêng, không phải bộ của phòng
khám đang chạy thật.

### 12.15. `caddy/Caddyfile` — cổng vào duy nhất

| Khối | Giải thích |
|---|---|
| `{ admin off }` | Tắt API quản trị của Caddy |
| `{$SITE_ADDRESS}` | `:80` → TLS do tunnel lo (mặc định); một tên miền → Caddy tự xin Let's Encrypt |
| `header { ... }` | HSTS 1 năm, `nosniff`, `X-Frame-Options DENY`, `Referrer-Policy`, `Permissions-Policy` khoá camera/mic/GPS, `-Server` (không lộ stack) |
| `handle /health` | `respond "ok" 200` — cho healthcheck compose, chạy được cả ở chế độ `:80` |
| `@dangnhap path /auth/v1/token*` | → `auth-guard` (nginx nhỏ chặn dò mật khẩu) |
| `@supabase path /auth/v1/* /rest/v1/* /realtime/v1/*` | → gateway Supabase; `handle` (**không** `handle_path`) để giữ nguyên tiền tố |
| `handle { reverse_proxy dashboard:3000 }` | Còn lại → Next.js. **API không bao giờ lộ ra ngoài** |

**VÌ SAO có `auth-guard` riêng.** Đo 12/08/2026: **10 lần đăng nhập sai liên tiếp vào PROD
đều lọt**, không lần nào bị chặn. GoTrue v2.177.0 không có giới hạn nào cho
`grant_type=password` (đã dò chuỗi trong binary), Caddy bản gốc không có module giới hạn,
và cổng Supabase cũng là Caddy (`Caddyfile:57-62`).

**VÌ SAO chỉ `/auth/v1/token`, không phải cả `/auth/v1/*`**: đổi mật khẩu, đăng xuất đều
nằm trong `/auth/v1` và không phải chỗ để dò — "kéo hết qua bộ chặn là mở rộng vùng có thể
hỏng mà không đổi lại được gì". Ngưỡng đặt rộng (20 lần/phút, dồn 10) vì **cả phòng khám
dùng chung một địa chỉ IP**.

> **Tên gateway theo biến, không ghi cứng.** Ghi cứng `clinicai_supabase_gateway` nghĩa là
> bản staging sẽ gọi thẳng vào database của phòng khám **đang chạy thật**. Lần dựng staging
> đầu tiên nó lỗi 502 chứ không rò sang prod, "**chỉ vì staging không được nối vào mạng của
> prod; đó là may, không phải thiết kế**" (`Caddyfile:47-53`).

### 12.16. `scripts/deploy-backend.sh` — 6 bước, có đường lùi

| Bước | Nội dung |
|---|---|
| **[1/6]** verify | Từ chối worktree bẩn; kiểm ref (`prod:main`, `staging:staging-*`); kiểm `APP_ENV` / `COMPOSE_PROJECT_NAME` / `IMAGE_TAG`; 6 biến bắt buộc không được rỗng hay còn `<placeholder>`; `mkdir -p` ổ bind; **cảnh báo migration chưa áp** |
| **[2/6]** snapshot | Ghi lại image id hiện tại + đọc `.active-state-<env>` (thư mục source + env file của bản đang chạy) |
| **[3/6]** build | `compose build`; rồi `remove_disabled_services` gỡ container của profile vừa bị tắt |
| **[4/6]** up -d | `\|\| UP_OK=0` — **không để `set -e` giết script** |
| **[4b]** relay | Dựng lại `notification-relay` nếu env bật cờ |
| **[5/6]** health | 24 vòng × 5s ≈ 120s; hỏng → **rollback** |
| **[6/6]** ghi state | Lưu `.active-state-<env>`, rồi `docker builder prune` |

**Khoá deploy** ngay đầu file: `mkdir "$LOCK_DIR"` (atomic) + `trap ... EXIT INT TERM`.

**Đóng băng env cho từng bản phát hành:** `ENV_FILE="${RELEASE_ENV_DIR}/${RELEASE_SHA}-${ENV_HASH}.env"`
— tên gồm **SHA của code** và **hash của env**, thư mục `chmod 700`, file `chmod 600`. "A
rollback must never reuse a newly edited/broken env file" (`deploy-backend.sh:86-87`).

**VÌ SAO bắt lỗi `up` thay vì để `set -e` dừng** (`deploy-backend.sh:281-284`): `set -e` sẽ
bỏ qua đoạn rollback bên dưới và **để production NẰM SẤP** — đúng cái mà rollback sinh ra
để chặn. "Một bản phát hành không khởi động nổi chính là lúc cần bản cũ nhất."

**Bước hồi sinh relay [4b]** (`deploy-backend.sh:291-301`):

```bash
if grep -q '^NOTIFICATION_RELAY_ENABLED=true' "$ENV_FILE"; then
  "${COMPOSE[@]}" --profile notifications up -d notification-relay \
    || echo "!! relay up failed — tin Telegram sẽ dồn hàng chờ, dựng tay sau"
fi
```

`up -d` **chỉ dựng profile mặc định**; relay nằm trong profile `notifications` nên **mỗi
lần deploy nó bị bỏ rơi**. Đo 17/08/2026: sau deploy, relay biến mất và **57 sự kiện xếp
hàng câm lặng** cho tới khi có người dựng tay. Và chỉ dựng khi env đã bật cờ — staging chưa
bật mà cứ dựng thì worker tự `SystemExit` và `restart: unless-stopped` biến nó thành
**crash-loop**.

**VÌ SAO migration chạy TRƯỚC deploy code.** Đầu file ghi rõ: *"DB migrations are NOT run
here — apply schema separately + reviewed via Supabase CLI"*. Lý do: schema **cần người
xem**, deploy thì không. Nhưng tách mà không kiểm nghĩa là **thứ tự đúng phụ thuộc vào trí
nhớ của người bấm** — nên có thêm bước cảnh báo:

> **Sự cố 06/08.** Deploy một bản code đọc **tám cột mới** của bảng `staff` trong khi
> migration tạo chúng **chưa** được áp. `/api/v1/staff` trả 500, màn Quản lý nhân sự trắng
> — và **không có gì trong quy trình deploy nói ra, vì health check vẫn xanh: `/health`
> không chạm bảng đó** (`deploy-backend.sh:201-213`).

Cảnh báo này **không chặn** (có lần deploy cố ý đi trước migration), nhưng nó phải nói ra,
và nói **trước khi dựng ảnh**.

**Dọn cache builder đặt SAU bước xác minh** (`deploy-backend.sh:384-396`): đo 08/08/2026
trên VPS — **408 mục, 30,03 GB**, không mục nào đang dùng, chiếm 30 trong 33 GB đã dùng của
cả ổ. Đặt trước bước xác minh thì lần rollback ngay sau đó phải dựng lại từ đầu, "đúng lúc
đang hỏng và đang vội".

### 12.17. `scripts/backup-db.sh` + `scripts/restore-drill.sh`

| Script | Vai trò |
|---|---|
| `backup-db.sh` | `pg_dump` schema `public` → gzip → `~/backups/clinicai/`, giữ 7 bản, tuỳ chọn đẩy lên R2 qua rclone. **Kèm một tệp thứ hai** chứa `auth.users` + `auth.identities` |
| `verify-backup.sh` | Kiểm file còn mới và nguyên vẹn |
| `restore-drill.sh` | **Khôi phục thật** vào một database dùng-một-lần rồi khẳng định hình dạng dữ liệu |

**VÌ SAO phải sao lưu cả `auth`.** Câu đầu file từng ghi "auth identities … require Supabase
PITR/backup" — đúng thời database còn ở Supabase cloud. Từ 06/08/2026 hệ tự dựng GoTrue,
nên **không còn ai sao lưu hộ phần auth** — "nếu file này không mang nó thì không ai mang
cả, và khôi phục xong sẽ là một phòng khám **đủ dữ liệu mà không ai đăng nhập được**"
(`backup-db.sh:2-8`).

**VÌ SAO cần diễn tập khôi phục** (`restore-drill.sh:5-14`): `backup-db.sh` chỉ kiểm **kho
lưu** — gzip toàn vẹn, sha256 khớp manifest, grep dấu hiệu hoàn tất. Không phép kiểm nào
từng **khôi phục** thứ gì, nên "backup verified" xưa nay chỉ có nghĩa "file **trông giống**
một dump" — và **một dump hỏng giữa chừng vẫn qua được tất cả**. Drill trả lời đúng câu hỏi
duy nhất quan trọng vào buổi sáng máy chết: *chạy cái này vào database rỗng, tôi có lấy lại
được phòng khám không?* — khôi phục thật rồi khẳng định số hàng và các bảng giữ bệnh nhân +
tiền, để một dump âm thầm cụt bị nhìn thấy thay vì làm người ta yên tâm.

Drill còn ghi rõ những gì bản dump **không** chứa (vì `--schema=public --no-owner --no-acl`):
schema `auth` + `auth.uid()` mà mọi RLS policy gọi; ba role `authenticated/anon/service_role`;
bốn extension `unaccent, pg_trgm, btree_gist, pgcrypto`. Supabase thật có sẵn hết, Postgres
trần thì không — drill tự cài từ chính file trong repo và **nói ra**.

### 12.18. `.github/workflows/cd.yml` — hai đường khác nhau

```
tag staging-*  → staging, TỰ ĐỘNG
main           → prod, PHẢI BẤM NÚT, chỉ trong khung 1h–4h sáng
```

| Bước | Giải thích |
|---|---|
| `workflow_run` **không lọc `branches:`** | Với một lần đẩy **TAG**, GitHub đặt tên TAG vào `head_branch` — lọc theo nhánh sẽ **im lặng bỏ qua mọi lần deploy staging** |
| `head_repository.full_name == github.repository` | Kho này **công khai**: ai cũng fork và chạy CI được, mà job này chạy trên máy có **khoá thật** của phòng khám |
| Bước `freshness` | Từ chối một commit **đã bị vượt qua** — deploy `head_sha` cũ trông y như hệ thống tự lùi bản, "rất khó đoán ra lúc đang có sự cố" |
| Dùng `curl` chứ không `gh` | Runner tự quản trên VPS **không có `gh`** — lần chạy đầu sau khi cài runner đã đỏ đúng vì thế |
| `path: release-<env>-<sha>` | Mỗi bản một thư mục riêng, không ghi đè → rollback không phụ thuộc thư mục còn nguyên |
| Khung giờ prod | `gio=$(TZ=Asia/Ho_Chi_Minh date +%H)` — **giờ Việt Nam, không phải giờ máy chủ**: "1h sáng của nó là 8h sáng của phòng khám, đúng giờ đông khách nhất" |
| Ô `ly_do_vuot_khung_gio` | Cửa vượt cho lúc cháy nhà. **Không im lặng** — lý do vào `::warning::` của lần chạy |
| `concurrency: clinicai-vps-deploy` | Prod và staging dùng chung một máy Docker → xếp hàng, `cancel-in-progress: false` |

Bí mật **không nằm trong cây mã nguồn**: chúng ở `/home/clinicai/clinicai` trên máy chủ và
chỉ được truyền vào bằng `CLINIC_ENV_DIR`.

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai (Vận hành)

- **CD nằm im không phải vì lỗi.** Nó trỏ `runs-on: [self-hosted, macmini]` trong khi hệ đã
  sang VPS từ 07/08 → nhãn trỏ vào cỗ máy không còn nhận việc (`cd.yml:12-17`). Thứ duy nhất
  còn trỏ về Mac là bản sao lưu hằng đêm — **và đó là chủ ý: bản sao phải nằm ở máy khác với
  thứ nó sao lưu**.
- **Healthcheck của chính hệ giám sát bị sai.** `wget` **không có** trong ảnh
  `louislam/uptime-kuma` → container đứng `unhealthy` vĩnh viễn dù Kuma vẫn phục vụ bình
  thường. "Một cái đèn đỏ không bao giờ tắt thì chẳng ai còn nhìn nó — và nó là công cụ
  GIÁM SÁT" (`docker-compose.yml:308-318`).
- **`compose up` không gỡ container của profile vừa tắt** → phải có `remove_disabled_services`.
- **`stat` có hai phương ngữ không tương thích** và dạng BSD-first **không chỉ lỗi trên
  Linux mà trả lời SAI** (`scripts/tests/test-infra-safety.sh:22-28`).

---

### D. KIỂM THỬ — BỐN LỚP

| Lớp | Chạy ở đâu | Bắt được gì | **Không** bắt được gì |
|---|---|---|---|
| **1. pytest (unit)** | job `backend`, `-m "not db and not integration"`, `--cov-fail-under=80` | Logic thuần Python: template, bộ lọc, backoff, giành khoá | Bất cứ thứ gì bị mock — xem bug `UUID vs str` |
| **2. Test ranh giới frontend** | job `frontend`, `node --test tests/*boundary.test.mts` (~40 file) | Logic nghiệp vụ rò vào TSX, quyền truy cập màn, hình dạng lỗi API | Hành vi runtime thật của trình duyệt |
| **3. SQL test trên Postgres thật** | job `database`, Postgres 17 dịch vụ | RLS, ràng buộc đa phòng khám, migration re-appliable | Code ứng dụng |
| **4. Kiểm hạ tầng** | job `infra-safety` + `portability` | Script phá huỷ, đường dẫn ghi cứng, ảnh amd64, container boot được | Dữ liệu thật, tải thật |

### 12.19. Năm job của `.github/workflows/ci.yml`

| Job | Canh cái gì |
|---|---|
| `backend` | `ruff check` + **`ruff format --check`** + `mypy` + **tenant-scope audit** + pytest ≥80% coverage |
| `frontend` | `tsc --noEmit` + `lint --max-warnings=0` + 5 bộ test (`audit`, `ops`, `boundary`, `roster`, `luu-nhap`) + `next build` |
| `infra-safety` | `./scripts/tests/test-infra-safety.sh` — smoke test **tất định** cho các script phá huỷ |
| `portability` | Không có đường dẫn `/Users/` hay `/home/<ai>/`; compose resolve được từ `.env.*.example`; build **linux/amd64**; ảnh **thật sự** là amd64; api và dashboard **boot được và trả lời health** |
| `database` | Migration/seed phải là **SQL thuần**; áp toàn chuỗi migration; migration từ 20260730 phải **áp lại được lần hai**; chạy mọi `supabase/tests/*.sql` |

**Tenant-scope audit** (`ci.yml:52-57`): backend nối database bằng **chủ sở hữu**, nên RLS
**không áp cho nó** — một truy vấn nhắc tên bảng thuộc phòng khám mà thiếu `clinic_id` sẽ
đọc **mọi phòng khám**. Job này giữ con số trong lúc nó đi xuống 0, bắt buộc phải xong
trước khi có phòng khám thứ hai (ADR-0009).

**"Migrations phải là SQL thuần"** (`ci.yml:259-268`): meta-command của psql (`\restrict`,
`COPY ... FROM stdin`) là cú pháp **client**. psql chạy được, **Supabase CLI thì không** —
nên một file sinh từ `pg_dump` có thể qua mọi test ở đây mà vẫn làm `supabase db push` chết
ở dòng 1.

**"Migrations phải re-appliable"** (`ci.yml:280-289`): `db push` có retry, và **diễn tập
khôi phục phát lại migration** — nên migration mới phải an toàn khi chạy hai lần. Migration
cũ đã ở production thì **không sửa ngược**.

**`portability` — vì sao tồn tại** (`ci.yml:114-117`): ADR-0013 — "Mac mini là một bản triển
khai, **không phải một kiến trúc**". Chuyển sang VPS phải là việc ops, nên chứng minh trên
**mỗi PR** rằng ảnh dựng và boot được trên `linux/amd64`, không phải Apple Silicon, không
phải Docker Desktop. Bước kiểm `/Users/` nói thẳng: "A `/Users/...` default is how *works on
the Mac mini* quietly becomes *only works on the Mac mini*".

**`CLINIC_ENV_FILE` phải bị ghi đè trong CI** (`ci.yml:150-154`): các file example trỏ nó
sang `.env.prod` / `.env.staging` — bí mật gitignore mà **không checkout CI nào có**.
Compose đọc `env_file` ở thời điểm config, nên không có bước ghi đè này thì cổng kiểm chỉ
qua được **trên máy đã sẵn có bí mật** — "đúng ngược lại điều nó sinh ra để chứng minh".

### 12.20. Ví dụ tiêu biểu cho từng lớp

| Ví dụ | Lớp | Nó chứng minh điều gì |
|---|---|---|
| `test_khong_mau_nao_dua_so_dien_thoai_vao_tin` (`test_notification_templates.py:79`) | 1 | Canh luật bằng cách đọc **source** → chặn cả nhánh chưa ai gọi tới |
| `test_trigger_event_log_chi_insert` (`test_notification_relay.py:263`) | 1 | Đọc file migration từ Python → giữ một luật kiến trúc (§12.8) mà không cần dựng database |
| `test_a_successful_send_never_waits` | 1 | `asyncio.sleep` **không được await** khi gửi thành công — "đường thuận lợi không được chậm đi vì cơ chế thử lại" |
| `test_hom_nay_chi_con_so_khong_danh_tinh` | 1 | `/homnay` không rò danh tính ra Telegram |
| ~40 file `tests/*boundary.test.mts` | 2 | Logic nghiệp vụ rò vào TSX, quyền truy cập màn, hình dạng lỗi API |
| 23 file `supabase/tests/*.sql` (`tenant_scoped_rls`, `event_log_rls`, `multi_tenant_foundation`, `payment_audit`…) | 3 | **RLS thật sự chặn** — mock không bao giờ nói được điều đó |
| `test-infra-safety.sh` | 4 | Script phá huỷ hành xử đúng, tất định, không cần dữ liệu thật |

**Lớp 4 — `portability` boot ảnh thật**:

```bash
docker run -d --name api-smoke --network host \
  -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres ...
curl -fsS http://localhost:8000/health/db || { docker logs api-smoke; exit 1; }
```

Comment nói rõ giới hạn: `/health/db` chỉ chạy `SELECT 1`, nên Postgres tiêu chuẩn trả lời
được. "**Thứ đang được chứng minh là ảnh khởi động và với tới được một database trên Linux —
không phải điều gì về Supabase.**"

#### ⚠️ Bẫy đã cắn / điểm dễ hiểu sai (Kiểm thử)

- **Coverage 80% không chứng minh code chạy được.** Mọi test relay đều xanh trong khi
  `poll_and_deliver` **chưa bao giờ chạy nổi một vòng thật** (bug UUID). Lớp mock càng dày,
  điều test khẳng định càng xa sự thật.
- **`ruff format --check` hay bị quên khi chạy CI ở máy** — nó là bước riêng, không nằm
  trong `ruff check`.
- **Test đọc source là con dao hai lưỡi.** `assert "phone" not in ma` phải `.replace()` chính
  câu comment nói về nó — sửa comment đó là test đỏ. Chấp nhận được ở đây vì luật quan trọng
  hơn sự bất tiện, nhưng đừng nhân rộng vô tội vạ.
- **`/health` xanh không có nghĩa là hệ chạy được.** Nó không chạm bảng của tính năng — xem
  sự cố 06/08 ở §12.16. Đây là lý do tồn tại của bước cảnh báo migration.


---

## PHẦN 13. NHỮNG BẪY ĐÃ CẮN THẬT — ĐỌC TRƯỚC KHI SỬA BẤT CỨ GÌ

Đây là phần **đáng đọc nhất** của tài liệu, và là phần không có trong bất kỳ khoá học nào:
mỗi mục dưới đây là một sự cố **đã xảy ra thật** trên hệ thống này, kèm triệu chứng người dùng
nhìn thấy, nguyên nhân thật, và luật rút ra.

> Vì sao phần này quan trọng hơn phần giảng code: code thì đọc lại được bất cứ lúc nào,
> còn **lý do một dòng code trông kỳ quặc** thì mất đi vĩnh viễn nếu không ai ghi lại.

Cách đọc mỗi mục: **Triệu chứng** (người dùng thấy gì) → **Nguyên nhân** → **Phát hiện bằng cách nào**
→ **Luật rút ra**.

---

### 13.1. ⚠️ "Slot còn 0/2 mà không đặt lại được" — lịch chết vẫn chiếm chỗ

**Triệu chứng.** Quản lý xoá ca trực của một bác sĩ. Màn đặt lịch hiện slot 7:00 Chủ nhật
vẫn vàng, ghi `0/2` (nghĩa là chưa ai đặt). Nhưng chọn slot đó cho bác sĩ khác thì hệ thống
từ chối.

**Nguyên nhân.** Khi gỡ bác sĩ khỏi ca, lịch cũ chỉ bị **gỡ bác sĩ** (`doctor_id = NULL`) chứ
không bị huỷ. Nó vẫn ở trạng thái "còn sống". Ô đếm sức chứa chỉ đếm lịch **có bác sĩ**, nên hiện
`0/2`; còn luật chống đặt trùng (`_patient_conflict`) lại xét **mọi lịch chưa chết** của cùng
bệnh nhân trong cùng khung giờ — nên nó chặn. Hai phép đếm khác nhau nhìn cùng một dòng dữ liệu
và ra hai kết luận trái ngược.

**Phát hiện bằng cách nào.** Người dùng thao tác thật rồi báo lại. Không bài kiểm nào bắt được,
vì mỗi phía **xét riêng đều đúng**.

**Cách sửa.** Xoá ca giờ **huỷ hẳn** những lịch rơi ra ngoài khung ca còn lại
(`status = CANCELLED`, `ly_do_huy_ma = 'BAC_SI_DOI_LICH'`), kèm một migration dọn các lịch
"ma" đã trót sinh ra trước đó.

> **Luật rút ra.** Mỗi sự kiện phải có **kết thúc dứt khoát**. Một bản ghi "nửa sống nửa chết"
> sẽ được hai chỗ khác nhau diễn giải theo hai kiểu, và người dùng là người lãnh hậu quả.

---

### 13.2. ⚠️ Vá sáu chỗ, đúng năm — dòng gạch ngang biến mất

**Triệu chứng.** Bấm nút tròn hoàn tác xong, dòng vừa rút lại **biến mất hẳn** khỏi
"Lịch sử các lần khám", thay vì nằm lại và bị gạch ngang như trước.

**Nguyên nhân.** Một bản vá trước đó (PR #139) sửa sáu chỗ cùng một mẫu "bỏ qua dòng đã hoàn tác".
Năm chỗ đúng. Chỗ thứ sáu lọc dòng đã hoàn tác **ngay từ nguồn dữ liệu** — mà khối
"Lịch sử các lần khám" đọc đúng nguồn đó để **vẽ** dòng gạch ngang. Trớ trêu: trong code cũ có sẵn
một dòng chú thích dặn đúng điều này, nhưng bản vá bỏ sót.

**Phát hiện bằng cách nào.** Người dùng thử trên staging.

> **Luật rút ra (quan trọng nhất trong tài liệu này).**
> **Hoàn tác ảnh hưởng phép ĐẾM, không ảnh hưởng phép KỂ.**
> Dòng bị rút lại thì thôi được *tính* (không còn là "việc đang mở", không còn là mốc kết thúc),
> nhưng vẫn phải *nằm lại* để kể chuyện. Sổ y tế không được phép mất dấu vết.

Bài kiểm sau đó được viết **hai chiều**: bắt buộc mốc đếm phải né dòng đã hoàn tác, **và cấm**
lọc nó khỏi nguồn hiển thị. Sai chiều nào CI cũng đỏ.

---

### 13.3. ⚠️ "F5 rồi mà vẫn không hoàn tác được" — lượt mặc định nhảy chỗ

**Triệu chứng.** Ghi một thao tác cho khách, đổi trạng thái xong, tải lại trang — nút tròn
không cho rút lại nữa.

**Nguyên nhân.** Mỗi lần chạm được ghi **gắn vào lượt khám đang xem**, và nút tròn chỉ rút được
dòng **của lượt đang xem**. Khi người dùng không tự bấm chọn lượt, màn hình **tự chọn** theo luật
"ưu tiên lượt đang khám, không thì lịch sắp tới gần nhất". Mà chính thao tác vừa rồi lại **làm lượt
đó rơi khỏi luật** (ví dụ Checkout → lượt thành "đã khám xong" → không còn là "lịch sắp tới").
Lần tải sau, màn nhảy sang lượt khác; dòng vừa ghi ở lại lượt cũ, ngoài tầm với của nút tròn.

Trường hợp nặng hơn: lần chạm ghi khi khách **chưa gắn lượt nào** thì **không lượt nào** rút được nó.

**Phát hiện bằng cách nào.** Người dùng mô tả đúng cơ chế (*"sau khi đã **chuyển trạng thái**"*)
trong khi chẩn đoán ban đầu của AI đổ lỗi cho F5 — sai. Chỉ khi đọc lại mã chọn-lượt mặc định
mới thấy đúng.

> **Luật rút ra.** Khi người dùng mô tả *khi nào* lỗi xảy ra, hãy tin mô tả đó hơn giả thuyết
> của mình. *"Sau khi đổi trạng thái"* và *"sau khi F5"* nghe giống nhau nhưng chỉ vào hai
> nguyên nhân hoàn toàn khác.

---

### 13.4. ⚠️ Ô "Quá SLA" đếm 0 trong khi dòng ngay dưới đang đỏ

**Triệu chứng.** Khách hiện chữ đỏ "đã quá giờ hẹn — chưa check-in", nhưng ô thống kê
"Quá SLA" trên đầu màn vẫn ghi **0**.

**Nguyên nhân.** Hai thước đo khác nhau cho cùng một khái niệm: view trong database đo
**theo ngày** (có việc quá hạn hôm nay), còn chip đỏ trên dòng đo **theo phút** (đã qua giờ hẹn
chưa). Ô thống kê chỉ cộng thước thứ nhất.

> **Luật rút ra.** Một con số tổng và các dòng bên dưới nó **phải dùng chung một định nghĩa**.
> Nếu không, người dùng sẽ tin con số tổng và bỏ sót việc thật.

---

### 13.5. ⚠️ Relay thông báo chết sau **mỗi** lần deploy

**Triệu chứng.** Telegram im lặng sau vài ngày, hàng đợi sự kiện dồn 57 tin chưa gửi.

**Nguyên nhân.** Dịch vụ relay nằm trong một "profile" của Docker Compose, mà `docker compose up`
mặc định **không** bật service thuộc profile. Mỗi lần deploy là relay bị bỏ lại, không ai nhận ra
vì các dịch vụ khác đều xanh.

**Cách sửa.** Thêm hẳn một bước trong `deploy-backend.sh`: sau khi dựng xong, nếu biến môi trường
bật thông báo thì dựng luôn relay.

> **Luật rút ra.** Thành phần nào **không** nằm trong đường deploy mặc định thì sớm muộn cũng
> bị bỏ quên. Đừng dựa vào trí nhớ người vận hành.

---

### 13.6. ⚠️ Đổi lược đồ xong, API báo "không tìm thấy quan hệ"

**Triệu chứng.** Vừa thêm bảng mới và khoá ngoại, ứng dụng báo lỗi kiểu
*"Could not find a relationship between 'patient' and 'patient_sdt_them'"*.

**Nguyên nhân.** PostgREST **giữ bản sao lược đồ trong bộ nhớ**. Bảng mới có thật trong database
nhưng nó chưa biết.

**Cách sửa.** Sau mỗi migration đổi lược đồ: `docker restart clinicai_rest` (và bản staging tương ứng).

> **Luật rút ra.** "Đã chạy migration" chưa đồng nghĩa "hệ thống đã thấy migration".

---

### 13.7. ⚠️ Hai cơ sở dữ liệu cùng tên "prod"

**Triệu chứng.** Đo đạc trên "prod" ra những con số vô lý, không khớp thực tế phòng khám.

**Nguyên nhân.** Tệp `.env.prod` trên máy Mac vẫn trỏ về Supabase cloud **cũ** — một bản sao đã
chết. Mọi lệnh chạy qua tệp đó đều nói về hệ thống sai.

> **Luật rút ra.** Trước khi tin một phép đo, hỏi: *"lệnh này vừa nói chuyện với máy chủ nào?"*
> Cùng một cái tên không có nghĩa là cùng một hệ thống.

---

### 13.8. ⚠️ Hai bảng theo dõi Uptime Kuma, mở nhầm cái rỗng

**Triệu chứng.** Bảng theo dõi trống trơn, 0 kênh — trong khi bot Telegram báo hệ thống bình thường.

**Nguyên nhân.** Máy Mac vẫn chạy stack cũ song song, trong đó có một Uptime Kuma **chưa bao giờ
được cấu hình**, và nó chiếm cổng `localhost:3001`. Kuma thật nằm trên máy chủ, có đủ kênh và
đều xanh.

**Cách sửa.** Mở đường hầm qua cổng khác: `ssh -N -L 3002:127.0.0.1:3001 clinic-vps`.

> **Luật rút ra.** Khi hai môi trường cùng tồn tại, **địa chỉ localhost là thứ dễ nói dối nhất**.

---

### 13.9. ⚠️ Cookie không phân biệt cổng — đăng nhập staging đá văng phiên prod

**Triệu chứng.** Mở hai tab prod và staging, đăng nhập bên này thì bên kia bị đăng xuất, hoặc
báo sai mật khẩu.

**Nguyên nhân.** Theo chuẩn cookie (RFC 6265 §8.5), `http://IP:80` và `http://IP:8080` là **hai
origin khác nhau với mọi thứ khác**, nhưng dùng **chung một hũ cookie**. Hai môi trường lại có hai
máy chủ xác thực với hai khoá ký khác nhau → token của bên này bị bên kia từ chối.

**Cách sửa.** Ghim tên cookie **kèm hậu tố theo cổng**; prod giữ nguyên tên cũ (đổi tên cookie
là đăng xuất toàn bộ người dùng), chỉ staging đổi.

---

### 13.10. ⚠️ Đổi email đăng nhập mà quên một bảng

**Triệu chứng.** Đổi email tài khoản xong, đăng nhập báo sai mật khẩu dù mật khẩu không đổi.

**Nguyên nhân.** Tầng xác thực lưu danh tính ở **hai nơi**: `auth.users` và `auth.identities`.
Sửa một nơi là hai nơi lệch nhau.

**Cách làm đúng.** Sửa cả hai trong **một giao dịch**, rồi **thử đăng nhập thật** bằng API trước
khi báo là xong.

> **Luật rút ra.** Với xác thực, "đã cập nhật database" không phải bằng chứng. **Đăng nhập thử
> mới là bằng chứng.**

---

### 13.11. ⚠️ `gh pr merge` im lặng không làm gì

**Triệu chứng.** Chạy lệnh merge, không báo lỗi rõ ràng, nhưng nhánh chính không đổi — rồi
deploy ra bản cũ.

**Nguyên nhân.** Khi CI chưa xong (hoặc bị huỷ), lệnh merge từ chối nhưng thông báo rất kín.

**Cách làm đúng.** Luôn **theo dõi đúng lượt CI của đúng commit** cho tới khi kết luận `success`,
rồi mới merge, rồi **kiểm lại** nhánh chính đã đổi thật chưa.

---

### 13.12. ⚠️ `/health` xanh nhưng màn hình hỏng

**Nguyên nhân.** Đường `/health` chỉ kiểm tra ứng dụng còn sống và nối được database — nó
**không chạm vào bảng của tính năng**. Thiếu một bảng do migration chưa chạy thì `/health` vẫn xanh
trong khi màn hình liên quan trắng xoá.

> **Luật rút ra.** Xanh nghĩa là **"còn thở"**, không phải **"còn đúng"**. Nghiệm thu phải bấm thử
> đúng màn hình vừa sửa.

---

### 13.13. ⚠️ Migration phải đi TRƯỚC code

**Triệu chứng.** Deploy xong, tính năng mới trả lỗi 500 hàng loạt.

**Nguyên nhân.** Code mới ghi một mã trạng thái mới, nhưng ràng buộc `CHECK` trong database chưa
được nới ra để chấp nhận mã đó.

> **Luật rút ra.** Thứ tự bắt buộc: **nới lược đồ trước → deploy code sau**. Ngược lại là sự cố;
> và vì thế migration trong dự án này chỉ được **thêm**, không sửa ngược.

---

### 13.14. ⚠️ Những bài kiểm tự động canh cả những thứ bất ngờ

Hai lần CI đỏ vì lý do không ai đoán được:

- **mypy chạy trên cả thư mục `src/`**, không chỉ `src/clinicai` — nên một chú thích kiểu thừa ở
  thư mục khác cũng làm đỏ.
- Một bài kiểm cấm **mã màu cứng** trong giao diện dùng biểu thức tìm chuỗi dạng `#` + chữ số.
  Một dòng chú thích tiếng Việt viết `#139` (số hiệu pull request) **khớp đúng mẫu đó** → CI đỏ.
  Sửa bằng cách viết `PR 139`.

> **Luật rút ra.** Bài kiểm là một người gác cổng máy móc. Khi nó đỏ, hãy đọc **chính xác** nó
> đang khớp cái gì, đừng vội cho là mình sai ở chỗ mình nghĩ.

---

### 13.15. ⚠️ `TRUNCATE` không phát tín hiệu realtime

**Triệu chứng.** Sau khi dọn sạch dữ liệu, các tab đang mở **vẫn hiển thị khách và lịch cũ** như
chưa có gì xảy ra; bấm vào thì lỗi.

**Nguyên nhân.** Cơ chế realtime dựa trên trigger theo từng dòng. `TRUNCATE` xoá cả bảng mà
**không kích hoạt trigger dòng** — có chủ ý, để tránh dội bom hàng vạn thông báo.

> **Luật rút ra.** Sau thao tác dọn dữ liệu hàng loạt, phải **báo mọi người tải lại trang**.
> Màn hình cũ là một tấm ảnh chụp, không phải sự thật.

---

### 13.16. ⚠️ Vòng lặp chờ với điều kiện thoát không bao giờ đúng

**Triệu chứng.** Một tiến trình nền chạy suốt gần một ngày.

**Nguyên nhân.** Vòng lặp chờ *"cho tới khi tìm được lượt deploy có mã commit trùng với commit của
tag"*. Nhưng hệ thống CI ghi lượt deploy đó dưới **mã commit của nhánh chính**, không phải mã của
tag → điều kiện thoát vĩnh viễn sai.

> **Luật rút ra.** Mọi vòng lặp chờ phải có **giới hạn thời gian**. Và khi muốn biết "đã xong
> chưa", hãy đo **hiện vật** (container đang chạy bản nào, tệp build có chứa chuỗi mới không)
> chứ đừng đo **nhãn** (metadata của hệ thống CI).

---

### 13.17. Bảng tra nhanh — triệu chứng → nghi phạm đầu tiên

| Triệu chứng | Nghi ngay |
|---|---|
| Màn hình trắng sau khi đổi truy vấn | Cú pháp cột của PostgREST (dấu `--` **không** phải chú thích) |
| API báo không tìm thấy bảng/quan hệ vừa tạo | PostgREST chưa restart |
| Lỗi 403 sau khi thêm nhân sự | Tài khoản chưa nối với hồ sơ nhân viên, hoặc vai chưa được thêm vào cổng chặn |
| Đăng nhập báo sai mật khẩu sau khi sửa tài khoản | `auth.users` và `auth.identities` lệch nhau |
| Deploy xong 500 hàng loạt | Migration chưa chạy trước |
| Telegram im lặng | Relay không được dựng lại sau deploy |
| Số tổng nói 0 mà dòng dưới đỏ | Hai thước đo khác nhau cho cùng khái niệm |
| Bấm nút không có gì xảy ra, log máy chủ trống | Request chưa rời trình duyệt — soi tab Network trước |
| Dữ liệu "vẫn còn" sau khi đã xoá | Tab cũ chưa tải lại |

---

## PHẦN 14. MƯỜI CÂU HAY ĐƯỢC HỎI — VÀ CÂU TRẢ LỜI NGẮN

**1. Vì sao tách `appointment` (lịch hẹn) và `visit` (lượt khám)?**
Vì hai chuyện khác nhau: khách có lịch mà không đến (không có lượt khám), và khách vãng lai
đến khám mà không có lịch (có lượt khám, không có lịch hẹn). Gộp làm một là mất khả năng
đếm đúng cả hai.

**2. Vì sao huỷ/hoàn tác không xoá dòng?**
Vì đây là hệ thống y tế: mọi thao tác phải để lại dấu vết ai làm, lúc nào. Dòng bị rút lại chỉ
thôi được *tính*, chứ vẫn nằm lại để *kể*.

**3. Vì sao không dùng Redis / hàng đợi tin nhắn / microservices?**
Vì ở quy mô này (khoảng một lượt gọi mỗi giây, một người vận hành) chúng thêm chỗ hỏng nhiều hơn
thêm giá trị. Mỗi hạ tầng bị từ chối đều được ghi trong `docs/SO-LUAT.md` **kèm ngưỡng đo được
để mở lại** — khi nào vượt ngưỡng thì bàn tiếp, không bàn theo cảm tính.

**4. Vì sao giao diện không nói chuyện thẳng với database?**
Vì luật nghiệp vụ phải nằm ở **một chỗ duy nhất** để còn kiểm thử được. Giao diện chỉ được nói
chuyện trực tiếp với Supabase cho hai việc: đăng nhập và nhận tín hiệu realtime.

**5. Làm sao biết bản nào đang chạy ở đâu?**
Đo hiện vật, không đo nhãn: liệt kê container trên máy chủ và xem tệp build có chứa chuỗi mới hay
không. Nhãn của hệ thống CI có thể ghi mã commit khác với thứ thực sự được dựng.

**6. Ai được làm gì?**
Vai suy ra từ tài khoản đăng nhập → hồ sơ nhân viên → phòng khám đang hoạt động. Không có màn
"chọn vai" nào cả — đó là thiết kế cũ đã bỏ vì giả mạo được.

**7. Dữ liệu hỏng thì khôi phục thế nào?**
Có bản sao lưu trước mỗi thao tác lớn và có kịch bản diễn tập phục hồi. Nhưng một bản sao lưu
**chưa từng phục hồi thử** thì chưa phải bản sao lưu — hãy chạy diễn tập ít nhất một lần.

**8. Vì sao có tới 5 cổng kiểm trong CI?**
Vì mỗi cổng bắt một loại lỗi mà các cổng khác mù: kiểu dữ liệu Python, giao diện, lược đồ database
chạy trên Postgres thật, an toàn hạ tầng, và tính di động khi chuyển máy chủ.

**9. Realtime hoạt động thế nào mà không cần F5?**
Database phát tín hiệu mỗi khi có dòng đổi → tiến trình nền nghe được → đẩy xuống trình duyệt qua
một kết nối mở sẵn → màn hình tự làm tươi. Có kèm cơ chế hỏi lại định kỳ phòng khi tín hiệu rớt.

**10. Vì sao mọi truy vấn phải mang `clinic_id`?**
Vì hệ thống được thiết kế **đa phòng khám ngay từ đầu**. Thiếu điều kiện đó là dữ liệu phòng khám
này lọt sang phòng khám khác — nên có hẳn một bài kiểm tự động đếm và chặn ở mức không cho phép
một trường hợp nào.

---

## PHẦN 15. LỘ TRÌNH ĐỌC CODE ĐỀ XUẤT — 7 BUỔI

Đừng đọc tài liệu này từ đầu tới cuối trong một lần. Đọc theo **đường đi của dữ liệu**:

| Buổi | Đọc gì | Mục tiêu sau buổi đó |
|---|---|---|
| 1 | Phần 0 → 2 | Kể lại được vòng đời một khách và ba khái niệm dễ nhầm |
| 2 | Phần 10 (frontend nền) + mở tab Network bấm thử một nút | Chỉ ra được cùng một request ở trình duyệt và ở log máy chủ |
| 3 | Phần 8 (API) — chỉ đọc bảng tổng endpoint | Biết mỗi màn hình gọi đường nào, vai nào được gọi |
| 4 | Phần 5 (booking_service) | Vẽ lại được máy trạng thái lịch hẹn từ trí nhớ |
| 5 | Phần 9 (database) | Giải thích được vì sao ràng buộc ở database mạnh hơn kiểm tra ở màn hình |
| 6 | Phần 11 (ba màn lớn) | Giải thích được "lượt khám đang xem" và vì sao nó hay gây hiểu nhầm |
| 7 | Phần 12 + Phần 13 | Chẩn được một sự cố theo tầng, và biết đường lùi |

> **Mẹo đọc.** Mỗi khi gặp một đoạn code trông kỳ quặc, hãy tìm **dòng chú thích tiếng Việt**
> ngay phía trên nó. Repo này có thói quen ghi lại *lý do* và *sự cố thật* ngay cạnh chỗ sửa —
> đó là kho kiến thức giá trị nhất, và tài liệu này chỉ là bản sắp xếp lại của kho đó.


---


## GHI CHÚ VỀ BẢN TÀI LIỆU NÀY

- Chụp theo nhánh chính tại commit `5ea90cc` — Hoàn tác phải còn dòng gạch ngang — PR 139 lọc nhầm từ nguồn kể chuyện (#140)
- Ngày soạn: 19/08/2026
- Chưa gộp vào tài liệu: các thay đổi đang chờ duyệt ở PR #141 (lối rút lại dự phòng + khối "Lịch sử thao tác").
- Khi tài liệu và code mâu thuẫn, **tin code**.
