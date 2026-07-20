# CHANGELOG — ClinicAI Dr4Women
> Mỗi entry = 1 packet Claude Code. Mới nhất trên cùng. Mục đích: báo cáo tổng quan thay đổi.

## [LOCAL — chưa push]

### 2026-06-19 · T-DASH-DATEFIELD-CLAMP-02 · FIX bug gõ liền "782019"→07/12/019 + không xóa được dấu "/" · commit `chưa commit`
- **Bug (CLAMP-01):** input controlled tự chèn "/" rồi đọc lại → nhánh maskSlashed thấy tháng "82" kẹp về "12" (ra 07/12/019). Backspace lại bị buildDisplay tự thêm "/" cuối → kẹt không xóa được qua dấu gạch.
- **Fix:** BỎ nhánh maskSlashed — LUÔN re-mask từ chuỗi SỐ thuần (bỏ "/"), nên gõ liền "782019" → đúng 07/08/2019. Thêm cờ `deleting` (chuỗi mới ngắn hơn): khi backspace KHÔNG tự thêm "/" cuối → xóa mượt qua cả dấu gạch tới rỗng.
- **VERIFY:** mô phỏng gõ từng phím + backspace (node) khớp; tsc + eslint + `next build` sạch.

### 2026-06-19 · T-DASH-DATEFIELD-CLAMP-01 · Ô ngày KẸP phạm vi khi gõ (ngày 1–31, tháng 1–12, năm 1900–nay) · commit `chưa commit`
- **Sửa lỗi:** `DateField` trước chỉ hiển thị thô số gõ vào (để lọt ngày 33 / tháng 34 / năm 3245), chỉ âm thầm reject lúc emit ISO → người dùng thấy ngày bậy. Senior-bug.
- **Nay KẸP NGAY khi gõ:** ngày 1–31, tháng 1–12, năm [minYear..maxYear] (suy từ min/max: ô ngày sinh max=hôm nay → 1900..năm nay; ô ngày khám → 1900..nay+10). Năm 4 chữ số vượt khoảng → kẹp về biên (3245 → năm nay).
- **Nhận diện gõ LIÊN TỤC:** số đầu ≥4 = ngày 1 chữ số, ≥2 = tháng 1 chữ số → tự nhảy ô. "782019"→07/08/2019; "07082019"→07/08/2019; "33342019" KHÔNG ra ngày 33 (kẹp 03/03 + năm kẹp).
- **Ô "Chỉ biết năm"** (NewPatientForm): cũng kẹp tối đa 4 chữ số + > năm nay → năm nay (không nhập 3245).
- **VERIFY:** tsc + eslint + `next build` sạch + test máy trạng thái mask (node).

### 2026-06-19 · T-DASH-INTAKE-WORDING-REQ-SEARCH-01 · Wording "Tạo bệnh nhân" + mục bắt buộc (*) + cảnh báo SĐT trùng (deploy) + tìm bỏ dấu · commit `chưa commit`
- **Wording đồng bộ → "Tạo bệnh nhân":** bỏ "khách vãng lai" / "khách hàng mới" / "khách hàng" ở luồng tạo BN. Sửa `NewPatientForm` (tiêu đề, nút Tạo, cảnh báo trùng), `nav-items` (nhãn + bỏ override "Vãng lai" của ĐD), `patients/new/page`, `CustomersView`.
- **Bắt buộc điền + dấu `*`:** thêm `*` cho Ngày sinh / SĐT chính / Giới tính (ngoài Họ tên + Cơ sở). Khoá nút Lưu tới khi đủ (`canSubmit`) + chặn trong `save()` với báo lỗi rõ.
- **FIX cảnh báo SĐT trùng KHÔNG hiện trên deploy:** `/api/patients/check-phone` trước gọi FastAPI (deploy không reachable → luôn rỗng → không cảnh báo). Nay tra THẲNG Supabase `patient.phone_primary/secondary` (như guard lúc submit) → cảnh báo ngay khi gõ đủ 10 số.
- **Tìm bỏ dấu + hoa-thường:** `PatientListView` đổi `toLowerCase` → `unaccentVi` ("Hoà"/"Hòa"/"HOA" + khớp một phần). Các list khác (customers/patients/home checkin) vốn đã dùng unaccent.
- **"PT":** chỉ còn ở `sk.ts`/`hmvs.ts` = "Đông máu cơ bản (PT, APTT, Fibrinogen)" — PT ở đây là xét nghiệm Prothrombin Time, KHÁC "Phẫu thuật" (đã đổi từ T-DASH-INTAKE-UX-01) → GIỮ.
- **VERIFY:** tsc + eslint + `next build` sạch.

### 2026-06-19 · T-DASH-TRUONGCA-OPSADMIN-01 · Trưởng ca = quản trị VẬN HÀNH (dưới Quản lý) · commit `chưa commit`
- **Mở rộng quyền Trưởng ca** (theo yêu cầu sếp, ĐẢO quyết định 17/6 cũ "chỉ hành chính"): thêm helper `isOpsAdmin = MANAGEMENT || TRUONG_CA`. TC giờ vào + sửa được phần vận hành: `/appointments` (+ `canManageAppt` hủy/phân lại lịch), `/patients`, `/cskh-today`, `/cashier/thuoc|dich-vu` (+ ghi bảng giá), `/schedule` + `/schedule/edit` (+ ghi roster), `/work-sessions`, `/reports`.
- **Ranh giới "thấp hơn quản lý":** `/settings` (tạo user / cấu hình hệ thống) VẪN chỉ `isAdminRole` (MANAGEMENT). **LÂM SÀNG = CHỈ XEM** (TC không thuộc `canWriteClinical`; xem tiến trình khám qua "Theo dõi buổi"). "Công việc của tôi" của TC giữ placeholder (chờ PK xem xét).
- Đổi gate `isAdminRole` → `isOpsAdmin` ở: reports, patients, schedule/edit, schedule, api/roster; thêm TRUONG_CA vào gate ghi `service-price`.
- **VERIFY:** tsc + eslint + `next build` sạch.

### 2026-06-19 · T-DASH-LETAN-DD-TESTACCT-01 · Tài khoản test rõ tên cho Lễ tân + Điều dưỡng · seed `chưa apply`
- **CHECK:** 2 vai ĐÃ tách sẵn ở `lib/roles.ts` — Điều dưỡng (`NURSE_ULTRASOUND`) = `canWriteClinical` (ghi Sinh hiệu + nhập hộ "Lý do khám bệnh"); Lễ tân (`RECEPTION`) = hành chính, KHÔNG lâm sàng. DB có staff cả 2 (ĐD 16, Lễ tân 2) NHƯNG 2 lễ tân tên "ĐD Huế/ĐD Quỳnh Anh" (dễ nhầm), CHƯA có tài khoản test rõ tên như các vai khác ("Thu ngân"/"Trưởng ca"/"Thư ký Y khoa").
- **Seed `057_letan_dieuduong_staff.sql`** (re-runnable, IF NOT EXISTS): thêm 2 staff "Lễ tân" (RECEPTION) + "Điều dưỡng" (NURSE_ULTRASOUND) để hiện rõ ở role-picker cho PK test phân quyền. KHÔNG cần migration CHECK (2 dept vốn hợp lệ). **CHƯA APPLY** — cần Quang chạy (lệnh ở báo cáo).
- Xác nhận distinction "Lý do khám bệnh" (BS đưa, ĐD nhập — chief_complaint) vs "Vấn đề khiến BN đi khám" (CSKH khai — `patient.van_de_di_kham`) ĐÃ có sẵn trong hệ thống.

### 2026-06-19 · T-DASH-PAYMENT-01 · Bảng payment: 2 màn thu ngân + thanh tiến trình Lễ tân ĐỒNG BỘ thật · commit `chưa commit`
- **Migration 056 `create_payment`** (forward+down): bảng `payment(visit_id, kind∈{thuoc,dich_vu}, status PAID, amount, paid_by_staff_id, paid_at)`, UNIQUE(visit_id,kind), RLS SELECT authenticated (ghi service-role). **CHƯA APPLY DB** — classifier chặn DDL lên prod; cần Quang chạy (lệnh ở báo cáo). Code degrade graceful nếu bảng chưa có (query lỗi → coi như rỗng, không crash).
- **API `/api/payment`** (POST upsert PAID / DELETE hoàn tác): gate vai thu ngân + kind thuộc quyền vai (CASHIER_THUOC→thuoc, CASHIER_DV→dich_vu, CASHIER→cả hai). 42P01 (bảng chưa có) → 503 báo rõ.
- **Thu ngân (`CashierWorkBoard`)**: nút "Đã thanh toán" giờ LƯU THẬT (POST) + "Hoàn tác" (DELETE); seed `paidInit` từ bảng payment để giữ qua tải lại; `router.refresh()` sau khi lưu để đồng bộ.
- **Lễ tân + Trưởng ca (`VisitStatusBoard`)**: mốc "Đã thanh toán" tích xanh khi **đã thu ĐỦ** = dịch vụ (luôn có dịch vụ khám) + thuốc (nếu lượt có đơn). Tính server: đọc `payment` + `prescription`. `reachedCount` thêm tham số `paid` → reached 3.
- **Realtime**: `VisitStatusRealtime` subscribe thêm bảng `payment` → thu ngân chốt thu là thanh tiến trình Lễ tân tự tích xanh (không cần tải lại).
- **VERIFY:** tsc + eslint + `next build` sạch. File: migration 056 (+down), `api/payment/route.ts` (mới), `CashierWorkBoard.tsx`, `tasks/page.tsx`, `VisitProgress.tsx`, `VisitStatusBoard.tsx`, `VisitStatusRealtime.tsx`, `home/page.tsx`, `truong-ca/page.tsx`.
- **NỢ:** (a) APPLY migration 056 lên Supabase (lệnh ở báo cáo) rồi `--mark-applied`; (b) cổng QR thật; (c) số tiền `amount` lưu tạm tính (giá phần lớn NULL).

