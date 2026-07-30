# ADR-0012 — Backend sở hữu hợp đồng: đổi/vứt frontend không ảnh hưởng backend

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-30 |
| **Deciders** | Quang — "code hoàn thiện backend đi để nếu đổi frontend như nào cũng không ảnh hưởng backend, hỏng hệ thống" |
| **Liên quan** | CLAUDE.md ("Frontend = UI only"), ADR-0004, ADR-0009, Phase 4 |

## Context
Mục tiêu: frontend là thứ thay được (đổi Next.js sang cái khác, thêm app mobile, thêm
màn cho phòng khám khác) mà backend không phải sửa và không thể bị làm hỏng.

Hiện trạng vi phạm mục tiêu này ở 2 chỗ:
1. **Dashboard đọc/ghi Supabase trực tiếp.** Ví dụ `/reports` đọc `booking_channel`,
   `/episodes` đọc `care_episode`, `app/api/*` dùng `getSupabaseService()` (service_role)
   — tức là frontend đang cầm quyền bỏ qua RLS. Bất kỳ frontend nào cũng có thể ghi sai
   dữ liệu mà backend không biết.
2. **Logic nghiệp vụ còn nằm trong `src/dashboard`** (Phase 4 chưa xong).

## Decision
1. **Hợp đồng = OpenAPI của FastAPI, có version (`/api/v1`).** Đây là mặt tiếp xúc duy
   nhất. Thay đổi phá vỡ hợp đồng ⇒ `/api/v2`, không sửa ngầm `v1`.
2. **Frontend chỉ được dùng Supabase trực tiếp cho `auth` và `realtime`** (đúng
   CLAUDE.md). Mọi đọc/ghi dữ liệu nghiệp vụ đi qua FastAPI.
3. **Service-role key rời khỏi frontend.** `getSupabaseService()` bị gỡ khỏi
   `src/dashboard`; `SUPABASE_SERVICE_ROLE_KEY` chỉ tồn tại trong env của `api`/`worker`.
4. **RLS siết đủ chặt để frontend không cần được tin.** Sau ADR-0009 + ADR-0004, một
   client cầm anon key + JWT hợp lệ chỉ đọc được đúng tenant của mình, và **không ghi
   được gì**. Đây là điều khiến "đổi frontend không hỏng hệ thống" thành đúng ở tầng DB
   chứ không phải lời hứa.
5. **Bất biến nghiệp vụ nằm ở DB + service layer**, không ở TSX: chống trùng slot, sức
   chứa, thứ tự gọi hàng đợi, gate của work item (ADR-0003, ADR-0011).
6. **Sinh client từ OpenAPI**, không viết tay type: frontend dùng type sinh tự động; CI
   fail nếu client lệch hợp đồng.
7. **Test hợp đồng chạy không cần frontend**: pytest gọi thẳng API; một frontend rỗng
   vẫn phải pass toàn bộ.

## Alternatives
| | Ưu | Nhược |
|---|---|---|
| **A. Backend sở hữu hợp đồng, FE thuần UI (chọn)** | FE thay được; bảo mật không phụ thuộc FE; test được không cần trình duyệt | phải gỡ toàn bộ đường đọc thẳng Supabase trong dashboard |
| B. Giữ Next.js BFF làm nơi chứa logic | ít việc trước mắt | đổi FE = mất logic; service_role nằm trong FE = FE bug là rò dữ liệu |
| C. Chỉ dùng Supabase (PostgREST) làm API | không phải viết backend | logic nghiệp vụ phức tạp (workflow, thanh toán) không diễn đạt được bằng RLS |

## Consequences
**Tích cực:** thêm app mobile / đổi framework = chỉ viết UI; kiểm thử và bảo mật không
phụ thuộc frontend; audit "ai làm gì" đầy đủ vì mọi ghi đều qua backend.
**Tiêu cực:** thêm một chặng mạng cho các màn đang đọc thẳng Supabase (chấp nhận được ở
tải hiện tại); phải viết endpoint cho mọi thứ frontend đang tự truy vấn.
**Kiểm chứng:** CI có test khẳng định `src/dashboard` không còn tham chiếu
`SUPABASE_SERVICE_ROLE_KEY`, và không `from("<bảng nghiệp vụ>")` ngoài auth/realtime.

## Trạng thái thực hiện (cập nhật 2026-07-30, W5 đợt 1)

