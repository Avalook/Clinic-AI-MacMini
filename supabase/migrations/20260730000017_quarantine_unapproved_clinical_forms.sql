-- Clinical safety: do not accept responses for forms that have no dedicated,
-- doctor-approved source specification.
--
-- NK was assembled from the male sections of the HMVS handover document and
-- explicitly carried TODO-BS-REVIEW. Keeping the catalogue row preserves any
-- historical responses while is_active=FALSE makes every new save fail closed.

UPDATE public.clinical_form_catalogue
   SET is_active = FALSE,
       updated_at = now()
 WHERE form_code = 'NK'
   AND is_active;

COMMENT ON COLUMN public.clinical_form_catalogue.is_active IS
  'FALSE preserves historical responses but blocks new saves; clinical forms '
  'must remain inactive until the clinic records doctor approval.';
