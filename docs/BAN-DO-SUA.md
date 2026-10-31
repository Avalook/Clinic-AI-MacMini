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
Chặn trừ sai tồn: kiểm kho lệch khi thuốc còn "đã giao chưa gắn lô" (`kiem_kho`), huỷ lấn phần đã bán chưa giao
(`pharmacy_service._ghi_kho_don_gian`, `lo_thuoc_service.huy_lo`) — test `T/services/test_kho_chan_tru_sai_ton_db.py`.

**Nhiều đơn vị bán + giá theo đơn vị (Tuyền 31/10/2026)** — trên màn `/pharmacy/inventory` tab Danh mục → Sửa →
"Đơn vị bán thêm" (đơn vị, hệ số về đơn vị gốc, giá; giá trống máy lưu rõ hệ số × giá gốc; "Tắt bán" thay cho xoá).
Đơn vị gốc = `drug_catalog.don_vi_ban`, giá gốc = `unit_price`, không đổi nghĩa; đơn vị thêm ở `thuoc_quy_doi` (`gia`,
`dang_ban`, migration `20261101200000`). Số trên dòng đơn / hoá đơn / hoàn tiền theo ĐƠN VỊ ĐÃ BÁN, số ở lô theo ĐƠN VỊ
LÔ; chỉ chỗ chạm tới cả hai mới đổi. Luật ở MỘT tệp `S/don_vi_thuoc.py` (`BangDonVi` nhận diện đơn vị + giá,
`QuyDoiDong` đổi dòng ↔ lô, `cau_thieu_quy_doi` câu báo). Hệ số lúc thu nằm ở `payment_bill_line.he_so` (đã thu thì sửa
danh mục không đổi gì), khách trả ghi thêm `drug_return.so_luong_ban`. Quầy đổi đơn vị: `QuayThuocService.doi_don_vi`,
`D/thu-ngan/ChinhDonQuay.tsx`. Ô đơn vị mọi màn: `D/ODonVi.tsx` (SearchSelect `choGoTu`). Form: `D/pharmacy/inventory/SuaDonViBan.tsx`,
`S/pharmacy_service.py` `luu_thuoc`. Test: `T/services/test_nhieu_don_vi_ban_db.py`, FT `nhieu-don-vi-ban-boundary.test.mts`.

**Theo dõi thuốc: đang ở đâu + dòng thời gian (Tuyền 31/10/2026)** — tab "Theo dõi thuốc" ở `/pharmacy/inventory`,
`D/pharmacy/inventory/TheoDoiThuoc.tsx` → `/api/pharmacy/theo-doi-thuoc` (+ `tim-theo-doi`, `theo-doi-thuoc-xlsx`) →
`S/theo_doi_thuoc_service.py`. Chỉ đọc, chỉ cơ sở đang làm. **Tên hành động + từ đâu → đến đâu: chỉ sửa bảng `HANH_DONG` /
`_TU_DEN` đầu tệp** (loại dòng sổ mới tự hiện, chưa khai thì ra "Thay đổi kho khác"). Hai loại việc không có dòng sổ
(giao chưa gán lô, nhập lại bán được) và gộp hai dòng chuyển kho nằm trong câu `_SU_KIEN`. Excel: `excel_export.xlsx_theo_doi_thuoc`.
Test: `T/services/test_theo_doi_thuoc_db.py`, `D/tests/theo-doi-thuoc-boundary.test.mts`.

**Giao thuốc: máy tự chọn lô, trừ kho ngay lúc giao (Tuyền 27/10/2026)** — bấm "Giao thuốc" không chỉ định lô thì
`S/pharmacy_service.py` `cap_phat` → `_giao_tu_chon_lo`: lô QUẦY đúng thuốc, đúng cơ sở của lượt, cùng đơn vị hoặc đổi được qua hệ số, còn hạn, xếp hạn
sớm nhất trước (không hạn xếp cuối), trừ theo `drug_batch_kha_dung` và trừ thêm các lần giao đang chờ gán lô; một lần giao có thể trừ
hai lô. Thiếu lô / thiếu tồn → phần còn lại VẪN giao, ghi `thuoc_giao_chua_gan_lo` (màn "Đã giao, chưa trừ kho" = hàng đợi
ngoại lệ, `gan_lo_da_giao`). Kết quả trả `lo_da_tru`, `chua_tru_kho`, `tom_tat` — màn `D/pharmacy/DongThuoc.tsx` chỉ hiện câu ấy.
Giao kèm `drug_batch_id` (quét lô, lô đã bán theo phân lô) vẫn đi đường cũ. Test: `T/services/test_giao_tu_chon_lo_db.py`
(FEFO, tách hai lô, thiếu tồn, hai lần giao cùng lúc), bài bấm ngẫu nhiên R6/R7 ở `test_mo_phong_kho_day_du_db.py`,
FT `giao-tu-chon-lo-boundary.test.mts`.

**Mã vạch thuốc: quét hộp / tem lô, gắn mã, in tem (G3b)** — ô quét `D/pharmacy/inventory/OQuetMa.tsx`
(máy quét USB = gõ nhanh + Enter; camera `CameraQuet.tsx` chỉ HTTPS) ở Phiếu nhập, Nhập lô, Kiểm kho
và quầy `/pharmacy` (`PharmacyBoard.tsx` điền sẵn lô cho `DongThuoc.tsx`). Máy chủ: `S/ma_vach_service.py`
(`tra_ma`, `gan_ma`, `go_ma`, `du_lieu_tem`), tách mã vuông GS1 `clinicai/core/gs1.py`, bảng `drug_ma_vach` +
cột `drug_batch.ma_tem` (migration `20261014135000`). Trang in tem `D/print/tem-lo/` (Code 128 tự vẽ
`D/lib/ma-vach.ts`). Test: `T/services/test_ma_vach_db.py`, `T/unit/test_gs1.py`, `D/tests/ma-vach-boundary.test.mts`.

**Tách KHO / QUẦY trong một cơ sở (G7)** — công tắc theo cơ sở `clinic_location.tach_kho_quay` (mặc định TẮT =
một kho như cũ). Mỗi lô tối đa hai hàng `drug_batch` (`noi_chua` KHO / QUAY, cùng số lô + mã tem); nhập đi vào KHO,
bán / giao / nhận trả CHỈ ở QUẦY (trigger `gac_ban_tu_quay` + kiểm ở `pharmacy_service._kiem_lo`,
`gan_lo_da_giao`, `_cap_phat_cu`), phiếu chuyển `S/kho_thuoc_service.py` (`chuyen_kho`, `hoan_tac_chuyen`,
`dat_tach_kho_quay`) — migration `20261014160000`. Quầy hết mà kho còn: `ban_thuoc_service` trả `kho_con` cho từng
dòng đơn. Test: `T/services/test_kho_quay_db.py` (bấm ngẫu nhiên 40×10).
Giao diện: tab "Chuyển kho ↔ quầy" trong khu KHO `D/pharmacy/inventory/ChuyenKho.tsx` (31/10 gắn lại; hiện khi cơ sở đã
tách hoặc người có `config.clinic.manage` — công tắc nằm trong tab; Quầy → Kho bắt lý do). Quầy hết mà kho còn: VẪN giao, phần thiếu vào
"Đã giao, chưa trừ kho", gán lô từ KHO hoặc QUẦY. Chip KHO/QUẦY ở `InventoryBoard.tsx` (prop `tachKhoQuay`), nút "Kho còn N — chuyển sang quầy?" ở dòng đơn
`D/pharmacy/KhoConChuyenQuay.tsx` (gắn trong `DongThuoc.tsx`); proxy `chuyen-kho` / `hoan-tac-chuyen-kho` /
`tach-kho-quay` ở `D/app/api/pharmacy/[action]/route.ts`. Test: `D/tests/kho-quay-giao-dien-boundary.test.mts`.

