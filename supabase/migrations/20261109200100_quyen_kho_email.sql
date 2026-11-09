-- QUYỀN XEM KHO EMAIL KẾT QUẢ (TẠM) — Gmail G1 (docs/KE-HOACH-KET-QUA-QUA-GMAIL.md mục 1.7).
--
-- Kho chứa MỌI thư kết quả đối tác gửi về Gmail (cả thư cũ, chưa ghép) — dữ liệu sức khoẻ.
-- "Kho tạm để mình tôi xem" (Tuyền 09/11): khối KHÔNG nằm trong nhóm mẫu nào (kể cả Quản lý),
-- KHÔNG nằm trong "mở full"; chỉ cấp riêng từng người ở màn Phân quyền. Mỗi lần mở PDF ghi
-- sự kiện `lab.archive_viewed` (khai ở G2, cùng code phát). Bỏ Kho = thu quyền (dữ liệu giữ).
--
-- Chạy lại được (ON CONFLICT), không BEGIN/COMMIT. Không cấp cho ai ở đây.

INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('kho_email', 'Kho email kết quả (tạm)', 'partner',
     'Xem mọi thư kết quả đối tác gửi về Gmail phòng khám — chỉ cấp riêng từng người')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('xet_nghiem.kho_email', 'Xem Kho email kết quả xét nghiệm đối tác', 'kho_email',
     'partner', 'clinical', false)
ON CONFLICT (ma) DO NOTHING;
