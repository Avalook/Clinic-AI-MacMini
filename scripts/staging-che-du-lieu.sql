-- CHE DỮ LIỆU KHÁCH CHO STAGING (01/10/2026) — xem docs/STAGING.md.
--
-- Chạy BÊN TRONG giao dịch nạp của scripts/staging-nap-ban-sao.sh, ngay sau khi
-- nạp bản sao lưu prod: dữ liệu khách chưa che không bao giờ được commit vào
-- database staging. Không có BEGIN/COMMIT ở đây — hỏng một câu là huỷ cả lần nạp.
--
-- GIỮ NGUYÊN: nhân sự, tài khoản đăng nhập (auth.*), phòng, lịch, dịch vụ, giá,
-- kho, mã khách (BN-…), giới tính, tỉnh/phường, nội dung khám (đã lọc tên/SĐT).
--
-- BA KIỂU CHE:
--   giá trị giả ỔN ĐỊNH   tên "Khách 0001", SĐT 09xxxxxxxx… — số thứ tự theo
--                         (created_at, id) nên khách cũ giữ số qua các đêm.
--   (đã che)              ghi chú tự do VỀ khách, nội dung CSKH, tin nhắn.
--   che_chu()             văn bản nghiệp vụ/khám: thay đúng chuỗi họ tên khách
--                         (và người nhà) bằng tên giả, mọi SĐT / email → giả.
--                         Giới hạn: biến thể tên (chỉ tên gọi, viết không dấu,
--                         chữ hoa) có thể sót — vì vậy ghi chú tự do bị thay hẳn.
--   JSON (sự kiện, ảnh chụp dòng đã xoá, phiếu…): khoá định danh (full_name,
--   phone…, xem che_json) → "(đã che)", ngày sinh → null, rồi che_chu cả khối.
--
-- TRIGGER: các bảng có chốt chỉ-thêm / khoá sau khi ký (event_log,
-- domain_event, du_lieu_da_xoa, visit_amendment, payment_*, …) chặn UPDATE. Tắt
-- ĐÚNG trigger của đúng các bảng bị sửa, trong giao dịch, rồi bật lại đúng trạng
-- thái cũ — cùng cách hàm don_khach_thu (migration 20261001240000). Tắt luôn
-- trigger AFTER: trigger ghi lịch sử (phieu_kham_luot) sẽ chép bản CŨ chưa che
-- sang bảng lịch sử, trigger updated_at sẽ làm sai mốc "sửa lần cuối".
-- NGOẠI LỆ: patient + patient_sdt_them GIỮ trigger — chúng tính lại cột tìm
-- kiếm `sdt_tim_kiem` từ SĐT đã che (không có chốt chặn nào trên hai bảng này).
--
-- Thêm cột chứa thông tin khách ở migration mới → thêm vào bảng _che_cot dưới
-- đây. src/tests/test_staging_che_du_lieu.py đỏ khi một cột định danh khách
-- (tên/SĐT/email/địa chỉ/CCCD/ngày sinh…) chưa được xếp loại.

DO $$
BEGIN
    IF current_setting('clinicai.che_cho_phep', true) IS DISTINCT FROM 'staging' THEN
        RAISE EXCEPTION 'staging-che-du-lieu.sql chỉ chạy trong staging-nap-ban-sao.sh '
            '(thiếu SET LOCAL clinicai.che_cho_phep = ''staging'')';
    END IF;
END $$;

-- Chạy lại trong CÙNG phiên (bài test chạy hai lần) — bảng tạm của lần trước.
DROP TABLE IF EXISTS pg_temp._che_cot, pg_temp._che_khach, pg_temp._che_ten, pg_temp._che_trigger;

