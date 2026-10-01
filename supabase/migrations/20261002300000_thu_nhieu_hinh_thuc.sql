-- THU TIỀN NHIỀU HÌNH THỨC + ẢNH CHUYỂN KHOẢN + HOÀN TÁC LẦN THU (Tuyền 01/10/2026).
--
-- "Khách chuyển khoản 200k mà đưa tiền mặt 500k cũng ghi được. Bỏ nút QR đi,
-- chuyển khoản với QR là một. Thêm chỗ lưu ảnh chuyển khoản. Tất cả đều có nút
-- HOÀN TÁC để nhân viên làm lại thao tác bị sai."
--
-- 1. `payment_cycle_phan` — MỘT LẦN THU = NHIỀU PHẦN theo hình thức (Tiền mặt,
--    Chuyển khoản). Mỗi hình thức tối đa một phần mỗi lần thu. Chỉ thêm. TỔNG
--    CÁC PHẦN = `payment_cycle.amount` ép ở Postgres bằng trigger hoãn tới
--    COMMIT (thêm phần rồi mới kiểm, không nhờ Python nhớ). Lần thu có phần
--    chuyển khoản thì `payment_cycle.method` phải là chuyển khoản — vì chính
--    nó quyết lần thu "chờ xác minh" (contract A2), hai thứ không được lệch.
--    `khach_dua`: tiền mặt khách đưa (≥ phần tiền mặt) — CHỈ để in "trả lại
--    khách"; sổ ghi đúng số thu.
--    Lần thu cũ (trước migration này) không có dòng phần nào: một phần duy
--    nhất = (hình thức hiệu lực, amount). QR cũ đọc ra là Chuyển khoản.
--
-- 2. `payment_cycle_doi_hinh_thuc` (V7) thêm `tien_mat` + `chuyen_khoan`: đổi
--    một phiếu sang CHIA (TM x + CK y). Bỏ CHECK "khác hình thức cũ" — chia lại
--    200/500 thành 300/400 vẫn là Chuyển khoản → Chuyển khoản; "không đổi gì"
--    do service kiểm (so cả phần). Trigger kiểm tổng chia = amount.
--
-- 3. `phan_thu_hieu_luc(clinic, cycle, goc, amount)` → jsonb các phần HIỆU
--    LỰC: dòng đổi mới nhất (nếu có) > các phần lúc thu > (goc, amount). MỌI chỗ
--    đọc chia phần (sổ thu, báo cáo cuối ngày, phiếu in) đọc qua hàm này.
--
-- 4. `anh_chuyen_khoan` — ảnh màn hình chuyển khoản của một lần thu. Tệp nằm ở
--    ổ VPS trước rồi container day-tep đẩy sang Viettel CFS (cùng cơ chế, cùng
--    cột với `tep_ket_qua` — services/day_tep.py đọc cả hai bảng). Không nằm
--    trong `tep_ket_qua`: đó là kết quả khám (gửi khách, bác sĩ duyệt, chuông
--    báo) — ảnh chuyển khoản là chứng từ quầy thu. Gỡ ảnh nhầm = ẩn (`go_luc`),
--    không xoá tệp.
--
-- 5. Báo tin SSE cho `payment_cycle` (quầy thu nghe nó nhưng trước giờ chưa
--    bảng nào gắn trigger — huỷ lần chờ xác minh không làm màn nào tự mới),
--    `anh_chuyen_khoan`, `payment_cycle_doi_hinh_thuc`.
--
-- 6. `don_khach_thu` (dọn dữ liệu khách thử) biết hai bảng mới.
--
-- Chạy lại được.

-- ── 1. Phần thu ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.payment_cycle_phan (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinic_id   uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    cycle_id    uuid NOT NULL,
    hinh_thuc   text NOT NULL CHECK (hinh_thuc IN ('CASH', 'TRANSFER')),
    so_tien     bigint NOT NULL CHECK (so_tien > 0),
    khach_dua   bigint,
    tao_luc     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT payment_cycle_phan_cycle_fkey
        FOREIGN KEY (cycle_id, clinic_id)
        REFERENCES public.payment_cycle (payment_cycle_id, clinic_id)
        ON DELETE RESTRICT,
    CONSTRAINT payment_cycle_phan_mot_hinh_thuc UNIQUE (cycle_id, hinh_thuc),
    CONSTRAINT payment_cycle_phan_khach_dua CHECK (
        khach_dua IS NULL OR (hinh_thuc = 'CASH' AND khach_dua >= so_tien))
);
CREATE INDEX IF NOT EXISTS ix_payment_cycle_phan_cycle
    ON public.payment_cycle_phan (clinic_id, cycle_id);

