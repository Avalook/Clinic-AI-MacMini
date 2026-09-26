# SITEMAP — bản đồ màn hình ClinicAI

> Lập 18/09/2026 (lượt 1, commit `6888633`). Cập nhật cùng ngày sau lượt 2:
> Tuyền chốt "1 ok, 2 bỏ ở home, 3 chỉ xem, 4 gộp hết".
>
> Mọi dòng đều có nguồn:
> - quyền vào lấy từ `NAV_ROLES` trong `src/dashboard/lib/roles.ts`;
> - nhãn thanh bên lấy từ `app/(dashboard)/nav-items.ts`;
> - "ai dẫn tới" lấy từ grep trong `src/dashboard` và `src/clinicai`.
>
> **Tờ này là bản chuẩn.** Trước khi sửa giao diện, tra ở đây xem chức năng đó
> có mấy lối vào (mục B), rồi sửa **tất cả**. Thêm, xoá hay đổi một route thì
> sửa tờ này trong **cùng commit**. Bài kiểm `tests/man-da-gop-boundary.test.mts`
> canh các màn đã gộp: chúng chỉ được còn chuyển hướng.

Trạng thái:
- **GIỮ**: màn chuẩn, đang dùng.
- **ĐÃ CHUYỂN HƯỚNG**: file trang chỉ còn `redirect()`, không có giao diện,
  không có mục thanh bên, không có dòng trong `NAV_ROLES`. Không sửa gì ở đây.
- **CẦN QUYẾT**: chưa chốt.
- **DEV**: chỉ chạy ở máy dev; bị chặn trên prod.

⚠️ Công tắc `NEXT_PUBLIC_MO_QUYEN_TAM_THOI` đang **BẬT** (mặc định `"1"`, xem
`roles.ts`). Khi bật, **mọi vai trong phòng khám gõ URL là vào được mọi trang**
trong bảng này. Ngoại lệ: `/console`, `/ops`, `/settings*`, `/reports`,
`/doi-tac`, `/display`. Cột "Ai vào" là **luật gốc**, chưa tính công tắc.

---

> **THANH BÊN = 21 LEGO (Tuyền 25/09/2026).** Quyền theo TÀI KHOẢN, không theo vai:
> mỗi màn thuộc một lego (`MAN` trong `permissions/catalogue.py`), thanh bên hiện
> màn KHI VÀ CHỈ KHI người ấy có quyền mở nó (`roles.ts` `NAV_QUYEN` → `hienTrenThanhBen`);
> máy chủ chưa trả lời quyền (`null`) thì rơi về luật vai cũ. Luôn bật: `/home`,
> `/hanh-trinh`. Cửa quản trị (nhân sự, tài khoản, cài đặt, lịch trực, bảng giá, báo
> cáo, vận hành, lịch sử thao tác, điều phối ca, CSKH, danh sách/thêm bệnh nhân) hỏi
> quyền ở backend (`cua_quyen` / `doi_quyen`), không còn `require_role(MANAGEMENT)`.
> Cột "Ai" của các dòng dưới là GÓI MẪU mặc định; quản lý bật/tắt lego ở `/phan-quyen`.

## A. Các trang

### Đăng nhập và điểm vào

| Route | Ai vào | Việc | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/login` · `/forgot-password` · `/reset-password` | chưa đăng nhập | Đăng nhập, quên và đặt lại mật khẩu | GIỮ | |
| `/` | mọi vai | Chuyển tới trang đích theo vai (`roleLanding`) | GIỮ | Bác sĩ và thư ký → `/ban-kham`. Bác sĩ siêu âm → `/phong` (danh sách phòng, 23/09). Đối tác → `/doi-tac`. Trưởng ca → `/truong-ca`. Còn lại → `/home`. |
| `/home` | mọi vai | Trang chủ: lịch tuần (**chỉ xem**), trạng thái buổi, lịch làm việc | GIỮ | **Không check-in ở đây** (18/09). Bấm tên khách mở biểu mẫu **chỉ xem**, có nút "Mở ở Bàn khám". Vai check-in thấy nút "Check-in ở Tiếp đón khách". |

### Lễ tân và điều dưỡng

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/reception/queue` | Lễ tân, ĐD, QL | Tiếp đón khách | GIỮ | **Nơi DUY NHẤT check-in.** Trên cùng là "Lịch hẹn hôm nay", có Check-in / Không đến / Hoàn tác. Bên dưới "Danh sách hàng đợi" — **24/09:** hai tab `[Chờ check-in (n)]` (lịch hôm nay chưa tới, `[Check-in]` ngay trên dòng — cùng `PATCH /api/appointments` action=checkin, cùng cổng `canCheckin`) · `[Đã check-in (n)]` (STT = số tiếp đón + cột **Đặt** = số booking, kéo đổi thứ tự). Nút **"Vào khám" OFF** (cờ `NUT_VAO_KHAM`) — check-in là đủ. Nút "Chưa đến — gọi người tiếp theo" **ĐÃ XOÁ** (24/09). Nút `[Check-in]` hiện ở mọi dòng tab Chờ (máy chủ quyết ai được bấm). STT và cột Đặt đứng cạnh nhau. Ba thẻ số đếm theo check-in (Chờ check-in · Đã check-in · Khách ưu tiên). |
| `/reception/checkout` | Lễ tân, QL | Check-out lượt khám | GIỮ | 24/09 chiều: còn việc dở VẪN cho khách về — lý do TUỲ CHỌN (để trống máy tự ghi kèm danh sách việc còn dở, `ly_do_tu_dong`); "khách về giữa chừng" vẫn bắt lý do. |
| `/do-sinh-hieu` | ĐD, Lễ tân, BS, QL | Đo sinh hiệu | GIỮ | **Nơi DUY NHẤT ghi sinh hiệu.** Máy chủ từ chối đường cũ từ `6976513`. **24/09 chiều:** BỎ nút [Bắt đầu] — lần gõ đầu tiên tự gửi lệnh bắt đầu (mốc bắt đầu = lúc gõ), nút lưu đổi tên **[Đo xong]** (= sự kiện đo xong). **25/09:** cạnh [Đo xong] có ô tick **"Bỏ qua bác sĩ tư vấn — vào thẳng bác sĩ chính"** — **ÁP NGAY** vào vị trí khách, không đợi [Đo xong] (Tuyền 25/09 chiều, sau ca bỏ qua nhầm): tick → hàng bác sĩ chính, bỏ tick → về lại hàng tư vấn (`bo-qua-tu-van` → `POST /api/v1/luot-kham/visits/{id}/bo-qua-tu-van`). Ô đọc trạng thái thật (`tu_van: {bo_qua, doi_duoc}` trong danh sách lượt); khoá khi tư vấn đã nhận khách / bác sĩ chính đã khám. Chỉ hiện với lượt qua tư vấn. |
| `/phong` | BS, BS SA, ĐD, TKYK, QL + ai có quyền `service.execute.start` | Phòng dịch vụ | GIỮ (mới 23/09) | **Danh sách phòng dịch vụ đọc từ `clinic_room`** (phòng đang bật, không phải phòng khám), phòng mình đứng hôm nay lên đầu. Thay chín mục `/phong/KN-*` viết cứng. **26/09 (lát 3 bản giao diện mẫu):** 17 mẫu kết quả v3 theo PDF (mig 20260926000004, gắn vào dịch vụ theo mã phòng khám); mục dạng BẢNG (Thai A | B, trái | phải — `BangMuc` trong `PhieuKetQua.tsx`, lưu {ma_cột: giá trị}); mẫu hai bên → HAI ô tải (`KhungTep ben=`), tệp gắn `ben` (mig 20260926000005); mỗi tệp có **Tải về** (`?tai=1` → `Content-Disposition: attachment`), nhiều tệp có **Tải tất cả**. |
| `/phong/[ma]` | MỘT luật `/phong` cho mọi phòng | Tên phòng thật (theo lịch trực hôm nay) | GIỮ | **24/09 trưa:** đầu cột hàng chờ có khối `phong/[ma]/ChuaXepPhong.tsx` "Đã trả tiền — chưa xếp phòng" — khách đã trả mà chưa ai xếp phòng hiện ở MỌI phòng làm được dịch vụ ấy (cùng cơ sở; `chua_xep_phong` của `/api/v1/luot-kham/hang-cho`), nút `[Nhận vào phòng này]` → `xep-phong-v1`. Một component (`PhongDichVu`) cho mọi phòng. **23/09: `[ma]` là `room_id`**; mã phòng cũ (`KN-SA1`…) vẫn mở được. Ngày có ca, thanh bên dựng mục theo `vi_tri_lam_viec.room_id`, tên = `clinic_room.name`. 23/09 khuya: phiếu kết quả mở được cả khi dịch vụ chưa gắn mẫu (mẫu gợi ý v5 chọn sẵn + 18 mẫu dự phòng, `mau_goi_y` từ `thuc-hien`); [In phiếu] → `/print/ket-qua/[orderId]`; [Bắt đầu] hiện cả khi `execution_status` NULL. **24/09 chiều:** phiếu kết quả có mẫu **"Kết quả chung (nhập tự do)"** (`KQ_CHUNG`, migration 20260925000008) — chọn sẵn cho dịch vụ không có mẫu riêng. **24/09 chiều:** nút Xong / **Đã lấy mẫu** có ô **"Ghi chú"** (lưu vào lần làm `service_execution_attempt.ghi_chu`, hiện ở Xem lượt); số "đang chờ" chỉ đếm NGƯỜI KHÁC check-in hôm nay. |

