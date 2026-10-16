# Hướng dẫn bấm thử các việc Notion — staging, 16/10/2026

Dành cho Tuyền (và người test). Mỗi mục có: **trang nào · trang có gì · cần theo dõi gì ·
bấm vào đâu · bấm xong đi đâu · tốc độ đo được · lỗi đã thấy**. Mọi thứ dưới đây là chuyện
đã BẤM THẬT trên https://staging.dr4women.io.vn (bản `gop-staging-1410m`), trừ chỗ ghi
**CHƯA BẤM**.

> Staging nạp lại từ prod mỗi đêm 03:31 (dữ liệu khách đã che) — mọi thứ test (khách thử,
> công tắc, tài khoản "Thử") sẽ mất. Đừng bấm ghi gì trên **prod** để thử.

## 0. Chuẩn bị

| Việc | Cách |
|---|---|
| Tài khoản quản lý để xem mọi màn | "Quản lý hệ thống" (HT). Tài khoản "Thử" = Lễ tân: chỉ vào màn được cấp quyền |
| Đổi tài khoản | Avatar góc phải → **Thoát** → đăng nhập lại |
| Đổi mật khẩu của mình | Avatar → **Đổi mật khẩu** → 3 ô (hiện tại · mới ≥ 8 ký tự · nhập lại) → **Lưu thay đổi** |
| Công tắc "Nhận khách tại phòng" | `/settings/day-noi` → dòng "Nhận khách tại phòng…" → nút Đang tắt/Đang bật (staging tự tắt lại sau mỗi lần nạp) |
| Khách thử | Dùng khách mã `BN-2026-…` do chính bạn tạo; đừng bấm ghi lên khách `KHACH-…` (bản sao khách thật đã che) trừ khi cần |

### Tốc độ trang đo được (HT, cache tắt, máy chủ trả trang)

| Trang | Lần đầu | Lần sau | Nhận xét |
|---|---|---|---|
| `/home` Trang chủ | 2,5 s | 1,3 s | **Chậm nhất** — gọi `home/bang-dieu-khien` (tới 2,3 s) |
| `/customers` Quản lý khách hàng | 4,6 s | 1,0 s | **Chậm** — gọi `cskh/man-khach-hang` (tới 4,2 s); chuyển trang RSC 2,7 s |
| `/reception/queue` Tiếp đón | 1,0 s | 1,0 s | Chậm vừa |
| `/nhac-tai-kham` | 0,8 s | 0,5 s | Hơi chậm |
| `/patient-list`, `/schedule`, `/pharmacy`, `/cashier/dich-vu`, `/reports` | 0,25–0,45 s | 0,13–0,4 s | Ổn |
| Còn lại (Phòng, Bàn khám, Thu ngân, Kho vật tư, Hoá đơn, Cài đặt…) | 60–200 ms | 60–200 ms | Nhanh |
| Lưu khách mới → hiện hồ sơ ở Quản lý khách | 3,2 s | — | Tạo + nạp lại trang `/customers` |

Đã giao agent giảm chậm 3 điểm đầu (nhánh `claude/giam-cham-trang-chu-quan-ly-khach`).

## 1. Tạo khách mới — Lễ tân / CSKH
**Trang:** `/patients/new` (menu "Thêm khách hàng") — cùng form ở tab **Thêm** của `/appointments`.
**Có gì:** Họ tên · Ngày sinh / Chỉ biết năm · SĐT chính · SĐT người nhà · **CCCD** · **Email (nếu có)** ·
Cơ sở đăng ký khám · Giới tính · Dân tộc · Quốc tịch · Nghề nghiệp · Đối tượng · Tỉnh/Phường/Địa chỉ ·
Vấn đề đi khám · ô tick **"Chỉ lưu hồ sơ — chưa đặt lịch"** · Dịch vụ khám · Kênh đặt · Chọn giờ khám.
**Chỉ bắt buộc Họ tên.** Email/CCCD điền thì được kiểm định dạng.

