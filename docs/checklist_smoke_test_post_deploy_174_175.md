# CHECKLIST SMOKE-TEST SAU DEPLOY — GIAO THOA #174 VÀ #175

> **Mục đích:** Kịch bản kiểm thử thao tác người thật trên môi trường sau khi deploy (staging/prod).
> **Phạm vi:** Kiểm chứng sự hội tụ của PR #174 (Quyền `ket_qua.xac_nhan`, xác nhận tệp kết quả ngoài, 2-tier gate, Khám xong HANDOFF/TERMINAL) và PR #175 (Kê đơn danh mục `drug_catalog`, tính giá & thu tiền không qua gate kho vật lý).
> **Nguyên tắc:** Thao tác từng bước bằng giao diện người dùng (UI), có chốt kiểm tra phản hồi API và dữ liệu database khi gặp sự cố. **Không deploy trong đợt này — tài liệu dùng ngay sau khi deploy.**

---

## BẢNG TÀI KHOẢN VÀ VAI TEST MẪU

> **Lưu ý về tài khoản:** Chọn tài khoản test thực tế sau deploy/staging; checklist không giả định các tài khoản này đã tồn tại sẵn trong database.

| Vai trò | Tài khoản test đề xuất (Placeholder) | Quyền / Capability yêu cầu | Màn hình chính |
|---|---|---|---|
| **Quản lý** | `<tai-khoan-quan-ly-test>` | Role `MANAGEMENT` | `/nhan-su` |
| **Bác sĩ khám** | `<tai-khoan-bac-si-test>` | Role `DOCTOR` | `/ban-kham` |
| **Điều dưỡng / KTV** | `<tai-khoan-nhan-vien-xac-nhan-test>` | Role `NURSE_ULTRASOUND`, có/chưa có `ket_qua.xac_nhan` | `/xac-nhan-ket-qua`, `/do-sinh-hieu` |
| **Đối tác xét nghiệm** | `<tai-khoan-doi-tac-test>` | Role `PARTNER` | `/doi-tac` |
| **Lễ tân / Thu ngân** | `<tai-khoan-le-tan-test>` | Role `RECEPTION` / `CASHIER` | `/thu-ngan/thuoc` |

---

## KỊCH BẢN CHI TIẾT 9 SMOKE CASES

### SMOKE 1 — Bác sĩ kê thuốc catalog → Lễ tân thu tiền CASH (Flag OFF)

- **Mục tiêu:** Bác sĩ kê thuốc chọn từ danh mục có sẵn; Lễ tân nhìn thấy hóa đơn chính xác và thu tiền CASH thành công mà không bị chặn bởi kho (không đòi hỏi tồn kho, lô, hạn dùng hay sinh phiếu xuất).
- **Tài khoản:** Bác sĩ (`<tai-khoan-bac-si-test>`) + Lễ tân (`<tai-khoan-le-tan-test>`).
- **Mã bệnh nhân test:** `BN-TEST-SMOKE-01` (Tạo mới hoặc chọn lượt khám chưa kê thuốc).

