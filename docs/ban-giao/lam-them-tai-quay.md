# Bàn giao — nhánh `claude/lam-them-tai-quay` (01/10/2026)

**Mục tiêu (Tuyền 01/10):** nút "+ Nước tiểu"… ở Tiếp đón + Đo sinh hiệu — tick là chỉ
định ngay, không cần bác sĩ; quản lý gắn / bớt nút; hiện trên hành trình khách.
**Đã tiếp quản 01/10/2026**: code + test mục tiêu đạt; đang chờ CI máy + PR.
## Đã làm
- Migration `20261002200000_lam_them_tai_quay.sql` (chạy lại được; **đã áp vào
  `chung_test_db` 55600 và `clinicai_thu_db`**): `service_order.consultation_id` bỏ
  NOT NULL, cột `nguon_lam_them` ('tiep_don'|'sinh_hieu'), CHECK "không phiên thì phải
  có nguồn quầy", chỉ mục duy nhất từng phần `uq_service_order_lam_them_song`, trigger
  `gan_lan_chi_dinh` cho việc quầy lan NULL; bảng `lam_them_tai_quay` (RLS đọc, notify,
  kiểm mã bảng giá) + seed CLS_NUOC_TIEU "Nước tiểu" bật cả hai nơi.
- `services/lam_them_tai_quay_service.py` `LamThemTaiQuayService`: `dat` (khoá visit;
  quyền `reception.checkin.perform` | `vitals.measure` theo màn), `nut_cho_luot`,
  `cau_hinh`/`luu_muc`/`bo_muc` (`config.wiring.manage`); thuần `trang_thai_nut`,
  `nhan_lam_them`, `doc_noi`. Router `routers/lam_them_tai_quay.py` (`/api/v1/lam-them/*`,
  đăng ký `main.py`); proxy `dashboard/app/api/lam-them/route.ts`.
- Sự kiện `service_order.desk_added`/`desk_removed` (catalogue, modules, whitelist
  dòng thời gian); `consumers/hanh_trinh.py` xếp phòng qua cửa làm khi `desk_added`.
- Nhãn "Làm thêm tại quầy …": `phieu_kham/hanh_trinh.py`, `hanh_trinh_khach_service.py`
  (thẻ, `gon.lam_them`, "chỉ định N" không tính việc quầy), `bang_hanh_trinh_service.py`,
  `service_selection_service.cho_khach_quyet` (không gán bác sĩ), `quay_thu_service.py`,
  `phieu_kham/ket_qua_chi_dinh.py`. `complete_consultation` NO_SERVICES không bị chặn.
- UI: `_lam-viec/LamThemTaiQuay.tsx` (`useLamThem`, `NutLamThem`) trong `QueueBoard.tsx`
  + `BangDoSinhHieu.tsx`; cấu hình `settings/day-noi/LamThemTaiQuayCauHinh.tsx`; chip ở
  `ChonDichVu.tsx`, `HoaDonMot.tsx`, `KetQuaChiDinh.tsx` (việc quầy hiện cùng lần đang
  mở), `HanhTrinhKhach.tsx`, `lib/hanh-trinh*.ts`. Docs: SITEMAP (mục B + day-noi),
  BAN-DO-SUA, BAN-DO-CODE (đã chạy `ban-do-code.py`).
- Test: unit `test_lam_them_tai_quay.py` 12 đạt; DB `test_lam_them_tai_quay_db.py` 11
  đạt; bộ DB liên quan 157/158 (bài `test_luot_khep_han_phat_visit_exam_completed_dung_mot_lan`
  đỏ khi chạy chung, chạy riêng xanh — lỗi thứ tự DB chung). ruff/mypy/tsc/eslint xanh.
- Bấm thật local (3202/8202, ảnh ở scratchpad `lt/`): tick → quầy thu thấy nhãn; bỏ
  tick → biến mất; ĐD tick ở 375; /hanh-trinh có nhãn; QL thêm "Lấy máu" hiện, tắt
  Nước tiểu ẩn (đã trả lại); 375 không tràn ngang.