-- ── Danh sách cột: bảng · cột · cách che ────────────────────────────────────
--   rieng      câu UPDATE riêng bên dưới (cần số thứ tự khách)
--   xoa        → '(đã che)' (khi có giá trị)
--   chu        → pg_temp.che_chu()
--   json       → pg_temp.che_json(…, false)
--   json_manh  → pg_temp.che_json(…, true) — thêm cả ghi chú / nội dung
--   giu        đã xét: không phải thông tin khách (nhân sự, cơ sở, danh mục)
CREATE TEMP TABLE _che_cot (bang text, cot text, cach text, PRIMARY KEY (bang, cot)) ON COMMIT DROP;
INSERT INTO _che_cot (bang, cot, cach) VALUES
    -- khách
    ('patient', 'full_name', 'rieng'),
    ('patient', 'phone_primary', 'rieng'),
    ('patient', 'phone_secondary', 'rieng'),
    ('patient', 'national_id_number', 'rieng'),
    ('patient', 'date_of_birth', 'rieng'),
    ('patient', 'birth_year', 'rieng'),
    ('patient', 'address', 'rieng'),
    ('patient', 'address_detail', 'rieng'),
    ('patient', 'guardian_name', 'rieng'),
    ('patient', 'nguoi_gioi_thieu', 'rieng'),
    ('patient', 'patient_objection', 'rieng'),
    ('patient', 'occupation', 'rieng'),
    ('patient', 'van_de_di_kham', 'rieng'),
    ('patient', 'uu_tien_ly_do', 'rieng'),
    ('patient', 'full_name_unaccent', 'giu'),   -- cột sinh tự động từ full_name
    ('patient', 'sdt_tim_kiem', 'giu'),         -- trigger tính lại từ SĐT đã che
    ('patient', 'ward_name', 'giu'),
    ('patient', 'province_name', 'giu'),
    ('patient_next_of_kin', 'full_name', 'rieng'),
    ('patient_next_of_kin', 'phone', 'rieng'),
    ('patient_next_of_kin', 'zalo_id', 'rieng'),
    ('patient_next_of_kin', 'notes', 'xoa'),
    ('patient_contact_channel', 'channel_value', 'rieng'),
    ('patient_sdt_them', 'so_dien_thoai', 'rieng'),
    ('patient_link', 'note', 'xoa'),
    ('patient_medical_profile', 'notes', 'chu'),
    ('patient_medical_profile', 'family_history', 'json'),
    ('cskh_log', 'patient_info', 'rieng'),
    ('cskh_log', 'phone', 'rieng'),
    ('cskh_log', 'note', 'xoa'),
    ('cskh_log', 'ket_qua', 'chu'),
    ('cskh_action', 'action_data', 'xoa'),
    ('cskh_action', 'description', 'xoa'),
    ('cskh_action', 'result_text', 'xoa'),
    ('cskh_action', 'patient_link_raw', 'xoa'),
    ('tuong_tac_cskh', 'noi_dung', 'xoa'),
    ('tuong_tac_cskh', 'ly_do_hoan_tac', 'chu'),
    ('ghi_chu_khach', 'noi_dung', 'xoa'),
    ('phan_hoi_khach', 'noi_dung', 'xoa'),
    ('phan_hoi_khach', 'huong_xu_ly', 'xoa'),
    ('hen_goi_lai', 'ly_do', 'chu'),
    ('nhac_tai_kham', 'ghi_chu', 'xoa'),
    ('nhac_tai_kham', 'ly_do', 'chu'),
    ('nhac_viec_ca_nhan', 'noi_dung', 'chu'),
    ('follow_up_case', 'reason', 'chu'),
    ('follow_up_case', 'notes', 'xoa'),
    ('clinical_data_consent', 'revoke_reason', 'chu'),
    ('payment', 'paid_by_text', 'xoa'),
    ('payment', 'void_reason', 'chu'),
    ('payment_refund', 'reason', 'chu'),
    ('payment_refund', 'closed_reason', 'chu'),
    ('payment_cycle', 'close_reason', 'chu'),
    ('payment_cycle_doi_hinh_thuc', 'ly_do', 'chu'),
    ('doi_tac_thanh_toan', 'ghi_chu', 'chu'),
    ('doi_tac_thanh_toan', 'ly_do_huy', 'chu'),
    -- lịch / lượt / khám (nội dung giữ, lọc tên + SĐT)
    ('appointment', 'notes', 'xoa'),
    ('appointment', 'cancellation_reason', 'chu'),
    ('appointment_doi_lich', 'ly_do', 'chu'),
    ('visit', 'incomplete_reason', 'chu'),
    ('visit', 'theo_doi_thu_thuat', 'chu'),
    ('visit_amendment', 'reason', 'chu'),
    ('visit_amendment', 'original_values', 'json'),
    ('visit_amendment', 'corrected_values', 'json'),
    ('visit_route', 'reason', 'chu'),
    ('encounter_flow', 'route_reason', 'chu'),
    ('queue_entry', 'reason', 'chu'),
    ('consultation_note', 'body', 'chu'),
    ('clinical_record', 'soap_subjective', 'json'),
    ('clinical_record', 'soap_objective', 'json'),
    ('clinical_record', 'soap_assessment', 'json'),
    ('clinical_record', 'soap_plan', 'json'),
    ('clinical_record', 'prescription_draft', 'json'),
    ('clinical_record', 'chief_complaint_at_visit', 'chu'),
    ('clinical_record', 'voice_transcript', 'chu'),
    ('clinical_form_response', 'form_data', 'json'),
    ('form_instance', 'du_lieu', 'json'),
    ('form_instance', 'du_lieu_dang_sua', 'json'),
    ('form_instance_lich_su', 'du_lieu', 'json'),
    ('phieu_kham_luot', 'du_lieu', 'json'),
    ('phieu_kham_lich_su', 'truoc', 'json'),
    ('phieu_kham_lich_su', 'sau', 'json'),
    ('ultrasound_record', 'findings', 'json'),
    ('ultrasound_record', 'impression', 'chu'),
    ('lab_result', 'raw_payload', 'json'),
    ('lab_result', 'triage_reason', 'chu'),
    ('pregnancy', 'high_risk_reason', 'chu'),
    ('prescription', 'quantity_note', 'chu'),
    ('prescription', 'refusal_reason', 'chu'),
    ('prescription', 'removal_reason', 'chu'),
    ('prescription', 'caution', 'chu'),
    ('service_order', 'result_note', 'chu'),
    ('service_order', 'not_performed_reason', 'chu'),
    ('service_order', 'cancel_reason', 'chu'),
    ('service_order', 'bac_si_danh_gia', 'chu'),
    ('service_execution_attempt', 'interruption_reason_note', 'chu'),
    ('service_execution_attempt', 'ghi_chu', 'chu'),
    ('service_log', 'result_text', 'chu'),
    ('service_log', 'patient_link_raw', 'xoa'),
    ('doi_tac_nhan_viec', 'ly_do', 'chu'),
    ('doi_tac_nhan_viec', 'ghi_chu_lay_mau', 'chu'),
    ('doi_tac_nhan_viec', 'ghi_chu_tai_lieu', 'chu'),
    ('tep_ket_qua', 'ten_hien_thi', 'chu'),
    ('tep_ket_qua', 'xac_nhan_ly_do', 'chu'),
    ('tep_ket_qua', 'thu_hoi_ly_do', 'chu'),
    ('tep_ket_qua', 'da_xoa_ly_do', 'chu'),
    -- thông báo / việc / lỗi — câu chữ có thể nhắc tên khách
    ('thong_bao', 'tieu_de', 'chu'),
    ('thong_bao', 'noi_dung', 'chu'),
    ('thong_bao', 'ghi_chu_xu_ly', 'chu'),
    ('staff_task', 'title', 'chu'),
    ('staff_task', 'description', 'chu'),
    ('canh_bao', 'noi_dung', 'chu'),
    ('loi_nhom', 'thong_diep', 'chu'),
    ('owner_feedback', 'comment', 'chu'),
    ('owner_feedback', 'resolved_note', 'chu'),
    -- JSON sự kiện / nhật ký / ảnh chụp
    ('domain_event', 'payload', 'json'),
    ('event_log', 'payload', 'json'),
    ('event_log', 'metadata', 'json'),
    ('luot_dong_thoi_gian', 'chi_tiet', 'json'),
    ('work_item', 'payload', 'json'),
    ('work_item_event', 'metadata', 'json'),
    ('work_item_event', 'reason', 'chu'),
    ('hen_gio', 'chi_tiet', 'json'),
    ('pos_outbox', 'payload', 'json'),
    ('idempotency_key', 'response', 'json'),
    ('command_receipt', 'result', 'json'),
    ('du_lieu_da_xoa', 'du_lieu', 'json_manh'),
    ('lan_don_du_lieu_thu', 'khach', 'json_manh'),
    -- đã xét, GIỮ: nhân sự / tài khoản / cơ sở (không phải khách)
    ('staff', 'full_name', 'giu'),
    ('staff', 'phone', 'giu'),
    ('staff', 'email', 'giu'),
    ('staff', 'date_of_birth', 'giu'),
    ('staff', 'national_id_number', 'giu'),
    ('app_credential', 'email', 'giu'),
    ('clinic', 'address', 'giu'),
    ('clinic_location', 'address', 'giu'),
    ('province', 'full_name', 'giu'),           -- danh mục hành chính
    ('ward', 'full_name', 'giu'),
    ('work_roster', 'staff_name', 'giu'),
    ('work_roster_thay_nguoi', 'nguoi_cu_ten', 'giu'),
    ('work_roster_thay_nguoi', 'nguoi_moi_ten', 'giu'),
    ('owner_feedback', 'staff_name', 'giu'),
    ('lan_don_du_lieu_thu', 'boi_ten', 'giu'),
    ('cskh_log', 'confirmed_by', 'giu'),
    ('cskh_log', 'cskh_by', 'giu');

