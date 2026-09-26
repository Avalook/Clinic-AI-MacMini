-- Dọn sạch dữ liệu khách trên PROD trước khi bàn giao (viết lại 25/09/2026).
--
-- ĐỪNG CHẠY TAY FILE NÀY — chạy qua `scripts/don-prod-truoc-ban-giao.sh`: nó
-- sao lưu trước, dừng các dịch vụ đang ghi, dọn tệp kết quả, rồi bật lại.
--
-- XOÁ: mọi thứ sinh ra từ KHÁCH — bệnh nhân, lịch hẹn, lượt khám, bệnh án,
-- chỉ định, thanh toán, đơn thuốc, việc/nhắc việc, thông báo, sổ sự kiện.
-- GIỮ: cấu hình — phòng khám, cơ sở, phòng, nhân sự + tài khoản + quyền, dịch
-- vụ + giá, mẫu phiếu/mẫu kết quả, danh mục thuốc, lịch trực, luật đặt lịch.
--
-- VÌ SAO VIẾT LẠI bản 14/08: bản cũ thiếu ~30 bảng ra đời sau nó (domain_event,
-- service_order, doi_tac_nhan_viec, prescription_allocation, …) và dùng
-- `TRUNCATE … CASCADE`. Với khoá ngoại mới, CASCADE từ `prescription` kéo theo
-- `prescription_allocation` → `inventory_txn`: xoá SẠCH lịch sử kho mà tồn kho
-- (`drug_batch.quantity_on_hand`) vẫn giữ số cũ — không báo gì.
--
-- BỐN CHỐT AN TOÀN
--   1. KHÔNG CASCADE. Bảng nào ngoài danh sách còn trỏ vào bảng bị xoá thì
--      Postgres từ chối, cả giao dịch cuộn lại. Có bảng mới → script dừng,
--      chứ không lặng lẽ xoá lan.
--   2. Kiểm đồ thị khoá ngoại TRƯỚC khi xoá, báo tên bảng cụ thể.
--   3. Chỉ tắt đúng các trigger chặn xoá (không dùng session_replication_role,
--      vì nó tắt luôn cả kiểm khoá ngoại khi DELETE). Bật lại trong cùng giao
--      dịch.
--   4. Mặc định là CHẠY THỬ: làm thật toàn bộ rồi ROLLBACK. Chỉ `-v that=1`
--      mới COMMIT.
--
-- Biến psql:
--   that=1     COMMIT thật (thiếu = chạy thử, cuộn lại)
--   kho=xoa    xoá cả tồn kho thuốc (lô + phiếu kho) — kho về 0, nhập tồn đầu
--              kỳ lại. Mặc định `giu`: giữ lô và phiếu nhập/điều chỉnh tay, chỉ
--              bỏ phiếu xuất/bán/trả gắn với khách và TRẢ LẠI số lượng vào lô.

\set ON_ERROR_STOP on
\if :{?that}
\else
  \set that 0
\endif
\if :{?kho}
\else
  \set kho giu
\endif

SELECT (:'kho' = 'xoa') AS xoa_kho, (:'that' = '1') AS lam_that \gset

BEGIN;
SET LOCAL lock_timeout = '10s';

