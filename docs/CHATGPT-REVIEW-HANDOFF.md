# ClinicAI — bàn giao cho external code review

```text
REVIEW_SOURCE_SHA=c187fea2e87da01f3c3732cd7c780ec0c2437606
PROD_SHA=c187fea2e87da01f3c3732cd7c780ec0c2437606   (prod đang chạy đúng SHA này từ 18/09/2026 17:30 +07)
CREATED_AT=2026-09-19T10:40+07:00
main branch=main
latest migration=supabase/migrations/20260918000003_thai_ky_bac_si_xac_nhan.sql   (165 file; prod đã áp đủ 165)
latest merged PR=#168 "Batch hoàn thiện pilot…" (merge commit c187fea)
open PR (CHƯA merge, KHÔNG có trong main)=#169 nhánh claude/fix-ky-khoa-kham-xong (head 49ce1a6)
```

Đọc repo private `Avalook/Clinic-AI-MacMini` tại **đúng** `REVIEW_SOURCE_SHA` (= `main` lúc viết; nếu `main` đã tiến thì checkout SHA này). Tài liệu này nằm trên nhánh `claude/chatgpt-review-handoff` — chỉ thêm 3 file trong `docs/`, không đổi mã.

---

## A. Baseline & những gì đã biết là sai ở baseline

- Prod = `c187fea`. Có một lỗi prod đã tái hiện bằng test, bản sửa nằm ở PR #169 (chưa merge):
  **ký bệnh án (`visit.status=FINALIZED`) làm kẹt luồng** — "Khám xong" ở phiên đọc kết quả trả `VISIT_CLOSED` → `appointment` không lên `COMPLETED` → thu ngân bị chặn vĩnh viễn; Bàn khám mất sinh hiệu/chỉ định của lượt đã ký (`bang`, `cho_quyet` lọc `status IN ('OPEN','IN_PROGRESS')`). Xem diff của PR #169.
- Tài liệu vận hành trong `docs/` (DANG-LAM, RUNBOOK…) viết theo từng giai đoạn; khi mâu thuẫn với mã thì **mã thắng**. `CLAUDE.md` mục "Hai môi trường/staging :8080" đã lỗi thời (VPS hiện chỉ có prod).

## B. Cách chạy (không có mật khẩu)

| Phần | Entrypoint |
|---|---|
| Backend | FastAPI `src/clinicai/main.py` (`uvicorn clinicai.main:app`); mọi router mount dưới `/api/v1`. Python 3.12, `poetry install`. |
| Frontend | Next.js (bản có breaking changes — xem `src/dashboard/AGENTS.md`) ở `src/dashboard`; `npm ci && npx next build && npx next start`. Frontend gọi FastAPI qua proxy `src/dashboard/app/api/**/route.ts`. |
| Database | Postgres + Supabase tự dựng (GoTrue/PostgREST/Realtime). Lược đồ = `supabase/migrations/*.sql` theo thứ tự tên file. Áp: `scripts/apply-pending-migrations.sh` (mỗi migration + dòng ghi sổ trong 1 giao dịch). |
| Local đủ stack | `scripts/dev-up.sh` (web :3100, API :8100, Supabase local). |
| Test backend | `scripts/tests/dung-db-kiem.sh` (DB thử :55433) rồi `pytest src/tests -m "not integration" --ignore=src/tests/integration` (≈2170 test; `DATABASE_URL_TEST` bật test DB). |
| Test frontend | trong `src/dashboard`: `tsc --noEmit`, `npm run lint`, `npm run test:boundary` (+ `test:audit test:ops test:roster test:luu-nhap test:khung test:gio-ca test:bo-nho test:nhip`). |
| CI | `.github/workflows/ci.yml`: ruff, mypy, tenant-scope audit, pytest+coverage ≥80%, migration áp 2 lần + `supabase/tests/*.sql`, tsc/eslint/next build. |