**Kiểm kê đầu / cuối ca ở QUẦY + cột tồn của "Báo cáo hàng hoá" (G6)** — phiếu `kiem_ke_ca` (+ `_dong`),
migration `20261014170000`, `20261101100000`: NHÁP → CHỐT, đầu/cuối ca một phiếu mỗi ca (UNIQUE từng phần ở Postgres), đột
xuất nhiều phiếu, kiểm một phần tự nhận ra. Từ 31/10 CHỐT là số thật: dòng lệch bắt lý do riêng, ghi `ADJUST` ngay
(`ref_type 'kiem_ke_ca'`), hoàn tác bằng ADJUST ngược. Lệch tính TẠI LÚC ĐẾM (`dem_luc` từng dòng, `phat_sinh_sau_dem`):
lệch = đếm + N (đã giao chưa gắn lô) − sổ lúc đếm; phiếu ngày trước so với sổ cuối ca ấy (`moc_dem`). Phần không áp được
nằm ở `chua_ap` + `chua_ap_ly_do`, không báo đã khớp. "Điều chỉnh theo kiểm kê" chỉ còn cho phiếu cũ chưa ghi sổ.
Service `S/kiem_ke_ca_service.py` (`mo_phieu`, `luu_dem`, `dung_so_cuoi_ca_truoc`, `chot`, `dieu_chinh_theo_kiem_ke`,
`hoan_tac_dieu_chinh`, `nhac_thieu_kiem`; thuần: `khung_moc`, `tinh_xnt_dong`, `ghep_ton_ca`), 9 route `/pharmacy/kiem-ke-ca…`
ở `S/../routers/pharmacy.py`. Báo cáo: MỘT chỗ gắn ở `bao_cao_cuoi_ngay_service.py` (`ghep_vao_bao_cao` sau
`gom_hang_hoa`) thêm khối `kho` vào mỗi dòng thuốc — số thu cũ (SL bán theo thu, doanh thu) KHÔNG đổi; `kho.theo_don_vi[]`
= Tồn đầu · Nhập · SL bán (= số GIAO) · SL trả · khác · Tồn cuối · Kiểm kê · Lệch · đã thu chưa giao. Chuông lệch:
sự kiện `pharmacy.stocktake_mismatch` → `chuong.py` (người nhận ở `day_nhan_thong_bao`, quản lý chỉnh).
Test: `T/services/test_kiem_ke_ca_db.py` (bấm ngẫu nhiên 40×10), `T/unit/test_xnt_theo_ca.py`.
Giao diện: tab "Kiểm đầu/cuối ca" ở Kho thuốc `D/pharmacy/inventory/KiemKeCa.tsx` (đếm mù → [Chốt kiểm kê] hiện dòng lệch + ô lý do trong `XacNhanTaiCho` → hoàn tác,
nhắc thiếu kiểm); proxy `D/app/api/pharmacy/kiem-ke-ca/**` (danh sách trắng bước ghi); cột tồn ở `/reports?tab=hang-hoa`
→ `D/reports/BangHangHoa.tsx` (`BangCoTon`, chỉ khi máy chủ trả `co_ton`; bản in = `window.print()`, Excel/CSV chưa có cột tồn).
FT: `D/tests/kiem-ke-ca-boundary.test.mts`.

**Lệch kiểm kê ở Báo cáo kho + quản lý sửa số sau cùng (31/10)** — khối dưới bảng XNT `D/pharmacy/inventory/LechKiemKe.tsx` →
`/pharmacy/lech-kiem-ke`, `.xlsx`, `/pharmacy/sua-so-kiem-ke` (`report.view` hoặc `config.clinic.manage`) → `S/lech_kiem_ke_service.py`
(`ds_lech`, `sua_so_sau_cung`); bảng chỉ thêm `kiem_ke_sua_so`, ADJUST `ref_type 'kiem_ke_sua'`. Kiểm đếm kho: `kho_thuoc_service.kiem_kho`
(lý do từng dòng, N chỉ tách ở hàng QUẦY — `tach_cho_gan_lo`), `hoan_tac_kiem_kho`, tab `KiemKho.tsx` + `DanhSachPhieu.tsx`.
Test: `T/services/test_kho_quay_that_db.py`, FT `D/tests/kho-quay-that-boundary.test.mts`.

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
vấn / đi thẳng phòng · chuông sự kiện báo ai · dừng liệu trình tính giá gói hay
phá gói tính giá lẻ**
- Dừng liệu trình (`lieu_trinh_dung_tinh_gia_le`, 30/10/2026): lệnh dừng chụp
  chính sách vào `lieu_trinh.chinh_sach_dung` — đổi dây chỉ áp cho lần dừng sau.
  Tính + câu cho thu ngân: `S/lieu_trinh_tien.py` `quyet_toan_dung`,
  `gan_quyet_toan`. Test: `T/services/test_lieu_trinh_chinh_sach_dung_db.py`.
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
**[Không đo] + lý do (30/10/2026)** — nút cạnh [Đo xong] → chip lý do (danh sách
`S/luot_kham_rules.py::LY_DO_KHONG_DO`, trả ở `ly_do_khong_do` của bảng) →
`SinhHieuService.khong_do` (`POST /luot-kham/visits/{id}/vitals/khong-do`): ghi bảng
`sinh_hieu_khong_do` (migration 20261031130000; không số giả), luồng `recorded`, phát
`vitals.recorded` có cờ `khong_do` (Hành trình xếp đi tiếp). Câu "Không đo · <lý do>":
`rules.nhan_khong_do`, đọc ở `S/sinh_hieu_buoi.py::khong_do_cua_luot` → `luot_kham_doc`
(`khong_do`) và `phieu_kham/mang_sang.py` (`sinh_hieu_khong_do`) — chỉ khi chưa có số đo
(lần đo thật thắng). Test `T/services/test_sinh_hieu_khong_do_db.py`.

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

**Đơn thuốc điền tiếp ở bàn tư vấn (13/10/2026)** — MỘT đơn cho cả lượt: bác sĩ chính
điền dở / vội thì bác sĩ tư vấn điền tiếp đúng đơn đó, không có đơn thứ hai. UI:
`D/ban-kham/KhoiDonThuocBanTuVan.tsx` (công tắc "Đơn thuốc" = mục E của phiếu lượt,
`PhieuKhamLuot chiMuc=["E"]`, nút In đơn thuốc) trong `BanTuVan.tsx`; khách đã khám xong
không qua tư vấn: nhóm "Đã khám xong — điền đơn thuốc" ở `BanKham.tsx` → `BanDienDonThuoc.tsx`
(hàng chung: `S/luot_kham_doc.py` `hang_cho`, nhánh `tu_van`). Máy chủ:
`S/phieu_kham_service.py` `luu_don_thuoc` — người có lego Tư vấn không đi kèm bác sĩ chính hôm
nay vẫn lưu được (cổng ca trực `kiem_dung_ca` dùng chung KHÔNG nới), sự kiện `prescription.saved`
mang `ke_tai_tu_van` và người bấm tự đứng tên (không `on_behalf_of`); `doc_don_thuoc` trả
`nguoi_ke` / `nguoi_ke_la_bac_si`. Hành trình: mốc `KE_DON_TU_VAN` ở `phieu_kham/hanh_trinh.py`.
Phiếu in: `app/print/phieu-kham/[visitId]/InPhieuKham.tsx` + `nguoiKeDon` ở `lib/phieu-kham.ts`
(đơn in riêng `?phan=don` ký bác sĩ ghi dòng mới nhất; TKYK nhập hộ chỉ là "Người nhập").
Nút [Xong kê đơn thuốc] / [Mở lại] (mốc, không khoá đơn): `BanDienDonThuoc.tsx` → `/api/phieu-kham`
`thao_tac=xong-ke-don` → `PUT /phieu-kham/luot/{visit}/ke-don-tu-van` → `PhieuKhamService.danh_dau_xong_ke_don`
(sự kiện `prescription.consultant_marked`; lần mới nhất quyết định; `hang_cho` trả `ke_don_tu_van_xong`).
Lỗi 409 cần lý do đính chính (dòng đã thu / bán / giao): proxy `lib/backend-proxy.ts` giữ mã ở `ma_loi`.
Test: `T/services/test_don_thuoc_ban_tu_van_1310_db.py`, `T/services/test_hanh_trinh_tu_van_db.py`,
`T/unit/test_hanh_trinh_moc.py`, FT `don-thuoc-ban-tu-van-boundary.test.mts`, `npm run test:phieu-kham`.

