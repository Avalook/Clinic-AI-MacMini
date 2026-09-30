-- DỌN DỮ LIỆU KHÁCH THỬ — chọn từng khách (Tuyền chốt 30/09/2026).
--
-- "Giao diện hiện theo kiểu tiếp đón khách để biết ngày nào là ai, lỡ xoá nhầm
-- người thật thì sao" — quản trị viên (quyền `permission.manage`) TỰ CHỌN khách
-- để xoá ở màn `/settings/don-du-lieu-thu`. Script `scripts/don-truoc-moc.sh`
-- (xoá theo mốc thời gian) gọi CÙNG hàm này — một chỗ duy nhất biết "xoá một
-- khách" là xoá những dòng nào.
--
-- 1. `lan_don_du_lieu_thu` — NHẬT KÝ: ai xoá, lúc nào, xoá những ai (mã + tên),
--    bao nhiêu dòng mỗi bảng, tệp nào. KHÔNG xoá được (trigger), chỉ được điền
--    kết quả chuyển tệp một lần sau khi giao dịch xoá đã xong.
-- 2. `du_lieu_da_xoa` — BẢN LƯU: mọi dòng bị xoá, nguyên văn (to_jsonb), để
--    khôi phục bằng tay nếu lỡ tay. Không sửa được.
-- 3. `don_khach_thu(...)` — lập kế hoạch + (nếu `p_lam_that`) lưu, xoá, kiểm.
--
-- CÁCH XOÁ (y như `don-prod-truoc-ban-giao.sql`, nhưng CHỌN LỌC):
--   * Không CASCADE lặng lẽ, không `session_replication_role` (nó tắt luôn kiểm
--     khoá ngoại). Chỉ tắt các trigger BEFORE (chốt chặn xoá cứng / chỉ-thêm)
--     của đúng những bảng có dòng bị xoá, bật lại trong cùng giao dịch.
--   * Dòng kéo theo tìm bằng cột nối (clinic_patient_id, visit_id,
--     service_order_id…) cho tới khi không thêm được dòng nào.
--   * Chốt 1 — khoá ngoại theo DỮ LIỆU: dòng được GIỮ mà trỏ vào dòng sắp xoá →
--     dừng, báo tên bảng (bảng mới quên khai → dừng, không xoá lan).
--   * Chốt 2 — không rò sang khách khác (clinic_patient_id / visit_id /
--     appointment_id của khách không được chọn → dừng).
--   * Chốt 4 — sau khi xoá: mỗi bảng mất đúng số dòng kế hoạch, không cột uuid
--     nào còn trỏ vào id đã xoá, lịch + lượt của khách khác còn nguyên, không lô
--     thuốc tồn âm, không trigger nào còn tắt.
--   * Kho thuốc: phiếu xuất/bán của khách bị xoá được bỏ và TRẢ số lượng về lô.
--   * Có `p_moc` (chế độ script): thêm sổ ≤ mốc trỏ vào thứ không còn tồn tại
--     (rác chạy thử), bộ nhớ chống bấm trùng ≤ mốc, nhóm lỗi / cảnh báo có lần
--     cuối ≤ mốc.
--
-- Tệp kết quả KHÔNG xoá ở đây: hàm trả danh sách (vi_tri, khoa); lớp gọi chuyển
-- tệp sang thư mục lưu trữ SAU khi giao dịch xong, rồi ghi kết quả vào nhật ký.

-- ── 1. Nhật ký ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.lan_don_du_lieu_thu (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    luc timestamptz NOT NULL DEFAULT now(),
    boi_staff_id uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    boi_ten text,
    nguon text NOT NULL CHECK (nguon IN ('man_quan_tri', 'script_moc')),
    moc timestamptz,
    khach jsonb NOT NULL DEFAULT '[]'::jsonb,
    so_dong jsonb NOT NULL DEFAULT '{}'::jsonb,
    tep jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- Kết quả chuyển tệp sang thư mục lưu trữ (điền sau giao dịch xoá).
    tep_da_chuyen jsonb
);
CREATE INDEX IF NOT EXISTS lan_don_du_lieu_thu_luc_idx
    ON public.lan_don_du_lieu_thu (clinic_id, luc DESC);

