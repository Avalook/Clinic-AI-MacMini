-- W8 — Give the patient_summary view its tenant.
--
-- The view projects patient plus a few aggregates and is what the pre-visit
-- brief reads first. It did not expose clinic_id, so the backend — which
-- bypasses RLS — had no way to scope it: the detail queries around it could be
-- filtered by clinic, but the summary that carries the name, patient code, date
-- of birth and national id could not.
--
-- clinic_id is appended at the end so CREATE OR REPLACE accepts it (Postgres
-- allows adding trailing columns to a view, not reordering existing ones).
--
-- The LATERAL joins stay keyed on clinic_patient_id alone, which is correct:
-- that column is a globally unique uuid, so a patient's own visits, appointments
-- and labs cannot belong to another clinic.

CREATE OR REPLACE VIEW public.patient_summary AS
SELECT p.clinic_patient_id,
       p.patient_code,
       p.full_name,
       p.date_of_birth,
       p.phone_primary,
       p.national_id_number,
       v_agg.last_visit_at,
       v_agg.total_visits,
       next_appt.next_appointment_at,
       next_appt.next_appointment_status,
       last_lab.last_lab_received_at,
       last_lab.last_lab_test_code,
       last_lab.last_lab_triage_group,
       p.clinic_id
  FROM patient p
  LEFT JOIN LATERAL (
      SELECT max(COALESCE(v.checked_in_at, v.created_at)) AS last_visit_at,
             count(*) AS total_visits
        FROM visit v
       WHERE v.clinic_patient_id = p.clinic_patient_id
  ) v_agg ON true
  LEFT JOIN LATERAL (
      SELECT a.slot_start AS next_appointment_at,
             a.status AS next_appointment_status
        FROM appointment a
       WHERE a.clinic_patient_id = p.clinic_patient_id
         AND a.status = ANY (ARRAY['SCHEDULED'::text, 'CONFIRMED'::text])
         AND a.slot_start > now()
       ORDER BY a.slot_start
       LIMIT 1
  ) next_appt ON true
  LEFT JOIN LATERAL (
      SELECT lr.result_received_at AS last_lab_received_at,
             lr.test_code AS last_lab_test_code,
             lr.triage_group AS last_lab_triage_group
        FROM lab_result lr
       WHERE lr.clinic_patient_id = p.clinic_patient_id
       ORDER BY lr.result_received_at DESC
       LIMIT 1
  ) last_lab ON true;

GRANT SELECT ON public.patient_summary TO authenticated, service_role;
