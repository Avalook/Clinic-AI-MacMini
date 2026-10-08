-- KHO RIÊNG TỪNG CƠ SỞ (Tuyền chốt 08/10/2026, mở cơ sở Hào Nam).
--
-- Lô thuốc và phiếu kho thuộc về MỘT cơ sở (`clinic_location`). Lô cũ thuộc
-- cơ sở đang có (Kim Ngưu); lô Hào Nam sẽ được chép sang bằng script riêng —
-- nên CÙNG số lô phải tồn tại được ở hai cơ sở: khoá duy nhất đổi từ
-- (clinic_id, batch_code) sang (clinic_id, location_id, batch_code).
--
-- Bất biến ép Ở ĐÂY, không ở Python (SO-LUAT Phần 6):
--   * lô / phiếu trỏ đúng một cơ sở CỦA CHÍNH phòng khám (khoá ngoại ghép
--     (location_id, clinic_id) → clinic_location (id, clinic_id));
--   * phân lô cho một lượt chỉ nhận lô của cơ sở của LƯỢT
--     (`coalesce(visit.location_id, appointment.location_id)`);
--   * dòng sổ kho giao thuốc theo dòng đơn (`ref_type = 'prescription'` —
--     giao luồng cũ, gán lô cho lần giao chưa gán lô) cũng vậy;
--   * dòng phiếu kho chỉ trỏ lô cùng cơ sở với phiếu.
-- Lượt không xác định được cơ sở (visit và lịch hẹn đều trống — hồ sơ rất
-- cũ) thì KHÔNG chặn: không có gì để so, chặn là khoá cứng thao tác.
--
-- KHÔNG làm chuyển kho giữa cơ sở (tạm làm tay: phiếu xuất + phiếu nhập).
--
-- Chạy lại nhiều lần được.

-- ── 0. Khoá ghép cho clinic_location ───────────────────────────────────
-- Khoá ngoại ghép (location_id, clinic_id) cần một khoá duy nhất đúng hai
-- cột ấy bên bảng được trỏ. `id` đã là khoá chính nên ràng buộc này không
-- bao giờ vỡ trên dữ liệu có sẵn.
DO $uq$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'uq_clinic_location_id_clinic'
           AND conrelid = 'public.clinic_location'::regclass
    ) THEN
        ALTER TABLE public.clinic_location
            ADD CONSTRAINT uq_clinic_location_id_clinic UNIQUE (id, clinic_id);
    END IF;
END
$uq$;

-- ── 1. Cột mới ─────────────────────────────────────────────────────────
ALTER TABLE public.drug_batch ADD COLUMN IF NOT EXISTS location_id uuid;
ALTER TABLE public.phieu_kho  ADD COLUMN IF NOT EXISTS location_id uuid;

-- ── 2. Điền cơ sở cho dữ liệu cũ ───────────────────────────────────────
-- Prod 08/10: một phòng khám, MỘT cơ sở đang hoạt động (Kim Ngưu), 81 lô,
-- 0 phiếu kho. Chọn cơ sở theo thứ tự, KHÔNG đoán theo tên:
--   1. phòng khám có đúng MỘT cơ sở is_active → cơ sở ấy (trường hợp prod);
--   2. không thì cơ sở mã 'KN' (Kim Ngưu — nơi kho đã nằm từ trước khi có
--      cơ sở thứ hai);
--   3. không thì cơ sở tạo sớm nhất (cơ sở gốc của phòng khám; mọi phòng
--      khám có ít nhất một cơ sở từ 20260730000003).
-- (Hàm tạm trong pg_temp thay vì bảng tạm: không phụ thuộc migration có chạy
-- trong một giao dịch hay không.)
CREATE OR REPLACE FUNCTION pg_temp.co_so_kho_mac_dinh(p_clinic_id uuid)
 RETURNS uuid
 LANGUAGE sql
 STABLE
AS $function$
    SELECT l.id
      FROM (
          SELECT l.*,
                 count(*) FILTER (WHERE coalesce(l.is_active, false))
                     OVER () AS so_dang_mo
            FROM public.clinic_location l
           WHERE l.clinic_id = p_clinic_id
      ) l
     ORDER BY (l.so_dang_mo = 1 AND coalesce(l.is_active, false)) DESC,
              (l.code = 'KN') DESC,
              l.created_at NULLS LAST,
              l.id
     LIMIT 1
$function$;

UPDATE public.drug_batch b
   SET location_id = pg_temp.co_so_kho_mac_dinh(b.clinic_id)
 WHERE b.location_id IS NULL;

-- phieu_kho CHỈ THÊM (trigger `phieu_kho_chi_them` chặn UPDATE) — tắt đúng
-- trigger ấy trong lúc điền cột mới, bật lại ngay. Migration áp trong một
-- giao dịch (apply-pending-migrations.sh) nên không ai ghi lọt khe hở này.
ALTER TABLE public.phieu_kho DISABLE TRIGGER phieu_kho_chi_them;
UPDATE public.phieu_kho p
   SET location_id = pg_temp.co_so_kho_mac_dinh(p.clinic_id)
 WHERE p.location_id IS NULL;
