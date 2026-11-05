# ADR-0015 — Xét nghiệm đối tác: thu hộ sổ riêng, thu xong mới lấy mẫu, kết quả về từ Drive

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-05 |
| **Liên quan** | ADR-0003 (bất biến đồng thời), ADR-0014 (nguồn thu bất biến), `docs/KE-HOACH-XET-NGHIEM-DOI-TAC.md`, migration `20260928000091` (sổ `doi_tac_thanh_toan`), `20260920000005` (xác nhận tệp) |

## Context

Bàn đối tác làm từ 27/09 đến 16/10 giả định đối tác đăng nhập (vai `PARTNER`), tự bấm
Nhận mẫu, Trả kết quả, tự ghi "đã thu tiền khách". Thực tế: đối tác không vào hệ thống;
nhân viên phòng khám ở bàn xét nghiệm làm mọi bước; đối tác chỉ gửi tệp qua Google Drive.
Tuyền dựng bản mẫu giao diện mới và chốt sáu câu nghiệp vụ ngày 05/11/2026.

## Decision

1. **Thu hộ là sổ ghi nhận riêng.** `doi_tac_thanh_toan` (mở rộng TM + CK, mã GD, ảnh CK,
   giá gợi ý) là nơi duy nhất ghi tiền khách trả cho đối tác. Không dòng nào vào
   `payment_cycle`, `payment`, `payment_bill_line`, két, doanh thu. Báo cáo cuối ngày chỉ
   hiện để tham khảo. Két chung ở lễ tân và quyết toán với đối tác: quyết định sau.
2. **Ngoại lệ của "làm trước, thu sau" (30/09) và "thu hộ không chặn việc nào khác" (16/10):**
   với việc của đối tác, **nút Lấy mẫu** chỉ mở khi đã có ghi nhận thu hộ còn hiệu lực
   (bất kỳ số tiền, kể cả CK chưa thấy tiền) **hoặc** Quản lý cho qua kèm lý do. Không chặn
   chỉ định, khám, thu ngân hay bất kỳ việc nào khác. Lý do: tiền này là của đối tác, phòng
   khám không ứng trước cho bên thứ ba.
3. **Mã mẫu theo ống**, duy nhất theo phòng khám, chữ số kiểm Damm, cấp ở Postgres lúc lấy
   mẫu. Một ống phục vụ nhiều chỉ định cùng một đối tác (ép bằng khoá ngoại ghép).
4. **Kết quả về hiện ngay** cho bác sĩ và CSKH. Luật DB cấm gửi khách tệp đối tác chưa xác
   nhận **giữ nguyên**; nút gửi là "Đúng người, gửi" (xác nhận + gửi một giao dịch).
5. **Đối tác không đăng nhập.** Hệ thống đọc thư mục Drive của phòng khám bằng tài khoản dịch
   vụ Google (chỉ đọc, Changes API 3 phút/lần, chống trùng theo `file_id` + `md5`, nhịp sống
   > 1 giờ thì cảnh báo). Dự phòng: Gmail phòng khám OAuth chỉ đọc. Cấm link công khai. Luôn
   có đường nhân viên tải tay. Lệnh phía đối tác tắt dần, đếm bằng test "chỉ được giảm".
6. **Giá là gợi ý.** Nhân viên ghi số khách thật trả; sổ lưu cả giá gợi ý lúc ghi.
7. **Trạng thái không lưu**, tính bằng một hàm `trang_thai_xet_nghiem()` từ các sự việc
   (thu, mẫu, tệp, gửi). **Hoàn tác là lệnh bù theo bước**, có lý do và sự kiện; bước do hệ
   thống làm (tệp về) không hoàn tác mà Từ chối tệp.

## Consequences

- `doi_tac_service.py` và router `doi_tac.py` bị đóng băng; code mới ở `services/xet_nghiem/`.
- Có thêm 6 bảng nhỏ thuộc một module mới; `service_order` không thêm cột.
- Một kết nối ra ngoài (Google Drive) với dữ liệu sức khoẻ: khoá chỉ trong `.env.prod`,
  thư mục chỉ chia sẻ cho đúng đối tác và tài khoản dịch vụ.
- Khi làm két chung ở lễ tân: phải mở lại ADR này để quyết tiền mặt thu hộ có vào két không.
