# Thiết kế: nhiều cơ sở (Hào Nam) + phòng khám đối tác tự nhập

| | |
|---|---|
| **Trạng thái** | Đề xuất — chờ Tuyền review |
| **Ngày** | 05/10/2026 |
| **Quyết định kèm** | [ADR-0015](../adr/0015-co-so-hien-hanh-va-co-so-cua-thuc-the.md) · [ADR-0016](../adr/0016-phong-kham-moi-tao-tu-mau-va-tu-nhap.md) |
| **Nền đã có** | [ADR-0009](../adr/0009-multi-tenant-thuc-tu-dau.md) (tenant thật), `docs/kien-truc-nhieu-phong-kham.md` |

## 1. Bối cảnh

Hai việc sắp tới:

1. **Dr4Women mở cơ sở thứ hai: Hào Nam.** Dùng chung nhân sự và quyền. Chỉ khác cấu trúc phòng.
2. **Phòng khám đối tác dùng ClinicAI.** Họ phải tự nhập được dữ liệu của mình, không cần lập trình viên.

Hệ thống có sẵn hai tầng:

| Tầng | Bảng | Hiện trạng |
|---|---|---|
| **Phòng khám** (tenant) | `clinic`, `clinic_membership` | ✅ Thật từ 30/07. ~130 bảng có `clinic_id`. RLS theo tenant. CI audit trần = 0. Đã có bài kiểm cô lập lúc chạy. |
| **Cơ sở** (chi nhánh) | `clinic_location` | ⚠️ Có bảng; `location_id` có trên lịch hẹn, lượt, khách, phòng. Tự xếp phòng, điều phối, TV, số tiếp đón đã theo cơ sở. **Phần còn lại chưa.** |

**Lỗ hổng gốc:** cơ sở của một request lấy từ `staff.primary_location_id` (`src/clinicai/api/identity.py`, khoảng dòng 478). Cột này cố định, mỗi người một giá trị. Ví dụ: người đăng ký ở Kim Ngưu, hôm nay sang Hào Nam làm. Họ sẽ thấy bảng điều phối Kim Ngưu, và lịch họ đặt rơi vào Kim Ngưu. Đây chính là sự cố "cơ sở lạc" ngày 24/09, chỉ khác là lần này xảy ra mỗi ngày.

Các chỗ hở khác (soát 05/10):

- **Lịch trực:** `work_roster` và `vi_tri_lam_viec` không có cơ sở.
- **Hàng chờ:** `hang_cho.py` (~285) lấy quầy `LUOTKHAM-01` đầu tiên của *cả phòng khám*.
- **Danh sách phòng không lọc cơ sở:** `luot_kham_doc.py` (~287, ~609) và `api/v1/routers/identity.py` (~115).
- **Ô chọn cơ sở rơi về `locations[0]`:** `AppointmentBooking.tsx:126` và `NewPatientForm.tsx:450`.
- **Kho, thu ngân, công nợ, báo cáo:** 0 chỗ lọc theo cơ sở.
- **Đăng nhập:** đòi "đúng một phòng khám", không ghi cơ sở. API đã nhận được `X-Clinic-ID` nhưng giao diện chưa gửi.
- **CI:** `tenant-scope-audit.py` dùng danh sách bảng viết tay, thiếu `clinic_room`, `drug_batch`, `phieu_kho`, `payment_cycle`… Audit cũng không biết gì về cơ sở.
- **Ràng buộc:** không có khoá ngoại ghép `(location_id, clinic_id)`.
- **Trigger tự gán cơ sở:** chỉ chạy khi phòng khám có đúng 1 cơ sở.
- **Dữ liệu prod:** Hào Nam đã bị xoá ngày 27/09, phải tạo lại.

## 2. Đã chốt (Tuyền, 05/10)

