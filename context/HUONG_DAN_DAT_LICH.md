# Hướng dẫn: Cách hoạt động của Đặt lịch hẹn (CAP-01 Phase 1 + 1.1)

> Cập nhật: 29/06/2026. Đang chạy production trên dr4women.vercel.app — commit
> `168c9fb` (Vercel Production build success). DB prod (atf) đã có migration `061`
> (schema) + `062` (seed). Ai sửa logic xin đọc kèm Decision Doc
> `.ai/tasks/T-20260629-CAP-01-capacity-budget-phase1.md` và `src/dashboard/lib/capacity.ts`.

---

## 1. Bức tranh tổng quát

Phòng khám nghẽn ở **một trạm: BS Phan Chí Thành** — bác sĩ này "chạm" mỗi ca khám
tới 2 lần (B1 hỏi bệnh + B3 đọc kết quả), giữa chừng rảnh khi siêu âm (B2). Nên hệ
thống **không giới hạn số ca thô**, mà giới hạn theo **ngân sách phút-Thành cho mỗi
khung 1 giờ** + **trần số ca KHÁM MỚI mỗi khung (newCap — cái phanh chính)**.

Có **2 cửa tạo lịch**, đều đi qua cùng một API `POST /api/appointments` nên **đều bị
engine ngân sách kiểm**:

| Cửa | File | Ai dùng | Mục đích |
|---|---|---|---|
| **Đặt lịch trong hồ sơ** | `patients/AppointmentBooking.tsx` | CSKH | Hẹn lịch cho bệnh nhân đã có hồ sơ (online/điện thoại/zalo…) |
| **Nhập BN mới** | `patients/new/NewPatientForm.tsx` | Lễ tân | Tạo bệnh nhân mới + đặt lịch, gồm cả **walk-in tới trực tiếp** |

Ngoài ra check-in/xác nhận đi qua PATCH (không tạo lịch, không bị engine kiểm):
`home/HomeCheckin.tsx`, `tasks/ConfirmBoard.tsx`.

---

## 2. Hai vai trò & hai loại khách

### a) CSKH — đặt lịch hẹn (online, điện thoại, zalo, facebook…)
- Vào hồ sơ bệnh nhân → khối **Đặt lịch hẹn** (`AppointmentBooking`).
- Chọn: **Loại khám** (Khám mới / Tái khám), **Siêu âm** (có/không), cơ sở, bác sĩ,
  ngày, giờ, **Kênh đặt** (Hotline/Zalo/Facebook/Giới thiệu…).
- Thấy **dải màu khung-giờ** (strip) báo khung nào còn chỗ, khung nào nặng (mục 4).
- Lịch tạo ra ở trạng thái **SCHEDULED** (chờ tới hẹn → check-in sau).

### b) Lễ tân — nhập BN mới & walk-in trực tiếp
- Vào **Nhập BN mới** (`NewPatientForm`). Có 2 nhánh:
  - **Đặt lịch thường**: chọn ngày/giờ tương lai → trạng thái **SCHEDULED**.
  - **Walk-in (khách tới trực tiếp hôm nay)**: kênh tự đặt **WALK_IN**, giờ = bây giờ
    → hệ thống **tự check-in luôn** (trạng thái **CHECKED_IN**), đẩy thẳng vào hàng đợi.
- Form này giờ cũng có **Loại khám** (mặc định **Khám mới** — vì đăng ký BN mới phần
  lớn là khám lần đầu) + **Có siêu âm**. Lễ tân đổi sang **Tái khám** khi khách cũ
  quay lại.

> **Vì sao bắt buộc chọn Loại khám:** hiện tại nếu request không gửi `patient_kind`,
> API **mặc định coi là Tái khám** (`route.ts:303`, để tương thích client cũ) → ca nặng
> bị coi là nhẹ, **newCap không kích hoạt** và đếm thiếu tải Thành. Cả 2 form đã luôn
> gửi field này. *Khuyến nghị (đề xuất task CAP-01.2):* đổi mặc định "thiếu thì RETURN"
> thành **trả lỗi 400 bắt buộc chọn**, để không ai vô tình bỏ trống.

