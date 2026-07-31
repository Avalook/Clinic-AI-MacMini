# Catalogue thiết kế ClinicAI — 44 màn/asset

Trích tự động từ 45 file thiết kế ngày 01/08/2026.

**Đây là bản ghi những gì THIẾT KẾ nói, không phải bản đã chốt để xây.** Nhiều màn đòi
dữ liệu hệ thống chưa có (bảng quầy, called_at, ICD, chữ ký số…), và các bộ trạng thái
trong thiết kế mâu thuẫn nhau — riêng lớp CSKH dùng tới ba bộ khác nhau. Bộ trạng thái
đã chốt của hệ là 8 cái trong `src/dashboard/lib/work-item-status.ts`; mọi màn phải quy về đó.

Bộ ảnh có HAI thế hệ: **V1** (24 màn) và **V2** (20 màn, mới hơn — topbar có chuông + avatar).
Khi hai bản mâu thuẫn, lấy shell và ngôn ngữ trạng thái của V2.

| Vai trò | Số màn |
|---|---|
| PATIENT_DISPLAY | 2 |
| CASHIER | 7 |
| PHARMACIST | 6 |
| ULTRASOUND | 7 |
| DOCTOR | 7 |
| RECEPTION | 7 |
| CSKH | 7 |
| TRUONG_CA | 1 |

## PATIENT_DISPLAY

### Phòng chờ – Thông báo lượt khám (màn hình TV công cộng)
`ChatGPT_Image_10_45_18_24_thg_7_2026_(2).jpg` · V2 · PATIENT_DISPLAY (không đăng nhập; phục vụ bệnh nhân ở khu chờ)  
Kiosk/TV 16:9 không sidebar: header (logo + tiêu đề + đồng hồ 09:30 / Thứ Tư 13/05/2026) + hàng trên 3 khối (Khám bác sĩ | ĐANG GỌI cỡ lớn | chú giải trạng thái) + hàng dưới 5 thẻ khu (SA1, SA2, SA3, Xét nghiệm, Thanh toán) + footer nhắc nhở/WiFi/hotline

Màn hình lớn hiển thị số đang gọi và hàng đợi theo từng khu (khám bác sĩ, siêu âm SA1–SA3, xét nghiệm, thanh toán) để bệnh nhân tự theo dõi lượt của mình.

- **Hành động:** (chỉ hiển thị – không có thao tác của người dùng; cập nhật realtime khi gọi số)
- **Dữ liệu cần:** hàng đợi gọi số theo khu/phòng (đang gọi, tiếp theo, đang chờ), ánh xạ số thứ tự ↔ phòng/quầy, đồng hồ + ngày hệ thống, cấu hình khu hiển thị (số lượng thẻ, số dòng mỗi cột), sự kiện realtime khi gọi số
- **Ghi chú:** Thế hệ khó xác định tuyệt đối vì là màn TV nên không có badge V2/topbar; logo dùng bản 'CONNECTED CLINIC WORKFLOW' giống V2 và tông màu trùng bộ V2 → xếp V2 với độ tin cậy trung bình. Hoàn toàn read-only, không map node kernel (nó phản chiếu trạng thái gọi số của các work_item khám/SA/XN/thanh toán). Lưu ý riêng tư: chỉ hiện mã số, không hiện tên bệnh nhân — đúng. Số hiển thị dùng tiền tố theo khu, khác với PKO-062 (số khám phụ khoa) ở ảnh 3, cần thống nhất quy ước đánh số.

### Phòng chờ — Thông báo lượt khám (màn hình TV công cộng)
`ChatGPT_Image_12_01_26_24_thg_7_2026_(8).jpg` · asset · Bệnh nhân / khách chờ (display-only, không đăng nhập; dữ liệu do RECEPTION/hệ thống hàng đợi đẩy)  
Toàn màn hình ngang (16:9): header thương hiệu + đồng hồ/ngày | 5 cột thẻ khu vực song song | footer hướng dẫn 3 mục + dòng branding

Bảng điện tử treo tại phòng chờ hiển thị số đang gọi, số tiếp theo và hàng chờ theo từng khu vực dịch vụ.

- **Node kernel:** none (bề mặt hiển thị của hàng đợi; gián tiếp gắn LUOTKHAM-01 tiếp nhận và các node dịch vụ siêu âm/xét nghiệm)
- **Hành động:** none (màn hình chỉ đọc)
- **Dữ liệu cần:** queue_number đang gọi theo từng khu vực/phòng (kèm tên phòng khi có nhiều phòng cùng khu), số tiếp theo + N số đang chờ (9) theo thứ tự gọi của từng khu vực, danh sách khu vực/máy siêu âm đang hoạt động (SA1–SA3), tiền tố số theo loại dịch vụ (C/SA/X), đồng hồ + ngày hệ thống, kênh realtime để cập nhật tức thời khi gọi số (Supabase realtime)
- **Ghi chú:** Đây là ASSET trình chiếu chứ không phải màn hình thao tác — tỉ lệ artboard rộng 16:9, không có chrome ứng dụng. LỖI DỮ LIỆU trong mock cần sửa khi dựng thật: các số trùng lặp/không nhất quán giữa các cột — SA031 vừa 'đang gọi' ở SA2 vừa nằm trong hàng chờ SA1; SA033–SA035 xuất hiện cả ở SA1 và SA2; SA036 xuất hiện ở cả SA2 và SA3; SA024–SA028 lặp ở SA3 dù SA025 đang gọi ở SA1. Số thứ tự phải duy nhất theo ngày + theo clinic (khớp quyết định 'daily queue number thuộc một clinic'). Không có KPI.

## CASHIER

### Lịch sử giao dịch
`image_14.jpg` · V1 · CASHIER (Thu ngân) — tra cứu, có thể mở rộng TRUONG_CA/MANAGEMENT  
2 cột: sidebar | bảng giao dịch (giữa, rộng) | drawer chi tiết giao dịch bên phải (có nút X đóng)

Tra cứu giao dịch, biên nhận, điều chỉnh và hoàn tiền theo khoảng thời gian và bộ lọc.

- **Hành động:** In biên nhận, Tải chứng từ, Xem bản ghi (nút chính)
- **Dữ liệu cần:** bảng giao dịch (payment/refund) có phân trang server-side + filter theo ngày/loại/phương thức/trạng thái, liên kết giao dịch ↔ lượt khám ↔ bệnh nhân, metadata thanh toán: ngân hàng, 4 số cuối, mã tham chiếu, idempotency key, số biên nhận, audit log per-transaction (4 sự kiện, timestamp tới giây, người thực hiện), KPI: giao dịch hôm nay, đã xác nhận, cần đối chiếu, hoàn tiền
- **Ghi chú:** Màn tra cứu, không gắn node kernel. Quy tắc append-only (không sửa giao dịch đã xác nhận, chỉ tạo giao dịch điều chỉnh) là ràng buộc DB/service — nên enforce ở FastAPI + constraint, không chỉ ẩn nút ở UI. Idempotency key hiển thị dạng masked.

### Thanh toán khám & dịch vụ
`image_13.jpg` · V1 · CASHIER / CASHIER_DV (Thu ngân)  
3 cột: sidebar | danh sách chờ thanh toán (trái) + nghĩa vụ thanh toán & form thu tiền (giữa) | thông tin lượt khám + lịch sử xử lý (phải)

Ghi nhận giao dịch thanh toán khám–dịch vụ của một lượt khám và phát hành biên nhận.

- **Node kernel:** LUOTKHAM-14, LUOTKHAM-13, LUOTKHAM-15
- **Hành động:** Lưu chờ đối chiếu, In bảng kê, Xác nhận thanh toán (nút chính)
- **Dữ liệu cần:** hàng đợi lượt khám chờ thanh toán + thời gian chờ + cờ đủ điều kiện/bị chặn, payment obligations theo nhóm (xét nghiệm / thuốc / khám & dịch vụ) + trạng thái + số biên nhận, chi tiết dòng dịch vụ (đơn giá, SL, thành tiền, giảm giá), phương thức thanh toán khả dụng, mã tham chiếu giao dịch + idempotency key, timeline work_item của lượt khám (đã xong / đang làm / chưa tới), SĐT bệnh nhân cho SMS/Zalo, trạng thái đối soát của lượt khám
- **Ghi chú:** Timeline bên phải chính là view work_item của kernel — nên bind trực tiếp vào bảng work_item thay vì hardcode 7 bước. Mốc 'Phát thuốc' xuất hiện trong timeline nhưng không nằm trong 7 bước xương sống đã nêu → cần xác nhận node tương ứng. Ghi nhận idempotency là yêu cầu backend (FastAPI), không phải UI.

### Thanh toán nghĩa vụ khám & dịch vụ
`ChatGPT_Image_10_45_22_24_thg_7_2026_(5).jpg` · V2 · CASHIER_DV (Thu ngân dịch vụ)  
3 cột: sidebar THU NGÂN | workspace (banner 3 nghĩa vụ + hồ sơ BN + bảng chi tiết khoản thu) | panel thu tiền (phương thức, tiền khách đưa, lịch sử thanh toán, thông tin lượt khám)

Thu tiền cho nghĩa vụ 'Khám & dịch vụ' của một lượt khám, tách biệt với nghĩa vụ xét nghiệm và thuốc.

- **Node kernel:** LUOTKHAM-14
- **KPI:** Số tiền cần thu 550.000đ · Tiền thừa 50.000đ · Tổng theo nghĩa vụ: 650.000 / 245.000 / 550.000đ
- **Hành động:** Xác nhận thu tiền (F9), In tạm tính (F8), Thêm giảm giá, Xem chi tiết từng nghĩa vụ, Xem chi tiết lượt khám
- **Dữ liệu cần:** visit/encounter (mã, thời gian, bác sĩ, khoa phòng), patient (mã BN, tên, DOB, giới, SĐT), 3 payment_obligation theo loại + trạng thái + số tiền, order/service_item lines: mã dịch vụ, tên, người thực hiện, đơn giá, SL, thành tiền, discount lines, payment_transaction history (thời gian, thu ngân, phương thức, số tiền, trạng thái), danh mục phương thức thanh toán
- **Ghi chú:** Đây là màn thao tác thu tiền, không phải dashboard — không nên nhồi KPI. Mô hình 3 nghĩa vụ tách rời là điểm cốt lõi cần giữ. Ngày hiển thị 14/05/2026 lệch với các ảnh khác (13/05, 16/01) — dữ liệu demo không đồng bộ. Nút 'Đang thanh toán' trên card thứ 3 là link chứ không phải trạng thái chuẩn trong bộ 8 trạng thái.

### Thanh toán nghĩa vụ khám & dịch vụ
`ChatGPT_Image_12_01_26_24_thg_7_2026_(7).jpg` · V2 · CASHIER_DV (Thu ngân dịch vụ) — user hiển thị: Phạm Mỹ Linh, Thu ngân  
3 vùng: sidebar trái (4 mục Thu ngân) | cột giữa rộng (hàng 3 thẻ nghĩa vụ trên cùng + form thu tiền) | panel phải (thông tin lượt khám, tổng quan nghĩa vụ, lịch sử thanh toán)

Thu tiền cho một nghĩa vụ (khám & dịch vụ) trong một lượt khám, tách bạch với nghĩa vụ xét nghiệm và thuốc.

- **Node kernel:** LUOTKHAM-14 (thanh toán), LUOTKHAM-13 (đối soát chi phí — mục sidebar 'Đối soát chi phí')
- **Hành động:** Xác nhận thu tiền (F9), In tạm tính (F8), Xem chi tiết từng nghĩa vụ, Xem tất cả lịch sử giao dịch, Chọn phương thức thanh toán
- **Dữ liệu cần:** visit/encounter: mã lượt khám, giờ khám, bác sĩ khám, khoa phòng, patient: họ tên, ngày sinh + tuổi tính sẵn, giới tính, SĐT, danh sách nghĩa vụ thanh toán của lượt khám (loại: xét nghiệm / thuốc / khám & dịch vụ) kèm trạng thái + số tiền, per-nghĩa vụ: tổng tiền, đã thu trước, còn phải thu, payment_transaction history theo nghĩa vụ (thời điểm, phương thức, số tiền, trạng thái), danh mục phương thức thanh toán khả dụng, tính tiền thừa = khách đưa − còn phải thu (nên tính ở backend/FE thuần hiển thị)
- **Ghi chú:** Không thấy badge 'V2' trên artboard nhưng topbar có chuông + avatar + tỉ lệ hẹp hơn → xếp V2. Điểm mạnh: mô hình nhiều 'nghĩa vụ' trên cùng 1 lượt khám, mỗi nghĩa vụ trạng thái độc lập (kể cả 'Thanh toán thất bại'). Điểm cần soát: trạng thái card ('Thanh toán thất bại', 'Đã thanh toán, chờ nhà thuốc', 'Đang thu tiền') là trạng thái nghiệp vụ payment, KHÔNG nằm trong bộ 8 trạng thái work_item đã chốt — cần map rõ sang node LUOTKHAM-14. Panel phải lặp lại 3 con số của cột giữa (dư thừa). Không có KPI/thống kê nào trên màn này.