-- Cột trong danh sách mà lược đồ không có → DỪNG: một cột bị đổi tên ở
-- migration mới thì cột tên mới đang KHÔNG được che (test CI bắt trước).
DO $$
DECLARE thieu text;
BEGIN
    SELECT string_agg(c.bang || '.' || c.cot, ', ') INTO thieu
    FROM _che_cot c
    WHERE NOT EXISTS (SELECT 1 FROM information_schema.columns i
                      WHERE i.table_schema = 'public' AND i.table_name = c.bang
                        AND i.column_name = c.cot);
    IF thieu IS NOT NULL THEN
        RAISE EXCEPTION 'che dữ liệu: lược đồ không có cột %. Sửa scripts/staging-che-du-lieu.sql.', thieu;
    END IF;
END $$;

-- ── Ánh xạ khách → số thứ tự + tên thật → tên giả ───────────────────────────
CREATE TEMP TABLE _che_khach ON COMMIT DROP AS
SELECT clinic_patient_id AS id,
       row_number() OVER (ORDER BY created_at, clinic_patient_id) AS n
FROM public.patient;
CREATE UNIQUE INDEX ON _che_khach (id);

CREATE TEMP TABLE _che_ten (that text PRIMARY KEY, gia text NOT NULL) ON COMMIT DROP;
INSERT INTO _che_ten
SELECT btrim(p.full_name), 'Khách ' || lpad(c.n::text, 4, '0')
FROM public.patient p JOIN _che_khach c ON c.id = p.clinic_patient_id
WHERE nullif(btrim(p.full_name), '') IS NOT NULL
ON CONFLICT DO NOTHING;
INSERT INTO _che_ten
SELECT btrim(k.full_name), 'Người nhà khách ' || lpad(c.n::text, 4, '0')
FROM public.patient_next_of_kin k JOIN _che_khach c ON c.id = k.clinic_patient_id
WHERE nullif(btrim(k.full_name), '') IS NOT NULL
ON CONFLICT DO NOTHING;
INSERT INTO _che_ten
SELECT btrim(p.guardian_name), 'Người nhà khách ' || lpad(c.n::text, 4, '0')
FROM public.patient p JOIN _che_khach c ON c.id = p.clinic_patient_id
WHERE nullif(btrim(p.guardian_name), '') IS NOT NULL
ON CONFLICT DO NOTHING;
INSERT INTO _che_ten
SELECT btrim(p.nguoi_gioi_thieu), 'Người giới thiệu ' || lpad(c.n::text, 4, '0')
FROM public.patient p JOIN _che_khach c ON c.id = p.clinic_patient_id
WHERE nullif(btrim(p.nguoi_gioi_thieu), '') IS NOT NULL
ON CONFLICT DO NOTHING;
-- Tên của khách ĐÃ XOÁ (chỉ còn trong ảnh chụp du_lieu_da_xoa / lan_don_du_lieu_thu)
-- vẫn có thể nằm trong thông báo, nhật ký… Không còn số thứ tự → tên chung.
INSERT INTO _che_ten
SELECT DISTINCT btrim(v), 'Khách đã xoá'
FROM (
    SELECT du_lieu->>'full_name' AS v FROM public.du_lieu_da_xoa WHERE bang IN ('patient', 'patient_next_of_kin')
    UNION SELECT du_lieu->>'guardian_name' FROM public.du_lieu_da_xoa WHERE bang = 'patient'
    UNION SELECT du_lieu->>'nguoi_gioi_thieu' FROM public.du_lieu_da_xoa WHERE bang = 'patient'
    UNION SELECT e->>'ten' FROM public.lan_don_du_lieu_thu,
        jsonb_array_elements(CASE WHEN jsonb_typeof(khach) = 'array' THEN khach ELSE '[]' END) e
) s
WHERE nullif(btrim(v), '') IS NOT NULL
ON CONFLICT DO NOTHING;
-- Biến thể của mọi tên ở trên: không dấu, CHỮ HOA, chữ thường không dấu (văn bản
-- gõ tay và cột tìm kiếm hay gặp).
INSERT INTO _che_ten
SELECT v, t.gia
FROM _che_ten t,
     LATERAL (VALUES (replace(replace(public.f_unaccent(t.that), 'đ', 'd'), 'Đ', 'D')),
                     (upper(t.that)),
                     (upper(replace(replace(public.f_unaccent(t.that), 'đ', 'd'), 'Đ', 'D'))),
                     (lower(replace(replace(public.f_unaccent(t.that), 'đ', 'd'), 'Đ', 'D')))) x(v)
