-- Đếm ghế cả-ngày-một-lần khớp từng khung với slot_seats_used (20260821000002).
--
-- Migration tách luật chọn ghế ra `slot_seats_ban` (theo khoảng) và biến
-- `slot_seats_used` (theo khung) thành vỏ mỏng trên nó. Bài kiểm này canh HAI
-- hợp đồng:
--
--   ① vỏ theo-khung đếm ĐÚNG trên các ca chủ đích — đặc biệt ba ca mà dữ liệu
--     thật hiếm khi có sẵn: đến muộn sang khung sau, đến muộn NGAY TRONG khung
--     hẹn (không được chiếm thêm ghế), và đến muộn XUYÊN NGÀY (hẹn hôm trước,
--     sáng hôm sau mới tới);
--   ② phép chia khung bằng SỐ HỌC (cách lưới đặt lịch dùng slot_seats_ban)
--     cho ra Y HỆT con số của vỏ theo-khung, trên mọi khung của hai ngày.
--
-- Luật gốc đã có bài kiểm riêng (ghe_vang_lai_khach_den_muon.sql) — file này
-- không lặp lại nó, chỉ canh phần MỚI: theo-khoảng và số học chia khung.
--
-- Mọi thứ rollback.

BEGIN;

CREATE TEMP TABLE _dich ON COMMIT DROP AS
SELECT (SELECT id FROM public.clinic ORDER BY id LIMIT 1)          AS clinic_id,
       (SELECT id FROM public.clinic_location ORDER BY id LIMIT 1) AS location_id;

DO $$
DECLARE
    v_clinic  uuid := (SELECT clinic_id   FROM _dich);
    v_loc     uuid := (SELECT location_id FROM _dich);
    v_svc     uuid;
    -- Mỗi ghế một bệnh nhân riêng: uq_appointment_patient_slot_live cấm một
    -- người có hai lịch sống cùng slot_start — đúng chốt chống bấm đúp.
    v_bn      uuid[];
    i         integer;
    v_bs      uuid;
    v_phut    integer;
    v_A       timestamptz;      -- đầu khung A (neo tương lai xa, canh mép khung)
    v_B       timestamptz;      -- khung kế tiếp
    v_homqua  timestamptz;      -- cùng giờ khung A của NGÀY HÔM TRƯỚC
    v_appt    uuid;
    v_bo_qua  uuid;             -- lịch dùng thử p_exclude
    v_dem     integer;
    v_lech    integer;