### 2026-06-19 · T-DASH-VISIT-PROGRESS-GRAB-03 · Mốc 3 "Hoàn tất"→"Đã thanh toán" + FIX realtime nghe thiếu bảng appointment · commit `chưa commit`
- **Đổi mốc 3 "Hoàn tất" → "Đã thanh toán"** (yêu cầu sếp). `reachedCount` cap ở 2 (Đang khám=IN_PROGRESS · Khám xong=appt COMPLETED) — mốc "Đã thanh toán" chưa có bảng billing nên không tự tích, hiện "đang tới" (hồng pulse) chờ thu ngân.
- **FIX "đồng bộ chậm" (bác sĩ khám xong mà Lễ tân chưa tích "Khám xong"):** `VisitStatusRealtime` trước CHỈ nghe bảng `visit`. Nhưng "Khám xong" = `appointment.status=COMPLETED` (bác sĩ "Lưu & Khám xong" cập nhật bảng **appointment**, KHÔNG đụng visit) → realtime không fire → board không tự refresh. Nay subscribe **CẢ `visit` VÀ `appointment`**.
- **Lưới an toàn:** thêm poll `router.refresh()` mỗi 30s — nếu bảng nào chưa bật realtime replication thì vẫn đồng bộ chậm nhất ~30s. Realtime lo cập nhật tức thời (debounce 1.5s).
- **VERIFY:** tsc + eslint + `next build` sạch. File: `VisitProgress.tsx`, `VisitStatusRealtime.tsx`.

### 2026-06-19 · T-DASH-CASHIER-PAY-01 · Màn thu ngân "Công việc của tôi": BN đang khám + thu tiền dịch vụ/thuốc + QR demo · commit `chưa commit`
- **Thay placeholder** `CashierWorkBoard` bằng màn THU TIỀN thật: bảng 2 cột — TRÁI ô gộp "Bệnh nhân" (tên + mã + SĐT); PHẢI khoản thu theo mode.
- **ĐỒNG BỘ THẬT (cái đã có ở khâu khác):** Dịch vụ = dịch vụ khám (`appointment.service_type`) + CLS bác sĩ chỉ định (`lab_result` theo appointment) + dịch vụ ĐD làm (`service_log` hôm nay). Thuốc = đơn thuốc bác sĩ kê (`prescription` của lượt khám). Giá best-effort khớp tên với `service_price` (chỉ dòng có đơn giá) — chưa khớp/chưa nhập → để trống "—".
- **Mode theo vai:** CASHIER_THUOC=[thuoc], CASHIER_DV=[dich_vu], CASHIER=cả hai (toggle). List = BN có `visit` tạo hôm nay (đang/đã khám).
- **Khâu CHƯA CÓ → để trống (demo, không bịa):** nút "Thanh toán" → hiện ô **mã QR placeholder** (chưa nối cổng) → "Đã thanh toán". Trạng thái đã-thu **CHỈ ở client, KHÔNG lưu** (chưa có bảng billing) — ghi rõ ở header + có "Hoàn tác". Khi nối cổng/billing sau sẽ thay QR thật + lưu DB.
- **VERIFY:** tsc + eslint + `next build` sạch. File: `CashierWorkBoard.tsx` (viết lại), `tasks/page.tsx` (thêm `CashierTasks` server-fetch + gate mode theo vai).
- **NỢ:** (a) bảng billing/phiếu thu để LƯU "đã thanh toán" (hiện ephemeral); (b) cổng QR thật; (c) giá thuốc trong `drug_catalog` phần lớn NULL → cột giá thuốc thường trống; (d) khớp giá theo tên là best-effort (chưa map service_type_id → service_price).

### 2026-06-19 · T-DASH-VISIT-PROGRESS-GRAB-02 · Mốc cuối "Thanh toán"→"Hoàn tất" + FIX "Khám xong" đọc đúng nguồn · commit `chưa commit`
- **Đổi mốc 3 "Thanh toán" → "Hoàn tất"** (yêu cầu sếp). Lý do bỏ "Thanh toán": thu ngân hiện CHỈ là **bảng giá + placeholder**, CHƯA có luồng billing — `CashierWorkBoard` tự ghi "chưa có dữ liệu phiếu thu"; grep toàn migration **0 cột** paid/payment/invoice. Không có dữ liệu để tự tích → không đặt mốc "Thanh toán".
- **FIX QUAN TRỌNG — "Khám xong" phải đọc `appointment.status=COMPLETED`, KHÔNG phải `visit.FINALIZED`:** dashboard KHÔNG bao giờ tự set `visit.FINALIZED` (mọi route ghi rõ "KHÔNG đụng visit.status/FINALIZED"); "khám xong" = bác sĩ "Lưu & Khám xong" → `appointment.COMPLETED`. Map cũ (Khám xong=FINALIZED) sẽ **không bao giờ xanh** → thanh kẹt ở "Đang khám". Nay join `appointment.status` vào query (home + truong-ca).
- **Map mới 3 mốc:** Đang khám = visit IN_PROGRESS · Khám xong = appt COMPLETED · Hoàn tất = visit FINALIZED/AMENDED (hồ sơ chốt — gate riêng, chưa nối nút chốt nên thường còn ở bước "đang tới"). Badge + đồng hồ chờ cũng suy từ appt COMPLETED (BN khám xong → badge "Đã khám xong", đồng hồ dừng) thay vì kẹt "Đang khám".
- **VERIFY:** tsc + eslint + `next build` sạch. File: `VisitProgress.tsx`, `VisitStatusBoard.tsx`, `home/page.tsx`, `truong-ca/page.tsx`.

### 2026-06-19 · T-DASH-VISIT-PROGRESS-GRAB-01 · Bảng "Trạng thái BN buổi khám" kiểu thanh tiến trình Grab + cập nhật liên tục · commit `chưa commit`
- **Redesign `VisitStatusBoard`** (Lễ tân trang chủ + dùng chung Trưởng ca): bảng 2 cột — **Ô 1** gộp đủ thông tin (tên BN + mã · bác sĩ · dịch vụ · **badge trạng thái live** + đồng hồ chờ đếm liên tục từ check-in + giờ vào); **Ô 2** = thanh tiến trình.
- **`ProgressStepper` viết lại kiểu Grab — 3 MỐC:** `Đang khám → Khám xong → Thanh toán`. Node tròn + đoạn nối; **đến mốc nào tích xanh (✓) mốc ấy**; mốc đang tới = chấm hồng pulse. Map từ `visit.status`: Đang khám=IN_PROGRESS, Khám xong=FINALIZED/AMENDED.
- **"Thanh toán" = unbacked (xám, KHÔNG tự xanh):** chưa có nguồn dữ liệu billing/thu ngân → giữ honest (không bịa tích xanh), tooltip "Chờ thu ngân — chưa nối dữ liệu thanh toán". Khi nối vertical thu ngân sau sẽ cho tích.
- **"Cập nhật liên tục"** = `VisitStatusRealtime` (client): subscribe `postgres_changes` bảng `visit` → debounce 1.5s → `router.refresh()` (cùng khuôn AppointmentsRealtime). Pill "● Cập nhật liên tục +N" ở cạnh tiêu đề (chỉ section Lễ tân).
- **VERIFY:** tsc + eslint + `next build` sạch (0 lỗi). File: `VisitProgress.tsx`, `VisitStatusBoard.tsx`, `VisitStatusRealtime.tsx` (mới), `home/page.tsx`.
- **NỢ:** mốc "Thanh toán" chờ nối thu ngân; bỏ 4 mốc cũ (Hẹn/Xác nhận/Check-in/Chờ SA-XN) — gộp gọn còn 3 mốc theo yêu cầu sếp 19/6.

