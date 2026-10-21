# BẢN ĐỒ THEO KHỐI — muốn sửa / thêm gì thì vào khối nào

> Sinh bởi `scripts/ban-do-code.py` lúc 2026-10-21 12:33. **Đừng sửa tay** —
> sửa bản khai `src/clinicai/modules.py` rồi chạy `python3 scripts/ban-do-code.py`;
> CI (`--kiem`) đỏ khi tệp này lệch code.

**Cách tra (3 bước):**

1. Biết **màn** đang thấy → mục 3 (tìm đường dẫn màn) ra các khối màn ấy chạm.
   Biết **dữ liệu / bảng** → mục 4 ra khối giữ bảng ấy.
2. Vào **khối** ở mục 2: tệp code, lệnh, sự kiện, quyền, màn, test.
3. Trước khi sửa, xem **khối nghe** sự kiện của nó và **nợ ghi chéo**: đó là
   những chỗ "sửa chỗ này dễ hỏng chỗ kia" — phải kiểm cùng.

Chi tiết từng màn (thành phần, API, router): `docs/BAN-DO-CODE.md`. Luật lego:
`src/clinicai/modules.py`. Luật canh ghi chéo + sổ nợ:
`src/tests/unit/test_luat_cam_ghi_cheo.py`. Màn và mọi lối vào: `docs/SITEMAP.md`.

## 1. Các khối (36)

Ghi chéo ra = tệp của khối này ghi bảng khối khác; vào = khối khác ghi bảng
của nó (sổ nợ, chỉ được ngắn đi).

| Khối | Việc | Bảng | Tệp | Màn | Ghi chéo ra / vào |
|---|---|---|---|---|---|
| `service_order` | Chỉ định dịch vụ | 5 | 6 | 22 | 5 / 12 |
| `vat_tu` | Bán thêm vật tư | 2 | 2 | 19 | 0 / 0 |
| `lieu_trinh` | Liệu trình điều trị nhiều buổi | 4 | 2 | 7 | 0 / 0 |
| `phi_kham` | Dịch vụ khám (tiền khám) | 1 | 1 | 19 | 1 / 1 |
| `service_selection` | Khách chọn dịch vụ | 1 | 2 | 19 | 4 / 0 |
| `service_routing` | Điều phối khách | 4 | 7 | 21 | 17 / 7 |
| `execution` | Thực hiện dịch vụ | 1 | 1 | 19 | 3 / 2 |
| `result` | Biểu mẫu kết quả | 4 | 4 | 13 | 5 / 3 |
| `catalogue` | Danh mục & biểu mẫu | 6 | 3 | 2 | 0 / 12 |
| `permission` | Phân quyền | 10 | 6 | 5 | 1 / 4 |
| `journey` | Hành trình lượt khám | 0 | 0 | 0 | 0 / 0 |
| `trach_nhiem` | Trách nhiệm không được rơi | 4 | 4 | 9 | 1 / 6 |
| `reception` | Tiếp đón | 1 | 3 | 12 | 4 / 11 |
| `vitals` | Sinh hiệu | 1 | 1 | 1 | 1 / 1 |
| `hanh_trinh` | Hành trình lượt khám (Process Manager) | 1 | 0 | 0 | 0 / 5 |
| `consultation` | Khám bệnh | 8 | 6 | 22 | 19 / 5 |
| `payment` | Thu tiền dịch vụ | 10 | 6 | 9 | 0 / 0 |
| `result_file` | Tệp kết quả | 1 | 2 | 13 | 1 / 1 |
| `vong_doc` | Vòng đọc kết quả + khép lượt | 2 | 0 | 0 | 0 / 4 |
| `chuong` | Chuông thông báo | 3 | 5 | 2 | 0 / 3 |
| `chuong_nhan_cheo` | Chuông nhận chéo (phòng quên Xong) | 0 | 0 | 0 | 0 / 0 |
| `booking` | Đặt lịch | 6 | 5 | 12 | 6 / 5 |
| `doi_tac` | Đối tác | 2 | 2 | 8 | 2 / 0 |
| `cskh` | Chăm sóc khách hàng | 7 | 7 | 11 | 1 / 2 |
| `lab` | Xét nghiệm nhập tay | 1 | 2 | 0 | 0 / 0 |
| `thai_ky` | Theo dõi thai kỳ | 1 | 1 | 3 | 0 / 0 |
| `pharmacy` | Quầy thuốc | 12 | 9 | 9 | 7 / 2 |
| `cong_no` | Công nợ khách (chặn check-out còn nợ) | 1 | 2 | 7 | 0 / 0 |
| `so_no` | Sổ nợ hai chiều (phải thu / phải trả theo lượt) | 2 | 1 | 0 | 0 / 0 |
| `kho_vat_tu` | Kho vật tư (phiếu kho, tồn theo nơi chứa, mức tối thiểu) | 4 | 3 | 1 | 0 / 0 |
| `dieu_tri` | Điều trị theo lịch đặt + đổi dịch vụ trong hồ sơ | 1 | 1 | 6 | 0 / 0 |
| `van_hanh` | Vận hành, báo cáo, lịch sử thao tác | 1 | 3 | 3 | 3 / 0 |
| `ke_toan` | Kế toán — xem tài chính đầy đủ, hoá đơn, theo hàng hoá | 6 | 3 | 9 | 2 / 0 |
| `lich_truc` | Lịch làm việc | 5 | 1 | 1 | 0 / 6 |
| `co_so` | Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối) | 7 | 7 | 15 | 14 / 2 |
| `ho_so_khach` | Hồ sơ khách (thông tin, số điện thoại, đồng ý dữ liệu) | 4 | 2 | 7 | 0 / 3 |

## 2. Từng khối

Tên mã khối (vd `so_no`) tra ở bảng mục 1. **Màn gọi tới** = màn có gọi một
tệp của khối, kể cả gián tiếp qua API dùng chung — không phải màn riêng của
khối. **Test canh** = tệp test nhắc tên tệp code của khối nhiều nhất.
### `service_order` — Chỉ định dịch vụ

- **Giữ bảng:** `service_order`, `lam_them_tai_quay`, `lam_them_tai_quay_revision`, `luot_phu_thu`, `so_sua_chi_dinh`
- **Tệp code** (`src/clinicai/`): `services/chi_dinh_service.py`, `services/ho_so_dich_vu.py`, `services/lam_them_tai_quay_config.py`, `services/lam_them_tai_quay_service.py`, `services/service_order_service.py`, `services/so_sua_chi_dinh_service.py`
- **Lệnh:** `PlaceServiceOrders`, `CarryOverUnfinishedOrders`, `SetServiceOrderRequired`, `AddDeskService`, `RemoveDeskService`, `ConfigureDeskServices`, `CancelServiceOrder`
- **Phát sự kiện → khối nghe:** `service_order.placed` → journey; `service_order.carried_over` → journey, so_no; `service_order.required_changed` → journey; `service_order.desk_added` → journey, hanh_trinh; `service_order.desk_removed` → journey; `service_order.cancelled` → journey, so_no; `service_order.restored` → journey, hanh_trinh, so_no
- **Quyền (lego):** `clinical.order.place`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/do-sinh-hieu`, `/doi-tac`, `/duyet-ket-qua`, `/hanh-trinh`, `/home`, `/patient-list`, `/pharmacy`, `/phong`, `/phong/[ma]`, `/print/phieu-kham/[visitId]`, `/print/phieu-thu/[id]`, `/reception/queue` (+7)
- **Test canh:** `test_ho_so_kham_db.py`, `test_luat_1509_nhap_chi_dinh_va_ky.py`, `test_review_0710_ban_kham_db.py`, `test_bio_chi_dinh_db.py`, `test_lam_them_tai_quay_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (5), khối khác ghi bảng của nó (12):
  - ra: `services/lam_them_tai_quay_service.py` ghi `queue_entry` (của `service_routing` · đúng thiết kế)
  - ra: `services/service_order_service.py` ghi `visit_route` (của `service_routing` · chưa xét)
  - ra: `services/service_order_service.py` ghi `work_item` (của `trach_nhiem` · chưa xét)
  - ra: `services/so_sua_chi_dinh_service.py` ghi `luot_phi_kham` (của `phi_kham` · đúng thiết kế)
  - ra: `services/so_sua_chi_dinh_service.py` ghi `thong_bao` (của `chuong` · chưa xét)
  - vào: `services/doi_tac_service.py` (`doi_tac`) ghi `service_order` · vi phạm đã xác nhận
  - vào: `services/form_engine_service.py` (`result`) ghi `service_order` · vi phạm đã xác nhận
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `service_order` · xem lại khối
  - vào: `services/lam_truoc_thu_sau.py` (`service_selection`) ghi `service_order` · chưa xét
  - vào: `services/luot_kham_service.py` (`consultation`) ghi `service_order` · vi phạm đã xác nhận
  - vào: `services/nhan_tai_phong.py` (`service_routing`) ghi `service_order` · chưa xét
  - vào: `services/phi_kham_service.py` (`phi_kham`) ghi `so_sua_chi_dinh` · chưa xét
  - vào: `services/service_execution_service.py` (`execution`) ghi `service_order` · chưa xét
  - vào: `services/service_routing_service.py` (`service_routing`) ghi `service_order` · chưa xét
  - vào: `services/service_selection_service.py` (`service_selection`) ghi `luot_phu_thu` · chưa xét
  - vào: `services/service_selection_service.py` (`service_selection`) ghi `service_order` · chưa xét
  - vào: `services/tep_ket_qua_service.py` (`result_file`) ghi `service_order` · chưa xét

### `vat_tu` — Bán thêm vật tư

- **Giữ bảng:** `luot_vat_tu`, `vat_tu_goi_y`
- **Tệp code** (`src/clinicai/`): `services/bio_chi_dinh_service.py`, `services/vat_tu_service.py`
- **Lệnh:** `AddSupplyToBill`, `SetSupplyQuantity`, `RemoveSupply`
- **Phát sự kiện → khối nghe:** `visit.supply_changed` → journey, so_no
- **Quyền (lego):** `vat_tu.approve`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/do-sinh-hieu`, `/doi-tac`, `/duyet-ket-qua`, `/hanh-trinh`, `/home`, `/patient-list`, `/pharmacy`, `/phong`, `/phong/[ma]`, `/print/phieu-thu/[id]`, `/reception/queue`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su` (+4)
- **Test canh:** `test_bio_chi_dinh_db.py`, `test_vat_tu_ban_them_db.py`, `test_vat_tu_chinh_sach_ban.py`, `test_vat_tu_chinh_sach_ban_db.py`, `test_vat_tu_danh_muc_db.py`

### `lieu_trinh` — Liệu trình điều trị nhiều buổi