BEGIN
    IF v_clinic IS NULL OR v_loc IS NULL THEN
        RAISE EXCEPTION 'Không dựng được dữ liệu kiểm (clinic=% loc=%)',
            v_clinic, v_loc;
    END IF;

    SELECT id INTO v_svc FROM public.service_type
     WHERE clinic_id = v_clinic AND code = 'KIEMTHU-GHE-NGAY';
    IF v_svc IS NULL THEN
        INSERT INTO public.service_type (code, name, clinic_id)
        VALUES ('KIEMTHU-GHE-NGAY', 'Kiểm thử đếm ghế cả ngày', v_clinic)
        RETURNING id INTO v_svc;
    END IF;

    v_bn := ARRAY[]::uuid[];
    FOR i IN 1..8 LOOP
        INSERT INTO public.patient
            (patient_code, full_name, location_id, clinic_id)
        VALUES ('BN-KIEMTHU-GHENGAY-' || i, 'Kiểm thử ghế ngày ' || i,
                v_loc, v_clinic)
        RETURNING clinic_patient_id INTO v_appt;  -- mượn biến tạm
        v_bn := v_bn || v_appt;
    END LOOP;

    INSERT INTO public.staff (primary_location_id, full_name, primary_department)
    VALUES (v_loc, 'BS kiểm thử ghế ngày', 'DOCTOR')
    RETURNING id INTO v_bs;

    -- Độ dài khung từ chính resolver — phòng khám đổi cấu hình thì bài kiểm
    -- đổi theo, không gõ cứng 15 phút.
    SELECT slot_minutes INTO v_phut
      FROM public.resolve_effective_cap(v_clinic, NULL, now());

    -- Neo 450 ngày tới (xa hơn bài kiểm anh em để hai bộ dữ liệu không đụng
    -- nhau nếu chạy chung phiên), canh đúng mép khung.
    v_A := to_timestamp(
             floor(extract(epoch FROM (now() + interval '450 days'))
                   / (v_phut * 60)) * (v_phut * 60));
    v_B      := v_A + make_interval(mins => v_phut);
    v_homqua := v_A - interval '1 day';

    -- ── Dựng đủ các loại ghế ──────────────────────────────────────────────
    -- ① đặt hẹn thường ở khung A (không bác sĩ — làn chung)
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id,
         slot_start, slot_end, booking_channel, status, clinic_id)
    VALUES (v_bn[1], v_loc, v_svc, v_A, v_B, 'ONLINE', 'SCHEDULED', v_clinic);

    -- ② vãng lai thật ở khung A — chữ thường 'walk_in' để canh luôn nhánh
    -- upper() của luật; ràng buộc walkin_channel_agree đòi is_walkin khớp kênh.
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id, slot_start, slot_end,
         booking_channel, is_walkin, status, clinic_id)
    VALUES (v_bn[2], v_loc, v_svc, v_A, v_B, 'walk_in', TRUE, 'SCHEDULED',
            v_clinic);

    -- ③ đến muộn SANG KHUNG SAU: hẹn khung A, check-in khung B
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id,
         slot_start, slot_end, booking_channel, status, clinic_id)
    VALUES (v_bn[3], v_loc, v_svc, v_A, v_B, 'PHONE', 'CHECKED_IN', v_clinic)
    RETURNING id INTO v_appt;
    INSERT INTO public.visit
        (clinic_patient_id, appointment_id, status, clinic_id, checked_in_at)
    VALUES (v_bn[3], v_appt, 'OPEN', v_clinic,
            v_B + make_interval(mins => v_phut / 2));

    -- ④ đến muộn NGAY TRONG khung hẹn: check-in giữa chính khung A
    --    → KHÔNG được chiếm thêm ghế vãng lai nào.
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id,
         slot_start, slot_end, booking_channel, status, clinic_id)
    VALUES (v_bn[4], v_loc, v_svc, v_A, v_B, 'ZALO', 'CHECKED_IN', v_clinic)
    RETURNING id INTO v_appt;
    INSERT INTO public.visit
        (clinic_patient_id, appointment_id, status, clinic_id, checked_in_at)
    VALUES (v_bn[4], v_appt, 'OPEN', v_clinic,
            v_A + make_interval(mins => v_phut / 2));

    -- ⑤ đến muộn XUYÊN NGÀY: hẹn hôm trước, check-in khung A hôm sau.
    --    Bản theo-khoảng lọc ghế trễ theo GIỜ CHECK-IN — người này phải chiếm
    --    ghế vãng lai của khung A dù giờ hẹn nằm ngoài khoảng đang hỏi.
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id,
         slot_start, slot_end, booking_channel, status, clinic_id)
    VALUES (v_bn[5], v_loc, v_svc, v_homqua,
            v_homqua + make_interval(mins => v_phut), 'PHONE', 'CHECKED_IN',
            v_clinic)
    RETURNING id INTO v_appt;
    INSERT INTO public.visit
        (clinic_patient_id, appointment_id, status, clinic_id, checked_in_at)
    VALUES (v_bn[5], v_appt, 'OPEN', v_clinic,
            v_A + make_interval(mins => v_phut / 3));

    -- ⑥ lịch ĐÃ HUỶ ở khung A — không được đếm ở đâu cả
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id, slot_start, slot_end,
         booking_channel, status, clinic_id,
         -- chốt appointment_huy_phai_co_ly_do: đã huỷ thì phải nói vì sao
         cancelled_at, cancellation_reason, ly_do_huy_ma)
    VALUES (v_bn[6], v_loc, v_svc, v_A, v_B, 'ONLINE', 'CANCELLED', v_clinic,
            now(), 'Dữ liệu kiểm thử', 'KHAC');

    -- ⑦ lịch của BÁC SĨ — làn riêng, không lẫn vào làn chung
    INSERT INTO public.appointment
        (clinic_patient_id, doctor_id, location_id, service_type_id,
         slot_start, slot_end, booking_channel, status, clinic_id)
    VALUES (v_bn[7], v_bs, v_loc, v_svc, v_A, v_B, 'ONLINE', 'SCHEDULED',
            v_clinic);

    -- ⑧ lịch để thử p_exclude
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id,
         slot_start, slot_end, booking_channel, status, clinic_id)
    VALUES (v_bn[8], v_loc, v_svc, v_A, v_B, 'ONLINE', 'SCHEDULED', v_clinic)
    RETURNING id INTO v_bo_qua;

    -- ── ① Vỏ theo-khung đếm đúng các ca chủ đích ─────────────────────────
    -- Khung A, làn chung, ghế đặt hẹn: ①+③+④+⑧ = 4 (② là vãng lai, ⑥ huỷ,
    -- ⑦ của bác sĩ, ⑤ hẹn hôm qua).
    v_dem := public.slot_seats_used(v_clinic, NULL, v_A, v_B, FALSE, NULL);
    IF v_dem <> 4 THEN
        RAISE EXCEPTION 'Ghế đặt hẹn khung A: chờ 4, đếm được %', v_dem;
    END IF;

    -- Khung A, ghế vãng lai: ② (vãng lai thật) + ⑤ (xuyên ngày, check-in
    -- trong A, hẹn hôm qua < đầu khung A) = 2. Ca ④ check-in trong A nhưng
    -- hẹn CŨNG ở A nên không chiếm thêm.
    v_dem := public.slot_seats_used(v_clinic, NULL, v_A, v_B, TRUE, NULL);
    IF v_dem <> 2 THEN
        RAISE EXCEPTION 'Ghế vãng lai khung A: chờ 2 (thật + xuyên ngày), đếm %',
            v_dem;
    END IF;

    -- Khung B, ghế vãng lai: chỉ ③ (hẹn A, check-in B) = 1.
    v_dem := public.slot_seats_used(
                 v_clinic, NULL, v_B, v_B + make_interval(mins => v_phut),
                 TRUE, NULL);
    IF v_dem <> 1 THEN
        RAISE EXCEPTION 'Ghế vãng lai khung B: chờ 1 (đến muộn), đếm %', v_dem;
    END IF;

    -- p_exclude loại đúng một ghế đặt hẹn.
    v_dem := public.slot_seats_used(v_clinic, NULL, v_A, v_B, FALSE, v_bo_qua);
    IF v_dem <> 3 THEN
        RAISE EXCEPTION 'p_exclude: chờ 3, đếm được %', v_dem;
    END IF;

    -- Làn bác sĩ tách khỏi làn chung.
    v_dem := public.slot_seats_used(v_clinic, v_bs, v_A, v_B, FALSE, NULL);
    IF v_dem <> 1 THEN
        RAISE EXCEPTION 'Làn bác sĩ: chờ 1, đếm được %', v_dem;
    END IF;

    -- ── ② Số học chia khung == vỏ theo-khung, TRÊN MỌI KHUNG hai ngày ────
    -- Đây là chính phép tính của lưới đặt lịch (capacity_service): gọi
    -- slot_seats_ban MỘT lần cho cả khoảng, chia khung bằng phút, ghế trễ chỉ
    -- vào khung nằm sau giờ hẹn. Nếu phép số học này lệch vỏ dù chỉ một khung
    -- thì lưới sẽ vẽ số khác với con số trigger dùng để từ chối.
    WITH khung AS (
        SELECT v_homqua + make_interval(mins => g) AS bat_dau,
               v_homqua + make_interval(mins => g + v_phut) AS ket_thuc
          FROM generate_series(0, 2 * 24 * 60 - v_phut, v_phut) g
    ),
    ban AS (
        SELECT b.loai, b.ts, b.ts_goc
          FROM public.slot_seats_ban(
                   v_clinic, NULL, v_homqua,
                   v_homqua + interval '2 days', NULL, NULL) b
    ),
    so_hoc AS (
        SELECT k.bat_dau,
               count(*) FILTER (WHERE b.loai = 'DAT_HEN')::int AS dat_hen,
               count(*) FILTER (
                   WHERE b.loai = 'VANG_LAI'
                      OR (b.loai = 'VANG_LAI_TRE' AND b.ts_goc < k.bat_dau)
               )::int AS vang_lai
          FROM khung k
          LEFT JOIN ban b ON b.ts >= k.bat_dau AND b.ts < k.ket_thuc
         GROUP BY k.bat_dau
    )
    SELECT count(*) INTO v_lech
      FROM so_hoc s
      JOIN khung k ON k.bat_dau = s.bat_dau
     WHERE s.dat_hen <> public.slot_seats_used(
               v_clinic, NULL, k.bat_dau, k.ket_thuc, FALSE, NULL)
        OR s.vang_lai <> public.slot_seats_used(
               v_clinic, NULL, k.bat_dau, k.ket_thuc, TRUE, NULL);

    IF v_lech <> 0 THEN
        RAISE EXCEPTION
            'Số học chia khung lệch vỏ theo-khung ở % khung', v_lech;
    END IF;

    RAISE NOTICE 'dem_ghe_ca_ngay_mot_lan: PASS';
END $$;

ROLLBACK;
