-- Nhắc tái khám hai lượt gọi (migration 20260807000005).
--
-- Khẳng định quan trọng nhất là ⑤: CHẠY LẠI KHÔNG ĐẺ THÊM. Hàm sinh việc sẽ
-- được gọi mỗi lần CSKH mở màn hình — nếu nó không idempotent thì mỗi lần tải
-- trang là một dòng việc mới, và hàng đợi biến thành rác trong một buổi sáng.
--
-- Mọi thứ rollback.

BEGIN;

DO $$
DECLARE
    v_clinic uuid := (SELECT id FROM public.clinic ORDER BY id LIMIT 1);
    v_loc    uuid := (SELECT id FROM public.clinic_location ORDER BY id LIMIT 1);
    v_svc    uuid;
    v_staff  uuid := (SELECT id FROM public.staff ORDER BY id LIMIT 1);
    v_bn1    uuid;   -- bác sĩ dặn tái khám, CHƯA đặt lịch  → lượt 1
    v_bn2    uuid;   -- đã có lịch hẹn HÔM NAY              → lượt 2
    v_bn3    uuid;   -- dặn tái khám NHƯNG đã đặt lịch      → không sinh lượt 1
    v_visit  uuid;
    v_hom_nay date := (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    v_n      integer;
    v_viec   uuid;
BEGIN
    IF v_clinic IS NULL OR v_loc IS NULL THEN
        RAISE EXCEPTION 'Không dựng được dữ liệu kiểm';
    END IF;
    IF v_staff IS NULL THEN
        INSERT INTO public.staff (full_name, short_name, primary_department,
                                  employment_type, is_active)
        VALUES ('CSKH kiểm thử', 'CSKT', 'CSKH', 'FULL_TIME', TRUE)
        RETURNING id INTO v_staff;
    END IF;

    SELECT id INTO v_svc FROM public.service_type
     WHERE clinic_id = v_clinic LIMIT 1;
    IF v_svc IS NULL THEN
        INSERT INTO public.service_type (code, name, clinic_id)
        VALUES ('KIEMTHU-NTK', 'Dịch vụ kiểm thử nhắc tái khám', v_clinic)
        RETURNING id INTO v_svc;
    END IF;

    INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
    VALUES ('BN-NTK-1', 'Nhắc lượt một', v_loc, v_clinic)
    RETURNING clinic_patient_id INTO v_bn1;
    INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
    VALUES ('BN-NTK-2', 'Nhắc lượt hai', v_loc, v_clinic)
    RETURNING clinic_patient_id INTO v_bn2;
    INSERT INTO public.patient (patient_code, full_name, location_id, clinic_id)
    VALUES ('BN-NTK-3', 'Đã tự đặt lịch', v_loc, v_clinic)
    RETURNING clinic_patient_id INTO v_bn3;

    -- ── Bệnh nhân 1: bệnh án đã ký, dặn quay lại sau 6 ngày ────────────────
    INSERT INTO public.visit (clinic_patient_id, status, clinic_id, checked_in_at)
    VALUES (v_bn1, 'FINALIZED', v_clinic, now())
    RETURNING visit_id INTO v_visit;
    INSERT INTO public.clinical_record (visit_id, clinic_id, soap_plan)
    VALUES (v_visit, v_clinic,
            jsonb_build_object('tai_kham',
                jsonb_build_object('ngay', (v_hom_nay + 6)::text)));

    -- ── Bệnh nhân 2: có lịch hẹn HÔM NAY ───────────────────────────────────
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id, slot_start, slot_end,
         status, clinic_id)
    VALUES (v_bn2, v_loc, v_svc,
            (v_hom_nay + interval '9 hours') AT TIME ZONE 'Asia/Ho_Chi_Minh',
            (v_hom_nay + interval '9 hours 15 min') AT TIME ZONE 'Asia/Ho_Chi_Minh',
            'SCHEDULED', v_clinic);

    -- ── Bệnh nhân 3: cũng được dặn tái khám, NHƯNG đã tự đặt lịch ──────────
    INSERT INTO public.visit (clinic_patient_id, status, clinic_id, checked_in_at)
    VALUES (v_bn3, 'FINALIZED', v_clinic, now())
    RETURNING visit_id INTO v_visit;
    INSERT INTO public.clinical_record (visit_id, clinic_id, soap_plan)
    VALUES (v_visit, v_clinic,
            jsonb_build_object('tai_kham',
                jsonb_build_object('ngay', (v_hom_nay + 5)::text)));
    INSERT INTO public.appointment
        (clinic_patient_id, location_id, service_type_id, slot_start, slot_end,
         status, clinic_id)
    VALUES (v_bn3, v_loc, v_svc,
            (v_hom_nay + interval '5 days 9 hours') AT TIME ZONE 'Asia/Ho_Chi_Minh',
            (v_hom_nay + interval '5 days 9 hours 15 min') AT TIME ZONE 'Asia/Ho_Chi_Minh',
            'SCHEDULED', v_clinic);

    -- ── ① SINH VIỆC ────────────────────────────────────────────────────────
    PERFORM public.sinh_viec_nhac_tai_kham(v_clinic, v_hom_nay);

    -- ── ② Lượt 1 sinh cho người CHƯA đặt lịch ──────────────────────────────
    SELECT count(*) INTO v_n FROM public.nhac_tai_kham
     WHERE clinic_patient_id = v_bn1 AND luot_goi = 1;
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'Người được dặn tái khám phải có 1 việc lượt 1, có %', v_n;
    END IF;

    -- Hạn gọi = ngày hẹn − 7, đúng luật "gọi trước 5–7 ngày".
    SELECT count(*) INTO v_n FROM public.nhac_tai_kham
     WHERE clinic_patient_id = v_bn1 AND luot_goi = 1
       AND han_goi = ngay_hen - 7;
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'Hạn gọi lượt 1 không phải ngày hẹn trừ 7';
    END IF;

    -- ── ③ Lượt 2 sinh cho người CÓ LỊCH HÔM NAY ────────────────────────────
    SELECT count(*) INTO v_n FROM public.nhac_tai_kham
     WHERE clinic_patient_id = v_bn2 AND luot_goi = 2;
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'Người có lịch hôm nay phải có 1 việc lượt 2, có %', v_n;
    END IF;

    -- ── ④ ĐÃ TỰ ĐẶT LỊCH thì KHÔNG sinh lượt 1 ─────────────────────────────
    -- Gọi mời đặt lịch một người đã đặt rồi là làm phiền khách và tốn công CSKH.
    SELECT count(*) INTO v_n FROM public.nhac_tai_kham
     WHERE clinic_patient_id = v_bn3 AND luot_goi = 1;
    IF v_n <> 0 THEN
        RAISE EXCEPTION 'Người đã đặt lịch vẫn bị sinh việc mời đặt lịch';
    END IF;

    -- ── ⑤ CHẠY LẠI KHÔNG ĐẺ THÊM ───────────────────────────────────────────
    -- Khẳng định quan trọng nhất của cả bài: hàm này chạy mỗi lần mở màn hình.
    PERFORM public.sinh_viec_nhac_tai_kham(v_clinic, v_hom_nay);
    PERFORM public.sinh_viec_nhac_tai_kham(v_clinic, v_hom_nay);
    PERFORM public.sinh_viec_nhac_tai_kham(v_clinic, v_hom_nay);

    SELECT count(*) INTO v_n FROM public.nhac_tai_kham
     WHERE clinic_patient_id IN (v_bn1, v_bn2, v_bn3);
    IF v_n <> 2 THEN
        RAISE EXCEPTION 'Chạy 4 lần ra % việc — lẽ ra vẫn phải là 2', v_n;
    END IF;

    -- ── ⑥ GHI KẾT QUẢ: đã gọi thì phải có đủ dấu vết ───────────────────────
    SELECT id INTO v_viec FROM public.nhac_tai_kham
     WHERE clinic_patient_id = v_bn1 AND luot_goi = 1;

    -- Đánh dấu đã gọi mà KHÔNG có kết quả: phải bị chặn.
    BEGIN
        UPDATE public.nhac_tai_kham
           SET trang_thai = 'DA_GOI', goi_luc = now(),
               nguoi_goi_staff_id = v_staff, dong_luc = now()
         WHERE id = v_viec;
        RAISE EXCEPTION 'Ghi "đã gọi" mà thiếu kết quả KHÔNG bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;   -- đúng
    END;

    UPDATE public.nhac_tai_kham
       SET trang_thai = 'DA_GOI', ket_qua = 'CHUA_NGHE_MAY',
           goi_luc = now(), nguoi_goi_staff_id = v_staff, dong_luc = now()
     WHERE id = v_viec;

    -- ── ⑦ Đã gọi rồi thì rời hàng đợi, KHÔNG bị sinh lại ───────────────────
    PERFORM public.sinh_viec_nhac_tai_kham(v_clinic, v_hom_nay);
    SELECT count(*) INTO v_n FROM public.nhac_tai_kham
     WHERE clinic_patient_id = v_bn1 AND luot_goi = 1;
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'Việc đã gọi bị sinh lại (% dòng)', v_n;
    END IF;

    -- ── ⑧ Lượt 2 bắt buộc gắn với một lịch hẹn ─────────────────────────────
    BEGIN
        INSERT INTO public.nhac_tai_kham
            (clinic_id, clinic_patient_id, luot_goi, ngay_hen, han_goi)
        VALUES (v_clinic, v_bn2, 2, v_hom_nay + 30, v_hom_nay + 30);
        RAISE EXCEPTION 'Lượt 2 không có lịch hẹn mà vẫn lưu được';
    EXCEPTION WHEN check_violation THEN NULL;   -- đúng
    END;

    RAISE NOTICE 'nhac_tai_kham_hai_luot_goi: tất cả khẳng định đều đạt';
END $$;

ROLLBACK;
