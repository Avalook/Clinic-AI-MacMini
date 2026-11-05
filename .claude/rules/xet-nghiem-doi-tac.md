---
paths:
  - "src/clinicai/services/xet_nghiem/**"
  - "src/clinicai/services/doi_tac_service.py"
  - "src/clinicai/services/tep_ket_qua_service.py"
  - "src/clinicai/services/bao_ket_qua_ve.py"
  - "src/clinicai/services/bao_cao_cuoi_ngay_service.py"
  - "src/clinicai/api/v1/routers/doi_tac.py"
  - "src/clinicai/api/v1/routers/xet_nghiem.py"
  - "src/dashboard/app/doi-tac/**"
  - "src/dashboard/app/xet-nghiem/**"
  - "src/tests/**/*xet_nghiem*"
  - "src/tests/**/*doi_tac*"
  - "supabase/migrations/202611052*"
---

# Xét nghiệm đối tác — luật đã chốt (Tuyền 05/11/2026)

Kế hoạch: `docs/KE-HOACH-XET-NGHIEM-DOI-TAC.md`. Vì sao: `docs/adr/0015-xet-nghiem-doi-tac.md`.
Đọc kế hoạch mục 1 (6 câu đã chốt) và mục 9 (không được làm) **trước khi sửa bất cứ gì ở đây**.

## Tiền thu hộ — sổ riêng
- Thu hộ chỉ ghi vào `doi_tac_thanh_toan` (+ `doi_tac_hoan_tien`). **Không bao giờ** đụng
  `payment_cycle`, `payment`, `payment_bill_line`, `payment_refund`, két, doanh thu.
  Test khoá việc này phải luôn xanh; đừng sửa test để nó xanh.
- Giá chỉ là **gợi ý**. Không validate "số tiền phải bằng giá". Lưu cả `gia_goi_y` và `so_tien`.
- **Huỷ** = ghi sai (bắt lý do). **Hoàn** = trả tiền thật cho khách (dòng mới, bắt lý do). Hai lệnh khác nhau.
- Tab tiền lọc theo **ngày ghi nhận/ngày hoàn** (giờ Việt Nam), không theo ngày chỉ định.
- Sửa cột của `doi_tac_thanh_toan` ⇒ sửa luôn hàm trigger `doi_tac_thanh_toan_chi_huy()`.

## Lấy mẫu — ngoại lệ duy nhất của "làm trước, thu sau"
- Nút Lấy mẫu chỉ mở khi việc có ghi nhận thu còn hiệu lực (kể cả 0đ, CK chưa thấy tiền).
  "Quản lý cho qua" đã BỎ (Tuyền 05/11, kế hoạch 5d). **Không chặn thêm thứ gì khác** — chỉ định, khám,
  thu ngân, ra về vẫn chạy như luật 30/09 và 16/10.
- Mã mẫu cấp ở Postgres (`cap_ma_mau`), theo ống, chữ số kiểm Damm. Không suy từ mã khách.
- Một ống chỉ chứa việc của **một** đối tác — ép bằng khoá ngoại, không bằng `if` Python.

## Trạng thái — một hàm
- Chữ trạng thái chỉ do `services/xet_nghiem/trang_thai.py: trang_thai_xet_nghiem()` tính.
  Màn, đếm, lọc, báo cáo đều gọi nó. Không thêm cột trạng thái, không tính lại trong TSX hay SQL.
- Thêm trạng thái mới = sửa hàm + bảng test của hàm, không sửa chỗ khác.

## Hoàn tác — lệnh bù theo bước
- Không chụp/khôi phục bản ghi. Mỗi bước có lệnh bù riêng, bắt lý do ≥ 3 ký tự, phát sự kiện
  khai trong `events/catalogue.py`.
- Tệp do hệ thống kéo về ⇒ **Từ chối tệp** (`TU_CHOI`), nhớ `(file_id, md5)` để lượt quét sau bỏ qua.
- Đã gửi khách ⇒ chỉ **Thu hồi** (lý do, báo khách). Không xoá mốc gửi.

## Kết quả về
- Tệp đối tác vào `tep_ket_qua` ở `CHO_XAC_NHAN`, hiện ngay, báo qua `bao_ket_qua_ve`.
  **Không gỡ** trigger cấm gửi tệp chưa xác nhận. Gửi khách = "Đúng người, gửi" (một giao dịch, kênh bắt buộc).
- Tải tay: nhân viên đã chọn đúng việc ⇒ xác nhận cùng bước.
- Drive: chỉ tài khoản dịch vụ / OAuth chỉ đọc; khoá chỉ trong biến môi trường (`.env.prod`);
  **cấm link công khai**; không gọi Drive từ trình duyệt. Mã trong tên tệp sai số kiểm,
  không thấy mã, sai đối tác, hoặc ống nhiều việc ⇒ **hàng ghép tay**, không đoán.

## Đối tác & vai PARTNER
- Đối tác lưu theo `doi_tac_id`. Đơn chụp id lúc chỉ định; đổi tên/ngưng không đổi đơn cũ;
  việc dở của đối tác đã ngưng vẫn hiện.
- `doi_tac_service.py` và router `doi_tac.py` **đóng băng**: không thêm hàm/cửa. Cần sửa hành vi
  cũ ⇒ gọi sang `services/xet_nghiem/`. Test đếm dòng/cửa chỉ được giảm.
- Hẹn trả: đặt ở cặp (đối tác, dịch vụ) hoặc mặc định đối tác — **một nơi**; chụp thành ngày cụ thể vào mẫu lúc lấy.