### Bác sĩ và thư ký

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/tu-van` | BS, QL + ai có quyền `clinical.intake.perform` | Bàn khám tư vấn | GIỮ (mới 24/09) | **Hàng tư vấn CHUNG** (dây H1): khách 5 loại khám lõi check-in → đo sinh hiệu → hàng này. `[Bắt đầu tư vấn]` (nhận được cả khách chưa đo — không khoá) → **24/09 chiều: MỘT ô chữ tự do** (`ban-kham/ONhapTuVan.tsx`, tự lưu → `noi-dung-tu-van` → `POST /api/v1/luot-kham/consultations/{id}/noi-dung-tu-van`) → hiện ở mục "Dữ liệu mang sang từ phần khám/tư vấn ban đầu" của phiếu bác sĩ chính (bản mới nhất). Phiếu khám v5 cho bàn tư vấn OFF (cờ `TU_VAN_O_TU_DO`) → `[Xong tư vấn — chuyển bác sĩ chính]` (`xong-tu-van`, đợi phiếu lưu xong) → khối Hành trình xếp khách vào hàng bác sĩ chính (H3). Cùng component `BanKham` chế độ `tu_van`. Vị trí trực "Hỏi bệnh ban đầu" mở màn này. **24/09 chiều:** dưới ô chữ tư vấn có **mục B "Phiếu khám / đánh giá chuyên khoa"** của CHÍNH phiếu khám lượt (`PhieuKhamLuot chiMuc={["B"]}`) — bác sĩ tư vấn và bác sĩ chính cùng thêm/sửa/xoá. |
| `/ban-kham` · `/ban-kham/[phong]` | BS, TKYK, QL (một luật cho mọi phòng) | Bàn khám (24/09: bỏ chữ "khách của tôi") · Bàn khám · <tên phòng> | GIỮ | 23/09: `[phong]` là `room_id` (mã cũ vẫn mở được), ô chọn phòng đi theo `room_id`. **Nơi DUY NHẤT sửa bệnh án** (cùng `/tu-van`, chung component). 24/09: thêm mục **"Sắp tới — đang ở tư vấn"** (chỉ xem). 23/09: trên chỉ còn `[Bắt đầu khám]`; `[Hoàn tất]` ở CUỐI hồ sơ (→ dải xác nhận tại chỗ `XacNhanTaiCho` → `kham-xong`; 24/09 bỏ `window.confirm`). **Không còn Ký bệnh án** (`POST /clinical/{id}/sign` trả 410); Hoàn tất KHÔNG khoá, bệnh án sửa tiếp được. Khung `HoSoHoanTatPanel`: `[Cho phép CSKH gửi]` (sau Hoàn tất), `[Đính chính]` (chỉ lượt cũ đã ký). Nợ sau nhóm 6: mỗi chỉ định có phiếu kết quả có nút `[Xem phiếu kết quả]` (`_lam-viec/XemPhieuKetQua.tsx` → `GET /api/phieu?xem=<order>` → `/api/v1/phieu/xem/{order}`), mở là tự ghi đã xem. **24/09 chiều:** [Hoàn tất] gửi luôn — hộp "Hoàn tất lượt khám này…? [Hoàn tất] [Thôi]" OFF (cờ `HOI_LAI_KHI_HOAN_TAT`); chỉ định khách BỎ ở quầy không chặn Hoàn tất. **24/09 chiều:** `/ban-kham/[phong]` của phòng làm thủ thuật (có bước `DICHVU-THUTHUAT`: phòng Thủ thuật, Sàn chậu) hiện thêm lượt khám chính của khách đặt **Thủ thuật / Sàn chậu** (loại "đi thẳng phòng"), dù lịch đã gắn bác sĩ khác — ai ở phòng bấm Bắt đầu khám là nhận. |
| `/phan-quyen` | ai có lego 19 (`permission.manage`) | Phân quyền | MỚI 23/09 · **LÀM LẠI 25/09 (21 lego)** | **Tab "Quyền của từng người":** chọn người → **21 lego = 21 node thanh bên** (thứ tự thanh bên), mỗi dòng **một công tắc** (`components/ui/CongTac.tsx`; "Một phần" khi có vài khối), "▾ Chi tiết" chỉ XEM màn + khối; lego 5 **Phòng dịch vụ** bật xong bung danh sách phòng (+ "Tất cả phòng" = phạm vi CLINIC, phòng lẻ = ROOM); hai hàng khoá **Luôn bật** (Trang chủ, Hành trình); `[+ Thêm gói mẫu <tên vai tiếng Việt>]`. `phan-quyen/LegoCuaNguoi.tsx` → `GET /api/phan-quyen?lego=<id>` (→ `GET /api/v1/phan-quyen/nhan-su/{id}/lego`), `POST doi-lego` (→ `POST …/lego`). Không còn bật từng khối kỹ thuật (nút "Đang bật — tắt" OFF). Ẩn khỏi màn: Duyệt kết quả, Xác nhận tệp. Tab "Theo màn" (gói mẫu × lego) + "Nhóm quyền mẫu" giữ. |
| `/viec-can-xu-ly` | QL, Thu ngân, Trưởng ca, BS | Việc cần xử lý | MỚI 23/09 | Việc sinh ra từ SỰ KIỆN: khách đã trả tiền mà dịch vụ không làm được (`OPS-FINANCIAL-RESOLUTION`), dịch vụ dừng giữa chừng (`OPS-SERVICE-INTERRUPTED`). Đọc `GET /api/work-items?workspace=khu_van_hanh`; đóng việc bằng lệnh kernel `complete`. |
| `/hanh-trinh` | Mọi vai nội bộ (CSKH, lễ tân, trưởng ca, QL, BS, TKYK, BS SA, ĐD, thu ngân, dược sĩ) | Hành trình khách hôm nay | MỚI 24/09 (nhóm 3) | **Bảng hành trình chung**: mỗi khách hôm nay — đang ở đâu / đã xong gì / còn chờ gì. `hanh-trinh/BangHanhTrinh.tsx` → `?xem=hanh-trinh` → `GET /api/v1/hanh-trinh/hom-nay` (`bang_hanh_trinh_service.py`). "Đã xong" đọc dòng thời gian sự kiện. Mỗi dòng có nút Xem hành trình. |
| `/duyet-ket-qua` | BS, BS SA, QL | Duyệt kết quả | **OFF khỏi thanh bên 23/09 tối** | Tuyền: "không cần cái duyệt kết quả nữa, duyệt làm gì khi ta có thể tự điền vào đây". Bác sĩ đọc/điền kết quả trong phiếu khám (Bàn khám, mục C). Route còn giữ (mở thẳng được); gỡ khỏi `NAV_ITEMS`, `MAN_THEO_VI_TRI`, tab "Theo màn". Chuông "có kết quả về" (`bao_ket_qua_ve.py`) nay trỏ `/ban-kham`. |
| `/xac-nhan-ket-qua` | nội bộ (trừ đối tác, TV) + quyền `result.file.confirm` | Xác nhận kết quả | **OFF khỏi thanh bên 24/09** | Tuyền: "không cần nút xác nhận kết quả, cho vào luôn phiếu khám bác sĩ". Tệp đối tác HỢP LỆ ngay khi tải lên (cờ `XAC_NHAN_TEP_DOI_TAC` trong `tep_ket_qua_service.py`); bác sĩ đọc ở `/ban-kham` mục C (tên tệp mở thẳng tệp). Route còn giữ, bật cờ là về luồng xác nhận. |
| `/patient-list` | gần như mọi vai trong phòng | Danh sách bệnh nhân | GIỮ | Tra cứu chung. Bệnh án mở ở đây **chỉ xem** (`readOnly`). 24/09: dòng + đầu hồ sơ hiện kênh đặt · người giới thiệu · đổi/huỷ gần nhất (`KenhDoiHuy`). |
| `/patients/[id]` | theo quyền trong trang | (không có mục) | GIỮ | Hồ sơ một bệnh nhân. |
| `/patients/new` | Lễ tân, QL | Tạo bệnh nhân / Thêm khách hàng / Nhập thông tin khách hàng mới | GIỮ | Cùng `NewPatientForm` với tab "Thêm" trong `/appointments`. Một nút mang 3 tên theo vai (`navLabelFor`). **25/09 (P4C):** khối "Lịch hẹn khám" có ô **"Chỉ lưu hồ sơ — chưa đặt lịch"** (mặc định KHÔNG tick) — tick thì ẩn khối lịch, bỏ kiểm dịch vụ/ngày/giờ/kênh, chỉ gọi `POST /api/patients` (không gọi `/api/appointments`). Áp cho cả hai lối (`/patients/new` và tab "Thêm" của `/appointments`) vì cùng component. |

### Thu ngân và nhà thuốc

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/thu-ngan/dich-vu` · `/thu-ngan/thuoc` | Lễ tân, thu ngân, QL | Thu tiền dịch vụ · Thu tiền thuốc | GIỮ | **Màn thu tiền duy nhất.** `thu-ngan/QuayThuNgan.tsx`, nút "Đã nhận đủ". **Nhóm 2 (24/09):** ô dịch vụ hiện khách NGAY KHI có chỉ định (không đợi khám xong), thu được nhiều lần; khối `ChonDichVu.tsx` "Khách làm dịch vụ nào?" (bỏ tích = khách không làm) — **25/09 (P2): dịch vụ bác sĩ đánh dấu "Bắt buộc" có nhãn "Bắt buộc", ô tích khoá (không bỏ được); máy chủ chặn `SERVICE_REQUIRED`** + **ô "Làm ở phòng" từng dịch vụ** (24/09 chiều — `phong_chon_duoc` do máy chủ trả; chốt xong gửi `phong-du-kien` → `/api/v1/luot-kham/orders/{id}/routing/phong-du-kien`; thu xong dây H4 xếp đúng phòng này, phòng hỏng thì phòng vắng nhất) → `[Chốt dịch vụ khách làm]`; **mỗi lần tích / bỏ tick / đổi phòng là LƯU NGAY (cùng lệnh chốt) và tổng tiền trừ/cộng liền** (24/09 tối — trước đó bỏ tick chỉ đổi trên màn, tổng vẫn tính tới khi bấm Chốt); **Ô thuốc (24/09 tối):** khối `thu-ngan/ChinhDonQuay.tsx` "Khách lấy thuốc nào?" — tích / bỏ tick, số lượng (thuốc bác sĩ kê: số mua ≤ số kê; thuốc quầy thêm: sửa số lượng, cách dùng, lưu ý) + "Lấy thêm thuốc" dùng lại `DonThuocPhieu` → `/api/quay-thuoc` → `/api/v1/quay-thuoc/*`. Thu rồi thì khoá. **Thu xong vẫn xếp/đổi phòng được (24/09 trưa):** khối `thu-ngan/XepPhongDaThu.tsx` "Phòng làm dịch vụ (đã thu)" dùng lại `DoiPhong` (→ `xep-phong-v1` → `/api/v1/luot-kham/orders/{id}/routing/assign`) cho chỉ định đã trả chưa bắt đầu (`xep_phong` của bảng thu ngân); lượt thu đủ rồi mà khách chưa vào phòng hiện ở mục **"Đã thu — chờ vào phòng"** dưới danh sách chờ thu. thu xong hệ thống tự xếp phòng (dây H4), nút "Xem hành trình · đổi phòng" để báo/đổi phòng. **25/09 (P3) — NGUỒN xếp phòng:** quầy thu xếp/đổi phòng LÚC NÀO CŨNG ĐƯỢC (ô "Làm ở phòng" trước thu: đã xếp thì đổi thẳng phòng thật; khối "Phòng làm dịch vụ (đã thu)": `DoiPhong nguon="quay_thu"`), TRỪ khi trưởng ca đã xếp — ô khoá, ghi "Trưởng ca đã xếp — muốn đổi báo trưởng ca" (`truong_ca_da_xep` của `xep_phong`); máy chủ chặn `ROUTING_TRUONG_CA_DA_XEP`. Mỗi lần xếp ghi `service_order.routing_nguon` (quay_thu · truong_ca · tu_dong · khac, migration 20260925000016) + sự kiện `service.routed.nguon`. Ô thuốc vẫn đợi khám xong (nhóm 4). **24/09 chiều:** thu QR / chuyển khoản: [Đã nhận tiền] KHÔNG bắt mã giao dịch (ô mã tuỳ chọn; migration 20260925000007 bỏ CHECK `payment_cycle_dien_tu_co_ma`). 24/09 chiều: ô "Khách làm dịch vụ nào?" có nhãn **"Đối tác làm"** cho chỉ định làm bên ngoài (`doi_tac`). |
| `/cashier/thuoc` · `/cashier/dich-vu` | lego 16 Bảng giá (`price.service.manage`) | Bảng giá thuốc · Bảng giá dịch vụ | GIỮ (`/cashier/thuoc` **TẮT khỏi thanh bên 25/09**) | Là **bảng giá**, không phải thu tiền. **25/09:** giá thuốc chuẩn chuyển về **Kho thuốc → Danh mục thuốc** (`/pharmacy/inventory`); các dòng nhóm thuốc ở đây đã TẮT (migration 20260925000014) — sửa giá thuốc ở Kho. Sửa ở đây vẫn đồng bộ sang danh mục cùng tên (`_dong_bo_gia_danh_muc_thuoc`). **26/09 (lát 1 bản giao diện mẫu):** Bảng giá dịch vụ có cột **Mã phòng khám** (mã KiotViet, sửa tại dòng; mã ẩn `CLS_*`/`KV_*` in nhạt dưới) + cột **Phòng làm** (chọn là lưu); ô tìm tra cả mã phòng khám; thêm mới nhập mã phòng khám + phòng làm (mã danh mục bỏ trống = `KV_<mã>`). `/api/service-price` (GET `?xem=phong-lam`, POST/PATCH mang `ma_kiotviet`, `node_code`) — bỏ chốt VAI ở proxy, máy chủ hỏi `price.service.manage`. |
| `/pharmacy` | Lễ tân, dược sĩ, QL | Cấp thuốc | GIỮ | **Làm lại 19/09 (contract tiền–thuốc CP4):** theo lượt, đọc qua `GET /api/v1/pharmacy/ban-thuoc` (không còn đọc thẳng Supabase). `PharmacyBoard.tsx` + `DongThuoc.tsx` (thay `ThaoTacCapPhat.tsx`): xác định thuốc kho · số mua · chọn/bỏ/đổi lô · giao thuốc — nút theo `thao_tac` máy chủ trả. 24/09 chiều: MỘT kho — lưu đơn tự gắn thuốc kho theo tên (thiếu thì thêm vào danh mục, `needs_review`); thuốc mẫu của phiếu gắn theo tên trùng khít; migration 12 bù dòng cũ. |
| `/pharmacy/inventory` | Lễ tân, dược sĩ, QL | Kho thuốc | GIỮ | **25/09 — hai tab** (`pharmacy/inventory/KhoThuoc.tsx`): **Danh mục thuốc** (`DanhMucKho.tsx` — nạp sẵn 82 mặt hàng KiotViet + 9 thuốc chỉ có trên phiếu v5 [cần soát], migration 20260925000014; lọc Đang dùng / Cần soát / Đã tắt; `[+ Thêm thuốc]`, `[Sửa]` tên · mã hàng · giá bán · đơn vị · đường dùng · biệt dược · cách dùng · lưu ý · bật/tắt → `luu-thuoc` → `POST /api/v1/pharmacy/danh-muc`; đọc `GET /api/v1/pharmacy/danh-muc`) và **Tồn theo lô** (`InventoryBoard.tsx` — `[+ Nhập lô]` (`NhapLo.tsx` → `receive`), từng lô `[Điều chỉnh]` (`adjust`, số có dấu + lý do) / `[Huỷ]` (`discard` + lý do)). **Danh mục kho là NGUỒN GIÁ THUỐC DUY NHẤT** (khép HOLD J5: `service_price` nhóm thuốc TẮT) và nguồn hướng dẫn của màn kê đơn. Quyền ghi: `pharmacy.dispense`. |
| `/pharmacy/history` · `/pharmacy/consult` | dược sĩ, QL | Lịch sử bàn giao · Tư vấn dùng thuốc | GIỮ (Claude chốt 24/09 — Tuyền soát) | Còn gắn badge "Mới". 24/09: đọc qua backend `/pharmacy/lich-su` · `/pharmacy/cho-tu-van` (thôi đọc thẳng Supabase). |

