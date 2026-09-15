-- THƯ KÝ Y KHOA ĐI THEO BÁC SĨ — QUẢN LÝ PHÂN (15/09/2026).
--
-- Tuyền chốt: thư ký đi theo bác sĩ, không theo ca; "thư ký nào đi cùng bác sĩ
-- nào sẽ được phân". Trước bản này không có bảng ghép người–người nào
-- (`staff_node` là người–bước; `work_roster.bac_si_phu_trach_id` theo từng ca
-- và không ai đọc), nên mọi màn của thư ký thấy khách của CẢ phòng khám.
--
-- Một thư ký có thể theo nhiều bác sĩ và ngược lại. Thư ký CHƯA được phân ai
-- thì KHÔNG thấy, không làm được khách nào ("không được làm việc của bác sĩ
-- khác") — xem clinicai/services/thu_ky_bac_si.py.

CREATE TABLE IF NOT EXISTS public.thu_ky_bac_si (
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    thu_ky_staff_id  uuid NOT NULL REFERENCES public.staff(id) ON DELETE CASCADE,
    bac_si_staff_id  uuid NOT NULL REFERENCES public.staff(id) ON DELETE CASCADE,
    phan_boi         uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    phan_luc         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, thu_ky_staff_id, bac_si_staff_id),
    CONSTRAINT thu_ky_bac_si_khac_nguoi CHECK (thu_ky_staff_id <> bac_si_staff_id)
);

CREATE INDEX IF NOT EXISTS idx_thu_ky_bac_si_bac_si
    ON public.thu_ky_bac_si (clinic_id, bac_si_staff_id);

COMMENT ON TABLE public.thu_ky_bac_si IS
    'Thư ký y khoa đi cùng bác sĩ nào — quản lý phân (20260915000020).';

ALTER TABLE public.thu_ky_bac_si ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS thu_ky_bac_si_select_own_clinic ON public.thu_ky_bac_si;
CREATE POLICY thu_ky_bac_si_select_own_clinic
    ON public.thu_ky_bac_si
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT ON public.thu_ky_bac_si TO authenticated;
GRANT ALL ON public.thu_ky_bac_si TO service_role;
