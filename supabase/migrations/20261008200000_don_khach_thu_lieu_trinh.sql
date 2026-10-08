-- DỌN KHÁCH THỬ BIẾT BẢNG LIỆU TRÌNH (08/10/2026, liệu trình C2).
--
-- `don_khach_thu` lập kế hoạch xoá bằng DANH SÁCH bảng dữ liệu khách; bảng mới
-- chưa khai thì Chốt 1 ("dòng được GIỮ trỏ vào dòng sắp xoá") dừng cả lần dọn —
-- đúng thiết kế (không xoá lan bảng lạ), nhưng nghĩa là dọn một khách thử có
-- liệu trình đang DỪNG. Bản này:
--   1. `_don_thu_lan`: chép nguyên bản 20261001240000, thêm cột nối
--      'lieu_trinh_id' (lịch sử sửa liệu trình chỉ nối qua cột này).
--   2. `don_khach_thu`: chép nguyên bản 20261003000000 (bản mới nhất), chỉ thêm
--      vào danh sách bảng dữ liệu khách:
--        * 4 bảng liệu trình: lieu_trinh, lieu_trinh_lich_su, lieu_trinh_buoi,
--          lieu_trinh_tra_truoc (20261008100000 / 20261008110000);
--        * 4 bảng có dữ liệu khách ra đời sau bản 20261003 mà cũng chưa khai:
--          so_sua_chi_dinh, tien_thua_giu_lai, form_instance_lich_su, luot_ghi_chu.
--      Thứ tự xoá theo khoá ngoại tự lo (vòng "bị trỏ tới thì để vòng sau");
--      trigger chỉ-thêm (BEFORE) của bảng có dòng bị xoá tắt/bật trong cùng giao
--      dịch như cũ (Chốt 3) — không đổi cách làm.
-- Chạy lại được (CREATE OR REPLACE).

-- ── 1. Lan theo cột nối (+ lieu_trinh_id) ─────────────────────────────────
-- Lan theo cột nối qua mọi bảng dữ liệu khách cho tới khi không thêm được dòng.
-- Cố ý KHÔNG lan theo "tham chiếu mềm" (lich_truoc_id, vitals_tu_visit_id,
-- mang_tu_visit_id, xac_nhan_visit_id): trỏ chéo sang khách giữ thì Chốt 1 bắt.
CREATE OR REPLACE FUNCTION public._don_thu_lan(bang_khach text[])
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    cot_noi text[] := ARRAY[
        'clinic_patient_id', 'patient_id_a', 'patient_id_b', 'patient_a',
        'patient_b', 'subject_patient_id', 'grantee_patient_id',
        'appointment_id', 'opened_appointment_id', 'episode_id', 'care_episode_id',
        'visit_id', 'nguon_visit_id',
        'service_order_id', 'consultation_id', 'form_instance_id', 'round_id',
        'follow_up_case_id', 'work_item_id', 'origin_work_item_id',
        'predecessor_work_item_id', 'successor_work_item_id',
        'payment_id', 'payment_cycle_id', 'cycle_id', 'payment_bill_line_id',
        'refund_id', 'prescription_id', 'allocation_id', 'amendment_id',
        'created_in_correction_id', 'removed_in_correction_id', 'superseded_by_id',
        'pregnancy_id', 'phieu_id', 'event_id', 'reverses_txn_id',
        'original_dispense_txn_id',
        -- Liệu trình (08/10/2026): lịch sử sửa / buổi / trả trước nối qua đây.
        'lieu_trinh_id'];
    t text; dk text; them bigint; tong bigint := 0; vong int := 0;