### Đối soát chi phí
`image_12.jpg` · V1 · CASHIER (Thu ngân)  
3 cột: sidebar THU NGÂN | danh sách lượt khám (trái) + bảng đối soát chi tiết (giữa) | panel chi tiết sai lệch (phải)

So khớp dịch vụ đã thực hiện, thuốc đã cấp và các nghĩa vụ tài chính trước khi cho phép đóng lượt khám.

- **Node kernel:** LUOTKHAM-13, LUOTKHAM-14, LUOTKHAM-15
- **Hành động:** Giao việc xử lý, Lưu ghi chú, Xác nhận đã đối soát (nút chính, đang disabled vì còn sai lệch)
- **Dữ liệu cần:** visit + patient (mã BN, mã lượt khám, tuổi/giới, bác sĩ điều trị, thời gian khám), charge/billing lines theo nguồn: LIS, Pharmacy, EMR, PACS, Lab Ext. (phải thu, đã thu, trạng thái thực hiện), biên bản sai lệch/discrepancy: giá hệ thống vs nguồn ngoài, thời gian, trạng thái, mã tham chiếu ngoài, đếm KPI: chờ đối soát, có sai lệch, đã cân bằng, chặn đóng lượt, danh mục lý do ngoại lệ + danh sách người chịu trách nhiệm, checklist rule đối soát, quyền/role của user hiện tại
- **Ghi chú:** Workspace thu_ngan_dong_luot. Không có badge V2 và topbar thiếu chuông/avatar-kiểu-V2 → xếp V1. Trạng thái hiển thị dùng nhãn nghiệp vụ (Đủ dữ liệu, Chờ nguồn ngoài, 2 sai lệch) chứ không dùng 8 trạng thái chuẩn (ready/blocked/...) — cần map lại. Nút chính bị disable là đúng logic chặn đóng lượt.

### Đối soát chi phí
`ChatGPT_Image_10_45_24_24_thg_7_2026_(7).jpg` · V2 · CASHIER / Thu ngân – Checkout  
3 cột: sidebar THU NGÂN/CHECKOUT + HỖ TRỢ | workspace (thông tin lượt khám, banner chặn, thanh điều kiện, 3 card nghĩa vụ, tiêu chí check-out) | panel Tổng quan nghĩa vụ + Trạng thái tổng thể + Hành động gợi ý + Nhật ký đối soát

Đối soát 3 nghĩa vụ (xét nghiệm, thuốc, khám & dịch vụ) và các xác nhận bàn giao trước khi cho phép check-out lượt khám.

- **Node kernel:** LUOTKHAM-13
- **KPI:** Tổng số nghĩa vụ 3 · Đã hoàn tất 1 / Chưa hoàn tất 2 · Tổng số tiền 2.320.000đ · Đã thanh toán 450.000đ · Còn lại 1.870.000đ · Tiến độ điều kiện 1/3
- **Hành động:** Thanh toán lại xét nghiệm, Liên hệ nhà thuốc, Xem chi tiết lỗi, Xem hồ sơ, Làm mới (refresh cập nhật lần cuối)
- **Dữ liệu cần:** visit + appointment (mã lịch hẹn, giờ, bác sĩ, trạng thái), 3 payment_obligation: mã giao dịch, tham chiếu, đơn vị thực hiện, trạng thái thanh toán, cờ xác nhận, số tiền, ghi chú, tổng hợp tài chính lượt khám (tổng/đã thu/còn lại), blocking reasons + gợi ý hành động, audit log đối soát (thời gian, actor, hành động)
- **Ghi chú:** Trạng thái nghĩa vụ hiển thị bằng tiếng Anh raw (PaymentFailed, Pending, Completed) trộn với nhãn tiếng Việt ở nơi khác → cần thống nhất; Completed/Pending map được vào bộ 8 nhưng PaymentFailed thì không (gần với blocked). Lỗi chính tả trong ảnh: 'Chủ sở bhực hưa/thực hiện', 'Đơn vị thực hiện' lặp 2 lần trong cùng card, 'Đno vị thực hiện'. Không có nút hành động chính đi tiếp (chuyển sang check-out) — chỉ bị chặn; cần bổ sung CTA khi đủ điều kiện.

### Đối soát chi phí
`ChatGPT_Image_12_01_25_24_thg_7_2026_(5).jpg` · unknown · CASHIER / thu ngân — user hiển thị: Phạm Mỹ Linh, Thu ngân  
2 cột chính: nội dung trung tâm (thông tin lượt khám + banner chặn + điều kiện hoàn tất + 3 card nghĩa vụ + tiêu chí chuyển check-out) | cột phải (Tổng quan nghĩa vụ, Trạng thái tổng thể, Nhật ký đối soát); kèm sidebar trái

Thu ngân đối soát 3 nghĩa vụ (xét nghiệm, thuốc, khám & dịch vụ) và xác nhận bàn giao trước khi lượt khám được chuyển sang check-out.

- **Node kernel:** LUOTKHAM-13 — đối soát chi phí (node chính, workspace thu_ngan_dong_luot), LUOTKHAM-14 — thanh toán (các giao dịch LAB/MED/SVC), LUOTKHAM-15 — đóng lượt khám (bước kế tiếp bị chặn)
- **KPI:** Điều kiện hoàn tất: 1/3 hoàn tất · Tổng số nghĩa vụ: 3 · Đã hoàn tất: 1 · Chưa hoàn tất: 2 · Tổng số tiền: 2.060.000 đ · Đã thanh toán: 1.410.000 đ · Còn lại: 650.000 đ
- **Hành động:** Thanh toán lại (nghĩa vụ xét nghiệm thất bại), Thanh toán lại xét nghiệm (hành động gợi ý cột phải), Liên hệ nhà thuốc, Xem chi tiết lỗi, Chuyển sang check-out (bị khóa khi còn nghĩa vụ chưa đạt)
- **Dữ liệu cần:** Lượt khám: mã lịch hẹn, giờ hẹn, bác sĩ, trạng thái lượt, Bệnh nhân: tên, ngày sinh, tuổi, giới, SĐT, Danh sách nghĩa vụ tài chính theo nhóm (xét nghiệm / thuốc / khám & dịch vụ): mã giao dịch, đơn vị thực hiện, chủ sở hữu doanh thu, số tiền, Trạng thái thanh toán từng nghĩa vụ (đã thanh toán / thất bại / chờ) + trạng thái xác nhận bàn giao, Tổng hợp tiền: tổng, đã thanh toán, còn lại, Trạng thái chặn tổng thể + danh sách lý do chặn có cấu trúc, Nhật ký/audit log đối soát (thời điểm, actor người hay hệ thống, nội dung), Quy tắc tiêu chí chuyển check-out (3 điều kiện)
- **Ghi chú:** Không có badge 'V2'; topbar có chuông (badge 3) + avatar. Cảnh báo dữ liệu: bệnh nhân ở đây là 'Nguyễn Thị Hằng' (12/06/1990, 35 tuổi) trong khi ảnh (3) và (4) dùng 'Nguyễn Thị Hương' (1988, 36 tuổi) — cùng SĐT 0901 234 567, dễ nhầm là một người; nên thống nhất persona demo. Số tiền thuốc 860.000 đ khớp với ảnh (6) → hai màn này là cùng một luồng nghĩa vụ thuốc. Card có cột 'Chủ sở hữu' (Phòng Xét nghiệm / Nhà thuốc - CSI / Phòng khám 1) hàm ý mô hình chia doanh thu theo đơn vị sở hữu — cần chốt trong schema thanh toán in-house. 'Bị chặn' map sang kernel 'blocked'.

## PHARMACIST

### Chuẩn bị thuốc
`image_9.jpg` · V2 · Dược sĩ (NHÀ THUỐC)  
Sidebar + topbar + 4 KPI + 3 cột: Danh sách phiếu (nhóm theo trạng thái) | Phiếu chuẩn bị thuốc (bảng nhập SL thực cấp) | Kiểm tra trước bàn giao (checklist 6 bước + thông tin xử lý)

Đối chiếu, soạn và kiểm tra thuốc theo đơn đã được phép cấp trước khi bàn giao.

- **KPI:** Đang chuẩn bị: 5 · Chờ kiểm tra: 4 · Thiếu thuốc: 2 · Sắp quá SLA: 3
- **Hành động:** Xác nhận đã chuẩn bị, Lưu nháp, Báo thiếu thuốc
- **Dữ liệu cần:** Phiếu chuẩn bị theo đơn + trạng thái (đang soạn/chờ kiểm tra/thiếu thuốc), Dòng thuốc kê: tên thương mại, hoạt chất, hàm lượng, quy cách, SL kê, SL thực cấp nhập tay + chênh lệch tính toán, Lô (LOT) + hạn dùng từ kho, Checklist kiểm tra 6 mục và trạng thái từng mục, Thời gian bắt đầu/đang thực hiện, người thực hiện, Ngưỡng SLA sắp quá hạn
- **Ghi chú:** Có ổ khóa trên cột SL kê và Lô/Hạn dùng — read-only, phù hợp nguyên tắc dược sĩ không đổi thuốc/liều. Checklist 6 bước là ứng viên tự nhiên để mô hình hóa thành sub-node kernel (AND gate: 6 mục đều xong mới cho 'Xác nhận đã chuẩn bị'). Không có chuông thông báo trên topbar ở ảnh này (chỉ avatar) — khác nhẹ với image_8/10/11.

### Lịch sử bàn giao thuốc (Đã bàn giao)
`image_10.jpg` · V2 · Dược sĩ (NHÀ THUỐC)  
Sidebar + topbar + 4 KPI + 3 cột: Bệnh nhân (search + filter) | Lịch sử cấp thuốc của bệnh nhân (khoảng ngày + list bản ghi + phân trang) | Chi tiết bàn giao

Tra cứu bản ghi thuốc đã thực cấp cho từng bệnh nhân (read-only, bất biến).

- **KPI:** Bàn giao hôm nay: 28 · Cấp đủ: 24 · Cấp một phần: 4 · Tổng bản ghi: 1.846
- **Hành động:** Xem chi tiết, Tải biên nhận, In hướng dẫn
- **Dữ liệu cần:** Danh mục bệnh nhân + số lần cấp thuốc, Bản ghi cấp phát (MDR) bất biến: mã, thời điểm, kết quả cấp đủ/một phần, Dòng thuốc đã cấp: hàm lượng, dạng bào chế, SL kê vs SL thực cấp, Người nhận thuốc, phương thức bàn giao, ghi chú, Trạng thái tư vấn liên kết, Mốc thời gian 4 bước xử lý (audit trail), Thống kê ngày: bàn giao hôm nay, cấp đủ, cấp một phần, tổng bản ghi
- **Ghi chú:** Màn hình read-only/audit — đúng KPI, không có hành động ghi. Timeline 4 mốc ở đây chính là chuỗi node nhà thuốc: soạn → kiểm tra → tư vấn → bàn giao; nên hiện thực hóa thành 4 node kernel để 3 màn kia sinh ra bản ghi này.

### Nhà thuốc & cấp thuốc
`ChatGPT_Image_10_45_23_24_thg_7_2026_(6).jpg` · V2 · Dược sĩ (nhà thuốc)  
3 cột: sidebar NHÀ THUỐC (Đơn chờ cấp 12 / Chuẩn bị thuốc 8 / Đã bàn giao / Tư vấn dùng thuốc) | list đơn thuốc (search + filter + tab) | workspace chi tiết đơn + panel Thao tác/Thông tin đơn

Quản lý hàng đợi đơn thuốc chờ cấp và chạy quy trình 5 bước chuẩn bị → bàn giao → hướng dẫn dùng thuốc, chặn khi nghĩa vụ thanh toán thuốc chưa xong.

- **KPI:** Đơn chờ cấp 12 · Chuẩn bị thuốc 8 · Chờ thanh toán thuốc 4 · Đã sẵn sàng 5 · Quá hạn 2 · Tổng tiền thuốc 860.000đ
- **Hành động:** Chuẩn bị thuốc, Xác nhận thanh toán thuốc, Bàn giao thuốc, Hướng dẫn sử dụng, Liên hệ thu ngân, Lưu ghi chú
- **Dữ liệu cần:** prescription (mã, ngày kê, bác sĩ kê, nơi khám, hình thức ngoại trú), patient (tên, DOB, giới, SĐT, địa chỉ), prescription_line: thuốc, hàm lượng, dạng bào chế, liều dùng, SL kê, SL cấp, inventory/tồn kho theo thuốc, 3 payment_obligation của lượt khám (khám / thuốc / dịch vụ khác), work_item tiến trình 5 bước cấp phát + trạng thái, ghi chú tư vấn dược sĩ, file đính kèm đơn thuốc
- **Ghi chú:** Đây là quy trình nhà thuốc, chưa map vào 7 node xương sống LUOTKHAM — nếu đưa vào kernel cần định nghĩa node riêng (chuỗi cấp phát thuốc). Badge dùng nhãn tiếng Việt tự do ('Đang chuẩn bị', 'Sẵn sàng bàn giao', 'Chưa thể cấp') không trùng bộ 8 trạng thái đã chốt → cần map: Đang chuẩn bị=in_progress, Sẵn sàng bàn giao=ready, Chưa thể cấp/Chờ thanh toán=blocked, Quá hạn=overdue. Ngày 13/05/2026, avatar dùng ảnh thật (khác 3 ảnh còn lại).