| Bấm | Kết quả |
|---|---|
| Gõ email sai (vd `sai-email`) | Chữ đỏ "Email không đúng định dạng" cạnh ô, nút Lưu không đi |
| Điền tên + (email đúng) → tick "Chỉ lưu hồ sơ" → **Tạo bệnh nhân** | Sang **`/customers?selected=<mã khách>`** (Quản lý khách hàng, đúng khách vừa tạo). Email lưu chữ thường |
| Điền tên, **không** tick gì, khối lịch để trống | Cũng sang `/customers?selected=…` (khối lịch trống = chỉ lưu hồ sơ) |
| Điền SĐT đã có người dùng | Hộp "Đã có bệnh nhân dùng SĐT này…" → **Dùng bệnh nhân này** → sang `/reception/queue` (Tiếp đón); hoặc "vẫn tạo mới" |
| Có chọn dịch vụ + ngày + giờ | Tạo khách + đặt lịch, rồi về Tiếp đón (hoặc hồ sơ theo vai) |

**Theo dõi:** khách mới "chỉ lưu hồ sơ" tự có việc **"Gọi điện xác nhận"** ở Quản lý khách hàng.
**Lỗi/lưu ý:** nếu sau khi lưu bị đưa về trang chủ → tài khoản đó chưa được cấp quyền **Quản lý khách
hàng** (xem `/phan-quyen`); báo mình tên tài khoản. Nhãn avatar ghi "bấm để thoát" nhưng thực ra mở menu.

## 2. Quản lý khách hàng — CSKH
**Trang:** `/customers`. **Thanh lọc:** Cần xử lý hôm nay · Quá SLA · **Chờ xác nhận** · Đã hoàn thành ·
Ngày hẹn / Ngày tạo hồ sơ · nút **Thêm khách hàng mới**. Bảng: Khách hàng · Trạng thái · Mới/Cũ ·
Tương tác gần nhất · Bước tiếp theo · Hạn xử lý · Người xử lý gần nhất. Bấm một dòng → khung phải.

**Khung phải (theo thứ tự trên xuống):**
1. **Trạng thái khách hàng** — chip "Gọi điện xác nhận" (khách chưa có lịch) hoặc "Gọi xác nhận lịch" (có lịch do nhân viên đặt hộ).
2. **TRƯỚC KHÁM:** *Xác nhận lịch trước 7 ngày* (vòng tròn — bấm để ghi "đã gọi xác nhận", bấm lại để **Hoàn tác**) ·
   *Đã gọi nhắc hẹn* · Ghi chú khi gọi · Hẹn gọi lại · Không gọi được · Huỷ lịch (từ nút huỷ lịch).
3. **Bộ nút gọi:** Đã liên hệ được · Không nghe máy · Không liên lạc được · Hẹn gọi lại sau · Hẹn ngày tái khám… ·
   Hẹn gọi lại ngày… · Đổi / huỷ lịch hẹn (ghi lý do). Khách chưa có SĐT → báo "Khách chưa có số điện thoại".
4. **Phản hồi của khách** → **+ Ghi phản hồi** (Khiếu nại/claim · Góp ý · Khen) → **Ghi lại**.
5. **PHẢN HỒI SAU DÙNG THUỐC:** chọn đơn thuốc (ngày · bác sĩ · thuốc) · kênh **Gọi điện / Zalo / Trực tiếp** ·
   ô "Khách dùng thuốc thấy thế nào (bắt buộc)" · **Đặt lịch khám** (nếu cần tư vấn thêm) · **Lưu phản hồi** ·
   mỗi phản hồi có người ghi + giờ + nút **Gỡ**.
6. GHI CHÚ VỀ KHÁCH (**Lưu ghi chú**) · TỰ NHẮC TÔI (**Nhắc tôi**) · LIỆU TRÌNH.
7. **Công ty xuất hoá đơn** → **Thêm công ty**: Tên công ty · Mã số thuế (10 số, hoặc 10 số-001) · Địa chỉ công ty ·
   Email nhận hoá đơn · Người mua (không bắt buộc) → **Lưu công ty** → hiện dòng công ty + **Sửa / Gỡ**.
   (Thu ngân và Lễ tân cũng ghi được từ màn thu tiền.)