COMMENT ON TABLE public.payment_cycle_phan IS
'Một lần thu chia theo hình thức (01/10/2026): tổng các phần = payment_cycle.amount (trigger hoãn tới COMMIT). Chỉ thêm. Lần thu cũ không có dòng nào.';

CREATE OR REPLACE FUNCTION public.payment_cycle_phan_chi_them()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'payment_cycle_phan là sổ chỉ thêm — không % được', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;

DROP TRIGGER IF EXISTS trg_payment_cycle_phan_chi_them ON public.payment_cycle_phan;
CREATE TRIGGER trg_payment_cycle_phan_chi_them
    BEFORE UPDATE OR DELETE ON public.payment_cycle_phan
    FOR EACH ROW EXECUTE FUNCTION public.payment_cycle_phan_chi_them();
DROP TRIGGER IF EXISTS trg_payment_cycle_phan_khong_truncate ON public.payment_cycle_phan;
CREATE TRIGGER trg_payment_cycle_phan_khong_truncate
    BEFORE TRUNCATE ON public.payment_cycle_phan
    FOR EACH STATEMENT EXECUTE FUNCTION public.payment_cycle_phan_chi_them();

-- Tổng các phần = số tiền lần thu; có phần chuyển khoản ⇔ lần thu là chuyển
-- khoản. Hoãn tới COMMIT: các phần của một lần thu được thêm từng dòng.
CREATE OR REPLACE FUNCTION public.payment_cycle_phan_kiem_tong()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    lan record;
    tong bigint;
    co_ck boolean;
BEGIN
    SELECT amount, method INTO lan FROM public.payment_cycle
     WHERE payment_cycle_id = NEW.cycle_id AND clinic_id = NEW.clinic_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Không tìm thấy lần thu của phần này'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    SELECT sum(so_tien), bool_or(hinh_thuc = 'TRANSFER') INTO tong, co_ck
      FROM public.payment_cycle_phan
     WHERE cycle_id = NEW.cycle_id AND clinic_id = NEW.clinic_id;
    IF tong IS DISTINCT FROM lan.amount THEN
        RAISE EXCEPTION 'Tổng các phần thu (%) phải bằng số tiền lần thu (%)',
            tong, lan.amount USING ERRCODE = 'check_violation';
    END IF;
    IF co_ck IS DISTINCT FROM (lan.method IN ('TRANSFER', 'QR')) THEN
        RAISE EXCEPTION 'Lần thu có phần chuyển khoản phải ghi là chuyển khoản (đang: %)',
            lan.method USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_payment_cycle_phan_kiem_tong ON public.payment_cycle_phan;
CREATE CONSTRAINT TRIGGER trg_payment_cycle_phan_kiem_tong
    AFTER INSERT ON public.payment_cycle_phan
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.payment_cycle_phan_kiem_tong();

ALTER TABLE public.payment_cycle_phan ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_cycle_phan_select_own_clinic ON public.payment_cycle_phan;
CREATE POLICY payment_cycle_phan_select_own_clinic ON public.payment_cycle_phan
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.payment_cycle_phan TO authenticated;
GRANT SELECT, INSERT ON public.payment_cycle_phan TO service_role;

-- ── 2. Đổi hình thức sang CHIA ───────────────────────────────────────────────
ALTER TABLE public.payment_cycle_doi_hinh_thuc
    ADD COLUMN IF NOT EXISTS tien_mat bigint,
    ADD COLUMN IF NOT EXISTS chuyen_khoan bigint;

ALTER TABLE public.payment_cycle_doi_hinh_thuc
    DROP CONSTRAINT IF EXISTS payment_cycle_doi_hinh_thuc_khac_cu;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.payment_cycle_doi_hinh_thuc'::regclass
                      AND conname = 'payment_cycle_doi_hinh_thuc_chia') THEN
        ALTER TABLE public.payment_cycle_doi_hinh_thuc
            ADD CONSTRAINT payment_cycle_doi_hinh_thuc_chia CHECK (
                (tien_mat IS NULL AND chuyen_khoan IS NULL)
                OR (tien_mat > 0 AND chuyen_khoan > 0 AND method_moi = 'TRANSFER'));
    END IF;
END $$;