**Dịch vụ của lượt trong hồ sơ khám — đổi dịch vụ, phiếu cũ, lượt Điều trị (07/10/2026)**
— UI `D/_lam-viec/phieu-kham/KhoiDichVuHoSo.tsx` (đầu phiếu + hồ sơ tối giản ở
`PhieuKhamLuot.tsx` nhánh `chonDuoc`) → `/api/ho-so-kham` → `R/ho_so_kham.py` →
`S/ho_so_dich_vu.py` (`doc`, `doi` → `BookingService.doi_dich_vu_kham(trong_ho_so=True)`;
luật mở khoá `S/doi_dich_vu_kham.py` `ly_do_khong_doi(trong_ho_so=…)`, quyền
`QUYEN_DOI_TRONG_HO_SO`). Phiếu theo dịch vụ HIỆN TẠI: `S/phieu_kham_service.py` `doc_luot`.
Lượt Điều trị vào hàng → chỉ định sẵn: consumer `src/clinicai/events/consumers/dieu_tri.py`
(nghe `visit.routed`) → `sinh_chi_dinh_dieu_tri`; không phí khám `S/bill_service.py` `_kham`
(luật `khong_tu_cong_phi_kham`: Điều trị + Thủ thuật trừ lượt cũ qua TU_VAN, 09/10/2026);
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
`noi_lam = BAN_KHAM`; chỉ định chưa có phòng thì xếp vào phòng bàn khám, đã có phòng
khác thì CHUYỂN sang phòng bàn khám — phòng cũ ở `service_execution_attempt.phong_truoc_ban_kham`,
hoàn tác trả về (09/10/2026); cửa tiền `cua_tien_chot_ho` = cùng cửa với phòng). Kê lại dịch vụ điều trị đã có trong lượt
không đẻ dòng thứ hai: `S/chi_dinh_service.py` (`chi_dinh_dieu_tri_dang_co`). Test:
`T/services/test_dieu_tri_ban_kham_db.py`, `T/unit/test_dieu_tri_ban_kham.py`, FT
`khoi-dieu-tri-boundary.test.mts`. Lịch sử sửa MỌI phiếu kết quả: trigger
`trg_form_instance_lich_su` → bảng chỉ thêm `form_instance_lich_su` (migration
`20261007630000`; test `T/services/test_form_instance_lich_su_db.py`).

**Khối 1 theo loại lượt — lượt Điều trị / Thủ thuật (09/10/2026)** — luật thuần
`src/clinicai/phieu_kham/che_do.py` `che_do_khoi1(nhom, form_code)` → `DIEU_TRI` /
`THU_THUAT` / None; `S/phieu_kham_service.py` `doc_luot` trả `khoi1` (lượt Điều trị không
phiếu → mở khung TRUNG TÍNH "Hồ sơ điều trị" `HO_SO_DIEU_TRI` — `src/clinicai/phieu_kham/khung.py`,
`dinh_nghia/HO_SO_DIEU_TRI.json`, mig `20261009600000`; ngoài `FORM_IDS`, không A/B; dòng phiếu chỉ sinh
khi bác sĩ ghi — không bao giờ mở phiếu THU_THUAT cho lượt Điều trị). Thẻ làm tại bàn khám:
`S/dieu_tri_ban_kham.py` `ma_ban_kham_sql` (điều trị ∪ thủ thuật `DICHVU-THUTHUAT` khi lượt
Thủ thuật) — `doc_the` (`khoi1`, `nhac_tick`), `thao_tac`, `chon_thu_thuat` (chỉ định +
Bắt đầu tại bàn khám; `/api/ho-so-kham` `thao_tac=chon-thu-thuat` →
`R/ho_so_kham.py` `/ho-so-kham/{visit}/dieu-tri/chon-thu-thuat`); cờ `ban_kham` mỗi chỉ
định ở `src/clinicai/phieu_kham/ket_qua_chi_dinh.py` (`dieu_tri` giữ cho bản in). Ô
"Làm trước – thu sau" tại chỗ CHỈ khi FinanceGate chặn vì chưa thu + chưa tick:
cờ `nhac_tick` = `S/service_execution_service.py` `chan_vi_chua_thu` (E1; cửa tiền
`cua_tien_chot_ho` trên `states_for_orders(gia_su_chon=True)`) ở `doc_the` và
`S/nhan_tai_phong.py` `_chi_dinh` (chỉ định ở khung phải phòng). Link "Mở bàn khám" ở
Sắp đến: `S/nhan_tai_phong.py` `mo_ban_kham`. Test: `T/unit/test_khoi1_theo_loai_luot.py`,
`T/services/test_khoi1_ban_kham_db.py`, `T/services/test_nhac_tick_phong_db.py`.
Giao diện: `PhieuKham.tsx` prop `oKhoi1` + `khoi1` (ẩn A/B lượt Điều trị — `mucAnKhoi1`),
`PhieuKhamLuot.tsx` dựng `oKhoi1` (thẻ `ban_kham` theo `phanChiDinh(…, khoi1).banKham`),
nút chọn `D/_lam-viec/phieu-kham/ChonThuThuatBanKham.tsx` (lọc `danhSachThuThuatBanKham`), ô
tick tại chỗ `D/_lam-viec/OLamTruocThuSau.tsx` `OTickTaiCho` (khối 1 qua `KhoiDieuTri` prop
`oTick`; khung phải `D/phong/[ma]/KhungChiDinhKhach.tsx`), link `D/phong/[ma]/SapDenPhong.tsx`.
FT `khoi-dieu-tri-boundary.test.mts`, `nhan-tai-phong-boundary.test.mts`, `lib/phieu-kham.test.mts`.

**Liệu trình MINH BẠCH (09/10/2026, Tuyền chốt):** mặc định mỗi chỉ định điều trị là
BUỔI LẺ; bác sĩ đề xuất lộ trình KHÔNG biến chỉ định hôm nay thành buổi 1 (`tao`
mặc định chỉ đề xuất; `khach_chon` = khách nhận luôn). Khách nhận = [Khách chọn lộ trình]
(lệnh `gan` vào liệu trình DE_XUAT → máy chủ ghi đăng ký; bỏ tick "tính buổi hôm nay" =
`dang-ky`) — `S/lieu_trinh_service.py` `_khach_chon`; hoàn tác đăng ký gỡ buổi gắn cùng lệnh.
Trigger tự gắn chỉ nhắm liệu trình ĐANG LÀM (mig `20261009145151_lieu_trinh_minh_bach.sql`).
SỐ BUỔI HIỆN = thứ tự làm xong, đọc qua view `v_lieu_trinh_buoi` (`buoi_so`, `da_lam`);
chữ "Buổi k/N · đã làm / chưa làm" = `S/nhan_luot.py` `chu_buoi` (nhãn lượt, chip, thẻ) và
`nhanBuoi` ở `D/lib/lieu-trinh*.ts` (quầy, phòng, in). Dải ở PHÒNG DỊCH VỤ: `D/_lam-viec/
phieu-kham/LieuTrinhChiDinh.tsx` (vẽ trong `D/phong/[ma]/PhongDichVu.tsx`, cùng `DaiLieuTrinh`),
quyền sửa theo cờ máy chủ `ghi_duoc`. Test: `T/services/test_lieu_trinh_db.py`
(`test_staging_0910_*`, `test_so_buoi_theo_thu_tu_lam_xong`), FT `lieu-trinh-boundary.test.mts`.

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