| Câu hỏi | Chốt |
|---|---|
| Kho thuốc | **Riêng từng cơ sở** |
| Giá dịch vụ | **Chung** toàn phòng khám |
| KiotViet | **Không mở chi nhánh thứ hai.** Mục tiêu là làm hết trên ClinicAI. Hào Nam không đồng bộ POS. |
| Giờ ca làm | **Chung** |
| Báo cáo doanh thu | **Tách theo cơ sở, kèm dòng tổng** |
| Hồ sơ khách | **Chung** toàn phòng khám, để khách bên kia sang vẫn được nhận là khách cũ |
| Phòng khám đối tác | Phải có sẵn đường để họ **tự nhập** |

## 3. Mục tiêu / Không làm

**Làm:**

- **G1.** Một nhân sự được phép làm ở một hoặc nhiều cơ sở. Mặc định là mọi cơ sở. Quản lý tick bỏ được.
- **G2.** Đăng nhập theo thứ tự: chọn phòng khám (nếu thuộc nhiều phòng khám) → chọn cơ sở (nếu được nhiều cơ sở). Cơ sở được gợi ý sẵn theo lịch trực hôm nay. Có nút đổi cơ sở trên thanh trên.
- **G3.** Mọi màn vận hành chỉ hiện việc của cơ sở đang đứng.
- **G4.** Mọi thao tác ghi đúng cơ sở *của thứ đang được thao tác*, không phải cơ sở của người bấm.
- **G5.** Mỗi cơ sở có kho riêng, có phiếu chuyển kho giữa hai cơ sở.
- **G6.** Báo cáo có bộ lọc cơ sở và dòng tổng.
- **G7.** Tạo được phòng khám đối tác từ một bộ mẫu. Quản lý của họ tự nhập cơ sở, phòng, nhân sự, dịch vụ, giá, thuốc và tồn đầu bằng Excel mẫu, có xem trước và hoàn tác.

**Không làm (lần này):**

- Giá riêng theo cơ sở. Nếu sau này cần, sẽ thêm `location_id` có thể rỗng vào `service_price` theo đúng khuôn "luật mới cắt luật cũ".
- KiotViet chi nhánh 2.
- Mỗi đối tác một database riêng (đã loại ở ADR-0009, phương án C).
- Tên miền và thương hiệu riêng cho từng đối tác. Mục 9 ghi lại để quyết sau.
- Thu phí đối tác.

## 4. Quy mô (vì sao không cần hạ tầng mới)

| | Nay | Hào Nam | 10 đối tác cỡ Dr4Women |
|---|---|---|---|
| Lượt gọi API | ~1/giây | < 2/giây | ~10–20/giây lúc cao điểm |
| Database | 57 MB | ~100 MB/năm | ~1–2 GB/năm |
| CPU API (VPS 4 vCPU) | 0.3% | < 1% | vài % |

Cả ba cột đều còn xa ngưỡng trong `SO-LUAT.md` Phần 7. **Không thêm Redis, không thêm bản sao, không thêm database.** Nút thắt thật của việc này là **tính đúng** (ghi đúng cơ sở), không phải tải.

## 5. Khái niệm then chốt

### 5.1 Cơ sở là phân vùng vận hành, KHÔNG phải ranh giới bảo mật

| | Phòng khám (tenant) | Cơ sở |
|---|---|---|
| Là gì | Ranh giới **bảo mật / pháp lý** | Phân vùng **vận hành** ("đúng chỗ") |
| Rò chéo nghĩa là | Lộ dữ liệu y tế cho pháp nhân khác | Ghi nhầm nơi: khách bị gọi ở quầy bên kia, trừ nhầm kho |
| Ép bằng | RLS + audit trần 0 + kiểm lúc chạy | Khoá ngoại ghép + trigger "cùng cơ sở" + mô phỏng 2 cơ sở |
| Đọc chéo | **Cấm** | **Được.** Khách chung, lịch sử chung; nhân sự xem được cơ sở kia khi cần |

Hệ quả: **không viết RLS theo cơ sở.** Lọc cơ sở là bộ lọc mặc định ở màn đọc. Lớp ép cứng chỉ đặt ở chỗ ghi sai sẽ gây hại vật lý: kho, phòng, quầy.

### 5.2 Hai nguồn cơ sở, luật ưu tiên rõ ràng (ADR-0015)