| Bước | Diễn giải thao tác (Người thật) | Màn hình | Thao tác / Nút bấm (UI ví dụ) | Dữ liệu đầu vào | Kết quả nhìn thấy trên giao diện | State / API / DB đối chiếu khi lỗi |
|---|---|---|---|---|---|---|
| 1.1 | Bác sĩ vào bàn khám | `/ban-kham` | Chọn bệnh nhân `BN-TEST-SMOKE-01` | Lượt khám trạng thái `OPEN` | Mở hồ sơ bệnh án khám bệnh | `visit.status = 'OPEN'` |
| 1.2 | Kê đơn thuốc từ danh mục | Tab **Đơn thuốc** | Gõ tên thuốc vào ô tìm kiếm | "Augmentin 1g" hoặc "Paracetamol 500mg" | Hiện gợi ý từ `drug_catalog` kèm đơn giá (ví dụ: 15.000đ/viên) | API `GET /api/catalog` trả danh mục thuốc |
| 1.3 | Nhập số lượng & cách dùng | Tab **Đơn thuốc** | Chọn thuốc từ gợi ý, nhập ô Số lượng & Liều dùng | Số lượng: `14 viên`, Liều: `Ngày 2 viên sáng chiều sau ăn` | Dòng thuốc hiển thị đủ Tên thuốc, Đơn vị (viên), Đơn giá (15.000đ), Thành tiền (210.000đ) | `prescription.drug_catalog_id IS NOT NULL`, `quantity_num = 14` |
| 1.4 | Bác sĩ hoàn tất khám | Tab **Chẩn đoán** & Nút hành động | Bấm **Lưu bệnh án** -> Bấm **Khám xong** | Chọn kết thúc lượt khám (`DONE`) | Thông báo khám thành công, lượt chuyển sang trạng thái đã khám xong | `visit.exam_completed_at IS NOT NULL` |
| 1.5 | Lễ tân mở quầy thu ngân | `/thu-ngan/thuoc` | Mở danh sách chờ thu tiền thuốc | Tìm mã `BN-TEST-SMOKE-01` | Thấy bệnh nhân trong danh sách chờ thu với số tiền đúng (ví dụ: 210.000đ) | Dashboard API `GET /api/cashier?modes=thuoc` (Backend: `GET /api/v1/cashier/board?modes=thuoc`) |
| 1.6 | Kiểm tra chi tiết hóa đơn | `/thu-ngan/thuoc` | Bấm vào dòng bệnh nhân | - | Chi tiết hiển thị đúng: Tên thuốc, số lượng, đơn giá, thành tiền. **KHÔNG** hiện cảnh báo "chưa xác định thuốc trong kho", **KHÔNG** yêu cầu chọn lô/hạn | `tinh_hoa_don` trả `thu_duoc = True`, `van_de = []` |
| 1.7 | Thực hiện thu tiền CASH | `/thu-ngan/thuoc` | Chọn phương thức **Tiền mặt (CASH)** -> Bấm **Xác nhận thu tiền** | Khách đưa đủ tiền mặt | Trạng thái hiển thị **ĐÃ THANH TOÁN (PAID)**, cho phép in phiếu thu | Dashboard API `POST /api/payment` (Backend: `POST /api/v1/payments`), `payment_cycle.status = 'PAID'`, `payment.payment_method = 'CASH'`, không có bản ghi `inventory_txn` nào được tạo |

- **Kết quả nghiệm thu:** ☐ PASS    ☐ FAIL
- **Ghi chú / Mã hóa đơn đối soát:** `....................................................`

---

### SMOKE 2 — Bác sĩ kê thuốc catalog → Lễ tân thu tiền chuyển khoản QR / TRANSFER

- **Mục tiêu:** Quy trình thanh toán điện tử phải qua trạng thái chờ xác minh giao dịch (`PENDING_VERIFICATION`), sau khi xác minh mã giao dịch mới chuyển `PAID`, không bị bypass xác minh ngay cả khi không dùng kho.
- **Tài khoản:** Bác sĩ (`<tai-khoan-bac-si-test>`) + Lễ tân (`<tai-khoan-le-tan-test>`).
- **Mã bệnh nhân test:** `BN-TEST-SMOKE-02`.