8. **Sửa thông tin:** Họ tên · Ngày sinh · Giới tính · **Số CCCD (sửa được, kể cả khách chuyển từ Notion)** · **Email** ·
   SĐT chính · SĐT người nhà · Dân tộc · Quốc tịch · Nghề nghiệp · Đối tượng · Người giám hộ · Địa chỉ → **Lưu thông tin / Huỷ**.

**Đã bấm thật:** ghi phản hồi (khách `BN-…750070`) → hiện ở hồ sơ, và bác sĩ thấy ở **Bàn khám** (khung "Lượt khám trước"
→ "Phản hồi sau dùng thuốc (CSKH ghi)"). Bấm vòng tròn *Xác nhận lịch* → việc `CHO_XAC_NHAN` biến mất (thay bằng
"Nhắc hẹn ngày mai"), sổ ghi `DA_LIEN_HE`; bấm lại → sổ đánh dấu huỷ, việc quay lại.
**Lỗi:** sau Hoàn tác, giao diện hiện trạng thái cũ vài giây (tải lại là đúng).

## 3. Tiếp đón → Đo sinh hiệu → Bàn tư vấn → Bàn khám
| Trang | Có gì / bấm | Đi đâu |
|---|---|---|
| `/reception/queue` Tiếp đón khách | Tất cả / Chưa check-in / Đã check-in · lịch hẹn cả tuần · mỗi dòng **Check-in** / **Không đến** · **+ Thêm khách hàng** | Check-in xong dòng hiện "Đang chờ: Bàn tư vấn" + nút **Hoàn tác** |
| `/do-sinh-hieu` Đo sinh hiệu | điều dưỡng nhập mạch, nhiệt, huyết áp… | khách sang Bàn tư vấn (chưa đo vẫn nhận được) |
| `/tu-van` Bàn khám tư vấn | Chờ tư vấn · Chưa đo sinh hiệu · Đang tư vấn · Đã chuyển bác sĩ chính → **Bắt đầu tư vấn** → **Xong tư vấn — chuyển bác sĩ chính** | khách sang `/ban-kham` |
| `/ban-kham` Bàn khám | Chờ khám · Kết quả cần đọc · Đang khám · Đã khám xong → **Bắt đầu khám**; 4 khối: 1 Thông tin cơ bản · **2 Chỉ định cận lâm sàng** · 3 Chỉ định điều trị · 4 Đơn thuốc; ô **Làm trước – thu sau**; **Hoàn tất** | Hoàn tất → khách đi các phòng đã chỉ định |

**Chỉ định cận lâm sàng:** tick dịch vụ ("tick là thêm") → nút **Chỉ định N mục · lần 1 · giá** → dòng "Đã chỉ định & kết quả"
(có **Hoàn tác chỉ định**, **Mở phiếu kết quả**, **+ Chỉ định thêm (lần 2)**). Dịch vụ "Thu hộ đối tác" ghi rõ "trả đối tác".
**Đầu dò Bio** nay chọn ngay ở bước chỉ định (xem khối 2). **Lưu ý:** nếu còn tick chưa gửi mà bấm **Hoàn tất** hoặc đổi
khách/phòng/ngày → hiện dải "Còn N mục đã chọn chưa gửi chỉ định…" với **[Chỉ định ngay rồi hoàn tất] / [Bỏ chọn]** (không mất tick im lặng).

