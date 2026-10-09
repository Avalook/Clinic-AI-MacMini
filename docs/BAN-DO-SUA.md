# BẢN ĐỒ SỬA — muốn sửa gì thì đi đâu

> Viết tay 01/10/2026 (Tuyền: "được chỉ định đúng chỗ nào, việc gì, kết quả cần
> đạt như nào" thay vì đọc cả quyển). Ngắn có chủ ý: mỗi mục trỏ tới màn, file,
> hàm, test. Chuỗi đầy đủ màn → route → router → service → test nằm ở
> **`docs/BAN-DO-CODE.md`** (sinh từ code, không lỗi thời — tìm theo route).
> Giao việc cho AI khác: **`docs/MAU-GIAO-VIEC.md`**.

**Cách tra (≤ 2 bước):** (1) tìm mục theo nghiệp vụ dưới đây. (2) Có dòng
**Trên màn** → làm trên màn, KHÔNG cần code, không cần AI. Không có / không đủ →
dòng **Code** cho file + hàm + test; cần thêm chi tiết thì tìm route của màn
trong `docs/BAN-DO-CODE.md`.

Viết tắt: `D/` = `src/dashboard/app/(dashboard)/` · `S/` = `src/clinicai/services/`
· `R/` = `src/clinicai/api/v1/routers/` · `T/` = `src/tests/` · `FT/` =
`src/dashboard/tests/`. Quyền: từ 30/09 mọi nhân sự nội bộ có đủ lego, **trừ**
hai lego chỉ Quản lý giữ — **Cài đặt phòng khám** (`/settings*`) và **Nhân sự &
phân quyền** (`/nhan-su`, `/phan-quyen`, `/settings/tai-khoan`,
`/settings/don-du-lieu-thu`).

## Luật chung cho MỌI việc code (không nhắc lại ở từng mục)

1. **Không luật nghiệp vụ trong TSX** (SO-LUAT 3.1) — TSX chỉ vẽ và gửi lệnh;
   quyết định nằm ở service Python (`S/`) hoặc SQL. Route `app/api/**/route.ts`
   chỉ chuyển tiếp (3.2).
2. **Đổi database = migration MỚI** trong `supabase/migrations/` (không sửa tay,
   không sửa migration cũ); bất biến có tranh chấp ép ở Postgres (6.2). Áp bằng
   `scripts/apply-pending-migrations.sh`, không trong lúc deploy.
3. **Hàm nhận ngày/giờ từ người dùng trả rỗng, không ném** — kèm test đầu vào rác.
4. **Giao diện:** màu/cỡ/bo góc từ `DESIGN.md` + token `src/dashboard/app/globals.css`;
   nút từ `src/dashboard/components/ui/`; không hex, px tự chế, `style={{}}` mới,
   `window.confirm`; `<button>` luôn có `type=`. Nghiệm thu 375 và 1280.
5. **Sửa màn: tra `docs/SITEMAP.md` mục B** (mọi lối vào của cùng chức năng) và sửa
   đủ; thêm/đổi route, mục thanh bên → sửa SITEMAP cùng commit.
6. **Sự kiện mới** khai ở `src/clinicai/events/catalogue.py` (không khai thì
   `emit_event` từ chối). Thêm bên nghe = thêm consumer, không sửa nơi phát.
7. **Đổi màn/route/router/service → chạy `python3 scripts/ban-do-code.py`** rồi
   commit `docs/BAN-DO-CODE.md` (CI `--kiem` đỏ nếu quên). `./scripts/ci-may.sh
   --bao-github` xanh mới merge.

---

## 1. Danh mục, giá, phòng — phần lớn là DỮ LIỆU, sửa trên màn

**Giá dịch vụ · nhóm hàng · thêm/tạm ngưng dịch vụ · PHÒNG LÀM từng dịch vụ**
- Trên màn: `/cashier/dich-vu` (Bảng giá dịch vụ & phòng, 01/10). Lưu là dùng ngay
  cho lượt mới. Lọc "Chưa có phòng" + [Gán phòng] (cần lego Cài đặt phòng khám).
  **Vật tư bán thêm** (đầu dò Bio, Mirena…): ngăn riêng dưới bảng — chỉ giá + đang bán, không phòng (§7).
- Nguồn sự thật danh mục: file phòng khám gửi 01/10 → bảng `danh_muc_dich_vu_nguon`
  + hàm `dong_bo_danh_muc_dich_vu` (migration `20261002100000_danh_muc_dich_vu_chuan_0110.sql`;
  đợt file mới = thêm `nguon` mới rồi gọi lại hàm). Luật "phí khám / cần phòng /
  phòng nào làm được / chưa có phòng" ở MỘT hàm Postgres `danh_muc_dich_vu(clinic)`.
- Code: `D/cashier/DanhMucDichVuPhong.tsx` → `/api/service-price` (`?xem=danh-muc`,
  POST/PATCH có `nhom`) → `R/config.py` (`danh_muc_dich_vu`, `add_price`,
  `update_price`) → `S/danh_muc_dich_vu_service.py` `DanhMucDichVuService.doc`,
  `S/config_service.py` `PriceListService`; gán phòng → `/api/clinic-config`
  `service-rooms` → `S/clinic_config_service.py` `set_service_rooms`. Bảng giá
  thuốc vẫn `D/cashier/CashierView.tsx`.
- Test: `T/services/test_danh_muc_dich_vu_chuan_db.py`, `T/unit/test_danh_muc_dich_vu.py`,
  `T/services/test_danh_muc_kiotviet_db.py`, FT `cashier-catalog-ui-boundary.test.mts`.

**Dịch vụ nào làm ở phòng nào** (vd Ghế điện từ trường chỉ ở Phòng Sàn chậu)
- Trên màn: `/settings/clinic-config` → phòng → "Làm việc gì" → tick dịch vụ
  (dịch vụ đã tick ở một phòng thì CHỈ làm ở các phòng được tick).
- Code: `D/settings/clinic-config/ViecCuaPhong.tsx`, `CoSoPhong.tsx` → `/api/clinic-config`
  (`room-services`) → `R/clinic_config.py:set_room_services` →
  `S/clinic_config_service.py` `ClinicConfigService.set_room_services`. Luật
  "phòng làm được" là hàm Postgres `phong_lam_duoc` (migration
  `supabase/migrations/20261001210000_phong_lam_theo_dich_vu.sql`); Python gọi qua
  `S/service_routing_service.py` `phong_lam_duoc_sql`. Bảng `clinic_room_service`.
- Test: `T/services/test_phong_lam_theo_dich_vu_db.py`, `T/services/test_phong_lam_theo_dich_vu.py`.

**Phòng, tầng, tên phòng, bật/tắt phòng, cơ sở, thư ký đi cùng bác sĩ**
- Trên màn: `/settings/clinic-config` (Cấu trúc phòng khám).
- Code: `D/settings/clinic-config/ClinicConfigBoard.tsx` → `S/clinic_config_service.py`
  (`set_room_floor`, `rename_room`, `set_room_active`, `set_room_nodes`…). Test:
  `T/services/test_clinic_config.py`, `T/services/test_phong_la_tai_nguyen_db.py`.

**Phí khám (dịch vụ con của loại khám)** — chọn ở quầy: `D/_lam-viec/ChonDichVuKham.tsx`
→ `R/luot_kham.py` → `S/phi_kham_service.py` `PhiKhamService` (`doc`, `chon` — gửi `them`/`bo`
theo từng dịch vụ, sự kiện `visit.exam_service_changed`). Dòng "Dịch vụ khám" trên Hành trình
khách: `S/hanh_trinh_khach_service.py` `dong_dich_vu_kham`. Test: `T/services/test_phi_kham_chon_db.py`,
`T/services/test_hanh_trinh_trang_thai_hien_tai_db.py`.

**Kho thuốc: thêm thuốc, giá thuốc, nhập lô, kiểm kho** — trên màn `/pharmacy/inventory`
(tab Danh mục, Nhập, Kiểm kho). Code: `D/pharmacy/inventory/DanhMucKho.tsx`,
`PhieuNhap.tsx`, `KiemKho.tsx` → `/api/pharmacy/[action]` → `S/pharmacy_service.py`
(`luu_thuoc`, `nhap_lo`), `S/kho_thuoc_service.py` (`tao_phieu_nhap`, `kiem_kho`,
`xuat_nhap_ton`). Test: `T/services/test_kho_thuoc_danh_muc_db.py`, `T/services/test_kho_kiotviet_db.py`.

**Mẫu kết quả · biểu mẫu phiếu kết quả · gán mẫu cho dịch vụ**
- Trên màn: `/settings/mau-ket-qua` (tab Gán mẫu · Sửa mẫu; xuất bản là dùng).
- Code: `D/settings/mau-ket-qua/` (`MauKetQuaView.tsx`, `GanMau.tsx`, `TrinhSuaMau.tsx`)
  → `/api/mau-ket-qua` → `S/mau_ket_qua_service.py` `MauKetQuaService`,
  `S/form_engine_service.py` `FormEngineService` (`xuat_ban`). Mẫu gốc:
  `src/clinicai/phieu_kham/mau_ket_qua_v3.json`. Test: `T/services/test_man_mau_ket_qua_db.py`,
  `T/services/test_mau_ket_qua_v3_db.py`, `T/services/test_form_engine_db.py`.

**Dọn khách THỬ** — trên màn `/settings/don-du-lieu-thu` (tick từng khách). Code:
`S/don_du_lieu_thu_service.py`; test `T/services/test_don_du_lieu_thu_db.py`.

## 2. Dây nối nghiệp vụ — công tắc, sửa trên màn

**Thu trước khi làm · tự xếp phòng · chỉ xếp theo phòng lễ tân chọn · khách quen
vào thẳng BS · cùng buổi thẳng dịch vụ · quyền theo lịch · báo CSKH khi về còn
việc · số ngày kết quả đối tác quá hạn · phút nhắc check-out · loại khám qua tư
vấn / đi thẳng phòng · chuông sự kiện báo ai**
- Trên màn: `/settings/day-noi` (Quản lý). Bật/tắt là có hiệu lực ngay.
- Code (khi cần DÂY MỚI hoặc đổi nghĩa dây): danh sách + mặc định ở
  `S/day_noi.py` (`DAY`); đọc/ghi `S/day_noi_service.py` `DayNoiService` (`dat_day`,
  `dat_loai_kham`, `dat_chuong`); màn `D/settings/day-noi/DayNoiBoard.tsx`. Ý nghĩa
  từng dây H1…H8: `docs/BAN-DO-DAY-NOI-LEGO.md`. Test: `T/services/test_day_noi_nhac_db.py`.

## 3. Đặt lịch

**Giờ mở cửa, giờ ca, số chỗ mỗi bác sĩ, luật bác sĩ bắt buộc, thời lượng**
- Trên màn: `/settings/booking-policy` (Luật đặt lịch).
- Code: `D/settings/GioCaLamViecCard.tsx`, `LuatBacSiCard.tsx`, `BookingPolicyCard.tsx`
  → `S/clinic_settings_service.py` `ClinicSettingsService`, `S/booking_override_service.py`
  `BookingOverrideService` (luật số chỗ, "luật mới cắt luật cũ"). Test:
  `T/services/test_booking_policy_dau_vao_rac_db.py`, FT `booking-policy-boundary.test.mts`.

**Khung giờ "đã qua" ở màn đặt / đổi lịch** (09/10/2026) — đã qua = khung đã KẾT
THÚC (khung đang chạy vẫn đặt được), cùng luật máy chủ `_chan_dat_vao_qua_khu`.
MỘT hàm `src/dashboard/lib/khung-da-qua.ts` (`khungDaQua`, `khungDaQuaTheoPhut`,
`khungDaQuaVn`) dùng ở `patients/new/NewPatientForm.tsx`, `patients/CinemaSlotPicker.tsx`,
`patients/AppointmentBooking.tsx` (→ `DatLichModal`, `AppointmentEditModal`,
`DatLichBuoiKe`), `appointments/BangBacSiTuan.tsx` (→ `BookingHub`). Test FT
`lib/khung-da-qua.test.mts`. Ngoài ca / giờ mở cửa: máy chủ, không đổi.

**Hành vi đặt / đổi / huỷ lịch, chặn trùng, ngoài khung ca**
- Màn: `/appointments` (`D/appointments/BookingHub.tsx`), popover đổi lịch
  `D/_lam-viec/DoiLichTaiCho.tsx`, huỷ `D/_lam-viec/ThaoTacLichTaiCho.tsx`.
- Code: `S/booking_service.py` `BookingService` (`create`, `apply_action`,
  `doi_lich_nhanh`, `doi_dich_vu_kham`); sức chứa `S/capacity_service.py`; giữ chỗ
  `S/slot_hold_service.py`; đọc lưới ngày `S/man_dat_lich_doc.py`, `S/lich_hen_doc.py`.
- Test: `T/test_booking_service.py`, `T/services/test_capacity_roster_gate.py`. Luật:
  SO-LUAT 6.5 (sức chứa là ghế của MỘT bác sĩ, kiểm lúc xếp bác sĩ).

**Ô chọn dịch vụ khi đặt / sửa lịch — 4 nhóm Khám · Điều trị · Thuốc (ẩn) · Khác (07/10/2026)**
- Thêm/bớt/đổi tên một loại hay đổi nhóm = DỮ LIỆU (`service_type.nhom`, `thu_tu`,
  Điều trị trỏ dòng giá `service_price_id`; migration `20261007600000_nhom_dich_vu_dat_lich.sql`).
- Code: MỘT component `D/_lam-viec/ChonDichVuDatLich.tsx` (dạng ô chọn + dạng chip
  `ChonDichVuDatLichChip`, gợi ý ghi chú `GoiYGhiChu`) dùng ở `NewPatientForm.tsx`,
  `AppointmentBooking.tsx` (sửa/đặt ở Quản lý khách hàng), `BookingHub.tsx`,
  `ThaoTacLichTaiCho.tsx` (popover Đổi dịch vụ khám) → `/api/catalog/dich-vu-dat-lich` →
  `R/catalog.py` → `S/dich_vu_dat_lich.py` (`gom_nhom`, `doc`; popover dùng chung qua
  `S/doi_dich_vu_kham.py` `o_doi_dich_vu`). Ghi chú lịch = `appointment.notes`; đổi lịch
  sửa ghi chú qua `apply_action(reschedule, ghi_chu=…)`, bản cũ ở `event_log`
  (`ghi_chu_cu`/`ghi_chu_moi`); lễ tân thấy ở `QueueBoard.tsx` (`S/tiep_don_service.py`)
  và `WeeklyAppointmentsTable.tsx` (`S/week_appointments_service.py`).
- Test: `T/services/test_nhom_dich_vu_dat_lich_db.py`, `T/unit/test_dich_vu_dat_lich.py`,
  FT `nam-dich-vu-kham-boundary.test.mts`.

**Ô tìm khách ở màn Đặt lịch (tìm trên toàn bộ hồ sơ, 06/10/2026)**
- Màn: `/appointments` → `D/appointments/BookingHub.tsx` (`ketQuaTim`, debounce 300 ms, từ 2
  ký tự) → route `app/api/appointments/tim-khach/route.ts` (chỉ chuyển tiếp).
- Code: `S/man_dat_lich_doc.py` `tim_khach` + `_TIM_SQL` (dùng chung `chuoi_tim`/`mau_so`
  của `S/danh_sach_benh_nhan_service.py`; đổi cách tìm thì đổi CẢ HAI màn). Trần `TRAN_TIM`.
- Test: `T/services/test_dat_lich_tim_khach_db.py`, FT `dat-lich-tim-khach-boundary.test.mts`.

## 4. Tiếp đón · check-in · sinh hiệu

**Check-in / Không đến / Hoàn tác** — màn duy nhất `/reception/queue`
(`D/reception/queue/ManTiepDon.tsx` → thanh tìm + lọc `ThanhLocTiepDon.tsx`,
`QueueBoard.tsx`, bảng `D/home/WeeklyAppointmentsTable.tsx`; lọc là hàm thuần
`src/dashboard/lib/tiep-don.ts`; nút `src/dashboard/components/ui/NutCheckIn.tsx`).
Code: `S/luot_kham_service.py` `LuotKhamService.check_in` + `xep_sau_check_in`
(khách đi đâu sau check-in), `S/tiep_don_service.py` `TiepDonService`.
**Hoàn tác check-in chỉ khi chưa làm gì** (09/10/2026): luật + câu từ chối ở
`S/hoan_tac_check_in.py` (`ly_do_khong_hoan_tac`, `VIEC_DA_LAM_SQL`), gọi từ
`S/booking_service.py` `_hanh_dong_trong_gd` (khoá lịch → lượt → luồng). Test:
`T/services/test_hoan_tac_check_in_db.py`, `T/unit/test_hoan_tac_check_in.py`,
`T/services/test_check_in_lai_sau_hoan_tac_db.py`, `T/unit/test_tiep_don_service.py`.

**Đo sinh hiệu** — màn duy nhất `/do-sinh-hieu` (`D/do-sinh-hieu/BangDoSinhHieu.tsx`).
Code: `S/sinh_hieu_service.py` `SinhHieuService` (`record_vitals`,
`bat_dau_do_sinh_hieu`); dùng lại số đo cùng buổi `S/sinh_hieu_buoi.py`. Test:
`T/services/test_sinh_hieu_cung_buoi_db.py`, `T/services/test_sinh_hieu_khong_chan_db.py`.

**Nút "+ Nước tiểu"… — làm thêm tại quầy (lễ tân / người đo tick, không cần bác
sĩ)** — Trên màn: danh sách nút (thêm "Xét nghiệm máu", tắt, chỗ hiện, chữ trên
nút) ở `/settings/day-noi` khối "Dịch vụ làm thêm tại quầy". Code: nút
`D/_lam-viec/LamThemTaiQuay.tsx` (dùng ở `QueueBoard.tsx`, `BangDoSinhHieu.tsx`),
cấu hình `D/settings/day-noi/LamThemTaiQuayCauHinh.tsx` → `/api/lam-them` →
`R/lam_them_tai_quay.py` → `S/lam_them_tai_quay_service.py` `LamThemTaiQuayService`
(`dat`, `nut_cho_luot`, `luu_muc`, `bo_muc`). Chỉ định quầy: `service_order
.nguon_lam_them`, không có `consultation_id`; bảng `lam_them_tai_quay` (migration
`20261002200000_lam_them_tai_quay.sql`). Xếp phòng: sự kiện
`service_order.desk_added` → consumer Hành trình (H4). Test:
`T/services/test_lam_them_tai_quay_db.py`, `T/unit/test_lam_them_tai_quay.py`.

**Nhập kết quả ngay tại quầy cho dịch vụ làm thêm (Nước tiểu…) + dịch vụ chưa gắn
mẫu** — dịch vụ chưa gắn mẫu thì MÁY CHỦ chọn mẫu `CHUNG` (nhập tự do; hoặc mẫu
gợi ý v5), cờ `mac_dinh`; quản lý gắn mẫu riêng sau thì mẫu gắn thắng. Code luật:
`src/clinicai/phieu_kham/mau_goi_y.py` (`chon_mau`, `mau_cho_cac_dich_vu` — một chỗ cho phòng
dịch vụ, phiếu khám, quầy, `MauKetQuaService.mau_cua_dich_vu`). Nút "Nhập kết quả"
dưới chip tick: `D/_lam-viec/NhapKetQuaLamThem.tsx` (ghép `PhieuKetQua` + `KhungTep`,
đường lưu / hoàn tất / tải tệp có sẵn) ← `LamThemTaiQuay.tsx` ← khối `ket_qua` của
`S/lam_them_tai_quay_service.py` (`_ket_qua_cac_don`; `nhap_duoc` = quyền
`result.form.fill`). Test: `T/services/test_ket_qua_chung_lam_them_db.py`.
**Hoàn tất kết quả ở quầy = dịch vụ làm thêm XONG (phương án A, Tuyền 01/10):**
`S/lam_them_dong_dich_vu.py` (`dong_tai_quay`, `hoan_tac_tai_quay`, cửa tiền
`finance_gate.can_start` — dây `thu_truoc_khi_lam`, chưa thu thì nói rõ không đóng) gọi
lệnh `bat_dau` + `xong` CÓ SẴN của `S/service_execution_service.py`; lệnh mới
`hoan_tac_xong_tai_quay` (về chờ làm, lý do `RESULT_UNDONE`, migration
`20261002700000_hoan_tac_xong_tai_quay.sql`). Móc ở `S/form_engine_service.py`
(`hoan_tat`, `mo_sua`, `huy_sua`); nút [Đóng dịch vụ] / [Hoàn tác] ở `NhapKetQuaLamThem.tsx`
→ `/api/lam-them` (`dong-dich-vu`, `hoan-tac-dich-vu`).

## 5. Tư vấn · Bàn khám · phiếu khám

**Bàn tư vấn / Bàn khám (hàng chờ, nhận khách, xong tư vấn, khám xong)** — màn
`/tu-van`, `/ban-kham`, `/ban-kham/[phong]` (một component `D/ban-kham/BanKham.tsx`,
`BanTuVan.tsx`). Code: `S/luot_kham_service.py` (`start_consultation`,
`xong_tu_van`, `kham_xong`, `complete_consultation`), bảng đọc `S/luot_kham_doc.py`
`BangLuotKham`. Test: `T/services/test_hanh_trinh_tu_van_db.py`, `T/services/test_bo_qua_tu_van_chi_dinh_them_db.py`.

**Phiếu khám v5 (bảy phiếu: nội dung, khối, chữ)** — UI `D/_lam-viec/phieu-kham/`
(`PhieuKham.tsx`, `PhieuKhamLuot.tsx`, `KhoiDauPhieu.tsx`); máy chủ
`S/phieu_kham_service.py` `PhieuKhamService`, định nghĩa phiếu
`src/clinicai/phieu_kham/dinh_nghia/` + `src/clinicai/phieu_kham/khung.py`. Đặc tả:
`docs/phieu-kham/`. Test: `T/services/test_phieu_kham_db.py`, `T/services/test_phieu_kham_luot_db.py`,
FT `phieu-kham-boundary.test.mts`, `npm run test:phieu-kham`.
Bốn khối (thứ tự mục, tên khối) = `KHOI_PHIEU` ở `D/lib/phieu-kham.ts`: 1 Thông tin cơ bản
(A+B) · 2 Chỉ định cận lâm sàng (đã chỉ định & kết quả → danh mục C → "Chẩn đoán và xử lý"
D, sửa được, mọi phiếu) · 3 Chỉ định điều trị (thẻ điều trị → thẻ thủ thuật đã chỉ định →
lưới "Dịch vụ khác" F → Hẹn khám G) · 4 Đơn thuốc (E). Thẻ nào vào khối nào = `phanChiDinh`
(cờ `dieu_tri` máy chủ trước, rồi danh mục thủ thuật, còn lại CLS) — FT
`khoi-dieu-tri-boundary.test.mts`, `phieu-kham-boundary.test.mts` (mỗi mục A–G của bảy
phiếu ở đúng một khối), `lib/phieu-kham.test.mts`.

**Dịch vụ của lượt trong hồ sơ khám — đổi dịch vụ, phiếu cũ, lượt Điều trị (07/10/2026)**
— UI `D/_lam-viec/phieu-kham/KhoiDichVuHoSo.tsx` (đầu phiếu + hồ sơ tối giản ở
`PhieuKhamLuot.tsx` nhánh `chonDuoc`) → `/api/ho-so-kham` → `R/ho_so_kham.py` →
`S/ho_so_dich_vu.py` (`doc`, `doi` → `BookingService.doi_dich_vu_kham(trong_ho_so=True)`;
luật mở khoá `S/doi_dich_vu_kham.py` `ly_do_khong_doi(trong_ho_so=…)`, quyền
`QUYEN_DOI_TRONG_HO_SO`). Phiếu theo dịch vụ HIỆN TẠI: `S/phieu_kham_service.py` `doc_luot`.
Lượt Điều trị vào hàng → chỉ định sẵn: consumer `src/clinicai/events/consumers/dieu_tri.py`
(nghe `visit.routed`) → `sinh_chi_dinh_dieu_tri`; không phí khám `S/bill_service.py` `_kham`;
không chặn check-out `S/checkout_service.py` (`exam_open`); tick dịch vụ khám cho
Điều trị / Khác + giữ tick khi đổi `S/phi_kham_service.py` `_doc`. Test:
`T/services/test_ho_so_kham_db.py`, `T/unit/test_doi_dich_vu_kham.py`, FT `ho-so-dich-vu-boundary.test.mts`.

**Chỉ định điều trị trong hồ sơ — phiếu điều trị + làm tại bàn khám (07/10/2026)**
— Phiếu điều trị = phiếu KẾT QUẢ mẫu `PHIEU_DIEU_TRI` (2 ô) gắn cho dịch vụ của loại
khám nhóm DIEU_TRI (migration `20261007620000_phieu_dieu_tri_ban_kham.sql`; sửa ô = sửa
mẫu ở màn mẫu kết quả, là DỮ LIỆU). Thẻ + nút: đầu khối 3 "Chỉ định điều trị" (và hồ sơ
tối giản) `D/_lam-viec/phieu-kham/KhoiDieuTri.tsx` — khung thẻ là `KetQuaChiDinh.tsx`
(prop `dieuTri`: tiền, bắt buộc, Hoàn tác chỉ định, Ảnh · tệp), phần điều trị (chip
trạng thái, nút làm, phiếu `PhieuDieuTri` / `PhieuKetQua` của chỉ định) ở `KhoiDieuTri` →
`/api/ho-so-kham` (`xem=dieu-tri`, `thao_tac=ban-kham`) → `R/ho_so_kham.py` (`/ho-so-kham/{visit}/dieu-tri…`) → `S/dieu_tri_ban_kham.py`
(`doc_the`, `thao_tac`) → lệnh `S/service_execution_service.py` `bat_dau_tai_ban_kham` /
`xong_tai_ban_kham` / `huy_bat_dau_tai_ban_kham` / `hoan_tac_xong_tai_ban_kham` (lần làm
`noi_lam = BAN_KHAM`; chỉ định chưa có phòng thì xếp vào phòng bàn khám; cửa tiền
`cua_tien_ban_kham` = FinanceGate của phòng). Kê lại dịch vụ điều trị đã có trong lượt
không đẻ dòng thứ hai: `S/chi_dinh_service.py` (`chi_dinh_dieu_tri_dang_co`). Test:
`T/services/test_dieu_tri_ban_kham_db.py`, `T/unit/test_dieu_tri_ban_kham.py`, FT
`khoi-dieu-tri-boundary.test.mts`. Lịch sử sửa MỌI phiếu kết quả: trigger
`trg_form_instance_lich_su` → bảng chỉ thêm `form_instance_lich_su` (migration
`20261007630000`; test `T/services/test_form_instance_lich_su_db.py`).

**Liệu trình điều trị nhiều buổi — dải trong thẻ điều trị (08/10/2026, C1)** — đặc tả
`docs/KE-HOACH-LIEU-TRINH.md`. Dải "Buổi k/N · đã làm · đã trả · còn nợ", [Tạo liệu trình]
(ô "Lộ trình N buổi"), [Điều chỉnh] · [Dừng]/[Mở lại] · [Lịch sử sửa] · [Hoàn tác] · [Gỡ khỏi
liệu trình] · [Lập liệu trình mới] · chọn liệu trình (`can_chon`) · các buổi (ngày, nơi làm,
phiếu điều trị mở chỉ đọc) + lối "Chỉ đề xuất liệu trình (không làm hôm nay)":
`D/_lam-viec/phieu-kham/LieuTrinhThe.tsx` (vẽ trong `KhoiDieuTri.tsx`, nghe `lieu_trinh*`) →
`D/lib/lieu-trinh.ts` → `/api/lieu-trinh` (`xem=theo-luot|lich-su`, `thao_tac=tao|dieu-chinh|dung|
mo-lai|hoan-tac|gan|go`) → `R/lieu_trinh.py` → `S/lieu_trinh_service.py` (`theo_luot` trả số + nút
`nut`/`hoan_tac`/`dich_vu_de_xuat`; hàm thuần `nut_lieu_trinh`, `nut_chi_dinh`). Gắn / gỡ buổi tự
động, trạng thái, bất biến: Postgres (migration `20261008100000`). Test:
`T/services/test_lieu_trinh_db.py`, `T/services/test_lieu_trinh_giao_dien_db.py`, FT
`lieu-trinh-boundary.test.mts`.

**Lịch sử khám (popup, mọi lượt) + `/patient-list` mở đúng khung (07/10/2026)** — UI
`D/_lam-viec/LichSuKham.tsx` (Bàn khám qua `PhieuKhamLuot.tsx`, `D/patient-list/PatientListView.tsx`
`moLuot`, `D/customers/ThanhLuotKham.tsx`) → `/api/ho-so-kham?xem=lich-su` → `R/ho_so_kham.py`
`lich_su` → `S/lich_su_luot.py` (`LOAI_DU_LIEU_SQL` dùng chung với `S/danh_sach_benh_nhan_service.py`
`_LUOT_SQL`). Test: `T/services/test_lich_su_luot_db.py`, FT `lich-su-kham-boundary.test.mts`.

**Thai kỳ** — `D/ban-kham/ThaiKy.tsx` → `S/thai_ky_service.py`.

## 6. Chỉ định & chọn dịch vụ

**Bác sĩ/thư ký chỉ định, dịch vụ bắt buộc, chỉ định thêm** — UI
`D/_lam-viec/phieu-kham/DanhMucChiDinh.tsx`, `ChiDinhThuThuat.tsx` → `/api/luot-kham`
(`chi-dinh`) → `S/chi_dinh_service.py` `ChiDinhService.dat_chi_dinh`. Test:
`T/services/test_chi_dinh_db.py`, `T/services/test_chi_dinh_bat_buoc_db.py`.
Danh mục chọn được (thiếu dịch vụ nào thì xem đây): `S/phieu_kham_service.py`
`tham_chieu_that` ← hàm `danh_muc_dich_vu` — MỌI dịch vụ đang bán, kể cả phí
khám và thủ thuật của phiếu giấy, đều có ở mục C (C21, 02/10/2026; mig
`20261003700000_phi_kham_chi_dinh_duoc.sql`). Tiền khám không tính hai lần:
`S/phi_kham_service.py` `chan_trung_dich_vu_kham` (gọi từ `LuotKhamService._services`
và `PhiKhamService.chon`). Ô tìm + nút Tìm luôn hiện, danh mục mở sẵn
(`DanhMucChiDinh.tsx`);
ô tìm `timDanhMucChiDinh` (`src/dashboard/lib/phieu-kham.ts`). Test:
`T/services/test_danh_muc_dich_vu_chuan_db.py` (`test_moi_dich_vu_dang_ban_deu_chi_dinh_duoc`).

**Khách chọn làm dịch vụ nào (ở quầy)** — chỉ ở `D/thu-ngan/ChonDichVu.tsx` →
`S/service_selection_service.py` (`ServiceSelectionService`; luật ở hàm `plan`, `ap_lua_chon`).

## 7. Thu tiền · phiếu thu · phiếu hướng dẫn

**Vật tư khách mua thêm ở quầy thu dịch vụ (01/10 — C13: đầu dò Bio chọn nhanh, tìm tên, Mirena cần QL duyệt)** —
màn `D/thu-ngan/VatTuQuay.tsx` (khối "Mua thêm vật tư", chỉ quầy dịch vụ) → `S/vat_tu_service.py`
(`VatTuService.them` / `dat_so_luong` / `bo`, hàm thuần `ly_do_khong_ban`: giá 0 / chưa có giá = không bán).
Tiền vào hoá đơn DỊCH VỤ: dòng `vat_tu` ở `S/bill_service.py` (`_VAT_TU_SQL`, `ghep_dich_vu`), hiện ở quầy
qua `S/quay_thu_service.py` `dung_hoa_don_quay`, nợ khi check-out `S/cong_no_service.py` `loc_no_dich_vu`.
Dữ liệu: `service_price` nhóm `vat_tu` (+ cột `don_vi`, `can_ql_duyet`, `chon_nhanh`), dòng bán `luot_vat_tu`,
gợi ý dịch vụ→vật tư `vat_tu_goi_y` (mig 20261003000000; nạp lại: `SELECT * FROM dong_bo_vat_tu(false)`).
**Sửa giá / tắt bán / thêm hàng = việc DỮ LIỆU: quản lý làm trên `/cashier/dich-vu` (ngăn "Vật tư bán thêm
ở quầy thu", `D/cashier/VatTuBangGia.tsx`)** — không code. Hàng cần QL duyệt = cột `can_ql_duyet` (Mirena).
Test: `T/services/test_vat_tu_ban_them_db.py`, FT `quay-thu-vat-tu-boundary.test.mts`.

**Liệu trình ở quầy thu dịch vụ — trả trước k buổi (08/10/2026, C1)** — khối "Liệu trình" của
khách đang thu `D/thu-ngan/LieuTrinhQuay.tsx` ([Trả trước … buổi] / [Trả hết]) → `/api/lieu-trinh`
(`xem=quay`, `thao_tac=tra-truoc`) → `S/lieu_trinh_tien.py` (`quay`, `dat_tra_truoc`); [Bỏ] dòng trả
trước + chip "Buổi k/N · đã trả trước" trên chỉ định ở `D/thu-ngan/HoaDonMot.tsx`
(`thao_tac=bo-tra-truoc`). Dòng hoá đơn `source_type='lieu_trinh'`: `S/bill_service.py`; lượt CHỈ có
dòng trả trước vẫn lên bảng quầy: `S/cashier_board_service.py` `_SQL`; phiếu thu in "(liệu trình)":
`S/quay_thu_service.py` `phieu` + `D/print/phieu-thu/[id]/InPhieuThu.tsx`. Huỷ / hoàn tác lần thu trả
trước khi buổi đã làm bằng tiền ấy: CHẶN (#16) với câu `CAU_HUY_TRA_TRUOC_DA_DUNG`. Test:
`T/services/test_lieu_trinh_tien_db.py`, `T/services/test_lieu_trinh_giao_dien_db.py`.

**Màn thu, cái gì hiện ở quầy nào, "Đã nhận đủ"** — `/thu-ngan/dich-vu`,
`/thu-ngan/thuoc` (cùng `D/thu-ngan/QuayThuNgan.tsx`, prop `quay`). Bảng quầy:
`S/cashier_board_service.py` `CashierBoardService.board`; ghi tiền
`S/payment_service.py` `PaymentService.record_payment` (`QUYEN_THU`: loại tiền →
quyền thu). Test: `T/test_payment_service.py`, `T/services/test_cashier_board.py`,
FT `quay-thu-ngan-boundary.test.mts`.

**Thuốc và dịch vụ thu RIÊNG HẲN (01/10 — quầy thuốc không thu hộ tiền dịch vụ, và ngược lại)** —
luật máy chủ `S/payment_service.py` `kiem_quay` (409 `QUAY_KHAC_LOAI`; mọi lệnh thu / xác minh /
huỷ chờ / hoàn tác nhận `quay`); bảng thu lọc theo quầy ở `S/cashier_board_service.py`
(`board`, `giao_dich(kind=)`, `_lam_truoc_dich_vu`); sổ lịch sử `S/quay_thu_service.py`; báo
cáo cuối ngày lọc `loai` ở `S/bao_cao_cuoi_ngay_service.py`; Postgres ép dòng hoá đơn khớp loại
lần thu (mig 20261002800000). Màn: `D/thu-ngan/QuayThuNgan.tsx` (`quayThu`), `GiaoDich.tsx` (prop
`quay`). Quyền thu từng loại: `QUYEN_THU` trong `S/payment_service.py` + lego Thanh toán dịch vụ
/ Thu tiền thuốc (`/phan-quyen`). Test: `T/services/test_tach_thu_thuoc_dich_vu_db.py`, FT
`quay-thu-tach-thuoc-dich-vu-boundary.test.mts`. (Dịch vụ "XN thu hộ" của đối tác vẫn là tiền DỊCH VỤ,
thu ở quầy dịch vụ.)
Lượt Bán lẻ ở quầy thuốc: `D/pharmacy/BanLeThu.tsx` → `S/ban_le_service.py`.

**Thu trước – làm trước (tick "Làm trước – thu sau")** — công tắc: `/settings/day-noi`
(`thu_truoc_khi_lam`). Code: `S/lam_truoc_thu_sau.py`, cổng `S/finance_gate.py`
(`cua_lam`, `can_start`), ô tick `D/_lam-viec/OLamTruocThuSau.tsx`. Test:
`T/services/test_thu_truoc_lam_truoc_tick_db.py`, `T/services/test_lam_truoc_thu_sau_db.py`.

**Phiếu thu (80mm), phiếu hoàn, phiếu hướng dẫn phòng** — trang in
`src/dashboard/app/print/phieu-thu/[id]/InPhieuThu.tsx` (`?loai=thu|hoan|huong_dan`;
tiêu đề, chữ cố định, khổ 80mm ở đây). Tên cơ sở + địa chỉ đầu phiếu là DỮ LIỆU:
sửa ở `/settings/clinic-config` (cơ sở). Dữ liệu: `R/cashier.py:cashier_phieu` →
`S/quay_thu_service.py` `QuayThuService.phieu` / `phieu_cua_luot`, dòng phiếu hướng
dẫn `dong_huong_dan` (không tiền). Nút in: `D/thu-ngan/QuayThuNgan.tsx`, `D/thu-ngan/XepPhongDaThu.tsx`,
`D/_lam-viec/OLamTruocThuSau.tsx`. Test: `T/unit/test_quay_thu.py`, `T/services/test_phieu_huong_dan_db.py`.

**Thu nhiều hình thức (TM + CK), ảnh chuyển khoản, hoàn tác lần thu** (01/10) —
luật chia `S/phan_thu.py` (thuần; QR cũ = CK), ghi `PaymentService.record_payment(phan=)`
+ `_ghi_phan` → sổ `payment_cycle_phan` (Postgres ép tổng, mig 20261002300000), đọc qua
hàm SQL `phan_thu_hieu_luc`; hoàn tác `PaymentService.hoan_tac`; ảnh
`S/anh_chuyen_khoan_service.py`. Màn: `D/thu-ngan/ChiaHinhThuc.tsx`, `NutHoanTac.tsx`,
`AnhChuyenKhoan.tsx`, tên hiển thị `src/dashboard/lib/hinh-thuc-thu.ts`; phiếu in mỗi
phần một dòng (`InPhieuThu.tsx`). Test: `T/unit/test_phan_thu.py`,
`T/services/test_thu_nhieu_hinh_thuc_db.py`.

**Mua thêm vật tư / đầu dò** (khối "Món kèm" cũ đã gỡ 02/10, C17; dòng `luot_phu_thu` cũ
vẫn đọc ở `bill_service._PHU_THU_SQL`) — `D/thu-ngan/VatTuQuay.tsx`. **Thanh ngày quầy thu
(xem lại ngày cũ)** — `D/thu-ngan/TabThuNgan.tsx` + `S/cashier_board_service.py::khoang_ngay_xem`;
test `T/services/test_thu_ngan_thanh_ngay_db.py`, `D/tests/quay-thu-thanh-ngay-boundary.test.mts`.
**Hoàn tiền, đổi hình thức TM/CK (chia được), huỷ phiếu** — `D/thu-ngan/HoanTien.tsx` → `S/hoan_tien_service.py`;
`D/thu-ngan/DoiHinhThuc.tsx` → `S/doi_hinh_thuc_service.py`; huỷ →
`PaymentService.void_payment`. Test: `T/services/test_doi_hinh_thuc_db.py`.

## 8. Xếp phòng · đổi phòng · chọn bác sĩ trong phòng

- Tự xếp (dây H4) + gợi ý + xếp tay: `S/service_routing_service.py`
  `ServiceRoutingService` (`assign`, `recommend`, `dat_phong_du_kien`); khối chọn
  phòng dùng chung `D/_lam-viec/DoiPhong.tsx` (quầy thu, trưởng ca, bàn khám).
- Chọn bác sĩ trong phòng ≥2 bác sĩ: `S/lan_bac_si.py`, `D/_lam-viec/ChonBacSiLam.tsx`;
  test `T/services/test_chon_bac_si_trong_phong_db.py`.
- Chuyển phòng từng chỉ định (trưởng ca): `D/truong-ca/ChiDinhCuaBacSi.tsx`.
- Test chung: `T/services/test_service_routing_db.py`, `T/services/test_nguon_xep_phong_db.py`.

## 9. Phòng dịch vụ · thực hiện · kết quả · tệp

- Màn: `/phong`, `/phong/[ma]` (`D/phong/[ma]/PhongDichVu.tsx`, khách đã trả chưa
  xếp `ChuaXepPhong.tsx`). Bắt đầu/Hoàn tất/Không làm/Gián đoạn:
  `S/service_execution_service.py` `ServiceExecutionService` (`bat_dau`, `xong`,
  `khong_lam`, `gian_doan`). Test: `T/services/test_service_execution_db.py`.
- Điền phiếu kết quả: `D/_lam-viec/PhieuKetQua.tsx` → `/api/phieu` →
  `S/form_engine_service.py` (`luu_nhap`, `hoan_tat`, `mo_sua`).
- Tệp ảnh/PDF: `D/_lam-viec/KhungTep.tsx` → `/api/cskh/ket-qua` →
  `S/tep_ket_qua_service.py` (quyền xoá/khôi phục `xoa_duoc`, `khoi_phuc_duoc`);
  tệp nằm `/mnt/viettel-cfs`. Test: `T/unit/test_kho_tep.py`, `T/services/test_xac_nhan_tep_ket_qua_db.py`.

## 10. Thuốc · quầy thuốc · cấp thuốc

- Cấp thuốc theo lượt, chọn lô, giao: `/pharmacy` (`D/pharmacy/PharmacyBoard.tsx`,
  `DongThuoc.tsx`) → `/api/pharmacy/[action]` → `S/pharmacy_service.py`
  (`cap_phat`, `xac_dinh_thuoc`, `khai_so_luong_mua`, `chot`); màn đọc
  `S/ban_thuoc_service.py` `man_nha_thuoc`. Đơn bán ở quầy: `S/quay_thuoc_service.py`
  `QuayThuocService`. Test: `T/services/test_quay_thuoc_db.py`,
  `T/services/test_giao_thuoc_khong_lo_db.py`, FT `nha-thuoc-phan-lo-boundary.test.mts`.

- **Bác sĩ quên số lượng thuốc → quầy thu thuốc điền (C14, 01/10)** — màn `/thu-ngan/thuoc`,
  khối `D/thu-ngan/ChinhDonQuay.tsx` (dòng tô nổi + ô Số lượng) → `S/quay_thuoc_service.py`
  `QuayThuocService.doi_so_luong` / `_dien_so_luong` (không trần — **C19 02/10: quầy đặt số
  TUỲ Ý, tăng hay giảm, kể cả dòng bác sĩ đã ghi số**; dấu người + lúc ở
  `prescription.so_luong_dien_boi/_luc`, số bác sĩ kê gốc ở `so_luong_ke_goc`; sự kiện
  `DIEN_SO_LUONG` / `SUA_SO_LUONG`; lưới DB: trigger `prescription_dinh_chinh_guard`, mig
  `20261003500000`; mốc "lấy bớt" của `medicine.declined` = số kê gốc,
  `payment_service._phat_thuoc_bi_bo`-nhóm). Test: `T/services/test_quay_thuoc_dien_so_luong_db.py` (`test_c19_*`). Câu báo + loại dòng
  khỏi tổng: `S/bill_service.py` `THIEU_SO_LUONG`, `ghep_thuoc`. Nhãn "SL do thu ngân điền"
  ở màn kê đơn: `D/_lam-viec/phieu-kham/DonThuocPhieu.tsx`, gộp tự động
  `D/_lam-viec/phieu-kham/PhieuKhamLuot.tsx` + `lib/phieu-kham.ts` `gopSoLuongQuayDien`;
  đọc đơn `S/phieu_kham_service.py` `doc_don_thuoc`. Lượt đã ký vẫn điền được: migration
  `20261003100000_quay_thuoc_dien_so_luong.sql` (trigger `prescription_dinh_chinh_guard`).
  Test: `T/services/test_quay_thuoc_dien_so_luong_db.py`.

## 11. Check-out · trạng thái khách · hành trình

**Check-out (đóng lượt, khách về)** — `/reception/checkout` (`D/reception/checkout/CheckoutBoard.tsx`),
nút dùng chung `D/_lam-viec/NutCheckOut.tsx` → `S/checkout_service.py`
`CheckoutService` (`readiness`, `close`; việc còn dở chặn/nhắc ở hàm `build_blockers`). Test:
`T/services/test_checkout_blockers.py`, `T/unit/test_checkout_trang_thai_kham.py`.

**Nhãn trạng thái lịch/lượt trên mọi màn ("Đã về", "Đang khám"…)** — MỘT hàm
`src/clinicai/core/trang_thai_lich.py` `trang_thai_hien_thi`; trạng thái khám suy từ
phiên `S/checkout_service.py` `trang_thai_kham`. Check-out đổi lịch sang COMPLETED:
migration `supabase/migrations/20261001230100_lich_cua_luot_da_ve_dong_bo.sql`.
Test: `T/unit/test_trang_thai_hien_thi.py`, `T/services/test_thu_thuat_nhu_kham_thuong_db.py`
(`test_check_out_moi_man_cung_noi_da_ve`), `T/services/test_dong_bo_hai_cot_trang_thai_db.py`.

**Hành trình khách (đang ở / tiếp theo / dòng thời gian)** — màn `/hanh-trinh`,
popup `D/_lam-viec/HanhTrinhKhach.tsx`; máy chủ `S/hanh_trinh_khach_service.py`,
`S/bang_hanh_trinh_service.py`; luật THỨ TỰ khách đi = consumer
`src/clinicai/events/consumers/hanh_trinh.py`. Test: `T/services/test_hanh_trinh_khach_db.py`,
`T/services/test_hanh_trinh_db.py`, `npm run test:hanh-trinh`.

## 12. CSKH · hẹn tái khám

- Màn chuẩn `/customers` (`D/customers/CustomersView.tsx`, `VungLamViecKhach.tsx`,
  `HanhDongTrangThai.tsx`) → `S/cskh_service.py`, `S/danh_sach_khach_cskh.py`; ghi
  chăm sóc `S/tuong_tac_cskh_service.py`. Test: `T/unit/test_so_tuong_tac_cskh.py`.
- Hẹn tái khám / nhắc gọi: `/nhac-tai-kham` (`D/nhac-tai-kham/ViecGoiNhac.tsx`),
  `D/_lam-viec/ViecTaiKham.tsx` → `S/hen_tai_kham_service.py`, `S/recall_service.py`;
  chuông tới hạn = consumer `src/clinicai/events/consumers/nhac_tai_kham.py`. Test:
  `T/services/test_hen_tai_kham_db.py`, `T/unit/test_recall_service.py`.
- **Liệu trình — CSKH + khung khách (C2, 08/10):** tab "Liệu trình" của `/nhac-tai-kham`
  (`D/nhac-tai-kham/TabNhacTaiKham.tsx`, `LieuTrinhCskh.tsx`: "Đề xuất chưa đăng ký" /
  "Đang dở, quá X ngày"); khối "Liệu trình" của khung khách `D/_lam-viec/KhungKhach.tsx`;
  dòng + nút dùng chung `D/_lam-viec/LieuTrinhKhach.tsx` (Đăng ký 1/N/số khác · Dừng ·
  Mở lại · Hoàn tác · Lịch sử sửa) → `/api/cskh/lieu-trinh` (`?loai=` / `?khach=`),
  `/api/cskh/lieu-trinh/[id]` → `S/lieu_trinh_service.py` (`cskh`, `theo_khach`,
  `dang_ky`, `dung`, `mo_lai`, `hoan_tac`, `lich_su`). [Đặt lịch buổi kế] = bộ đặt lịch
  sẵn có `D/_lam-viec/DatLichBuoiKe.tsx` → `D/customers/DatLichModal.tsx` (khoá
  `service_type_id` máy chủ trả). Chữ: `lib/lieu-trinh.ts`. Test:
  `T/services/test_lieu_trinh_db.py`, `T/services/test_lieu_trinh_c2_db.py`, FT
  `lieu-trinh-c2-boundary.test.mts`.
- **Liệu trình "Sắp hết lộ trình" (08/10):** danh sách ĐẦU tab Liệu trình
  (`LieuTrinhCskh.tsx`, `?loai=sap_het`) + chip lý do ở khung khách; luật + ngưỡng
  (`SAP_HET_CON_TOI_DA` = 1) ở `S/lieu_trinh_service.py` `ly_do_sap_het` / `moc_sap_het`;
  [Đã xử lý] = `da_xu_ly_sap_het` → dòng sổ `tuong_tac_cskh` (`trang_thai_ma` = mốc,
  hoàn tác bằng `/api/cskh/tuong-tac/[id]/hoan-tac` sẵn có); [Thêm buổi] = `dang-ky`
  với số buổi mới (`lib/lieu-trinh-cskh.ts` `soBuoiSauKhiThem`); [Ghi cuộc gọi] = POST
  `/api/cskh/tuong-tac`. Chuông CSKH khi buổi xong: consumer
  `src/clinicai/events/consumers/lieu_trinh_sap_het.py` (nghe `service.completed`,
  `nguon = lieu_trinh_sap_het`, một mốc một chuông). Test:
  `T/services/test_lieu_trinh_sap_het_db.py`, FT `lieu-trinh-sap-het-boundary.test.mts`.
- **Nhãn đếm lượt "Lượt khám n" / "Buổi k/N" (08/10, mọi màn):** máy chủ đếm ở
  `S/nhan_luot.py` (`gan_nhan` thuần + `doc_nhan_luot` một câu SQL), gắn `nhan_luot` vào
  dữ liệu của `S/man_khach_hang_service.py` (`/customers` — kèm giờ thật `den_luc` /
  `kham_xong_luc` / `ve_luc`), `S/lich_su_luot.py` (popup Lịch sử khám),
  `S/danh_sach_benh_nhan_service.py` (`/patient-list`), `S/clinical_form_service.py`
  `lich_su_kham` (Bàn khám `LuotKhamTruoc`), `S/clinical_record_service.py`
  `lich_su_cho_ho_so` (`tasks/ClinicalRecordForm`). TSX chỉ vẽ (`lib/nhan-luot.ts`:
  `chuNhanLuot`, `gioLuot`). Test: `T/services/test_nhan_luot_db.py`, FT
  `nhan-luot-boundary.test.mts`.
- **Chip liệu trình (phòng · tiếp đón · bàn khám):** hook `D/_lam-viec/dung-chip-lieu-trinh.ts`
  (MỘT lần gọi `/api/lieu-trinh/chip?luot=` mỗi màn) → `S/lieu_trinh_service.py` `chip`;
  vẽ ở `D/phong/[ma]/KhungChiDinhKhach.tsx` · `SapDenPhong.tsx` · `HangChoKhachPhong.tsx`,
  `D/reception/queue/QueueBoard.tsx`, `D/ban-kham/BanKham.tsx` (`Nhom`). Chỉ thêm chữ —
  không đổi lọc / đếm / sắp xếp. Bản in "Liệu trình: buổi k/N":
  `src/clinicai/phieu_kham/ket_qua_chi_dinh.py` (`lieu_trinh`) →
  `src/dashboard/app/print/phieu-kham/[visitId]/InPhieuKham.tsx` `DieuTriIn`.
- **Dọn khách thử có liệu trình:** `don_khach_thu` bản mới nhất ở mig
  `20261008200000_don_khach_thu_lieu_trinh.sql` (danh sách bảng khách + cột nối
  `lieu_trinh_id`) — bảng có dữ liệu khách mới thì CHÉP bản này, thêm tên bảng.
- **Bác sĩ đặt LỊCH HẸN THẬT ngay ở ô Ngày tái khám (02/10):** khung
  `D/_lam-viec/phieu-kham/DatLichTaiKham.tsx` (bảng `D/appointments/BangBacSiTuan.tsx`
  chế độ `chiNgay`) → `/api/phieu-kham` (`dat-lich-tai-kham` / `huy-lich-tai-kham`)
  → `S/lich_tai_kham_service.py` `LichTaiKhamService` (qua `BookingService.create`);
  cột `appointment.hen_tu_visit_id` + trigger không đóng việc gọi của chính lượt:
  mig `20261003720000_lich_hen_tu_phieu_kham.sql`. Test:
  `T/services/test_lich_tai_kham_tu_phieu_db.py`.
- **Lịch sử khám cũ từ Notion (05/10):** khối `D/patient-list/LichSuNotion.tsx` trong
  hồ sơ khách `/patient-list` → `/api/lich-su-notion` (`?khach=` / `?luot=`, tệp PDF
  `/api/lich-su-notion/tep`) → `S/lich_su_notion_service.py` (đọc schema
  `lich_su_notion`, mig `20261005100000_lich_su_notion.sql`). Nạp / nạp lại / gỡ:
  `S/nhap_lich_su_notion.py`, `scripts/nhap-lich-su-notion.sh`,
  `scripts/hoan-tac-lich-su-notion.sql` — xem `docs/NHAP-LICH-SU-NOTION.md`. Test:
  `T/services/test_lich_su_notion_db.py`.
- **Danh sách bệnh nhân `/patient-list` — tìm, tab, xếp, phân trang (06/10):** mọi luật
  ở `S/danh_sach_benh_nhan_service.py` (`_CO_SO`: số lượt / đang mở / mốc xếp / khớp ô
  tìm; `MOT_TRANG` = 50; `LOC_THEO_SO_LUOT` = tab) qua `GET /api/v1/patients/danh-sach
  ?trang&q&loc&sap&chon`; màn `D/patient-list/page.tsx` (đọc URL) +
  `PatientListView.tsx` (ô tìm debounce, tab, chọn khách ghi `?chon=`); thanh số trang
  `src/dashboard/components/ui/ThanhSoTrang.tsx` + `src/dashboard/lib/so-trang.ts`. Test:
  `T/services/test_danh_sach_benh_nhan_phan_trang_db.py`,
  `T/unit/test_danh_sach_benh_nhan.py`, `lib/so-trang.test.mts` (`npm run test:so-trang`).

## 13. Lịch làm việc · phòng · tầng

- Trên màn: `/schedule` (Lịch làm việc — xếp ca, áp tuần, đổi người trong ca); lịch
  của phòng sửa tại chỗ ở `/settings/clinic-config`.
- Code: `D/schedule/` (`TabLichLamViec.tsx`, `ApDungTuan.tsx`, `DoiNguoiTrongCa.tsx`)
  → `/api/roster` → `S/config_service.py` `RosterService` (`apply_week`,
  `add_shift`, `decide`); lịch phòng `S/lich_phong_service.py` `LichPhongService`.
  Nạp cả tuần từ bảng: `scripts/ap-lich-tuan-2809.py`. Test:
  `T/unit/test_lich_phong.py`, `T/services/test_doi_nguoi_trong_ca_db.py`.
- **Ô chọn nhân viên khi xếp ca (09/10):** ô tìm + nhóm theo vai xổ ra/thu vào —
  `D/schedule/ChonNhanVien.tsx`; lọc/chia nhóm ở `src/dashboard/lib/chon-nhan-vien.ts`
  (test `chon-nhan-vien.test.mts`). Ai được xếp vào ô vẫn lọc theo ma trận
  `vai_duoc_vao_tram` trong `RosterRegisterTable.tsx` (`nhanVienHopLe`).
- **Chữ cột Phòng / Tầng của vị trí không gắn phòng** (Trưởng ca → "Quản lý ca
  khám"): trên màn `/settings/day-noi` → Vị trí trực → "Chữ cột Phòng/Tầng".
  Code `S/day_noi_service.py` `sua_vi_tri` (`phong`, `tang`); bảng lịch đọc ở
  `R/identity.py` `vi_tri_hom_nay` (phòng thật trước, chữ sau). Test
  `T/services/test_vi_tri_chu_phong_db.py`.
- **Lịch sử thay đổi lịch trực (06/10):** khối "Lịch sử thay đổi" ở `/schedule`
  (`D/schedule/PhienBanLich.tsx`, tô màu ô trong `D/home/WorkRosterTable.tsx`
  `MAU_THAY_DOI`) → `GET /api/v1/roster/phien-ban` → `S/lich_truc_phien_ban_service.py`
  (`dung_phien_ban`, `so_sanh`, `LichTrucPhienBanService.xem`). Ghi bằng trigger
  (mig `20261006300000_lich_truc_phien_ban.sql`); lối ghi lịch MỚI phải bọc câu ghi
  bằng `giao_dich_lich_truc(conn, staff_id)` (hoặc `dat_nguoi_bam` trong giao dịch
  sẵn có) để sổ có tên người sửa. Test: `T/unit/test_lich_truc_phien_ban.py`,
  `T/services/test_lich_truc_phien_ban_db.py`.

## 14. Quyền · lego · tài khoản

- Trên màn: bật/tắt lego, kỹ năng, nhóm quyền mẫu → `/phan-quyen`; nhân sự →
  `/nhan-su`; tài khoản đăng nhập → `/settings/tai-khoan`, `/settings/new-user`.
- Code: danh mục lego/khối/quyền `src/clinicai/permissions/catalogue.py` (`MAN`,
  `KHOI`, `PRESET`); hỏi quyền `src/clinicai/permissions/can.py`, cổng router
  `src/clinicai/permissions/cua_quyen.py`; ghi quyền `S/permission_service.py`;
  thanh bên `D/nav-items.ts` + `src/dashboard/lib/roles.ts` (`NAV_ROLES`, `NAV_QUYEN`).
  Tạo nhiều tài khoản: `scripts/tao-tai-khoan-nhan-su.py`.
- Test: `T/services/test_lego_21_db.py`, `T/services/test_permission_db.py`,
  `T/services/test_mo_full_lego_db.py`, FT `sidebar-theo-quyen-boundary.test.mts`.
- Luật: ẩn nút không phải bảo mật — mọi lệnh kiểm lại quyền ở backend.

## 15. In ấn (A4, 80mm)

- Trang in: `src/dashboard/app/print/` — phiếu khám `phieu-kham/[visitId]/InPhieuKham.tsx`,
  kết quả `ket-qua/[orderId]/InKetQua.tsx`, mọi kết quả của lượt `ket-qua-luot/`,
  hoá đơn thuốc `hoa-don-thuoc/`, phiếu thu 80mm `phieu-thu/[id]/InPhieuThu.tsx`.
  Khổ A4 chung: `src/dashboard/app/print/KieuInA4.tsx`; khối dùng chung `KhoiIn.tsx`.
- Luật đã cắn (memory 30/09): **chữ ký bác sĩ LUÔN cuối cùng, sau cả trang ảnh;
  ảnh không bị cắt** — kiểm bằng in ra PDF thật. Test: FT `trang-in-du-kho-boundary.test.mts`.
- Tên người ký: `S/bac_si_ky.py` (chỉ tài khoản vai bác sĩ).

## 16. Sự kiện · realtime

- Danh mục sự kiện (tên, payload, ai nghe): `src/clinicai/events/catalogue.py`;
  phát `src/clinicai/events/emit.py`; worker `src/clinicai/events/worker.py`;
  hẹn giờ `src/clinicai/events/hen_gio.py`; bên nghe `src/clinicai/events/consumers/`
  (bảng đầy đủ: mục 4 của `docs/BAN-DO-CODE.md`). Test: `T/unit/test_danh_muc_su_kien.py`,
  `T/services/test_event_worker_db.py`.
- Màn tự cập nhật: Postgres NOTIFY → `R/events.py` (SSE `/api/events/stream`) →
  `D/RealtimeRefresher.tsx` → hook `D/dung-nghe-bang.ts` (`useNgheBang`).
- Chuông báo ai: dữ liệu ở `/settings/day-noi` (khối chuông); code consumer
  `src/clinicai/events/consumers/chuong.py`.

## 17. Vận hành (deploy, sao lưu, lỗi)

- Deploy/sao lưu/migration: đúng thứ tự trong skill `len-prod` (`.claude/skills/len-prod/SKILL.md`);
  `scripts/deploy-backend.sh`, `scripts/backup-db.sh`, `scripts/apply-pending-migrations.sh`,
  sổ tay `docs/VAN-HANH-MAY-CHU.md`. CI: `scripts/ci-may.sh`; chạy test: `docs/CHAY-TEST.md`.
- Lỗi & cảnh báo: màn `/ops` (tab Lỗi & cảnh báo, Nhật ký vận hành) → kho lỗi
  `S/kho_loi.py`, canh gác `S/canh_gac.py`, nhật ký `S/nhat_ky_van_hanh.py`.
- Sao lưu kéo về Mac: `cat ~/Projects/ClinicAI-Backups/TRANG-THAI.txt` phải "BÌNH THƯỜNG".
- Lịch sử Notion: schema `lich_su_notion` NGOÀI `public` — bản 15 phút không lấy; bản
  đêm lấy thành `*_lich_su_notion.sql.gz` (`BACKUP_LICH_SU_NOTION=1` ở `clinicai-backup.service`).

## 18. Giao diện chung

- Hiến pháp giao diện: `DESIGN.md` (5 cỡ chữ, lưới 4px, nút, bảng, responsive);
  token màu `src/dashboard/app/globals.css`; thành phần `src/dashboard/components/ui/`
  (`Button.tsx`, `Chip.tsx`, `HopXacNhan.tsx`, `ThanhNgay.tsx`, `SoLuot.tsx`…).
- Khung: `D/Shell.tsx`, thanh bên `D/Nav.tsx` + `D/nav-items.ts`, đầu trang
  `D/GlobalHeader.tsx`. Ratchet px: FT `px-tu-che-ratchet-boundary.test.mts`.
- **Sửa .tsx và thấy ngay (không dựng lại):** đã chạy `scripts/dev-up.sh` một lần →
  `scripts/dev-giao-dien.sh` (thay `next start` bằng `next dev` ở cổng 3100, cùng bộ
  biến môi trường; lưu tệp là trang tự đổi). Xong: Ctrl+C rồi
  `scripts/dev-nap-lai.sh web` để về bản dựng như prod. Muốn giữ 3100:
  `WEB_PORT=3190 scripts/dev-giao-dien.sh`. `next dev` chỉ không hydrate dưới
  trình duyệt HEADLESS — Chrome/Safari thật chạy bình thường.
