# Bàn giao — nhánh `claude/danh-muc-chuan-0110` (01/10/2026)

## Mục tiêu (Tuyền 01/10)
Danh mục dịch vụ chuẩn theo file "[Dr4women] Bảng giá dịch vụ trên Kiot 01.10.26 (Hà Nguyễn gửi).xlsx"
(93 dòng); MỌI dịch vụ đang bán (trừ phí khám) chọn được ở ô chỉ định, có tìm, gom theo nhóm;
XN thu hộ hiện đúng giá file kể cả 0đ; màn quản lý "dịch vụ & phòng" lọc "chưa có phòng", gán phòng tại chỗ.

## Đã làm (commit WIP 530cd192, đã push)
- Migration `supabase/migrations/20261002100000_danh_muc_dich_vu_chuan_0110.sql` (+ gọi lại cuối `supabase/seed.sql`):
  bảng `danh_muc_dich_vu_nguon` (93 dòng nguyên văn, nguon='kiot_0110'), `khoa_ten_dich_vu`, `nhom_viec_theo_nhom_hang`,
  `ghep_danh_muc_dich_vu` (khớp tên chuẩn hoá + ánh xạ tay SP000140 Tropocel / SP000136 Regenlab),
  `dong_bo_danh_muc_dich_vu(nguon)` (tên, category = Nhóm hàng, active, giá; XN thu hộ → EXTERNAL_PARTNER + giá file kể cả 0;
  phòng khám thu KHÔNG nạp 0; thêm dòng thiếu `DV_<md5 tên>`; gắn nhóm cho dịch vụ ngoài file; tắt 2 dòng tiêu đề
  CLS_XET_NGHIEM_DICH_AM_DAO, CLS_LASER; loại khám THU_THUAT thêm mọi dòng nhóm Thủ thuật), hàm đọc `danh_muc_dich_vu(clinic)`
  (la_phi_kham, can_phong, phong jsonb qua `phong_lam_duoc`, chua_co_phong). Chạy lại = (0,0,0,0).
- `S/danh_muc_dich_vu_service.py` (mới): hàm thuần nhom_hang_hien / thu_tu_nhom_hang / ly_do_khoa_chi_dinh / dong_danh_muc,
  `dem_chua_co_phong`, `DanhMucDichVuService.doc`.
- `S/phieu_kham_service.py` `tham_chieu_that`: đọc `danh_muc_dich_vu`; mọi dịch vụ trừ phí khám (bỏ điều kiện có mã KV + node);
  nhóm "(danh mục phòng khám)" theo nhóm hàng; mỗi mục thêm `nhom_hang`, `khoa` (chưa nhóm việc → khoá ô kèm câu).
- `S/luot_kham_doc.py` (ô "Chỉ định thêm" Bàn khám): cùng hàm, bỏ lọc DICHVU-*.
- `S/clinic_config_service.py` `set_service_rooms` + route `PUT /api/v1/clinic-config/service-rooms` (quyền config.clinic.manage;
  rỗng = về theo nhóm việc; dịch vụ chưa node lấy node DICHVU-* của phòng đầu).
- `S/config_service.py`: `nhom` (category) ở add/update, mã tự sinh `ma_dich_vu_theo_ten`, `_nhom_hang`.
- Router `GET /api/v1/service-prices/danh-muc`; proxy `/api/service-price?xem=danh-muc`, `nhom`; `/api/clinic-config` what=service-rooms.
- UI: `/cashier/dich-vu` → `cashier/DanhMucDichVuPhong.tsx` (mới; bảng thuốc vẫn CashierView), nav đổi "Bảng giá dịch vụ & phòng";
  `DanhMucChiDinh.tsx` ô tìm + gom nhóm hàng + khoá theo `khoa`; `lib/phieu-kham.ts` `timDanhMucChiDinh`, `gomTheoNhomGoc`, `boDauTim`;
  trang chủ "Cần xử lý" dòng `dich_vu_chua_phong` (chỉ ai có config.clinic.manage) → `/cashier/dich-vu?loc=chua-phong`.
