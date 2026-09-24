-- Nhắc lịch trước 7 ngày và trước 1 ngày (20260915000010, Tuyền mô tả 15/09/2026):
-- đặt 2/9 lịch 15/9 → CSKH nhắc ngày 8/9 và 14/9; quá mốc chưa gọi là quá hạn.

BEGIN;

DO $$
DECLARE
    pk   uuid := 'a0000000-0000-4000-8000-000000000001';
    loc  uuid;
    sv   uuid;
    hn   date := (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    xa   uuid; tre uuid; gan uuid; mai uuid; nay uuid;
    r    record;
    bn   uuid;
    ap   uuid;
    nv   uuid;

BEGIN
    INSERT INTO public.clinic_location (clinic_id, code, name)
    VALUES (pk, 'NHAC-7-1', 'CS nhắc lịch') RETURNING id INTO loc;
    INSERT INTO public.service_type (clinic_id, code, name, is_active)
    VALUES (pk, 'NHAC-7-1', 'Khám nhắc lịch', true) RETURNING id INTO sv;

    -- Tạo lịch: slot = hôm nay + p_cach (9:00 VN), đặt từ p_dat_truoc ngày trước.
    CREATE TEMP TABLE _lich (ten text, id uuid) ON COMMIT DROP;
    FOR r IN SELECT * FROM (VALUES
        ('xa',  7, 10),   -- khám sau 7 ngày, đặt 10 ngày trước → CHO_XAC_NHAN hạn hôm nay
        ('tre', 5, 10),   -- khám sau 5 ngày, đặt 10 ngày trước → CHO_XAC_NHAN hạn đã qua
        ('gan', 5, 0),    -- khám sau 5 ngày, đặt HÔM NAY → không có CHO_XAC_NHAN
        ('mai', 1, 3),    -- khám ngày mai → NHAC_HEN_MAI hạn hôm nay
        ('nay', 0, 3)     -- khám hôm nay, chưa đến → NHAC_HEN_MAI quá hạn
    ) AS t(ten, cach, dat_truoc) LOOP
        INSERT INTO public.patient (clinic_id, location_id, patient_code, full_name)
        VALUES (pk, loc, 'BN-NHAC-' || r.ten, 'Khách nhắc ' || r.ten)
        RETURNING clinic_patient_id INTO bn;
        INSERT INTO public.appointment (clinic_id, location_id, clinic_patient_id,
            service_type_id, slot_start, slot_end, status, booking_channel, created_at)
        VALUES (pk, loc, bn, sv,
                ((hn + r.cach) + time '23:00') AT TIME ZONE 'Asia/Ho_Chi_Minh',
                ((hn + r.cach) + time '23:15') AT TIME ZONE 'Asia/Ho_Chi_Minh',
                'CONFIRMED', 'HOTLINE', now() - make_interval(days => r.dat_truoc))
        RETURNING id INTO ap;
        INSERT INTO _lich VALUES (r.ten, ap);
    END LOOP;
    SELECT id INTO xa  FROM _lich WHERE ten = 'xa';
    SELECT id INTO tre FROM _lich WHERE ten = 'tre';
    SELECT id INTO gan FROM _lich WHERE ten = 'gan';
    SELECT id INTO mai FROM _lich WHERE ten = 'mai';
    SELECT id INTO nay FROM _lich WHERE ten = 'nay';

    IF NOT EXISTS (SELECT 1 FROM public.v_viec_cskh WHERE appointment_id = xa
                    AND trang_thai = 'CHO_XAC_NHAN' AND han_xu_ly = hn AND NOT qua_han) THEN
        RAISE EXCEPTION 'Lịch khám sau 7 ngày (đặt xa) phải có việc xác nhận hạn hôm nay';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.v_viec_cskh WHERE appointment_id = tre
                    AND trang_thai = 'CHO_XAC_NHAN' AND han_xu_ly = hn - 2 AND qua_han) THEN
        RAISE EXCEPTION 'Qua mốc 7 ngày chưa gọi thì việc xác nhận phải đỏ quá hạn';
    END IF;
    IF EXISTS (SELECT 1 FROM public.v_viec_cskh WHERE appointment_id = gan
                AND trang_thai = 'CHO_XAC_NHAN') THEN
        RAISE EXCEPTION 'Lịch đặt trong vòng 7 ngày không sinh việc nhắc 7 ngày';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.v_viec_cskh WHERE appointment_id = mai
                    AND trang_thai = 'NHAC_HEN_MAI' AND han_xu_ly = hn AND NOT qua_han) THEN
        RAISE EXCEPTION 'Lịch ngày mai phải có việc nhắc trước 1 ngày hạn hôm nay';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.v_viec_cskh WHERE appointment_id = nay
                    AND trang_thai = 'NHAC_HEN_MAI' AND qua_han) THEN
        RAISE EXCEPTION 'Bỏ lỡ nhắc hôm trước thì sang ngày khám việc vẫn còn, đỏ quá hạn';
    END IF;

    -- Gọi được và ghi XAC_NHAN_LICH → việc đóng.
    INSERT INTO public.staff (primary_location_id, full_name, primary_department)
    VALUES (loc, 'CSKH nhắc lịch', 'CSKH') RETURNING id INTO nv;
    INSERT INTO public.tuong_tac_cskh (clinic_id, clinic_patient_id, appointment_id,
        loai, kenh, ket_qua, nhan_vien_staff_id)
    SELECT pk, clinic_patient_id, id, 'XAC_NHAN_LICH', 'GOI', 'DA_LIEN_HE', nv
      FROM public.appointment WHERE id = xa;
    IF EXISTS (SELECT 1 FROM public.v_viec_cskh WHERE appointment_id = xa
                AND trang_thai = 'CHO_XAC_NHAN') THEN
        RAISE EXCEPTION 'Đã gọi xác nhận mà việc vẫn mở';
    END IF;

    -- Kết quả: CSKH gửi KHÔNG cần bác sĩ cho phép (Tuyền chốt 23/09/2026,
    -- migration 20260923000021 — luật 15/09 "bác sĩ cho phép gửi" đã tắt):
    -- A. Tệp nội bộ (xac_nhan_trang_thai IS NULL): tải lên là CSKH có việc gửi
    --    (KQ_CHUA_GUI) ngay, không qua "chờ bác sĩ" (CHO_BAC_SI).
    -- B. Tệp đối tác: CHO_XAC_NHAN thì CHƯA hiện ở CSKH (chưa chắc đúng người);
    --    xác nhận HOP_LE là có việc gửi ngay.
    DECLARE
        tk_ext uuid;
        kh_nb  uuid;
        kh_ext uuid;
    BEGIN
        -- A. TỆP NỘI BỘ (NULL):
        SELECT clinic_patient_id INTO kh_nb FROM public.appointment WHERE id = mai;
        INSERT INTO public.tep_ket_qua (clinic_id, clinic_patient_id, khoa, loai_tep,
            mime, so_byte, sha256, tai_len_boi_staff_id)
        VALUES (pk, kh_nb, 'test/nhac-7-1-nb.pdf', 'PDF', 'application/pdf', 10,
                repeat('1', 64), nv);

        IF NOT EXISTS (SELECT 1 FROM public.v_viec_cskh
                        WHERE clinic_patient_id = kh_nb AND trang_thai = 'KQ_CHUA_GUI') THEN
            RAISE EXCEPTION 'Tệp nội bộ vừa tải lên thì CSKH phải có việc gửi ngay';
        END IF;
        IF EXISTS (SELECT 1 FROM public.v_viec_cskh
                    WHERE clinic_patient_id = kh_nb AND trang_thai = 'CHO_BAC_SI') THEN
            RAISE EXCEPTION 'Tệp nội bộ không còn phải chờ bác sĩ cho phép';
        END IF;

        -- B. TỆP ĐỐI TÁC (CHO_XAC_NHAN):
        SELECT clinic_patient_id INTO kh_ext FROM public.appointment WHERE id = gan;
        INSERT INTO public.tep_ket_qua (clinic_id, clinic_patient_id, khoa, loai_tep,
            mime, so_byte, sha256, tai_len_boi_staff_id, xac_nhan_trang_thai)
        VALUES (pk, kh_ext, 'test/nhac-7-1-ext.pdf', 'PDF', 'application/pdf', 10,
                repeat('2', 64), nv, 'CHO_XAC_NHAN')
        RETURNING id INTO tk_ext;

        IF EXISTS (SELECT 1 FROM public.v_viec_cskh
                    WHERE clinic_patient_id = kh_ext AND trang_thai IN ('CHO_BAC_SI', 'KQ_CHUA_GUI')) THEN
            RAISE EXCEPTION 'Tệp đối tác CHO_XAC_NHAN không được xuất hiện trong hàng CSKH';
        END IF;

        UPDATE public.tep_ket_qua
           SET xac_nhan_trang_thai = 'HOP_LE', xac_nhan_luc = now(), xac_nhan_boi_staff_id = nv
         WHERE id = tk_ext;

        IF NOT EXISTS (SELECT 1 FROM public.v_viec_cskh
                        WHERE clinic_patient_id = kh_ext AND trang_thai = 'KQ_CHUA_GUI') THEN
            RAISE EXCEPTION 'Tệp đối tác đã HOP_LE thì CSKH phải có việc gửi ngay';
        END IF;
        IF EXISTS (SELECT 1 FROM public.v_viec_cskh
                    WHERE clinic_patient_id = kh_ext AND trang_thai = 'CHO_BAC_SI') THEN
            RAISE EXCEPTION 'Tệp đối tác HOP_LE không còn phải chờ bác sĩ cho phép';
        END IF;
    END;
END
$$;

ROLLBACK;