### c) Phân biệt "khách online" vs "khách vãng lai trực tiếp"
| | Online / hẹn trước | Vãng lai (walk-in) tới trực tiếp |
|---|---|---|
| Ai nhập | CSKH (hoặc lễ tân nhánh thường) | Lễ tân nhánh walk-in |
| Kênh (`booking_channel`) | HOTLINE / ZALO_PK / FB_DR4WOMEN / REFERRAL | **WALK_IN** |
| Trạng thái sau khi tạo | **SCHEDULED** (chờ check-in) | **CHECKED_IN** (vào hàng đợi ngay) |
| Quota riêng trong ngân sách | dùng **online_quota_min** | dùng **walkin_quota_min** (giữ chỗ cho khách vãng lai) |

Hai loại **chia nhau cùng ngân sách phút-Thành** của khung giờ, nhưng có **hạn mức kênh
riêng**: hệ thống giữ một phần cho walk-in (`walkin_quota_min`) để khách tới trực tiếp
không bị lịch hẹn online chiếm hết, và ngược lại.

---

## 3. Luồng đi của một lượt khám (status lifecycle)

```
        CSKH/Lễ tân tạo lịch
                │
   ┌────────────┴─────────────┐
   │ online / hẹn trước        │ walk-in hôm nay
   ▼                           ▼
SCHEDULED                  CHECKED_IN ──────────┐
   │ (CSKH xác nhận)             (vào hàng đợi)  │
   ▼                                            │
CONFIRMED ──(khách tới, check-in)──► CHECKED_IN ┘
                                          │
                                    (gọi khám → khám xong)
                                          ▼
                                 COMPLETED / NO_SHOW / CANCELLED
```

- **SCHEDULED → CONFIRMED**: CSKH gọi xác nhận (action `cskh_confirm`).
- **→ CHECKED_IN**: lễ tân check-in khi khách tới (`checkin`); lỡ tay thì `undo_checkin`.
- **NO_SHOW**: khách không tới (`no_show`). **CANCELLED**: huỷ (không tính vào ngân sách).
- Engine ngân sách đếm **mọi ca trong khung trừ CANCELLED**.

---

## 4. Dải màu khung-giờ (budget strip) — đọc thế nào

Khi chọn cơ sở + ngày (+ bác sĩ), form gọi `GET /api/appointments/quote` và vẽ dải chip
theo từng khung 1 giờ. **Strip chỉ để GỢI Ý — không phải chỗ chọn giờ** (giờ vẫn nhập
bằng ô giờ / sơ đồ slot). 6 màu:

| Trạng thái | Nhãn | Nghĩa |
|---|---|---|
| `free` | **Trống** | Còn nhiều chỗ, đặt thoải mái |
| `few` | **Còn ít** | Sắp đầy, cân nhắc |
| `return_only` | **Chỉ tái khám** | Hết trần ca mới (newCap) — chỉ nhận Tái khám |
| `full_thanh` | **Đầy-Thành** | Cạn ngân sách phút-Thành — không nhận thêm ca nặng |
| `walkin_hold` | **Giữ vãng lai** | Phần còn lại đang giữ cho khách tới trực tiếp |
| `locked` | **Khoá** | Đã chạm trần tổng ca/giờ (max_total) |

---

## 5. Engine quyết định CHẶN hay CHO — thứ tự kiểm

Khi bấm Lưu, API chạy `evaluateBudget` (file `lib/capacity.ts`) theo đúng thứ tự sau;
gặp điều kiện vi phạm đầu tiên là **trả 409 + thông báo**, không tạo lịch:

1. **max_total** — tổng số ca/giờ đã chạm trần (mặc định 12) → *"Khoá"*.
2. **new_cap** — nếu ca này là **Khám mới** và khung đã đủ trần ca mới (mặc định 3)
   → chặn *"Khung đã đủ trần ca khám mới"* (Tái khám vẫn lọt). **Đây là phanh chính.**
3. **Quota kênh** — WALK_IN vượt `walkin_quota_min`, hoặc kênh khác vượt
   `online_quota_min` → chặn.
4. **Ngân sách phút-Thành** — tổng phút-Thành đã đặt + ca này > `thanh_budget_min`
   + `buffer_min` → *"Đầy-Thành"*.
5. **Cảnh báo mềm** — sát ngưỡng thì cho qua nhưng gắn cảnh báo (không chặn).

**Tải mỗi ca (phút-Thành) ước lượng tự động** nếu UI không gửi số cụ thể (`suggestLoad`):