## C. Sơ đồ thư mục

```text
src/clinicai/
  main.py                     FastAPI app, mount router, middleware
  api/identity.py             StaffIdentity, ClinicRole, vai theo vị trí trực (VAI_THEO_VI_TRI), dung_vai(), RoleGuard
  api/v1/routers/*.py         router MỎNG (không luật nghiệp vụ)
  services/*.py               luật nghiệp vụ (Python thuần + asyncpg)
    luot_kham_service.py      ★ lõi rail mới: bảng/hàng chờ, check-in, sinh hiệu, phiên khám, chỉ định, xếp phòng,
                                thực hiện, vòng đọc kết quả, yêu cầu/quyết định, duyệt kết quả, đối tác
    luot_kham_rules.py        luật thuần: need mặc định, kế hoạch vòng đọc
    checkout_service.py       đối soát + đóng lượt ở quầy
    payment_service.py        thu tiền (khoá lịch hẹn, idempotency)
    cashier_board_service.py  bảng thu ngân (đọc service_order + giá)
    pharmacy_service.py       nhà thuốc: nhận/cấp/từ chối/điều chỉnh tồn
    tep_ket_qua_service.py    tệp kết quả (upload, cho phép gửi, CSKH đọc)
    clinical_sign_service.py  ký / phát hành / sửa bệnh án (FINALIZED/AMENDED)
    clinical_form_service.py  phiếu chuyên khoa (form_data JSONB)
    thai_ky_service.py        thai kỳ (bảng pregnancy)
    xem_luot_service.py       viewer chỉ đọc 1 lượt, cắt theo vai
    booking_service.py        đặt lịch + chuyển trạng thái lịch hẹn (check-in qua đây)
    cskh_service.py, man_khach_hang_service.py, tuong_tac_cskh_service.py, recall_*   CSKH
    dispatch_service.py       điều phối trưởng ca, check-out list, thông báo
    work_item_service.py, service_log_service.py, lab_order_service.py   ← RAIL CŨ (mục J)
  core/                       clock (Asia/Ho_Chi_Minh), shifts, exceptions
src/dashboard/
  app/(dashboard)/<route>/    màn hình (TSX, chỉ giao diện)
  app/(dashboard)/_lam-viec/  thành phần dùng chung: XemLuot, KhungTep, api.ts (docBang/guiThaoTac)
  app/api/**/route.ts         proxy tới FastAPI (10/81 route còn chạm DB trực tiếp — nợ, xem K)
  lib/roles.ts                NAV_ROLES: route → vai (chỉ là hiển thị; quyền thật ở backend)
  lib/form-schemas/{pk,sk,nt,nk,hmvs}.ts   schema 5 phiếu chuyên khoa
  components/ui/              kit giao diện (Button, StatusChip, ThanhTab…)
supabase/migrations/          lược đồ, RLS, trigger, view (165 file)
supabase/tests/*.sql          kiểm lược đồ chạy trong CI
src/tests/                    pytest (services/*_db.py = test DB thật)
docs/SITEMAP.md               màn chuẩn + mọi lối vào của từng chức năng
docs/SO-LUAT.md               luật kiến trúc (frontend không chứa luật, bất biến ép ở Postgres…)
docs/GIAI-THICH-CODE.md       giải thích mã từng file
```

## D. Canonical journey (rail mới)