**Danh sách hoá đơn theo khách** — `/hoa-don` ngay dưới Báo cáo; `D/hoa-don/DanhSachHoaDon.tsx`
+ `ChiTietHoaDon.tsx` → `/api/hoa-don` → `S/danh_sach_hoa_don_service.py`.
Đọc phiếu đã thu và xử lý sau thanh toán (hoàn / hủy), gom dịch vụ + thuốc theo khách.
Giảm giá: số trước giảm / đã giảm / sau giảm, lý do / người / giờ theo snapshot phiếu;
dòng hiển thị phần giảm được phân bổ từ máy chủ. Miễn phí 100% có số thực thu 0 vẫn là phiếu đã thu,
không suy ra hoàn tiền từ số 0. Test FT `hoa-don-giam-gia-boundary.test.mts` + E2E fixture giảm 100%.
Số tổng giao dịch trong kỳ khác số toàn bộ phiếu liên quan của khách nếu hoàn khác ngày thu.
Tên phòng từng dòng dịch vụ (màn + cột "Phòng" sheet "Dòng phiếu" của Excel, 30/10/2026): đúng nguồn phiếu
thu in (`S/quay_thu_service.py` `_PHONG_CHI_DINH_SQL` + `_phong_cua_dong`), chữ do `S/hoa_don_projection.py::nhan_phong`
/ `gan_phong`; test `T/services/test_hoa_don_ten_phong_db.py`. Bản xuất MISA không có cột này (mẫu cố định).
Test `T/services/test_danh_sach_hoa_don_db.py`, `T/unit/test_danh_sach_hoa_don.py`,
FT `danh-sach-hoa-don-boundary.test.mts`, E2E `e2e/danh-sach-hoa-don.mjs` (API giả lập, auth DEMO thật).

**Xuất hoá đơn GTGT (mẫu MISA cho kế toán)** — `/xuat-hoa-don` ngay dưới Danh sách hoá đơn;
`D/xuat-hoa-don/XuatHoaDon.tsx` → `/api/xuat-hoa-don` → `GET /api/v1/hoa-don/xuat` (+ `/xlsx`)
→ `S/xuat_hoa_don_service.py` (`dung_hoa_don` thuần, `xlsx_misa` đổ vào tệp mẫu
`S/mau/hoa_don_gtgt_1_thue_suat.xlsx`, bỏ 8 dòng chữ hướng dẫn → tiêu đề dòng 1, dữ liệu dòng 2). Dùng lại `DanhSachHoaDonService.xem` (cùng cổng quyền).
Mỗi phiếu thu trong kỳ = 1 hoá đơn; bỏ phiếu huỷ; trừ dòng đã hoàn xong; ô chưa có dữ liệu để trống.
Đổi mẫu = thay tệp `.xlsx` đó (tiêu đề cột ở dòng `TIEU_DE_MAU` = 9). Test `T/unit/test_xuat_hoa_don.py`,
FT `xuat-hoa-don-boundary.test.mts`.
**Kế toán — lego #22 + Theo hàng hoá (G5a, 14/10)** — quyền KHÔNG theo vai: khối `ke_toan` /
quyền `accounting.finance.full` (`P/permissions/catalogue.py`: KHOI, QUYEN, `MAN["ke_toan"]`,
`PRESET["KE_TOAN"]` đặt SAU vòng mở-full, `KHOI_CHI_QUAN_LY` chứa `ke_toan` để nhân viên khác không
tự có) + migration `20261014150000_lego_ke_toan.sql`. Cổng tài chính: nhánh capability trong
`S/report_access_service.py::access()` (có quyền → xem mọi ca / cơ sở, không thành `quan_ly`).
Gói Kế toán KHÔNG có `thu_tien_dv`/`thu_tien_thuoc` → thu/hoàn/đổi hình thức bị `payment_service` /
`hoan_tien_service` chặn theo quyền. Thống kê: `D/ke-toan/KeToan.tsx` → `/api/theo-hang-hoa` →
`GET /api/v1/hoa-don/theo-hang-hoa` (+ `/xlsx`) → `S/theo_hang_hoa_service.py` (`gom_theo_hang_hoa` thuần)
dùng lại `XuatHoaDonService.xem`. Test `T/services/test_ke_toan_lego_db.py`, `test_theo_hang_hoa_db.py`,
`T/unit/test_theo_hang_hoa.py`, FT `ke-toan-boundary.test.mts`.

**Thuế GTGT cho kế toán (G5b, 14/10) — backend; màn đặt thuế = tab "Thuế suất" ở `/ke-toan` (C2)** — giá đã gồm thuế, tách ngược
khi xuất (K1); KHÔNG chạm vận hành (`T/unit/test_thue_khong_cham_van_hanh.py` khoá: chỉ `thue_suat_service`,
`xuat_hoa_don_service`, `thue_gtgt` biết cột thuế). Cột `service_price.thue_suat_ma`, `drug_catalog.thue_suat_ma`,
bảng `thue_suat_nhom` (migration `20261014155000_thue_gtgt.sql`, hàm `thue_suat_hop_le`); quyền đặt
`accounting.tax.manage`. Đặt: `S/thue_suat_service.py` ← `R/ke_toan.py` (`GET/PUT /ke-toan/thue-suat…`).
Xuất: `S/xuat_hoa_don_service.py::dung_hoa_don` gán thuế suất dòng (sửa tay > mặt hàng > nhóm) →
`S/thue_gtgt.py::ap_thue_hoa_don` (tách theo thuế suất `che_do=tach` | một hoá đơn `mot`; K2 `ghi_giam_gia`) →
`xlsx_misa` ghi K (thuế suất) / L (tiền thuế). Query `/hoa-don/xuat?che_do&ghi_giam_gia&ghi_de={"id dòng":"mã"}`.
Chưa đặt thuế → xuất y như cũ. Test `T/unit/test_thue_gtgt.py` (bảng số tay), `T/services/test_thue_gtgt_db.py`.
**Màn đặt thuế (C2):** `D/ke-toan/KeToan.tsx` (tab bar `ThanhTab`: Theo hàng hoá | Thuế suất) → `D/ke-toan/ThueSuat.tsx` (nhóm + tìm mặt hàng, hoàn tác) → `/api/ke-toan/thue-suat(/nhom/[nhom] | /mat-hang)` → `R/ke_toan.py`; nhãn thuế `D/ke-toan/thue-suat.ts` (`tenThueSuat`). FT `thue-suat-boundary.test.mts`.
**Điều khiển thuế ở màn xuất (C2):** `D/xuat-hoa-don/XuatHoaDon.tsx` (`cheDo`, `ghiGiamGia`, `ghiDe` → query `che_do`/`ghi_giam_gia`/`ghi_de`; `DongHangGon` có ô sửa thuế từng dòng) → `D/api/xuat-hoa-don/route.ts` (chuyển tiếp 3 tham số) → `R/hoa_don.py::xuat_hoa_don`. Danh sách mức dùng chung `D/ke-toan/thue-suat.ts::MUC_THUE`. FT `xuat-hoa-don-thue-boundary.test.mts`.

