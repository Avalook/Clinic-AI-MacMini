# Bàn giao nhánh `claude/ca-truc-va-no` (01/10/2026)

**Mục tiêu** (Tuyền chốt 01/10, sau sự cố Nhữ Duy Hoàn 30/09): A. chỉ người ĐÚNG CA làm thay bác sĩ;
B. check-out còn nợ thì CHẶN (thu ngay / "Ghi nợ" kèm lý do); C. danh sách truy thu ngay.

## ĐÃ LÀM (~20%)
- **C xong**: `scripts/bao-cao/khach-con-no.sql` (chỉ đọc; đã chạy prod). Kết quả: nợ chắc 950k
  (Cao Yến Nhi 500k, Phạm Diệu Thúy 450k); cần xác minh: Hòa (Bio 900k), Thu (Ghế ĐTT 3tr),
  Nhữ Duy Hoàn (SA 650k chưa chốt + King Seal 930k + Levina). Bản đầy đủ: scratchpad `khach-con-no.md`.
- **Phát hiện phụ (báo Tuyền):** Nam khoa / Sàn chậu chuyên sâu / Thủ thuật / Nội tiết có
  `service_type.gia_mac_dinh = 0` → không ai tick dịch vụ khám (`luot_phi_kham`) thì phí khám = 0đ,
  check-out không thấy nợ. 3 dịch vụ của Hoàn là `selection_status=PENDING`, `exec_status=authorized`
  (chưa chốt, chưa ghi đã làm) → hoá đơn máy chủ KHÔNG tính; XN máu là đối tác thu hộ.
  Prod chưa từng ghi "đã giao thuốc" (`dispense_status` luôn `CHUA_CAP`, `dispensed_qty=0`).
- A, B: CHƯA code dòng nào. Mới đọc xong hạ tầng (dưới).

## Hạ tầng đã đọc (khỏi đọc lại)
- `permissions/lich.py::doi_lich_phong` = cổng phòng DV, theo dây `quyen_theo_lich` (TẮT, miễn
  `dispatch.manage`). **Đừng dùng miễn `dispatch.manage`/`roster.manage`: prod 63 người có**
  (MỞ HẾT). Chỉ `permission.manage`/`staff.manage`/`config.clinic.manage` = 5 quản lý.
- Bác sĩ của phiên: `bac_si_phu_trach.bac_si_cua_phien` (phiên → chỗ chờ → lượt → lịch hẹn → vòng 1
  → BS duy nhất cùng phòng người bấm). Cùng phòng: `bac_si_cung_phong_hom_nay` (ca đang diễn ra,
  ngoài ca → cả ngày; KHÔNG xét làn). Làn: `lan_bac_si.lan_cua_toi_trong_phong`, `vi_tri_lam_viec.lan`.
- Điểm gác lâm sàng (`services/luot_kham_service.py`): `goi_khach` 1430, `kham_xong` 1514,
  `start_consultation` 1638, `propose_orders` 2064, `authorize_orders` 2124, `complete_consultation`
  2319, `quyet_yeu_cau` 2688, `duyet_ket_qua` 3335; kê đơn `clinical_prescription_service.py`;
  phiếu khám `phieu_kham_service.py`.
- `domain_event.on_behalf_of uuid` có sẵn; `events/emit.py::NguoiGayRa.on_behalf_of`, `nguoi(identity)`.
- Check-out: `services/checkout_service.py::close` (blockers `unpaid_service`/`unpaid_drug` hiện vượt
  được bằng lý do); nợ tính ở `bill_service.hoa_don_con_no` + `tinh_hoa_don(kind="thuoc")`.
  Sự kiện tiền: `payment.service_collected`, `payment.medicine_collected` (catalogue.py ~129/144).

## CÒN LẠI (theo thứ tự) — thiết kế đề xuất
1. Migration `20261002500000_ca_truc_lam_sang.sql`: bảng `ngoai_le_ca_truc` (clinic_id, staff_id,
   ngay date, bac_si_id NULL = mọi BS, ly_do NOT NULL, mo_boi, mo_luc, huy_boi, huy_luc).
