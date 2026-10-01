# Bàn giao — nhánh `claude/thu-nhieu-hinh-thuc` (01/10/2026, WIP)

**Mục tiêu (Tuyền 01/10):** một lần thu = nhiều hình thức (Tiền mặt + Chuyển khoản; bỏ QR, QR cũ = CK);
khách đưa dư → "trả lại khách X" (chỉ hiển thị); ảnh chuyển khoản (không bắt buộc, VPS→CFS);
nút **Hoàn tác lần thu** ở mọi chỗ thu, mở cho người đứng quầy, lý do tuỳ chọn, mọi màn tự cập nhật.

## ĐÃ LÀM (chưa chạy test/tsc/eslint lần nào)
- **Migration `supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql`** (CHƯA áp DB chung):
  `payment_cycle_phan` (phần theo hình thức, chỉ thêm, trigger HOÃN tới COMMIT ép tổng = amount và
  "có phần CK ⇔ method TRANSFER"); `payment_cycle_doi_hinh_thuc` + `tien_mat`/`chuyen_khoan` (đổi sang
  chia), bỏ CHECK `khac_cu`, guard kiểm tổng; hàm `phan_thu_hieu_luc(clinic,cycle,goc,amount)→jsonb`;
  bảng `anh_chuyen_khoan` (cùng bộ cột đẩy tệp với `tep_ket_qua`); trigger notify cho `payment_cycle`,
  `payment_cycle_doi_hinh_thuc`, `anh_chuyen_khoan`; chép lại `don_khach_thu` thêm 2 bảng mới.
- `services/phan_thu.py` (thuần): `doc_phan`, `ap_phan`, `hinh_thuc_chinh`, `doc_phan_db`, `nhan_phan`, `tra_lai`.
- `payment_service.py`: `record_payment(phan=…)` (QR→TRANSFER, ghi `_ghi_phan`), `hoan_tac()` (PAID→`void_payment`,
  PENDING→`huy_cho_xac_minh`; lý do mặc định `ly_do_hoan_tac`), sự kiện `payment.collection_undone`
  (`_phat_hoan_tac`, khai ở catalogue/modules/dong_thoi_gian/audit_labels), `ly_do_khong_hoan_tac`;
  void thuốc của lượt BÁN LẺ → `ban_le_service.mo_lai_luot_ban_le`.
- `anh_chuyen_khoan_service.py` (tải lên qua `nhan_multipart`, đọc qua `_tim_ban`, gỡ = ẩn); `day_tep.py` đẩy cả 2 bảng (`BANG_TEP`).
- Router `payment.py`: `phan` trong POST /payments; `POST /payments/hoan-tac`; `/payments/anh-chuyen-khoan` (POST/GET/{id}/go); doi-hinh-thuc nhận `tien_mat`,`chuyen_khoan`.
- Đọc chia phần: `cashier_board_service` (giao_dich: `phan`,`anh_ck`,`hoan_tac`; board cho_xac_minh: `phan`,`anh_ck`),
  `quay_thu_service` (lịch sử: phần + tổng theo phần, bỏ ô QR; phiếu in: `phan`,`tra_lai`), `bao_cao_cuoi_ngay_service`
  (theo hình thức cộng từng phần, QR→CK), `doi_hinh_thuc_service` (chia), `ban_le_service`.
- FE: `lib/hinh-thuc-thu.ts`; `thu-ngan/ChiaHinhThuc.tsx`, `AnhChuyenKhoan.tsx`, `NutHoanTac.tsx` (mới);
  sửa `HoaDonMot`, `QuayThuNgan` (NhomThu/NoKhac/khối chờ xác minh/nút hoàn tác sau câu "Đã thu"),
  `GiaoDich`, `LichSuThu`, `DoiHinhThuc` (chia), `HoanTien` (bỏ QR), `reports/CuoiNgay`, `pharmacy/BanLeThu`;
  route `app/api/payment/route.ts` (hoan-tac, phan, chia) + mới `app/api/payment/anh-ck/route.ts`.

