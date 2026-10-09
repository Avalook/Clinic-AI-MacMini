# Kế hoạch: Chọn dịch vụ 4 nhóm + Hồ sơ khám (Tuyền chốt 07/10/2026)

Nhánh `claude/chon-dich-vu-ho-so-kham` (từ `origin/main`), migration dải
`20261007600000`–`20261007699999`, cổng API/web 8252/3252. Chạy song song với nhánh
nhận-tại-phòng (`claude/service-room-assignment-flow-d71f40`, plan
`docs/KE-HOACH-NHAN-TAI-PHONG.md`) — nhánh đó merge trước.

Nguyên tắc chung: **không khoá cứng** (mọi thứ là gợi ý / tuỳ chọn, không chặn lưu,
không chặn check-in/check-out); **không cái gì sau đè cái trước** (lịch sử ở sự kiện
hoặc bản ghi thêm, không UPDATE mất dấu); **làm mới không mất cũ** (dữ liệu cũ hiện đủ).

## Luật đã chốt

**T0 — Bộ chọn dịch vụ 4 nhóm, MỘT component dùng chung** thay 4 chỗ tự viết:
`patients/new/NewPatientForm.tsx` (:1438, :1599 — đang dò dịch vụ theo TÊN, bỏ),
`patients/AppointmentBooking.tsx` (:352-381, dùng ở customers/AppointmentEditModal +
DatLichModal), `appointments/BookingHub.tsx` (:1316), `_lam-viec/ThaoTacLichTaiCho.tsx`
`DoiDichVuKhamTaiCho` (:312). Danh sách + nhóm do backend trả (một endpoint thay hai nguồn
`catalog/service-types` và `hub-dat-lich`); không luật nhóm trong TSX.
- **Khám**: 7 loại hiện có.
- **Điều trị**: Tập máy Bio điều trị (chưa gồm đầu dò) · Ghế điện từ trường · Laser trẻ hoá
  tiền đình · Laser trẻ hoá tiền đình và âm đạo · Laser điều trị bệnh lý 1 thành · 2 thành
  (mã/giá: migration `20261002100000_danh_muc_dich_vu_chuan_0110.sql`).
- **Thuốc**: ẩn hẳn (T4).
- **Khác**: ô ghi chú.
Cần: cột nhóm trên `service_type`; 6 dòng `service_type` Điều trị (không `form_code`,
trỏ đúng dòng `service_price`) + 1 dòng "Khác". Bẫy migration loại khám: memory
`nam-dich-vu-kham-va-tang` (UPDATE về trạng thái, không chỉ INSERT DO NOTHING; seed/
20260807000007/20260917000006 chạy lại).

