-- Ca trực cho thao tác lâm sàng + ngoại lệ có lý do (phần A).
--
-- Công tắc này TÁCH HẲN `quyen_theo_lich`: dây cũ gác phòng dịch vụ, còn dây
-- mới chỉ gác việc làm thay bác sĩ. Mốc `sua_luc` của dòng được dùng để không
-- kẹt lượt đã bắt đầu trước lúc triển khai/bật lại dây.
-- Chạy lại được.

INSERT INTO public.day_nghiep_vu (clinic_id, ma, gia_tri, sua_luc)
SELECT id, 'ca_truc_lam_sang', 'true'::jsonb, now()
  FROM public.clinic
ON CONFLICT (clinic_id, ma) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.ngoai_le_ca_truc (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic (id) ON DELETE CASCADE,
    staff_id    uuid NOT NULL REFERENCES public.staff (id),
    ngay        date NOT NULL,
    bac_si_id   uuid REFERENCES public.staff (id),
    ly_do       text NOT NULL CHECK (length(btrim(ly_do)) BETWEEN 3 AND 500),
    mo_boi      uuid NOT NULL REFERENCES public.staff (id),
    mo_luc      timestamptz NOT NULL DEFAULT now(),
    huy_boi     uuid REFERENCES public.staff (id),
    huy_luc     timestamptz,
    CHECK ((huy_boi IS NULL) = (huy_luc IS NULL))
);

CREATE INDEX IF NOT EXISTS ix_ngoai_le_ca_truc_dang_mo
    ON public.ngoai_le_ca_truc (clinic_id, ngay, staff_id, bac_si_id)
    WHERE huy_luc IS NULL;

COMMENT ON TABLE public.ngoai_le_ca_truc IS
'Quản lý mở quyền làm thay bác sĩ ngoài ca, có lý do và huỷ được; không xoá lịch sử.';

ALTER TABLE public.ngoai_le_ca_truc ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ngoai_le_ca_truc_select_own_clinic
    ON public.ngoai_le_ca_truc;
CREATE POLICY ngoai_le_ca_truc_select_own_clinic
    ON public.ngoai_le_ca_truc FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));

GRANT SELECT, INSERT, UPDATE ON public.ngoai_le_ca_truc TO service_role;