WHERE v IS NOT NULL AND v <> t.that
ON CONFLICT DO NOTHING;
-- Chỉ thay chuỗi CÓ ít nhất hai chữ (họ + tên) và dài ≥ 5: thay một chữ đơn lẻ
-- ("Lan", "Mai") là phá nát văn bản. Bỏ tên đã là tên giả (chạy lại lần hai).
DELETE FROM _che_ten
WHERE that IS NULL OR length(that) < 5 OR position(' ' IN that) = 0
   OR lower(replace(replace(public.f_unaccent(that), 'đ', 'd'), 'Đ', 'D'))
      ~ '^((khach|nguoi nha khach|nguoi gioi thieu) [0-9]+|\(da che\)|khach da xoa)$';

-- Một biểu thức chính quy gộp mọi tên — lọc nhanh "chuỗi này có tên nào không"
-- trước khi thay từng tên (Postgres giữ sẵn bản biên dịch của biểu thức).
SELECT set_config('clinicai.che_re',
    coalesce((SELECT string_agg(regexp_replace(that, '([.^$*+?()\[\]{}|\\])', '\\\1', 'g'), '|'
                                ORDER BY length(that) DESC) FROM _che_ten), ''),
    true);

CREATE FUNCTION pg_temp.che_chu(s text) RETURNS text LANGUAGE plpgsql AS $f$
DECLARE
    r record;
    re text := current_setting('clinicai.che_re', true);