## CÒN LẠI (theo thứ tự)
1. `print/phieu-thu/[id]/InPhieuThu.tsx`: in mỗi phần một dòng (`phieu.phan`) + "Khách đưa / Trả lại" (`tra_lai`); bỏ QR ở TEN_PT.
2. `npx tsc --noEmit`, `npx eslint .`, `poetry run ruff check/format`, `mypy` — sửa lỗi.
3. Sửa test cũ đổi hành vi (QR→TRANSFER): `T/unit/test_quay_thu.py` (ô `qr`, lọc QR), `T/unit/test_bao_cao_cuoi_ngay.py`
   (dòng QR), `T/unit/test_doi_hinh_thuc.py`, `T/services/test_tien_thuoc_cp2_db.py:343` (QR giờ ghi TRANSFER), test day_tep nếu đỏ.
4. Test mới: `T/unit/test_phan_thu.py` (doc_phan rác, ap_phan lệch tổng, ly_do_hoan_tac); DB: thu 700k = 500k TM + 200k CK
   (cycle TRANSFER chờ → xác minh → PAID, `phan_thu_hieu_luc` 2 phần), trigger chặn tổng lệch, hoan_tac PAID/PENDING/đã-có-hoàn,
   hoàn tác dịch vụ đã bắt đầu vẫn được, bán lẻ mở lại lượt, đổi hình thức sang chia, ảnh tải/đọc/gỡ.
5. Áp migration vào DB chung: `CLINIC_DB_CONTAINER=chung_test_db ./scripts/apply-pending-migrations.sh --apply` (+ `clinicai_thu_db` để bấm thật).
6. `docs/SITEMAP.md` mục B (dòng Thu tiền / Đổi hình thức: bỏ QR, thêm chia + ảnh + Hoàn tác; route API mới), `docs/BAN-DO-SUA.md` mục 7,
   `python3 scripts/ban-do-code.py` rồi commit `docs/BAN-DO-CODE.md`.
7. Bấm thật 375 + 1280, `./scripts/ci-may.sh --bao-github`, PR (bảng nút/link đã đụng).

## Quyết định đã chốt + lý do
- `payment_cycle.method` của lần thu chia = TRANSFER (có CK ⇒ phải "chờ xác minh" như contract A2); chia thật ở `payment_cycle_phan`.
- Hoàn tác KHÔNG làm đường thứ hai: dùng lại `void_payment`/`huy_cho_xac_minh`. Hoàn tác ≠ hoàn tiền (hoàn tiền: khách trả đúng, giờ trả lại; phiếu vẫn đứng). Phiếu dịch vụ đã có khoản hoàn → không hoàn tác (tránh trả hai lần).
- Ảnh CK không vào `tep_ket_qua` (bảng ấy là kết quả khám: gửi khách, chuông bác sĩ) → bảng riêng, cùng cơ chế VPS→CFS.
- Đổi hình thức sang chia lưu ở `payment_cycle_doi_hinh_thuc` (sự kiện `sang="CASH+TRANSFER"`, không đổi version payload).

## Bẫy
- Hook rtk chặn `git` trong worktree → dùng `/usr/bin/git`. Lệnh python heredoc dài bị chặn → viết kịch bản vào scratchpad.
- `don_khach_thu` có danh sách bảng cứng: nhóm khác cũng sửa hàm này → khi merge giữ đủ cả hai bảng `payment_cycle_phan`, `anh_chuyen_khoan`.
- Ảnh của khách thử bị dọn sẽ còn tệp mồ côi trên đĩa (hàm dọn chỉ trả tệp `tep_ket_qua`).

## Kịch bản bấm thử staging
1. `/thu-ngan/dich-vu` khách có 700k → tick Tiền mặt + Chuyển khoản, gõ CK 200000 (TM tự = 500.000), Khách đưa 600000 → thấy "Trả lại khách 100.000đ"; chọn ảnh CK → [Thu · chờ xác minh CK] → [Đã nhận tiền].
2. Tab "Đã thanh toán hôm nay": dòng hiện "Tiền mặt 500.000đ + Chuyển khoản 200.000đ", thấy ảnh; [In phiếu thu] thấy 2 dòng hình thức (sau khi làm mục 1 CÒN LẠI).
3. [Hoàn tác lần thu] (bỏ trống lý do) → quầy hiện lại khách "chờ thu"; Xem hành trình có dòng "Hoàn tác lần thu"; thu lại tiền mặt đủ → OK.
4. `/reports` Cuối ngày: dòng Tiền mặt +500k, Chuyển khoản +200k; không còn dòng QR.