- **Giữ bảng:** `lieu_trinh`, `lieu_trinh_lich_su`, `lieu_trinh_buoi`, `lieu_trinh_tra_truoc`
- **Tệp code** (`src/clinicai/`): `services/lieu_trinh_service.py`, `services/lieu_trinh_tien.py`
- **Lệnh:** `ProposeTreatmentPlan`, `AdjustTreatmentPlan`, `RegisterTreatmentPlan`, `StopTreatmentPlan`, `ReopenTreatmentPlan`, `UndoTreatmentPlanChange`, `LinkPlanSession`, `UnlinkPlanSession`, `SetPlanPrepayment`, `RemovePlanPrepayment`
- **Phát sự kiện → khối nghe:** `lieu_trinh.created` → chưa khối nào nghe; `lieu_trinh.revised` → chưa khối nào nghe; `lieu_trinh.session_relinked` → chưa khối nào nghe; `lieu_trinh.prepay_set` → chưa khối nào nghe
- **Nghe:** `service.completed`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/nhac-tai-kham`, `/phong/[ma]`, `/reception/queue`, `/tu-van`
- **Test canh:** `test_lieu_trinh_giao_dien_db.py`, `test_lieu_trinh_db.py`, `test_lieu_trinh_sap_het_db.py`, `test_lieu_trinh_tien_db.py`

### `phi_kham` — Dịch vụ khám (tiền khám)

- **Giữ bảng:** `luot_phi_kham`
- **Tệp code** (`src/clinicai/`): `services/phi_kham_service.py`
- **Lệnh:** `ChonDichVuKham`
- **Phát sự kiện → khối nghe:** `visit.exam_service_changed` → journey, so_no
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/do-sinh-hieu`, `/doi-tac`, `/duyet-ket-qua`, `/hanh-trinh`, `/home`, `/patient-list`, `/pharmacy`, `/phong`, `/phong/[ma]`, `/print/phieu-thu/[id]`, `/reception/queue`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su` (+4)
- **Test canh:** `test_hanh_trinh_trang_thai_hien_tai_db.py`, `test_phi_kham_chon_db.py`, `test_so_sua_chi_dinh_db.py`, `test_thu_dich_vu_nhieu_lan_db.py`, `test_thu_thuat_nhu_kham_thuong_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (1), khối khác ghi bảng của nó (1):
  - ra: `services/phi_kham_service.py` ghi `so_sua_chi_dinh` (của `service_order` · chưa xét)
  - vào: `services/so_sua_chi_dinh_service.py` (`service_order`) ghi `luot_phi_kham` · đúng thiết kế

### `service_selection` — Khách chọn dịch vụ

- **Giữ bảng:** `service_selection_state`
- **Tệp code** (`src/clinicai/`): `services/lam_truoc_thu_sau.py`, `services/service_selection_service.py`
- **Lệnh:** `ConfirmServiceSelection`, `SetDeferPayment`
- **Phát sự kiện → khối nghe:** `service_selection.confirmed` → journey, hanh_trinh, vong_doc, doi_tac; `visit.defer_payment_set` → journey, hanh_trinh, doi_tac; `visit.defer_payment_cleared` → journey
- **Quyền (lego):** `service_selection.confirm`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/do-sinh-hieu`, `/doi-tac`, `/duyet-ket-qua`, `/hanh-trinh`, `/home`, `/patient-list`, `/pharmacy`, `/phong`, `/phong/[ma]`, `/print/phieu-thu/[id]`, `/reception/queue`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su` (+4)
- **Test canh:** `test_thu_truoc_lam_truoc_tick_db.py`, `test_thu_truoc_lam_truoc_tick.py`, `test_nhan_tai_phong_db.py`, `test_service_selection_db.py`, `test_audit_labels_drift.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (4), khối khác ghi bảng của nó (0):
  - ra: `services/lam_truoc_thu_sau.py` ghi `service_order` (của `service_order` · chưa xét)
  - ra: `services/lam_truoc_thu_sau.py` ghi `visit` (của `reception` · chưa xét)
  - ra: `services/service_selection_service.py` ghi `luot_phu_thu` (của `service_order` · chưa xét)
  - ra: `services/service_selection_service.py` ghi `service_order` (của `service_order` · chưa xét)

### `service_routing` — Điều phối khách

- **Giữ bảng:** `queue_entry`, `visit_route`, `visit_gate_override`, `dispatch_threshold`
- **Tệp code** (`src/clinicai/`): `services/dispatch_service.py`, `services/doi_bac_si_service.py`, `services/gate_rule_service.py`, `services/hang_cho.py`, `services/hoan_tac_service.py`, `services/nhan_tai_phong.py`, `services/service_routing_service.py`
- **Lệnh:** `AssignServiceRoom`, `InvalidateServiceRouting`, `AutoAssignPaidOrders`, `PlanServiceRoom`, `TransferInProgressService`, `ReceiveAtRoom`, `UndoReceiveAtRoom`
- **Phát sự kiện → khối nghe:** `service.routed` → journey; `service.routing_invalidated` → journey, trach_nhiem; `service.room_transferred` → journey; `service.doctor_chosen` → journey; `service.room_released` → journey, chuong_nhan_cheo; `service.room_receive_undone` → journey; `service.room_release_undone` → journey, chuong_nhan_cheo; `service.room_guided` → journey
- **Quyền (lego):** `service.routing.view`, `service.routing.assign`, `service.routing.invalidate`, `dispatch.manage`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/do-sinh-hieu`, `/doi-tac`, `/duyet-ket-qua`, `/hanh-trinh`, `/home`, `/patient-list`, `/pharmacy`, `/phong`, `/phong/[ma]`, `/print/phieu-thu/[id]`, `/reception/queue`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su` (+6)
- **Test canh:** `test_luot_kham_service_db.py`, `test_thanh_ngay_moi_ban_db.py`, `test_hanh_trinh_tu_van_db.py`, `test_nhan_tai_phong_db.py`, `test_bac_si_cua_phien_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (17), khối khác ghi bảng của nó (7):
  - ra: `services/doi_bac_si_service.py` ghi `appointment` (của `booking` · vi phạm đã xác nhận)
  - ra: `services/doi_bac_si_service.py` ghi `consultation` (của `consultation` · chưa xét)
  - ra: `services/doi_bac_si_service.py` ghi `visit` (của `reception` · chưa xét)
  - ra: `services/hang_cho.py` ghi `visit` (của `reception` · chưa xét)
  - ra: `services/hoan_tac_service.py` ghi `appointment` (của `booking` · đúng thiết kế)
  - ra: `services/hoan_tac_service.py` ghi `consultation` (của `consultation` · chưa xét)
  - ra: `services/hoan_tac_service.py` ghi `encounter_flow` (của `hanh_trinh` · chưa xét)
  - ra: `services/hoan_tac_service.py` ghi `follow_up_case` (của `trach_nhiem` · chưa xét)
  - ra: `services/hoan_tac_service.py` ghi `review_round` (của `vong_doc` · đúng thiết kế)
  - ra: `services/hoan_tac_service.py` ghi `round_requirement` (của `vong_doc` · chưa xét)
  - ra: `services/hoan_tac_service.py` ghi `service_execution_attempt` (của `execution` · xem lại khối)
  - ra: `services/hoan_tac_service.py` ghi `service_order` (của `service_order` · xem lại khối)
  - ra: `services/hoan_tac_service.py` ghi `visit` (của `reception` · chưa xét)
  - ra: `services/hoan_tac_service.py` ghi `work_item` (của `trach_nhiem` · chưa xét)
  - ra: `services/nhan_tai_phong.py` ghi `service_order` (của `service_order` · chưa xét)
  - ra: `services/service_routing_service.py` ghi `service_execution_attempt` (của `execution` · vi phạm đã xác nhận)
  - ra: `services/service_routing_service.py` ghi `service_order` (của `service_order` · chưa xét)
  - vào: `services/booking_service.py` (`booking`) ghi `queue_entry` · vi phạm đã xác nhận
  - vào: `services/checkout_service.py` (`reception`) ghi `queue_entry` · vi phạm đã xác nhận
  - vào: `services/doi_tac_service.py` (`doi_tac`) ghi `queue_entry` · vi phạm đã xác nhận
  - vào: `services/lam_them_tai_quay_service.py` (`service_order`) ghi `queue_entry` · đúng thiết kế
  - vào: `services/luot_kham_service.py` (`consultation`) ghi `queue_entry` · vi phạm đã xác nhận
  - vào: `services/service_execution_service.py` (`execution`) ghi `queue_entry` · vi phạm đã xác nhận
  - vào: `services/service_order_service.py` (`service_order`) ghi `visit_route` · chưa xét

### `execution` — Thực hiện dịch vụ

- **Giữ bảng:** `service_execution_attempt`
- **Tệp code** (`src/clinicai/`): `services/service_execution_service.py`
- **Lệnh:** `StartService`, `CompleteService`, `MarkServiceNotPerformed`, `InterruptService`, `PrepareServiceRetry`, `CancelMistakenStart`, `UndoServiceCompletion`, `StartServiceAtDesk`, `CompleteServiceAtDesk`, `CancelDeskStart`, `UndoDeskCompletion`
- **Phát sự kiện → khối nghe:** `service.started` → journey, so_no; `service.completed` → lieu_trinh, journey, hanh_trinh, vong_doc, chuong_nhan_cheo, doi_tac, so_no; `service.not_performed` → journey, trach_nhiem, vong_doc, so_no; `service.interrupted` → journey, trach_nhiem, chuong_nhan_cheo; `service.retry_prepared` → journey; `service.patient_moved` → journey; `service.start_cancelled` → journey, chuong_nhan_cheo, so_no; `service.completion_undone` → journey, so_no
- **Quyền (lego):** `service.execute.start`, `service.execute.complete`, `service.execute.not_performed`, `service.execute.interrupt`, `service.execute.retry`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/do-sinh-hieu`, `/doi-tac`, `/duyet-ket-qua`, `/hanh-trinh`, `/home`, `/patient-list`, `/pharmacy`, `/phong`, `/phong/[ma]`, `/print/phieu-thu/[id]`, `/reception/queue`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su` (+4)
- **Test canh:** `test_dieu_tri_ban_kham_db.py`, `test_batch_2409_chieu_db.py`, `test_bio_chi_dinh_db.py`, `test_chuong_nhan_cheo_db.py`, `test_cong_no_check_out_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (3), khối khác ghi bảng của nó (2):
  - ra: `services/service_execution_service.py` ghi `form_instance` (của `result` · vi phạm đã xác nhận)
  - ra: `services/service_execution_service.py` ghi `queue_entry` (của `service_routing` · vi phạm đã xác nhận)
  - ra: `services/service_execution_service.py` ghi `service_order` (của `service_order` · chưa xét)
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `service_execution_attempt` · xem lại khối
  - vào: `services/service_routing_service.py` (`service_routing`) ghi `service_execution_attempt` · vi phạm đã xác nhận

### `result` — Biểu mẫu kết quả

- **Giữ bảng:** `form_instance`, `ultrasound_record`, `clinical_form_response`, `result_correction`
- **Tệp code** (`src/clinicai/`): `services/clinical_form_service.py`, `services/form_engine_service.py`, `services/media_service.py`, `services/ultrasound_service.py`
- **Lệnh:** `OpenForm`, `SaveFormDraft`, `CompleteForm`, `ReopenForm`, `RevokeResultApproval`
- **Phát sự kiện → khối nghe:** `result_form.completed` → journey; `result.ready` → journey, vong_doc, chuong; `result.corrected` → journey, vong_doc, chuong; `result.reviewed` → journey; `result.viewed` → journey; `result.approval_revoked` → journey
- **Gọi thẳng lệnh khối khác (đã khai):** `execution.CompleteService`
- **Quyền (lego):** `result.form.fill`, `result.file.confirm`, `result.review.approve`, `result.file.delete`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/doi-tac`, `/duyet-ket-qua`, `/patient-list`, `/phong/[ma]`, `/print/ket-qua-luot/[visitId]`, `/print/ket-qua/[orderId]`, `/print/phieu-kham/[visitId]`, `/settings/mau-ket-qua`, `/tu-van`, `/xac-nhan-ket-qua`
- **Test canh:** `test_xac_nhan_tep_ket_qua_db.py`, `test_tep_ket_qua.py`, `test_kho_tep_ghi.py`, `test_media.py`, `test_full_chi_dinh_slice_ab_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (5), khối khác ghi bảng của nó (3):
  - ra: `services/form_engine_service.py` ghi `form_definition` (của `catalogue` · xem lại khối)
  - ra: `services/form_engine_service.py` ghi `ket_qua_mau` (của `catalogue` · xem lại khối)
  - ra: `services/form_engine_service.py` ghi `service_order` (của `service_order` · vi phạm đã xác nhận)
  - ra: `services/form_engine_service.py` ghi `visit_amendment` (của `consultation` · chưa xét)
  - ra: `services/ultrasound_service.py` ghi `visit` (của `reception` · chưa xét)
  - vào: `services/clinical_sign_service.py` (`consultation`) ghi `ultrasound_record` · chưa xét
  - vào: `services/service_execution_service.py` (`execution`) ghi `form_instance` · vi phạm đã xác nhận
  - vào: `services/ultrasound_board_service.py` (`trach_nhiem`) ghi `ultrasound_record` · chưa xét

### `catalogue` — Danh mục & biểu mẫu

- **Giữ bảng:** `ket_qua_mau`, `dich_vu_mau_ket_qua`, `form_definition`, `service_price`, `service_type`, `drug_catalog`
- **Tệp code** (`src/clinicai/`): `phieu_kham/nap.py`, `services/mau_ket_qua_service.py`, `services/vat_tu_danh_muc_service.py`
- **Lệnh:** `BindResultTemplate`, `UnbindResultTemplate`, `PublishFormVersion`
- **Quyền (lego):** `catalogue.result_template.manage`, `catalogue.form_template.edit`, `catalogue.form_template.publish`, `config.wiring.manage`, `price.service.manage`, `config.clinic.manage`
- **Màn gọi tới:** `/kho-vat-tu`, `/settings/mau-ket-qua`
- **Test canh:** `test_lich_su_notion_db.py`, `test_staging_bootstrap_safety.py`, `test_staging_che_du_lieu.py`, `test_ket_qua_chung_lam_them_db.py`, `test_kiem_khung_mau.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (0), khối khác ghi bảng của nó (12):
  - vào: `services/chuyen_luot_that.py` (`van_hanh`) ghi `service_type` · chưa xét
  - vào: `services/clinic_config_service.py` (`co_so`) ghi `service_price` · chưa xét
  - vào: `services/clinic_config_service.py` (`co_so`) ghi `service_type` · chưa xét
  - vào: `services/config_service.py` (`co_so`) ghi `drug_catalog` · chưa xét
  - vào: `services/config_service.py` (`co_so`) ghi `service_price` · chưa xét
  - vào: `services/day_noi_service.py` (`co_so`) ghi `service_type` · chưa xét
  - vào: `services/dinh_chinh_don.py` (`consultation`) ghi `drug_catalog` · chưa xét
  - vào: `services/form_engine_service.py` (`result`) ghi `form_definition` · xem lại khối
  - vào: `services/form_engine_service.py` (`result`) ghi `ket_qua_mau` · xem lại khối
  - vào: `services/pharmacy_service.py` (`pharmacy`) ghi `drug_catalog` · chưa xét
  - vào: `services/thue_suat_service.py` (`ke_toan`) ghi `drug_catalog` · chưa xét
  - vào: `services/thue_suat_service.py` (`ke_toan`) ghi `service_price` · chưa xét