BEGIN
    IF s IS NULL OR s = '' THEN
        RETURN s;
    END IF;
    IF re <> '' AND s ~ re THEN
        FOR r IN SELECT that, gia FROM _che_ten ORDER BY length(that) DESC LOOP
            IF position(r.that IN s) > 0 THEN
                s := replace(s, r.that, r.gia);
            END IF;
        END LOOP;
    END IF;
    s := regexp_replace(s, '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', 'an@vi-du.invalid', 'g');
    s := regexp_replace(s, '\+84[0-9]{9}\M', '+84900000000', 'g');
    s := regexp_replace(s, '\m0[0-9]{9}\M', '0900000000', 'g');
    s := regexp_replace(s, '\m0[0-9]{2,3}[ .][0-9]{3}[ .][0-9]{3,4}\M', '0900 000 000', 'g');
    RETURN s;
END $f$;

CREATE FUNCTION pg_temp.che_json(j jsonb, manh boolean) RETURNS jsonb LANGUAGE plpgsql AS $f$
DECLARE
    t text;
    khoa text := 'full_name|full_name_unaccent|ho_ten|ten_khach|khach_ten|patient_name'
        || '|guardian_name|nguoi_gioi_thieu|patient_info|patient_objection'
        || '|phone|phone_primary|phone_secondary|sdt|sdt_tim_kiem|so_dien_thoai'
        || '|channel_value|zalo_id|email|address|address_detail|dia_chi'
        || '|national_id_number|cccd|cmnd';