| Loại | Không siêu âm | Có siêu âm |
|---|---|---|
| **Khám mới (NEW)** | 15' | 15' (+ 12' máy siêu âm) |
| **Tái khám (RETURN)** | 5' | 7' (+ 8' máy siêu âm) |

> Phần siêu âm (`sono_min`) được lưu/ước lượng để **đo tải máy & người siêu âm**, KHÔNG
> ăn vào phút-Thành. **Lưu ý Phase 1:** engine **chưa chặn** theo `sono_budget_min` —
> cột này đã có sẵn nhưng `evaluateBudget` mới chỉ từ chối theo max_total / newCap /
> quota kênh / ngân sách Thành. Chặn theo ngân sách siêu âm là việc của Phase sau.

### Lưới an toàn nhiều lớp (kể cả engine sai vẫn không vỡ)
- **Fail-open (DEC-8):** khung giờ chưa có dòng cấu hình ngân sách → **cho đặt bình
  thường** (không chặn nhầm).
- **Best-effort (DEC-7):** engine chỉ là lớp mềm ở app; **ràng buộc DB
  `appointment_no_doctor_overlap`** (1 bác sĩ không trùng 6 ca cùng lúc) vẫn là **chốt
  cuối** không thể vượt.
- WALK_IN **không được miễn** kiểm — vẫn bị chặn nếu vượt quota/ngân sách, chỉ là có
  hạn mức kênh riêng.

---

## 6. Cấu hình ngân sách (bảng `block_budget`) — seed hiện tại

Mỗi dòng = ngân sách cho **(cơ sở × bác sĩ × thứ × khung-giờ)**. Tra theo thứ tự ưu
tiên: dòng riêng bác sĩ+thứ → riêng bác sĩ → theo thứ → **dòng mặc định cơ sở**.

- **Dòng mặc định** (mọi bác sĩ, mọi ngày, giờ 8–22h): thanh 50' / sono 90' /
  online 35' / walk-in 10' / buffer 5' / **new_cap 3** / max_total 12.
- **Dòng riêng BS Thành** (khung tối 17–22h) — chặt hơn theo giờ cao điểm, ví dụ 19–20h:
  thanh 55' / new_cap 3 / max_total 12; 22h: thanh 30' / new_cap 1 / max_total 6.

Đổi cấu hình = sửa bảng `block_budget` (qua migration tracked, ví dụ `062`), **không
sửa code**.

> **Khi nào cần `NOTIFY pgrst, 'reload schema';`** — chỉ sau khi đổi **schema**
> (ADD COLUMN/TABLE… như migration `061`); nếu không reload, PostgREST cache cũ làm
> màn hình trống dù dữ liệu còn nguyên. Còn **đổi dữ liệu** (seed như `062`,
> hay sửa số trong `block_budget`) **không cần NOTIFY** — đọc lên ngay.

---

## 7. Tình huống thường gặp & xử lý

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Báo *"Khung đã đủ trần ca khám mới"* | newCap khung đó đã đầy | Đổi khung giờ khác (xem strip), hoặc nếu là tái khám thì chọn lại Loại khám = Tái khám |
| Báo *"Đầy-Thành / Khoá"* | Cạn ngân sách / max khung | Chọn khung "Trống/Còn ít" trên strip |
| Strip không hiện | Chưa chọn đủ cơ sở + ngày, hoặc cơ sở chưa có cấu hình ngân sách | Chọn đủ; nếu vẫn trống → khung fail-open, đặt vẫn được |
| Walk-in tạo xong không vào hàng đợi | Giờ không phải hôm nay → ra SCHEDULED chứ không CHECKED_IN | Đảm bảo nhánh walk-in đặt giờ = hôm nay |
| Số liệu newCap/tải lệch | Form không gửi Loại khám → bị coi Tái khám | Luôn chọn đúng Loại khám ở cả 2 form |

---

## 8. Lưu ý cho người sửa code sau này

- **Bất kỳ UI/luồng tạo lịch mới** nào cũng PHẢI gửi `patient_kind` + `need_sono`
  trong body, nếu không engine coi là Tái khám (xem memory `capacity-budget-patient-kind`).
  Đề xuất **CAP-01.2**: đổi mặc-định-RETURN thành bắt buộc (400) + chặn theo
  `sono_budget_min`.
- Múi giờ tính khung dùng **Asia/Ho_Chi_Minh** (`vnBlockOf`), không dùng giờ UTC thô.
- Logic engine nằm gọn ở `lib/capacity.ts` (thuần, có smoke test); API chỉ ráp dữ liệu
  rồi gọi `evaluateBudget`. Phase sau dự kiến dời vào Scheduling sub-graph (TODO D017).
</content>
