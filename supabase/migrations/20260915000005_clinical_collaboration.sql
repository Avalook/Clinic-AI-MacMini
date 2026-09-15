-- Full chart saves compare this revision while holding the visit/record locks.
-- A database trigger also covers vitals, signing, and other record writers.
ALTER TABLE public.clinical_record
    ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 1
    CHECK (revision > 0);

-- Secretary entries are stored on the chart until a physician approves them.
ALTER TABLE public.clinical_record
    ADD COLUMN IF NOT EXISTS prescription_draft jsonb;
ALTER TABLE public.prescription
    ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES public.staff(id);

CREATE OR REPLACE FUNCTION public.bump_clinical_record_revision()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
    NEW.revision := OLD.revision + 1;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_clinical_record_revision ON public.clinical_record;
CREATE TRIGGER trg_clinical_record_revision
    BEFORE UPDATE ON public.clinical_record
    FOR EACH ROW EXECUTE FUNCTION public.bump_clinical_record_revision();

-- Existing relay payload contains only table/clinic, never chart content.
DROP TRIGGER IF EXISTS trg_notify_clinical_record ON public.clinical_record;
CREATE TRIGGER trg_notify_clinical_record
    AFTER INSERT OR UPDATE OR DELETE ON public.clinical_record
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

DROP TRIGGER IF EXISTS trg_notify_patient_medical_profile ON public.patient_medical_profile;
CREATE TRIGGER trg_notify_patient_medical_profile
    AFTER INSERT OR UPDATE OR DELETE ON public.patient_medical_profile
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
