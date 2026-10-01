# Bàn giao: claude/hoan-tac-moi-thao-tac — HOÀN TÁC ở mọi thao tác (01/10/2026)

**Mục tiêu (Tuyền, sau thực nghiệm 30/09):** mọi thao tác bấm nhầm đều có nút Hoàn tác; hoàn tác cập nhật MỌI nơi (quầy thu, hàng chờ, hành trình); không gì khoá hẳn. Ràng buộc thật (đã thu, khách đã về, KQ đã duyệt) → hỏi xác nhận + lý do, không chặn.

## ĐÃ LÀM (commit WIP a1333f89, ~65%)
- `S/hoan_tac_service.py` `HoanTacService`: `mo_lai_kham` (Khám xong/Hoàn tất/Xong tư vấn → phiên in_progress; bỏ vòng đọc vừa mở, follow-up vừa mở, phiên sau còn queued; mở lại mốc `exam_completed_at` + lịch COMPLETED→CHECKED_IN; khách đã check-out → mở lại lượt), `huy_chi_dinh` (chưa thu: huỷ, hoá đơn quầy tự bớt; đã thu: 409 `CAN_XAC_NHAN` rồi huỷ → tiền thừa), `hoan_tac_xong_dich_vu` (COMPLETED→IN_PROGRESS, lần làm cũ mở lại, khách về phòng), `mo_lai_luot` (hoàn tác check-out / về giữa chừng). Đọc tiền: `tien_da_thu_cua_chi_dinh`, `tien_thua_cua_luot`. Mỗi lệnh: quyền = quyền lệnh gốc, `domain_event` + `event_log`, bấm 2 lần = `already`.
- Router `R/hoan_tac.py` (đăng ký ở `main.py`): `POST /luot-kham/consultations/{id}/mo-lai`, `/orders/{id}/huy-chi-dinh`, `/orders/{id}/execution/hoan-tac-xong`, `/visits/{id}/mo-lai-luot`; thân `{ly_do?, xac_nhan?}`.
- Sự kiện mới (`events/catalogue.py` + `dong_thoi_gian.py` + `modules.py`): `consultation.reopened`, `service_order.cancelled`, `service.completion_undone`, `visit.reopened` → dòng thời gian Hành trình khách. Nhãn `audit_labels.py`.
- `luot_kham_service.py`: phiên REVIEW đã huỷ được mở lại khi vòng đọc sẵn sàng lại; `chuyen_bac_si_chinh` bỏ qua nếu phiên tư vấn đang mở (tin H3 tới sau Hoàn tác).
- Quầy thu: `cashier_board_service.py` — lượt có tiền thừa vẫn hiện + `item.tien_thua` + vào `ds_cho_thu`; `QuayThuNgan.tsx` khối `TienThuaKhoi` (trỏ tab "Đã thanh toán hôm nay" để hoàn / huỷ phiếu).
- UI: `components/ui/NutHoanTac.tsx` (chữ + ↶, tự mở `HopXacNhan` có ô lý do khi máy chủ trả `can_xac_nhan`), `ThongBaoHoanTac.tsx` (toast 10s "Đã … · Hoàn tác", dừng đếm khi đang hỏi), `HopXacNhan` thêm `nhanDangChay`. Ống dẫn `_lam-viec/hoan-tac.ts` + whitelist proxy `app/api/luot-kham/route.ts`.
- Màn: Bàn khám/Bàn tư vấn (`BanKham.tsx`: dòng done → chip "Đã khám xong HH:MM · Hoàn tác" + toast sau Hoàn tất/Xong tư vấn); phiếu khám thẻ chỉ định (`KetQuaChiDinh.tsx` nút "Hoàn tác chỉ định", qua `PhieuKham`/`PhieuKhamLuot`); phòng dịch vụ (`PhongDichVu.tsx`: khối Đã làm + toast sau Xong); check-out (`NutCheckOut.tsx` sau khi đóng; `/reception/queue` dòng "Đã về" có Hoàn tác — cờ máy chủ `mo_lai_duoc` ở `tiep_don_service.py`, kiểu `lib/tiep-don.ts`).
- Test: `T/services/test_hoan_tac_moi_thao_tac_db.py` 11 bài XANH trên DB chung :55600; unit `test_o_cam_module`, `test_danh_muc_su_kien`, audit drift xanh; `tsc`, `eslint`, `test:boundary` xanh; `ban-do-code.py --kiem` khớp.