**Hoá đơn công ty (G5c, 14/10)** — khách lấy hoá đơn về công ty: tên + địa chỉ + MST (+ email nhận HĐ). Lưu THEO HOÁ ĐƠN
(`hoa_don_cong_ty`, bản chụp theo `payment_cycle`) và ghi vào HỒ SƠ khách (`khach_cong_ty`, nhiều công ty/khách, dùng gần nhất
đứng đầu = điền sẵn lần trước); sửa hồ sơ KHÔNG đổi bản chụp; sửa/bỏ bản chụp ghi `hoa_don_cong_ty_lich_su`; gỡ khỏi hồ sơ = ẩn
(`an_luc`), bỏ chọn = `bo_luc` (hoàn tác = ghi lại). Migration `20261014156000_hoa_don_cong_ty.sql`. Luật: `S/hoa_don_cong_ty_service.py`
(MST sai dạng chỉ NHẮC — `nhac_mst`, vẫn lưu; ghi rác 422, đọc rác → rỗng) ← `R/hoa_don_cong_ty.py` (`/hoa-don/cong-ty/khach/{id}`,
`/hoa-don/cong-ty/an/{id}`, `/hoa-don/cong-ty/phieu/{payment_cycle_id}` (+ `/lich-su`)). Cửa = một trong các quyền
`QUYEN_CONG_TY` (Lễ tân/CSKH/Thu ngân/Kế toán — lego, không vai). Xuất: `S/xuat_hoa_don_service.py::dung_hoa_don` — hoá đơn công ty
→ C=tên cty, D=địa chỉ cty, E=MST, F=người mua (trống nếu không điền), G=email cty, H/I trống (không SĐT/CCCD/địa chỉ/email cá nhân);
hoá đơn khác giữ nguyên. **Màn:** `D/hoa-don/CongTyHoaDon.tsx` (gắn vào từng phiếu ở `ChiTietHoaDon.tsx`) → `/api/hoa-don/cong-ty/phieu/[id]` (+ `/lich-su`); xem trước xuất hoá đơn (`D/xuat-hoa-don/XuatHoaDon.tsx::KhachHang`) hiện công ty thay cho khách cá nhân. Test `T/unit/test_hoa_don_cong_ty.py`, `T/services/test_hoa_don_cong_ty_db.py` (có bấm ngẫu nhiên 40×10), FT `hoa-don-cong-ty-boundary.test.mts`.
**Công ty trong hồ sơ khách (màn):** `D/CongTyKhach.tsx` (gắn trong `D/PatientAdminEditor.tsx`, chế độ xem) dùng chung `D/hoa-don/FormCongTy.tsx` với khối trên phiếu → `/api/hoa-don/cong-ty/khach/[id]` (GET/PUT) + `/api/hoa-don/cong-ty/an/[id]` (PUT). FT `cong-ty-khach-boundary.test.mts`.

**Đánh dấu "đã xuất sang MISA" + "có thay đổi sau khi xuất" (G5c, 14/10)** — kế toán tải Excel xong bấm đánh dấu khoảng ngày:
máy chủ DỰNG LẠI danh sách hoá đơn của khoảng (không tin danh sách từ trình duyệt), lưu mỗi hoá đơn một dòng
(`hoa_don_misa_xuat_dong`) cùng hai dấu vân tay (`S/hoa_don_misa_doc.py::dau_van_tay`: người mua/công ty và nội dung —
KHÔNG gồm thuế suất). Sau đó `/hoa-don/xuat` gắn `misa` cho từng hoá đơn (`S/hoa_don_misa_service.py::gan_trang_thai`:
đã xuất lúc nào, có đổi không, lý do) + `so_da_xuat_misa` / `so_co_thay_doi_sau_xuat`. Bỏ đánh dấu = `huy_luc`
(`PUT` khôi phục). Migration `20261014157000_hoa_don_misa_xuat.sql`. Router `R/hoa_don_misa.py`
(`/hoa-don/misa-xuat` GET/POST, `/{id}` GET chi tiết · DELETE bỏ · PUT khôi phục); quyền lego `accounting.finance.full`.
Ngày rác khi ghi → 422. **Màn:** `D/xuat-hoa-don/XuatHoaDon.tsx` (nút đánh dấu + chip `TrangThaiMisa` + banner tổng) và `D/xuat-hoa-don/LanXuatMisa.tsx` (các lần đã xuất, xem thay đổi, bỏ / khôi phục) → `/api/xuat-hoa-don/misa(/[id])`. Test `T/unit/test_hoa_don_misa.py`, `T/services/test_hoa_don_misa_db.py` (bấm ngẫu nhiên 20×10 khớp mô hình), FT `hoa-don-misa-boundary.test.mts`.

Nút thu dùng chung `NhomThu` ở 2 quầy và Bán lẻ đổi thành **Tạo bill**; tiền mặt vẫn ghi thu,
chuyển khoản vẫn chờ xác minh, nút xác minh **Đã nhận tiền** giữ nguyên.

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

**Đầu dò Bio chọn ở CHỈ ĐỊNH CLS (14/10/2026, G9 — Notion recap 12/10 mục 3: "hiện bổ sung trong Chỉ định CLS thay vì ở bước thanh toán")** —
bác sĩ chọn "Bio 1 lần / nhiều lần" ngay ở thẻ chỉ định: màn `D/_lam-viec/phieu-kham/DauDoChiDinh.tsx` (gắn trong
`KetQuaChiDinh.tsx` qua prop `dauDoLuot`) → `S/bio_chi_dinh_service.py` (`BioChiDinhService.doc` / `chon`; quyền
`clinical.order.place`; chọn = ĐẶT, radio, không cộng dồn; đã thu → khoá). Dòng bán vẫn là `luot_vat_tu` nhưng có
`order_id` (migration 20261014190000; dòng cũ NULL, không di chuyển). **Tiền đi theo chỉ định, suy từ trạng thái chỉ
định lúc đọc** (không chép sang dòng Bio): `S/bill_service.py` `_VAT_TU_THEO_CHI_DINH` (hoá đơn còn nợ), nợ khi check-out
chỉ khi chỉ định đã làm `S/cong_no_service.py` `loc_no_dich_vu`, màn quầy `S/vat_tu_service.py` `_DONG_SQL` (`tinh_tien`).
Quầy bỏ dòng đi kèm chỉ định bắt ghi lý do (`VatTuService.bo(ly_do=)`, cột `bo_ly_do`); bỏ chỉ định đã thu Bio →
`HoanTacService.huy_chi_dinh` nhắc khoản Bio (không tự thành tiền thừa); hoàn tác bỏ chỉ định sau hoàn tiền (chỉ định
MỚI) → Bio chưa thu đi theo (`so_sua_chi_dinh_service._chi_dinh_moi_thay` → `chuyen_bio_chua_thu`).
Test: `T/services/test_bio_chi_dinh_db.py` (bất biến B1–B5 + bấm ngẫu nhiên 40×10 có bên nhận sự kiện xen giữa),
FT `dau-do-chi-dinh-boundary.test.mts`. Luật duyệt trigger `luot_vat_tu_gac` KHÔNG đổi ở G9.