### Nhà thuốc & cấp thuốc
`ChatGPT_Image_12_01_25_24_thg_7_2026_(6).jpg` · unknown · Dược sĩ (nhà thuốc) — user hiển thị: Hoàng Thị Mai, Dược sĩ  
2 cột: danh sách đơn thuốc chờ cấp (card list, có sidebar điều hướng bên trái) | panel chi tiết đơn thuốc chiếm phần lớn màn hình

Dược sĩ quản lý đơn thuốc chờ cấp, theo dõi quy trình 5 bước cấp phát và chỉ bàn giao thuốc khi nghĩa vụ thanh toán thuốc đã hoàn tất.

- **Node kernel:** none — cấp phát thuốc là node ngoài 7 bước xương sống, LUOTKHAM-14 — thanh toán (bước 3 'Xác nhận thanh toán thuốc' phụ thuộc trực tiếp), LUOTKHAM-13 — đối soát chi phí (xác nhận bàn giao thuốc là đầu vào cho card 'Thuốc' ở ảnh (5))
- **KPI:** Đơn thuốc chờ cấp: 12 · Chuẩn bị thuốc: 8 · Đã bàn giao: 5 · Tư vấn dùng thuốc: 7 · Tổng tiền thuốc: 860.000 đ · Hiển thị 1–7 trong 12
- **Hành động:** Liên hệ thu ngân (khi thuốc chưa thanh toán), Làm mới trạng thái thanh toán, Chuẩn bị thuốc / tiến bước trong quy trình 5 bước, Bàn giao thuốc (khóa cho tới khi xác nhận thanh toán), Nhập ghi chú tư vấn dược sĩ, Tìm kiếm / lọc đơn thuốc
- **Dữ liệu cần:** Hàng đợi đơn thuốc theo trạng thái (chờ cấp / chuẩn bị / đã bàn giao / tư vấn), Đơn thuốc: mã RX, thời gian kê, bác sĩ kê đơn, liên kết lượt khám, Bệnh nhân: tên, ngày sinh, tuổi, giới, SĐT, địa chỉ, Trạng thái 3 nhóm nghĩa vụ thanh toán (khám bệnh / thuốc / dịch vụ khác) + số tiền, Chi tiết dòng thuốc: tên, hàm lượng, dạng bào chế, liều dùng, SL kê, SL cấp, thành tiền, Tồn kho theo thuốc (để kiểm tra đủ hàng trước khi cấp), Trạng thái 5 bước quy trình cấp phát + mốc thời gian, khóa bước theo điều kiện thanh toán, Ghi chú tư vấn dược sĩ (tối đa 500 ký tự)
- **Ghi chú:** Không có badge 'V2'; topbar có chuông (badge 3) + avatar. LỖI SỐ LIỆU trong mockup: tổng tiền thuốc ghi 860.000 đ nhưng 3 dòng cộng lại chỉ 160.000 đ (120k+24k+16k) — con số 860.000 đ được ép cho khớp ảnh (5), cần sửa dữ liệu demo. Ghi chú luồng: bước 3 'Xác nhận thanh toán thuốc' ở đây và 'Chờ nhà thuốc xác nhận bàn giao' ở ảnh (5) là quan hệ hai chiều giữa nhà thuốc và thu ngân — nên mô hình bằng phụ thuộc FS trong kernel thay vì hai trạng thái tự quản. Trạng thái 'Đang thực hiện' map sang kernel 'in_progress', các bước khóa map sang 'blocked'.

### Tư vấn dùng thuốc
`image_11.jpg` · V2 · Dược sĩ (NHÀ THUỐC)  
Sidebar + topbar + 4 KPI + 3 cột: Danh sách chờ tư vấn (tabs Tất cả/Ưu tiên/Thường) | Nội dung tư vấn (theo từng thuốc, checkbox) | Panel phải: thông tin người bệnh, đơn thuốc, dị ứng, tiến độ, người xử lý

Hướng dẫn người bệnh cách dùng thuốc và ghi nhận đã tư vấn trước khi bàn giao.

- **KPI:** Chờ tư vấn: 6 · Đang tư vấn: 2 · Cần lưu ý: 3 · Hoàn tất hôm nay: 25
- **Hành động:** Xác nhận đã tư vấn & bàn giao, In hướng dẫn, Lưu nháp, Xem hồ sơ bệnh nhân
- **Dữ liệu cần:** Hàng đợi tư vấn + mức ưu tiên, Nội dung tư vấn chuẩn theo từng thuốc (5 nhóm nội dung) — thư viện knowledge base thuốc, Chỉ định gốc của bác sĩ (read-only), Dị ứng thuốc + thuốc đang dùng của bệnh nhân, Trạng thái phiếu chuẩn bị (3/3 mặt hàng), Checkbox tiến độ tư vấn (7/8) + xác nhận người bệnh, Ghi chú tự do ≤500 ký tự, Người xử lý + thời điểm
- **Ghi chú:** Đây là bước cuối trước bàn giao — nút gộp 'Xác nhận đã tư vấn & bàn giao' đóng luôn node bàn giao, sinh bản ghi MDR ở image_10. Tiến độ 7/8 = 15 checkbox nội dung + 3 xác nhận nhưng hiển thị 7/8 → công thức đếm chưa rõ, cần chốt lại quy tắc tính. Topbar có chuông + avatar (dấu hiệu V2), không thấy badge chữ 'V2' hiển thị trên artboard nhưng bố cục 1500px và cấu trúc topbar khớp thế hệ V2 của 4 ảnh này.

### Đơn thuốc chờ cấp
`image_8.jpg` · V2 · Dược sĩ (NHÀ THUỐC)  
Sidebar NHÀ THUỐC (4 mục) + topbar (ngày, giờ 10:20, chuông, avatar Lê Hoàng Minh/Dược sĩ) + hàng 4 KPI + 2 cột: danh sách đơn (tab Tất cả/Đủ điều kiện/Bị chặn + search) | panel chi tiết đơn

Tiếp nhận đơn thuốc hợp lệ và xác định đơn nào đủ điều kiện để bắt đầu chuẩn bị.

- **KPI:** Chờ cấp: 12 · Đủ điều kiện: 9 · Đang bị chặn: 3 · Quá SLA: 2
- **Hành động:** Bắt đầu chuẩn bị, Tạm giữ, Xác minh đơn (từ item trong list), Mở chi tiết đơn
- **Dữ liệu cần:** Hàng đợi đơn thuốc theo ngày + trạng thái (chờ cấp/đủ điều kiện/bị chặn/quá SLA), Hồ sơ bệnh nhân rút gọn (tên, năm sinh, giới, tuổi, mã BN), Đơn thuốc: mã RX, phiên bản, bác sĩ kê + mã bác sĩ, thời điểm kê, Dòng thuốc: tên, liều/cách dùng, số lượng, Tồn kho theo mặt hàng thuốc, Cờ điều kiện cấp phát (hợp lệ, đúng BN, được phép chuẩn bị + thời điểm cho phép, đủ tồn kho), Sự kiện tiến trình đơn (audit: ai, lúc nào), Đồng hồ chờ / ngưỡng SLA
- **Ghi chú:** Badge trạng thái theo đơn: Được phép chuẩn bị / Chờ thanh toán thuốc / Cần xác minh đơn — đây là trạng thái nghiệp vụ nhà thuốc, KHÔNG trùng 8 trạng thái hiển thị kernel; cần map rõ. Node kernel cho nhà thuốc chưa có trong bộ 7 bước xương sống (LUOTKHAM-01..15) — nhiều khả năng thuộc nhóm node cấp phát thuốc riêng, cần bổ sung định nghĩa. 'Chờ thanh toán thuốc' cho thấy phụ thuộc FS với node thanh toán (LUOTKHAM-14).

## ULTRASOUND

### Báo cáo siêu âm đã ký
`image_7.jpg` · V2 · TKYK / Thư ký siêu âm (tra cứu & phát hành); đọc bởi CSKH, RECEPTION, bác sĩ  
3 cột: danh sách bệnh nhân | lịch sử báo cáo của bệnh nhân được chọn | panel phải chi tiết báo cáo đã ký

Tra cứu lịch sử kết quả siêu âm đã được bác sĩ ký theo từng bệnh nhân, xem bản đã phát hành và in/tải/gửi cho bệnh nhân.

- **KPI:** Đã ký hôm nay = 18 · Đã phát hành = 14 · Chưa gửi bệnh nhân = 4 · Tổng báo cáo lưu trữ = 1.286
- **Hành động:** In báo cáo, Tải xuống, Xem bản PDF, Lọc theo khoảng ngày + dịch vụ, Chọn bệnh nhân / mở chi tiết một báo cáo
- **Dữ liệu cần:** kho báo cáo đã ký theo bệnh nhân (không giới hạn ngày hiện tại → cần index theo patient_id + ngày), chữ ký số: bác sĩ ký, timestamp, trạng thái hợp lệ, phiên bản bản phát hành (v1.0), nội dung báo cáo đã đóng băng (immutable) + ảnh đính kèm, timeline phát hành: ký → phát hành → gửi qua ứng dụng bệnh nhân, kênh gửi cho bệnh nhân (app/zalo) + trạng thái đã gửi, file PDF render + quyền in/tải
- **Ghi chú:** Thế hệ V2 (topbar chuông + avatar, logo có tagline, sidebar thu gọn) — 3 màn còn lại vẫn V1, cần đồng bộ lại header/sidebar cho cả bộ. Không thấy badge chữ 'V2' in trên artboard nên suy luận theo dấu hiệu topbar. Đây là màn READ-ONLY: báo cáo đã ký phải bất biến, mọi sửa chữa phải tạo phiên bản mới (amend) — cần chốt chính sách amend/thu hồi vì hiện chưa có nút nào cho việc đó. KPI 'Chưa gửi bệnh nhân = 4' là hàng động (actionable) nhưng không có nút 'Gửi bệnh nhân' trên màn → thiếu hành động tương ứng. Mã bệnh nhân ở màn này là BN250514-xxx trong khi các màn khác dùng US250514-xxx (mã yêu cầu) — cần phân biệt rõ patient_code vs request_code. Dữ liệu demo lệch: Lê Minh Châu ở image_4 sinh 1990/35 tuổi, ở đây 1991/35 tuổi; Nguyễn Thu Hà 1993/33 tuổi vs 1990/36 tuổi.

### Danh sách chờ siêu âm
`image_4.jpg` · V1 · TKYK / Thư ký siêu âm (Nguyễn Phương Anh), phục vụ NURSE_ULTRASOUND + ULTRASOUND_DOCTOR  
2 cột: main (KPI row + filter bar + bảng hàng đợi có phân trang) | panel phải chi tiết yêu cầu

Tiếp nhận yêu cầu siêu âm trong ngày, kiểm tra điều kiện sẵn sàng và theo dõi thời gian chờ / SLA trước khi đẩy sang điều phối phòng.

- **Node kernel:** LUOTKHAM-05
- **KPI:** Tổng yêu cầu hôm nay = 146 · Chờ tiếp nhận = 12 · Chờ phòng = 31 · Quá SLA = 4 (icon đỏ)
- **Hành động:** Chuyển sang điều phối phòng, Ghi chú, Mở hồ sơ bệnh nhân, Lọc theo dịch vụ / ưu tiên & SLA, Tìm kiếm bệnh nhân, mã yêu cầu, dịch vụ
- **Dữ liệu cần:** danh sách yêu cầu siêu âm theo ngày + clinic (mã US250514-xxx), hồ sơ bệnh nhân rút gọn: tên, năm sinh, giới, tuổi, mã BN, service_code / tên dịch vụ siêu âm + nội dung chỉ định, bác sĩ chỉ định + thời gian chỉ định, giờ hẹn, thời điểm check-in → tính 'đã chờ', cấu hình SLA tiếp nhận (30 phút) để tính badge Quá SLA, cờ ưu tiên (Thường / Ưu tiên), 4 điều kiện sẵn sàng: đã check-in, đã xác minh danh tính, chỉ định hợp lệ, đã được phép thực hiện (thường = đã thanh toán/duyệt)
- **Ghi chú:** Trạng thái hiển thị KHÔNG khớp bộ 8 trạng thái kernel đã chốt: ảnh dùng 'Sẵn sàng / Đã check-in / Quá SLA / Chờ check-in / Chờ phòng / Chờ tiếp nhận'. Cần map: Sẵn sàng→ready, Chờ phòng/Chờ tiếp nhận→ready|blocked, Quá SLA→overdue (overdue nên là cờ phụ chứ không thay trạng thái). KPI 'Chờ tiếp nhận 12 + Chờ phòng 31' = 43 nhưng bảng nói 38 đang chờ → số liệu demo chưa nhất quán. Đây là 1 trong 3 màn cùng bộ dùng chung dữ liệu US250514-001..009.

