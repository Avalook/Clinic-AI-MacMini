# BẢN ĐỒ CODE — màn → API → router → service → test

> Sinh bởi `scripts/ban-do-code.py` lúc 2026-10-17 15:04. **Đừng sửa tay** —
> chạy `python3 scripts/ban-do-code.py` để sinh lại; CI (`--kiem`, job backend
> của `scripts/ci-may.sh`) đỏ khi tệp này lệch code.

Tra theo việc trước ở `docs/BAN-DO-SUA.md`; tệp này là chuỗi file chi tiết.
Tìm nhanh: tìm chuỗi route (vd `/thu-ngan/dich-vu`), tên route.ts hay tên
service. **`?`** = phân tích tĩnh không suy được — mở file mà xem, đừng tin là
không có. Thành phần đi tối đa 3 tầng import (liệt kê 2 tầng); bỏ `components/ui` và
tệp mà hơn 25% số màn cùng import (dùng chung): `app/(dashboard)/dung-nghe-bang.ts`, `lib/backend-proxy.ts`, `lib/booking-policy.ts`, `lib/clinic-session.ts`, `lib/co-so.ts`, `lib/current-staff.ts`, `lib/datetime.ts`, `lib/kiem-phien-tai-cho.ts`, `lib/quyen-cua-toi.ts`, `lib/roles.ts`, `lib/roster.ts`, `lib/supabase-cookie.ts`, `lib/supabase-server.ts`.

Mục lục: 1. Màn · 2. API Next → backend · 3. Service → màn · 4. Sự kiện (consumer) · 5. Bảng → migration

## 1. Màn (90)
### `/`
- page: `src/dashboard/app/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/appointments` — Đặt lịch
- page: `src/dashboard/app/(dashboard)/appointments/page.tsx` · quyền: lego `dat_lich` (Đặt lịch · mặc định: CSKH, lễ tân)
- thành phần: BookingHub.tsx, app/(dashboard)/patients/new/NewPatientForm.tsx, app/(dashboard)/BookingPolicyContext.tsx, app/(dashboard)/DateField.tsx, app/(dashboard)/QuyenContext.tsx, app/(dashboard)/SearchSelect.tsx, app/(dashboard)/_lam-viec/ChonDichVuDatLich.tsx, BangBacSiTuan.tsx (+8)
- gọi API Next: `/api/appointments/tim-khach`, `/api/appointments/slot-hold`, `/api/appointments/cho-trong-tuan`, `/api/appointments/quote`, `/api/cskh-action`, `/api/wards`, `/api/patients/check-duplicate`, `/api/appointments/doi-lich-nhanh`, `/api/appointments/service-history`, `/api/catalog/dich-vu-dat-lich` (+5)
- gọi thẳng backend (server): `/api/v1/appointments/hub-dat-lich${maKhach`, `/api/v1/staff/bac-si-dat-duoc`
- service: man_dat_lich_doc.{tim_khach, hub_dat_lich} · SlotHoldService.{release, active, hold} · capacity_service · CapacityService.quote · CskhService.record_action · MPIService.find_candidates (+7 service)
- test: test_clinical_cluster.py, test_capacity_roster_gate.py, test_lich_hen_doc_db.py, test_lich_truc_phien_ban_db.py, test_pham_vi_vi_tri_lich_truc.py (+21)

### `/appointments/cho-xep-bac-si` — Chờ xếp bác sĩ
- page: `src/dashboard/app/(dashboard)/appointments/cho-xep-bac-si/page.tsx` · quyền: lego `dat_lich` (Đặt lịch · mặc định: CSKH, lễ tân)
- thành phần: HangChoView.tsx
- gọi API Next: `/api/cskh/tuong-tac`, `/api/appointments`
- gọi thẳng backend (server): `/api/v1/appointments/cho-xep-bac-si`, `/api/v1/staff/bac-si-dat-duoc`
- service: TuongTacCskhService.{lich_su, ghi} · lich_hen_doc.{lich_sap_toi, lich_trong_ngay} · BookingService.{create, apply_action} · lich_truc_co_so
- test: test_so_tuong_tac_cskh.py, test_lich_hen_doc_db.py, test_booking_service.py, test_chan_dat_ngoai_khung_ca.py, test_huy_lich_tai_cho_db.py (+2)

### `/audit-log` — Lịch sử thao tác
- page: `src/dashboard/app/(dashboard)/audit-log/page.tsx` · quyền: lego `van_hanh` (Vận hành hệ thống · mặc định: Quản lý)
- thành phần: AuditLogBoard.tsx, types.ts
- gọi thẳng backend (server): `/api/v1/audit/events`
- service: AuditLogService.events

### `/ban-kham` — Bàn khám
- page: `src/dashboard/app/(dashboard)/ban-kham/page.tsx` · quyền: lego `ban_kham` (Bàn khám · mặc định: Bác sĩ chính + Thư ký y khoa)
- thành phần: BanKham.tsx, app/(dashboard)/_lam-viec/DoiPhong.tsx, app/(dashboard)/_lam-viec/KhungTep.tsx, app/(dashboard)/_lam-viec/XemLuot.tsx, app/(dashboard)/_lam-viec/XemPhieuKetQua.tsx, app/(dashboard)/_lam-viec/api.ts, app/(dashboard)/_lam-viec/dung-chip-lieu-trinh.ts, app/(dashboard)/_lam-viec/dung-ngay-xem.ts (+11)
- gọi API Next: `/api/thai-ky`, `/api/clinical-forms/history`, `/api/clinical-form/andrology-review`, `/api/clinical-record`, `/api/catalog`, `/api/clinical/[visit_id]/[action]`, `/api/clinical-form`, `/api/ultrasound`, `/api/visits/[id]/theo-doi-thu-thuat`, `/api/cskh/khach/[id]` (+14)
- service: ThaiKyService.{doc, cap_nhat, tao} · phan_hoi_thuoc_service · ClinicalFormService.{lich_su_kham, get_form, save_form} · AndrologyReviewService.review · ho_so_lam_sang_doc · y_khoa (+42 service)
- test: test_hoan_tac_moi_thao_tac_db.py, test_phieu_kham_db.py, test_tep_ket_qua.py, test_cashier_scope_db.py, test_hanh_trinh_tu_van_db.py (+98)

### `/ban-kham/[phong]` — Bàn khám
- page: `src/dashboard/app/(dashboard)/ban-kham/[phong]/page.tsx` · quyền: lego `ban_kham` (Bàn khám · mặc định: Bác sĩ chính + Thư ký y khoa)
- thành phần: app/(dashboard)/ban-kham/BanKham.tsx, app/(dashboard)/_lam-viec/DoiPhong.tsx, app/(dashboard)/_lam-viec/KhungTep.tsx, app/(dashboard)/_lam-viec/XemLuot.tsx, app/(dashboard)/_lam-viec/XemPhieuKetQua.tsx, app/(dashboard)/_lam-viec/api.ts, app/(dashboard)/_lam-viec/dung-chip-lieu-trinh.ts, app/(dashboard)/_lam-viec/dung-ngay-xem.ts (+11)
- gọi API Next: `/api/thai-ky`, `/api/clinical-forms/history`, `/api/clinical-form/andrology-review`, `/api/clinical-record`, `/api/catalog`, `/api/clinical/[visit_id]/[action]`, `/api/clinical-form`, `/api/ultrasound`, `/api/visits/[id]/theo-doi-thu-thuat`, `/api/cskh/khach/[id]` (+14)
- service: ThaiKyService.{doc, cap_nhat, tao} · phan_hoi_thuoc_service · ClinicalFormService.{lich_su_kham, get_form, save_form} · AndrologyReviewService.review · ho_so_lam_sang_doc · y_khoa (+42 service)
- test: test_hoan_tac_moi_thao_tac_db.py, test_phieu_kham_db.py, test_tep_ket_qua.py, test_cashier_scope_db.py, test_hanh_trinh_tu_van_db.py (+98)

### `/cashier`
- page: `src/dashboard/app/(dashboard)/cashier/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/cashier/board`
- page: `src/dashboard/app/(dashboard)/cashier/board/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/cashier/dich-vu` — Bảng giá dịch vụ & phòng
- page: `src/dashboard/app/(dashboard)/cashier/dich-vu/page.tsx` · quyền: lego `bang_gia` (Bảng giá · mặc định: Thu ngân, QL)
- thành phần: app/(dashboard)/cashier/DanhMucDichVuPhong.tsx, app/(dashboard)/cashier/VatTuBangGia.tsx
- gọi API Next: `/api/clinic-config`, `/api/service-price`
- gọi thẳng backend (server): `/api/v1/service-prices/danh-muc`
- service: ClinicConfigService.{overview, set_service_rooms, create_location, create_room} · DanhMucDichVuService.doc · PriceListService.{phong_lam, add, update, remove}
- test: test_danh_muc_dich_vu_chuan_db.py, test_phong_la_tai_nguyen_db.py, test_vat_tu_danh_muc_db.py, test_gia_thuoc_hai_nguon_khop_db.py, test_lay_mau_doi_tac_db.py (+2)

### `/cashier/thuoc` — Bảng giá thuốc
- page: `src/dashboard/app/(dashboard)/cashier/thuoc/page.tsx` · quyền: ?
- thành phần: app/(dashboard)/cashier/CashierView.tsx
- gọi API Next: `/api/service-price`
- gọi thẳng backend (server): `/api/v1/service-prices`
- service: DanhMucDichVuService.doc · PriceListService.{phong_lam, add, update, remove, +1}
- test: test_danh_muc_dich_vu_chuan_db.py, test_vat_tu_danh_muc_db.py, test_lay_mau_doi_tac_db.py, test_gia_thuoc_hai_nguon_khop_db.py, test_mau_gui_doi_tac_db.py

### `/chon-co-so`
- page: `src/dashboard/app/(auth)/chon-co-so/page.tsx` · quyền: ?
- thành phần: actions.ts, duong-ve.ts
- gọi thẳng backend (server): `/api/v1/me/co-so`

### `/console` — Bảng điều khiển
- page: `src/dashboard/app/console/page.tsx` · quyền: ?
- thành phần: FeedbackBox.tsx
- gọi API Next: `/api/console/feedback`
- gọi thẳng backend (server): `/api/v1/console/overview`
- service: ConsoleService.{add_feedback, overview}

### `/cskh-tasks`
- page: `src/dashboard/app/(dashboard)/cskh-tasks/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/customers` — Quản lý khách hàng
- page: `src/dashboard/app/(dashboard)/customers/page.tsx` · quyền: lego `cham_soc_khach` (Chăm sóc khách hàng · mặc định: CSKH)
- thành phần: AppointmentEditModal.tsx, CustomersView.tsx, NhacTaiKham.tsx, PhanHoiKhach.tsx, PhanHoiThuocCot.tsx, TepKetQua.tsx, so-tuong-tac.ts, app/(dashboard)/PatientAdminEditor.tsx (+21)
- gọi API Next: `/api/hoa-don/cong-ty/khach/[id]`, `/api/hoa-don/cong-ty/an/[id]`, `/api/cskh/ho-so-kham/[appointmentId]`, `/api/appointments/cho-xep-bac-si`, `/api/patients/[id]/uu-tien`, `/api/cskh/nhac-tai-kham`, `/api/cskh/hen-goi-lai`, `/api/cskh/phan-hoi`, `/api/cskh/ket-qua/chi-dinh`, `/api/cskh/lieu-trinh/[id]` (+20)
- gọi thẳng backend (server): `/api/v1/cskh/danh-sach-khach`, `/api/v1/cskh/man-khach-hang`, `/api/v1/cskh/recall-jobs`, `/api/v1/catalog/locations`, `/api/v1/catalog/service-types`, `/api/v1/staff/bac-si-dat-duoc`
- service: HoaDonCongTyService.{doc_cong_ty_khach, luu_cong_ty_khach, an_cong_ty_khach} · HoSoKhamService.doc · lich_truc_co_so · ThongBaoService.goi · ThuTuKhamService.dat_uu_tien · RecallJobService.{tao_thu_cong, ghi_ket_qua, danh_sach} (+29 service)
- test: test_lieu_trinh_db.py, test_tep_ket_qua.py, test_ghi_chu_khach_db.py, test_so_tuong_tac_cskh.py, test_phan_hoi_thuoc_db.py (+53)

### `/design-system` — ClinicAI — Hệ thiết kế
- page: `src/dashboard/app/design-system/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/display`
- page: `src/dashboard/app/display/page.tsx` · quyền: ?
- thành phần: DisplayBoard.tsx
- gọi thẳng backend (server): `/api/v1/display/queue`
- service: DisplayBoardService.board
- test: test_co_so_hien_hanh_db.py

### `/do-sinh-hieu` — Đo sinh hiệu
- page: `src/dashboard/app/(dashboard)/do-sinh-hieu/page.tsx` · quyền: lego `do_sinh_hieu` (Đo sinh hiệu · mặc định: Điều dưỡng)
- thành phần: BangDoSinhHieu.tsx, app/(dashboard)/_lam-viec/LamThemTaiQuay.tsx, app/(dashboard)/_lam-viec/XemLuot.tsx, app/(dashboard)/_lam-viec/dung-ngay-xem.ts
- gọi API Next: `/api/lam-them`, `/api/nhac-viec`, `/api/cskh/ket-qua`, `/api/luot-kham`, `/api/cashier`
- service: LamThemTaiQuayService.{cau_hinh, nut_cho_luot, dat, dong_dich_vu, +1} · NhacViecService.{cua_toi, tao, xong} · TepKetQuaService.{danh_sach, da_xoa_gan_day, tai_len, danh_dau_da_gui} · nhan_tep_luong · SinhHieuService.{record_vitals, bat_dau_do_sinh_hieu} · LuotKhamService.{doi_duong_tu_van, cho_quyet} (+14 service)
- test: test_cashier_scope_db.py, test_loc_co_so_nhom_c_db.py, test_tep_ket_qua.py, test_bio_chi_dinh_db.py, test_bo_qua_tu_van_chi_dinh_them_db.py (+40)

### `/doctor/board`
- page: `src/dashboard/app/(dashboard)/doctor/board/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/doctor/orders/[visitId]`
- page: `src/dashboard/app/(dashboard)/doctor/orders/[visitId]/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/doi-tac` — Việc của đối tác
- page: `src/dashboard/app/doi-tac/page.tsx` · quyền: lego `doi_tac` (Đối tác · mặc định: Đối tác)
- thành phần: app/(auth)/login/actions.ts, app/(dashboard)/NotificationContext.tsx, app/(dashboard)/Shell.tsx, BangDoiTac.tsx, app/(dashboard)/BottomNav.tsx, app/(dashboard)/GlobalHeader.tsx, app/(dashboard)/Nav.tsx, app/(dashboard)/QuyenContext.tsx (+6)
- gọi API Next: `/api/auth/nhat-ky-doi-mat-khau`, `/api/thong-bao`, `/api/thong-bao/[id]/da-xu-ly`, `/api/doi-tac`, `/api/doi-tac/da-lay-mau`, `/api/doi-tac/cho-tai-lieu`, `/api/doi-tac/da-thu-tien`, `/api/doi-tac/huy-da-thu`, `/api/ops/agent`, `/api/loi` (+7)
- service: audit · ThongBaoService.{cua_toi, danh_dau_da_doc, da_xu_ly} · DoiTacService.{viec_doi_tac, doi_tac_da_lay_mau, doi_tac_cho_tai_lieu, ghi_nhan_da_thu, +1} · nhan_tep_luong · TepKetQuaService.{tai_len, khoi_phuc_tep, xoa_tep, mo_de_doc, +3} · agent_tom_tat.{doc, tao} (+25 service)
- test: test_so_sua_chi_dinh_db.py, test_hoan_tac_moi_thao_tac_db.py, test_tep_ket_qua.py, test_cashier_scope_db.py, test_xac_nhan_tep_ket_qua_db.py (+57)

### `/duyet-ket-qua` — Duyệt kết quả
- page: `src/dashboard/app/(dashboard)/duyet-ket-qua/page.tsx` · quyền: ?
- thành phần: DuyetKetQua.tsx, app/(dashboard)/_lam-viec/KhungTep.tsx, app/(dashboard)/_lam-viec/api.ts, app/(dashboard)/_lam-viec/hoan-tac.ts
- gọi API Next: `/api/cskh/ket-qua/[tepId]/khoi-phuc`, `/api/cskh/ket-qua/[tepId]/xoa`, `/api/cskh/ket-qua/[tepId]/noi-dung`, `/api/cskh/ket-qua`, `/api/phieu-kham`, `/api/luot-kham`
- service: TepKetQuaService.{khoi_phuc_tep, xoa_tep, mo_de_doc, danh_sach, +3} · media_service · tep_ket_qua_service · nhan_tep_luong · khung · PhieuKhamService.{tham_chieu_that, khung_theo_ban, doc_luot, lich_su, +10} (+16 service)
- test: test_hoan_tac_moi_thao_tac_db.py, test_phieu_kham_db.py, test_tep_ket_qua.py, test_phieu_kham_luot_db.py, test_xac_nhan_tep_ket_qua_db.py (+45)

### `/episodes`
- page: `src/dashboard/app/(dashboard)/episodes/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/forgot-password`
- page: `src/dashboard/app/(auth)/forgot-password/page.tsx` · quyền: ?
- thành phần: ForgotPasswordForm.tsx
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/giam-sat` — Trung tâm giám sát
- page: `src/dashboard/app/giam-sat/page.tsx` · quyền: ?
- thành phần: app/(auth)/login/actions.ts, TrungTamGiamSat.tsx, agent-demo.ts
- gọi API Next: `/api/ops/agent`, `/api/loi`
- service: agent_tom_tat.{doc, tao} · tong_quan_giam_sat.doc · chi_phi.so_lieu · agent_giam_sat.{danh_sach, danh_gia, dat_che_do} · kho_loi.ghi_loi_web
- test: test_agent_giam_sat_db.py, test_llm_chi_phi_db.py, test_theo_doi_pha_1.py, test_theo_doi_pha_1_db.py

### `/hanh-trinh` — Hành trình khách hôm nay
- page: `src/dashboard/app/(dashboard)/hanh-trinh/page.tsx` · quyền: ?
- thành phần: BangHanhTrinh.tsx, app/(dashboard)/_lam-viec/HanhTrinhKhach.tsx, app/(dashboard)/_lam-viec/NutCheckOut.tsx, app/(dashboard)/_lam-viec/NutXemLuot.tsx, app/(dashboard)/_lam-viec/api.ts, app/(dashboard)/_lam-viec/dung-ngay-xem.ts
- gọi API Next: `/api/reception/checkout`, `/api/phieu-kham`, `/api/luot-kham`, `/api/cashier`
- service: CheckoutService.{pending_list, stale_list, chi_tiet, readiness, +1} · payment_access_service · TienThuaService.{giu_lai, huy_giu_lai} · CongNoService.{ghi, huy} · khung · PhieuKhamService.{tham_chieu_that, khung_theo_ban, doc_luot, lich_su, +10} (+19 service)
- test: test_hoan_tac_moi_thao_tac_db.py, test_phieu_kham_db.py, test_cashier_scope_db.py, test_phieu_kham_luot_db.py, test_bio_chi_dinh_db.py (+56)

### `/hoa-don` — Danh sách hoá đơn
- page: `src/dashboard/app/(dashboard)/hoa-don/page.tsx` · quyền: lego `bao_cao` (Báo cáo · mặc định: Quản lý)
- thành phần: DanhSachHoaDon.tsx, app/(dashboard)/QuyenContext.tsx, app/(dashboard)/form-ui.ts, ChiTietHoaDon.tsx, types.ts, app/(dashboard)/reports/NgayTrucBaoCao.tsx
- gọi API Next: `/api/hoa-don/cong-ty/phieu/[id]`, `/api/hoa-don`, `/api/reports/access`
- gọi thẳng backend (server): `/api/v1/catalog/locations`, `/api/v1/catalog/service-types`
- service: HoaDonCongTyService.{doc_hoa_don, ghi_hoa_don, bo_hoa_don} · DanhSachHoaDonService.xem · danh_sach_hoa_don_service · ReportAccessService.access
- test: test_hoa_don_cong_ty_db.py, test_vai_ke_toan_db.py, test_an_ton_co_so_ngung_db.py, test_danh_sach_hoa_don.py, test_danh_sach_hoa_don_db.py (+4)

### `/home` — Trang chủ
- page: `src/dashboard/app/(dashboard)/home/page.tsx` · quyền: ?
- thành phần: app/(dashboard)/WeekNav.tsx, CotTongQuan.tsx, VisitStatusBoard.tsx, VisitStatusRealtime.tsx, WeeklyAppointmentsTable.tsx, WorkRosterTable.tsx, lich-hen-ngay.ts, app/(dashboard)/nav-items.ts (+7)
- gọi API Next: `/api/appointments/doi-lich-nhanh`, `/api/appointments/doi-dich-vu-kham`, `/api/catalog/dich-vu-dat-lich`, `/api/cskh/tuong-tac`, `/api/appointments/luoi-ngay`, `/api/appointments`, `/api/luot-kham`, `/api/cashier`
- gọi thẳng backend (server): `/api/v1/home/bang-dieu-khien`
- service: doi_lich_nhanh.o_doi_lich · BookingService.{doi_lich_nhanh, doi_dich_vu_kham, create, apply_action} · doi_dich_vu_kham.o_doi_dich_vu · dich_vu_dat_lich.doc · TuongTacCskhService.{lich_su, ghi} · capacity_service (+18 service)
- test: test_cashier_scope_db.py, test_bio_chi_dinh_db.py, test_loc_co_so_nhom_c_db.py, test_cashier_scope.py, test_payment_access.py (+45)

### `/ke-toan` — Kế toán
- page: `src/dashboard/app/(dashboard)/ke-toan/page.tsx` · quyền: lego `ke_toan` (Kế toán · mặc định: Kế toán)
- thành phần: KeToan.tsx, app/(dashboard)/form-ui.ts, app/(dashboard)/hoa-don/types.ts, ThueSuat.tsx, thue-suat.ts
- gọi API Next: `/api/theo-hang-hoa`, `/api/ke-toan/thue-suat`, `/api/ke-toan/thue-suat/nhom/[nhom]`, `/api/ke-toan/thue-suat/mat-hang`
- gọi thẳng backend (server): `/api/v1/catalog/locations`, `/api/v1/catalog/service-types`
- service: TheoHangHoaService.xem · theo_hang_hoa_service · ThueSuatService.{xem, dat_nhom, dat_mat_hang}
- test: test_thue_gtgt_db.py, test_theo_hang_hoa_db.py, test_theo_hang_hoa.py

### `/kham/[loai]`
- page: `src/dashboard/app/(dashboard)/kham/[loai]/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/kho-vat-tu` — Kho vật tư
- page: `src/dashboard/app/(dashboard)/kho-vat-tu/page.tsx` · quyền: lego `kho_vat_tu` (Kho vật tư · mặc định: Mọi người (QL chỉnh mức tối thiểu))
- thành phần: app/(dashboard)/cashier/VatTuBangGia.tsx, ChoDuyetVatTu.tsx, DanhSachPhieuVatTu.tsx, KhoVatTu.tsx, TonVatTu.tsx, app/(dashboard)/cashier/VatTuThuocTinh.tsx, DanhMucVatTu.tsx, LapPhieuVatTu.tsx (+2)
- gọi API Next: `/api/service-price/vat-tu-hang-loat`, `/api/vat-tu-kho/[action]`, `/api/service-price`, `/api/cashier`
- gọi thẳng backend (server): `/api/v1/vat-tu-kho/ton`, `/api/v1/vat-tu-kho/phieu`, `/api/v1/vat-tu-kho/cho-duyet`
- service: vat_tu_danh_muc_service · vat_tu_kho_service.{doc_ton, tao_phieu, hoan_phieu} · vat_tu_kho_man_service.{doc_noi_chua, doc_vat_tu_chon, doc_phieu, dat_muc_toi_thieu} · vat_tu_tieu_hao_service.doc_tieu_hao · can · vat_tu_nhap_duyet_service.{doc_cho_duyet, duyet, rut_lai, tu_choi} (+5 service)
- test: test_cashier_scope_db.py, test_vat_tu_nhap_duyet_db.py, test_danh_muc_dich_vu_chuan_db.py, test_vat_tu_kho_man_db.py, test_cashier_scope.py (+15)

### `/lab-queue`
- page: `src/dashboard/app/(dashboard)/lab-queue/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/lich-do-ve` — Lịch đổ về
- page: `src/dashboard/app/(dashboard)/lich-do-ve/page.tsx` · quyền: lego `bao_cao` (Báo cáo · mặc định: Quản lý)
- gọi thẳng backend (server): `/api/v1/appointments/week`
- service: WeekAppointmentsService.week
- test: test_thu_thuat_nhu_kham_thuong_db.py, test_week_appointments.py

### `/login`
- page: `src/dashboard/app/(auth)/login/page.tsx` · quyền: ?
- thành phần: LoginForm.tsx, actions.ts
- gọi API Next: `/api/ops/agent`, `/api/loi`
- service: agent_tom_tat.{doc, tao} · tong_quan_giam_sat.doc · chi_phi.so_lieu · agent_giam_sat.{danh_sach, danh_gia, dat_che_do} · kho_loi.ghi_loi_web
- test: test_agent_giam_sat_db.py, test_llm_chi_phi_db.py, test_theo_doi_pha_1.py, test_theo_doi_pha_1_db.py

### `/luot-kham`
- page: `src/dashboard/app/(dashboard)/luot-kham/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/nhac-tai-kham` — Nhắc tái khám
- page: `src/dashboard/app/(dashboard)/nhac-tai-kham/page.tsx` · quyền: lego `cham_soc_khach` (Chăm sóc khách hàng · mặc định: CSKH)
- thành phần: LieuTrinhCskh.tsx, TabNhacTaiKham.tsx, ViecGoiNhac.tsx, app/(dashboard)/_lam-viec/DatLichBuoiKe.tsx, app/(dashboard)/_lam-viec/LieuTrinhKhach.tsx, app/(dashboard)/_lam-viec/ViecTaiKham.tsx
- gọi API Next: `/api/cskh/lieu-trinh/[id]`, `/api/cskh/tuong-tac/[id]/hoan-tac`, `/api/cskh/lieu-trinh`, `/api/recall-jobs/[id]/ket-qua`, `/api/lieu-trinh`, `/api/appointments/doi-dich-vu-kham`, `/api/cskh/tuong-tac`, `/api/appointments`, `/api/cashier`
- gọi thẳng backend (server): `/api/v1/cskh/recall-jobs`, `/api/v1/catalog/locations`, `/api/v1/catalog/service-types`, `/api/v1/staff/bac-si-dat-duoc`
- service: LieuTrinhService.{lich_su, da_xu_ly_sap_het, dang_ky, dieu_chinh, +6} · TuongTacCskhService.{hoan_tac, lich_su, ghi} · RecallJobService.{ghi_ket_qua, danh_sach} · doi_dich_vu_kham.o_doi_dich_vu · BookingService.{doi_dich_vu_kham, create, apply_action} · lich_hen_doc.{lich_sap_toi, lich_trong_ngay} (+3 service)
- test: test_lieu_trinh_db.py, test_cashier_scope_db.py, test_so_tuong_tac_cskh.py, test_cashier_scope.py, test_payment_access.py (+16)

### `/nhan-su` — Quản lý nhân sự
- page: `src/dashboard/app/(dashboard)/nhan-su/page.tsx` · quyền: lego `nhan_su` (Nhân sự & phân quyền · mặc định: Quản lý)
- thành phần: NhanSuBoard.tsx
- gọi API Next: `/api/staff`
- gọi thẳng backend (server): `/api/v1/staff`, `/api/v1/clinic-config/overview`
- service: StaffService.{list_assignable, list_active, create_staff, update_staff} · ClinicConfigService.overview
- test: test_staff_service.py, test_phong_la_tai_nguyen_db.py, test_phong_lam_theo_dich_vu_db.py, test_quyen_khoi_dong_db.py, test_vai_doi_tac_nhan_su_db.py

### `/ops` — Vận hành hệ thống
- page: `src/dashboard/app/(dashboard)/ops/page.tsx` · quyền: lego `van_hanh` (Vận hành hệ thống · mặc định: Quản lý)
- thành phần: LoiCanhBao.tsx, LuuLuongOps.tsx, NhatKyVanHanh.tsx, OpsCenter.tsx, SucKhoeApi.tsx, ToanCanh.tsx, PortalBoard.tsx
- gọi API Next: `/api/ops/theo-doi`, `/api/ops/summary`, `/api/ops/traffic`
- gọi thẳng backend (server): `/api/v1/reports/toan-canh`, `/api/v1/catalog/locations`, `/api/v1/catalog/service-types`, `/api/v1/ops/telemetry`
- service: day_tep.so_lieu · canh_gac.danh_sach · nhat_ky_van_hanh.doc_nhat_ky · kho_loi.doi_trang_thai · can · cashier_navigation_service (+3 service)
- test: test_theo_doi_pha_1_db.py, test_traffic_service.py, test_cashier_navigation.py, test_cua_quyen_lego.py, test_bao_cao_theo_co_so_db.py (+7)

### `/ops/telemetry`
- page: `src/dashboard/app/(dashboard)/ops/telemetry/page.tsx` · quyền: lego `van_hanh` (Vận hành hệ thống · mặc định: Quản lý)
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/patient-list` — Danh sách bệnh nhân
- page: `src/dashboard/app/(dashboard)/patient-list/page.tsx` · quyền: lego `ds_benh_nhan` (Danh sách bệnh nhân · mặc định: CSKH, lễ tân)
- thành phần: PatientListView.tsx, app/(dashboard)/tasks/DoctorApptRow.ts, app/(dashboard)/SplitPane.tsx, app/(dashboard)/_lam-viec/LichSuKham.tsx, app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx, app/(dashboard)/customers/KenhDoiHuy.tsx, LichSuNotion.tsx, app/(dashboard)/tasks/ClinicalRecordForm.tsx
- gọi API Next: `/api/lich-su-notion/tep`, `/api/lich-su-notion`, `/api/clinical-record`, `/api/catalog`, `/api/clinical/[visit_id]/[action]`, `/api/clinical-form`, `/api/ultrasound`, `/api/visits/[id]/theo-doi-thu-thuat`, `/api/cskh/khach/[id]`, `/api/ho-so-kham` (+7)
- gọi thẳng backend (server): `/api/v1/patients/danh-sach`, `/api/v1/patients/danh-sach${thamSo.size`
- service: lich_su_notion_service · tep_ket_qua_service · TepMoDoc · ho_so_lam_sang_doc · y_khoa · ClinicalRecordService.save (+36 service)
- test: test_hoan_tac_moi_thao_tac_db.py, test_phieu_kham_db.py, test_loc_co_so_nhom_c_db.py, test_phieu_kham_luot_db.py, test_tep_ket_qua.py (+83)

### `/patients/[id]`
- page: `src/dashboard/app/(dashboard)/patients/[id]/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/patients/new` — Tạo bệnh nhân
- page: `src/dashboard/app/(dashboard)/patients/new/page.tsx` · quyền: lego `them_benh_nhan` (Thêm bệnh nhân · mặc định: Lễ tân, CSKH)
- thành phần: NewPatientForm.tsx, app/(dashboard)/BookingPolicyContext.tsx, app/(dashboard)/DateField.tsx, app/(dashboard)/QuyenContext.tsx, app/(dashboard)/SearchSelect.tsx, app/(dashboard)/_lam-viec/ChonDichVuDatLich.tsx, app/(dashboard)/appointments/BangBacSiTuan.tsx, app/(dashboard)/appointments/cho-trong.ts (+5)
- gọi API Next: `/api/appointments/cho-trong-tuan`, `/api/appointments/quote`, `/api/appointments/slot-hold`, `/api/cskh-action`, `/api/wards`, `/api/patients/check-duplicate`, `/api/appointments/service-history`, `/api/catalog/dich-vu-dat-lich`, `/api/appointments/luoi-ngay`, `/api/roster` (+3)
- gọi thẳng backend (server): `/api/v1/catalog/provinces`, `/api/v1/catalog/locations`, `/api/v1/catalog/service-types`, `/api/v1/staff/bac-si-dat-duoc`
- service: capacity_service · CapacityService.quote · SlotHoldService.{release, active, hold} · CskhService.record_action · MPIService.find_candidates · lich_hen_doc.{lich_su_dich_vu, lich_sap_toi, lich_trong_ngay} (+5 service)
- test: test_clinical_cluster.py, test_capacity_roster_gate.py, test_lich_hen_doc_db.py, test_lich_truc_phien_ban_db.py, test_pham_vi_vi_tri_lich_truc.py (+18)

