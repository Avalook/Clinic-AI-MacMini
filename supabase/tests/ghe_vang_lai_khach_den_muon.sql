-- Ghế vãng lai tính CẢ khách có hẹn đến muộn (migration 20260807000001).
--
-- Dựng đúng ví dụ Quang mô tả, rút gọn còn hai khung:
--   khung A  — một người ĐẶT TRƯỚC, không đến trong khung của mình
--   khung B  — khung kế tiếp, trần vãng lai 1 chỗ
--   người của khung A check-in trong khung B  → chiếm chỗ vãng lai của B
--   → khách vãng lai thật của khung B bị từ chối
--
-- Bài kiểm tự dựng toàn bộ dữ liệu: trên lược đồ trần của CI không có bệnh
-- nhân nào, và một bài kiểm chỉ chạy khi sẵn dữ liệu là một bài kiểm không chạy.
--
-- Mọi thứ rollback.

BEGIN;

CREATE TEMP TABLE _dich ON COMMIT DROP AS
SELECT (SELECT id FROM public.clinic ORDER BY id LIMIT 1)          AS clinic_id,
       (SELECT id FROM public.clinic_location ORDER BY id LIMIT 1) AS location_id;

DO $$
DECLARE
    v_clinic   uuid := (SELECT clinic_id   FROM _dich);
    v_loc      uuid := (SELECT location_id FROM _dich);
    v_svc      uuid;
    v_bn_hen   uuid;
    v_bn_vl    uuid;
    v_phut     integer;
    v_tran_vl  integer;
    v_A        timestamptz;   -- đầu khung A
    v_B        timestamptz;   -- đầu khung B (khung kế tiếp)
    v_appt_hen uuid;
    v_bn_lap   uuid;
    v_dem      integer;