## 4. Phòng dịch vụ & nhận khách tại phòng
**Trang:** `/phong` (danh sách phòng, mỗi phòng 3 số **sắp đến · đang chờ · đang làm**) → `/phong/<phòng>`.
**Cần bật** công tắc "Nhận khách tại phòng" (`/settings/day-noi`). Khi bật: hệ thống không tự xếp phòng; chọn phòng ở quầy thu/bàn khám chỉ là **hướng dẫn**.
**Luồng:** Sắp đến → **Nhận** → Đang chờ → **Bắt đầu** → Đang làm → **Xong**; mỗi nút có **Hoàn tác**; phòng khác vẫn nhận chéo được
(phòng cũ nhận chuông "khách đã sang phòng khác" nếu đang làm dở).
**Đã bấm thật** (khách xét nghiệm máu): bác sĩ chỉ định → cả 6 phòng thường hiện "1 sắp đến"; sau khi bác sĩ **Hoàn tất**, phòng "Bàn xét nghiệm máu"
có nút **Nhận** → Đang chờ → Bắt đầu → Xong ("Đã xong Xét nghiệm máu").
**Lưu ý:** nút **Nhận** chỉ hiện SAU khi bác sĩ bấm Hoàn tất (khi khách còn "đang khám ở bàn khám" chỉ thấy tên). **★ phòng chuyên** chỉ là nhãn + thứ tự,
không bắt buộc. **Phòng đối tác không có nút Nhận** — việc đối tác đi theo `/doi-tac`.
**Khi khách đang ở bước/phòng khác:** dòng vẫn có nút **Bắt đầu** (nhận chéo, hệ thống ghi giờ + người bấm).

### Việc của đối tác — `/doi-tac` (HOÃN, chỉ ghi lại)
Thanh: chờ lấy mẫu · chờ nhận mẫu · đã nhận mẫu · có kết quả. Chọn khách → **Nhận mẫu** (báo "Đã nhận mẫu — việc đối tác XONG") →
**Tải kết quả lên** (lúc nào cũng được). Có ô "Thu hộ đối tác" (đã thu hộ / chưa). Prod đang có ~34 mẫu chờ nhận 3–5 ngày: nhắc phòng khám.

## 5. Thu ngân dịch vụ — `/thu-ngan/dich-vu`
**Có gì:** tab Chờ thanh toán · Đã thanh toán hôm nay · Lịch sử giao dịch; chọn khách → khung phải:
Dịch vụ khám (chọn loại khám) · **Mua thêm vật tư** (có ô **Nguyên nhân bán thêm** 5–500 ký tự, tìm vật tư; chỉ vật tư "được kinh doanh") ·
PHÒNG KHÁM THU (tiền khám) · **THU HỘ ĐỐI TÁC — KHÔNG CỘNG** (xét nghiệm đối tác hiện riêng, không cộng vào tiền phòng khám) ·
**Làm trước – thu sau** · **Giảm giá / Miễn phí** · **Tiền mặt / Chuyển khoản** (tách được TM + CK; "Khách đưa" tính tiền thừa) ·
**Tạo bill** · HƯỚNG DẪN PHÒNG (không bắt buộc) + In phiếu hướng dẫn phòng.
**Theo dõi:** tiền khách đưa vs phải thu; "Có dịch vụ chưa có giá — chưa thu được" (phải gắn giá ở Bảng giá).
**Sau khi thu:** khách vào "Đã thu — chờ vào phòng"; mọi thao tác (giảm giá, đổi hình thức, hoàn) hoàn tác được và hiện ở báo cáo.
**Lưu ý:** "Đầu dò Bio 1 lần / nhiều lần" **vẫn còn** ở mục Mua thêm vật tư của thu ngân (ngoài việc đã có ở bước chỉ định) — cần Tuyền chốt giữ hay bỏ.

