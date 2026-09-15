-- Thư ký theo bác sĩ — chặn cả đường đọc thẳng database (20260915000021).
--
-- Thư ký chưa được phân: đọc 0 bệnh án. Phân theo BS Một: chỉ đọc bệnh án khách
-- của BS Một. Bác sĩ vẫn đọc như cũ (chính sách restrictive không đụng vai khác).
-- Mọi thứ rollback.

BEGIN;

INSERT INTO public.clinic (id, code, name)
VALUES ('c2100000-0000-4000-8000-000000000001', 'TKRLS', 'Phòng khám TK-RLS')
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('cc210000-0000-4000-8000-000000000001',
        'c2100000-0000-4000-8000-000000000001', 'TKR', 'Cơ sở TK-RLS')
ON CONFLICT (id) DO NOTHING;

INSERT INTO auth.users (id) VALUES
    ('a2100000-0000-4000-8000-000000000001'),
    ('a2100000-0000-4000-8000-000000000002'),
    ('a2100000-0000-4000-8000-000000000003')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.staff (id, full_name, primary_department, auth_user_id, is_active, primary_location_id)
VALUES
    ('b2100000-0000-4000-8000-000000000001', 'TKRLS BS Mot', 'DOCTOR',
     'a2100000-0000-4000-8000-000000000001', TRUE, 'cc210000-0000-4000-8000-000000000001'),
    ('b2100000-0000-4000-8000-000000000002', 'TKRLS BS Hai', 'DOCTOR',
     'a2100000-0000-4000-8000-000000000002', TRUE, 'cc210000-0000-4000-8000-000000000001'),
    ('b2100000-0000-4000-8000-000000000003', 'TKRLS Thu ky', 'DOCTOR',
     'a2100000-0000-4000-8000-000000000003', TRUE, 'cc210000-0000-4000-8000-000000000001')
ON CONFLICT (id) DO NOTHING;

DELETE FROM public.clinic_membership
 WHERE staff_id IN ('b2100000-0000-4000-8000-000000000001',
                    'b2100000-0000-4000-8000-000000000002',
                    'b2100000-0000-4000-8000-000000000003');
INSERT INTO public.clinic_membership (clinic_id, staff_id, role, is_active) VALUES
    ('c2100000-0000-4000-8000-000000000001', 'b2100000-0000-4000-8000-000000000001', 'DOCTOR', TRUE),
    ('c2100000-0000-4000-8000-000000000001', 'b2100000-0000-4000-8000-000000000002', 'DOCTOR', TRUE),
    ('c2100000-0000-4000-8000-000000000001', 'b2100000-0000-4000-8000-000000000003', 'TKYK', TRUE);

INSERT INTO public.patient (clinic_id, clinic_patient_id, patient_code, full_name, location_id) VALUES
    ('c2100000-0000-4000-8000-000000000001', 'd2100000-0000-4000-8000-000000000001',
     'BN-TKR-1', 'Khach 1', 'cc210000-0000-4000-8000-000000000001'),
    ('c2100000-0000-4000-8000-000000000001', 'd2100000-0000-4000-8000-000000000002',
     'BN-TKR-2', 'Khach 2', 'cc210000-0000-4000-8000-000000000001')
ON CONFLICT (clinic_patient_id) DO NOTHING;

INSERT INTO public.visit (clinic_id, visit_id, clinic_patient_id, attending_doctor_id, status) VALUES
    ('c2100000-0000-4000-8000-000000000001', 'e2100000-0000-4000-8000-000000000001',
     'd2100000-0000-4000-8000-000000000001', 'b2100000-0000-4000-8000-000000000001', 'IN_PROGRESS'),
    ('c2100000-0000-4000-8000-000000000001', 'e2100000-0000-4000-8000-000000000002',
     'd2100000-0000-4000-8000-000000000002', 'b2100000-0000-4000-8000-000000000002', 'IN_PROGRESS');

INSERT INTO public.clinical_record (clinic_id, visit_id, soap_subjective) VALUES
    ('c2100000-0000-4000-8000-000000000001', 'e2100000-0000-4000-8000-000000000001', '"k1"'::jsonb),
    ('c2100000-0000-4000-8000-000000000001', 'e2100000-0000-4000-8000-000000000002', '"k2"'::jsonb);

SET LOCAL ROLE authenticated;

-- Thư ký chưa được phân → 0 dòng.
SELECT set_config('request.jwt.claim.sub', 'a2100000-0000-4000-8000-000000000003', true);
DO $chua_phan$
BEGIN
    IF (SELECT count(*) FROM public.clinical_record
         WHERE clinic_id = 'c2100000-0000-4000-8000-000000000001') <> 0 THEN
        RAISE EXCEPTION 'thư ký chưa được phân bác sĩ phải đọc 0 bệnh án';
    END IF;
    IF (SELECT count(*) FROM public.visit
         WHERE clinic_id = 'c2100000-0000-4000-8000-000000000001') <> 0 THEN
        RAISE EXCEPTION 'thư ký chưa được phân bác sĩ phải đọc 0 lượt khám';
    END IF;
END
$chua_phan$;

-- Phân theo BS Một (ghi bằng quyền chủ, như backend).
RESET ROLE;
INSERT INTO public.thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)
VALUES ('c2100000-0000-4000-8000-000000000001',
        'b2100000-0000-4000-8000-000000000003', 'b2100000-0000-4000-8000-000000000001');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'a2100000-0000-4000-8000-000000000003', true);

DO $theo_bs_mot$
BEGIN
    IF (SELECT count(*) FROM public.clinical_record
         WHERE clinic_id = 'c2100000-0000-4000-8000-000000000001') <> 1
       OR NOT EXISTS (SELECT 1 FROM public.clinical_record
                       WHERE visit_id = 'e2100000-0000-4000-8000-000000000001') THEN
        RAISE EXCEPTION 'thư ký theo BS Một chỉ được đọc đúng bệnh án khách BS Một';
    END IF;
END
$theo_bs_mot$;

-- Bác sĩ Hai vẫn đọc cả hai (không phải thư ký → restrictive không lọc).
SELECT set_config('request.jwt.claim.sub', 'a2100000-0000-4000-8000-000000000002', true);
DO $bac_si_khong_doi$
BEGIN
    IF (SELECT count(*) FROM public.clinical_record
         WHERE clinic_id = 'c2100000-0000-4000-8000-000000000001') <> 2 THEN
        RAISE EXCEPTION 'bác sĩ phải đọc bệnh án như trước';
    END IF;
END
$bac_si_khong_doi$;

ROLLBACK;
