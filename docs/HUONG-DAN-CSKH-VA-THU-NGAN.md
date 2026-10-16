# Hướng dẫn thao tác — CSKH quản lý khách chưa có lịch · Thu ngân giảm giá

Dành cho CSKH, lễ tân, thu ngân. Mỗi bước nói đúng tên nút / màn trên giao diện.
Đối chiếu code ngày 16/10/2026.

> **Lưu ý về bản chạy:** các bước đánh dấu **[chờ bản mới]** chỉ đúng sau khi
> bản sửa 15/10 lên prod (PR #475 "chỉ lưu hồ sơ → sang Quản lý khách hàng",
> PR #476 "gọi xác nhận mọi lịch đặt hộ"). Trước đó màn vẫn chạy kiểu cũ.
> Chỗ nào ghi **(cần Tuyền xác nhận)** là chỗ chưa tìm thấy trong code để khẳng định.

---

## 1. CSKH quản lý khách CHƯA CÓ LỊCH HẸN

Khách gọi hỏi nhưng chưa chốt ngày khám: ghi hồ sơ lại để còn gọi, **không cần đặt lịch ngay**.

### 1.1 Nhập khách mới, chưa đặt lịch

1. Thanh bên → **Quản lý khách hàng** → bấm **Thêm khách hàng mới**
   (hoặc mục **Nhập thông tin khách hàng mới** / **Tạo bệnh nhân** ở thanh bên, hoặc
   tab **Thêm** trong màn **Đặt lịch** — cùng một biểu mẫu).
2. Chỉ **Họ tên** là bắt buộc; các ô khác để trống được, sửa sau ở hồ sơ.
3. Ở khối **Lịch hẹn khám**, tick **Chỉ lưu hồ sơ — chưa đặt lịch** (khối lịch ẩn đi).
4. Bấm **Nhập thông tin khách hàng** (CSKH / trưởng ca / quản lý) hoặc **Tạo bệnh nhân** (vai khác).
5. **[chờ bản mới]** Trang tự sang **Quản lý khách hàng**, mở đúng khách vừa tạo
   (địa chỉ `/customers?selected=…`). Trước bản mới: lễ tân về màn Tiếp đón, CSKH về hồ sơ khách.
   Nút **Dùng bệnh nhân này** (khách đã có sẵn) vẫn giữ đường cũ.

### 1.2 Gọi xác nhận khách mới

Khách chỉ lưu hồ sơ tự có trạng thái **Gọi điện xác nhận** (chip trên khách ở danh sách và
ở đầu khung giữa "Trạng thái khách hàng").

1. Ở danh sách bên trái bấm vào khách → cột phải hiện **số điện thoại** (bấm để gọi) và
   ô **Ghi chú** (không bắt buộc, gõ trước khi bấm nút kết quả).
2. Gọi xong, bấm **đúng chuyện đã xảy ra**:

| Nút | Dùng khi | Việc có hết không |
|---|---|---|
| **Đã liên hệ được** | nói chuyện được với khách | Hết việc **[chờ bản mới]**; chip đổi thành "Đã gọi xác nhận" |
| **Không nghe máy** | máy đổ chuông không ai nghe | Còn việc — phải gọi lại |
| **Không liên lạc được** | tắt máy / sai số | Còn việc — phải gọi lại |
| **Hẹn gọi lại sau** | khách bận, hẹn gọi lại | Còn việc |

3. Khách hẹn giờ cụ thể ("gọi lại sau 5h"): bấm **Hẹn gọi lại ngày…** (cuối cột phải) →
   chọn ngày, giờ (bỏ trống giờ = chỉ hẹn tới ngày), gõ **Gọi lại để làm gì** → **Hẹn**.
   Khách hiện lại ở danh sách đúng ngày đó.
4. Bác sĩ dặn tái khám (hoặc khách nói "tháng sau quay lại"): bấm **Hẹn ngày tái khám…** →
   chọn ngày, ghi lý do (không bắt buộc) → **Hẹn ngày tái khám**. Hệ thống tự sinh hai mốc gọi:
   trước 7 ngày mời đặt lịch, trước 1 ngày nhắc đi khám (hiện ở khối **Nhắc tái khám** cột giữa).
5. Khách đồng ý đặt lịch: cuối cột giữa, mục **Đặt lịch tiếp** → **Đặt lịch khám mới**
   (không nối chuỗi lượt cũ) hoặc **Tái khám** (nối tiếp lượt đang xem; nút xám nếu khách chưa có lượt nào).

### 1.3 Tìm lại khách đang chờ

- Trên cùng màn **Quản lý khách hàng** có 4 ô số: **Cần xử lý hôm nay** · **Quá SLA** ·
  **Chờ xác nhận** · **Đã hoàn thành**. Bấm một ô là lọc danh sách đúng bằng con số ấy;
  bấm **Bỏ lọc, xem tất cả khách hàng** để bỏ.
  - Khách "Gọi điện xác nhận" (chưa có lịch) và khách "Gọi xác nhận lịch" cùng nằm ở ô **Chờ xác nhận**.
    (Chỗ này là **ô số**, không phải tab riêng.)
- Ô **Tìm theo tên, số điện thoại, mã khách hàng**: gõ là lọc ngay, **Enter** = tìm liền.
- Thanh ngày: công tắc **Ngày hẹn** / **Ngày tạo hồ sơ** + ô lịch **Khoảng ngày tra cứu khách**
  (Hôm nay · Hôm qua · 7 ngày · Tuần trước · 30 ngày · Tất cả · tuỳ chọn). Khách chưa có lịch
  nên chọn **Ngày tạo hồ sơ** để tìm theo ngày nhập.

### 1.4 Ghi phản hồi của khách (kể cả sau khi dùng thuốc)

Chọn khách → khối **Phản hồi của khách** nằm trong khung làm việc của khách (dưới phần lịch sử các lần khám).

1. Bấm **+ Ghi phản hồi**.
2. Chọn loại: **Khiếu nại / claim** · **Góp ý** · **Khen**.
3. Ô **Khách nói gì?** gõ nội dung → **Ghi lại**.
4. Xử lý tiếp: **Bắt đầu xử lý** (→ trạng thái Đang xử lý) rồi **Đã xử lý…** → gõ
   **Đã xử lý thế nào?** → **Chốt đã xử lý**.
5. Gọi hỏi thăm không phải khiếu nại, chỉ cần để lại lời dặn cho ca sau: dùng
   **Ghi chú về khách** ở khung phải.

> (cần Tuyền xác nhận) Trên màn **không có mục tên "Phản hồi sau dùng thuốc"**. Phản hồi
> sau dùng thuốc hiện ghi chung ở **Phản hồi của khách** như trên. Nếu cần mục riêng, báo
> để làm thêm.

### 1.5 Việc "Gọi xác nhận lịch" cho lịch nhân viên đặt hộ

**[chờ bản mới]** Luật 15/10: **mọi** lịch còn hiệu lực, **trừ lịch khách đến thẳng
(kênh "Trực tiếp / WALK_IN")**, đều có việc **Gọi xác nhận lịch** nếu giờ khám nằm từ hôm nay
đến 7 ngày tới — kể cả lịch vừa đặt sát ngày. Hạn gọi = (ngày khám − 7 ngày), nhưng không sớm hơn ngày đặt.

Cách làm:

1. **Quản lý khách hàng** → ô **Chờ xác nhận** (hoặc tìm khách) → bấm khách.
2. Khung giữa, khối **Trước khám**, dòng **Xác nhận lịch trước 7 ngày**
   ("Gọi khách xác nhận lịch, xong bấm vòng tròn để ghi lại").
3. Gọi xong → bấm **vòng tròn** cuối dòng. Vòng tròn xanh có dấu ✓ = đã ghi, việc hết.
4. Khách không nghe máy / chưa gặp: bấm **Không gọi được** (bên dưới) — việc chuyển thành
   **Gọi lại — lần trước chưa gặp**. Khách hẹn gọi lại: bấm **Hẹn gọi lại**, chọn ngày giờ ở cột phải.
5. Ô **Ghi chú khi gọi — khách dặn dò gì** gõ trước khi bấm vòng tròn: ghi chú đi kèm đúng lần bấm đó.

> (cần Tuyền xác nhận) Hệ thống **chưa có cột "ai đặt"** (chưa có cổng khách tự đặt),
> nên "lịch nhân viên đặt hộ" hiện = mọi lịch khác kênh Trực tiếp.

### 1.6 Bấm nhầm — rút lại

Mọi thao tác ghi vào **sổ chăm sóc**, không xoá được nhưng **rút lại được**; dòng đã rút
vẫn nằm trong **Lịch sử thao tác** (gạch ngang, ghi "đã rút lại").

- **Vòng tròn đã xanh:** bấm **lại lần nữa** = **Hoàn tác** (rê chuột thấy gợi ý
  "Bấm lại để hoàn tác — dòng vẫn nằm trong sổ chăm sóc").
- **Khách chưa có lịch / lượt nào:** ở đầu khung giữa hiện dòng **Vừa ghi: …** kèm nút
  **↺ Rút lại thao tác này**. **[chờ bản mới]**
- **Thao tác gần nhất nằm ở lượt khác:** hiện dải vàng "Thao tác gần nhất nằm ở … — nút tròn
  bên dưới không rút được" kèm nút **↺ Rút lại thao tác này**.
- Rút lại xong, nhãn "Đã gọi xác nhận" mất, việc quay lại danh sách.

---

## 2. THU NGÂN áp giảm giá

Áp dụng ở **Thu tiền dịch vụ**, **Thu tiền thuốc** và **Bán lẻ** (khách chỉ mua thuốc) —
cùng một khối "Giảm giá".

### 2.1 Các bước

1. Thanh bên → **Thu tiền dịch vụ** (hoặc **Thu tiền thuốc**) → tab **Chờ thanh toán** →
   bấm khách trong danh sách → hoá đơn hiện bên phải.
2. Kiểm các dòng đã tick đúng (dịch vụ khách làm / thuốc khách lấy). **Giảm giá tính trên
   TỔNG hoá đơn, không giảm riêng từng dòng.**
3. Dưới danh sách, tick **Giảm giá / Miễn phí**. (Ô này chỉ hiện khi hoá đơn còn tiền
   và chưa thu.)
4. Chọn cách giảm:
   - **Giảm tiền (đ)** → ô **Số tiền giảm**; hoặc
   - **Giảm %** → ô **% giảm (0–100)**.
   Bên cạnh hiện số quy đổi (≈ % hoặc ≈ đ) để xem trước.
5. Gõ **Lý do giảm giá** (bắt buộc, tối đa 500 ký tự, ví dụ "khách quen", "người nhà bác sĩ").
6. Xem dòng tổng: "*tổng gốc − tiền giảm = số phải thu*". Giảm hết = hiện **Miễn phí**.
7. Chọn hình thức thu (tiền mặt / chuyển khoản / chia) như thường, rồi bấm **Tạo bill**
   (quầy dịch vụ, có phần chuyển khoản: **Tạo bill · chờ xác minh CK**). Giảm 100%: nút đổi thành **Ghi nhận miễn phí**
   (không cần chọn hình thức).

### 2.2 Luật hệ thống đang chạy

| Việc | Luật (đối chiếu code) |
|---|---|
| Ai giảm được | Ai **đứng được quầy thu** (có quyền **Thu tiền dịch vụ** / **Thu tiền thuốc**). Không có quyền riêng "giảm giá". |
| Cần duyệt không | **Không có bước duyệt**, không có ngưỡng % theo vai. (cần Tuyền xác nhận: có muốn đặt ngưỡng / người duyệt không.) |
| Lý do | **Bắt buộc**, chữ tự do. Thiếu lý do → nút thu khoá, báo đỏ "Phải ghi lý do giảm giá." |
| Mức tối đa | Không vượt phần **được phép giảm** của hoá đơn. **Liệu trình trả trước không giảm được**; vượt thì báo đỏ, nút thu khoá. % chỉ từ 0 đến 100. |
| Làm tròn | Tiền giảm làm tròn đến 1đ; nếu còn 0đ thì báo "nhập giá trị lớn hơn". |
| Khách đang ghi nợ | Vẫn giảm được như thường (thu nợ có thể giảm; miễn phí = giảm 100%). |
| Ai quyết số cuối | **Máy chủ tính lại** số tiền giảm và số phải thu; số trên màn chỉ để xem trước. |

### 2.3 Giảm giá hiện ở đâu sau khi thu

- **Phiếu thu in** (`Tổng trước giảm` + dòng **Giảm giá**).
- Tab **Đã thanh toán hôm nay** / **Lịch sử giao dịch** của quầy: sau số tiền có
  `[giảm X — lý do]`; giảm hết ghi "0đ (Miễn phí)".
- **Danh sách hoá đơn** → mở một phiếu: "Trước giảm: … · Giảm: …" từng dòng và
  "Giảm giá X (Y%)" ở đầu phiếu.
- **Báo cáo** → tab **Cuối ngày**: dòng **Giảm giá** trong tóm tắt tài chính
  (hiện "Chưa có dữ liệu" nếu máy chủ chưa tính được).

### 2.4 Giảm nhầm — làm lại

Hoá đơn **chưa bấm Tạo bill**: sửa thẳng ô giảm (hoặc bỏ tick **Giảm giá / Miễn phí**) rồi tạo bill.

Đã **Tạo bill** rồi mới thấy sai:

1. Vào tab **Đã thanh toán hôm nay** (hoặc **Lịch sử giao dịch**) → tìm khách → bấm
   **Hoàn tác lần thu**.
2. Hộp xác nhận hiện "Lượt về chưa thu — trả lại tiền cho khách nếu đã nhận" → gõ lý do
   (không bắt buộc) → **Hoàn tác**.
3. Khách quay về **Chờ thanh toán**, chưa thu → làm lại từ bước 3 mục 2.1 với mức giảm đúng.
   Nếu đã nhận tiền của khách, **trả lại tiền thật** cho khách.

Giới hạn:
- Nút **Hoàn tác lần thu** chỉ làm được **trong ngày**, ở đúng quầy (dịch vụ / thuốc), và chỉ
  khi người xem có lịch trực thu tiền. Màn **Lịch sử** của ngày cũ chỉ để xem.
- Phiếu **dịch vụ đã có khoản hoàn tiền** không hoàn tác được nữa — xử lý bằng **Hoàn tiền**.
- **Hoàn tác** = thu nhầm, trả lại như chưa thu. **Hoàn tiền** = khách đã trả đúng, giờ trả lại
  (phiếu thu vẫn đứng). Đừng nhầm hai nút.