## 6. Nhà thuốc
### 6.1 Cấp thuốc — `/pharmacy`
Tab **Đơn thuốc** (Đang xử lý / Xong hôm nay; Chờ thu tiền · Đã thu — giao thuốc · Chờ xác minh chuyển khoản) và nút **Khách mua thuốc**:
tìm khách (SĐT/mã/tên) hoặc nhập **khách mới** (Họ tên · SĐT · Năm sinh → **Tạo khách & mở lượt mua thuốc**) → lượt **Bán lẻ**.
**Bán theo đơn:** chọn khách cũ → **Lịch sử đơn thuốc** (mới → cũ: ngày khám · bác sĩ · hẹn tái khám · từng thuốc *Kê / Đã mua / Còn*) →
**Bán theo đơn này** → lượt Bán lẻ nối đơn gốc ("Đang bán theo đơn", nút **Gỡ nối đơn**); thuốc còn lại tự thêm dòng; đơn đã mua đủ thì không thêm,
bác sĩ chưa ghi số thì báo "thêm tay". **Chỉ nhắc, không chặn:** quá 2 tháng chưa tái khám hoặc mua quá số kê (mới có test, chưa gặp khách đủ điều kiện để bấm).
### 6.2 Kho thuốc — `/pharmacy/inventory`
Tab: Danh mục thuốc · **Tồn theo lô** · Chờ gán lô · **Phiếu nhập** · **Chuyển kho** · **Kiểm kê ca** · Kiểm kho · Thẻ kho · Xuất nhập tồn.
- **Tồn theo lô:** ô **Cảnh báo trước hạn (số ngày)** + **Lưu cảnh báo**; chip *Lô thuốc · Tổng tồn · Lô sắp hết hạn · Lô hết hạn còn trên kệ*;
  lọc Tất cả / Còn hạn / Sắp hết hạn / Hết hạn / Chưa có hạn; mỗi lô: **In tem · Sửa lô · Điều chỉnh · Huỷ · Huỷ lô hết hạn**; **+ Nhập lô**.
  Có quét mã vạch (camera iPhone đọc QR được); lô gắn mã + hạn dùng.
- **Kiểm kê ca:** chọn Ngày · Ca (sáng/chiều/tối) · Loại (Đầu ca / Cuối ca / Đột xuất) → **Mở / tiếp tục phiếu** → bảng thuốc có ô **Đếm** →
  **Lưu nháp** → **Chốt kiểm kê**. Nhắc (không chặn bán): "Ca sáng hôm nay chưa kiểm đầu ca. Ca trước chưa kiểm cuối ca."
  Chốt chỉ ghi chênh lệch, **không tự sửa tồn**; có lệch → chuông báo rà soát (mỗi người nhận 1 chuông).
- **Hai nơi lưu trữ:** Kho (nhập về) và Quầy (bán/xuất) — chuyển bằng tab **Chuyển kho** (có hoàn tác).

## 7. Kho vật tư — `/kho-vat-tu`
Tab: **Tồn theo nơi chứa** · **Phiếu** · **Chờ duyệt** · **Tiêu hao** · **Danh mục (84)**.
- **Phiếu:** Loại phiếu (Nhập kho · Xuất kho → phòng · Phòng trả kho · Chuyển phòng → phòng · Kiểm đếm chỉnh tồn · Kiểm đếm chỉ ghi số đếm · Huỷ hỏng) → chọn vật tư, phòng nhận, số lượng, giá nhập, lý do → **Lưu phiếu**; "Phiếu đã lập" có **Xem dòng / Hoàn tác**.
- **Danh mục:** mỗi vật tư có Loại (văn phòng phẩm / vật tư y tế) · Giá · Giá nhập · Mã vạch · **Được kinh doanh** (hiện ở Thu ngân) ·
  **Cần QL duyệt bán** · **Cần duyệt nhập**.
- **Chờ duyệt:** phiếu nhập có mặt hàng "cần duyệt nhập" chưa vào kho tới khi người có quyền **Duyệt vật tư** (Trưởng ca/Quản lý) bấm **Duyệt** /
  **Từ chối** (lý do ≥ 5 ký tự) hoặc người lập **Rút lại**; chip số trên tab chỉ hiện khi có yêu cầu.
