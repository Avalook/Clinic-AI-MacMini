# CD-01 — Bác sĩ chỉ định dịch vụ

> **Lát (slice)** = đơn vị nhỏ nhất giao được cho một người làm.
> Khuôn 8 mục, không thêm không bớt. Ví dụ xuyên suốt: **CI12** được BS chính chỉ định
> siêu âm đầu dò + xét nghiệm máu.

| | |
|---|---|
| **Mã** | CD-01 |
| **Module chủ** | `service_order` (Chỉ định) |
| **Trạng thái** | ĐÃ CODE 23/09 — backend + màn bàn khám; chưa bấm thật trên trình duyệt |
| **Ngày** | 23/09/2026 |

---

## 1. Trigger — ai bấm, ở màn nào

| | |
|---|---|
| **Màn** | Bàn khám bác sĩ chính · `/kham/[consultationId]` |
| **Vai** | `DOCTOR` (bác sĩ) và `MEDICAL_SECRETARY` (thư ký y khoa) — **quyền như nhau**, chốt tin #149 |
| **Nút** | `[Xác nhận 2 chỉ định]` — nút nói rõ việc, không phải `[OK]` (luật #150) |
| **Trước đó** | Form chọn dịch vụ **tự lưu nháp**, không có nút `[Lưu]`. Tự lưu **không** phát sự kiện. |

---

## 2. Command — lệnh gửi lên

```text
PlaceServiceOrders
```

```http
POST /luot-kham/consultations/{consultation_id}/service-orders
Idempotency-Key: <bắt buộc>
```

**Tham số**

| Trường | Kiểu | Nghĩa |
|---|---|---|
| `consultation_id` | uuid | lượt khám nào |
| `service_codes` | text[] | danh sách mã dịch vụ, ví dụ `["SA-DAUDO", "XN-MAU"]` |
| `note` | text? | dặn dò kèm theo |
| `expected_version` | int | bản của lượt mà màn đang thấy, để chặn hai người sửa đè nhau |

**Lệnh bị từ chối khi:** không đủ quyền · lượt đã đóng · mã dịch vụ không còn bán ·
`expected_version` cũ · `Idempotency-Key` trùng mà tham số khác (trả lỗi, **không** âm thầm bỏ qua).

---

## 3. Events — sự kiện phát ra

| Sự kiện | Khi nào | Payload | Công khai? |
|---|---|---|---|
| `service_order.placed` | mỗi dịch vụ **một** sự kiện | `order_id`, `service_code`, `service_name`, `consultation_id`, `patient_id`, `ordered_by`, `selection_status=PENDING`, `billing_status=UNPAID` | `public: true` |

- Tên: `danh_từ.quá_khứ`. **Không** dùng `service.order_needed` (đó là mệnh lệnh trá hình).
- Hai dịch vụ ⇒ **hai** sự kiện, chung một `correlation_id` (mã lượt khám của CI12).
- `causation_id` = id của lệnh `PlaceServiceOrders`.
- `aggregate_type = service_order`, `aggregate_id = order_id`, `aggregate_version = 1`.
- Payload theo luật **fact có chọn lọc**: đủ để bên nghe quyết định, không chép cả bảng,
  **không có** chẩn đoán hay ghi chú lâm sàng (đó là PHI).

**Không phát:** `consultation.updated`, `dashboard.refresh`, hay sự kiện cho việc tự lưu nháp.

---

## 4. Views — ai đọc sự kiện này

| Bên nghe (`consumer`) | Dùng để làm gì | Đồng bộ hay nền |
|---|---|---|
| `worklist_le_tan` | lễ tân thấy "CI12 có 2 chỉ định chờ khách quyết" | nền (realtime đẩy màn) |
| `journey_projection` | vẽ dòng thời gian hành trình CI12 | nền |
| `cskh_360` | hồ sơ khách: đã được chỉ định gì | nền |
| `bang_gia_tam_tinh` | ước tính tiền cho khách xem | nền |
| `ai_goi_y_phong` (sau này) | gợi ý phòng trống cho SA | nền |

Bốn bên đầu **chưa tồn tại** thì thêm sau cũng không phải sửa lại module Chỉ định.
Đó là chỗ trả lời câu "LEGO để làm gì".

---

## 5. Constraint — luật ép ở đâu

| Luật | Ép ở đâu | Cụ thể |
|---|---|---|
| Một lệnh gửi hai lần chỉ tạo một lần | **Postgres** | `UNIQUE(clinic_id, idempotency_key)` |
| Không tạo trùng cùng một dịch vụ đang mở trong một lượt | **Postgres** | unique một phần trên `(consultation_id, service_code)` khi chưa huỷ |
| Chỉ định luôn là chính thức, không có bước duyệt | **Code lệnh** | bỏ hẳn đường `draft → authorize` |
| Không tạo chỉ định cho lượt đã đóng | **Code lệnh** | kiểm trạng thái lượt |
| Dữ liệu không rò sang phòng khám khác | **Postgres (RLS)** | mọi câu đều lọc `clinic_id` |
| State và event ghi cùng lúc | **Một giao dịch** | sai một cái thì hỏng cả hai |

Cột "ép ở đâu" là bắt buộc: **đụng tranh chấp thì phải ép ở Postgres**, không tự khoá trong Python
(`docs/SO-LUAT.md` Phần 6).

---

## 6. Hotspot — chỗ chưa chốt

1. **Bỏ chỉ định đã tạo:** huỷ (`service_order.cancelled`) hay ghi nhầm (`entered-in-error`)?
   Hai cái khác nhau về kế toán. → cần Tuyền chốt.
2. **Chỉ định đúng dịch vụ khách vừa từ chối** ở lượt này thì có chặn không, hay chỉ cảnh báo?
3. **Gói dịch vụ** (một mã kéo theo nhiều dịch vụ con) phát một hay nhiều sự kiện?

Chưa chốt thì **không code**, và cũng không tự đoán (luật làm việc với Claude).

---

## 7. Time source — có hẹn giờ không

Không. CD-01 không sinh hẹn giờ nào.

*(Nếu sau này muốn "chỉ định quá 30 phút chưa ai chốt thì nhắc lễ tân", nó là một lát riêng,
dùng `scheduled_message`, không nhét vào đây.)*

---

## 8. Given / When / Then — nghiệm thu

```text
G1
  Given lượt khám CI12 đang mở, BS chính đang khám
  When  PlaceServiceOrders(["SA-DAUDO","XN-MAU"])
  Then  2 dòng service_order, selection=PENDING, billing=UNPAID
        + 2 sự kiện service_order.placed, cùng correlation_id
        + 4 bên nghe × 2 sự kiện = 8 dòng event_delivery ở trạng thái PENDING

G2  (bấm hai lần do mạng)
  Given G1 đã chạy
  When  gửi lại đúng lệnh đó, cùng Idempotency-Key
  Then  vẫn 2 dòng, vẫn 2 sự kiện — không nhân đôi

G3  (thư ký y khoa)
  Given người bấm là MEDICAL_SECRETARY
  When  PlaceServiceOrders(...)
  Then  thành công, không cần ai duyệt (tin #149)

G4  (lượt đã đóng)
  Given lượt CI12 đã đóng
  When  PlaceServiceOrders(...)
  Then  bị từ chối, không state nào đổi, không sự kiện nào phát

G5  (hai người cùng sửa)
  Given màn của thư ký đang giữ expected_version = 3, thực tế đã là 4
  When  PlaceServiceOrders(...)
  Then  bị từ chối kèm thông báo "màn đã cũ, tải lại"
```

**Luật thông tin đủ (information completeness):** mọi ô hiện trên màn lễ tân ở mục 4
phải chỉ ra được sự kiện nào sinh ra nó. Chỉ không được ⇒ lát này chưa xong.

---

## Phụ lục — đã làm gì (23/09/2026)

| Thứ | Ở đâu |
|---|---|
| Lệnh `PlaceServiceOrders` | `src/clinicai/services/chi_dinh_service.py` |
| Endpoint `POST /luot-kham/consultations/{id}/service-orders` | `src/clinicai/api/v1/routers/luot_kham.py` |
| Sự kiện `service_order.placed` | khai ở `src/clinicai/events/catalogue.py` |
| Đường proxy `chi-dinh` | `src/dashboard/app/api/luot-kham/route.ts` |
| Nút `[Xác nhận N chỉ định]` | `src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx` |
| Test G1–G5 + hai ca quyền | `src/tests/services/test_chi_dinh_db.py` |

**Bảng nút/link đã đụng**

| Màn | Nút | Đi đâu | Vai nào thấy |
|---|---|---|---|
| Bàn khám `/ban-kham/[phòng]` | `[Xác nhận N chỉ định]` | `chi-dinh` → `POST …/service-orders` | DOCTOR, TKYK |
| Bàn khám | `[Duyệt N chỉ định nháp (bản cũ)]` | `duyet-chi-dinh` → `…/authorize-orders` | chỉ hiện khi còn bản nháp cũ |

## Đường cũ còn sống (xoá khi nào)

`draft-orders` và `authorize-orders` **giữ nguyên**, vì trong database còn những
bản nháp tạo trước hôm nay và chỉ bác sĩ mới dọn được. Xoá cả hai endpoint, ba
sự kiện `service_order.draft_*` và nút "bản cũ" trong **một commit**, khi:

1. `SELECT count(*) FROM service_order WHERE exec_status = 'draft'` trả về 0 trên prod, và
2. không màn nào còn gọi `nhap-chi-dinh` / `duyet-chi-dinh`.