COMMENT ON TABLE public.lan_don_du_lieu_thu IS
    'Nhật ký dọn dữ liệu khách thử (30/09/2026): ai, lúc nào, xoá khách nào. Không xoá được.';

CREATE OR REPLACE FUNCTION public.lan_don_du_lieu_thu_chi_them()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Chỉ được điền kết quả chuyển tệp, và chỉ một lần.
        IF OLD.tep_da_chuyen IS NULL
           AND (to_jsonb(NEW) - 'tep_da_chuyen') = (to_jsonb(OLD) - 'tep_da_chuyen') THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'Nhật ký dọn dữ liệu chỉ được thêm, không sửa / xoá (%).', TG_OP
        USING ERRCODE = 'check_violation';
END $$;

DROP TRIGGER IF EXISTS trg_lan_don_du_lieu_thu_chi_them ON public.lan_don_du_lieu_thu;
CREATE TRIGGER trg_lan_don_du_lieu_thu_chi_them
    BEFORE UPDATE OR DELETE ON public.lan_don_du_lieu_thu
    FOR EACH ROW EXECUTE FUNCTION public.lan_don_du_lieu_thu_chi_them();
DROP TRIGGER IF EXISTS trg_lan_don_du_lieu_thu_khong_truncate ON public.lan_don_du_lieu_thu;
CREATE TRIGGER trg_lan_don_du_lieu_thu_khong_truncate
    BEFORE TRUNCATE ON public.lan_don_du_lieu_thu
    FOR EACH STATEMENT EXECUTE FUNCTION public.lan_don_du_lieu_thu_chi_them();

-- ── 2. Bản lưu các dòng đã xoá ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.du_lieu_da_xoa (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lan_id uuid NOT NULL REFERENCES public.lan_don_du_lieu_thu (id) ON DELETE RESTRICT,
    bang text NOT NULL,
    du_lieu jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS du_lieu_da_xoa_lan_idx ON public.du_lieu_da_xoa (lan_id, bang);

COMMENT ON TABLE public.du_lieu_da_xoa IS
    'Nguyên văn mọi dòng bị xoá bởi don_khach_thu (to_jsonb) — khôi phục bằng tay.';

CREATE OR REPLACE FUNCTION public.du_lieu_da_xoa_khong_sua()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Bản lưu dữ liệu đã xoá không sửa được.'
        USING ERRCODE = 'check_violation';
END $$;
DROP TRIGGER IF EXISTS trg_du_lieu_da_xoa_khong_sua ON public.du_lieu_da_xoa;
CREATE TRIGGER trg_du_lieu_da_xoa_khong_sua
    BEFORE UPDATE ON public.du_lieu_da_xoa
    FOR EACH ROW EXECUTE FUNCTION public.du_lieu_da_xoa_khong_sua();

-- Hai bảng này chứa dữ liệu bệnh nhân: không mở cho PostgREST.
ALTER TABLE public.lan_don_du_lieu_thu ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.du_lieu_da_xoa ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.lan_don_du_lieu_thu FROM PUBLIC;
REVOKE ALL ON public.du_lieu_da_xoa FROM PUBLIC;
DO $$
DECLARE v text;
BEGIN
    FOREACH v IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v) THEN
            EXECUTE format('REVOKE ALL ON public.lan_don_du_lieu_thu FROM %I', v);
            EXECUTE format('REVOKE ALL ON public.du_lieu_da_xoa FROM %I', v);
        END IF;
    END LOOP;
END $$;

-- ── 3. Hàm phụ ───────────────────────────────────────────────────────────
-- Biểu thức khoá chính (text) của bảng `t`, bí danh `a`.
CREATE OR REPLACE FUNCTION public._don_thu_khoa(t regclass, a text)
RETURNS text LANGUAGE sql STABLE AS $$
    SELECT 'ROW(' || string_agg(format('%s.%I', a, att.attname), ', ' ORDER BY k.n)
           || ')::text'
    FROM pg_index i
    CROSS JOIN LATERAL unnest(i.indkey::int2[]) WITH ORDINALITY AS k(attnum, n)
    JOIN pg_attribute att ON att.attrelid = i.indrelid AND att.attnum = k.attnum
    WHERE i.indrelid = t AND i.indisprimary