BEGIN
    IF j IS NULL THEN
        RETURN NULL;
    END IF;
    IF manh THEN
        khoa := khoa || '|ten|noi_dung|notes|note|ghi_chu|description|action_data|result_text';
    END IF;
    t := j::text;
    -- jsonb in ra dạng chuẩn `"khoá": "giá trị"`; giá trị có thể chứa \" nên
    -- khớp theo ký tự thoát, không theo dấu nháy đầu tiên.
    t := regexp_replace(t, '"(' || khoa || ')": "(?:[^"\\]|\\.)*"', '"\1": "(đã che)"', 'g');
    t := regexp_replace(t, '"(date_of_birth|ngay_sinh)": "[^"]*"', '"\1": null', 'g');
    t := pg_temp.che_chu(t);
    RETURN t::jsonb;
EXCEPTION WHEN others THEN
    -- Không bao giờ để lọt bản chưa che chỉ vì một khối JSON lạ.
    RETURN jsonb_build_object('da_che', true);
END $f$;

-- ── Tắt trigger của đúng các bảng sẽ sửa (trừ patient, patient_sdt_them) ────
CREATE TEMP TABLE _che_trigger ON COMMIT DROP AS
SELECT c.relname AS bang, t.tgname AS ten, t.tgenabled AS trang_thai
FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
WHERE NOT t.tgisinternal AND t.tgenabled <> 'D'
  AND c.relnamespace = 'public'::regnamespace
  AND c.relname IN (SELECT bang FROM _che_cot WHERE cach <> 'giu'
                    UNION SELECT 'clinic_secret')
  AND c.relname NOT IN ('patient', 'patient_sdt_them');
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT * FROM _che_trigger ORDER BY bang, ten LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE TRIGGER %I', r.bang, r.ten);
    END LOOP;
END $$;

-- Bí mật tích hợp của phòng khám (Zalo, POS…) — staging không được giữ.
DELETE FROM public.clinic_secret;

-- ── Che theo số thứ tự khách ────────────────────────────────────────────────
UPDATE public.patient_next_of_kin k SET
    full_name = CASE WHEN nullif(btrim(k.full_name), '') IS NULL THEN k.full_name
                     ELSE 'Người nhà khách ' || lpad(c.n::text, 4, '0') END,
    phone = CASE WHEN nullif(btrim(k.phone), '') IS NULL THEN k.phone
                 ELSE '06' || lpad(c.n::text, 8, '0') END,
    zalo_id = NULL
FROM _che_khach c WHERE c.id = k.clinic_patient_id;

UPDATE public.patient_contact_channel x SET
    channel_value = CASE
        WHEN x.channel_value IS NULL THEN NULL
        WHEN x.channel_value LIKE '%@%' THEN 'khach' || lpad(c.n::text, 4, '0') || '@vi-du.invalid'
        WHEN x.channel_value ~ '[0-9]{6}' THEN '05' || lpad(c.n::text, 8, '0')
        ELSE 'khach-' || lpad(c.n::text, 4, '0') END
FROM _che_khach c WHERE c.id = x.clinic_patient_id;

-- SĐT thêm: duy nhất theo (khách, số) → đánh số theo dòng.
UPDATE public.patient_sdt_them s SET so_dien_thoai = '07' || lpad(m.k::text, 8, '0')
FROM (SELECT id, row_number() OVER (ORDER BY created_at, id) AS k FROM public.patient_sdt_them) m
WHERE m.id = s.id;

UPDATE public.cskh_log l SET
    patient_info = CASE WHEN l.patient_info IS NULL THEN NULL
                        WHEN m.n IS NULL THEN '(đã che)'
                        ELSE 'Khách ' || lpad(m.n::text, 4, '0') END,
    phone = CASE WHEN l.phone IS NULL THEN NULL
                 WHEN m.n IS NULL THEN '0900000000'
                 ELSE '09' || lpad(m.n::text, 8, '0') END
FROM (SELECT x.id, c.n FROM public.cskh_log x
      LEFT JOIN _che_khach c ON c.id = x.clinic_patient_id) m
WHERE m.id = l.id;