ALTER TABLE public.phieu_kho ENABLE TRIGGER phieu_kho_chi_them;

ALTER TABLE public.drug_batch ALTER COLUMN location_id SET NOT NULL;
ALTER TABLE public.phieu_kho  ALTER COLUMN location_id SET NOT NULL;

-- ── 3. Khoá ngoại ghép: cơ sở phải của chính phòng khám ────────────────
ALTER TABLE public.drug_batch DROP CONSTRAINT IF EXISTS drug_batch_location_fkey;
ALTER TABLE public.drug_batch ADD CONSTRAINT drug_batch_location_fkey
    FOREIGN KEY (location_id, clinic_id)
    REFERENCES public.clinic_location (id, clinic_id) ON DELETE RESTRICT;

ALTER TABLE public.phieu_kho DROP CONSTRAINT IF EXISTS phieu_kho_location_fkey;
ALTER TABLE public.phieu_kho ADD CONSTRAINT phieu_kho_location_fkey
    FOREIGN KEY (location_id, clinic_id)
    REFERENCES public.clinic_location (id, clinic_id) ON DELETE RESTRICT;

-- ── 4. Số lô duy nhất THEO CƠ SỞ ───────────────────────────────────────
-- Giữ nguyên UNIQUE (id, clinic_id) và các khoá ngoại ghép trỏ vào nó.
ALTER TABLE public.drug_batch DROP CONSTRAINT IF EXISTS uq_drug_batch_clinic_code;
ALTER TABLE public.drug_batch DROP CONSTRAINT IF EXISTS uq_drug_batch_clinic_location_code;
ALTER TABLE public.drug_batch ADD CONSTRAINT uq_drug_batch_clinic_location_code
    UNIQUE (clinic_id, location_id, batch_code);

CREATE INDEX IF NOT EXISTS phieu_kho_theo_co_so
    ON public.phieu_kho (clinic_id, location_id, loai, tao_luc DESC);

COMMENT ON COLUMN public.drug_batch.location_id IS
    'Cơ sở giữ lô (kho riêng từng cơ sở, 08/10/2026). Cùng số lô được có ở hai cơ sở.';
COMMENT ON COLUMN public.phieu_kho.location_id IS
    'Cơ sở của phiếu nhập / kiểm kho (08/10/2026). Mã phiếu mang mã cơ sở.';

-- ── 5. Cơ sở của một lượt ──────────────────────────────────────────────
-- MỘT định nghĩa cho cả trigger lẫn backend (Python gọi hàm này để nói lỗi
-- bằng tiếng Việt trước khi trigger từ chối).
CREATE OR REPLACE FUNCTION public.co_so_cua_luot(p_clinic_id uuid, p_visit_id uuid)
 RETURNS uuid
 LANGUAGE sql
 STABLE
AS $function$
    SELECT coalesce(v.location_id, a.location_id)
      FROM public.visit v
      LEFT JOIN public.appointment a
        ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
     WHERE v.clinic_id = p_clinic_id AND v.visit_id = p_visit_id
$function$;

COMMENT ON FUNCTION public.co_so_cua_luot(uuid, uuid) IS
    'Cơ sở của lượt = coalesce(visit.location_id, appointment.location_id); NULL = không xác định.';

-- Lô có dùng được cho lượt không: đúng khi lượt không xác định được cơ sở.
CREATE OR REPLACE FUNCTION public.lo_dung_co_so_luot(
    p_clinic_id uuid, p_visit_id uuid, p_drug_batch_id uuid
)
 RETURNS boolean
 LANGUAGE sql
 STABLE
AS $function$
    SELECT CASE
               WHEN public.co_so_cua_luot(p_clinic_id, p_visit_id) IS NULL THEN true
               ELSE coalesce((
                   SELECT b.location_id = public.co_so_cua_luot(p_clinic_id, p_visit_id)
                     FROM public.drug_batch b
                    WHERE b.id = p_drug_batch_id AND b.clinic_id = p_clinic_id
               ), true)  -- lô không có: để khoá ngoại / trigger khác nói
           END
$function$;

-- ── 6. Phân lô: lô phải thuộc cơ sở của lượt ───────────────────────────
-- Trigger RIÊNG (không chép lại cả `prescription_allocation_guard`): chỉ
-- một luật, một chỗ đọc. Chỉ INSERT — guard sẵn có đã chặn đổi
-- drug_batch_id / visit_id tại chỗ.
CREATE OR REPLACE FUNCTION public.prescription_allocation_dung_co_so()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF NOT public.lo_dung_co_so_luot(NEW.clinic_id, NEW.visit_id, NEW.drug_batch_id) THEN
        RAISE EXCEPTION 'Phân lô: lô thuộc kho cơ sở khác với cơ sở của lượt khám'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_prescription_allocation_dung_co_so
    ON public.prescription_allocation;
