-- THƯ KÝ THEO BÁC SĨ — CHẶN CẢ Ở DATABASE (15/09/2026).
--
-- Tuyền chốt: "thư ký nào thì theo bác sĩ ấy, không được làm việc của bác sĩ
-- khác". Backend đã lọc (clinicai.services.thu_ky_bac_si), nhưng đường đọc thẳng
-- PostgREST vẫn mở: chính sách đọc bệnh án / phiếu chuyên khoa / siêu âm / xét
-- nghiệm chỉ khoá theo phòng khám + vai lâm sàng, nên một thư ký dùng token của
-- mình gọi thẳng API database là đọc được khách của mọi bác sĩ.
--
-- Bản này thêm một chính sách RESTRICTIVE (AND với chính sách sẵn có) trên các
-- bảng có nội dung khám của khách: người gọi KHÔNG phải thư ký ở phòng khám đó
-- → không đổi gì; là thư ký → chỉ dòng của khách thuộc bác sĩ mình được phân.
-- Cùng định nghĩa "khách của bác sĩ" với Python (_KHACH_CUA_BAC_SI_SQL): lịch hẹn
-- với bác sĩ, lượt khám bác sĩ phụ trách, việc siêu âm bác sĩ thực hiện (chưa ai
-- nhận thì thư ký của một bác sĩ siêu âm thấy). ĐỔI MỘT BÊN THÌ ĐỔI CẢ HAI.

CREATE OR REPLACE FUNCTION public.thu_ky_duoc_xem_khach(
    p_clinic_id uuid,
    p_clinic_patient_id uuid
) RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $$
    WITH toi AS (
        SELECT public.current_staff_id() AS staff_id
    ),
    la_thu_ky AS (
        SELECT EXISTS (
            SELECT 1 FROM public.clinic_membership m, toi
             WHERE m.clinic_id = p_clinic_id AND m.staff_id = toi.staff_id
               AND m.is_active AND m.role = 'TKYK'
        ) AS v
    ),
    bac_si AS (
        SELECT tb.bac_si_staff_id AS id
          FROM public.thu_ky_bac_si tb, toi
         WHERE tb.clinic_id = p_clinic_id AND tb.thu_ky_staff_id = toi.staff_id
    ),
    co_sa AS (
        SELECT EXISTS (
            SELECT 1 FROM public.clinic_membership m
             WHERE m.clinic_id = p_clinic_id AND m.is_active
               AND m.role = 'ULTRASOUND_DOCTOR'
               AND m.staff_id IN (SELECT id FROM bac_si)
        ) AS v
    )
    SELECT NOT (SELECT v FROM la_thu_ky)
        OR EXISTS (
            SELECT 1 FROM public.appointment a
             WHERE a.clinic_id = p_clinic_id
               AND a.clinic_patient_id = p_clinic_patient_id
               AND a.doctor_id IN (SELECT id FROM bac_si))
        OR EXISTS (
            SELECT 1 FROM public.visit v
             WHERE v.clinic_id = p_clinic_id
               AND v.clinic_patient_id = p_clinic_patient_id
               AND v.attending_doctor_id IN (SELECT id FROM bac_si))
        OR EXISTS (
            SELECT 1 FROM public.work_item w
             WHERE w.clinic_id = p_clinic_id
               AND w.clinic_patient_id = p_clinic_patient_id
               AND w.node_code = 'DICHVU-SIEUAM'
               AND w.status <> 'CANCELLED'
               AND (w.assigned_to IN (SELECT id FROM bac_si)
                    OR (w.assigned_to IS NULL
                        AND w.status IN ('PENDING', 'IN_PROGRESS')
                        AND (SELECT v FROM co_sa))))
$$;

COMMENT ON FUNCTION public.thu_ky_duoc_xem_khach(uuid, uuid) IS
  'TRUE nếu người gọi không phải thư ký ở phòng khám này, hoặc là thư ký và khách '
  'thuộc bác sĩ mình được phân (20260915000021). Khớp thu_ky_bac_si.py.';

REVOKE ALL ON FUNCTION public.thu_ky_duoc_xem_khach(uuid, uuid) FROM public;
GRANT EXECUTE ON FUNCTION public.thu_ky_duoc_xem_khach(uuid, uuid)
    TO authenticated, service_role;

-- Bảng có clinic_patient_id: kiểm thẳng.
DO $bang_co_khach$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'ultrasound_record', 'lab_result', 'prescription',
        'patient_medical_profile', 'pregnancy', 'visit', 'tep_ket_qua'
    ] LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I',
                       t || '_thu_ky_theo_bac_si', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I AS RESTRICTIVE FOR SELECT TO authenticated '
            'USING (public.thu_ky_duoc_xem_khach(clinic_id, clinic_patient_id))',
            t || '_thu_ky_theo_bac_si', t);
    END LOOP;
END
$bang_co_khach$;

-- Bảng chỉ có visit_id: tra khách qua lượt khám.
DO $bang_theo_luot$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'clinical_record', 'clinical_form_response', 'visit_amendment',
        'vital_measurement'
    ] LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I',
                       t || '_thu_ky_theo_bac_si', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I AS RESTRICTIVE FOR SELECT TO authenticated '
            'USING (public.thu_ky_duoc_xem_khach(clinic_id, '
            '(SELECT v.clinic_patient_id FROM public.visit v '
            '  WHERE v.visit_id = %I.visit_id)))',
            t || '_thu_ky_theo_bac_si', t, t);
    END LOOP;
END
$bang_theo_luot$;