1. **Cơ sở của thực thể** — `visit.location_id`, `appointment.location_id`, `drug_batch.location_id`, `phieu_kho.location_id`…
   **Luôn thắng.** Thao tác lên một lượt ở Hào Nam thì dùng phòng, quầy, kho của Hào Nam, bất kể người bấm đang chọn cơ sở nào.
2. **Cơ sở hiện hành của phiên** — người dùng chọn lúc đăng nhập. Chỉ dùng cho hai việc:
   - **mặc định khi tạo mới**: lịch hẹn, tiếp đón, bán lẻ, phiếu kho;
   - **bộ lọc mặc định của danh sách**.

Worker nền (su-kien, canh gác) không có phiên, nên luôn đi theo luật 1. Vì vậy lỗi kiểu `hang_cho.py:285` (lấy quầy của cả phòng khám) được sửa theo luật 1: lấy quầy theo `visit.location_id`.

## 6. Mô hình dữ liệu

### 6.1 Bảng mới, cột mới

```sql
-- Ai được làm ở cơ sở nào (G1). Quyền lego vẫn theo phòng khám, không nhân đôi.
CREATE TABLE staff_location (
  clinic_id   uuid NOT NULL,
  staff_id    uuid NOT NULL REFERENCES staff(id),
  location_id uuid NOT NULL,
  is_active   boolean NOT NULL DEFAULT true,
  PRIMARY KEY (staff_id, location_id),
  FOREIGN KEY (location_id, clinic_id) REFERENCES clinic_location(id, clinic_id)
);
-- + trigger: (staff_id, clinic_id) phải có clinic_membership đang hoạt động.

ALTER TABLE clinic_location ADD CONSTRAINT uq_location_id_clinic UNIQUE (id, clinic_id);
ALTER TABLE clinic_location ADD COLUMN settings jsonb NOT NULL DEFAULT '{}';
-- settings của cơ sở GHI ĐÈ clinic.settings theo từng khoá (giờ mở cửa, địa chỉ in phiếu…).
-- Đọc qua MỘT hàm: cau_hinh_co_so(location_id). Hôm nay rỗng = dùng chung (đúng chốt
-- "giờ ca chung"); mai khác thì sửa dữ liệu, không sửa code.

ALTER TABLE vi_tri_lam_viec ADD COLUMN location_id uuid;  -- backfill Kim Ngưu → NOT NULL
-- + trigger: nếu vị trí gắn phòng thì location_id phải trùng phòng.
-- Lịch trực của cơ sở X = work_roster nối vi_tri_lam_viec có location_id = X.
```

- `staff.primary_location_id` được giữ lại, đổi nghĩa thành **"cơ sở mặc định"**. Chỉ dùng khi người đó chỉ được một cơ sở, hoặc khi không có gợi ý nào khác.
- `patient.location_id` được giữ lại, nghĩa là **"cơ sở đăng ký lần đầu"**. Chỉ để thông tin. **Không bao giờ dùng để lọc** tìm khách hay hồ sơ.

### 6.2 Khoá ngoại ghép: chặn cơ sở của phòng khám khác

Thay FK đơn `location_id → clinic_location(id)` bằng `(location_id, clinic_id) → clinic_location(id, clinic_id)` trên các bảng `appointment`, `visit`, `patient`, `clinic_room`, `staff_node`, `block_budget`, `work_session`, `staff_task`, `visit_gate_rule`, `pregnancy`, cùng các bảng mới ở dưới.

`visit.location_id`: backfill Kim Ngưu cho các lượt trước 24/09, rồi đặt NOT NULL.

### 6.3 Bảng con của lượt: KHÔNG chép `location_id`

`queue_entry`, `payment_cycle`, `payment*`, `cong_no`, `service_order`, `prescription*`… đều suy cơ sở qua `visit.location_id` bằng JOIN.

**Đánh đổi:** chép cột sang (denormalize) thì truy vấn nhanh hơn một chút, nhưng sinh ra hai nguồn sự thật có thể lệch nhau. Ở 57 MB, JOIN qua `visit` không đáng kể. Ngưỡng để lật lại quyết định này: một màn có p95 > 800 ms và đo được nguyên nhân là JOIN này.