CREATE OR REPLACE FUNCTION public.payment_cycle_doi_hinh_thuc_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    lan record;
    hien_tai text;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment_cycle_doi_hinh_thuc là sổ chỉ thêm — không % được', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT status, method, amount INTO lan FROM public.payment_cycle
     WHERE payment_cycle_id = NEW.cycle_id AND clinic_id = NEW.clinic_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Không tìm thấy phiếu thu này'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF lan.status <> 'PAID' THEN
        RAISE EXCEPTION 'Chỉ đổi hình thức phiếu đang đã thu (phiếu này: %)', lan.status
            USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (SELECT 1 FROM public.payment_refund r
                WHERE r.clinic_id = NEW.clinic_id
                  AND r.payment_cycle_id = NEW.cycle_id
                  AND r.status IN ('PENDING', 'COMPLETED')) THEN
        RAISE EXCEPTION 'Phiếu đã có khoản hoàn — không đổi hình thức được'
            USING ERRCODE = 'check_violation';
    END IF;
    hien_tai := public.hinh_thuc_hieu_luc(NEW.clinic_id, NEW.cycle_id, lan.method);
    IF NEW.method_cu IS DISTINCT FROM hien_tai THEN
        RAISE EXCEPTION 'Hình thức vừa được đổi (đang là %) — tải lại rồi đổi', hien_tai
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.tien_mat IS NOT NULL
       AND NEW.tien_mat + NEW.chuyen_khoan <> lan.amount THEN
        RAISE EXCEPTION 'Tiền mặt + chuyển khoản (%) phải bằng số tiền phiếu (%)',
            NEW.tien_mat + NEW.chuyen_khoan, lan.amount
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- ── 3. Các phần HIỆU LỰC ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.phan_thu_hieu_luc(
    p_clinic uuid, p_cycle uuid, p_goc text, p_amount bigint)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $fn$
    SELECT CASE
        WHEN d.id IS NOT NULL AND d.tien_mat IS NOT NULL THEN jsonb_build_array(
            jsonb_build_object('hinh_thuc', 'CASH', 'so_tien', d.tien_mat),
            jsonb_build_object('hinh_thuc', 'TRANSFER', 'so_tien', d.chuyen_khoan))
        WHEN d.id IS NOT NULL THEN jsonb_build_array(jsonb_build_object(
            'hinh_thuc', CASE WHEN d.method_moi = 'QR' THEN 'TRANSFER'
                              ELSE d.method_moi END,
            'so_tien', p_amount))
        WHEN ph.ds IS NOT NULL THEN ph.ds
        ELSE jsonb_build_array(jsonb_build_object(
            'hinh_thuc', CASE WHEN p_goc = 'QR' THEN 'TRANSFER' ELSE p_goc END,
            'so_tien', p_amount))
    END
      FROM (SELECT 1) z
      LEFT JOIN LATERAL (
           SELECT x.id, x.method_moi, x.tien_mat, x.chuyen_khoan
             FROM public.payment_cycle_doi_hinh_thuc x
            WHERE x.clinic_id = p_clinic AND x.cycle_id = p_cycle
            ORDER BY x.id DESC LIMIT 1) d ON true
      LEFT JOIN LATERAL (
           SELECT jsonb_agg(jsonb_build_object(
                      'hinh_thuc', p.hinh_thuc, 'so_tien', p.so_tien,
                      'khach_dua', p.khach_dua)
                  ORDER BY CASE p.hinh_thuc WHEN 'CASH' THEN 0 ELSE 1 END) AS ds
             FROM public.payment_cycle_phan p
            WHERE p.clinic_id = p_clinic AND p.cycle_id = p_cycle) ph ON true
$fn$;

COMMENT ON FUNCTION public.phan_thu_hieu_luc(uuid, uuid, text, bigint) IS
'Các phần thu HIỆU LỰC của một lần thu (01/10/2026): [{hinh_thuc CASH|TRANSFER|null, so_tien, khach_dua?}]. Đổi hình thức mới nhất > phần lúc thu > (goc, amount). QR cũ = TRANSFER.';

