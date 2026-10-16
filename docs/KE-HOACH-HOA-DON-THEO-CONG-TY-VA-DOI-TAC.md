# Kế hoạch: tick "Xuất hoá đơn theo công ty" ở bước thu + bật lại Đối tác (16/10/2026)

Mức 3 (tiền, migration, hạ tầng dữ liệu) — **chờ Tuyền duyệt, chưa có dòng code sản phẩm nào**.
Khảo sát bằng property test: `src/tests/unit/test_hd_cong_ty_thuoc_tinh.py` (chưa commit).

## 0. Nền tảng

G5c (hoá đơn công ty) **đã có trên `origin/gop-staging-1410m`** (chưa lên prod): bảng `khach_cong_ty`,
`hoa_don_cong_ty` (bản chụp theo `payment_cycle`, có `bo_luc` để hoàn tác), màn công ty ở `/hoa-don`,
cột công ty trong Excel. `main`/prod chưa có gì → **làm trên nền 1410m**, PR đợi 1410m vào `main`.
Migration mới phải > `20261016400000` (soát `origin/dot/*` trước khi chọn số).

## 1. Điều property test cho thấy (nền 1410m)

| Luật (Tuyền) | Kết quả | Gốc |
|---|---|---|
| L1 Không tick → cột C "Tên khách hàng" **trống** | **SAI** (đang in tên khách) | `xlsx_misa` cột 3 = `ten_khach` |
| L2 Tick → C=tên cty, D=địa chỉ cty, E=MST, **F=tên khách thật**, G=email cty | **SAI ở F** (đang để trống theo Q19 của G5c) | `dung_hoa_don`: `nguoi_mua = ct.nguoi_mua` |
| L3 Tick không đổi tiền (số HĐ, dòng, tổng) | đúng | — |
| L4 Thông tin chỉ ở dòng đầu, STT lặp mọi dòng | đúng | — |

"Sửa ở quản lý khách hàng không đồng bộ sang xuất hoá đơn": nguyên nhân là **`main`/prod**:
`PatientUpdateDTO` chỉ nhận 8 trường, `address`… bị Pydantic bỏ im lặng nhưng UI báo "Đã lưu";
email nằm ở bảng khác (`patient_contact_channel`) mà không code nào ghi. **1410m đã vá**
(DTO đủ trường + cột `patient.email`) → đi theo 1410m, không cần vá riêng. Việc còn lại: thêm test
đồng bộ (mục 5).

## 2. Việc A — tick ở bước thu

- **Lưu cờ**: dùng lại `hoa_don_cong_ty` (không thêm cột vào `payment_cycle`, tránh viết lại
  `payment_cycle_guard`). Tick = tạo bản chụp công ty cho phiếu thu **cùng giao dịch** với
  `record_payment`; bỏ tick/hoàn tác = `bo_hoa_don` có sẵn (đáp "mọi thao tác hoàn tác được").
- **Giao diện** (mỗi khối thu có tick riêng vì dịch vụ và thuốc là 2 `payment_cycle`): `HoaDonMot.tsx`
  + `NhomThu` ở `QuayThuNgan.tsx` + `pharmacy/BanLeThu.tsx`; nhãn "Xuất hoá đơn theo công ty",
  chỉ hiện khi khách có công ty trong hồ sơ; có >1 công ty thì chọn.
- **Đường gửi**: `api/payment/route.ts` → `routers/payment.py` (`PaymentRecordRequest`) →
  `payment_service.record_payment`. Mẫu bắt chước: giảm giá 13/10.
- **Bẫy phải xử lý**: (1) gửi lại cùng `bill_revision` thì `_ghi_lan_thu_dich_vu` trả lần chờ cũ, bỏ qua
  cờ mới → cờ phải nằm trong khoá idempotent (`dinhDanhThaoTac`); (2) hoá đơn 0đ không tạo
  `payment_cycle` nên không gắn được cờ; (3) khách bấm tick xong sửa công ty ở hồ sơ → bản chụp giữ
  nguyên (đúng thiết kế snapshot, nói rõ trên UI).
- **Excel**: giữ `ten_khach` làm tên nội bộ (dấu vân tay "đã xuất MISA" dựa vào nó — đổi là mọi HĐ
  đã đánh dấu báo "thay đổi sau xuất"); chỉ đổi cái GHI RA ô: C = tên cty nếu tick, **trống** nếu không;
  F = tên khách thật cả hai trường hợp. Sửa màn xem trước `/xuat-hoa-don` theo cùng hàm.