| Bước | Route FE | Component | API (FastAPI) | Service | Bảng chính |
|---|---|---|---|---|---|
| Đặt lịch | `/appointments`, `/customers` | BookingHub, DatLichModal | `POST /appointments/bookings`, `GET /appointments/quote` | booking_service, capacity_service | appointment, work_roster, roster_week |
| Check-in | `/reception/queue` | QueueBoard | `POST /luot-kham/check-in` (→ BookingService.apply_action "checkin") | luot_kham_service.check_in, booking_service | appointment(CHECKED_IN), visit, encounter_flow, queue_entry, event_log |
| Sinh hiệu | `/do-sinh-hieu` | BangDoSinhHieu | `POST /luot-kham/visits/{id}/goi-do`, `/vitals` | goi_do_sinh_hieu, record_vitals | vital_measurement, encounter_flow |
| Bàn khám | `/ban-kham` | BanKham, ClinicalRecordForm, ServiceFormEngine, ClinicalSignPanel, ThaiKy | `GET /luot-kham/bang`, `/hang-cho`; `POST /luot-kham/hang-cho/{q}/goi`, `/consultations/{c}/start`, `/notes`, `/kham-xong` | luot_kham_service | consultation, clinical_record, clinical_form_response |
| ServiceOrder | `/ban-kham` (Chỉ định & kết quả) | ChiDinhPanel | `POST /consultations/{c}/draft-orders` (TKYK), `/authorize-orders` (BS) | propose_orders, authorize_orders | service_order (draft→authorized→assigned) |
| Trưởng ca | `/truong-ca` | ChiDinhHomNay, điều phối | `POST /luot-kham/orders/{o}/dispatch`, `GET /luot-kham/chi-dinh-hom-nay`, `/dispatch/*` | dispatch_order, chi_dinh_hom_nay | service_order.room_id, queue_entry |
| Phòng thực hiện | `/phong/[ma]` | PhongDichVu, KhungTep | `POST /luot-kham/orders/{o}/start`, `/complete` (performed / not_performed + lý do) | start_service, complete_service | service_order (in_progress→performed/not_performed) |
| Kết quả | `/doi-tac`, `/phong/[ma]` | BangDoiTac, KhungTep | `POST /doi-tac/ket-qua`, `/doi-tac/viec/{id}/*`, upload tệp | tep_ket_qua_service, sau_khi_co_ket_qua | tep_ket_qua, service_order.ket_qua_luc |
| Quay lại BS | `/ban-kham` ("Kết quả cần đọc", "Chờ bác sĩ quyết"), `/duyet-ket-qua` | BanKham, ChoBacSiQuyet, DuyetKetQua | `GET /luot-kham/cho-quyet`, `POST /yeu-cau/{r}/quyet`, `GET /ket-qua-cho-duyet`, `POST /orders/{o}/duyet-ket-qua` | _evaluate_rounds, quyet_yeu_cau, duyet_ket_qua | review_round, round_requirement, follow_up_case |
| Chẩn đoán/Plan/Rx + ký | `/ban-kham` | ClinicalRecordForm, ClinicalSignPanel | `POST /clinical-records`, `POST /clinical/{v}/sign`, `/release`, `/amend` | clinical_record_service, clinical_sign_service | clinical_record, prescription, visit.status (FINALIZED/AMENDED) |
| Khám xong | `/ban-kham` nút "Khám xong" | BanKham.HoSo | `POST /luot-kham/consultations/{c}/kham-xong` | kham_xong → complete_consultation → _ket_thuc_neu_xong | consultation, review_round, appointment(COMPLETED), encounter_flow.finished_at |
| Thu tiền | `/thu-ngan/dich-vu`, `/thu-ngan/thuoc` | TabThuNgan, QuayThuNgan, GiaoDich | `GET /cashier/board`, `/cashier/giao-dich`; `POST/DELETE /payments` | cashier_board_service, payment_service | payment, service_price |
| Nhà thuốc | `/pharmacy` | PharmacyBoard | `/pharmacy/*` | pharmacy_service | prescription, dispensing, inventory tables |
| Check-out | `/reception/checkout` | ChiTietLuot | `GET /reception/checkout`, `/chi-tiet/{v}`; `POST /reception/checkout` | checkout_service | visit.closed_at, work_item(LUOTKHAM-15), event_log |
| CSKH / theo dõi | `/customers` | CustomersView, VungLamViecKhach, TepKetQua | `/cskh/*` (ket-qua, tuong-tac, recall-jobs…) | cskh_service, man_khach_hang_service | v_viec_cskh (view), follow_up_case, tep_ket_qua, cskh_* |
| Xem lại lượt | nút "Xem lại cả lượt" ở mọi màn | _lam-viec/XemLuot, NutXemLuot | `GET /xem-luot/{visit_id}` | xem_luot_service (cắt theo vai) | đọc nhiều bảng + event_log |