### `permission` — Phân quyền

- **Giữ bảng:** `capability_grant`, `quyen_preset`, `ky_nang`, `nhan_su_ky_nang`, `ngoai_le_ca_truc`, `staff`, `staff_node`, `clinic_membership`, `app_credential`, `vai_duoc_vao_tram`
- **Tệp code** (`src/clinicai/`): `services/auth_service.py`, `services/ky_nang_service.py`, `services/ngoai_le_ca_truc_service.py`, `services/permission_service.py`, `services/staff_service.py`, `services/tai_khoan_service.py`
- **Lệnh:** `GrantWorkPack`, `RevokeWorkPack`, `ApplyRolePreset`, `SaveRolePreset`, `RemoveRolePreset`, `SetStaffSkill`, `OpenClinicalShiftException`, `CancelClinicalShiftException`
- **Phát sự kiện → khối nghe:** `capability.granted` → chưa khối nào nghe; `capability.revoked` → chưa khối nào nghe; `clinical_shift.exception_opened` → chưa khối nào nghe; `clinical_shift.exception_cancelled` → chưa khối nào nghe
- **Quyền (lego):** `permission.manage`, `staff.manage`, `account.manage`
- **Màn gọi tới:** `/nhan-su`, `/phan-quyen`, `/schedule`, `/settings/new-user`, `/settings/tai-khoan`
- **Test canh:** `test_chi_dinh_db.py`, `test_ky_nang_ke_hoach.py`, `test_permission_db.py`, `test_quyen_khoi_dong_db.py`, `test_auth_service.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (1), khối khác ghi bảng của nó (4):
  - ra: `services/staff_service.py` ghi `work_roster` (của `lich_truc` · chưa xét)
  - vào: `services/chuyen_luot_that.py` (`van_hanh`) ghi `staff` · chưa xét
  - vào: `services/clinic_config_service.py` (`co_so`) ghi `staff_node` · chưa xét
  - vào: `services/config_service.py` (`co_so`) ghi `vai_duoc_vao_tram` · chưa xét
  - vào: `services/day_noi_service.py` (`co_so`) ghi `vai_duoc_vao_tram` · chưa xét

### `journey` — Hành trình lượt khám

- **Giữ bảng:** —
- **Tệp code** (`src/clinicai/`): —
- **Nghe:** `partner.order_received`, `partner.payment_recorded`, `partner.payment_voided`, `visit.checked_in`, `vitals.started`, `vitals.recorded`, `prescription.saved`, `prescription.consultant_marked`, `medicine.counter_changed`, `medicine.declined`, `service_selection.confirmed`, `service_order.placed`, `service_order.desk_added`, `service_order.desk_removed`, `service.started` (+69)
- **Màn gọi tới:** —
- **Test canh:** —

### `trach_nhiem` — Trách nhiệm không được rơi

- **Giữ bảng:** `work_item`, `work_item_event`, `follow_up_case`, `nhac_viec_ca_nhan`
- **Tệp code** (`src/clinicai/`): `events/consumers/trach_nhiem.py`, `services/nhac_viec_service.py`, `services/ultrasound_board_service.py`, `services/work_item_service.py`
- **Nghe:** `service.not_performed`, `service.interrupted`, `service.routing_invalidated`
- **Quyền (lego):** `worklist.handle`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/do-sinh-hieu`, `/patient-list`, `/pharmacy`, `/phong/[ma]`, `/tu-van`, `/viec-can-xu-ly`
- **Test canh:** `test_work_item_service.py`, `test_cua_quyen_lego.py`, `test_luat_1509_sieu_am_va_hang_cho.py`, `test_loc_co_so_nhom_c_db.py`, `test_day_noi_nhac_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (1), khối khác ghi bảng của nó (6):
  - ra: `services/ultrasound_board_service.py` ghi `ultrasound_record` (của `result` · chưa xét)
  - vào: `services/booking_service.py` (`booking`) ghi `work_item` · chưa xét
  - vào: `services/checkout_service.py` (`reception`) ghi `work_item` · chưa xét
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `follow_up_case` · chưa xét
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `work_item` · chưa xét
  - vào: `services/luot_kham_service.py` (`consultation`) ghi `follow_up_case` · chưa xét
  - vào: `services/service_order_service.py` (`service_order`) ghi `work_item` · chưa xét

### `reception` — Tiếp đón

- **Giữ bảng:** `visit`
- **Tệp code** (`src/clinicai/`): `services/checkout_service.py`, `services/theo_doi_thu_thuat_service.py`, `services/thu_tu_kham_service.py`
- **Lệnh:** `CheckInPatient`, `CheckOutPatient`, `ReopenVisit`
- **Phát sự kiện → khối nghe:** `visit.checked_in` → journey, hanh_trinh; `visit.checked_out` → journey, hanh_trinh, so_no; `visit.left_early` → journey, hanh_trinh, so_no; `visit.reopened` → journey, so_no
- **Quyền (lego):** `reception.checkin.perform`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/hanh-trinh`, `/patient-list`, `/reception/checkout`, `/reception/queue`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su`, `/thu-ngan/thuoc`, `/thu-ngan/thuoc/lich-su`, `/tu-van`
- **Test canh:** `test_checkout_blockers.py`, `test_so_tuong_tac_cskh.py`, `test_audit_labels_drift.py`, `test_luat_1509_thu_ky_va_dieu_phoi.py`, `test_slice1_rail_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (4), khối khác ghi bảng của nó (11):
  - ra: `services/checkout_service.py` ghi `appointment` (của `booking` · vi phạm đã xác nhận)
  - ra: `services/checkout_service.py` ghi `queue_entry` (của `service_routing` · vi phạm đã xác nhận)
  - ra: `services/checkout_service.py` ghi `work_item` (của `trach_nhiem` · chưa xét)
  - ra: `services/thu_tu_kham_service.py` ghi `patient` (của `ho_so_khach` · chưa xét)
  - vào: `services/ban_le_service.py` (`pharmacy`) ghi `visit` · chưa xét
  - vào: `services/ban_theo_don_service.py` (`pharmacy`) ghi `visit` · chưa xét
  - vào: `services/booking_service.py` (`booking`) ghi `visit` · chưa xét
  - vào: `services/clinical_record_service.py` (`consultation`) ghi `visit` · chưa xét
  - vào: `services/clinical_sign_service.py` (`consultation`) ghi `visit` · chưa xét
  - vào: `services/doi_bac_si_service.py` (`service_routing`) ghi `visit` · chưa xét
  - vào: `services/hang_cho.py` (`service_routing`) ghi `visit` · chưa xét
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `visit` · chưa xét
  - vào: `services/lam_truoc_thu_sau.py` (`service_selection`) ghi `visit` · chưa xét
  - vào: `services/luot_kham_service.py` (`consultation`) ghi `visit` · chưa xét
  - vào: `services/ultrasound_service.py` (`result`) ghi `visit` · chưa xét

### `vitals` — Sinh hiệu