| Bước | Diễn giải thao tác | Màn hình | Thao tác / Nút bấm (UI ví dụ) | Dữ liệu đầu vào | Kết quả nhìn thấy | State / API / DB đối chiếu |
|---|---|---|---|---|---|---|
| 2.1 | Kê đơn thuốc & Khám xong | `/ban-kham` | Kê thuốc catalog -> Lưu -> Khám xong | Thuốc catalog có giá, ví dụ: 100.000đ | Khám xong thành công | `visit.exam_completed_at IS NOT NULL` |
| 2.2 | Lễ tân tạo thanh toán Chuyển khoản | `/thu-ngan/thuoc` | Chọn phương thức **Chuyển khoản (TRANSFER)** -> Bấm **Tạo giao dịch thu** | Mã BN `BN-TEST-SMOKE-02` | Màn hình hiện mã QR chuyển khoản kèm thông tin tài khoản và số tiền | Dashboard API `POST /api/payment` với `method: "TRANSFER"` (Backend: `POST /api/v1/payments`), trả `status = 'PENDING_VERIFICATION'`, `payment_cycle.status = 'PENDING_VERIFICATION'` |
| 2.3 | Kiểm tra trạng thái chờ duyệt | `/thu-ngan/thuoc` | Xem trạng thái thanh toán của lượt | - | **CHƯA ĐƯỢC CHUYỂN THÀNH PAID**, gắn nhãn "Chờ xác minh chuyển khoản" | `payment_cycle.status` vẫn giữ nguyên `PENDING_VERIFICATION` |
| 2.4 | Lễ tân xác minh giao dịch | `/thu-ngan/thuoc` | Nhập **Mã giao dịch ngân hàng** (FT Code) -> Bấm **Xác nhận đã nhận tiền** | Mã GD: `FT26092088899` | Giao dịch chuyển sang trạng thái xanh **ĐÃ THANH TOÁN (PAID)** | Dashboard API `POST /api/payment` với `{ action: "xac-minh", paymentCycleId, reference }` (Backend: `POST /api/v1/payments/xac-minh`), `payment_cycle.status = 'PAID'`, ghi nhận `transfer_reference` |

- **Kết quả nghiệm thu:** ☐ PASS    ☐ FAIL
- **Ghi chú / Mã giao dịch:** `....................................................`

---

### SMOKE 3 — Thuốc ngoài danh mục (Free-text không có ID)

- **Mục tiêu:** Bác sĩ gõ tự do tên thuốc không có trong danh mục giá -> hệ thống không tự ý tính thành 0đ, quầy thu ngân phát hiện và chặn thu tiền đúng lý do "thuốc chưa có trong danh mục giá".
- **Tài khoản:** Bác sĩ (`<tai-khoan-bac-si-test>`) + Lễ tân (`<tai-khoan-le-tan-test>`).
- **Mã bệnh nhân test:** `BN-TEST-SMOKE-03`.

| Bước | Diễn giải thao tác | Màn hình | Thao tác / Nút bấm (UI ví dụ) | Dữ liệu đầu vào | Kết quả nhìn thấy | State / API / DB đối chiếu |
|---|---|---|---|---|---|---|
| 3.1 | Bác sĩ kê thuốc ngoài danh mục | `/ban-kham` (Tab Đơn thuốc) | Gõ tên thuốc tự do không chọn gợi ý dropdown | "Thuốc đặc trị thảo dược gia truyền XYZ", SL: `1 lọ` | Dòng đơn thuốc lưu dưới dạng free-text, không có đơn giá tự động | `prescription.drug_catalog_id IS NULL`, `prescription.drug_name_raw` lưu đúng text |
| 3.2 | Bác sĩ lưu hồ sơ khám | `/ban-kham` | Bấm **Lưu bệnh án** | - | Bệnh án lưu thành công kèm dòng thuốc ngoài danh mục | `clinical_record` lưu draft/prescription |
| 3.3 | Lễ tân kiểm tra quầy thu | `/thu-ngan/thuoc` | Mở hồ sơ thu tiền của `BN-TEST-SMOKE-03` | Mã `BN-TEST-SMOKE-03` | Cảnh báo rõ ràng: **"Thuốc chưa có trong danh mục giá: Thuốc đặc trị thảo dược gia truyền XYZ"** | Dashboard API `GET /api/cashier?modes=thuoc`, `tinh_hoa_don` trả `thu_duoc = False`, danh sách `van_de` có mô tả lỗi |
| 3.4 | Kiểm tra chốt an toàn nút thu | `/thu-ngan/thuoc` | Quan sát nút bấm thu tiền | - | **Nút "Thu tiền" bị vô hiệu hóa (disabled)** hoặc bấm vào báo lỗi từ chối, tuyệt đối **không có dòng 0đ** để thu nhầm | Gọi API thanh toán nhận `400 / 422 ValidationError` |

- **Kết quả nghiệm thu:** ☐ PASS    ☐ FAIL
- **Ghi chú:** `....................................................`

---