**Đã gỡ service-role khỏi 3 chỗ** — nhờ policy thêm ở W1b/W3, không cần bypass RLS nữa:
`app/api/wards`, `app/api/patients/check-phone`, `app/(dashboard)/patients/new`.
Đọc `province`/`ward`/`patient` giờ đi bằng session của chính người gọi, nên còn được
lọc theo phòng khám thay vì thấy toàn hệ thống.

**Ranh giới đã có hàng rào, không còn là lời hứa.**
`src/dashboard/tests/service-role-boundary.test.mts` (chạy trong CI qua
`npm run test:boundary`) giữ một **danh sách trắng chỉ được ngắn đi**:
- thêm file mới đụng tới service-role ⇒ **CI đỏ**;
- để lại file đã hết dùng service-role trong danh sách ⇒ **CI cũng đỏ** (chống mục);
- trần cứng **19 file**, chỉ được hạ. W5 xong khi còn **2** (factory + route Auth-admin).

Test này còn tìm ra 3 chỗ mà `grep getSupabaseService` bỏ sót vì chúng tự tạo client
inline từ `SUPABASE_SERVICE_ROLE_KEY`: `api/roster`, `api/service-price`,
`settings/new-user`.

**Một vertical đã dời trọn sang FastAPI làm mẫu:** vòng đời `care_episode`.
`EpisodeService` + router `PATCH /api/v1/episodes/{id}`, gate vai trò bằng
`require_role(CSKH, MANAGEMENT, TRUONG_CA)` — khớp `canManageAppt` trong `roles.ts`, và
`require_role` nay trả về `RoleGuard` có `allowed_roles` đọc lại được nên test khẳng định
được cổng vai trò mà không cần dựng HTTP. Bản backend **chặt hơn** bản Next: đổi trạng
thái và ghi audit event nằm trong **cùng một transaction**, nên không thể có chuyện đóng
đợt khám mà thiếu event. Bật bằng `EPISODE_VIA_BACKEND=1`, mặc định tắt.

**Còn lại:** 14 route nghiệp vụ (đặt lịch/check-in, bệnh án, siêu âm, xét nghiệm, thu
tiền, service-log, sono, CSKH, roster, bảng giá). Mỗi entry trong danh sách trắng ghi rõ
nó phải về router nào.

## W5 đợt 2 — cụm lâm sàng (2026-07-30)

**4 route lâm sàng đã có bản backend đầy đủ**, mỗi cái sau một cờ, mặc định tắt:

| Route Next | Endpoint FastAPI | Cờ |
|---|---|---|
| `api/lab-result` POST/PATCH | `POST /api/v1/lab/orders` · `PATCH /api/v1/lab/results/{id}` | `LAB_VIA_BACKEND` |
| `api/ultrasound` POST | `POST /api/v1/ultrasound/measurements` | `ULTRASOUND_VIA_BACKEND` |
| `api/clinical-form` POST/PATCH | `PUT /api/v1/clinical-forms` | `CLINICAL_FORM_VIA_BACKEND` |
| `api/clinical-record` POST | `POST /api/v1/clinical-records` | `CLINICAL_RECORD_VIA_BACKEND` |

Mọi luật được port **nguyên vẹn**, kể cả những luật là *sự kiềm chế lâm sàng cố ý*:
EFW **nhập tay, không tự tính** (Hadlock chờ BS chốt công thức); cờ bất thường do bác sĩ
bấm, không suy từ số đo; siêu âm chỉ `ULTRASOUND_DOCTOR`, không nới; nhập KQ xét nghiệm
loại trừ Lễ tân/Quản lý (chốt 17/6); khoá hồ sơ sau **48h**; `FINALIZED` **và** `AMENDED`
đều bất biến theo TT13 (whitelist chứ không chỉ chặn FINALIZED).

**Bản backend chặt hơn bản nó thay ở 3 chỗ:**
1. `clinical-record` trước là **5 câu lệnh tuần tự** — hỏng giữa chừng để lại visit có hồ
   sơ mà không có đơn thuốc, hoặc lưu hồ sơ xong mất tiền sử. Nay **một transaction**.
2. `ultrasound` trước tạo visit rồi mới ghi record ở 2 bước — crash ở giữa để lại một
   visit rỗng dính vào lịch hẹn. Nay chung transaction.
3. Mọi ghi lâm sàng đều kèm audit event trong cùng transaction.

