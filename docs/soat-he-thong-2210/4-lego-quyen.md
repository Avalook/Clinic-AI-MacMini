# Soát 22/10 · Khối 4 — LEGO + QUYỀN

> Phiên soát CHỈ ĐỌC trên nhánh `main` (SHA `00bde52`). Không sửa code, test hay
> migration. Bản đồ dùng để định hướng: nhánh `claude/ban-do-hieu`; bản khai chủ
> bảng: PR #513 (nhánh `claude/goi4-ranh-gioi-lego`, chưa merge).
> Phát hiện đã đối chiếu với `phat-hien.json`; trùng thì ghi "đã biết".

## Tóm tắt 10 dòng

1. **Lỗ nặng nhất không nằm ở FastAPI mà ở PostgREST** (`/rest/v1`, Supabase tự dựng, đang mở ra Internet).
2. Mọi tài khoản đã đăng nhập — **kể cả đối tác (người ngoài) và tivi phòng chờ** — đọc thẳng được bảng khách, lịch hẹn, tiền, xét nghiệm, thai kỳ (C1).
3. Mọi nhân viên đọc được CCCD / SĐT / ngày sinh của đồng nghiệp và CCCD khách không che (C2). Giao diện chỉ cần 2 bảng; ~40 bảng còn lại là bề mặt thừa (C3).
4. Lỗ quyền thứ hai: **tự xếp mình vào ca "Điều phối" là thu tiền, hoàn tiền, xem hoá đơn được dù đã bị tắt lego** — vì gói "mở full" cho ai cũng quyền xếp lịch (C7).
5. "Quyền theo tài khoản" chưa trọn: tắt hết lego thì vai cũ quay lại (C8); vai Quản lý vẫn mở khoá ca / xem tài chính bất kể lego (C9).
6. FastAPI: 619 endpoint, không thấy lệnh ghi nào "quên kiểm quyền" — chỗ hở nằm ở luật lịch trực và vai.
7. Giao diện (TSX) **không tự quyết tiền** — máy chủ tính lại và từ chối khi lệch. 78 chỗ hỏi vai, ~25 chỗ quyết thuần theo vai, đều đã có máy chủ chặn.
8. Route Next chạm DB: đúng **1** (`check-phone`, đã tắt); xoá 5 tệp route chết là về 0. Riêng `console/feedback` cho người lạ ghi 8MB/lần lên đĩa (B1).
9. Ranh giới lego: bản khai PR #513 khớp code `main` (bài quét xanh); 97 chỗ ghi chéo, bảng `visit` bị 11 tệp khối khác ghi; 53 hàm SQL ghi bảng nằm ngoài tầm quét.
10. Lộ trình: khoá PostgREST + vá chuỗi Điều phối trước (Mức 3, cần Tuyền duyệt), rồi quyền theo tài khoản, cuối cùng mới gom luật khỏi TSX.

## Bảng phát hiện

| # | Mức | Ở đâu | Một câu | Độ chắc |
|---|---|---|---|---|
| C1 | **cao** | `20260730000004_tenant_scoped_rls.sql:149-171` | Đối tác / tivi đọc toàn bộ khách, tiền, xét nghiệm qua `/rest/v1` | chắc theo code, chưa chạy DB |
| C2 | **cao** | `20260730000008_table_grants.sql:48-59` | Mọi nhân viên đọc CCCD đồng nghiệp + CCCD khách không che | chắc theo code |
| C7 | **cao** | `cashier_scope_service.py:386`, `payment_service.py:342`, `config_service.py:163` | Tự xếp ca DIEU_PHOI ⇒ vượt lego Thu tiền / Hoàn tiền / Báo cáo | chắc |
| C3 | vừa | `20260730000008_table_grants.sql` | Chưa có khoá PostgREST tổng; ~40 bảng đọc được không cần lego | chắc |
| C4 | vừa (đã biết) | `20260923000003_capability.sql:175-188` | View quyền vượt RLS, đọc chéo phòng khám | chắc |
| C8 | vừa | `api/identity.py:897` | Tắt hết lego ⇒ vai tài khoản quay lại | chắc |
| C9 | vừa | `chot_so_ca_service.py:234`, `report_access_service.py:95` | Đặc quyền Quản lý chỉ hỏi vai, không theo lego | chắc |
| C10 | vừa | `staff_service.py:310-320` | `staff.manage` tự nâng mình lên Quản lý | chắc, khó xảy ra |
| C11 | vừa | `doi_tac_service.py:463-503` | Đối tác thấy và trả kết quả việc của đối tác khác | chắc |
| C12 | vừa | `20260929000001_doi_nguoi_trong_ca.sql:168-175` | Quyền theo lịch tính cả ngày, cả dòng PENDING | chắc |
| B1 | vừa | `app/api/console/feedback/route.ts:17-41` | Người lạ ghi ảnh 8MB lên đĩa trước khi kiểm phiên | chắc |
| B2 | vừa (hỏi Tuyền) | `payment_service.py:240-268` | Giảm giá tới 100% không cần quyền riêng | chắc |
| B3 | vừa/thấp (hỏi Tuyền) | `app/api/admin/users/route.ts:350-410` | Lego Tài khoản đặt lại mật khẩu Quản lý được | chắc |
| A1 | vừa | sổ nợ PR #513 | `visit` bị 11 tệp khối khác ghi thẳng | chắc |
| A3 | vừa | `routers/booking.py:337` | Cách ly phòng khám chỉ dựa `WHERE clinic_id` thủ công | chắc (cơ chế) |
| C5 | thấp-vừa | Caddy `/realtime/v1` | Realtime không dùng mà vẫn mở | nghi |
| C6 | thấp | `scripts/backup-db.sh:243` | Chưa biết ACL thật trên prod | — |
| C13 | thấp | `routers/thu_ky.py:69,96` | Hồ sơ hành chính khách chỉ đòi đăng nhập | chắc |
| C14 | thấp | `permission_service.py` | Tự cấp quyền; `valid_until` rác ⇒ 500 | chắc / nghi |
| C15 | thấp (đã biết) | `permission_service.py:~601` | Nhóm mẫu tắt vẫn rơi về PRESET | chắc |
| A2 | thấp | migrations | 53 hàm SQL ghi bảng ngoài tầm bài quét | chắc |
| A4 | thấp | `routers/config.py:800-833` | display-settings đọc–trộn–ghi không khoá | chắc |
| B4 | thấp | `proxy.ts:28` + 5 route | Route đã tắt còn tệp, còn chạm DB | chắc |
| B5-B8 | thấp | xem phần (b) | Luật / phép tính chép trong TSX, máy chủ đã chặn | chắc |

---

## Từ ngữ dùng trong báo cáo

- **Khối lego / module**: một vùng nghiệp vụ có ranh giới rõ (Đặt lịch, Thu tiền,
  Khám bệnh…). Khai trong `src/clinicai/modules.py`.
- **Chủ bảng**: khối DUY NHẤT được ghi một bảng. Khối khác muốn đổi dữ liệu ấy thì
  gọi lệnh của khối chủ hoặc phát sự kiện cho nó tự nghe.