## E. Vai và quyền

- **Identity:** 1 tài khoản GoTrue ↔ `staff.auth_user_id` ↔ `clinic_membership(role)`. `api/identity.py` dựng `StaffIdentity(role, vai_tai_khoan, clinic_id, staff_id…)`. Không gắn `auth_user_id` = đăng nhập được nhưng mọi ghi trả 403.
- **Capability:** các tập vai ở đầu `luot_kham_service.py`: `CHECKIN_ROLES` (Lễ tân, QL) · `VITALS_ROLES` · `CONSULT_ROLES`/`NOTE_ROLES` (BS, TKYK) · `DRAFT_ROLES` (TKYK — chỉ nháp chỉ định) · `DOCTOR_ROLES` (BS — duyệt chỉ định, quyết yêu cầu, thai kỳ) · `DISPATCH_ROLES` (Trưởng ca, QL) · `PERFORMER_ROLES` · `REVIEW_ROLES` (BS, BS siêu âm — duyệt kết quả) · `CLINICAL_READ_ROLES`. `lib/roles.ts` NAV_ROLES **chỉ** điều khiển thanh bên.
- **Assignment:** bác sĩ phụ trách = `visit.attending_doctor_id`; thư ký ↔ bác sĩ = `thu_ky_bac_si` (TKYK chỉ thấy lượt của bác sĩ mình; `MO_QUYEN_TAM_THOI` đang BẬT → TKYK thấy mọi bác sĩ); chỉ bác sĩ phụ trách quyết yêu cầu.
- **Acting context (đa vai):** vai hôm nay suy từ `work_roster` theo `VAI_THEO_VI_TRI` (vd T1_LETAN/T1_THUNGAN→RECEPTION, T1_DOCHISO→NURSE_ULTRASOUND). `RoleGuard` đổi vai khi vai tài khoản không đủ mà vai vị trí đủ; `dung_vai()` ở check-in. Audit ghi `clinic_role` (vai đang dùng) + `vai_tai_khoan` (vai gốc). `clinic.settings.vai_lich_theo_ca` (siết theo giờ ca) đang TẮT trên prod.

| Vai (ClinicRole) | Làm được (tóm tắt) |
|---|---|
| Lễ tân RECEPTION | check-in, check-out, thu tiền (quầy DV qua vai vị trí thu ngân), phòng lấy mẫu (theo NAV) |
| Điều dưỡng NURSE_ULTRASOUND | gọi/đo sinh hiệu, thực hiện dịch vụ ở phòng (lấy mẫu, thủ thuật) |
| Bác sĩ DOCTOR | khám, duyệt chỉ định, quyết yêu cầu (miễn/theo dõi), duyệt kết quả, ký/phát hành/sửa bệnh án, thai kỳ, thủ thuật |
| TKYK | nhập bệnh án nháp, nháp chỉ định, bắt đầu/kết thúc phiên đi kèm BS; KHÔNG ký, KHÔNG duyệt, KHÔNG quyết |
| Trưởng ca TRUONG_CA | xếp/đổi phòng từng chỉ định, điều phối, cảnh báo |
| Quản lý MANAGEMENT | cấu hình, lịch trực, xem hầu hết màn; KHÔNG duyệt kết quả (403) |
| BS siêu âm ULTRASOUND_DOCTOR | phòng siêu âm: làm, tải tệp, duyệt kết quả |
| Thủ thuật | không có vai riêng: người làm = vai được phép ở phòng `KN-THUTHUAT` (BS, ĐD, TKYK, QL theo NAV; backend PERFORMER_ROLES) |
| Thu ngân CASHIER / _DV / _THUOC | bảng thu, ghi/huỷ phiếu thu |
| Dược sĩ PHARMACIST | nhà thuốc: nhận hàng, cấp, từ chối, điều chỉnh |
| CSKH | màn khách hàng, gọi nhắc, tệp kết quả đã được cho phép gửi, ghi đã gửi |
| Đối tác PARTNER | chỉ `/doi-tac`: nhận mẫu, tải kết quả; không đọc bệnh án |
| DISPLAY | tivi phòng chờ, bị chặn mọi đường ghi |