### SMOKE 4 — Quản lý cấp và thu hồi quyền xác nhận kết quả (`ket_qua.xac_nhan`)

- **Mục tiêu:** Quản lý có thể cấp quyền xác nhận tệp kết quả cho nhân sự từ màn Nhân sự, reload trang quyền vẫn giữ, nhân viên lập tức vào được màn xác nhận; khi thu hồi, nhân viên lập tức bị chặn (403).
- **Tài khoản:** Quản lý (`<tai-khoan-quan-ly-test>`) + Nhân viên (`<tai-khoan-nhan-vien-xac-nhan-test>`).

| Bước | Diễn giải thao tác | Màn hình | Thao tác / Nút bấm (UI ví dụ) | Dữ liệu đầu vào | Kết quả nhìn thấy | State / API / DB đối chiếu |
|---|---|---|---|---|---|---|
| 4.1 | Nhân viên chưa có quyền kiểm tra | `/xac-nhan-ket-qua` | Đăng nhập tài khoản nhân viên, mở URL trực tiếp | Tài khoản nhân viên | Bị chặn truy cập, báo lỗi **403: Chưa được cấp quyền xác nhận kết quả** | API `/api/cskh/ket-qua/cho-xac-nhan` trả `403 Forbidden` |
| 4.2 | Quản lý mở danh sách nhân sự | `/nhan-su` | Đăng nhập tài khoản Quản lý, tìm nhân viên test | Tìm kiếm theo tên | Thấy hồ sơ nhân viên trong danh sách | `staff` query trả đúng ID nhân viên |
| 4.3 | Quản lý bật quyền xác nhận | `/nhan-su` | Bật switch / checkbox **"Được xác nhận tệp kết quả"** | Nhân viên test | Switch chuyển sang trạng thái BẬT, thông báo cập nhật quyền thành công | Dashboard API `POST /api/staff/{id}/capabilities` (Backend: `POST /api/v1/staff/{id}/capabilities`), DB có dòng trong `staff_capability`, `event_log` có `staff.capability_granted` |
| 4.4 | Kiểm tra độ bền (persistence) | `/nhan-su` | Bấm F5 / Reload lại trang Quản lý nhân sự | - | Switch **"Được xác nhận tệp kết quả" vẫn BẬT** | Dashboard API `GET /api/staff/{id}/capabilities` (Backend: `GET /api/v1/staff/{id}/capabilities`) trả `["ket_qua.xac_nhan"]` |
| 4.5 | Nhân viên truy cập màn xác nhận | `/xac-nhan-ket-qua` | Đăng nhập tài khoản nhân viên, vào màn xác nhận | - | **Vào được trang bình thường**, danh sách hàng chờ tệp kết quả hiển thị | Dashboard API `GET /api/cskh/ket-qua/cho-xac-nhan` trả mã `200 OK` |
| 4.6 | Quản lý thu hồi quyền | `/nhan-su` | Đăng nhập Quản lý, gạt switch **"Được xác nhận tệp kết quả"** sang TẮT | Nhân viên test | Switch TẮT, thông báo thu hồi quyền thành công | Dashboard API `DELETE /api/staff/{id}/capabilities?capability=ket_qua.xac_nhan` (Backend: `DELETE /api/v1/staff/{id}/capabilities/ket_qua.xac_nhan`), `event_log` có `staff.capability_revoked` |
| 4.7 | Nhân viên bị chặn ngay lập tức | `/xac-nhan-ket-qua` | Nhân viên bấm F5 hoặc thao tác trên màn xác nhận | - | **Bị chặn lại ngay lập tức (403)**, không còn quyền thao tác | DB không còn capability, queue từ chối `403` |

- **Kết quả nghiệm thu:** ☐ PASS    ☐ FAIL
- **Ghi chú:** `....................................................`

---

### SMOKE 5 — Quy trình kết quả ngoài 2 tầng: Đối tác upload → Xác nhận hợp lệ → Bác sĩ cho phép gửi

