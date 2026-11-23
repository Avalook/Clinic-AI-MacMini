# Bật liên thông đơn thuốc quốc gia — phòng khám cần chuẩn bị gì

> Viết 24/11/2026. Phần mềm đã dựng sẵn và đang **TẮT**. Khi phòng khám có tài
> khoản liên thông thì chỉ cần điền biến môi trường rồi bật. Không phải viết thêm code.

## Trạng thái và hai lựa chọn mặc định (Tuyền chốt 24/11/2026)

**Chưa bật.** Quy trình đơn thuốc và tiền hiện do chủ phòng khám tính toán bên
ngoài hệ thống. Công tắc `DTQG_BAT` giữ **TẮT**. Phần mềm không đổi màn nào và
không đổi hành vi hiện tại chút nào.

Hai lựa chọn dưới đây được chọn để phản ánh đúng cách hệ thống đang chạy. Đây là
**mặc định, có thể đổi** khi chủ phòng khám chốt quy trình:

- **(a) "Đơn chốt"** là lúc lượt khám **đã đóng**, tức khách về hoặc về giữa chừng.
  Lựa chọn này khớp cách hệ thống đang chạy và không thêm bước nào cho nhân viên.
- **(b) Đơn đã gửi lên hệ thống quốc gia mà bị sửa** thì phần mềm tạo **đơn thay
  thế với mã mới**. Đơn cũ giữ nguyên, theo luật thiết kế "không sửa quá khứ" và
  QĐ 425 Điều 9. Chỉ tạo đơn thay thế khi phần nội dung đơn đổi (thuốc, chẩn đoán,
  bác sĩ, họ tên, ngày sinh).

## Vì sao phải làm

Các điều khoản dưới đây đã đối chiếu với văn bản gốc:

- **TT 26/2025/TT-BYT, Điều 13 khoản 3b.** Cơ sở không phải bệnh viện phải kê đơn
  điện tử **trước 01/01/2026**. Mốc này đã qua.
- **TT 26/2025/TT-BYT, Điều 12 khoản 6d.** Đơn phải được gửi lên Hệ thống đơn thuốc
  quốc gia ngay sau khi khám xong.
- **TT 26/2025/TT-BYT, Điều 12 khoản 6đ.** Đơn (hoặc mã đơn) phải được gửi cho người
  bệnh qua phương tiện điện tử. Phần này **chưa làm** (xem mục cuối).
- **TT 26/2025/TT-BYT, Điều 10.** Đơn điện tử phải được ký số.
- **Chuẩn kết nối: QĐ 808/QĐ-BYT ngày 01/04/2022**, bản gốc tại
  https://donthuocquocgia.vn/quyet-dinh-808.pdf. QĐ 425/QĐ-BYT năm 2025, Điều 9, vẫn
  dẫn chiếu QĐ 808. Đến 24/11/2026 chưa thấy văn bản đặc tả nào thay thế.

## Phần mềm làm gì khi bật

1. **Khi nào gửi.** Đơn được coi là đã chốt khi lượt khám **đóng**, tức là khách
   đã về hoặc về giữa chừng (`visit.closed_at`), và lượt có ít nhất một dòng thuốc
   do bác sĩ kê. Thuốc quầy bán thêm không tính.
2. **Cách gửi.** Mỗi phút, worker `su-kien` dò các lượt vừa đóng, ghi đơn vào hàng
   chờ (bảng `dtqg_gui`) rồi gửi đi. Quầy và bàn khám **không bao giờ phải chờ**
   hệ thống quốc gia.
3. **Bác sĩ đứng tên đơn** (và là người đăng nhập để gửi) lấy theo luật chung
   `bac_si_ky.py` (chốt 19/11): người bấm Hoàn tất nếu là bác sĩ → bác sĩ chính
   của lượt → bác sĩ của lịch hẹn. Người **nhập** dòng thuốc (TKYK, điều dưỡng
   nhập hộ) không bao giờ đứng tên. Vì vậy `DTQG_BAC_SI` phải có đủ các bác sĩ
   khám chính.