### Kết quả siêu âm
`image_6.jpg` · V1 · TKYK / Thư ký siêu âm nhập & hoàn thiện; ULTRASOUND_DOCTOR rà soát + ký  
3 cột: danh sách kết quả (có tab) | workspace soạn kết quả | panel phải thông tin chỉ định + checklist + phiên bản

Thư ký hoàn thiện mô tả hình ảnh theo mẫu, đính kèm ảnh đồng bộ từ máy siêu âm rồi gửi bác sĩ rà soát và ký.

- **KPI:** Chờ nhập kết quả = 6 · Bản nháp = 4 · Chờ thư ký hoàn thiện = 7 · Chờ bác sĩ ký = 14
- **Hành động:** Áp dụng mẫu báo cáo, Thêm hình ảnh, Lưu nháp, Gửi bác sĩ rà soát, Chuyển tab Chờ hoàn thiện / Bản nháp / Chờ ký
- **Dữ liệu cần:** template báo cáo theo service_code (form schema), ảnh DICOM/JPG đồng bộ từ máy siêu âm theo phòng + gắn vào yêu cầu, nội dung mô tả / kết luận / khuyến nghị + versioning (bản nháp v3), audit trail người nhập + thời điểm cập nhật, phân quyền: thư ký chỉ lưu nháp & gửi, chỉ bác sĩ ký/phát hành, checklist điều kiện gửi rà soát, bác sĩ chỉ định vs bác sĩ thực hiện
- **Ghi chú:** Ràng buộc nghiệp vụ rõ trong thiết kế: trường Kết luận sơ bộ + Khuyến nghị KHÓA với vai trò thư ký (placeholder 'Chờ bác sĩ...'), chỉ bác sĩ ký & phát hành → cần enforce ở FastAPI, không chỉ disable ở TSX. Có versioning bản nháp → cần bảng lịch sử phiên bản. KPI trùng lặp với màn điều phối (Chờ thư ký hoàn thiện 7, Chờ bác sĩ ký 14) → nên là cùng một query dùng chung, đặt ở service layer.

### Siêu âm SA1–SA3 (Điều phối phòng siêu âm)
`ChatGPT_Image_12_01_27_24_thg_7_2026_(10).jpg` · V2 · NURSE_ULTRASOUND / thư ký siêu âm (Nguyễn Phương Anh — 'Thư ký siêu âm'); liên quan ULTRASOUND_DOCTOR ở bước ký  
3 vùng: sidebar trái | cột giữa (hàng KPI 5 ô + 3 cột phòng SA1/SA2/SA3 + băng quy trình 4 bước dưới cùng) | panel phải chi tiết yêu cầu đang chọn

Điều phối 3 phòng siêu âm: theo dõi bệnh nhân đang thực hiện, hàng chờ từng phòng, chuyển bệnh nhân khi phòng bảo trì, và đẩy quy trình hoàn thiện/ký kết quả.

- **Node kernel:** node dịch vụ siêu âm sinh từ LUOTKHAM-05 (không thuộc 7 bước xương sống), LUOTKHAM-13 (đối soát chi phí — hạ nguồn khi kết quả hoàn tất)
- **KPI:** Tổng yêu cầu hôm nay: 146 (cập nhật 10:20) · Chờ phòng: 31 — TB chờ 27 phút · Đang thực hiện: 3 · Chờ thư ký hoàn thiện: 7 — TB chờ 18 phút · Chờ bác sĩ ký: 14 — TB chờ 15 phút · Đếm số bệnh nhân theo từng phòng: SA1 5, SA2 4, SA3 7
- **Hành động:** Mở kết quả siêu âm, Đổi phòng thực hiện (dropdown), Tạm dừng đếm ngược, Ghi chú, Xem chi tiết, Xem tất cả hàng chờ từng phòng
- **Dữ liệu cần:** work_item/yêu cầu siêu âm theo ngày + trạng thái (để tính 5 KPI và thời gian chờ trung bình), trạng thái phòng SA1–SA3 (hoạt động/bảo trì + thời gian dự kiến hoàn tất bảo trì), hàng chờ theo phòng, có thứ tự, giờ dự kiến, phòng nguồn khi bị chuyển, chi tiết chỉ định: dịch vụ, lý do chỉ định, bác sĩ chỉ định, thời điểm chỉ định, mức ưu tiên, ghi chú, phiên thực hiện: giờ bắt đầu, dự kiến kết thúc (để tính đếm ngược ở FE từ mốc backend), trạng thái pipeline báo cáo (hoàn thiện của thư ký, chữ ký bác sĩ, hoàn tất), realtime cập nhật hàng chờ + KPI
- **Ghi chú:** Đây là màn duy nhất trong bộ có KPI thật. Rủi ro dữ liệu trong mock: 'Đang thực hiện = 3' nhưng chỉ 2 phòng có bệnh nhân hiện tại (SA2 bảo trì), còn băng quy trình dưới ghi '(4)' — 3 con số phải cùng một nguồn. 4 bệnh nhân chờ chuyển ở SA2 (US...006/007/008/009) xuất hiện lại trong danh sách chờ SA3 (006/007/008) — nhất quán nhưng cần rõ đây là cùng work_item được đổi phòng chứ không nhân đôi. 'Dự kiến hoàn tất 18:00' cho một ca siêu âm bắt đầu 10:05 là sai thực tế (đếm ngược 01:39 lại không khớp 18:00). Các badge 'Chờ phòng/Chờ chuyển/Chờ xử lý' là nhãn hiển thị, cần map về bộ 8 trạng thái (ready/assigned/in_progress/blocked...).

### Siêu âm SA1–SA3 – Điều phối phòng siêu âm
`ChatGPT_Image_10_45_20_24_thg_7_2026_(4).jpg` · V2 · NURSE_ULTRASOUND / thư ký siêu âm (Nguyễn Phương Anh – 'Thư ký siêu âm')  
Sidebar trái (4 mục Siêu âm) + topbar + hàng 5 KPI tile + tab 'Tổng quan phòng' / 'Danh sách chờ tổng hợp' + 3 cột phòng SA1|SA2|SA3 + panel phải 'Chi tiết yêu cầu' + thanh 'Luồng trạng thái siêu âm' dưới cùng

Điều phối 3 phòng siêu âm: theo dõi bệnh nhân đang thực hiện, hàng chờ mỗi phòng, chuyển phòng khi sự cố, và xử lý một yêu cầu cụ thể (gọi, đưa vào phòng, lưu mô tả, gửi ký).

- **KPI:** Tổng yêu cầu hôm nay = 128 · Chờ phòng = 24 (TB chờ 25 phút) · Đang thực hiện = 3 · Chờ thư ký hoàn thiện = 7 (TB chờ 18 phút) · Chờ bác sĩ ký = 15 (TB chờ 12 phút)
- **Hành động:** Gọi bệnh nhân, Đưa vào phòng, Lưu mô tả, Gửi ký, Chuyển phòng (dropdown phòng được phân công), Tạm dừng/tiếp tục đếm ngược
- **Dữ liệu cần:** danh sách yêu cầu siêu âm trong ngày + trạng thái, cấu hình phòng SA1–SA3 + trạng thái phòng/thiết bị (bảo trì), hàng chờ theo phòng + thứ tự + lịch sử chuyển phòng, thời lượng dự kiến theo loại dịch vụ (progress/countdown), mẫu report siêu âm theo dịch vụ + phiên bản report, trạng thái ký của bác sĩ, chỉ số tổng hợp: tổng yêu cầu, chờ phòng, đang thực hiện, chờ hoàn thiện, chờ ký + thời gian chờ trung bình
- **Ghi chú:** V2 (badge V2, topbar chuông + avatar). Đây là work_item nhánh dịch vụ (siêu âm) sinh từ LUOTKHAM-05, không phải node xương sống nên để 'none'. Luồng trạng thái riêng của siêu âm (6 bước: chờ phòng/đã gọi/đang thực hiện/chờ thư ký/chờ ký/hoàn tất) KHÔNG trùng bộ 8 trạng thái hiển thị đã chốt (ready, assigned, in_progress, blocked, completed, skipped, cancelled, overdue) — cần chốt đây là sub-status nghiệp vụ ánh xạ vào 8 trạng thái kernel, kẻo phình bộ trạng thái. SA2 tạm dừng là ví dụ blocked ở cấp tài nguyên (thiết bị) chứ không phải cấp work_item. KPI đều là đếm/thời gian chờ thực dụng, không có chỉ số trang trí.

### Điều phối phòng siêu âm
`image_5.jpg` · V1 · TKYK / Thư ký siêu âm (người điều phối), phối hợp NURSE_ULTRASOUND  
2 cột: main (KPI row + 3 cột kanban theo phòng SA1|SA2|SA3) | panel phải chi tiết yêu cầu & phân công

Điều phối bệnh nhân vào 3 phòng SA1–SA3, theo dõi ca đang thực hiện và xử lý chuyển phòng khi có phòng bảo trì.

- **KPI:** Tổng yêu cầu hôm nay = 146 · Chờ phòng = 31 · Đang thực hiện = 3 · Chờ thư ký hoàn thiện = 7 · Chờ bác sĩ ký = 14
- **Hành động:** Điều phối 4 bệnh nhân (bulk re-assign khi phòng bảo trì), Chuyển phòng, Chọn phòng thực hiện (dropdown), Mở kết quả siêu âm, Ghi chú, Xem tất cả bệnh nhân trong hàng đợi
- **Dữ liệu cần:** danh mục phòng siêu âm + trạng thái phòng (hoạt động / bảo trì + ETA hoàn tất), hàng đợi theo phòng, thứ tự gọi, ca đang thực hiện: giờ bắt đầu, thời lượng dự kiến theo dịch vụ → progress, lịch sử chuyển phòng (từ SA2) để hiện badge nguồn, SLA chờ + cờ ưu tiên, trạng thái pipeline báo cáo của từng ca (4 bước), quyền điều phối / gán phòng
- **Ghi chú:** Đây là biến thể trạng thái đặc biệt: SA2 bảo trì → hệ thống KHÔNG tự chuyển, bắt buộc người điều phối chọn tay (design intent quan trọng). Stepper 4 bước báo cáo nên là node kernel riêng của luồng siêu âm (thực hiện → thư ký hoàn thiện → bác sĩ ký → phát hành), chưa có mã LUOTKHAM tương ứng. Trạng thái 'Sắp đến lượt', 'Chờ chọn phòng' nằm ngoài bộ 8 trạng thái chuẩn — nên là nhãn dẫn xuất (derived label), không phải status mới. Logo/artboard hơi khác image_4 (icon ClinicAI mảnh hơn) nhưng vẫn thế hệ cũ, không có badge V2.

### Đo & ghi sinh hiệu
`image_23.jpg` · V2 · NURSE / Điều dưỡng (nhóm NURSE_ULTRASOUND / điều dưỡng sinh hiệu)  
3 cột: danh sách chờ sinh hiệu (có tab) | form 9 ô chỉ số dạng lưới 3x3 + thông tin bổ sung + checklist trước xác nhận | panel thông tin lượt khám + đánh giá tự động + hành trình dịch vụ + nhật ký

Ghi nhận 9 chỉ số sinh hiệu, tự động cảnh báo ngoài ngưỡng và chuyển người bệnh sang bước khám.

- **Node kernel:** LUOTKHAM-03
- **KPI:** Chờ đo sinh hiệu: 9 · Đang thực hiện: 2 · Có cảnh báo: 3 (đỏ) · Có cảnh báo: 3 (cam) · Hoàn tất hôm nay: 31
- **Hành động:** Xác nhận sinh hiệu & chuyển bước (nút chính), Lưu nháp, Đo lại, Chuyển tab Ưu tiên / Cần đo lại
- **Dữ liệu cần:** vital_signs 9 chỉ số + đơn vị + dải tham chiếu theo tuổi/giới/thai kỳ, device binding: mã thiết bị nguồn đo, timestamp đồng bộ tự động, BMI tính tự động từ cân nặng/chiều cao (không cho nhập tay), context đo: tư thế, vị trí đo, trạng thái ăn uống, tình trạng thai kỳ, work_item LUOTKHAM-03: người thực hiện, thời điểm bắt đầu, elapsed, SLA mục tiêu, rule ngưỡng + hành động khi vượt (yêu cầu đo lại / báo bác sĩ), identity check: đối chiếu danh tính khớp/không khớp, dependency: bước kế tiếp (Khám bác sĩ) để enable nút chuyển bước
- **Ghi chú:** V2: topbar có chuông thông báo + avatar, artboard hẹp hơn nhóm V1 (dù không thấy badge 'V2' in trên ảnh). LỖI CẦN SỬA: hai KPI giữa trùng nhãn 'Có cảnh báo' (một đỏ, một cam) và cùng giá trị 3 — nhiều khả năng phải là 'Có cảnh báo' và 'Chờ xử lý cảnh báo'/'Quá SLA'; cần đặt lại nhãn. Ngoài ra 'Lượt khám hiện tại: Khám bác sĩ' hiển thị cùng lúc với bước Đo sinh hiệu đang thực hiện — dễ gây nhầm, nên đổi thành 'Bước kế tiếp'.