- **Mục tiêu:** Tệp kết quả bên ngoài phải trải qua đúng quy trình 2 tầng: KTV có quyền xác nhận `HOP_LE` -> Bác sĩ mới được duyệt `cho_phep_gui`. Không được có bước nào tự ý nhảy cóc.
- **Tài khoản:** Bác sĩ (`<tai-khoan-bac-si-test>`), Đối tác Lab (`<tai-khoan-doi-tac-test>`), Nhân viên đã có quyền (`<tai-khoan-nhan-vien-xac-nhan-test>`).
- **Mã bệnh nhân test:** `BN-TEST-SMOKE-05`.

| Bước | Diễn giải thao tác | Màn hình | Thao tác / Nút bấm (UI ví dụ) | Dữ liệu đầu vào | Kết quả nhìn thấy | State / API / DB đối chiếu |
|---|---|---|---|---|---|---|
| 5.1 | Bác sĩ chỉ định dịch vụ ngoài | `/ban-kham` | Chọn chỉ định xét nghiệm gửi ngoài (ví dụ: `XN-MAU-NGOAI`) | Bệnh nhân `BN-TEST-SMOKE-05` | Chỉ định được tạo với cờ `lam_ben_ngoai = true` | `service_order.node_code` thuộc nhóm ngoài |
| 5.2 | Đối tác nhận việc & upload tệp | `/doi-tac` | Đăng nhập tài khoản đối tác, chọn đơn việc, bấm **Tải tệp kết quả lên** | Tệp PDF kết quả xét nghiệm test (`kq_test.pdf`) | Tệp tải lên thành công, trạng thái hiển thị **CHỜ XÁC NHẬN** | `tep_ket_qua.xac_nhan_trang_thai = 'CHO_XAC_NHAN'` |
| 5.3 | Kiểm tra chốt chặn bác sĩ sớm | `/ban-kham` (Hồ sơ kết quả) | Bác sĩ mở tệp kết quả xem thử | Bấm nút **Cho phép gửi kết quả** | **BỊ CHẶN**, hệ thống báo lỗi: "Tệp kết quả chưa được xác nhận hợp lệ" | Trigger DB hoặc API từ chối: `cho_phep_gui` chỉ cho phép khi `xac_nhan_trang_thai = 'HOP_LE'` |
| 5.4 | Nhân viên xác nhận HỢP LỆ | `/xac-nhan-ket-qua` | Đăng nhập nhân viên có quyền, mở hàng chờ, xem tệp -> Bấm **Xác nhận hợp lệ** | Lý do (tùy chọn): "Đạt chuẩn xét nghiệm" | Tệp chuyển sang trạng thái xanh **HỢP LỆ**, biến mất khỏi hàng chờ chưa xác nhận | Dashboard API `POST /api/cskh/ket-qua/[tepId]/xac-nhan` (Backend: `POST /api/v1/cskh/ket-qua/tep/{id}/xac-nhan`), `tep_ket_qua.xac_nhan_trang_thai = 'HOP_LE'`, `event_log` có `tep_ket_qua.xac_nhan` |
| 5.5 | Bác sĩ cho phép gửi | `/ban-kham` | Bác sĩ mở lại kết quả -> Bấm **Cho phép gửi cho khách** | - | Nút thành công, nhãn hiển thị **ĐÃ CHO PHÉP GỬI**, ghi nhận tên bác sĩ và thời điểm duyệt | Dashboard API `POST /api/cskh/ket-qua/[tepId]/cho-phep-gui` (Backend: `POST /api/v1/cskh/ket-qua/tep/{id}/cho-phep-gui`), `tep_ket_qua.cho_phep_gui = true`, `cho_phep_gui_boi = bác sĩ`, `cho_phep_gui_luc IS NOT NULL` |

- **Kết quả nghiệm thu:** ☐ PASS    ☐ FAIL
- **Ghi chú / Tệp ID:** `....................................................`

---

### SMOKE 6 — Chốt chặn tự xác nhận tệp (Self-upload Prevention)

- **Mục tiêu:** Người tải lên tệp kết quả tuyệt đối không được tự xác nhận tệp của chính mình (chống gian lận / sai sót).
- **Tài khoản:** Nhân viên vừa có quyền upload vừa có capability `ket_qua.xac_nhan` (ví dụ: `<tai-khoan-nhan-vien-xac-nhan-test>`).