## F. Source of truth

| Khái niệm | Bảng/model chuẩn | Trạng thái quan trọng | Ghi chính | Đọc chính |
|---|---|---|---|---|
| Patient | `patient` (+ `patient_summary`) | is_active, uu_tien | patient_service, mpi_service | mọi màn |
| Appointment | `appointment` | SCHEDULED/CONFIRMED/CHECKED_IN/COMPLETED/CANCELLED/NO_SHOW | booking_service, luot_kham_service._ket_thuc_neu_xong | payment_service (COMPLETED mới thu) |
| Visit/Encounter | `visit` + `encounter_flow` | visit.status OPEN/IN_PROGRESS/INCOMPLETE/FINALIZED/AMENDED (FINALIZED = khoá hồ sơ, trigger `visit_finalized_block_update`); `closed_at` = đóng lượt; encounter_flow.vitals_status/finished_at | luot_kham_service, checkout_service, clinical_sign_service | mọi màn |
| Vitals | `vital_measurement` | — | record_vitals | Bàn khám (chỉ xem), XemLuot |
| Clinical record | `clinical_record` (+ prescription) | revision, draft/signed | clinical_record_service, clinical_sign_service | Bàn khám, XemLuot |
| Forms chuyên khoa | `clinical_form_response` (service_code = MÃ FORM PK/SK/NT/NK/HMVS) | form_data JSONB | clinical_form_service | ServiceFormEngine, sign gate |
| Pregnancy | `pregnancy` | outcome ONGOING/…; edd_nguon | thai_ky_service (chỉ BS) | ThaiKy, XemLuot |
| ServiceOrder | `service_order` | exec_status draft/authorized/assigned/in_progress/performed/not_performed/cancelled; ket_qua_luc; duyet_luc | luot_kham_service | Trưởng ca, phòng, thu ngân, checkout, CSKH view |
| ReviewRound | `review_round` + `round_requirement` | round collecting/ready/in_review/closed; requirement need PERFORMED/VALID_RESULT, status open/satisfied/waived/follow_up | _evaluate_rounds, quyet_yeu_cau | Bàn khám, checkout |
| Consultation | `consultation` | kind PRIMARY/REVIEW, status queued/in_progress/completed | luot_kham_service | Bàn khám |
| Result/File | `tep_ket_qua` | cho_phep_gui_luc (duyệt THEO TỪNG TỆP), gui_luc | tep_ket_qua_service, duyet_ket_qua | CSKH, checkout, XemLuot |
| FollowUp | `follow_up_case` | OPEN/DONE/CANCELLED; service_order_id, visit_id | quyet_yeu_cau(FOLLOW_UP), duyet_ket_qua | CSKH (v_viec_cskh), checkout |
| Prescription | `prescription` (+ draft rows) | released | clinical_prescription_service | nhà thuốc, thu ngân thuốc |
| Payment | `payment` | PAID/VOIDED (+ void_reason), kind dịch vụ/thuốc | payment_service | thu ngân, checkout |
| Inventory | bảng kho nhà thuốc (xem migration `20260802000001_pharmacy_inventory.sql`) | — | pharmacy_service | nhà thuốc |
| QueueEntry | `queue_entry` | waiting/called/serving/done/blocked | luot_kham_service | hàng chờ phòng/BS |
| WorkItem | `work_item` (+ `work_item_event`) | RAIL CŨ — xem J | booking/checkout/work_item_service | checkout (lượt không có consultation), vài màn cũ |
| Staff/Roster | `staff`, `clinic_membership`, `work_roster`, `roster_week`, `thu_ky_bac_si` | roster APPROVED/PENDING/REJECTED | config_service (QL) | identity, capacity, booking |
| Audit/Event | `event_log` (metadata.clinic_role, vai_tai_khoan, clinic_staff_id) | — | `record_event` / audit.py | XemLuot, checkout timeline, audit-log |