### `/phan-quyen` — Phân quyền
- page: `src/dashboard/app/(dashboard)/phan-quyen/page.tsx` · quyền: lego `nhan_su` (Nhân sự & phân quyền · mặc định: Quản lý)
- thành phần: BangPhanQuyen.tsx, KyNangCuaNguoi.tsx, LegoCuaNguoi.tsx, NhomQuyenMau.tsx, QuyenTheoMan.tsx
- gọi API Next: `/api/phan-quyen`
- gọi thẳng backend (server): `/api/v1/staff`
- service: PermissionService.{them_preset, lego_cua_nguoi, doi_lego, danh_sach_nhom, +5} · KyNangService.{cua_nguoi, doi, chep, danh_sach} · KHOI.values · PRESET.items · catalogue · StaffService.{list_assignable, list_active, create_staff}
- test: test_lego_21_db.py, test_permission_db.py, test_staff_service.py, test_no_con_lai_db.py, test_clinical_cluster.py (+7)

### `/pharmacy` — Cấp thuốc
- page: `src/dashboard/app/(dashboard)/pharmacy/page.tsx` · quyền: lego `kho_thuoc` (Kho thuốc · mặc định: Dược sĩ (+ lễ tân))
- thành phần: PharmacyBoard.tsx, ban-thuoc.ts, app/(dashboard)/_lam-viec/XemLuot.tsx, app/(dashboard)/form-ui.ts, BanLeThu.tsx, DongThuoc.tsx, KhachMuaThuoc.tsx, app/(dashboard)/pharmacy/inventory/OQuetMa.tsx (+1)
- gọi API Next: `/api/pharmacy/[action]`, `/api/payment`, `/api/payment/anh-ck`, `/api/quay-thuoc`, `/api/nhac-viec`, `/api/cskh/ket-qua`, `/api/phieu-kham`, `/api/luot-kham`, `/api/cashier`
- gọi thẳng backend (server): `/api/v1/pharmacy/ban-thuoc`
- service: lo_thuoc_service.{sua_lo, huy_lo, hoan_huy_lo, so_ngay_canh_bao, +1} · can · PharmacyService.{nhap_lo, cap_phat, tu_choi, chot, +13} · kho_thuoc_service.{tao_phieu_nhap, kiem_kho, chuyen_kho, hoan_tac_chuyen, +4} · BanLeService.{mo_luot, mo_theo_don, tim_khach, doc, +1} · ma_vach_service.{gan_ma, go_ma, tra_ma, du_lieu_tem} (+34 service)
- test: test_kho_quay_db.py, test_ban_theo_don_db.py, test_payment_access.py, test_phieu_kham_db.py, test_ban_le_thuoc_db.py (+90)

### `/pharmacy/consult` — Tư vấn dùng thuốc
- page: `src/dashboard/app/(dashboard)/pharmacy/consult/page.tsx` · quyền: lego `kho_thuoc` (Kho thuốc · mặc định: Dược sĩ (+ lễ tân))
- thành phần: ConsultBoard.tsx
- gọi thẳng backend (server): `/api/v1/pharmacy/cho-tu-van`
- service: PharmacyService.cho_tu_van
- test: test_loc_co_so_nhom_b_db.py

### `/pharmacy/history` — Lịch sử bàn giao
- page: `src/dashboard/app/(dashboard)/pharmacy/history/page.tsx` · quyền: lego `kho_thuoc` (Kho thuốc · mặc định: Dược sĩ (+ lễ tân))
- thành phần: HistoryBoard.tsx
- gọi thẳng backend (server): `/api/v1/pharmacy/lich-su`
- service: PharmacyService.lich_su_giao
- test: test_loc_co_so_nhom_b_db.py

### `/pharmacy/inventory` — Kho thuốc
- page: `src/dashboard/app/(dashboard)/pharmacy/inventory/page.tsx` · quyền: lego `kho_thuoc` (Kho thuốc · mặc định: Dược sĩ (+ lễ tân))
- thành phần: ChoGanLo.tsx, DanhMucKho.tsx, InventoryBoard.tsx, KhoThuoc.tsx, ThuocTraChoKiem.tsx, app/(dashboard)/form-ui.ts, app/(dashboard)/pharmacy/KhachMuaThuoc.tsx, ChuyenKho.tsx (+7)
- gọi API Next: `/api/pharmacy/kiem-ke-ca`, `/api/pharmacy/[action]`
- gọi thẳng backend (server): `/api/v1/pharmacy/inventory`, `/api/v1/pharmacy/danh-muc`, `/api/v1/pharmacy/cho-gan-lo`, `/api/v1/pharmacy/thuoc-tra-cho-kiem`, `/api/v1/pharmacy/so-ngay-canh-bao`, `/api/v1/pharmacy/tach-kho-quay`
- service: kiem_ke_ca_service.{nhac_thieu_kiem, danh_sach, mo_phieu} · lo_thuoc_service.{sua_lo, huy_lo, hoan_huy_lo, so_ngay_canh_bao, +1} · can · PharmacyService.{nhap_lo, cap_phat, tu_choi, chot, +16} · kho_thuoc_service.{tao_phieu_nhap, kiem_kho, chuyen_kho, hoan_tac_chuyen, +5} · BanLeService.{mo_luot, mo_theo_don, tim_khach, doc, +1} (+4 service)
- test: test_kho_quay_db.py, test_kho_kiotviet_db.py, test_kiem_ke_ca_db.py, test_ban_theo_don_db.py, test_ma_vach_db.py (+20)

### `/phong` — Phòng dịch vụ
- page: `src/dashboard/app/(dashboard)/phong/page.tsx` · quyền: lego `phong` (Phòng dịch vụ · mặc định: BS siêu âm / thủ thuật + Điều dưỡng)
- thành phần: app/(dashboard)/LiveBoardSync.tsx, app/(dashboard)/_lam-viec/api.ts
- gọi API Next: `/api/phieu-kham`, `/api/luot-kham`
- gọi thẳng backend (server): `/api/v1/luot-kham/phong-hom-nay`
- service: khung · PhieuKhamService.{tham_chieu_that, khung_theo_ban, doc_luot, lich_su, +10} · y_khoa · LichTaiKhamService.{doc, dat, huy} · BangLuotKham.{bang, phong_hom_nay, ket_qua_cho_duyet, chi_dinh_hom_nay, +1} · LuotKhamService.cho_quyet (+10 service)
- test: test_phieu_kham_db.py, test_phieu_kham_luot_db.py, test_danh_muc_dich_vu_chuan_db.py, test_loc_co_so_nhom_c_db.py, test_bio_chi_dinh_db.py (+33)

### `/phong/[ma]`
- page: `src/dashboard/app/(dashboard)/phong/[ma]/page.tsx` · quyền: lego `phong` (Phòng dịch vụ · mặc định: BS siêu âm / thủ thuật + Điều dưỡng)
- thành phần: PhongDichVu.tsx, app/(dashboard)/_lam-viec/ChonBacSiLam.tsx, app/(dashboard)/_lam-viec/HangChoCot.tsx, app/(dashboard)/_lam-viec/KhungTep.tsx, app/(dashboard)/_lam-viec/PhieuKetQua.tsx, app/(dashboard)/_lam-viec/XemLuot.tsx, app/(dashboard)/_lam-viec/api.ts, app/(dashboard)/_lam-viec/dung-chip-lieu-trinh.ts (+7)
- gọi API Next: `/api/lieu-trinh`, `/api/lieu-trinh/chip`, `/api/phieu`, `/api/nhac-viec`, `/api/cskh/ket-qua/[tepId]/khoi-phuc`, `/api/cskh/ket-qua/[tepId]/xoa`, `/api/cskh/ket-qua/[tepId]/noi-dung`, `/api/cskh/ket-qua`, `/api/phieu-kham`, `/api/luot-kham` (+1)
- service: LieuTrinhService.{tao, gan, go, chip} · FormEngineService.{luu_nhap, hoan_tat, mo_sua, huy_sua, +3} · NhacViecService.{cua_toi, tao, xong} · TepKetQuaService.{khoi_phuc_tep, xoa_tep, mo_de_doc, danh_sach, +3} · media_service · tep_ket_qua_service (+22 service)
- test: test_hoan_tac_moi_thao_tac_db.py, test_phieu_kham_db.py, test_tep_ket_qua.py, test_cashier_scope_db.py, test_phieu_kham_luot_db.py (+63)

### `/portal`
- page: `src/dashboard/app/(dashboard)/portal/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/print/[appointmentId]`
- page: `src/dashboard/app/print/[appointmentId]/page.tsx` · quyền: ?
- thành phần: MedicalSummaryPrint.tsx
- gọi thẳng backend (server): `/api/v1/clinical-records/in-theo-lich/${encodeURIComponent(appointmentId)}`, `/api/v1/phieu-kham/luot/${encodeURIComponent(doc.visit.visit_id)}/phieu`
- service: ho_so_lam_sang_doc · y_khoa · PhieuKhamService.{doc_luot, luu_luot}
- test: test_phieu_kham_luot_db.py, test_bao_cao_va_danh_sach_khach_db.py, test_clinical_read_and_legacy_boundaries.py, test_ho_so_lam_sang_doc_db.py, test_phieu_kham_lich_su_db.py (+2)

### `/print/hoa-don-thuoc/[visitId]` — In hoá đơn thuốc
- page: `src/dashboard/app/print/hoa-don-thuoc/[visitId]/page.tsx` · quyền: ?
- thành phần: InHoaDonThuoc.tsx, app/print/phieu-thu/[id]/InPhieuThu.tsx
- gọi API Next: `/api/cashier`
- service: CashierBoardService.{board, giao_dich} · CashierScopeService.{authorize_active, days, authorize, receipt, +1} · QuayThuService.{lich_su, phieu, phieu_cua_luot}
- test: test_cashier_scope_db.py, test_cashier_scope.py, test_payment_access.py, test_doi_hinh_thuc_db.py, test_tach_thu_thuoc_dich_vu_db.py (+4)

### `/print/ket-qua-luot/[visitId]` — In kết quả
- page: `src/dashboard/app/print/ket-qua-luot/[visitId]/page.tsx` · quyền: ?
- thành phần: InKetQuaLuot.tsx
- gọi API Next: `/api/phieu-kham`
- gọi thẳng backend (server): `/api/v1/phieu/in/{order}`
- service: khung · PhieuKhamService.{tham_chieu_that, khung_theo_ban, doc_luot, lich_su, +10} · y_khoa · LichTaiKhamService.{doc, dat, huy} · FormEngineService.in_ket_qua
- test: test_phieu_kham_db.py, test_phieu_kham_luot_db.py, test_danh_muc_dich_vu_chuan_db.py, test_don_thuoc_ban_tu_van_1310_db.py, test_lich_tai_kham_tu_phieu_db.py (+11)

### `/print/ket-qua/[orderId]`
- page: `src/dashboard/app/print/ket-qua/[orderId]/page.tsx` · quyền: ?
- thành phần: InKetQua.tsx, app/(dashboard)/_lam-viec/AnhKetQua.tsx, app/print/KhoiIn.tsx, app/print/KieuInA4.tsx
- gọi API Next: `/api/phieu`, `/api/cskh/ket-qua/[tepId]/noi-dung`
- service: FormEngineService.{in_ket_qua, xem_ket_qua, mo_phieu} · media_service · TepKetQuaService.mo_de_doc · tep_ket_qua_service
- test: test_tep_ket_qua.py, test_xac_nhan_tep_ket_qua_db.py, test_form_engine_db.py, test_full_chi_dinh_slice_ab_db.py, test_in_anh_dot3_db.py (+4)

### `/print/phieu-kham/[visitId]`
- page: `src/dashboard/app/print/phieu-kham/[visitId]/page.tsx` · quyền: ?
- thành phần: InPhieuKham.tsx, app/(dashboard)/_lam-viec/AnhKetQua.tsx, app/print/KhoiIn.tsx, app/print/KieuInA4.tsx
- gọi API Next: `/api/ho-so-kham`, `/api/phieu`, `/api/cskh/ket-qua/[tepId]/noi-dung`, `/api/phieu-kham`
- service: lich_su_luot.doc · y_khoa · doc_bang · ho_so_dich_vu.{doc, doi} · dieu_tri_ban_kham.{doc_the, chon_thu_thuat, thao_tac} · ghi_chu_luot.{doc, luu} (+7 service)
- test: test_phieu_kham_db.py, test_phieu_kham_luot_db.py, test_danh_muc_dich_vu_chuan_db.py, test_don_thuoc_ban_tu_van_1310_db.py, test_khoi1_ban_kham_db.py (+27)

### `/print/phieu-thu/[id]` — In phiếu thu
- page: `src/dashboard/app/print/phieu-thu/[id]/page.tsx` · quyền: ?
- thành phần: InPhieuThu.tsx, app/(dashboard)/_lam-viec/DoiPhong.tsx
- gọi API Next: `/api/luot-kham`, `/api/cashier`
- service: ServiceRoutingService.{assign, invalidate, dat_phong_du_kien, chuyen_phong_dang_lam, +1} · HoanTacService.{mo_lai_kham, huy_chi_dinh, hoan_tac_xong_dich_vu, mo_lai_luot, +1} · SoSuaChiDinhService.{hoan_tac, doc} · NhanTaiPhongService.hoan_tac_nhan · BangLuotKham.{bang, phong_hom_nay, ket_qua_cho_duyet, chi_dinh_hom_nay, +1} · LuotKhamService.cho_quyet (+11 service)
- test: test_hoan_tac_moi_thao_tac_db.py, test_cashier_scope_db.py, test_bio_chi_dinh_db.py, test_loc_co_so_nhom_c_db.py, test_so_sua_chi_dinh_db.py (+33)

### `/print/sono/[id]`
- page: `src/dashboard/app/print/sono/[id]/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/print/tem-lo` — In tem lô thuốc
- page: `src/dashboard/app/print/tem-lo/page.tsx` · quyền: ?
- thành phần: InTemLo.tsx, app/(dashboard)/pharmacy/ban-thuoc.ts, app/(dashboard)/pharmacy/inventory/OQuetMa.tsx, app/(dashboard)/pharmacy/inventory/gui-kho.ts
- gọi API Next: `/api/pharmacy/[action]`
- service: lo_thuoc_service.{sua_lo, huy_lo, hoan_huy_lo, so_ngay_canh_bao, +1} · can · PharmacyService.{nhap_lo, dieu_chinh, huy, danh_muc, +3} · kho_thuoc_service.{tao_phieu_nhap, kiem_kho, chuyen_kho, hoan_tac_chuyen, +4} · ma_vach_service.{gan_ma, go_ma, tra_ma, du_lieu_tem} · pharmacy_service (+2 service)
- test: test_kho_quay_db.py, test_kho_kiotviet_db.py, test_ma_vach_db.py, test_sua_huy_lo_db.py, test_cua_ngo_ghi_moi.py (+14)

### `/queue`
- page: `src/dashboard/app/(dashboard)/queue/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/reception/checkout` — Check-out lượt khám
- page: `src/dashboard/app/(dashboard)/reception/checkout/page.tsx` · quyền: lego `tiep_don` (Tiếp đón khách · mặc định: Lễ tân)
- thành phần: app/(dashboard)/LiveBoardSync.tsx, CheckoutBoard.tsx, app/(dashboard)/_lam-viec/KhoanNoKhiVe.tsx, ChiTietLuot.tsx, LuotTonDong.tsx
- gọi API Next: `/api/reception/checkout`, `/api/cashier`
- gọi thẳng backend (server): `/api/v1/reception/checkout`
- service: CheckoutService.{pending_list, stale_list, chi_tiet, readiness, +1} · payment_access_service · HoanTienService.hoan_tien_thua · TienThuaService.{giu_lai, huy_giu_lai} · CongNoService.{ghi, huy} · CashierBoardService.{board, giao_dich} (+2 service)
- test: test_cashier_scope_db.py, test_payment_access.py, test_cashier_scope.py, test_mo_phong_dong_tien_db.py, test_tien_thua_phan_e_db.py (+17)

### `/reception/queue` — Tiếp đón khách
- page: `src/dashboard/app/(dashboard)/reception/queue/page.tsx` · quyền: lego `tiep_don` (Tiếp đón khách · mặc định: Lễ tân)
- thành phần: app/(dashboard)/LiveBoardSync.tsx, app/(dashboard)/WeekNav.tsx, app/(dashboard)/home/WeeklyAppointmentsTable.tsx, app/(dashboard)/home/lich-hen-ngay.ts, ManTiepDon.tsx, QueueBoard.tsx, app/(dashboard)/BookingPolicyContext.tsx, app/(dashboard)/_lam-viec/DoiLichTaiCho.tsx (+9)
- gọi API Next: `/api/appointments/doi-lich-nhanh`, `/api/lam-them`, `/api/appointments/doi-dich-vu-kham`, `/api/catalog/dich-vu-dat-lich`, `/api/cskh/tuong-tac`, `/api/lieu-trinh/chip`, `/api/appointments/luoi-ngay`, `/api/reception/checkout`, `/api/appointments`, `/api/luot-kham`
- gọi thẳng backend (server): `/api/v1/reception/danh-sach`, `/api/v1/home/lich-hen-tuan`
- service: doi_lich_nhanh.o_doi_lich · BookingService.{doi_lich_nhanh, doi_dich_vu_kham, create, apply_action} · LamThemTaiQuayService.{cau_hinh, nut_cho_luot, dat, dong_dich_vu, +1} · doi_dich_vu_kham.o_doi_dich_vu · dich_vu_dat_lich.doc · TuongTacCskhService.{lich_su, ghi} (+24 service)
- test: test_hoan_tac_moi_thao_tac_db.py, test_bio_chi_dinh_db.py, test_loc_co_so_nhom_c_db.py, test_so_sua_chi_dinh_db.py, test_so_tuong_tac_cskh.py (+56)

### `/reports` — Báo cáo
- page: `src/dashboard/app/(dashboard)/reports/page.tsx` · quyền: lego `bao_cao` (Báo cáo · mặc định: Quản lý)
- thành phần: app/(dashboard)/StatCard.tsx, BaoCaoHangHoa.tsx, CuoiNgay.tsx, PrintReportButton.tsx, access.ts, app/(dashboard)/form-ui.ts, BangHangHoa.tsx, KhoiChotCa.tsx (+3)
- gọi API Next: `/api/reports/cuoi-ngay`, `/api/reports/chot-ca`, `/api/reports/access`, `/api/cashier`
- gọi thẳng backend (server): `/api/v1/reports/access${ngay`, `/api/v1/reports/tong-quan${locCoSo`, `/api/v1/reports/booking-channels`, `/api/v1/reports/kpi-dat-lich${locCoSo`, `/api/v1/catalog/locations`, `/api/v1/catalog/service-types`
- service: ReportAccessService.{authorize, access} · BaoCaoCuoiNgayService.bao_cao · report_access_service · ChotSoCaService.{chot, mo_khoa} · CashierBoardService.{board, giao_dich} · CashierScopeService.{authorize_active, days, authorize, receipt, +1} (+3 service)
- test: test_cashier_scope_db.py, test_report_access_db.py, test_bao_cao_theo_co_so_db.py, test_cashier_scope.py, test_payment_access.py (+11)