**T1 — Lịch Điều trị khi check-in:** tự sinh chỉ định đúng dịch vụ đã đặt (bằng
**consumer mới**, không sửa `hanh_trinh.py`). Khách hiện ở **cả hai nơi**: "Sắp đến" của
phòng làm được (nhánh nhận-tại-phòng lo) và hàng chờ bác sĩ chính (nhãn "Điều trị — đi
thẳng phòng được"). Bên nào nhận trước thì khách ở đó. Hàng bác sĩ của lượt Điều trị là
**tuỳ chọn** — không ai nhận cũng không chặn check-out. Không tự thu phí khám (bác sĩ có
khám thật thì tick dịch vụ khám con như cũ).
Trong hồ sơ khám: chỉ định đã sinh sẵn (không phải kê lại) hiện ở **khối 4 "Điều trị"**
với nhãn "Khách đã đặt" (Tuyền 07/10 chiều: gộp ô "Khách đã đặt" vào khối 4 — xem T6).
Bác sĩ kê lại đúng dịch vụ ấy → **không đẻ chỉ định thứ hai** (`chi_dinh_service`
trả chỉ định đang có, `da_co_san`) — quầy thu một dòng. Đường kiểm trùng cũ
`/visits/[id]/service-orders/duplicates` đã TẮT (410) từ 24/09 nên chặn ở máy chủ, chỉ
cho dịch vụ nhóm Điều trị (CLS / thủ thuật vẫn kê lần 2 được như cũ).

**T2 — Giá** Điều trị = đúng dòng bảng giá của dịch vụ, không giá riêng ở loại khám, không
thu hai lần.

**T3 — "Khác" mở hoàn toàn:** không bắt chọn dịch vụ (kể cả dịch vụ phòng khám chưa có, hay
chỉ gặp bác sĩ). Ghi chú **khuyến khích, không bắt buộc** (gợi ý "nên ghi", không chặn
lưu). Ghi chú dùng `appointment.notes` (đã có); sửa: NewPatientForm + AppointmentBooking
chưa gửi notes; lễ tân chưa thấy notes ở `/reception/queue`, `/home` → hiện. Lượt "Khác"
đi như khám thường, hồ sơ bản tối giản (ô ghi chú tự do + kê chỉ định CLS/điều trị được);
đổi sang loại khám thật lúc nào cũng được (T5). Lượt/ghi chú "Khác" đếm được (cho QL/AI).

**T4 — Nhóm Thuốc:** ẩn hẳn, không làm trước.

**T5 — Đổi dịch vụ khám trong hồ sơ:** BS, ĐD, thư ký, trưởng ca, quản lý (theo lego —
`permissions/y_khoa.py` QUYEN_Y_KHOA + trưởng ca/QL). Mở khoá `ly_do_khong_doi`
(`services/doi_dich_vu_kham.py:55-91`) cho đường trong hồ sơ: đã có phiếu, đã thu tiền
khám, đã tick dịch vụ khám con đều đổi được. Chênh lệch tiền theo luật tiền thừa / nợ đã
chốt 06/10. Dịch vụ con đã tick giữ nguyên. Cập nhật cả `appointment.service_type_id` và
`visit.service_type_id` (`booking_service.py:1291` `doi_dich_vu_kham`).
Phiếu: 7 mẫu không có ô chung → **giữ nguyên phiếu cũ** (dòng `phieu_kham_luot` cũ),
mở phiếu mẫu mới; hồ sơ hiện "Phiếu cũ: <mẫu> — đã nhập N ô [xem]"; đổi ngược về đúng
phiếu cũ đủ dữ liệu. `phieu_kham_service.doc_luot` (:226) phải chọn phiếu theo dịch vụ
HIỆN TẠI (hiện chọn dòng sửa gần nhất). Lịch sử đổi: tái dùng
`appointment.service_switched` (ai, lúc, từ → sang) và **hiện ngay trên hồ sơ**.

**T6 — Khối 4 "Điều trị" (Tuyền đổi 07/10 chiều — thay bản "bảng riêng theo lượt")**
(dưới khối "Chỉ định điều trị"; `lib/phieu-kham.ts` `KHOI_PHIEU`):
- **Phiếu điều trị = phiếu KẾT QUẢ theo CHỈ ĐỊNH**, dùng bộ mẫu KQ có sẵn: mẫu
  `PHIEU_DIEU_TRI` (2 ô chữ tự do "Cảm nhận", "Vấn đề sau điều trị") gắn ở
  `dich_vu_mau_ket_qua` cho dịch vụ của 6 loại nhóm DIEU_TRI (khớp qua
  `service_type.service_price_id`, migration `20261007620000`); một `form_instance`
  mỗi chỉ định. Hiệu lực MỌI LÚC chỉ định ấy tồn tại (bác sĩ kê ở khối 3 hay lượt đặt lịch
  Điều trị tự sinh) — không phụ thuộc loại khám của lượt.
- Khối 4 = danh sách chỉ định điều trị của lượt, mỗi chỉ định một thẻ: phiếu 2 ô (CHÍNH
  form_instance đó — tự lưu, revision chống ghi đè như phiếu KQ) + trạng thái (chưa làm /
  đang làm ở P. X / đang làm tại bàn khám / xong). Phòng dịch vụ mở CÙNG phiếu (khung kết
  quả hiện có) — bàn khám ghi dở thì phòng ghi tiếp, không điền lại. Lượt không có chỉ
  định điều trị: "Chưa có chỉ định điều trị — kê ở khối Chỉ định điều trị".
- **Bỏ** bảng ghi chung theo lượt `luot_dieu_tri_ghi` (migration `20261007610000` gỡ khỏi
  nhánh — chưa lên prod).
- **Làm tại bàn khám:** [Làm tại bàn khám] → [Xong] (2 cú, giờ thật), hoàn tác từng bước.
  Lệnh riêng của module Thực hiện (`*_tai_ban_kham`, không đổi đường phòng / quầy): không
  đụng chỗ 'serving' của phiên bác sĩ (`uq_queue_entry_one_serving`); lần làm ghi
  `noi_lam = BAN_KHAM` + phòng bác sĩ (sự kiện `service.*` mang `noi_lam`) để màn phòng
  đọc. Chỉ định CHƯA có phòng → xếp vào phòng bàn khám (cột cũ `exec_status`
  in_progress/performed bắt buộc có phòng, công nợ check-out còn đọc cột cũ); hoàn tác
  Bắt đầu gỡ đúng phòng ấy. Quyền = khối y khoa + trưởng ca (như đổi dịch vụ trong hồ sơ).
  Điền phiếu KHÔNG tự tính là đã làm.
- **Lịch sử sửa mọi phiếu kết quả** (không đè): bảng chỉ-thêm `form_instance_lich_su` +
  trigger BEFORE UPDATE ghi bản cũ khi `du_lieu` / `trang_thai` đổi.

**T9 — Thanh toán dịch vụ điều trị (Tuyền dặn 07/10)** — mọi điểm có test DB
(`test_dieu_tri_ban_kham_db.py`):
- [Làm tại bàn khám] qua ĐÚNG cổng tiền của phòng (`finance_gate.can_start` / `cua_lam`,
  dây `thu_truoc_khi_lam`): chưa thu + chưa tick → chặn "Chưa thu tiền — thu trước hoặc
  tick Làm trước – thu sau."; đã thu hoặc đã tick → làm được (chỉ định khách chưa chốt
  thì chốt như lúc tick).
