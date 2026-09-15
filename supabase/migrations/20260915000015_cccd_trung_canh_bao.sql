-- CCCD TRÙNG: CẢNH BÁO + LÝ DO, KHÔNG CHẶN CỨNG (15/09/2026).
--
-- LUẬT (Tuyền chốt 15/09): CCCD trùng hồ sơ khác thì cảnh báo và bắt ghi lý do.
-- Trước bản này `idx_patient_clinic_national_id_unique` (20260730000003) chặn
-- cứng ở DB, nên quầy không có đường nào tạo hồ sơ khi số CCCD đã bị ai đó nhập
-- nhầm từ trước — lỗi của hồ sơ cũ khoá luôn người thật đang đứng ở quầy.
--
-- patient_service kiểm trùng trước khi thêm, trả danh sách hồ sơ trùng, và chỉ
-- tạo khi có lý do (ghi vào event_log `patient.created`). Chỉ mục thường giữ
-- cho phép tra trùng vẫn nhanh. LƯU Ý (đo 15/09): MPI hiện KHÔNG chấm điểm CCCD
-- — hai hồ sơ trùng CCCD khác tên được 49 điểm, dưới ngưỡng xếp hàng gộp.

DROP INDEX IF EXISTS public.idx_patient_clinic_national_id_unique;
CREATE INDEX IF NOT EXISTS idx_patient_clinic_national_id
    ON public.patient (clinic_id, national_id_number)
    WHERE national_id_number IS NOT NULL;