## Bổ sung khi tiếp quản (Codex 01/10/2026)
- Migration mới `20261002210000_lam_them_tai_quay_xor.sql` (đã áp
  `chung_test_db`): ép một chỉ định thuộc **phiên bác sĩ XOR nguồn quầy**; không sửa
  migration cũ đã áp.
- Migration mới `20261002220000_lam_them_tai_quay_revision.sql` (đã áp
  `chung_test_db`): tombstone tăng đơn điệu theo lượt + dịch vụ, chặn lệnh cũ sau
  chuỗi thêm → bỏ (ABA).
- `bo_muc` đổi từ DELETE cứng sang tắt mềm: giữ nhãn/thứ tự/chỗ hiện và bật lại ngay.
  Đổi thứ tự hai dòng nay là một lệnh/một transaction, không còn lưu nửa vời.
- Tick/bỏ tick có `idempotency_key` + `expected_order_id/version`; lệnh cũ đến muộn
  không huỷ nhầm chỉ định mới. Tick lại cập nhật đúng người/nguồn/thời điểm mới.
- Dịch vụ đã làm/ghi không làm vẫn hiện đã tick và khoá, không trở thành nút “+”;
  `kham_xong` bỏ việc quầy khỏi quyết định/vòng đọc của bác sĩ.
- Danh sách >300 lượt được chia gói; UI cấu hình dùng `components/ui`; bổ sung nhãn
  audit. Test mục tiêu: unit/audit 34 đạt, frontend 2 đạt, DB tính năng 17 đạt.

## Còn lại (theo thứ tự)
1. `./scripts/ci-may.sh --bao-github`.
2. Mở PR vào `main` (bảng nút/link đã đụng + kịch bản dưới).
3. (Tuỳ chọn) nút ở bảng "Lịch hẹn" trên `/reception/queue` — cố ý chưa làm (dùng chung `/home`).

## Quyết định + lý do
- Việc quầy không gắn phiên khám: mọi màn đọc chỉ định theo lượt → tự đi quầy thu,
  FinanceGate, xếp phòng, phòng làm. Tick = `SELECTED`; quầy thu vẫn bỏ được.
- Bỏ tick chỉ khi chưa làm + chưa thu (đã thu → hoàn ở quầy thu; đã làm → Huỷ bắt
  đầu/Không làm ở phòng). Bỏ = huỷ (không xoá), chỗ chờ phòng huỷ, phụ thu đóng.
- Bác sĩ đã chỉ định cùng dịch vụ → quầy không chồng (ALREADY_ORDERED).
- Cấu hình ở `/settings/day-noi` để không đụng `/settings/clinic-config` (nhóm danh mục).

## Bẫy
- Turbopack từ chối `node_modules` symlink → `cp -cR` vào worktree.
- Worker sự kiện local chạy code `main`: bấm thử local, xếp phòng sau tick chỉ qua thu tiền.

## Kịch bản bấm thử staging
1. Lễ tân `/reception/queue`: check-in khách A → tick "+ Nước tiểu".
2. Thu ngân `/thu-ngan/dich-vu`: A có "Tổng phân tích nước tiểu" + chip "Làm thêm tại
   quầy tiếp đón"; thu → phòng Lấy mẫu thấy A.
3. Khách B lễ tân không tick → ĐD `/do-sinh-hieu` chọn B, tick → `/hanh-trinh` ghi "làm thêm tại quầy".
4. Bỏ tick khách C trước khi thu → dòng biến khỏi quầy thu.
5. QL `/settings/day-noi` → thêm "Xét nghiệm máu" (chữ "Lấy máu") → nút mới hiện;
   “Bỏ khỏi quầy” Nước tiểu → ẩn, rồi bật lại → giữ nguyên chữ/chỗ hiện/thứ tự.
SQL: `SELECT nguon_lam_them, exec_status, count(*) FROM service_order WHERE nguon_lam_them IS NOT NULL GROUP BY 1,2;`
