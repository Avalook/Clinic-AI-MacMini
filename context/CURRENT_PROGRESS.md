<!-- ════════════════════════════════════════════════════════════════════
     📍 BÀN GIAO PHIÊN (đọc khối này TRƯỚC) — cập nhật 2026-07-03
     ════════════════════════════════════════════════════════════════════ -->

## 📍 2026-07-03 — APP ĐẦY ĐỦ CHẠY 24/7 TRÊN MAC MINI M4 (LIVE) 🟢

**Link app (WEB + backend) — mở trình duyệt ra trang Dr4Women Dashboard:**
`https://mac-mini-ca-quang.tailc94236.ts.net` (→ `/login`). API nội bộ `api:8000`.

**Kiến trúc hiện tại:** Mac mini chạy **BẢN ĐẦY ĐỦ RIÊNG** = `dashboard` (Next.js :3000, phơi qua Tailscale Funnel) + `api` (FastAPI/LangGraph :8000 nội bộ, dashboard gọi qua `http://api:8000`). **Vercel là bản SONG SONG cho khách**; Mac là bản độc lập của mình. **Cả hai chung 1 Supabase.** (Quang chốt: Mac = full app riêng, Vercel giữ cho khách vì Vercel không sợ mất điện/mạng nhà.)

**Setup đã làm (tất cả trên Mac mini, KHÔNG đụng Vercel):**
- **Clone RIÊNG** `~/clinic-server/Clinic-AI-Dr4Women` (nhánh `chinh`), tách hẳn folder dev. `.env` (secret, KHÔNG commit) trỏ **Supabase ATF `atfmxvdfnbeenrdbbllp`** = ĐÚNG project Vercel/khách đang dùng (KHÁC folder dev đang dùng fzw). `CHECKPOINTER_BACKEND=postgres`. Đổi DB → phải rebuild dashboard (URL Supabase baked lúc build).
- **Docker = Colima** (headless, thay Docker Desktop — chạy không cần đăng nhập GUI). Đã fix `~/.docker/config.json` bỏ `credsStore:desktop` (backup `.bak-*`).
- **Compose prod** `docker-compose.prod.yml` (project `clinicai_prod`: `clinicai_prod-api-1` + `clinicai_prod-dashboard-1`, KHÔNG đụng project dev). Chạy: `docker compose -f docker-compose.prod.yml up -d`. Dashboard build cần lock synced (đã fix playwright) + `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`.
- **Tailscale Funnel** phơi `:3000` (DASHBOARD/web; api :8000 chỉ nội bộ) — tài khoản là **`nguyencongtuyenlp@github`** (tailnet `nguyencongtuyenlp.github`, suffix `tailc94236.ts.net`), MagicDNS+HTTPS+Funnel đã bật. ⚠️ Tài khoản Tailscale/máy là của Tuyền (GitHub login) — sau nên chuyển sang tài khoản công ty.
- **24/7**: LaunchDAEMON `/Library/LaunchDaemons/com.dr4women.clinic-backend.plist` (boot + self-heal 5', chạy `scripts/clinic-backend-boot.sh`: colima start → compose prod up → assert funnel). `sudo pmset -a sleep 0 disablesleep 1 autorestart 1`. Đã GỠ LaunchAgent CŨ (user, trỏ dev folder) để hết xung đột.
- **Deploy sau này**: `cd ~/clinic-server/... && ./scripts/deploy-backend.sh` (pull→build→migrate→NOTIFY pgrst→up→health). Backend deploy THỦ CÔNG → push `chinh` cho Vercel KHÔNG ảnh hưởng backend đang chạy.

**Quy ước từ điển với Quang:** "sửa cho khách xem" = dashboard→Vercel; "sửa cho server" = `src/clinicai`→Mac mini. Cùng nhánh `chinh`, khác nơi chạy.

**CÒN TREO:**
- **Chưa nối Vercel** (Quang dặn chưa đụng): khi muốn dashboard dùng backend Mac → set trên Vercel `CLINIC_API_URL=https://mac-mini-ca-quang.tailc94236.ts.net` + `BACKEND_API_KEY` (khớp .env server) → redeploy. Chưa set thì dashboard vẫn ghi thẳng Supabase (fallback).
- **Chưa test reboot thật** (log xác nhận daemon chạy đúng, nhưng chưa reboot để chốt).
- **FileVault chưa bật** (nên bật — mã hóa đĩa cho PII).
- Nâng cấp tương lai (đã plan, chưa làm): domain riêng→Cloudflare Tunnel; local-LLM native (Qwen/MLX) cho voice/giảm chi phí; workers/cron. Xem `docs/deploy-mac-mini.md` + `~/.claude/plans/ok-hi-n-l-m-nh-replicated-panda.md`.

---

## 📍 2026-07-03 — Fix "người thứ 2 không đặt được slot" + nhãn khung 15' dạng dải

**Triệu chứng (Quang báo, có ảnh):** lưới 2+1 hiện BN2 còn trống, bấm đặt → lỗi "Khung giờ đã đầy tải: Khung đã đầy quota đặt trước (online)". BN1 đã kín, BN2 lẽ ra đặt được.

**Nguyên nhân:** POST `/api/appointments` chạy 2 cửa tải ĐỘC LẬP. Cửa 2+1 (`slotCapMessage`, đúng lưới) CHO QUA; nhưng cửa CAP-01 (`evaluateBudget`, ngân sách PHÚT/GIỜ) chặt hơn → chặn oan (`full_online`: 2 khách mới ×15' = 30' > `online_quota_min`=28' khung 17h). Hai hệ đo khác đơn vị (ghế/15' vs phút/giờ), mâu thuẫn.

**Quyết định (Quang chốt):** luật đặt chỗ chính thức = **2+1 mỗi khung 15'** (CSKH 2 chỗ BN1/BN2, chỗ 3 vãng lai). CAP-01 KHÔNG còn chặn đặt lịch.

**Đã làm:**
- **`app/api/appointments/route.ts`:** gỡ khối CAP-01 chặn 409 khỏi POST (giữ engine `capacity.ts` + `block_budget` cho Phase 1.5 làm cảnh báo mềm/advisory-lock). Net cứng còn lại: luật 2+1 (`slotCapMessage`) + 6-overlap DB. Gỡ import thừa (`vnBlockOf`/`resolveBudget`/`evaluateBudget`/`isBlocking`/`BudgetRow`/`ApptLite`/`vnLocalToUtcISO`/`VN_TZ`); giữ `suggestLoad`/`patient_kind`/`thanh_min`/`sono_min` (vẫn ghi DB). PATCH reschedule/reassign KHÔNG đụng (vốn chỉ dùng 2+1).
- **Nhãn cột lưới 15' → dạng dải "17:00-17:15":** helper chung `slotRange()` trong `lib/datetime.ts`; dùng ở `CinemaSlotPicker` (header + tooltip, nới ô `min-w-[3.75rem]`) + `NewPatientForm` (dòng xác nhận vãng lai).

**Test:** `tsc --noEmit` 0 lỗi; `next build` 0 lỗi. KHÔNG cần migration. Đã push `avalook chinh`.

### Bổ sung cùng ngày — "Thông tin khách hàng": ẩn nút hồ sơ khi CHƯA khám
- **Yêu cầu (Quang):** panel chi tiết ở `/customers` chỉ để Lễ tân/CSKH sửa thông tin hành chính. Người mới đặt lịch/check-in mà CHƯA khám (kể cả đang khám nhưng hồ sơ chưa lưu) thì KHÔNG hiện nút "Hồ sơ & lịch sử khám" — đã khám đâu mà xem. Khám xong họ thành "bệnh nhân" (hiện ở `/patient-list`).
- **Đã làm:** `customers/page.tsx` thêm `examined` vào `apptByPatient` = `list.some(status==='COMPLETED')` (KHÔNG thêm query — tái dùng query lịch sẵn có; cùng định nghĩa "bệnh nhân" với `/patient-list`). `CustomersView.tsx` chỉ render nút khi `selectedAppt?.examined`. CHECKED_IN/IN_PROGRESS/mới đặt → ẩn.
- **Test:** `tsc` + `next build` 0 lỗi. Không cần migration.

### Bổ sung cùng ngày — tạm ẩn "Số thứ tự gọi khám" + fix "!" sinh hiệu không mất
- **Tạm ẩn `/queue`:** `lib/roles.ts` đặt `NAV_ROLES["/queue"] = []` → ẩn sidebar mọi vai + gõ URL bị `requireNavAccess` redirect `/home`. Mở lại: khôi phục danh sách vai đã comment ngay trên.
- **Fix "!" nhắc điền sinh hiệu (điều dưỡng) không mất sau khi lưu:** trước đây badge "!" ở `WeeklyAppointmentsTable` dựa THUẦN `isNurse && status==='CHECKED_IN'` — mà lưu sinh hiệu KHÔNG đổi appointment.status nên "!" còn mãi + vẫn điền lại được. **Đã xác nhận save THẬT lưu** (`saveVitals`→`/api/clinical-record` POST: tạo/tìm visit IN_PROGRESS + merge `clinical_record.soap_objective.vitals`, đã có `router.refresh()`). Fix: `home/page.tsx` đọc visit→clinical_record của các lịch CHECKED_IN, coi ĐÃ GHI khi đủ 3 vital bắt buộc (huyết áp/cân nặng/chiều cao = REQUIRED_VITALS), truyền `has_vitals` xuống bảng; badge chỉ hiện khi `CHECKED_IN && !has_vitals`. Điền lại để sửa vẫn được (visit IN_PROGRESS ghi đè, khóa 48h + FINALIZED giữ nguyên). Query đọc qua RLS caller (đã xác nhận nurse SELECT được visit/clinical_record — cùng client với form).
- **Test:** `tsc` + `next build` 0 lỗi (lint chỉ còn `selAppt as any` CÓ SẴN). Không cần migration.

### Bổ sung cùng ngày — thu ngân CHỈ thấy BN khi bác sĩ ĐÃ khám xong
- **Bug (Quang check):** màn thu ngân (`CashierWorkBoard` qua `tasks/page.tsx` → `CashierTasks`) lấy MỌI `visit` tạo hôm nay, KHÔNG lọc trạng thái → BN mới CHECKED_IN / đang khám (IN_PROGRESS) đã hiện cho thu ngân thu tiền dù bác sĩ CHƯA khám xong. `appt_status` có nhưng không dùng để lọc/khoá.
- **Fix (2 lớp):**
  - **List:** `tasks/page.tsx` lọc `visits` chỉ giữ `oneOf(v.appointment)?.status === "COMPLETED"` (khám xong). "Khám xong" = appointment.status COMPLETED (khớp `/patient-list` + VisitStatusBoard; dashboard KHÔNG set visit.FINALIZED).
  - **API (chốt tiền):** `POST /api/payment` thêm guard đọc `visit → appointment.status`, `!== COMPLETED` → 409 "Bác sĩ chưa khám xong lượt này — chưa thể thu tiền." (chặn cả khi board lỡ hiện do cache/đua hoặc gọi API trực tiếp). DELETE (hoàn tác) KHÔNG gán điều kiện.
- **Test:** `tsc` + `next build` 0 lỗi. Không cần migration.

### Bổ sung cùng ngày — điều dưỡng CHỈ điền sinh hiệu SAU khi lễ tân check-in
- **Yêu cầu (Quang):** lễ tân check-in cho khách RỒI điều dưỡng mới được điền sinh hiệu (trước đây gộp check-in + sinh hiệu = "đón-khám", điền được cả khi chưa check-in).
- **Đã làm (3 lớp):**
  - **Form gate:** `ClinicalRecordForm` — `arrivalPending` bỏ điều kiện `!vitalsOnly` → áp cho CẢ luồng sinh hiệu. Trước CHECKED_IN/COMPLETED: ô sinh hiệu read-only, nút "Lưu sinh hiệu" disabled, banner "🕓 Chờ lễ tân check-in — chưa điền được sinh hiệu". `saveVitals()` thêm guard early-return.
  - **Server:** `POST /api/clinical-record` khi `vitalsOnly` đọc appointment.status, `!== CHECKED_IN && !== COMPLETED` → 409 "Chờ lễ tân check-in… trước khi điền sinh hiệu." (chặn cả khi gọi API trực tiếp / UI lỡ hiện).
  - **Bảng lịch hẹn:** `WeeklyAppointmentsTable` — trước check-in hiện chữ "Chờ lễ tân check-in" thay cho nút "Điền sinh hiệu" (COMPLETED vẫn cho sửa). "!" vốn đã chỉ hiện khi CHECKED_IN && !has_vitals.
- **Test:** `tsc` + `next build` 0 lỗi. Không cần migration.

### Bổ sung cùng ngày — AUDIT luồng ngách (4 subagent) + sửa Tier 1 & Tier 3
Quang yêu cầu rà toàn bộ luồng ngách tìm corner-case/lỗi thiết kế. Chạy 4 subagent (appointments/booking, visit/clinical/episode, payment/cashier/queue, roles/access). **2 pattern gốc:** (A) API kiểm VAI nhưng KHÔNG kiểm sở hữu record; (B) guard toàn app-level fail-open, không có net DB (mig 057 đã DROP ràng buộc overlap; queue_number không unique). **Lỗi thiết kế lớn:** visit.FINALIZED KHÔNG bao giờ được set → mô hình bất biến/khóa hồ sơ chỉ là 48h age-lock. Báo cáo đầy đủ đã trình Quang; chọn sửa **Tier 1 (bảo mật)** + **Tier 3 (nhất quán trạng thái)**.
- **Tier 1 (đã push):** (1.1) `requireClinicRole()` mới trong clinic-session → gọi ở 2 trang `/print/*` (trước đây ngoài (dashboard) layout, KHÔNG gác quyền, ai gõ URL cũng xem PII/hồ sơ). (1.2) `POST /api/clinical-record` thêm ownership: bác sĩ chỉ ghi hồ sơ đầy đủ cho lịch của mình/chưa phân; chặn lịch của BS khác (miễn trừ TKYK/ĐD/vitalsOnly).
- **Tier 3 (đã push):** (3.1) `home/page.tsx` lọc bảng "Trạng thái BN buổi khám" bỏ lượt appointment CANCELLED/NO_SHOW (visit treo OPEN/IN_PROGRESS không còn hiện "đang khám" mãi; KHÔNG xóa data). (3.2) appointments PATCH reassign/reschedule → đồng bộ `visit.attending_doctor_id` sang BS mới (visit chưa chốt) để không ghi nhầm bác sĩ cũ.
- **CÒN TREO (cần Quang quyết):** (3.3) `undo_checkin` hardcode về CONFIRMED (bịa trạng thái BS đã duyệt) + giữ queue_number — sửa đúng cần LƯU trạng thái trước check-in (migration cột `checkin_prev_status`). (3.4) ghi đè đơn thuốc khi 2 người mở form cùng lúc (delete-then-insert mù) — cần cờ "đã sửa đơn"/optimistic-lock. Tier 2 (đúng tiền) + Tier 4 (net DB 2+1, cấp số nguyên tử) chưa làm.
- **Test:** `tsc` + `next build` 0 lỗi. Không cần migration cho phần đã push.

---

## 📍 SLOT-21 — Đặt lịch "2+1 mỗi khung 15'" (BN1/BN2 + chỗ vãng lai) — ĐÃ CODE, COMMIT LOCAL, CHƯA PUSH

**Yêu cầu (3 ảnh PK gửi 2026-07-02):** mỗi BÁC SĨ × KHUNG 15' có đúng 3 chỗ — BN1+BN2 cho lịch hẹn (CSKH/Lễ tân đặt trước), chỗ thứ 3 DÀNH RIÊNG khách vãng lai; sơ đồ chỉ hiện BÁC SĨ TRỰC CA hôm đó; trang chủ bảng Lịch hẹn khám gom khung giờ → bác sĩ → BN1/BN2/ô xanh "đặt vào đây"; Lịch làm việc GIỮ NGUYÊN.

**Quyết định (Quang chốt qua hỏi-đáp):**
- Chỗ 3 nhận diện THEO KÊNH `booking_channel = WALK_IN` — KHÔNG thêm cột DB → KHÔNG cần migration/atf. (Hệ quả: kênh đặt thành BẮT BUỘC ở AppointmentBooking, vì kênh rỗng bị server mặc định WALK_IN sẽ chiếm nhầm chỗ vãng lai.)
- Chặn CỨNG server + UI (mọi corner case): POST + PATCH reschedule/reassign đều kiểm; trần 6-overlap DB + engine CAP-01 giữ nguyên làm lưới an toàn.
- Ngày chưa có lịch trực → fallback hiện TẤT CẢ bác sĩ + dòng cảnh báo, không chặn đặt.
- Ô xanh trang chủ BẤM ĐƯỢC → `/patients/new?date&time&doctor` điền sẵn (chỉ hôm nay; ngày sau chỉ hiển thị).

**Đã làm (KHÔNG đổi DB):**
- **`lib/slot-capacity.ts` (MỚI, thuần):** REGULAR_CAP=2, WALKIN_CAP=1, bucket 15' (`slotBucketMs/Range`), `buildSlotUsage/usageAt`, DEAD_STATUSES=CANCELLED/NO_SHOW/DOCTOR_DECLINED (không giữ chỗ). Dùng chung UI + server để không lệch luật.
- **API `/api/appointments`:** GET thêm `booking_channel`; POST thêm `slotCapMessage()` (chặn 409 sau check trùng-BS, trước CAP-01; hàng "Chưa phân bác sĩ" doctor_id null cũng bị cap); PATCH `reassign`+`reschedule` kiểm cap ở đích (loại trừ chính lịch, đúng loại chỗ theo kênh của lịch). Best-effort fail-open như CAP-01 (race 2 người đặt cùng lúc vẫn có thể lách — chờ Phase 1.5 advisory lock).
- **API `/api/roster`:** thêm GET `?date=` → bác sĩ trực (`work_roster` station LICH_KHAM, APPROVED, khử trùng SANG/CHIEU, bỏ dòng thiếu staff_id). Đọc bằng phiên caller (RLS SELECT).
- **`CinemaSlotPicker` v2:** mỗi bác sĩ 3 hàng con BN1/BN2/Vãng-lai(xanh); prop `mode`: "regular" (CSKH/Lễ tân đặt hẹn — chỉ BN1/BN2 bấm được, hàng xanh khoá "chỉ đặt khi được chỉ định — làm sau") vs "walkin" (chỉ hàng xanh bấm được); prop `dutyDoctorIds` lọc bác sĩ trực (null=chưa nạp→tất cả; []=chưa phân trực→tất cả+cảnh báo); giữ hàng "Chưa phân bác sĩ".
- **`AppointmentBooking`:** fetch duty theo ngày; mode regular; `isSlotBooked` theo cap-2; Kênh đặt * bắt buộc. (QuickBookingModal + PatientBooking dùng chung → tự lan.)
- **`NewPatientForm`:** full-variant như trên; **walkin-variant (Lễ tân/ĐD)**: thay DoctorLoadBoard bằng sơ đồ mode walkin (HÔM NAY) — bấm ô xanh chọn bác sĩ+khung, `bookFor` dùng khung đã chọn (không chọn = khám ngay giờ hiện tại như cũ); prop mới `initialAppt` nhận prefill từ query của trang `/patients/new` (page.tsx đọc searchParams).
- **Trang chủ:** `WeeklyAppointmentsTable` viết lại — gom NGÀY → KHUNG 15' (chỉ khung có lịch) → BÁC SĨ (trực trước, khác sau, "Chưa phân BS" cuối; rowSpan 2 cột đầu); mỗi nhóm: các dòng lịch (giữ nguyên cột Số/Thông tin/Phân loại/Thao tác check-in/sinh hiệu/in phiếu + popup ClinicalRecordForm) + Ô XANH khi chỗ vãng lai trống & khung chưa qua (hôm nay = Link prefill, ngày sau = chỉ nhìn; lịch vãng lai có nhãn "· vãng lai"). `home/page.tsx`: select thêm `doctor_id, booking_channel`, đọc duty theo `work_date IN tuần lịch hẹn` (KHÔNG lọc week_start — weekAppt ≠ weekRoster). Lịch làm việc (WorkRosterTable) KHÔNG ĐỤNG.

**Test:** `tsc --noEmit` 0 lỗi; `next build` ✓ (route /api/roster GET, /patients/new, /home compile). Lint 9 file sửa: chỉ còn lỗi CÓ SẴN TỪ TRƯỚC (AppointmentBooking DURATIONS/setDuration unused + set-state-in-effect; NewPatientForm 2 pattern cũ y hệt; `selAppt as any` giữ nguyên từ bản cũ). Lỗi mới duy nhất (Date.now trong render) đã sửa bằng `nowMs()`.

**CÒN TREO:**
- **Chưa push** (chờ Quang "OK"). Không có migration nào phải chạy trên atf cho task này (CAP-01 061+062 vẫn treo như cũ).
- Race 2 request cùng khung vẫn lách được cap 2+1 (best-effort) — gộp vào Phase 1.5 advisory lock của CAP-01.
- "Chỗ 3 theo chỉ định" cho CSKH: PK nói LÀM SAU — hiện hàng xanh khoá ở mode regular.
- Data cũ: lịch CSKH từng lưu kênh rỗng→WALK_IN sẽ hiện ở hàng vãng lai (chấp nhận, đã chốt nhận diện theo kênh).
- DoctorLoadBoard.tsx không còn nơi dùng (giữ file, chưa xoá).

---

## 📍 CAP-01 — Capacity Phase 1 (engine ngân sách + newCap) — ĐÃ CODE, COMMIT LOCAL, CHƯA PUSH

**Task:** `.ai/tasks/T-20260629-CAP-01-capacity-budget-phase1.md` (Decision Doc v2, DEC-1..8 đã ký).
**Mục tiêu:** chặn quá tải BS Thành theo NGÂN SÁCH phút/khung-giờ + trần ca-mới (newCap), thay vì chỉ đếm số ca. Mô hình re-entrant (Thành chạm 2 lần B1+B3, rảnh khi BN siêu âm) — xem memory [[bottleneck-thanh-fragment-model]]. Production đã window-based nên KHÔNG có FRAGMENT, KHÔNG port prototype.

**Đã làm:**
- **DB (fzw dev đã apply 061+062 + NOTIFY pgrst; atf prod CHƯA — chờ Quang chạy):**
  - **061** `capacity_budget`: `appointment` +4 cột nullable (`patient_kind`'NEW'|'RETURN', `thanh_min`, `sono_min`, `need_sono`); bảng mới `block_budget` (ngân sách/cơ sở×BS×thứ×giờ) + unique index COALESCE.
  - **062** `seed_block_budget` (TRACKED, không paste tay): seed 42 dòng qua `INSERT...SELECT` tra ID **theo TÊN** (clinic_location + staff Thành), KHÔNG hard-code UUID (fzw≠atf), idempotent `ON CONFLICT DO NOTHING`, **FAIL-FAST `RAISE EXCEPTION`** nếu match BS Thành ≠ 1. Đã test fail-fast kích hoạt đúng.
  - ⚠️ atf chưa có 061+062 → Quang phải chạy **061 schema + `NOTIFY pgrst,'reload schema'` + 062 seed** TRƯỚC khi push (không thì web prod lỗi cột thiếu / engine fail-open không chặn). Memory [[postgrest-reload-after-ddl]], [[two-supabase-prod-sync-workflow]]. Lưu ý: em chỉ truy cập fzw, atf do Quang chạy tay.
- **Engine:** `src/dashboard/lib/capacity.ts` (thuần, không I/O): `vnBlockOf` (Asia/Ho_Chi_Minh), `suggestLoad`, `resolveBudget` (DEC-8 fallback), `evaluateBudget` (max_total→new_cap→quota kênh→ngân sách Thành→cảnh báo), `usageOf`+`cellState` (6 trạng thái ô).
- **API:** `app/api/appointments/route.ts` POST chèn kiểm ngân sách SAU check trùng-giờ-BS, TRƯỚC insert (best-effort DEC-7, giữ net 6-overlap DEC-1, fail-open DEC-8); +4 cột vào payload. Endpoint mới `app/api/appointments/quote/route.ts` (GET, read-only) trả tải/khung cho UI.
- **UI:** `AppointmentBooking.tsx` thêm select "Loại khám" + checkbox "Siêu âm" (gửi `patient_kind`/`need_sono`; backend tự gợi ý `thanh_min`/`sono_min`), strip chip 6 màu trạng thái khung-giờ dưới sơ đồ. NewPatientForm dùng chung component này → tự lan.

**Test:** `tsc --noEmit` 0 lỗi; `next build` ✓ compiled (quote route đăng ký). Lint: 4 file mới/sửa của task → capacity/route/quote 0 lỗi; AppointmentBooking còn các lỗi lint CÓ SẴN TỪ TRƯỚC (DURATIONS/setDuration unused, any[], immutability@160) + 1 set-state-in-effect giống pattern committed dòng 104 — build không chặn (eslint ignored at build).

**CÒN TREO / việc tiếp:**
- **Chưa push** (chờ Quang "OK"). Trước khi push PHẢI apply 061 lên atf prod.
- Phase 1.5: chống race bằng RPC + `pg_advisory_xact_lock` (hiện best-effort).
- Phase 2: ngân sách `sono_min` (2 trạm) + Layer-2 hàng đợi B1/B2/B3.
- Seed `block_budget` hiện là ước lượng — hiệu chỉnh từ `visit.exam_completed_at` sau 2–4 tuần (DEC-5).

---


## 📍 ĐANG Ở ĐÂU — bàn giao cho phiên sau (vd mở remote ở nhà)

**Việc gần nhất ĐÃ XONG & ĐÃ PUSH (`avalook/chinh` = `9cd79aa`):** trang lẻ `/queue`
"Số thứ tự GỌI khám" ưu tiên Model ② (chi tiết ngay mục dưới). KHÔNG đụng DB.

**Bản đồ file ↔ logic (sửa ở đâu nếu cần đổi tiếp):**
| Muốn đổi gì | File | Điểm cần sửa |
|---|---|---|
| Luật xếp thứ tự GỌI / cửa sổ trễ | `src/dashboard/lib/queue.ts` | `callRank()` + hằng `LATE_GRACE_MS` (đang 10') |
| Giao diện bảng gọi số | `src/dashboard/app/(dashboard)/queue/QueueBoard.tsx` | client, gom theo bác sĩ, refresh 30s |
| Dữ liệu trang gọi số | `src/dashboard/app/(dashboard)/queue/page.tsx` | SELECT + lọc CHECKED_IN hôm nay |
| Ai thấy menu /queue | `lib/roles.ts` (NAV_ROLES) + `app/(dashboard)/nav-items.ts` | |
| Board check-in /home & "Việc của tôi" | `home/page.tsx` (CHECKIN_SELECT) · `tasks/page.tsx` (DOCTOR_SELECT) · `tasks/DoctorWorkBoard.tsx` | đều dùng `compareQueue` từ `lib/queue.ts` |

**CÒN TREO (ý tưởng, CHƯA làm — chờ Quang quyết):**
- `/queue` mới chỉ HIỂN THỊ + tự refresh, **chưa có nút thao tác** "đã gọi / bỏ qua / gọi lại". Nếu cần biến thành bảng điều khiển thật thì làm thêm action + cột trạng thái gọi.
- `LATE_GRACE_MS` đang **cứng 10'** — nếu muốn chỉnh theo phòng khám thì cân nhắc đưa thành cấu hình.
- `WeeklyAppointmentsTable` (overview tuần) cố ý để fallback, chưa gắn 2 field mới.

**Quy tắc còn hiệu lực:** mọi việc trên nhánh `chinh`; push chỉ `git push avalook chinh` SAU khi Quang nói "OK"; đổi DB → đưa SQL cho Quang paste vào prod (atf), KHÔNG tự apply.

---

## ▶ 2026-06-26 (tối) — THỨ TỰ GỌI KHÁM ưu tiên (Model ②) + trang lẻ /queue

**Bối cảnh / nỗi đau:** số vé (queue_number) cấp lúc ĐẾN nên KHÔNG thể là thứ tự gọi: người hẹn 9:00 đến 9:03 sẽ thua 2 khách vãng lai đến 9:00 (đã tự check-in, có vé trước). Quang chốt: **tách số vé (chỉ định danh) khỏi thứ tự GỌI**; gọi bệnh nhân **theo TÊN**; người có hẹn đến đúng giờ xếp trước vãng lai; đến trễ quá cửa sổ thì tụt xuống theo giờ đến.

**Quyết định đã chốt:** cửa sổ trễ = **10 phút**; làm luôn mục 3 (đồng bộ các board đang có).

**Việc đã làm:**
- `lib/queue.ts`: thêm `HasQueue.booking_channel` + `HasQueue.checked_in_at`, hằng `LATE_GRACE_MS = 10'`, hàm **`callRank()`** (tầng −1 ƯT người quen → tầng 0 CÓ HẸN đến ≤ giờ hẹn+10' xếp theo GIỜ HẸN → tầng 1 vãng lai / đến trễ xếp theo GIỜ ĐẾN). `compareQueue` nay dùng `callRank` cho hàng ĐÃ check-in, fallback `queueRank` (ƯT→số→giờ) khi thiếu 2 field mới ⇒ tương thích ngược.
- Trang lẻ mới **`app/(dashboard)/queue/`** (`page.tsx` + `QueueBoard.tsx`): lấy lịch hôm nay status CHECKED_IN + embed `visit.checked_in_at`/`status` + `booking_channel`; gom theo bác sĩ, mỗi cột sắp theo `callRank`, tách "Đang khám" (visit IN_PROGRESS) lên trên; hiển thị TÊN to + nhãn "Có hẹn/Vãng lai" + số vé; tự refresh 30s. Chỉ-đọc.
- Nav: `lib/roles.ts` NAV_ROLES `+"/queue"` (CSKH/QL/Lễ tân/Trưởng ca/TKYK/ĐD + bác sĩ); `nav-items.ts` `+` mục "Số thứ tự gọi khám" (icon ListOrdered).
- **Mục 3 — đồng bộ board cũ:** thêm `booking_channel` + embed `visit.checked_in_at` (phẳng hoá mảng→field) vào CHECKIN_SELECT (`home/page.tsx` → HomeCheckin) và DOCTOR_SELECT (`tasks/page.tsx` → DoctorWorkBoard); `DoctorApptRow` thêm 2 field optional. WeeklyAppointmentsTable để fallback (overview tuần, không cần).

**Kiểm chứng:** tsc sạch; lint 0 lỗi mới (chỉ warning baseline `isThuKyRole` unused có sẵn); `next build` thành công, route `/queue` xuất hiện (dynamic).

**Chưa làm:** chưa push (chờ Quang "OK"). Lưu ý DB: dùng cột có sẵn (`booking_channel`, `visit.checked_in_at`) — KHÔNG migration.

---

## ▶ 2026-06-26 (chiều) — Lễ tân walk-in: bảng "Tải hôm nay theo bác sĩ" + bỏ auto-ƯT-theo-phút

**Bối cảnh:** Quang hỏi sao lễ tân không có "rạp chiếu phim". Phân tích: màn Tạo BN của lễ tân là **walk-in** (khách đang ở quầy → tạo + mở lượt khám NGAY) nên không có khối đặt-giờ-tương-lai; "rạp chiếu phim" (chọn slot tương lai) là việc CSKH/tái khám, không hợp walk-in. Thử đặt board check-in lên /home → Quang bác (trùng "Lịch hẹn khám", gây loạn) → ĐÃ GỠ.

**Nỗi đau thật (memory bottleneck-thanh):** phòng khám nghẽn quanh 1 trạm BS Thành, cách chữa là đẩy bớt sang BS phụ. ⇒ thứ lễ tân cần khi tạo walk-in là NHÌN tải từng bác sĩ hôm nay để ĐỊNH TUYẾN, không phải chọn slot.

**Việc đã làm:**
- Mới `app/(dashboard)/patients/DoctorLoadBoard.tsx` — bảng CHỈ-ĐỌC "Tải hôm nay theo bác sĩ": hàng = bác sĩ, cột = giờ, mỗi ghế = 1 lịch (chưa đến hồng / đã đến xanh / xong xám) + cột "Tổng", tô đậm hàng bác sĩ ĐANG CHỌN. Nhúng vào màn walk-in của lễ tân (`NewPatientForm.tsx`, dùng lại `existingAppts` walk-in đã fetch). KHÔNG check-in (đã có ở /home), KHÔNG đặt slot, KHÔNG đụng backend.
- **Số khám:** giữ NGUYÊN = số chung toàn PK theo thời gian (`route.ts` POST + PATCH check-in `max+1`). KHÔNG đổi per-doctor (Quang chốt: số là số chung theo thời gian; BN khám BS nào đã ghi rõ).
- **Bỏ auto-ƯT-theo-phút** (misfeature): `AppointmentBooking.tsx` + `NewPatientForm.tsx` trước đây tự dập `số khám = ƯT1/2/3/4` chỉ theo PHÚT slot (00→ƯT1…), và PATCH check-in GIỮ NGUYÊN ⇒ khách online vô tình chọn phút :00 bị đánh dấu ƯT (người quen) — SAI nghĩa. ƯT thật = người quen nhà bác sĩ, gõ tay. Sửa: effect chỉ để TRỐNG số khám CSKH (check-in cấp số theo thời gian); placeholder đổi "Để trống — gõ ƯT cho người quen nhà bác sĩ".

**Kiểm chứng:** tsc sạch; lint 3 file (DoctorLoadBoard 0/0; 2 file CSKH = lỗi baseline có sẵn, không lỗi mới); `next build` Compiled successfully.

**Chưa làm:** chưa push (chờ Quang "OK"). /home reception board đã gỡ hẳn.

---

## ▶ 2026-06-26 — CSKH: "Số chỗ còn trống" → sơ đồ đặt chỗ kiểu rạp chiếu phim (dùng chung BN mới + tái khám)

**Việc đã làm:**
- Mới: `app/(dashboard)/patients/CinemaSlotPicker.tsx` — component lưới đặt chỗ dùng chung. Mỗi bác sĩ 1 hàng, mỗi ô = 1 khung 15' trong giờ mở cửa (`clinicHoursForDate`). Ô đã có lịch / quá giờ → khoá; ô trống bấm → `onPick(doctorId, "HH:mm")`. Component thuần render (parent truyền `existingAppts`, nhận callback) → tái dùng được cả 2 luồng.
- `patients/AppointmentBooking.tsx` (luồng **tái khám** qua `PatientBooking` + step 2): thay khối "Số chỗ còn trống" bằng `<CinemaSlotPicker/>` (span 2 cột), giữ Time24Input làm nhập tay dự phòng. Fetch `/api/appointments` **bỏ** filter `doctor_id` → lấy lịch mọi bác sĩ để vẽ đủ hàng.
- `patients/new/NewPatientForm.tsx` (luồng **BN mới**): thay y hệt; fetch non-walkin bỏ `doctor_id`.

**Quyết định & lý do:**
- 1 component dùng chung thay vì 2 bản: logic chọn giờ ở 2 màn vốn trùng 100%; yêu cầu của Quang là tái khám cũng phải có "rạp chiếu phim".
- **Giữ** Time24Input (nhập tay) làm dự phòng theo chốt với Quang; picker và ô nhập tay đồng bộ qua cùng state `apptTime/doctorId`.
- **KHÔNG** đụng backend: GET `/api/appointments` khi bỏ `doctor_id` đã trả lịch mọi bác sĩ kèm field `doctor_id`.

**Kiểm chứng:** `next build` Errors 0; typecheck sạch; lint 3 file — CinemaSlotPicker 0 lỗi, 2 file kia số lỗi = baseline (toàn lỗi có sẵn: DURATIONS/setDuration/any/set-state-in-effect, không thuộc vùng sửa).

**Chưa làm / cần khi chạy thử:** chưa push (chờ Quang "OK"). Refactor gộp trùng lặp NewPatientForm↔AppointmentBooking để sau (ngoài scope).

---

## ▶ LƯU Ý 2026-06-23 (chiều) — Điều dưỡng: nav/quyền + 3 hàng đợi + sinh hiệu + phiếu khám

**ĐÃ SỬA (feedback PM cho vai Điều dưỡng `NURSE_ULTRASOUND`) — commit `a6a017e`:**
- `+` nav `/patient-list` ("Thông tin bệnh nhân"): ĐD tra cứu BN + xem lịch sử khám (parity bác sĩ).
- BỎ check-in khỏi ĐD (`canCheckin` chỉ còn RECEPTION + MANAGEMENT) — check-in là việc Lễ tân.
- BỎ tạo BN khỏi ĐD (`canWriteIntake` + nav `/patients/new`) — ĐD không tạo BN.
- 3 hàng đợi ĐD KHÔNG ảnh hưởng (chúng gate `canWriteClinical` / check role trực tiếp, ĐD vẫn ghi).

**QUYẾT ĐỊNH (Quang 23/6): 3 hàng đợi (`/lab-queue`, `/service-queue`, `/sono`) TẠM GIỮ HẾT cho ĐD — KHÔNG tách/gộp.**
LÝ DO: chưa có insight tách vai "Phụ siêu âm" + **phòng khám CHƯA phản hồi**. (Chi tiết: memory `dieu-duong-queues-decision`.)
**OPEN khi PK phản hồi:** `/sono` (làn SA + làn XN phụ) CHỒNG LẤN `/lab-queue` (cùng là XN) và `/service-queue` (cùng đọc `service_log`). Nếu "Phụ siêu âm" chỉ lo siêu âm → nên BỎ làn XN trong `/sono` (dồn về `/lab-queue`). Nguồn order các hàng đợi = PHIẾU CHỈ ĐỊNH (Thủ thuật / Xét nghiệm / Siêu âm / Thuốc).

**SINH HIỆU (vitals) — ĐÃ LÀM (commit `6254adb`):** bỏ check-in khỏi ĐD làm ĐD mất lối nhập sinh hiệu (vốn nằm trong form check-in). Search thực hành phòng khám lớn: ghi sinh hiệu là việc CLINICAL (điều dưỡng / medical assistant), KHÔNG phải lễ tân (front desk = hành chính). Đã bù: thêm khu **"Sinh hiệu bệnh nhân hôm nay"** trên trang chủ CHỈ cho ĐD — tái dùng `HomeCheckin` ở chế độ vitals (prop `canCheckinActions=false` → ẩn nút check-in/xác nhận, chỉ mở BN nhập sinh hiệu; `canWriteClinical=true` cho ĐD → sửa được). Lễ tân vẫn chỉ XEM. Ghi qua `/api/clinical-record` vitalsOnly (tạo/đụng visit IN_PROGRESS như cũ).

**PHIẾU KHÁM theo loại (NT/PK/SK/NK/HMVS):** ĐÃ XONG trước đó (T-FORM-COMPACT-01/02). Engine `lib/form-schemas/` config-driven theo `service_code`, render qua `<ServiceFormEngine>` trong tab phiếu khám `ClinicalRecordForm.tsx`. Khớp đặc tả "Sáng Ý - Bàn giao KCB". Hạn chế còn lại: `resolveServiceCode` đang ĐOÁN theo TÊN dịch vụ (chưa truyền `service_type.code`).

---

## ▶ Phiên 2026-06-23 — Quy ước nhánh + đọc lại dashboard

**QUY ƯỚC NHÁNH (Quang chốt 23/6 — nguồn chân lý đầy đủ ở `CLAUDE.md §3`):**
- Mọi thay đổi code/commit DIỄN RA TRÊN `chinh`. KHÔNG bao giờ code/commit thẳng lên `feat/t-transform-01`.
- **Cổng 1** — push `chinh`: chỉ khi Quang nói **"OK"**.
- **Cổng 2** — merge `chinh` → `feat/t-transform-01` (= PRODUCTION nối Vercel, autoDeploy, phòng khám đang xem): chỉ khi Quang nói **"CHỐT"** + có lệnh rõ.

**Việc phiên này:** (1) Ghi rule nhánh 2 cổng vào `CLAUDE.md §3` + worklog này. (2) Đọc lại toàn bộ dashboard `src/dashboard` (Next.js **16.2.6** — có breaking changes, đọc `node_modules/next/dist/docs/` trước khi viết code; xem `src/dashboard/AGENTS.md`): **11 role**, ~24 trang `(dashboard)`, ~22 API route; data-path = tạo BN qua **FastAPI MPI** (`/api/patients` → `CLINIC_API_URL`), đọc/ghi khác qua **Supabase** (browser=anon, server=anon+cookie, service=service-role bypass RLS). Gate an toàn: FINALIZED visit (clinical-record/clinical-form 409), GROUP_C lab "chờ BS duyệt", append-only `event_log`.
**Đã sửa (feedback PM, mục "Chung / Giao diện") — ĐÃ COMMIT `b7e8264`:**
1. **Trùng chữ "BS"** (`BS. TS.BS. Phan Chí Thành`): gốc = code prepend `BS.`/`BS ` trong khi `staff.full_name` đã có học hàm (seed `053_doctor_full_names.sql`: TS.BS./Ths.BS./BSNT./BSCKI./Ths./BS.). Tạo helper `lib/doctor-name.ts` → `doctorName()` chỉ thêm `BS.` khi tên CHƯA có học hàm, đã có thì giữ nguyên. Áp 5 chỗ: `home/WeeklyAppointmentsTable.tsx` (chỗ trong ảnh, bỏ luôn `cleanDoctor` cũ), `appointments/AppointmentsKanban.tsx`, `patients/[id]/PatientDetail.tsx`, `cskh-today/page.tsx`. (Các chỗ render tên trần không prefix — giữ nguyên, vốn đã hiển thị đủ học hàm.)
2. **`/customers` tìm kiếm phải bấm "Tìm" → bất tiện**: `CustomersView.tsx` đổi sang GÕ-TỚI-ĐÂU-LỌC-TỚI-ĐÓ = lọc CLIENT tức thì (`useMemo`+`unaccentVi`, giống `/patient-list` mà PM OK) + tự gọi server debounce 350ms bọc `useTransition` (phủ toàn DB cho BN ngoài 300 dòng đã nạp, KHÔNG nháy skeleton, KHÔNG mất focus). BỎ nút "Tìm"; Enter vẫn tìm ngay; "Xoá" hiện theo `term`. (`/patient-list` không đụng — PM bảo OK.)
- Verify: `tsc --noEmit` ✓ · `npm run lint` ✓ · `next build` ✓ (exit 0).
- **3 commit local trên `chinh`** (CHƯA push): `b7e8264` fix dashboard · `8ec8f00` feat roster seed · `091e778` docs. Chờ Quang duyệt → ra lệnh push (CỔNG 1).

### T-FORM-COMPACT-02 — TAB hoá PHIẾU KHÁM BỆNH `ClinicalRecordForm.tsx` (giảm cuộn) — ĐÃ VÀO `chinh`
**Sửa scope của -01:** lần trước nhắm `ServiceFormEngine.tsx` (chỉ là 1 card nhỏ ở đáy). Phiếu DÀI mà BS/TKYK thật sự cuộn là **`ClinicalRecordForm.tsx`** (~1158 dòng, render dọc liên tục I→X + Sinh hiệu + Phiếu chuyên khoa). Lần này nhắm đúng nó. Chỉ đổi CÁCH HIỂN THỊ, GIỮ NGUYÊN mọi field/logic/chế độ.
**File sửa DUY NHẤT:** `src/dashboard/app/(dashboard)/tasks/ClinicalRecordForm.tsx`. KHÔNG đụng ServiceFormEngine/SonoBiometry/PreVisitBrief/API/schema/lib.
**Đã làm (BỌC JSX, không viết lại logic):**
- **(A) Gom 4 TAB** theo luồng khám + state `const [tab,setTab]=useState(vitalsOnly?1:0)`: **Tab 0 Hành chính & Tiền sử** (I + PreVisitBrief + Lịch sử khám trước + III + IV) · **Tab 1 Khám** (Sinh hiệu + II Lý do + V Bệnh sử/khám thai + SonoBiometry — Sono dời xuống cuối tab) · **Tab 2 Cận lâm sàng & Chuyên khoa** (VI + ServiceFormEngine card tab riêng, nested OK) · **Tab 3 Chẩn đoán & Xử trí** (VII + VIII + IX Đơn thuốc + X Tái khám). Cách bọc: mỗi khối giữ NGUYÊN nội dung + điều kiện (`showSono`/`showPreVisitBrief`/`viewingPast`/`!vitalsOnly`), chỉ thêm `{tab===N && (...)}`; chỉ render tab đang chọn (state global useState → không mất gì, field điều kiện chéo tab vẫn đúng).
- **(B) Khung cố định, chỉ ruột cuộn:** Header+Pager (cố định) → Banner cảnh báo dời lên vùng cố định → thanh TAB cố định (cuộn ngang, có ✓ khi tab đã điền) → GIỮA cuộn (`overflow-y-auto` chỉ ở lớp nội dung tab) → Footer Lưu/Tái khám/Đóng cố định (vốn đã là sibling cố định — nay nút Lưu LUÔN thấy, khỏi cuộn đáy). `msg` cạnh footer như cũ.
- **(C) Validation auto-nhảy tab:** cả `saveVitals()` (ĐD) lẫn `save()` (BS) khi thiếu REQUIRED_VITALS (huyet_ap/can_nang/chieu_cao) → `setVitalsTried(true)` + `setTab(1)` (tab Khám) + msg → thấy ô đỏ dù đang ở tab khác. (Trước đó `save()` BS KHÔNG validate vitals → đã thêm guard, đúng D26 + đúng kịch bản test packet "BS thiếu sinh hiệu → nhảy tab Khám".)
- **(D) ✓ tiến độ trên tab** (helper `tabFilled` đọc thuần state) — optional, đã làm.
**Chế độ (review logic, giữ nguyên hành vi):** readOnly/Lễ tân (đổi tab xem, ẩn Lưu) · locked/FINALIZED (mọi field disabled, banner 🔒) · vitalsOnly/ĐD (mặc định tab Khám, chỉ Sinh hiệu sửa, IX+Phiếu chuyên khoa ẩn) · viewingPast/pager (◀▶ chạy, ẩn Lưu). ServiceFormEngine vẫn `readOnly={readOnly||locked}`.
**Verify (từ `src/dashboard`):** `tsc --noEmit` ✓ · `eslint` file mình ✓ No issues · `npm run build` ✓ exit 0.
**⚠️ Git — entangled với Quang:** trong lúc làm, **Quang code SONG SONG cùng file trên VSCode và đã COMMIT working-tree của mình**. Toàn bộ thay đổi -02 của Claude đã nằm trong commit `136fb7f` (style/whitespace) + `ac93005` (close tab 3 JSX + scope ServiceFormEngine vào tab 2) trên `chinh`; tree giờ CLEAN. → KHÔNG tạo commit trùng. Code -02 verified pass trên HEAD hiện tại. CHƯA push (chờ Quang — Cổng 1).

### T-FORM-COMPACT-01 — Form khám "ÍT CUỘN" (ĐÃ COMMIT `29aab14`, CHƯA push)
**Vấn đề PM:** phiếu khám chuyên khoa quá dài → BS/TKYK phải cuộn nhiều khi vội. Yêu cầu: GIỮ ĐỦ trường, gần như hết cuộn. Chỉ đổi CÁCH HIỂN THỊ, không đổi dữ liệu.
**File sửa DUY NHẤT:** `src/dashboard/app/(dashboard)/tasks/ServiceFormEngine.tsx` (engine config-driven → 1 lần sửa, cả 5 form PK/SK/NT/HMVS/NK hưởng). KHÔNG đụng schema/field/API/`form_data`.
**Đã làm:**
- **(A) Chia TAB theo section** — thêm state `activeIdx`; thanh tab ngang sticky (cuộn ngang được), chỉ render section đang active (DOM gọn, `values` vẫn giữ toàn bộ → không mất dữ liệu/field điều kiện chéo section). Tab có dấu ✓ khi section đã điền ≥1 field. Thanh nav dưới LUÔN hiện: `← Mục trước · Mục i/N · title · Mục sau →` + **nút "Lưu phiếu" đưa vào thanh này** (khỏi cuộn xuống đáy). readOnly vẫn chuyển tab xem, ẩn nút Lưu.
- **(B) radio + checkbox_group → CHIP** (pill bấm) thay list dọc → cắt chiều cao 2–3 lần. radio = chọn 1, group = toggle nhiều (vẫn dùng `onToggleGroup`, value giữ string / string[]). Chip active nền hồng nhạt + chữ `#9d2463`; disabled khi readOnly.
- **(C) Field ngắn nhiều cột** — grid section lên `sm:grid-cols-2 lg:grid-cols-3`; textarea/conditional/fullWidth chiếm trọn hàng (`sm:col-span-2 lg:col-span-3`).
- **(D, stretch) "Tất cả bình thường"** — làm GENERIC (không hard-code schema): nút đầu section, dò option có label/value ∈ {"bình thường","bt","không","ko"} cho field radio/checkbox_group rồi set; chỉ hiện khi section có ≥1 field khớp. Không đụng field khác.
**Verify (từ `src/dashboard`):** `npx tsc --noEmit` ✓ No errors · `eslint` file mình ✓ No issues (2 lỗi lint còn lại nằm ở file Quang đang code: `WeeklyAppointmentsTable.tsx`, `tasks/page.tsx` — KHÔNG đụng) · `npm run build` ✓ Compiled successfully (exit 0).
**Lưu ý git:** lúc stage, `Nav.tsx`+`Shell.tsx` (file Quang đang sửa) đang nằm sẵn trong index → đã `git restore --staged` để commit CHỈ chứa `ServiceFormEngine.tsx`. Working tree còn `Nav.tsx`, `Shell.tsx`, `docs/VAN_HANH.md` nguyên vẹn của Quang.
**TODO/ngoài scope (giữ nguyên):** prefill tiền sử, auto-BMI/EFW — task khác. CHƯA push (chờ Quang nói "OK" — Cổng 1).

### Lịch làm việc TRỐNG → ĐÃ IMPORT + áp DB ✓
**Nguyên nhân:** `/schedule` ([schedule/page.tsx](src/dashboard/app/(dashboard)/schedule/page.tsx)) query `work_roster WHERE week_start = <thứ 2 của tuần>`. Tuần 15-21/06 (`week_start = 2026-06-15`) chỉ có 1 ô cũ (BS Thành 18/06) → lưới trống. Cần nạp dữ liệu thật từ Excel.

**Đã làm (auto, KHÔNG ghi DB):**
- Viết parser [scripts/data_import/import_roster_llv_062026.py](scripts/data_import/import_roster_llv_062026.py) đọc sheet **LLV 06-2026** của `~/Downloads/BẢNG LÀM VIỆC 06.2026 (1).xlsx`.
- Sinh seed idempotent [src/migrations/seed/056_roster_llv_062026.sql](src/migrations/seed/056_roster_llv_062026.sql): **305 dòng, 3 tuần** (`2026-06-01`, `2026-06-08`, `2026-06-15`). Đã spot-check: 15/06 LICH_KHAM=BS HÙNG, 18/06=BS THÀNH+BS QUYẾT (khớp Excel).
- SQL: `BEGIN; DELETE work_roster WHERE week_start IN (3 tuần); INSERT 305 dòng; COMMIT;` (chạy lại an toàn).

**ĐÃ ÁP vào DB (Quang chạy psql 23/6) — confirmed:** `2026-06-01`=95 · `2026-06-08`=111 · `2026-06-15`=99 (tổng 305).
- `/schedule` mặc định mở TUẦN HIỆN TẠI. Hôm nay 23/6 → tuần 22-28/06 (KHÔNG có trong Excel) nên mặc định trống; data thật ở tuần 01–21 (`/schedule?week=2026-06-15`).
- **TEMP COPY (Quang yêu cầu 23/6):** copy tuần 15-21 → 22-28 (+7 ngày) cho có hiển thị tạm:
  `DELETE work_roster WHERE week_start='2026-06-22'; INSERT (...) SELECT '2026-06-22', work_date+7, ... WHERE week_start='2026-06-15';`
  → **TUẦN 22-28 LÀ DATA NHÁI** (bản sao 15-21), KHÔNG phải lịch thật → đè khi có lịch thật.

**Map cột Excel → station key (lib/roster.ts), tái dùng cho tháng sau:**
`C=LICH_KHAM · D=SB_CHIEU · E=HSS_THU_THUAT · F=LE_TAN · G=LAY_MAU · H=PHU_BS_KHAM · I=TLYK · K=PHU_BS_SA · L=PHONG_NGOAI_MOR · M=MAY_TRONG · N=MAY_NGOAI`. Mỗi ngày = 2 hàng tên; T7/CN tách Sáng/Chiều (shift SANG/CHIEU), T2–T6 = FULL.

**Caveat:** (a) `staff_id = NULL`, `staff_name` = nguyên văn tên tắt (có ô 2 người như "Hằng Trang Lê") → bảng hiển thị đủ, nhưng form "Đăng ký ca của tôi" lọc theo staff_id sẽ không nhận; backfill staff_id sau nếu cần. (b) Cột J "THU NGÂN THUỐC" (chỉ tuần 15-21) chưa có STATION trong dashboard → ĐÃ BỎ QUA; muốn hiện phải thêm 1 key vào `STATIONS` (lib/roster.ts) + cột bảng. (c) Sheet LLV 06-2026 chỉ có 3 tuần (01–21); tuần 22–30/06 chưa có trong file.

**⚠️ Quang đang code SONG SONG (VSCode, CHƯA commit — KHÔNG phải của Claude phiên này):** `nav-items.ts`, `patients/new/{NewPatientForm,page}.tsx`, `api/appointments/route.ts`, migration `057_drop_appointment_doctor_overlap_constraint` (gỡ chặn trùng giờ BS — overbook 3.4). Claude chỉ stage đúng file của mình; mấy file này còn nguyên trong working tree.

> ⚠️ Lưu ý: `CLAUDE.md §2 PHASE` còn ghi "LOAD chưa chạy / 17 bảng" — LỆCH với `SYSTEM_STATE_ACTUAL.md` (03/06: đã LOAD, 27 bảng). Chưa sửa §2 vì ngoài scope; chờ lệnh.

---

# HANDOFF WORKLOG — Dashboard Ver2 (phiên 19/6, đóng)

## TRẠNG THÁI
Dashboard Ver2: hoàn tất TOÀN BỘ phần code làm được mà không cần input người.
~42 commit LOCAL, CHƯA push. Branch: feat/t-transform-01.
Phần còn lại = CHỜ PK/Quang/BS (không phải nợ code).

---

## COMMIT PHIÊN NÀY (theo thứ tự)
- 82454db — Lễ tân: progress stepper + đồng hồ chờ đổi màu (WAIT_GREEN_MAX=10/YELLOW=20). 2 mốc cuối xám chờ billing.
- 0bff182 — CSKH: bảng nhắc gọi 4 bucket (FOLLOWUP_TIERS=[2,10,20,30]) + nút "Đã gọi" → cskh_followup. Bucket RỖNG tới khi BS điền tai_kham.ngay (đúng, không phải bug).
- 73d5ff6 — Cashier split: mig052, role CASHIER_THUOC + CASHIER_DV (2 login riêng), CASHIER cũ = superset.
- 871418b — Catalog: mig051, drug_catalog (64 thuốc) + service_price (29 DV), giá NULL (lazy-fill). Picker runtime /api/catalog + datalist, dùng chung 5 form. 3 needs_review.
- 11f02d3 — Bỏ nút BS "Nhận/Trả lịch" (luồng: Lễ tân check-in → BS khám thẳng) + tên BS đầy đủ (mig053 seed 17 BS) + 3 chỗ render short_name→full_name (roster/chip/picker).
- 8ba2a8e — TKYK enable: mở menu /tasks + /patient-list + vào form khám (clinical-record gate thêm isThuKyRole). Nhánh B: thấy MỌI BS. attending_doctor_id = appointment.doctor_id (TKYK không bị ghi là người khám). TKYK KHÔNG finalize (giữ cho BS).
- bc29641 — Địa chỉ dropdown sau sáp nhập: mig054, bảng province (34) + ward (3321), nguồn ThangLeQuoc/vietnamese-provinces-database tag v3.1.0 (cấu trúc tỉnh→phường bỏ huyện). Form intake 2 select phụ thuộc. BN cũ free-text giữ nguyên.
- 2d9daea — Sửa wording board Lễ tân ("không chỉnh sửa" → "xem lâm sàng, ĐƯỢC sửa hành chính") + tên BS 3 chỗ sót (home greeting, TasksRealtime, schedule/edit).
- fabda0a — CSKH: field van_de_di_kham (text) + linh_vuc (mig055, CHECK 5 mã = TÁI DÙNG service_code PK/SK/NT/HMVS/NK, sẵn map sang form khám). KHÔNG đụng "Lý do khám" của BS.
- 5add7f0 — Form số đo siêu âm: ultrasound_record.findings JSONB (mig018 đã có), 7 số đo CRL/NT/BPD/HC/AC/FL + EFW NHẬP TAY (// TODO auto-EFW chờ Hadlock BS Thắng). 4 nút Bắt đầu/Lưu/Bất thường/Hoàn tất. Gate isUltrasoundDoctorRole, chặn ghi khi FINALIZED.
- 0bc6d47 — FIX dropdown tỉnh trống: gốc = RLS bảng province/ward bật nhưng KHÔNG có policy SELECT → authenticated đọc 0 dòng. Sửa: đọc bằng service-role bypass RLS (data hành chính công khai, server-only an toàn).

---

## TRẠNG THÁI Ô VÀNG EXCEL (12 mục): 10 XONG
- ✅ 3.0/18.0 TKYK · 4.0 PT→Phẫu thuật + tên BS · 6.0 giới tính Khác · 10.0 địa chỉ dropdown · 11.0 ngày DD/MM/YYYY · 12.0 bỏ BS duyệt + check-in Lễ tân · 13.0 Lễ tân sửa BN · 15.0 ĐD sửa Lý do khám · 16.0 sinh hiệu HA/CN/CC + dấu *
- ⚠️ 1.0 Trưởng ca: LỆCH SPEC — đã làm hành chính-only (theo recap 17/6), Excel ghi "toàn bộ". CHỜ QUANG CHỐT.
- ❌ 5.0 CM/lịch làm việc: scope chưa rõ (Excel có 2 đề xuất). CHỜ PK.

## TRẠNG THÁI HTML 7 MỤC: 5 trọn + 1 vừa xong + 1 defer
- ✅ #1 CSKH nhắc gọi · #2 lễ tân progress · #4 ĐD siêu âm 2 hàng đợi · #5 form theo dịch vụ · #6 BS siêu âm số đo (vừa xong)
- ⚠️ #3 thu ngân: role tách XONG; THIẾU hóa đơn QR + billing thuốc (chờ STK VietQR + bảng giá PK)
- ⏸️ #7 lưu ảnh: Phase 3 defer (đã chốt)

---

## CHỜ PK/QUANG/BS 24/6 (KHÔNG code được — thiếu input người)
1. ⚠️ 4.1 LỖ HỔNG NGHI: api/lab-result PATCH KHÔNG check FINALIZED → có thể sửa lab sau khi visit chốt. PK quyết: kết quả XN về muộn nhập vào đâu — amendment (có vết) hay sửa thẳng? (Tuyền test tay xác nhận trước.)
2. 1.0 Trưởng ca: "toàn bộ" (Excel) hay "hành chính only" (recap 17/6)? → Quang.
3. 5.0 CM khác Trưởng ca chỗ nào + cơ chế lịch làm việc (2 đề xuất).
4. 3.4 slot gối giờ overbook: 1 khung tối đa mấy BN, giới hạn theo BS/phòng/dịch vụ? (mig012 đang CHẶN trùng — cần gỡ đúng cách.)
5. 3.5 cấu trúc tóm tắt điều trị đa-visit → BS Thắng.
6. auto-EFW: công thức Hadlock? → BS Thắng.
7. Form tiền hôn nhân + NPĐH: field lâm sàng → BS đưa.
8. linh_vuc CSKH chọn → có AUTO chọn form khám tương ứng không? (mã đã trùng service_code, wire 1-line nếu PK muốn.)
9. #3d hóa đơn: STK + ngân hàng để sinh VietQR + bảng giá thuốc.
10. 3 thuốc needs_review → DƯỢC: Fes 1/10 · Utrogestan (Đ)/(U) · nhóm Difavon/Diflucan/Fluconazole.

---

## NỢ KỸ THUẬT
- RLS policy: province/ward đang đọc bằng service-role (vá). Idiomatic = thêm RLS policy SELECT giống service_type. Không gấp (data công khai, không PII).
- 88 row work_roster.staff_name cũ vẫn tên tắt (chỉ ca mới dùng full_name) — chưa backfill, ngoài scope.
- 4.1 PATCH lab-result chưa guard FINALIZED — chờ PK quyết (xem trên).
- in phiếu siêu âm chưa hiện số đo (chưa wire print).
- is_abnormal trong JSONB — nếu cần query "ca bất thường" thì promote thành cột riêng.
- ~42 commit LOCAL chưa push.
- 043 vẫn lỗ (append-only clinical chỉ app-layer cho clinical_record/lab_result; prescription xóa-ghi-lại tự do). Apply 043 + mở logEvent phủ thao tác lâm sàng = việc xin tài trợ làm sau.

---

## TUYỀN LOGIN TEST TAY (subagent không verify UI được)
1. ⚠️ 4.1 (ƯU TIÊN): nhập lab SAU khi visit FINALIZED → DB/API có chặn không? Lọt = báo lại (lỗ hổng).
2. Dropdown tỉnh /patients/new: ra 34 tỉnh chưa? Chọn tỉnh → phường lọc đúng? (vừa fix 0bc6d47)
3. ĐD nhập "Lý do khám" → BS vào sau, data còn không?
4. Lễ tân bấm tên BN → nút "Sửa thông tin" sáng + lưu được? (wording mới)
5. Tên BS đầy đủ ở lời chào + các board?
6. Gõ "hoa" có ra "Hòa" (search BN + nhân sự)?
7. Datalist "Chỉ định CLS" gợi ý + nhóm theo chuyên khoa? Picker thuốc lưu liều/HDSD?

---

## VIỆC NGOÀI CODE
- Push ~42 commit local khi sẵn sàng.
- Gửi DƯỢC 3 câu thuốc needs_review.
- Mang 10 câu (mục CHỜ PK) đi họp PK 24/6.
- Sửa pre-commit hook (gốc python@3.14 đã gỡ → Poetry chết): cài lại Poetry bằng python3.12 + poetry env use python3.12. Hiện đang --no-verify.

---

## QUY ƯỚC CẦU NỐI CLAUDE CODE ↔ PHIÊN CHAT (quan trọng)
Phiên chat (advisor) KHÔNG tự thấy việc làm bên Claude Code. Để advisor nắm thay đổi:
- Bên Claude Code: mỗi việc xong → ghi vào worklog/CURRENT_PROGRESS.md (delta + commit hash).
- Phiên chat sau: PASTE worklog này (hoặc git log --oneline -20) cho advisor đọc.
- Memory chỉ nhớ bối cảnh trong cuộc trò chuyện, KHÔNG tự cập nhật việc làm chỗ khác — phải tự kể/paste.