## G. 5 phiếu chuyên khoa

Route: `/ban-kham` → `ServiceFormEngine` (theo `service_code` = mã form) + `ClinicalRecordForm` + `ClinicalSignPanel`. Schema: `src/dashboard/lib/form-schemas/{pk,sk,nt,nk,hmvs}.ts`. API: `GET/PUT /clinical-forms`. Ký: `clinical_sign_service` (gate "còn thiếu", khoá sau ký).

| Form | Đã làm (semantics) |
|---|---|
| PK Phụ khoa | Khám ngoài/Khám trong đúng nhãn (key giữ nguyên); lưu → tải lại → ký → chỉ đọc |
| SK Sản khoa | + Thai kỳ trên bảng `pregnancy` sẵn có: CHỈ BS tạo/sửa/kết cục, dự kiến sinh bắt buộc nguồn (`edd_nguon`), tuổi thai tính từ EDD; unique 1 thai kỳ ONGOING/khách (index có điều kiện) |
| NT Nội tiết | MHT tách nghĩa: yếu tố chỉ định / chống chỉ định / thận trọng (textarea, dữ kiện) ≠ `mht_quyet_dinh`; KHÔNG hard-code guideline; hướng xử trí NT được tính là "kế hoạch" khi ký |
| NK Nam khoa | ký bị chặn khi thiếu lý do; tinh dịch đồ chỉ hiện tham chiếu WHO, KHÔNG chặn cứng |
| HMVS | "đang đánh giá" phải có hướng xử trí mới ký được (đã bịt đường lách) |
Chung: sinh hiệu trong phiếu CHỈ XEM (nguồn = màn Đo sinh hiệu), không nhập trùng.

## H. Service matrix (theo mã hiện có — không bổ sung luật chuyên môn)

Giá/mã: `service_price` (service_code, node_code). Phòng: `clinic_room.node_code` + `clinic_room_node`. Mức cần mặc định: `luot_kham_rules.need_mac_dinh` = `VALID_RESULT` nếu `node_definition.lam_ben_ngoai` hoặc `flow_group='ket_qua'`, ngược lại `PERFORMED`; BS đổi được từng chỉ định khi "Khám xong" (`ke_hoach`).