BEGIN
    LOOP
        them := 0; vong := vong + 1;
        FOREACH t IN ARRAY bang_khach LOOP
            SELECT string_agg(format('x.%I IN (SELECT id FROM _dt_d)', c.column_name), ' OR ')
              INTO dk
            FROM information_schema.columns c
            WHERE c.table_schema = 'public' AND c.table_name = t
              AND c.data_type = 'uuid' AND c.column_name = ANY (cot_noi);
            IF t = 'inventory_txn' THEN
                -- Phiếu xuất/bán/trả thuốc gắn với khách (ref_id = đơn / kỳ thu).
                dk := coalesce(dk || ' OR ', '')
                      || '(x.ref_type IN (''prescription'', ''payment_cycle'', ''drug_return'')'
                      || ' AND x.ref_id IN (SELECT id FROM _dt_d))';
            END IF;
            IF dk IS NOT NULL THEN
                them := them + public._don_thu_lap(t, dk);
            END IF;
        END LOOP;
        tong := tong + them;
        EXIT WHEN them = 0;
        IF vong > 50 THEN RAISE EXCEPTION 'Lan quá 50 vòng — có vòng lặp lạ'; END IF;
    END LOOP;
    RETURN tong;
END $$;

-- ── 2. don_khach_thu (+ 8 bảng) ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.don_khach_thu(
    p_clinic uuid,
    p_khach uuid[],
    p_lam_that boolean,
    p_moc timestamptz DEFAULT NULL,
    p_nguoi uuid DEFAULT NULL,
    p_nguoi_ten text DEFAULT NULL,
    p_nguon text DEFAULT 'man_quan_tri'
) RETURNS jsonb
LANGUAGE plpgsql
AS $fn$
DECLARE
    -- Bảng dữ liệu KHÁCH (lan theo cột nối). Bảng mới có dữ liệu khách mà
    -- chưa khai ở đây → Chốt 1 hoặc Chốt 4 dừng và báo tên.
    bang_khach text[] := ARRAY[
        'patient', 'patient_contact_channel', 'patient_medical_profile',
        'patient_next_of_kin', 'patient_sdt_them', 'patient_link',
        'pregnancy', 'mpi_merge_queue', 'clinical_data_consent',
        'appointment', 'appointment_doi_lich', 'care_episode',
        'follow_up_case', 'round_requirement', 'review_round',
        'nhac_tai_kham', 'hen_goi_lai', 'tuong_tac_cskh', 'cskh_action',
        'cskh_log', 'phan_hoi_khach', 'service_log', 'ghi_chu_khach',
        'luot_phi_kham',
        'visit', 'visit_amendment', 'visit_route', 'visit_gate_override',
        'encounter_flow', 'queue_entry', 'consultation', 'consultation_note',
        'clinical_record', 'clinical_form_response', 'clinical_release',
        'phieu_kham_luot', 'phieu_kham_lich_su', 'ultrasound_record', 'lab_result',
        'vital_measurement', 'form_instance', 'form_result_release',
        'result_correction',
        'service_order', 'service_order_draft', 'service_selection_state',
        'service_execution_attempt', 'doi_tac_nhan_viec', 'doi_tac_thanh_toan',
        'luot_phu_thu', 'luot_vat_tu', 'tep_ket_qua',
        'payment', 'payment_cycle', 'payment_bill_line', 'payment_refund',
        'payment_refund_line', 'payment_cycle_doi_hinh_thuc',
        'payment_cycle_phan', 'anh_chuyen_khoan',
        'prescription', 'prescription_allocation', 'prescription_correction',
        'drug_return', 'thuoc_giao_chua_gan_lo', 'inventory_txn',
        'work_item', 'work_item_dependency', 'work_item_event',
        'nhac_viec_ca_nhan', 'slot_hold',
        'event_delivery', 'luot_dong_thoi_gian',
        -- Ra đời sau bản 20261003 (06–07/10/2026).
        'so_sua_chi_dinh', 'tien_thua_giu_lai', 'form_instance_lich_su',
        'luot_ghi_chu',
        -- Liệu trình điều trị nhiều buổi (08/10/2026).
        'lieu_trinh', 'lieu_trinh_lich_su', 'lieu_trinh_buoi',
        'lieu_trinh_tra_truoc'];
    r record;
    n bigint;
    sai text;
    vong int;
    tien boolean;
    con_lai int;
    loi text;
    dk text;
    v_lan uuid;
    v_khach jsonb;
    v_so_dong jsonb;
    v_tep jsonb;