- **Giữ bảng:** `vital_measurement`
- **Tệp code** (`src/clinicai/`): `services/sinh_hieu_service.py`
- **Lệnh:** `StartVitals`, `RecordVitals`
- **Phát sự kiện → khối nghe:** `vitals.started` → journey; `vitals.recorded` → journey, hanh_trinh
- **Quyền (lego):** `vitals.measure`
- **Màn gọi tới:** `/do-sinh-hieu`
- **Test canh:** `test_bo_qua_tu_van_chi_dinh_them_db.py`, `test_doc_luot_v5_sinh_hieu_buoi_db.py`, `test_loi_sinh_hieu_co_truong.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (1), khối khác ghi bảng của nó (1):
  - ra: `services/sinh_hieu_service.py` ghi `encounter_flow` (của `hanh_trinh` · chưa xét)
  - vào: `services/clinical_record_service.py` (`consultation`) ghi `vital_measurement` · vi phạm đã xác nhận

### `hanh_trinh` — Hành trình lượt khám (Process Manager)

- **Giữ bảng:** `encounter_flow`
- **Tệp code** (`src/clinicai/`): —
- **Phát sự kiện → khối nghe:** `visit.routed` → journey, dieu_tri
- **Nghe:** `visit.checked_in`, `vitals.recorded`, `consultation.handed_over`, `payment.service_collected`, `payment.medicine_collected`, `service_selection.confirmed`, `service_order.desk_added`, `service_order.restored`, `visit.defer_payment_set`, `visit.checked_out`, `visit.left_early`, `service.completed`, `partner.sample_collected`, `appointment.service_switched`
- **Gọi thẳng lệnh khối khác (đã khai):** `consultation.RouteAfterCheckIn`, `consultation.RerouteAfterServiceSwitch`, `consultation.OpenIntakeQueue`, `consultation.HandToPrimaryDoctor`, `service_order.CarryOverUnfinishedOrders`, `service_routing.AutoAssignPaidOrders`
- **Màn gọi tới:** —
- **Test canh:** —
- **Nợ ghi chéo** — khối này ghi bảng khối khác (0), khối khác ghi bảng của nó (5):
  - vào: `services/booking_service.py` (`booking`) ghi `encounter_flow` · chưa xét
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `encounter_flow` · chưa xét
  - vào: `services/lenh_kham_core.py` (`consultation`) ghi `encounter_flow` · chưa xét
  - vào: `services/luot_kham_service.py` (`consultation`) ghi `encounter_flow` · chưa xét
  - vào: `services/sinh_hieu_service.py` (`vitals`) ghi `encounter_flow` · chưa xét

### `consultation` — Khám bệnh

- **Giữ bảng:** `clinical_record`, `patient_medical_profile`, `prescription`, `consultation`, `consultation_note`, `phieu_kham_luot`, `clinical_release`, `visit_amendment`
- **Tệp code** (`src/clinicai/`): `services/clinical_record_service.py`, `services/clinical_sign_service.py`, `services/dinh_chinh_don.py`, `services/lenh_kham_core.py`, `services/luot_kham_service.py`, `services/phieu_kham_service.py`
- **Lệnh:** `StartConsultation`, `CompleteConsultation`, `SaveConsultationNote`, `SaveClinicalRecord`, `ReleaseRecord`, `StartIntake`, `CompleteIntake`, `RecordIntakeNote`, `RouteAfterCheckIn`, `RerouteAfterServiceSwitch`, `OpenIntakeQueue`, `HandToPrimaryDoctor`, `ReopenConsultation`
- **Phát sự kiện → khối nghe:** `consultation.started` → journey; `consultation.resumed` → journey; `consultation.handed_over` → journey, hanh_trinh; `consultation.completed` → journey; `consultation.reopened` → journey; `followup.scheduled` → journey; `prescription.saved` → journey, so_no; `prescription.consultant_marked` → journey
- **Quyền (lego):** `clinical.intake.perform`, `clinical.consult.perform`, `clinical.record.write`, `clinical.consult.finalize`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/do-sinh-hieu`, `/doi-tac`, `/duyet-ket-qua`, `/hanh-trinh`, `/home`, `/patient-list`, `/pharmacy`, `/phong`, `/phong/[ma]`, `/print/[appointmentId]`, `/print/ket-qua-luot/[visitId]`, `/print/phieu-kham/[visitId]`, `/print/phieu-thu/[id]` (+7)
- **Test canh:** `test_luat_1509_nhap_chi_dinh_va_ky.py`, `test_clinical_record_revision_sql.py`, `test_doi_tac_khong_giu_luot.py`, `test_sinh_hieu_bat_buoc_va_lich_su.py`, `test_tien_thuoc_cp6_dinh_chinh_da_ky_service_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (19), khối khác ghi bảng của nó (5):
  - ra: `services/clinical_record_service.py` ghi `visit` (của `reception` · chưa xét)
  - ra: `services/clinical_record_service.py` ghi `vital_measurement` (của `vitals` · vi phạm đã xác nhận)
  - ra: `services/clinical_sign_service.py` ghi `cskh_action` (của `cskh` · chưa xét)
  - ra: `services/clinical_sign_service.py` ghi `hen_goi_lai` (của `cskh` · chưa xét)
  - ra: `services/clinical_sign_service.py` ghi `ultrasound_record` (của `result` · chưa xét)
  - ra: `services/clinical_sign_service.py` ghi `visit` (của `reception` · chưa xét)
  - ra: `services/dinh_chinh_don.py` ghi `drug_catalog` (của `catalogue` · chưa xét)
  - ra: `services/dinh_chinh_don.py` ghi `prescription_allocation` (của `pharmacy` · vi phạm đã xác nhận)
  - ra: `services/dinh_chinh_don.py` ghi `prescription_correction` (của `pharmacy` · chưa xét)
  - ra: `services/lenh_kham_core.py` ghi `encounter_flow` (của `hanh_trinh` · chưa xét)
  - ra: `services/luot_kham_service.py` ghi `appointment` (của `booking` · vi phạm đã xác nhận)
  - ra: `services/luot_kham_service.py` ghi `encounter_flow` (của `hanh_trinh` · chưa xét)
  - ra: `services/luot_kham_service.py` ghi `follow_up_case` (của `trach_nhiem` · chưa xét)
  - ra: `services/luot_kham_service.py` ghi `queue_entry` (của `service_routing` · vi phạm đã xác nhận)
  - ra: `services/luot_kham_service.py` ghi `review_round` (của `vong_doc` · xem lại khối)
  - ra: `services/luot_kham_service.py` ghi `round_requirement` (của `vong_doc` · chưa xét)
  - ra: `services/luot_kham_service.py` ghi `service_order` (của `service_order` · vi phạm đã xác nhận)
  - ra: `services/luot_kham_service.py` ghi `tep_ket_qua` (của `result_file` · vi phạm đã xác nhận)
  - ra: `services/luot_kham_service.py` ghi `visit` (của `reception` · chưa xét)
  - vào: `services/doi_bac_si_service.py` (`service_routing`) ghi `consultation` · chưa xét
  - vào: `services/form_engine_service.py` (`result`) ghi `visit_amendment` · chưa xét
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `consultation` · chưa xét
  - vào: `services/pharmacy_service.py` (`pharmacy`) ghi `prescription` · chưa xét
  - vào: `services/quay_thuoc_service.py` (`pharmacy`) ghi `prescription` · vi phạm đã xác nhận

### `payment` — Thu tiền dịch vụ

- **Giữ bảng:** `payment_cycle`, `payment_bill_line`, `payment_cycle_doi_hinh_thuc`, `payment_cycle_phan`, `anh_chuyen_khoan`, `payment`, `payment_refund`, `payment_refund_line`, `tien_thua_giu_lai`, `chot_so_ca`
- **Tệp code** (`src/clinicai/`): `services/anh_chuyen_khoan_service.py`, `services/chot_so_ca_service.py`, `services/doi_hinh_thuc_service.py`, `services/hoan_tien_service.py`, `services/payment_service.py`, `services/tien_thua_service.py`
- **Lệnh:** `CollectServicePayment`
- **Phát sự kiện → khối nghe:** `payment.service_collected` → journey, hanh_trinh, doi_tac, cong_no, so_no; `payment.medicine_collected` → journey, hanh_trinh, cong_no, so_no; `payment.refunded` → journey, so_no; `payment.method_changed` → journey; `payment.collection_undone` → journey, so_no; `medicine.declined` → journey
- **Quyền (lego):** `payment.service.collect`, `payment.medicine.collect`
- **Màn gọi tới:** `/hanh-trinh`, `/pharmacy`, `/reception/checkout`, `/reception/queue`, `/reports`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su`, `/thu-ngan/thuoc`, `/thu-ngan/thuoc/lich-su`
- **Test canh:** `test_clinical_data_integrity.py`, `test_mo_phong_dong_tien_db.py`, `test_doi_hinh_thuc_db.py`, `test_ke_toan_lego_db.py`, `test_payment_head_scope_db.py`

### `result_file` — Tệp kết quả

- **Giữ bảng:** `tep_ket_qua`
- **Tệp code** (`src/clinicai/`): `services/don_tep_ket_qua.py`, `services/tep_ket_qua_service.py`
- **Lệnh:** `UploadResultFile`, `ConfirmResultFile`, `OpenResultFile`, `MarkSent`, `RevokeResultFile`, `DeleteResultFile`, `RestoreResultFile`
- **Phát sự kiện → khối nghe:** `result_file.uploaded` → journey, vong_doc, chuong; `result_file.confirmed` → journey, vong_doc, chuong; `result_file.revoked` → journey, vong_doc; `result_file.deleted` → journey, vong_doc; `result_file.restored` → journey, vong_doc; `result_file.viewed` → journey; `result_file.sent_to_patient` → journey
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/do-sinh-hieu`, `/doi-tac`, `/duyet-ket-qua`, `/patient-list`, `/pharmacy`, `/phong/[ma]`, `/print/ket-qua/[orderId]`, `/print/phieu-kham/[visitId]`, `/tu-van`, `/xac-nhan-ket-qua`
- **Test canh:** `test_xac_nhan_tep_ket_qua_db.py`, `test_full_chi_dinh_slice_ab_db.py`, `test_tep_ket_qua.py`, `test_cho_xac_nhan_queue_va_doc_tep_db.py`, `test_slice1_http_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (1), khối khác ghi bảng của nó (1):
  - ra: `services/tep_ket_qua_service.py` ghi `service_order` (của `service_order` · chưa xét)
  - vào: `services/luot_kham_service.py` (`consultation`) ghi `tep_ket_qua` · vi phạm đã xác nhận

### `vong_doc` — Vòng đọc kết quả + khép lượt

- **Giữ bảng:** `review_round`, `round_requirement`
- **Tệp code** (`src/clinicai/`): —
- **Phát sự kiện → khối nghe:** `visit.exam_completed` → journey
- **Nghe:** `service_selection.confirmed`, `service.completed`, `service.not_performed`, `partner.sample_collected`, `partner.sample_received`, `result.ready`, `result.corrected`, `result_file.uploaded`, `result_file.confirmed`, `result_file.revoked`, `result_file.deleted`, `result_file.restored`
- **Màn gọi tới:** —
- **Test canh:** —
- **Nợ ghi chéo** — khối này ghi bảng khối khác (0), khối khác ghi bảng của nó (4):
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `review_round` · đúng thiết kế
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `round_requirement` · chưa xét
  - vào: `services/luot_kham_service.py` (`consultation`) ghi `review_round` · xem lại khối
  - vào: `services/luot_kham_service.py` (`consultation`) ghi `round_requirement` · chưa xét

### `chuong` — Chuông thông báo