## 3. Việc B — bật lại Đối tác

Hiện trạng (agent đọc code): tắt 01/10 bằng **script SQL ngoài git**
(`ClinicAI-Backups/bo-doi-tac-lam-0110.sql`: `node_definition.lam_ben_ngoai=false` ở 5 node,
`service_price.doi_tac_lay_mau=false` ở 3 dịch vụ). Màn `/doi-tac`, sổ `doi_tac_thanh_toan` (ghi nhận
đã thu, huỷ kèm lý do, lịch sử) **đã có**.

- **Tiền**: Excel GTGT, hoá đơn, báo cáo cuối ngày/ca **đã loại dòng `billing_owner='EXTERNAL_PARTNER'`**
  (`_DONG_SQL` lọc `CLINIC`). Nhưng tiền bám **theo `billing_owner` của dịch vụ**, KHÔNG theo
  phòng. Dịch vụ chỉ định về phòng đối tác mà `billing_owner=CLINIC` vẫn vào doanh thu/Excel. Đây là
  rủi ro thật nhất — xem câu hỏi Q3.
- **Bật lại**: UPDATE ngược 2 cờ (dữ liệu, không migration), do Tuyền chạy sau khi xem bảng SELECT.
  Cẩn thận: nếu cờ node tắt, đổi "phòng làm" ở Bảng giá sẽ lật dịch vụ chưa chọn tay về CLINIC.
- **Tài khoản đối tác**: vai `PARTNER` có sẵn (chỉ thấy `/doi-tac`) nhưng **màn Nhân sự không tạo được**
  (`PrimaryDepartment`, `DEPARTMENTS` thiếu `PARTNER`). Thêm PARTNER vào 2 chỗ này (không migration).
  Đụng `claude/vai-ke-toan` (cùng file) → rebase.
- **"Toggle chọn đối tác"**: hệ thống KHÔNG có thực thể đối tác (không bảng, không `doi_tac_id`). Bản
  đơn giản (một đối tác) = không cột mới. Nhiều đối tác thật = bảng + `doi_tac_id` + gắn tài khoản
  (migration, lượt sau).
- Giữ nguyên: nút đối tác chỉ ghi sự kiện, không khoá hành trình khách (memory 28/09).

## 4. Câu cần Tuyền chốt (nghiệp vụ)

1. **Email khi tick mà công ty không có email**: để trống, hay lấy email cá nhân khách?
   (G5c hiện: trống, không lộ dữ liệu cá nhân.)
2. **SĐT / CCCD khi tick**: G5c để trống. Giữ?
3. **"Đối tác làm ⇒ không tính tiền"**: dùng quy tắc nào? (a) giữ `billing_owner` theo từng dịch vụ,
   Tuyền đặt "Thu hộ đối tác" cho đúng các dịch vụ (dữ liệu, không code); hoặc (b) code: dịch vụ được
   chỉ định vào phòng `la_doi_tac` thì luôn EXTERNAL. 29/09 Tuyền chốt nước tiểu (SP000025) và soi CTC
   (SP000076) **phòng khám thu**; (b) sẽ mâu thuẫn với chốt này nếu chúng đi qua node đối tác.
4. **Ai được tick ở quầy**: G5c giới hạn *ghi* công ty cho Kế toán + Quản lý. Thu ngân chỉ **chọn công ty
   đã có trong hồ sơ** khi thu — cho phép (khuyến nghị) hay chỉ Kế toán?
5. **G5c trước hay song song**: 1410m còn chờ "lên prod" (và lỗ hổng đơn vị lô thuốc). Làm trên nền 1410m,
   đợi nó vào main (khuyến nghị) hay đẩy một đợt riêng sau?

## 5. Test sẽ viết TRƯỚC code (verifier trước)

- Property (đã có, 4 luật) → chuyển thành `dung_hoa_don` tests bắt buộc xanh sau sửa; thêm: email cty
  trống + email cá nhân có → không lộ (nếu Q1 = trống); dấu vân tay không đổi khi chỉ đổi cách in cột C.
