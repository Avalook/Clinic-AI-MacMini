-- Tên phòng / vị trí siêu âm KHÔNG ghi tầng (Tuyền chốt 17/09/2026): quản lý đã
-- xếp ai ngồi đâu, người đứng vị trí tự biết chỗ. Đánh số 1–2–3 khớp "BS Siêu âm
-- 1/2/3" trong bảng phân công theo đầu mục của phòng khám. Cột `tang` giữ nguyên
-- (bảng lịch vẫn gom theo tầng như file Excel).
UPDATE public.clinic_room SET name = 'Phòng siêu âm 1', updated_at = now() WHERE code = 'KN-SA-T1';
UPDATE public.clinic_room SET name = 'Phòng siêu âm 2', updated_at = now() WHERE code = 'KN-SA1';
UPDATE public.clinic_room SET name = 'Phòng siêu âm 3', updated_at = now() WHERE code = 'KN-SA2';

UPDATE public.vi_tri_lam_viec SET ten = 'BS siêu âm 1' WHERE code = 'T1_SA_BS';
UPDATE public.vi_tri_lam_viec SET ten = 'Điều dưỡng siêu âm 1' WHERE code = 'T1_SA_DD';
UPDATE public.vi_tri_lam_viec SET ten = 'BS siêu âm 2' WHERE code = 'T4_SA_BS1';
UPDATE public.vi_tri_lam_viec SET ten = 'Điều dưỡng siêu âm 2' WHERE code = 'T4_SA_DD1';
UPDATE public.vi_tri_lam_viec SET ten = 'BS siêu âm 3' WHERE code = 'T4_SA_BS2';
UPDATE public.vi_tri_lam_viec SET ten = 'Điều dưỡng siêu âm 3' WHERE code = 'T4_SA_DD2';