## DOCTOR

### Danh sách bệnh nhân
`image_16.jpg` · V1 · DOCTOR (Bác sĩ — nhóm menu KHÁM BÁC SĨ)  
3 cột: (trái) sidebar điều hướng + danh sách/lọc bệnh nhân | (giữa) workspace hồ sơ tổng quan theo tab | (phải) panel 'Thông tin lượt khám hiện tại'

Tra cứu hồ sơ tổng hợp của người bệnh, lịch sử điều trị và bước tiếp theo trong lượt khám đang mở.

- **Node kernel:** LUOTKHAM-01, LUOTKHAM-03, LUOTKHAM-05, LUOTKHAM-13, LUOTKHAM-14
- **Hành động:** Mở hồ sơ khám, Xem hành trình, Xem tất cả lịch sử khám, Xem tất cả tệp đính kèm, Lọc/tìm bệnh nhân, Menu ... trên header bệnh nhân
- **Dữ liệu cần:** patient (mã BN, họ tên, năm sinh, giới, tuổi), encounter/visit đang mở (mã LK, trạng thái, ưu tiên), allergy list, chronic conditions, obstetric history (G/P, LMP), vitals mới nhất + timestamp, visit history (danh sách lượt khám trước: ngày, mã LK, lý do, bác sĩ), work_item của visit (tên bước, trạng thái, assignee, SLA), service orders + trạng thái thực hiện, external lab result attachments (file, nguồn, thời điểm nhận)
- **Ghi chú:** KPI: Tổng bệnh nhân 3.842 | Có lượt đang mở 28 | Chờ bác sĩ xử lý 9 | Cần theo dõi 14. Đây là màn READ-ONLY/tra cứu, không ký duyệt. Trạng thái hiển thị trong stepper dùng nhãn tiếng Việt tự do ('Đang thực hiện', 'Chờ thực hiện', 'Đã nhận kết quả') — cần map về đúng 8 trạng thái đã chốt (ready/assigned/in_progress/blocked/completed/skipped/cancelled/overdue). Không có badge V2, artboard rộng, topbar không có chuông → thế hệ V1.

### Danh sách khám bệnh hôm nay
`image_17.jpg` · V1 · DOCTOR (Bác sĩ)  
3 cột: (trái) hàng đợi hôm nay theo nhóm trạng thái | (giữa) form khám 5 khối + cột chỉ định & kết quả liên quan | (phải) panel 'Việc còn thiếu & điều phối'

Workspace khám: ghi bệnh án, ra chỉ định, chẩn đoán, duyệt kết quả và ký hoàn tất hồ sơ trong một màn hình.

- **Node kernel:** LUOTKHAM-05, LUOTKHAM-13, none (khám bác sĩ & ký duyệt hồ sơ — chưa thấy mã node tương ứng trong 7 bước xương sống)
- **Hành động:** Lưu nháp, Tạo chỉ định, Ký duyệt & hoàn tất hồ sơ (CTA chính), Duyệt kết quả, Xem kết quả, Gợi ý AI — bản nháp
- **Dữ liệu cần:** hàng đợi visit hôm nay theo trạng thái + giờ hẹn, vitals của lượt hiện tại, allergy flags, clinical note fields (lý do khám, bệnh sử, khám lâm sàng, chẩn đoán ICD, kế hoạch), service orders + kết quả (loại, người thực hiện, thời điểm, version kết quả), result approval queue (v1.2, chờ bác sĩ duyệt), prescription items (thuốc, hàm lượng, liều, số ngày), consent record
- **Ghi chú:** KPI: 24 / 7 / 3 / 5. Ghi chú phân quyền rõ: 'Vai trò Bác sĩ được ký duyệt và phát hành bản cuối. Thư ký chỉ được lưu nháp' → ràng buộc ROLE. Nhóm hàng đợi ('Chờ khám', 'Đang khám', 'Quay lại đọc kết quả') là nhãn UI, cần map sang trạng thái kernel. Avatar topbar là TD nhưng tên BS. Trần Văn Dũng (ảnh 16 dùng TV) — initials không nhất quán giữa các màn. Thế hệ V1 (không badge V2, topbar chỉ có avatar, không chuông).

### Duyệt kết quả
`ChatGPT_Image_10_45_27_24_thg_7_2026_(9).jpg` · V1 · DOCTOR (Bác sĩ duyệt kết quả)  
2 cột chính: sidebar điều hướng | danh sách hàng đợi (bảng) | panel chi tiết phải (viewer PDF + diễn giải + hành động)

Bác sĩ xem lại báo cáo kết quả (xét nghiệm/siêu âm) kèm diễn giải AI rồi ký duyệt hoặc trả lại chỉnh sửa trước khi trả cho bệnh nhân.

- **KPI:** Không có KPI card; chỉ đếm số trong tab/sidebar: Chờ duyệt 18, Cần chỉnh sửa 6, Đã ký 132
- **Hành động:** Ký duyệt (Xác nhận và cho phép trả kết quả), Trả lại chỉnh sửa (Yêu cầu bổ sung hoặc chỉnh sửa), Tạo theo dõi sau khám (chuyển bệnh nhân sang CSKH follow-up), Lọc/tìm kiếm, phân trang 10/trang, refresh
- **Dữ liệu cần:** Hàng đợi kết quả chờ duyệt theo bác sĩ + ngày, visit/appointment code (LH…), bệnh nhân: tên, năm sinh, giới, tuổi, SĐT, Loại kết quả + chuyên khoa con (huyết học, sinh hóa, miễn dịch, hormon, nước tiểu, siêu âm tuyến giáp/tim/ổ bụng), Trạng thái duyệt + có phiên bản sửa hay không, Mức độ ưu tiên/mức bất thường, Mốc thời gian: yêu cầu, nhận mẫu, yêu cầu lúc, File báo cáo (PDF, số trang), Diễn giải AI + timestamp + nguồn
- **Ghi chú:** Thế hệ V1: artboard rộng, topbar chỉ có date + chuông + avatar, không có badge 'V2', không có đồng hồ giờ. Không map trực tiếp vào 7 node xương sống LUOTKHAM (đây là nhánh cận lâm sàng sau node 05 tạo chỉ định, trước node 13/14). Nút 'Tạo theo dõi sau khám' là điểm nối sang màn CSKH follow-up. Trạng thái hiển thị dùng ở đây ('Chờ duyệt', 'Cần chỉnh sửa', 'Chưa thể trả', 'Đã ký có phiên bản sửa') KHÔNG nằm trong bộ 8 trạng thái kernel đã chốt — cần map lại hoặc coi là trạng thái nghiệp vụ riêng của result-review.

### Duyệt kết quả
`ChatGPT_Image_12_01_24_24_thg_7_2026_(3).jpg` · unknown · DOCTOR (bác sĩ duyệt kết quả) — user hiển thị: BS. Trần Minh Đức  
3 cột: sidebar điều hướng | danh sách hàng đợi kết quả (bảng + tab + tìm kiếm + phân trang) | panel chi tiết bên phải (báo cáo + diễn giải + hành động)

Bác sĩ xem báo cáo kết quả CLS/xét nghiệm kèm diễn giải (có bản nháp AI) rồi ký duyệt, trả lại chỉnh sửa hoặc tạo theo dõi sau khám.

- **Node kernel:** none — màn này là node ký duyệt kết quả CLS, không nằm trong 7 bước xương sống LUOTKHAM-01/02/03/05/13/14/15, liên quan gián tiếp LUOTKHAM-05 (tạo chỉ định) là nguồn sinh yêu cầu kết quả, là điều kiện chặn cho LUOTKHAM-15 (đóng lượt) — xem màn Check-out: 'Kết quả siêu âm chưa ký'
- **KPI:** Chờ duyệt: 18 · Cần chỉnh sửa: 6 · Đã ký: 132 · Kết quả đã ký (sidebar): 132 · Yêu cầu chỉnh sửa (sidebar): 6
- **Hành động:** Ký duyệt (Ký xác nhận và cho phép trả kết quả), Trả lại chỉnh sửa (Yêu cầu bổ sung hoặc chỉnh sửa), Tạo theo dõi sau khám (Chuyển bệnh nhân sang theo dõi), Xem nguồn bản nháp AI, Tải xuống / zoom phiếu kết quả, Lọc, tìm kiếm, làm mới hàng đợi
- **Dữ liệu cần:** Hàng đợi kết quả chờ duyệt theo bác sĩ + theo ngày (thời gian yêu cầu, trạng thái, mức độ bất thường), Hồ sơ bệnh nhân: tên, năm sinh, tuổi, giới, SĐT, mã lượt khám, Yêu cầu CLS: mã, loại/nhóm (huyết học, sinh hóa, miễn dịch, nước tiểu, hormon, siêu âm...), thời điểm yêu cầu và nhận mẫu, Kết quả xét nghiệm chi tiết: chỉ số, giá trị, đơn vị, khoảng tham chiếu, cờ bất thường, File/PDF phiếu kết quả để hiển thị và tải, Diễn giải kết quả + bản nháp do AI sinh (kèm model version, nguồn, cờ chưa xác nhận), Ghi chú lâm sàng (nhập tay, giới hạn 200 ký tự), Checklist điều kiện trả kết quả (đủ kết quả / diễn giải / chữ ký KTV / thông tin hành chính)
- **Ghi chú:** Không thấy badge 'V2' trên artboard nhưng topbar CÓ chuông + avatar (đặc trưng V2) → generation không xác định chắc chắn; 4 ảnh trong lô này dùng chung một shell (logo 'ClinicAI — CONNECTED CLINIC WORKFLOW', sidebar thu gọn được, pill ngày + giờ, chuông có số, avatar) nên cùng một thế hệ. Điểm cần chốt: trạng thái hiển thị trong bảng ('Chờ duyệt', 'Cần chỉnh sửa', 'Chưa thể trả', 'Đã ký có phiên bản sửa') KHÔNG khớp bộ 8 trạng thái kernel đã chốt 01/08/2026 (ready/assigned/in_progress/blocked/completed/skipped/cancelled/overdue) — đây là trạng thái nghiệp vụ riêng của kết quả CLS, cần map rõ sang trạng thái work_item. Khối 'Bản nháp AI' cần cờ chưa xác nhận + lưu vết model version.

### Khám phụ khoa & Order composer
`ChatGPT_Image_12_01_27_24_thg_7_2026_(9).jpg` · V2 · DOCTOR — bác sĩ phụ khoa (BS. Vũ Ngọc Lan)  
5 cột: sidebar trái | cột 1 hồ sơ/tiền sử/sinh hiệu | cột 2 kết quả khám phụ khoa | cột 3 (rộng nhất) Order composer chỉ định dịch vụ | panel phải cảnh báo & tóm tắt đơn — phía trên là banner bệnh nhân full-width

Bác sĩ thăm khám, ghi nhận kết quả khám phụ khoa và soạn/gửi bộ chỉ định dịch vụ trong cùng một màn hình.

- **Node kernel:** LUOTKHAM-03 (sinh hiệu — hiển thị), LUOTKHAM-05 (tạo chỉ định — node chính của màn này), LUOTKHAM-02 (xác minh — dữ liệu BN)
- **Hành động:** Xem và gửi chỉ định, Chọn/bỏ chọn bộ chỉ định & dịch vụ lẻ, Thêm dịch vụ khác, Đặt nhanh từ mẫu, Gọi CSKH giải thích chi phí, Ghi nhận từ chối
- **Dữ liệu cần:** patient + mã BN, tiền sử kinh nguyệt/sản khoa/phụ khoa (structured, không free text), vital signs của lượt khám kèm timestamp ghi nhận, clinical form khám phụ khoa (mã form theo service_code — lưu ý mismatch đã ghi nhận trong memory), catalog dịch vụ: mã (GYN-xxx), tên, giá, nhóm, mức ưu tiên/chuẩn bị, service bundles (bộ chỉ định) + giá gộp + số dịch vụ, work_item đang blocked + blocked_reason + điều kiện hoàn tất (kernel), lịch sử chỉ định 30 ngày gần nhất của bệnh nhân để tính trùng lặp (backend), quy tắc tính tạm tính/giảm giá/phí khác (SQL hoặc service, không tính ở TSX)
- **Ghi chú:** Màn dày nhất trong bộ. Trạng thái 'ĐANG BỊ CHẶN' khớp đúng trạng thái kernel `blocked` và có nêu điều kiện gỡ chặn — đây là chỗ kernel work_item lộ ra UI rõ nhất. Lưu ý: 'Trạng thái ● Đang khám' ở cột 1 là nhãn nghiệp vụ, nên map về `in_progress`. Cảnh báo trùng lặp + chặn chi phí là logic backend, tuyệt đối không tính trong TSX. Không có KPI dạng số đếm trên màn này (chỉ số tiền/đếm dịch vụ trong đơn).

