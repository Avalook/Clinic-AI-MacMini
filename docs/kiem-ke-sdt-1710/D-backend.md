# Vùng D — BACKEND (src/clinicai/**): nơi backend tự ghép/trả tên bệnh nhân

Kiểm kê CHỈ ĐỌC, worktree `invoice-by-company-8a73f2` (HEAD 25140241). Mục tiêu: hiện SĐT (`patient.phone_primary`) cạnh tên khách.
Số dòng là dòng chứa `p.full_name` (SQL) hoặc dòng ghép chuỗi, đọc trên nhánh này — có thể trượt vài dòng.

Quy ước cột:
- **JOIN/phone**: "JOIN, CÓ phone" = đã JOIN patient và SELECT/trả `phone_primary` rồi (backend không phải sửa, chỉ giao diện). "JOIN, thiếu" = đã JOIN patient, chỉ thêm cột. "Không JOIN" = phải thêm JOIN.
- **Nóng**: có / ấm / lạnh. Căn cứ: mỗi lượt ghi dựng lại 7–10 trang mọi tab (memory `do-tai-prod-1710`, 14/10: ~14–18 req/s cao điểm; `/api/luot-kham` 3.557 lần/30 phút). Thêm 1 cột `p.phone_primary` vào truy vấn ĐÃ JOIN patient ≈ 0 chi phí (cùng dòng heap, không thêm JOIN, vài byte/dòng) — chỉ đáng lo khi phải THÊM JOIN hoặc thêm truy vấn riêng.
- **Ngoài đọc**: TV phòng chờ / Telegram / Zalo / MISA-kế toán / bản in cho khách / log.

## A. API trả danh sách / bảng cho nhân viên (JSON)