### 2026-06-19 · T-DASH-TAIKHAM-PAGER-01 · Nút "Tái khám" (CSKH/Lễ tân) + pager ◀▶ lượt khám (Bác sĩ/TKYK) · commit `chưa commit`
- **Phần 1 — Nút "Tái khám":** trong popup "Phiếu khám bệnh" ở *Danh sách bệnh nhân*, thêm nút **Tái khám** cạnh **Đóng** → `router.push('/patients/[id]')` (trang đã có sẵn: hành chính giữ nguyên + form đặt lịch bên dưới). Gate `showRebook` = CSKH || Lễ tân (server `patient-list/page.tsx`). Bác sĩ KHÔNG thấy (không thuộc canWriteIntake).
- **Phần 2 — Pager lượt khám:** thêm `◀ trang i/n ▶` trên dòng tiêu đề "Phiếu khám bệnh". Trang 1 = lượt mới nhất; ▶ lùi về lượt cũ, ◀ tiến tới lượt mới. Lượt cũ **luôn khóa ghi** (`viewingPast` → `ro`, ẩn nút Lưu, ẩn form siêu âm, `save()` chặn sớm). Gate `enableVisitPager`: DoctorWorkBoard (bác sĩ/TKYK/lễ-tân-clone) bật cứng; patient-list bật cho bác sĩ. `pages` dựng 1 lần từ lượt-hiện-tại + lịch sử; component remount theo `key={appt.id}` nên tự reset.
- **Phần 3 — "Bản nháp": BỎ** theo quyết định sếp (19/6). Upsert hiện tại vốn "giữ lần lưu cuối" → không cần đụng. KHÔNG migration, KHÔNG đụng luật bất biến FINALIZED/append-only.
- **API:** GET `/api/clinical-record` thêm tham số `visitId` (chỉ đọc) cho pager nạp lượt cũ, scope thêm `clinic_patient_id` (không lộ lượt khám BN khác).
- **VERIFY:** tsc + eslint (5 file) + `next build` sạch (0 lỗi). File: `clinical-record/route.ts`, `ClinicalRecordForm.tsx`, `DoctorWorkBoard.tsx`, `PatientListView.tsx`, `patient-list/page.tsx`.
- **NỢ nhỏ:** khi xem lượt cũ qua pager, mục "Lịch sử khám trước" có thể liệt kê cả lượt đang xem (cosmetic, không ảnh hưởng ghi).

### 2026-06-18 · T-DASH-PROVINCE-DROPDOWN-FIX-01 · Fix dropdown Tỉnh rỗng (RLS thiếu policy) · commit `chưa commit`
- **Vỡ ở tầng DB-quyền-đọc (RLS), KHÔNG phải API/form logic:** bảng `province`/`ward` có **RLS = bật nhưng KHÔNG có policy SELECT** (khác `service_type` có `*_select_authenticated`) → role `authenticated` của dashboard đọc về **0 dòng**. Data vẫn đủ (34 tỉnh / 3321 phường). **Chứng minh:** PostgREST anon key → `content-range */0` (0); service key → `0-0/34`.
- **Sửa (chỉ tầng API/fetch, KHÔNG đụng DB/policy/migration theo boundary):** đọc province (`patients/new/page.tsx`) + ward (`api/wards/route.ts`) bằng **service-role client** (`getSupabaseService`, bypass RLS) thay vì `getSupabaseServer`. Data tham chiếu hành chính CÔNG KHAI, server-only → an toàn.
- **VERIFY:** tsc + eslint + `next build` sạch; service-role trả 34 tỉnh (proof trên).
- **NỢ / thay thế:** fix "idiomatic" hơn = thêm RLS policy SELECT cho province/ward giống service_type (1 migration nhỏ) — boundary cấm migration nên dùng service-role; nếu sau muốn đọc bằng authenticated thì thêm policy. Cần Tuyền login `/patients/new` test lại: dropdown Tỉnh hiện 34 → chọn tỉnh → phường lọc đúng.

### 2026-06-18 · T-DASH-SONO-BIOMETRY-01 · Form số đo siêu âm thai (CRL/NT/BPD/HC/AC/FL/EFW) · commit `chưa commit`
- **KHÔNG migration:** `ultrasound_record` (mig 018) đã có cột **`findings` JSONB** (comment ghi rõ "measurement payload BPD/FL/AC/EFW") → 7 số đo + cờ `is_abnormal` + `status` lưu vào findings. Verify insert/readback (rollback txn, FK OK).
- **Gắn vào đâu (quyết định):** `ultrasound_record` cần `visit_id`, mà `/sono` (service_log queue, gated ĐD) KHÔNG có visit_id → gắn form vào **ClinicalRecordForm cho Bác sĩ Siêu âm** (ULTRASOUND_DOCTOR, có visit qua /tasks). API `/api/ultrasound` find-or-create visit (BS siêu âm tự khám → attending = chính mình).
- **API** `app/api/ultrasound/route.ts` (GET + POST), gate **CHỈ `isUltrasoundDoctorRole`** (helper mới roles.ts) — KHÔNG mở rộng. Chặn ghi khi visit FINALIZED/AMENDED (whitelist OPEN/IN_PROGRESS). KHÔNG suy luận bất thường (cờ do BS bấm).
- **UI** `SonoBiometry.tsx`: 7 ô (CRL/NT/BPD/HC/AC/FL mm + **EFW gram nhập TAY**) + 4 nút **Bắt đầu siêu âm / Lưu kết quả / Đánh dấu bất thường / Hoàn tất** + badge trạng thái/bất thường. Thread `showSono` qua tasks/page.tsx → DoctorWorkBoard → ClinicalRecordForm.
- **EFW NHẬP TAY** — `// TODO auto-EFW` chờ BS Thắng xác nhận công thức (Hadlock). KHÔNG tự tính (cấm bịa số y khoa).
- **VERIFY:** tsc + eslint + `next build` sạch (/api/ultrasound build).
- **NỢ:** (a) **auto-EFW chờ công thức BS Thắng**; (b) `/sono` (ĐD, service_log) vẫn tách — số đo nằm ở luồng BS siêu âm (vì /sono không có visit_id); (c) in phiếu chưa hiện số đo (chưa wire print); (d) `is_abnormal` lưu trong findings JSONB (chưa cột riêng → muốn query "ca bất thường" sau cần promote cột).

### 2026-06-18 · T-DASH-CSKH-VANDE-LINHVUC-01 · Field "Vấn đề khiến BN đi khám" + "Lĩnh vực" (CSKH) · commit `chưa commit`
- **2 field CSKH** (khâu đặt lịch/tạo BN), gắn vào bảng **patient** (như address, sống cả khi không có lịch hẹn): `van_de_di_kham` (text — KHÁC `clinical_record.chief_complaint_at_visit` "Lý do khám" của BS, KHÔNG đụng) + `linh_vuc` (mã chuyên khoa).
- **Lĩnh vực DÙNG LẠI 5 service_code có sẵn** (PK/SK/NT/HMVS/NK = 5 form chuyên khoa, `lib/form-schemas`) → lưu MÃ, map được sang form khám sau (getFormSchema/resolveServiceCode). KHÔNG tạo enum mới. Const `lib/linh-vuc.ts`.
- **Migration 055** (`20260618_055_patient_vande_linhvuc.sql`, apply LẺ + `--mark-applied`, **has_043=False**): ADD 2 cột nullable + CHECK `linh_vuc IN (5 mã)`. Verify: cột landed, 'PK' nhận / 'XYZ' từ chối (rollback, không ghi rác). DOWN drop constraint + 2 cột.
- **UI:** `NewPatientForm` thêm dropdown "Lĩnh vực" (5) + ô text "Vấn đề khiến BN đi khám" → POST `/api/patients` (whitelist 5 mã, giá trị lạ→null không chặn tạo BN). **Hiển thị lại** ở `PatientAdminEditor` (view-row có điều kiện, label hoá mã) — wired select ở `/customers` + `/patients/[id]`.
- **An toàn:** 2 field CHỈ capture qua POST intake + **CHỈ hiển thị** ở editor (KHÔNG đưa vào Form edit → PATCH KHÔNG đụng → không ghi đè null). PatientAdmin field optional → nguồn chưa select vẫn build (BS clinical form ẩn 2 row). KHÔNG đụng "Lý do khám"/lâm sàng/quyền.
- **VERIFY:** tsc + eslint + `next build` sạch.
- **NỢ:** (a) sửa 2 field SAU intake chưa hỗ trợ (như address) — chỉ POST; (b) BS clinical form chưa thread DOCTOR_SELECT (2 field ẩn trong popup BS); (c) **CHỜ PK xác nhận: "Lĩnh vực" có AUTO chọn form khám tương ứng không** (mã đã trùng service_code, sẵn sàng map nhưng chưa wire auto).

### 2026-06-18 · T-DASH-WORDING-NAMEFIX-01 · Sửa wording Lễ tân + tên BS 3 chỗ sót · commit `chưa commit`
- **(1.5) Wording board readOnly** (`tasks/page.tsx`): "👁 Chế độ chỉ xem … không chỉnh sửa" → "👁 Chỉ xem phần lâm sàng … KHÔNG sửa lâm sàng, NHƯNG ĐƯỢC sửa thông tin hành chính (mục I) — bấm tên BN để sửa". Khớp quyền thật (Lễ tân/Thu ngân có canEditAdmin=true ở board này). KHÔNG đụng logic.
- **(2.1) short_name → full_name** 3 chỗ CÒN SÓT (audit FINAL phát hiện): `home/page.tsx:55` (lời chào), `tasks/TasksRealtime.tsx:125,174` (bảng staff_task cũ), `schedule/edit/page.tsx:59` (editor ca trực). Cùng 3 chỗ roster/chip/picker đã fix ở T-DASH-DOCTOR-CLEANUP-01 → giờ tên BS đầy đủ ở MỌI nơi render.
- **VERIFY:** tsc + eslint + `next build` sạch. Chỉ đổi text + field render, KHÔNG migration/quyền/lâm sàng.
- **NỢ:** TasksRealtime là màn staff_task cũ chưa dùng (chưa xoá) — sửa cho nhất quán. Test tay: login Lễ tân xem wording rõ; tên BS đầy đủ ở lời chào + board.