4. **Mã đơn.** Mỗi đơn có mã 14 ký tự theo TT 26 Phụ lục I: 5 ký tự mã cơ sở, 7 ký tự
   ngẫu nhiên, dấu gạch, rồi loại đơn. Ví dụ: `79abc` + `k3m9x2a` + `-c`.
5. **Khi đơn bị sửa sau lúc đã gửi** (sửa số, gỡ dòng, thêm số chứng chỉ hành nghề
   của bác sĩ…): đơn đã lên hệ thống quốc gia thì **không sửa hay huỷ được**. QĐ 808
   không có API sửa/huỷ, và QĐ 425 Điều 9 cấm. Phần mềm vì vậy gửi một **đơn thay
   thế với mã mới**. Đơn cũ vẫn nằm trên hệ thống.
   - Đơn thay thế chỉ sinh ra khi **phần đơn** đổi: thuốc, chẩn đoán, bác sĩ, họ tên,
     ngày sinh người bệnh. Lễ tân sửa SĐT, địa chỉ hay CCCD **sau khi đã gửi** thì
     không sinh đơn thay thế, để người bệnh không phải cầm hai mã cho cùng một đơn.
   - Đơn **chưa** gửi được thì khác: mọi thay đổi đều được tính, kể cả SĐT hay địa
     chỉ. Nhờ vậy một đơn đang dừng vì thiếu địa chỉ sẽ tự đi ngay khi lễ tân điền
     địa chỉ.
6. **Khi đơn đã gửi rồi bị gỡ hết thuốc:** phần mềm **không gửi được gì** và mở cảnh
   báo để người xử lý (báo người bệnh, xem trên web).
7. **Khi gửi lỗi:**
   - Lỗi mạng hoặc máy chủ: tự thử lại sau 1 phút, rồi 5 phút, 25 phút… tối đa
     `DTQG_SO_LAN_THU` lần (mặc định 6).
   - Hệ thống từ chối nội dung hoặc đơn thiếu dữ liệu: dừng ngay.
   - Cả hai trường hợp đều hiện ở `/ops`, tab "Lỗi & cảnh báo", qua các mã sau:
     - `DTQG_LOI`: có đơn không gửi được.
     - `DTQG_TON_DONG`: có đơn chờ quá 30 phút.
     - `DTQG_CAU_HINH_SAI`: đã bật nhưng điền sai cấu hình.
   - Nếu đã cấu hình kênh Telegram ops thì cảnh báo cũng gửi về đó. Tin chỉ có số đếm,
     không có tên khách.
   - `DTQG_LOI` chỉ đếm đơn trong **7 ngày** gần nhất. Không có màn "đã xử lý" nào,
     nên nếu không giới hạn thì cảnh báo sẽ mở mãi.
8. **Đơn đã ở `LOI` thì không tự gửi lại khi nội dung đơn không đổi.** Ví dụ: hệ
   thống quốc gia sập lâu làm cạn hết lượt thử, hoặc mật khẩu bác sĩ bị sai rồi được
   sửa trong `.env`. Muốn đơn đi lại thì đơn phải đổi; điền dữ liệu còn thiếu là
   đủ. Lệnh "gửi lại một đơn" (ghi bù một phiên bản mới, có lý do) là **việc mang
   sang**, chưa làm.
9. **Tắt công tắc khi đang có cảnh báo `DTQG_*` mở:** cảnh báo cũ không tự đóng, vì
   lúc tắt module không chạy một câu SQL nào. Đóng tay ở `/ops`, hoặc bật lại để
   vòng canh gác tự đóng.
10. **Staging không bao giờ gửi lên hệ thống thật.** Cấu hình
   `DTQG_NHA_CUNG_CAP=that` bị từ chối khi `APP_ENV` khác `production`, và vòng canh
   gác mở cảnh báo `DTQG_CAU_HINH_SAI`. Lý do: staging nạp lại bản sao prod mỗi đêm.
   Gói đơn trong `dtqg_gui` được che theo `scripts/staging-che-du-lieu.sql`.