- Chỉ định điều trị (tự sinh / bác sĩ kê) hiện ở quầy đúng giá dòng `service_price`, thu
  đúng một lần; lượt Điều trị không phí khám; kê lại không thành hai dòng.
- Làm tại bàn khám chưa thu → check-out chặn nợ y như dịch vụ làm ở phòng.
- Hoàn tác Bắt đầu / Xong không đụng tiền. Bỏ chỉ định đã thu → tiền thừa. Hoàn tác bỏ
  sau khi đã hoàn tiền → nợ mới: luật E5 của Khối 2 (#342/#343, `test_tien_thua_phan_e_db`)
  — chỉ định điều trị là `service_order` thường nên đi đúng luật ấy khi đợt Khối 2 merge.
- Báo cáo cuối ngày / doanh thu theo dịch vụ đọc `payment_bill_line` — dòng của dịch vụ
  điều trị làm tại bàn khám mang đúng tên + tiền như làm ở phòng.

**T7 — "Lịch sử khám":** nút phía trên bộ 4 khối → popup: tìm theo ngày / loại dịch vụ, nút
lịch cạnh ô tìm chấm xanh những ngày khách có khám; bấm một lượt mở hồ sơ lượt đó chỉ
đọc. Endpoint mới liệt kê MỌI lượt (kể cả không phiếu, lượt Notion) — `lich_su_kham`
hiện chỉ trả lượt có phiếu, tối đa 20. Một component dùng chung ở Bàn khám,
`/patient-list`, `/customers` (`ThanhLuotKham`/`HoSoKham`). Chip "Lần n" (`LuotKhamTruoc`)
ở Bàn khám **giữ lại**.

**T8 — `/patient-list`:** bỏ khung "Phiếu khám bệnh" cũ (`tasks/ClinicalRecordForm.tsx`
:995 trong `PatientListView` :770-790) thay bằng hồ sơ khám kiểu Bàn khám; "Các lượt khám
(N)" (:709-745, `li` không onClick) bấm là mở lượt đó trong trang (thêm `visit_id` vào
`danh_sach_benh_nhan_service._LUOT_SQL` :194, `patient-list/page.tsx`, `VisitSummary`).
**Chỉ đổi hiển thị, không đụng dữ liệu.** Popup chọn khung đọc theo loại dữ liệu: phiếu
v5 → hồ sơ mới; phiếu đời cũ / lượt Notion → khung đọc cũ (giữ code, không xoá
`ClinicalRecordForm` — BanKham còn dùng). Test đủ 4 loại lượt (v5, cũ, Notion, không
phiếu) hiện đủ ô như khung cũ.

## Sửa sau bấm thử staging (Tuyền 07/10 tối — lượt 016a401c, Ghế điện từ trường)

**Gốc lỗi "đã check-out vẫn ở Kết quả cần đọc"** (đọc DB staging): BS Khám xong 14:09
khi Ghế chưa làm → vòng đọc 2 chờ Ghế; lễ tân check-out 15:32 (vượt bằng lý do);
15:37 Ghế được làm tại bàn khám → `vong_doc_luot_kham` chỉ chặn theo `visit.status`
(check-out giữ IN_PROGRESS) nên mở vòng → chỗ chờ REVIEW mới → "Kết quả cần đọc".

**Luật luồng (chốt lại):**
- Lượt Điều trị KHÔNG qua bàn khám (phiên BS chưa bắt đầu): mở hoàn toàn — phòng làm →
  thu → check-out, không vướng, không vòng đọc; vẫn hiện ở hàng bàn khám (tuỳ chọn).
- ĐÃ qua bàn khám: đúng luật bàn khám như lượt khám thường (không nới check-out). Ngoại
  lệ duy nhất: dịch vụ làm NGAY TẠI BÀN KHÁM (`noi_lam = BAN_KHAM`) đã xong thì không
  cần đọc kết quả của chính nó (`luot_kham_rules.vong_khong_can_doc` → `review.skipped`
  lý do `lam_tai_ban_kham`); dịch vụ làm ở phòng vẫn giữ vòng.
