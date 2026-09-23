-- NHÓM 4 — kê đơn: thư ký y khoa = bác sĩ (Tuyền chốt 24/09/2026).
--
-- "Kê đơn thư ký = bác sĩ, không nháp, không duyệt (phòng khám cho phép). Đơn ghi
-- đúng NGƯỜI NHẬP, kèm BÁC SĨ CHÍNH của lượt."
--   người nhập   = prescription.created_by (đã có, nay ghi cả khi thư ký nhập)
--   bác sĩ chính = prescription.bac_si_chinh_id (mới) — CHỤP lúc ghi dòng, vì bác
--                  sĩ chính của lượt đổi được về sau mà đơn đã kê thì không.
--
-- Chạy lại được.

ALTER TABLE public.prescription
    ADD COLUMN IF NOT EXISTS bac_si_chinh_id uuid REFERENCES public.staff (id);

COMMENT ON COLUMN public.prescription.bac_si_chinh_id IS
'Bác sĩ chính của lượt lúc dòng đơn được ghi (trigger điền từ visit.attending_doctor_id). Người nhập ở created_by — thư ký y khoa nhập thay bác sĩ là chuyện thường.';

CREATE OR REPLACE FUNCTION public.don_thuoc_chup_bac_si_chinh()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NEW.bac_si_chinh_id IS NULL AND NEW.visit_id IS NOT NULL THEN
        SELECT v.attending_doctor_id INTO NEW.bac_si_chinh_id
          FROM public.visit v
         WHERE v.visit_id = NEW.visit_id AND v.clinic_id = NEW.clinic_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_don_thuoc_chup_bac_si_chinh ON public.prescription;
CREATE TRIGGER trg_don_thuoc_chup_bac_si_chinh
    BEFORE INSERT ON public.prescription
    FOR EACH ROW EXECUTE FUNCTION public.don_thuoc_chup_bac_si_chinh();

-- Dòng cũ: lấy bác sĩ chính hiện tại của lượt (không có gì tốt hơn để chụp).
UPDATE public.prescription rx
   SET bac_si_chinh_id = v.attending_doctor_id
  FROM public.visit v
 WHERE rx.bac_si_chinh_id IS NULL
   AND v.visit_id = rx.visit_id AND v.clinic_id = rx.clinic_id
   AND v.attending_doctor_id IS NOT NULL;