**Bán vật tư trừ kho đúng phòng + danh sách đối soát (31/10/2026)** — mọi đường bán đi qua MỘT hàm `S/vat_tu_ban_service.py`
`dong_bo_ban_vat_tu` (so số phải trừ với số đang trừ, gọi lại không đổi gì; bảng `vat_tu_ban`, phiếu `BAN`/`HOAN`, migration 20261101300000).
Luật: trừ khi có lần thu giữ phủ (đã thu HOẶC chuyển khoản chờ xác minh, thu 0đ vẫn trừ) hoặc dịch vụ đã bắt đầu làm mà chưa thu; hoàn tác lần
thu / huỷ lần chờ → số về, TRỪ dịch vụ đã làm (hàng đã dùng, khách thành nợ); bỏ chỉ định / không làm → số về; khôi phục → trừ lại. HOÀN TIỀN
KHÔNG tự cộng kho: dòng ghi `so_hoan_tien`, người kho "Nhận lại hàng" / "Không nhận lại", hoặc quầy tick "Khách trả lại hàng" ở `D/thu-ngan/HoanTien.tsx`
(cả hai quầy). Nơi lấy: phòng chỉ định → phòng bác sĩ theo lịch → "Chờ gán phòng" (không đoán: phòng tắt, cơ sở khác, phòng đối tác, nhiều bác sĩ,
bác sĩ hai phòng); người kho gán rồi thì máy không đổi. Móc: `S/payment_service.py` (tạo lần thu, huỷ lần chờ, `void_payment`),
`S/hoan_tien_service.py`, `S/vat_tu_service.py` (`dat_so_luong`, `bo`), `S/bio_chi_dinh_service.py` `chon`; trạng thái chỉ định: bên nhận
`events/consumers/vat_tu_ban.py`. Hàng ở `drug_catalog` trùng mã vật tư: `S/vat_tu_trung_ma.py` (mã rỗng / không có bên vật tư = thuốc thường), giao ở
`S/pharmacy_service.py` `_giao_vat_tu`. Màn: `D/kho-vat-tu/BanChoKhachVatTu.tsx`, `NhapBuVatTu.tsx`. Dữ liệu cũ không trừ ngược: dòng chỉ sinh từ lần
thu mới hoặc `luot_vat_tu.tru_kho`. Test: `T/services/test_vat_tu_ban_kho_db.py`, FT `kho-vat-tu-boundary.test.mts`.

**Ai duyệt vật tư cần duyệt + nguyên nhân bán thêm (14/10/2026, G8b — Notion recap 12/10 mục 3.3, Tuyền Q11)** — người duyệt là
LEGO, không phải vai: khối `duyet_vat_tu` / quyền `vat_tu.approve` (`P/catalogue.py`, nằm trong `KHOI_CHI_QUAN_LY` — KHÔNG "mở full";
migration 20261014200000 cấp bù cho tài khoản Quản lý + Trưởng ca đang có; tài khoản Trưởng ca MỚI do Quản lý cấp ở `/phan-quyen`).
`S/vat_tu_service.py` (`_NGUOI_DUYET_SQL`, `_nguoi_duyet`, `doc` → `quan_ly` / `la_quan_ly` giữ tên khoá cũ cho màn) và trigger
`luot_vat_tu_gac` (CHỈ đổi điều kiện người duyệt: có `vat_tu.approve` trong `v_quyen_thuc_te`, đang làm việc). Nguyên nhân bán thêm:
cột `luot_vat_tu.ly_do_ban`, `VatTuService.them(ly_do_ban=)`, luôn ghi khi có gửi (5–500 ký tự, rác → 422); dây nối
`vat_tu_bat_ly_do_ban` (`S/day_noi.py`, mặc định TẮT) BẬT thì dòng MỚI ở quầy phải có. Màn: `D/thu-ngan/VatTuQuay.tsx`.
Test: `T/services/test_vat_tu_duyet_db.py` (D1–D4 + bấm ngẫu nhiên cấp/thu lego, bật/tắt dây, bán, bỏ), FT `duyet-vat-tu-boundary.test.mts`.

**Phiếu NHẬP vật tư chờ duyệt (14/10/2026, G8b-2)** — mặt hàng có cờ "cần duyệt nhập" (`can_duyet_nhap_vat_tu`, đặt ở danh mục vật tư):
`S/vat_tu_kho_service.py` `tao_phieu` (NHẬP) gọi `S/vat_tu_nhap_duyet_service.py` `xu_ly_nhap_can_duyet` — phiếu có ít nhất một dòng như vậy
KHÔNG ghi sổ mà thành YÊU CẦU ở bảng `vat_tu_nhap_cho_duyet` (migration 20261014200100; nội dung bất biến, giá nhập chụp lúc xin; cả phiếu chờ,
không ghi nửa phiếu). Người có lego Duyệt vật tư `duyet` → lập phiếu NHẬP thật đúng số; `tu_choi` (bắt lý do); người lập / người có lego `rut_lai`;
người có lego tự lập = tự duyệt; quyết MỘT lần; hoàn tác nhập đã duyệt = `hoan_phieu` như mọi phiếu. Route `R/vat_tu_nhap_duyet.py`:
`GET /vat-tu-kho/cho-duyet`, `POST …/{id}/duyet|tu-choi|rut-lai`. Sự kiện `vat_tu.nhap_cho_duyet`, `vat_tu.nhap_da_quyet`. CHƯA có màn: nút
Duyệt / Từ chối / Rút lại + danh sách chờ gắn vào `/kho-vat-tu` khi phiên màn G8a gộp (không sửa màn đó ở G8b). Test: `T/services/test_vat_tu_nhap_duyet_db.py`.

**Đặt cờ vật tư HÀNG LOẠT theo loại (16/10/2026)** — Kho vật tư → tab Danh mục, khối "Đặt cho cả loại":
`D/kho-vat-tu/DatCoTheoLoai.tsx` (Loại VPP/VTYT/Chưa phân loại + Cờ Được kinh doanh/Cần QL duyệt bán/Cần duyệt nhập
+ Bật/Tắt; xem trước "Sẽ đổi N vật tư" → Áp dụng → xác nhận tại chỗ → Hoàn tác) → `/api/service-price/vat-tu-hang-loat`
→ `POST /service-prices/vat-tu/hang-loat` (`R/config.py` `dat_co_vat_tu_hang_loat`, quyền `price.service.manage`) →
`S/vat_tu_danh_muc_service.py` `dat_co_hang_loat` + `kiem_hang_loat` (bảng `LOAI_HANG_LOAT` / `CO_HANG_LOAT` — thêm cờ
mới thì thêm ở đây và ở `DatCoTheoLoai.tsx`, FT canh lệch). Chỉ vật tư đang bán, chỉ đúng cột cờ; ghi `event_log`
`vat_tu.co_hang_loat`. Test: `T/services/test_vat_tu_hang_loat_db.py`, FT `vat-tu-hang-loat-boundary.test.mts`.

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
Bán theo đơn khám cũ (lịch sử đơn thuốc, kê / đã mua / còn lại, nhắc quá 2 tháng / vượt số kê,
nối – gỡ đơn gốc `visit.don_goc_visit_id`, mig `20261010100000`): khung "Lịch sử đơn thuốc"
`D/pharmacy/LichSuDonThuoc.tsx` (khung chọn khách `KhachMuaThuoc.tsx` — chưa mở lượt — và
`BanLeThu.tsx`; nút "Lịch sử khám" = popup chung `D/_lam-viec/LichSuKham.tsx`) →
`S/ban_theo_don_service.py` (`lich_su_don` — mới → cũ theo trang, `noi_don`, `go_noi_don`) +
`S/ban_le_service.py` (`lich_su_don`, `mo_theo_don` — mở lượt + nối + thêm dòng một giao dịch). Test:
`T/unit/test_ban_theo_don.py`, `T/services/test_ban_theo_don_db.py`.

