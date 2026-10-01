# Bàn giao — nhánh `claude/danh-muc-chuan-0110` (01/10/2026)

## Mục tiêu (Tuyền 01/10)
Danh mục dịch vụ chuẩn theo file "[Dr4women] Bảng giá dịch vụ trên Kiot 01.10.26 (Hà Nguyễn gửi).xlsx"
(93 dòng); MỌI dịch vụ đang bán (trừ phí khám) chọn được ở ô chỉ định, có tìm, gom theo nhóm;
XN thu hộ hiện đúng giá file kể cả 0đ; màn quản lý "dịch vụ & phòng" lọc "chưa có phòng", gán phòng tại chỗ.

## Đã làm (commit 530cd192 + ce058d5c + commit hiện tại)
- Migration `supabase/migrations/20261002100000_danh_muc_dich_vu_chuan_0110.sql` (+ gọi lại cuối `supabase/seed.sql`):
  bảng `danh_muc_dich_vu_nguon` (93 dòng nguyên văn, nguon='kiot_0110'), `khoa_ten_dich_vu`, `nhom_viec_theo_nhom_hang`,
  `ghep_danh_muc_dich_vu` (khớp tên chuẩn hoá + ánh xạ tay SP000140 Tropocel / SP000136 Regenlab),
  `dong_bo_danh_muc_dich_vu(nguon)` (tên, category = Nhóm hàng, active, giá; XN thu hộ → EXTERNAL_PARTNER + giá file kể cả 0;
  phòng khám thu KHÔNG nạp 0; thêm dòng thiếu `DV_<md5 tên>`; gắn nhóm cho dịch vụ ngoài file; tắt 2 dòng tiêu đề
  CLS_XET_NGHIEM_DICH_AM_DAO, CLS_LASER; loại khám THU_THUAT thêm mọi dòng nhóm Thủ thuật), hàm đọc `danh_muc_dich_vu(clinic)`
  (la_phi_kham, can_phong, phong jsonb qua `phong_lam_duoc`, chua_co_phong). Chạy lại = (0,0,0,0).
- `S/danh_muc_dich_vu_service.py`: hàm thuần nhom_hang_hien / thu_tu_nhom_hang / ly_do_khoa_chi_dinh / dong_danh_muc,
  `dem_chua_co_phong`, `DanhMucDichVuService.doc`.
- `S/phieu_kham_service.py` `tham_chieu_that`: đọc `danh_muc_dich_vu`; mọi dịch vụ trừ phí khám (bỏ điều kiện có mã KV + node);
  nhóm "(danh mục phòng khám)" theo nhóm hàng; mỗi mục thêm `nhom_hang`, `khoa` (chưa nhóm việc → khoá ô kèm câu).
- `S/luot_kham_doc.py` (ô "Chỉ định thêm" Bàn khám): cùng hàm, bỏ lọc DICHVU-*.
- `S/clinic_config_service.py` `set_service_rooms` + route `PUT /api/v1/clinic-config/service-rooms` (quyền config.clinic.manage;
  rỗng = về theo nhóm việc; dịch vụ chưa node lấy node DICHVU-* của phòng đầu).
- `S/config_service.py`: `nhom` (category) ở add/update, mã tự sinh `ma_dich_vu_theo_ten`, `_nhom_hang`; gỡ `LIMIT 1000` ở `PriceListService.list` (tránh rớt dòng ở DB nhiều bản ghi test).
- Router `GET /api/v1/service-prices/danh-muc`; proxy `/api/service-price?xem=danh-muc`, `nhom`; `/api/clinic-config` what=service-rooms.
- UI: `/cashier/dich-vu` → `cashier/DanhMucDichVuPhong.tsx` (mới; bảng thuốc vẫn CashierView), nav đổi "Bảng giá dịch vụ & phòng";
  `DanhMucChiDinh.tsx` ô tìm + gom nhóm hàng + khoá theo `khoa`; `lib/phieu-kham.ts` `timDanhMucChiDinh`, `gomTheoNhomGoc`, `boDauTim`;
  trang chủ "Cần xử lý" dòng `dich_vu_chua_phong` (chỉ ai có config.clinic.manage) → `/cashier/dich-vu?loc=chua-phong`.
- Docs: SITEMAP (3 hàng), BAN-DO-SUA mục 1 + 6, BAN-DO-CODE sinh lại (khớp).
- Test: `T/services/test_danh_muc_dich_vu_chuan_db.py` (5 test, xanh), `T/unit/test_danh_muc_dich_vu.py`,
  FT `tim-danh-muc-chi-dinh-boundary.test.mts`, sửa `test_danh_muc_kiotviet_db.py`, `test_man_trang_chu.py`, `cashier-catalog-ui-boundary`.
- Đã giải quyết test đỏ: sửa `LIMIT 1000` trong `PriceListService.list` giúp `test_ben_thu_chon_tay_khong_bi_phong_ghi_de` xanh.
- Đã bấm thật local qua Playwright (Chrome thật) ở 1280 và 375:
  + Màn Bảng giá dịch vụ & phòng (`/cashier/dich-vu`): lọc chưa có phòng, gán phòng, bỏ gán riêng hoàn tác.
  + Màn Bàn khám (`/ban-kham`): mở phiếu khám, ô chỉ định tìm PRP (Tropocel & Regenlab), NIPT, Liên cầu B (0đ · trả đối tác).

## Bẫy & Lưu ý
- Test chập chờn: `test_bao_cao_cuoi_ngay_db.py` kiểm tra top 10 doanh thu trong ngày, khi DB dùng chung bị tích luỹ nhiều giao dịch test thì dịch vụ test bị đẩy khỏi top 10. Chạy trong CI trên DB nhân bản sạch từ template1 xanh hoàn toàn.

## Migration
`20261002100000_danh_muc_dich_vu_chuan_0110.sql` — ĐÃ áp vào `chung_test_db` (55600) và `clinicai_thu_db` (54422). Chưa lên VPS.
SQL kiểm sau khi áp prod: `SELECT * FROM dong_bo_danh_muc_dich_vu('kiot_0110');` → 0,0,0,0;
`SELECT count(*) FROM danh_muc_dich_vu('a0000000-0000-4000-8000-000000000001') WHERE chua_co_phong;` → 0.

## Kịch bản bấm thử staging
1. Bác sĩ mở phiếu khám → mục C gõ "PRP", "NIPT", "Liên cầu B" → thấy đủ; Liên cầu B "0 đ · trả đối tác".
2. Chỉ định NIPT basic → quầy thu thấy dòng thu hộ "tham khảo 0 đ", không cộng tổng.
3. Quản lý mở Trang chủ: không có dòng "dịch vụ chưa có phòng" (prod = 0). Vào Bảng giá dịch vụ & phòng → chip "Chưa có phòng 0".
4. Chọn "Massage vú" → [Sửa phòng] → chỉ tick Phòng Sàn chậu → Lưu → chip "gán riêng"; quầy/xếp phòng chỉ gợi ý Sàn chậu;
   [Bỏ gán riêng — theo nhóm việc] để trả lại.
5. Thêm dịch vụ mới không nhóm việc → dải vàng "1 dịch vụ chưa có phòng" + dòng ở Trang chủ → [Gán phòng] → hết cảnh báo.