### 2026-06-18 · T-DASH-ADDRESS-DROPDOWN-01 · Địa chỉ hành chính sau sáp nhập (tỉnh → phường, bỏ huyện) · commit `chưa commit`
- **Data nguồn:** github.com/ThangLeQuoc/vietnamese-provinces-database **tag v3.1.0** (mới nhất, sau bug Gia Lai của v3.0.x). Cấu trúc NQ 202/2025 + QĐ 19/2025: **34 tỉnh + 3321 phường/xã**, KHÔNG cấp huyện. Verify count khớp, 0 orphan FK, 0 dup code.
- **Migration 054** (`20260618_054_create_province_ward_address.sql`, apply LẺ out-of-band + `--mark-applied`, KHÔNG sequential-to-max, **has_043=False** giữ nguyên): tạo `province`(code PK) + `ward`(code PK, `province_code` FK + index) + **ADD 5 cột patient** (`province_code` FK, `province_name`, `ward_code` FK, `ward_name`, `address_detail`) NULLABLE — `patient.address` free-text GIỮ NGUYÊN (BN cũ hiển thị được). DOWN drop cột + 2 bảng.
- **Seed** `seed/054_province_ward.sql` (219KB, idempotent ON CONFLICT DO NOTHING) sinh bằng `scripts/gen_province_ward_seed.py` (ghim URL v3.1.0, regen được). Verify: province 34, ward 3321.
- **UI** form intake (`NewPatientForm`): ô địa chỉ free-text → **2 select phụ thuộc** (Tỉnh → Phường, load `/api/wards?province=` runtime) + 1 ô **địa chỉ chi tiết**. Lưu: address (gộp full để back-compat) + mã/tên tỉnh + mã/tên phường + chi tiết. API `/api/wards` (GET) + `/api/patients` POST nhận 5 field mới.
- **VERIFY:** tsc + eslint + `next build` sạch (sửa `set-state-in-effect`: load ward trong handler thay vì effect).
- **NỢ:** (a) Chỉ wire ở **POST create**; PUT/update (`PatientAdminEditor` sửa BN cũ) chưa nhận structured field — vẫn free-text. (b) Địa chỉ cấu trúc chỉ ở form nhập; các nơi khác vẫn đọc `address` text. (c) Đổi địa giới tương lai → regen seed bằng gen script + tag mới. (d) seed/054 219KB committed (như postgres ImportData nguồn).

### 2026-06-18 · T-DASH-TKYK-ENABLE-01 · Mở menu + đường vào form khám cho TKYK (nhập hộ bệnh án) · commit `chưa commit`
- **Vấn đề (từ audit T-DASH-AUDIT-TKYK-SCOPE-01):** TKYK chỉ thấy "Trang chủ", bị khóa khỏi mọi UI lâm sàng. Tệ hơn: clinical-record route dùng gate RIÊNG `isDoctorRole || (vitalsOnly && isNurseRole)` (KHÔNG phải canWriteClinical) → TKYK lưu bệnh án sẽ 403.
- **(1) `roles.ts` NAV:** thêm `TKYK` vào `/tasks` + `/patient-list` (mở menu + qua requireNavAccess).
- **(2) `tasks/page.tsx`:** thêm param `allDoctors` cho `DoctorTasks` (bỏ lọc `doctor_id` mà vẫn GHI) + nhánh `isThuKyRole → DoctorTasks(false,true,true)`. Chọn **NHÁNH B**: TKYK thấy hàng đợi MỌI bác sĩ (TKYK là vai chung, không buộc 1 BS) + header báo "✍ Nhập hộ bệnh án".
- **(3) `clinical-record/route.ts`:** (a) thêm `isThuKyRole` vào gate `allowed` → TKYK ghi full nháp; (b) khi TẠO visit, `attending_doctor_id` lấy từ `appointment.doctor_id` cho TKYK (như ĐD vitalsOnly) — **TKYK KHÔNG bị ghi nhầm là bác sĩ khám**.
- **GIỮ "TKYK nhập, BS chốt":** action `complete` ở `/api/appointments` vẫn gate `isDoctorRole` → TKYK lưu xong KHÔNG tự chuyển "Đã khám xong" (BS làm). Visit FINALIZE không đụng. TKYK ≤ BS.
- **VERIFY:** tsc + eslint + `next build` sạch.
- **NỢ:** (a) "Chỉ định XN" (`orderLab`→`/api/lab-result` gate `isDoctorRole`) vẫn chặn TKYK — order CLS là quyết định BS, để nguyên (ghi nhận, chưa mở). (b) TKYK lưu khi đủ chẩn đoán+lời dặn hiện báo "Chưa tự chuyển Khám xong — hãy tải lại" (cosmetic, do 403 complete by-design). (c) roleLanding(TKYK) vẫn `/home` (chưa cho đáp thẳng /tasks như BS — ngoài scope).

### 2026-06-18 · T-DASH-DOCTOR-CLEANUP-01 · Bỏ nút nhận/trả lịch BS + tên BS đầy đủ · commit `chưa commit`
- **(A) Gỡ nút "Nhận/Từ chối lịch" khỏi màn BS** (`tasks/DoctorWorkBoard.tsx`): xoá 2 nút Nhận/Từ chối + hàm `act()` + state `busyId/error/router` + import `useRouter,Check,X`. Lịch chưa check-in (SCHEDULED/CSKH_CONFIRMED/CONFIRMED) nay chỉ hiện "Chờ lễ tân check-in" (passive). Luồng mới: Lễ tân check-in → BN tự vào hàng BS (CHECKED_IN) → BS "Mở hồ sơ → khám" → điền Chẩn đoán+Lời dặn, Lưu → TỰ COMPLETED. KHÔNG còn bước trung gian.
- **KHÔNG đụng:** check-in của Lễ tân (`api/appointments` action=checkin nguyên vẹn), finalize/FINALIZED, GROUP_C lab gate D022 (`cskh-today`), ConfirmBoard (CSKH/QL) + AppointmentActions (QL) vẫn còn confirm/decline cho luồng quản lý lịch.
- **(B1) UPDATE staff.full_name 17 BS** tên tắt→đầy đủ có học hàm (seed `src/migrations/seed/053_doctor_full_names.sql`, apply lẻ out-of-band). Idempotent (WHERE full_name=tên tắt; chạy lại 0 row). short_name GIỮ NGUYÊN làm khóa ổn định. 17/17 BS đổi, 0 tên "BS …" sót. Đối chiếu bảng map PK: đủ 17, không tên lạ.
- **(B2) Đổi short_name→full_name 3 chỗ render:** `api/roster/route.ts:50` (tên ghi vào ca trực), `layout.tsx:35` (chip danh tính top-bar), `StaffPicker.tsx:100` (role-picker). Dropdown chọn BS đã full_name từ trước.
- **VERIFY:** tsc + eslint + `next build` sạch.
- **NỢ:** 88 row `work_roster.staff_name` cũ vẫn lưu tên tắt (denormalized; chỉ ca đăng ký MỚI dùng full_name) — chưa backfill, ngoài scope. **ROLLBACK (B1)** = chạy UPDATE đảo: tra short_name→full_name cũ (`Thành`→`BS Thành`, `Linh Nam khoa`→`BS Linh Nam khoa`, `Bá Linh/Đạt/Minh/Hoàng/Tiến/Giáp`→`BS SA <x>`, còn lại `<x>`→`BS <x>`).

### 2026-06-18 · T-DASH-TRUONGCA-LANDING-01 · Trưởng ca đăng nhập vào thẳng màn riêng "Theo dõi buổi" · commit `chưa commit`
- **Bối cảnh:** Kiểm tra yêu cầu PK "tạo màn hình riêng cho Trưởng ca như vai bác sĩ". Khảo sát code+DB: role `TRUONG_CA` ĐÃ làm đủ ở commit `c3cef3f` (account seed trong DB active, constraint 9 value có TRUONG_CA, sidebar đủ: Trang chủ·Thông tin khách hàng·Danh sách bệnh nhân·Nhập KH·Theo dõi buổi·Công việc của tôi; `canWriteIntake` += TRUONG_CA; KHÔNG lâm sàng). Chỉ thiếu 1 điểm để "giống bác sĩ": landing.
- **Fix:** `lib/roles.ts` `roleLanding()` — thêm `if (isTruongCaRole(role)) return "/truong-ca"`. Trước đó Trưởng ca đáp xuống `/home` chung; nay vào thẳng board riêng "Theo dõi buổi" (đối xứng bác sĩ → `/tasks`).
- **Phạm vi an toàn:** 1 nhánh `if`; KHÔNG đụng quyền/lâm sàng/migration/DB. tsc + eslint sạch.
- **Còn chờ:** "Công việc của tôi" vẫn placeholder (chờ mẫu báo cáo PK 24/6 — đúng yêu cầu PK). CM CHƯA làm (dùng tài khoản Admin MANAGEMENT có sẵn).