**Thu trước – làm trước (tick "Làm trước – thu sau")** — công tắc: `/settings/day-noi`
(`thu_truoc_khi_lam`). Code: `S/lam_truoc_thu_sau.py`, cổng `S/finance_gate.py`
(`cua_lam`, `can_start`), ô tick `D/_lam-viec/OLamTruocThuSau.tsx`. Test:
`T/services/test_thu_truoc_lam_truoc_tick_db.py`, `T/services/test_lam_truoc_thu_sau_db.py`.
**Cửa tiền CHUNG khi Bắt đầu làm (phòng + bàn khám, 09/10/2026)** — hàm thuần
`S/service_execution_service.py` `cua_tien_chot_ho` (cờ hiện ô tick: `chan_vi_chua_thu`),
đầu vào `finance_gate.states_for_orders(gia_su_chon=True)`; lệnh `_cua_tien_chot_ho` chốt hộ
chỉ định chờ quyết (`lam_truoc_thu_sau.chot_mot_chi_dinh`, nguồn `lam_tai_phong` /
`lam_tai_ban_kham`), Huỷ bắt đầu trả về (`_tra_lua_chon`). Test:
`T/services/test_phong_bat_dau_chot_ho_db.py`, `T/unit/test_cua_tien_chot_ho.py`.

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

**Tài khoản ngân hàng nhận chuyển khoản (31/10/2026)** — danh mục là việc DỮ LIỆU: Quản lý làm trên
`/settings/tai-khoan-nhan` (thêm / sửa / đặt mặc định / tắt — không xoá). Code: `S/tai_khoan_nhan_service.py`
(`chon_mac_dinh` thuần: chọn > mặc định cơ sở > mặc định dùng chung > tài khoản duy nhất > "Chưa phân loại";
`chon_cho_lan_thu` gọi trong giao dịch thu từ `S/payment_service.py::_tai_khoan_nhan`, hoàn `S/hoan_tien_service.py::_tao_trong`,
đổi hình thức `S/doi_hinh_thuc_service.py`; sửa tài khoản phiếu đã thu `doi_cho_lan_thu` ← `R/payment.py` `/payments/doi-tai-khoan`,
vết event_log `payment.receiving_account_changed`) ← `R/tai_khoan_nhan.py`. Cột `payment_cycle.tai_khoan_nhan_id`,
`payment_refund.tai_khoan_nhan_id`, bảng `tai_khoan_nhan`, guard lần thu cho đổi đúng cột này (mig 20261031120000).
Báo cáo: `S/bao_cao_cuoi_ngay_service.py::gom_bao_cao` → `theo_tai_khoan` (cộng = dòng Chuyển khoản), CSV + `S/excel_report_export.py`;
`/hoa-don`: `S/hoa_don_projection.py::tach_tai_khoan`. Màn: `D/thu-ngan/TaiKhoanNhan.tsx` (`ChonTaiKhoan` trong `ChiaHinhThuc`,
`DoiTaiKhoan` ở `LichSuThu`), `D/reports/TomTatCuoiNgay.tsx`, `D/hoa-don/DanhSachHoaDon.tsx` + `ChiTietHoaDon.tsx`.
Test: `T/unit/test_tai_khoan_nhan.py` (bất biến bấm ngẫu nhiên), `T/services/test_tai_khoan_nhan_db.py`.

**Mua thêm vật tư / đầu dò** (khối "Món kèm" cũ đã gỡ 02/10, C17; dòng `luot_phu_thu` cũ
vẫn đọc ở `bill_service._PHU_THU_SQL`) — `D/thu-ngan/VatTuQuay.tsx`. **Thanh ngày quầy thu
(xem lại ngày cũ)** — `D/thu-ngan/TabThuNgan.tsx` + `S/cashier_board_service.py::khoang_ngay_xem`;
test `T/services/test_thu_ngan_thanh_ngay_db.py`, `D/tests/quay-thu-thanh-ngay-boundary.test.mts`.
**Hoàn tiền, đổi hình thức TM/CK (chia được), huỷ phiếu** — `D/thu-ngan/HoanTien.tsx` → `S/hoan_tien_service.py`;
`D/thu-ngan/DoiHinhThuc.tsx` → `S/doi_hinh_thuc_service.py`; huỷ →
`PaymentService.void_payment`. Test: `T/services/test_doi_hinh_thuc_db.py`.

**Kiểm kê tiền mặt két đầu ca – cuối ca (31/10/2026)** — KHÁC kiểm kê HÀNG (`S/kiem_ke_ca_service.py`). Màn: `/reports` tab
Cuối ngày → xem MỘT ngày + một ca + một cơ sở → khối "Tiền mặt két" ngay dưới Chốt ca (`D/reports/KhoiKetTienMat.tsx`:
quỹ đầu gõ tổng / đếm mệnh giá, gợi ý = đếm cuối ca trước; đếm cuối; lệch ≠ 0 bắt lý do; người nhận bàn giao; [Mở lại]
bắt lý do; "Lịch sử két"); cả ngày → `KetTienMatNgay` liệt kê từng ca. → `/api/reports/ket-tien-mat` →
`R/reports.py` (`GET/POST /reports/ket-tien-mat`) → `S/ket_tien_mat_service.py` (`doc_dem`, `tinh_cuoi`, `tien_mat_trong_ca`
thuần; dự kiến = quỹ đầu + dòng Tiền mặt `thuc_thu` của báo cáo cuối ca; cửa quyền dùng chung `S/chot_so_ca_service.py::kiem_ca`).
Bảng `ket_tien_mat_ca` (một dòng mỗi cơ sở/ngày/ca; Postgres ép tổng = bảng đếm qua `tong_to_tien`, dự kiến / lệch đúng công
thức, lệch ≠ 0 có lý do, không xoá) + vết chỉ thêm `ket_tien_mat_ca_lich_su` (mig 20261031125000). Báo cáo cuối ngày gắn
`ket_tien_mat` (`doc_ket_trong_khoang`, cả khi trả bản chụp chốt ca) + CSV. Test: `T/unit/test_ket_tien_mat.py`,
`T/services/test_ket_tien_mat_db.py`.

## 8. Xếp phòng · đổi phòng · chọn bác sĩ trong phòng

- Tự xếp (dây H4) + gợi ý + xếp tay: `S/service_routing_service.py`
  `ServiceRoutingService` (`assign`, `recommend`, `dat_phong_du_kien`); khối chọn
  phòng dùng chung `D/_lam-viec/DoiPhong.tsx` (quầy thu, trưởng ca, bàn khám).
- Chọn bác sĩ trong phòng ≥2 bác sĩ: `S/lan_bac_si.py`, `D/_lam-viec/ChonBacSiLam.tsx`;
  test `T/services/test_chon_bac_si_trong_phong_db.py`.
- Chuyển phòng từng chỉ định (trưởng ca): `D/truong-ca/ChiDinhCuaBacSi.tsx`.
  Cùng khối: [Bỏ chỉ định] / [Hoàn tác] — cờ `bo_duoc`, `hoan_tac_bo_id` ở
  `S/dispatch_service.py::chi_dinh` (luật `S/luot_kham_rules.py::chan_bo_chi_dinh`,
  dùng chung với `HoanTacService.huy_chi_dinh`); test `T/services/test_truong_ca_dieu_phoi_db.py`.
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

- **Hoàn tác giao / hoàn tác lần thu thuốc (31/10)** — `S/hoan_tac_giao_service.py`: sổ kho dòng `DISPENSE_REVERSAL` (đảo đúng
  một lần giao, phần khách đã trả không đảo; ép ở trigger `inventory_txn_ban_hop_le`, `uq_inventory_txn_dao_giao_mot_lan`).
  Nút ở từng lần giao `D/pharmacy/DongThuoc.tsx` (`xuat[].thao_tac.hoan_tac_giao`, `cho_gan[]`) và `ChoGanLo.tsx` →
  `PharmacyService.hoan_tac_giao` / `huy_dong_cho_gan_lo`: tiền giữ, giao lại được. Hoàn tác lần thu: `void_payment` gọi
  `dao_giao_khi_huy_phieu` — mọi thuốc đã giao về quầy, dòng về chưa giao, mở lại dòng đã chốt; câu xác nhận
  `D/thu-ngan/NutHoanTac.tsx` đọc `GET /payments/hoan-tac/xem-truoc` (phải trả = đã thu − đã hoàn). Sự kiện
  `medicine.dispense_undone` (hành trình, sổ nợ). Phiếu đã hoàn tác không hoàn tiền thêm (`payment_refund_guard`).