**Ngoại lệ:** thứ có chỗ đứng vật lý mà không gắn với lượt (kho, phiếu kho, bán lẻ không lượt) thì mang `location_id` trực tiếp.

### 6.4 Kho theo cơ sở (G5)

| Bảng | Đổi |
|---|---|
| `drug_batch` | `+ location_id NOT NULL` (backfill Kim Ngưu). Unique `(clinic_id, batch_code)` → `(clinic_id, location_id, batch_code)`, vì cùng một lô có thể nằm ở cả hai nơi sau khi chuyển. |
| `inventory_txn` | `+ location_id`, **điền bằng trigger tra từ `drug_batch`** (cùng khuôn `work_item_event`), không nhận từ code. `txn_type` thêm `TRANSFER_OUT`, `TRANSFER_IN`. |
| `phieu_kho` | `+ location_id NOT NULL`; `loai` thêm `'CHUYEN'`; `+ location_den_id`, `trang_thai` (`DANG_CHUYEN` → `DA_NHAN` / `DA_HUY`). Mã phiếu kèm mã cơ sở (`PN-KN-0001`). |
| Đơn thuốc | Chọn lô (FEFO) **trong kho của `visit.location_id`**. Trigger từ chối cấp lô khác cơ sở với lượt. |
| `drug_catalog`, giá thuốc | Chung, không đổi. |

**Chuyển kho hai bước:**

1. Bên gửi bấm "Gửi": ghi `TRANSFER_OUT`, phiếu ở trạng thái `DANG_CHUYEN`. Hàng đang đi đường vẫn nhìn thấy được.
2. Bên nhận bấm "Đã nhận": ghi `TRANSFER_IN`. Lô ở cơ sở đích được tạo mới hoặc cộng dồn.

