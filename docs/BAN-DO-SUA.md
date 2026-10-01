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

**Giá dịch vụ · thêm/bớt/đổi tên dịch vụ trong bảng giá**
- Trên màn: `/cashier/dich-vu` (Bảng giá dịch vụ). Lưu là dùng ngay cho lượt mới.
- Code: `D/cashier/CashierView.tsx` → `/api/service-price` → `R/config.py`
  (`add_price`, `update_price`, `remove_price`) → `S/config_service.py`
  `PriceListService` (`add/update/remove/list`). Bảng `service_price`.
- Test: `T/services/test_danh_muc_kiotviet_db.py`, `T/services/test_gia_thuoc_hai_nguon_khop_db.py`.

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
→ `R/luot_kham.py` → `S/phi_kham_service.py` `PhiKhamService` (`doc`, `chon`).

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

**Hành vi đặt / đổi / huỷ lịch, chặn trùng, ngoài khung ca**
- Màn: `/appointments` (`D/appointments/BookingHub.tsx`), popover đổi lịch
  `D/_lam-viec/DoiLichTaiCho.tsx`, huỷ `D/_lam-viec/ThaoTacLichTaiCho.tsx`.
- Code: `S/booking_service.py` `BookingService` (`create`, `apply_action`,
  `doi_lich_nhanh`, `doi_dich_vu_kham`); sức chứa `S/capacity_service.py`; giữ chỗ
  `S/slot_hold_service.py`; đọc lưới ngày `S/man_dat_lich_doc.py`, `S/lich_hen_doc.py`.
- Test: `T/test_booking_service.py`, `T/services/test_capacity_roster_gate.py`. Luật:
  SO-LUAT 6.5 (sức chứa là ghế của MỘT bác sĩ, kiểm lúc xếp bác sĩ).

## 4. Tiếp đón · check-in · sinh hiệu

**Check-in / Không đến / Hoàn tác** — màn duy nhất `/reception/queue`
(`D/reception/queue/QueueBoard.tsx`, bảng `D/home/WeeklyAppointmentsTable.tsx`,
nút `src/dashboard/components/ui/NutCheckIn.tsx`). Code: `S/luot_kham_service.py`
`LuotKhamService.check_in` + `xep_sau_check_in` (khách đi đâu sau check-in),
`S/tiep_don_service.py` `TiepDonService`. Test: `T/services/test_check_in_lai_sau_hoan_tac_db.py`,
`T/unit/test_tiep_don_service.py`.

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

**Thai kỳ** — `D/ban-kham/ThaiKy.tsx` → `S/thai_ky_service.py`.

## 6. Chỉ định & chọn dịch vụ

**Bác sĩ/thư ký chỉ định, dịch vụ bắt buộc, chỉ định thêm** — UI
`D/_lam-viec/phieu-kham/DanhMucChiDinh.tsx`, `ChiDinhThuThuat.tsx` → `/api/luot-kham`
(`chi-dinh`) → `S/chi_dinh_service.py` `ChiDinhService.dat_chi_dinh`. Test:
`T/services/test_chi_dinh_db.py`, `T/services/test_chi_dinh_bat_buoc_db.py`.

**Khách chọn làm dịch vụ nào (ở quầy)** — chỉ ở `D/thu-ngan/ChonDichVu.tsx` →
`S/service_selection_service.py` (`ServiceSelectionService`; luật ở hàm `plan`, `ap_lua_chon`).

## 7. Thu tiền · phiếu thu · phiếu hướng dẫn

**Màn thu, cái gì hiện ở quầy nào, "Đã nhận đủ"** — `/thu-ngan/dich-vu`,
`/thu-ngan/thuoc` (cùng `D/thu-ngan/QuayThuNgan.tsx`, prop `quay`). Bảng quầy:
`S/cashier_board_service.py` `CashierBoardService.board`; ghi tiền
`S/payment_service.py` `PaymentService.record_payment` (`QUYEN_THU`: loại tiền →
quyền thu). Test: `T/test_payment_service.py`, `T/services/test_cashier_board.py`,
FT `quay-thu-ngan-boundary.test.mts`.

**Quầy thuốc thu nợ dịch vụ (và ngược lại)** — máy chủ đã trả `no_khac` cho mọi
quầy: `S/cashier_board_service.py` `_lam_truoc_va_no_khac`; màn hiện ở
`D/thu-ngan/QuayThuNgan.tsx` (`no_khac`). Quyền thu từng loại: `QUYEN_THU` trong
`S/payment_service.py` + lego Thanh toán dịch vụ / Thu tiền thuốc (`/phan-quyen`).
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

**Phụ thu, hoàn tiền, đổi hình thức TM/CK/QR, huỷ phiếu** — `D/thu-ngan/PhuThuKem.tsx`
→ `S/phu_thu_service.py`; `D/thu-ngan/HoanTien.tsx` → `S/hoan_tien_service.py`;
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

## 13. Lịch làm việc · phòng · tầng

- Trên màn: `/schedule` (Lịch làm việc — xếp ca, áp tuần, đổi người trong ca); lịch
  của phòng sửa tại chỗ ở `/settings/clinic-config`.
- Code: `D/schedule/` (`TabLichLamViec.tsx`, `ApDungTuan.tsx`, `DoiNguoiTrongCa.tsx`)
  → `/api/roster` → `S/config_service.py` `RosterService` (`apply_week`,
  `add_shift`, `decide`); lịch phòng `S/lich_phong_service.py` `LichPhongService`.
  Nạp cả tuần từ bảng: `scripts/ap-lich-tuan-2809.py`. Test:
  `T/unit/test_lich_phong.py`, `T/services/test_doi_nguoi_trong_ca_db.py`.

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

- Deploy/sao lưu/migration: đúng thứ tự trong `CLAUDE.md` mục "Đưa code lên máy chủ";
  `scripts/deploy-backend.sh`, `scripts/backup-db.sh`, `scripts/apply-pending-migrations.sh`,
  sổ tay `docs/VAN-HANH-MAY-CHU.md`. CI: `scripts/ci-may.sh`; chạy test: `docs/CHAY-TEST.md`.
- Lỗi & cảnh báo: màn `/ops` (tab Lỗi & cảnh báo, Nhật ký vận hành) → kho lỗi
  `S/kho_loi.py`, canh gác `S/canh_gac.py`, nhật ký `S/nhat_ky_van_hanh.py`.
- Sao lưu kéo về Mac: `cat ~/Projects/ClinicAI-Backups/TRANG-THAI.txt` phải "BÌNH THƯỜNG".

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
