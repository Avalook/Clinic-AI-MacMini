-- Tài khoản đa vai cho acceptance (batch pilot 18/09/2026) — LOCAL ONLY.
--
-- "Đa năng local" (tài khoản Điều dưỡng) hôm nay đứng BA vị trí: Lễ tân
-- (T1_LETAN), Thu ngân (T1_THUNGAN — quầy thu thuộc vai lễ tân), Đo chỉ số
-- (T1_DOCHISO). Vai vận hành đến từ lịch (`identity.VAI_THEO_VI_TRI`), nên một
-- người thấy đủ ba nhóm việc mà không cần tài khoản thứ hai. Nhật ký ghi vai
-- tài khoản + vai thực sự dùng (S0-5).
--
-- Chạy lại mỗi ngày được: xoá lịch HÔM NAY của đúng người này rồi ghi lại.

\set ON_ERROR_STOP on

DO $$
DECLARE
    v_clinic uuid := 'a0000000-0000-4000-8000-000000000001';
    v_hom_nay date := (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    v_sid uuid;
    v_ten text;
    tram text;
    i int := 0;
BEGIN
    SELECT s.id, s.full_name INTO v_sid, v_ten
      FROM public.staff s JOIN auth.users u ON u.id = s.auth_user_id
     WHERE u.email = 'danang@dr4women.local';
    IF v_sid IS NULL THEN
        RAISE EXCEPTION 'chưa có danang@dr4women.local — chạy staff_logins.sql trước';
    END IF;
    DELETE FROM public.work_roster
     WHERE clinic_id = v_clinic AND staff_id = v_sid AND work_date = v_hom_nay;
    FOREACH tram IN ARRAY ARRAY['T1_LETAN', 'T1_THUNGAN', 'T1_DOCHISO'] LOOP
        i := i + 1;
        INSERT INTO public.work_roster
            (clinic_id, week_start, work_date, shift, station, staff_id,
             staff_name, sort, status)
        VALUES (v_clinic, v_hom_nay - (extract(isodow FROM v_hom_nay)::int - 1),
                v_hom_nay, 'FULL', tram, v_sid, v_ten, i, 'APPROVED');
    END LOOP;
END $$;