-- patient CUỐI CÙNG: trigger của nó tính lại sdt_tim_kiem từ SĐT đã che (kể
-- cả patient_sdt_them vừa che ở trên).
UPDATE public.patient p SET
    full_name = 'Khách ' || lpad(c.n::text, 4, '0'),
    phone_primary = CASE WHEN p.phone_primary IS NULL THEN NULL
                         ELSE '09' || lpad(c.n::text, 8, '0') END,
    phone_secondary = CASE WHEN p.phone_secondary IS NULL THEN NULL
                           ELSE '08' || lpad(c.n::text, 8, '0') END,
    national_id_number = CASE WHEN p.national_id_number IS NULL THEN NULL
                              ELSE '0' || lpad(c.n::text, 11, '0') END,
    -- Lệch ỔN ĐỊNH −14…+14 ngày theo mã khách: tuổi vẫn đúng tới vài ngày
    -- (màn khám, sản khoa cần tuổi), ngày sinh thật không còn tra được.
    date_of_birth = CASE WHEN p.date_of_birth IS NULL THEN NULL
        ELSE least(p.date_of_birth + ((abs(hashtext(p.clinic_patient_id::text)) % 29) - 14), current_date) END,
    birth_year = CASE WHEN p.date_of_birth IS NULL THEN p.birth_year
        ELSE extract(year FROM least(p.date_of_birth
             + ((abs(hashtext(p.clinic_patient_id::text)) % 29) - 14), current_date))::smallint END,
    address = CASE WHEN nullif(btrim(p.address), '') IS NULL THEN p.address
        ELSE 'Số ' || c.n || ' đường Thử' || coalesce(', ' || p.ward_name, '')
             || coalesce(', ' || p.province_name, '') END,
    address_detail = CASE WHEN nullif(btrim(p.address_detail), '') IS NULL THEN p.address_detail
        ELSE 'Số ' || c.n || ' đường Thử' END,
    guardian_name = CASE WHEN nullif(btrim(p.guardian_name), '') IS NULL THEN p.guardian_name
        ELSE 'Người nhà khách ' || lpad(c.n::text, 4, '0') END,
    nguoi_gioi_thieu = CASE WHEN nullif(btrim(p.nguoi_gioi_thieu), '') IS NULL THEN p.nguoi_gioi_thieu
        ELSE 'Người giới thiệu ' || lpad(c.n::text, 4, '0') END,
    patient_objection = CASE WHEN nullif(btrim(p.patient_objection), '') IS NULL THEN p.patient_objection
        ELSE '(đã che)' END,
    occupation = pg_temp.che_chu(p.occupation),
    van_de_di_kham = pg_temp.che_chu(p.van_de_di_kham),
    uu_tien_ly_do = pg_temp.che_chu(p.uu_tien_ly_do)
FROM _che_khach c WHERE c.id = p.clinic_patient_id;

-- ── Che theo danh sách (một UPDATE mỗi bảng) ────────────────────────────────
DO $$
DECLARE
    r record;
    set_ds text;
    where_ds text;
BEGIN
    FOR r IN SELECT bang FROM _che_cot WHERE cach IN ('xoa', 'chu', 'json', 'json_manh')
             GROUP BY bang ORDER BY bang LOOP
        SELECT string_agg(format('%I = %s', cot, CASE cach
                   WHEN 'xoa' THEN format('CASE WHEN nullif(btrim(%I), '''') IS NULL THEN %I ELSE ''(đã che)'' END', cot, cot)
                   WHEN 'chu' THEN format('pg_temp.che_chu(%I)', cot)
                   WHEN 'json' THEN format('pg_temp.che_json(%I, false)', cot)
                   ELSE format('pg_temp.che_json(%I, true)', cot) END), ', ' ORDER BY cot),
               string_agg(format('%I IS NOT NULL', cot), ' OR ' ORDER BY cot)
          INTO set_ds, where_ds
        FROM _che_cot WHERE bang = r.bang AND cach IN ('xoa', 'chu', 'json', 'json_manh');
        EXECUTE format('UPDATE public.%I SET %s WHERE %s', r.bang, set_ds, where_ds);
    END LOOP;
END $$;

-- ── Bật lại trigger, ĐÚNG trạng thái cũ ─────────────────────────────────────
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT * FROM _che_trigger ORDER BY bang, ten LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE %s TRIGGER %I', r.bang,
            CASE r.trang_thai WHEN 'A' THEN 'ALWAYS' WHEN 'R' THEN 'REPLICA' ELSE '' END, r.ten);
    END LOOP;
END $$;

DROP FUNCTION pg_temp.che_json(jsonb, boolean);
DROP FUNCTION pg_temp.che_chu(text);
SELECT set_config('clinicai.che_re', '', true);