## Phòng khám cần chuẩn bị (theo sách hướng dẫn trên donthuocquocgia.vn)

| # | Việc | Ai làm | Ra cái gì |
|---|---|---|---|
| 1 | Đăng ký cơ sở tại https://donthuocquocgia.vn/dang-ky-ma-lien-thong-co-so-kham-chua-benh. Cần: giấy phép hoạt động (PDF), mã cơ sở KCB 5 ký tự, người chịu trách nhiệm chuyên môn kèm CCHN, danh sách nhân sự, danh mục kỹ thuật | Quản lý | Hồ sơ tự chuyển về Sở Y tế |
| 2 | Sở Y tế duyệt (3–5 ngày) | Sở | **Mã liên thông cơ sở** và mật khẩu tài khoản cơ sở |
| 3 | Từng bác sĩ đăng ký tại https://donthuocquocgia.vn/dang-ky-ma-lien-thong-bac-si (CCHN, CCCD, ảnh, email). Cơ sở duyệt trên web, sau đó Sở nơi cấp CCHN duyệt | Từng bác sĩ | **Mã liên thông bác sĩ** và mật khẩu của bác sĩ |
| 4 | Thêm từng bác sĩ vào cơ sở (QĐ 808 mục IV), mỗi người một lần, bằng lệnh `them_bac_si` ở dưới | Tuyền | Bác sĩ đăng nhập được để gửi đơn |
| 5 | Điền số CCHN cho mọi bác sĩ trên màn nhân sự (`staff.license_number`) | Quản lý (việc dữ liệu) | Đơn không bị dừng vì "thiếu CCHN" |

Hỏi kỹ thuật: hotrokythuat@donthuocquocgia.vn, tổng đài 1900 8960 nhánh 4.

## Biến môi trường (`.env.prod` trên VPS)

| Biến | Bắt buộc | Nghĩa |
|---|---|---|
| `DTQG_BAT` | — | `1` để bật. Để trống hoặc `0` là **tắt**: không chạy câu SQL nào, không đổi gì |
| `DTQG_NHA_CUNG_CAP` | — | `gia_lap` (mặc định: không gọi mạng, dùng cho staging) hoặc `that` (chỉ nhận khi `APP_ENV=production`) |
| `DTQG_CLINIC_ID` | ✓ | uuid phòng khám |
| `DTQG_LOCATION_ID` | ✓ | uuid **cơ sở** (`clinic_location`) đã có mã. Lượt ở cơ sở khác không gửi |
| `DTQG_MA_CO_SO` | ✓ | Mã cơ sở KCB **đúng 5 ký tự**, dùng làm đầu mã đơn |
| `DTQG_GUI_TU` | ✓ | `yyyy-mm-dd`. Chỉ gửi đơn của lượt đóng **từ ngày này**. Có gửi bù đơn cũ hay không là việc phòng khám quyết; phần mềm không tự gửi bù |
| `DTQG_MA_LIEN_THONG_CO_SO` | ✓ khi `that` | Mã liên thông cơ sở (bước 2) |
| `DTQG_BAC_SI` | ✓ khi `that` | JSON `{"<staff_id>": {"ma_lien_thong": "…", "mat_khau": "…"}}`, mỗi bác sĩ một mục |
| `DTQG_MAT_KHAU_CO_SO` | chỉ cho bước 4 | Mật khẩu tài khoản cơ sở. Worker không dùng biến này |
| `DTQG_URL` | — | Mặc định `https://api.donthuocquocgia.vn` |
| `DTQG_KY_SO` | — | Mặc định `khong`. Hiện chưa có bộ ký số nào được cài (xem mục Ký số) |
| `DTQG_SO_LAN_THU` / `DTQG_SOAT_NGAY` | — | Mặc định 6 lần / 3 ngày. "Soát 3 ngày" nghĩa là đơn bị sửa trong vòng 3 ngày sau khi khách về sẽ thành đơn thay thế |