- **Giao nhầm hàng vật tư ở quầy thuốc (31/10)** — `PharmacyService.hoan_tac_giao_vat_tu`, nút ở `D/pharmacy/DongThuoc.tsx`: dòng về chưa giao, tiền và
  số Kho vật tư giữ nguyên. Kiểm ca / kiểm kho: có lần kiểm sau trên lô thì hoàn tác hay sửa số cũ bị chặn (`kiem_ke_ca_service.lo_co_kiem_sau`).
  Hàm SQL `he_so_don_vi` (mig `20261101400000`) phải giữ cùng luật `BangDonVi._khop`. Test: `T/services/test_soat_kho_3110_db.py`, `test_soat_kho_3110_b_db.py`.

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

- **Nhập nhanh khách chưa lịch (13/10):** CSKH lưu/Enter ở tên hoặc SĐT trong
  `D/patients/new/NewPatientForm.tsx` → `/customers?selected=…`, kể cả có quyền
  Tiếp đón. `S/man_khach_hang_service.py` trả `CHO_DAT_LICH` cho hồ sơ tiếp nhận
  chưa từng có lịch/lượt và chưa có việc CSKH khác: nhóm “Chờ xác nhận”, bước
  “Gọi điện xác nhận”; ghi cuộc gọi loại `HOI_THAM`, không xác nhận lịch chưa có.
  Có lịch/lượt là hết việc này. **15/10:** chỉ lưu hồ sơ → `NewPatientForm` sang
  `/customers?selected=` cho MỌI vai vào được màn ấy (prop `veQuanLyKhach`, trang
  `patients/new/page.tsx` + `appointments/page.tsx` → `BookingHub`; "Dùng bệnh nhân
  này" giữ đường cũ); CSKH gọi xong (`DA_LIEN_HE`) thì việc đóng, không nghe máy thì
  còn mở, rút lại được kể cả khi khách chưa có lượt (`VungLamViecKhach.tsx` `rutNgoaiLuot`
  + `chuaCoLuot`), nhãn chip `customers/mot-cham.ts` (`CHO_DAT_LICH`). FT
  `luu-ho-so-sang-quan-ly-khach-boundary.test.mts`. Test `T/services/test_man_khach_hang_callback_db.py`,
  FT `intake-patient-ui-boundary.test.mts`; bấm thật `e2e/quick-intake-confirmation.mjs`.
- **Gọi xác nhận lịch đặt hộ (15/10):** việc `CHO_XAC_NHAN` ("Gọi xác nhận lịch") sinh
  cho MỌI lịch còn sống, kênh ≠ `WALK_IN`, khám trong [hôm nay, +7 ngày], kể cả đặt sát
  ngày; hạn = `GREATEST(ngày khám − so_ngay, ngày đặt)`; đóng bằng một dòng
  `XAC_NHAN_LICH` chưa hoàn tác (không nghe máy/hẹn lại → `GOI_LAI`). Nguồn: view
  `v_viec_cskh` (migration `20261015110000`, nhãn ở `luat_cskh`). Không có cột "ai đặt"
  (chưa có cổng khách tự đặt) — thêm đường ghi lịch mới thì làm phương án B (cột nguồn
  đặt). Test `T/services/test_goi_xac_nhan_lich_dat_ho_db.py` + bài canh ba nơi ghi
  lịch `T/unit/test_dat_lich_chi_ba_noi_ghi.py`. Việc dữ liệu: bật/tắt, số ngày =
  `luat_cskh` (sửa trên màn).
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
- **Phản hồi sau dùng thuốc (10/10):** khối "Phản hồi sau dùng thuốc" của khung khách
  (`D/_lam-viec/KhungKhach.tsx` → `D/_lam-viec/PhanHoiThuocKhach.tsx`: chọn lượt có đơn,
  kênh, nội dung · Gỡ · [Đặt lịch khám] = `DatLichModal` "kham-moi" của `CustomersView`)
  → `/api/cskh/khach/[id]` (`?xem=phan-hoi-thuoc`, `thao_tac: phan-hoi-thuoc |
  go-phan-hoi-thuoc`) → `S/phan_hoi_thuoc_service.py` (`doc`, `ghi`, `go`). Lưu ở
  `tuong_tac_cskh` loại `PHAN_HOI_THUOC` + cột `visit_id` (mig `20261010200000`); chỉ
  người ghi gỡ được (cả `tuong_tac_cskh_service.hoan_tac`); POST nhận `Idempotency-Key`.
  Bác sĩ đọc: `doc_theo_khach` → `phan_hoi_thuoc` của `GET /clinical-forms/history`
  (Bàn khám `LuotKhamTruoc`, theo KHÁCH — cả lượt có đơn chưa có phiếu) và
  `doc_theo_luot` → `S/lich_su_luot.py` (popup `LichSuKham`). Test: `T/services/test_phan_hoi_thuoc_db.py`.
  **Ra bảng danh sách (16/10):** cột "Phản hồi thuốc" của `/customers`
  (`D/customers/PhanHoiThuocCot.tsx`, vẽ trong `CustomersView.tsx`) đọc khối `phan_hoi_thuoc`
  của `GET /cskh/man-khach-hang` → `S/man_khach_hang_service.py` (`goi_du_lieu` một câu
  `DISTINCT ON` + `count() OVER`; `tom_tat_phan_hoi_thuoc`, `rut_gon` ~40 ký tự); nút lọc
  "Có phản hồi sau dùng thuốc" = `?phan_hoi_thuoc=1` → `GET /cskh/danh-sach-khach` →
  `S/danh_sach_khach_cskh.py` (`co_phan_hoi_thuoc`); dòng "gần nhất" ở đầu `KhungKhach.tsx`
  (nhận từ `PhanHoiThuocKhach` qua `onDoc`, không đọc thêm). Chỉ mục: mig `20261016300000`.
  Test: `T/services/test_phan_hoi_thuoc_cot_db.py`, `T/unit/test_man_khach_hang.py`
  (`TestPhanHoiThuocCot`), FT `phan-hoi-thuoc-cot-boundary.test.mts`.
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

- **Trưởng ca thấy sai cơ sở trong báo cáo/quầy thu:** `S/report_access_service.py`
  `ROSTER_LOCATION_JOIN` dùng chung với `S/cashier_scope_service.py`. Vị trí
  `DIEU_PHOI` không gắn phòng dùng chung cơ sở đang bật trong cùng phòng khám;
  có phòng thì lấy cơ sở của phòng. Không suy ra từ cơ sở mặc định nhân viên.
  Test: `T/services/test_report_access_db.py`.

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
- **API chậm / nghi cạn bể kết nối (14/10/2026):** log container `api` có dòng
  `request_cham` (mỗi request ≥ 500ms), `api_nhip_phut` (mỗi phút), `pool_cho_lau`/
  `pool_day`/`pool_ban_keo_dai`; `/ops/pool` (số tức thời) + cảnh báo `POOL_API_DAY` ở
  `/ops`. Code: `src/clinicai/core/quan_sat.py` (đo), `S/canh_gac_pool.py` (vòng nền +
  cảnh báo), `TimingMiddleware` ở `src/clinicai/api/middleware.py`; trần bể
  `POOL_MAX_SIZE` ở `src/clinicai/core/database.py`. Test: `T/core/test_quan_sat.py`,
  `T/services/test_quan_sat_pool_db.py`. Bẫy: **không mượn kết nối thứ hai khi đang giữ
  một** (truyền `conn`, đừng truyền `pool` xuống hàm con).
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
