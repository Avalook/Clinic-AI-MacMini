-- The list of exam forms becomes data (ADR-0011 config-as-data, ADR-0012).
--
-- WHY. `clinical_form_response.service_code` holds a FORM code — PK, SK, NT,
-- HMVS, NK — not a service_type code. That is what the live system writes:
-- ClinicalRecordForm derives it with resolveServiceCode(service.name) and
-- ServiceFormEngine sends it. When the save moved to FastAPI, the backend had
-- no way to see lib/form-schemas, so it validated the code against the
-- service_type catalogue instead. The two vocabularies do not intersect, so
-- every save failed once CLINICAL_FORM_VIA_BACKEND was switched on: the
-- catalogue code is refused by Next, the UI's code is refused by FastAPI.
--
-- The fix is not to pick one of the two lists. It is to stop keeping the list
-- of forms somewhere the backend cannot read. The rows below are exactly the
-- keys of the REGISTRY in src/dashboard/lib/form-schemas/index.ts, so nothing
-- about which form a service uses changes: that mapping still lives in
-- resolveServiceCode(), by service name, exactly as today.
--
-- Rendering stays in the frontend. This table answers one question — "is this a
-- form this clinic uses?" — which is the question the backend was getting wrong.

CREATE TABLE IF NOT EXISTS public.clinical_form_catalogue (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid DEFAULT public.default_clinic_id() NOT NULL,
    -- Matches clinical_form_response.service_code. Upper-case by convention;
    -- the backend upper-cases before comparing.
    form_code text NOT NULL,
    title text NOT NULL,
    -- A clinic that stops offering a form keeps its old responses readable but
    -- cannot write new ones. Deleting the row would orphan history.
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT clinical_form_catalogue_pkey PRIMARY KEY (id),
    CONSTRAINT clinical_form_catalogue_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT uq_clinical_form_catalogue UNIQUE (clinic_id, form_code),
    CONSTRAINT clinical_form_catalogue_code_check
        CHECK (form_code = upper(form_code) AND length(form_code) BETWEEN 1 AND 32)
);

CREATE INDEX IF NOT EXISTS idx_clinical_form_catalogue_clinic
    ON public.clinical_form_catalogue (clinic_id) WHERE is_active;

COMMENT ON TABLE public.clinical_form_catalogue IS
  'Exam forms a clinic uses, keyed by the code stored in '
  'clinical_form_response.service_code. The frontend owns how a form renders; '
  'this owns whether it exists.';

-- Every clinic that exists today gets the five forms the pilot renders. A new
-- clinic is seeded by whoever onboards it — an empty catalogue means no exam
-- form can be saved, which is the honest default for a clinic nobody has
-- configured yet.
INSERT INTO public.clinical_form_catalogue (clinic_id, form_code, title)
SELECT c.id, f.form_code, f.title
  FROM public.clinic c
 CROSS JOIN (VALUES
        ('PK',   'Khám phụ khoa'),
        ('SK',   'Khám sản khoa'),
        ('NT',   'Khám nội tiết'),
        ('HMVS', 'Hiếm muộn / vô sinh'),
        ('NK',   'Khám nam khoa')
 ) AS f(form_code, title)
ON CONFLICT (clinic_id, form_code) DO NOTHING;

-- Read-only reference for signed-in staff, like the other catalogues; only the
-- backend writes it.
ALTER TABLE public.clinical_form_catalogue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS clinical_form_catalogue_select ON public.clinical_form_catalogue;
CREATE POLICY clinical_form_catalogue_select ON public.clinical_form_catalogue
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT ON public.clinical_form_catalogue TO authenticated;
GRANT ALL ON public.clinical_form_catalogue TO service_role;
