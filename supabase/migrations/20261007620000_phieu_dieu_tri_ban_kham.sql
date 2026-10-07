-- PHIẾU ĐIỀU TRỊ theo CHỈ ĐỊNH + LÀM TẠI BÀN KHÁM (Tuyền chốt 07/10/2026).
--
-- 1. "Phiếu điều trị" là PHIẾU KẾT QUẢ của chỉ định điều trị — dùng đúng bộ mẫu
--    kết quả có sẵn (`ket_qua_mau` + `form_definition` KQ_* + `form_instance`
--    một phiếu cho mỗi chỉ định), KHÔNG bảng riêng theo lượt. Mẫu
--    `PHIEU_DIEU_TRI`: hai ô chữ tự do "Cảm nhận", "Vấn đề sau điều trị".
--    Bàn khám và phòng dịch vụ mở CÙNG một phiếu (cùng `form_instance`, chống
--    đè bằng revision như mọi phiếu kết quả) — bên này ghi dở thì bên kia ghi
--    tiếp, không điền lại.
-- 2. Gắn mẫu cho dịch vụ của các loại khám nhóm ĐIỀU TRỊ — khớp qua
--    `service_type.service_price_id` (migration 20261007600000), không viết cứng
--    mã dịch vụ. Có hiệu lực mọi lúc chỉ định ấy tồn tại (bác sĩ kê hay lượt đặt
--    lịch Điều trị tự sinh), không phụ thuộc loại khám của lượt. Gắn thêm, không
--    gỡ mẫu nào quản lý đã gắn.
-- 3. `service_execution_attempt.noi_lam`: lần làm diễn ra Ở ĐÂU khi không phải
--    phòng của chỉ định. NULL = phòng như trước nay; 'BAN_KHAM' = bác sĩ làm luôn
--    tại bàn khám (`room_id_snapshot` = phòng bác sĩ). Màn phòng đọc cột này để
--    nói "đang làm ở bàn khám".
--    `gan_phong_ban_kham`: chỉ định CHƯA xếp phòng thì lần làm tại bàn khám xếp
--    nó vào phòng bác sĩ (cột cũ `exec_status` in_progress/performed BẮT BUỘC có
--    phòng — CHECK service_order_room_when_assigned; công nợ check-out, vòng
--    đọc, theo dõi thủ thuật còn đọc cột cũ). Hoàn tác Bắt đầu thì gỡ đúng phòng
--    đã xếp ấy (cờ này), không gỡ phòng quầy / trưởng ca đã xếp.
--
-- Chạy lại được.

INSERT INTO public.ket_qua_mau (clinic_id, ma, nhom, ten)
SELECT c.id, 'PHIEU_DIEU_TRI', 'Điều trị', 'Phiếu điều trị'
  FROM public.clinic c
ON CONFLICT (clinic_id, ma) DO NOTHING;

INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)
SELECT c.id, 'KQ_PHIEU_DIEU_TRI', 1, 'Phiếu điều trị', 'Điều trị',
       $khung$[
         {"ma": "cam_nhan", "ten": "Cảm nhận",
          "block": [{"ma": "cam_nhan", "ten": "Cảm nhận", "kieu": "doan_van"}]},
         {"ma": "van_de_sau", "ten": "Vấn đề sau điều trị",
          "block": [{"ma": "van_de_sau", "ten": "Vấn đề sau điều trị",
                     "kieu": "doan_van"}]}
       ]$khung$::jsonb,
       'PUBLISHED', NULL, now()
  FROM public.clinic c
 WHERE NOT EXISTS (SELECT 1 FROM public.form_definition d
                    WHERE d.clinic_id = c.id AND d.form_id = 'KQ_PHIEU_DIEU_TRI');

INSERT INTO public.dich_vu_mau_ket_qua (clinic_id, service_code, mau)
SELECT DISTINCT st.clinic_id, sp.service_code, 'PHIEU_DIEU_TRI'
  FROM public.service_type st
  JOIN public.service_price sp
    ON sp.id = st.service_price_id AND sp.clinic_id = st.clinic_id
 WHERE st.nhom = 'DIEU_TRI'
   AND EXISTS (SELECT 1 FROM public.ket_qua_mau m
                WHERE m.clinic_id = st.clinic_id AND m.ma = 'PHIEU_DIEU_TRI')
ON CONFLICT (clinic_id, service_code, mau) DO NOTHING;

ALTER TABLE public.service_execution_attempt
    ADD COLUMN IF NOT EXISTS noi_lam text;
ALTER TABLE public.service_execution_attempt
    DROP CONSTRAINT IF EXISTS service_execution_attempt_noi_lam;
ALTER TABLE public.service_execution_attempt
    ADD CONSTRAINT service_execution_attempt_noi_lam
    CHECK (noi_lam IS NULL OR noi_lam IN ('BAN_KHAM'));
ALTER TABLE public.service_execution_attempt
    ADD COLUMN IF NOT EXISTS gan_phong_ban_kham boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN public.service_execution_attempt.gan_phong_ban_kham IS
    'Lần làm tại bàn khám đã xếp chỉ định (chưa có phòng) vào phòng bác sĩ — hoàn tác Bắt đầu gỡ lại.';
COMMENT ON COLUMN public.service_execution_attempt.noi_lam IS
    'NULL = làm ở phòng của chỉ định; BAN_KHAM = bác sĩ làm tại bàn khám (07/10/2026).';