### Khám phụ khoa & chỉ định
`ChatGPT_Image_10_45_19_24_thg_7_2026_(3).jpg` · V2 · DOCTOR (bác sĩ phụ khoa – BS. Vũ Ngọc Lan)  
Sidebar trái (5 mục 'Bác sĩ phụ khoa') + header bệnh nhân (Nguyễn Thị Hạnh, mã KH250514-087, SĐT, ngày khám, BS điều trị) + 4 cột: thông tin lượt khám/tiền sử/sinh hiệu | kết quả khám & chẩn đoán | chỉ định dịch vụ | panel chặn + tóm tắt đơn hàng + cảnh báo trùng lặp

Bác sĩ xem tiền sử + kết quả khám phụ khoa, ghi chẩn đoán sơ bộ/hướng xử trí và tạo chỉ định dịch vụ (bộ chỉ định hoặc dịch vụ lẻ) rồi gửi đi.

- **Node kernel:** LUOTKHAM-05, LUOTKHAM-03
- **Hành động:** Chọn bộ chỉ định / tick dịch vụ lẻ, Thêm dịch vụ khác, Xem và gửi chỉ định, Gọi CSKH giải thích chi phí, Ghi nhận từ chối, Điều chỉnh chỉ định
- **Dữ liệu cần:** hồ sơ + lượt khám hiện tại (mã BN, số thứ tự, giờ vào, trạng thái), tiền sử kinh nguyệt/sản khoa/phụ khoa, sinh hiệu đã ghi (từ node sinh hiệu), biểu mẫu kết quả khám phụ khoa (form schema chuyên khoa), danh mục dịch vụ + bảng giá + nhóm + mức ưu tiên, bộ chỉ định mẫu (service bundle) và mapping bundle→dịch vụ, lịch sử chỉ định 30 ngày gần nhất để phát hiện trùng, trạng thái xác nhận chi phí của bệnh nhân (blocker)
- **Ghi chú:** V2 (badge V2 trên logo, topbar chuông + avatar). Chính là node LUOTKHAM-05 'tạo chỉ định'; cột 1 tiêu thụ output của LUOTKHAM-03 (sinh hiệu). Panel 'ĐANG BỊ CHẶN' đúng khuôn mẫu blocked của kernel (lý do chặn + hoàn tất khi + hành động gỡ chặn) và khớp trạng thái 'blocked' trong bộ 8 trạng thái. Điểm cần lưu ý: mã dịch vụ dùng tiền tố GYN-/LAB- trong khi memory ghi service_code theo bộ FORM (PK/SK/NT/HMVS/NK) — cần kiểm tra mismatch mã dịch vụ vs mã form. Số thứ tự PKO-062 là số theo chuyên khoa, khác tiền tố C### ở màn TV.

### Kết quả đã ký
`image_18.jpg` · V1 · DOCTOR (Bác sĩ)  
2 cột: (trái) bộ lọc + bảng kết quả có phân trang | (phải) panel chi tiết kết quả đã ký (read-only)

Tra cứu kết quả đã ký, quyết định phát hành và xem lịch sử phiên bản của từng bản kết quả.

- **Node kernel:** none (tra cứu/lưu trữ kết quả sau ký, ngoài 7 bước xương sống)
- **Hành động:** In kết quả, Tải PDF, Xem phiên bản, Xem chi tiết lịch sử phiên bản, Lọc theo ngày/loại/trạng thái phát hành, Sắp xếp theo thời gian ký
- **Dữ liệu cần:** signed result records (mã, loại, version, thời gian ký, người ký), patient + visit link (mã BN, mã LK), digital signature validity, result content summary (kết luận, chẩn đoán ICD, kế hoạch, đơn thuốc), audit/version history (ai, làm gì, lúc nào, version), release/publish status + amendment flag, tổng số bản ghi cho phân trang
- **Ghi chú:** KPI: 16 / 14 / 2. Đây là màn immutability + audit: bản ký là read-only, sửa phải tạo amendment. Bảng thiếu cột hành động per-row (chỉ chọn dòng để xem panel). Thế hệ V1.

## RECEPTION

### Check-in & tiếp nhận
`image_19.jpg` · V1 · RECEPTION (Lễ tân — Trần Ngọc Mai)  
3 cột: (trái) danh sách người bệnh đến theo tab | (giữa) khối xác minh định danh & dịch vụ hôm nay | (phải) form 'Tạo lượt khám'

Xác nhận người bệnh đã đến, xác minh định danh/dịch vụ, tạo lượt khám và đưa vào hàng đợi.

- **Node kernel:** LUOTKHAM-01, LUOTKHAM-02, LUOTKHAM-03, LUOTKHAM-05
- **Hành động:** Xác nhận check-in & vào hàng đợi (CTA chính), Lưu chờ xác minh, In số thứ tự, Quét mã CCCD/QR, Copy mã lượt khám, Cấp lại số thứ tự
- **Dữ liệu cần:** appointment list hôm nay + trạng thái đến (sớm/muộn/no-show/walk-in), patient identity + CCCD/CMND, contact, address, MPI match result / dedup check, appointment detail (chuyên khoa, bác sĩ, phòng), registered services + bảng giá → tổng tiền, insurance (BHYT card, bảo hiểm khác), kiểm tra Encounter mở trùng, cấp mã lượt khám (LK) + số thứ tự hàng đợi theo clinic/ngày
- **Ghi chú:** KPI: 86 / 42 / 8 / 5. Màn này chính là điểm sinh work_item của visit (check-in tạo 7 bước xương sống) — 'Điểm đến ban đầu' + 'Hành trình tiếp theo' phải render từ kernel chứ không hardcode. Kiểm tra 'Không có Encounter mở trùng' = ràng buộc chống tạo trùng lượt. Số thứ tự A021 phải unique theo clinic+ngày (khớp commit 7dad3ad). Thế hệ V1 (topbar chỉ date/giờ/avatar, không chuông, không badge V2).

### Check-out lượt khám
`image_21.jpg` · V1 · RECEPTION (Lễ tân)  
3 cột: danh sách lượt khám (có tab lọc) | checklist đóng lượt 4 nhóm | panel thông tin lượt khám + timeline + hồ sơ trả/bàn giao; KPI strip 4 ô phía trên

Đối soát đủ điều kiện đóng lượt, trả hồ sơ cho người bệnh và xác nhận kết thúc lượt khám.

- **Node kernel:** LUOTKHAM-13, LUOTKHAM-14, LUOTKHAM-15
- **KPI:** Chờ check-out: 12 · Đủ điều kiện đóng: 8 · Đang bị chặn: 4 · Kết quả trả sau: 3
- **Hành động:** Xác nhận trả hồ sơ & đóng lượt (nút chính), In bộ hồ sơ, Gửi qua ứng dụng, Lọc theo Đủ điều kiện / Bị chặn, Mở chi tiết dịch vụ trả sau / follow-up
- **Dữ liệu cần:** visit: mã lượt khám, mã BN, bác sĩ phụ trách, phòng khám, thời gian check-in/kết thúc, work_item theo dịch vụ: loại dịch vụ, người thực hiện, trạng thái completed/blocked, cờ 'kết quả trả sau', billing/nghĩa vụ tài chính: nhóm nghĩa vụ (xét nghiệm/thuốc/dịch vụ), số tiền, trạng thái thanh toán, kết quả đối soát, documents: danh sách file PDF (kết quả XN, kết quả siêu âm, đơn thuốc, hướng dẫn sau khám, giấy hẹn tái khám) + trạng thái sẵn sàng, follow_up task: mã FU, loại, owner (CSKH), hạn xử lý, handover: kênh bàn giao (bệnh nhân/người nhà/app) + SĐT người nhận, timeline sự kiện lượt khám, blocking rules: điều kiện chặn đóng lượt (chưa thanh toán, chưa có follow-up)
- **Ghi chú:** V1 (không có chuông thông báo trên topbar). Đây chính là UI của node LUOTKHAM-15 (đóng lượt) với tiền đề LUOTKHAM-13 đối soát chi phí + 14 thanh toán; checklist 4 nhóm là biểu diễn cổng AND (mọi nhóm phải đủ mới cho đóng). Badge 'Còn nghĩa vụ thanh toán' / 'Chưa có follow-up' = trạng thái blocked. Workspace tương ứng: thu_ngan_dong_luot.

### Check-out lượt khám
`ChatGPT_Image_10_45_25_24_thg_7_2026_(8).jpg` · V2 · RECEPTION (Lễ tân) – Checkout  
2 cột chính: sidebar LỄ TÂN/CHECKOUT | bảng danh sách lượt khám (kèm thanh Điều kiện hoàn tất 3 bước ở trên) | panel phải Chi tiết lượt khám (drawer đóng được)

Danh sách lượt khám trong ngày để lễ tân đóng lượt sau khi đối soát chi phí xong, kèm panel chi tiết nêu rõ lý do bị chặn.

- **Node kernel:** LUOTKHAM-15, LUOTKHAM-13
- **KPI:** Tất cả 18 · Sẵn sàng 12 · Đang bị chặn 6 · Đã check-out 45 · Trạng thái nghĩa vụ 3/3
- **Hành động:** Check-out lượt khám (disable khi chưa đủ 3 nghĩa vụ), Mở đối soát chi phí, Xem nghĩa vụ còn mở, Xem chi tiết / Xem hồ sơ, Lọc & tìm kiếm
- **Dữ liệu cần:** danh sách visit trong ngày + trạng thái checkout + lý do chặn, patient (tên, năm sinh, giới, mã hồ sơ, SĐT), bác sĩ + chuyên khoa/phòng khám, tóm tắt lâm sàng (lý do khám, chẩn đoán, số dịch vụ, kết quả chính), tài liệu trả sau: loại, trạng thái ký, thời gian dự kiến trả, 3 điều kiện đóng lượt + trạng thái từng điều kiện, bộ đếm tab (18/12/6/45)
- **Ghi chú:** Ngày 16/01/2026 và mã LH/HS khác hệ mã của 3 ảnh kia (ENC/KH/SCH) → hệ thống mã định danh chưa thống nhất giữa các màn. Thanh 'Điều kiện hoàn tất' trên cùng hiển thị cả 3 mốc tick xanh trong khi hàng/panel đang bị chặn → mâu thuẫn trạng thái, cần bind theo lượt khám đang chọn. Trạng thái 'Đang bị chặn' = blocked, 'Sẵn sàng' = ready, 'Đã check-out' = completed trong bộ 8.

### Check-out lượt khám
`ChatGPT_Image_12_01_24_24_thg_7_2026_(4).jpg` · unknown · RECEPTION (lễ tân) — user hiển thị: Lê Thị Mai, Lễ tân  
3 cột: sidebar (Check-out / Bệnh nhân / Hàng đợi) | danh sách lượt khám dạng bảng có tab + bộ lọc | panel chi tiết lượt khám bên phải (đóng được bằng nút X)

Lễ tân hoàn tất thủ tục cuối cùng để đóng lượt khám sau khi 3 nghĩa vụ (tài chính, tài liệu trả sau, đóng lượt) đã đạt.