- Docs: SITEMAP (3 hàng), BAN-DO-SUA mục 1 + 6, BAN-DO-CODE sinh lại (khớp).
- Test: `T/services/test_danh_muc_dich_vu_chuan_db.py` (5 test, xanh), `T/unit/test_danh_muc_dich_vu.py`,
  FT `tim-danh-muc-chi-dinh-boundary.test.mts`, sửa `test_danh_muc_kiotviet_db.py`, `test_man_trang_chu.py`, `cashier-catalog-ui-boundary`.

## Đã kiểm
ruff + format + mypy xanh; pytest không-DB 3302 xanh; 457 boundary FE xanh; tsc xanh; DB: 5 test mới + 70 test liên quan xanh.
Bộ DB đầy đủ chạy dở bị dừng: có **1 F ở ~28%** chưa xem tên — việc đầu tiên phải làm.

## Còn lại (theo thứ tự)
1. Chạy `pytest -m db src/tests` trên DB chung 55600, tìm test đỏ (nghi: test dựa vào giá/bên thu cũ của XN thu hộ trong seed —
   seed nay KV_SP000092/088… thành EXTERNAL_PARTNER, HPV/ThinPrep/PCR giá 0). Sửa test theo luật mới, không nới luật.
2. Bấm thật local (API 8201 / web 3201 trỏ clinicai_thu_db — migration ĐÃ áp vào đó, local hiện 6 dịch vụ chưa phòng):
   375 + 1280 cho `/cashier/dich-vu`, phiếu khám (ô tìm), trang chủ quản lý. Chú ý `scripts/dev-nap-lai.sh` pkill uvicorn của người khác — tự chạy uvicorn/next tay.
3. `./scripts/ci-may.sh --bao-github` rồi mở PR (bảng nút/link, kịch bản dưới, SQL kiểm).
4. Đề xuất cho Tuyền (chưa làm): dịch vụ đang bán ngoài file (giữ bật): 3 chụp phim ngoài, XN nam khoa (CFTR, NST Y, karyotype,
   nước tiểu sau xuất tinh, nội tiết nam), tinh dịch đồ, DFI, Siêu âm 3D sàn chậu, Biofeedback cơ bản/nâng cao, Trải nghiệm ghế ĐTT ×2, Xét nghiệm máu.
   Phí khám 0đ (Khám sau sinh BN cũ, Tư vấn KQ XN cũ) vẫn TRỐNG — miễn phí thật thì quản lý nhập 0 ở Bảng giá.

## Quyết định tự chốt + lý do
- 0đ chỉ cho dịch vụ thu hộ (khách trả đối tác, giá chỉ tham khảo); phòng khám thu mà 0 = thu 0 đồng → giữ luật 26/09.
- Phí khám = không nhóm việc VÀ (category Phí khám/Tiền khám, mã KHAM_*, hoặc có trong loai_kham_phi). Vật lý trị liệu,
  Tư vấn phụ khoa chuyên sâu có nhóm việc → vẫn là dịch vụ chỉ định được (như quyết định 01/10 ở mig 20261001210000).
- Không xoá gì; chỉ tắt 2 dòng tiêu đề phiếu giấy (đã ẩn khỏi chỉ định từ 27/09, không có trong file). KHONG_LIET_KE giữ.
- Gán phòng ở màn Bảng giá dùng `clinic_room_service` (danh sách đầy đủ; rỗng = theo nhóm việc) — không bảng mới.
- Bỏ nút Xoá ở bảng giá dịch vụ (thôi bán = bỏ tick Đang bán) → không còn window.confirm.

## Bẫy
- `.venv` và `src/dashboard/node_modules` trong worktree là symlink (không commit).
- Hàm cũ `chuan_hoa_danh_muc_dich_vu_kiotviet()` chạy lại sẽ đưa HPV 900k/PCR 1,1tr về — chỉ seed/test gọi; seed gọi hàm mới SAU nó.
- DB chung có nhiều dòng rác của test (GK2-*, SA2-*) → đếm "chưa có phòng" ở 55600 lớn; đừng ghim số trong test.

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
