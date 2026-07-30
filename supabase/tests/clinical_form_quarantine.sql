\set ON_ERROR_STOP on

DO $assert_clinical_form_quarantine$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM public.clinical_form_catalogue
         WHERE form_code = 'NK'
           AND is_active
    ) THEN
        RAISE EXCEPTION
            'unapproved NK form must remain inactive until doctor approval';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM public.clinical_form_catalogue
         WHERE form_code = 'NK'
    ) THEN
        RAISE EXCEPTION
            'quarantine must preserve the catalogue row and old responses';
    END IF;
END
$assert_clinical_form_quarantine$;
