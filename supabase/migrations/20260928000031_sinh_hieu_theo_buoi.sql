-- SINH HIỆU THEO BUỔI KHÁM (27/09/2026, đợt 3).
--
-- Góp ý phòng khám: "BN sau khi đăng kí thêm dịch vụ lần 2 trong buổi khám bị
-- auto chuyển sang Đo sinh hiệu → không cần đo sinh hiệu". Lượt thứ hai cùng
-- ngày của cùng khách nay DÙNG lần đo mới nhất của buổi (dây nghiệp vụ
-- `h1_cung_buoi_thang_dich_vu`, mặc định BẬT, khai trong `day_noi.py` — không
-- cần dòng dữ liệu).
--
-- Số đo KHÔNG chép sang lượt mới (một con số một chỗ sửa). Khối Hành trình (H1)
-- chỉ đặt `vitals_status = 'recorded'` và ghi lại LƯỢT NGUỒN ở cột dưới để truy
-- vết: "lượt này không tự đo — dùng số của lượt kia".
--
-- Không thêm bảng mới: cột nằm trên `encounter_flow` (đã có clinic_id + RLS/
-- tenant như cũ). Khoá ngoại ghép (clinic_id, visit) giữ lượt nguồn cùng phòng
-- khám; xoá lượt nguồn chỉ đặt NULL cột này (Postgres ≥ 15), không kéo theo.
-- Chạy lại được.

ALTER TABLE public.encounter_flow
    ADD COLUMN IF NOT EXISTS vitals_tu_visit_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'encounter_flow_vitals_tu_visit_fk'
           AND conrelid = 'public.encounter_flow'::regclass
    ) THEN
        ALTER TABLE public.encounter_flow
            ADD CONSTRAINT encounter_flow_vitals_tu_visit_fk
            FOREIGN KEY (clinic_id, vitals_tu_visit_id)
            REFERENCES public.visit (clinic_id, visit_id)
            ON DELETE SET NULL (vitals_tu_visit_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'encounter_flow_vitals_tu_visit_khac'
           AND conrelid = 'public.encounter_flow'::regclass
    ) THEN
        -- Nguồn là lượt KHÁC; lượt tự đo thì để trống.
        ALTER TABLE public.encounter_flow
            ADD CONSTRAINT encounter_flow_vitals_tu_visit_khac
            CHECK (vitals_tu_visit_id IS NULL OR vitals_tu_visit_id <> visit_id);
    END IF;
END $$;

COMMENT ON COLUMN public.encounter_flow.vitals_tu_visit_id IS
    'Lượt cùng buổi (cùng khách, cùng ngày giờ VN) có lần đo sinh hiệu mà lượt '
    'này dùng thay cho đo lại (dây H1 h1_cung_buoi_thang_dich_vu). NULL = lượt '
    'tự đo hoặc chưa đo. Chỉ để truy vết — số đo vẫn đọc từ vital_measurement.';