### 2026-06-18 · T-DASH-CHECKIN-AT-01 · Set visit.checked_in_at lúc tạo lượt khám → đồng hồ chờ chạy thật · commit `chưa commit`
- **Vấn đề:** `WaitClock` (board Lễ tân) hiện "—" cho mọi visit tạo từ dashboard vì `visit.checked_in_at` chưa bao giờ được ghi (chỉ luồng import/FastAPI set).
- **Fix:** `api/clinical-record/route.ts` — thêm `checked_in_at: new Date().toISOString()` vào **INSERT visit** (block chỉ chạy khi CHƯA có visit → set đúng 1 lần lúc tạo, lần lưu sau KHÔNG ghi đè). Cột `visit.checked_in_at` (timestamptz, nullable) đã có sẵn (mig 017) → KHÔNG migration.
- **Phạm vi an toàn:** chỉ thêm 1 field vào INSERT có sẵn; KHÔNG đổi luồng check-in, KHÔNG tạo visit ở bước check-in, KHÔNG DELETE/UPDATE visit, KHÔNG đụng visit.status/FINALIZED/043. tsc/eslint/next build sạch.
- **Ngữ nghĩa:** mốc = lúc TẠO lượt khám (đón khách/nhập sinh hiệu — người đầu tiên lưu hồ sơ), không phải lúc check-in ở quầy (visit chưa tồn tại trong lúc chờ trước đó — kiến trúc board dựa trên visit). Đủ cho "đồng hồ chờ" của board chạy thật + đổi màu theo ngưỡng.
- **Nợ:** 4 visit test cũ vẫn NULL (không backfill — tránh UPDATE bảng append-only); visit mới sau deploy sẽ có mốc. Muốn đo đúng "chờ từ lúc check-in ở quầy" cần task lớn hơn (tạo visit OPEN ngay khi check-in + xử lý undo_checkin) — chưa làm.

### 2026-06-18 · T-DASH-REVIEW-FIX-01 · Fix sau review đa-agent (trước khi push cho PK test) · commit `chưa commit`
- **Bối cảnh:** review toàn diff chưa push (20 commit) bằng skill code-review + 4 subagent (phân quyền / data-path feature mới / migration-DB / line-by-line). DB verify: has_043=False, constraint 11 role khớp ALL_ROLES, drug_catalog=64, service_price CLS=29. Clinical gates (FINALIZED/AMENDED) còn nguyên, không vai thu ngân/lễ tân nào ghi được lâm sàng.
- **2 BUG CONFIRMED (do cashier-split, đã fix):**
  1. `tasks/page.tsx:164` — `role === "CASHIER"` không match CASHIER_THUOC/CASHIER_DV → 2 vai tách rơi vào board bác sĩ read-only (LỘ lịch+BN của BS). Sửa: `isCashierRole(role)`.
  2. `api/service-price/route.ts:42` — `role !== "CASHIER" && != MANAGEMENT` chặn 2 vai tách sửa giá (403) dù có nav. Sửa: `!isCashierRole(role) && != MANAGEMENT`.
- **2 fix nhẹ:** `ClinicalRecordForm` CLS `<option key>` đổi `c.name`→`c.service_code` (uniqueness ở (group,service_code), tránh trùng key khi 2 dịch vụ cùng tên); `settings/new-user` DEPT_LABEL thêm 4 nhãn còn thiếu (TKYK/TRUONG_CA/CASHIER_THUOC/CASHIER_DV — trước hiện raw code).
- **Nợ đã ghi nhận (KHÔNG sửa lần này, cần quyết định/scope riêng):**
  - `visit.checked_in_at` KHÔNG được dashboard ghi (chỉ import/FastAPI set) → WaitClock hiện "—" cho visit tạo từ dashboard. Stepper vẫn chạy (theo visit.status). Cần task riêng set checked_in_at lúc check-in.
  - TKYK nằm trong `canWriteClinical` nhưng route clinical-record/clinical-form chỉ cho `isDoctorRole` → TKYK chưa ghi được bệnh án (đúng nợ "TKYK chưa wire" đã ghi). Cần PK quyết định trước khi mở.
  - cskh-today: BN quá hạn hiện ở CẢ khối ③ (đến hạn) lẫn ③b (nhắc gọi) — chủ đích khác mức độ, có thể gộp sau.
- **Build:** tsc 0 · eslint 0 · next build Errors:0.

### 2026-06-18 · T-DASH-CASHIER-SPLIT-01 · Tách 2 vai thu ngân thuốc ⟂ dịch vụ · commit `chưa commit`
- **Yêu cầu phòng khám:** 2 thu ngân (thuốc / dịch vụ) = 2 tài khoản riêng, không thấy màn nhau. CASHIER cũ giữ làm superset (QL/admin xem cả hai).
- **Migration 052** (`20260618_052_staff_dept_add_cashier_split.sql` + `.down`): CHECK `staff_primary_department_check` += `CASHIER_THUOC` + `CASHIER_DV` (9→11 value, mirror 050). Apply LẺ out-of-band (psql → `apply_migrations.py --mark-applied`), KHÔNG sequential-to-max. Verify: **has_043=False**, has_052=True. DOWN revert về 9 value. Seed `seed/052_cashier_split_staff.sql`: 2 staff "Thu ngân thuốc"/"Thu ngân dịch vụ" (guard IF NOT EXISTS) — đã landed.
- **roles.ts:** `ClinicRole` + `ALL_ROLES` += 2 vai; `ROLE_LABEL` ("Thu ngân thuốc"/"Thu ngân dịch vụ"); helper mới `isCashierRole` (CASHIER∪THUOC∪DV); `isTasksReadOnly` dùng `isCashierRole` (cả 2 vai xem board /tasks chỉ-đọc như CASHIER). `home/page.tsx` GREET_LABEL += 2 (giữ Record<ClinicRole> đủ key).
- **Gating (NAV_ROLES — page tự gate qua `requireNavAccess`+`canSeeNav`, KHÔNG dựng UI mới):**
  - `/cashier/thuoc` → `[CASHIER_THUOC, CASHIER, MANAGEMENT]`; `/cashier/dich-vu` → `[CASHIER_DV, CASHIER, MANAGEMENT]`.
  - `/customers`, `/patient-list`, `/tasks` += cả 2 vai (baseline như CASHIER).
  - Nav mỗi vai chỉ hiện màn của mình (Nav.tsx lọc bằng canSeeNav); CASHIER thấy cả hai.
- **canWriteClinical KHÔNG đụng** (cả 2 vai hành chính, không lâm sàng). KHÔNG đụng service_price/billing/catalog/VisitProgress/cskh-followup.
- **Build:** tsc 0 lỗi · eslint 0 lỗi · next build Errors:0.
- **Nợ:** 2 vai mới chưa link auth cá nhân (shared-login + role-picker như các vai khác); CashierWorkBoard (/tasks, billing placeholder) vẫn toggle thuoc/dich_vu tự do — chưa khoá theo vai (chờ build billing thật).

### 2026-06-18 · T-DASH-CSKH-FOLLOWUP-01 · Danh sách BN cần nhắc gọi (bucket 2/10/20/30 ngày) + nút "Đã gọi" · commit `chưa commit`
- **Yêu cầu phòng khám:** trong màn CSKH ("Cần làm hôm nay"), thêm danh sách BN quá hạn/không phản hồi chia bucket theo số ngày + nút "Đã gọi" ghi nhật ký CSKH.
- **Anchor (TÁI DÙNG, không định nghĩa mới):** `tai_kham.ngay` (soap_plan, cùng nguồn `dueLimit` khối ③). Quá hạn = `today − tai_kham.ngay` (ngày). Dùng lại đúng tập `recalls` đã loại BN có lịch hẹn tương lai.
- **Bucket:** `FOLLOWUP_TIERS = [2,10,20,30]` khai 1 chỗ đầu `cskh-today/page.tsx`. `buildFollowupBuckets` xếp mỗi BN vào ngưỡng quá-hạn cao nhất khớp (≥30 / ≥20 / ≥10 / ≥2 ngày); <2 ngày bỏ qua (vẫn ở khối ③ tái khám thường).
- **Action "Đã gọi":** route mới `app/api/cskh-followup/route.ts` (POST `{clinic_patient_id}`) → INSERT 1 dòng `cskh_log` (TÁI DÙNG cột `cskh_status="Đã gọi nhắc tái khám"` + `cskh_followup="Nhắc gọi tái khám"` + `last_cskh_date`+`cskh_by`), service-role (cskh_log RLS SELECT-only), gate `canWriteIntake`, có `logEvent`. Hiện ngay trong nhật ký CSKH của BN (`PatientCskhLog`).
- **UI:** client `CskhFollowupList.tsx` group theo bucket, mỗi dòng BN + nút "Đã gọi" (busy guard, optimistic "✓ Đã ghi", `router.refresh()` sau bấm). Section mới ③b trong page (server tính bucket, truyền xuống client).
- **Boundary giữ:** KHÔNG migration (cskh_log/cskh_followup đã có mig 037); KHÔNG đụng visit.status/FINALIZED/043/lâm sàng; KHÔNG đụng home/VisitProgress*. Build: tsc/eslint/next build Errors:0.
- **Nợ:** hiện DB có **0** visit với `soap_plan.tai_kham.ngay` → bucket rỗng tới khi BS điền ngày tái khám (data contract mới, chưa có data thật — giống khối ③). "Không phản hồi" hiện = quá hạn theo ngày; chưa lọc theo "đã gọi gần đây" (có thể chặn spam gọi lại ở Phase sau bằng cách đọc `cskh_log.last_cskh_date`).