Bác sĩ nào chưa có trong `DTQG_BAC_SI` thì đơn của bác sĩ đó dừng ở "thiếu mã liên
thông". Thêm bác sĩ vào biến rồi khởi động lại `su-kien`, đơn sẽ tự đi.

## Thử: không có môi trường thử công khai

Đã tra QĐ 808, sách hướng dẫn 101 trang và trang chủ ngày 24/11/2026: **không thấy
sandbox**. Vì vậy:

1. **Staging:** đặt `DTQG_BAT=1` và `DTQG_NHA_CUNG_CAP=gia_lap`. Bấm thử một lượt có
   kê đơn rồi cho khách về. Trong khoảng 1 phút, `dtqg_gui` có một dòng trạng thái
   `DA_GUI` với `nha_cung_cap = GIA_LAP`. Câu kiểm tra (chỉ đọc):
   `SELECT ma_don, public.dtqg_trang_thai(g), loi_cuoi FROM dtqg_gui g ORDER BY tao_luc DESC LIMIT 20;`
2. **Lần đầu dùng hệ thống thật:** trước hết hỏi bộ phận hỗ trợ sáu câu ở cuối tài
   liệu. Sau đó bật `that` với **một bác sĩ** trong `DTQG_BAC_SI` và `DTQG_GUI_TU` là
   ngày hôm nay. Xem đơn đầu tiên trên web bằng tài khoản cơ sở, rồi mới thêm các bác
   sĩ còn lại.

Lệnh bước 4 chạy trên VPS, trong container `su-kien` của prod (project compose
`clinicai_prod`, đặt ở `scripts/deploy-backend.sh`), sau khi đã điền biến và deploy.
Đặt staff_id của bác sĩ vào biến `BS` ở dòng đầu, đúng khoá đã ghi trong
`DTQG_BAC_SI`:

```bash
BS=00000000-0000-0000-0000-000000000000; docker exec "$(docker ps -q --filter label=com.docker.compose.project=clinicai_prod --filter label=com.docker.compose.service=su-kien)" python -m clinicai.services.don_thuoc_quoc_gia.them_bac_si "$BS"
```

Lệnh này gửi dữ liệu ra hệ thống ngoài, nên Tuyền chạy tay. AI chỉ soạn lệnh.

## Trường còn thiếu trong dữ liệu ClinicAI

| Trường QĐ 808 | Hiện có | Khi thiếu thì | Đề xuất |
|---|---|---|---|
| Mã liên thông + mật khẩu bác sĩ | — | đơn dừng | Tạm để ở biến `DTQG_BAC_SI`. Về lâu dài thêm cột `staff.ma_lien_thong_dtqg` (mật khẩu vẫn để ở `.env`). Việc này cần sửa màn nhân sự, phải hỏi trước |
| Số CCHN bác sĩ | `staff.license_number` (đã có cột) | đơn dừng | Việc dữ liệu: điền trên màn |
| Ngày sinh **đầy đủ** | `patient.date_of_birth`. Nhiều khách chỉ có năm sinh | dừng (API bắt buộc d/m/Y) | Lễ tân hỏi đủ ngày sinh. Không tự điền 01/01 vì sẽ thành dữ liệu sai trên hệ thống quốc gia |
| Địa chỉ | `patient.address` | dừng | Việc dữ liệu |
| Chẩn đoán **mã ICD-10** | chỉ có chữ tự do (`pk_dx`…) | gửi mã rỗng, kèm tên chẩn đoán. **Có thể bị từ chối (422)** | Thêm ô chọn ICD-10 trên phiếu khám. Việc này đổi màn bác sĩ, phải hỏi trước |
| Mã thuốc | `drug_catalog.ma_hang` (mã nội bộ, các phần mềm khác cũng gửi kiểu này) | dừng nếu thuốc gõ tay ngoài danh mục | Kê thuốc từ danh mục |
| Hoạt chất (`biet_duoc`) | `drug_catalog.biet_duoc` (lẫn tên thương mại) | gửi tên thuốc thay | Thêm cột hoạt chất vào danh mục |
| Số lượng **dạng số** | `prescription.quantity_num` | dừng nếu dòng chỉ ghi chữ | Không cần làm gì thêm. Quầy đã điền số khi bác sĩ bỏ trống (C14) |
| Loại đơn (thường / gây nghiện / hướng thần / cổ truyền) | danh mục chưa phân loại | mọi đơn gửi loại `c` (thường) | Gắn cờ trên danh mục **nếu** phòng khám có kê thuốc gây nghiện hoặc hướng thần |
| Ngày tái khám (tính bằng **số ngày**) | có `pk_follow_date` trên phiếu | gửi rỗng | Nối sau |
| Cân nặng, lời dặn, BHYT | chưa gửi | — | Không bắt buộc (cân nặng chỉ bắt buộc với trẻ dưới 72 tháng) |