$$;

-- Thêm vào kế hoạch (`_dt_kh`) các dòng của bảng `t` thoả `dk` (bí danh x);
-- khoá chính 1 cột uuid thì id vào `_dt_d` để lan tiếp. Trả số dòng MỚI.
CREATE OR REPLACE FUNCTION public._don_thu_lap(t text, dk text)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    n bigint;
    kc text := public._don_thu_khoa(('public.' || t)::regclass, 'x');
    cot_id text;
BEGIN
    IF kc IS NULL THEN
        RAISE EXCEPTION 'Bảng % không có khoá chính — không lập kế hoạch xoá được', t;
    END IF;
    EXECUTE format(
        'INSERT INTO _dt_kh (bang, k) SELECT %L, %s FROM public.%I x WHERE (%s)'
        || ' ON CONFLICT DO NOTHING', t, kc, t, dk);
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
        SELECT att.attname INTO cot_id
        FROM pg_index i JOIN pg_attribute att
          ON att.attrelid = i.indrelid AND att.attnum = i.indkey[0]
        WHERE i.indrelid = ('public.' || t)::regclass AND i.indisprimary
          AND i.indnatts = 1 AND att.atttypid = 'uuid'::regtype;
        IF cot_id IS NOT NULL THEN
            EXECUTE format(
                'INSERT INTO _dt_d (id) SELECT x.%I FROM public.%I x'
                || ' WHERE %s IN (SELECT k FROM _dt_kh WHERE bang = %L)'
                || ' ON CONFLICT DO NOTHING', cot_id, t, kc, t);
        END IF;
    END IF;
    RETURN n;
END $$;

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
        'original_dispense_txn_id'];
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

-- Sổ sự kiện / hẹn giờ / biên nhận / thông báo trỏ vào dữ liệu bị xoá. Có mốc:
-- thêm dòng ≤ mốc trỏ vào thứ không còn tồn tại (`_dt_song`), bộ nhớ chống bấm
-- trùng, kho lỗi, cảnh báo ≤ mốc.
CREATE OR REPLACE FUNCTION public._don_thu_lap_so(p_moc timestamptz)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    loai_khach text := '(''patient'', ''clinic_patient'', ''appointment'', ''visit'','
        || ' ''consultation'', ''service_order'', ''form_instance'', ''ket_qua'','
        || ' ''payment'', ''payment_cycle'', ''prescription'', ''tep_ket_qua'','
        || ' ''lab_result'', ''clinical_form_response'', ''cskh_action'','
        || ' ''slot_hold'', ''thong_bao'', ''work_item'', ''care_episode'')';
    moc text := quote_literal(p_moc::text) || '::timestamptz';
    co_moc boolean := p_moc IS NOT NULL;
    them bigint := 0;