| Bước | Diễn giải thao tác | Màn hình | Thao tác / Nút bấm (UI ví dụ) | Dữ liệu đầu vào | Kết quả nhìn thấy | State / API / DB đối chiếu |
|---|---|---|---|---|---|---|
| 6.1 | Nhân viên tự upload tệp | Màn hình tiếp nhận / Hồ sơ | Đăng nhập nhân viên test, tải lên 1 tệp kết quả | Tệp PDF test | Tệp ghi nhận `tai_len_boi_staff_id = staff_id nhân viên test` | `tep_ket_qua.tai_len_boi_staff_id` lưu đúng ID nhân viên |
| 6.2 | Mở hàng chờ xác nhận | `/xac-nhan-ket-qua` | Vẫn đăng nhập nhân viên test, mở danh sách chờ xác nhận | Tìm tệp vừa tải | Dòng tệp hiển thị nhãn "Bạn tải lên" | Giao diện nhận diện người tải |
| 6.3 | Thử bấm xác nhận | `/xac-nhan-ket-qua` | Bấm nút **Xác nhận hợp lệ** hoặc **Từ chối** | - | **Nút bị ẩn / disabled** hoặc bấm vào báo lỗi: **"Người tải lên không được tự xác nhận tệp của chính mình"** | Dashboard API `POST /api/cskh/ket-qua/[tepId]/xac-nhan` trả `400 / 403 SafetyGateError` |

- **Kết quả nghiệm thu:** ☐ PASS    ☐ FAIL
- **Ghi chú:** `....................................................`

---

### SMOKE 7 — Bác sĩ bấm "Khám xong" khi kết quả ngoài chưa hợp lệ → Chuyển HANDOFF

- **Mục tiêu:** Bác sĩ khám lượt có chỉ định bắt buộc đang chờ kết quả ngoài, khi bấm Khám xong hệ thống không được TERMINAL kết thúc lượt sai mà phải chuyển sang chế độ bàn giao / chờ kết quả (`SERVICES` / `HANDOFF`), giữ nguyên đơn thuốc và bệnh án.
- **Tài khoản:** Bác sĩ (`<tai-khoan-bac-si-test>`).
- **Mã bệnh nhân test:** `BN-TEST-SMOKE-07`.

| Bước | Diễn giải thao tác | Màn hình | Thao tác / Nút bấm (UI ví dụ) | Dữ liệu đầu vào | Kết quả nhìn thấy | State / API / DB đối chiếu |
|---|---|---|---|---|---|---|
| 7.1 | Mở khám & duyệt chỉ định ngoài | `/ban-kham` | Bắt đầu khám -> Duyệt chỉ định xét nghiệm ngoài | Chỉ định `need = VALID_RESULT` | Chỉ định chờ thực hiện | `round_requirement.need = 'VALID_RESULT'` |
| 7.2 | Kê đơn thuốc kèm theo | `/ban-kham` | Kê thuốc catalog (ví dụ: Cefixim 200mg, 10 viên) | Thuốc catalog | Đơn thuốc hiển thị trên bệnh án | `prescription` có `drug_catalog_id` |
| 7.3 | Bác sĩ bấm Khám xong phiên 1 | `/ban-kham` | Bấm nút **Khám xong** | Chọn phương án tiếp tục: Chờ kết quả cận lâm sàng | Lượt khám **KHÔNG KẾT THÚC TERMINAL**, hiển thị badge "Chờ kết quả cận lâm sàng (HANDOFF)" | `visit.status = 'OPEN'`, `visit.exam_completed_at IS NULL`, `consultation.outcome = 'SERVICES'` |
| 7.4 | Kiểm tra quầy thu ngân | `/thu-ngan/thuoc` | Lễ tân mở danh sách chờ thu tiền thuốc | Tìm mã `BN-TEST-SMOKE-07` | Lượt chưa kết thúc khám nên **chưa hiển thị đủ điều kiện thu thuốc** (đúng luật chặn thu trước khi khám xong) | Dashboard API `GET /api/cashier?modes=thuoc`, chốt an toàn thu ngân chặn khi chưa có `exam_completed_at` |