- **Giữ bảng:** `day_nhan_thong_bao`, `thong_bao`, `thong_bao_an_cua_toi`
- **Tệp code** (`src/clinicai/`): `events/consumers/chuong.py`, `events/consumers/chuong_nhan_cheo.py`, `events/hen_gio.py`, `events/worker.py`, `services/thong_bao_service.py`
- **Nghe:** `result_file.uploaded`, `result_file.confirmed`, `result.ready`, `result.corrected`, `lab_result.arrived`, `partner.order_received`, `partner.result_returned`, `pharmacy.expiry_checked`, `pharmacy.stocktake_mismatch`
- **Màn gọi tới:** `/customers`, `/doi-tac`
- **Test canh:** `test_hen_tai_kham_db.py`, `test_hen_gio_db.py`, `test_canh_bao_han_lo_db.py`, `test_kiem_ke_ca_db.py`, `test_doi_tac_nhan_mau_la_xong_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (0), khối khác ghi bảng của nó (3):
  - vào: `services/day_noi_service.py` (`co_so`) ghi `day_nhan_thong_bao` · chưa xét
  - vào: `services/hen_tai_kham_service.py` (`cskh`) ghi `thong_bao` · chưa xét
  - vào: `services/so_sua_chi_dinh_service.py` (`service_order`) ghi `thong_bao` · chưa xét

### `chuong_nhan_cheo` — Chuông nhận chéo (phòng quên Xong)

- **Giữ bảng:** —
- **Tệp code** (`src/clinicai/`): —
- **Nghe:** `service.room_released`, `service.completed`, `service.interrupted`, `service.start_cancelled`, `service.room_release_undone`
- **Màn gọi tới:** —
- **Test canh:** —

### `booking` — Đặt lịch

- **Giữ bảng:** `appointment`, `appointment_doi_lich`, `care_episode`, `doctor_booking_override`, `slot_booking_override`, `luat_bac_si_bat_buoc`
- **Tệp code** (`src/clinicai/`): `services/booking_override_service.py`, `services/booking_service.py`, `services/episode_service.py`, `services/luat_bac_si_service.py`, `services/scheduling_service.py`
- **Lệnh:** `BookAppointment`, `RescheduleAppointment`, `CancelAppointment`, `MarkNoShow`, `ConfirmByCall`, `SwitchExamService`
- **Phát sự kiện → khối nghe:** `appointment.booked` → journey; `appointment.rescheduled` → journey; `appointment.service_switched` → journey, hanh_trinh; `appointment.cancelled` → journey; `appointment.no_show` → journey; `appointment.confirmed_by_call` → journey
- **Quyền (lego):** `booking.create`, `booking.manage`
- **Màn gọi tới:** `/appointments`, `/appointments/cho-xep-bac-si`, `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/home`, `/nhac-tai-kham`, `/patient-list`, `/patients/new`, `/reception/queue`, `/settings/booking-policy`, `/tu-van`
- **Test canh:** `test_booking_service.py`, `test_so_tuong_tac_cskh.py`, `test_dat_lich_chi_ba_noi_ghi.py`, `test_clinical_data_integrity.py`, `test_cua_ngo_ghi_moi.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (6), khối khác ghi bảng của nó (5):
  - ra: `services/booking_service.py` ghi `encounter_flow` (của `hanh_trinh` · chưa xét)
  - ra: `services/booking_service.py` ghi `patient` (của `ho_so_khach` · chưa xét)
  - ra: `services/booking_service.py` ghi `queue_entry` (của `service_routing` · vi phạm đã xác nhận)
  - ra: `services/booking_service.py` ghi `visit` (của `reception` · chưa xét)
  - ra: `services/booking_service.py` ghi `work_item` (của `trach_nhiem` · chưa xét)
  - ra: `services/booking_service.py` ghi `work_roster` (của `lich_truc` · chưa xét)
  - vào: `services/checkout_service.py` (`reception`) ghi `appointment` · vi phạm đã xác nhận
  - vào: `services/config_service.py` (`co_so`) ghi `appointment` · chưa xét
  - vào: `services/doi_bac_si_service.py` (`service_routing`) ghi `appointment` · vi phạm đã xác nhận
  - vào: `services/hoan_tac_service.py` (`service_routing`) ghi `appointment` · đúng thiết kế
  - vào: `services/luot_kham_service.py` (`consultation`) ghi `appointment` · vi phạm đã xác nhận

### `doi_tac` — Đối tác

- **Giữ bảng:** `doi_tac_nhan_viec`, `doi_tac_thanh_toan`
- **Tệp code** (`src/clinicai/`): `events/consumers/doi_tac.py`, `services/doi_tac_service.py`
- **Lệnh:** `MarkSampleCollected`, `MarkAwaitingDocuments`, `RecordPartnerPayment`, `VoidPartnerPayment`, `ReturnPartnerResult`, `UndoPartnerResult`, `UndoSampleReceipt`
- **Phát sự kiện → khối nghe:** `partner.sample_collected` → journey, hanh_trinh, vong_doc, doi_tac; `partner.sample_received` → journey, vong_doc; `partner.sample_receipt_undone` → journey; `partner.result_returned` → journey, chuong; `partner.result_return_undone` → journey; `partner.order_received` → journey, chuong; `partner.payment_recorded` → journey; `partner.payment_voided` → journey
- **Nghe:** `service_selection.confirmed`, `visit.defer_payment_set`, `payment.service_collected`, `service.completed`, `partner.sample_collected`
- **Quyền (lego):** `partner.work`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/do-sinh-hieu`, `/doi-tac`, `/duyet-ket-qua`, `/pharmacy`, `/phong/[ma]`, `/tu-van`
- **Test canh:** `test_full_chi_dinh_slice_ab_db.py`, `test_luot_kham_service_db.py`, `test_doi_tac_nhan_mau_la_xong_db.py`, `test_doi_tac_nhan_viec_db.py`, `test_lan_chi_dinh_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (2), khối khác ghi bảng của nó (0):
  - ra: `services/doi_tac_service.py` ghi `queue_entry` (của `service_routing` · vi phạm đã xác nhận)
  - ra: `services/doi_tac_service.py` ghi `service_order` (của `service_order` · vi phạm đã xác nhận)

### `cskh` — Chăm sóc khách hàng

- **Giữ bảng:** `tuong_tac_cskh`, `ghi_chu_khach`, `cskh_action`, `cskh_log`, `hen_goi_lai`, `nhac_tai_kham`, `phan_hoi_khach`
- **Tệp code** (`src/clinicai/`): `services/cskh_service.py`, `services/ghi_chu_khach_service.py`, `services/hen_tai_kham_service.py`, `services/phan_hoi_khach_service.py`, `services/phan_hoi_thuoc_service.py`, `services/recall_job_service.py`, `services/tuong_tac_cskh_service.py`
- **Lệnh:** `LogContact`
- **Phát sự kiện → khối nghe:** `patient.contacted` → chưa khối nào nghe
- **Quyền (lego):** `crm.manage`, `patient.create`, `patient.list.view`
- **Màn gọi tới:** `/appointments`, `/appointments/cho-xep-bac-si`, `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/home`, `/nhac-tai-kham`, `/patient-list`, `/patients/new`, `/reception/queue`, `/tu-van`
- **Test canh:** `test_so_tuong_tac_cskh.py`, `test_recall_callback_consistency.py`, `test_hen_tai_kham_db.py`, `test_phan_hoi_thuoc_db.py`, `test_checkout_blockers.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (1), khối khác ghi bảng của nó (2):
  - ra: `services/hen_tai_kham_service.py` ghi `thong_bao` (của `chuong` · chưa xét)
  - vào: `services/clinical_sign_service.py` (`consultation`) ghi `cskh_action` · chưa xét
  - vào: `services/clinical_sign_service.py` (`consultation`) ghi `hen_goi_lai` · chưa xét

### `lab` — Xét nghiệm nhập tay

- **Giữ bảng:** `lab_result`
- **Tệp code** (`src/clinicai/`): `services/lab_order_service.py`, `services/lab_safety_service.py`
- **Lệnh:** `EnterLabResult`
- **Phát sự kiện → khối nghe:** `lab_result.arrived` → journey, chuong
- **Màn gọi tới:** —
- **Test canh:** `test_clinical_cluster.py`, `test_clinical_data_integrity.py`, `test_lab_safety_service.py`, `test_lab_triage_skeleton.py`, `test_no_con_lai_db.py`

### `thai_ky` — Theo dõi thai kỳ

- **Giữ bảng:** `pregnancy`
- **Tệp code** (`src/clinicai/`): `services/thai_ky_service.py`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/tu-van`
- **Test canh:** `test_thai_ky_db.py`, `test_thai_ky_tu_phieu.py`, `test_thai_ky_tu_phieu_sk_db.py`

### `pharmacy` — Quầy thuốc

- **Giữ bảng:** `prescription_allocation`, `inventory_txn`, `drug_batch`, `drug_ma_vach`, `drug_return`, `thuoc_quy_doi`, `thuoc_giao_chua_gan_lo`, `prescription_correction`, `phieu_kho`, `phieu_kho_dong`, `kiem_ke_ca`, `kiem_ke_ca_dong`
- **Tệp code** (`src/clinicai/`): `services/ban_le_service.py`, `services/ban_theo_don_service.py`, `services/kho_thuoc_service.py`, `services/kiem_ke_ca_service.py`, `services/lo_thuoc_service.py`, `services/ma_vach_service.py`, `services/phan_lo_service.py`, `services/pharmacy_service.py`, `services/quay_thuoc_service.py`
- **Lệnh:** `MapDrug`, `SetPurchasedQty`, `AdjustSaleAtCounter`, `AllocateLots`, `DispenseMedicine`, `RefuseLine`, `CloseLine`
- **Phát sự kiện → khối nghe:** `medicine.dispensed` → journey, so_no; `medicine.counter_changed` → journey; `pharmacy.expiry_checked` → chuong; `medicine.returned` → journey, so_no; `pharmacy.stocktake_mismatch` → chuong
- **Quyền (lego):** `pharmacy.dispense`, `pharmacy.view`
- **Màn gọi tới:** `/pharmacy`, `/pharmacy/consult`, `/pharmacy/history`, `/pharmacy/inventory`, `/print/tem-lo`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su`, `/thu-ngan/thuoc`, `/thu-ngan/thuoc/lich-su`
- **Test canh:** `test_quy_doi_don_vi_db.py`, `test_kho_quay_db.py`, `test_ban_theo_don_db.py`, `test_ma_vach_db.py`, `test_doi_chieu_kho_thuoc_db.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (7), khối khác ghi bảng của nó (2):
  - ra: `services/ban_le_service.py` ghi `visit` (của `reception` · chưa xét)
  - ra: `services/ban_theo_don_service.py` ghi `visit` (của `reception` · chưa xét)
  - ra: `services/kho_thuoc_service.py` ghi `clinic_location` (của `co_so` · chưa xét)
  - ra: `services/lo_thuoc_service.py` ghi `clinic` (của `co_so` · chưa xét)
  - ra: `services/pharmacy_service.py` ghi `drug_catalog` (của `catalogue` · chưa xét)
  - ra: `services/pharmacy_service.py` ghi `prescription` (của `consultation` · chưa xét)
  - ra: `services/quay_thuoc_service.py` ghi `prescription` (của `consultation` · vi phạm đã xác nhận)
  - vào: `services/dinh_chinh_don.py` (`consultation`) ghi `prescription_allocation` · vi phạm đã xác nhận
  - vào: `services/dinh_chinh_don.py` (`consultation`) ghi `prescription_correction` · chưa xét

### `cong_no` — Công nợ khách (chặn check-out còn nợ)