CREATE TRIGGER trg_prescription_allocation_dung_co_so
    BEFORE INSERT ON public.prescription_allocation
    FOR EACH ROW EXECUTE FUNCTION public.prescription_allocation_dung_co_so();

-- ── 7. Sổ kho giao theo dòng đơn: lô phải thuộc cơ sở của lượt ──────────
-- Đường giao không qua phân lô (lần thu cũ / thu không chờ kho, gán lô sau
-- cho lần giao chưa gán lô) ghi DISPENSE với ref_type 'prescription'.
-- Dòng có allocation_id đã được §6 kiểm ở phân lô.
CREATE OR REPLACE FUNCTION public.inventory_txn_dung_co_so()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_visit uuid;
BEGIN
    SELECT r.visit_id INTO v_visit
      FROM public.prescription r
     WHERE r.id = NEW.ref_id AND r.clinic_id = NEW.clinic_id;
    IF v_visit IS NOT NULL
       AND NOT public.lo_dung_co_so_luot(NEW.clinic_id, v_visit, NEW.drug_batch_id) THEN
        RAISE EXCEPTION 'Sổ kho: lô thuộc kho cơ sở khác với cơ sở của lượt khám'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_inventory_txn_dung_co_so ON public.inventory_txn;
CREATE TRIGGER trg_inventory_txn_dung_co_so
    BEFORE INSERT ON public.inventory_txn
    FOR EACH ROW
    WHEN (NEW.ref_type = 'prescription' AND NEW.ref_id IS NOT NULL)
    EXECUTE FUNCTION public.inventory_txn_dung_co_so();

-- ── 8. Dòng phiếu kho: lô cùng cơ sở với phiếu ─────────────────────────
CREATE OR REPLACE FUNCTION public.phieu_kho_dong_dung_co_so()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM public.phieu_kho p
          JOIN public.drug_batch b
            ON b.id = NEW.drug_batch_id AND b.clinic_id = NEW.clinic_id
         WHERE p.id = NEW.phieu_kho_id AND p.clinic_id = NEW.clinic_id
           AND b.location_id IS DISTINCT FROM p.location_id
    ) THEN
        RAISE EXCEPTION 'Phiếu kho: lô thuộc kho cơ sở khác với phiếu'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_phieu_kho_dong_dung_co_so ON public.phieu_kho_dong;
CREATE TRIGGER trg_phieu_kho_dong_dung_co_so
    BEFORE INSERT ON public.phieu_kho_dong
    FOR EACH ROW EXECUTE FUNCTION public.phieu_kho_dong_dung_co_so();

-- ── 9. Khối kiểm cuối ──────────────────────────────────────────────────
DO $kiem$
DECLARE
    v_n integer;
BEGIN
    SELECT count(*) INTO v_n FROM public.drug_batch WHERE location_id IS NULL;
    IF v_n <> 0 THEN
        RAISE EXCEPTION 'kho_theo_co_so: % lô chưa có cơ sở', v_n;
    END IF;
    SELECT count(*) INTO v_n FROM public.phieu_kho WHERE location_id IS NULL;
    IF v_n <> 0 THEN
        RAISE EXCEPTION 'kho_theo_co_so: % phiếu kho chưa có cơ sở', v_n;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_drug_batch_clinic_code'
                  AND conrelid = 'public.drug_batch'::regclass) THEN
        RAISE EXCEPTION 'kho_theo_co_so: khoá cũ uq_drug_batch_clinic_code còn';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_drug_batch_clinic_location_code'
                      AND conrelid = 'public.drug_batch'::regclass) THEN
        RAISE EXCEPTION 'kho_theo_co_so: thiếu uq_drug_batch_clinic_location_code';
    END IF;
    -- Khoá ngoại ghép trỏ vào lô (phiếu_kho_dong, phân lô…) cần UNIQUE (id, clinic_id).
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c
         WHERE c.conrelid = 'public.drug_batch'::regclass AND c.contype IN ('u', 'p')
           AND (SELECT array_agg(a.attname::text ORDER BY a.attname)
                  FROM pg_attribute a
                 WHERE a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey))
               = ARRAY['clinic_id', 'id']
    ) THEN
        RAISE EXCEPTION 'kho_theo_co_so: mất UNIQUE (id, clinic_id) của drug_batch';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                    WHERE tgname = 'phieu_kho_chi_them'
                      AND tgrelid = 'public.phieu_kho'::regclass
                      AND tgenabled = 'O') THEN
        RAISE EXCEPTION 'kho_theo_co_so: trigger phieu_kho_chi_them chưa bật lại';
    END IF;
END
$kiem$;