### 2026-06-18 · T-DASH-LETAN-PROGRESS-01 · Progress stepper + đồng hồ chờ đổi màu (board Lễ tân) · commit `chưa commit`
- **Yêu cầu phòng khám:** board theo dõi BN của Lễ tân cần (a) thanh tiến trình các mốc khám, (b) đồng hồ chờ đổi màu theo thời gian. THUẦN PRESENTATIONAL, đọc data sẵn có.
- **Target = `VisitStatusBoard`** (board read-only "Trạng thái BN buổi khám" cho Lễ tân, `home/page.tsx` `isReception`) — vì nó có `visit.status` + `checked_in_at`. HomeCheckin (hàng đợi appointment) KHÔNG có `checked_in_at` nên không đặt đồng hồ ở đó.
- **Mới `VisitProgress.tsx`** (client island):
  - `ProgressStepper(status)`: 7 mốc Hẹn→Xác nhận→Check-in→Đang khám→Chờ SA/XN→Chờ thanh toán→Xong. Backed (CÓ data): Hẹn/Xác nhận/Check-in (ngầm DONE vì visit chỉ tồn tại sau check-in) + **Đang khám** (`visit.status=IN_PROGRESS`; FINALIZED/AMENDED = done). XÁM/inactive (chưa data): **Chờ SA/XN** (chưa join sono/lab) + **Chờ thanh toán** + **Xong** (chờ billing) — title tooltip ghi rõ lý do. KHÔNG bịa data.
  - `WaitClock(checkedInAt, active)`: `setInterval` 1s client tính `now − checked_in_at`, hiển thị `mm:ss`, đổi màu theo **ngưỡng hằng số đầu file** (`WAIT_GREEN_MAX=10`, `WAIT_YELLOW_MAX=20`): <10p xanh / 10–20p vàng / >20p đỏ. Chỉ chạy khi OPEN/IN_PROGRESS; FINALIZED/AMENDED → dừng ("—"). Guard `nowMs=null` tới khi mount → tránh hydration mismatch. Cleanup `clearTimeout`+`clearInterval` khi unmount.
- **`VisitStatusBoard.tsx`:** thêm 2 cột "Chờ" (WaitClock) + "Tiến trình" (ProgressStepper), colSpan empty 5→7. KHÔNG đụng logic/badge cũ.
- **Boundary giữ:** KHÔNG thêm/sửa enum status, KHÔNG migration, KHÔNG ghi DB, KHÔNG đụng visit.status/FINALIZED/043/lâm sàng. Đồng hồ thuần client từ `checked_in_at`.
- **Build:** tsc 0 lỗi · eslint 0 lỗi (sửa `react-hooks/set-state-in-effect`: tick đầu qua `setTimeout(0)`) · next build Errors:0.
- **Nợ:** 2 mốc cuối "Chờ thanh toán"/"Xong(thu ngân)" + "Chờ SA/XN" render xám tới khi build billing + nối hàng đợi sono/lab vào board. HomeCheckin (appointment) chưa có stepper/đồng hồ (thiếu checked_in_at — sẽ cần join visit nếu muốn).

### 2026-06-17 · T-DATA-CHIDINH-CATALOG-SEED-01 · Seed danh mục CLS + thuốc từ PHIẾU CHỈ ĐỊNH (PK) + nối picker form khám · commit `chưa commit`
- **Nguồn:** `scripts/catalog_src/PHIEU_CHI_DINH_update.docx` (PK gửi). Parser `scripts/parse_chidinh_catalog.py` (python-docx) → `scripts/catalog_out/{services,drugs}.csv` (gitignore `*.csv` — regen bằng chạy lại script).
- **Parse:** **29 dịch vụ/CLS** (Table0+1 theo nhóm-cột: Tầng 1 / Thủ thuật / Chụp phim ngoài / Thai / Nội tiết–phụ khoa; gộp 1 dòng trùng "Đo mật độ xương") + **64 thuốc** (Table2, 9 dòng-nhóm L1–L9; splitter tôn trọng ngoặc → giữ `Letrozole (10v, 15v)`, tách `;` cho `Diphereline…; GonaF`). **needs_review=TRUE: 3** (`Fes 1/10`, `Utrogestan (Đ) (1v/2v): (U)`, `Difavon/Diflucan/Fluconazole/Zolmed`). KHÔNG bỏ sót dòng nào.
- **Migration 051** (`20260617_051_create_drug_catalog_and_cls_seed.sql` + `.down.sql`):
  - TẠO MỚI `drug_catalog` (name_base, name_raw UNIQUE verbatim, variant, group_label, **unit_price NULL**, needs_review, is_active, created_at) + RLS SELECT authenticated. (Cột `prescription.drug_catalog_ref` mig 031 đã chờ sẵn.)
  - `service_price`: **ADD COLUMN** `category` + `tang` (nullable → KHÔNG đụng rows cũ) để picker CLS gom nhóm theo group_label.
  - Seed 64 thuốc (giá NULL, `ON CONFLICT(name_raw) DO NOTHING`) + 29 dịch vụ NEW vào `service_price` group='dich_vu' (giá NULL, `ON CONFLICT("group",service_code) DO NOTHING`, service_code = `CLS_<slug>`). SQL sinh bởi `scripts/gen_catalog_seed_sql.py` (deterministic).
  - **Apply LẺ out-of-band**: psql trực tiếp (INSERT 64 + 29, COMMIT) → `apply_migrations.py --mark-applied`. **KHÔNG sequential-to-max.** Verify sau apply: **has_043=False** (lỗ 043 còn nguyên), has_051=True, drug_catalog=64, service_price dich_vu=29.
- **Wire picker (dùng chung 5 form pk/sk/nt/nk/hmvs):** route mới `app/api/catalog/route.ts` (GET, đọc-only) → `{drugs, cls}`. `ClinicalRecordForm.tsx`: fetch 1 lần, 2 `<datalist>` (options BƠM RUNTIME, KHÔNG hardcode vào schema tĩnh): input "Đơn thuốc" (mục IX) `list=drug-catalog-list` (name_raw + nhãn variant/⚠cần dược); input "Chỉ định CLS" (mục VI) `list=cls-catalog-list` (name + nhãn category). Giữ gõ tự do (catalog là MENU, không phải safety gate) → persist qua đường có sẵn (prescription / lab_result).
- **Build:** tsc 0 lỗi · eslint 0 lỗi (file đổi) · next build Errors:0.
- **Boundary giữ:** giá NULL (không bịa); name_raw verbatim; chỉ THÊM dịch vụ NEW (rows/giá cũ không đụng); KHÔNG chạm 043/visit.status/FINALIZED/lâm sàng; KHÔNG push.
- **Nợ:** giá lazy-fill ở màn Thu ngân (toàn bộ 93 row unit_price NULL); 3 thuốc needs_review chờ DƯỢC xác nhận biến thể/định danh; variant tách best-effort (vd `Đ`=đặt/`U`=uống) nên dược rà; root còn bản docx trùng `PHIẾU CHỈ ĐỊNH - update.docx` (bản chuẩn đã ở `scripts/catalog_src/`) — Quang xoá bản root nếu muốn.

### 2026-06-17 · T-DASH-BO-BS-CHIDINH-01 · Gỡ UI "Bác sĩ phụ trách chỉ định" → NO-OP (field chưa từng tồn tại) · commit `chưa commit`
- **Yêu cầu phòng khám (họp 17/6):** bỏ field/label "Bác sĩ phụ trách chỉ định" (thuật ngữ sai), GIỮ "Chỉ định CLS".
- **Kết quả khảo sát:** label này **KHÔNG tồn tại** trong code dashboard và **chưa từng tồn tại**.
  - Grep literal `"Bác sĩ phụ trách chỉ định"` toàn repo (trừ node_modules/.next): 0 hit.
  - `git log -S "Bác sĩ phụ trách chỉ định"` / `-S "phụ trách chỉ định"`: 0 commit → chưa bao giờ vào code.
  - Chuỗi "phụ trách" chỉ ở 2 chỗ KHÁC target: `print/sono/[id]/SonoResultPrint.tsx:167` (dòng ký tên footer phiếu in) + `api/clinical-record/route.ts:297` (comment). Các `<label>Bác sĩ</label>` (AppointmentBooking/NewPatientForm/ConfirmBoard) = dropdown PHÂN BÁC SĨ cho lịch hẹn, lõi luồng đặt lịch — KHÔNG đụng.
- **"Chỉ định CLS" còn nguyên:** = các section "Cận lâm sàng" (field `cls_*`) trong `lib/form-schemas/{pk,nt,nk,sk,hmvs}.ts`.
- **Kết luận:** R4 = **no-op**. Field chỉ sống trong doc thiết kế/recap họp, chưa bao giờ build vào UI. KHÔNG sửa code, KHÔNG migration, KHÔNG drop cột (đúng boundary). Quyết định "đóng no-op" do Quang chốt.
- **Nợ:** không có cột mồ côi để dọn (vì chưa từng build). Nếu PK vẫn thấy field này ở đâu đó → đang nhìn bản mockup/doc cũ, không phải dashboard hiện hành.

