# E2E — Mô phỏng ngày khám (đặt lịch + tiếp nhận)

Bot Playwright (script Node độc lập) giả lập luồng một buổi khám và **chỉ ra chỗ nghẽn**:

```
CSKH đặt lịch online hôm nay → Lễ tân check-in → Lễ tân nhập walk-in
→ Hệ tự cấp số khám → /queue đúng thứ tự → Board bác sĩ đồng bộ → (nếu được) B3 lab
```

## Cài & chạy

```bash
cd src/dashboard
npm i -D playwright           # đã thêm sẵn vào devDependencies
npx playwright install chromium

# Khai báo env (xem e2e/env.example), ví dụ:
export E2E_BASE_URL=http://localhost:3000
export E2E_RECEPTION_EMAIL=...  E2E_RECEPTION_PASSWORD=...
export E2E_CSKH_EMAIL=...       E2E_CSKH_PASSWORD=...

npm run e2e:intake
```

App phải đang chạy ở `E2E_BASE_URL` (`npm run dev` ở terminal khác, hoặc trỏ prod).

## An toàn (mặc định read-only)

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `E2E_ALLOW_WRITE` | `0` | `1` mới cho tạo dữ liệu test |
| `E2E_ALLOW_PROD_WRITE` | `0` | bắt buộc `=1` để ghi khi `BASE_URL` là production |
| `E2E_CLEANUP` | `0` | `1` = huỷ (cancel) lịch test sau chạy, **không xoá cứng** |

- Mọi bệnh nhân test có prefix tên **`E2E_TEST_`**.
- Thiếu credential/cổng → **SKIP mềm** + in hướng dẫn, không crash.
- KHÔNG migration, KHÔNG tự apply DB, KHÔNG `git add -A`, KHÔNG push.

## Báo cáo

In bảng ra console và ghi file:

```
src/dashboard/e2e-report/intake-day-simulation-<timestamp>.md
```

Bảng: `Phase | Scenario | Expected | Actual | Kết quả | Evidence | Bottleneck/Risk`, kèm phần trả lời các câu trọng tâm (lễ tân có kẹt? phải nhập tay số khám? walk-in auto check-in? queue hiện BN? board đồng bộ? lỗi auth/role? quote ổn?).

Exit code: `1` nếu có FAIL, `2` nếu lỗi cấu hình (thiếu BASE_URL / chưa cài Chromium), `0` còn lại.

## Trạng thái các Phase

| Phase | Trạng thái | Ghi chú |
| --- | --- | --- |
| **A — Smoke read-only** | ✅ Đã làm | Mở `/patients/new`, bảng "Tải hôm nay", không còn ô "Số khám" tay, bấm bảng → fill bác sĩ, `/queue` & `/tasks` không crash, soi console/network. |
| **E — Capacity/quote (read-only)** | ✅ Đã làm | Lấy `location_id` từ form → `GET /api/appointments/quote`, liệt kê khung giờ đầy/nghẽn. |
| **B — Online appt + check-in** | ⏳ Stub có guard | Cần chạy thật để chốt selector của widget tuỳ biến (xem dưới). |
| **C — Walk-in** | ⏳ Stub có guard | nt. |
| **D — Queue ordering** | ⏳ Stub có guard | Đọc lại `/queue` so sánh online vs walk-in sau khi B/C tạo data. |
| **F — B3 lab** | ⏳ Stub có guard | `POST /api/lab-result` (bác sĩ) → `PATCH` trả KQ (điều dưỡng) → lên làn B3. |

### Vì sao B/C/D/F chưa tự động hoá đầy đủ

Form (`NewPatientForm`, `AppointmentBooking`) **không có `data-testid`** và dùng các widget
tuỳ biến (`DateField`, `Time24Input`, combobox bác sĩ). Tự động hoá ghi nhiều bước qua các
widget này cần **chạy thử trên dev để chốt selector** — làm "mù" rồi khẳng định chạy đúng là
không trung thực, và chạy ghi chưa kiểm dễ tạo rác/đụng prod. Khung hàm + guard (`CAN_WRITE`)
đã sẵn trong `intake-day-simulation.mjs`; cần một vòng chạy `E2E_HEADLESS=0` trên dev để quan
sát rồi điền selector cho các bước:

- Phase B: điền `Họ tên` = `E2E_TEST_ONLINE_<ts>`, chọn Dịch vụ/Bác sĩ(Thành)/Ngày(hôm nay)/Giờ/Kênh(HOTLINE), submit → bắt response `POST /api/appointments` lấy `appointment_id`; đăng nhập Lễ tân → `/home` → HomeCheckin → "Check-in"; đọc lại `GET /api/appointments?date=` xác nhận `CHECKED_IN` + có `queue_number`; mở `/queue` thấy BN.
- Phase C: variant walk-in của `/patients/new`, dùng bảng "Tải hôm nay" bấm chọn bác sĩ, submit → kỳ vọng `WALK_IN` + auto `CHECKED_IN` + có `queue_number`.
- Phase D: so callRank — khách có hẹn đúng giờ phải đứng trên walk-in/trễ trong cùng cột bác sĩ ở `/queue`.
- Phase F: với BN đã check-in, `POST /api/lab-result {clinicPatientId, appointmentId, test_name}` → BN CHƯA lên B3; `PATCH /api/lab-result {lab_result_id, result_value}` → BN lên làn "🔔 Chờ đọc kết quả" ở `/queue` và badge ở board bác sĩ.

Nhắn để mình hoàn thiện B–F sau khi bạn chạy được A/E trên dev (cho mình DOM/screenshot của widget ngày–giờ là đủ).
