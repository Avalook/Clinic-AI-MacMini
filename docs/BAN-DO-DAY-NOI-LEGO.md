# BẢN ĐỒ DÂY NỐI LEGO — để Tuyền duyệt TRƯỚC khi code

Bản nháp 23/09/2026. Mục đích: duyệt NGHĨA nghiệp vụ của từng dây nối trước khi
viết code (kỹ thuật *Event Storming*). Chuẩn mỗi khối: `docs/CHUAN-CAM-LEGO.md`.
Luồng chuẩn 11 bước: memory `luong-chuan-tuyen-2309.md`.

Ký hiệu hiện trạng: ✅ đã có ở sổ mới (`domain_event`) · 🟡 có nhưng chỉ ghi sổ cũ
hoặc gọi thẳng khối khác · ❌ chưa có · ◻︎ không cần event (cấu hình/CRUD có nhật ký,
đúng thesis: "cấu hình tĩnh dùng CRUD với audit log").

Cách đọc một dây: **Lệnh** (ai bấm) → khối ghi **state riêng** → phát **event** (sự
thật đã xảy ra) → **node nghe** làm việc của nó.

---

## A. Các khối và event mỗi khối phát

| # | Khối (module) | Lệnh — ai bấm | State riêng | Event phát ra | Hiện trạng |
|---|---|---|---|---|---|
| 1 | **Đặt lịch** | Đặt / Đổi / Huỷ lịch — CSKH, lễ tân | `appointment` (+ số booking) | `appointment.booked` · `appointment.rescheduled` · `appointment.cancelled` | 🟡 sổ cũ |
| 2 | **Lịch làm việc** | Xếp ca, Công bố tuần — quản lý | `work_roster`, `roster_week` | `roster.week_published` | 🟡 sổ cũ |
| 3 | **Tiếp đón** | Check-in / Hoàn tác — lễ tân | `visit` (mở lượt, số quầy) | `visit.checked_in` · `visit.check_in_undone` | ✅ / ❌ |
| 4 | **Sinh hiệu** | Bắt đầu đo / Lưu — điều dưỡng | `vital_measurement`, `encounter_flow.vitals_*` | `vitals.started` · `vitals.recorded` | ✅ |
| 5 | **Khám tư vấn** | Bắt đầu / Xong tư vấn — bác sĩ tư vấn | `consultation` (loại TU_VAN) | `consultation.started` · `consultation.handed_over` (xong tư vấn, chuyển bác sĩ chính) | ❌ chưa có khối |
| 6 | **Khám chính** | Bắt đầu khám / Khám xong — bác sĩ chính, thư ký | `consultation` (PRIMARY/REVIEW) | `consultation.started` · `consultation.completed` | 🟡 sổ cũ |
| 7 | **Bệnh án** | Lưu / Hoàn tất — bác sĩ, thư ký (sửa lúc nào cũng được) | `clinical_record` (có phiên bản) | `clinical_record.completed` (chỉ khi bấm Hoàn tất, không phải mỗi lần lưu — DE-03) | ❌ |
| 8 | **Chỉ định** | Xác nhận chỉ định — bác sĩ, thư ký, điều dưỡng | `service_order` | `service_order.placed` | ✅ |
| 9 | **Chọn dịch vụ** | Chốt dịch vụ khách thật làm — lễ tân | `service_selection_state` | `service_selection.confirmed` | 🟡 sổ cũ |
| 10 | **Thu tiền dịch vụ** | Thu / Xác minh chuyển khoản / Huỷ phiếu — lễ tân | `payment_cycle`, `payment_bill_line` | `payment.service_collected` · `payment.voided` | ❌ |
| 11 | **Điều phối phòng** | Xếp / Đổi phòng — ai có quyền điều phối | `service_order.room_id`, `queue_entry` | `service.routed` · `service.routing_invalidated` | ❌ / ✅ |
| 12 | **Thực hiện dịch vụ** | Bắt đầu / Xong / Không làm / Dừng / Làm lại — phòng | `service_execution_attempt` | `service.started` · `service.completed` · `service.not_performed` · `service.interrupted` · `service.retry_prepared` | ✅ |
| 13 | **Phiếu kết quả** | Điền / Hoàn tất / Sửa lại — phòng | `form_instance` | `result_form.completed` · `result.ready` · `result.corrected` | ✅ |
| 14 | **Tệp kết quả + đối tác** | Tải tệp / Xác nhận đúng người — điều dưỡng, đối tác | `tep_ket_qua` | `result_file.uploaded` · `result_file.confirmed` | ❌ |
| 15 | **Duyệt kết quả** | Bác sĩ xem/duyệt | `service_order.duyet_*` | `result.reviewed` | 🟡 sổ cũ |
| 16 | **Kê đơn** | Kê thuốc — bác sĩ (thư ký nháp) | `prescription` | `prescription.written` | ❌ |
| 17 | **Quầy thuốc** | Phát thuốc theo khách chọn (ít/thêm) + thu tiền thuốc — dược sĩ | `prescription` (số phát), `payment_cycle` | `medicine.dispensed` (kèm chênh lệch kê ↔ mua) · `payment.medicine_collected` | 🟡 |
| 18 | **Gửi khách (CSKH)** | Đánh dấu đã gửi kết quả — CSKH | `tep_ket_qua.gui_*`, `tuong_tac_cskh` | `result.sent_to_patient` | 🟡 |
| 19 | **Rời phòng khám** | Check-out — lễ tân | `visit.closed_*` | `visit.checked_out` | 🟡 sổ cũ |
| 20 | **Quyền** | Cấp / Thu khối quyền — quản lý | `capability_grant` | `capability.granted` · `capability.revoked` | ✅ |
| 21 | **Phòng, vị trí, dịch vụ** | Thêm/đổi tên/tắt — quản lý | `clinic_room`, `vi_tri_lam_viec`, `service_price` | — | ◻︎ CRUD + nhật ký |