### CSKH và lịch hẹn

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/customers` | CSKH, **Lễ tân (24/09, đủ quyền)**, QL, trưởng ca, thu ngân | Quản lý khách hàng | GIỮ | Màn chuẩn của CSKH. 24/09: danh sách khách (lọc kỳ / theo hẹn / tìm không dấu / phân trang) đọc qua `/cskh/danh-sach-khach`. **24/09 chiều:** modal "Đổi / huỷ lịch hẹn" MỞ — đổi được dịch vụ (đủ loại khám đang bật, không còn 5 lĩnh vực cứng), kênh đặt, người giới thiệu (điền sẵn từ hồ sơ), ô **"Lý do đổi lịch"** → `appointment_doi_lich.ly_do`; danh sách khách + khung thông tin hiện **kênh đặt gần nhất · người giới thiệu · đổi/huỷ gần nhất + lý do** (`customers/KenhDoiHuy.tsx`, cột `COT_KENH_DOI_HUY`); dòng trạng thái có lại ô **"Đã gọi nhắc hẹn"** (NHAC_HEN_MAI) + ô **"Ghi chú khi gọi — khách dặn dò gì"** (ghi kèm lần bấm vòng tròn, hiện lại dưới ô). |
| `/appointments` | CSKH, Lễ tân, QL | Đặt lịch | GIỮ | Đặt "Trực tiếp" hôm nay thì tự check-in (luật máy chủ). 24/09: loại khám = 7 (5 lõi + **Thủ thuật** + **Sàn chậu chuyên sâu**, migration 20260925000006; hai loại sau đi thẳng phòng — dây H2). |
| `/appointments/cho-xep-bac-si` | QL, CSKH | Chờ xếp bác sĩ | **TẮT khỏi thanh bên 25/09** (route giữ) | Tuyền 25/09: tạm tắt. Thông báo từ máy chủ vẫn trỏ vào đây (mở thẳng được). `roles.ts` `TAT_KHOI_THANH_BEN`. |
| `/nhac-tai-kham` | QL | Nhắc tái khám | GIỮ | Cùng API với khối nhắc tái khám trong `/customers`. |
| `/lich-do-ve` | QL | Lịch đổ về | GIỮ | |

### Trưởng ca, đối tác, màn TV

| Route | Ai vào | Nhãn thanh bên | Trạng thái |
|---|---|---|---|
| `/truong-ca` | lego 9 Điều phối khách (`dispatch.manage`) | Điều phối ca | GIỮ | **25/09 (P3):** đổi phòng ở "Bác sĩ chỉ định gì" gửi `nguon="truong_ca"` — trưởng ca CAO NHẤT: đè được lần xếp của quầy thu / tự động, và lần xếp của trưởng ca thì chỉ trưởng ca đổi được. 24/09: ô "Chuyển bác sĩ" chia nhóm (Đang trực hôm nay · Bác sĩ khác · Quản lý có quyền khám) — `/api/dispatch-read?what=bac-si` → `/api/v1/dispatch/bac-si` trả `nhom`. Có link "Hành trình khách hôm nay →" sang `/hanh-trinh`. 24/09: khối "Bác sĩ chỉ định gì" (`truong-ca/ChiDinhCuaBacSi.tsx`) đổi phòng chỉ định đời mới bằng khối chung `_lam-viec/DoiPhong.tsx` (`xep-phong-v1`, cùng luật Bàn khám / Xem lượt); chỉ định đời cũ vẫn ô chọn phòng cũ (`xep-phong` → `/orders/{id}/dispatch`). |
| `/truong-ca/hang-doi` | trưởng ca, QL | Hàng đợi theo trạm | GIỮ |
| `/truong-ca/lich-su` | trưởng ca, QL | Lịch sử điều phối | GIỮ |
| `/truong-ca/tv` | trưởng ca, QL | TV phòng chờ | GIỮ |
| `/doi-tac` | đối tác, QL | Việc của đối tác | GIỮ 24/09 chiều: bàn chỉ hiện việc ĐÃ NHẬN qua sự kiện (`doi_tac_nhan_viec`, dây H9): tự-lấy-mẫu sau khi khách trả tiền, điều-dưỡng-lấy sau khi phòng bấm Xong; có chuông vai Đối tác. Nút "Đã lấy mẫu" / "Nhận mẫu · chờ tài liệu" có ô **ghi chú** (lưu `doi_tac_nhan_viec.ghi_chu_*`, hiện trên bàn + Xem lượt). |
| `/display` | DISPLAY (máy TV) | (không có mục) | GIỮ |

### Quản lý và hệ thống

| Route | Ai vào | Nhãn thanh bên | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `/schedule` | mọi vai trừ CSKH, đối tác, TV | Lịch làm việc | GIỮ | |
| `/reports` | QL | Báo cáo | GIỮ | 24/09: các ô đếm đọc qua `/reports/tong-quan` (một lượt, theo ngày VN). |
| `/audit-log` | CSKH, QL | Lịch sử thao tác | GIỮ | |
| `/nhan-su` | QL | Quản lý nhân sự | GIỮ | **Không quản quyền** (23/09): ô "Được xác nhận tệp kết quả" (hệ `staff_capability` cũ) đã gỡ; nút `[Mở Phân quyền cho người này]` → `/phan-quyen?nguoi=<id>`. `/api/staff/{id}/capabilities` trả 410. |
| `/settings` | QL | Cài đặt | GIỮ | |
| `/settings/booking-policy` | QL | Luật đặt lịch | GIỮ | 24/09: card "Giờ mở cửa & giờ ca làm việc" (`settings/GioCaLamViecCard.tsx`) sửa được GIỜ MỞ CỬA từng ngày + [Chép giờ Thứ Hai cho cả tuần]; lưu cùng giờ ca một lần → `/api/ca-lam-viec` PATCH `{ca_lam_viec, gio_mo_cua}` → `/api/v1/ca-lam-viec`. |
| `/settings/clinic-config` | QL | Cấu trúc phòng khám | GIỮ | 23/09 (CORE-C): phòng là tài nguyên, định danh `room_id`. `[+ Thêm phòng]` (tên tự do + làm việc gì + tầng; mã nội bộ tự sinh, không hiện) · sửa tên tại chỗ · `[Tắt phòng]/[Bật phòng]` (chặn khi còn khách chờ) · dải cảnh báo bước chưa có phòng (`CONFIG_MISSING`). |
| `/settings/day-noi` | QL (+ ai có quyền `config.wiring.manage`) | Dây nối nghiệp vụ | MỚI 24/09 (nhóm 5) | Khối chỉnh dây: bật/tắt tự xếp phòng (H4), báo CSKH khi khách về còn việc (H6), số ngày kết quả đối tác quá hạn (H7), số phút nhắc check-out (H8); loại khám qua tư vấn / đi thẳng phòng; ai nhận chuông; vị trí trực (thêm, đổi tên, gắn phòng, tắt). `settings/day-noi/DayNoiBoard.tsx` → `/api/day-noi` → `/api/v1/day-noi*`. |
| `/settings/mau-ket-qua` | QL (+ ai có quyền `catalogue.result_template.manage` / `catalogue.form_template.edit` / `catalogue.form_template.publish` — lego 18, khối "Danh mục & biểu mẫu") | Mẫu kết quả | MỚI 27/09 | Hai tab (`settings/mau-ket-qua/`). **Gắn mẫu cho dịch vụ** (`GanMau.tsx`): dịch vụ CÓ PHÒNG LÀM theo phòng, tìm theo tên / mã phòng khám / phòng, lọc "chưa gắn"; [+ Gắn mẫu…] / [Gỡ] → `POST /api/mau-ket-qua {thao_tac: gan\|go}` → `/api/v1/mau-ket-qua/gan\|go`; "Máy đề xuất theo tên" (`/mau-ket-qua/de-xuat`) chỉ gợi ý, bấm [Gắn] mới gắn. **Sửa · tạo mẫu** (`SuaMau.tsx` + `TrinhSuaMau.tsx`): sửa mục / ô (tên, kiểu: chữ ngắn · đoạn văn · số · ngày · chọn một), lựa chọn, đơn vị, câu bình thường điền sẵn (bảng: theo cột), mục dạng bảng (≤8 cột), đổi thứ tự / xoá; [Xuất bản bản N+1] → `/api/v1/bieu-mau/{form_id}/xuat-ban` kèm `expected_version` (người khác vừa xuất bản → 409 + [Tải bản mới]); máy chủ KIỂM khung (`phieu_kham/kiem_khung_mau.py`); đổi tên ô KHÔNG đổi mã ô, ô mới nhận mã lúc xuất bản; phiếu đã điền giữ bản cũ. [+ Tạo mẫu mới] (trống có mục Kết luận, hoặc chép từ mẫu có sẵn) → `/api/v1/mau-ket-qua/tao`. Đổi sang mẫu khác khi còn thay đổi chưa xuất bản → hỏi tại chỗ (`XacNhanTaiCho`). |
| `/settings/tai-khoan` | QL | Thiết lập tài khoản cho nhân viên | GIỮ | |
| `/settings/new-user` | QL | (không có mục; mở từ `/settings/tai-khoan`) | GIỮ | |
| `/ops` | QL | Vận hành hệ thống | GIỮ | **Ba tab:** Hệ thống (`OpsCenter`) · Sức khoẻ API (`SucKhoeApi`, `?tab=api`) · Toàn cảnh (`ToanCanh` → `PortalBoard`, `?tab=toan-canh`, đọc qua `/reports/toan-canh` từ 24/09; tiêu đề trong tab cũng là "Toàn cảnh"). Thanh trên cùng của trang không có tiêu đề riêng lấy tên nút thanh bên (`GlobalHeader` ← `NAV`). |
| `/console` | | | DEV | `notFound()` khi `APP_ENV=production`. |
| `/design-system` | | | DEV | `notFound()` khi không phải `development`. |
| `/print/[appointmentId]` | | (nút In phiếu) | GIỮ | 24/09: đọc qua `/clinical-records/in-theo-lich/{id}` (cửa ROLE-02 như hồ sơ lâm sàng). |
| `/print/sono/[id]` | | | **OFF 24/09** (Claude chốt — Tuyền soát) | Không chỗ nào dẫn tới. Trang chỉ còn câu báo tắt; phiếu in kết quả hiện hành là `/print/ket-qua/[orderId]`. Bản cũ nằm trong git. |
| `/print/phieu-kham/[visitId]` | BS, TKYK, QL + ai có khối khám/kết quả (`requireClinicalRole`) | In phiếu khám | MỚI 24/09 | Tuyền: "chỗ cho in phiếu khám của bệnh nhân đâu?". Mở từ `[In phiếu khám]` ở đầu phiếu khám v5 (`PhieuKhamLuot` → `PhieuKham`, Bàn khám). Bản in CHỈ ĐỌC, chữ thường thay ô nhập; đọc đúng 5 nguồn Bàn khám đọc qua `/api/phieu-kham` (phiếu · đầu phiếu · chỉ định+kết quả · đơn thuốc · tham chiếu). Lượt chưa mở phiếu → báo "chưa có gì để in". Khác `/print/[appointmentId]` (Tóm tắt khám bệnh đời cũ, mở từ `/home`). **26/09 (lát 5):** A4 theo bản mẫu (`app/print/KieuInA4.tsx`: lề 14/12/16mm, chân trang "DR4WOMEN CLINIC · Trang x / y" — Safari không in dòng số trang), in theo BA KHỐI (`KHOI_PHIEU` chung với màn khám), ẨN ô / nhóm / mục trống (trước in "—" từng ô), KHÔNG in khối tư vấn; không cắt đôi dòng bảng / chữ ký. |
| `/print/ket-qua/[orderId]` | BS, TKYK, BS SA, ĐD SA, trưởng ca, QL, CSKH + ai có `result.form.fill` | In phiếu kết quả | MỚI 23/09 khuya | Mở từ `[In phiếu]` của `PhieuKetQua` (phòng dịch vụ + phiếu khám mục C) và `[In]` ở dòng kết quả mục C. Đọc `GET /api/phieu?in=` → `/api/v1/phieu/in/{order}`. Bản chưa Hoàn tất in kèm "BẢN NHÁP". **26/09 (lát 5):** A4 (`KieuInA4`), in kèm ẢNH của chỉ định 4 tấm/hàng (`anh` trong `GET /api/phieu?in=` — tệp chưa xác nhận / bị từ chối / thu hồi không in; video, tài liệu chỉ đếm); chỉ định CHỈ có ảnh vẫn in được trang ảnh; không cắt đôi Kết luận / chữ ký. |

### Đã chuyển hướng (không còn giao diện)

| Route cũ | Chuyển tới | Gộp ngày |
|---|---|---|
| `/tasks` | **theo vai:** thu ngân → `/thu-ngan/dich-vu` · BS SA → `/phong` · BS/TKYK → `/ban-kham` · ĐD → `/do-sinh-hieu` · Lễ tân → `/reception/queue` · QL/CSKH → `/customers` · còn lại → `/home` | 18/09 |
| `/queue` | `/reception/queue` | 18/09 |
| `/cashier/board` | `/thu-ngan/dich-vu` | 18/09 |
| `/cskh-tasks` | `/customers` (bảng `cskh_action` 0 dòng trên prod) | 18/09 |
| `/episodes` | `/customers` (0 đợt `PENDING_CLOSE` trên prod; không code nào còn tạo trạng thái ấy) | 18/09 |
| `/work-sessions` | `/schedule` (bảng `work_session` 0 dòng trên prod) | 18/09 |
| `/portal` | `/ops?tab=toan-canh` | 18/09 |
| `/ops/telemetry` | `/ops?tab=api` | 18/09 |
| `/doctor/board` · `/doctor/orders/[visitId]` · `/kham/[loai]` · `/luot-kham` | `/ban-kham` | 16/09 |
| `/lab-queue` | `/phong` (23/09; trước là `/phong/KN-LAYMAU`) | 16/09 |
| `/service-queue` | `/phong` (23/09; trước là `/phong/KN-THUTHUAT`) | 16/09 |
| `/sieu-am` · `/sono` | `/phong` (23/09; trước là `/phong/KN-SA-T1`) | 16/09 |
| `/result-review` | `/duyet-ket-qua` | 16/09 |
| `/cashier` | `/cashier/thuoc` | |

Thư mục `app/(dashboard)/tasks/` vẫn giữ **component dùng chung**:
`ClinicalRecordForm`, `ServiceFormEngine`, `DoctorApptRow`… Chỉ `page.tsx` là
chuyển hướng.

**Route `/api` đã tắt (24/09/2026, trả 410 ở `proxy.ts`, danh sách ở
`lib/route-da-tat.ts`)** — không màn nào gọi: `dispatch/alerts-call`,
`cskh/ket-qua/[tepId]/cho-phep-gui`, `cskh/zalo`, `lab-result` (gốc; `/review`
và `/triage` vẫn chạy), `sono`, `service-log`, `ultrasound/image`,
`visits/[id]/charges`, `visits/[id]/service-orders` (+ `current`, `draft`,
`draft/approve`, `draft/discard`, `duplicates`, `remove`),
`work-items/[id]/blockers`, `patients/check-phone`. File giữ nguyên; bỏ dòng ở
danh sách là bật lại.

---

## B. Một chức năng, mấy lối vào (bảng tra trước khi sửa)

| Chức năng | Lối vào (file) | Ghi / xem |
|---|---|---|
| **Bệnh án** (`ClinicalRecordForm`) | `ban-kham/BanKham.tsx` | **ghi** |
| | `home/WeeklyAppointmentsTable.tsx` | chỉ xem (`readOnly` + `vitalsOnly`) |
| | `patient-list/PatientListView.tsx` | chỉ xem (`readOnly`) |
| **Phiếu khám theo dịch vụ** (`ServiceFormEngine`) | `ban-kham/BanKham.tsx` · `tasks/ClinicalRecordForm.tsx` | ghi ở Bàn khám — **OFF cho lượt KHÁM từ 23/09 tối** (cờ `PHIEU_V5`), chỉ còn đọc lượt cũ (`LuotKhamTruoc`) và bàn khám tư vấn |
| **Phiếu khám v5 (bảy phiếu NT/HMVS/PK/SK/NK/Thủ thuật/Sàn chậu)** — 23/09 khuya: tab "Chỉ định & kết quả" + cột `ChiDinhPanel` ở `/ban-kham` **OFF** (cờ `PHIEU_V5`); tệp kết quả mở ở mục C `[Ảnh · tệp]` (`KhungTep`) | `ban-kham/BanKham.tsx` → `_lam-viec/phieu-kham/PhieuKhamLuot.tsx` (→ `PhieuKham`, `DanhMucChiDinh`, `KetQuaChiDinh`, `DonThuocPhieu`) → `/api/phieu-kham` (GET `?visit_id&xem=phieu|dau-phieu|don-thuoc`, PUT `luu-phieu`/`luu-don`) → `/api/v1/phieu-kham/*` | **23/09 tối.** Tự lưu (không nút Lưu hồ sơ). Mục C/F: danh mục có giá → chỉ định thật (`chi-dinh`). **25/09 — Chỉ định thêm:** lượt đã có chỉ định thì trên cùng mục C/F là ghi chú **"Đã chỉ định — Lần 1 · 09:40 — …"** (gom theo vòng khám, `lan` do máy chủ trả trong `/api/phieu-kham?visit_id`), danh mục gập sau nút **[+ Chỉ định thêm (lần N)]** → cùng lệnh `chi-dinh` (vẫn thu tiền rồi làm như lần đầu); mục đã chỉ định ghi "Đã chỉ định · lần k" **26/09 (lát 4) — số lần thật:** cột `service_order.lan_chi_dinh` do trigger gán (mỗi lần bấm chốt = một lần, cả khi cùng vòng khám; nháp thư ký nhận số lúc duyệt; mang sang = không số; migration 20260926000006) — trước đó chỉ định thêm trong cùng phiên vẫn hiện "Lần 1". Mục đã chỉ định **tô xanh nhưng VẪN TICK LẠI ĐƯỢC** ở lần mới (kèm ô "Bắt buộc"). `ChiDinhPanel` cũ (cờ `PHIEU_V5` OFF) cố ý không sửa. Mục C: chỉ định làm ở **đối tác** (phòng `lam_ben_ngoai`) có chip "Đối tác · chờ lấy mẫu / đã lấy mẫu / chờ tài liệu / đã gửi kết quả" (`doi_tac` trong `/api/phieu-kham?visit_id`, cùng hàm `trang_thai_doi_tac` với bàn đối tác); danh sách chỉ định + kết quả tự nạp lại khi có tin `service_order` / `form_instance` / `tep_ket_qua`. **25/09 (P2) — Bắt buộc:** tick một dịch vụ để chỉ định thì hiện ô nhỏ **"Bắt buộc — quầy thu không bỏ được"** (mặc định KHÔNG tick; gửi `bat_buoc_codes` cùng lệnh `chi-dinh`). Ghi chú "Đã chỉ định" có ô **"bắt buộc"** cạnh từng dịch vụ → `bat-buoc` → `POST /api/v1/luot-kham/orders/{id}/bat-buoc` (quyền Chỉ định; chỉ khi CHƯA thu — máy chủ chặn `SERVICE_ALREADY_PAID`; sự kiện `service_order.required_changed`; cột `service_order.bat_buoc`, migration 20260925000017). Mục C: [Xem kết quả] (tự ghi đã xem) · [Điền kết quả] (`PhieuKetQua`, cùng engine phòng). Mục E: đơn thuốc tự lưu → `luu_don_chua_ky` → nhà thuốc. **25/09:** danh sách thuốc gợi ý = 73 thuốc của phiếu (đủ 73 mã ghép kho ở `anh_xa_danh_muc.THUOC`) + mọi mặt hàng kho khác (`kho:<id>`); tên/giá/đơn vị/cách dùng/lưu ý đọc từ **danh mục kho** — dược sĩ sửa ở Kho là màn kê đơn đổi theo. Bệnh án cũ `ClinicalRecordForm` OFF cho lượt khám (cờ `PHIEU_V5`). **26/09 (lát 2 bản giao diện mẫu) — BA KHỐI:** phiếu bác sĩ chính gom mục sẵn có thành 1 · Thông tin cơ bản (A+B) · 2 · Chỉ định cận lâm sàng (C) · 3 · Chỉ định điều trị (D+E+F+G); hành chính luôn ở trên; nút khối ở CỘT PHẢI dính khi cuộn (màn hẹp: hàng nút trên đầu), bấm khối nào hiện khối đó, nút "Sang: … →" ở cuối; `ma` ô KHÔNG đổi. Tự lưu gửi CHỈ ô vừa đổi (`thay_doi`) — hai người sửa hai ô khác nhau không 409. Bàn tư vấn: mục B sau công tắc **"Thông tin cơ bản"** (`CongTacThongTinCoBan.tsx`, mặc định đóng). Ngày tái khám mục G (`*_follow_date`) sinh nhắc tái khám (mig 20260926000002). **25/09 (P4A) — Lịch sử sửa:** đầu phiếu có nút **[Lịch sử sửa]** (`LichSuSuaPhieu.tsx`, cạnh "In phiếu khám") → `/api/phieu-kham?visit_id&xem=lich-su&chon=<form>` → `GET /api/v1/phieu-kham/luot/{visit_id}/lich-su` (cùng quyền đọc phiếu): ai · lúc nào · ô nào · trước → sau, nhãn "Ghi lần đầu" / "Sửa sau Hoàn tất". Trigger `ghi_lich_su_phieu_kham` trên `phieu_kham_luot` ghi bảng `phieu_kham_lich_su` (migration 20260925000018), cùng người trong 10 phút gộp một dòng. Hoàn tất vẫn KHÔNG khoá; đính chính đơn thuốc đã thu/cấp (`dinh_chinh_don`) giữ nguyên. **26/09 (lát 5 — bản giao diện mẫu):** đầu phiếu bác sĩ chính có dải **"Hành trình hôm nay"** (`HanhTrinhLuot.tsx` → `components/ui/Timeline` ← `GET /api/phieu-kham?visit_id&xem=hanh-trinh` → `/api/v1/phieu-kham/luot/{id}/hanh-trinh`, cùng quyền đọc phiếu; mốc do máy chủ tính từ `luot_dong_thoi_gian` + hiện trạng, nhiều chỉ định cùng lúc = MỘT mốc theo lần; "Đang ở …" cùng hàm Bảng hành trình; tự nạp lại theo tin realtime). Bàn tư vấn (`chiMuc`) không có dải này. Mục C: ảnh / video / tài liệu hiện NGAY tại dòng chỉ định (`_lam-viec/AnhKetQua.tsx`: ≤3 tệp từng tấm, nhiều hơn xếp chồng theo loại + "Xem tất cả N →"); nút **⤢** và bấm ảnh mở hộp CHIA ĐÔI (`components/ui/Lightbox`: kết quả trái, ảnh phải; [Chỉ xem ảnh] · [Lưới] · [Tải về] · [Tải tất cả]) — mở hộp = xem kết quả nên ghi "đã xem" như [Xem kết quả]. |
| **Check-in / Không đến / Hoàn tác** | `reception/queue/page.tsx` → `WeeklyAppointmentsTable` với `choCheckIn` · **Check-in** còn ở `reception/queue/QueueBoard.tsx` tab "Chờ check-in" (24/09, cùng API + cùng cổng `canCheckin`) | cùng một màn `/reception/queue` |
| | đặt lịch "Trực tiếp" hôm nay (`/appointments`) | máy chủ tự check-in |
| **Bảng lịch hẹn** (`WeeklyAppointmentsTable` + `home/lich-hen-ngay.ts`) | `/home` (cả tuần, xem) · `/reception/queue` (hôm nay, check-in) | cùng một phép dựng |
| **Hàng chờ tiếp đón** (`QueueBoard`) | `/reception/queue` | |
| **Ghi sinh hiệu** | `/do-sinh-hieu` | biểu mẫu bệnh án chỉ xem + nút dẫn sang |
| **Chọn lô / giao thuốc** (`/api/pharmacy/{phan-lo,bo-phan-lo,doi-lo,dispense,…}`) | `pharmacy/DongThuoc.tsx` (qua `/pharmacy`) | **chỉ ở đây** (contract tiền–thuốc CP4) |
| **Thu tiền** (`POST /api/payment`) | `thu-ngan/QuayThuNgan.tsx` (qua `/thu-ngan/dich-vu`, `/thu-ngan/thuoc`) | chỉ ở đây |
| **Khách chọn làm dịch vụ nào** (`chon-dich-vu` → `POST /luot-kham/visits/{id}/service-selection/confirm`) | `thu-ngan/ChonDichVu.tsx` (trong `QuayThuNgan.tsx`) | **chỉ ở đây** — nhóm 2, 24/09. Trước đó lệnh có mà không màn nào gọi, nên chỉ định mới không vào được hoá đơn. 25/09: dịch vụ "Bắt buộc" không bỏ được — bỏ tick ở phiếu khám (Bàn khám) |
| **Tạo bệnh nhân** (`NewPatientForm`) | `/patients/new` · tab "Thêm" trong `/appointments` | cùng component |
| **Đặt / sửa lịch** (`AppointmentBooking`) | `customers/AppointmentEditModal.tsx` · `customers/DatLichModal.tsx` · `patients/[id]/PatientBooking.tsx` | `/appointments` dùng `BookingHub` riêng — CẦN QUYẾT |
| **Nhắc tái khám** (`/api/recall-jobs`) | `customers/NhacTaiKham.tsx` · `customers/VungLamViecKhach.tsx` · `nhac-tai-kham/ViecGoiNhac.tsx` | cùng API |
| **Tệp kết quả** (`/api/cskh/ket-qua`) | `customers/TepKetQua.tsx` · `_lam-viec/KhungTep.tsx` · `tasks/TepCuaLuotKham.tsx` | 26/09 (lát 5): hộp xem tệp CHUNG `components/ui/Lightbox` (lật ←/→, lưới, Tải về, Tải tất cả, PDF trong khung) thay popup một-tệp ở `KhungTep` và `customers/TepKetQua` (`tasks/TepCuaLuotKham` dùng lại `TepKetQua`); ô gửi tệp là `components/ui/Dropzone`. Mở tệp KHÔNG ghi "đã xem". |
| **Chỉ định dịch vụ / cận lâm sàng** (`service_order`) | `ban-kham/BanKham.tsx` → `ChiDinhPanel`. **23/09: bác sĩ VÀ thư ký y khoa cùng bấm `[Xác nhận N chỉ định]` → lệnh `PlaceServiceOrders` (`chi-dinh` → `POST /luot-kham/consultations/{id}/service-orders`), không còn bước duyệt.** Nút `[Duyệt … (bản cũ)]` chỉ hiện khi lượt còn bản nháp cũ. Lát `docs/slices/CD-01-bac-si-chi-dinh-dich-vu.md` | **chỉ ở đây.** Ô "Chỉ định CLS" gõ tự do trong bệnh án (ghi `lab_result`) đã gỡ 18/09 — Slice 1 |
| **Thực hiện dịch vụ trong phòng** (`/luot-kham/orders/{id}/execution/*`) | `phong/[ma]/PhongDichVu.tsx` | **chỉ ở đây.** 23/09: backend có NĂM lệnh, nhưng màn chỉ bày **hai nút chính — [Bắt đầu] rồi [Hoàn tất]** (ChatGPT tin 156, Tuyền tin 157). Ba ngoại lệ (không làm được · dừng giữa chừng · làm lại) nằm ở hàng phụ. Trạng thái + hai `revision` đọc qua `?xem=thuc-hien`. Hai đường cũ `bat-dau-dich-vu`/`xong-dich-vu` còn trong danh sách trắng nhưng **không màn nào gọi**. Lát `docs/slices/TH-01-thuc-hien-dich-vu.md` |
| **Điền phiếu kết quả** (`/api/phieu` → Form Template Engine) | `_lam-viec/PhieuKetQua.tsx`, mở từ `phong/[ma]/PhongDichVu.tsx` | Một màn cho MỌI biểu mẫu: máy chủ trả `khung`, màn vẽ đúng khung ấy. **[Hoàn tất] là nút kết thúc DUY NHẤT**: nó đóng luôn dịch vụ và phát `result.ready` nếu dịch vụ có kết quả ngay tại phòng. **Hoàn tất rồi vẫn sửa được** — [Sửa lại] → [Xác nhận sửa] → `result.corrected`. Ruột 18 mẫu phòng khám đưa sau — không phải sửa TSX. Lát `docs/slices/BM-01-form-template-engine.md` **27/09:** mẫu nào gắn cho dịch vụ nào, nội dung mẫu — sửa ở `/settings/mau-ket-qua` (bản mới chỉ áp cho phiếu mở sau khi xuất bản). |
| **Nhóm quyền mẫu** (`/api/phan-quyen?nhom=1`) | `phan-quyen/NhomQuyenMau.tsx` (tab trong `/phan-quyen`) | Quản lý thêm · sửa · xoá nhóm mà không cần deploy. Nhóm **không phải quyền**: sửa nhóm không đổi quyền người đã cấp. Nhóm dựng sẵn thì tắt chứ không xoá mất dấu. |
| **Bác sĩ quyết kết quả chờ / dịch vụ không làm được** (`/luot-kham/cho-quyet`, `quyet-yeu-cau`) | `ban-kham/ChoBacSiQuyet.tsx` | bác sĩ quyết; thư ký chỉ xem — Slice 1 |
| **Xem lại một lượt khám** (`/xem-luot/{visit}`, chỉ đọc, máy chủ cắt theo vai) | `_lam-viec/XemLuot.tsx` (+ `NutXemLuot.tsx`) mở từ: `ban-kham/BanKham.tsx` · `do-sinh-hieu/BangDoSinhHieu.tsx` · `phong/[ma]/PhongDichVu.tsx` · `truong-ca/ChiDinhHomNay.tsx` · `reception/queue/QueueBoard.tsx` · `thu-ngan/GiaoDich.tsx` · `thu-ngan/QuayThuNgan.tsx` (nhóm 2 — đổi phòng sau khi thu) · `hanh-trinh/BangHanhTrinh.tsx` (nhóm 3) · `pharmacy/PharmacyBoard.tsx`. Nhóm 3: thêm mục "Hành trình (sự kiện)" đọc `luot_dong_thoi_gian`; CSKH xem được. Nhóm 5: thêm "Tự nhắc tôi về khách này" (`_lam-viec/TuNhac.tsx` → `/api/nhac-viec`) | batch pilot 18/09 24/09 chiều: chỉ định khách BỎ ở quầy ra khỏi danh sách việc (một dòng "Khách không làm: …"); dưới mỗi dịch vụ hiện **ghi chú** của phòng / đối tác. |
| **Thai kỳ** (`/api/thai-ky`) | `ban-kham/ThaiKy.tsx` (cạnh phiếu Sản) | bác sĩ ghi; vai lâm sàng khác chỉ xem |
| **Giao dịch thu ngân đã ghi** (`/api/cashier?xem=giao-dich`) | `thu-ngan/TabThuNgan.tsx` → `GiaoDich.tsx` (tab Đã thanh toán hôm nay · Lịch sử) | chỉ đọc |
| **Chuyển phòng** | `truong-ca/ChiDinhCuaBacSi.tsx` (từng chỉ định — luồng mới) · `truong-ca/OverviewClient.tsx` (cả lượt — chỉ lượt đời cũ; lượt luồng mới bị ẩn + máy chủ từ chối) | Slice 1 |

---

## C. Bài học dẫn tới tờ này

Ngày 17/09, nút QR demo được gỡ ở `tasks/CashierWorkBoard.tsx`. Đó là **bản
cũ** ở `/tasks`. Màn thu tiền đang dùng (`QuayThuNgan`) vốn không có QR. Hai
màn còn đặt hai tên cho cùng một nút: "Đã thanh toán" và "Đã nhận đủ".

Ngày 18/09, `/tasks` và 5 component của nó đã gỡ:
`DoctorWorkBoard`, `CashierWorkBoard`, `ConfirmBoard`, `CskhActionBoard`,
`TasksRealtime`.

---

## D. Số đo giao diện (để đo tiến bộ)

| Hạng mục | 18/09 trước lượt 2 | Sau lượt 2 |
|---|---|---|
| Mục thanh bên (`NAV`) | 53 | 46 |
| `[..px]` tự chế (ratchet `px-tu-che`) | 85 | 64 → 61 (Nhà thuốc CP4, 19/09) |
| `<button>` viết tay | 337 / 97 file | chưa đo lại |
| Dùng `<Button>` / `buttonClass()` chung | 6 | chưa đo lại |
| `window.confirm` | 5 | chưa đo lại |