- **Giữ bảng:** `cong_no`
- **Tệp code** (`src/clinicai/`): `events/consumers/cong_no.py`, `services/cong_no_service.py`
- **Lệnh:** `GhiNo`, `HuyGhiNo`
- **Phát sự kiện → khối nghe:** `cong_no.ghi` → journey, so_no; `cong_no.huy` → journey, so_no; `cong_no.da_thu` → journey
- **Nghe:** `payment.service_collected`, `payment.medicine_collected`
- **Màn gọi tới:** `/hanh-trinh`, `/reception/checkout`, `/reception/queue`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su`, `/thu-ngan/thuoc`, `/thu-ngan/thuoc/lich-su`
- **Test canh:** `test_cong_no_check_out_db.py`, `test_danh_sach_hoa_don_viec_ton_db.py`, `test_giam_gia_db.py`, `test_mo_phong_dong_tien_db.py`, `test_thu_ngan_thanh_ngay_db.py`

### `so_no` — Sổ nợ hai chiều (phải thu / phải trả theo lượt)

- **Giữ bảng:** `so_no`, `so_no_moc`
- **Tệp code** (`src/clinicai/`): `services/so_no_service.py`
- **Nghe:** `visit.checked_out`, `visit.left_early`, `visit.reopened`, `cong_no.ghi`, `cong_no.huy`, `payment.service_collected`, `payment.medicine_collected`, `payment.collection_undone`, `payment.refunded`, `service_order.cancelled`, `service_order.restored`, `service_order.carried_over`, `service.started`, `service.completed`, `service.not_performed` (+7)
- **Màn gọi tới:** —
- **Test canh:** `test_an_ton_co_so_ngung_db.py`, `test_danh_sach_hoa_don.py`, `test_so_no_hai_chieu_db.py`, `test_tra_thuoc_hoan_db.py`

### `kho_vat_tu` — Kho vật tư (phiếu kho, tồn theo nơi chứa, mức tối thiểu)

- **Giữ bảng:** `vat_tu_phieu`, `vat_tu_ton`, `vat_tu_txn`, `vat_tu_nhap_cho_duyet`
- **Tệp code** (`src/clinicai/`): `services/vat_tu_kho_man_service.py`, `services/vat_tu_kho_service.py`, `services/vat_tu_nhap_duyet_service.py`
- **Lệnh:** `LapPhieuVatTu`, `HoanPhieuVatTu`, `DatMucToiThieuVatTu`, `DuyetPhieuNhapVatTu`, `TuChoiPhieuNhapVatTu`, `RutLaiPhieuNhapVatTu`
- **Phát sự kiện → khối nghe:** `vat_tu.nhap_cho_duyet` → chưa khối nào nghe; `vat_tu.nhap_da_quyet` → chưa khối nào nghe
- **Quyền (lego):** `vat_tu.manage`
- **Màn gọi tới:** `/kho-vat-tu`
- **Test canh:** `test_vat_tu_kho_db.py`, `test_vat_tu_kho_man_db.py`, `test_kho_audit_bo_sung_db.py`, `test_mo_phong_vat_tu_day_du_db.py`, `test_tieu_hao_vat_tu.py`

### `dieu_tri` — Điều trị theo lịch đặt + đổi dịch vụ trong hồ sơ

- **Giữ bảng:** `luot_ghi_chu`
- **Tệp code** (`src/clinicai/`): `services/ghi_chu_luot.py`
- **Lệnh:** `DoiDichVuTrongHoSo`
- **Nghe:** `visit.routed`
- **Gọi thẳng lệnh khối khác (đã khai):** `execution.StartServiceAtDesk`, `execution.CompleteServiceAtDesk`, `execution.CancelDeskStart`, `execution.UndoDeskCompletion`
- **Màn gọi tới:** `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/patient-list`, `/print/phieu-kham/[visitId]`, `/tu-van`
- **Test canh:** `test_ghi_chu_luot_db.py`

### `van_hanh` — Vận hành, báo cáo, lịch sử thao tác

- **Giữ bảng:** `agent_cau_hinh`
- **Tệp code** (`src/clinicai/`): `services/agent_giam_sat.py`, `services/chuyen_luot_that.py`, `services/nhap_lich_su_notion.py`
- **Quyền (lego):** `report.view`, `ops.view`, `audit.view`, `giamsat.view`
- **Màn gọi tới:** `/doi-tac`, `/giam-sat`, `/login`
- **Test canh:** `test_lich_su_notion_db.py`, `test_dat_lich_chi_ba_noi_ghi.py`, `test_agent_giam_sat.py`, `test_agent_giam_sat_db.py`, `test_hanh_trinh_khach.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (3), khối khác ghi bảng của nó (0):
  - ra: `services/chuyen_luot_that.py` ghi `service_type` (của `catalogue` · chưa xét)
  - ra: `services/chuyen_luot_that.py` ghi `staff` (của `permission` · chưa xét)
  - ra: `services/nhap_lich_su_notion.py` ghi `patient` (của `ho_so_khach` · chưa xét)

### `ke_toan` — Kế toán — xem tài chính đầy đủ, hoá đơn, theo hàng hoá

- **Giữ bảng:** `hoa_don_cong_ty`, `hoa_don_cong_ty_lich_su`, `hoa_don_misa_xuat`, `hoa_don_misa_xuat_dong`, `khach_cong_ty`, `thue_suat_nhom`
- **Tệp code** (`src/clinicai/`): `services/hoa_don_cong_ty_service.py`, `services/hoa_don_misa_service.py`, `services/thue_suat_service.py`
- **Quyền (lego):** `accounting.finance.full`, `accounting.tax.manage`
- **Màn gọi tới:** `/customers`, `/hoa-don`, `/ke-toan`, `/pharmacy`, `/thu-ngan/dich-vu`, `/thu-ngan/dich-vu/lich-su`, `/thu-ngan/thuoc`, `/thu-ngan/thuoc/lich-su`, `/xuat-hoa-don`
- **Test canh:** `test_hoa_don_misa_db.py`, `test_hoa_don_cong_ty.py`, `test_hoa_don_cong_ty_db.py`, `test_thue_gtgt_db.py`, `test_thue_khong_cham_van_hanh.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (2), khối khác ghi bảng của nó (0):
  - ra: `services/thue_suat_service.py` ghi `drug_catalog` (của `catalogue` · chưa xét)
  - ra: `services/thue_suat_service.py` ghi `service_price` (của `catalogue` · chưa xét)

### `lich_truc` — Lịch làm việc

- **Giữ bảng:** `work_roster`, `work_roster_thay_nguoi`, `roster_week`, `vi_tri_lam_viec`, `thu_ky_bac_si`
- **Tệp code** (`src/clinicai/`): `services/thu_ky_bac_si.py`
- **Quyền (lego):** `roster.view`, `roster.shift.swap`, `roster.manage`
- **Màn gọi tới:** `/settings/clinic-config`
- **Test canh:** `test_luat_1509_thu_ky_va_dieu_phoi.py`, `test_luot_kham_service_db.py`, `test_luat_1509_sieu_am_va_hang_cho.py`, `test_bac_si_cua_phien_db.py`, `test_luat_1509_nhap_chi_dinh_va_ky.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (0), khối khác ghi bảng của nó (6):
  - vào: `services/booking_service.py` (`booking`) ghi `work_roster` · chưa xét
  - vào: `services/config_service.py` (`co_so`) ghi `roster_week` · chưa xét
  - vào: `services/config_service.py` (`co_so`) ghi `work_roster` · chưa xét
  - vào: `services/config_service.py` (`co_so`) ghi `work_roster_thay_nguoi` · chưa xét
  - vào: `services/day_noi_service.py` (`co_so`) ghi `vi_tri_lam_viec` · chưa xét
  - vào: `services/staff_service.py` (`permission`) ghi `work_roster` · chưa xét

### `co_so` — Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối)