CREATE TEMP TABLE bang_xoa (ten text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO bang_xoa (ten) VALUES
  -- Bệnh nhân và hồ sơ treo vào người
  ('patient'), ('patient_contact_channel'), ('patient_medical_profile'),
  ('patient_next_of_kin'), ('patient_sdt_them'), ('patient_link'),
  ('pregnancy'), ('mpi_merge_queue'), ('clinical_data_consent'),
  -- Lịch hẹn, chăm sóc khách
  ('appointment'), ('appointment_doi_lich'), ('care_episode'),
  ('follow_up_case'), ('round_requirement'), ('review_round'), ('slot_hold'),
  ('nhac_tai_kham'), ('hen_goi_lai'), ('tuong_tac_cskh'), ('cskh_action'),
  ('cskh_log'), ('phan_hoi_khach'), ('service_log'),
  -- Lượt khám, bệnh án, kết quả
  ('visit'), ('visit_amendment'), ('visit_route'), ('visit_gate_override'),
  ('encounter_flow'), ('queue_entry'), ('consultation'), ('consultation_note'),
  ('clinical_record'), ('clinical_form_response'), ('clinical_release'),
  ('phieu_kham_luot'), ('phieu_kham_lich_su'), ('ultrasound_record'), ('lab_result'),
  ('vital_measurement'), ('form_instance'), ('form_result_release'),
  ('result_correction'),
  -- Chỉ định, đối tác, tệp kết quả
  ('service_order'), ('service_order_draft'), ('service_selection_state'),
  ('service_execution_attempt'), ('doi_tac_nhan_viec'), ('tep_ket_qua'),
  -- Thanh toán
  ('payment'), ('payment_cycle'), ('payment_bill_line'), ('payment_refund'),
  ('payment_refund_line'), ('pos_outbox'),
  -- Đơn thuốc
  ('prescription'), ('prescription_allocation'), ('prescription_correction'),
  ('drug_return'),
  -- Việc, nhắc việc, thông báo, góp ý
  ('work_item'), ('work_item_dependency'), ('work_item_event'),
  ('staff_task'), ('nhac_viec_ca_nhan'), ('thong_bao'), ('owner_feedback'),
  -- Sổ sự kiện, hẹn giờ, biên nhận lệnh
  ('domain_event'), ('event_delivery'), ('luot_dong_thoi_gian'),
  ('event_log'), ('hen_gio'), ('command_receipt'), ('idempotency_key');

\if :xoa_kho
INSERT INTO bang_xoa (ten) VALUES ('drug_batch'), ('inventory_txn');
\endif

-- ── Chốt 2: đồ thị khoá ngoại ────────────────────────────────────────────
DO $$
DECLARE
  thieu text;
  lan text;
BEGIN
  SELECT string_agg(b.ten, ', ') INTO thieu
  FROM bang_xoa b WHERE to_regclass('public.' || b.ten) IS NULL;
  IF thieu IS NOT NULL THEN
    RAISE EXCEPTION 'Bảng không tồn tại: %', thieu;
  END IF;

  -- Bảng GIỮ mà trỏ vào bảng XOÁ. Ngoại lệ duy nhất: inventory_txn ở chế độ
  -- giữ kho — các dòng gắn với khách được xoá riêng ở dưới.
  SELECT string_agg(DISTINCT format('%s → %s', con.conrelid::regclass,
                                    con.confrelid::regclass), '; ')
    INTO lan
  FROM pg_constraint con
  JOIN pg_namespace n ON n.oid = con.connamespace AND n.nspname = 'public'
  WHERE con.contype = 'f'
    AND con.confrelid::regclass::text IN (SELECT ten FROM bang_xoa)
    AND con.conrelid::regclass::text NOT IN (SELECT ten FROM bang_xoa)
    AND con.conrelid::regclass::text <> 'inventory_txn';
  IF lan IS NOT NULL THEN
    RAISE EXCEPTION 'Bảng GIỮ đang trỏ vào bảng XOÁ (thêm vào danh sách hoặc bỏ ra): %', lan;
  END IF;
END $$;

-- ── Trước khi xoá ────────────────────────────────────────────────────────
DO $$
DECLARE r record; n bigint; tong bigint := 0;
BEGIN
  FOR r IN SELECT ten FROM bang_xoa ORDER BY ten LOOP
    EXECUTE format('SELECT count(*) FROM public.%I', r.ten) INTO n;
    tong := tong + n;
    IF n > 0 THEN RAISE NOTICE 'sẽ xoá  %  %', rpad(r.ten, 28), n; END IF;
  END LOOP;
  RAISE NOTICE 'TỔNG sẽ xoá: % dòng', tong;
END $$;

-- ── Giữ kho: bỏ phiếu kho gắn với khách, trả số lượng về lô ─────────────
\if :xoa_kho
\else
-- Phiếu trả thuốc trỏ vào phiếu xuất: bỏ nó trước (nó cũng nằm trong danh sách xoá).
TRUNCATE public.drug_return;
ALTER TABLE public.inventory_txn DISABLE TRIGGER inventory_txn_append_only;
WITH RECURSIVE bo AS (
  SELECT id FROM public.inventory_txn
  WHERE allocation_id IS NOT NULL OR payment_cycle_id IS NOT NULL
     OR ref_type IN ('prescription', 'payment_cycle', 'drug_return')
  UNION
  SELECT t.id FROM public.inventory_txn t JOIN bo ON t.reverses_txn_id = bo.id
), xoa AS (
  DELETE FROM public.inventory_txn t USING bo WHERE t.id = bo.id
  RETURNING t.drug_batch_id, t.quantity
), tra AS (
  UPDATE public.drug_batch b
     SET quantity_on_hand = b.quantity_on_hand - s.q, updated_at = now()
    FROM (SELECT drug_batch_id, sum(quantity) AS q FROM xoa GROUP BY 1) s
   WHERE b.id = s.drug_batch_id
  RETURNING b.id
)
SELECT (SELECT count(*) FROM xoa) AS phieu_kho_bo,
       (SELECT count(*) FROM tra) AS lo_tra_lai;
ALTER TABLE public.inventory_txn ENABLE TRIGGER inventory_txn_append_only;
\endif

-- ── Chốt 3 + xoá ─────────────────────────────────────────────────────────
-- Ở chế độ giữ kho, inventory_txn (GIỮ) còn khoá ngoại trỏ vào
-- prescription_allocation / payment_cycle (XOÁ). TRUNCATE từ chối theo sự TỒN
-- TẠI của khoá ngoại chứ không theo dữ liệu — nên gỡ tạm, xoá, rồi gắn lại
-- nguyên văn. Gắn lại = Postgres kiểm lại toàn bộ dòng còn lại.
CREATE TEMP TABLE fk_tam ON COMMIT DROP AS
SELECT con.conname AS ten, pg_get_constraintdef(con.oid) AS dinh_nghia
FROM pg_constraint con
WHERE con.contype = 'f'
  AND con.conrelid = 'public.inventory_txn'::regclass
  AND con.confrelid::regclass::text IN (SELECT ten FROM bang_xoa)
  AND 'inventory_txn' NOT IN (SELECT ten FROM bang_xoa);

DO $$
DECLARE r record; danh_sach text;
BEGIN
  FOR r IN SELECT ten FROM fk_tam LOOP
    EXECUTE format('ALTER TABLE public.inventory_txn DROP CONSTRAINT %I', r.ten);
  END LOOP;

  -- Chỉ tắt trigger có bắt sự kiện TRUNCATE (các chốt "no_truncate").
  FOR r IN
    SELECT c.relname, t.tgname FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
    WHERE NOT t.tgisinternal AND (t.tgtype & 32) <> 0
      AND c.relname IN (SELECT ten FROM bang_xoa)
  LOOP
    EXECUTE format('ALTER TABLE public.%I DISABLE TRIGGER %I', r.relname, r.tgname);
  END LOOP;

  SELECT string_agg(format('public.%I', ten), ', ' ORDER BY ten)
    INTO danh_sach FROM bang_xoa;
  EXECUTE 'TRUNCATE ' || danh_sach || ' RESTART IDENTITY';

  FOR r IN SELECT ten, dinh_nghia FROM fk_tam LOOP
    EXECUTE format('ALTER TABLE public.inventory_txn ADD CONSTRAINT %I %s',
                   r.ten, r.dinh_nghia);
  END LOOP;

  FOR r IN
    SELECT c.relname, t.tgname FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
    WHERE NOT t.tgisinternal AND (t.tgtype & 32) <> 0
      AND c.relname IN (SELECT ten FROM bang_xoa)
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE TRIGGER %I', r.relname, r.tgname);
  END LOOP;

  -- Mã bệnh nhân / mã xét nghiệm đếm lại từ 1.
  IF to_regclass('public.patient_code_seq') IS NOT NULL THEN
    ALTER SEQUENCE public.patient_code_seq RESTART;
  END IF;
  IF to_regclass('public.lab_result_code_seq') IS NOT NULL THEN
    ALTER SEQUENCE public.lab_result_code_seq RESTART;
  END IF;
END $$;

-- ── Sau khi xoá: phải toàn 0, và phần GIỮ còn nguyên ─────────────────────
DO $$
DECLARE r record; n bigint; con bigint := 0;
BEGIN
  FOR r IN SELECT ten FROM bang_xoa LOOP
    EXECUTE format('SELECT count(*) FROM public.%I', r.ten) INTO n;
    con := con + n;
  END LOOP;
  IF con <> 0 THEN RAISE EXCEPTION 'Còn % dòng chưa xoá', con; END IF;
  IF EXISTS (SELECT 1 FROM public.drug_batch WHERE quantity_on_hand < 0) THEN
    RAISE EXCEPTION 'Có lô thuốc tồn âm sau khi trả lại';
  END IF;
  -- Còn trigger chặn xoá nào đang tắt thì dừng (không để hở ra ngoài).
  IF EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
             WHERE NOT t.tgisinternal AND t.tgenabled = 'D'
               AND c.relname IN (SELECT ten FROM bang_xoa UNION ALL SELECT 'inventory_txn')) THEN
    RAISE EXCEPTION 'Còn trigger bị tắt';
  END IF;
END $$;

SELECT 'GIỮ: nhân sự' AS muc, count(*) FROM public.staff
UNION ALL SELECT 'GIỮ: phòng', count(*) FROM public.clinic_room
UNION ALL SELECT 'GIỮ: dịch vụ', count(*) FROM public.service_type
UNION ALL SELECT 'GIỮ: giá', count(*) FROM public.service_price
UNION ALL SELECT 'GIỮ: danh mục thuốc', count(*) FROM public.drug_catalog
UNION ALL SELECT 'GIỮ: lô thuốc', count(*) FROM public.drug_batch
UNION ALL SELECT 'GIỮ: phiếu kho', count(*) FROM public.inventory_txn
UNION ALL SELECT 'GIỮ: ca trực', count(*) FROM public.work_roster
UNION ALL SELECT 'GIỮ: mẫu phiếu', count(*) FROM public.form_definition;

\if :lam_that
COMMIT;
\echo '>>> ĐÃ XOÁ THẬT (COMMIT).'
\else
ROLLBACK;
\echo '>>> CHẠY THỬ: mọi thay đổi đã cuộn lại, chưa xoá gì.'
\endif
