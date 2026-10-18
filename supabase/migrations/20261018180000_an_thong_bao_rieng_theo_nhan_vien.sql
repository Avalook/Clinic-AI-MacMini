-- Ẩn thông báo khỏi chuông của một nhân viên mà không đóng việc chung theo vai.
CREATE TABLE IF NOT EXISTS public.thong_bao_an_cua_toi (
    clinic_id      uuid NOT NULL REFERENCES public.clinic (id) ON DELETE CASCADE,
    staff_id       uuid NOT NULL REFERENCES public.staff (id) ON DELETE CASCADE,
    thong_bao_id   uuid NOT NULL REFERENCES public.thong_bao (id) ON DELETE CASCADE,
    an_luc         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, staff_id, thong_bao_id)
);

COMMENT ON TABLE public.thong_bao_an_cua_toi IS
'Thông báo nhân viên tự ẩn khỏi chuông của mình. Không thay đổi trạng thái đã đọc/đã xử lý dùng chung theo vai.';

ALTER TABLE public.thong_bao_an_cua_toi ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS thong_bao_an_cua_toi_service_clinic
    ON public.thong_bao_an_cua_toi;
DROP POLICY IF EXISTS thong_bao_an_cua_toi_service_read
    ON public.thong_bao_an_cua_toi;
CREATE POLICY thong_bao_an_cua_toi_service_read
    ON public.thong_bao_an_cua_toi
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));

GRANT SELECT, INSERT ON public.thong_bao_an_cua_toi TO service_role;