- **Giữ bảng:** `clinic`, `clinic_location`, `clinic_floor`, `clinic_room`, `clinic_room_node`, `clinic_room_service`, `day_nghiep_vu`
- **Tệp code** (`src/clinicai/`): `api/v1/routers/config.py`, `services/clinic_config_service.py`, `services/clinic_floor_service.py`, `services/clinic_settings_service.py`, `services/config_service.py`, `services/day_noi_service.py`, `services/report_access_service.py`
- **Màn gọi tới:** `/appointments`, `/cashier/dich-vu`, `/cashier/thuoc`, `/customers`, `/doi-tac`, `/hoa-don`, `/kho-vat-tu`, `/nhan-su`, `/patients/new`, `/reports`, `/schedule`, `/settings`, `/settings/booking-policy`, `/settings/clinic-config`, `/settings/day-noi`
- **Test canh:** `test_e2e_lab_triage.py`, `test_e2e_scheduling.py`, `test_routing.py`, `test_audit_labels_drift.py`, `test_dashboard_backend_paths.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (14), khối khác ghi bảng của nó (2):
  - ra: `services/clinic_config_service.py` ghi `service_price` (của `catalogue` · chưa xét)
  - ra: `services/clinic_config_service.py` ghi `service_type` (của `catalogue` · chưa xét)
  - ra: `services/clinic_config_service.py` ghi `staff_node` (của `permission` · chưa xét)
  - ra: `services/config_service.py` ghi `appointment` (của `booking` · chưa xét)
  - ra: `services/config_service.py` ghi `drug_catalog` (của `catalogue` · chưa xét)
  - ra: `services/config_service.py` ghi `roster_week` (của `lich_truc` · chưa xét)
  - ra: `services/config_service.py` ghi `service_price` (của `catalogue` · chưa xét)
  - ra: `services/config_service.py` ghi `vai_duoc_vao_tram` (của `permission` · chưa xét)
  - ra: `services/config_service.py` ghi `work_roster` (của `lich_truc` · chưa xét)
  - ra: `services/config_service.py` ghi `work_roster_thay_nguoi` (của `lich_truc` · chưa xét)
  - ra: `services/day_noi_service.py` ghi `day_nhan_thong_bao` (của `chuong` · chưa xét)
  - ra: `services/day_noi_service.py` ghi `service_type` (của `catalogue` · chưa xét)
  - ra: `services/day_noi_service.py` ghi `vai_duoc_vao_tram` (của `permission` · chưa xét)
  - ra: `services/day_noi_service.py` ghi `vi_tri_lam_viec` (của `lich_truc` · chưa xét)
  - vào: `services/kho_thuoc_service.py` (`pharmacy`) ghi `clinic_location` · chưa xét
  - vào: `services/lo_thuoc_service.py` (`pharmacy`) ghi `clinic` · chưa xét

### `ho_so_khach` — Hồ sơ khách (thông tin, số điện thoại, đồng ý dữ liệu)

- **Giữ bảng:** `patient`, `patient_sdt_them`, `patient_link`, `clinical_data_consent`
- **Tệp code** (`src/clinicai/`): `services/consent_service.py`, `services/patient_service.py`
- **Màn gọi tới:** `/appointments`, `/ban-kham`, `/ban-kham/[phong]`, `/customers`, `/patient-list`, `/patients/new`, `/tu-van`
- **Test canh:** `test_patient_integration.py`, `test_patient_service.py`, `test_tran_khong_cat_im_lang.py`, `test_clinical_cluster.py`, `test_consent.py`
- **Nợ ghi chéo** — khối này ghi bảng khối khác (0), khối khác ghi bảng của nó (3):
  - vào: `services/booking_service.py` (`booking`) ghi `patient` · chưa xét
  - vào: `services/nhap_lich_su_notion.py` (`van_hanh`) ghi `patient` · chưa xét
  - vào: `services/thu_tu_kham_service.py` (`reception`) ghi `patient` · chưa xét

## 3. Màn → khối (90)

Khối suy từ service mà màn gọi (qua API). `—` = màn tĩnh, hoặc service của
nó chưa khai khối (mục 5).

| Màn | Tiêu đề | Khối |
|---|---|---|
| `/` |  | — |
| `/appointments` | Đặt lịch | booking, co_so, cskh, ho_so_khach |
| `/appointments/cho-xep-bac-si` | Chờ xếp bác sĩ | booking, cskh |
| `/audit-log` | Lịch sử thao tác | — |
| `/ban-kham` | Bàn khám | booking, consultation, cskh, dieu_tri, doi_tac, execution, ho_so_khach, lieu_trinh, phi_kham, reception, result, result_file, service_order, service_routing, service_selection, thai_ky, trach_nhiem, vat_tu |
| `/ban-kham/[phong]` | Bàn khám | booking, consultation, cskh, dieu_tri, doi_tac, execution, ho_so_khach, lieu_trinh, phi_kham, reception, result, result_file, service_order, service_routing, service_selection, thai_ky, trach_nhiem, vat_tu |
| `/cashier` |  | — |
| `/cashier/board` |  | — |
| `/cashier/dich-vu` | Bảng giá dịch vụ & phòng | co_so |
| `/cashier/thuoc` | Bảng giá thuốc | co_so |
| `/chon-co-so` |  | — |
| `/console` | Bảng điều khiển | — |
| `/cskh-tasks` |  | — |
| `/customers` | Quản lý khách hàng | booking, chuong, co_so, cskh, dieu_tri, ho_so_khach, ke_toan, lieu_trinh, reception, result, result_file, service_order, trach_nhiem |
| `/design-system` | ClinicAI — Hệ thiết kế | — |
| `/display` |  | — |
| `/do-sinh-hieu` | Đo sinh hiệu | consultation, doi_tac, execution, phi_kham, result_file, service_order, service_routing, service_selection, trach_nhiem, vat_tu, vitals |
| `/doctor/board` |  | — |
| `/doctor/orders/[visitId]` |  | — |
| `/doi-tac` | Việc của đối tác | chuong, co_so, consultation, doi_tac, execution, phi_kham, result, result_file, service_order, service_routing, service_selection, van_hanh, vat_tu |
| `/duyet-ket-qua` | Duyệt kết quả | consultation, doi_tac, execution, phi_kham, result, result_file, service_order, service_routing, service_selection, vat_tu |
| `/episodes` |  | — |
| `/forgot-password` |  | — |
| `/giam-sat` | Trung tâm giám sát | van_hanh |
| `/hanh-trinh` | Hành trình khách hôm nay | cong_no, consultation, execution, payment, phi_kham, reception, service_order, service_routing, service_selection, vat_tu |
| `/hoa-don` | Danh sách hoá đơn | co_so, ke_toan |
| `/home` | Trang chủ | booking, consultation, cskh, execution, phi_kham, service_order, service_routing, service_selection, vat_tu |
| `/ke-toan` | Kế toán | ke_toan |
| `/kham/[loai]` |  | — |
| `/kho-vat-tu` | Kho vật tư | catalogue, co_so, kho_vat_tu |
| `/lab-queue` |  | — |
| `/lich-do-ve` | Lịch đổ về | — |
| `/login` |  | van_hanh |
| `/luot-kham` |  | — |
| `/nhac-tai-kham` | Nhắc tái khám | booking, cskh, lieu_trinh |
| `/nhan-su` | Quản lý nhân sự | co_so, permission |
| `/ops` | Vận hành hệ thống | — |
| `/ops/telemetry` |  | — |
| `/patient-list` | Danh sách bệnh nhân | booking, consultation, cskh, dieu_tri, execution, ho_so_khach, phi_kham, reception, result, result_file, service_order, service_routing, service_selection, trach_nhiem, vat_tu |
| `/patients/[id]` |  | — |
| `/patients/new` | Tạo bệnh nhân | booking, co_so, cskh, ho_so_khach |
| `/phan-quyen` | Phân quyền | permission |
| `/pharmacy` | Cấp thuốc | consultation, doi_tac, execution, ke_toan, payment, pharmacy, phi_kham, result_file, service_order, service_routing, service_selection, trach_nhiem, vat_tu |
| `/pharmacy/consult` | Tư vấn dùng thuốc | pharmacy |
| `/pharmacy/history` | Lịch sử bàn giao | pharmacy |
| `/pharmacy/inventory` | Kho thuốc | pharmacy |
| `/phong` | Phòng dịch vụ | consultation, execution, phi_kham, service_order, service_routing, service_selection, vat_tu |
| `/phong/[ma]` |  | consultation, doi_tac, execution, lieu_trinh, phi_kham, result, result_file, service_order, service_routing, service_selection, trach_nhiem, vat_tu |
| `/portal` |  | — |
| `/print/[appointmentId]` |  | consultation |
| `/print/hoa-don-thuoc/[visitId]` | In hoá đơn thuốc | — |
| `/print/ket-qua-luot/[visitId]` | In kết quả | consultation, result |
| `/print/ket-qua/[orderId]` |  | result, result_file |
| `/print/phieu-kham/[visitId]` |  | consultation, dieu_tri, result, result_file, service_order |
| `/print/phieu-thu/[id]` | In phiếu thu | consultation, execution, phi_kham, service_order, service_routing, service_selection, vat_tu |
| `/print/sono/[id]` |  | — |
| `/print/tem-lo` | In tem lô thuốc | pharmacy |
| `/queue` |  | — |
| `/reception/checkout` | Check-out lượt khám | cong_no, payment, reception |
| `/reception/queue` | Tiếp đón khách | booking, cong_no, consultation, cskh, execution, lieu_trinh, payment, phi_kham, reception, service_order, service_routing, service_selection, vat_tu |
| `/reports` | Báo cáo | co_so, payment |
| `/reset-password` |  | — |
| `/result-review` |  | — |
| `/schedule` | Lịch làm việc | co_so, permission |
| `/service-queue` |  | — |
| `/settings` | Cài đặt | co_so |
| `/settings/booking-policy` | Luật đặt lịch | booking, co_so |
| `/settings/clinic-config` | Cấu trúc phòng khám | co_so, lich_truc |
| `/settings/day-noi` | Dây nối nghiệp vụ | co_so, service_order |
| `/settings/don-du-lieu-thu` | Dọn dữ liệu thử | — |
| `/settings/mau-ket-qua` | Mẫu kết quả | catalogue, result |
| `/settings/new-user` |  | permission |
| `/settings/tai-khoan` | Thiết lập tài khoản cho nhân viên | permission |
| `/sieu-am` |  | — |
| `/sono` |  | — |
| `/tasks` |  | — |
| `/thu-ngan/dich-vu` | Thu ngân dịch vụ | cong_no, consultation, execution, ke_toan, payment, pharmacy, phi_kham, reception, service_order, service_routing, service_selection, vat_tu |
| `/thu-ngan/dich-vu/lich-su` | Lịch sử thu dịch vụ | cong_no, consultation, execution, ke_toan, payment, pharmacy, phi_kham, reception, service_order, service_routing, service_selection, vat_tu |
| `/thu-ngan/thuoc` | Thu ngân thuốc | cong_no, consultation, execution, ke_toan, payment, pharmacy, phi_kham, reception, service_order, service_routing, service_selection, vat_tu |
| `/thu-ngan/thuoc/lich-su` | Lịch sử thu thuốc | cong_no, consultation, execution, ke_toan, payment, pharmacy, phi_kham, reception, service_order, service_routing, service_selection, vat_tu |
| `/traffic` |  | — |
| `/truong-ca` | Điều phối ca | consultation, execution, phi_kham, service_order, service_routing, service_selection, vat_tu |
| `/truong-ca/hang-doi` |  | — |
| `/truong-ca/lich-su` | Lịch sử điều phối | service_routing |
| `/truong-ca/tv` | TV phòng chờ | service_routing |
| `/tu-van` | Bàn khám tư vấn | booking, consultation, cskh, dieu_tri, doi_tac, execution, ho_so_khach, lieu_trinh, phi_kham, reception, result, result_file, service_order, service_routing, service_selection, thai_ky, trach_nhiem, vat_tu |
| `/viec-can-xu-ly` | Việc cần xử lý | trach_nhiem |
| `/work-sessions` |  | — |
| `/xac-nhan-ket-qua` | Xác nhận kết quả | result, result_file |
| `/xuat-hoa-don` | Xuất hoá đơn | ke_toan |

## 4. Bảng → khối (129)

- `agent_cau_hinh` → `van_hanh` (Vận hành, báo cáo, lịch sử thao tác)
- `anh_chuyen_khoan` → `payment` (Thu tiền dịch vụ)
- `app_credential` → `permission` (Phân quyền)
- `appointment` → `booking` (Đặt lịch)
- `appointment_doi_lich` → `booking` (Đặt lịch)
- `capability_grant` → `permission` (Phân quyền)
- `care_episode` → `booking` (Đặt lịch)
- `chot_so_ca` → `payment` (Thu tiền dịch vụ)
- `clinic` → `co_so` (Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối))
- `clinic_floor` → `co_so` (Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối))
- `clinic_location` → `co_so` (Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối))
- `clinic_membership` → `permission` (Phân quyền)
- `clinic_room` → `co_so` (Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối))
- `clinic_room_node` → `co_so` (Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối))
- `clinic_room_service` → `co_so` (Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối))
- `clinical_data_consent` → `ho_so_khach` (Hồ sơ khách (thông tin, số điện thoại, đồng ý dữ liệu))
- `clinical_form_response` → `result` (Biểu mẫu kết quả)
- `clinical_record` → `consultation` (Khám bệnh)
- `clinical_release` → `consultation` (Khám bệnh)
- `cong_no` → `cong_no` (Công nợ khách (chặn check-out còn nợ))
- `consultation` → `consultation` (Khám bệnh)
- `consultation_note` → `consultation` (Khám bệnh)
- `cskh_action` → `cskh` (Chăm sóc khách hàng)
- `cskh_log` → `cskh` (Chăm sóc khách hàng)
- `day_nghiep_vu` → `co_so` (Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối))
- `day_nhan_thong_bao` → `chuong` (Chuông thông báo)
- `dich_vu_mau_ket_qua` → `catalogue` (Danh mục & biểu mẫu)
- `dispatch_threshold` → `service_routing` (Điều phối khách)
- `doctor_booking_override` → `booking` (Đặt lịch)
- `doi_tac_nhan_viec` → `doi_tac` (Đối tác)
- `doi_tac_thanh_toan` → `doi_tac` (Đối tác)
- `drug_batch` → `pharmacy` (Quầy thuốc)
- `drug_catalog` → `catalogue` (Danh mục & biểu mẫu)
- `drug_ma_vach` → `pharmacy` (Quầy thuốc)
- `drug_return` → `pharmacy` (Quầy thuốc)
- `encounter_flow` → `hanh_trinh` (Hành trình lượt khám (Process Manager))
- `follow_up_case` → `trach_nhiem` (Trách nhiệm không được rơi)
- `form_definition` → `catalogue` (Danh mục & biểu mẫu)
- `form_instance` → `result` (Biểu mẫu kết quả)
- `ghi_chu_khach` → `cskh` (Chăm sóc khách hàng)
- `hen_goi_lai` → `cskh` (Chăm sóc khách hàng)
- `hoa_don_cong_ty` → `ke_toan` (Kế toán — xem tài chính đầy đủ, hoá đơn, theo hàng hoá)
- `hoa_don_cong_ty_lich_su` → `ke_toan` (Kế toán — xem tài chính đầy đủ, hoá đơn, theo hàng hoá)
- `hoa_don_misa_xuat` → `ke_toan` (Kế toán — xem tài chính đầy đủ, hoá đơn, theo hàng hoá)
- `hoa_don_misa_xuat_dong` → `ke_toan` (Kế toán — xem tài chính đầy đủ, hoá đơn, theo hàng hoá)
- `inventory_txn` → `pharmacy` (Quầy thuốc)
- `ket_qua_mau` → `catalogue` (Danh mục & biểu mẫu)
- `khach_cong_ty` → `ke_toan` (Kế toán — xem tài chính đầy đủ, hoá đơn, theo hàng hoá)
- `kiem_ke_ca` → `pharmacy` (Quầy thuốc)
- `kiem_ke_ca_dong` → `pharmacy` (Quầy thuốc)
- `ky_nang` → `permission` (Phân quyền)
- `lab_result` → `lab` (Xét nghiệm nhập tay)
- `lam_them_tai_quay` → `service_order` (Chỉ định dịch vụ)
- `lam_them_tai_quay_revision` → `service_order` (Chỉ định dịch vụ)
- `lieu_trinh` → `lieu_trinh` (Liệu trình điều trị nhiều buổi)
- `lieu_trinh_buoi` → `lieu_trinh` (Liệu trình điều trị nhiều buổi)
- `lieu_trinh_lich_su` → `lieu_trinh` (Liệu trình điều trị nhiều buổi)
- `lieu_trinh_tra_truoc` → `lieu_trinh` (Liệu trình điều trị nhiều buổi)
- `luat_bac_si_bat_buoc` → `booking` (Đặt lịch)
- `luot_ghi_chu` → `dieu_tri` (Điều trị theo lịch đặt + đổi dịch vụ trong hồ sơ)
- `luot_phi_kham` → `phi_kham` (Dịch vụ khám (tiền khám))
- `luot_phu_thu` → `service_order` (Chỉ định dịch vụ)
- `luot_vat_tu` → `vat_tu` (Bán thêm vật tư)
- `ngoai_le_ca_truc` → `permission` (Phân quyền)
- `nhac_tai_kham` → `cskh` (Chăm sóc khách hàng)
- `nhac_viec_ca_nhan` → `trach_nhiem` (Trách nhiệm không được rơi)
- `nhan_su_ky_nang` → `permission` (Phân quyền)
- `patient` → `ho_so_khach` (Hồ sơ khách (thông tin, số điện thoại, đồng ý dữ liệu))
- `patient_link` → `ho_so_khach` (Hồ sơ khách (thông tin, số điện thoại, đồng ý dữ liệu))
- `patient_medical_profile` → `consultation` (Khám bệnh)
- `patient_sdt_them` → `ho_so_khach` (Hồ sơ khách (thông tin, số điện thoại, đồng ý dữ liệu))
- `payment` → `payment` (Thu tiền dịch vụ)
- `payment_bill_line` → `payment` (Thu tiền dịch vụ)
- `payment_cycle` → `payment` (Thu tiền dịch vụ)
- `payment_cycle_doi_hinh_thuc` → `payment` (Thu tiền dịch vụ)
- `payment_cycle_phan` → `payment` (Thu tiền dịch vụ)
- `payment_refund` → `payment` (Thu tiền dịch vụ)
- `payment_refund_line` → `payment` (Thu tiền dịch vụ)
- `phan_hoi_khach` → `cskh` (Chăm sóc khách hàng)
- `phieu_kham_luot` → `consultation` (Khám bệnh)
- `phieu_kho` → `pharmacy` (Quầy thuốc)
- `phieu_kho_dong` → `pharmacy` (Quầy thuốc)
- `pregnancy` → `thai_ky` (Theo dõi thai kỳ)
- `prescription` → `consultation` (Khám bệnh)
- `prescription_allocation` → `pharmacy` (Quầy thuốc)
- `prescription_correction` → `pharmacy` (Quầy thuốc)
- `queue_entry` → `service_routing` (Điều phối khách)
- `quyen_preset` → `permission` (Phân quyền)
- `result_correction` → `result` (Biểu mẫu kết quả)
- `review_round` → `vong_doc` (Vòng đọc kết quả + khép lượt)
- `roster_week` → `lich_truc` (Lịch làm việc)
- `round_requirement` → `vong_doc` (Vòng đọc kết quả + khép lượt)
- `service_execution_attempt` → `execution` (Thực hiện dịch vụ)
- `service_order` → `service_order` (Chỉ định dịch vụ)
- `service_price` → `catalogue` (Danh mục & biểu mẫu)
- `service_selection_state` → `service_selection` (Khách chọn dịch vụ)
- `service_type` → `catalogue` (Danh mục & biểu mẫu)
- `slot_booking_override` → `booking` (Đặt lịch)
- `so_no` → `so_no` (Sổ nợ hai chiều (phải thu / phải trả theo lượt))
- `so_no_moc` → `so_no` (Sổ nợ hai chiều (phải thu / phải trả theo lượt))
- `so_sua_chi_dinh` → `service_order` (Chỉ định dịch vụ)
- `staff` → `permission` (Phân quyền)
- `staff_node` → `permission` (Phân quyền)
- `tep_ket_qua` → `result_file` (Tệp kết quả)
- `thong_bao` → `chuong` (Chuông thông báo)
- `thong_bao_an_cua_toi` → `chuong` (Chuông thông báo)
- `thu_ky_bac_si` → `lich_truc` (Lịch làm việc)
- `thue_suat_nhom` → `ke_toan` (Kế toán — xem tài chính đầy đủ, hoá đơn, theo hàng hoá)
- `thuoc_giao_chua_gan_lo` → `pharmacy` (Quầy thuốc)
- `thuoc_quy_doi` → `pharmacy` (Quầy thuốc)
- `tien_thua_giu_lai` → `payment` (Thu tiền dịch vụ)
- `tuong_tac_cskh` → `cskh` (Chăm sóc khách hàng)
- `ultrasound_record` → `result` (Biểu mẫu kết quả)
- `vai_duoc_vao_tram` → `permission` (Phân quyền)
- `vat_tu_goi_y` → `vat_tu` (Bán thêm vật tư)
- `vat_tu_nhap_cho_duyet` → `kho_vat_tu` (Kho vật tư (phiếu kho, tồn theo nơi chứa, mức tối thiểu))
- `vat_tu_phieu` → `kho_vat_tu` (Kho vật tư (phiếu kho, tồn theo nơi chứa, mức tối thiểu))
- `vat_tu_ton` → `kho_vat_tu` (Kho vật tư (phiếu kho, tồn theo nơi chứa, mức tối thiểu))
- `vat_tu_txn` → `kho_vat_tu` (Kho vật tư (phiếu kho, tồn theo nơi chứa, mức tối thiểu))
- `vi_tri_lam_viec` → `lich_truc` (Lịch làm việc)
- `visit` → `reception` (Tiếp đón)
- `visit_amendment` → `consultation` (Khám bệnh)
- `visit_gate_override` → `service_routing` (Điều phối khách)
- `visit_route` → `service_routing` (Điều phối khách)
- `vital_measurement` → `vitals` (Sinh hiệu)
- `work_item` → `trach_nhiem` (Trách nhiệm không được rơi)
- `work_item_event` → `trach_nhiem` (Trách nhiệm không được rơi)
- `work_roster` → `lich_truc` (Lịch làm việc)
- `work_roster_thay_nguoi` → `lich_truc` (Lịch làm việc)

Bảng kỹ thuật (không thuộc khối nào — `BANG_KY_THUAT`):
- `agent_nhan_dinh` — agent giám sát (shadow)
- `agent_tom_tat` — agent giám sát (shadow)
- `canh_bao` — bộ canh gác
- `command_receipt` — biên nhận lệnh (idempotency)
- `domain_event` — sổ sự kiện chung — mọi khối ghi qua emit_event
- `event_delivery` — dòng giao sự kiện — emit_event ghi cùng giao dịch
- `event_log` — sổ cũ (record_event)
- `hen_gio` — hẹn giờ của bên nghe
- `idempotency_key` — khoá chống bấm hai lần
- `lan_don_du_lieu_thu` — sổ các lần dọn dữ liệu thử
- `llm_lan_goi` — sổ lượt gọi model
- `loi_nhom` — kho lỗi
- `luot_dong_thoi_gian` — dòng thời gian lượt — khối journey dựng từ sự kiện
- `mpi_merge_queue` — CHỜ BỎ — chỉ ghi, không ai đọc
- `nhat_ky_van_hanh` — nhật ký vận hành
- `owner_feedback` — góp ý của chủ phòng khám
- `pos_outbox` — hộp thư đi sang máy POS
- `service_log` — CHỜ BỎ — /api/service-log tắt từ 24/09
- `service_order_draft` — CHỜ BỎ — đường nháp chỉ định tắt từ 24/09
- `slot_hold` — giữ chỗ tạm lúc đặt lịch
- `staff_task` — CHỜ BỎ — còn triage xét nghiệm ghi, gỡ chỗ ấy trước
- `work_session` — CHỜ BỎ — lịch thật đã sang work_roster
- `work_session_staff` — CHỜ BỎ — lịch thật đã sang work_roster

## 5. Service có màn dùng nhưng chưa khai khối (56)

Phần lớn là tệp CHỈ ĐỌC (luật lego chỉ bắt khai tệp có ghi database). Thêm
vào `TEP_CUA_KHOI` khi biết rõ khối — bản đồ sẽ tự xếp chúng vào đúng khối.

- `services/agent_tom_tat.py`
- `services/andrology_review_service.py`
- `services/audit.py`
- `services/audit_log_service.py`
- `services/ban_thuoc_service.py`
- `services/bang_hanh_trinh_service.py`
- `services/bao_cao_cuoi_ngay_service.py`
- `services/canh_gac.py`
- `services/capacity_service.py`
- `services/cashier_board_service.py`
- `services/cashier_navigation_service.py`
- `services/cashier_scope_service.py`
- `services/console_service.py`
- `services/danh_muc_dich_vu_service.py`
- `services/danh_sach_benh_nhan_service.py`
- `services/danh_sach_hoa_don_service.py`
- `services/danh_sach_khach_cskh.py`
- `services/day_tep.py`
- `services/dich_vu_dat_lich.py`
- `services/dieu_tri_ban_kham.py`
- `services/display_board_service.py`
- `services/doi_dich_vu_kham.py`
- `services/doi_lich_nhanh.py`
- `services/don_du_lieu_thu_service.py`
- `services/excel_export.py`
- `services/hanh_trinh_khach_service.py`
- `services/ho_so_kham_service.py`
- `services/ho_so_lam_sang_doc.py`
- `services/kho_loi.py`
- `services/lich_hen_doc.py`
- `services/lich_phong_service.py`
- `services/lich_su_luot.py`
- `services/lich_su_notion_service.py`
- `services/lich_tai_kham_service.py`
- `services/lich_truc_co_so.py`
- `services/lich_truc_phien_ban_service.py`
- `services/luot_kham_doc.py`
- `services/man_dat_lich_doc.py`
- `services/man_khach_hang_service.py`
- `services/man_trang_chu_service.py`
- `services/mpi_service.py`
- `services/nhan_tep_luong.py`
- `services/nhat_ky_van_hanh.py`
- `services/ops_status.py`
- `services/payment_access_service.py`
- `services/quay_thu_service.py`
- `services/reports_service.py`
- `services/slot_hold_service.py`
- `services/theo_hang_hoa_service.py`
- `services/tiep_don_service.py`
- `services/tong_quan_giam_sat.py`
- `services/traffic_service.py`
- `services/vat_tu_tieu_hao_service.py`
- `services/week_appointments_service.py`
- `services/xem_luot_service.py`
- `services/xuat_hoa_don_service.py`