- **Kết quả nghiệm thu:** ☐ PASS    ☐ FAIL
- **Ghi chú:** `....................................................`

---

### SMOKE 8 — Kết quả bắt buộc đã hợp lệ → Bác sĩ review và Khám xong TERMINAL

- **Mục tiêu:** Sau khi kết quả ngoài đã được xác nhận hợp lệ, bác sĩ mở phiên đọc kết quả (REVIEW), bấm Khám xong -> hệ thống cho phép kết thúc TERMINAL chuẩn xác, không còn blocker giả, đơn thuốc catalog bảo toàn 100%.
- **Tài khoản:** Bác sĩ (`<tai-khoan-bac-si-test>`), Nhân viên (`<tai-khoan-nhan-vien-xac-nhan-test>`).
- **Mã bệnh nhân test:** `BN-TEST-SMOKE-07` (Tiếp tục từ Smoke 7).

| Bước | Diễn giải thao tác | Màn hình | Thao tác / Nút bấm (UI ví dụ) | Dữ liệu đầu vào | Kết quả nhìn thấy | State / API / DB đối chiếu |
|---|---|---|---|---|---|---|
| 8.1 | Xác nhận tệp hợp lệ | `/xac-nhan-ket-qua` | Nhân viên xác nhận tệp PDF gửi về là **HỢP LỆ** | Tệp kết quả của `BN-TEST-SMOKE-07` | Tệp chuyển sang HỢP LỆ, vòng đọc chuyển sang sẵn sàng (`ready`) | Dashboard API `POST /api/cskh/ket-qua/[tepId]/xac-nhan`, `review_round.status = 'ready'`, sinh phiên khám `consultation.kind = 'REVIEW'` |
| 8.2 | Bác sĩ mở phiên REVIEW | `/ban-kham` | Mở danh sách khám, chọn bệnh nhân trong hàng chờ đọc kết quả | Bấm **Bắt đầu đọc kết quả** | Mở phiên đọc kết quả, hiển thị tệp PDF đã được xác nhận hợp lệ | `consultation.status = 'in_progress'` |
| 8.3 | Bác sĩ xem kết quả & chẩn đoán | `/ban-kham` | Cho phép gửi file, điền chẩn đoán xác định và lời dặn | Chẩn đoán: "Viêm họng cấp", Lời dặn: "Uống thuốc theo đơn" | Thông tin bệnh án hoàn tất, đơn thuốc catalog trước đó vẫn nguyên vẹn | `clinical_record.soap_assessment`, `prescription.drug_catalog_id` không đổi |
| 8.4 | Bác sĩ bấm Khám xong phiên cuối | `/ban-kham` | Bấm nút **Khám xong** -> Chọn **Hoàn tất khám (DONE)** | Outcome: `DONE` | Lượt khám **KẾT THÚC THÀNH CÔNG (TERMINAL)**, bệnh nhân chuyển sang bước thu ngân / ra về | `visit.exam_completed_at IS NOT NULL`, không còn blocker giữ lượt |

- **Kết quả nghiệm thu:** ☐ PASS    ☐ FAIL
- **Ghi chú:** `....................................................`

---

### SMOKE 9 — Giao thoa toàn diện: Thuốc catalog + Kết quả ngoài + Thu tiền sau Khám xong

- **Mục tiêu:** Kiểm tra trọn vẹn điểm giao thoa giữa PR #174 và PR #175 trên cùng một bệnh nhân từ đầu đến cuối luồng.
- **Tài khoản:** Bác sĩ (`<tai-khoan-bac-si-test>`), Nhân viên (`<tai-khoan-nhan-vien-xac-nhan-test>`), Lễ tân (`<tai-khoan-le-tan-test>`), Đối tác Lab (`<tai-khoan-doi-tac-test>`).
- **Mã bệnh nhân test:** `BN-TEST-SMOKE-09`.