- DB property (random trộn dòng CLINIC/EXTERNAL, tick/không tick, thu thuốc/dịch vụ, hoàn một phần):
  tổng Excel = tổng dòng CLINIC; `payment_cycle.amount` không chứa EXTERNAL; tick không đổi tiền;
  bỏ tick trả Excel về dạng cá nhân; gửi lại cùng khoá không nuốt cờ.
- DB đồng bộ: PATCH hồ sơ (địa chỉ, email, CCCD, công ty) → `/xuat-hoa-don` đọc đúng giá trị mới
  (hiện chưa có test nào cho cả chuỗi này).
- Test loại EXTERNAL khỏi Excel (hiện **chưa có test nào**).

## 6. ĐÃ LÀM (16/10, nhánh `claude/invoice-by-company-8a73f2`, nền `gop-staging-1410m`, chưa commit)

Tuyền chốt: tick ở khâu thanh toán, hiện thông tin công ty, **theo lượt khám** (không theo hồ sơ).
Mặc định đã chọn cho Q1–Q5 (sai thì nói): email công ty trống thì để trống · SĐT/CCCD trống khi tick (**ĐÃ ĐỔI 16/10 chiều: Tuyền chốt H = SĐT khách, email công ty trống → email cá nhân, CCCD vẫn trống**) ·
thu ngân được CHỌN công ty có sẵn trong hồ sơ (ghi/sửa công ty vẫn Kế toán + Quản lý) · làm trên nền 1410m.

| Việc | Ở đâu |
|---|---|
| Excel: C "Tên khách hàng" trống nếu không tick; F = khách thật luôn | `xuat_hoa_don_service.py` (`dung_hoa_don`, `xlsx_misa`) |
| Tick theo lượt: chép công ty hồ sơ → bản chụp của phiếu vừa thu | `HoaDonCongTyService.gan_khi_thu`, router `payment.py` (`cong_ty_id`) |
| Bảng quầy thu báo danh sách công ty của khách | `cashier_board_service.py` (`item.cong_ty`) |
| Ô tick + hiện công ty (tên, MST, địa chỉ, email) ở quầy dịch vụ, thuốc | `CongTyKhiThu.tsx`, `HoaDonMot.tsx`, `QuayThuNgan.tsx`, `api/payment/route.ts` |
| Tài khoản đối tác: vai `PARTNER` ở màn Nhân sự | `schemas/staff.py`, `NhanSuBoard.tsx` |
| Bật lại đối tác + kiểm tiền lệch (Tuyền chạy) | `scripts/bat-lai-doi-tac-1610.sql`, `scripts/kiem-doi-tac-1610.sql` |

**Không đổi:** nút bán lẻ thuốc `pharmacy/BanLeThu.tsx` (khách vãng lai) chưa có ô tick.
**Tiền đối tác:** 14 tổ hợp (mọi tập con chỉ định × tiền mặt/chuyển khoản) — phiếu thu, Excel, danh sách
hoá đơn, báo cáo cuối ngày đều KHÔNG cộng dịch vụ đối tác. Nếu staging/prod vẫn thấy lọt, nguyên nhân là
DỮ LIỆU (bên thu của dịch vụ lúc thu, hoặc dịch vụ vào phòng đối tác nhưng bên thu CLINIC) → chạy
`kiem-doi-tac-1610.sql`.

## 7. Kịch bản bấm thử (staging, Tuyền)

1. Hồ sơ khách (Kế toán/Quản lý) → thêm công ty (tên, MST, địa chỉ, email).
2. Quầy thu dịch vụ của khách đó → thấy ô "Xuất hoá đơn về công ty"; tick → hiện đúng 4 thông tin; Tạo bill.
3. Cùng khách, lượt khác KHÔNG tick → Tạo bill. Khách chưa có công ty → ô tick xám + câu nhắc.
4. /xuat-hoa-don hôm nay → tải Excel: lượt tick có C=tên cty, D=địa chỉ cty, E=MST, F=tên khách, G=email cty;
   lượt không tick C TRỐNG, F=tên khách, D/G/H/I cá nhân. Lượt tick: H = SĐT khách, G = email cty (trống → email cá nhân), I trống.
5. /hoa-don → bỏ chọn công ty của lượt đã tick → Excel quay về dạng cá nhân (hoàn tác được).
6. Nhân sự → Thêm nhân viên → vai "Đối tác" → đăng nhập: chỉ thấy /doi-tac.