**Phần khó nhất được tách thành hàm thuần và test kỹ**: `merge_objective`. Bác sĩ có thể
đã mở form **trước khi** điều dưỡng nhập sinh hiệu; form của họ post lên vitals rỗng, ghi
đè mù sẽ **xoá số đo đã lấy trên người bệnh nhân**. Giữ giá trị cũ, chỉ ô không-rỗng mới
đè. 49 test cho cụm này.

**Một khác biệt có chủ đích:** route cũ từ chối `service_code` không có schema render
trong `lib/form-schemas` — một registry của frontend mà backend không nhìn thấy. Backend
validate theo `service_type` (danh mục thật của phòng khám); frontend giữ nguyên check
của nó trước khi hiện form. Đưa form schema vào DB là cách đúng, và ADR-0011 đã dự trù.

**Danh sách trắng vẫn 19 file** — đúng như thiết kế: con số chỉ giảm khi **xoá nhánh
legacy**, tức là sau khi bật cờ và chạy ổn trên staging. Lý do của 4 entry đã đổi thành
"đã port, chờ bật cờ".

## W5 hoàn tất phần port (2026-07-30)

**Mọi route nghiệp vụ đều đã có bản backend.** Danh sách trắng còn lại **toàn là
nhánh legacy chờ xoá**, không còn việc phải viết:

| Cụm | Endpoint FastAPI | Cờ |
|---|---|---|
| Lâm sàng | `lab/orders`, `lab/results/{id}`, `ultrasound/measurements`, `clinical-forms`, `clinical-records` | `LAB_`/`ULTRASOUND_`/`CLINICAL_FORM_`/`CLINICAL_RECORD_VIA_BACKEND` |
| CSKH | `cskh/actions`, `cskh/followup-calls` | `CSKH_VIA_BACKEND` |
| Dịch vụ | `service-log`, `sono/queue` | `SERVICE_LOG_VIA_BACKEND` |
| Đặt lịch | `appointments/bookings`, `PATCH appointments/{id}` | `BOOKING_VIA_BACKEND` |
| Cấu hình | `roster/shifts`, `service-prices` | `CONFIG_VIA_BACKEND` |
| Bệnh nhân | `PATCH patients/{id}` | `PATIENT_EDIT_VIA_BACKEND` |
| Đợt khám | `PATCH episodes/{id}` | `EPISODE_VIA_BACKEND` |
| Thu tiền | `payments` | `PAYMENT_VIA_BACKEND` |

**Ba route bỏ được service-role mà không cần backend**, nhờ policy thêm ở W1b/W3/W5:
`api/wards`, `patients/check-phone`, `patients/new` (province/ward),
`appointments/service-history` (appointment + care_episode), `appointments/quote`
(`block_budget` có policy đọc theo tenant từ `20260730000009` — nó là **cấu hình**, không
phải dữ liệu bệnh nhân, và chính nhân viên đặt lịch cần đọc).

Trần danh sách trắng **19 → 17**. Nó chỉ giảm tiếp khi **xoá nhánh legacy**, việc đó xảy
ra sau khi bật cờ chạy ổn — không phải khi viết xong backend.

### ⚠️ Phát hiện lớn hơn: backend chạy như service_role, RLS KHÔNG bảo vệ nó

Đây là hệ quả trực tiếp của chính ADR này mà tôi chưa nói rõ ở bản đầu. Khi mọi thứ đi
qua FastAPI, **FastAPI kết nối bằng quyền chủ database** — mọi policy RLS viết ở W3 đều
**không áp dụng** cho tiến trình đó. Nghĩa là **mỗi câu query trong backend phải tự lọc
`clinic_id`**, nếu không nó chạm tới mọi phòng khám.

Các service viết ở W5 đều làm đúng. Nhưng service có **trước** W5 thì không:

| Service | Query trên bảng tenant | Có lọc `clinic_id` |
|---|---|---|
| `patient_service` | 7 | **0** |
| `scheduling_service` | 4 | **0** |

Đã sửa `PatientService.update_patient` (nó update theo `clinic_patient_id` đơn thuần —
tức là sửa được bệnh nhân của phòng khám khác nếu biết id) và gate 2 endpoint
confirm/cancel trong `scheduling.py` vốn **không có gate vai trò nào**.

**Phần còn lại chưa rà hết** — xem task W8. Hôm nay vô hại vì chỉ có một phòng khám thật;
ngày có phòng khám thứ hai thì đó là rò dữ liệu chéo. Phải xong **trước** khi onboard
tenant thứ 2.