| Nhóm (node) | Dịch vụ (mã CLS_*) | Phòng (prod seed) | Need mặc định | Người làm | Tệp/kết quả | BS duyệt |
|---|---|---|---|---|---|---|
| DICHVU-SIEUAM | 16 loại siêu âm | KN-SA-T1 "Phòng siêu âm 1", KN-SA1 "Phòng siêu âm **2**", KN-SA2 "Phòng siêu âm 3" | PERFORMED | BS siêu âm (+ĐD, TKYK, QL theo NAV) | ghi kết luận + tệp | có (REVIEW_ROLES) |
| DICHVU-LAYMAU-MAU | XN máu, nội tiết nam, NST đồ, CFTR, Y-microdeletion | KN-LAYMAU, KN-DOITAC (la_doi_tac) | VALID_RESULT | ĐD lấy mẫu → đối tác | đối tác tải tệp | có |
| DICHVU-LAYMAU-NUOCTIEU | Nước tiểu, NT sau xuất tinh | KN-LAYMAU, KN-DOITAC | VALID_RESULT | như trên | như trên | có |
| DICHVU-LAYMAU-AMDAO | XN dịch âm đạo | KN-THUTHUAT, KN-DOITAC | VALID_RESULT | | | có |
| DICHVU-SANGLOC-COTUCUNG | Soi cổ tử cung | KN-THUTHUAT, KN-DOITAC | VALID_RESULT | | | có |
| DICHVU-HINHANH-NGOAI | Chụp vú ép, MRI vú, chụp TC-vòi trứng | KN-DOITAC | VALID_RESULT | ngoài | tệp | có |
| DICHVU-THUTHUAT | Biofeedback CB/NC, cấy/tháo que, đặt/tháo vòng, monitoring | KN-THUTHUAT, KN-TTNG, KN-SANCHAU, KN-SAN-BIO | PERFORMED | BS/ĐD tại phòng | ghi thực hiện + tệp tuỳ chọn | theo dõi thủ thuật riêng |
| DICHVU-DXA | Đo mật độ xương | **prod: chưa có phòng** (local demo gán KN-DOCHISO) | PERFORMED | ? | | |
| DICHVU-TINHDICHDO | Tinh dịch đồ, DFI | **prod: chưa có phòng** (local demo gán KN-LAYMAU) | VALID_RESULT (flow_group ket_qua) | ? | | |
HOLD: phòng thật cho DXA / Tinh dịch đồ; "Soi cổ tử cung" đang thuộc nhóm sàng lọc CTC; bảng giá prod có thể còn trống.

## I. File lifecycle (mã thật)

```text
upload        tep_ket_qua_service.tai_len (service_order_id bắt buộc khớp khách; loại ANH/VIDEO/PDF/TAI_LIEU; sha256)
              → sau_khi_co_ket_qua: đặt service_order.ket_qua_luc, requirement VALID_RESULT → satisfied, review_round → ready
version       KHÔNG có bảng version: mỗi lần tải là một dòng tep_ket_qua mới (bản điều chỉnh = dòng mới)
doctor review luot_kham_service.duyet_ket_qua (REVIEW_ROLES): đặt service_order.duyet_luc/bac_si_danh_gia
approval      UPDATE tep_ket_qua SET cho_phep_gui_luc … WHERE service_order_id=… AND cho_phep_gui_luc IS NULL
              → chỉ các tệp đang có; tệp tải SAU không thừa hưởng (cho_phep_gui_luc NULL)
              ket_qua_cho_duyet: chỉ định có duyet_luc NHƯNG còn tệp cho_phep_gui_luc NULL → quay lại hàng duyệt
                (cờ duyet_lan_truoc + da_cho_gui từng tệp); duyệt lần sau chỉ mở tệp mới, giữ đánh giá cũ
CSKH          GET /cskh/ket-qua/{patient}, /cskh/ket-qua/tep/{id}/noi-dung (xem/tải — HIỆN KHÔNG chặn tệp chưa duyệt),
              POST /cskh/ket-qua/tep/{id}/da-gui (chặn nếu chưa cho_phep_gui — backend + DB)
sent log      tep_ket_qua.gui_luc/gui_kenh/gui_boi_staff_id + event_log
BS siêu âm    tệp do BS siêu âm tải được cho phép gửi ngay (self-approve) — HOLD
```

## J. Rail cũ còn tồn tại