Huỷ khi chưa nhận thì ghi `TRANSFER_IN` ngược về kho gửi (hoàn tác được, đúng luật CLAUDE.md #7). Tồn kho được ép ở Postgres bằng `CHECK quantity_on_hand >= 0` và cập nhật có điều kiện (`SO-LUAT` Phần 6). Đánh đổi chọn hai bước thay vì một bước: thêm một lần bấm, đổi lại biết hàng thất lạc trên đường.

### 6.5 Số đếm

| Số | Phạm vi | Đổi? |
|---|---|---|
| `so_tiep_don` | (phòng khám, cơ sở, ngày) | đã đúng |
| `queue_number` | (phòng khám, ngày, bác sĩ) | giữ. Một bác sĩ không ở hai nơi cùng lúc. |
| `so_booking` | (phòng khám, ngày) | giữ. Là mã tra cứu, không phải số gọi. |
| Mã phiếu kho | (phòng khám, mã) | giữ unique, chèn mã cơ sở vào chuỗi |

### 6.6 Sức chứa đặt lịch

Giữ theo **bác sĩ × khung giờ** (không theo cơ sở), vì người không phân thân được: điều này đúng cho cả hai cơ sở. Sửa duy nhất một chỗ: kiểm "bác sĩ có ca" (`booking.py` ~265) phải hỏi thêm **ca đó ở cơ sở nào**, qua `vi_tri_lam_viec.location_id`. Đặt lịch ở Hào Nam cho một bác sĩ chỉ có ca ở Kim Ngưu thì bị từ chối, kèm câu giải thích rõ.

## 7. Cơ sở hiện hành: đăng nhập, API, giao diện (G2–G3)

### 7.1 Luồng đăng nhập

```
Đăng nhập (GoTrue)
  └─ clinic_membership đang hoạt động
       ├─ 1 → tự chọn
       └─ >1 → màn "Chọn phòng khám"  → cookie clinicai_clinic
  └─ staff_location đang hoạt động trong phòng khám đó
       ├─ 1 → tự chọn
       └─ >1 → màn "Chọn cơ sở" — ô ĐƯỢC CHỌN SẴN theo thứ tự:
                 ① lịch trực hôm nay (vị trí → cơ sở)
                 ② cơ sở dùng lần trước (cookie)
                 ③ staff.primary_location_id
              → một lần bấm "Vào" → cookie clinicai_location
```

Sửa `login/actions.ts` cho đúng: bỏ điều kiện "phải đúng một phòng khám".

### 7.2 API

- `src/dashboard/lib/backend-proxy.ts` đọc hai cookie, rồi gắn `X-Clinic-ID` và `X-Location-ID` vào request gửi API.
- `_resolve_identity` dùng lại đúng khuôn của `_requested_clinic_id`. Header chỉ là **bộ chọn, không phải thẩm quyền**:
  - Có header, và cơ sở đó nằm trong `staff_location` đang hoạt động → `identity.location_id` = cơ sở đó.
  - Có header nhưng người dùng không được làm ở cơ sở đó → **403**.
  - Không có header, và chỉ được 1 cơ sở → dùng cơ sở đó.
  - Không có header, và được từ 2 cơ sở → **428 "Chọn cơ sở"**. Giao diện bắt mã này và đưa sang `/chon-co-so`. **Không đoán** — đoán chính là gốc sự cố 24/09.
- `GET /api/v1/me/co-so` trả về danh sách cơ sở được phép, kèm gợi ý theo lịch trực.

### 7.3 Giao diện

- **Thanh trên** có `📍 Hào Nam ▾`. Đổi cơ sở = ghi cookie rồi tải lại dữ liệu. Có ghi một dòng nhật ký vận hành. Đổi lại được bất cứ lúc nào.
- **Dải cảnh báo:** nếu cơ sở đang chọn khác cơ sở trong lịch trực hôm nay, hiện *"Hôm nay bạn được xếp ở Hào Nam — Đổi sang Hào Nam"*. Đây là lớp chặn chính cho chuyện quên đổi.
- Màn **Nhân sự** có thêm cột tick cơ sở (G1).

**Màn lọc theo cơ sở hiện hành:**

- đặt lịch / lịch hẹn (vẫn xem được cơ sở kia);
- tiếp đón, hàng chờ, bàn khám, phòng dịch vụ;
- điều phối, TV;
- thu ngân, quầy thuốc, kho;
- lịch trực.

**Màn KHÔNG lọc:**

- tìm khách, hồ sơ, lịch sử khám (thêm cột "Cơ sở");
- danh mục, giá, quyền, nhân sự.

**Báo cáo:** có bộ lọc `Tất cả / Kim Ngưu / Hào Nam`, độc lập với cơ sở đang đứng. Có dòng tổng (G6).

**TV phòng chờ:** gắn cơ sở theo cấu hình của màn TV, không theo người đăng nhập.

Mọi thay đổi route hoặc thanh bên đều phải sửa `docs/SITEMAP.md` trong cùng commit.

## 8. Phòng khám đối tác tự nhập (G7, ADR-0016)

### 8.1 Đã có và còn thiếu

**Đã có:**

- cô lập tenant: RLS, audit trần 0, kiểm lúc chạy;
- API đã nhận `X-Clinic-ID`;
- một bác sĩ làm được ở nhiều phòng khám, qua `clinic_membership`.

**Còn thiếu:**

- (a) Không có cách tạo phòng khám mới. Chỉ có dòng seed Dr4Women trong migration.
- (b) Phòng khám mới cần khoảng 25 bảng cấu hình mới chạy được: `node_definition*`, `route_template`, `form_definition`, `clinical_form_catalogue`, `quyen_preset`, `ky_nang`, `vai_duoc_vao_tram`, `loai_kham_phi`, `dich_vu_mau_ket_qua`, `ket_qua_mau`, `phu_thu_mau`, `semen_reference_range`, `day_nghiep_vu`, `luat_*`, `dispatch_threshold`, `booking_channel`, `clinic.settings`…
- (c) Danh mục, nhân sự, giá hiện đều nhập bằng script (`scripts/nhan-su-kim-nguu.py`, `kim-nguu-3-tang-2709.py`), không có màn nhập.

### 8.2 Thiết kế

**Bộ mẫu sản phẩm nằm trong git:** `supabase/mau-phong-kham/`, gồm các tệp dữ liệu có phiên bản. Hàm `tao_phong_kham(code, ten, ...)` chạy trong **một transaction**:

1. tạo dòng `clinic`;
2. chép bộ mẫu vào tenant mới;
3. tạo một cơ sở đầu tiên;
4. tạo tài khoản quản lý đầu tiên.

Khi bộ mẫu lên phiên bản mới thì có lệnh "áp phần mẫu mới" chỉ-thêm. Lệnh này không ghi đè thứ đối tác đã sửa.

**Ai tạo phòng khám:** chỉ người vận hành nền tảng (Avalook). Giai đoạn 1 tạo bằng lệnh `scripts/tao-phong-kham.py` trên VPS. Màn quản trị nền tảng để sau.

**Màn "Thiết lập phòng khám"** dành cho quản lý của đối tác, là một wizard có thứ tự. Mỗi bước dùng lại được về sau:

1. **Thông tin phòng khám:** tên, logo, địa chỉ in phiếu.
2. **Cơ sở → tầng → phòng:** gắn mỗi phòng với bước nó làm được.
3. **Nhân sự:** nhập từ Excel mẫu, mời tài khoản, chọn bộ quyền có sẵn, tick cơ sở.
4. **Dịch vụ + giá:** nhập từ Excel mẫu.
5. **Thuốc + tồn đầu theo cơ sở:** nhập từ Excel mẫu. Tồn đầu sinh phiếu nhập kho, không ghi đè số tồn.
6. **Giờ mở cửa, ca làm.**
7. **Kiểm sẵn sàng:**
   - dịch vụ nào chưa có phòng làm được;
   - phòng nào chưa có người;
   - dịch vụ nào chưa có giá.

**Khuôn nhập Excel dùng chung cho mọi bước:**

- tải lên;
- máy đọc và **xem trước**: từng dòng một, lỗi đánh đỏ kèm lý do;
- người dùng bấm "Nhập";
- ghi **trong một transaction**, **idempotent theo mã** (nhập lại thì cập nhật, không nhân đôi);
- mỗi lần nhập là một **lô** có thể **hoàn tác cả lô**.

Dr4Women dùng luôn khuôn này cho danh mục và nhân sự Hào Nam. Không viết thêm script lẻ.

**Tạo tài khoản:** API phía máy chủ gọi GoTrue admin để mời. Khoá admin chỉ nằm trong API, không bao giờ xuống frontend.

## 9. Việc mở / chờ chốt sau

Mỗi câu đều đã có mặc định. Không chặn việc khởi động PR A–D.

| # | Câu hỏi | Mặc định nếu không ai chốt |
|---|---|---|
| Q1 | Giờ **mở cửa** (khác giờ ca) của Hào Nam có khác Kim Ngưu không? | Chung. Khác thì điền `clinic_location.settings.hours`. |
| Q2 | Hào Nam có quầy thu / két riêng, chốt ca thu ngân riêng không? | Có. Chốt ca theo cơ sở. |
| Q3 | Khách đặt lịch online chọn cơ sở ở đâu? | Biểu mẫu công khai thêm ô chọn cơ sở. Mặc định Kim Ngưu. |
| Q4 | Tên miền / thương hiệu cho đối tác (họ không nên thấy chữ "Dr4Women") | Quang chốt tên miền sản phẩm. Trước đó: tên/logo lấy từ `clinic`, không viết cứng. |
| Q5 | Đối tác rời đi: xuất trả dữ liệu (Nghị định 13/2023) | Script xuất theo `clinic_id`. Làm khi có đối tác thật. |

## 10. Kế hoạch triển khai

Theo QUY TRÌNH CHUẨN: mỗi PR một nhánh, một dải giờ migration, một cổng. Thứ tự bên dưới là phụ thuộc thật.

| PR | Nội dung | Phụ thuộc | Đổi hành vi khi chỉ có Kim Ngưu? |
|---|---|---|---|
| **A — Nền** | `staff_location` + backfill · `UNIQUE(id, clinic_id)` + FK ghép · `clinic_location.settings` + `cau_hinh_co_so()` · `vi_tri_lam_viec.location_id` · `visit.location_id` NOT NULL · audit lấy danh sách bảng tenant **từ `information_schema`**, bỏ danh sách viết tay | — | Không |
| **B — Cơ sở hiện hành** | Cookie + header + `_resolve_identity` (403/428) · `/chon-co-so` · chọn phòng khám khi có nhiều membership · nút đổi cơ sở + dải cảnh báo · cột cơ sở ở màn Nhân sự | A | Không (1 cơ sở → tự chọn) |
| **C — Đúng cơ sở trong nghiệp vụ** | Luật "cơ sở của thực thể thắng" · sửa `hang_cho.py:285`, các danh sách phòng, `booking.py` kiểm ca theo cơ sở, `locations[0]` ở 2 form · lọc hàng chờ / thu ngân / quầy thuốc / lịch trực · báo cáo lọc theo cơ sở + tổng | B | Không |
| **D — Kho theo cơ sở** | Mục 6.4 đầy đủ, gồm chuyển kho hai bước và FEFO theo cơ sở · báo cáo tồn theo cơ sở | A (chạy song song B/C được) | Không |
| **E — Mô phỏng 2 cơ sở** | `scripts/mo-phong/ngay_kham.py` chạy Kim Ngưu + Hào Nam cùng lúc. Khẳng định: 0 lượt chạm phòng / quầy / kho / lô của cơ sở kia; báo cáo tổng = tổng từng cơ sở | A–D | — (cổng bắt buộc trước khi bật Hào Nam) |
| *Dữ liệu (Tuyền, trên màn)* | Tạo Hào Nam · tầng/phòng/bước của phòng · vị trí + lịch trực · tick cơ sở cho nhân sự · phiếu nhập tồn đầu | A–E trên prod | **Bật Hào Nam = `is_active` true. Tắt lại được.** |
| **F — Tạo phòng khám từ mẫu** | `supabase/mau-phong-kham/` + `tao_phong_kham()` + `scripts/tao-phong-kham.py` · bài test: tạo tenant mới → mô phỏng 1 ngày khám chạy được | A | — |
| **G — Wizard + nhập Excel** | Khuôn nhập (xem trước / idempotent / hoàn tác lô) · 7 bước mục 8.2 · mời tài khoản qua GoTrue admin | F | — |

**Ràng buộc thứ tự quan trọng:** không bật Hào Nam trước khi B lên prod. Sau khi B có mặt, người được hai cơ sở mà không gửi header sẽ nhận 428. Giao diện của B chính là thứ gửi header đó.

## 11. Kiểm như thế nào

- **pytest trên DB chung** gồm:
  - `_resolve_identity`: 4 nhánh (có header hợp lệ / header không được phép / không header với 1 cơ sở / không header với 2 cơ sở);
  - trigger cấp lô khác cơ sở;
  - chuyển kho gửi / nhận / huỷ, tồn không âm khi hai người bấm cùng lúc;
  - FK ghép từ chối cơ sở của phòng khám khác.
- **Mô phỏng 2 cơ sở** (PR E) là cổng nghiệm thu chính. Kiểm bằng giấy không bắt được lỗi "lấy phần tử đầu tiên".
- **Bấm thật ở 375 và 1280:**
  - đăng nhập bằng tài khoản 2 cơ sở → màn chọn có gợi ý đúng theo lịch trực;
  - đổi cơ sở → hàng chờ đổi theo;
  - tiếp đón ở Hào Nam → khách hiện ở quầy Hào Nam, không hiện ở Kim Ngưu;
  - khách cũ của Kim Ngưu được nhận ra ở Hào Nam.
- **Kiểm tenant:** `tenant-scope-runtime-check.py` chạy với phòng khám thứ hai được tạo bằng `tao_phong_kham()` (PR F) thay cho dòng INSERT tay.