- **Tiêu hao:** vật tư không kinh doanh dùng theo phòng.
**CHƯA BẤM:** Duyệt / Từ chối (tài khoản HT có sẵn quyền tự duyệt nên phiếu tự vào kho). Để thử cần 2 tài khoản: A không có quyền "Duyệt vật tư", B có;
bật "Cần duyệt nhập" cho 1 mặt hàng; A lập phiếu nhập → tab Chờ duyệt → B duyệt.

## 8. Báo cáo, hoá đơn
### 8.1 `/reports` — 3 tab: Vận hành · **Cuối ngày** · **Hàng hoá**
**Cuối ngày:** lọc Cơ sở · Hôm nay/Hôm qua/7 ngày/30 ngày/khoảng ngày · Tất cả/Dịch vụ/Thuốc · **Cả ngày / Ca sáng / Ca chiều / Ca tối** · **In · Xuất Excel**.
Khối **Dòng tiền:** **Dòng tiền vào** (TM / CK) · **Trả lại tiền khách hàng** (TM / CK) · **Nợ** · **Giảm giá** · **Nợ thu được** ·
**Thực thu** (TM / CK) · **Doanh thu thuần**; mỗi khối có link **Xem hoá đơn**; cuối: **Xem hoá đơn không đúng**.
*Ví dụ 14/10:* vào 2.295.000 − trả lại 160.000 − nợ 400.000 − giảm 500.000 + nợ thu được 400.000 = **thực thu 1.635.000** ✓.
**Hàng hoá (thuốc):** cột Tồn đầu · Nhập trong ca · SL bán · SL trả · Tồn cuối ca · Kiểm kê · Lệch · Đã thu chưa giao · Doanh thu · GT trả · Doanh thu thuần.
**Còn thiếu:** link tới bảng Kiểm kê đầu–cuối ca (agent đang làm, PR `claude/bao-cao-hang-hoa-link-kiem-ke`).
**Phân quyền theo ca:** tài khoản Lễ tân "Thử" (chưa có ca trực) mở báo cáo chỉ thấy "Ngày trực: Chưa có ngày trực được duyệt. Bạn chỉ được xem báo cáo ngày và ca đã được phân công". Trưởng ca/Quản lý xem cả ngày. Cấu hình ở `/settings` → "Thiết lập báo cáo".
### 8.2 `/hoa-don` Danh sách hoá đơn
Lọc Ngày · Ca · Cơ sở · Loại · **Nhóm hoá đơn** (Mọi hoá đơn / **Hoá đơn đúng** / **Hoá đơn không đúng** / Có trả lại tiền·huỷ / Có giảm giá / Đổi hình thức thu / Khách còn nợ / Phòng khám còn nợ khách / Huỷ lần chờ chuyển khoản) · Hình thức · Trạng thái · **Xuất Excel (.xlsx)**.
Số **Đúng N · Không đúng M** + tổng (Tổng tiền hàng · Giảm giá · Tiền đã thu · Phiếu huỷ · Đã trả lại · Thực thu · Chưa trả lại · Việc còn tồn). Tab "Theo khách" / "Việc còn tồn". *Ví dụ 14/10:* đúng 4, không đúng 3 (trả lại 2 · cần đối soát 1 · huỷ chờ CK 1).
### 8.3 `/xuat-hoa-don` Xuất hoá đơn cho kế toán
"Theo từng hoá đơn" | **Theo hàng hoá →**; lọc Ngày thu · Loại · Cơ sở; chọn cách xử lý phiếu nhiều thuế suất (tách / giữ một) và **Ghi giảm giá trên hoá đơn**; **Tải file Excel** (đúng mẫu nhập hoá đơn GTGT của kế toán; ô chưa có dữ liệu để trống; khách lấy theo công ty chỉ xuất địa chỉ công ty).
"Các lần đã xuất sang MISA" có **Xem thay đổi / Khôi phục** (đánh dấu và bỏ đánh dấu). **CHƯA đối chiếu** file Excel với file mẫu chính thức của kế toán (chưa nhận mẫu).