BEGIN
    IF v_clinic IS NULL OR v_loc IS NULL THEN
        RAISE EXCEPTION 'Không dựng được dữ liệu kiểm (clinic=% loc=%)',
            v_clinic, v_loc;
    END IF;

    -- Dịch vụ tự dựng, KHÔNG lấy `LIMIT 1` của bảng có sẵn: lược đồ trần của
    -- CI không có dòng service_type nào, và một bài kiểm phụ thuộc dữ liệu sẵn
    -- có là một bài kiểm sẽ im lặng biến mất đúng lúc cần nó nhất.
    SELECT id INTO v_svc FROM public.service_type
     WHERE clinic_id = v_clinic AND code = 'KIEMTHU-GHE';
    IF v_svc IS NULL THEN
        INSERT INTO public.service_type (code, name, clinic_id)
        VALUES ('KIEMTHU-GHE', 'Dịch vụ kiểm thử ghế', v_clinic)
        RETURNING id INTO v_svc;
    END IF;

    INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
    VALUES ('BN-KIEMTHU-DENMUON', 'Kiểm thử đến muộn', v_loc, v_clinic)
    RETURNING clinic_patient_id INTO v_bn_hen;

    INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
    VALUES ('BN-KIEMTHU-VANGLAI', 'Kiểm thử vãng lai', v_loc, v_clinic)
    RETURNING clinic_patient_id INTO v_bn_vl;

    -- Độ dài khung + trần vãng lai lấy từ chính resolver mà trigger dùng, chứ
    -- không gõ 15 phút vào đây: phòng khám đổi cấu hình thì bài kiểm đổi theo.
    SELECT slot_minutes, walkin_cap INTO v_phut, v_tran_vl
      FROM public.resolve_effective_cap(v_clinic, NULL, now());

    -- Neo vào một ngày TƯƠNG LAI xa và canh đúng mép khung, để không đụng dữ
    -- liệu thật và để bucket_start của trigger rơi đúng vào v_A / v_B.
    v_A := to_timestamp(
             floor(extract(epoch FROM (now() + interval '400 days'))
                   / (v_phut * 60)) * (v_phut * 60));
    v_B := v_A + make_interval(mins => v_phut);

    -- ── ① Người ĐẶT TRƯỚC ở khung A ────────────────────────────────────────
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id,
         slot_start, slot_end, booking_channel, status, clinic_id)
    VALUES (v_bn_hen, v_loc, v_svc, v_A, v_B, 'ONLINE', 'SCHEDULED', v_clinic)
    RETURNING id INTO v_appt_hen;

    -- Chưa check-in: khung B chưa mất ghế vãng lai nào.
    v_dem := public.slot_seats_used(v_clinic, NULL, v_B,
                 v_B + make_interval(mins => v_phut), TRUE, NULL);
    IF v_dem <> 0 THEN
        RAISE EXCEPTION 'Chưa đến mà đã trừ ghế vãng lai của khung B (đếm=%)', v_dem;
    END IF;

    -- ── ② Họ đến MUỘN — check-in rơi vào khung B ───────────────────────────
    INSERT INTO public.visit
        (clinic_patient_id, appointment_id, status, clinic_id, checked_in_at)
    VALUES (v_bn_hen, v_appt_hen, 'OPEN', v_clinic,
            v_B + make_interval(mins => 1));

    v_dem := public.slot_seats_used(v_clinic, NULL, v_B,
                 v_B + make_interval(mins => v_phut), TRUE, NULL);
    IF v_dem <> 1 THEN
        RAISE EXCEPTION
            'Khách đến muộn phải chiếm 1 ghế vãng lai của khung B, đếm được %',
            v_dem;
    END IF;

    -- Ghế ĐẶT HẸN của khung A thì không đổi — họ đã đặt nó từ trước.
    v_dem := public.slot_seats_used(v_clinic, NULL, v_A, v_B, FALSE, NULL);
    IF v_dem <> 1 THEN
        RAISE EXCEPTION 'Ghế đặt hẹn của khung A phải vẫn là 1, đếm được %', v_dem;
    END IF;

    -- ── ③ Khách vãng lai THẬT của khung B bị chặn khi hết trần ─────────────
    -- `is_walkin` phải khai ĐÚNG cùng lúc: cột boolean ấy có CHECK buộc khớp
    -- với `booking_channel` (appointment_walkin_channel_agree). Bản đầu của bài
    -- kiểm này quên nó, và khối dưới "đạt" vì vi phạm CHECK kia — cũng là
    -- check_violation. Một bài kiểm bắt nhầm ngoại lệ là một bài kiểm luôn xanh.
    IF v_tran_vl <= 1 THEN
        BEGIN
            INSERT INTO public.appointment
                (clinic_patient_id, location_id, service_type_id,
                 slot_start, slot_end, booking_channel, is_walkin,
                 status, clinic_id)
            VALUES (v_bn_vl, v_loc, v_svc, v_B,
                    v_B + make_interval(mins => v_phut),
                    'WALK_IN', TRUE, 'SCHEDULED', v_clinic);
            RAISE EXCEPTION
                'Nhận thêm khách vãng lai trong khi ghế đã bị người đến muộn chiếm';
        EXCEPTION
            WHEN check_violation THEN
                -- Phải là CHÍNH trigger sức chứa từ chối, không phải một CHECK
                -- nào khác tình cờ cùng mã lỗi.
                IF position('Khung giờ đã đầy' IN SQLERRM) = 0 THEN
                    RAISE EXCEPTION 'Bị chặn vì lý do khác: %', SQLERRM;
                END IF;
        END;
    END IF;

    -- ── ④ Dòng ĐÃ GIỮ GHẾ vẫn đổi được trạng thái ──────────────────────────
    -- Không có nhánh trả-về-sớm trong trigger thì chính phép đếm mới ở ② sẽ
    -- khoá luôn vòng đời của lịch hẹn: "khám xong" cũng bị từ chối.
    UPDATE public.appointment SET status = 'CHECKED_IN' WHERE id = v_appt_hen;
    UPDATE public.appointment SET status = 'COMPLETED'  WHERE id = v_appt_hen;

    IF (SELECT status FROM public.appointment WHERE id = v_appt_hen)
       <> 'COMPLETED' THEN
        RAISE EXCEPTION 'Không đổi được trạng thái của lịch đã giữ ghế';
    END IF;

    -- ── ⑤ Sống lại từ CANCELLED thì VẪN bị kiểm ────────────────────────────
    -- Nhánh trả-về-sớm chỉ miễn cho dòng ĐANG CÒN SỐNG. Một dòng đã huỷ mà
    -- được bật lại là đang đòi một ghế mới, và phải xếp hàng như mọi dòng khác.
    UPDATE public.appointment SET status = 'CANCELLED' WHERE id = v_appt_hen;

    -- Lấp đầy ghế đặt hẹn của khung A bằng đúng regular_cap người KHÁC, rồi
    -- thử bật lại dòng đã huỷ. Mỗi vòng một bệnh nhân mới: một người không
    -- được giữ hai lịch còn sống trong cùng một khung (uq_appointment_patient_slot_live).
    SELECT regular_cap INTO v_dem
      FROM public.resolve_effective_cap(v_clinic, NULL, v_A);
    FOR i IN 1..v_dem LOOP
        INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
        VALUES ('BN-KIEMTHU-LAP-' || i, 'Kiểm thử lấp chỗ ' || i, v_loc, v_clinic)
        RETURNING clinic_patient_id INTO v_bn_lap;

        INSERT INTO public.appointment
            (clinic_patient_id, location_id, service_type_id,
             slot_start, slot_end, booking_channel, status, clinic_id)
        VALUES (v_bn_lap, v_loc, v_svc, v_A, v_B,
                'ONLINE', 'SCHEDULED', v_clinic);
    END LOOP;

    BEGIN
        UPDATE public.appointment SET status = 'SCHEDULED'
         WHERE id = v_appt_hen;
        RAISE EXCEPTION
            'Dòng huỷ được bật lại vào một khung đã đầy mà không bị chặn';
    EXCEPTION
        WHEN check_violation THEN
            -- Phải là chính trigger sức chứa, không phải một CHECK khác.
            IF position('Khung giờ đã đầy' IN SQLERRM) = 0 THEN
                RAISE EXCEPTION 'Bị chặn vì lý do khác: %', SQLERRM;
            END IF;
    END;

    -- ── ⑥ Trạng thái chết KHÔNG giữ ghế ────────────────────────────────────
    -- Luật này từng được canh trong Python (test_booking_service.py). Nó theo
    -- phép đếm xuống đây, nên bài kiểm cũng phải theo — nếu không nó biến mất
    -- mà không ai nhận ra.
    INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
    VALUES ('BN-KIEMTHU-HUY', 'Kiểm thử đã huỷ', v_loc, v_clinic)
    RETURNING clinic_patient_id INTO v_bn_lap;

    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id,
         slot_start, slot_end, booking_channel, is_walkin, status, clinic_id)
    VALUES (v_bn_lap, v_loc, v_svc,
            v_B + make_interval(mins => v_phut * 2),
            v_B + make_interval(mins => v_phut * 3),
            'WALK_IN', TRUE, 'CANCELLED', v_clinic);

    v_dem := public.slot_seats_used(
                 v_clinic, NULL,
                 v_B + make_interval(mins => v_phut * 2),
                 v_B + make_interval(mins => v_phut * 3), TRUE, NULL);
    IF v_dem <> 0 THEN
        RAISE EXCEPTION 'Lịch đã huỷ vẫn giữ ghế vãng lai (đếm=%)', v_dem;
    END IF;

    RAISE NOTICE 'ghe_vang_lai_khach_den_muon: tất cả khẳng định đều đạt';
END $$;

ROLLBACK;