## ĐỢT 2 (01/10 chiều) — đã làm
- (e) Huỷ xếp phòng: nút `NutHoanTac` "Huỷ xếp phòng" trong `_lam-viec/DoiPhong.tsx` (mọi lối: quầy thu `XepPhongDaThu`, Bàn khám, Xem lượt) → lệnh có sẵn `huy-xep-phong-v1` với mã lý do MỚI `ASSIGNED_BY_MISTAKE` (`INVALIDATE_REASONS`; "OTHER" bị từ chối vì đòi ghi chú).
- (h) Thu hồi duyệt kết quả: `HoanTacService.thu_hoi_duyet_ket_qua` + `POST /luot-kham/orders/{id}/thu-hoi-duyet` (thao tác `thu-hoi-ket-qua`), sự kiện `result.approval_revoked`. Bỏ `duyet_luc/duyet_boi`, mở lại việc theo dõi mà chính lần duyệt đóng (cùng `now()`); tệp đã gửi khách → hỏi xác nhận. Mốc `cho_phep_gui_luc` của tệp giữ (trigger cấm sửa, không còn là cửa gửi). Màn `/duyet-ket-qua`: toast "Đã duyệt … · Hoàn tác".
- (7) Toast sau chỉ định ở Bàn khám: "Đã chỉ định N dịch vụ — <khách> · Hoàn tác" (bỏ đúng `order_ids` máy chủ trả).
- Test DB: 14 bài xanh (thêm thu hồi duyệt ×2, huỷ xếp phòng).
- Bấm thật 1280 + 375: khám xong → Hoàn tác → Hoàn tất lại; chỉ định → toast Hoàn tác → quầy mất dòng → chỉ định khác hiện ngay; check-out → Hoàn tác ở dòng "Đã về"; huỷ xếp phòng ở quầy; duyệt → Hoàn tác.

## CÒN LẠI (đợt sau)
- (f) Sinh hiệu: chỉ "đo lại" (dòng mới thắng) — chưa xoá/sửa lần đo.
- Chưa có hoàn tác: huỷ lịch / không đến (booking CANCELLED/NO_SHOW), "Không làm" dịch vụ, quyết yêu cầu (miễn/theo dõi), đối tác đã lấy mẫu, chốt dòng thuốc, ký siêu âm (`clinical_sign`).
- `/reception/checkout` (CheckoutBoard) đóng lượt bằng code riêng — hoàn tác ở `/reception/queue` dòng "Đã về".
- `/reception/queue` cập nhật chậm 5–10 s sau Check-out VÀ sau Hoàn tác (có từ trước — `router.refresh()` không vẽ lại, đợi vòng làm tươi kế; máy chủ đã đúng ngay). Cần soát riêng.

## Quyết định đã chốt + lý do
- Bỏ chỉ định ĐANG LÀM / ĐÃ XONG → báo "Huỷ bắt đầu nhầm / Hoàn tác Xong ở phòng trước" (thứ tự, không khoá; không xoá ngầm việc người khác đang làm).
- Đã thu → KHÔNG đụng phiếu thu (việc nhóm thu tiền); khoản thành tiền thừa (đã trừ khoản hoàn PENDING/COMPLETED), gồm cả dịch vụ `not_performed` đã thu.
- Mở lại khám: phiên sau đã có người nhận → báo hoàn tác phiên sau trước. Vòng đọc chưa ai đọc thì XOÁ (khám xong lại mở vòng mới, tránh trùng `uq_review_round`).
- Hoàn tác Xong dịch vụ không đụng phiếu/tệp kết quả; KQ đã duyệt/phiếu READY/bác sĩ đã đọc → hỏi xác nhận.
- Lý do ≥ 5 ký tự chỉ bắt khi máy chủ hỏi xác nhận.

## Bẫy đã gặp
- `test_o_cam_module`: sự kiện mới vào `dong_thoi_gian_luot` phải khai trong `nghe` của module `journey`.
- `thuc-hien-phieu-boundary`: PhongDichVu chỉ được MỘT chữ `"xong-v1"` → toast dựa `kq.data.execution_status`.
- `HopXacNhan` cứng chữ "Đang xoá…" → thêm prop.

## Migration
Không có (chỉ đổi code; ràng buộc DB hiện có cho phép mọi chuyển ngược).

## Kịch bản bấm thử staging
1. Bác sĩ kê đơn thiếu số lượng → Hoàn tất → ngay dòng "Đã khám xong · Hoàn tác" (hoặc toast) bấm Hoàn tác → khách về "đang khám" → sửa số lượng → Hoàn tất lại; quầy thuốc/quầy thu thấy khách về đang khám rồi khám xong lại.
2. Chỉ định nhầm Siêu âm (chưa thu) → thẻ chỉ định "Hoàn tác chỉ định" → quầy thu mất dòng SA ngay → chỉ định dịch vụ khác → quầy thu hiện dịch vụ mới.
3. Chỉ định SA → quầy thu thu tiền → bác sĩ "Hoàn tác chỉ định" → hộp xác nhận nói "đã thu … thành TIỀN THỪA" → ghi lý do → quầy thu hiện khối vàng "Tiền thừa 300.000đ".
4. Phòng SA bấm Xong nhầm → toast/khối Đã làm "Hoàn tác" → dịch vụ về đang làm, khách về phòng → Xong lại.
5. Lễ tân check-out nhầm → "Hoàn tác" ngay sau đó (hoặc ở dòng "Đã về" trên Tiếp đón) → khách về lại hàng chờ → check-out lại được.
6. Lịch sử Hành trình khách có dòng "Hoàn tác …" kèm người + lý do.