### 2026-06-17 · T-DASH-TRUONGCA-01 · Role Trưởng ca (hành chính, KHÔNG lâm sàng) · commit `chưa commit`
- **Yêu cầu phòng khám:** thêm vai "Trưởng ca" (quản 1 ca/ngày, thay phiên) = quyền HÀNH CHÍNH như Lễ tân/CSKH, TUYỆT ĐỐI không lâm sàng.
- **Đã làm:**
  - Role/department **TRUONG_CA** mirror CASHIER/QL: roles.ts (union + ALL_ROLES + ROLE_LABEL + GREET_LABEL + helper isTruongCaRole) + NAV.
  - **Migration 050**: DROP+RECREATE staff_primary_department_check — 8 value cũ (...TKYK) + 'TRUONG_CA' = 9. Test temp schema PASS (pre/up/junk/intact/down), apply LẺ qua psql (per-file, KHÔNG replay 042-049, KHÔNG chạm 043) + insert schema_migrations. Seed 1 staff "Trưởng ca" (guard IF NOT EXISTS).
  - **Quyền:** `canWriteIntake += TRUONG_CA` → sửa intake + hồ sơ hành chính (qua canEditPatient) ở /customers, /patients/[id], /patients/new, PATCH/POST patients. `canWriteClinical` GIỮ NGUYÊN (BS+ĐD+TKYK) — TRUONG_CA KHÔNG ghi lâm sàng.
  - **UI:** trang `/truong-ca` "Theo dõi buổi" READ-ONLY (tái dùng VisitStatusBoard, visit hôm nay, không nút mutate) + `/truong-ca/cong-viec` placeholder "Công việc của tôi" (Đang xây dựng — chờ mẫu báo cáo PK 24/6). Nav 2 mục mới.
- **File sửa (5 code + 3 migration/seed):** lib/roles.ts · home/page.tsx · nav-items.ts · truong-ca/page.tsx (mới) · truong-ca/cong-viec/page.tsx (mới) + migrations 050(.sql/.down) + seed/050.
- **Migration:** 050 apply LẺ qua psql + seed; insert ledger. KHÔNG runner sequential, KHÔNG chạm 043.
- **Boundary giữ:** KHÔNG visit.status/FINALIZED/043/logic lâm sàng; KHÔNG thêm TRUONG_CA vào canWriteClinical; KHÔNG sửa migration đã merged; KHÔNG đụng FastAPI.
- **Nợ / next:** auth cá nhân cho staff Trưởng ca (hiện shared-login + role-picker); nội dung thật "Công việc của tôi" chờ mẫu báo cáo PK 24/6; cân nhắc thêm TRUONG_CA vào enum staff FastAPI nếu sau tạo staff qua API.

### 2026-06-17 · T-DASH-LETAN-WORKQUEUE-01 · Màn làm việc Lễ tân (hàng chờ + nút hành động) · commit `chưa commit`
- **Yêu cầu phòng khám:** triết lý "màn hình làm việc, không phải bảng trạng thái — mỗi nút = 1 việc thật". Hàng chờ hôm nay có nút đổi theo pha.
- **Đã làm:**
  - Nâng HomeCheckin (/home) từ read-only → hàng đợi TƯƠNG TÁC. Cột: Bệnh nhân · Giờ hẹn · Trạng thái (nhãn VN) · Nút hành động.
  - Nút theo pha (mỗi nút 1 action tái dùng /api/appointments, chặn double-click qua busyId, refetch router.refresh sau bấm):
    SCHEDULED → "Gọi xác nhận" (`cskh_confirm`); CSKH_CONFIRMED/CONFIRMED → "Check-in" (`checkin`); CHECKED_IN → "Đang chờ bác sĩ khám" + Hoàn tác (`undo_checkin`); COMPLETED → In phiếu; +"Không đến" (`no_show`) ở pha trước khi đến.
  - Nhãn trạng thái VN (STATUS_VN) cho cột Trạng thái.
- **File sửa (1 + CHANGELOG):** app/(dashboard)/home/HomeCheckin.tsx.
- **Migration:** none. Route: KHÔNG thêm action mới — TÁI DÙNG cskh_confirm/checkin/undo_checkin/no_show sẵn có.
- **Quyết định (đã hỏi Planner):** nút "Đưa vào khám" cho CHECKED_IN cần 1 pha trung gian KHÔNG có trong enum (CHECKED_IN→COMPLETED, không "đang khám"). Chọn **không migration**: CHECKED_IN = ĐÃ vào hàng khám của bác sĩ (DoctorWorkBoard đã hiện) → bỏ nút đổi-pha, chỉ hiện "Đang chờ bác sĩ khám" + Hoàn tác.
- **Boundary giữ:** workqueue HÀNH CHÍNH (gate canWriteIntake/canCheckin của route sẵn có); KHÔNG đụng visit.status/FINALIZED/GROUP_C/043/ghi lâm sàng; TKYK (vai lâm sàng) không thấy màn này (home showCheckin=canCheckin). Nút chỉ hiện đúng pha (state machine).
- **Nợ / next:** nếu PK muốn tách rõ "đã đến" ⟂ "đang khám" → packet riêng thêm status IN_EXAM (migration lẻ) + action to_exam + cập nhật DoctorWorkBoard. Walk-in SCHEDULED hiện cần Gọi xác nhận → Check-in (2 bước) đúng mapping ảnh; nếu muốn 1 bước cho khách tới trực tiếp thì refine sau.

### 2026-06-17 · T-DASH-TKYK-CLINICAL-01 · Role TKYK + canWriteClinical+=TKYK + siết lab/service-log · commit `chưa commit`
- **Yêu cầu phòng khám:** recap 17/6 — "Chỉ bác sĩ, điều dưỡng và thư ký y khoa có quyền điều chỉnh hồ sơ lâm sàng."
- **Đã làm:**
  - Tạo role/department **TKYK** (Thư ký Y khoa) theo pattern CASHIER (047): roles.ts (union + ALL_ROLES + ROLE_LABEL + GREET_LABEL), helper `isThuKyRole`.
  - **Migration 049**: DROP+RECREATE `staff_primary_department_check` — copy 7 value cũ (...CASHIER) + 'TKYK' = 8. Test temp schema PASS (pre/up/junk/intact/seed-idempotent/down), apply LẺ qua psql → public + insert `schema_migrations`. Seed 1 staff "Thư ký Y khoa" (guard `IF NOT EXISTS` theo full_name).
  - `canWriteClinical` (Packet 4) += `isThuKyRole` → = isDoctorRole || isNurseRole || isThuKyRole.
  - Siết 2 route lâm sàng còn rộng: `/api/lab-result` (nhập KQ XN) + `/api/service-log` (log SA/XN) đổi gate `canCheckin` → `canWriteClinical`. Lễ tân/QL bị 403; BS/ĐD/TKYK ghi được.
- **File sửa (5 code + 3 migration/seed):** lib/roles.ts · home/page.tsx · app/api/lab-result/route.ts · app/api/service-log/route.ts · CHANGELOG.md + migrations/20260617_049_staff_dept_add_tkyk.sql(+.down) + migrations/seed/049_tkyk_staff.sql.
- **Migration:** 049 apply LẺ qua psql + seed; insert ledger. KHÔNG runner sequential.
- **Boundary giữ:** migration chỉ đụng `staff_primary_department_check`; KHÔNG 043 / visit.status / FINALIZED / GROUP_C / append-only. ĐD (NURSE_ULTRASOUND) VẪN ghi lab/service (isNurseRole). KHÔNG đụng UI workqueue (để R3).
- **Nợ / next:** R3 — wire NAV/workqueue UI cho TKYK (chưa có nav → TKYK đăng nhập role-picker được nhưng chưa có màn làm việc riêng); liên kết auth cá nhân cho staff TKYK; cân nhắc thêm TKYK vào enum staff phía FastAPI (src/clinicai/schemas/staff.py) nếu sau này tạo staff qua API.

### 2026-06-17 · T-DASH-RECEPTION-FLOW-01 · Bỏ gate BS duyệt + Lễ tân sửa hành chính + rename phiếu khám · commit `chưa commit`
- **Yêu cầu phòng khám:** D21 (bỏ bước bác sĩ duyệt BN), D22 (Lễ tân sửa hành chính), + rename nhãn "Tóm tắt khám bệnh"→"Phiếu khám bệnh".
- **Đã làm:**
  - (A) D21 — Gỡ gate "BS duyệt" (workflow `appointment.status` thuần, KHÔNG dính visit.status/FINALIZED/lab/043): check-in cho phép từ `["SCHEDULED","CSKH_CONFIRMED","CONFIRMED"]` (trước: chỉ `CONFIRMED`). HomeCheckin hiện nút Check-in cho mọi lịch còn sống, bỏ chặn "Chờ bác sĩ xác nhận". → BN đến → check-in → khám được ngay. Nút "Nhận ca/Từ chối" của bác sĩ GIỮ (Từ chối → phân lại), nhưng không còn là điều kiện check-in.
  - (B) D22 — Lễ tân sửa hành chính: ĐÃ CÓ SẴN, không cần đổi code. `canWriteIntake` đã gồm RECEPTION; POST/PATCH `/api/patients` gate `canWriteIntake`/`canEditPatient`; mọi surface (/customers, /patient-list qua isTasksReadOnly, /patients/[id], /tasks) đã cấp `canEdit`/`canEditAdmin` cho RECEPTION. PatientAdminEditor chỉ sửa trường HÀNH CHÍNH (không CCCD, không lâm sàng) → `canWriteClinical` (Packet 4) giữ nguyên.
  - (C) Rename 3 chuỗi hiển thị "Tóm tắt khám bệnh"/"(tóm tắt khám)"→"Phiếu khám bệnh"/"(phiếu khám)": MedicalSummaryPrint (tiêu đề in), ClinicalRecordForm (header panel), patients/[id] (mô tả). KHÔNG đổi tên biến/route/key/cột. KHÔNG đụng "Tóm tắt trước khám" (PreVisitBrief) / "Tóm tắt kết quả" (lab) — khác nghĩa.