## 9. Cài đặt & quản lý
| Trang | Làm gì |
|---|---|
| `/settings` | **Thiết lập báo cáo** (quyền xem theo ca) · **Chế độ phòng khám** (Chỉ CSKH & Đặt lịch / đầy đủ) |
| `/nhan-su` Quản lý nhân sự | tạo / sửa nhân sự |
| `/settings/tai-khoan` | **+ Thêm tài khoản** · mỗi dòng: **Đổi tên đăng nhập · Đặt lại mật khẩu · Gỡ tài khoản · Khoá & nghỉ việc · Mở lại** — gỡ tài khoản không mất lịch sử hoạt động |
| `/settings/clinic-config` Cấu trúc phòng khám | **+ Thêm cơ sở · + Thêm phòng · Sửa**; việc của từng phòng; **phòng chuyên ★**; cơ sở mặc định khi đăng nhập |
| `/cashier/dich-vu` Bảng giá dịch vụ & phòng | sửa giá dịch vụ |
| `/phan-quyen` | cấp lego theo tài khoản (Quản lý khách hàng, Duyệt vật tư, Kế toán…) |
| `/settings/day-noi` | công tắc nghiệp vụ (Nhận khách tại phòng, Thu trước khi làm…) |
| Avatar → Đổi mật khẩu | nhân sự tự đổi mật khẩu của mình (đã sửa lỗi hộp bị cắt, 16/10) |
**Tôi KHÔNG tự bấm** đổi mật khẩu / tạo / gỡ tài khoản trên staging (bạn tự bấm).

## 10. Danh sách lỗi và việc còn lại
| # | Điều | Mức | Tình trạng |
|---|---|---|---|
| 1 | Staging: DB giới hạn 384 MiB, Postgres bị OOM-kill (07:36) → API đứt kết nối → "Máy chủ đang bận" cho tới khi hồi phục | Hạ tầng staging | Cần tăng `STG_DB_MEMORY_LIMIT` (lệnh VPS do Tuyền chạy) |
| 2 | Nạp lại staging hỏng 15/10, 16/10 (thiếu cột `patient.email` ở bản sao prod) | Hạ tầng | **Đã sửa** (commit `3ae39074`), chờ đêm nay 03:31 |
| 3 | Cơ sở thử **Trung Kính** còn trên staging (tạo 15/10 12:17, 0 lượt khám) | Dữ liệu thử | Chờ Tuyền chạy lệnh tắt, hoặc nạp lại xoá |
| 4 | `/home`, `/customers`, `/reception/queue` chậm (xem mục 0) | Hiệu năng | Đang giao agent |
| 5 | Thiếu link sang bảng Kiểm kê ở báo cáo Hàng hoá | Thiếu tính năng | Đang giao agent |
| 6 | "Đầu dò Bio" còn ở Mua thêm vật tư của Thu ngân | Chốt nghiệp vụ | Chờ Tuyền |
| 7 | Nút **Nhận** ở phòng chỉ hiện sau khi bác sĩ Hoàn tất | Chốt nghiệp vụ | Chờ Tuyền (muốn nhận ngay khi vừa chỉ định?) |
| 8 | Kim Ngưu / Trung Kính còn trong ô chọn cơ sở ở nhiều báo cáo; **Kim Ngưu vẫn bật trên prod** | Dữ liệu | Tắt Kim Ngưu trên prod khi lên |
| 9 | Hoàn tác ở Quản lý khách: giao diện trễ vài giây | Nhẹ | Chưa sửa |
| 10 | Nhãn avatar "bấm để thoát" nhưng mở menu | Nhẹ | Chưa sửa |
| 11 | 94 việc "Gọi xác nhận lịch" cũ trên staging đều quá hạn (không backfill) | Chốt nghiệp vụ | Chờ Tuyền (tính hạn từ ngày lên prod?) |
| 12 | Chờ duyệt vật tư, nhắc >2 tháng khi bán theo đơn, Excel mẫu kế toán, mẫu kiểm kê của anh Thắng, upload kết quả của đối tác | Chưa bấm / chưa có mẫu | Xem từng mục trên |