-- ── 4. Ảnh chuyển khoản ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.anh_chuyen_khoan (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id            uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    cycle_id             uuid NOT NULL,
    khoa                 text NOT NULL UNIQUE,
    mime                 text NOT NULL,
    so_byte              bigint NOT NULL CHECK (so_byte > 0),
    sha256               text NOT NULL,
    tai_len_boi_staff_id uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    tai_len_luc          timestamptz NOT NULL DEFAULT now(),
    -- Gỡ ảnh nhầm: ẩn khỏi màn, giữ tệp + dòng (vết).
    go_luc               timestamptz,
    go_boi_staff_id      uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    -- Cùng cột đẩy tệp với tep_ket_qua (mig 20261001000000) — day_tep đọc cả hai.
    vi_tri               text NOT NULL DEFAULT 'vps',
    da_day_luc           timestamptz,
    so_lan_day_loi       int NOT NULL DEFAULT 0,
    loi_day_cuoi         text,
    day_loi_luc          timestamptz,
    da_xoa_ban_vps_luc   timestamptz,
    -- Luôn NULL (bảng này không có job dọn V9) — để câu chọn lô của day_tep
    -- dùng chung được cho hai bảng.
    da_don_tep_luc       timestamptz,
    CONSTRAINT anh_chuyen_khoan_cycle_fkey
        FOREIGN KEY (cycle_id, clinic_id)
        REFERENCES public.payment_cycle (payment_cycle_id, clinic_id)
        ON DELETE RESTRICT,
    CONSTRAINT anh_chuyen_khoan_go_du_vet CHECK (
        (go_luc IS NULL) = (go_boi_staff_id IS NULL)),
    CONSTRAINT anh_chuyen_khoan_vi_tri_hop_le CHECK (
        vi_tri IN ('vps', 'cfs')
        AND so_lan_day_loi >= 0
        AND (vi_tri = 'cfs' OR (da_day_luc IS NULL AND da_xoa_ban_vps_luc IS NULL))
        AND (da_xoa_ban_vps_luc IS NULL OR da_day_luc IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_anh_chuyen_khoan_cycle
    ON public.anh_chuyen_khoan (clinic_id, cycle_id);
CREATE INDEX IF NOT EXISTS idx_anh_chuyen_khoan_cho_day
    ON public.anh_chuyen_khoan (tai_len_luc) WHERE vi_tri = 'vps';

COMMENT ON TABLE public.anh_chuyen_khoan IS
'Ảnh màn hình chuyển khoản của một lần thu (01/10/2026). Ổ VPS trước → day-tep đẩy sang CFS. Gỡ = ẩn (go_luc), không xoá.';

ALTER TABLE public.anh_chuyen_khoan ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anh_chuyen_khoan_select_own_clinic ON public.anh_chuyen_khoan;
CREATE POLICY anh_chuyen_khoan_select_own_clinic ON public.anh_chuyen_khoan
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.anh_chuyen_khoan TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.anh_chuyen_khoan TO service_role;

-- ── 5. Báo tin cho màn (SSE) ─────────────────────────────────────────────────
DO $$
DECLARE
    t text;
    bang text[] := ARRAY['payment_cycle', 'payment_cycle_doi_hinh_thuc'];
BEGIN
    FOREACH t IN ARRAY bang LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I',
                       'trg_notify_' || t, t);
        EXECUTE format(
            'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION public.notify_row_change()',
            'trg_notify_' || t, t
        );
    END LOOP;
END $$;

-- Ảnh: báo khi thêm / gỡ; việc đẩy tệp (vi_tri, đếm lỗi…) không làm màn tải lại.
DROP TRIGGER IF EXISTS trg_notify_anh_chuyen_khoan ON public.anh_chuyen_khoan;
CREATE TRIGGER trg_notify_anh_chuyen_khoan
    AFTER INSERT OR DELETE ON public.anh_chuyen_khoan
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
DROP TRIGGER IF EXISTS trg_anh_chuyen_khoan_bao_tin_khi_go ON public.anh_chuyen_khoan;
CREATE TRIGGER trg_anh_chuyen_khoan_bao_tin_khi_go
    AFTER UPDATE ON public.anh_chuyen_khoan
    FOR EACH ROW
    WHEN (OLD.go_luc IS DISTINCT FROM NEW.go_luc)
    EXECUTE FUNCTION public.notify_row_change();

-- ── 6. Dọn dữ liệu khách thử biết hai bảng mới ──────────────────────────────
-- Chép nguyên hàm của 20261001240000_don_du_lieu_thu.sql, chỉ thêm
-- 'payment_cycle_phan', 'anh_chuyen_khoan' vào danh sách bảng dữ liệu khách
-- (không khai thì Chốt 1 dừng: dòng giữ lại trỏ vào lần thu sắp xoá).
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
        'payment_cycle_phan', 'anh_chuyen_khoan',
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