- **Node kernel:** LUOTKHAM-15 — đóng lượt khám (node chính của màn này), LUOTKHAM-13 — đối soát chi phí (điều kiện chặn: 'Đối soát chi phí chưa đạt'), LUOTKHAM-14 — thanh toán (nằm trong nghĩa vụ tài chính), node ký kết quả CLS (chặn 'Kết quả siêu âm chưa ký') — xem ảnh (3)
- **KPI:** Tất cả: 18 · Sẵn sàng: 12 · Đang bị chặn: 6 · Đã check-out: 45 · Trạng thái nghĩa vụ: 3/3 (hiển thị 3 nghĩa vụ, cả 3 chưa đạt trên ca đang chọn) · Hiển thị 1–8 trong 18
- **Hành động:** Mở đối soát chi phí (chuyển sang màn Thu ngân / Đối soát chi phí), Xem nghĩa vụ còn mở, Xem chi tiết từng lượt khám, Xem hồ sơ / Xem tất cả tài liệu trả sau, Đóng lượt khám (bước 3 — chỉ khi hết chặn), Lọc theo trạng thái / bác sĩ, tìm kiếm, làm mới
- **Dữ liệu cần:** Danh sách lượt khám trong ngày theo trạng thái check-out (sẵn sàng / bị chặn / đã check-out + mốc giờ check-out), Bệnh nhân: tên, năm sinh, tuổi, giới, SĐT, mã hồ sơ, mã lượt khám, Bác sĩ phụ trách + loại khám, Tóm tắt lượt khám: lý do khám, chẩn đoán, số dịch vụ đã thực hiện, kết quả chính, Danh sách tài liệu trả sau: loại, trạng thái ký, thời gian dự kiến trả, Trạng thái 3 nghĩa vụ đóng lượt + lý do chặn cụ thể, Quyền/vai trò lễ tân để thực hiện đóng lượt, Bộ đếm cho các tab (18/12/6/45)
- **Ghi chú:** Không có badge 'V2'; topbar có chuông (badge 3) + avatar. Đây là mặt lễ tân của cùng cơ chế chặn với ảnh (5) — cần dùng CHUNG một nguồn sự thật về 3 nghĩa vụ để hai màn không lệch. Nhãn 'Trạng thái nghĩa vụ (3/3)' dễ gây hiểu nhầm là 'đã xong 3/3' trong khi cả 3 đều chưa đạt → nên đổi thành '0/3 hoàn tất'. Trạng thái 'Đang bị chặn' map được sang kernel 'blocked'; 'Sẵn sàng' → 'ready'; 'Đã check-out' → 'completed'.

### Hàng đợi tiếp nhận
`image_20.jpg` · V1 · RECEPTION (Lễ tân)  
3 cột: danh sách hàng đợi | thông tin người bệnh + trạng thái xử lý + xử lý ngoại lệ | điều phối tại quầy (panel phải); trên cùng có KPI strip 4 ô

Gọi số và xác minh người bệnh đang chờ tại khu tiếp nhận, hoàn tất bước tiếp nhận cho từng lượt khám.

- **Node kernel:** LUOTKHAM-01, LUOTKHAM-02
- **KPI:** Đang chờ tiếp nhận: 18 · Đã gọi: 3 · Cần xác minh: 4 · Quá SLA: 2 · (phụ, trong panel) Sức chứa 4 / Đang phục vụ 1 / Đang chờ 2 / Trống 1
- **Hành động:** Gọi số A021, Xác nhận có mặt & hoàn tất (nút chính), Đánh dấu vắng mặt, Tạm giữ, Xử lý ngoại lệ kèm lý do bắt buộc, Xem tất cả hàng đợi / nhật ký
- **Dữ liệu cần:** queue_ticket: số thứ tự (A0xx), thời điểm đến, thời gian chờ, trạng thái (queued/called/confirmed), quầy gán, ưu tiên, patient/MPI: họ tên, năm sinh, giới tính, tuổi, mã BN, SĐT, địa chỉ, ngày sinh, appointment: ngày giờ hẹn, dịch vụ, bác sĩ phụ trách, loại đến (đặt hẹn/walk-in), insurance: số thẻ BHYT, nơi ĐKKCB ban đầu, hiệu lực từ–đến, kết quả kiểm tra hợp lệ, counter/desk: sức chứa, đang phục vụ, đang chờ, trống, danh sách số đã gọi, nhân sự trực quầy, SLA: SLA mục tiêu theo bước, thời gian chờ thực tế, đếm quá SLA, exception reason enum: no-show / sai chuyên khoa / trùng hồ sơ / thiếu giấy tờ + ghi chú, audit log: actor (hệ thống/nhân viên), hành động, timestamp
- **Ghi chú:** Thế hệ V1: artboard rộng, topbar KHÔNG có chuông thông báo, chỉ có avatar. Trạng thái hiển thị 'QUEUED' viết hoa tiếng Anh — lệch với bộ 8 trạng thái đã chốt (ready/assigned/in_progress/blocked/completed/skipped/cancelled/overdue); nên map sang 'ready'/'assigned' và hiển thị tiếng Việt. Stepper 5 bước ở đây là sub-step nội bộ của LUOTKHAM-01/02, không phải node kernel.

### Phòng chờ — Thông báo lượt khám (màn hình TV công cộng)
`image_15.jpg` · asset · Không đăng nhập — màn hình public cho bệnh nhân; nguồn gọi số từ RECEPTION / các phòng  
Full-screen kiosk: header (logo + tiêu đề + đồng hồ 10:28 + ngày) | 6 cột thẻ khu vực | footer hướng dẫn + dòng thương hiệu

Hiển thị số đang gọi, số tiếp theo và hàng chờ cho từng khu vực dịch vụ tại phòng chờ.

- **Node kernel:** LUOTKHAM-01, LUOTKHAM-03, LUOTKHAM-05, LUOTKHAM-14
- **Hành động:** Không có thao tác — màn hình chỉ đọc (read-only display)
- **Dữ liệu cần:** hàng đợi realtime theo từng khu vực/phòng: số đang gọi, số tiếp theo, N số đang chờ, tiền tố số theo khu vực (C / SA / X / T) và số thứ tự trong ngày theo phòng khám (per-clinic counter), phòng khám gán cho số đang gọi (PHÒNG KHÁM 2), đồng hồ + ngày server, kênh realtime (Supabase realtime) để đẩy cập nhật, kèm TTS/loa
- **Ghi chú:** Đây là asset/display screen, không phải màn nghiệp vụ có nút. Lỗi dữ liệu trong mock: cột SA1 lặp SA031/SA032/SA033/SA034/SA035 trùng với SA2, và SA2 'đang gọi' SA031 trong khi SA1 vẫn còn SA031 ở hàng chờ; cột SA3 có SA036 trùng SA2 và thứ tự không tăng dần (SA036 đứng trước SA024) → chỉ là số minh hoạ, cần quy tắc: mỗi số thuộc đúng 1 hàng đợi. Số thứ tự phải theo clinic_id, khớp commit 7dad3ad.

### Đặt lịch — bước 2: chọn khung giờ
`image_2.jpg` · V1 · CSKH (lễ tân/khu đặt lịch)  
3 cột: sidebar | lưới slot bác sĩ × giờ | panel thông tin đặt lịch

Chọn khung giờ còn sức chứa theo bác sĩ và giữ chỗ 10 phút trước khi xác nhận lịch.

- **KPI:** Lịch hôm nay 42 · Còn chỗ 18 · Đang giữ 4 · Đã xác nhận 20
- **Hành động:** Chọn slot, Giữ chỗ 10 phút, Hủy chọn, Đổi khách hàng / dịch vụ / bác sĩ, Chuyển ngày
- **Dữ liệu cần:** slot capacity theo bác sĩ/dịch vụ/khung 15 phút (đang dùng sức chứa 3), số đã đặt + số đang giữ (hold) từng slot, danh sách bác sĩ theo chuyên khoa/ngày, khách hàng đã chọn (name, code, phone), dịch vụ đã chọn, TTL hold = 10 phút, KPI ngày: tổng lịch, còn chỗ, đang giữ, đã xác nhận
- **Ghi chú:** KPI có mâu thuẫn số học cần chốt: 42 lịch hôm nay nhưng chỉ 20 đã xác nhận + 4 đang giữ = 24 → 18 còn lại là gì? Và 'Còn chỗ 18' (đơn vị = chỗ trống) bị đặt cạnh 'Lịch hôm nay 42' (đơn vị = lịch) nên trông như 42 = 18 + 4 + 20, dễ đọc sai. Nên tách rõ: tổng slot capacity / đã đặt / đang giữ / còn trống, hoặc đổi nhãn. Ô slot vừa mã hoá bằng màu vừa có chữ (tốt cho a11y). Vấn đề UI: khung giờ dùng nhãn 'Có thể đặt · 0/3' — 0/3 nghĩa là đã đặt 0, còn 'Còn 2 chỗ · 1/3' cùng lúc hiển thị 2 cách đếm ngược nhau → nên thống nhất 1 quy ước. Sức chứa 3/slot khớp mô hình capacity CAP-01; logic giữ chỗ + TTL phải nằm ở FastAPI/SQL, không phải TSX. Màn này là tiền-lượt-khám (sinh appointment), sau đó check-in mới sinh 7 work item xương sống.

## CSKH

### Công việc chăm sóc (Nhiệm vụ hôm nay)
`image_1.jpg` · V1 · CSKH  
3 cột: sidebar | danh sách công việc (list) | panel chi tiết + form xử lý

Không gian làm việc để CSKH chọn 1 công việc chăm sóc, ghi kết quả liên hệ và đóng công việc.

- **KPI:** Cần làm hôm nay 12 · Quá SLA 3 · Chờ phản hồi 5 · Đã hoàn thành 24
- **Hành động:** Chọn kết quả liên hệ, Chọn bước tiếp theo, Lưu nháp, Hoàn thành công việc
- **Dữ liệu cần:** follow_up_task: id/code, type, title, due_at, status, assignee, reason, customer: name, code, phone, link hồ sơ, lịch sử liên hệ gần nhất, enum kết quả liên hệ + enum bước tiếp theo, điều kiện hoàn thành (definition of done) theo loại việc, đếm KPI: cần làm hôm nay, quá SLA, chờ phản hồi, đã hoàn thành
- **Ghi chú:** Đây là màn mạnh nhất trong 4: có checklist điều kiện hoàn thành → nút Hoàn thành nên disable đến khi đủ 3 điều kiện (thiết kế chưa thể hiện trạng thái disabled). KPI lệch giữa 2 màn: 'Chờ xác nhận 8' (màn Khách hàng) vs 'Chờ phản hồi 5' (màn này) trong khi 3 KPI kia y hệt — hai chỉ số này đo hai thứ khác nhau nhưng đặt cùng vị trí, dễ hiểu nhầm; cần đặt tên/định nghĩa phân biệt. Badge trạng thái ở đây (Đến hạn, Quá SLA, Chờ phản hồi, Sẵn sàng, Cần liên hệ) lại là bộ THỨ BA, khác cả màn 1 lẫn 8 trạng thái kernel → phải thống nhất về ready/in_progress/blocked/overdue/completed. Mô hình 'work item + due + assignee + DoD' này chính là kernel work_item áp cho việc CSKH: nên dùng chung bảng work_item với node_definition riêng thay vì bảng follow-up song song.

### Lịch sử thao tác (audit log)
`image_3.jpg` · V1 · CSKH / TRUONG_CA / MANAGEMENT  
3 cột: sidebar | dòng thời gian sự kiện (gom theo ngày) | panel chi tiết sự kiện

Tra cứu ai đã thay đổi gì, lúc nào, và dữ liệu trước/sau của thay đổi đó.

- **Hành động:** Lọc theo ngày/người dùng/loại thao tác, Xem chi tiết diff, Xuất CSV, Xem sự kiện liên quan
- **Dữ liệu cần:** audit_event: id/code, occurred_at, actor (staff hoặc system), actor_role, entity_type, entity_id/label, action_type, summary, source/channel, context/reason, field-level diff: field, old_value, new_value, correlation id để 'Xem sự kiện liên quan', đếm KPI: sự kiện hôm nay, người dùng hoạt động, thay đổi lịch hẹn, cảnh báo cần xem
- **Ghi chú:** KPI ở đây yếu nhất về ý nghĩa: 'Người dùng hoạt động 12' và 'Thay đổi lịch hẹn 31' là số đếm mô tả, không dẫn tới hành động; chỉ 'Cảnh báo cần xem 3' là actionable → nên giữ Cảnh báo + Sự kiện hôm nay, thay 2 thẻ kia bằng thứ có hành động (vd 'Sửa sau khi chốt', 'Thao tác bị từ chối/403'). KPI cũng không click-lọc được. Về UI: diff hiển thị tốt (trước/sau + ngữ cảnh), có audit cho actor 'Hệ thống' — đúng hướng. Cần đảm bảo audit ghi từ tầng DB/FastAPI (trigger hoặc service), không phải do frontend gửi, nếu không log sẽ khuyết. 'Xuất CSV' trên dữ liệu bệnh nhân cần giới hạn quyền (MANAGEMENT/TRUONG_CA) và chính nó phải bị audit.

### Quản lý khách hàng
`image.jpg` · V1 · CSKH  
2 cột: sidebar điều hướng | vùng nội dung (KPI row → tabs → search/filter → bảng + phân trang)

Danh sách khách hàng CSKH đang theo dõi, kèm trạng thái và bước tiếp theo phải làm cho từng người.