BEGIN
    IF p_nguon NOT IN ('man_quan_tri', 'script_moc') THEN
        RAISE EXCEPTION 'Nguồn không hợp lệ: %', p_nguon;
    END IF;
    p_khach := coalesce(p_khach, ARRAY[]::uuid[]);
    SELECT count(*) INTO n FROM unnest(p_khach) u(id)
    WHERE NOT EXISTS (SELECT 1 FROM public.patient p
                      WHERE p.clinic_patient_id = u.id AND p.clinic_id = p_clinic);
    IF n > 0 THEN
        RAISE EXCEPTION 'Có % khách không tồn tại hoặc không thuộc phòng khám này', n
            USING ERRCODE = 'no_data_found';
    END IF;

    SET CONSTRAINTS ALL IMMEDIATE;

    -- Gọi lần hai trong cùng giao dịch (xem trước rồi xoá): bỏ bảng tạm cũ.
    -- Kiểm tồn tại trước (không `DROP IF EXISTS`) để khỏi rải NOTICE ra client.
    FOREACH dk IN ARRAY ARRAY['_dt_kh', '_dt_d', '_dt_song', '_dt_tb_uuid', '_dt_dem',
                              '_dt_giu', '_dt_trigger', '_dt_tep'] LOOP
        IF to_regclass('pg_temp.' || dk) IS NOT NULL THEN
            EXECUTE format('DROP TABLE pg_temp.%I', dk);
        END IF;
    END LOOP;
    CREATE TEMP TABLE _dt_kh (bang text, k text, PRIMARY KEY (bang, k)) ON COMMIT DROP;
    CREATE TEMP TABLE _dt_d (id uuid PRIMARY KEY) ON COMMIT DROP;
    CREATE TEMP TABLE _dt_song (id uuid PRIMARY KEY) ON COMMIT DROP;

    -- ── Kế hoạch: khách → mọi dòng kéo theo ───────────────────────────────
    PERFORM public._don_thu_lap('patient',
        'x.clinic_patient_id = ANY (' || quote_literal(p_khach::text) || '::uuid[])');
    PERFORM public._don_thu_lan(bang_khach);

    -- Chốt 2: không rò sang khách không được chọn.
    sai := '';
    FOR r IN
        SELECT c.table_name AS t, c.column_name AS cot
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name IN (SELECT DISTINCT bang FROM _dt_kh)
          AND c.column_name IN ('clinic_patient_id', 'visit_id', 'appointment_id')
          AND c.data_type = 'uuid'
    LOOP
        EXECUTE format(
            'SELECT count(*) FROM public.%I x WHERE %s IN (SELECT k FROM _dt_kh WHERE bang = %L)'
            || ' AND x.%I IS NOT NULL AND x.%I NOT IN (SELECT id FROM _dt_d)',
            r.t, public._don_thu_khoa(('public.' || r.t)::regclass, 'x'), r.t,
            r.cot, r.cot) INTO n;
        IF n > 0 THEN sai := sai || format('%s.%s (%s dòng); ', r.t, r.cot, n); END IF;
    END LOOP;
    IF sai <> '' THEN
        RAISE EXCEPTION 'Kế hoạch rò sang dữ liệu của khách KHÔNG được chọn: %', sai;
    END IF;

    -- ── Sổ sự kiện, thông báo… ────────────────────────────────────────────
    IF p_moc IS NOT NULL THEN
        -- "Còn sống" = khoá chính uuid mọi bảng, trừ dòng sắp xoá.
        FOR r IN
            SELECT c.relname, att.attname
            FROM pg_class c
            JOIN pg_index i ON i.indrelid = c.oid AND i.indisprimary AND i.indnatts = 1
            JOIN pg_attribute att ON att.attrelid = c.oid AND att.attnum = i.indkey[0]
            WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
              AND att.atttypid = 'uuid'::regtype
        LOOP
            EXECUTE format('INSERT INTO _dt_song SELECT x.%I FROM public.%I x'
                           || ' ON CONFLICT DO NOTHING', r.attname, r.relname);
        END LOOP;
        DELETE FROM _dt_song WHERE id IN (SELECT id FROM _dt_d);
    END IF;
    -- Thông báo trỏ bằng chuỗi (nguon_id "loai:<uuid>", duong_dan "?selected=<uuid>").
    CREATE TEMP TABLE _dt_tb_uuid ON COMMIT DROP AS
    SELECT b.id AS tb, m[1]::uuid AS u
    FROM public.thong_bao b
    CROSS JOIN LATERAL regexp_matches(
        coalesce(b.nguon_id, '') || ' ' || coalesce(b.duong_dan, ''),
        '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'g') AS m
    WHERE b.clinic_id = p_clinic;
    vong := 0;
    LOOP
        vong := vong + 1;
        EXIT WHEN public._don_thu_lap_so(p_moc) + public._don_thu_lan(bang_khach) = 0;
        IF vong > 20 THEN RAISE EXCEPTION 'Lan sổ quá 20 vòng'; END IF;
    END LOOP;

    -- Chốt 1: dòng được GIỮ trỏ (khoá ngoại) vào dòng sắp xoá → dừng.
    sai := '';
    FOR r IN
        SELECT c.conrelid::regclass AS rr, c.confrelid::regclass AS tt, c.conkey, c.confkey
        FROM pg_constraint c
        WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
          AND c.confrelid::regclass::text IN (SELECT DISTINCT bang FROM _dt_kh)
    LOOP
        SELECT string_agg(format('r.%I = t.%I', ra.attname, ta.attname), ' AND ')
          INTO dk
        FROM unnest(r.conkey, r.confkey) AS u(rk, tk)
        JOIN pg_attribute ra ON ra.attrelid = r.rr AND ra.attnum = u.rk
        JOIN pg_attribute ta ON ta.attrelid = r.tt AND ta.attnum = u.tk;
        EXECUTE format(
            'SELECT count(*) FROM %s r JOIN %s t ON %s'
            || ' WHERE %s IN (SELECT k FROM _dt_kh WHERE bang = %L)'
            || ' AND %s NOT IN (SELECT k FROM _dt_kh WHERE bang = %L)',
            r.rr, r.tt, dk,
            public._don_thu_khoa(r.tt, 't'), r.tt::text,
            public._don_thu_khoa(r.rr, 'r'), r.rr::text) INTO n;
        IF n > 0 THEN sai := sai || format('%s → %s (%s dòng); ', r.rr, r.tt, n); END IF;
    END LOOP;
    IF sai <> '' THEN
        RAISE EXCEPTION 'Dòng được GIỮ đang trỏ vào dòng sắp xoá (khai bảng vào don_khach_thu hoặc xem lại): %', sai;
    END IF;

    -- ── Kết quả kế hoạch ──────────────────────────────────────────────────
    SELECT coalesce(jsonb_agg(jsonb_build_object(
               'id', p.clinic_patient_id, 'ma', p.patient_code, 'ten', p.full_name)
             ORDER BY p.full_name), '[]'::jsonb)
      INTO v_khach
    FROM public.patient p WHERE p.clinic_patient_id = ANY (p_khach);
    SELECT coalesce(jsonb_object_agg(bang, so), '{}'::jsonb) INTO v_so_dong
    FROM (SELECT bang, count(*) AS so FROM _dt_kh GROUP BY bang) x;
    CREATE TEMP TABLE _dt_tep ON COMMIT DROP AS
    SELECT t.vi_tri, t.khoa FROM public.tep_ket_qua t
    WHERE t.id IN (SELECT id FROM _dt_d) AND t.khoa IS NOT NULL AND t.da_don_tep_luc IS NULL;
    SELECT coalesce(jsonb_agg(jsonb_build_object('vi_tri', vi_tri, 'khoa', khoa) ORDER BY khoa),
                    '[]'::jsonb)
      INTO v_tep FROM _dt_tep;

    -- Chỉ xem trước, hoặc không có gì để xoá (chạy lại lần hai): không ghi nhật ký.
    IF NOT p_lam_that OR v_so_dong = '{}'::jsonb THEN
        RETURN jsonb_build_object('lam_that', false, 'khach', v_khach,
                                  'so_dong', v_so_dong, 'tep', v_tep);
    END IF;

    -- ── Làm thật ──────────────────────────────────────────────────────────
    INSERT INTO public.lan_don_du_lieu_thu
        (clinic_id, boi_staff_id, boi_ten, nguon, moc, khach, so_dong, tep)
    VALUES (p_clinic, p_nguoi, p_nguoi_ten, p_nguon, p_moc, v_khach, v_so_dong, v_tep)
    RETURNING id INTO v_lan;

    -- Bản lưu nguyên văn TRƯỚC khi xoá.
    FOR r IN SELECT DISTINCT bang FROM _dt_kh ORDER BY bang LOOP
        EXECUTE format(
            'INSERT INTO public.du_lieu_da_xoa (lan_id, bang, du_lieu)'
            || ' SELECT %L::uuid, %L, to_jsonb(x) FROM public.%I x'
            || ' WHERE %s IN (SELECT k FROM _dt_kh WHERE bang = %L)',
            v_lan, r.bang, r.bang,
            public._don_thu_khoa(('public.' || r.bang)::regclass, 'x'), r.bang);
    END LOOP;

    -- Chụp số dòng mọi bảng + lịch/lượt của khách GIỮ (Chốt 4).
    CREATE TEMP TABLE _dt_dem (bang text PRIMARY KEY, truoc bigint) ON COMMIT DROP;
    FOR r IN SELECT relname FROM pg_class
             WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'
               AND relname NOT IN ('lan_don_du_lieu_thu', 'du_lieu_da_xoa') LOOP
        EXECUTE format('SELECT count(*) FROM public.%I', r.relname) INTO n;
        INSERT INTO _dt_dem VALUES (r.relname, n);
    END LOOP;
    CREATE TEMP TABLE _dt_giu ON COMMIT DROP AS
    SELECT p.clinic_patient_id AS id,
           (SELECT count(*) FROM public.appointment a WHERE a.clinic_patient_id = p.clinic_patient_id) AS so_lich,
           (SELECT count(*) FROM public.visit v WHERE v.clinic_patient_id = p.clinic_patient_id) AS so_luot
    FROM public.patient p
    WHERE p.clinic_id = p_clinic AND p.clinic_patient_id <> ALL (p_khach);

    -- Chốt 3: tắt các trigger BEFORE (chốt chặn xoá cứng / chỉ-thêm) của đúng
    -- các bảng có dòng bị xoá. Trigger AFTER (báo realtime…) vẫn chạy.
    CREATE TEMP TABLE _dt_trigger ON COMMIT DROP AS
    SELECT c.relname AS bang, t.tgname AS ten
    FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
    WHERE NOT t.tgisinternal AND t.tgenabled <> 'D' AND (t.tgtype & 2) <> 0
      AND c.relnamespace = 'public'::regnamespace
      AND c.relname IN (SELECT DISTINCT bang FROM _dt_kh)
    ORDER BY 1, 2;
    FOR r IN SELECT * FROM _dt_trigger LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE TRIGGER %I', r.bang, r.ten);
    END LOOP;

    -- Kho: trả số lượng của phiếu xuất/bán sắp xoá về lô (lô vẫn giữ).
    UPDATE public.drug_batch b
       SET quantity_on_hand = b.quantity_on_hand - s.q, updated_at = now()
      FROM (SELECT t.drug_batch_id, sum(t.quantity) AS q FROM public.inventory_txn t
            WHERE t.id IN (SELECT id FROM _dt_d) GROUP BY 1) s
     WHERE b.id = s.drug_batch_id;

    -- Vòng khoá ngoại đã biết: appointment.episode_id ↔
    -- care_episode.opened_appointment_id. Cắt ở phía care_episode (dòng sắp xoá).
    UPDATE public.care_episode x SET opened_appointment_id = NULL
    WHERE x.id IN (SELECT id FROM _dt_d) AND x.opened_appointment_id IS NOT NULL;

    -- Xoá theo vòng: bảng nào còn bị trỏ tới thì để vòng sau.
    vong := 0;
    LOOP
        vong := vong + 1; tien := false; con_lai := 0; loi := '';
        FOR r IN SELECT DISTINCT bang FROM _dt_kh ORDER BY bang LOOP
            BEGIN
                EXECUTE format(
                    'DELETE FROM public.%I x WHERE %s IN (SELECT k FROM _dt_kh WHERE bang = %L)',
                    r.bang, public._don_thu_khoa(('public.' || r.bang)::regclass, 'x'), r.bang);
                GET DIAGNOSTICS n = ROW_COUNT;
                IF n > 0 THEN tien := true; END IF;
            -- Bị trỏ tới, hoặc ON DELETE SET NULL của bảng cha đụng CHECK /
            -- NOT NULL ở một dòng CŨNG sắp xoá → để vòng sau.
            EXCEPTION WHEN foreign_key_violation OR restrict_violation
                        OR check_violation OR not_null_violation THEN
                con_lai := con_lai + 1;
                loi := loi || r.bang || ' (' || SQLERRM || '); ';
            END;
        END LOOP;
        EXIT WHEN con_lai = 0;
        IF NOT tien OR vong > 30 THEN
            RAISE EXCEPTION 'Kẹt khoá ngoại, không xoá được: %', loi;
        END IF;
    END LOOP;

    FOR r IN SELECT * FROM _dt_trigger LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE TRIGGER %I', r.bang, r.ten);
    END LOOP;

    -- ── Chốt 4 ────────────────────────────────────────────────────────────
    sai := '';
    FOR r IN SELECT d.bang, d.truoc,
                    (SELECT count(*) FROM _dt_kh k WHERE k.bang = d.bang) AS ke_hoach
             FROM _dt_dem d LOOP
        EXECUTE format('SELECT count(*) FROM public.%I', r.bang) INTO n;
        IF r.truoc - n <> r.ke_hoach THEN
            sai := sai || format('%s (kế hoạch %s, mất %s); ', r.bang, r.ke_hoach, r.truoc - n);
        END IF;
    END LOOP;
    IF sai <> '' THEN RAISE EXCEPTION 'Số dòng mất KHÁC kế hoạch: %', sai; END IF;

    FOR r IN
        SELECT c.table_name AS t, c.column_name AS cot
        FROM information_schema.columns c
        JOIN pg_class pc ON pc.relname = c.table_name
         AND pc.relnamespace = 'public'::regnamespace AND pc.relkind = 'r'
        WHERE c.table_schema = 'public' AND c.data_type = 'uuid'
    LOOP
        EXECUTE format('SELECT count(*) FROM public.%I WHERE %I IN (SELECT id FROM _dt_d)',
                       r.t, r.cot) INTO n;
        IF n > 0 THEN sai := sai || format('%s.%s (%s); ', r.t, r.cot, n); END IF;
    END LOOP;
    IF sai <> '' THEN RAISE EXCEPTION 'Còn dòng trỏ vào dữ liệu đã xoá: %', sai; END IF;

    IF EXISTS (
        SELECT 1 FROM _dt_giu g
        WHERE g.so_lich <> (SELECT count(*) FROM public.appointment a WHERE a.clinic_patient_id = g.id)
           OR g.so_luot <> (SELECT count(*) FROM public.visit v WHERE v.clinic_patient_id = g.id)
           OR NOT EXISTS (SELECT 1 FROM public.patient p WHERE p.clinic_patient_id = g.id)
    ) THEN
        RAISE EXCEPTION 'Dữ liệu của khách KHÔNG được chọn bị đổi — dừng';
    END IF;
    IF EXISTS (SELECT 1 FROM public.drug_batch WHERE quantity_on_hand < 0) THEN
        RAISE EXCEPTION 'Có lô thuốc tồn âm sau khi trả lại';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
               JOIN _dt_trigger x ON x.bang = c.relname AND x.ten = t.tgname
               WHERE t.tgenabled = 'D') THEN
        RAISE EXCEPTION 'Còn trigger bị tắt';
    END IF;

    RETURN jsonb_build_object('lam_that', true, 'lan_id', v_lan, 'khach', v_khach,
                              'so_dong', v_so_dong, 'tep', v_tep);
END $fn$;