| Bước | Diễn giải thao tác | Màn hình | Thao tác / Nút bấm (UI ví dụ) | Dữ liệu đầu vào | Kết quả nhìn thấy | State / API / DB đối chiếu |
|---|---|---|---|---|---|---|
| 9.1 | Tiếp đón & Bác sĩ khám chính | `/ban-kham` | Mở lượt -> Bác sĩ kê 2 thuốc catalog + 1 chỉ định lab đối tác ngoài | Thuốc A (50k) x 2, Thuốc B (30k) x 1, XN ngoài (150k) | Đơn thuốc và chỉ định lưu đầy đủ vào hồ sơ | `prescription` có 2 dòng `drug_catalog_id` chuẩn |
| 9.2 | Khám xong phiên 1 -> HANDOFF | `/ban-kham` | Bác sĩ bấm Khám xong chuyển chờ kết quả ngoài | Bàn giao | Lượt chuyển trạng thái chờ kết quả | `consultation.outcome = 'SERVICES'`, `visit.status = 'OPEN'` |
| 9.3 | Đối tác gửi kết quả | `/doi-tac` | Đối tác lấy mẫu -> tải tệp PDF lên | Tệp PDF kết quả | Tệp chờ xác nhận | `tep_ket_qua.xac_nhan_trang_thai = 'CHO_XAC_NHAN'` |
| 9.4 | KTV xác nhận hợp lệ | `/xac-nhan-ket-qua` | KTV có capability duyệt tệp **HỢP LỆ** | Xác nhận | Tệp hợp lệ -> Kích hoạt phiên REVIEW cho bác sĩ | `review_round.status = 'ready'` |
| 9.5 | Bác sĩ đọc kết quả & Khám xong | `/ban-kham` | Bác sĩ mở phiên REVIEW, duyệt tệp, bấm **Khám xong (DONE)** | Bệnh án hoàn tất | **TERMINAL THÀNH CÔNG**, hồ sơ hoàn tất | `visit.exam_completed_at IS NOT NULL`, `prescription` giữ nguyên vẹn |
| 9.6 | Lễ tân thu tiền thuốc CASH | `/thu-ngan/thuoc` | Mở hồ sơ `BN-TEST-SMOKE-09` -> Kiểm tra chi tiết -> Thu CASH | Tiền mặt: 130.000đ | Hóa đơn hiển thị chính xác: 2 thuốc × đơn giá = 130.000đ. Thu tiền thành công, trạng thái **PAID**. Không yêu cầu chọn kho/lô, không sinh lỗi kho | Dashboard API `POST /api/payment` (Backend: `POST /api/v1/payments`), `payment_cycle.status = 'PAID'`, `payment_bill_line` đủ 2 dòng thuốc kèm catalog_id snapshot, không sinh `inventory_txn` |

- **Kết quả nghiệm thu:** ☐ PASS    ☐ FAIL
- **Ghi chú / Tổng tiền thu:** `....................................................`

---

## BIÊN BẢN KÝ DUYỆT SMOKE-TEST (Sau khi deploy)

| Nội dung | Người thực hiện | Thời gian thực hiện | Kết quả tổng | Chữ ký |
|---|---|---|---|---|
| Smoke 1: Bác sĩ kê thuốc -> Lễ tân thu CASH | | | | |
| Smoke 2: Thu tiền chuyển khoản QR/TRANSFER | | | | |
| Smoke 3: Thuốc ngoài danh mục chặn thu | | | | |
| Smoke 4: Cấp/thu hồi capability kết quả | | | | |
| Smoke 5: Kết quả ngoài 2 tầng duyệt | | | | |
| Smoke 6: Chặn tự xác nhận tệp upload | | | | |
| Smoke 7: Khám xong HANDOFF | | | | |
| Smoke 8: Khám xong TERMINAL | | | | |
| Smoke 9: Giao thoa toàn diện | | | | |

> **Quy định xử lý lỗi:** Nếu bất kỳ bước nào trong 9 smoke case trên bị FAIL, dừng kiểm thử, ghi lại mã bệnh nhân test, chụp màn hình console network + log API tương ứng để đội ngũ kỹ thuật đối chiếu rollback hoặc khắc phục theo đúng runbook.