- **KPI:** Cần xử lý hôm nay 12 · Quá SLA 3 · Chờ xác nhận 8 · Đã hoàn thành 24
- **Hành động:** Thêm khách hàng, Lọc / tìm kiếm, Mở menu hành động từng dòng, Chuyển tab sang Nhiệm vụ hôm nay
- **Dữ liệu cần:** customer.id, full_name, customer_code, trạng thái CSKH của khách (Đã khám / Chờ xác nhận lịch / Quá SLA / Cần tái khám / Đang tư vấn / Hoàn thành), lần tương tác gần nhất: loại + kênh (Zalo/gọi) + timestamp, work_item/follow-up kế tiếp: loại hành động + due_at, assignee (staff phụ trách), đếm KPI: cần xử lý hôm nay, quá SLA, chờ xác nhận, đã hoàn thành
- **Ghi chú:** KPI CSKH đúng bản chất tồn đọng/deadline (workload + SLA), không phải KPI doanh thu — hợp lý. Nhưng 'Chờ xác nhận 8' không có tab tương ứng (tab chỉ có Cần theo dõi/Quá SLA), KPI không click-through được → nên cho mỗi KPI lọc thẳng vào bảng. Bảng 6 dòng/68 KH mà trang 12 → cỡ trang quá nhỏ. Cột 'Trạng thái' là trạng thái CSKH tự chế, KHÔNG khớp 8 trạng thái kernel đã chốt (ready/assigned/in_progress/blocked/completed/skipped/cancelled/overdue) — cần map rõ hoặc đổi tên cột thành 'Giai đoạn'. Màn này nằm ngoài xương sống lượt khám, thuộc lớp CRM trước/sau lượt.

### Theo dõi sau khám
`ChatGPT_Image_12_01_23_24_thg_7_2026_(2).jpg` · V2 · CSKH  
3 cột: sidebar | danh sách follow-up | panel chi tiết; KPI row 5 thẻ phía trên

Bản V2 của bảng điều phối follow-up sau khám: hàng đợi theo hạn xử lý + chi tiết case + thao tác nhanh.

- **KPI:** Tổng follow-up 482 (Case đang mở) · Quá hạn 68 (Cần xử lý ngay) · Đến hạn hôm nay 96 (Hạn trong ngày) · Đã hoàn tất hôm nay 124 (Hoàn tất trong ngày) · Hoàn tất đúng SLA 92,4% (Mục tiêu ≥ 90%)
- **Hành động:** Gọi lại, Gửi tin nhắn, Tạo tái hẹn, Đóng case, Chuyển giao, Xem chi tiết nội dung được duyệt
- **Dữ liệu cần:** Như bản V1 của màn này, Thêm: timeline hoạt động gần đây của case (loại sự kiện + timestamp), Mã lịch hẹn liên kết ngược về visit (LH250514-001)
- **Ghi chú:** Thế hệ V2 (topbar có đồng hồ 10:40, artboard hẹp hơn, sidebar gọn hơn). Cùng màn với ảnh (10) V1 — khác biệt V1→V2: bỏ form 'Ghi nhận kết quả follow-up' inline, thay bằng 'Hoạt động gần đây'; chip SLA chỉ còn ở dòng active; sort đổi sang toggle 'Hạn xử lý ↑↓'. Bất nhất cần chú ý: header nói 'Hiển thị 1–10 trong 482' + '10 / trang' nhưng list vẽ 12 dòng; và KPI y hệt bản V1 dù khác ngày (14/05 vs 11/05) → số KPI trong mockup là tĩnh, khi implement phải bind theo ngày đang chọn.

### Theo dõi sau khám (Chăm sóc sau khám)
`ChatGPT_Image_10_45_28_24_thg_7_2026_(10).jpg` · V1 · CSKH  
3 cột: sidebar | danh sách follow-up (list) | panel chi tiết case + thao tác nhanh; KPI row 5 thẻ phía trên

CSKH quản lý hàng đợi follow-up sau khám: liên hệ, trả kết quả trong phạm vi được duyệt, tạo tái hẹn hoặc đóng case đúng SLA.

- **KPI:** Tổng follow-up 482 (Case đang mở) · Quá hạn 68 (Cần xử lý ngay) · Đến hạn hôm nay 96 (Hạn trong ngày) · Đã hoàn tất hôm nay 124 (Hoàn tất trong ngày) · Hoàn tất đúng SLA 92,4% (Mục tiêu ≥ 90%) — donut
- **Hành động:** Gọi lại, Gửi tin nhắn, Tạo tái hẹn, Đóng case, Chuyển giao người phụ trách, Ghi nhận kết quả follow-up + ghi chú
- **Dữ liệu cần:** Danh sách follow-up case theo người phụ trách/ngày, sort theo hạn, Bệnh nhân: tên, năm sinh, giới, tuổi, mã KH/hồ sơ, Lý do follow-up, nguồn (khám phụ khoa…), ngày khám, mã lịch hẹn, SLA: hạn xử lý, trạng thái đến hạn/quá hạn, % hoàn tất đúng SLA, Người phụ trách + lịch sử chuyển giao, Số lần liên hệ + kênh đã consent (phone/Zalo/SMS), Trạng thái escalation, Bản ghi bác sĩ phê duyệt nội dung được phép trả (ai, lúc nào, nội dung)
- **Ghi chú:** Thế hệ V1 (không badge V2, topbar không có đồng hồ giờ). Gần như trùng ảnh (2) nhưng khác ngày (11/05/2026 vs 14/05/2026), khác nhóm khối dưới (bản này có form 'Ghi nhận kết quả follow-up', bản (2) có 'Hoạt động gần đây'), sort control khác ('Sắp xếp: Hạn gần nhất' vs 'Hạn xử lý ↑↓'). Đây là nhánh hậu-lượt-khám, nằm ngoài 7 node xương sống; nhận đầu vào từ nút 'Tạo theo dõi sau khám' ở màn Duyệt kết quả.

### Đặt lịch CSKH
`ChatGPT_Image_10_45_17_24_thg_7_2026_(1).jpg` · V2 · CSKH  
Sidebar trái (6 mục CSKH) + topbar (date picker, chuông 3, avatar Trần Thị Lan/CSKH) + hàng thẻ 'Nguồn khách hàng' (4 kênh) + banner cảnh báo chặn (Lý do chặn → Hướng đi tiếp theo) + 3 cột: tìm/tạo hồ sơ & leads gần đây | form đặt lịch | panel tóm tắt đặt lịch + slot giữ tạm + danh sách chờ + điều kiện hoàn tất

CSKH tiếp nhận lead từ nhiều kênh, tra/tạo hồ sơ khách hàng rồi đặt lịch hẹn với bác sĩ ưu tiên, có cơ chế giữ chỗ tạm thời và danh sách chờ khi hết slot.

- **Hành động:** Xác nhận slot giữ chỗ, Thêm vào danh sách chờ, Tạo hồ sơ mới, Gia hạn giữ chỗ, Chọn slot khác, Tiếp tục
- **Dữ liệu cần:** lead/nguồn khách hàng (kênh, định danh kênh), hồ sơ khách hàng (họ tên, ngày sinh, tuổi, giới tính, SĐT, CMND/CCCD), danh mục chuyên khoa + lý do đặt lịch, danh sách bác sĩ + chi nhánh, lịch trống theo bác sĩ/chi nhánh/ngày (slot availability), bản ghi giữ chỗ tạm (hold) + TTL/hết hạn, hàng đợi waitlist theo slot (vị trí/tổng), lịch sử tương tác CSKH (số lần, kênh, nội dung, thời điểm)
- **Ghi chú:** V2 rõ ràng (badge V2 cạnh logo, topbar có chuông + avatar). Đây là màn TRƯỚC check-in (đặt lịch/pre-visit) nên không map vào 7 node xương sống LUOTKHAM-01..15; workspace gần với 'khu_dat_lich'. Không có KPI tile — đúng tinh thần 'form + trạng thái', không nhồi số. Điểm cần chốt: giữ chỗ hiển thị hai mốc lệch nhau (banner nói 15 phút / panel nói giữ đến 09:27 / form nói 'Hết hạn sau 14:32') — 14:32 nhiều khả năng là đồng hồ đếm ngược mm:ss nhưng dễ đọc nhầm thành giờ; nên thống nhất định dạng. Ngày trong topbar 07/05/2026 khớp dữ liệu lead.

### Đặt lịch CSKH
`ChatGPT_Image_12_01_23_24_thg_7_2026_(1).jpg` · V2 · CSKH  
3 cột trong 1 trang tác vụ: nguồn khách + tìm/tạo hồ sơ | form đặt lịch | tóm tắt đặt lịch + slot giữ + danh sách chờ; có header bệnh nhân và banner cảnh báo trên cùng

CSKH tư vấn và đặt lịch hẹn chủ động cho khách/lead, xử lý tình huống slot bị chiếm và giữ chỗ tạm thời có đếm ngược.

- **KPI:** Không có KPI card. Chỉ số đáng chú ý mang tính state: đếm ngược giữ chỗ 14:32, TTL 15 phút, vị trí danh sách chờ #2/4
- **Hành động:** Tiếp tục đặt lịch (tạo phiếu hẹn + gửi xác nhận), Chọn slot khác, Gia hạn giữ chỗ, Tạo hồ sơ mới, Xem hồ sơ bệnh nhân / Xem lịch sử tương tác, Xem chi tiết danh sách chờ
- **Dữ liệu cần:** Lead/khách: tên, năm sinh, giới, tuổi, mã KH, SĐT, ngày tạo; danh sách leads gần đây, Danh mục lý do đặt lịch, chuyên khoa, bác sĩ, chi nhánh, Lịch slot khả dụng theo bác sĩ/chi nhánh/ngày (kèm trạng thái đã bị đặt), Cơ chế hold slot: slot id, thời điểm hết hạn (TTL 15 phút), server time để đếm ngược, Waitlist: vị trí và tổng số người chờ theo slot, Nguồn khách hàng (phone/FB/website/tái hẹn bác sĩ), Ghi chú ≤200 ký tự, Cấu hình gửi xác nhận SMS/Zalo
- **Ghi chú:** Thế hệ V2 (topbar có đồng hồ giờ 08:30, chuông + avatar; artboard hẹp hơn). Không thấy badge chữ 'V2' rõ trên artboard nhưng đặc trưng topbar khớp V2. Màn thuộc workspace 'khu_dat_lich', đứng TRƯỚC lượt khám nên không sinh work_item nào của LUOTKHAM-01..15. Rủi ro: thời gian giữ chỗ hiển thị 2 nơi (banner + form + card phải) — phải cùng 1 nguồn server-side TTL, không tính client, và logic hold/waitlist phải nằm ở FastAPI chứ không phải TSX.

## TRUONG_CA

### Điều phối lượt khám — Trưởng ca
`image_22.jpg` · V1 · TRUONG_CA (Trưởng ca)  
3 vùng: KPI strip + thanh filter | lưới 8 thẻ trạm dịch vụ + bảng bệnh nhân cần điều phối (có phân trang) | drawer phải 'Chi tiết hành trình' của bệnh nhân được chọn

Giám sát toàn bộ trạm dịch vụ, SLA, nguồn lực và điểm nghẽn theo thời gian thực để gỡ chặn và điều phối bệnh nhân.

- **Node kernel:** LUOTKHAM-01, LUOTKHAM-03, LUOTKHAM-05, LUOTKHAM-13, LUOTKHAM-14, LUOTKHAM-15
- **KPI:** Đang trong phòng khám: 146 · Đang chờ: 38 · Bị chặn: 7 · Quá SLA: 5 · Nguồn lực khả dụng: 18/22
- **Hành động:** Gỡ chặn & điều phối tiếp (nút chính, bắt buộc nhập lý do), Đổi mức ưu tiên, Điều chuyển trạm, Giao người xử lý, Chọn nhiều bệnh nhân (bulk qua checkbox), Lọc/sắp xếp theo SLA, ưu tiên, lý do chặn
- **Dữ liệu cần:** station/node aggregate: số chờ, đang phục vụ, thời gian chờ TB, trạng thái SLA, phòng, nhân sự phụ trách, năng lực (đang dùng/tối đa), work_item cấp bệnh nhân: trạm hiện tại, trạm kế tiếp, thời gian chờ, SLA mục tiêu, ưu tiên, lý do chặn, người phụ trách, dependency graph để suy ra 'trạm kế tiếp' và dịch vụ song song (SS/FS), resource: 18/22 nguồn lực khả dụng, trạng thái thiết bị/phòng (bảo trì SA2), audit log điều phối + lý do bắt buộc cho mọi hành động ghi đè, realtime channel (auto refresh / cập nhật trực tiếp)
- **Ghi chú:** V1. Đây là màn 'bang_dieu_phoi' — view ngang toàn bộ work_item của nhiều lượt khám, đúng tinh thần kernel (trạm = node_definition, trạm kế tiếp = dependency). Legend timeline chỉ dùng 4 trạng thái (hoàn tất/đang thực hiện/chờ/bị chặn) — là tập con của bộ 8 đã chốt; cần map ready+assigned → 'Chờ xử lý', in_progress → 'Đang thực hiện'. Checkbox hàng loạt có nhưng chưa thấy thanh bulk-action, cần bổ sung.