BEGIN
    them := them + public._don_thu_lap('domain_event',
        'x.aggregate_id IN (SELECT id FROM _dt_d)' || CASE WHEN co_moc THEN
        ' OR (x.occurred_at <= ' || moc || ' AND x.aggregate_type IN ' || loai_khach
        || ' AND x.aggregate_id NOT IN (SELECT id FROM _dt_song))' ELSE '' END);
    them := them + public._don_thu_lap('event_log',
        'x.aggregate_id IN (SELECT id FROM _dt_d)' || CASE WHEN co_moc THEN
        ' OR (x.occurred_at <= ' || moc || ' AND x.aggregate_type IN ' || loai_khach
        || ' AND x.aggregate_id NOT IN (SELECT id FROM _dt_song))' ELSE '' END);
    them := them + public._don_thu_lap('hen_gio',
        'x.ve_cai_gi IN (SELECT id FROM _dt_d)' || CASE WHEN co_moc THEN
        ' OR (x.tao_luc <= ' || moc || ' AND x.ve_cai_gi NOT IN (SELECT id FROM _dt_song))'
        ELSE '' END);
    them := them + public._don_thu_lap('command_receipt',
        'x.target_ref IN (SELECT id FROM _dt_d)' || CASE WHEN co_moc THEN
        ' OR (x.created_at <= ' || moc || ' AND x.target_ref NOT IN (SELECT id FROM _dt_song))'
        ELSE '' END);
    them := them + public._don_thu_lap('pos_outbox',
        'x.subject_id IN (SELECT id FROM _dt_d)' || CASE WHEN co_moc THEN
        ' OR (x.created_at <= ' || moc || ' AND x.subject_id NOT IN (SELECT id FROM _dt_song))'
        ELSE '' END);
    them := them + public._don_thu_lap('staff_task',
        'x.source_id IN (SELECT id FROM _dt_d)' || CASE WHEN co_moc THEN
        ' OR (x.created_at <= ' || moc || ' AND x.source_id NOT IN (SELECT id FROM _dt_song))'
        ELSE '' END);
    them := them + public._don_thu_lap('thong_bao',
        'x.id IN (SELECT tb FROM _dt_tb_uuid WHERE u IN (SELECT id FROM _dt_d))'
        || CASE WHEN co_moc THEN
        ' OR (x.tao_luc <= ' || moc || ' AND x.id IN (SELECT tb FROM _dt_tb_uuid)'
        || ' AND x.id NOT IN (SELECT tb FROM _dt_tb_uuid WHERE u IN (SELECT id FROM _dt_song)))'
        ELSE '' END);
    IF co_moc THEN
        -- Giữ chỗ ≤ mốc không gắn lịch nào còn sống.
        them := them + public._don_thu_lap('slot_hold',
            '(x.appointment_id IS NULL OR x.appointment_id NOT IN (SELECT id FROM _dt_song))'
            || ' AND x.held_at <= ' || moc);
        them := them + public._don_thu_lap('idempotency_key', 'x.created_at <= ' || moc);
        them := them + public._don_thu_lap('loi_nhom', 'x.lan_cuoi <= ' || moc);
        them := them + public._don_thu_lap('canh_bao', 'x.lan_cuoi <= ' || moc);
    END IF;
    RETURN them;
END $$;

-- ── 4. Hàm chính ─────────────────────────────────────────────────────────
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
        'luot_phu_thu', 'tep_ket_qua',
        'payment', 'payment_cycle', 'payment_bill_line', 'payment_refund',
        'payment_refund_line', 'payment_cycle_doi_hinh_thuc',
        'prescription', 'prescription_allocation', 'prescription_correction',
        'drug_return', 'thuoc_giao_chua_gan_lo', 'inventory_txn',
        'work_item', 'work_item_dependency', 'work_item_event',
        'nhac_viec_ca_nhan', 'slot_hold',
        'event_delivery', 'luot_dong_thoi_gian'];
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

COMMENT ON FUNCTION public.don_khach_thu(uuid, uuid[], boolean, timestamptz, uuid, text, text) IS
    'Xoá khách thử + mọi dữ liệu kéo theo (30/09/2026). Chỉ API (quyền permission.manage) và scripts/don-truoc-moc.sh gọi.';

-- Không mở cho PostgREST (anon / authenticated gọi RPC được mọi hàm public
-- có quyền EXECUTE của PUBLIC).
DO $$
DECLARE f text; v text;
BEGIN
    FOREACH f IN ARRAY ARRAY[
        'public.don_khach_thu(uuid, uuid[], boolean, timestamptz, uuid, text, text)',
        'public._don_thu_khoa(regclass, text)',
        'public._don_thu_lap(text, text)',
        'public._don_thu_lan(text[])',
        'public._don_thu_lap_so(timestamptz)',
        'public.lan_don_du_lieu_thu_chi_them()',
        'public.du_lieu_da_xoa_khong_sua()'] LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', f);
        FOREACH v IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v) THEN
                EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I', f, v);
            END IF;
        END LOOP;
    END LOOP;
END $$;
