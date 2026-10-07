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
Trong hồ sơ khám: **một ô "Khách đã đặt: <dịch vụ>"** — chỉ định đã sinh sẵn (không phải
kê lại), bấm mở phiếu thực hiện / kết quả của dịch vụ đó **nếu muốn** (tuỳ chọn, không
bắt buộc, không gắn vào mẫu phiếu khám chung). Bác sĩ làm luôn tại bàn khám được.

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

**T6 — Khối 4 "Điều trị"** (dưới khối "Chỉ định điều trị"; `lib/phieu-kham.ts:807`
`KHOI_PHIEU` + kiểu `1|2|3` rải ở `PhieuKham.tsx` :184 :312 :359 :526-544): 2 ô chữ tự
do "Cảm nhận", "Vấn đề sau điều trị". **Bảng riêng theo lượt**, không nhét vào 7 mẫu
JSON; tự lưu (mẫu `OTuVanTuLuu.tsx`); mỗi lần lưu thêm một phiên bản (không đè), hiện bản
mới nhất. Dùng được cả lượt không có phiếu (Điều trị, Khác). In kèm phiếu khi có nội dung.

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

## Tách PR (mỗi PR ≲400 dòng không tính test/migration/tệp sinh)

| PR | Nội dung |
|---|---|
| 2a | Nhóm + 6 loại Điều trị + "Khác" (migration) · component chọn 4 nhóm thay 4 chỗ · notes gửi đủ + lễ tân thấy |
| 2b | Đổi dịch vụ trong hồ sơ (quyền, mở khoá, giữ phiếu cũ, lịch sử) · lượt Điều trị: consumer sinh chỉ định, hàng BS tuỳ chọn, ô "Khách đã đặt" |
| 2c | Khối 4 "Điều trị" (migration bảng mới) |
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