- **File sửa (5):** app/api/appointments/route.ts · app/(dashboard)/home/HomeCheckin.tsx · app/print/[appointmentId]/MedicalSummaryPrint.tsx · app/(dashboard)/tasks/ClinicalRecordForm.tsx · app/(dashboard)/patients/[id]/page.tsx.
- **Migration:** none.
- **Boundary giữ:** gate BS duyệt = hành chính thuần (appointment.status) — gỡ an toàn; KHÔNG đụng 043/visit.status/FINALIZED/lab; Lễ tân chỉ chạm hành chính (canWriteClinical nguyên); rename chỉ chuỗi hiển thị.
- **Nợ / next:** confirm/decline của bác sĩ giờ tuỳ chọn (work_roster auto-insert vẫn gắn với `confirm` — bác sĩ không nhận ca sẽ không tự lên Lịch làm việc; nếu muốn bỏ hẳn UI nhận ca thì packet riêng). Comment file header vẫn ghi "TÓM TẮT KHÁM BỆNH" (giữ — boundary chỉ đổi chuỗi hiển thị).

### 2026-06-17 · T-DASH-CLINICAL-PERM-SIET-01 · Lâm sàng chỉ BS+ĐD, tách check-in khỏi vitals · commit `chưa commit`
- **Yêu cầu phòng khám:** chốt họp — CHỈ Bác sĩ + Điều dưỡng được chỉnh lâm sàng (sửa lại nới quá rộng ở Packet 2 cho mọi role `canCheckin`).
- **Đã làm:**
  - Thêm helper `canWriteClinical(role) = isDoctorRole || isNurseRole` trong roles.ts (`isNurseRole` đã có sẵn = NURSE_ULTRASOUND).
  - Route `/api/clinical-record`: gate nhánh vitalsOnly đổi `canCheckin`→`isNurseRole` → `isDoctorRole(role) || (vitalsOnly && isNurseRole(role))`. Lễ tân/QL bị 403 khi ghi lâm sàng.
  - UI: HomeCheckin nhận `canWriteClinical`, truyền `readOnly={!canWriteClinical}` cho ClinicalRecordForm → Lễ tân/QL xem hồ sơ lâm sàng chỉ-đọc (vitals + lý do khoá, ẩn nút Lưu).
  - TÁCH check-in (hành chính) khỏi ghi vitals (lâm sàng): check-in vẫn ở `/api/appointments` action=checkin (gate `canCheckin`) — Lễ tân/QL/ĐD vẫn đón khách bình thường.
- **File sửa (4):** lib/roles.ts · app/api/clinical-record/route.ts · app/(dashboard)/home/HomeCheckin.tsx · app/(dashboard)/home/page.tsx.
- **Migration:** none (app-layer thuần, không đụng RLS).
- **Boundary giữ:** không migration / không RLS / không đụng 043 / visit.status / FINALIZED (vẫn qua WRITABLE_VISIT_STATUSES). BS save full hồ sơ KHÔNG đổi (isDoctorRole bỏ qua vitalsOnly). DoctorWorkBoard & PatientListView vốn đã readOnly cho non-doctor — không leak.
- **Nợ / next:** lab-result + service-log vẫn gate `canCheckin` (ngoài scope — ĐD nhập KQ XN/log SA; nếu muốn siết tiếp thì packet riêng).

### 2026-06-17 · T-DASH-NURSE-PERM-01 · ĐD sửa lý do khám + vital required HA/CN/CC · commit `chưa commit`
- **Yêu cầu phòng khám:** D25 (STT 15.0) cho điều dưỡng sửa "Lý do khám bệnh"; D26 (STT 16.0) chỉ 3 sinh hiệu bắt buộc.
- **Đã làm:**
  - (A) "Lý do khám bệnh" (Section II = `chief_complaint`, BS đưa ra/ĐD nhập hộ) mở quyền sửa cho luồng đón-khám: ô đổi `disabled` từ `roRest`→`ro`; `saveVitals()` gửi kèm `chief_complaint`; route `/api/clinical-record` nhánh `vitalsOnly` ghi `chief_complaint_at_visit` (CHỈ khi non-empty → không xoá lý do BS đã ghi).
  - (B) Sinh hiệu: thêm bắt buộc CHỈ 3 trường Huyết áp / Cân nặng / Chiều cao (dấu `*` + viền đỏ + chặn lưu khi thiếu); các vital khác giữ optional (vốn chưa từng required).
  - Xác nhận tách bạch 2 trường: "Vấn đề khiến BN đi khám" (CSKH lúc đặt lịch) KHÔNG tồn tại trong code → không đụng nhầm.
- **File sửa (2):** app/(dashboard)/tasks/ClinicalRecordForm.tsx · app/api/clinical-record/route.ts.
- **Migration:** none (validation frontend + ghi qua route service-role sẵn có).
- **Boundary giữ:** quyền xử ở APP-LAYER (route gate `vitalsOnly && canCheckin`, KHÔNG đụng RLS); KHÔNG đụng visit.status/FINALIZED gate (vẫn chặn qua WRITABLE_VISIT_STATUSES)/lab_result/043.
- **Nợ / next:** quyền mở cho mọi role `canCheckin` (ĐD/Lễ tân/QL) theo kiến trúc vitalsOnly sẵn có — nếu cần CHỈ điều dưỡng thì siết riêng sau; required HA/CN/CC enforce ở luồng đón-khám (save của bác sĩ không chặn).

### 2026-06-17 · T-DASH-GENDER-KHAC-02 · Giới tính "Khác" + bootstrap CHANGELOG · commit `chưa commit`
- **Yêu cầu phòng khám:** D13 (giới tính cần lựa chọn "Khác" ngoài Nam/Nữ).
- **Đã làm:**
  - Migration 048 nới `patient_gender_check` → chấp nhận `'Nam'/'Nữ'/'Khác'` (giữ NULL).
  - Test temp schema PASS (pre-reject → up-accept → junk-reject → Nam/Nữ intact → down-revert), rồi apply lẻ vào public + insert ledger.
  - Thêm `<option>Khác` vào 3 dropdown giới tính (NewPatientForm, PatientAdminEditor, ConfirmBoard).
  - Verify write path: `/api/patients` không có allowlist gender → `'Khác'` ghi DB OK (smoke insert chỉ vướng patient_code auto-gen, gender check PASS).
- **File sửa (4 + 2 migration + 1 changelog):** NewPatientForm.tsx · PatientAdminEditor.tsx · ConfirmBoard.tsx · (CHANGELOG.md mới) · migrations/20260617_048_patient_gender_add_khac.sql(+.down).
- **Migration:** 048 apply LẺ qua psql (BEGIN/COMMIT), insert `schema_migrations`. Không chạy runner sequential.
- **Boundary giữ:** chỉ DROP+RECREATE đúng 1 constraint `patient_gender_check`; KHÔNG đụng cột/constraint khác, KHÔNG đụng 043 (vẫn lỗ), không đổi giá trị Nam/Nữ đang lưu (10 Nữ / 7 NULL).
- **Nợ / next:** down 048 chỉ an toàn khi chưa có BN gender='Khác'; 043 vẫn pending (đợt riêng).

### 2026-06-17 · T-DASH-INTAKE-UX-01 · UX form intake (PT, tên BS, search bỏ dấu, date) · commit `08365f6`
- **Yêu cầu phòng khám:** D11 (nhãn PT + tên BS đầy đủ + tìm không dấu), D19 (ô ngày DD/MM/YYYY).
- **Đã làm:**
  - (a) `PT`→`Phẫu thuật` (ClinicalRecordForm); bác sĩ hiển thị HỌ TÊN ĐẦY ĐỦ (WeeklyAppointmentsTable bỏ in-hoa/viết-tắt; heading /appointments dùng full_name).
  - (b) Tìm tên KHÔNG phân biệt dấu: tái dùng cột `full_name_unaccent` (migration 039) cho customers/page (server, có fallback); lọc client HomeCheckin + StaffPicker qua `unaccentVi`; gom `unaccentVi` vào lib/validation.
  - (c) [DỪNG ở packet này] Giới tính "Khác" bị CHECK chặn → chuyển sang packet T-DASH-GENDER-KHAC-02.
  - (d) Component `DateField` dùng chung: 1 ô DD/MM/YYYY, tự đệm 0 (7→07), nút lịch native, emit ISO (DB date không đổi); gộp 3 ô DOB rời; áp cho DOB + ngày khám ở NewPatientForm/AppointmentBooking/PatientAdminEditor.
- **File sửa (12):** DateField.tsx (mới) · lib/validation.ts · NewPatientForm.tsx · AppointmentBooking.tsx · PatientAdminEditor.tsx · WeeklyAppointmentsTable.tsx · HomeCheckin.tsx · appointments/page.tsx · ClinicalRecordForm.tsx · customers/page.tsx · PatientsList.tsx · StaffPicker.tsx.
- **Migration:** none (chỉ tái dùng cột 039 sẵn có).
- **Boundary giữ:** frontend-only; KHÔNG migration, KHÔNG đổi schema/RLS/route ghi; search tái dùng cột sẵn có (không đổi DB).
- **Nợ / next:** nghiệm thu mắt DateField trên local (gõ tay + chọn lịch + "Chỉ biết năm").