| Rail | Còn GHI ở | Còn ĐỌC ở | Vai trò hiện tại |
|---|---|---|---|
| `work_item` (+event) | booking_service (tạo kế hoạch bước lúc check-in), checkout_service (bước đóng lượt LUOTKHAM-15), service_order_service, ultrasound_board_service, work_item_service | checkout (lượt không có consultation), dispatch_service, theo_doi_thu_thuat_service, thu_ky_bac_si, man_khach_hang, man_trang_chu, console, gate_rule, audit_log, clinical_sign_service | kế hoạch bước đời cũ + đóng lượt; rail mới KHÔNG dựa vào nó cho kết quả/đọc lại/theo dõi (Slice 1) |
| `service_log` | service_log_service (`/service-log`, `/sono/queue`) | service_log_service | nhật ký dịch vụ đời cũ; thu ngân đã bỏ đọc |
| `lab_result` | lab_order_service, lab_safety_service (`/orders`, `/results/*`, `/triage`) | doctor_board, display_board, patient_context, ho_so_kham, tep_ket_qua_service, queue router, graph lab_triage | kết quả XN đời cũ + triage AI; rail mới dùng service_order + tep_ket_qua |
| legacy endpoints | `/work-items*`, `/visits/{id}/service-orders*` (work_items router), `/ultrasound/queue*`, `/results/*` | | còn mount; màn cũ đã chuyển hướng (SITEMAP mục "đã chuyển hướng") |
| Dashboard chạm DB trực tiếp | 10/81 `app/api/**/route.ts`: patients/check-phone, clinical-record, appointments, appointments/service-history, roster, wards, catalog, admin/users, clinical-form, brief/[id] | | nợ "đưa luật ra khỏi dashboard" |

## K. HOLD / debt (nguyên trạng — không tự giải quyết)

1. **Thời điểm trừ kho** nhà thuốc — chưa chốt.
2. **Thu tiền trước hay sau khi BS đọc kết quả**: bảng thu ngân hiện khách khi PRIMARY xong; `payment_service` chỉ cho thu khi `appointment=COMPLETED` → UI cho bấm mà server từ chối.
3. **CSKH xem được nội dung tệp chưa duyệt** (không gửi được).
4. **BS siêu âm tự cho phép gửi** tệp của mình.
5. **MHT**: danh mục chống chỉ định cần nguồn Dr4Women.
6. **NK**: có chặn cứng theo WHO hay không.
7. **CoupleCase / TreatmentCycle**: chưa dựng.
8. **Sửa bệnh án sau ký**: có `/clinical/{v}/amend` (FINALIZED→AMENDED) nhưng luồng sửa phiếu chuyên khoa sau ký chưa hoàn chỉnh.
9. **DXA / Tinh dịch đồ**: prod chưa có phòng.
10. **Ký bệnh án khoá luồng khám** (mục A) — sửa ở PR #169.
11. **Lấy mẫu có ghi chú được tính "có kết quả"**: `complete_service` với `result_note` đặt `ket_qua_luc` kể cả dịch vụ cần VALID_RESULT (quan sát prod 18/09) — nghi vấn.
12. `.ops-status/production` chủ root → `deploy-backend.sh` thoát 1 sau khi đã healthy.
13. Quyền lệch: NAV cho QL mở `/duyet-ket-qua` nhưng API chỉ BS (câu báo tiếng Anh).
14. Tên phòng lệch mã (`KN-SA1` = "Phòng siêu âm 2").
15. `MO_QUYEN_TAM_THOI` đang BẬT (TKYK thấy mọi bác sĩ) — cố ý tạm thời.

## Lưu ý bảo mật khi review

Repo private này CÓ chứa tài liệu vận hành nhạy cảm (danh sách tài khoản nhân sự và mật khẩu chung trong `docs/TAI-KHOAN-FINAL-CLOUD.md`, `docs/DANG-LAM.md`, `docs/HUONG-DAN-THAO-TAC-THU.md`, một số `scripts/tao-tai-khoan-*.py`, fixture `supabase/fixtures/clinic_roster.sql`…; IP/alias máy chủ trong tài liệu vận hành). **Không trích dẫn mật khẩu / IP / tên đăng nhập trong kết quả review.** Việc đổi mật khẩu chung của nhân sự trên prod là việc của chủ dự án, ghi ở đây như một phát hiện (security debt), không phải việc của reviewer.