- Check-out xong: `vong_doc` không chạy lại vòng đọc (`visit.closed_at`); thẻ điều trị
  chỉ đọc + lệnh làm tại bàn khám bị từ chối ("Mở lại lượt" để làm tiếp).

**Phiếu điều trị (C):** MỘT component `_lam-viec/PhieuDieuTri.tsx` ở khối 4 Bàn khám và
khung kết quả phòng dịch vụ (`PhieuKetQua` chuyển sang khi mẫu PHIEU_DIEU_TRI; không sửa
`phong/**`). Mỗi ô một nhãn, "Tự lưu khi gõ", chân "Bản n · người sửa · giờ", In phiếu;
không "Hoàn tất phiếu". Ở phòng có [Xong] (đóng dịch vụ bằng lệnh hoàn tất của engine).
Engine: mẫu không có bước Hoàn tất (`phieu_kham/mau_dieu_tri.py`) lưu được cả khi đã
chốt, in không ghi BẢN NHÁP, khối kết quả trả nội dung khi còn nháp.

**Lượt "Khác" (D):** ô chữ to tự do, bảng chỉ-thêm `luot_ghi_chu` (migration
`20261007640000`, mỗi lần lưu một phiên bản, 409 khi màn cầm bản cũ; RLS 103 → 104).
Không tái dùng `consultation_note` (phiên PRIMARY bị liệt kê hết mọi bản ở mục A).

**In gộp một lượt (E):** `/print/phieu-kham/{visit}` — Khám · Đơn thuốc · Dịch vụ/CLS ·
Điều trị (tên + ô đã ghi của phiếu điều trị) · Ghi chú; mục trống ẩn; nhóm theo dữ
liệu (`dieu_tri` từ máy chủ); chữ ký bác sĩ cuối cùng.

## Tách PR (mỗi PR ≲400 dòng không tính test/migration/tệp sinh)

| PR | Nội dung |
|---|---|
| 2a | Nhóm + 6 loại Điều trị + "Khác" (migration) · component chọn 4 nhóm thay 4 chỗ · notes gửi đủ + lễ tân thấy |
| 2b | Đổi dịch vụ trong hồ sơ (quyền, mở khoá, giữ phiếu cũ, lịch sử) · lượt Điều trị: consumer sinh chỉ định, hàng BS tuỳ chọn · mẫu PHIEU_DIEU_TRI + làm tại bàn khám (backend) + thanh toán T9 |
| 2c | Khối 4 "Điều trị" = thẻ chỉ định điều trị (gộp "Khách đã đặt") · gỡ `luot_dieu_tri_ghi` · lịch sử sửa phiếu kết quả `form_instance_lich_su` |
| 2d | Popup Lịch sử khám + `/patient-list` + `/customers` |

## Ranh giới với nhánh nhận-tại-phòng

- KHÔNG đụng: `service_routing_service.py`, `service_execution_service.py`,
  `events/consumers/hanh_trinh.py`, `luot_kham_doc.hang_cho`/`phong_hom_nay`,
  `luot_kham_service.start_consultation`, `phong/**`, `_lam-viec/DoiPhong.tsx`, khối phòng
  quầy thu.
- `BanKham.tsx`: chỉ khu hồ sơ (~807, ~1170, ~1222-1285). Nhãn "Điều trị — đi thẳng phòng
  được" ở dòng hàng chờ nằm khu của nhánh kia → làm SAU khi nhánh kia merge (đồng bộ main
  trước), hoặc trả về từ backend một trường và chỉ thêm một dòng hiển thị.
- `catalogue.py`, `audit_labels.py`, `dong_thoi_gian.py`, `modules.py`,
  `app/api/luot-kham/route.ts`: chỉ THÊM dòng.
- Merge sau nhánh kia: đồng bộ main, chạy lại `scripts/ban-do-code.py`.

## Kiểm

pytest trên `chung_test_db`; test cần sửa/chạy lại: xem báo cáo dò (unit/test_doi_dich_vu_kham,
services/test_doi_dich_vu_kham_db — đang khẳng định chặn khi có phiếu, phải đổi;
test_phieu_kham_luot_db, test_phieu_kham_db, unit/test_phieu_kham_v2, test_danh_sach_benh_nhan_*,
unit/test_ho_so_kham, test_xem_luot_db, api/test_catalog_endpoints,
migrations/test_sql_columns_exist, test_danh_muc_*); boundary frontend theo
`grep -l <file> src/dashboard/tests`; thêm boundary cho component chọn dịch vụ và popup.
Diễn tập migration → ROLLBACK. CI một lần mỗi PR (`ci-may.sh --bao-github`). Tuyền bấm
trên staging.

Ước: ~6–7h AI, ~15–20M token.