## B. Các node nghe — dây nối

### B1. Khối HÀNH TRÌNH (Journey Process Manager) — giữ luật THỨ TỰ, chỉ gửi LỆNH

| Dây | Nghe | Điều kiện | Gửi lệnh (của khối khác) | Hiện trạng |
|---|---|---|---|---|
| H1 | `visit.checked_in` | dịch vụ khám có bước tư vấn | Xếp khách vào hàng **bác sĩ tư vấn** | ❌ |
| H2 | `visit.checked_in` | không có bước tư vấn | Xếp khách vào hàng **bác sĩ chính** | 🟡 gọi thẳng (F2) |
| H3 | `consultation.handed_over` | — | Xếp khách vào hàng bác sĩ chính | ❌ |
| H4 | `visit.checked_in` | lịch hẹn là THỦ THUẬT/dịch vụ (đặt từ lượt trước) | Tạo sẵn chỉ định theo lịch → chờ thu tiền | ❌ |
| H5 | `payment.service_collected` | chỉ định đã chọn, chưa có phòng | **Xếp phòng** (gợi ý vắng nhất, thay cho người vừa thu tiền) | ❌ ← mối thử đầu tiên |
| H6 | `service.completed` / `result.ready` | bác sĩ chính còn chờ đọc | Đưa khách vào hàng **đọc kết quả** của bác sĩ chính | 🟡 |
| H7 | `visit.checked_out` | còn kết quả chưa đọc / việc mở | Mở **theo dõi sau khám** (CSKH) | ❌ (thesis ContinuityRisk) |
| H8 | hẹn giờ: kết quả đối tác quá hạn chưa về | — | Mở việc CSKH gọi đối tác/khách | ❌ |

### B2. Các node khác

| Node | Nghe | Làm gì | Hiện trạng |
|---|---|---|---|
| **Dòng thời gian** (projection) | mọi event của một lượt | Ghi một dòng lên màn hành trình; dựng lại được bằng phát lại | ✅ (thiếu các event ❌ ở bảng A) |
| **Trách nhiệm không rơi** | `service.not_performed` (đã thu tiền) · `service.interrupted` · `service.routing_invalidated` | Mở việc đối soát tiền / quyết làm lại, có hạn | ✅ |
| **Thông báo (chuông)** | `result_file.uploaded` · `result.ready` · `appointment.booked` | Báo CSKH + bác sĩ của khách | 🟡 gọi thẳng |
| **Việc CSKH** | `result_file.confirmed` · `result.ready` · `appointment.cancelled` · `roster.week_published` | Sinh việc: gửi KQ, hỏi lý do huỷ, lịch vượt sức chứa | 🟡 đang là VIEW đọc bảng (`v_viec_cskh`) — giữ view được |
| **Nhắc tái khám** | `consultation.completed` có hẹn tái khám | Tạo lời nhắc | 🟡 |
| **Quầy thuốc** (projection) | `prescription.written` | Hiện đơn cần phát ở quầy | 🟡 đọc bảng |
| **Sức chứa** | `appointment.booked/rescheduled/cancelled` · `roster.week_published` | Đánh dấu khung vượt sức chứa | 🟡 trigger DB + view |

## C. Luật vẫn ĐỒNG BỘ (không qua event — luật an toàn trong cùng giao dịch)

Quyền (`doi_quyen`) · cổng tiền trước khi bắt đầu dịch vụ (FinanceGate) · chặn sức
chứa khi ĐÃ công bố lịch · số booking/số quầy (trigger DB) · khoá phiên bản chống ghi
đè (revision). Mỗi cái là luật của CHÍNH khối đó, không phải dây nối giữa khối.

## D. Cần Tuyền xác minh

1. **Bảng A:** tên + ý nghĩa từng event có đúng "sự thật đã xảy ra" không? Có sự thật
   nào phòng khám cần mà thiếu không?
2. **H1/H3 (bác sĩ tư vấn):** dịch vụ khám nào đi qua tư vấn? Hay mọi khách mặc định
   qua tư vấn trừ khi lễ tân/bác sĩ chính nhận thẳng?
3. **H4:** khách đặt lịch thủ thuật từ lượt trước — check-in xong có cần thu tiền trước
   khi vào phòng như chỉ định thường không?
4. **H5:** khối Hành trình xếp phòng **thay cho người vừa thu tiền** (dùng quyền của
   người ấy, không tự nâng quyền) — đúng ý không?
5. **Quầy thuốc:** thu tiền thuốc có cần bác sĩ bấm Khám xong trước không?
6. **Bệnh án:** event chỉ phát khi bấm Hoàn tất (không phát mỗi lần lưu) — đồng ý?

Duyệt xong bản đồ này thì code theo từng nhóm dây, mỗi nhóm nghiệm thu bằng khách giả.