| # | Nơi (file:dòng / hàm) | Loại | JOIN patient? phone? | Cần thêm gì | Nóng? | Ngoài đọc? | Rủi ro |
|---|---|---|---|---|---|---|---|
| 1 | `api/v1/routers/queue.py:37` `_APPT_SQL`, trả ở `:147` (`GET /queue`) | API list (hàng chờ lễ tân) | JOIN, thiếu | `p.phone_primary AS patient_phone` + key `patient.phone_primary` | Có (nóng nhất) | Không | Thấp; SQL nằm trong router (không mỏng) |
| 2 | `services/luot_kham_doc.py:101` `BangLuotKham.bang` (key `"ten"` `:357`) | API list (bảng làm việc Đo sinh hiệu/Bàn khám) | JOIN, thiếu | thêm `p.phone_primary`, key `sdt` cạnh `ten` | Có | Không | Thấp |
| 3 | `luot_kham_doc.py:332` cùng `bang` (lịch chờ check-in, `:593`) | API list | JOIN, thiếu | như #2 | Có | Không | Thấp |
| 4 | `luot_kham_doc.py:883` `hang_cho` (hàng bác sĩ, `:1140`) + `:1038` "sắp tới" (`:1223`) | API list | JOIN, thiếu | như #2 (2 truy vấn) | Có | Không | Thấp |
| 5 | `luot_kham_doc.py:1267` `chi_dinh_hom_nay` (`:1354`, LIMIT $2) | API list | JOIN, thiếu | như #2 | Có | Không | Thấp |
| 6 | `luot_kham_doc.py:1395` `ket_qua_cho_duyet` (`:1481`, LIMIT 200) | API list | JOIN, thiếu | như #2 | Có | Không | Thấp |
| 7 | `services/work_item_service.py:382` `list_for_visit` (`:450`), `:510` `list_worklist` (`:647`) | API list | JOIN, CÓ phone (`phone_primary`) | không (chỉ giao diện) | Có | Không | — |
| 8 | `api/v1/routers/lab.py:153` `ket_qua_cho_duyet` (LIMIT 100) | API list | JOIN, CÓ phone (`patient.phone_primary`) | không | Ấm | Không | — |
| 9 | `services/doctor_board_service.py:126` (`:250`) | API list (bảng bác sĩ) | JOIN, CÓ phone | không | Có | Không | — |
| 10 | `services/week_appointments_service.py:201` (`:431`) | API list (lịch tuần) | JOIN, CÓ phone | không | Ấm | Không | — |
| 11 | `services/man_dat_lich_doc.py:75` + `:168` `hub_dat_lich` (LIMIT 200 / $6) | API list (đặt lịch, tìm khách) | JOIN, CÓ phone | không | Ấm | Không | — |
| 12 | `api/v1/routers/booking.py:264`, `:346` `cho_xep_bac_si` (LIMIT 500) | API list | JOIN, CÓ phone | không | Ấm | Không | SQL trong router |
| 13 | `services/tiep_don_service.py:226` `trang_thai` (`sdt` `:321`) | API list (tiếp đón) | JOIN, CÓ phone | không | Có | Không | — |
| 14 | `services/cashier_board_service.py:155` (`phone` `:1141`) | API list (bảng thu ngân) | JOIN, CÓ phone | không | Có | Không | — |
| 15 | `cashier_board_service.py:486` `giao_dich` (LIMIT 1000) | API list (giao dịch) | JOIN, thiếu | `p.phone_primary` | Ấm | Không | Thấp |
| 16 | `services/checkout_service.py:82` (`_READINESS_SQL`; `pending_list` LIMIT 300 `:421`, `stale_list` LIMIT 300 `:700`; `chi_tiet`) — key `patient_name` `:384/:437/:585/:711` | API list (check-out) | JOIN, thiếu | thêm `p.phone_primary` vào `_READINESS_SQL` + 4 chỗ dựng dict | Có | Không | Thấp; 1 SQL dùng chung 4 hàm → sửa 1 chỗ |
| 17 | `services/quay_thu_service.py:886` `_KHACH_SQL` (sổ thu `lich_su`, key `ten`/`ma_bn`) | API list | Không JOIN trực tiếp ở đây: `LEFT JOIN patient`, thiếu phone | `p.phone_primary AS sdt` | Ấm | Có — dùng chung cho file xuất (mục E) | Thấp |
| 18 | `services/danh_sach_hoa_don_service.py:58` `quay_cua_no` (CÓ `so_dien_thoai`); `:138`, `:150`, `:164` không phone | API list (hoá đơn / quầy cửa nợ) | JOIN; `:58` CÓ, 3 truy vấn còn lại thiếu | thêm `p.phone_primary` vào `:138/:150/:164` | Ấm | `:58` đi vào MISA (đã có SĐT) | Thấp |
| 19 | `services/ban_thuoc_service.py:215` `man_nha_thuoc` (LIMIT 300; `phone` `:507`), `:429` bán lẻ (LIMIT 100; `:584`) | API list (nhà thuốc) | JOIN, CÓ phone | không | Có | Không | — |
| 20 | `services/pharmacy_service.py:126` `hang_doi` (LIMIT 300, key `patient_name`) | API list | JOIN, thiếu | `p.phone_primary` | Có | Không | Thấp; trả `dict(r)` → cột thêm tự lên |
| 21 | `pharmacy_service.py:176` `lich_su_giao` (LIMIT 200), `:212` `cho_tu_van` (LIMIT 100) | API list | JOIN, CÓ phone (trả `dict(r)` thẳng) | không | Ấm | Không | — |
| 22 | `pharmacy_service.py:886` `cho_gan_lo` (`khach` `:942`) | API list | JOIN, thiếu | `pt.phone_primary` | Ấm | Không | Thấp |
| 23 | `services/ban_le_service.py:93` `tim_khach` (CÓ phone) · `:214` `doc` (key `ten_khach` `:264`) · `:287` `_mo_hoac_lay` (`:338`) | API (bán lẻ) | `tim_khach` CÓ; `doc` + `_mo_hoac_lay` thiếu | thêm `p.phone_primary` ở 2 chỗ | Ấm | Không | Thấp |
| 24 | `services/dispatch_service.py:122` `_OVERVIEW_SQL` (LIMIT 400; `_overview_row` `:961`) | API list (điều phối trưởng ca) | JOIN, thiếu | `p.phone_primary` + key | Có | Không (nhưng #34, #45) | Thấp |
| 25 | `services/nhan_tai_phong.py:114` `_CHI_DINH_SQL` (Sắp đến, ô khách) + `:383` `_chi_dinh` | API list (màn phòng) | JOIN, thiếu | `p.phone_primary` ở CTE `o` rồi chuyển qua `gom_sap_den` | Có | Không | Trung bình: CTE `MATERIALIZED`, phải lần theo `gom_sap_den`/`dang_o_phong` để key tới giao diện |
| 26 | `services/ultrasound_board_service.py:90` (LIMIT 300; `:516`), `:176` (LIMIT 300; `:551/:592`) | API list (bảng siêu âm) | LEFT JOIN, thiếu | `p.phone_primary` ×2 | Có | Không | Thấp |
| 27 | `services/man_trang_chu_service.py:359` (LIMIT $4; lồng `patient{full_name,patient_code}` `:555`) | API list (trang chủ lễ tân) | LEFT JOIN, thiếu | `p.phone_primary` + thêm vào dict lồng | Có | Không | Thấp (giao diện đọc `patient?.full_name`) |
| 28 | `services/bang_hanh_trinh_service.py:151` (LIMIT `_TRAN_LUOT`; key `ten` `:313`) | API list (bảng hành trình) | JOIN, thiếu | `p.phone_primary` | Có | Không | Thấp |
| 29 | `api/v1/routers/visit_progress.py:84` (`/visits/{id}/workflow`, `:188`), `:233` (`/visits/active`, **không LIMIT**, `:293`) | API list | JOIN, thiếu | `p.phone_primary` ×2 | Ấm / Có (active) | Không | Thấp |
| 30 | `services/luot_kham_service.py:3098` `cho_quyet` | API list | JOIN, thiếu | `p.phone_primary` | Ấm | Không | Thấp |
| 31 | `services/service_routing_service.py:662` `cho_nhan_vao_phong` | API list | JOIN, thiếu | `p.phone_primary` | Ấm | Không | Thấp |
| 32 | `services/xem_luot_service.py:244` `doc` (`ten` `:283`) | API (hồ sơ một lượt) | JOIN, thiếu | `p.phone_primary` | Lạnh | Không | Thấp |
| 33 | `services/clinical_sign_service.py:115` `status` (`:194`) | API | JOIN, thiếu | `p.phone_primary` | Ấm | Không | Thấp |
| 34 | `services/doi_tac_service.py:198` `viec_doi_tac` (LIMIT 300; `ten_khach` `:336`) | API list | JOIN, thiếu | `p.phone_primary` | Ấm | Không | Thấp |
| 35 | `services/tep_ket_qua_service.py:1796` `cho_bac_si_cho_phep` (LIMIT 200), `:1826` `cho_xac_nhan` (LIMIT 100) | API list | JOIN, thiếu | `p.phone_primary` ×2 | Ấm | Không | Thấp |
| 36 | `services/kho_thuoc_service.py:198` `the_kho` (LIMIT 1000; tên khách chỉ khi `ref_type='prescription'`) | API list (thẻ kho) | JOIN, thiếu | `p.phone_primary` (CASE như tên) | Lạnh | Không | Thấp |
| 37 | `services/so_no_service.py:464` `doc_so_no_ky`/`doc_so_du_mo` → `cong_no_service.py:389` (`khach`, `ma_bn`) | API list (khách còn nợ) | JOIN, thiếu | `p.phone_primary AS sdt` — **cần nhất khi truy thu nợ** | Ấm | Có — đi vào báo cáo cuối ngày | Thấp |
| 38 | `services/bao_cao_viec_tien_service.py:59`, `:88`; `bao_cao_thuoc_service.py:259` (LIMIT 1000, `gom_thuoc_theo_khach`) | API / báo cáo | JOIN, thiếu | `p.phone_primary` (tuỳ chọn) | Lạnh | Có (vào CSV #E3) | Thấp |
| 39 | `services/doi_lich_nhanh.py:165` (`ten_khach` `:276`); `services/lich_hen_doc.py:143` (LIMIT 20; `patient{full_name}` `:162`) | API | JOIN, thiếu | `p.phone_primary` | Lạnh | Không | Thấp |
| 40 | `services/recall_job_service.py:111` `danh_sach` (LIMIT 500, **có phone**); `recall_service.py:39` (job sinh việc, có phone) | API list (nhắc tái khám) | JOIN, CÓ phone | không | Ấm | Không | — |
| 41 | `services/danh_sach_khach_cskh.py:65` (LIMIT $9), `services/danh_sach_benh_nhan_service.py:138`, `lieu_trinh_service.py:247` (`sdt`), `ghi_chu_khach_service.py:188`, `ho_so_khach_doc.py:79`, `ho_so_lam_sang_doc.py:142`, `ho_so_kham_service.py:52`, `form_engine_service.py:310` | API list/hồ sơ | JOIN, CÓ phone | không | Ấm/lạnh | Phiếu in cho khách (đã có SĐT) | — |
| 42 | `services/nhat_ky_van_hanh.py:93` `doc_nhat_ky` (LIMIT $5; `khach`,`ma_khach` `:126/:141`; lọc `ILIKE` tên/mã `:104`) | API (nhật ký hôm nay) | JOIN, thiếu | `p.phone_primary AS sdt_khach` (+ có thể lọc theo SĐT) | Lạnh | Không | Thấp |
| 43 | `services/consent_service.py:112` `_LINK_SQL` (`other_name` `:177`: người liên kết hồ sơ) | API | LEFT JOIN, thiếu | `p.phone_primary` (tuỳ) | Lạnh | Không | Thấp |
| 44 | `api/v1/patients.py:164` `check_duplicate` (trả `matches` có tên + mã + năm sinh; **cố ý KHÔNG trả SĐT**, comment `:193`) | API (kiểm trùng khi tạo khách) | JOIN, thiếu | **Quyết định nghiệp vụ**: đây là chỗ "trùng tên" cắn nhất → nên trả SĐT che (`che_sdt` `0334***897`, sẵn ở `don_du_lieu_thu_service.py:93`) | Lạnh | Không | Trung bình: đảo một quyết định bảo mật có chủ ý |
| 45 | `tools/patient/get_summary.py:65` | Tool AI | CÓ phone (`phone`) | không | Lạnh | Gửi sang LLM | — |

## B. Chuỗi ghép sẵn: chuông (`thong_bao`) và cảnh báo — giao diện KHÔNG tự thêm SĐT được

`thong_bao` KHÔNG có cột `clinic_patient_id`; tên khách nằm CỨNG trong `tieu_de`/`noi_dung` (ghi một lần, lúc phát sinh). Đọc lại ở `ThongBaoService.cua_toi` (`thong_bao_service.py:~305`, LIMIT 50, **không JOIN patient**, khoá gộp dòng có cả `tieu_de`).
Khuôn lặp ~10 lần: `f"{full_name} ({patient_code})"`. Tất cả đều là "đã có JOIN patient trong truy vấn lấy tên → chỉ thêm `phone_primary`".

| # | Nơi | Loại | JOIN/phone | Cần thêm gì | Nóng? | Ngoài đọc? | Rủi ro |
|---|---|---|---|---|---|---|---|
| B1 | `events/consumers/chuong.py:88` `_khach_va_bac_si`, ghép `:190` (`ten`) → dùng trong ~7 tiêu đề `:205–251` (kết quả về, đối tác, sửa lại, XN) | Chuỗi ghép (chuông vai + bác sĩ) | JOIN, thiếu | thêm `p.phone_primary`; `ten` thêm SĐT | Ấm (mỗi sự kiện kết quả) | Không | Thấp; chuông tới mọi **vai** trong `day_nhan_thong_bao` — vai có thể không nên thấy SĐT |
| B2 | `events/consumers/nhac_tai_kham.py:44` + `:75–78` ("Hẹn tái khám dd/mm — cần gọi chốt giờ: Tên (Mã)", `[:200]`) | Chuỗi ghép → vai CSKH | JOIN, thiếu | thêm SĐT; **CSKH cần nhất ở chỗ này** | Lạnh (hẹn giờ) | Không | Thấp; chú ý `[:200]` cắt đuôi |
| B3 | `events/consumers/lieu_trinh_sap_het.py:68` (`lt['ten_khach']`, `ma_khach`) | Chuỗi ghép → CSKH | `LieuTrinhService.doc_nhieu` đã SELECT `p.phone_primary AS sdt` (`lieu_trinh_service.py:248`) | chỉ dùng `lt['sdt']` — **không cần truy vấn thêm** | Lạnh | Không | Rất thấp |
| B4 | `events/consumers/hanh_trinh.py:215` `_ten_khach` (3 chỗ gọi `:250`, `:319`, `:377`; tiêu đề `:257`, `:326`, `:384`) | Chuỗi ghép (đã thanh toán, nhắc check-out, kết quả đối tác quá hạn) | JOIN, thiếu | thêm `p.phone_primary` vào `_ten_khach` (1 chỗ) | Lạnh | Không | Thấp |
| B5 | `events/consumers/chuong_nhan_cheo.py:77` + `:105` (`cau_chuong(khach=…)`) | Chuỗi ghép | JOIN, thiếu | thêm SĐT (ít cần: gửi nhân viên phòng) | Lạnh | Không | Thấp |
| B6 | `services/service_routing_service.py:922` `_reo_cho_xep_phong` (`:928`, tiêu đề `:935`) | Chuỗi ghép → vai quầy | JOIN, thiếu | thêm SĐT | Ấm | Không | Thấp |
| B7 | `services/bao_ket_qua_ve.py:36`, ghép `:55`, tiêu đề `:57` (CSKH + bác sĩ) | Chuỗi ghép | JOIN, thiếu | thêm SĐT (**CSKH gửi kết quả cho khách → cần**) | Lạnh | Không | Thấp |
| B8 | `services/booking_service.py:1682` `_bao_cskh_da_co_bac_si` (`noi_dung` `:1711`: "Tên (Mã) · giờ · BS…, gọi xác nhận") | Chuỗi ghép → CSKH | JOIN, thiếu | thêm SĐT (**việc là "gọi khách"**) | Lạnh | Không | Thấp |
| B9 | `api/v1/routers/booking.py:406` `bao_xep_bac_si` (tiêu đề `:426`: "Cần xếp bác sĩ: Tên") | Chuỗi ghép → quản lý | LEFT JOIN, thiếu | thêm SĐT | Lạnh | Không | Thấp; SQL trong router |
| B10 | `services/config_service.py:1114` (`apply_week`: `noi_dung` liệt kê tối đa 8 lịch "giờ Tên (BS X nghỉ)" → CSKH/trưởng ca) | Chuỗi ghép (danh sách) | LEFT JOIN, thiếu | thêm SĐT mỗi dòng (**CSKH phải gọi từng khách**); dòng dài hơn → xem trần độ dài `noi_dung` | Lạnh | Không | Trung bình: nội dung dài; chú ý khoá chống trùng |
| B11 | `services/tuong_tac_cskh_service.py:717` (`fetchval full_name`) → `_bao_hen_goi_lai` tiêu đề `:777` "Hẹn gọi lại … — Tên" | Chuỗi ghép → chính người hẹn | `fetchval` → đổi `fetchrow` lấy cả `phone_primary` | thêm SĐT | Lạnh | Không | Thấp |
| B12 | `services/so_sua_chi_dinh_service.py:349` (tiêu đề `:384` "Chỉ định bị bỏ — Tên", → bác sĩ chính) | Chuỗi ghép | LEFT JOIN, thiếu | thêm SĐT (ít cần) | Lạnh | Không | Thấp |
| B13 | `services/dispatch_service.py:865`, `:894`, `:909`, `:899/:913` `build_alerts` (message "Tên chờ N phút…", `patients[{name,code}]`) — nguồn `_OVERVIEW_SQL` (#24) | Chuỗi ghép (cảnh báo trưởng ca) + `/dispatch/alerts/call` tạo chuông với `tieu_de` do người gọi gõ | JOIN, thiếu | `phone_primary` từ #24; thêm `phone` vào `patients[]`; **KHÔNG nhất thiết đưa vào `message`** | Có (polled) | Không | Thấp |
| B14 | `api/v1/routers/dispatch.py:134` `/dispatch/tv` (`names`) và `services/display_board_service.py:75/:334` | **TV phòng chờ — công khai** | JOIN, thiếu | **KHÔNG THÊM.** `display_board_service.py` docstring ① cấm mọi định danh ngoài tên; có "bài kiểm canh đúng điều đó" | Có | **CÓ — người ngồi chờ** | Cao nếu thêm: vi phạm ràng buộc "KHÔNG ĐƯỢC ĐÁNH ĐỔI" của chính module (phòng khám phụ khoa/hiếm muộn) |
| B15 | `services/thong_bao_service.py` `cua_toi` | Đọc chuông | Không JOIN | Chỉ khi chọn phương án chuông "đọc-lúc-xem" (xem phần b) | Có (chuông, mỗi người mỗi lần làm mới) | Không | Trung bình |

## C. Nhật ký / audit / sự kiện

| # | Nơi | Loại | JOIN/phone | Cần thêm gì | Nóng? | Ngoài đọc? | Rủi ro |
|---|---|---|---|---|---|---|---|
| C1 | `services/audit_log_service.py:51–111` `_SQL` (nhánh `v_audit_log` + nhánh `work_item_event` tự JOIN patient `:88`) → `subject_label()` `:~150` ghép sẵn `"Tên (Mã)"` | Nhật ký thao tác (chuỗi ghép + view SQL) | `v_audit_log` (migration `20260805000001_v_audit_log.sql:81`, cột `subject_name`/`subject_code`) không có phone | Thêm cột `subject_phone` vào cuối view (`CREATE OR REPLACE VIEW` chỉ được thêm cột ở cuối) + nhánh `quy_trinh`; `subject_label()` thêm SĐT | Lạnh (LIMIT $2, ≤ MAX_ROWS) | Không | Trung bình: đổi view = migration; nếu chỉ muốn ghi nhật ký thì KHÔNG cần SĐT — hỏi chủ ý |
| C2 | `services/dispatch_service.py:681–753` `history` (`v_dispatch_history` `20260804000003_dispatch_move.sql:162` + nhánh `event_log` JOIN patient) | Nhật ký điều phối (view + UNION) | thiếu | Không sửa view: LEFT JOIN patient qua visit ngay trong `_SQL` của `history` | Lạnh | Không | Thấp |
| C3 | `events/catalogue.py` + mọi payload `emit()` | Sự kiện | **Không có tên/SĐT** — `event_log.payload` cố ý chỉ ID (`notification_relay._lam_giau` docstring) | Không | — | — | Giữ nguyên |
| C4 | `notify_row_change` (`20260806000001`) + SSE `/api/events/stream` | Realtime | **Không có dữ liệu hàng** (chỉ `{t: bảng, c: clinic}`) | Không | — | — | Không đụng |
| C5 | `services/kho_loi.py`, `canh_gac*.py`, `core/logging.py:30–60` (khoá bị che: `full_name`, `patient_name`, `phone`, `phone_number`; regex SĐT VN `:70`) | Kho lỗi / log | Tên khách được che | Nếu thêm field mới tên `sdt`/`so_dien_thoai`/`dien_thoai` vào log → **không** nằm trong `_SENSITIVE_KEYS` | — | Log | Trung bình: thêm các khoá này vào danh sách che khi thêm field |

## D. Tin gửi ra ngoài

| # | Nơi | Loại | JOIN/phone | Cần thêm gì | Nóng? | Ngoài đọc? | Rủi ro |
|---|---|---|---|---|---|---|---|
| D1 | `services/notification_relay.py:90` `_lam_giau` + `notification_templates.py:36` `_khach()` ("Tên (Mã)") → Telegram nhóm vận hành | Tin Telegram | JOIN; **cố ý không lấy phone** | **KHÔNG THÊM.** Docstring đầu `notification_templates.py` + `_lam_giau` ("KHÔNG đắp số điện thoại"): Telegram là bên thứ ba. Test canh: `src/tests/unit/test_notification_templates.py:84` | Lạnh | **CÓ (bên thứ ba)** | Cao nếu thêm: đỏ test + đảo chính sách |
| D2 | `services/providers/zalo.py` `gui_zns` (`:101`) — gửi cho KHÁCH bằng template ZNS (`du_lieu={"ten", "gio_hen"}` ở `tuong_tac_cskh_service.py:889`) | Tin tới khách | Lấy `phone_primary` làm địa chỉ gửi | Không (tin gửi chính chủ, template Zalo đã duyệt cố định) | Lạnh | Có (khách) | Không đụng |
| D3 | `tools/communication/send_zalo.py` | STUB, không gửi | — | Không | — | — | — |
| D4 | Email / SMS | — | **CHƯA KIỂM** — grep `smtp|sms` không thấy mã gửi email/SMS tới khách trong `src/clinicai` ngoài Zalo/Telegram | — | — | — | — |
| D5 | `services/telegram_bot.py` (lệnh `/trangthai`…) | Telegram | Không có tên khách (chỉ số đếm/health) | Không | — | Có | — |

## E. File xuất (CSV/XLSX/PDF)

| # | Nơi | Loại | Có cột tên/SĐT khách? | Cần thêm gì | Nóng? | Ngoài đọc? | Rủi ro |
|---|---|---|---|---|---|---|---|
| E1 | `services/quay_thu_service.py:744` `csv_lich_su`, `:813` `xlsx_lich_su` (router `cashier.py:~170/~195`) | CSV + XLSX sổ thu | Có "Khách", "Mã khách"; không SĐT | Thêm cột "SĐT" sau "Mã khách" (cần #17) | Lạnh | Kế toán/quản lý | Thấp; chú ý `_o()` chống công thức |
| E2 | `services/hoa_don_excel.py` (`g["ten"]`,`g["ma_bn"]` ~10 sheet, `:331`; "Theo khách") | XLSX hoá đơn/quầy cửa nợ | Có tên + mã; `quay_cua_no` đã có `so_dien_thoai` | Thêm cột SĐT (dữ liệu có sẵn từ #18 `:58`) | Lạnh | Kế toán | Thấp |
| E3 | `services/bao_cao_cuoi_ngay_service.py:585` `csv_bao_cao` (cột Khách/Mã BN `:610`, `:677`, `:705`, `:727`, `:878`) | CSV báo cáo cuối ngày | Có tên + mã; không SĐT | Thêm cột SĐT cần sửa 4 SQL `:927/:993/:1070/:1094` (LIMIT 5000) + ~8 chỗ dựng dict `:240–419` | Lạnh | Quản lý | Trung bình: nhiều chỗ, test chia cột CSV |
| E4 | `services/xuat_hoa_don_service.py:~258–277` + `hoa_don_misa_doc.py:50–53` (MISA) | XLSX MISA | Cá nhân: **ĐÃ có SĐT** (`so_dien_thoai`, cột 8 `:332`); hoá đơn công ty: cố ý để trống SĐT/CCCD (comment `:~245`) | Không | Lạnh | **Kế toán/thuế** | Không đụng — đã đúng chủ ý |
| E5 | `services/excel_report_export.py`, `theo_hang_hoa_service.py`, `excel_export.py` | XLSX báo cáo hàng hoá/kho | Không có khách | Không | — | — | — |
| E6 | PDF (`reportlab`/`weasyprint`) | — | **Không có** trong `src/clinicai` (grep rỗng); phiếu in là HTML do giao diện dựng | — | — | — | — |
| E7 | Phiếu in/kết quả: `phieu_kham/mang_sang.py:258` (`patient.phone` `:89`), `form_engine_service.py:310` (`dien_thoai` `:499`) | Dữ liệu cho bản in | Ô "hành chính" `dung_hanh_chinh` (`:179`) chỉ tên/năm sinh/mã; SĐT ở `dung_ho_so` | Không (đã có) | Lạnh | **Khách cầm bản in** | — |

## F. Bản sao tên phi chuẩn hoá trong DB, và view SQL

(a) **Bản sao tên khách phi chuẩn hoá** (SĐT không lấy được từ bản sao — phải lấy từ `patient` hoặc nhét thêm lúc ghi):
- `thong_bao.tieu_de` / `thong_bao.noi_dung` (migration `20260807000006`): chuỗi ghép chứa "Tên (Mã)", ghi MỘT lần, **không có `clinic_patient_id`**; sửa SĐT/tên sau đó không cập nhật; dòng cũ sẽ không có SĐT. Khoá gộp ở `cua_toi` gồm `tieu_de` (SĐT đổi → coi là chuông khác, ảnh hưởng nhỏ).
- `lich_su_notion.nguoi.ten`, `.sdt` (`20261005100000`): bản sao từ Notion lúc nhập, phục vụ hồ sơ lịch sử — mức dùng khi hiển thị danh sách: **CHƯA KIỂM**.
- `hoa_don_cong_ty.nguoi_mua`, `khach_cong_ty.nguoi_mua` (`20261014156000`): tên người mua nhập tay, không nhất thiết trùng tên khách.
- `payment.paid_by_text` (baseline `:752`): chữ tự do "người trả" (`xem_luot_service.py:749`).
- `patient.guardian_name` (người giám hộ) — không phải bản sao tên khách.
- KHÔNG phải bản sao (tên đọc sống): `v_audit_log`, `v_dispatch_history`, `patient_summary` (view có `phone_primary`), `event_log.payload` (chỉ ID), `appointment`/`visit`/`service_order` (không có cột tên khách — đã grep `ten_khach|patient_name|ho_ten` trong 360 migration).
- `luot_dong_thoi_gian.nhan` (nhãn): **CHƯA KIỂM** có chứa tên khách không.

View/hàm SQL trả tên khách: `public.patient_summary` (có `phone_primary`), `public.doctor_patient_list()` (có `phone_primary`; không thấy Python gọi — chỉ giao diện/PostgREST?), `v_audit_log` (thiếu), `v_dispatch_history` (thiếu), hàm kế hoạch dọn dữ liệu thử `don_du_lieu_thu` (`jsonb 'ten'`, SĐT đã che bằng `che_sdt` — cố ý).

## (b) Đề xuất vị trí hàm dùng chung (backend)

Hiện KHÔNG có hàm chung lấy "tên hiển thị khách" (`grep ten_hien_thi|display_name` chỉ ra tên TỆP; `f"{full_name} ({patient_code})"` lặp ≥ 10 chỗ ở mục B; khoá SĐT trong dict đặt 5 kiểu: `phone_primary`, `phone`, `sdt`, `so_dien_thoai`, `dien_thoai`).

1. `core/phone.py` (đã có `normalize_vn_phone`, `phone_variants`): thêm `hien_sdt(raw) -> str | None` — rỗng → `None`; parse được → "0901 234 567"; không parse (số cũ gõ tự do, `phone_primary` lưu NGUYÊN VĂN, không chuẩn hoá lúc ghi) → trả nguyên văn.
2. Tệp mới thuần (không DB) `services/ten_khach.py`: `ten_kem_ma(full_name, patient_code=None, phone=None, *, kem_sdt=True) -> str` → "Nguyễn Thị Lan (BN-0012 · 0901 234 567)", an toàn với None. Thay cả B1–B12 + `audit_log_service.subject_label` + `dispatch.build_alerts`. `kem_sdt=False` cho TV và Telegram (nơi cấm) để cùng một hàm, cờ tắt tường minh.
3. Quy ước khoá cho danh sách mới: luôn `phone_primary` (cùng `work_item_service`, `doctor_board_service`), lồng trong `patient{}` nếu danh sách đã lồng.
4. Không đặt ở DB (generated column / hàm SQL): thêm cột sinh trên bảng `patient` nóng, đổi định dạng sẽ cần migration; Python thuần đủ và test được. Ngoại lệ: `v_audit_log` nếu muốn SĐT trong nhật ký (xem C1).
5. Chuông: 2 phương án —
   - **P1 (rẻ, khuyến nghị cho đợt này):** nhét SĐT vào chuỗi lúc ghi (qua `ten_kem_ma`). Ưu: không migration, không đụng `cua_toi`. Nhược: SĐT đóng băng, mọi vai nhận chuông đều thấy.
   - **P2 (đúng hơn):** thêm cột `thong_bao.clinic_patient_id`, `cua_toi` `LEFT JOIN patient` trả `sdt` riêng (giao diện hiện cạnh tên; áp quyền xem SĐT được; luôn mới). Cần migration (dải giờ riêng, nhớ luật trùng số migration), đổi chữ ký `ghi_chuong_vai/nguoi`, `goi`, `goi_nguoi`; `cua_toi` thêm tối đa 50 tra PK mỗi lần làm mới chuông (rẻ nhưng chuông là đường nóng).
   - Mức việc: P1 = Mức 2; P2 = Mức 3 (migration).
6. Thêm khoá `sdt`, `so_dien_thoai`, `dien_thoai`, `phone_primary` vào `core/logging._SENSITIVE_KEYS` khi thêm field.
7. Thêm một test "drift" (kiểu `scripts/ban-do-code.py`): mọi `f"{…full_name…} ({…patient_code…})"` mới phải đi qua `ten_kem_ma`.

## (c) Chỗ KHÔNG chắc / CHƯA KIỂM

- **Tần suất thật từng endpoint**: không đo; "nóng/ấm/lạnh" suy từ loại màn hình + số đo cũ trong memory (14/10, 17/10), không đo lại.
- **Chính sách đang cấm SĐT** (cần Quang/Tuyền quyết trước khi ai đó "làm cho đủ"): TV phòng chờ (B14), Telegram (D1), `check-duplicate` (#44), hoá đơn công ty (E4). Hai chỗ có test canh: `test_notification_templates.py:84` và bài kiểm của `display_board_service` (**CHƯA KIỂM tên tệp test**).
- **Quyền xem SĐT theo vai**: không thấy cơ chế che SĐT theo vai ở backend (chỉ `che_sdt` ở `don_du_lieu_thu_service.py:93`). Chuông P1 đóng cứng chuỗi → mọi vai trong `day_nhan_thong_bao` (cấu hình được) sẽ thấy; chưa biết vai nào "không nên".
- **Dạng hiển thị**: `phone_primary` lưu nguyên văn người gõ (có thể `+84…`, có khoảng trắng); khách không SĐT (con nhỏ dùng số mẹ → `phone_secondary`/`patient_sdt_them`); chưa chốt hiện số nào khi có nhiều số.
- **Chưa đọc từng test** xem sửa chuỗi chuông sẽ làm đỏ test nào (có thể nhiều test so chuỗi tiêu đề chuông).
- **Python regex quét có thể sót** SQL dựng bằng f-string/ghép chuỗi hoặc alias lạ (đã soát tay: dispatch, checkout, pharmacy, ultrasound, ban_thuoc, lieu_trinh; còn lại dựa vào grep `full_name|patient_name|ten_khach`).
- **Không kiểm**: `src/dashboard/**` (vùng khác), PostgREST `/rest/v1` (giao diện còn đọc trực tiếp Supabase cho đăng nhập), module `voice/`, `orchestrator/`, `llm/` (grep không thấy tên/SĐT khách), email/SMS (D4).
- `lich_su_notion` và `luot_dong_thoi_gian.nhan`: mức dùng/nội dung **CHƯA KIỂM**.