### `/reset-password`
- page: `src/dashboard/app/(auth)/reset-password/page.tsx` · quyền: ?
- thành phần: ResetPasswordForm.tsx
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/result-review`
- page: `src/dashboard/app/(dashboard)/result-review/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/schedule` — Lịch làm việc
- page: `src/dashboard/app/(dashboard)/schedule/page.tsx` · quyền: lego `lich_lam_viec` (Lịch làm việc · mặc định: Mọi người)
- thành phần: app/(dashboard)/home/WorkRosterTable.tsx, ApDungTuan.tsx, LichTheoNguoi.tsx, NgoaiLeCaTruc.tsx, OfficialRosterTable.tsx, PhienBanLich.tsx, RosterRegisterTable.tsx, TabLichLamViec.tsx (+2)
- gọi API Next: `/api/roster/ngoai-le-ca-truc`, `/api/roster/thay-nguoi`, `/api/roster`
- gọi thẳng backend (server): `/api/v1/roster/lich-tuan`, `/api/v1/roster/phien-ban`, `/api/v1/roster/clinical-exceptions`
- service: NgoaiLeCaTrucService.{danh_sach, mo, huy} · RosterService.{thay_nguoi, applied_weeks, tram_cho_nhan_vien, bac_si_trong_ngay, +5} · LichTrucPhienBanService.xem
- test: test_ca_truc_lam_sang_db.py, test_clinical_cluster.py, test_lich_truc_phien_ban_db.py, test_pham_vi_vi_tri_lich_truc.py, test_doi_nguoi_trong_ca_db.py (+4)

### `/service-queue`
- page: `src/dashboard/app/(dashboard)/service-queue/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/settings` — Cài đặt
- page: `src/dashboard/app/(dashboard)/settings/page.tsx` · quyền: lego `cai_dat` (Cài đặt phòng khám · mặc định: Quản lý)
- thành phần: BookingPolicyCard.tsx, FeatureModeCard.tsx, PhamViViTriCard.tsx, ReportSettingsCard.tsx, app/(dashboard)/form-ui.ts
- gọi API Next: `/api/config/feature-mode`, `/api/roster/pham-vi`, `/api/reports/settings`, `/api/booking-policy`
- gọi thẳng backend (server): `/api/v1/reports/settings`, `/api/v1/roster/station-scope`, `/api/v1/feature-mode`
- service: ClinicSettingsService.{get_feature_mode, update_feature_mode, update_booking_policy} · RosterService.{ma_tran_vi_tri, dat_vi_tri_cho_vai} · ReportAccessService.{settings, save}
- test: test_clinic_settings_service.py, test_pham_vi_vi_tri_lich_truc.py, test_report_access_db.py, test_ke_toan_lego_db.py, test_truong_ca_xep_lich_db.py

### `/settings/booking-policy` — Luật đặt lịch
- page: `src/dashboard/app/(dashboard)/settings/booking-policy/page.tsx` · quyền: lego `cai_dat` (Cài đặt phòng khám · mặc định: Quản lý)
- thành phần: app/(dashboard)/settings/BookingPolicyCard.tsx, app/(dashboard)/settings/GioCaLamViecCard.tsx, app/(dashboard)/settings/LuatBacSiCard.tsx, app/(dashboard)/settings/MeasuredDurationCard.tsx, app/(dashboard)/settings/OverridePolicyCard.tsx, app/(dashboard)/form-ui.ts
- gọi API Next: `/api/ca-lam-viec`, `/api/booking-rules/doctor`, `/api/booking-rules`, `/api/booking-overrides/doctor/[id]`, `/api/booking-overrides/slot/[id]`, `/api/booking-policy`
- gọi thẳng backend (server): `/api/v1/booking-rules/thoi-luong-do`, `/api/v1/booking-rules/doctor`, `/api/v1/catalog/locations`, `/api/v1/catalog/service-types`, `/api/v1/staff/bac-si-dat-duoc`
- service: LuatBacSiService.{xem_thu, danh_sach, luu, xoa} · BookingOverrideService.{save_rule, delete_doctor_override, delete_slot_override} · ClinicSettingsService.update_booking_policy
- test: test_cua_ngo_ghi_moi.py, test_clinic_settings_service.py

### `/settings/clinic-config` — Cấu trúc phòng khám
- page: `src/dashboard/app/(dashboard)/settings/clinic-config/page.tsx` · quyền: lego `cai_dat` (Cài đặt phòng khám · mặc định: Quản lý)
- thành phần: ClinicConfigBoard.tsx, types.ts, ChonCoSoDangNhap.tsx, CoSoPhong.tsx
- gọi API Next: `/api/clinic-config`, `/api/day-noi`, `/api/roster`
- gọi thẳng backend (server): `/api/v1/clinic-config/overview`, `/api/v1/clinic-config/staff`, `/api/v1/clinic-config/services`
- service: ClinicConfigService.{staff, services, overview, set_room_floor, +12} · LichPhongService.tuan · thu_ky_bac_si · DayNoiService.{doc, tao_vi_tri} · LichTrucPhienBanService.xem · RosterService.{applied_weeks, tram_cho_nhan_vien, bac_si_trong_ngay, apply_week, +3}
- test: test_phong_la_tai_nguyen_db.py, test_clinic_config.py, test_clinical_cluster.py, test_lich_truc_phien_ban_db.py, test_pham_vi_vi_tri_lich_truc.py (+11)

### `/settings/day-noi` — Dây nối nghiệp vụ
- page: `src/dashboard/app/(dashboard)/settings/day-noi/page.tsx` · quyền: lego `cai_dat` (Cài đặt phòng khám · mặc định: Quản lý)
- thành phần: DayNoiBoard.tsx, LamThemTaiQuayCauHinh.tsx
- gọi API Next: `/api/day-noi`, `/api/lam-them`, `/api/cashier`
- service: DayNoiService.{doc, dat_day, dat_chuong, tao_vi_tri, +2} · LamThemTaiQuayService.{cau_hinh, nut_cho_luot, luu_muc, bo_muc, +1} · CashierBoardService.{board, giao_dich} · CashierScopeService.{authorize_active, days, authorize, receipt, +1} · QuayThuService.{lich_su, phieu, phieu_cua_luot}
- test: test_day_noi_nhac_db.py, test_cashier_scope_db.py, test_lam_them_tai_quay_db.py, test_cashier_scope.py, test_payment_access.py (+8)

### `/settings/don-du-lieu-thu` — Dọn dữ liệu thử
- page: `src/dashboard/app/(dashboard)/settings/don-du-lieu-thu/page.tsx` · quyền: lego `nhan_su` (Nhân sự & phân quyền · mặc định: Quản lý)
- thành phần: DonDuLieuThu.tsx
- gọi API Next: `/api/don-du-lieu-thu`
- gọi thẳng backend (server): `/api/v1/quan-tri/don-du-lieu-thu`
- service: DonDuLieuThuService.{danh_sach, xem_truoc, xoa}

### `/settings/mau-ket-qua` — Mẫu kết quả
- page: `src/dashboard/app/(dashboard)/settings/mau-ket-qua/page.tsx` · quyền: lego `cai_dat` (Cài đặt phòng khám · mặc định: Quản lý)
- thành phần: MauKetQuaView.tsx, GanMau.tsx, SuaMau.tsx, du-lieu.ts
- gọi API Next: `/api/mau-ket-qua`
- service: MauKetQuaService.{bang_gan, de_xuat, gan, go, +1} · FormEngineService.{doc_bieu_mau, xuat_ban}
- test: test_man_mau_ket_qua_db.py, test_mau_ket_qua_db.py, test_form_engine_db.py, test_mau_mo_ta_db.py

### `/settings/new-user`
- page: `src/dashboard/app/(dashboard)/settings/new-user/page.tsx` · quyền: lego `nhan_su` (Nhân sự & phân quyền · mặc định: Quản lý)
- thành phần: NewUserForm.tsx
- gọi API Next: `/api/admin/users`
- gọi thẳng backend (server): `/api/v1/staff/tai-khoan`
- service: audit · TaiKhoanService.{doc, noi, thu_hoi} · can · cashier_navigation_service · StaffService.{ca_truc_tuong_lai, deactivate, activate}
- test: test_dieu_phoi_api_1509.py, test_staff_service.py, test_cashier_navigation.py, test_cua_quyen_lego.py, test_doi_nguoi_trong_ca_db.py (+4)

### `/settings/tai-khoan` — Thiết lập tài khoản cho nhân viên
- page: `src/dashboard/app/(dashboard)/settings/tai-khoan/page.tsx` · quyền: lego `nhan_su` (Nhân sự & phân quyền · mặc định: Quản lý)
- thành phần: app/(dashboard)/settings/AccountActions.tsx
- gọi API Next: `/api/admin/users`
- gọi thẳng backend (server): `/api/v1/staff/tai-khoan`
- service: audit · TaiKhoanService.{doc, noi, thu_hoi} · can · cashier_navigation_service · StaffService.{ca_truc_tuong_lai, deactivate, activate}
- test: test_dieu_phoi_api_1509.py, test_staff_service.py, test_cashier_navigation.py, test_cua_quyen_lego.py, test_doi_nguoi_trong_ca_db.py (+4)

### `/sieu-am`
- page: `src/dashboard/app/(dashboard)/sieu-am/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/sono`
- page: `src/dashboard/app/(dashboard)/sono/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/tasks`
- page: `src/dashboard/app/(dashboard)/tasks/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/thu-ngan/dich-vu` — Thu ngân dịch vụ
- page: `src/dashboard/app/(dashboard)/thu-ngan/dich-vu/page.tsx` · quyền: lego `thu_tien_dv` (Thanh toán dịch vụ · mặc định: Lễ tân, thu ngân)
- thành phần: app/(dashboard)/thu-ngan/TabThuNgan.tsx, app/(dashboard)/_lam-viec/dung-ngay-xem.ts, app/(dashboard)/thu-ngan/GiaoDich.tsx, app/(dashboard)/thu-ngan/LichSuThu.tsx, app/(dashboard)/thu-ngan/NgayTruc.tsx, app/(dashboard)/thu-ngan/QuayThuNgan.tsx
- gọi API Next: `/api/payment/anh-ck`, `/api/quay-thuoc`, `/api/payment`, `/api/reception/checkout`, `/api/phieu-kham`, `/api/luot-kham`, `/api/cashier`
- service: payment_access_service · AnhChuyenKhoanService.{doc, tai_len, go} · CashierScopeService.{authorize_any_active, authorize_active, days, authorize, +2} · nhan_tep_luong · QuayThuocService.{doc, chon, doi_so_luong, luu_dong_them} · HoanTienService.{tao, xac_nhan, dong, hoan_tien_thua} (+25 service)
- test: test_payment_access.py, test_phieu_kham_db.py, test_bio_chi_dinh_db.py, test_cashier_scope_db.py, test_phieu_kham_luot_db.py (+69)

### `/thu-ngan/dich-vu/lich-su` — Lịch sử thu dịch vụ
- page: `src/dashboard/app/(dashboard)/thu-ngan/dich-vu/lich-su/page.tsx` · quyền: lego `thu_tien_dv` (Thanh toán dịch vụ · mặc định: Lễ tân, thu ngân)
- thành phần: app/(dashboard)/thu-ngan/TabThuNgan.tsx, app/(dashboard)/_lam-viec/dung-ngay-xem.ts, app/(dashboard)/thu-ngan/GiaoDich.tsx, app/(dashboard)/thu-ngan/LichSuThu.tsx, app/(dashboard)/thu-ngan/NgayTruc.tsx, app/(dashboard)/thu-ngan/QuayThuNgan.tsx
- gọi API Next: `/api/payment/anh-ck`, `/api/quay-thuoc`, `/api/payment`, `/api/reception/checkout`, `/api/phieu-kham`, `/api/luot-kham`, `/api/cashier`
- service: payment_access_service · AnhChuyenKhoanService.{doc, tai_len, go} · CashierScopeService.{authorize_any_active, authorize_active, days, authorize, +2} · nhan_tep_luong · QuayThuocService.{doc, chon, doi_so_luong, luu_dong_them} · HoanTienService.{tao, xac_nhan, dong, hoan_tien_thua} (+25 service)
- test: test_payment_access.py, test_phieu_kham_db.py, test_bio_chi_dinh_db.py, test_cashier_scope_db.py, test_phieu_kham_luot_db.py (+69)

### `/thu-ngan/thuoc` — Thu ngân thuốc
- page: `src/dashboard/app/(dashboard)/thu-ngan/thuoc/page.tsx` · quyền: lego `thu_tien_thuoc` (Thu tiền thuốc · mặc định: Lễ tân, thu ngân, dược sĩ)
- thành phần: app/(dashboard)/thu-ngan/TabThuNgan.tsx, app/(dashboard)/_lam-viec/dung-ngay-xem.ts, app/(dashboard)/thu-ngan/GiaoDich.tsx, app/(dashboard)/thu-ngan/LichSuThu.tsx, app/(dashboard)/thu-ngan/NgayTruc.tsx, app/(dashboard)/thu-ngan/QuayThuNgan.tsx
- gọi API Next: `/api/payment/anh-ck`, `/api/quay-thuoc`, `/api/payment`, `/api/reception/checkout`, `/api/phieu-kham`, `/api/luot-kham`, `/api/cashier`
- service: payment_access_service · AnhChuyenKhoanService.{doc, tai_len, go} · CashierScopeService.{authorize_any_active, authorize_active, days, authorize, +2} · nhan_tep_luong · QuayThuocService.{doc, chon, doi_so_luong, luu_dong_them} · HoanTienService.{tao, xac_nhan, dong, hoan_tien_thua} (+25 service)
- test: test_payment_access.py, test_phieu_kham_db.py, test_bio_chi_dinh_db.py, test_cashier_scope_db.py, test_phieu_kham_luot_db.py (+69)

### `/thu-ngan/thuoc/lich-su` — Lịch sử thu thuốc
- page: `src/dashboard/app/(dashboard)/thu-ngan/thuoc/lich-su/page.tsx` · quyền: lego `thu_tien_thuoc` (Thu tiền thuốc · mặc định: Lễ tân, thu ngân, dược sĩ)
- thành phần: app/(dashboard)/thu-ngan/TabThuNgan.tsx, app/(dashboard)/_lam-viec/dung-ngay-xem.ts, app/(dashboard)/thu-ngan/GiaoDich.tsx, app/(dashboard)/thu-ngan/LichSuThu.tsx, app/(dashboard)/thu-ngan/NgayTruc.tsx, app/(dashboard)/thu-ngan/QuayThuNgan.tsx
- gọi API Next: `/api/payment/anh-ck`, `/api/quay-thuoc`, `/api/payment`, `/api/reception/checkout`, `/api/phieu-kham`, `/api/luot-kham`, `/api/cashier`
- service: payment_access_service · AnhChuyenKhoanService.{doc, tai_len, go} · CashierScopeService.{authorize_any_active, authorize_active, days, authorize, +2} · nhan_tep_luong · QuayThuocService.{doc, chon, doi_so_luong, luu_dong_them} · HoanTienService.{tao, xac_nhan, dong, hoan_tien_thua} (+25 service)
- test: test_payment_access.py, test_phieu_kham_db.py, test_bio_chi_dinh_db.py, test_cashier_scope_db.py, test_phieu_kham_luot_db.py (+69)

### `/traffic`
- page: `src/dashboard/app/traffic/page.tsx` · quyền: ?
- gọi API Next: `/api/ops/traffic`
- service: traffic_service.{doc_du_lieu_traffic, xac_thuc_admin, xac_thuc_ma_pin}
- test: test_traffic_service.py

### `/truong-ca` — Điều phối ca
- page: `src/dashboard/app/(dashboard)/truong-ca/page.tsx` · quyền: lego `dieu_phoi` (Điều phối khách · mặc định: Trưởng ca)
- thành phần: app/(dashboard)/LiveBoardSync.tsx, QueuesClient.tsx, load.ts, ChiDinhCuaBacSi.tsx, HistoryClient.tsx, keo-tha.ts, nhan-trang-thai.tsx, shared.tsx (+1)
- gọi API Next: `/api/dispatch-read`, `/api/dispatch/[action]`, `/api/luot-kham`
- gọi thẳng backend (server): `/api/v1/dispatch/overview`, `/api/v1/dispatch/alerts`, `/api/v1/dispatch/routes`, `/api/v1/dispatch/history`, `/api/v1/dispatch/*`
- service: DispatchService.{overview, stations, alerts, history, +5} · DoiBacSiService.{doi, bac_si_trong_phong_kham} · LuotKhamService.{dispatch_order, cho_quyet} · ServiceRoutingService.{assign, invalidate, dat_phong_du_kien, chuyen_phong_dang_lam, +1} · BangLuotKham.{bang, phong_hom_nay, ket_qua_cho_duyet, chi_dinh_hom_nay, +1} · XemLuotService.doc (+8 service)
- test: test_dieu_phoi_api_1509.py, test_loc_co_so_nhom_c_db.py, test_truong_ca_dieu_phoi_db.py, test_bio_chi_dinh_db.py, test_dieu_tri_ban_kham_db.py (+32)

### `/truong-ca/hang-doi`
- page: `src/dashboard/app/(dashboard)/truong-ca/hang-doi/page.tsx` · quyền: lego `dieu_phoi` (Điều phối khách · mặc định: Trưởng ca)
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/truong-ca/lich-su` — Lịch sử điều phối
- page: `src/dashboard/app/(dashboard)/truong-ca/lich-su/page.tsx` · quyền: lego `dieu_phoi` (Điều phối khách · mặc định: Trưởng ca)
- thành phần: app/(dashboard)/truong-ca/HistoryClient.tsx, app/(dashboard)/truong-ca/load.ts, app/(dashboard)/truong-ca/types.ts
- gọi thẳng backend (server): `/api/v1/dispatch/overview`, `/api/v1/dispatch/alerts`, `/api/v1/dispatch/routes`, `/api/v1/dispatch/history`, `/api/v1/dispatch/*`
- service: DispatchService.{overview, stations, alerts, routes, +4} · DoiBacSiService.{bac_si_trong_phong_kham, doi}
- test: test_dieu_phoi_api_1509.py, test_doi_bac_si_theo_quyen_db.py, test_lich_su_dieu_phoi_bam_tay_db.py, test_luat_1509_thu_ky_va_dieu_phoi.py, test_ban_le_thuoc_db.py (+4)

### `/truong-ca/tv` — TV phòng chờ
- page: `src/dashboard/app/(dashboard)/truong-ca/tv/page.tsx` · quyền: lego `dieu_phoi` (Điều phối khách · mặc định: Trưởng ca)
- thành phần: app/(dashboard)/truong-ca/load.ts, app/(dashboard)/truong-ca/ten-phong.ts, app/(dashboard)/truong-ca/types.ts
- gọi thẳng backend (server): `/api/v1/dispatch/overview`, `/api/v1/dispatch/alerts`, `/api/v1/dispatch/routes`, `/api/v1/dispatch/history`, `/api/v1/dispatch/*`
- service: DispatchService.{overview, stations, alerts, routes, +4} · DoiBacSiService.{bac_si_trong_phong_kham, doi}
- test: test_dieu_phoi_api_1509.py, test_doi_bac_si_theo_quyen_db.py, test_lich_su_dieu_phoi_bam_tay_db.py, test_luat_1509_thu_ky_va_dieu_phoi.py, test_ban_le_thuoc_db.py (+4)

### `/tu-van` — Bàn khám tư vấn
- page: `src/dashboard/app/(dashboard)/tu-van/page.tsx` · quyền: lego `tu_van` (Khám tư vấn · mặc định: Bác sĩ tư vấn)
- thành phần: app/(dashboard)/ban-kham/BanKham.tsx, app/(dashboard)/_lam-viec/DoiPhong.tsx, app/(dashboard)/_lam-viec/KhungTep.tsx, app/(dashboard)/_lam-viec/XemLuot.tsx, app/(dashboard)/_lam-viec/XemPhieuKetQua.tsx, app/(dashboard)/_lam-viec/api.ts, app/(dashboard)/_lam-viec/dung-chip-lieu-trinh.ts, app/(dashboard)/_lam-viec/dung-ngay-xem.ts (+11)
- gọi API Next: `/api/thai-ky`, `/api/clinical-forms/history`, `/api/clinical-form/andrology-review`, `/api/clinical-record`, `/api/catalog`, `/api/clinical/[visit_id]/[action]`, `/api/clinical-form`, `/api/ultrasound`, `/api/visits/[id]/theo-doi-thu-thuat`, `/api/cskh/khach/[id]` (+14)
- service: ThaiKyService.{doc, cap_nhat, tao} · phan_hoi_thuoc_service · ClinicalFormService.{lich_su_kham, get_form, save_form} · AndrologyReviewService.review · ho_so_lam_sang_doc · y_khoa (+42 service)
- test: test_hoan_tac_moi_thao_tac_db.py, test_phieu_kham_db.py, test_tep_ket_qua.py, test_cashier_scope_db.py, test_hanh_trinh_tu_van_db.py (+98)

### `/viec-can-xu-ly` — Việc cần xử lý
- page: `src/dashboard/app/(dashboard)/viec-can-xu-ly/page.tsx` · quyền: lego `viec_can_xu_ly` (Việc cần xử lý · mặc định: Quản lý, trưởng ca)
- thành phần: BangViecCanXuLy.tsx, app/(dashboard)/_lam-viec/NutXemLuot.tsx
- gọi API Next: `/api/work-items`, `/api/work-items/[id]/commands/[command]`, `/api/cashier`
- service: QUYEN_THEO_KHU.get · can · WorkItemService.{list_worklist, issue} · CashierBoardService.{board, giao_dich} · CashierScopeService.{authorize_active, days, authorize, receipt, +1} · QuayThuService.{lich_su, phieu, phieu_cua_luot}
- test: test_cashier_scope_db.py, test_cashier_scope.py, test_payment_access.py, test_doi_hinh_thuc_db.py, test_tach_thu_thuoc_dich_vu_db.py (+11)

### `/work-sessions`
- page: `src/dashboard/app/(dashboard)/work-sessions/page.tsx` · quyền: ?
- gọi API: (không thấy — màn tĩnh, hoặc gọi qua lối không suy được ?)

### `/xac-nhan-ket-qua` — Xác nhận kết quả
- page: `src/dashboard/app/(dashboard)/xac-nhan-ket-qua/page.tsx` · quyền: ?
- thành phần: HangChoXacNhanKetQua.tsx
- gọi API Next: `/api/cskh/ket-qua/cho-xac-nhan`, `/api/cskh/ket-qua/[tepId]/xac-nhan`, `/api/cskh/ket-qua/[tepId]/noi-dung`
- service: TepKetQuaService.{cho_xac_nhan, xac_nhan_tep, mo_de_doc} · media_service · tep_ket_qua_service
- test: test_xac_nhan_tep_ket_qua_db.py, test_tep_ket_qua.py, test_cho_xac_nhan_queue_va_doc_tep_db.py, test_full_chi_dinh_slice_ab_db.py, test_slice1_rail_db.py (+1)

### `/xuat-hoa-don` — Xuất hoá đơn
- page: `src/dashboard/app/(dashboard)/xuat-hoa-don/page.tsx` · quyền: lego `bao_cao` (Báo cáo · mặc định: Quản lý)
- thành phần: XuatHoaDon.tsx, app/(dashboard)/form-ui.ts, app/(dashboard)/hoa-don/types.ts, app/(dashboard)/ke-toan/thue-suat.ts
- gọi API Next: `/api/xuat-hoa-don`
- gọi thẳng backend (server): `/api/v1/catalog/locations`, `/api/v1/catalog/service-types`
- service: XuatHoaDonService.xem · HoaDonMisaService.gan_trang_thai · xuat_hoa_don_service
- test: test_thue_gtgt_db.py, test_hoa_don_misa_db.py, test_sua_ho_so_khach_db.py, test_xuat_hoa_don.py

## 2. API Next → backend (137)

Mỗi `app/api/**/route.ts`: đường `/api/v1` nó proxy → hàm router FastAPI → service.

#### `/api/admin/users` · `src/dashboard/app/api/admin/users/route.ts`
- POST `/api/v1/staff/{id}/nhat-ky-tai-khoan` → `src/clinicai/api/v1/routers/staff.py:ghi_nhat_ky_tai_khoan` → record_event + SQL ngay trong router
- GET `/api/v1/staff/{id}/tai-khoan` → `src/clinicai/api/v1/routers/staff.py:doc_tai_khoan` → TaiKhoanService.doc
- GET `/api/v1/phan-quyen/toi` → `src/clinicai/api/v1/routers/phan_quyen.py:quyen_cua_toi` → quyen_hieu_luc, cashier_navigation, navigation_deadline
- GET `/api/v1/staff/{id}/ca-truc-tuong-lai` → `src/clinicai/api/v1/routers/staff.py:lay_ca_truc_tuong_lai` → StaffService.ca_truc_tuong_lai
- GET `/api/v1/staff/tai-khoan` → `src/clinicai/api/v1/routers/staff.py:danh_sach_tai_khoan` → (SQL ngay trong router, không qua service)
- POST `/api/v1/staff/{id}/tai-khoan/noi` → `src/clinicai/api/v1/routers/staff.py:noi_tai_khoan` → TaiKhoanService.noi
- POST `/api/v1/staff/{id}/khoa-nghi-viec` → `src/clinicai/api/v1/routers/staff.py:khoa_nghi_viec_staff` → StaffService.deactivate
- POST `/api/v1/staff/{id}/mo-lai` → `src/clinicai/api/v1/routers/staff.py:mo_lai_staff` → StaffService.activate
- POST `/api/v1/staff/{id}/tai-khoan/thu-hoi` → `src/clinicai/api/v1/routers/staff.py:thu_hoi_tai_khoan` → TaiKhoanService.thu_hoi
- test: src/tests/api/test_dieu_phoi_api_1509.py, src/tests/unit/test_staff_service.py, src/tests/services/test_cashier_navigation.py (+6)
- màn dùng: /settings/new-user, /settings/tai-khoan

#### `/api/appointments` · `src/dashboard/app/api/appointments/route.ts`
- GET `/api/v1/appointments/sap-toi` → `src/clinicai/api/v1/routers/booking.py:lich_sap_toi` → lich_hen_doc.lich_sap_toi
- GET `/api/v1/appointments/lich-ngay` → `src/clinicai/api/v1/routers/booking.py:lich_ngay` → lich_hen_doc.lich_trong_ngay
- POST `/api/v1/appointments/bookings` → `src/clinicai/api/v1/routers/booking.py:create_booking` → BookingService.create
- PATCH `/api/v1/appointments/{appointment_id}` → `src/clinicai/api/v1/routers/booking.py:apply_appointment_action` → BookingService.apply_action
- test: src/tests/services/test_lich_hen_doc_db.py, src/tests/services/test_huy_lich_tai_cho_db.py, src/tests/test_booking_service.py (+2)
- màn dùng: /appointments, /appointments/cho-xep-bac-si, /ban-kham, /ban-kham/[phong], /customers, /home (+5)

#### `/api/appointments/cho-trong-tuan` · `src/dashboard/app/api/appointments/cho-trong-tuan/route.ts`
- GET `/api/v1/appointments/cho-trong-tuan` → `src/clinicai/api/v1/routers/booking.py:cho_trong_tuan` → bang_tuan, CapacityService
- test: src/tests/services/test_capacity_roster_gate.py, src/tests/services/test_capacity_quote_params.py, src/tests/unit/test_bang_tuan_cho_trong.py
- màn dùng: /appointments, /patients/new

#### `/api/appointments/cho-xep-bac-si` · `src/dashboard/app/api/appointments/cho-xep-bac-si/route.ts`
- GET `/api/v1/appointments/cho-xep-bac-si` → `src/clinicai/api/v1/routers/booking.py:cho_xep_bac_si` → ca_thuoc_co_so + SQL ngay trong router
- POST `/api/v1/appointments/{appointment_id}/bao-xep-bac-si` → `src/clinicai/api/v1/routers/booking.py:bao_xep_bac_si` → ThongBaoService.goi + SQL ngay trong router
- test: src/tests/services/test_so_sua_chi_dinh_db.py, src/tests/unit/test_cua_ngo_ghi_moi.py
- màn dùng: /customers

#### `/api/appointments/doi-dich-vu-kham` · `src/dashboard/app/api/appointments/doi-dich-vu-kham/route.ts`
- GET `/api/v1/appointments/{appointment_id}/doi-dich-vu-kham` → `src/clinicai/api/v1/routers/booking.py:o_doi_dich_vu_kham` → doi_dich_vu_kham.o_doi_dich_vu
- POST `/api/v1/appointments/{appointment_id}/doi-dich-vu-kham` → `src/clinicai/api/v1/routers/booking.py:doi_dich_vu_kham_post` → BookingService.doi_dich_vu_kham
- test: src/tests/services/test_doi_dich_vu_kham_db.py, src/tests/unit/test_doi_dich_vu_kham.py
- màn dùng: /home, /nhac-tai-kham, /reception/queue

#### `/api/appointments/doi-lich-nhanh` · `src/dashboard/app/api/appointments/doi-lich-nhanh/route.ts`
- GET `/api/v1/appointments/{appointment_id}/doi-lich-nhanh` → `src/clinicai/api/v1/routers/booking.py:o_doi_lich_nhanh` → doi_lich_nhanh.o_doi_lich
- POST `/api/v1/appointments/{appointment_id}/doi-lich-nhanh` → `src/clinicai/api/v1/routers/booking.py:doi_lich_nhanh_post` → BookingService.doi_lich_nhanh
- test: src/tests/services/test_doi_lich_nhanh_db.py, src/tests/unit/test_chan_dat_ngoai_khung_ca.py
- màn dùng: /appointments, /home, /reception/queue

#### `/api/appointments/luoi-ngay` · `src/dashboard/app/api/appointments/luoi-ngay/route.ts`
- GET `/api/v1/appointments/luoi-ngay` → `src/clinicai/api/v1/routers/booking.py:luoi_ngay_dat_cho` → luoi_ngay, CapacityService
- test: src/tests/services/test_capacity_quote_params.py, src/tests/services/test_capacity_roster_gate.py, src/tests/services/test_dat_lich_theo_co_so_db.py (+1)
- màn dùng: /appointments, /customers, /home, /patients/new, /reception/queue

#### `/api/appointments/quote` · `src/dashboard/app/api/appointments/quote/route.ts`
- GET `/api/v1/appointments/quote` → `src/clinicai/api/v1/routers/booking.py:capacity_quote` → CapacityService.quote
- test: src/tests/services/test_capacity_quote_params.py, src/tests/services/test_capacity_roster_gate.py
- màn dùng: /appointments, /patients/new

#### `/api/appointments/service-history` · `src/dashboard/app/api/appointments/service-history/route.ts`
- GET `/api/v1/appointments/lich-su-dich-vu` → `src/clinicai/api/v1/routers/booking.py:lich_su_dich_vu` → lich_hen_doc.lich_su_dich_vu
- test: src/tests/services/test_lich_hen_doc_db.py
- màn dùng: /appointments, /customers, /patients/new

#### `/api/appointments/slot-hold` · `src/dashboard/app/api/appointments/slot-hold/route.ts`
- DELETE `/api/v1/appointments/slot-hold` → `src/clinicai/api/v1/routers/booking.py:release_slot` → SlotHoldService.release
- GET `/api/v1/appointments/slot-hold` → `src/clinicai/api/v1/routers/booking.py:list_slot_holds` → SlotHoldService.active
- POST `/api/v1/appointments/slot-hold` → `src/clinicai/api/v1/routers/booking.py:hold_slot` → SlotHoldService.hold
- màn dùng: /appointments, /patients/new

#### `/api/appointments/tim-khach` · `src/dashboard/app/api/appointments/tim-khach/route.ts`
- GET `/api/v1/appointments/tim-khach` → `src/clinicai/api/v1/routers/booking.py:tim_khach_dat_lich` → man_dat_lich_doc.tim_khach
- test: src/tests/services/test_dat_lich_tim_khach_db.py
- màn dùng: /appointments

#### `/api/auth/nhat-ky-doi-mat-khau` · `src/dashboard/app/api/auth/nhat-ky-doi-mat-khau/route.ts`
- POST `/api/v1/me/nhat-ky-doi-mat-khau` → `src/clinicai/api/v1/routers/identity.py:ghi_nhat_ky_doi_mat_khau_ca_nhan` → record_event
- test: src/tests/integration/test_rabbitmq_connectivity.py, src/tests/services/test_smoke_main_174_175_db.py
- màn dùng: /doi-tac

#### `/api/booking-overrides/doctor/[id]` · `src/dashboard/app/api/booking-overrides/doctor/[id]/route.ts`
- DELETE `/api/v1/booking-overrides/doctor/{override_id}` → `src/clinicai/api/v1/routers/config.py:delete_doctor_override` → BookingOverrideService.delete_doctor_override
- màn dùng: /settings/booking-policy

#### `/api/booking-overrides/slot/[id]` · `src/dashboard/app/api/booking-overrides/slot/[id]/route.ts`
- DELETE `/api/v1/booking-overrides/slot/{override_id}` → `src/clinicai/api/v1/routers/config.py:delete_slot_override` → BookingOverrideService.delete_slot_override
- màn dùng: /settings/booking-policy

#### `/api/booking-policy` · `src/dashboard/app/api/booking-policy/route.ts`
- PATCH `/api/v1/booking-policy` → `src/clinicai/api/v1/routers/config.py:update_booking_policy` → ClinicSettingsService.update_booking_policy
- test: src/tests/unit/test_clinic_settings_service.py
- màn dùng: /settings, /settings/booking-policy

#### `/api/booking-rules` · `src/dashboard/app/api/booking-rules/route.ts`
- POST `/api/v1/booking-rules` → `src/clinicai/api/v1/routers/config.py:save_booking_rule` → BookingOverrideService.save_rule
- màn dùng: /settings/booking-policy

#### `/api/booking-rules/doctor` · `src/dashboard/app/api/booking-rules/doctor/route.ts`
- GET `/api/v1/booking-rules/doctor/xem-thu` → `src/clinicai/api/v1/routers/config.py:preview_doctor_rule` → LuatBacSiService.xem_thu
- GET `/api/v1/booking-rules/doctor` → `src/clinicai/api/v1/routers/config.py:list_doctor_rules` → LuatBacSiService.danh_sach
- PUT `/api/v1/booking-rules/doctor` → `src/clinicai/api/v1/routers/config.py:save_doctor_rule` → LuatBacSiService.luu
- DELETE `/api/v1/booking-rules/doctor/{luat_id}` → `src/clinicai/api/v1/routers/config.py:delete_doctor_rule` → LuatBacSiService.xoa
- test: src/tests/unit/test_cua_ngo_ghi_moi.py
- màn dùng: /settings/booking-policy

#### `/api/ca-lam-viec` · `src/dashboard/app/api/ca-lam-viec/route.ts`
- GET `/api/v1/ca-lam-viec` → `src/clinicai/api/v1/routers/config.py:doc_ca_lam_viec` → (SQL ngay trong router, không qua service)
- PATCH `/api/v1/ca-lam-viec` → `src/clinicai/api/v1/routers/config.py:sua_ca_lam_viec` → (SQL ngay trong router, không qua service)
- màn dùng: /settings/booking-policy

#### `/api/cashier` · `src/dashboard/app/api/cashier/route.ts`
- GET `/api/v1/cashier/board` → `src/clinicai/api/v1/routers/cashier.py:cashier_board` → CashierBoardService.board, CashierScopeService.authorize_active
- GET `/api/v1/cashier/ngay-truc` → `src/clinicai/api/v1/routers/cashier.py:cashier_ngay_truc` → CashierScopeService.days
- GET `/api/v1/cashier/giao-dich` → `src/clinicai/api/v1/routers/cashier.py:cashier_giao_dich` → CashierScopeService.authorize, CashierBoardService.giao_dich
- GET `/api/v1/cashier/lich-su` → `src/clinicai/api/v1/routers/cashier.py:cashier_lich_su` → CashierScopeService.authorize, QuayThuService.lich_su
- `/api/v1/cashier/lich-su.${xem` → ?
- GET `/api/v1/cashier/phieu/{phieu_id}` → `src/clinicai/api/v1/routers/cashier.py:cashier_phieu` → CashierScopeService.receipt, QuayThuService.phieu
- GET `/api/v1/cashier/phieu-luot/{visit_id}` → `src/clinicai/api/v1/routers/cashier.py:cashier_phieu_luot` → QuayThuService.phieu_cua_luot, CashierScopeService.receipt_exempt, CashierScopeService.receipt, QuayThuService.phieu + SQL ngay trong router
- test: src/tests/services/test_cashier_scope_db.py, src/tests/unit/test_cashier_scope.py, src/tests/unit/test_payment_access.py (+6)
- màn dùng: /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /hanh-trinh, /home (+15)

#### `/api/catalog` · `src/dashboard/app/api/catalog/route.ts`
- GET `/api/v1/catalog/danh-muc-ke` → `src/clinicai/api/v1/routers/catalog.py:danh_muc_ke` → (SQL ngay trong router, không qua service)
- màn dùng: /ban-kham, /ban-kham/[phong], /patient-list, /tu-van

#### `/api/catalog/dich-vu-dat-lich` · `src/dashboard/app/api/catalog/dich-vu-dat-lich/route.ts`
- GET `/api/v1/catalog/dich-vu-dat-lich` → `src/clinicai/api/v1/routers/catalog.py:dich_vu_dat_lich_nhom` → dich_vu_dat_lich.doc
- test: src/tests/services/test_nhom_dich_vu_dat_lich_db.py
- màn dùng: /appointments, /customers, /home, /patients/new, /reception/queue

#### `/api/clinic-config` · `src/dashboard/app/api/clinic-config/route.ts`
- [staff] GET `/api/v1/clinic-config/staff` → `src/clinicai/api/v1/routers/clinic_config.py:staff` → ClinicConfigService.staff
- [lich-phong] GET `/api/v1/clinic-config/lich-phong` → `src/clinicai/api/v1/routers/clinic_config.py:lich_phong` → LichPhongService.tuan
- [services] GET `/api/v1/clinic-config/services` → `src/clinicai/api/v1/routers/clinic_config.py:services` → ClinicConfigService.services
- GET `/api/v1/clinic-config/overview` → `src/clinicai/api/v1/routers/clinic_config.py:overview` → ClinicConfigService.overview
- [room-floor] PUT `/api/v1/clinic-config/room-floor` → `src/clinicai/api/v1/routers/clinic_config.py:set_room_floor` → ClinicConfigService.set_room_floor
- [room-name] PUT `/api/v1/clinic-config/room-name` → `src/clinicai/api/v1/routers/clinic_config.py:rename_room` → ClinicConfigService.rename_room
- [room-active] PUT `/api/v1/clinic-config/room-active` → `src/clinicai/api/v1/routers/clinic_config.py:set_room_active` → ClinicConfigService.set_room_active
- [room-nodes] PUT `/api/v1/clinic-config/room-nodes` → `src/clinicai/api/v1/routers/clinic_config.py:set_room_nodes` → ClinicConfigService.set_room_nodes
- [room-node-chuyen] PUT `/api/v1/clinic-config/room-node-chuyen` → `src/clinicai/api/v1/routers/clinic_config.py:set_room_node_chuyen` → ClinicConfigService.set_room_node_chuyen
- [room-services] PUT `/api/v1/clinic-config/room-services` → `src/clinicai/api/v1/routers/clinic_config.py:set_room_services` → ClinicConfigService.set_room_services
- [service-rooms] PUT `/api/v1/clinic-config/service-rooms` → `src/clinicai/api/v1/routers/clinic_config.py:set_service_rooms` → ClinicConfigService.set_service_rooms
- [staff-nodes] PUT `/api/v1/clinic-config/staff-nodes` → `src/clinicai/api/v1/routers/clinic_config.py:set_staff_nodes` → ClinicConfigService.set_staff_nodes
- [service-form] PUT `/api/v1/clinic-config/service-form` → `src/clinicai/api/v1/routers/clinic_config.py:set_service_form` → ClinicConfigService.set_service_form
- [service-type] PUT `/api/v1/clinic-config/service-type` → `src/clinicai/api/v1/routers/clinic_config.py:update_service_type` → ClinicConfigService.update_service_type
- [thu-ky-bac-si] PUT `/api/v1/clinic-config/thu-ky-bac-si` → `src/clinicai/api/v1/routers/clinic_config.py:set_thu_ky_bac_si` → dat_bac_si_cho_thu_ky
- [location] PUT `/api/v1/clinic-config/location` → `src/clinicai/api/v1/routers/clinic_config.py:update_location` → ClinicConfigService.update_location
- [chon-co-so] PUT `/api/v1/clinic-config/chon-co-so` → `src/clinicai/api/v1/routers/clinic_config.py:set_chon_co_so` → ClinicConfigService.set_chon_co_so
- POST `/api/v1/clinic-config/locations` → `src/clinicai/api/v1/routers/clinic_config.py:create_location` → ClinicConfigService.create_location
- POST `/api/v1/clinic-config/rooms` → `src/clinicai/api/v1/routers/clinic_config.py:create_room` → ClinicConfigService.create_room
- test: src/tests/services/test_phong_la_tai_nguyen_db.py, src/tests/services/test_clinic_config.py, src/tests/services/test_phong_lam_theo_dich_vu_db.py (+6)
- màn dùng: /cashier/dich-vu, /settings/clinic-config

#### `/api/clinical-form` · `src/dashboard/app/api/clinical-form/route.ts`
- GET `/api/v1/clinical-forms` → `src/clinicai/api/v1/routers/clinical_forms.py:read_clinical_form` → ClinicalFormService.get_form, ghi_mo_ho_so
- PUT `/api/v1/clinical-forms` → `src/clinicai/api/v1/routers/clinical_forms.py:save_clinical_form` → ClinicalFormService.save_form
- test: src/tests/api/test_clinical_read_and_legacy_boundaries.py, src/tests/api/test_resource_abuse_guards.py, src/tests/services/test_doc_luot_v5_sinh_hieu_buoi_db.py (+1)
- màn dùng: /ban-kham, /ban-kham/[phong], /patient-list, /tu-van

#### `/api/clinical-form/andrology-review` · `src/dashboard/app/api/clinical-form/andrology-review/route.ts`
- POST `/api/v1/clinical-forms/andrology-review` → `src/clinicai/api/v1/routers/clinical_forms.py:andrology_review` → AndrologyReviewService.review
- test: src/tests/services/test_andrology_review.py
- màn dùng: /ban-kham, /ban-kham/[phong], /tu-van

#### `/api/clinical-forms/history` · `src/dashboard/app/api/clinical-forms/history/route.ts`
- GET `/api/v1/clinical-forms/history` → `src/clinicai/api/v1/routers/clinical_forms.py:read_exam_history` → doc_theo_khach, ClinicalFormService.lich_su_kham
- test: src/tests/services/test_doc_luot_v5_sinh_hieu_buoi_db.py, src/tests/services/test_phan_hoi_thuoc_cot_db.py, src/tests/services/test_phan_hoi_thuoc_db.py
- màn dùng: /ban-kham, /ban-kham/[phong], /tu-van

#### `/api/clinical-record` · `src/dashboard/app/api/clinical-record/route.ts`
- GET `/api/v1/clinical-records/doc` → `src/clinicai/api/v1/routers/clinical_records.py:doc_ho_so_lam_sang` → doc_ho_so, ghi_mo_ho_so
- POST `/api/v1/clinical-records` → `src/clinicai/api/v1/routers/clinical_records.py:save_clinical_record` → ClinicalRecordService.save
- test: src/tests/api/test_clinical_read_and_legacy_boundaries.py, src/tests/api/test_resource_abuse_guards.py, src/tests/services/test_clinical_record_revision_sql.py (+3)
- màn dùng: /ban-kham, /ban-kham/[phong], /patient-list, /tu-van

#### `/api/clinical/[visit_id]/[action]` · `src/dashboard/app/api/clinical/[visit_id]/[action]/route.ts`
- GET `/api/v1/clinical/{visit_id:uuid}/status` → `src/clinicai/api/v1/routers/clinical_sign.py:clinical_status` → ClinicalSignService.status
- POST `/api/v1/clinical/{visit_id:uuid}/amend` → `src/clinicai/api/v1/routers/clinical_sign.py:amend` → ClinicalSignService.amend
- POST `/api/v1/clinical/{visit_id:uuid}/release` → `src/clinicai/api/v1/routers/clinical_sign.py:release` → ClinicalSignService.release
- POST `/api/v1/clinical/{visit_id:uuid}/sign` → `src/clinicai/api/v1/routers/clinical_sign.py:sign` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- test: src/tests/services/test_tien_thuoc_cp6_dinh_chinh_da_ky_service_db.py, src/tests/services/test_luat_1509_nhap_chi_dinh_va_ky.py, src/tests/services/test_hoan_tat_khong_khoa_db.py
- màn dùng: /ban-kham, /ban-kham/[phong], /patient-list, /tu-van

#### `/api/config/feature-mode` · `src/dashboard/app/api/config/feature-mode/route.ts`
- GET `/api/v1/feature-mode` → `src/clinicai/api/v1/routers/config.py:get_feature_mode` → ClinicSettingsService.get_feature_mode
- PUT `/api/v1/feature-mode` → `src/clinicai/api/v1/routers/config.py:update_feature_mode` → ClinicSettingsService.update_feature_mode
- test: src/tests/unit/test_clinic_settings_service.py
- màn dùng: /settings

#### `/api/console/feedback` · `src/dashboard/app/api/console/feedback/route.ts`
- POST `/api/v1/console/feedback` → `src/clinicai/api/v1/routers/console.py:add_feedback` → ConsoleService.add_feedback
- màn dùng: /console

#### `/api/cskh-action` · `src/dashboard/app/api/cskh-action/route.ts`
- POST `/api/v1/cskh/actions` → `src/clinicai/api/v1/routers/cskh.py:record_cskh_action` → CskhService.record_action
- màn dùng: /appointments, /patients/new

#### `/api/cskh/hen-goi-lai` · `src/dashboard/app/api/cskh/hen-goi-lai/route.ts`
- POST `/api/v1/cskh/hen-goi-lai` → `src/clinicai/api/v1/routers/cskh.py:tao_hen_goi_lai` → HenGoiLaiService.tao
- PATCH `/api/v1/cskh/hen-goi-lai/{hen_id}` → `src/clinicai/api/v1/routers/cskh.py:dong_hen_goi_lai` → HenGoiLaiService.dong
- test: src/tests/unit/test_so_tuong_tac_cskh.py, src/tests/unit/test_recall_callback_consistency.py
- màn dùng: /customers

#### `/api/cskh/ho-so-kham/[appointmentId]` · `src/dashboard/app/api/cskh/ho-so-kham/[appointmentId]/route.ts`
- GET `/api/v1/cskh/ho-so-kham/{appointment_id}` → `src/clinicai/api/v1/routers/cskh.py:ho_so_kham` → HoSoKhamService.doc
- test: src/tests/services/test_doc_luot_v5_sinh_hieu_buoi_db.py, src/tests/unit/test_ho_so_kham.py
- màn dùng: /customers

#### `/api/cskh/ket-qua` · `src/dashboard/app/api/cskh/ket-qua/route.ts`
- GET `/api/v1/cskh/ket-qua/{clinic_patient_id}` → `src/clinicai/api/v1/routers/cskh.py:danh_sach_ket_qua` → TepKetQuaService.danh_sach, TepKetQuaService.da_xoa_gan_day
- POST `/api/v1/cskh/ket-qua/tep` → `src/clinicai/api/v1/routers/cskh.py:tai_len_ket_qua` → nhan_multipart, TepKetQuaService.tai_len, don_tep_tam, uuid_hoac_loi
- POST `/api/v1/cskh/ket-qua/tep/{tep_id}/da-gui` → `src/clinicai/api/v1/routers/cskh.py:danh_dau_da_gui` → TepKetQuaService.danh_dau_da_gui
- test: src/tests/unit/test_tep_ket_qua.py, src/tests/unit/test_kho_tep_ghi.py, src/tests/services/test_xac_nhan_tep_ket_qua_db.py (+3)
- màn dùng: /ban-kham, /ban-kham/[phong], /customers, /do-sinh-hieu, /doi-tac, /duyet-ket-qua (+4)

#### `/api/cskh/ket-qua/[tepId]/cho-phep-gui` · `src/dashboard/app/api/cskh/ket-qua/[tepId]/cho-phep-gui/route.ts`
- POST `/api/v1/cskh/ket-qua/tep/{tep_id}/cho-phep-gui` → `src/clinicai/api/v1/routers/cskh.py:cho_phep_gui_tep` → TepKetQuaService.cho_phep_gui
- test: src/tests/services/test_smoke_main_174_175_db.py, src/tests/services/test_xac_nhan_tep_ket_qua_db.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/cskh/ket-qua/[tepId]/khoi-phuc` · `src/dashboard/app/api/cskh/ket-qua/[tepId]/khoi-phuc/route.ts`
- POST `/api/v1/cskh/ket-qua/tep/{tep_id}/khoi-phuc` → `src/clinicai/api/v1/routers/cskh.py:khoi_phuc_tep_ket_qua` → TepKetQuaService.khoi_phuc_tep
- test: src/tests/services/test_day_tep_db.py, src/tests/services/test_xoa_mem_tep_db.py
- màn dùng: /ban-kham, /ban-kham/[phong], /customers, /doi-tac, /duyet-ket-qua, /phong/[ma] (+1)

#### `/api/cskh/ket-qua/[tepId]/noi-dung` · `src/dashboard/app/api/cskh/ket-qua/[tepId]/noi-dung/route.ts`
- GET `/api/v1/cskh/ket-qua/tep/{tep_id}/noi-dung` → `src/clinicai/api/v1/routers/cskh.py:doc_tep_ket_qua` → phan_tich_range, TepKetQuaService.mo_de_doc, doc_dan
- test: src/tests/services/test_xac_nhan_tep_ket_qua_db.py, src/tests/unit/test_tep_ket_qua.py, src/tests/services/test_full_chi_dinh_slice_ab_db.py
- màn dùng: /ban-kham, /ban-kham/[phong], /customers, /doi-tac, /duyet-ket-qua, /phong/[ma] (+4)

#### `/api/cskh/ket-qua/[tepId]/xac-nhan` · `src/dashboard/app/api/cskh/ket-qua/[tepId]/xac-nhan/route.ts`
- POST `/api/v1/cskh/ket-qua/tep/{tep_id}/xac-nhan` → `src/clinicai/api/v1/routers/cskh.py:xac_nhan_tep_ket_qua` → TepKetQuaService.xac_nhan_tep
- test: src/tests/services/test_slice1_rail_db.py, src/tests/services/test_xac_nhan_tep_ket_qua_db.py
- màn dùng: /xac-nhan-ket-qua

#### `/api/cskh/ket-qua/[tepId]/xoa` · `src/dashboard/app/api/cskh/ket-qua/[tepId]/xoa/route.ts`
- POST `/api/v1/cskh/ket-qua/tep/{tep_id}/xoa` → `src/clinicai/api/v1/routers/cskh.py:xoa_tep_ket_qua` → TepKetQuaService.xoa_tep
- test: src/tests/services/test_day_tep_db.py, src/tests/services/test_xoa_mem_tep_db.py
- màn dùng: /ban-kham, /ban-kham/[phong], /customers, /doi-tac, /duyet-ket-qua, /phong/[ma] (+1)

#### `/api/cskh/ket-qua/chi-dinh` · `src/dashboard/app/api/cskh/ket-qua/chi-dinh/route.ts`
- GET `/api/v1/cskh/ket-qua/chi-dinh-cua-lich/{appointment_id}` → `src/clinicai/api/v1/routers/cskh.py:chi_dinh_cua_lich` → TepKetQuaService.chi_dinh_cua_lich
- test: src/tests/services/test_in_anh_dot3_db.py
- màn dùng: /customers

#### `/api/cskh/ket-qua/cho-xac-nhan` · `src/dashboard/app/api/cskh/ket-qua/cho-xac-nhan/route.ts`
- GET `/api/v1/cskh/ket-qua/cho-xac-nhan` → `src/clinicai/api/v1/routers/cskh.py:tep_cho_xac_nhan` → TepKetQuaService.cho_xac_nhan
- test: src/tests/services/test_cho_xac_nhan_queue_va_doc_tep_db.py, src/tests/services/test_smoke_main_174_175_db.py
- màn dùng: /xac-nhan-ket-qua

#### `/api/cskh/khach/[id]` · `src/dashboard/app/api/cskh/khach/[id]/route.ts`
- GET `/api/v1/cskh/khach/{clinic_patient_id}/tom-tat` → `src/clinicai/api/v1/routers/cskh.py:tom_tat_khach` → GhiChuKhachService.tom_tat
- GET `/api/v1/cskh/khach/{clinic_patient_id}/ghi-chu` → `src/clinicai/api/v1/routers/cskh.py:ghi_chu_cua_khach` → GhiChuKhachService.danh_sach
- GET `/api/v1/cskh/khach/{clinic_patient_id}/phan-hoi-thuoc` → `src/clinicai/api/v1/routers/cskh.py:phan_hoi_thuoc_cua_khach` → PhanHoiThuocService.doc
- POST `/api/v1/cskh/khach/{clinic_patient_id}/ghi-chu` → `src/clinicai/api/v1/routers/cskh.py:ghi_chu_moi` → GhiChuKhachService.ghi
- POST `/api/v1/cskh/ghi-chu/{ghi_chu_id}/go` → `src/clinicai/api/v1/routers/cskh.py:go_ghi_chu` → GhiChuKhachService.go
- POST `/api/v1/cskh/khach/{clinic_patient_id}/phan-hoi-thuoc` → `src/clinicai/api/v1/routers/cskh.py:ghi_phan_hoi_thuoc` → PhanHoiThuocService.ghi
- POST `/api/v1/cskh/phan-hoi-thuoc/{phan_hoi_id}/go` → `src/clinicai/api/v1/routers/cskh.py:go_phan_hoi_thuoc` → PhanHoiThuocService.go
- test: src/tests/services/test_ghi_chu_khach_db.py, src/tests/services/test_phan_hoi_thuoc_db.py, src/tests/services/test_hen_tai_kham_db.py (+1)
- màn dùng: /ban-kham, /ban-kham/[phong], /customers, /patient-list, /tu-van

#### `/api/cskh/lieu-trinh` · `src/dashboard/app/api/cskh/lieu-trinh/route.ts`
- GET `/api/v1/lieu-trinh/theo-khach/{clinic_patient_id}` → `src/clinicai/api/v1/routers/lieu_trinh.py:theo_khach` → LieuTrinhService.theo_khach
- GET `/api/v1/lieu-trinh/cskh` → `src/clinicai/api/v1/routers/lieu_trinh.py:cskh` → LieuTrinhService.cskh
- test: src/tests/services/test_lieu_trinh_db.py
- màn dùng: /customers, /nhac-tai-kham

#### `/api/cskh/lieu-trinh/[id]` · `src/dashboard/app/api/cskh/lieu-trinh/[id]/route.ts`
- GET `/api/v1/lieu-trinh/{lieu_trinh_id}/lich-su` → `src/clinicai/api/v1/routers/lieu_trinh.py:lich_su` → LieuTrinhService.lich_su
- POST `/api/v1/lieu-trinh/{lieu_trinh_id}/da-xu-ly-sap-het` → `src/clinicai/api/v1/routers/lieu_trinh.py:da_xu_ly_sap_het` → LieuTrinhService.da_xu_ly_sap_het
- POST `/api/v1/lieu-trinh/{lieu_trinh_id}/dang-ky` → `src/clinicai/api/v1/routers/lieu_trinh.py:dang_ky` → LieuTrinhService.dang_ky
- POST `/api/v1/lieu-trinh/{lieu_trinh_id}/dieu-chinh` → `src/clinicai/api/v1/routers/lieu_trinh.py:dieu_chinh` → LieuTrinhService.dieu_chinh
- POST `/api/v1/lieu-trinh/{lieu_trinh_id}/dung` → `src/clinicai/api/v1/routers/lieu_trinh.py:dung` → LieuTrinhService.dung
- POST `/api/v1/lieu-trinh/{lieu_trinh_id}/hoan-tac` → `src/clinicai/api/v1/routers/lieu_trinh.py:hoan_tac` → LieuTrinhService.hoan_tac
- POST `/api/v1/lieu-trinh/{lieu_trinh_id}/mo-lai` → `src/clinicai/api/v1/routers/lieu_trinh.py:mo_lai` → LieuTrinhService.mo_lai
- test: src/tests/services/test_lieu_trinh_db.py
- màn dùng: /customers, /nhac-tai-kham

#### `/api/cskh/nhac-tai-kham` · `src/dashboard/app/api/cskh/nhac-tai-kham/route.ts`
- POST `/api/v1/cskh/nhac-tai-kham` → `src/clinicai/api/v1/routers/cskh.py:create_recall_by_hand` → RecallJobService.tao_thu_cong
- test: src/tests/unit/test_cua_ngo_ghi_moi.py, src/tests/unit/test_recall_callback_consistency.py
- màn dùng: /customers

#### `/api/cskh/phan-hoi` · `src/dashboard/app/api/cskh/phan-hoi/route.ts`
- POST `/api/v1/cskh/phan-hoi` → `src/clinicai/api/v1/routers/cskh.py:ghi_phan_hoi` → PhanHoiKhachService.ghi
- PATCH `/api/v1/cskh/phan-hoi/{phan_hoi_id}` → `src/clinicai/api/v1/routers/cskh.py:cap_nhat_phan_hoi` → PhanHoiKhachService.cap_nhat
- test: src/tests/unit/test_phan_hoi_khach.py
- màn dùng: /customers

#### `/api/cskh/tuong-tac` · `src/dashboard/app/api/cskh/tuong-tac/route.ts`
- GET `/api/v1/cskh/tuong-tac/{clinic_patient_id}` → `src/clinicai/api/v1/routers/cskh.py:lich_su_tuong_tac` → TuongTacCskhService.lich_su
- POST `/api/v1/cskh/tuong-tac` → `src/clinicai/api/v1/routers/cskh.py:ghi_tuong_tac` → TuongTacCskhService.ghi
- test: src/tests/unit/test_so_tuong_tac_cskh.py, src/tests/services/test_phan_hoi_thuoc_db.py, src/tests/unit/test_recall_callback_consistency.py
- màn dùng: /appointments/cho-xep-bac-si, /customers, /home, /nhac-tai-kham, /reception/queue

#### `/api/cskh/tuong-tac/[id]/hoan-tac` · `src/dashboard/app/api/cskh/tuong-tac/[id]/hoan-tac/route.ts`
- POST `/api/v1/cskh/tuong-tac/{tuong_tac_id}/hoan-tac` → `src/clinicai/api/v1/routers/cskh.py:hoan_tac_tuong_tac` → TuongTacCskhService.hoan_tac
- test: src/tests/services/test_man_khach_hang_callback_db.py, src/tests/unit/test_so_tuong_tac_cskh.py
- màn dùng: /customers, /nhac-tai-kham

#### `/api/cskh/zalo` · `src/dashboard/app/api/cskh/zalo/route.ts`
- GET `/api/v1/cskh/zalo/trang-thai` → `src/clinicai/api/v1/routers/cskh.py:zalo_trang_thai` → zalo.dang_bat, zalo.template_cho
- POST `/api/v1/cskh/zalo/gui` → `src/clinicai/api/v1/routers/cskh.py:gui_zalo` → GuiZaloService.gui
- test: src/tests/services/test_zalo_provider.py, src/tests/unit/test_so_tuong_tac_cskh.py, src/tests/unit/test_recall_callback_consistency.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/day-noi` · `src/dashboard/app/api/day-noi/route.ts`
- GET `/api/v1/day-noi` → `src/clinicai/api/v1/routers/day_noi.py:doc_day_noi` → DayNoiService.doc
- [day] PATCH `/api/v1/day-noi/day` → `src/clinicai/api/v1/routers/day_noi.py:dat_day` → DayNoiService.dat_day
- [chuong] PUT `/api/v1/day-noi/chuong` → `src/clinicai/api/v1/routers/day_noi.py:dat_chuong` → DayNoiService.dat_chuong
- [vi-tri-moi] POST `/api/v1/day-noi/vi-tri` → `src/clinicai/api/v1/routers/day_noi.py:tao_vi_tri` → DayNoiService.tao_vi_tri
- [loai-kham] PATCH `/api/v1/day-noi/loai-kham/{service_type_id}` → `src/clinicai/api/v1/routers/day_noi.py:dat_loai_kham` → DayNoiService.dat_loai_kham
- [vi-tri] PATCH `/api/v1/day-noi/vi-tri/{vi_tri_id}` → `src/clinicai/api/v1/routers/day_noi.py:sua_vi_tri` → DayNoiService.sua_vi_tri
- test: src/tests/services/test_day_noi_nhac_db.py, src/tests/services/test_vi_tri_chu_phong_db.py, src/tests/services/test_quay_kho_dot3_db.py
- màn dùng: /settings/clinic-config, /settings/day-noi

#### `/api/dispatch-read` · `src/dashboard/app/api/dispatch-read/route.ts`
- [overview] GET `/api/v1/dispatch/overview` → `src/clinicai/api/v1/routers/dispatch.py:overview` → DispatchService.overview, DispatchService.stations
- [alerts] GET `/api/v1/dispatch/alerts` → `src/clinicai/api/v1/routers/dispatch.py:alerts` → DispatchService.alerts
- [history] GET `/api/v1/dispatch/history` → `src/clinicai/api/v1/routers/dispatch.py:history` → DispatchService.history
- [routes] GET `/api/v1/dispatch/routes` → `src/clinicai/api/v1/routers/dispatch.py:routes` → DispatchService.routes
- [bac-si] GET `/api/v1/dispatch/bac-si` → `src/clinicai/api/v1/routers/dispatch.py:danh_sach_bac_si` → DoiBacSiService.bac_si_trong_phong_kham
- GET `/api/v1/dispatch/chi-dinh/{visit_id}` → `src/clinicai/api/v1/routers/dispatch.py:chi_dinh_cua_luot` → DispatchService.chi_dinh
- test: src/tests/api/test_dieu_phoi_api_1509.py, src/tests/services/test_lich_su_dieu_phoi_bam_tay_db.py, src/tests/services/test_thu_tien_xep_phong_mang_sang_db.py (+6)
- màn dùng: /truong-ca

#### `/api/dispatch/[action]` · `src/dashboard/app/api/dispatch/[action]/route.ts`
- POST `/api/v1/dispatch/move` → `src/clinicai/api/v1/routers/dispatch.py:move` → DispatchService.move
- POST `/api/v1/dispatch/transfer-room` → `src/clinicai/api/v1/routers/dispatch.py:transfer_room` → DispatchService.move
- POST `/api/v1/dispatch/route` → `src/clinicai/api/v1/routers/dispatch.py:apply_route` → DispatchService.apply_route
- PUT `/api/v1/dispatch/threshold` → `src/clinicai/api/v1/routers/dispatch.py:set_threshold` → DispatchService.set_threshold
- POST `/api/v1/dispatch/doi-bac-si` → `src/clinicai/api/v1/routers/dispatch.py:doi_bac_si` → DoiBacSiService.doi
- test: src/tests/api/test_dieu_phoi_api_1509.py, src/tests/services/test_dieu_phoi_chi_chi_dinh_da_duyet.py, src/tests/services/test_doi_bac_si_theo_quyen_db.py (+1)
- màn dùng: /truong-ca

#### `/api/dispatch/alerts-call` · `src/dashboard/app/api/dispatch/alerts-call/route.ts`
- POST `/api/v1/dispatch/alerts/call` → `src/clinicai/api/v1/routers/dispatch.py:call_department` → ThongBaoService.goi
- test: src/tests/services/test_so_sua_chi_dinh_db.py, src/tests/unit/test_cua_ngo_ghi_moi.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/doi-tac` · `src/dashboard/app/api/doi-tac/route.ts`
- GET `/api/v1/doi-tac/viec` → `src/clinicai/api/v1/routers/doi_tac.py:viec_cua_doi_tac` → DoiTacService.viec_doi_tac
- POST `/api/v1/doi-tac/ket-qua` → `src/clinicai/api/v1/routers/doi_tac.py:gui_ket_qua` → nhan_multipart, uuid_hoac_loi, TepKetQuaService.tai_len, don_tep_tam
- test: src/tests/unit/test_tep_ket_qua.py, src/tests/unit/test_kho_tep_ghi.py, src/tests/services/test_lay_mau_doi_tac_db.py (+2)
- màn dùng: /doi-tac

#### `/api/doi-tac/cho-tai-lieu` · `src/dashboard/app/api/doi-tac/cho-tai-lieu/route.ts`
- POST `/api/v1/doi-tac/viec/{chi_dinh_id}/cho-tai-lieu` → `src/clinicai/api/v1/routers/doi_tac.py:cho_tai_lieu` → DoiTacService.doi_tac_cho_tai_lieu
- test: src/tests/services/test_doi_tac_nhan_mau_la_xong_db.py, src/tests/services/test_mau_gui_doi_tac_db.py
- màn dùng: /doi-tac

#### `/api/doi-tac/da-lay-mau` · `src/dashboard/app/api/doi-tac/da-lay-mau/route.ts`
- POST `/api/v1/doi-tac/viec/{chi_dinh_id}/da-lay-mau` → `src/clinicai/api/v1/routers/doi_tac.py:da_lay_mau` → DoiTacService.doi_tac_da_lay_mau
- test: src/tests/services/test_doi_tac_nhan_viec_db.py, src/tests/services/test_lay_mau_doi_tac_db.py
- màn dùng: /doi-tac

#### `/api/doi-tac/da-thu-tien` · `src/dashboard/app/api/doi-tac/da-thu-tien/route.ts`
- POST `/api/v1/doi-tac/viec/{chi_dinh_id}/da-thu-tien` → `src/clinicai/api/v1/routers/doi_tac.py:da_thu_tien` → DoiTacService.ghi_nhan_da_thu
- test: src/tests/services/test_doi_tac_tu_thu_db.py, src/tests/services/test_mau_gui_doi_tac_db.py
- màn dùng: /doi-tac

#### `/api/doi-tac/huy-da-thu` · `src/dashboard/app/api/doi-tac/huy-da-thu/route.ts`
- POST `/api/v1/doi-tac/viec/{chi_dinh_id}/huy-da-thu` → `src/clinicai/api/v1/routers/doi_tac.py:huy_da_thu` → DoiTacService.huy_da_thu
- test: src/tests/services/test_doi_tac_tu_thu_db.py
- màn dùng: /doi-tac

#### `/api/don-du-lieu-thu` · `src/dashboard/app/api/don-du-lieu-thu/route.ts`
- GET `/api/v1/quan-tri/don-du-lieu-thu` → `src/clinicai/api/v1/routers/don_du_lieu_thu.py:danh_sach` → DonDuLieuThuService.danh_sach
- POST `/api/v1/quan-tri/don-du-lieu-thu/xem-truoc` → `src/clinicai/api/v1/routers/don_du_lieu_thu.py:xem_truoc` → DonDuLieuThuService.xem_truoc
- POST `/api/v1/quan-tri/don-du-lieu-thu/xoa` → `src/clinicai/api/v1/routers/don_du_lieu_thu.py:xoa` → DonDuLieuThuService.xoa
- màn dùng: /settings/don-du-lieu-thu

#### `/api/events/stream` · `src/dashboard/app/api/events/stream/route.ts`
- GET `/api/v1/events/stream` → `src/clinicai/api/v1/routers/events.py:stream` → ?
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/ho-so-kham` · `src/dashboard/app/api/ho-so-kham/route.ts`
- GET `/api/v1/ho-so-kham/lich-su` → `src/clinicai/api/v1/routers/ho_so_kham.py:lich_su` → lich_su_luot.doc, doc_duoc_in_phieu, doi_mot_quyen
- GET `/api/v1/ho-so-kham/{visit_id}/dich-vu` → `src/clinicai/api/v1/routers/ho_so_kham.py:doc_dich_vu` → ho_so_dich_vu.doc
- GET `/api/v1/ho-so-kham/{visit_id}/dieu-tri` → `src/clinicai/api/v1/routers/ho_so_kham.py:doc_dieu_tri` → dieu_tri_ban_kham.doc_the
- GET `/api/v1/ho-so-kham/{visit_id}/ghi-chu` → `src/clinicai/api/v1/routers/ho_so_kham.py:doc_ghi_chu` → ghi_chu_luot.doc
- PUT `/api/v1/ho-so-kham/{visit_id}/ghi-chu` → `src/clinicai/api/v1/routers/ho_so_kham.py:luu_ghi_chu` → ghi_chu_luot.luu
- POST `/api/v1/ho-so-kham/{visit_id}/dieu-tri/chon-thu-thuat` → `src/clinicai/api/v1/routers/ho_so_kham.py:chon_thu_thuat` → dieu_tri_ban_kham.chon_thu_thuat
- POST `/api/v1/ho-so-kham/{visit_id}/doi-dich-vu` → `src/clinicai/api/v1/routers/ho_so_kham.py:doi_dich_vu` → ho_so_dich_vu.doi
- POST `/api/v1/ho-so-kham/{visit_id}/dieu-tri/{order_id}/{lenh}` → `src/clinicai/api/v1/routers/ho_so_kham.py:lam_tai_ban_kham` → dieu_tri_ban_kham.thao_tac
- test: src/tests/services/test_dieu_tri_ban_kham_db.py, src/tests/services/test_ghi_chu_luot_db.py, src/tests/services/test_ho_so_kham_db.py (+8)
- màn dùng: /ban-kham, /ban-kham/[phong], /customers, /patient-list, /print/phieu-kham/[visitId], /tu-van

#### `/api/hoa-don` · `src/dashboard/app/api/hoa-don/route.ts`
- GET `/api/v1/hoa-don` → `src/clinicai/api/v1/routers/hoa_don.py:danh_sach_hoa_don` → DanhSachHoaDonService.xem
- GET `/api/v1/hoa-don/xlsx` → `src/clinicai/api/v1/routers/hoa_don.py:danh_sach_hoa_don_excel` → xlsx_hoa_don
- test: src/tests/services/test_an_ton_co_so_ngung_db.py, src/tests/services/test_danh_sach_hoa_don_db.py, src/tests/services/test_danh_sach_hoa_don_viec_ton_db.py (+1)
- màn dùng: /hoa-don

#### `/api/hoa-don/cong-ty/an/[id]` · `src/dashboard/app/api/hoa-don/cong-ty/an/[id]/route.ts`
- PUT `/api/v1/hoa-don/cong-ty/an/{id}` → `src/clinicai/api/v1/routers/hoa_don_cong_ty.py:an_cong_ty_khach` → HoaDonCongTyService.an_cong_ty_khach
- test: src/tests/services/test_hoa_don_cong_ty_db.py, src/tests/services/test_tick_cong_ty_khi_thu_db.py
- màn dùng: /customers

#### `/api/hoa-don/cong-ty/khach/[id]` · `src/dashboard/app/api/hoa-don/cong-ty/khach/[id]/route.ts`
- GET `/api/v1/hoa-don/cong-ty/khach/{clinic_patient_id}` → `src/clinicai/api/v1/routers/hoa_don_cong_ty.py:doc_cong_ty_khach` → HoaDonCongTyService.doc_cong_ty_khach
- PUT `/api/v1/hoa-don/cong-ty/khach/{clinic_patient_id}` → `src/clinicai/api/v1/routers/hoa_don_cong_ty.py:luu_cong_ty_khach` → HoaDonCongTyService.luu_cong_ty_khach
- test: src/tests/services/test_hoa_don_cong_ty_db.py, src/tests/services/test_tick_cong_ty_khi_thu_db.py
- màn dùng: /customers

#### `/api/hoa-don/cong-ty/phieu/[id]` · `src/dashboard/app/api/hoa-don/cong-ty/phieu/[id]/route.ts`
- GET `/api/v1/hoa-don/cong-ty/phieu/{payment_cycle_id}` → `src/clinicai/api/v1/routers/hoa_don_cong_ty.py:doc_cong_ty_hoa_don` → HoaDonCongTyService.doc_hoa_don
- PUT `/api/v1/hoa-don/cong-ty/phieu/{payment_cycle_id}` → `src/clinicai/api/v1/routers/hoa_don_cong_ty.py:ghi_cong_ty_hoa_don` → HoaDonCongTyService.ghi_hoa_don
- DELETE `/api/v1/hoa-don/cong-ty/phieu/{payment_cycle_id}` → `src/clinicai/api/v1/routers/hoa_don_cong_ty.py:bo_cong_ty_hoa_don` → HoaDonCongTyService.bo_hoa_don
- test: src/tests/services/test_hoa_don_cong_ty_db.py, src/tests/services/test_hoa_don_misa_db.py, src/tests/services/test_tick_cong_ty_khi_thu_db.py (+1)
- màn dùng: /hoa-don

#### `/api/hoa-don/cong-ty/phieu/[id]/lich-su` · `src/dashboard/app/api/hoa-don/cong-ty/phieu/[id]/lich-su/route.ts`
- GET `/api/v1/hoa-don/cong-ty/phieu/{payment_cycle_id}/lich-su` → `src/clinicai/api/v1/routers/hoa_don_cong_ty.py:lich_su_cong_ty_hoa_don` → HoaDonCongTyService.doc_lich_su
- test: src/tests/services/test_hoa_don_cong_ty_db.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/ke-toan/thue-suat` · `src/dashboard/app/api/ke-toan/thue-suat/route.ts`
- GET `/api/v1/ke-toan/thue-suat` → `src/clinicai/api/v1/routers/ke_toan.py:xem_thue_suat` → ThueSuatService.xem
- test: src/tests/services/test_thue_gtgt_db.py
- màn dùng: /ke-toan

#### `/api/ke-toan/thue-suat/mat-hang` · `src/dashboard/app/api/ke-toan/thue-suat/mat-hang/route.ts`
- PUT `/api/v1/ke-toan/thue-suat/mat-hang` → `src/clinicai/api/v1/routers/ke_toan.py:dat_thue_mat_hang` → ThueSuatService.dat_mat_hang
- test: src/tests/services/test_thue_gtgt_db.py
- màn dùng: /ke-toan

#### `/api/ke-toan/thue-suat/nhom/[nhom]` · `src/dashboard/app/api/ke-toan/thue-suat/nhom/[nhom]/route.ts`
- PUT `/api/v1/ke-toan/thue-suat/nhom/{nhom}` → `src/clinicai/api/v1/routers/ke_toan.py:dat_thue_nhom` → ThueSuatService.dat_nhom
- test: src/tests/services/test_thue_gtgt_db.py
- màn dùng: /ke-toan

#### `/api/lab-result` · `src/dashboard/app/api/lab-result/route.ts`
- POST `/api/v1/lab/orders` → `src/clinicai/api/v1/routers/lab.py:order_lab_test` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- PATCH `/api/v1/lab/results/{lab_result_id}` → `src/clinicai/api/v1/routers/lab.py:enter_lab_result` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/lab-result/[id]/review` · `src/dashboard/app/api/lab-result/[id]/review/route.ts`
- POST `/api/v1/lab/results/{lab_result_id}/review` → `src/clinicai/api/v1/routers/lab.py:review_and_finalize_lab_result` → LabSafetyService.finalize_review
- test: src/tests/unit/test_lab_safety_service.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/lab-result/[id]/triage` · `src/dashboard/app/api/lab-result/[id]/triage/route.ts`
- POST `/api/v1/lab/triage/{lab_result_id}` → `src/clinicai/api/v1/routers/lab.py:triage_lab_result` → build_lab_triage_subgraph, build_lab_triage_subgraph.ainvoke, LabTriageState
- test: src/tests/graphs/lab_triage/test_lab_triage_skeleton.py, src/tests/graphs/task_manager/test_task_manager_graph.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/lam-them` · `src/dashboard/app/api/lam-them/route.ts`
- GET `/api/v1/lam-them/cau-hinh` → `src/clinicai/api/v1/routers/lam_them_tai_quay.py:doc_cau_hinh` → LamThemTaiQuayService.cau_hinh
- GET `/api/v1/lam-them/nut` → `src/clinicai/api/v1/routers/lam_them_tai_quay.py:nut_cho_luot` → LamThemTaiQuayService.nut_cho_luot
- [dat] POST `/api/v1/lam-them/dat` → `src/clinicai/api/v1/routers/lam_them_tai_quay.py:dat` → LamThemTaiQuayService.dat
- [dong-dich-vu] POST `/api/v1/lam-them/dong-dich-vu` → `src/clinicai/api/v1/routers/lam_them_tai_quay.py:dong_dich_vu` → LamThemTaiQuayService.dong_dich_vu
- [hoan-tac-dich-vu] POST `/api/v1/lam-them/hoan-tac-dich-vu` → `src/clinicai/api/v1/routers/lam_them_tai_quay.py:hoan_tac_dich_vu` → LamThemTaiQuayService.hoan_tac_dich_vu
- [luu-muc] PUT `/api/v1/lam-them/cau-hinh/{service_code}` → `src/clinicai/api/v1/routers/lam_them_tai_quay.py:luu_muc` → LamThemTaiQuayService.luu_muc
- [bo-muc] DELETE `/api/v1/lam-them/cau-hinh/{service_code}` → `src/clinicai/api/v1/routers/lam_them_tai_quay.py:bo_muc` → LamThemTaiQuayService.bo_muc
- [doi-thu-tu] PUT `/api/v1/lam-them/cau-hinh-thu-tu` → `src/clinicai/api/v1/routers/lam_them_tai_quay.py:doi_thu_tu` → LamThemTaiQuayService.doi_thu_tu
- test: src/tests/services/test_lam_them_tai_quay_db.py, src/tests/services/test_ket_qua_chung_lam_them_db.py
- màn dùng: /do-sinh-hieu, /reception/queue, /settings/day-noi

#### `/api/lich-su-notion` · `src/dashboard/app/api/lich-su-notion/route.ts`
- GET `/api/v1/patients/{id:uuid}/lich-su-notion` → `src/clinicai/api/v1/patients.py:lich_su_notion_cua_khach` → lich_su
- GET `/api/v1/lich-su-notion/luot/{luot_id:uuid}` → `src/clinicai/api/v1/patients.py:lich_su_notion_mot_luot` → chi_tiet_luot
- test: src/tests/services/test_lich_su_notion_db.py
- màn dùng: /customers, /patient-list

#### `/api/lich-su-notion/tep` · `src/dashboard/app/api/lich-su-notion/tep/route.ts`
- GET `/api/v1/lich-su-notion/xet-nghiem/{xn_id:uuid}/tep/{i}` → `src/clinicai/api/v1/patients.py:lich_su_notion_tep_xet_nghiem` → khoa_tep_xet_nghiem, _tim_ban, doc_dan, TepMoDoc
- test: src/tests/services/test_full_chi_dinh_slice_ab_db.py, src/tests/services/test_xac_nhan_tep_ket_qua_db.py, src/tests/services/test_lich_su_notion_db.py (+2)
- màn dùng: /customers, /patient-list

#### `/api/lieu-trinh` · `src/dashboard/app/api/lieu-trinh/route.ts`
- POST `/api/v1/lieu-trinh` → `src/clinicai/api/v1/routers/lieu_trinh.py:tao` → LieuTrinhService.tao
- [gan] POST `/api/v1/lieu-trinh-buoi/gan` → `src/clinicai/api/v1/routers/lieu_trinh.py:gan` → LieuTrinhService.gan
- [go] POST `/api/v1/lieu-trinh-buoi/go` → `src/clinicai/api/v1/routers/lieu_trinh.py:go` → LieuTrinhService.go
- test: src/tests/services/test_lieu_trinh_db.py
- màn dùng: /nhac-tai-kham, /phong/[ma]

#### `/api/lieu-trinh/chip` · `src/dashboard/app/api/lieu-trinh/chip/route.ts`
- GET `/api/v1/lieu-trinh/chip` → `src/clinicai/api/v1/routers/lieu_trinh.py:chip` → LieuTrinhService.chip
- test: src/tests/services/test_lieu_trinh_db.py
- màn dùng: /ban-kham, /ban-kham/[phong], /phong/[ma], /reception/queue, /tu-van

#### `/api/loi` · `src/dashboard/app/api/loi/route.ts`
- POST `/api/v1/loi-trinh-duyet` → `src/clinicai/api/v1/routers/ops.py:loi_trinh_duyet` → kho_loi.ghi_loi_web
- test: src/tests/services/test_theo_doi_pha_1_db.py, src/tests/unit/test_theo_doi_pha_1.py
- màn dùng: /doi-tac, /giam-sat, /login

#### `/api/luot-kham` · `src/dashboard/app/api/luot-kham/route.ts`
- [check-in] POST `/api/v1/luot-kham/check-in` → `src/clinicai/api/v1/routers/luot_kham.py:check_in` → LuotKhamService.check_in
- [sinh-hieu] POST `/api/v1/luot-kham/visits/{visit_id}/vitals` → `src/clinicai/api/v1/routers/luot_kham.py:record_vitals` → SinhHieuService.record_vitals
- [bo-qua-tu-van] POST `/api/v1/luot-kham/visits/{visit_id}/bo-qua-tu-van` → `src/clinicai/api/v1/routers/luot_kham.py:doi_duong_tu_van` → LuotKhamService.doi_duong_tu_van
- [bat-dau-do] POST `/api/v1/luot-kham/visits/{visit_id}/vitals/start` → `src/clinicai/api/v1/routers/luot_kham.py:bat_dau_do_sinh_hieu` → SinhHieuService.bat_dau_do_sinh_hieu
- [goi-do] POST `/api/v1/luot-kham/visits/{visit_id}/goi-do` → `src/clinicai/api/v1/routers/luot_kham.py:goi_do_sinh_hieu` → SinhHieuService.goi_do_sinh_hieu
- [nhan-kham] POST `/api/v1/luot-kham/consultations/{consultation_id}/start` → `src/clinicai/api/v1/routers/luot_kham.py:start_consultation` → LuotKhamService.start_consultation
- [xong-tu-van] POST `/api/v1/luot-kham/consultations/{consultation_id}/xong-tu-van` → `src/clinicai/api/v1/routers/luot_kham.py:xong_tu_van` → LuotKhamService.xong_tu_van
- [ghi-chu] POST `/api/v1/luot-kham/consultations/{consultation_id}/notes` → `src/clinicai/api/v1/routers/luot_kham.py:save_note` → LuotKhamService.save_note
- [noi-dung-tu-van] POST `/api/v1/luot-kham/consultations/{consultation_id}/noi-dung-tu-van` → `src/clinicai/api/v1/routers/luot_kham.py:luu_noi_dung_tu_van` → LuotKhamService.luu_noi_dung_tu_van
- [chi-dinh] POST `/api/v1/luot-kham/consultations/{consultation_id}/service-orders` → `src/clinicai/api/v1/routers/luot_kham.py:dat_chi_dinh` → ChiDinhService.dat_chi_dinh
- [nhap-chi-dinh] POST `/api/v1/luot-kham/consultations/{consultation_id}/draft-orders` → `src/clinicai/api/v1/routers/luot_kham.py:propose_orders` → LuotKhamService.propose_orders
- [duyet-chi-dinh] POST `/api/v1/luot-kham/consultations/{consultation_id}/authorize-orders` → `src/clinicai/api/v1/routers/luot_kham.py:authorize_orders` → LuotKhamService.authorize_orders
- [ket-thuc-kham] POST `/api/v1/luot-kham/consultations/{consultation_id}/complete` → `src/clinicai/api/v1/routers/luot_kham.py:complete_consultation` → LuotKhamService.complete_consultation
- [xep-phong] POST `/api/v1/luot-kham/orders/{order_id}/dispatch` → `src/clinicai/api/v1/routers/luot_kham.py:dispatch_order` → LuotKhamService.dispatch_order
- [bat-dau-dich-vu] POST `/api/v1/luot-kham/orders/{order_id}/start` → `src/clinicai/api/v1/routers/luot_kham.py:start_service` → LuotKhamService.start_service
- [xong-dich-vu] POST `/api/v1/luot-kham/orders/{order_id}/complete` → `src/clinicai/api/v1/routers/luot_kham.py:complete_service` → LuotKhamService.complete_service
- [kham-xong] POST `/api/v1/luot-kham/consultations/{consultation_id}/kham-xong` → `src/clinicai/api/v1/routers/luot_kham.py:kham_xong` → LuotKhamService.kham_xong
- [duyet-ket-qua] POST `/api/v1/luot-kham/orders/{order_id}/duyet-ket-qua` → `src/clinicai/api/v1/routers/luot_kham.py:duyet_ket_qua` → LuotKhamService.duyet_ket_qua
- [goi-khach] POST `/api/v1/luot-kham/hang-cho/{queue_entry_id}/goi` → `src/clinicai/api/v1/routers/luot_kham.py:goi_khach` → LuotKhamService.goi_khach
- [quyet-yeu-cau] POST `/api/v1/luot-kham/yeu-cau/{requirement_id}/quyet` → `src/clinicai/api/v1/routers/luot_kham.py:quyet_yeu_cau` → LuotKhamService.quyet_yeu_cau
- [chon-dich-vu] POST `/api/v1/luot-kham/visits/{visit_id}/service-selection/confirm` → `src/clinicai/api/v1/routers/luot_kham.py:confirm_service_selection` → ServiceSelectionService.confirm
- [bat-dau-v1] POST `/api/v1/luot-kham/orders/{order_id}/execution/bat-dau` → `src/clinicai/api/v1/routers/luot_kham.py:execution_bat_dau` → ServiceExecutionService.bat_dau
- [xong-v1] POST `/api/v1/luot-kham/orders/{order_id}/execution/xong` → `src/clinicai/api/v1/routers/luot_kham.py:execution_xong` → ServiceExecutionService.xong
- [khong-lam-v1] POST `/api/v1/luot-kham/orders/{order_id}/execution/khong-lam` → `src/clinicai/api/v1/routers/luot_kham.py:execution_khong_lam` → ServiceExecutionService.khong_lam
- [gian-doan-v1] POST `/api/v1/luot-kham/orders/{order_id}/execution/gian-doan` → `src/clinicai/api/v1/routers/luot_kham.py:execution_gian_doan` → ServiceExecutionService.gian_doan
- [lam-lai-v1] POST `/api/v1/luot-kham/orders/{order_id}/execution/lam-lai` → `src/clinicai/api/v1/routers/luot_kham.py:execution_lam_lai` → ServiceExecutionService.chuan_bi_lam_lai
- [huy-bat-dau-v1] POST `/api/v1/luot-kham/orders/{order_id}/execution/huy-bat-dau` → `src/clinicai/api/v1/routers/luot_kham.py:execution_huy_bat_dau` → ServiceExecutionService.huy_bat_dau
- [xep-phong-v1] POST `/api/v1/luot-kham/orders/{order_id}/routing/assign` → `src/clinicai/api/v1/routers/luot_kham.py:assign_service_room` → ServiceRoutingService.assign
- [huy-xep-phong-v1] POST `/api/v1/luot-kham/orders/{order_id}/routing/invalidate` → `src/clinicai/api/v1/routers/luot_kham.py:invalidate_service_routing` → ServiceRoutingService.invalidate
- [phong-du-kien] POST `/api/v1/luot-kham/orders/{order_id}/routing/phong-du-kien` → `src/clinicai/api/v1/routers/luot_kham.py:plan_service_room` → ServiceRoutingService.dat_phong_du_kien
- [chuyen-phong-dang-lam] POST `/api/v1/luot-kham/orders/{order_id}/routing/chuyen-phong-dang-lam` → `src/clinicai/api/v1/routers/luot_kham.py:transfer_in_progress_service` → ServiceRoutingService.chuyen_phong_dang_lam
- [bat-buoc] POST `/api/v1/luot-kham/orders/{order_id}/bat-buoc` → `src/clinicai/api/v1/routers/luot_kham.py:doi_bat_buoc` → ChiDinhService.doi_bat_buoc
- [vat-tu-them] GET `/api/v1/luot-kham/visits/{visit_id}/vat-tu` → `src/clinicai/api/v1/routers/luot_kham.py:doc_vat_tu` → VatTuService.doc
- [vat-tu-them] POST `/api/v1/luot-kham/visits/{visit_id}/vat-tu` → `src/clinicai/api/v1/routers/luot_kham.py:them_vat_tu` → VatTuService.them
- [vat-tu-so-luong] POST `/api/v1/luot-kham/vat-tu/{dong_id}` → `src/clinicai/api/v1/routers/luot_kham.py:dat_so_luong_vat_tu` → VatTuService.dat_so_luong
- [vat-tu-bo] POST `/api/v1/luot-kham/vat-tu/{dong_id}/bo` → `src/clinicai/api/v1/routers/luot_kham.py:bo_vat_tu` → VatTuService.bo
- [dau-do-chon] POST `/api/v1/luot-kham/orders/{order_id}/dau-do` → `src/clinicai/api/v1/routers/luot_kham.py:chon_dau_do` → BioChiDinhService.chon
- [phi-kham] GET `/api/v1/luot-kham/visits/{visit_id}/phi-kham` → `src/clinicai/api/v1/routers/luot_kham.py:doc_phi_kham` → PhiKhamService.doc
- [phi-kham] POST `/api/v1/luot-kham/visits/{visit_id}/phi-kham` → `src/clinicai/api/v1/routers/luot_kham.py:chon_phi_kham` → PhiKhamService.chon
- [lam-truoc-thu-sau] GET `/api/v1/luot-kham/visits/{visit_id}/lam-truoc-thu-sau` → `src/clinicai/api/v1/routers/luot_kham.py:doc_lam_truoc_thu_sau` → LamTruocThuSauService.doc
- [lam-truoc-thu-sau] POST `/api/v1/luot-kham/visits/{visit_id}/lam-truoc-thu-sau` → `src/clinicai/api/v1/routers/luot_kham.py:dat_lam_truoc_thu_sau` → LamTruocThuSauService.dat
- [mo-lai-kham] POST `/api/v1/luot-kham/consultations/{consultation_id}/mo-lai` → `src/clinicai/api/v1/routers/hoan_tac.py:mo_lai_kham` → HoanTacService.mo_lai_kham
- [huy-chi-dinh] POST `/api/v1/luot-kham/orders/{order_id}/huy-chi-dinh` → `src/clinicai/api/v1/routers/hoan_tac.py:huy_chi_dinh` → HoanTacService.huy_chi_dinh
- [hoan-tac-xong-v1] POST `/api/v1/luot-kham/orders/{order_id}/execution/hoan-tac-xong` → `src/clinicai/api/v1/routers/hoan_tac.py:hoan_tac_xong` → HoanTacService.hoan_tac_xong_dich_vu
- [mo-lai-luot] POST `/api/v1/luot-kham/visits/{visit_id}/mo-lai-luot` → `src/clinicai/api/v1/routers/hoan_tac.py:mo_lai_luot` → HoanTacService.mo_lai_luot
- [thu-hoi-ket-qua] POST `/api/v1/luot-kham/orders/{order_id}/thu-hoi-duyet` → `src/clinicai/api/v1/routers/hoan_tac.py:thu_hoi_duyet` → HoanTacService.thu_hoi_duyet_ket_qua
- [hoan-tac-bo-chi-dinh] POST `/api/v1/luot-kham/so-sua-chi-dinh/{so_id}/hoan-tac` → `src/clinicai/api/v1/routers/hoan_tac.py:hoan_tac_bo_chi_dinh` → SoSuaChiDinhService.hoan_tac
- [nhan-vao-phong] POST `/api/v1/luot-kham/visits/{visit_id}/nhan-vao-phong` → `src/clinicai/api/v1/routers/luot_kham.py:receive_at_room` → NhanTaiPhongService.nhan
- [hoan-tac-nhan] POST `/api/v1/luot-kham/visits/{visit_id}/hoan-tac-nhan` → `src/clinicai/api/v1/routers/luot_kham.py:undo_receive_at_room` → NhanTaiPhongService.hoan_tac_nhan
- GET `/api/v1/luot-kham/bang` → `src/clinicai/api/v1/routers/luot_kham.py:bang` → BangLuotKham.bang
- GET `/api/v1/luot-kham/phong-hom-nay` → `src/clinicai/api/v1/routers/luot_kham.py:phong_hom_nay` → BangLuotKham.phong_hom_nay
- GET `/api/v1/luot-kham/ket-qua-cho-duyet` → `src/clinicai/api/v1/routers/luot_kham.py:ket_qua_cho_duyet` → BangLuotKham.ket_qua_cho_duyet
- GET `/api/v1/luot-kham/cho-quyet` → `src/clinicai/api/v1/routers/luot_kham.py:cho_quyet` → LuotKhamService.cho_quyet
- GET `/api/v1/xem-luot/{visit_id}` → `src/clinicai/api/v1/routers/xem_luot.py:xem_luot` → XemLuotService.doc
- GET `/api/v1/luot-kham/chi-dinh-hom-nay` → `src/clinicai/api/v1/routers/luot_kham.py:chi_dinh_hom_nay` → BangLuotKham.chi_dinh_hom_nay
- GET `/api/v1/luot-kham/visits/{visit_id}/vat-tu` → `src/clinicai/api/v1/routers/luot_kham.py:doc_vat_tu` → VatTuService.doc
- POST `/api/v1/luot-kham/visits/{visit_id}/vat-tu` → `src/clinicai/api/v1/routers/luot_kham.py:them_vat_tu` → VatTuService.them
- GET `/api/v1/luot-kham/visits/{visit_id}/dau-do` → `src/clinicai/api/v1/routers/luot_kham.py:doc_dau_do` → BioChiDinhService.doc
- GET `/api/v1/luot-kham/visits/{visit_id}/lam-truoc-thu-sau` → `src/clinicai/api/v1/routers/luot_kham.py:doc_lam_truoc_thu_sau` → LamTruocThuSauService.doc
- POST `/api/v1/luot-kham/visits/{visit_id}/lam-truoc-thu-sau` → `src/clinicai/api/v1/routers/luot_kham.py:dat_lam_truoc_thu_sau` → LamTruocThuSauService.dat
- GET `/api/v1/luot-kham/visits/{visit_id}/so-sua-chi-dinh` → `src/clinicai/api/v1/routers/hoan_tac.py:so_sua_chi_dinh` → SoSuaChiDinhService.doc
- GET `/api/v1/luot-kham/visits/{visit_id}/phi-kham` → `src/clinicai/api/v1/routers/luot_kham.py:doc_phi_kham` → PhiKhamService.doc
- POST `/api/v1/luot-kham/visits/{visit_id}/phi-kham` → `src/clinicai/api/v1/routers/luot_kham.py:chon_phi_kham` → PhiKhamService.chon
- GET `/api/v1/hanh-trinh/hom-nay` → `src/clinicai/api/v1/routers/xem_luot.py:bang_hanh_trinh` → BangHanhTrinhService.hom_nay
- GET `/api/v1/luot-kham/visits/{visit_id}/hanh-trinh-khach` → `src/clinicai/api/v1/routers/xem_luot.py:hanh_trinh_khach` → HanhTrinhKhachService.mot_luot
- GET `/api/v1/luot-kham/orders/{order_id}/routing/recommendation` → `src/clinicai/api/v1/routers/luot_kham.py:recommend_service_room` → ServiceRoutingService.recommend
- GET `/api/v1/luot-kham/orders/{order_id}/execution` → `src/clinicai/api/v1/routers/luot_kham.py:execution_xem` → ServiceExecutionService.xem
- GET `/api/v1/luot-kham/hang-cho` → `src/clinicai/api/v1/routers/luot_kham.py:hang_cho` → BangLuotKham.hang_cho
- test: src/tests/services/test_luot_kham_service_db.py, src/tests/services/test_hoan_tac_moi_thao_tac_db.py, src/tests/services/test_bio_chi_dinh_db.py (+41)
- màn dùng: /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh (+13)

#### `/api/mau-ket-qua` · `src/dashboard/app/api/mau-ket-qua/route.ts`
- GET `/api/v1/mau-ket-qua/bang-gan` → `src/clinicai/api/v1/routers/mau_ket_qua.py:bang_gan` → MauKetQuaService.bang_gan
- GET `/api/v1/mau-ket-qua/de-xuat` → `src/clinicai/api/v1/routers/mau_ket_qua.py:de_xuat` → MauKetQuaService.de_xuat
- GET `/api/v1/bieu-mau/{form_id}` → `src/clinicai/api/v1/routers/phieu.py:doc_bieu_mau` → FormEngineService.doc_bieu_mau
- POST `/api/v1/mau-ket-qua/gan` → `src/clinicai/api/v1/routers/mau_ket_qua.py:gan` → MauKetQuaService.gan
- POST `/api/v1/mau-ket-qua/go` → `src/clinicai/api/v1/routers/mau_ket_qua.py:go` → MauKetQuaService.go
- POST `/api/v1/mau-ket-qua/tao` → `src/clinicai/api/v1/routers/mau_ket_qua.py:tao_mau` → MauKetQuaService.tao_mau
- POST `/api/v1/bieu-mau/{form_id}/xuat-ban` → `src/clinicai/api/v1/routers/phieu.py:xuat_ban` → FormEngineService.xuat_ban
- test: src/tests/services/test_man_mau_ket_qua_db.py, src/tests/services/test_mau_ket_qua_db.py, src/tests/services/test_form_engine_db.py (+1)
- màn dùng: /settings/mau-ket-qua

#### `/api/nhac-viec` · `src/dashboard/app/api/nhac-viec/route.ts`
- GET `/api/v1/nhac-viec` → `src/clinicai/api/v1/routers/day_noi.py:nhac_viec_cua_toi` → NhacViecService.cua_toi
- POST `/api/v1/nhac-viec` → `src/clinicai/api/v1/routers/day_noi.py:tao_nhac` → NhacViecService.tao
- POST `/api/v1/nhac-viec/{nhac_id}/xong` → `src/clinicai/api/v1/routers/day_noi.py:xong_nhac` → NhacViecService.xong
- test: src/tests/services/test_day_noi_nhac_db.py
- màn dùng: /ban-kham, /ban-kham/[phong], /customers, /do-sinh-hieu, /pharmacy, /phong/[ma] (+1)

#### `/api/ops/agent` · `src/dashboard/app/api/ops/agent/route.ts`
- GET `/api/v1/ops/agent/tom-tat` → `src/clinicai/api/v1/routers/ops.py:doc_tom_tat` → agent_tom_tat.doc
- GET `/api/v1/ops/agent/tong-quan` → `src/clinicai/api/v1/routers/ops.py:tong_quan_agent` → tong_quan_giam_sat.doc
- GET `/api/v1/ops/llm/chi-phi` → `src/clinicai/api/v1/routers/ops.py:chi_phi_llm` → chi_phi.so_lieu
- [1] GET `/api/v1/ops/agent` → `src/clinicai/api/v1/routers/ops.py:agent_nhan_dinh` → agent_giam_sat.danh_sach
- [true] GET `/api/v1/ops/agent` → `src/clinicai/api/v1/routers/ops.py:agent_nhan_dinh` → agent_giam_sat.danh_sach
- POST `/api/v1/ops/agent/{nhan_dinh_id}/danh-gia` → `src/clinicai/api/v1/routers/ops.py:danh_gia_nhan_dinh` → agent_giam_sat.danh_gia
- POST `/api/v1/ops/agent/tom-tat` → `src/clinicai/api/v1/routers/ops.py:tao_tom_tat` → agent_tom_tat.tao
- POST `/api/v1/ops/agent/che-do` → `src/clinicai/api/v1/routers/ops.py:dat_che_do_agent` → agent_giam_sat.dat_che_do
- test: src/tests/services/test_agent_giam_sat_db.py, src/tests/services/test_llm_chi_phi_db.py
- màn dùng: /doi-tac, /giam-sat, /login

#### `/api/ops/summary` · `src/dashboard/app/api/ops/summary/route.ts`
- GET `/api/v1/phan-quyen/toi` → `src/clinicai/api/v1/routers/phan_quyen.py:quyen_cua_toi` → quyen_hieu_luc, cashier_navigation, navigation_deadline
- GET `/api/v1/ops/status` → `src/clinicai/api/v1/routers/ops.py:get_ops_status` → OpsStatusService.collect
- test: src/tests/services/test_cashier_navigation.py, src/tests/unit/test_cua_quyen_lego.py, src/tests/services/test_doi_nguoi_trong_ca_db.py (+2)
- màn dùng: /ops

#### `/api/ops/theo-doi` · `src/dashboard/app/api/ops/theo-doi/route.ts`
- [1] GET `/api/v1/ops/loi` → `src/clinicai/api/v1/routers/ops.py:ds_loi` → kho_loi.danh_sach
- [true] GET `/api/v1/ops/loi` → `src/clinicai/api/v1/routers/ops.py:ds_loi` → kho_loi.danh_sach
- GET `/api/v1/ops/canh-bao` → `src/clinicai/api/v1/routers/ops.py:ds_canh_bao` → day_tep.so_lieu, canh_gac.danh_sach
- GET `/api/v1/ops/nhat-ky` → `src/clinicai/api/v1/routers/ops.py:nhat_ky` → nhat_ky_van_hanh.doc_nhat_ky
- POST `/api/v1/ops/loi/{loi_id}/trang-thai` → `src/clinicai/api/v1/routers/ops.py:doi_trang_thai_loi` → kho_loi.doi_trang_thai
- test: src/tests/services/test_theo_doi_pha_1_db.py, src/tests/unit/test_theo_doi_pha_1.py, src/tests/services/test_canh_bao_han_lo_db.py (+1)
- màn dùng: /ops

#### `/api/ops/traffic` · `src/dashboard/app/api/ops/traffic/route.ts`
- POST `/api/v1/ops/traffic` → `src/clinicai/api/v1/routers/ops.py:lay_bao_cao_traffic` → traffic_service.doc_du_lieu_traffic, traffic_service.xac_thuc_admin, traffic_service.xac_thuc_ma_pin
- test: src/tests/unit/test_traffic_service.py
- màn dùng: /ops, /traffic

#### `/api/patients` · `src/dashboard/app/api/patients/route.ts`
- POST `/api/v1/patients` → `src/clinicai/api/v1/patients.py:create_patient` → PatientService.create_patient
- PATCH `/api/v1/patients/{id:uuid}` → `src/clinicai/api/v1/patients.py:update_patient` → PatientService.update_patient
- test: src/tests/unit/test_patient_service.py, src/tests/api/test_patients_api.py, src/tests/services/test_sua_ho_so_khach_db.py
- màn dùng: /appointments, /ban-kham, /ban-kham/[phong], /customers, /patient-list, /patients/new (+1)

#### `/api/patients/[id]/uu-tien` · `src/dashboard/app/api/patients/[id]/uu-tien/route.ts`
- PUT `/api/v1/patients/{id:uuid}/uu-tien` → `src/clinicai/api/v1/patients.py:dat_khach_uu_tien` → ThuTuKhamService.dat_uu_tien
- test: src/tests/services/test_luat_1509_thu_ky_va_dieu_phoi.py, src/tests/services/test_thu_tu_kham_va_uu_tien.py
- màn dùng: /customers

#### `/api/patients/check-duplicate` · `src/dashboard/app/api/patients/check-duplicate/route.ts`
- GET `/api/v1/patients/check-duplicate` → `src/clinicai/api/v1/patients.py:check_duplicate` → MPIService.find_candidates + SQL ngay trong router
- test: src/tests/unit/test_mpi_service.py, src/tests/unit/test_trung_ten_don_thuan.py
- màn dùng: /appointments, /patients/new

#### `/api/patients/check-phone` · `src/dashboard/app/api/patients/check-phone/route.ts`
- backend: (không proxy /api/v1 — xử lý tại chỗ hoặc lối khác ?)
- ⚠ đọc DB thẳng: patient
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/patients/sdt-them` · `src/dashboard/app/api/patients/sdt-them/route.ts`
- POST `/api/v1/patients/sdt-them` → `src/clinicai/api/v1/patients.py:them_so_dien_thoai` → PatientService.them_so_dien_thoai
- DELETE `/api/v1/patients/sdt-them` → `src/clinicai/api/v1/patients.py:xoa_so_dien_thoai` → PatientService.xoa_so_dien_thoai
- test: src/tests/test_nhieu_so_dien_thoai.py
- màn dùng: /appointments, /ban-kham, /ban-kham/[phong], /customers, /patient-list, /patients/new (+1)

#### `/api/payment` · `src/dashboard/app/api/payment/route.ts`
- POST `/api/v1/payments/hoan-tien` → `src/clinicai/api/v1/routers/payment.py:hoan_tien` → authorize_payment, HoanTienService.tao
- POST `/api/v1/payments/hoan-tien/xac-nhan` → `src/clinicai/api/v1/routers/payment.py:xac_nhan_hoan` → authorize_payment, HoanTienService.xac_nhan
- POST `/api/v1/payments/hoan-tien/dong` → `src/clinicai/api/v1/routers/payment.py:dong_khoan_hoan` → authorize_payment, HoanTienService.dong
- POST `/api/v1/payments/doi-hinh-thuc` → `src/clinicai/api/v1/routers/payment.py:doi_hinh_thuc` → authorize_payment, DoiHinhThucService.doi
- POST `/api/v1/payments/hoan-tac` → `src/clinicai/api/v1/routers/payment.py:hoan_tac_lan_thu` → authorize_payment, PaymentService.hoan_tac
- POST `/api/v1/payments/xac-minh` → `src/clinicai/api/v1/routers/payment.py:xac_minh_dien_tu` → authorize_payment, PaymentService.xac_minh_dien_tu
- POST `/api/v1/payments/huy-cho` → `src/clinicai/api/v1/routers/payment.py:huy_cho_xac_minh` → authorize_payment, PaymentService.huy_cho_xac_minh
- POST `/api/v1/payments` → `src/clinicai/api/v1/routers/payment.py:record_payment` → authorize_payment, PaymentService.record_payment, HoaDonCongTyService.gan_khi_thu
- DELETE `/api/v1/payments` → `src/clinicai/api/v1/routers/payment.py:void_payment` → authorize_payment, PaymentService.void_payment
- test: src/tests/services/test_payment_head_scope_db.py, src/tests/unit/test_payment_access.py, src/tests/services/test_thu_dich_vu_nhieu_lan_db.py (+12)
- màn dùng: /pharmacy, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su

#### `/api/payment/anh-ck` · `src/dashboard/app/api/payment/anh-ck/route.ts`
- GET `/api/v1/payments/anh-chuyen-khoan/{anh_id}` → `src/clinicai/api/v1/routers/payment.py:xem_anh_chuyen_khoan` → authorize_payment, AnhChuyenKhoanService.doc
- POST `/api/v1/payments/anh-chuyen-khoan` → `src/clinicai/api/v1/routers/payment.py:tai_anh_chuyen_khoan` → CashierScopeService.authorize_any_active, nhan_multipart, uuid_hoac_loi, authorize_payment (+2)
- POST `/api/v1/payments/anh-chuyen-khoan/{anh_id}/go` → `src/clinicai/api/v1/routers/payment.py:go_anh_chuyen_khoan` → authorize_payment, AnhChuyenKhoanService.go
- test: src/tests/unit/test_payment_access.py, src/tests/services/test_payment_head_scope_db.py, src/tests/services/test_thu_nhieu_hinh_thuc_db.py (+3)
- màn dùng: /pharmacy, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su

#### `/api/phan-quyen` · `src/dashboard/app/api/phan-quyen/route.ts`
- [cap] POST `/api/v1/phan-quyen/nhan-su/{staff_id}/cap` → `src/clinicai/api/v1/routers/phan_quyen.py:cap_khoi` → PermissionService.cap_khoi
- [thu] POST `/api/v1/phan-quyen/nhan-su/{staff_id}/thu` → `src/clinicai/api/v1/routers/phan_quyen.py:thu_khoi` → PermissionService.thu_khoi
- [them-preset] POST `/api/v1/phan-quyen/nhan-su/{staff_id}/them-preset` → `src/clinicai/api/v1/routers/phan_quyen.py:them_preset` → PermissionService.them_preset
- [doi-lego] GET `/api/v1/phan-quyen/nhan-su/{staff_id}/lego` → `src/clinicai/api/v1/routers/phan_quyen.py:lego_cua_nguoi` → PermissionService.lego_cua_nguoi
- [doi-lego] POST `/api/v1/phan-quyen/nhan-su/{staff_id}/lego` → `src/clinicai/api/v1/routers/phan_quyen.py:doi_lego` → PermissionService.doi_lego
- [doi-ky-nang] GET `/api/v1/phan-quyen/nhan-su/{staff_id}/ky-nang` → `src/clinicai/api/v1/routers/phan_quyen.py:ky_nang_cua_nguoi` → KyNangService.cua_nguoi
- [doi-ky-nang] POST `/api/v1/phan-quyen/nhan-su/{staff_id}/ky-nang` → `src/clinicai/api/v1/routers/phan_quyen.py:doi_ky_nang` → KyNangService.doi
- [chep-ky-nang] POST `/api/v1/phan-quyen/nhan-su/{staff_id}/chep-ky-nang` → `src/clinicai/api/v1/routers/phan_quyen.py:chep_ky_nang` → KyNangService.chep
- GET `/api/v1/phan-quyen/nhom` → `src/clinicai/api/v1/routers/phan_quyen.py:danh_sach_nhom` → PermissionService.danh_sach_nhom
- GET `/api/v1/phan-quyen/man` → `src/clinicai/api/v1/routers/phan_quyen.py:quyen_theo_man` → PermissionService.theo_man
- GET `/api/v1/phan-quyen/ky-nang` → `src/clinicai/api/v1/routers/phan_quyen.py:danh_sach_ky_nang` → KyNangService.danh_sach
- GET `/api/v1/phan-quyen/nhan-su/{staff_id}/ky-nang` → `src/clinicai/api/v1/routers/phan_quyen.py:ky_nang_cua_nguoi` → KyNangService.cua_nguoi
- GET `/api/v1/phan-quyen/nhan-su/{staff_id}/lego` → `src/clinicai/api/v1/routers/phan_quyen.py:lego_cua_nguoi` → PermissionService.lego_cua_nguoi
- GET `/api/v1/phan-quyen/danh-muc` → `src/clinicai/api/v1/routers/phan_quyen.py:danh_muc` → KHOI.values, PRESET.items, quyen_cua_khoi
- GET `/api/v1/phan-quyen/nhan-su/{staff_id}` → `src/clinicai/api/v1/routers/phan_quyen.py:quyen_cua_nguoi` → PermissionService.quyen_cua_nguoi
- POST `/api/v1/phan-quyen/man` → `src/clinicai/api/v1/routers/phan_quyen.py:doi_man` → PermissionService.doi_man
- POST `/api/v1/phan-quyen/nhom` → `src/clinicai/api/v1/routers/phan_quyen.py:luu_nhom` → PermissionService.luu_nhom
- POST `/api/v1/phan-quyen/nhom/{ma}/xoa` → `src/clinicai/api/v1/routers/phan_quyen.py:xoa_nhom` → PermissionService.xoa_nhom
- test: src/tests/services/test_permission_db.py, src/tests/services/test_lego_21_db.py, src/tests/services/test_no_con_lai_db.py (+8)
- màn dùng: /phan-quyen

#### `/api/pharmacy/[action]` · `src/dashboard/app/api/pharmacy/[action]/route.ts`
- [sua-lo] POST `/api/v1/pharmacy/sua-lo` → `src/clinicai/api/v1/routers/pharmacy.py:sua_lo` → lo_thuoc_service.sua_lo
- [huy-lo-het-han] POST `/api/v1/pharmacy/huy-lo-het-han` → `src/clinicai/api/v1/routers/pharmacy.py:huy_lo_het_han` → lo_thuoc_service.huy_lo
- [hoan-huy-lo] POST `/api/v1/pharmacy/hoan-huy-lo` → `src/clinicai/api/v1/routers/pharmacy.py:hoan_huy_lo` → lo_thuoc_service.hoan_huy_lo
- [so-ngay-canh-bao] GET `/api/v1/pharmacy/so-ngay-canh-bao` → `src/clinicai/api/v1/routers/pharmacy.py:so_ngay_canh_bao` → lo_thuoc_service.so_ngay_canh_bao, can
- [so-ngay-canh-bao] POST `/api/v1/pharmacy/so-ngay-canh-bao` → `src/clinicai/api/v1/routers/pharmacy.py:doi_canh_bao` → lo_thuoc_service.doi_canh_bao
- [receive] POST `/api/v1/pharmacy/receive` → `src/clinicai/api/v1/routers/pharmacy.py:nhap_lo` → PharmacyService.nhap_lo
- [dispense] POST `/api/v1/pharmacy/dispense` → `src/clinicai/api/v1/routers/pharmacy.py:cap_phat` → PharmacyService.cap_phat
- [refuse] POST `/api/v1/pharmacy/refuse` → `src/clinicai/api/v1/routers/pharmacy.py:tu_choi` → PharmacyService.tu_choi
- [close-line] POST `/api/v1/pharmacy/close-line` → `src/clinicai/api/v1/routers/pharmacy.py:chot` → PharmacyService.chot
- [adjust] POST `/api/v1/pharmacy/adjust` → `src/clinicai/api/v1/routers/pharmacy.py:dieu_chinh` → PharmacyService.dieu_chinh
- [discard] POST `/api/v1/pharmacy/discard` → `src/clinicai/api/v1/routers/pharmacy.py:huy` → PharmacyService.huy
- [xac-dinh-thuoc] POST `/api/v1/pharmacy/xac-dinh-thuoc` → `src/clinicai/api/v1/routers/pharmacy.py:xac_dinh_thuoc` → PharmacyService.xac_dinh_thuoc
- [so-luong-mua] POST `/api/v1/pharmacy/so-luong-mua` → `src/clinicai/api/v1/routers/pharmacy.py:khai_so_luong_mua` → PharmacyService.khai_so_luong_mua
- [phan-lo] POST `/api/v1/pharmacy/phan-lo` → `src/clinicai/api/v1/routers/pharmacy.py:phan_lo` → PharmacyService.phan_lo
- [bo-phan-lo] POST `/api/v1/pharmacy/bo-phan-lo` → `src/clinicai/api/v1/routers/pharmacy.py:bo_phan_lo` → PharmacyService.bo_phan_lo
- [doi-lo] POST `/api/v1/pharmacy/doi-lo` → `src/clinicai/api/v1/routers/pharmacy.py:doi_lo_khi_cho` → PharmacyService.doi_lo_khi_cho
- [huy-phan-chua-giao] POST `/api/v1/pharmacy/huy-phan-chua-giao` → `src/clinicai/api/v1/routers/pharmacy.py:huy_phan_chua_giao` → PharmacyService.huy_phan_chua_giao
- [khach-tra] POST `/api/v1/pharmacy/khach-tra` → `src/clinicai/api/v1/routers/pharmacy.py:khach_tra_thuoc` → PharmacyService.khach_tra_thuoc
- [luu-thuoc] GET `/api/v1/pharmacy/danh-muc` → `src/clinicai/api/v1/routers/pharmacy.py:danh_muc_thuoc` → PharmacyService.danh_muc
- [luu-thuoc] POST `/api/v1/pharmacy/danh-muc` → `src/clinicai/api/v1/routers/pharmacy.py:luu_thuoc` → PharmacyService.luu_thuoc
- [gan-lo] POST `/api/v1/pharmacy/gan-lo` → `src/clinicai/api/v1/routers/pharmacy.py:gan_lo` → PharmacyService.gan_lo_da_giao
- [phieu-nhap] POST `/api/v1/pharmacy/phieu-nhap` → `src/clinicai/api/v1/routers/pharmacy.py:phieu_nhap` → kho_thuoc_service.tao_phieu_nhap
- [kiem-kho] POST `/api/v1/pharmacy/kiem-kho` → `src/clinicai/api/v1/routers/pharmacy.py:kiem_kho` → kho_thuoc_service.kiem_kho
- [ban-le] POST `/api/v1/pharmacy/ban-le` → `src/clinicai/api/v1/routers/pharmacy.py:mo_ban_le` → BanLeService.mo_luot
- [gan-ma-vach] POST `/api/v1/pharmacy/gan-ma-vach` → `src/clinicai/api/v1/routers/pharmacy.py:gan_ma_vach` → ma_vach_service.gan_ma
- [go-ma-vach] POST `/api/v1/pharmacy/go-ma-vach` → `src/clinicai/api/v1/routers/pharmacy.py:go_ma_vach` → ma_vach_service.go_ma
- [chuyen-kho] POST `/api/v1/pharmacy/chuyen-kho` → `src/clinicai/api/v1/routers/pharmacy.py:chuyen_kho` → kho_thuoc_service.chuyen_kho
- [hoan-tac-chuyen-kho] POST `/api/v1/pharmacy/hoan-tac-chuyen-kho` → `src/clinicai/api/v1/routers/pharmacy.py:hoan_tac_chuyen_kho` → kho_thuoc_service.hoan_tac_chuyen
- [tach-kho-quay] GET `/api/v1/pharmacy/tach-kho-quay` → `src/clinicai/api/v1/routers/pharmacy.py:tach_kho_quay` → tach_kho_quay_bat, can
- [tach-kho-quay] POST `/api/v1/pharmacy/tach-kho-quay` → `src/clinicai/api/v1/routers/pharmacy.py:dat_tach_kho_quay` → kho_thuoc_service.dat_tach_kho_quay
- [xu-ly-thuoc-tra] POST `/api/v1/pharmacy/xu-ly-thuoc-tra` → `src/clinicai/api/v1/routers/pharmacy.py:xu_ly_thuoc_tra` → PharmacyService.xu_ly_thuoc_tra
- [ban-le-theo-don] POST `/api/v1/pharmacy/ban-le/theo-don` → `src/clinicai/api/v1/routers/pharmacy.py:ban_le_theo_don` → ban_theo_don_service.noi_don
- [ban-le-go-don] POST `/api/v1/pharmacy/ban-le/go-don` → `src/clinicai/api/v1/routers/pharmacy.py:ban_le_go_don` → ban_theo_don_service.go_noi_don
- [ban-le-mo-theo-don] POST `/api/v1/pharmacy/ban-le/mo-theo-don` → `src/clinicai/api/v1/routers/pharmacy.py:ban_le_mo_theo_don` → BanLeService.mo_theo_don
- GET `/api/v1/pharmacy/the-kho/{drug_catalog_id}` → `src/clinicai/api/v1/routers/pharmacy.py:the_kho` → kho_thuoc_service.the_kho
- [xuat-nhap-ton] GET `/api/v1/pharmacy/xuat-nhap-ton` → `src/clinicai/api/v1/routers/pharmacy.py:xuat_nhap_ton` → kho_thuoc_service.xuat_nhap_ton
- [phieu-kho] GET `/api/v1/pharmacy/phieu-kho` → `src/clinicai/api/v1/routers/pharmacy.py:danh_sach_phieu` → kho_thuoc_service.danh_sach_phieu
- [tim-khach] GET `/api/v1/pharmacy/ban-le/tim-khach` → `src/clinicai/api/v1/routers/pharmacy.py:ban_le_tim_khach` → BanLeService.tim_khach
- GET `/api/v1/pharmacy/ban-le/{visit_id}` → `src/clinicai/api/v1/routers/pharmacy.py:doc_ban_le` → BanLeService.doc
- [tra-ma] GET `/api/v1/pharmacy/tra-ma` → `src/clinicai/api/v1/routers/pharmacy.py:tra_ma` → ma_vach_service.tra_ma
- GET `/api/v1/pharmacy/quy-doi` → `src/clinicai/api/v1/routers/pharmacy.py:xem_quy_doi_nhap` → kho_thuoc_service.xem_truoc_quy_doi
- [tem-lo] GET `/api/v1/pharmacy/tem-lo` → `src/clinicai/api/v1/routers/pharmacy.py:tem_lo` → ma_vach_service.du_lieu_tem
- GET `/api/v1/pharmacy/ban-le/lich-su-don` → `src/clinicai/api/v1/routers/pharmacy.py:ban_le_lich_su_don` → BanLeService.lich_su_don
- GET `/api/v1/pharmacy/xuat-nhap-ton.xlsx` → `src/clinicai/api/v1/routers/pharmacy.py:xuat_nhap_ton_xlsx` → kho_thuoc_service.xuat_nhap_ton, xlsx_inventory
- test: src/tests/services/test_kho_quay_db.py, src/tests/services/test_kho_kiotviet_db.py, src/tests/services/test_ban_theo_don_db.py (+22)
- màn dùng: /pharmacy, /pharmacy/inventory, /print/tem-lo

#### `/api/pharmacy/kiem-ke-ca` · `src/dashboard/app/api/pharmacy/kiem-ke-ca/route.ts`
- GET `/api/v1/pharmacy/kiem-ke-ca/nhac` → `src/clinicai/api/v1/routers/pharmacy.py:nhac_kiem_ke_ca` → kiem_ke_ca_service.nhac_thieu_kiem
- GET `/api/v1/pharmacy/kiem-ke-ca` → `src/clinicai/api/v1/routers/pharmacy.py:ds_kiem_ke_ca` → kiem_ke_ca_service.danh_sach
- POST `/api/v1/pharmacy/kiem-ke-ca` → `src/clinicai/api/v1/routers/pharmacy.py:mo_kiem_ke_ca` → kiem_ke_ca_service.mo_phieu
- test: src/tests/services/test_kiem_ke_ca_db.py
- màn dùng: /pharmacy/inventory

#### `/api/pharmacy/kiem-ke-ca/[id]` · `src/dashboard/app/api/pharmacy/kiem-ke-ca/[id]/route.ts`
- GET `/api/v1/pharmacy/kiem-ke-ca/{phieu_id}` → `src/clinicai/api/v1/routers/pharmacy.py:doc_kiem_ke_ca` → kiem_ke_ca_service.doc_phieu
- test: src/tests/services/test_kiem_ke_ca_db.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/pharmacy/kiem-ke-ca/[id]/[buoc]` · `src/dashboard/app/api/pharmacy/kiem-ke-ca/[id]/[buoc]/route.ts`
- POST `/api/v1/pharmacy/kiem-ke-ca/{phieu_id}/chot` → `src/clinicai/api/v1/routers/pharmacy.py:chot_kiem_ke_ca` → kiem_ke_ca_service.chot
- POST `/api/v1/pharmacy/kiem-ke-ca/{phieu_id}/dem` → `src/clinicai/api/v1/routers/pharmacy.py:luu_dem_kiem_ke_ca` → kiem_ke_ca_service.luu_dem
- POST `/api/v1/pharmacy/kiem-ke-ca/{phieu_id}/dieu-chinh` → `src/clinicai/api/v1/routers/pharmacy.py:dieu_chinh_kiem_ke_ca` → kiem_ke_ca_service.dieu_chinh_theo_kiem_ke
- POST `/api/v1/pharmacy/kiem-ke-ca/{phieu_id}/dung-so-cuoi-ca-truoc` → `src/clinicai/api/v1/routers/pharmacy.py:dung_so_cuoi_ca_truoc` → kiem_ke_ca_service.dung_so_cuoi_ca_truoc
- POST `/api/v1/pharmacy/kiem-ke-ca/{phieu_id}/hoan-tac-dieu-chinh` → `src/clinicai/api/v1/routers/pharmacy.py:hoan_tac_dieu_chinh_kiem_ke_ca` → kiem_ke_ca_service.hoan_tac_dieu_chinh
- test: src/tests/services/test_kiem_ke_ca_db.py, src/tests/services/test_chuong_mot_thong_bao_moi_nguoi_db.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/phieu` · `src/dashboard/app/api/phieu/route.ts`
- [luu] POST `/api/v1/phieu/{phieu_id}/luu` → `src/clinicai/api/v1/routers/phieu.py:luu_nhap` → FormEngineService.luu_nhap
- [hoan-tat] POST `/api/v1/phieu/{phieu_id}/hoan-tat` → `src/clinicai/api/v1/routers/phieu.py:hoan_tat` → FormEngineService.hoan_tat
- [mo-sua] POST `/api/v1/phieu/{phieu_id}/mo-sua` → `src/clinicai/api/v1/routers/phieu.py:mo_sua` → FormEngineService.mo_sua
- [huy-sua] POST `/api/v1/phieu/{phieu_id}/huy-sua` → `src/clinicai/api/v1/routers/phieu.py:huy_sua` → FormEngineService.huy_sua
- GET `/api/v1/phieu/in/{service_order_id}` → `src/clinicai/api/v1/routers/phieu.py:in_ket_qua` → FormEngineService.in_ket_qua
- GET `/api/v1/phieu/xem/{service_order_id}` → `src/clinicai/api/v1/routers/phieu.py:xem_ket_qua` → FormEngineService.xem_ket_qua
- GET `/api/v1/bieu-mau` → `src/clinicai/api/v1/routers/phieu.py:danh_sach` → (SQL ngay trong router, không qua service)
- POST `/api/v1/phieu/mo` → `src/clinicai/api/v1/routers/phieu.py:mo_phieu` → FormEngineService.mo_phieu
- test: src/tests/services/test_sua_ket_qua_db.py, src/tests/services/test_form_engine_db.py, src/tests/services/test_ket_qua_chung_lam_them_db.py (+3)
- màn dùng: /ban-kham, /ban-kham/[phong], /patient-list, /phong/[ma], /print/ket-qua/[orderId], /print/phieu-kham/[visitId] (+1)

#### `/api/phieu-kham` · `src/dashboard/app/api/phieu-kham/route.ts`
- GET `/api/v1/phieu-kham/dinh-nghia` → `src/clinicai/api/v1/routers/phieu_kham.py:danh_sach` → dinh_nghia
- GET `/api/v1/phieu-kham/tham-chieu` → `src/clinicai/api/v1/routers/phieu_kham.py:tham_chieu` → PhieuKhamService.tham_chieu_that
- GET `/api/v1/phieu-kham/dinh-nghia/{form_id}` → `src/clinicai/api/v1/routers/phieu_kham.py:mot_dinh_nghia` → PhieuKhamService.khung_theo_ban
- GET `/api/v1/phieu-kham/luot/{visit_id}/phieu` → `src/clinicai/api/v1/routers/phieu_kham.py:phieu_cua_luot` → PhieuKhamService.doc_luot, ghi_mo_ho_so
- GET `/api/v1/phieu-kham/luot/{visit_id}/lich-su` → `src/clinicai/api/v1/routers/phieu_kham.py:lich_su_phieu` → PhieuKhamService.lich_su
- GET `/api/v1/phieu-kham/luot/{visit_id}/lich-tai-kham` → `src/clinicai/api/v1/routers/phieu_kham.py:doc_lich_tai_kham` → LichTaiKhamService.doc
- GET `/api/v1/phieu-kham/luot/{visit_id}/dau-phieu` → `src/clinicai/api/v1/routers/phieu_kham.py:dau_phieu` → PhieuKhamService.dau_phieu
- GET `/api/v1/phieu-kham/luot/{visit_id}/don-thuoc` → `src/clinicai/api/v1/routers/phieu_kham.py:don_thuoc` → PhieuKhamService.doc_don_thuoc
- GET `/api/v1/phieu-kham/luot/{visit_id}/hanh-trinh` → `src/clinicai/api/v1/routers/phieu_kham.py:hanh_trinh` → PhieuKhamService.hanh_trinh
- GET `/api/v1/phieu-kham/luot/{visit_id}/ket-qua-chi-dinh` → `src/clinicai/api/v1/routers/phieu_kham.py:ket_qua_chi_dinh` → PhieuKhamService.ket_qua_chi_dinh, PhieuKhamService.mau_du_phong, PhieuKhamService.lan_chi_dinh, PhieuKhamService.tep_chua_gan
- PUT `/api/v1/phieu-kham/luot/{visit_id}/phieu` → `src/clinicai/api/v1/routers/phieu_kham.py:luu_phieu_cua_luot` → PhieuKhamService.luu_luot
- PUT `/api/v1/phieu-kham/luot/{visit_id}/don-thuoc` → `src/clinicai/api/v1/routers/phieu_kham.py:luu_don_thuoc` → PhieuKhamService.luu_don_thuoc
- PUT `/api/v1/phieu-kham/luot/{visit_id}/ke-don-tu-van` → `src/clinicai/api/v1/routers/phieu_kham.py:danh_dau_xong_ke_don` → PhieuKhamService.danh_dau_xong_ke_don
- POST `/api/v1/phieu-kham/luot/{visit_id}/lich-tai-kham` → `src/clinicai/api/v1/routers/phieu_kham.py:dat_lich_tai_kham` → LichTaiKhamService.dat
- DELETE `/api/v1/phieu-kham/luot/{visit_id}/lich-tai-kham/{appointment_id}` → `src/clinicai/api/v1/routers/phieu_kham.py:huy_lich_tai_kham` → LichTaiKhamService.huy
- test: src/tests/services/test_phieu_kham_db.py, src/tests/services/test_phieu_kham_luot_db.py, src/tests/services/test_danh_muc_dich_vu_chuan_db.py (+11)
- màn dùng: /ban-kham, /ban-kham/[phong], /duyet-ket-qua, /hanh-trinh, /patient-list, /pharmacy (+9)

#### `/api/quay-thuoc` · `src/dashboard/app/api/quay-thuoc/route.ts`
- GET `/api/v1/quay-thuoc/luot/{visit_id}` → `src/clinicai/api/v1/routers/quay_thuoc.py:doc_don_ban` → authorize_payment, QuayThuocService.doc
- POST `/api/v1/quay-thuoc/chon` → `src/clinicai/api/v1/routers/quay_thuoc.py:chon` → authorize_drug_line, QuayThuocService.chon
- POST `/api/v1/quay-thuoc/so-luong` → `src/clinicai/api/v1/routers/quay_thuoc.py:doi_so_luong` → authorize_drug_line, QuayThuocService.doi_so_luong
- POST `/api/v1/quay-thuoc/luot/{visit_id}/them` → `src/clinicai/api/v1/routers/quay_thuoc.py:luu_dong_them` → authorize_payment, QuayThuocService.luu_dong_them
- test: src/tests/services/test_payment_head_scope_db.py, src/tests/unit/test_payment_access.py, src/tests/services/test_quay_thuoc_db.py (+2)
- màn dùng: /pharmacy, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su

#### `/api/queue` · `src/dashboard/app/api/queue/route.ts`
- GET `/api/v1/queue` → `src/clinicai/api/v1/routers/queue.py:get_queue` → b3_ready_times, explain_queue, entry_from_row, b3_ready_times.get + SQL ngay trong router
- test: src/tests/test_no_queue_rule_in_dashboard.py, src/tests/test_queue_order.py, src/tests/services/test_display_board.py (+1)
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/queue/keo` · `src/dashboard/app/api/queue/keo/route.ts`
- POST `/api/v1/queue/keo` → `src/clinicai/api/v1/routers/queue.py:keo_thu_tu` → ThuTuKhamService.keo
- test: src/tests/services/test_luat_1509_sieu_am_va_hang_cho.py, src/tests/services/test_luat_1509_thu_ky_va_dieu_phoi.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/recall-jobs/[id]/ket-qua` · `src/dashboard/app/api/recall-jobs/[id]/ket-qua/route.ts`
- POST `/api/v1/cskh/recall-jobs/{viec_id}/ket-qua` → `src/clinicai/api/v1/routers/cskh.py:record_recall_call` → RecallJobService.ghi_ket_qua
- test: src/tests/unit/test_cua_ngo_ghi_moi.py, src/tests/unit/test_recall_callback_consistency.py
- màn dùng: /customers, /nhac-tai-kham

#### `/api/reception/checkout` · `src/dashboard/app/api/reception/checkout/route.ts`
- GET `/api/v1/reception/checkout` → `src/clinicai/api/v1/routers/dispatch.py:checkout_list` → CheckoutService.pending_list
- GET `/api/v1/reception/checkout/ton-dong` → `src/clinicai/api/v1/routers/dispatch.py:checkout_stale` → CheckoutService.stale_list
- GET `/api/v1/reception/checkout/chi-tiet/{visit_id:uuid}` → `src/clinicai/api/v1/routers/dispatch.py:checkout_chi_tiet` → CheckoutService.chi_tiet
- GET `/api/v1/reception/checkout/{visit_id:uuid}` → `src/clinicai/api/v1/routers/dispatch.py:checkout_readiness` → CheckoutService.readiness
- [hoan_tien_thua] POST `/api/v1/reception/checkout/hoan-tien-thua` → `src/clinicai/api/v1/routers/dispatch.py:checkout_hoan_tien_thua` → authorize_payment, HoanTienService.hoan_tien_thua
- [giu_lai_tien_thua] POST `/api/v1/reception/checkout/giu-lai-tien-thua` → `src/clinicai/api/v1/routers/dispatch.py:checkout_giu_lai_tien_thua` → authorize_payment, TienThuaService.giu_lai
- [huy_giu_lai_tien_thua] POST `/api/v1/reception/checkout/huy-giu-lai-tien-thua` → `src/clinicai/api/v1/routers/dispatch.py:checkout_huy_giu_lai_tien_thua` → authorize_payment, TienThuaService.huy_giu_lai
- [ghi_no] POST `/api/v1/reception/checkout/ghi-no` → `src/clinicai/api/v1/routers/dispatch.py:checkout_ghi_no` → CongNoService.ghi
- POST `/api/v1/reception/checkout/huy-ghi-no` → `src/clinicai/api/v1/routers/dispatch.py:checkout_huy_ghi_no` → CongNoService.huy
- POST `/api/v1/reception/checkout` → `src/clinicai/api/v1/routers/dispatch.py:checkout` → CheckoutService.close
- test: src/tests/services/test_mo_phong_dong_tien_db.py, src/tests/services/test_payment_head_scope_db.py, src/tests/services/test_tien_thua_phan_e_db.py (+11)
- màn dùng: /hanh-trinh, /reception/checkout, /reception/queue, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc (+1)

#### `/api/reports/access` · `src/dashboard/app/api/reports/access/route.ts`
- GET `/api/v1/reports/access` → `src/clinicai/api/v1/routers/reports.py:report_access` → ReportAccessService.access
- test: src/tests/services/test_report_access_db.py, src/tests/services/test_vai_ke_toan_db.py
- màn dùng: /hoa-don, /reports

#### `/api/reports/chot-ca` · `src/dashboard/app/api/reports/chot-ca/route.ts`
- POST `/api/v1/reports/chot-ca` → `src/clinicai/api/v1/routers/reports.py:chot_ca` → ChotSoCaService.chot
- POST `/api/v1/reports/chot-ca/mo-khoa` → `src/clinicai/api/v1/routers/reports.py:mo_khoa_ca` → ChotSoCaService.mo_khoa
- test: src/tests/services/test_chot_so_ca_db.py
- màn dùng: /reports

#### `/api/reports/cuoi-ngay` · `src/dashboard/app/api/reports/cuoi-ngay/route.ts`
- GET `/api/v1/reports/cuoi-ngay` → `src/clinicai/api/v1/routers/reports.py:bao_cao_cuoi_ngay` → ReportAccessService.authorize, BaoCaoCuoiNgayService.bao_cao, gioi_han_ban_hang, gioi_han_tai_chinh_ca
- `/api/v1/reports/cuoi-ngay.${format}` → ?
- test: src/tests/services/test_report_access_db.py, src/tests/unit/test_report_access.py, src/tests/services/test_bao_cao_cuoi_ca_db.py (+1)
- màn dùng: /reports

#### `/api/reports/settings` · `src/dashboard/app/api/reports/settings/route.ts`
- GET `/api/v1/reports/settings` → `src/clinicai/api/v1/routers/reports.py:report_settings` → ReportAccessService.settings
- PATCH `/api/v1/reports/settings` → `src/clinicai/api/v1/routers/reports.py:save_report_settings` → ReportAccessService.save
- test: src/tests/services/test_report_access_db.py, src/tests/services/test_ke_toan_lego_db.py
- màn dùng: /settings

#### `/api/roster` · `src/dashboard/app/api/roster/route.ts`
- GET `/api/v1/roster/ca-cua-toi` → `src/clinicai/api/v1/routers/config.py:ca_cua_toi` → (SQL ngay trong router, không qua service)
- GET `/api/v1/roster/phien-ban` → `src/clinicai/api/v1/routers/config.py:lich_truc_phien_ban` → LichTrucPhienBanService.xem
- GET `/api/v1/roster/weeks/applied` → `src/clinicai/api/v1/routers/config.py:applied_weeks` → RosterService.applied_weeks
- GET `/api/v1/roster/stations` → `src/clinicai/api/v1/routers/config.py:roster_stations` → RosterService.tram_cho_nhan_vien
- GET `/api/v1/roster/bac-si-ngay` → `src/clinicai/api/v1/routers/config.py:bac_si_trong_ngay` → RosterService.bac_si_trong_ngay
- POST `/api/v1/roster/weeks/apply` → `src/clinicai/api/v1/routers/config.py:apply_week` → RosterService.apply_week
- POST `/api/v1/roster/shifts` → `src/clinicai/api/v1/routers/config.py:add_shift` → RosterService.add_shift
- PATCH `/api/v1/roster/shifts/{roster_id}` → `src/clinicai/api/v1/routers/config.py:decide_shift` → RosterService.decide
- DELETE `/api/v1/roster/shifts/{roster_id}` → `src/clinicai/api/v1/routers/config.py:remove_shift` → RosterService.remove
- test: src/tests/test_clinical_cluster.py, src/tests/services/test_lich_truc_phien_ban_db.py, src/tests/unit/test_pham_vi_vi_tri_lich_truc.py (+3)
- màn dùng: /appointments, /customers, /doi-tac, /patients/new, /schedule, /settings/clinic-config

#### `/api/roster/ngoai-le-ca-truc` · `src/dashboard/app/api/roster/ngoai-le-ca-truc/route.ts`
- GET `/api/v1/roster/clinical-exceptions` → `src/clinicai/api/v1/routers/config.py:danh_sach_ngoai_le_ca_truc` → NgoaiLeCaTrucService.danh_sach
- POST `/api/v1/roster/clinical-exceptions` → `src/clinicai/api/v1/routers/config.py:mo_ngoai_le_ca_truc` → NgoaiLeCaTrucService.mo
- DELETE `/api/v1/roster/clinical-exceptions/{ngoai_le_id}` → `src/clinicai/api/v1/routers/config.py:huy_ngoai_le_ca_truc` → NgoaiLeCaTrucService.huy
- test: src/tests/services/test_ca_truc_lam_sang_db.py
- màn dùng: /schedule

#### `/api/roster/pham-vi` · `src/dashboard/app/api/roster/pham-vi/route.ts`
- GET `/api/v1/roster/station-scope` → `src/clinicai/api/v1/routers/config.py:station_scope` → RosterService.ma_tran_vi_tri
- PUT `/api/v1/roster/station-scope` → `src/clinicai/api/v1/routers/config.py:set_station_scope` → RosterService.dat_vi_tri_cho_vai
- test: src/tests/unit/test_pham_vi_vi_tri_lich_truc.py, src/tests/services/test_truong_ca_xep_lich_db.py
- màn dùng: /settings

#### `/api/roster/thay-nguoi` · `src/dashboard/app/api/roster/thay-nguoi/route.ts`
- POST `/api/v1/roster/shifts/{roster_id}/thay-nguoi` → `src/clinicai/api/v1/routers/config.py:thay_nguoi` → RosterService.thay_nguoi
- test: src/tests/services/test_ca_truc_lam_sang_db.py, src/tests/services/test_doi_nguoi_trong_ca_db.py
- màn dùng: /schedule

#### `/api/service-log` · `src/dashboard/app/api/service-log/route.ts`
- POST `/api/v1/service-log` → `src/clinicai/api/v1/routers/service_log.py:create_service_item` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- PATCH `/api/v1/service-log/{row_id}` → `src/clinicai/api/v1/routers/service_log.py:progress_service_item` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/service-price` · `src/dashboard/app/api/service-price/route.ts`
- GET `/api/v1/service-prices/danh-muc` → `src/clinicai/api/v1/routers/config.py:danh_muc_dich_vu` → DanhMucDichVuService.doc
- GET `/api/v1/service-prices/phong-lam` → `src/clinicai/api/v1/routers/config.py:list_phong_lam` → PriceListService.phong_lam
- POST `/api/v1/service-prices` → `src/clinicai/api/v1/routers/config.py:add_price` → PriceListService.add
- PATCH `/api/v1/service-prices/{price_id}` → `src/clinicai/api/v1/routers/config.py:update_price` → PriceListService.update
- DELETE `/api/v1/service-prices/{price_id}` → `src/clinicai/api/v1/routers/config.py:remove_price` → PriceListService.remove
- test: src/tests/services/test_danh_muc_dich_vu_chuan_db.py, src/tests/services/test_vat_tu_danh_muc_db.py, src/tests/services/test_gia_thuoc_hai_nguon_khop_db.py (+1)
- màn dùng: /cashier/dich-vu, /cashier/thuoc, /kho-vat-tu

#### `/api/service-price/vat-tu-hang-loat` · `src/dashboard/app/api/service-price/vat-tu-hang-loat/route.ts`
- POST `/api/v1/service-prices/vat-tu/hang-loat` → `src/clinicai/api/v1/routers/config.py:dat_co_vat_tu_hang_loat` → dat_co_hang_loat
- test: src/tests/services/test_vat_tu_hang_loat_db.py
- màn dùng: /kho-vat-tu

#### `/api/sono` · `src/dashboard/app/api/sono/route.ts`
- POST `/api/v1/sono/queue` → `src/clinicai/api/v1/routers/service_log.py:create_sono_row` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- PATCH `/api/v1/sono/queue/{row_id}` → `src/clinicai/api/v1/routers/service_log.py:progress_sono_row` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- DELETE `/api/v1/sono/queue/{row_id}` → `src/clinicai/api/v1/routers/service_log.py:remove_sono_row` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/staff` · `src/dashboard/app/api/staff/route.ts`
- GET `/api/v1/staff` → `src/clinicai/api/v1/routers/staff.py:list_staff` → StaffService.list_assignable, StaffService.list_active
- POST `/api/v1/staff` → `src/clinicai/api/v1/routers/staff.py:create_staff` → StaffService.create_staff
- PATCH `/api/v1/staff/{id}` → `src/clinicai/api/v1/routers/staff.py:update_staff` → StaffService.update_staff
- test: src/tests/unit/test_staff_service.py, src/tests/services/test_quyen_khoi_dong_db.py, src/tests/services/test_vai_doi_tac_nhan_su_db.py
- màn dùng: /nhan-su

#### `/api/thai-ky` · `src/dashboard/app/api/thai-ky/route.ts`
- GET `/api/v1/thai-ky` → `src/clinicai/api/v1/routers/thai_ky.py:doc_thai_ky` → ThaiKyService.doc
- PATCH `/api/v1/thai-ky/{pregnancy_id}` → `src/clinicai/api/v1/routers/thai_ky.py:cap_nhat_thai_ky` → ThaiKyService.cap_nhat
- POST `/api/v1/thai-ky` → `src/clinicai/api/v1/routers/thai_ky.py:tao_thai_ky` → ThaiKyService.tao
- test: src/tests/services/test_thai_ky_db.py, src/tests/services/test_thai_ky_tu_phieu_sk_db.py
- màn dùng: /ban-kham, /ban-kham/[phong], /tu-van

#### `/api/theo-hang-hoa` · `src/dashboard/app/api/theo-hang-hoa/route.ts`
- GET `/api/v1/hoa-don/theo-hang-hoa` → `src/clinicai/api/v1/routers/hoa_don.py:theo_hang_hoa` → TheoHangHoaService.xem
- GET `/api/v1/hoa-don/theo-hang-hoa/xlsx` → `src/clinicai/api/v1/routers/hoa_don.py:theo_hang_hoa_excel` → xlsx_theo_hang_hoa
- test: src/tests/services/test_theo_hang_hoa_db.py, src/tests/unit/test_theo_hang_hoa.py
- màn dùng: /ke-toan

#### `/api/thong-bao` · `src/dashboard/app/api/thong-bao/route.ts`
- GET `/api/v1/thong-bao` → `src/clinicai/api/v1/routers/dispatch.py:my_notifications` → ThongBaoService.cua_toi
- POST `/api/v1/thong-bao/da-doc` → `src/clinicai/api/v1/routers/dispatch.py:mark_notifications_read` → ThongBaoService.danh_dau_da_doc
- test: src/tests/services/test_so_sua_chi_dinh_db.py, src/tests/services/test_chuong_mot_thong_bao_moi_nguoi_db.py, src/tests/unit/test_cua_ngo_ghi_moi.py
- màn dùng: /doi-tac

#### `/api/thong-bao/[id]/da-xu-ly` · `src/dashboard/app/api/thong-bao/[id]/da-xu-ly/route.ts`
- POST `/api/v1/thong-bao/{thong_bao_id:uuid}/da-xu-ly` → `src/clinicai/api/v1/routers/dispatch.py:resolve_notification` → ThongBaoService.da_xu_ly
- test: src/tests/services/test_so_sua_chi_dinh_db.py, src/tests/unit/test_cua_ngo_ghi_moi.py
- màn dùng: /doi-tac

#### `/api/ultrasound` · `src/dashboard/app/api/ultrasound/route.ts`
- [rooms] GET `/api/v1/ultrasound/rooms` → `src/clinicai/api/v1/routers/ultrasound.py:sono_rooms` → UltrasoundBoardService.rooms
- [records] GET `/api/v1/ultrasound/records` → `src/clinicai/api/v1/routers/ultrasound.py:sono_records` → UltrasoundBoardService.records, group_by_patient
- GET `/api/v1/ultrasound/queue` → `src/clinicai/api/v1/routers/ultrasound.py:sono_queue` → UltrasoundBoardService.queue
- POST `/api/v1/ultrasound/queue/{work_item_id}/nhan` → `src/clinicai/api/v1/routers/ultrasound.py:nhan_ca_sieu_am` → ?
- POST `/api/v1/ultrasound/draft` → `src/clinicai/api/v1/routers/ultrasound.py:sono_save_draft` → UltrasoundBoardService.save_draft
- test: src/tests/services/test_luat_1509_sieu_am_va_hang_cho.py, src/tests/services/test_loc_co_so_nhom_c_db.py, src/tests/services/test_luat_1509_thu_ky_va_dieu_phoi.py (+1)
- màn dùng: /ban-kham, /ban-kham/[phong], /patient-list, /tu-van

#### `/api/ultrasound/image` · `src/dashboard/app/api/ultrasound/image/route.ts`
- POST `/api/v1/ultrasound/{ultrasound_id}/image` → `src/clinicai/api/v1/routers/ultrasound.py:upload_image` → MediaService.attach_ultrasound_image
- GET `/api/v1/ultrasound/image` → `src/clinicai/api/v1/routers/ultrasound.py:get_image` → MediaService.read_ultrasound_image
- test: src/tests/services/test_media.py, src/tests/unit/test_kho_tep_ghi.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/vat-tu-kho/[action]` · `src/dashboard/app/api/vat-tu-kho/[action]/route.ts`
- [ton] GET `/api/v1/vat-tu-kho/ton` → `src/clinicai/api/v1/routers/vat_tu_kho.py:ton` → vat_tu_kho_service.doc_ton, vat_tu_kho_man_service.doc_noi_chua, vat_tu_kho_man_service.doc_vat_tu_chon
- [canh-bao] GET `/api/v1/vat-tu-kho/canh-bao` → `src/clinicai/api/v1/routers/vat_tu_kho.py:canh_bao` → vat_tu_kho_man_service.doc_canh_bao
- [tieu-hao] GET `/api/v1/vat-tu-kho/tieu-hao` → `src/clinicai/api/v1/routers/vat_tu_kho.py:bao_cao_tieu_hao` → vat_tu_tieu_hao_service.doc_tieu_hao
- [cho-duyet] GET `/api/v1/vat-tu-kho/cho-duyet` → `src/clinicai/api/v1/routers/vat_tu_nhap_duyet.py:danh_sach` → can, vat_tu_nhap_duyet_service.doc_cho_duyet
- [phieu] GET `/api/v1/vat-tu-kho/phieu` → `src/clinicai/api/v1/routers/vat_tu_kho.py:danh_sach_phieu` → vat_tu_kho_man_service.doc_phieu
- [phieu] POST `/api/v1/vat-tu-kho/phieu` → `src/clinicai/api/v1/routers/vat_tu_kho.py:lap_phieu` → vat_tu_kho_service.tao_phieu
- POST `/api/v1/vat-tu-kho/cho-duyet/{yeu_cau_id}/duyet` → `src/clinicai/api/v1/routers/vat_tu_nhap_duyet.py:duyet` → vat_tu_nhap_duyet_service.duyet
- POST `/api/v1/vat-tu-kho/cho-duyet/{yeu_cau_id}/rut-lai` → `src/clinicai/api/v1/routers/vat_tu_nhap_duyet.py:rut_lai` → vat_tu_nhap_duyet_service.rut_lai
- POST `/api/v1/vat-tu-kho/cho-duyet/{yeu_cau_id}/tu-choi` → `src/clinicai/api/v1/routers/vat_tu_nhap_duyet.py:tu_choi` → vat_tu_nhap_duyet_service.tu_choi
- POST `/api/v1/vat-tu-kho/phieu` → `src/clinicai/api/v1/routers/vat_tu_kho.py:lap_phieu` → vat_tu_kho_service.tao_phieu
- POST `/api/v1/vat-tu-kho/phieu/{phieu_id}/hoan` → `src/clinicai/api/v1/routers/vat_tu_kho.py:hoan_phieu` → vat_tu_kho_service.hoan_phieu
- PUT `/api/v1/vat-tu-kho/muc-toi-thieu` → `src/clinicai/api/v1/routers/vat_tu_kho.py:muc_toi_thieu` → vat_tu_kho_man_service.dat_muc_toi_thieu
- test: src/tests/services/test_vat_tu_nhap_duyet_db.py, src/tests/services/test_vat_tu_kho_man_db.py, src/tests/services/test_vat_tu_kho_db.py (+3)
- màn dùng: /kho-vat-tu

#### `/api/visits/[id]/charges` · `src/dashboard/app/api/visits/[id]/charges/route.ts`
- GET `/api/v1/visits/{visit_id}/charges` → `src/clinicai/api/v1/routers/work_items.py:visit_charges` → CashierScopeService.active_visit, ServiceOrderService.charges
- test: src/tests/services/test_luat_1509_nhap_chi_dinh_va_ky.py, src/tests/unit/test_cashier_scope.py, src/tests/unit/test_payment_access.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/visits/[id]/service-orders` · `src/dashboard/app/api/visits/[id]/service-orders/route.ts`
- POST `/api/v1/visits/{visit_id}/service-orders` → `src/clinicai/api/v1/routers/work_items.py:order_services` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/visits/[id]/service-orders/current` · `src/dashboard/app/api/visits/[id]/service-orders/current/route.ts`
- GET `/api/v1/visits/{visit_id}/service-orders/current` → `src/clinicai/api/v1/routers/work_items.py:current_service_orders` → ServiceOrderService.dang_chi_dinh
- test: src/tests/services/test_luat_1509_thu_ky_va_dieu_phoi.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/visits/[id]/service-orders/draft` · `src/dashboard/app/api/visits/[id]/service-orders/draft/route.ts`
- GET `/api/v1/visits/{visit_id}/service-orders/draft` → `src/clinicai/api/v1/routers/work_items.py:get_service_order_draft` → ServiceOrderService.get_draft
- POST `/api/v1/visits/{visit_id}/service-orders/draft` → `src/clinicai/api/v1/routers/work_items.py:add_to_service_order_draft` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- PUT `/api/v1/visits/{visit_id}/service-orders/draft` → `src/clinicai/api/v1/routers/work_items.py:replace_service_order_draft` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- test: src/tests/services/test_luat_1509_nhap_chi_dinh_va_ky.py, src/tests/services/test_service_order_draft.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/visits/[id]/service-orders/draft/approve` · `src/dashboard/app/api/visits/[id]/service-orders/draft/approve/route.ts`
- POST `/api/v1/visits/{visit_id}/service-orders/draft/approve` → `src/clinicai/api/v1/routers/work_items.py:approve_service_order_draft` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/visits/[id]/service-orders/draft/discard` · `src/dashboard/app/api/visits/[id]/service-orders/draft/discard/route.ts`
- POST `/api/v1/visits/{visit_id}/service-orders/draft/discard` → `src/clinicai/api/v1/routers/work_items.py:discard_service_order_draft` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/visits/[id]/service-orders/duplicates` · `src/dashboard/app/api/visits/[id]/service-orders/duplicates/route.ts`
- POST `/api/v1/visits/{visit_id}/service-orders/duplicates` → `src/clinicai/api/v1/routers/work_items.py:check_duplicates` → ServiceOrderService.duplicates
- test: src/tests/services/test_luat_1509_nhap_chi_dinh_va_ky.py, src/tests/services/test_service_order_draft.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/visits/[id]/service-orders/remove` · `src/dashboard/app/api/visits/[id]/service-orders/remove/route.ts`
- POST `/api/v1/visits/{visit_id}/service-orders/remove` → `src/clinicai/api/v1/routers/work_items.py:remove_service_order` → ĐÃ NGHỈ — trả 410 (`clinicai/api/nghi_huu.py`), đừng sửa ở đây
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/visits/[id]/theo-doi-thu-thuat` · `src/dashboard/app/api/visits/[id]/theo-doi-thu-thuat/route.ts`
- GET `/api/v1/visits/{visit_id}/theo-doi-thu-thuat` → `src/clinicai/api/v1/routers/theo_doi_thu_thuat.py:doc_theo_doi` → TheoDoiThuThuatService.doc
- PUT `/api/v1/visits/{visit_id}/theo-doi-thu-thuat` → `src/clinicai/api/v1/routers/theo_doi_thu_thuat.py:dat_theo_doi` → TheoDoiThuThuatService.dat
- test: src/tests/services/test_dich_vu_rail_moi_db.py, src/tests/services/test_theo_doi_thu_thuat.py
- màn dùng: /ban-kham, /ban-kham/[phong], /patient-list, /tu-van

#### `/api/wards` · `src/dashboard/app/api/wards/route.ts`
- GET `/api/v1/catalog/wards` → `src/clinicai/api/v1/routers/catalog.py:list_wards` → (SQL ngay trong router, không qua service)
- màn dùng: /appointments, /patients/new

#### `/api/work-items` · `src/dashboard/app/api/work-items/route.ts`
- GET `/api/v1/work-items` → `src/clinicai/api/v1/routers/work_items.py:worklist` → QUYEN_THEO_KHU.get, doi_quyen, WorkItemService.list_worklist
- test: src/tests/api/test_worklist.py, src/tests/services/test_doi_nguoi_trong_ca_db.py, src/tests/services/test_permission_db.py (+2)
- màn dùng: /viec-can-xu-ly

#### `/api/work-items/[id]/blockers` · `src/dashboard/app/api/work-items/[id]/blockers/route.ts`
- GET `/api/v1/work-items/{work_item_id}/blockers` → `src/clinicai/api/v1/routers/work_items.py:work_item_blockers` → WorkItemService.blockers
- test: src/tests/test_work_item_service.py
- màn dùng: (không màn nào gọi thấy được ?)

#### `/api/work-items/[id]/commands/[command]` · `src/dashboard/app/api/work-items/[id]/commands/[command]/route.ts`
- POST `/api/v1/work-items/{work_item_id}/commands/cancel` → `src/clinicai/api/v1/routers/work_items.py:cancel_work_item` → WorkItemService.issue
- POST `/api/v1/work-items/{work_item_id}/commands/complete` → `src/clinicai/api/v1/routers/work_items.py:complete_work_item` → WorkItemService.issue
- POST `/api/v1/work-items/{work_item_id}/commands/skip` → `src/clinicai/api/v1/routers/work_items.py:skip_work_item` → WorkItemService.issue
- POST `/api/v1/work-items/{work_item_id}/commands/start` → `src/clinicai/api/v1/routers/work_items.py:start_work_item` → WorkItemService.issue
- test: src/tests/api/test_visit_work_items_read.py, src/tests/test_work_item_service.py
- màn dùng: /viec-can-xu-ly

#### `/api/xuat-hoa-don` · `src/dashboard/app/api/xuat-hoa-don/route.ts`
- GET `/api/v1/hoa-don/xuat` → `src/clinicai/api/v1/routers/hoa_don.py:xuat_hoa_don` → XuatHoaDonService.xem, HoaDonMisaService.gan_trang_thai
- GET `/api/v1/hoa-don/xuat/xlsx` → `src/clinicai/api/v1/routers/hoa_don.py:xuat_hoa_don_excel` → xlsx_misa
- test: src/tests/services/test_thue_gtgt_db.py, src/tests/services/test_hoa_don_misa_db.py, src/tests/services/test_sua_ho_so_khach_db.py (+1)
- màn dùng: /xuat-hoa-don

## 3. Service → màn (200)

| Service | Tệp | Màn dùng |
|---|---|---|
| `agent_giam_sat` | `src/clinicai/services/agent_giam_sat.py` | /doi-tac, /giam-sat, /login |
| `agent_tom_tat` | `src/clinicai/services/agent_tom_tat.py` | /doi-tac, /giam-sat, /login |
| `AndrologyReviewService` | `src/clinicai/services/andrology_review_service.py` | /ban-kham, /ban-kham/[phong], /tu-van |
| `AnhChuyenKhoanService` | `src/clinicai/services/anh_chuyen_khoan_service.py` | /pharmacy, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `append` | `src/clinicai/tools/event_log/append.py` | — (chỉ API/worker) |
| `AppendEventInput` | `src/clinicai/tools/event_log/append.py` | — (chỉ API/worker) |
| `audit` | `src/clinicai/services/audit.py` | /doi-tac, /settings/new-user, /settings/tai-khoan |
| `AuditLogService` | `src/clinicai/services/audit_log_service.py` | /audit-log |
| `AuthService` | `src/clinicai/services/auth_service.py` | — (chỉ API/worker) |
| `ban_theo_don_service` | `src/clinicai/services/ban_theo_don_service.py` | /pharmacy, /pharmacy/inventory |
| `ban_thuoc_service` | `src/clinicai/services/ban_thuoc_service.py` | /pharmacy |
| `BangHanhTrinhService` | `src/clinicai/services/bang_hanh_trinh_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `BangLuotKham` | `src/clinicai/services/luot_kham_doc.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `BanLeService` | `src/clinicai/services/ban_le_service.py` | /pharmacy, /pharmacy/inventory, /print/tem-lo |
| `bao_cao_cuoi_ngay_service` | `src/clinicai/services/bao_cao_cuoi_ngay_service.py` | — (chỉ API/worker) |
| `BaoCaoCuoiNgayService` | `src/clinicai/services/bao_cao_cuoi_ngay_service.py` | /reports |
| `BioChiDinhService` | `src/clinicai/services/bio_chi_dinh_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `BookingOverrideService` | `src/clinicai/services/booking_override_service.py` | /settings/booking-policy |
| `BookingService` | `src/clinicai/services/booking_service.py` | /appointments, /appointments/cho-xep-bac-si, /ban-kham, /ban-kham/[phong], /customers, /home, /nhac-tai-kham, /patient-list (+3) |
| `can` | `src/clinicai/permissions/can.py` | /kho-vat-tu, /ops, /pharmacy, /pharmacy/inventory, /print/tem-lo, /settings/new-user, /settings/tai-khoan, /viec-can-xu-ly |
| `canh_gac` | `src/clinicai/services/canh_gac.py` | /ops |
| `capacity_service` | `src/clinicai/services/capacity_service.py` | /appointments, /customers, /home, /patients/new, /reception/queue |
| `CapacityService` | `src/clinicai/services/capacity_service.py` | /appointments, /customers, /home, /patients/new, /reception/queue |
| `cashier_navigation_service` | `src/clinicai/services/cashier_navigation_service.py` | /ops, /settings/new-user, /settings/tai-khoan |
| `CashierBoardService` | `src/clinicai/services/cashier_board_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /hanh-trinh, /home, /kho-vat-tu, /nhac-tai-kham (+13) |
| `CashierScopeService` | `src/clinicai/services/cashier_scope_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /hanh-trinh, /home, /kho-vat-tu, /nhac-tai-kham (+13) |
| `catalogue` | `src/clinicai/permissions/catalogue.py` | /phan-quyen |
| `check_sla` | `src/clinicai/tools/task/check_sla.py` | — (chỉ API/worker) |
| `CheckoutService` | `src/clinicai/services/checkout_service.py` | /hanh-trinh, /reception/checkout, /reception/queue, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `chi_phi` | `src/clinicai/llm/chi_phi.py` | /doi-tac, /giam-sat, /login |
| `ChiDinhService` | `src/clinicai/services/chi_dinh_service.py` | /ban-kham, /ban-kham/[phong], /patient-list, /tu-van |
| `ChotSoCaService` | `src/clinicai/services/chot_so_ca_service.py` | /reports |
| `classify` | `src/clinicai/tools/lab/classify.py` | — (chỉ API/worker) |
| `clinic_policy` | `src/clinicai/services/clinic_policy.py` | — (chỉ API/worker) |
| `ClinicalFormService` | `src/clinicai/services/clinical_form_service.py` | /ban-kham, /ban-kham/[phong], /patient-list, /tu-van |
| `ClinicalRecordService` | `src/clinicai/services/clinical_record_service.py` | /ban-kham, /ban-kham/[phong], /patient-list, /tu-van |
| `ClinicalSignService` | `src/clinicai/services/clinical_sign_service.py` | /ban-kham, /ban-kham/[phong], /patient-list, /tu-van |
| `ClinicConfigService` | `src/clinicai/services/clinic_config_service.py` | /cashier/dich-vu, /nhan-su, /settings/clinic-config |
| `ClinicSettingsService` | `src/clinicai/services/clinic_settings_service.py` | /settings, /settings/booking-policy |
| `CongNoService` | `src/clinicai/services/cong_no_service.py` | /hanh-trinh, /reception/checkout, /reception/queue, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `ConsentService` | `src/clinicai/services/consent_service.py` | — (chỉ API/worker) |
| `ConsoleService` | `src/clinicai/services/console_service.py` | /console |
| `context` | `src/clinicai/tools/_common/context.py` | — (chỉ API/worker) |
| `create_task` | `src/clinicai/tools/task/create_task.py` | — (chỉ API/worker) |
| `CreateTaskInput` | `src/clinicai/tools/task/create_task.py` | — (chỉ API/worker) |
| `cskh_service` | `src/clinicai/services/cskh_service.py` | — (chỉ API/worker) |
| `CskhService` | `src/clinicai/services/cskh_service.py` | /appointments, /patients/new |
| `danh_sach_hoa_don_service` | `src/clinicai/services/danh_sach_hoa_don_service.py` | /hoa-don |
| `danh_sach_khach_cskh` | `src/clinicai/services/danh_sach_khach_cskh.py` | /customers |
| `DanhMucDichVuService` | `src/clinicai/services/danh_muc_dich_vu_service.py` | /cashier/dich-vu, /cashier/thuoc, /kho-vat-tu |
| `DanhSachBenhNhanService` | `src/clinicai/services/danh_sach_benh_nhan_service.py` | /patient-list |
| `DanhSachHoaDonService` | `src/clinicai/services/danh_sach_hoa_don_service.py` | /hoa-don |
| `day_tep` | `src/clinicai/services/day_tep.py` | /ops |
| `DayNoiService` | `src/clinicai/services/day_noi_service.py` | /settings/clinic-config, /settings/day-noi |
| `dich_vu_dat_lich` | `src/clinicai/services/dich_vu_dat_lich.py` | /appointments, /customers, /home, /patients/new, /reception/queue |
| `dieu_tri_ban_kham` | `src/clinicai/services/dieu_tri_ban_kham.py` | /ban-kham, /ban-kham/[phong], /customers, /patient-list, /print/phieu-kham/[visitId], /tu-van |
| `DispatchService` | `src/clinicai/services/dispatch_service.py` | /truong-ca, /truong-ca/lich-su, /truong-ca/tv |
| `DisplayBoardService` | `src/clinicai/services/display_board_service.py` | /display |
| `doc_bang` | `src/clinicai/permissions/doc_bang.py` | /ban-kham, /ban-kham/[phong], /customers, /patient-list, /print/phieu-kham/[visitId], /tu-van |
| `DoctorBoardService` | `src/clinicai/services/doctor_board_service.py` | — (chỉ API/worker) |
| `doi_dich_vu_kham` | `src/clinicai/services/doi_dich_vu_kham.py` | /home, /nhac-tai-kham, /reception/queue |
| `doi_lich_nhanh` | `src/clinicai/services/doi_lich_nhanh.py` | /appointments, /home, /reception/queue |
| `DoiBacSiService` | `src/clinicai/services/doi_bac_si_service.py` | /truong-ca, /truong-ca/lich-su, /truong-ca/tv |
| `DoiHinhThucService` | `src/clinicai/services/doi_hinh_thuc_service.py` | /pharmacy, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `DoiTacService` | `src/clinicai/services/doi_tac_service.py` | /doi-tac |
| `DonDuLieuThuService` | `src/clinicai/services/don_du_lieu_thu_service.py` | /settings/don-du-lieu-thu |
| `EpisodeService` | `src/clinicai/services/episode_service.py` | — (chỉ API/worker) |
| `excel_export` | `src/clinicai/services/excel_export.py` | /pharmacy, /pharmacy/inventory, /print/tem-lo |
| `excel_report_export` | `src/clinicai/services/excel_report_export.py` | — (chỉ API/worker) |
| `find_oncall` | `src/clinicai/tools/scheduling/find_oncall.py` | — (chỉ API/worker) |
| `FindOncallInput` | `src/clinicai/tools/scheduling/find_oncall.py` | — (chỉ API/worker) |
| `FormEngineService` | `src/clinicai/services/form_engine_service.py` | /ban-kham, /ban-kham/[phong], /patient-list, /phong/[ma], /print/ket-qua-luot/[visitId], /print/ket-qua/[orderId], /print/phieu-kham/[visitId], /settings/mau-ket-qua (+1) |
| `get_summary` | `src/clinicai/tools/patient/get_summary.py` | — (chỉ API/worker) |
| `GetPatientSummaryInput` | `src/clinicai/tools/patient/get_summary.py` | — (chỉ API/worker) |
| `ghi_chu_luot` | `src/clinicai/services/ghi_chu_luot.py` | /ban-kham, /ban-kham/[phong], /customers, /patient-list, /print/phieu-kham/[visitId], /tu-van |
| `GhiChuKhachService` | `src/clinicai/services/ghi_chu_khach_service.py` | /ban-kham, /ban-kham/[phong], /customers, /patient-list, /tu-van |
| `GuiZaloService` | `src/clinicai/services/tuong_tac_cskh_service.py` | — (chỉ API/worker) |
| `HanhTrinhKhachService` | `src/clinicai/services/hanh_trinh_khach_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `HenGoiLaiService` | `src/clinicai/services/tuong_tac_cskh_service.py` | /customers |
| `ho_so_dich_vu` | `src/clinicai/services/ho_so_dich_vu.py` | /ban-kham, /ban-kham/[phong], /customers, /patient-list, /print/phieu-kham/[visitId], /tu-van |
| `ho_so_khach_doc` | `src/clinicai/services/ho_so_khach_doc.py` | — (chỉ API/worker) |
| `ho_so_lam_sang_doc` | `src/clinicai/services/ho_so_lam_sang_doc.py` | /ban-kham, /ban-kham/[phong], /patient-list, /print/[appointmentId], /tu-van |
| `HoaDonCongTyService` | `src/clinicai/services/hoa_don_cong_ty_service.py` | /customers, /hoa-don, /pharmacy, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `HoaDonMisaService` | `src/clinicai/services/hoa_don_misa_service.py` | /xuat-hoa-don |
| `HoanTacService` | `src/clinicai/services/hoan_tac_service.py` | /ban-kham, /ban-kham/[phong], /doi-tac, /duyet-ket-qua, /hanh-trinh, /patient-list, /phong/[ma], /print/phieu-thu/[id] (+6) |
| `HoanTienService` | `src/clinicai/services/hoan_tien_service.py` | /pharmacy, /reception/checkout, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `HoSoKhamService` | `src/clinicai/services/ho_so_kham_service.py` | /customers |
| `kho_loi` | `src/clinicai/services/kho_loi.py` | /doi-tac, /giam-sat, /login, /ops |
| `kho_thuoc_service` | `src/clinicai/services/kho_thuoc_service.py` | /pharmacy, /pharmacy/inventory, /print/tem-lo |
| `KHOI` | `src/clinicai/permissions/catalogue.py` | /phan-quyen |
| `khung` | `src/clinicai/phieu_kham/khung.py` | /ban-kham, /ban-kham/[phong], /duyet-ket-qua, /hanh-trinh, /patient-list, /pharmacy, /phong, /phong/[ma] (+7) |
| `kiem_ke_ca_service` | `src/clinicai/services/kiem_ke_ca_service.py` | /pharmacy/inventory |
| `KyNangService` | `src/clinicai/services/ky_nang_service.py` | /phan-quyen |
| `lab_triage` | `src/clinicai/graphs/lab_triage/__init__.py` | — (chỉ API/worker) |
| `LabSafetyService` | `src/clinicai/services/lab_safety_service.py` | — (chỉ API/worker) |
| `LabTriageState` | `src/clinicai/graphs/lab_triage/state.py` | — (chỉ API/worker) |
| `LamThemTaiQuayService` | `src/clinicai/services/lam_them_tai_quay_service.py` | /do-sinh-hieu, /reception/queue, /settings/day-noi |
| `LamTruocThuSauService` | `src/clinicai/services/lam_truoc_thu_sau.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `lich_hen_doc` | `src/clinicai/services/lich_hen_doc.py` | /appointments, /appointments/cho-xep-bac-si, /ban-kham, /ban-kham/[phong], /customers, /home, /nhac-tai-kham, /patient-list (+3) |
| `lich_su_luot` | `src/clinicai/services/lich_su_luot.py` | /ban-kham, /ban-kham/[phong], /customers, /patient-list, /print/phieu-kham/[visitId], /tu-van |
| `lich_su_notion_service` | `src/clinicai/services/lich_su_notion_service.py` | /customers, /patient-list |
| `lich_truc_co_so` | `src/clinicai/services/lich_truc_co_so.py` | /appointments/cho-xep-bac-si, /customers |
| `LichPhongService` | `src/clinicai/services/lich_phong_service.py` | /settings/clinic-config |
| `LichTaiKhamService` | `src/clinicai/services/lich_tai_kham_service.py` | /ban-kham, /ban-kham/[phong], /duyet-ket-qua, /hanh-trinh, /patient-list, /pharmacy, /phong, /phong/[ma] (+7) |
| `LichTrucPhienBanService` | `src/clinicai/services/lich_truc_phien_ban_service.py` | /appointments, /customers, /doi-tac, /patients/new, /schedule, /settings/clinic-config |
| `LieuTrinhService` | `src/clinicai/services/lieu_trinh_service.py` | /ban-kham, /ban-kham/[phong], /customers, /nhac-tai-kham, /phong/[ma], /reception/queue, /tu-van |
| `LieuTrinhTienService` | `src/clinicai/services/lieu_trinh_tien.py` | — (chỉ API/worker) |
| `lo_thuoc_service` | `src/clinicai/services/lo_thuoc_service.py` | /pharmacy, /pharmacy/inventory, /print/tem-lo |
| `LuatBacSiService` | `src/clinicai/services/luat_bac_si_service.py` | /settings/booking-policy |
| `LuotKhamService` | `src/clinicai/services/luot_kham_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `LY_DO_HUY` | `src/clinicai/services/booking_service.py` | — (chỉ API/worker) |
| `ma_vach_service` | `src/clinicai/services/ma_vach_service.py` | /pharmacy, /pharmacy/inventory, /print/tem-lo |
| `man_dat_lich_doc` | `src/clinicai/services/man_dat_lich_doc.py` | /appointments |
| `ManKhachHangService` | `src/clinicai/services/man_khach_hang_service.py` | /customers |
| `ManTrangChuService` | `src/clinicai/services/man_trang_chu_service.py` | /home, /reception/queue |
| `MauKetQuaService` | `src/clinicai/services/mau_ket_qua_service.py` | /settings/mau-ket-qua |
| `media_service` | `src/clinicai/services/media_service.py` | /ban-kham, /ban-kham/[phong], /customers, /doi-tac, /duyet-ket-qua, /phong/[ma], /print/ket-qua/[orderId], /print/phieu-kham/[visitId] (+2) |
| `MediaService` | `src/clinicai/services/media_service.py` | — (chỉ API/worker) |
| `MPIService` | `src/clinicai/services/mpi_service.py` | /appointments, /patients/new |
| `NgoaiLeCaTrucService` | `src/clinicai/services/ngoai_le_ca_truc_service.py` | /schedule |
| `NhacViecService` | `src/clinicai/services/nhac_viec_service.py` | /ban-kham, /ban-kham/[phong], /customers, /do-sinh-hieu, /pharmacy, /phong/[ma], /tu-van |
| `nhan_tep_luong` | `src/clinicai/services/nhan_tep_luong.py` | /ban-kham, /ban-kham/[phong], /customers, /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /patient-list, /pharmacy (+6) |
| `NhanTaiPhongService` | `src/clinicai/services/nhan_tai_phong.py` | /ban-kham, /ban-kham/[phong], /doi-tac, /duyet-ket-qua, /hanh-trinh, /patient-list, /phong/[ma], /print/phieu-thu/[id] (+2) |
| `nhat_ky_van_hanh` | `src/clinicai/services/nhat_ky_van_hanh.py` | /ops |
| `OpsStatusService` | `src/clinicai/services/ops_status.py` | /ops |
| `OrchestratorService` | `src/clinicai/orchestrator/service.py` | — (chỉ API/worker) |
| `PatientService` | `src/clinicai/services/patient_service.py` | /appointments, /ban-kham, /ban-kham/[phong], /customers, /patient-list, /patients/new, /tu-van |
| `payment_access_service` | `src/clinicai/services/payment_access_service.py` | /hanh-trinh, /pharmacy, /reception/checkout, /reception/queue, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `PaymentService` | `src/clinicai/services/payment_service.py` | /pharmacy, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `PermissionService` | `src/clinicai/services/permission_service.py` | /phan-quyen |
| `phan_hoi_thuoc_service` | `src/clinicai/services/phan_hoi_thuoc_service.py` | /ban-kham, /ban-kham/[phong], /tu-van |
| `PhanHoiKhachService` | `src/clinicai/services/phan_hoi_khach_service.py` | /customers |
| `PhanHoiThuocService` | `src/clinicai/services/phan_hoi_thuoc_service.py` | /ban-kham, /ban-kham/[phong], /customers, /patient-list, /tu-van |
| `pharmacy_service` | `src/clinicai/services/pharmacy_service.py` | /pharmacy, /pharmacy/inventory, /print/tem-lo |
| `PharmacyService` | `src/clinicai/services/pharmacy_service.py` | /pharmacy, /pharmacy/consult, /pharmacy/history, /pharmacy/inventory, /print/tem-lo |
| `PhieuKhamService` | `src/clinicai/services/phieu_kham_service.py` | /ban-kham, /ban-kham/[phong], /duyet-ket-qua, /hanh-trinh, /patient-list, /pharmacy, /phong, /phong/[ma] (+8) |
| `PhiKhamService` | `src/clinicai/services/phi_kham_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `PRESET` | `src/clinicai/permissions/catalogue.py` | /phan-quyen |
| `PriceListService` | `src/clinicai/services/config_service.py` | /cashier/dich-vu, /cashier/thuoc, /kho-vat-tu |
| `quay_thu_service` | `src/clinicai/services/quay_thu_service.py` | — (chỉ API/worker) |
| `QuayThuocService` | `src/clinicai/services/quay_thuoc_service.py` | /pharmacy, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `QuayThuService` | `src/clinicai/services/quay_thu_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /hanh-trinh, /home, /kho-vat-tu, /nhac-tai-kham (+13) |
| `query_tasks` | `src/clinicai/tools/task/query_tasks.py` | — (chỉ API/worker) |
| `QueryTasksFilter` | `src/clinicai/tools/task/query_tasks.py` | — (chỉ API/worker) |
| `queue_order` | `src/clinicai/services/queue_order.py` | — (chỉ API/worker) |
| `queue_rows` | `src/clinicai/services/queue_rows.py` | — (chỉ API/worker) |
| `QUYEN_THEO_KHU` | `src/clinicai/services/work_item_service.py` | /viec-can-xu-ly |
| `read_policy` | `src/clinicai/tools/kb/read_policy.py` | — (chỉ API/worker) |
| `RecallJobService` | `src/clinicai/services/recall_job_service.py` | /customers, /nhac-tai-kham |
| `RecallService` | `src/clinicai/services/recall_service.py` | — (chỉ API/worker) |
| `report_access_service` | `src/clinicai/services/report_access_service.py` | /reports |
| `ReportAccessService` | `src/clinicai/services/report_access_service.py` | /hoa-don, /reports, /settings |
| `reports_service` | `src/clinicai/services/reports_service.py` | /ops, /reports |
| `ReportsService` | `src/clinicai/services/reports_service.py` | /reports |
| `RosterService` | `src/clinicai/services/config_service.py` | /appointments, /customers, /doi-tac, /patients/new, /schedule, /settings, /settings/clinic-config |
| `SchedulingService` | `src/clinicai/services/scheduling_service.py` | — (chỉ API/worker) |
| `send_zalo` | `src/clinicai/tools/communication/send_zalo.py` | — (chỉ API/worker) |
| `ServiceExecutionService` | `src/clinicai/services/service_execution_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `ServiceOrderService` | `src/clinicai/services/service_order_service.py` | — (chỉ API/worker) |
| `ServiceRoutingService` | `src/clinicai/services/service_routing_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `ServiceSelectionService` | `src/clinicai/services/service_selection_service.py` | /pharmacy, /thu-ngan/dich-vu, /thu-ngan/dich-vu/lich-su, /thu-ngan/thuoc, /thu-ngan/thuoc/lich-su |
| `SinhHieuService` | `src/clinicai/services/sinh_hieu_service.py` | /do-sinh-hieu |
| `SlotHoldService` | `src/clinicai/services/slot_hold_service.py` | /appointments, /patients/new |
| `SoSuaChiDinhService` | `src/clinicai/services/so_sua_chi_dinh_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `StaffService` | `src/clinicai/services/staff_service.py` | /nhan-su, /phan-quyen, /settings/new-user, /settings/tai-khoan |
| `TaiKhoanService` | `src/clinicai/services/tai_khoan_service.py` | /settings/new-user, /settings/tai-khoan |
| `tep_ket_qua_service` | `src/clinicai/services/tep_ket_qua_service.py` | /ban-kham, /ban-kham/[phong], /customers, /doi-tac, /duyet-ket-qua, /patient-list, /phong/[ma], /print/ket-qua/[orderId] (+3) |
| `TepKetQuaService` | `src/clinicai/services/tep_ket_qua_service.py` | /ban-kham, /ban-kham/[phong], /customers, /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /patient-list, /pharmacy (+5) |
| `TepMoDoc` | `src/clinicai/services/tep_ket_qua_service.py` | /customers, /patient-list |
| `ThaiKyService` | `src/clinicai/services/thai_ky_service.py` | /ban-kham, /ban-kham/[phong], /tu-van |
| `theo_hang_hoa_service` | `src/clinicai/services/theo_hang_hoa_service.py` | /ke-toan |
| `TheoDoiThuThuatService` | `src/clinicai/services/theo_doi_thu_thuat_service.py` | /ban-kham, /ban-kham/[phong], /patient-list, /tu-van |
| `TheoHangHoaService` | `src/clinicai/services/theo_hang_hoa_service.py` | /ke-toan |
| `ThongBaoService` | `src/clinicai/services/thong_bao_service.py` | /customers, /doi-tac |
| `thu_ky_bac_si` | `src/clinicai/services/thu_ky_bac_si.py` | /settings/clinic-config |
| `ThueSuatService` | `src/clinicai/services/thue_suat_service.py` | /ke-toan |
| `ThuTuKhamService` | `src/clinicai/services/thu_tu_kham_service.py` | /customers |
| `TienThuaService` | `src/clinicai/services/tien_thua_service.py` | /hanh-trinh, /reception/checkout, /reception/queue |
| `TiepDonService` | `src/clinicai/services/tiep_don_service.py` | /reception/queue |
| `tong_quan_giam_sat` | `src/clinicai/services/tong_quan_giam_sat.py` | /doi-tac, /giam-sat, /login |
| `traffic_service` | `src/clinicai/services/traffic_service.py` | /ops, /traffic |
| `TuongTacCskhService` | `src/clinicai/services/tuong_tac_cskh_service.py` | /appointments/cho-xep-bac-si, /customers, /home, /nhac-tai-kham, /reception/queue |
| `ultrasound_board_service` | `src/clinicai/services/ultrasound_board_service.py` | — (chỉ API/worker) |
| `UltrasoundBoardService` | `src/clinicai/services/ultrasound_board_service.py` | /ban-kham, /ban-kham/[phong], /patient-list, /tu-van |
| `UltrasoundService` | `src/clinicai/services/ultrasound_service.py` | — (chỉ API/worker) |
| `update_task_status` | `src/clinicai/tools/task/update_task_status.py` | — (chỉ API/worker) |
| `vat_tu_danh_muc_service` | `src/clinicai/services/vat_tu_danh_muc_service.py` | /kho-vat-tu |
| `vat_tu_kho_man_service` | `src/clinicai/services/vat_tu_kho_man_service.py` | /kho-vat-tu |
| `vat_tu_kho_service` | `src/clinicai/services/vat_tu_kho_service.py` | /kho-vat-tu |
| `vat_tu_nhap_duyet_service` | `src/clinicai/services/vat_tu_nhap_duyet_service.py` | /kho-vat-tu |
| `vat_tu_tieu_hao_service` | `src/clinicai/services/vat_tu_tieu_hao_service.py` | /kho-vat-tu |
| `VatTuService` | `src/clinicai/services/vat_tu_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `VisitProgressService` | `src/clinicai/services/visit_progress_service.py` | — (chỉ API/worker) |
| `WeekAppointmentsService` | `src/clinicai/services/week_appointments_service.py` | /lich-do-ve |
| `WorkItemService` | `src/clinicai/services/work_item_service.py` | /viec-can-xu-ly |
| `XemLuotService` | `src/clinicai/services/xem_luot_service.py` | /ban-kham, /ban-kham/[phong], /do-sinh-hieu, /doi-tac, /duyet-ket-qua, /hanh-trinh, /home, /patient-list (+11) |
| `xuat_hoa_don_service` | `src/clinicai/services/xuat_hoa_don_service.py` | /xuat-hoa-don |
| `XuatHoaDonService` | `src/clinicai/services/xuat_hoa_don_service.py` | /xuat-hoa-don |
| `y_khoa` | `src/clinicai/permissions/y_khoa.py` | /ban-kham, /ban-kham/[phong], /customers, /duyet-ket-qua, /hanh-trinh, /patient-list, /pharmacy, /phong (+9) |
| `zalo` | `src/clinicai/services/providers/zalo.py` | — (chỉ API/worker) |

## 4. Sự kiện (consumer)

Danh mục sự kiện: `src/clinicai/events/catalogue.py` (mỗi sự kiện khai một chỗ, kèm `consumers`). Worker: `src/clinicai/events/worker.py`.

| Consumer | Tên | Nghe | Cách |
|---|---|---|---|
| `src/clinicai/events/consumers/chuong.py` | `chuong_thong_bao` | `lab_result.arrived`, `partner.order_received`, `pharmacy.expiry_checked`, `pharmacy.stocktake_mismatch`, `result.corrected`, `result.ready`, `result_file.confirmed`, `result_file.uploaded` | sự kiện → `bao_chuong` |
| `src/clinicai/events/consumers/chuong_nhan_cheo.py` | `chuong_nhan_cheo` | `service.completed`, `service.interrupted`, `service.room_release_undone`, `service.room_released`, `service.start_cancelled` | sự kiện → `chuong_nhan_cheo` |
| `src/clinicai/events/consumers/cong_no.py` | `cong_no` | `payment.medicine_collected`, `payment.service_collected` | sự kiện → `xet_da_thu` |
| `src/clinicai/events/consumers/dieu_tri.py` | `dieu_tri_sinh_chi_dinh` | `visit.routed` | sự kiện → `sinh_chi_dinh` |
| `src/clinicai/events/consumers/doi_tac.py` | `doi_tac_nhan_viec` | `payment.service_collected`, `service.completed`, `service_selection.confirmed`, `visit.defer_payment_set` | sự kiện → `nhan_viec_doi_tac` |
| `src/clinicai/events/consumers/dong_thoi_gian.py` | `dong_thoi_gian_luot` | `appointment.booked`, `appointment.cancelled`, `appointment.confirmed_by_call`, `appointment.no_show`, `appointment.rescheduled`, `appointment.service_switched`, `cong_no.da_thu`, `cong_no.ghi`, `cong_no.huy`, `consultation.completed`, `consultation.handed_over`, `consultation.reopened`, `consultation.resumed`, `consultation.started`, `followup.scheduled` (+66) | sự kiện → `ghi_dong_thoi_gian` |
| `src/clinicai/events/consumers/hanh_trinh.py` | `hanh_trinh_luot_kham` | `appointment.service_switched`, `consultation.handed_over`, `partner.sample_collected`, `payment.medicine_collected`, `payment.service_collected`, `service.completed`, `service_order.desk_added`, `service_order.restored`, `service_selection.confirmed`, `visit.checked_in`, `visit.checked_out`, `visit.defer_payment_set`, `visit.left_early`, `vitals.recorded` | sự kiện → `xu_ly_hanh_trinh` |
| `src/clinicai/events/consumers/hanh_trinh.py` | `hanh_trinh.nhac_check_out` | — | hẹn giờ → `nhac_check_out` |
| `src/clinicai/events/consumers/hanh_trinh.py` | `hanh_trinh.ket_qua_doi_tac_qua_han` | — | hẹn giờ → `ket_qua_doi_tac_qua_han` |
| `src/clinicai/events/consumers/lieu_trinh_sap_het.py` | `lieu_trinh_sap_het` | `service.completed` | sự kiện → `bao_sap_het` |
| `src/clinicai/events/consumers/nhac_tai_kham.py` | `nhac_tai_kham.den_han` | — | hẹn giờ → `bao_den_han` |
| `src/clinicai/events/consumers/nhac_viec.py` | `nhac_viec.ca_nhan` | — | hẹn giờ → `nhac_ca_nhan` |
| `src/clinicai/events/consumers/so_no.py` | `so_no` | `cong_no.ghi`, `cong_no.huy`, `medicine.dispensed`, `medicine.returned`, `payment.collection_undone`, `payment.medicine_collected`, `payment.refunded`, `payment.service_collected`, `prescription.saved`, `service.completed`, `service.completion_undone`, `service.not_performed`, `service.start_cancelled`, `service.started`, `service_order.cancelled` (+7) | sự kiện → `ghi_so` |
| `src/clinicai/events/consumers/trach_nhiem.py` | `trach_nhiem_dich_vu` | `service.interrupted`, `service.not_performed`, `service.routing_invalidated` | sự kiện → `mo_viec_khi_can` |
| `src/clinicai/events/consumers/trach_nhiem.py` | `trach_nhiem.kiem_lai` | — | hẹn giờ → `kiem_lai_viec_con_mo` |
| `src/clinicai/events/consumers/vong_doc.py` | `vong_doc_luot_kham` | `partner.sample_collected`, `partner.sample_received`, `result.corrected`, `result.ready`, `result_file.confirmed`, `result_file.deleted`, `result_file.restored`, `result_file.revoked`, `result_file.uploaded`, `service.completed`, `service.not_performed`, `service_selection.confirmed` | sự kiện → `xu_ly_vong_doc` |

## 5. Bảng → migration

Bảng còn sống (tạo bằng `CREATE TABLE`, chưa `DROP`). Đổi lược đồ = migration MỚI.

| Bảng | Tạo ở migration | Số migration sửa sau |
|---|---|---|
| `agent_cau_hinh` | `20261009860000_agent_giam_sat.sql` | 0 |
| `agent_nhan_dinh` | `20261009860000_agent_giam_sat.sql` | 0 |
| `agent_tom_tat` | `20261009870000_llm_chi_phi.sql` | 0 |
| `anh_chuyen_khoan` | `20261002300000_thu_nhieu_hinh_thuc.sql` | 0 |
| `app_credential` | `20260806000002_app_credential.sql` | 1 |
| `appointment` | `20260714000001_baseline_schema.sql` | 9 |
| `appointment_doi_lich` | `20260924000004_ket_qua_chuong_doi_lich.sql` | 0 |
| `block_budget` | `20260714000001_baseline_schema.sql` | 0 |
| `booking_channel` | `20260714000001_baseline_schema.sql` | 1 |
| `canh_bao` | `20260927000004_loi_va_canh_bao.sql` | 0 |
| `capability` | `20260923000003_capability.sql` | 0 |
| `capability_grant` | `20260923000003_capability.sql` | 2 |
| `care_episode` | `20260714000001_baseline_schema.sql` | 0 |
| `chot_so_ca` | `20261014149000_chot_so_ca.sql` | 0 |
| `clinic` | `20260730000003_multi_tenant_foundation.sql` | 2 |
| `clinic_location` | `20260714000001_baseline_schema.sql` | 4 |
| `clinic_membership` | `20260730000003_multi_tenant_foundation.sql` | 4 |
| `clinic_room` | `20260804000001_dispatch_rooms.sql` | 4 |
| `clinic_room_node` | `20260804000013_room_serves_many_nodes.sql` | 1 |
| `clinic_room_service` | `20261001210000_phong_lam_theo_dich_vu.sql` | 0 |
| `clinic_secret` | `20260805000005_clinic_secret.sql` | 0 |
| `clinical_data_consent` | `20260804000020_patient_link_consent.sql` | 1 |
| `clinical_form_approval` | `20260804000019_andrology_catalogue.sql` | 0 |
| `clinical_form_catalogue` | `20260730000011_clinical_form_catalogue.sql` | 0 |
| `clinical_form_response` | `20260714000001_baseline_schema.sql` | 0 |
| `clinical_record` | `20260714000001_baseline_schema.sql` | 1 |
| `clinical_release` | `20260804000007_clinical_sign_release.sql` | 0 |
| `command_receipt` | `20260911000001_luot_kham_lat_1.sql` | 0 |
| `cong_no` | `20261002500000_cong_no.sql` | 0 |
| `consultation` | `20260911000001_luot_kham_lat_1.sql` | 1 |
| `consultation_note` | `20260911000001_luot_kham_lat_1.sql` | 1 |
| `cskh_action` | `20260714000001_baseline_schema.sql` | 0 |
| `cskh_log` | `20260714000001_baseline_schema.sql` | 1 |
| `danh_muc_dich_vu_nguon` | `20261002100000_danh_muc_dich_vu_chuan_0110.sql` | 0 |
| `day_nghiep_vu` | `20260924000005_day_nghiep_vu_nhac_viec.sql` | 0 |
| `day_nhan_thong_bao` | `20260924000004_ket_qua_chuong_doi_lich.sql` | 0 |
| `dich_vu_mau_ket_qua` | `20260923000004_mau_ket_qua.sql` | 3 |
| `dispatch_threshold` | `20260804000002_dispatch_routes.sql` | 0 |
| `doctor_booking_override` | `20260803000002_booking_override.sql` | 1 |
| `doi_tac_nhan_viec` | `20260925000009_doi_tac_nhan_viec.sql` | 3 |
| `doi_tac_thanh_toan` | `20260928000091_doi_tac_tu_thu_tien.sql` | 0 |
| `domain_event` | `20260923000001_domain_event.sql` | 1 |
| `drug_batch` | `20260802000001_pharmacy_inventory.sql` | 5 |
| `drug_catalog` | `20260714000001_baseline_schema.sql` | 5 |
| `drug_ma_vach` | `20261014135000_ma_vach.sql` | 0 |
| `drug_return` | `20260919000004_tien_thuoc_cp5_hoan_tra.sql` | 2 |
| `du_lieu_da_xoa` | `20261001240000_don_du_lieu_thu.sql` | 0 |
| `encounter_flow` | `20260911000001_luot_kham_lat_1.sql` | 4 |
| `event_delivery` | `20260923000001_domain_event.sql` | 1 |
| `event_log` | `20260714000001_baseline_schema.sql` | 0 |
| `follow_up_case` | `20260730000005_workflow_kernel.sql` | 1 |
| `form_definition` | `20260923000005_form_engine.sql` | 0 |
| `form_instance` | `20260923000005_form_engine.sql` | 3 |
| `form_instance_lich_su` | `20261007630000_form_instance_lich_su.sql` | 0 |
| `form_result_release` | `20260923000014_sua_ket_qua_giu_ban_cu.sql` | 0 |
| `ghi_chu_khach` | `20260927000003_ghi_chu_khach.sql` | 0 |
| `hen_gio` | `20260923000008_hen_gio.sql` | 1 |
| `hen_goi_lai` | `20260809000005_trang_thai_cskh_suy_ra.sql` | 1 |
| `hoa_don_cong_ty` | `20261014156000_hoa_don_cong_ty.sql` | 0 |
| `hoa_don_cong_ty_lich_su` | `20261014156000_hoa_don_cong_ty.sql` | 0 |
| `hoa_don_misa_xuat` | `20261014157000_hoa_don_misa_xuat.sql` | 0 |
| `hoa_don_misa_xuat_dong` | `20261014157000_hoa_don_misa_xuat.sql` | 0 |
| `idempotency_key` | `20260714000003_idempotency_key.sql` | 2 |
| `inventory_txn` | `20260802000001_pharmacy_inventory.sql` | 4 |
| `ket_qua_mau` | `20260923000004_mau_ket_qua.sql` | 0 |
| `khach_cong_ty` | `20261014156000_hoa_don_cong_ty.sql` | 0 |
| `kiem_ke_ca` | `20261014170000_kiem_ke_ca.sql` | 0 |
| `kiem_ke_ca_dong` | `20261014170000_kiem_ke_ca.sql` | 0 |
| `ky_nang` | `20260928000093_ky_nang.sql` | 0 |
| `lab_result` | `20260714000001_baseline_schema.sql` | 0 |
| `lam_them_tai_quay` | `20261002200000_lam_them_tai_quay.sql` | 0 |
| `lam_them_tai_quay_revision` | `20261002220000_lam_them_tai_quay_revision.sql` | 0 |
| `lan_don_du_lieu_thu` | `20261001240000_don_du_lieu_thu.sql` | 0 |
| `lich_truc_anh` | `20261006300000_lich_truc_phien_ban.sql` | 0 |
| `lich_truc_thay_doi` | `20261006300000_lich_truc_phien_ban.sql` | 0 |
| `lieu_trinh` | `20261008100000_lieu_trinh.sql` | 0 |
| `lieu_trinh_buoi` | `20261008100000_lieu_trinh.sql` | 0 |
| `lieu_trinh_lich_su` | `20261008100000_lieu_trinh.sql` | 0 |
| `lieu_trinh_tra_truoc` | `20261008110000_lieu_trinh_tien.sql` | 0 |
| `llm_lan_goi` | `20261009870000_llm_chi_phi.sql` | 0 |
| `loai_kham_phi` | `20260928000100_phi_kham_theo_kiotviet.sql` | 0 |
| `loi_nhom` | `20260927000004_loi_va_canh_bao.sql` | 0 |
| `luat_bac_si_bat_buoc` | `20260808000003_luat_bac_si_bat_buoc.sql` | 0 |
| `luat_cskh` | `20260809000005_trang_thai_cskh_suy_ra.sql` | 0 |
| `luot_dong_thoi_gian` | `20260923000002_projection_dong_thoi_gian.sql` | 2 |
| `luot_ghi_chu` | `20261007640000_luot_ghi_chu.sql` | 0 |
| `luot_phi_kham` | `20260928000100_phi_kham_theo_kiotviet.sql` | 0 |
| `luot_phu_thu` | `20260928000099_phu_thu_kem_dich_vu.sql` | 0 |
| `luot_vat_tu` | `20261003000000_vat_tu_ban_them.sql` | 2 |
| `mpi_merge_queue` | `20260714000001_baseline_schema.sql` | 0 |
| `ngoai_le_ca_truc` | `20261002600000_ca_truc_lam_sang.sql` | 0 |
| `nhac_tai_kham` | `20260807000005_nhac_tai_kham_hai_luot_goi.sql` | 2 |
| `nhac_viec_ca_nhan` | `20260924000005_day_nghiep_vu_nhac_viec.sql` | 0 |
| `nhan_su_ky_nang` | `20260928000093_ky_nang.sql` | 0 |
| `node_definition` | `20260730000005_workflow_kernel.sql` | 2 |
| `node_definition_version` | `20260730000005_workflow_kernel.sql` | 0 |
| `node_dependency` | `20260730000005_workflow_kernel.sql` | 0 |
| `owner_feedback` | `20260801000004_owner_feedback.sql` | 0 |
| `patient` | `20260714000001_baseline_schema.sql` | 6 |
| `patient_contact_channel` | `20260801000003_adopt_prod_only_tables.sql` | 0 |
| `patient_link` | `20260804000020_patient_link_consent.sql` | 0 |
| `patient_medical_profile` | `20260714000001_baseline_schema.sql` | 0 |
| `patient_next_of_kin` | `20260801000003_adopt_prod_only_tables.sql` | 0 |
| `patient_sdt_them` | `20260815000002_nhieu_so_dien_thoai.sql` | 0 |
| `payment` | `20260714000001_baseline_schema.sql` | 5 |
| `payment_bill_line` | `20260919000001_tien_thuoc_cp1_hoa_don.sql` | 8 |
| `payment_cycle` | `20260919000002_tien_thuoc_cp2_payment_cycle.sql` | 5 |
| `payment_cycle_doi_hinh_thuc` | `20260930500000_doi_hinh_thuc_thu.sql` | 1 |
| `payment_cycle_phan` | `20261002300000_thu_nhieu_hinh_thuc.sql` | 0 |
| `payment_refund` | `20260919000004_tien_thuoc_cp5_hoan_tra.sql` | 0 |
| `payment_refund_line` | `20260919000004_tien_thuoc_cp5_hoan_tra.sql` | 0 |
| `phan_hoi_khach` | `20260809000007_hanh_trinh_cskh_bam_duoc_het.sql` | 0 |
| `phieu_kham_lich_su` | `20260925000018_phieu_kham_lich_su.sql` | 0 |
| `phieu_kham_luot` | `20260924000008_phieu_kham_luot.sql` | 0 |
| `phieu_kho` | `20260929960000_kho_kieu_kiotviet.sql` | 2 |
| `phieu_kho_dong` | `20260929960000_kho_kieu_kiotviet.sql` | 2 |
| `phu_thu_mau` | `20260928000099_phu_thu_kem_dich_vu.sql` | 0 |
| `pos_outbox` | `20260730000007_pos_outbox.sql` | 0 |
| `pregnancy` | `20260714000001_baseline_schema.sql` | 1 |
| `prescription` | `20260714000001_baseline_schema.sql` | 9 |
| `prescription_allocation` | `20260919000003_tien_thuoc_cp3_phan_lo_ban.sql` | 1 |
| `prescription_correction` | `20260920000002_tien_thuoc_cp6_dinh_chinh_don.sql` | 0 |
| `province` | `20260714000001_baseline_schema.sql` | 0 |
| `queue_entry` | `20260911000001_luot_kham_lat_1.sql` | 2 |
| `quyen_preset` | `20260923000011_nhom_quyen_mau.sql` | 0 |
| `result_correction` | `20260923000014_sua_ket_qua_giu_ban_cu.sql` | 0 |
| `review_round` | `20260911000001_luot_kham_lat_1.sql` | 0 |
| `roster_week` | `20260808000001_tuan_lich_truc_da_ap_dung.sql` | 0 |
| `round_requirement` | `20260911000001_luot_kham_lat_1.sql` | 1 |
| `route_template` | `20260804000002_dispatch_routes.sql` | 1 |
| `schema_migrations` | `20260714000001_baseline_schema.sql` | 0 |
| `semen_reference_range` | `20260804000019_andrology_catalogue.sql` | 0 |
| `service_execution_attempt` | `20260922000001_service_lifecycle_v1_schema.sql` | 6 |
| `service_log` | `20260714000001_baseline_schema.sql` | 0 |
| `service_order` | `20260911000001_luot_kham_lat_1.sql` | 16 |
| `service_order_draft` | `20260915000008_service_order_draft.sql` | 0 |
| `service_price` | `20260714000001_baseline_schema.sql` | 10 |
| `service_selection_state` | `20260922000001_service_lifecycle_v1_schema.sql` | 0 |
| `service_type` | `20260714000001_baseline_schema.sql` | 6 |
| `slot_booking_override` | `20260803000002_booking_override.sql` | 1 |
| `slot_hold` | `20260804000008_slot_hold.sql` | 0 |
| `so_no` | `20261014140000_so_no_hai_chieu.sql` | 1 |
| `so_no_moc` | `20261014140000_so_no_hai_chieu.sql` | 0 |
| `so_sua_chi_dinh` | `20261006200000_so_sua_chi_dinh.sql` | 0 |
| `staff` | `20260714000001_baseline_schema.sql` | 6 |
| `staff_capability` | `20260714000001_baseline_schema.sql` | 0 |
| `staff_node` | `20260804000018_staff_node.sql` | 0 |
| `staff_task` | `20260714000001_baseline_schema.sql` | 1 |
| `staff_vi_tri` | `20260916000008_vi_tri_lam_viec_kim_nguu.sql` | 0 |
| `tep_ket_qua` | `20260809000008_tep_ket_qua.sql` | 8 |
| `thong_bao` | `20260807000006_thong_bao_goi_bo_phan.sql` | 1 |
| `thu_ky_bac_si` | `20260915000020_thu_ky_bac_si.sql` | 0 |
| `thue_suat_nhom` | `20261014155000_thue_gtgt.sql` | 0 |
| `thuoc_giao_chua_gan_lo` | `20260928000096_thuoc_giao_chua_gan_lo.sql` | 0 |
| `thuoc_quy_doi` | `20261017100000_thuoc_quy_doi.sql` | 0 |
| `tien_thua_giu_lai` | `20261006200003_tien_thua_xu_ly_va_chan_thu_dong_huy.sql` | 0 |
| `tuong_tac_cskh` | `20260809000003_so_tuong_tac_cskh.sql` | 6 |
| `ultrasound_record` | `20260714000001_baseline_schema.sql` | 3 |
| `vai_duoc_vao_tram` | `20260809000002_vai_duoc_vao_tram.sql` | 0 |
| `vat_tu_goi_y` | `20261003000000_vat_tu_ban_them.sql` | 0 |
| `vat_tu_nhap_cho_duyet` | `20261014200100_vat_tu_nhap_cho_duyet.sql` | 0 |
| `vat_tu_phieu` | `20261014180000_vat_tu_so_kho.sql` | 0 |
| `vat_tu_ton` | `20261014180000_vat_tu_so_kho.sql` | 1 |
| `vat_tu_txn` | `20261014180000_vat_tu_so_kho.sql` | 0 |
| `vi_tri_dong_ca` | `20260916000011_vi_tri_dong_ca.sql` | 0 |
| `vi_tri_lam_viec` | `20260916000008_vi_tri_lam_viec_kim_nguu.sql` | 4 |
| `visit` | `20260714000001_baseline_schema.sql` | 11 |
| `visit_amendment` | `20260801000003_adopt_prod_only_tables.sql` | 1 |
| `visit_gate_override` | `20260804000014_gate_rule.sql` | 0 |
| `visit_gate_rule` | `20260804000014_gate_rule.sql` | 2 |
| `visit_route` | `20260804000002_dispatch_routes.sql` | 1 |
| `vital_measurement` | `20260911000001_luot_kham_lat_1.sql` | 1 |
| `ward` | `20260714000001_baseline_schema.sql` | 0 |
| `work_item` | `20260730000005_workflow_kernel.sql` | 6 |
| `work_item_dependency` | `20260730000005_workflow_kernel.sql` | 0 |
| `work_item_event` | `20260730000005_workflow_kernel.sql` | 0 |
| `work_pack` | `20260923000003_capability.sql` | 0 |
| `work_roster` | `20260714000001_baseline_schema.sql` | 2 |
| `work_roster_thay_nguoi` | `20260929000001_doi_nguoi_trong_ca.sql` | 0 |
| `work_session` | `20260714000001_baseline_schema.sql` | 0 |
| `work_session_staff` | `20260714000001_baseline_schema.sql` | 0 |
