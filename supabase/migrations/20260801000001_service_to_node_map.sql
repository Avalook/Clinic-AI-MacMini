-- Link a service to the workflow node that performs it.
--
-- The kernel has twelve DICHVU-* nodes, each already routed to a room and a
-- role (siêu âm → khu_sieu_am/ULTRASOUND_DOCTOR, lấy máu → khu_dieu_duong/
-- NURSE_ULTRASOUND, and so on). The price list has 29 services. Nothing
-- connected the two, so ordering a service could not put work in front of the
-- person who performs it — which is the entire reason the doctor's order screen
-- is worth building.
--
-- WHY A COLUMN AND NOT A RULE IN CODE. The mapping is clinic configuration, not
-- logic: a clinic that buys a DXA machine, or sends mammography out to a
-- partner instead of doing it in-house, changes where that service is performed
-- without changing this system. A prefix rule in Python would also quietly
-- swallow the case below that matters most.
--
-- WHAT IS DELIBERATELY LEFT NULL. Services with no obvious node keep node_code
-- NULL, and the order endpoint REFUSES them with a message naming the service.
-- The alternative — defaulting to some general node — creates a work item in
-- the wrong room, and the failure surfaces as a patient sitting outside a door
-- nobody is expecting them at. Unmapped is a question for the clinic to answer,
-- not something to guess.

ALTER TABLE public.service_price
    ADD COLUMN IF NOT EXISTS node_code text;

COMMENT ON COLUMN public.service_price.node_code IS
  'Which node_definition performs this service. NULL = not yet mapped; the '
  'order endpoint refuses to order it rather than guessing a room.';

-- Only a real, active node of this clinic may be named.
ALTER TABLE public.service_price
    DROP CONSTRAINT IF EXISTS service_price_node_code_known;
ALTER TABLE public.service_price
    ADD CONSTRAINT service_price_node_code_known CHECK (
        node_code IS NULL OR node_code ~ '^(DICHVU|KHAM)-[A-Z0-9-]+$'
    );

CREATE INDEX IF NOT EXISTS idx_service_price_node_code
    ON public.service_price (clinic_id, node_code)
    WHERE node_code IS NOT NULL;

-- ---------------------------------------------------------------------------
-- The rules, as a function.
-- ---------------------------------------------------------------------------
-- A bare UPDATE here would map nothing on a fresh database: `supabase db reset`
-- runs migrations first and seed.sql second, so at this point service_price is
-- empty. Existing installations have rows now (the call at the bottom maps
-- them); a fresh one gets them from seed.sql, which calls this afterwards. One
-- copy of the rules either way — the alternative was the same UPDATE pasted in
-- two files, drifting the first time a service moved room.
--
-- Also safe to re-run when a clinic adds services: every rule is guarded by
-- `node_code IS NULL`, so a deliberate manual mapping is never overwritten.
CREATE OR REPLACE FUNCTION public.map_services_to_nodes()
RETURNS integer
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
DECLARE
    mapped integer;
BEGIN
-- ---------------------------------------------------------------------------

-- Every ultrasound goes to the ultrasound room. Fifteen of the 29 services.
    UPDATE public.service_price SET node_code = 'DICHVU-SIEUAM'
     WHERE service_code LIKE 'CLS_SIEU_AM%' AND node_code IS NULL;

-- Specimen collection, split by what is collected — different room prep, and
-- in the case of the vaginal swab a different set of roles.
    UPDATE public.service_price SET node_code = 'DICHVU-LAYMAU-MAU'
     WHERE service_code = 'CLS_XET_NGHIEM_MAU' AND node_code IS NULL;
    UPDATE public.service_price SET node_code = 'DICHVU-LAYMAU-NUOCTIEU'
     WHERE service_code = 'CLS_NUOC_TIEU' AND node_code IS NULL;
    UPDATE public.service_price SET node_code = 'DICHVU-LAYMAU-AMDAO'
     WHERE service_code = 'CLS_XET_NGHIEM_DICH_AM_DAO' AND node_code IS NULL;

-- Cervical screening: colposcopy is the screening node, not a procedure.
    UPDATE public.service_price SET node_code = 'DICHVU-SANGLOC-COTUCUNG'
     WHERE service_code = 'CLS_SOI_CO_TU_CUNG' AND node_code IS NULL;

-- Imaging this clinic does not perform itself.
    UPDATE public.service_price SET node_code = 'DICHVU-HINHANH-NGOAI'
     WHERE service_code IN ('CLS_CHUP_MRI_VU', 'CLS_CHUP_VU_EP',
                            'CLS_CHUP_TU_CUNG_VOI_TRUNG')
       AND node_code IS NULL;

    UPDATE public.service_price SET node_code = 'DICHVU-DXA'
     WHERE service_code = 'CLS_DO_MAT_DO_XUONG' AND node_code IS NULL;

-- Procedures: insertion and removal of contraceptives, and monitoring.
    UPDATE public.service_price SET node_code = 'DICHVU-THUTHUAT'
     WHERE service_code IN ('CLS_CAY_QUE_TRANH_THAI', 'CLS_THAO_QUE_TRANH_THAI',
                            'CLS_DAT_VONG_NOI_TIET', 'CLS_THAO_VONG',
                            'CLS_CHAY_MONITORING')
       AND node_code IS NULL;

-- CLS_KHAM_PHU_KHOA is a consultation, not an order the doctor raises for
-- somebody else to perform. It stays NULL on purpose: ordering it from the
-- composer would create a second consultation work item for a patient already
-- in front of a doctor.

    SELECT count(node_code) INTO mapped FROM public.service_price;
    RETURN mapped;
END
$fn$;

COMMENT ON FUNCTION public.map_services_to_nodes() IS
  'Apply the service→node mapping rules. Idempotent; never overwrites a '
  'node_code that is already set. Re-run after adding services.';

-- Map whatever exists right now (production, where the price list is real).
SELECT public.map_services_to_nodes();