- **Ghi chéo**: tệp của khối A chạy `INSERT/UPDATE/DELETE` vào bảng của khối B.
- **Capability (khối công việc)**: một quyền lệnh, vd `payment.service.collect`.
  Bật một lego trên màn Phân quyền = cấp một gói capability vào `capability_grant`.
- **Hỏi vai** vs **hỏi quyền**: hỏi vai = `if role == 'DOCTOR'`; hỏi quyền =
  `can(identity, 'clinical.record.write')`. Luật dự án: phải hỏi quyền.

---

## Phần (a) — Ranh giới khối lego

### a.1 Bản khai ở PR #513 có khớp code thật không?

Cách kiểm: chép `src/clinicai` của `main` hiện tại ra thư mục nháp, thay đúng
`modules.py` bằng bản của PR #513, rồi chạy 4 hàm kiểm của
`test_luat_cam_ghi_cheo.py` (bài quét mọi câu SQL ghi bảng trong code Python).

| Kiểm | Kết quả trên `main` 00bde52 |
|---|---|
| Mọi bảng bị ghi đều có chủ (hoặc là bảng kỹ thuật) | ĐẠT |
| Mọi tệp ghi bảng có chủ đều khai thuộc một khối | ĐẠT |
| Bản khai tệp hợp lệ (tệp còn, không khai hai nơi) | ĐẠT |
| Ghi chéo thực tế == sổ nợ `NO_GHI_CHEO` | ĐẠT — main chưa thêm chỗ ghi chéo mới kể từ lúc PR cắt nhánh |

**Sổ nợ ghi chéo: 97 chỗ** — 17 `VI_PHAM` (đã xác nhận sai), 71 `CHUA_XET` (chưa ai
đọc), 5 `XEM_LAI_KHOI`, 4 `DUNG_THIET_KE`. Tệp ghi chéo nhiều nhất:

| Tệp | Số bảng khối khác bị ghi | Ghi chú |
|---|---|---|
| `services/hoan_tac_service.py` | 10 | Hoàn tác nhiều khối trong một giao dịch — phần lớn là chủ ý |
| `services/luot_kham_service.py` | 9 | `appointment`, `queue_entry`, `service_order`, `tep_ket_qua`, `visit`… — **điểm nóng số 1** |
| `services/config_service.py` | 7 | Màn cấu hình ghi giá, thuốc, lịch trực |
| `services/booking_service.py` | 6 | Ghi `queue_entry`, `visit`, `patient`, `work_roster` |
| `services/clinical_sign_service.py` | 4 | Ký bệnh án ghi việc CSKH, hẹn gọi lại |

**Bảng `visit` (lượt khám, chủ là Tiếp đón) bị 11 tệp của 5 khối khác (Đặt lịch, Khám bệnh, Điều phối, Khách chọn dịch vụ, Kết quả, cộng 2 tệp quầy thuốc) ghi trực
tiếp.** Đây là chỗ "lego" yếu nhất: mọi khối đều tự đổi cột trạng thái lượt, nên
không có một chỗ nào biết đầy đủ "lượt đổi trạng thái vì sao". Muốn cho phòng khám
thứ hai dùng (có luật lượt khác) thì phải sửa ở 11 nơi.

### a.2 Điểm mù của bài quét — ghi chéo nằm trong hàm SQL của database

Bài quét của PR #513 chỉ đọc chuỗi SQL trong tệp `.py`. Nó tự ghi điểm mù "hàm SQL
trong database (trigger) không quét". Đo bổ sung: lấy định nghĩa CUỐI của mỗi hàm
`CREATE OR REPLACE FUNCTION` trong `supabase/migrations/` → **222 hàm, 53 hàm có
câu ghi bảng**. Một số ghi bảng của khối khác:

| Hàm (migration định nghĩa cuối) | Ghi bảng | Khối chủ bảng |
|---|---|---|
| `move_visit_to_station` (`20260920000003_…cp6_doc_don_hien_hanh.sql`) | `visit`, `work_item`, `event_log` | Tiếp đón, Trách nhiệm |
| `update_visit_current_node` (`20260807000003_…`) | `visit` | Tiếp đón |
| `instantiate_visit_workflow`, `order_services` (`20260915000022_…`) | `work_item`, `work_item_event` | Trách nhiệm |
| `check_in_appointment` (`20260812000001_…`) | `appointment` | Đặt lịch |
| `nhac_tai_kham_dong_khi_co_lich` (`20261003720000_…`) | `nhac_tai_kham`, `hen_gio` | CSKH |
| `sdt_them_lam_tuoi_patient` (`20260815000002_…`) | `patient` | Hồ sơ khách |

(Các hàm nạp danh mục / dọn dữ liệu thử chạy một lần — bỏ qua.)

### a.3 Router chứa luật thay vì gọi service

Đếm câu SQL viết thẳng trong `src/clinicai/api/v1/routers/*.py` (57 tệp): 15 tệp có
SQL. Phần lớn là ĐỌC (danh mục, tỉnh/thành) — chấp nhận được. Chỗ có LUẬT:

| Router | Chỗ | Luật nằm ở router |
|---|---|---|
| `config.py:784-835` | `PATCH /display-settings` | Đọc–trộn–ghi `clinic.settings.display` (không khoá dòng, hai người lưu cùng lúc thì người sau đè) |
| `config.py:~930-1030` | lưu giờ ca + giờ mở cửa | Kiểm giờ mở/đóng, gộp lỗi, khoá `FOR UPDATE`, ghi `clinic.settings` — đúng ra là `clinic_settings_service` (PR #513 đã tự ghi "trái luật router mỏng, để dời sau") |
| `booking.py:660-700` | lưới nhận lịch | Đọc giờ mở cửa + ca rồi cắt khung — gọi hàm thuần `khung_theo_thu`, chấp nhận được nhưng SQL nên về service |
| `booking.py:395-430` | CSKH báo cần xếp bác sĩ | Luật "lịch đã có bác sĩ thì không báo" ở router |
| `queue.py:104` | hàng chờ | lấy `date.today()` — **đã biết** (phat-hien.json, sửa ở PR #522) |

Đáng chú ý: comment ở `booking.py:337` ghi rõ **"backend chạy quyền chủ nên RLS
không áp"** — nghĩa là cách ly phòng khám A/B ở FastAPI hoàn toàn dựa vào việc MỖI
câu SQL tự nhớ `WHERE clinic_id = …`. Không có lưới an toàn thứ hai ở database.
Với mục tiêu "nhiều phòng khám dùng", đây là rủi ro cấu trúc (xem phát hiện A3).

### Phát hiện phần (a)

**A1 · vừa · `visit` bị 11 tệp của khối khác ghi thẳng** —
`services/luot_kham_service.py`, `booking_service.py`, `clinical_record_service.py`,
`clinical_sign_service.py`, `hoan_tac_service.py`, `hang_cho.py`,
`ultrasound_service.py`, `lam_truoc_thu_sau.py`, `ban_le_service.py`,
`ban_theo_don_service.py`, `doi_bac_si_service.py` (đều trong sổ nợ, nhãn `CHUA_XET`).
- Vì sao sai: lượt khám là trục của cả hệ thống; khi nhiều khối tự đổi trạng thái,
  bất biến kiểu "lượt đã đóng thì đứng yên" phải được ép lại ở từng chỗ (hiện ép bằng
  trigger `update_visit_current_node`). Thêm một khối mới là thêm một chỗ có thể quên.
- Kịch bản: chưa có kịch bản sai cụ thể đã tái hiện — đây là rủi ro bảo trì.
- Độ chắc: chắc chắn về cấu trúc (bài quét chạy được); về lỗi cụ thể: chưa.
- Test đề xuất: đã có bánh cóc `test_luat_cam_ghi_cheo` (PR #513) — **merge PR #513**
  là bước đầu; sau đó gỡ dần nhãn `CHUA_XET` của `visit` thành lệnh của Tiếp đón.
- Hướng sửa: khối Tiếp đón mở vài lệnh `dong_luot`, `mo_lai_luot`, `doi_buoc_luot`;
  các khối khác gọi lệnh đó thay vì `UPDATE visit`.

**A2 · thấp · Bài quét ghi chéo không thấy hàm SQL** — 53 hàm SQL ghi bảng (bảng
a.2). Độ chắc: chắc (đã đo). Test đề xuất: mở rộng bài quét đọc định nghĩa cuối
của hàm trong migration (cách đo ở a.2) và đưa vào sổ nợ riêng. Hướng sửa: ghi vào
sổ nợ trước, không cần đổi hàm ngay.

**A3 · vừa · Cách ly phòng khám ở FastAPI chỉ dựa vào `WHERE clinic_id` thủ công** —
`api/v1/routers/booking.py:337` (comment tự xác nhận), toàn bộ service dùng pool chủ.
- Vì sao sai: một câu SQL mới quên `clinic_id` = phòng khám B thấy dữ liệu phòng
  khám A. Hôm nay chỉ có MỘT phòng khám thật (Dr4Women, cơ sở Hào Nam) nên chưa có
  hại; với mục tiêu nhiều phòng khám thì đây là lỗ lớn nhất.
- Kịch bản (tương lai): phòng khám thứ hai lên; một endpoint đọc theo `id` lấy từ
  URL mà quên lọc `clinic_id` → nhân viên phòng khám B mở được lượt của A bằng cách
  đổi id trên URL.
- Độ chắc: chắc về cơ chế; chưa liệt kê đủ từng câu thiếu lọc (ngoài phạm vi).
- Test đề xuất: test "hai phòng khám" — dựng clinic A, B trong DB tạm, gọi mọi GET
  `/{id}` bằng danh tính B với id của A, mong 404.
- Hướng sửa: (dài hạn) đặt `SET LOCAL app.clinic_id` mỗi giao dịch và bật RLS theo
  biến đó cho bảng có `clinic_id`; (ngắn hạn) test hai phòng khám ở trên.

**A4 · thấp · `PATCH /display-settings` đọc–trộn–ghi không khoá** —
`api/v1/routers/config.py:800-833`. Hai người lưu cùng lúc (một bật khu A, một tắt
khu B) → người lưu sau đè mất thay đổi của người trước. Hàm giờ ca ngay dưới đã khoá
`FOR UPDATE`, hàm này thì không. Độ chắc: chắc (đọc code). Hậu quả nhỏ (công tắc
bảng gọi số). Hướng sửa: dời vào `clinic_settings_service`, dùng `jsonb_set` theo
từng khu hoặc `SELECT … FOR UPDATE`.

---

## Phần (b) — Luật nghiệp vụ còn nằm trong TSX

Kết luận ngắn: **không tìm thấy chỗ nào giao diện tự quyết TIỀN mà máy chủ tin
theo.** Giảm giá, chia hình thức thu, tiền thừa, hoàn tiền đều được FastAPI tính lại
và từ chối khi lệch (`services/phan_thu.py:135-140`, `payment_service.py:418-425`).
Cookie vai `clinic_role` chỉ được ghi lúc đăng nhập
(`app/(auth)/login/actions.ts:81`), không chỗ nào đọc nó để quyết quyền.

### b.1 Chỗ hỏi VAI trong TSX, theo nhóm

Đếm bằng grep các mẫu `role ===`, `isXxxRole(`, `canWriteIntake/canEditPatient/
canManageAppt/canCheckin/canSeeNav(`, `vaiLamViec(`, `getVaiChinh(`, `.includes(`
trên vai — không tính định nghĩa trong `lib/roles.ts` và tệp test: **78 dòng**.
(Con số ~123 ở CLAUDE.md có lẽ tính cả định nghĩa trong `roles.ts` và biến suy ra
như `canEdit`/`canManage` truyền qua prop — vd `CustomersView` có 17 chỗ dùng prop.)

| Nhóm | Số chỗ | Nguy hiểm? |
|---|---|---|
| Route Next ĐÃ TẮT (410): lab-result 4, check-phone 2, service-log 2, sono 2, dispatch/alerts-call 2 | 12 | Không — code chết, `proxy.ts` chặn trước (xem B4) |
| Khung, điều hướng: tasks/page 7, layout 6, nav-items 5, home/page 5, BottomNav 1, app/page 1, ops/PortalBoard 1 | 26 | Không — chuyển trang, nhãn, menu |
| Tiếp nhận / đặt lịch / khách: patient-list 5, customers/page 4, patients/new 3 + NewPatientForm 4, WeeklyAppointmentsTable 4, appointments 1, cho-xep-bac-si 1, reception/queue 1, QuyenContext 1 | 24 | Thấp — phần lớn "`quyen === null` thì dùng vai" |
| Lịch làm việc: schedule/page 4, NgoaiLeCaTruc 1 | 5 | Thấp — dự phòng khi chưa có quyền |
| Vận hành: ops/summary route 1, ops/ToanCanh 1 | 2 | Thấp (B5) |
| Lọc theo vai của NHÂN VIÊN ĐƯỢC HIỂN THỊ (không phải người xem): ClinicConfigBoard 2, BangBacSiTuan 1, HangChoXacNhanKetQua 1 | 4 | Không — đây là dữ liệu, không phải quyền |
| lib (clinic-session 3, identity-authority 1, quyen-cua-toi 1 là comment) | 5 | Không |

Trong 78 chỗ, **~25 chỗ quyết thuần theo vai** (không có nhánh quyền): chuyển trang
ở tasks, layout DISPLAY/PARTNER/TKYK, nav-items, `isReception` ở home, chọn luồng ở
patients/new. Còn lại là code chết hoặc chỉ dùng vai khi máy chủ chưa trả lời quyền.

### b.2 Route Next (`src/dashboard/app/api/**/route.ts`: 140 tệp)

| Loại | Số | Ghi chú |
|---|---|---|
| Chỉ chuyển sang FastAPI qua `lib/backend-proxy` | 135 | đúng luật |
| Tự `fetch` sang `CLINIC_API_URL` kèm token | 3 | `appointments/quote`, `appointments/slot-hold`, `ultrasound/image` (đã tắt) |
| **Chạm thẳng DB** | **1** | `patients/check-phone` (`.from("patient")` dòng 56) — đã tắt qua `lib/route-da-tat.ts`, nhưng tệp còn. Đúng như CLAUDE.md nói |
| Cầm khoá service-role | 1 | `admin/users` — cổng `authorizeAdmin` (dòng 68-113) xác minh phiên với GoTrue rồi hỏi `GET /api/v1/phan-quyen/toi`, phải có `account.manage`; trước mỗi lệnh GoTrue còn gọi backend kiểm cùng phòng khám (`tai_khoan_service.py:57-71`). **Không giả được bằng cookie vai.** |
| Tự xử lý dữ liệu | 2 | `console/feedback` ghi ổ đĩa (B1), `service-price` tự chuẩn hoá giá (B8) |

Ngoài route: `proxy.ts:140-145` mỗi lần mở trang đọc `.from("staff")` qua PostgREST
bằng phiên người dùng (chỉ để chặn trang; API tự kiểm lại).

Cờ mở quyền tạm `MO_QUYEN_TAM_THOI` / `NEXT_PUBLIC_MO_QUYEN_TAM_THOI`: mặc định TẮT ở
cả hai nửa (`api/identity.py:1076`, `lib/roles.ts:586-588`, `Dockerfile.dashboard:23`),
`main.py:123-133` cảnh báo khi bật. Rủi ro nhỏ: nửa giao diện là biến lúc build —
bật trong `.env.prod` mà không build lại dashboard thì hai nửa lệch nhau.
`lib/quyen-client.ts` đúng: `null` → `false` (hỏng thì đóng).

### Phát hiện phần (b)

**B1 · vừa · `/api/console/feedback` ghi ảnh ra ổ đĩa TRƯỚC khi kiểm người gọi** —
`src/dashboard/app/api/console/feedback/route.ts:17-41`; `proxy.ts:100` cho mọi `/api`
đi thẳng ("API tự kiểm").
- Vì sao sai: route `mkdir` + `writeFile` tới 8MB rồi mới chuyển sang backend. Backend
  trả 401 thì tệp đã nằm trên đĩa. Ngoài ra `role_at_time` do trình duyệt tự khai.
- Kịch bản: người lạ KHÔNG đăng nhập lặp lại
  `curl -F comment=x -F image=@anh-8mb.png https://dr4women.io.vn/api/console/feedback`
  → mỗi lần thêm 8MB vào `.feedback/`, đầy dần ổ của máy chạy dashboard (cùng VPS với
  prod). Tên tệp theo mili-giây nên hai lần trong cùng ms còn đè nhau.
- Độ chắc: **chắc** (đã đọc code). Chưa kiểm Caddy có giới hạn kích thước/tần suất không.
- Test đề xuất: POST không phiên → 401 và thư mục `.feedback/` không có tệp mới.
- Hướng sửa: `supabase.auth.getUser()` trước; tốt hơn: gọi backend trước, `ok` mới
  ghi tệp (hoặc chuyển tải ảnh xuống FastAPI). Bỏ `role_at_time` từ client.

**B2 · vừa (cần Tuyền quyết) · Giảm giá không có quyền riêng** —
`services/payment_service.py:240-268` (`_validate_discount_input`) chỉ kiểm số
(0 < % ≤ 100, có lý do), `bill_service.py:1217-1251` tương tự; trong
`permissions/catalogue.py` không có capability nào về giảm giá. TSX luôn hiện ô giảm
(`thu-ngan/HoaDonMot.tsx:382`, `QuayThuNgan.tsx:1265`).
- Kịch bản: bất kỳ ai có lego Thu tiền (thu ngân ca tối, người làm thay) chọn
  "Giảm 100%", lý do gõ "x" → lượt thu 0đ. Sổ có ghi người giảm, nhưng không có gì chặn
  trước.
- Độ chắc: **chắc**.
- Test đề xuất: tài khoản có `payment.service.collect` nhưng không có quyền giảm, gửi
  `discount_*` → 403.
- Hướng sửa: thêm capability `payment.discount.apply` (có thể kèm trần %), kiểm trong
  `_thu_dich_vu` và nhánh tiền thuốc; màn ẩn/hiện theo quyền đó. **Hỏi Tuyền**: giảm
  giá có cần quyền riêng / trần không?

**B3 · vừa/thấp (cần Tuyền quyết) · Người có `account.manage` đặt lại mật khẩu được
cho cả Quản lý** — `src/dashboard/app/api/admin/users/route.ts:350-372` (reset),
`374-410` (đổi tên đăng nhập); `TaiKhoanService.doc` chỉ kiểm "cùng phòng khám".
- Kịch bản: người được bật riêng lego Tài khoản (không có `permission.manage`) đặt lại
  mật khẩu tài khoản Quản lý → đăng nhập bằng tài khoản đó → có toàn quyền. Đây là
  đường leo thang quyền. Thêm: tài khoản GoTrue là toàn cục — khi có phòng khám thứ
  hai, nhân viên làm ở cả hai sẽ bị phòng A đổi được mật khẩu dùng ở phòng B.
- Độ chắc: **chắc** về code; mức thật tuỳ ai đang giữ `account.manage`
  (`catalogue.py:671`, lego chỉ-quản-lý).
- Test đề xuất: người giữ `account.manage` nhưng THIẾU một quyền mà người đích đang có
  → reset/change_email/ban bị 403.
- Hướng sửa: endpoint backend "được thao tác tài khoản này không" (người làm phải có
  ⊇ quyền người đích), gọi trước mọi lệnh GoTrue.

**B4 · thấp · 5 route đã tắt vẫn còn tệp, còn gác theo vai và chạm DB** —
lab-result, check-phone, service-log, sono, dispatch/alerts-call; chỉ được che bởi
`ROUTE_DA_TAT` (`proxy.ts:28`). Nếu ai thêm ngoại lệ vào matcher (như đã làm cho
`cskh/ket-qua`) thì handler sống lại với luật theo vai + `.from("patient")`. Độ chắc:
chắc. Test: mỗi mẫu trong `ROUTE_DA_TAT` không còn tệp `route.ts`. Sửa: xoá 5 tệp →
"route Next chạm DB" về **0**.

**B5 · thấp · `/phan-quyen/toi` hỏng (429, hết giờ) thì màn quay về luật theo vai** —
`customers/page.tsx:99-118`, `patient-list/page.tsx:146-160`, `schedule/page.tsx:73-76`,
`home/page.tsx:561`, `QuyenContext.tsx:36`, `lib/roles.ts:783-789, 808`. Lego đã tắt
mà nút vẫn hiện; máy chủ vẫn từ chối khi bấm → chỉ gây nhiễu. Riêng
`api/ops/summary/route.ts:31-33` trả link Kuma/Dozzle cho Quản lý đã tắt lego 20 (lộ
rất ít: hai dịch vụ chỉ nghe 127.0.0.1). Sửa: khi `null` thì ẩn nút hành động.

**B6 · thấp · Chọn luồng biểu mẫu tiếp nhận theo vai trong TSX** —
`patients/new/page.tsx:36-48`, `NewPatientForm.tsx:891,908,1847`,
`nav-items.ts:293,298,512`. Máy chủ vẫn ép đúng (`booking_service.py:571,588-596`: kênh
WALK_IN cần `reception.checkin.perform`) → nợ kiến trúc, không phải lỗ.

**B7 · thấp · Phép tính xem trước chép lại trong TSX** — `GiamGia.tsx:62-80` chép
`ap_giam_gia`, `ChiaHinhThuc.tsx:40-80` chép `ap_phan`; câu "Đã thu X"
(`QuayThuNgan.tsx:421-423`, `BanLeThu.tsx:269`) lấy số màn tự tính. Máy chủ tính lại và
từ chối khi lệch → hỏng thì đóng. Sửa: hiện số tiền máy chủ trả về. (Đã biết, không
báo lại: `HoaDonMot.tsx:254`, `ChiTietLuot.tsx:278`.)

**B8 · thấp · `api/service-price/route.ts:42-47` tự chuẩn hoá giá** (tạo thì làm tròn,
sửa thì gửi nguyên); backend `parse_price` (`config_service.py:1710,1825`) xử lý cả hai.
Luật bị chép — bỏ ở route.

---

## Phần (c) — Quyền

### c.1 Quyền phía API (FastAPI)

Quét 619 endpoint trong 59 router (`main` 00bde52):

| Kiểu kiểm ở cửa router | Số endpoint |
|---|---|
| Hỏi capability ngay ở cửa (`cua_quyen`, `cua_y_khoa`, `get_partner_identity`, `_require_tools_access`) | 328 |
| Chỉ đòi đăng nhập ở router (`get_current_identity`) — 179 trong số này có kiểm quyền bên trong service | 276 |
| Cửa nội bộ (`cua_noi_bo`) | 11 |
| DISPLAY / công khai | 3 |

Router không còn `require_role` (trừ một GET, `config.py:734`); hỏi vai đã dồn xuống
service dạng `identity.co_vai(...)` — còn ~64 chỗ. Các lệnh GHI "chỉ đăng nhập" đã đọc
tay: không có cái nào trống trơn (đều có `doi_quyen`/`can` trong service hoặc đã nghỉ
trả 410). **Lỗ thật không nằm ở "endpoint quên kiểm" mà ở ba chỗ: chuỗi lịch trực, vai
Quản lý theo tài khoản, và nhánh rơi về vai khi tắt hết lego.**

Đã kiểm, KHÔNG phải lỗ: `identity.clinic_id` luôn lấy từ membership (`X-Clinic-ID`,
`X-Location-ID` chỉ là bộ chọn, có đối chiếu DB); `location_id` trong body của
`clinic_config`/`floor` có kiểm thuộc phòng khám; DISPLAY/PARTNER bị
`get_current_identity` chặn ở mọi router thường; người KHÔNG có `permission.manage`
không có đường ghi thẳng `capability_grant` (mọi lối qua
`PermissionService.cap_khoi/thu_khoi` + `doi_quyen("permission.manage")`).

### Phát hiện phần (c.1)

**C7 · CAO · Tự xếp mình vào vị trí "Điều phối" (DIEU_PHOI) trong lịch trực là vượt
được lego Thu tiền, Hoàn tiền và Báo cáo.**
- Chuỗi (đã tự mở từng chỗ):
  1. "Mở full lego" cấp khối `truong_ca` cho mọi vai nội bộ
     (`permissions/catalogue.py:898-904`; `truong_ca` không thuộc `KHOI_CHI_QUAN_LY`
     dòng 892) → ai cũng có `roster.manage`.
  2. `services/config_service.py:144-150` `_xep_lich` = có `roster.manage` →
     `add_shift` (dòng 163, 251) ghi ca **APPROVED** ngay, không chặn ngày đã qua;
     `thay_nguoi` (~dòng 833) ghi rõ "không kiểm ma trận vai × vị trí".
  3. Đứng DIEU_PHOI → `cashier_scope_service.py:386-397` coi là trưởng ca (head) →
     `payment_access_service.py:114` gắn `cashier_head_scope` →
     `head_money_grant(...)` **thay cho** `can(...)` ở `payment_service.py:342` (và
     `:776`, `hoan_tien_service.py:69`, `quay_thuoc_service.py:84/199/419`) →
     `report_access_service.py:189` cho `financial=True`.
- Kịch bản: quản lý tắt lego Thu tiền và lego Báo cáo của lễ tân A. A (vẫn có
  `roster.manage` từ gói mở full) gọi `POST /roster/shifts {work_date: hôm nay,
  station: "DIEU_PHOI", shift: "FULL"}` → ca APPROVED → `POST /payments` thu được (kèm
  giảm giá tới 100%, B2), `/payments/hoan-tien` hoàn được, `GET /hoa-don?tu=…&den=…`
  xem toàn bộ hoá đơn + tên khách mọi ca. Đặt `work_date` ngày cũ → đọc tài chính ngày
  đó (nếu ma trận vị trí cho phép).
- Độ chắc: **chắc** (đã lần theo code); chưa bấm thật.
- Test đề xuất: tài khoản có `roster.manage`, KHÔNG có `payment.service.collect` → tự
  thêm DIEU_PHOI → `POST /payments` phải 403; `add_shift` ngày quá khứ → 422.
- Hướng sửa: `head_money_grant` vẫn phải đòi capability thu tiền (bỏ "hoặc"); báo cáo
  đòi `report.view`; cấm tự xếp / tự thay mình vào DIEU_PHOI; cấm `add_shift` quá khứ;
  cân nhắc đưa `truong_ca` vào `KHOI_CHI_QUAN_LY`. Mức 3 (quyền + tiền).

**C8 · VỪA · Tắt HẾT lego của một người thì vai tài khoản quay lại** —
`api/identity.py:897` (`doc_vai_theo_lego`): không còn dòng quyền nào → trả `None` →
`cac_vai()` dùng lại vai gốc (~`:236`). Các cửa còn hỏi vai mở ra:
`tep_ket_qua_service.py:220,245` (đọc/tải tệp kết quả), `booking_service.py:867`,
`ho_so_khach_doc.py:57`.
- Kịch bản: quản lý "đình chỉ" bác sĩ X bằng cách tắt mọi lego → X vẫn đọc / tải tệp
  kết quả mọi chỉ định (vì `co_vai(NORMAL_READ_ROLES)` đúng với DOCTOR).
- Độ chắc: chắc. Test: staff chỉ có grant đã thu → `cac_vai()` không chứa DOCTOR.
- Sửa: đã từng có grant (dù đã thu) → trả `frozenset()`, chỉ giữ lưới an toàn cho
  phòng khám CHƯA TỪNG cấp quyền.

**C9 · VỪA · Vai Quản lý / TKYK / BS siêu âm không đi theo lego, còn nhiều đặc quyền
chỉ hỏi vai** — `VAI_DO_LEGO` không chứa các vai này (`catalogue.py:1204`). Chỉ hỏi
`co_vai(MANAGEMENT)`: mở khoá ca đã chốt (`chot_so_ca_service.py:234`), xem tài chính
đầy đủ mọi ca/cơ sở (`report_access_service.py:95/105/187`), bỏ qua lịch trực ở mọi
quầy (`cashier_scope_service.py:113/359/462`), `tep_ket_qua_service.py:163`.
- Kịch bản: tài khoản Quản lý bị tắt lego Báo cáo vẫn `GET /hoa-don`,
  `/reports/cuoi-ngay`, `POST /reports/chot-ca/mo-khoa`. Đây chính là "quyền kiểm ở
  vai, không theo TÀI KHOẢN" mà mục tiêu 21 lego muốn bỏ.
- Độ chắc: chắc. Sửa: đổi sang capability (`report.view`,
  `accounting.finance.full`, quyền mới cho mở khoá ca).

**C10 · VỪA · `staff.manage` leo thang lên Quản lý** — `api/v1/routers/staff.py:167` →
`staff_service.update_staff` dòng 310-320 đổi `clinic_membership.role` không chặn tự
đổi cho mình, không chặn nâng lên MANAGEMENT; `create_staff` (`:144`) cấp preset theo
vai mới, preset MANAGEMENT có `quan_tri_quyen` (= `permission.manage`).
- Kịch bản: người có khối `nhan_su` nhưng không có `permission.manage` gọi
  `PATCH /staff/{id-của-mình} {"primary_department":"MANAGEMENT"}` → nhận các đặc quyền
  C9. Chỉ xảy ra khi `nhan_su` được cấp lẻ qua API (màn lego 19 luôn gộp hai khối).
- Độ chắc: chắc về code; khả năng xảy ra thấp. Sửa: đổi/tạo vai có preset chứa
  `quan_tri_quyen` phải đòi `permission.manage`; cấm đổi vai chính mình.

**C11 · VỪA · Đối tác thấy việc của MỌI đối tác và mọi cơ sở** —
`services/doi_tac_service.py:463-503` lọc theo `clinic_id` + có dòng
`doi_tac_nhan_viec`; không có gì gắn việc với đối tác cụ thể; vai PARTNER còn bỏ lọc
cơ sở. Kịch bản: tài khoản lab A `GET /doi-tac/viec` thấy tên + mã khách gửi lab B;
`POST /doi-tac/viec/{id}/tra-ket-qua` lên việc của B được. Hôm nay nếu chỉ có MỘT đối
tác thì chưa hại. Độ chắc: chắc. Sửa: gắn đối tác vào phòng/nút đối tác hoặc `staff`,
lọc theo đó. **Hỏi Tuyền**: hiện có mấy tài khoản đối tác?

**C12 · VỪA · Quyền theo lịch trong `v_quyen_thuc_te` không theo luật ca** —
`supabase/migrations/20260929000001_doi_nguoi_trong_ca.sql:168-175`: chỉ lọc
`status <> 'REJECTED'`, cả ngày; trong khi vai theo lịch (`identity.py`
`vi_tri_dang_trong_ca`) xét APPROVED + giờ ca khi bật `vai_lich_theo_ca`. Kịch bản:
người xếp ca SÁNG ở một phòng dịch vụ vẫn có quyền thực hiện / duyệt kết quả của phòng
đó lúc 20h; dòng PENDING cũ cũng cấp quyền. Độ chắc: chắc. Sửa: thêm
`status = 'APPROVED'` (và điều kiện ca khi bật) + test SQL. Mức 3 (migration).

**C13 · THẤP · `ho-so-khach/{id}/hanh-chinh` và `/cskh` chỉ đòi đăng nhập** —
`api/v1/routers/thu_ky.py:69,96`, không hỏi `patient.list.view`. Người bị tắt lego
Danh sách bệnh nhân vẫn đọc SĐT, địa chỉ, nhật ký CSKH nếu biết `clinic_patient_id`.
Sửa: thêm cửa quyền. (Lọc thư ký theo bác sĩ — **đã biết**, `thu_ky_bac_si.py:50`.)

**C14 · THẤP · Tự cấp quyền** — `cap_khoi` cố ý không chặn tự cấp (docstring đầu
`permission_service.py`): người có `permission.manage` tự cấp được mọi khối trừ
`noi_bo_giam_sat`. Chấp nhận được nếu chỉ Quản lý giữ; nên ghi nhật ký riêng. Phụ:
`valid_until` chuỗi thô vào `$6::timestamptz` → asyncpg ném DataError (500) — trái luật
"đầu vào ngày giờ rác trả rỗng" (nghi, chưa chạy).

**C15 · THẤP (đã biết) · Nhóm mẫu đã tắt vẫn rơi về hằng `PRESET`** —
`permission_service.py:~601`; sửa ở PR #522 chưa merge, vẫn còn trên `main`.

Bộ nhớ đệm quyền (5 giây "CÓ", danh tính 30 giây, `cache.quen()` sau cấp/thu/xếp lịch,
uvicorn 1 worker) — không thấy cửa sổ đáng kể. `/display/config?clinic_id=` công khai:
chỉ lộ cấu hình bảng gọi số; chuỗi không phải UUID → 5xx thay vì rỗng (thấp).

### c.2 PostgREST `/rest/v1` + RLS (đọc thẳng database qua Supabase tự dựng)

**PostgREST** = dịch vụ của Supabase biến mỗi bảng Postgres thành một địa chỉ web
(`/rest/v1/<bảng>`). **RLS** = luật lọc theo dòng do Postgres tự áp cho người gọi.
FastAPI chạy bằng quyền chủ database nên RLS KHÔNG áp cho FastAPI; RLS chỉ là
"cửa" khi ai đó gọi thẳng `/rest/v1`.

**Có phơi ra Internet không? CÓ.** `caddy/Caddyfile:191` chuyển
`/auth/v1/* /rest/v1/* /realtime/v1/*` sang gateway Supabase, gateway chuyển tiếp không
lọc (`docker/supabase/Caddyfile:29-31` → `rest:3000`, `:51-56` → `realtime:4000`);
staging cũng thế (`caddy/Caddyfile.staging:95-97`). Comment ở
`docker/supabase/Caddyfile:12-13` ("chưa bao giờ được phơi ra Internet") nay đã sai.
GoTrue tắt tự đăng ký (`docker-compose.supabase.yml:139`) → người lạ chỉ cầm khoá
`anon` công khai; muốn có token `authenticated` phải có tài khoản nhân viên thật —
**kể cả tài khoản ĐỐI TÁC (PARTNER) và TIVI (DISPLAY)**.

| Vai gọi | Đọc | Ghi | Căn cứ |
|---|---|---|---|
| `anon` (khoá công khai trong JS) | không bảng nào | không | init chỉ cấp mặc định cho `service_role` (`docker/supabase/init/01-vai-va-extension.sql:161-166`); thu EXECUTE hàm khỏi anon `20261019100000_harden_public_function_acl.sql:9`; có test `supabase/tests/public_function_acl.sql` |
| `authenticated` (mọi người đã đăng nhập) | **~40 bảng** (dưới) | không | ghi bị thu ở `20260804000016_no_client_write_policies.sql:36-44`, `20261001210000:89` |

Bảng `authenticated` ĐỌC được, lọc theo `current_clinic_ids()` = **mọi thành viên
phòng khám, bất kể vai** (`20260730000003_multi_tenant_foundation.sql:235-246`,
policy `20260730000004_tenant_scoped_rls.sql:149-171`): `patient`, `appointment`,
`visit`, `payment`, `prescription`, `lab_result`, `pregnancy`,
`patient_medical_profile`, `cskh_action`, `cskh_log`, `work_roster`, `care_episode`,
`drug_catalog`, `service_price`, `service_type`…; cộng `staff` (mọi cột,
`:182`), và các bảng cấp riêng: `patient_sdt_them`, `patient_link`, `payment_cycle`,
`payment_cycle_phan`, `payment_bill_line`, `payment_refund(_line)`,
`anh_chuyen_khoan`, `tep_ket_qua`, `capability_grant`, `quyen_preset`,
`clinic_membership`, `domain_event`, `tuong_tac_cskh`, `nhac_tai_kham`, `thong_bao`…
Riêng bảng lâm sàng (`clinical_record`, `ultrasound_record`, `consultation`…) có lọc
theo vai lâm sàng (`20260730000013_role_scoped_clinical_read.sql`). Đã thu, nay an
toàn: 11 bảng kho (`20261019120000_restrict_stock_postgrest_reads.sql`, có test),
`clinic_secret`, `idempotency_key`, `pos_outbox`.

Giao diện hiện **chỉ cần** `staff` và `clinic_membership`
(`app/(auth)/login/actions.ts:43,55`, `proxy.ts:141`, `lib/roster-names.ts:46`). Mọi
quyền đọc còn lại là bề mặt thừa — và nó đi VÒNG qua mọi luật của FastAPI
(capability, che CCCD, lọc thư ký theo bác sĩ).

**Giới hạn của phần này:** đọc từ migration, CHƯA chạy trên database. Prod từng sống
trên Supabase cloud (quyền mặc định ALL cho anon/authenticated) và bản sao lưu dùng
`--no-acl` (`scripts/backup-db.sh:243`), nên ACL thật trên prod có thể khác — xem C6.

### Phát hiện phần (c.2)

**C1 · CAO · Tài khoản ĐỐI TÁC (người ngoài phòng khám) và TIVI đọc được toàn bộ
khách, lịch hẹn, tiền, xét nghiệm, thai kỳ qua `/rest/v1`.**
- Ở đâu: policy SELECT của `patient`, `appointment`, `visit`, `payment`,
  `prescription`, `lab_result`, `pregnancy`, `patient_medical_profile`
  (`20260730000004_tenant_scoped_rls.sql:149-171`) dùng `current_clinic_ids()` — hàm
  trả MỌI membership đang hoạt động, không xét vai
  (`20260730000003_multi_tenant_foundation.sql:235-246`). PARTNER/DISPLAY là
  `clinic_membership.role` (xem `20260930900000_mo_full_lego.sql:35`). Policy
  RESTRICTIVE duy nhất (`20260915000021_thu_ky_rls_theo_bac_si.sql`) chỉ chặn thư ký.
  Comment ở `20260916000007_vai_doi_tac.sql:69-77` khẳng định "PARTNER không nằm
  trong tập vai nào" — **sai** với bảng khách/lịch/tiền.
- Kịch bản: nhân viên lab đối tác đăng nhập màn Đối tác → DevTools → cookie
  `sb-…-auth-token` lấy `access_token` →
  `curl 'https://dr4women.io.vn/rest/v1/patient?select=full_name,phone_primary,national_id_number,date_of_birth' -H "apikey: <khoá anon>" -H "Authorization: Bearer <token>"`
  → dự kiến nhận TOÀN BỘ khách của phòng khám. Đổi `patient` thành `lab_result`,
  `pregnancy`, `payment` cũng đọc được. Tivi phòng chờ (tài khoản DISPLAY, máy đặt nơi
  công cộng) cũng có token như vậy.
- Độ chắc: **chắc theo code** (đã tự mở hàm + policy); chưa chạy trên DB.
- Test đề xuất (`supabase/tests/`): tạo staff có membership PARTNER và DISPLAY,
  `SET LOCAL ROLE authenticated` + `request.jwt.claims`, assert `count(*) = 0` trên
  `patient`, `appointment`, `payment`, `lab_result`, `visit`, `staff`.
- Hướng sửa: nhanh nhất là C3 (khoá PostgREST tổng). Nếu chưa làm được C3: thêm policy
  RESTRICTIVE "vai ∉ {PARTNER, DISPLAY}" cho mọi bảng có policy `current_clinic_ids()`.
  Mức 3 (migration + quyền) → kế hoạch cho Tuyền duyệt trước.

**C2 · CAO · Mọi nhân viên đọc được CCCD, SĐT, ngày sinh, số CCHN của đồng nghiệp,
và CCCD khách KHÔNG che** —
`staff` có SELECT toàn bảng cho `authenticated` (vòng lặp
`20260730000008_table_grants.sql:48-59`, policy `20260730000004:182`); comment
`20260806000005_ho_so_nhan_su_day_du.sql:49-52` nói CCCD "chỉ Quản lý và Trưởng ca
đọc được — `_STAFF_MANAGEMENT_GUARD` là đường duy nhất" — sai, PostgREST là đường thứ
hai. `patient.national_id_number` được API che (`src/clinicai/schemas/patient.py`)
nhưng PostgREST trả nguyên số.
- Kịch bản: lễ tân lấy token như C1 →
  `curl '…/rest/v1/staff?select=full_name,national_id_number,phone,date_of_birth,license_number'`
  → thấy CCCD mọi đồng nghiệp.
- Độ chắc: chắc theo code; không migration nào thu quyền cột trên `staff`/`patient`.
- Test: `has_column_privilege('authenticated','public.staff','national_id_number','SELECT')`
  phải `false`; tương tự `patient`.
- Hướng sửa: `REVOKE SELECT ON staff, patient FROM authenticated`; nếu đăng nhập còn
  cần thì chỉ `GRANT SELECT (id, auth_user_id, full_name, is_active, primary_department)
  ON staff`.

**C3 · VỪA · Quyền đọc PostgREST cấp theo kiểu "có policy là có quyền", rộng hơn hẳn
nhu cầu** — `20260730000008_table_grants.sql:48-59` + ~70 GRANT tay. **Chưa có
migration "khoá PostgREST tổng"** — chỉ khoá lẻ từng bảng (kho, `clinic_secret`…).
- Kịch bản: thu ngân `curl '…/rest/v1/capability_grant?select=*'` hoặc
  `…/rest/v1/payment_cycle?select=*` → đọc bảng phân quyền và sổ thu, không cần lego.
- Độ chắc: chắc.
- Test: pytest đọc `information_schema.role_table_grants WHERE grantee IN
  ('anon','authenticated')` so với danh sách cho phép cố định (chỉ `staff` vài cột,
  `clinic_membership`).
- Hướng sửa: một migration `REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon,
  authenticated` + `ALTER DEFAULT PRIVILEGES … REVOKE`, rồi GRANT lại đúng cột đăng
  nhập cần. Tốt hơn nữa: chuyển hai chỗ đọc `staff`/`clinic_membership` của giao diện
  sang FastAPI rồi chặn hẳn `/rest/v1` ở Caddy. Giải luôn C1, C2, C4.

**C4 · VỪA (đã biết — P1 kiểm toán 19/10, chưa sửa trên `main`) · View
`v_quyen_hieu_luc` vượt RLS, đọc chéo phòng khám** —
`20260923000003_capability.sql:175-188`, không `security_invoker`, có GRANT cho
`authenticated`. Một phòng khám hôm nay → tác động nhỏ. Nghi thêm: `v_quyen_thuc_te`
(`20260929000001:168,229`) có thể lỗi `permission denied` với `authenticated` vì hàm
`quyen_theo_lich_bang()` đã bị thu EXECUTE (chưa chạy, suy luận). Sửa:
`ALTER VIEW … SET (security_invoker = true)`. Test: mọi view có grant cho
`authenticated` phải có `reloptions @> '{security_invoker=true}'`.

**C5 · THẤP–VỪA · Realtime vẫn chạy và mở ra ngoài dù không còn dùng** — Caddy
`/realtime/v1`; publication còn `appointment`, `visit`, `payment`, `lab_result`,
`prescription`… (`20260803000004:92-106`). App đã thôi dùng Realtime từ 27/09.
`postgres_changes` theo RLS nên PARTNER/DISPLAY nhận được thay đổi trực tiếp (cùng lỗ
C1). Độ chắc: nghi (chưa thử). Sửa: bỏ `/realtime/v1` khỏi Caddy, dừng dịch vụ
`realtime`, gỡ bảng khỏi publication.

**C6 · THẤP · Chưa biết ACL thật trên prod** — bản sao lưu `--no-acl`
(`scripts/backup-db.sh:243`). Việc Tuyền làm (chỉ đọc):
`SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants WHERE grantee IN ('anon','authenticated') ORDER BY 1,2;`
trên prod, gửi kết quả để chốt C1–C3.

---

## Phần (d) — Lộ trình gỡ, xếp theo rủi ro

Nguyên tắc xếp: **chặn đường lộ dữ liệu / leo thang trước, gom luật ra khỏi giao diện
sau.** Giao diện hiện KHÔNG tự quyết tiền (máy chủ tính lại), nên việc gom TSX là nợ
kiến trúc, không phải cháy nhà. Lỗ thật nằm ở PostgREST và chuỗi lịch trực.

| Đợt | Việc | Phát hiện | Mức việc (CLAUDE.md) | Vì sao xếp ở đây |
|---|---|---|---|---|
| **0 — ngay** | Tuyền chạy truy vấn chỉ đọc ACL trên prod (C6) để chốt quy mô C1-C3 | C6 | 0 | Rẻ, quyết định độ khẩn của đợt 1 |
| **1 — khẩn** | Khoá PostgREST tổng: `REVOKE ALL … FROM anon, authenticated`, chỉ GRANT lại cột `staff`/`clinic_membership` đăng nhập cần; tắt `/realtime/v1` | C1, C2, C3, C4, C5 | 3 (migration + quyền) | Lộ dữ liệu khách cho đối tác/tivi; một migration giải năm lỗ |
| **1 — khẩn** | `head_money_grant` vẫn đòi capability; báo cáo đòi `report.view`; cấm tự xếp mình vào DIEU_PHOI / ngày quá khứ | C7 | 3 (tiền + quyền) | Vượt lego thu tiền / hoàn tiền |
| **1** | `console/feedback` kiểm phiên trước khi ghi đĩa | B1 | 2 | Người lạ làm đầy ổ VPS |
| **2** | Tắt hết lego ⇒ không còn vai (`frozenset()`); đổi đặc quyền "chỉ hỏi MANAGEMENT" sang capability; chặn `staff.manage` nâng vai | C8, C9, C10 | 3 | Quyền theo TÀI KHOẢN đúng nghĩa — đúng mục tiêu 21 lego |
| **2** | `v_quyen_thuc_te` chỉ tính ca APPROVED (+ giờ ca); đối tác chỉ thấy việc của mình; cửa quyền cho `thu_ky` hồ sơ khách | C12, C11, C13 | 3 / 2 | |
| **2** | Quyết nghiệp vụ rồi làm: quyền giảm giá riêng; `account.manage` không đụng tài khoản có nhiều quyền hơn mình | B2, B3 | 3 | Cần Tuyền quyết trước |
| **3** | Xoá 5 route Next đã tắt → "route Next chạm DB" = **0** | B4 | 1 | Rẻ, đóng hẳn con số CLAUDE.md theo dõi |
| **3** | Merge PR #513 (bánh cóc ghi chéo); mở lệnh của Tiếp đón cho `visit`, gỡ dần 17 `VI_PHAM` | A1 | 2 | Lego thật cho nhiều phòng khám |
| **3** | Test "hai phòng khám" (GET `/{id}` chéo → 404) trước khi có phòng khám thứ hai | A3 | 1 (chỉ test) | Lưới an toàn duy nhất cho cách ly phòng khám |
| **4** | Gom ~25 chỗ hỏi vai thuần trong TSX: (1) `patients/new` + `NewPatientForm` (luồng tiếp nhận) → backend trả "luồng được phép"; (2) `tasks/page`, `layout`, `home` → `roleLanding` do backend trả; (3) nhánh `quyen === null` ⇒ ẩn nút hành động; (4) bỏ phép tính xem trước chép tay (`GiamGia`, `ChiaHinhThuc`) — dùng số máy chủ trả | B5, B6, B7, B8 | 2 mỗi nhóm | Nợ kiến trúc, máy chủ đã chặn |
| **4** | Dời luật giờ ca / display-settings từ `routers/config.py` sang `clinic_settings_service`; mở rộng bài quét ghi chéo sang hàm SQL | A2, A4 | 1-2 | |

Ước: đợt 0-1 ≈ 2-3 PR (một Mức 3 có kế hoạch duyệt trước); đợt 2 ≈ 3-4 PR; đợt 3-4
gom theo nhóm, mỗi nhóm một PR nhỏ < 400 dòng.

## Việc Tuyền làm

1. Chạy trên prod (chỉ đọc), gửi lại kết quả:
   `SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants WHERE grantee IN ('anon','authenticated') ORDER BY 1,2;`
2. Trả lời ba câu nghiệp vụ: (B2) giảm giá có cần quyền riêng / trần %? (B3) người giữ
   lego Tài khoản có được đặt lại mật khẩu Quản lý? (C11) hiện có mấy tài khoản đối tác,
   mỗi đối tác có nên chỉ thấy việc của mình?
3. Duyệt kế hoạch Mức 3 cho đợt 1 (khoá PostgREST + vá C7) trước khi giao code.