## Ký số: điểm cắm đã có, chưa chọn nhà cung cấp

- **Trong gói API**, trường `signature` để rỗng. Sách hướng dẫn (FAQ 1.6, 1.22) ghi
  rằng Bộ Y tế "chưa có kế hoạch triển khai chữ ký số" ở trường này. Các phần mềm
  đang chạy (mã nguồn công khai) cũng gửi rỗng.
- **Nghĩa vụ ký số theo TT 26 Điều 10** áp lên **bản đơn**, tức file PDF/XML lưu tại
  phòng khám và gửi cho người bệnh. QĐ 425 Điều 11 cho hai cách ký:
  - người chịu trách nhiệm chuyên môn ký số, kèm chữ ký điện tử của người kê;
  - hoặc từng bác sĩ tự ký số.
- **Điểm cắm trong code:** `KySoDonThuoc` ở `src/clinicai/ports/don_thuoc_quoc_gia.py`.
  Thêm một nhà cung cấp gồm hai việc: viết một adapter, rồi thêm tên vào
  `KY_SO_DA_CAI`.
- **Các lựa chọn ký từ xa ở VN** (danh sách có giấy phép trên neac.gov.vn):
  - Viettel MySign: có API ký hash công khai theo chuẩn CSC.
  - VNPT SmartCA: tài liệu chỉ cấp cho đối tác.
  - MISA eSign, FPT.eSign, Bkav, EasyCA: chưa thấy tài liệu API công khai.
  - Đây là quyết định mua dịch vụ, phòng khám chọn.

## Chưa làm, và vì sao

- **Gửi mã đơn cho người bệnh (khoản 6đ):** in mã đơn kèm QR trên đơn in, và/hoặc
  nhắn qua Zalo. Việc này đổi bản in mà nhân viên đang dùng và gửi tin ra ngoài, nên
  phải hỏi trước.
- **Màn xem hàng chờ:** hiện xem được ở `/ops` (cảnh báo) và bằng câu SQL ở trên.

## Sáu câu cần hỏi hotrokythuat@donthuocquocgia.vn trước khi bật thật

1. Có môi trường thử (sandbox) không?
2. Trường `signature` dùng định dạng gì?
3. Mã đơn viết hoa hay viết thường?
4. `ma_thuoc` dùng bộ mã nào?
5. `danh_sach_cac_loi` có hình dạng JSON ra sao, và khi trùng mã đơn thì câu trả lời ghi gì?
6. Các khoá con của `dot_dung_thuoc` tên là gì?

Mã nguồn: `src/clinicai/services/don_thuoc_quoc_gia/` (cấu hình, ánh xạ, hàng chờ,
gửi, vòng, lệnh thêm bác sĩ) · `src/clinicai/adapters/don_thuoc_quoc_gia/` (giả lập,
bản thật theo QĐ 808) · migration `20261124020000_don_thuoc_quoc_gia.sql` · test
`src/tests/unit/test_don_thuoc_quoc_gia.py`, `src/tests/services/test_don_thuoc_quoc_gia_db.py`.