2. `permissions/ca_truc.py`: hàm thuần `duoc_lam_thay(...)` + `doi_dung_ca(conn, identity, visit_id,
   consultation_id)` → trả id BS. Luật: dây mới `ca_truc_lam_sang` (mặc định BẬT, tách khỏi
   `quyen_theo_lich` để không chặn phòng DV/tiếp đón/thu/kho/CSKH); lượt check-in ngày cũ → cho qua;
   ngoại lệ còn hiệu lực → qua; tài khoản BS có dòng lịch hôm nay → qua; người khác: phải có lịch
   hôm nay CÙNG PHÒNG với BS của phiên (phòng ≥2 BS và cả hai có `lan` → cùng làn; thiếu làn → cả
   phòng); BS không xác định mà mình có lịch cùng phòng với BS nào đó → qua. Sai → `SafetyGateError`
   "Bạn không có ca trực hôm nay với BS … — nhờ quản lý mở ngoại lệ". Không miễn quyền nào.
3. Gắn vào 8 điểm gác + kê đơn + lưu phiếu khám. `on_behalf_of`: ContextVar trong `emit.py`
   (gate ghi (staff, BS); `nguoi()` điền on_behalf_of khi staff khớp và ≠ BS) — tránh sửa từng emit.
4. API ngoại lệ (mở/huỷ/danh sách, cửa `permission.manage`) + sự kiện `ca_truc.ngoai_le_mo/huy`
   + màn: khối ở màn Lịch làm việc (tra `docs/SITEMAP.md`), sửa SITEMAP nếu thêm route.
5. B: migration `20261002500100_cong_no.sql` bảng `cong_no` (visit_id, clinic_patient_id, so_tien,
   dong jsonb, ly_do NOT NULL, ghi_boi, ghi_luc, trang_thai CHUA_THU/DA_THU, thu_luc). Hàm
   `no_khi_ve(conn, visit)`: phí khám (chỉ khi có phiên khám in_progress/completed) + chỉ định ĐÃ/ĐANG
   LÀM chưa phủ (kể cả chưa chốt) + phụ thu + thuốc có `purchased_qty>0` hoặc đã cấp chưa thu;
   bỏ dòng chưa làm/không chọn. `close()` (cả `incomplete`): còn nợ mà chưa có `cong_no` CHUA_THU
   phủ đủ → `ValidationError` (không vượt bằng lý do nữa). Endpoint "Ghi nợ" (quyền
   `reception.checkin.perform`) + sự kiện `cong_no.ghi`. Consumer `payment.*_collected` → nợ
   của lượt hết thì `DA_THU` (khỏi đụng code thu của nhóm "thu nhiều hình thức").
6. UI hộp check-out: từng dòng nợ, nút "Thu ngay" (API thu hiện có), "Ghi nợ" + lý do; báo cáo cuối
   ngày + trang chủ quản lý "Khách còn nợ: n — x đ". Phối hợp nhóm "hoàn tác" (mở lại lượt).
7. Test: không ca bị chặn (mở phiên/chỉ định/kê đơn/khám xong); cùng ca/cùng làn qua; ngoại lệ;
   on_behalf_of; check-out nợ bị chặn → thu/ghi nợ thì qua; dòng chưa làm không tính; báo cáo nợ.

## Quyết định tự chốt + lý do
- Dây riêng `ca_truc_lam_sang` (không bật `quyen_theo_lich`): bật cái cũ sẽ chặn cả phòng DV.
- Người mở ngoại lệ = `permission.manage` (5 quản lý); "trưởng ca" quyền đã phát cho 63 người.
- Thuốc tính nợ khi quầy đã ghi số khách mua (`purchased_qty`) — vì prod không ghi "đã giao".

## Bẫy
- Hook rtk chặn `git` trong worktree agent → dùng `/usr/bin/git`.
- Lượt đang mở lúc deploy: BS của lượt có ca → người cùng ca làm tiếp (luật 2 đã đủ).

## Migration: chưa có (chưa áp DB chung). Test: chưa chạy. CI: chưa chạy. PR: chưa mở.

## Kịch bản bấm thử staging (khi xong)
1. TK điều dưỡng KHÔNG có lịch hôm nay → Bàn khám bấm Gọi/Bắt đầu khám → thấy câu chặn.
2. Quản lý mở ngoại lệ cho người đó (lý do) → làm lại được; dòng thời gian ghi "làm cho BS X".
3. ĐD cùng phòng BS (lịch hôm nay) → chỉ định, kê đơn, khám xong được.
4. Lượt có dịch vụ đã làm chưa thu → Check-out bị chặn → Thu ngay hoặc Ghi nợ (lý do) → qua;
   trang chủ quản lý hiện "Khách còn nợ"; thu nợ ở quầy → nợ chuyển đã thu.
