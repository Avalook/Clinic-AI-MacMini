-- Contract tiền–thuốc, CP6 bước 4a (20/09/2026): ĐÍNH CHÍNH ĐƠN THUỐC — nền DB.
--
-- Bác sĩ đổi đơn sau khi nhà thuốc / thu ngân đã đụng tới dòng đơn: KHÔNG sửa
-- nghĩa của dòng cũ tại chỗ, mà GỠ nó khỏi đơn hiện hành và (nếu thay thuốc)
-- tạo DÒNG THAY THẾ có id mới. Dòng cũ ở lại làm lịch sử — mọi tiền / kho đã
-- phát sinh vẫn trỏ vào đúng id của nó.
--
--   dòng hiện hành  = prescription.removed_at IS NULL
--   dòng lịch sử    = đã gỡ; superseded_by_id = dòng thay nó (NULL = bỏ hẳn)
--   một lần đính chính = một dòng prescription_correction (lý do, người, lúc,
--                        và amendment_id khi hồ sơ đã ký)
--
-- Mức dấu vết của một dòng (prescription_muc_dau_vet), duyệt 20/09:
--   0  A  chưa gì cả                     → sửa tại chỗ mọi thứ, xoá cứng được
--   1  B  đã có phân lô (kể cả đã nhả) hoặc đã chốt/từ chối, chưa có gì dưới
--         → đổi liều / lưu ý tại chỗ được; đổi thuốc / số lượng phải thay thế
--   2  C  có ảnh chụp hoá đơn, phân lô gắn lần thu, SALE, DISPENSE (theo phân lô
--         hoặc luồng cũ) hoặc khách trả → MỌI thay đổi chuyên môn, kể cả liều /
--         lưu ý, phải thay thế: sửa tại chỗ là viết lại hướng dẫn "lúc giao".
--
-- Dòng lịch sử (duyệt 20/09, Q3): BẤT BIẾN về nội dung, và KHÔNG nhận tác động
-- thương mại MỚI — không phân lô mới, không gắn lần thu, không SALE, không
-- DISPENSE. Tác động đã có giữ nguyên và đối soát bằng CP5 (SALE_REVERSAL,
-- khách trả, hoàn tiền) — những thứ ấy vẫn được.
--
-- Hồ sơ đã ký (visit FINALIZED / AMENDED): mọi thay đổi chuyên môn của đơn phải
-- đi qua đường đính chính hồ sơ — giao dịch mang `SET LOCAL
-- clinicai.amendment_id` trỏ tới dòng `visit_amendment` vừa ghi CÙNG giao dịch,
-- cùng phòng khám, cùng lượt. ĐÂY LÀ LƯỚI TOÀN VẸN chống code đi nhầm đường,
-- KHÔNG phải ranh giới bảo mật: service_role đặt được biến phiên. Quyền của
-- người đính chính do service/API kiểm.
--
-- Việc vận hành của nhà thuốc (xác định thuốc, số mua, giao, chốt) sau khi ký
-- vẫn ghi được — đó không phải nội dung đã ký.
--
-- Không backfill: cột mới rỗng = mọi dòng hiện có là dòng hiện hành. Đo prod
-- 20/09 (chỉ đọc): 3 dòng đơn, 0 dòng visit_id NULL. Chạy lại được.

-- ── 1. Neo ghép ───────────────────────────────────────────────────────────
DO $cp6_4a_neo$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.visit_amendment'::regclass
                      AND conname = 'uq_visit_amendment_id_clinic_visit') THEN
        ALTER TABLE public.visit_amendment
            ADD CONSTRAINT uq_visit_amendment_id_clinic_visit
            UNIQUE (amendment_id, clinic_id, visit_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.prescription'::regclass
                      AND conname = 'uq_prescription_id_clinic_visit') THEN
        ALTER TABLE public.prescription
            ADD CONSTRAINT uq_prescription_id_clinic_visit
            UNIQUE (id, clinic_id, visit_id);
    END IF;
END $cp6_4a_neo$;

-- Tra ảnh chụp hoá đơn theo dòng đơn (mức dấu vết).
CREATE INDEX IF NOT EXISTS idx_payment_bill_line_nguon
    ON public.payment_bill_line (clinic_id, source_type, source_id);

-- ── 2. Một lần đính chính ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.prescription_correction (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id      uuid NOT NULL,
    corrected_by  uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    corrected_at  timestamptz NOT NULL DEFAULT now(),
    reason        text NOT NULL,
    amendment_id  uuid,
    CONSTRAINT prescription_correction_ly_do CHECK (length(btrim(reason)) >= 5),
    CONSTRAINT prescription_correction_visit_fkey
        FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit(clinic_id, visit_id) ON DELETE RESTRICT,
    CONSTRAINT prescription_correction_amendment_fkey
        FOREIGN KEY (amendment_id, clinic_id, visit_id)
        REFERENCES public.visit_amendment(amendment_id, clinic_id, visit_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_prescription_correction_neo UNIQUE (id, clinic_id, visit_id)
);
CREATE INDEX IF NOT EXISTS idx_prescription_correction_visit
    ON public.prescription_correction (clinic_id, visit_id);

-- ── 3. Cột lịch sử trên dòng đơn ──────────────────────────────────────────
ALTER TABLE public.prescription
    ADD COLUMN IF NOT EXISTS removed_at timestamptz,
    ADD COLUMN IF NOT EXISTS removed_by uuid,
    ADD COLUMN IF NOT EXISTS removal_reason text,
    ADD COLUMN IF NOT EXISTS removed_in_correction_id uuid,
    ADD COLUMN IF NOT EXISTS superseded_by_id uuid,
    ADD COLUMN IF NOT EXISTS created_in_correction_id uuid;

DO $cp6_4a_rang_buoc$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.prescription'::regclass
                      AND conname = 'prescription_removed_by_fkey') THEN
        ALTER TABLE public.prescription
            ADD CONSTRAINT prescription_removed_by_fkey
                FOREIGN KEY (removed_by) REFERENCES public.staff(id) ON DELETE RESTRICT,
            -- Ghép cùng phòng khám VÀ cùng lượt: không gỡ bằng lần đính chính
            -- của lượt khác, không thay bằng dòng của lượt khác.
            ADD CONSTRAINT prescription_removed_in_correction_fkey
                FOREIGN KEY (removed_in_correction_id, clinic_id, visit_id)
                REFERENCES public.prescription_correction(id, clinic_id, visit_id)
                ON DELETE RESTRICT,
            ADD CONSTRAINT prescription_created_in_correction_fkey
                FOREIGN KEY (created_in_correction_id, clinic_id, visit_id)
                REFERENCES public.prescription_correction(id, clinic_id, visit_id)
                ON DELETE RESTRICT,
            ADD CONSTRAINT prescription_superseded_by_fkey
                FOREIGN KEY (superseded_by_id, clinic_id, visit_id)
                REFERENCES public.prescription(id, clinic_id, visit_id)
                ON DELETE RESTRICT,
            -- Bốn dấu vết gỡ đi cùng nhau.
            ADD CONSTRAINT prescription_go_du_dau_vet CHECK (
                (removed_at IS NULL) = (removed_by IS NULL)
                AND (removed_at IS NULL) = (removal_reason IS NULL)
                AND (removed_at IS NULL) = (removed_in_correction_id IS NULL)),
            ADD CONSTRAINT prescription_go_co_ly_do CHECK (
                removal_reason IS NULL OR length(btrim(removal_reason)) >= 5),
            ADD CONSTRAINT prescription_thay_the_la_da_go CHECK (
                superseded_by_id IS NULL OR removed_at IS NOT NULL),
            ADD CONSTRAINT prescription_khong_tu_thay CHECK (
                superseded_by_id IS DISTINCT FROM id),
            ADD CONSTRAINT prescription_khong_sinh_roi_go_cung_lan CHECK (
                removed_in_correction_id IS NULL
                OR created_in_correction_id IS DISTINCT FROM removed_in_correction_id),
            -- Khoá ngoại MATCH SIMPLE bỏ qua NULL: dòng không lượt (di sản) không
            -- được tham gia đính chính.
            ADD CONSTRAINT prescription_dinh_chinh_can_luot CHECK (
                visit_id IS NOT NULL
                OR (removed_in_correction_id IS NULL
                    AND created_in_correction_id IS NULL
                    AND superseded_by_id IS NULL));
    END IF;
END $cp6_4a_rang_buoc$;

-- Một dòng mới thay tối đa MỘT dòng cũ (tách A → B + C: C là dòng thêm mới
-- trong cùng lần đính chính).
CREATE UNIQUE INDEX IF NOT EXISTS uq_prescription_thay_mot
    ON public.prescription (superseded_by_id) WHERE superseded_by_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prescription_hien_hanh
    ON public.prescription (clinic_id, visit_id) WHERE removed_at IS NULL;

-- ── 4. Hàm dùng chung ─────────────────────────────────────────────────────
-- Mức dấu vết: 0 = A, 1 = B, 2 = C (xem đầu file).
CREATE OR REPLACE FUNCTION public.prescription_muc_dau_vet(p_id uuid, p_clinic uuid)
RETURNS integer
LANGUAGE sql STABLE
AS $$
    SELECT CASE
        WHEN EXISTS (SELECT 1 FROM public.prescription r
                      WHERE r.id = p_id AND r.clinic_id = p_clinic
                        AND r.dispensed_qty > 0)
          OR EXISTS (SELECT 1 FROM public.payment_bill_line b
                      WHERE b.clinic_id = p_clinic AND b.source_type = 'prescription'
                        AND b.source_id = p_id::text)
          OR EXISTS (SELECT 1 FROM public.prescription_allocation a
                      WHERE a.prescription_id = p_id AND a.clinic_id = p_clinic
                        AND (a.payment_cycle_id IS NOT NULL OR a.handed_over_qty > 0))
          OR EXISTS (SELECT 1 FROM public.inventory_txn t
                       JOIN public.prescription_allocation a
                         ON a.id = t.allocation_id AND a.clinic_id = t.clinic_id
                      WHERE a.prescription_id = p_id AND a.clinic_id = p_clinic
                        AND t.txn_type IN ('SALE', 'DISPENSE'))
          OR EXISTS (SELECT 1 FROM public.inventory_txn t
                      WHERE t.clinic_id = p_clinic AND t.txn_type = 'DISPENSE'
                        AND t.ref_type = 'prescription' AND t.ref_id = p_id)
          OR EXISTS (SELECT 1 FROM public.drug_return d
                      WHERE d.prescription_id = p_id AND d.clinic_id = p_clinic)
            THEN 2
        WHEN EXISTS (SELECT 1 FROM public.prescription_allocation a
                      WHERE a.prescription_id = p_id AND a.clinic_id = p_clinic)
          OR EXISTS (SELECT 1 FROM public.prescription r
                      WHERE r.id = p_id AND r.clinic_id = p_clinic
                        AND r.closed_at IS NOT NULL)
            THEN 1
        ELSE 0
    END
$$;

-- Hồ sơ của lượt đã ký chưa (FINALIZED hoặc đã từng đính chính).
CREATE OR REPLACE FUNCTION public.luot_da_ky(p_visit uuid, p_clinic uuid)
RETURNS boolean
LANGUAGE sql STABLE
AS $$
    SELECT coalesce((SELECT v.status IN ('FINALIZED', 'AMENDED')
                       FROM public.visit v
                      WHERE v.visit_id = p_visit AND v.clinic_id = p_clinic), false)
$$;

-- Giao dịch hiện tại có đang đi đường đính chính hồ sơ của ĐÚNG lượt này không:
-- `clinicai.amendment_id` trỏ tới một visit_amendment cùng phòng khám, cùng
-- lượt, ghi trong chính giao dịch này (amended_at = now()). Lưới toàn vẹn —
-- không phải token bảo mật (xem đầu file).
CREATE OR REPLACE FUNCTION public.dang_dinh_chinh_ho_so(p_visit uuid, p_clinic uuid)
RETURNS uuid
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    ma text := nullif(btrim(current_setting('clinicai.amendment_id', true)), '');
BEGIN
    IF ma IS NULL
       OR ma !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
        RETURN NULL;
    END IF;
    RETURN (SELECT a.amendment_id FROM public.visit_amendment a
             WHERE a.amendment_id = ma::uuid AND a.clinic_id = p_clinic
               AND a.visit_id = p_visit AND a.amended_at = now());
END $$;

-- ── 5. Guard của lần đính chính ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.prescription_correction_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'prescription_correction chỉ ghi thêm — lịch sử đính chính không sửa, không xoá'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- Lần đính chính thuộc CHÍNH giao dịch ghi nó: dòng đơn chỉ gỡ / sinh được
    -- bằng lần đính chính có corrected_at = now().
    NEW.corrected_at := now();
    IF public.luot_da_ky(NEW.visit_id, NEW.clinic_id) THEN
        IF NEW.amendment_id IS NULL
           OR NEW.amendment_id IS DISTINCT FROM
              public.dang_dinh_chinh_ho_so(NEW.visit_id, NEW.clinic_id) THEN
            RAISE EXCEPTION 'Hồ sơ đã ký: đính chính đơn phải đi qua đính chính hồ sơ (cùng giao dịch)'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.amendment_id IS NOT NULL THEN
        RAISE EXCEPTION 'Hồ sơ chưa ký: đính chính đơn không gắn đính chính hồ sơ'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_prescription_correction_guard ON public.prescription_correction;
CREATE TRIGGER trg_prescription_correction_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.prescription_correction
    FOR EACH ROW EXECUTE FUNCTION public.prescription_correction_guard();

-- ── 6. Guard của dòng đơn ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.prescription_dinh_chinh_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    -- Cột không tính khi so "nội dung có đổi không".
    bo_qua constant text[] := ARRAY['updated_at', 'dispense_status'];
    cot_go constant text[] := ARRAY['removed_at', 'removed_by', 'removal_reason',
                                    'removed_in_correction_id', 'superseded_by_id'];
    ky boolean;
    lan record;
    sau record;
    doi_thuoc boolean;
    doi_huong_dan boolean;
    muc integer;
    -- amendment_id của lần đính chính đang dùng (NULL khi không có / chưa ký).
    lan_sua uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF public.luot_da_ky(OLD.visit_id, OLD.clinic_id) THEN
            RAISE EXCEPTION 'Dòng đơn của hồ sơ đã ký không xoá — gỡ bằng đính chính hồ sơ'
                USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.removed_at IS NOT NULL OR OLD.created_in_correction_id IS NOT NULL
           OR public.prescription_muc_dau_vet(OLD.id, OLD.clinic_id) > 0 THEN
            RAISE EXCEPTION 'Dòng đơn đã có dấu vết (nhà thuốc / thu tiền / đính chính) — không xoá, phải gỡ bằng đính chính'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN OLD;
    END IF;

    ky := public.luot_da_ky(NEW.visit_id, NEW.clinic_id);

    IF TG_OP = 'INSERT' THEN
        IF NEW.removed_at IS NOT NULL OR NEW.superseded_by_id IS NOT NULL
           OR NEW.removed_in_correction_id IS NOT NULL THEN
            RAISE EXCEPTION 'Dòng đơn mới phải là dòng hiện hành'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.created_in_correction_id IS NOT NULL THEN
            SELECT * INTO lan FROM public.prescription_correction
             WHERE id = NEW.created_in_correction_id AND clinic_id = NEW.clinic_id;
            lan_sua := lan.amendment_id;
            IF lan.corrected_at IS DISTINCT FROM now() THEN
                RAISE EXCEPTION 'Dòng thay thế phải sinh trong chính lần đính chính đang ghi'
                    USING ERRCODE = 'check_violation';
            END IF;
            -- Dòng thay thế KHÔNG kế thừa việc nhà thuốc đã làm cho dòng cũ.
            IF NEW.drug_catalog_id IS NOT NULL OR NEW.purchased_qty IS NOT NULL
               OR NEW.dispensed_qty <> 0 OR NEW.closed_at IS NOT NULL
               OR NEW.refusal_reason IS NOT NULL THEN
                RAISE EXCEPTION 'Dòng thay thế bắt đầu trống: không thuốc kho, không số mua, chưa giao, chưa chốt'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        IF ky AND (lan_sua IS NULL
                   OR lan_sua IS DISTINCT FROM
                      public.dang_dinh_chinh_ho_so(NEW.visit_id, NEW.clinic_id)) THEN
            RAISE EXCEPTION 'Hồ sơ đã ký: thêm dòng đơn phải đi qua đính chính hồ sơ'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- UPDATE ─ danh tính không đổi.
    IF NEW.id <> OLD.id OR NEW.clinic_id <> OLD.clinic_id
       OR NEW.visit_id IS DISTINCT FROM OLD.visit_id
       OR NEW.created_in_correction_id IS DISTINCT FROM OLD.created_in_correction_id THEN
        RAISE EXCEPTION 'Dòng đơn: danh tính / nguồn gốc đính chính không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;

    -- Dòng lịch sử: bất biến (chỉ updated_at).
    IF OLD.removed_at IS NOT NULL THEN
        IF (to_jsonb(NEW) - bo_qua) IS DISTINCT FROM (to_jsonb(OLD) - bo_qua) THEN
            RAISE EXCEPTION 'Dòng đơn đã được đính chính (lịch sử) — không sửa được'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- Gỡ khỏi đơn hiện hành: một thao tác thuần, không kèm đổi nội dung.
    IF NEW.removed_at IS NOT NULL THEN
        IF (to_jsonb(NEW) - bo_qua - cot_go) IS DISTINCT FROM (to_jsonb(OLD) - bo_qua - cot_go) THEN
            RAISE EXCEPTION 'Gỡ dòng đơn không được kèm sửa nội dung dòng'
                USING ERRCODE = 'check_violation';
        END IF;
        SELECT * INTO lan FROM public.prescription_correction
         WHERE id = NEW.removed_in_correction_id AND clinic_id = NEW.clinic_id;
        IF lan.corrected_at IS DISTINCT FROM now() THEN
            RAISE EXCEPTION 'Gỡ dòng đơn phải bằng lần đính chính đang ghi'
                USING ERRCODE = 'check_violation';
        END IF;
        IF ky AND (lan.amendment_id IS NULL
                   OR lan.amendment_id IS DISTINCT FROM
                      public.dang_dinh_chinh_ho_so(NEW.visit_id, NEW.clinic_id)) THEN
            RAISE EXCEPTION 'Hồ sơ đã ký: gỡ dòng đơn phải đi qua đính chính hồ sơ'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.superseded_by_id IS NOT NULL THEN
            SELECT removed_at, created_in_correction_id INTO sau
              FROM public.prescription
             WHERE id = NEW.superseded_by_id AND clinic_id = NEW.clinic_id;
            IF sau.removed_at IS NOT NULL
               OR sau.created_in_correction_id IS DISTINCT FROM NEW.removed_in_correction_id THEN
                RAISE EXCEPTION 'Dòng thay thế phải là dòng hiện hành sinh trong cùng lần đính chính'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        -- Kế hoạch lô chưa gắn lần thu phải nhả trước ("Bác sĩ đính chính đơn").
        -- Phân lô đã gắn lần thu thì giữ — tiền và kho cũ đối soát riêng.
        IF EXISTS (SELECT 1 FROM public.prescription_allocation a
                    WHERE a.prescription_id = OLD.id AND a.clinic_id = OLD.clinic_id
                      AND a.released_at IS NULL AND a.payment_cycle_id IS NULL) THEN
            RAISE EXCEPTION 'Dòng đơn còn phân lô chưa thu — nhả trước khi gỡ'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- Dòng hiện hành, đổi nội dung chuyên môn tại chỗ.
    doi_thuoc := NEW.drug_name_raw IS DISTINCT FROM OLD.drug_name_raw
              OR NEW.quantity IS DISTINCT FROM OLD.quantity
              OR NEW.quantity_num IS DISTINCT FROM OLD.quantity_num
              OR NEW.unit IS DISTINCT FROM OLD.unit;
    doi_huong_dan := NEW.dosage_instructions IS DISTINCT FROM OLD.dosage_instructions
                  OR NEW.caution IS DISTINCT FROM OLD.caution;
    IF NOT (doi_thuoc OR doi_huong_dan) THEN
        RETURN NEW;  -- việc vận hành của nhà thuốc
    END IF;
    IF ky AND public.dang_dinh_chinh_ho_so(NEW.visit_id, NEW.clinic_id) IS NULL THEN
        RAISE EXCEPTION 'Hồ sơ đã ký: sửa đơn phải đi qua đính chính hồ sơ'
            USING ERRCODE = 'check_violation';
    END IF;
    muc := public.prescription_muc_dau_vet(OLD.id, OLD.clinic_id);
    IF muc >= 2 THEN
        RAISE EXCEPTION 'Dòng đơn đã thu tiền / bán / giao / trả — đổi thuốc, số lượng, liều hay lưu ý đều phải tạo dòng thay thế'
            USING ERRCODE = 'check_violation';
    END IF;
    IF muc = 1 AND doi_thuoc THEN
        RAISE EXCEPTION 'Dòng đơn nhà thuốc đã chọn lô / đã chốt — đổi thuốc hay số lượng phải tạo dòng thay thế'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_prescription_dinh_chinh_guard ON public.prescription;
CREATE TRIGGER trg_prescription_dinh_chinh_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.prescription
    FOR EACH ROW EXECUTE FUNCTION public.prescription_dinh_chinh_guard();

-- ── 7. Phân lô: dòng lịch sử không nhận phân lô / gắn lần thu / giao mới ──
CREATE OR REPLACE FUNCTION public.prescription_allocation_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    rx record;
    lo record;
    trang_thai text;
    da_phan numeric;
    da_ban numeric;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'prescription_allocation không xoá — gỡ bằng released_at'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.released_at IS NOT NULL OR NEW.handed_over_qty <> 0 THEN
            RAISE EXCEPTION 'Phân lô mới phải còn hiệu lực và chưa giao'
                USING ERRCODE = 'check_violation';
        END IF;
        -- FOR SHARE: chờ lệnh gỡ dòng đơn đang chạy (CP6) rồi mới đọc.
        SELECT visit_id, drug_catalog_id, unit, quantity_num, purchased_qty, closed_at,
               removed_at
          INTO rx FROM public.prescription
         WHERE id = NEW.prescription_id AND clinic_id = NEW.clinic_id
           FOR SHARE;
        IF rx.visit_id IS DISTINCT FROM NEW.visit_id THEN
            RAISE EXCEPTION 'Phân lô: dòng đơn không thuộc lượt khám này'
                USING ERRCODE = 'check_violation';
        END IF;
        IF rx.removed_at IS NOT NULL THEN
            RAISE EXCEPTION 'Phân lô: dòng đơn đã được bác sĩ đính chính (lịch sử)'
                USING ERRCODE = 'check_violation';
        END IF;
        IF rx.closed_at IS NOT NULL THEN
            RAISE EXCEPTION 'Phân lô: dòng đơn đã chốt' USING ERRCODE = 'check_violation';
        END IF;
        IF rx.drug_catalog_id IS DISTINCT FROM NEW.drug_catalog_id THEN
            RAISE EXCEPTION 'Phân lô: khác thuốc kho đã xác định của dòng đơn'
                USING ERRCODE = 'check_violation';
        END IF;
        IF rx.unit IS NULL OR btrim(rx.unit) = '' OR rx.quantity_num IS NULL THEN
            RAISE EXCEPTION 'Phân lô: dòng đơn chưa xác định đơn vị/số lượng'
                USING ERRCODE = 'check_violation';
        END IF;
        SELECT drug_catalog_id, unit INTO lo FROM public.drug_batch
         WHERE id = NEW.drug_batch_id AND clinic_id = NEW.clinic_id;
        IF lo.drug_catalog_id IS DISTINCT FROM NEW.drug_catalog_id THEN
            RAISE EXCEPTION 'Phân lô: lô không phải thuốc này'
                USING ERRCODE = 'check_violation';
        END IF;
        IF public.don_vi_chuan(lo.unit) <> public.don_vi_chuan(rx.unit) THEN
            RAISE EXCEPTION 'Phân lô: đơn vị lô khác đơn vị kê'
                USING ERRCODE = 'check_violation';
        END IF;
        SELECT coalesce(sum(quantity), 0) INTO da_phan
          FROM public.prescription_allocation
         WHERE prescription_id = NEW.prescription_id AND clinic_id = NEW.clinic_id
           AND released_at IS NULL;
        IF da_phan + NEW.quantity > coalesce(rx.purchased_qty, rx.quantity_num) THEN
            RAISE EXCEPTION 'Phân lô: tổng phân lô vượt số mua'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.payment_cycle_id IS NOT NULL THEN
            SELECT status INTO trang_thai FROM public.payment_cycle
             WHERE payment_cycle_id = NEW.payment_cycle_id AND clinic_id = NEW.clinic_id
               AND kind = 'thuoc';
            IF trang_thai IS DISTINCT FROM 'PENDING_VERIFICATION' THEN
                RAISE EXCEPTION 'Phân lô mới chỉ gắn được lần thu thuốc đang chờ'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    -- UPDATE: danh tính của phân lô không đổi tại chỗ.
    IF NEW.id <> OLD.id OR NEW.clinic_id <> OLD.clinic_id
       OR NEW.visit_id <> OLD.visit_id OR NEW.prescription_id <> OLD.prescription_id
       OR NEW.drug_catalog_id <> OLD.drug_catalog_id
       OR NEW.drug_batch_id <> OLD.drug_batch_id OR NEW.quantity <> OLD.quantity
       OR NEW.created_by <> OLD.created_by OR NEW.created_at <> OLD.created_at
       OR (OLD.payment_cycle_id IS NOT NULL
           AND NEW.payment_cycle_id IS DISTINCT FROM OLD.payment_cycle_id)
       OR (OLD.released_at IS NOT NULL AND (
               NEW.released_at IS DISTINCT FROM OLD.released_at
               OR NEW.released_by IS DISTINCT FROM OLD.released_by
               OR NEW.release_reason IS DISTINCT FROM OLD.release_reason
               OR NEW.handed_over_qty <> OLD.handed_over_qty))
       OR NEW.handed_over_qty < OLD.handed_over_qty THEN
        RAISE EXCEPTION 'prescription_allocation: cột đã ghi không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;

    -- CP6: gắn lần thu / giao thêm là tác động thương mại MỚI — dòng lịch sử
    -- không nhận. Nhả phân lô thì vẫn được.
    IF (OLD.payment_cycle_id IS NULL AND NEW.payment_cycle_id IS NOT NULL)
       OR NEW.handed_over_qty > OLD.handed_over_qty THEN
        SELECT removed_at INTO rx FROM public.prescription
         WHERE id = NEW.prescription_id AND clinic_id = NEW.clinic_id
           FOR SHARE;
        IF rx.removed_at IS NOT NULL THEN
            RAISE EXCEPTION 'Dòng đơn đã được bác sĩ đính chính (lịch sử) — không gắn lần thu, không giao thêm'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF OLD.payment_cycle_id IS NULL AND NEW.payment_cycle_id IS NOT NULL THEN
        SELECT status INTO trang_thai FROM public.payment_cycle
         WHERE payment_cycle_id = NEW.payment_cycle_id AND clinic_id = NEW.clinic_id
           AND kind = 'thuoc';
        IF NEW.released_at IS NOT NULL
           OR trang_thai NOT IN ('PENDING_VERIFICATION', 'PAID') THEN
            RAISE EXCEPTION 'Chỉ gắn phân lô còn hiệu lực vào lần thu thuốc đang sống'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF OLD.released_at IS NULL AND NEW.released_at IS NOT NULL THEN
        IF NEW.handed_over_qty > 0 THEN
            RAISE EXCEPTION 'Phân lô đã giao thuốc — không gỡ được (trả thuốc: CP5)'
                USING ERRCODE = 'check_violation';
        END IF;
        SELECT coalesce(-sum(quantity), 0) INTO da_ban FROM public.inventory_txn
         WHERE allocation_id = OLD.id AND clinic_id = OLD.clinic_id
           AND txn_type IN ('SALE', 'SALE_REVERSAL');
        IF da_ban <> 0 THEN
            RAISE EXCEPTION 'Phân lô đang bán (chưa đảo) — không gỡ được'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $function$;

-- ── 8. Sổ kho: không SALE / DISPENSE mới trên dòng lịch sử ────────────────
-- SALE_REVERSAL và RETURN_RECEIVED vẫn được: đó là đối soát tác động cũ.
CREATE OR REPLACE FUNCTION public.inventory_txn_ban_hop_le()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    pl record;
    goc record;
    tra record;
    trang_thai text;
    da_xuat numeric;
    da_hoan numeric;
    da_dao numeric;
    da_go timestamptz;
BEGIN
    IF NEW.txn_type = 'RETURN_RECEIVED' THEN
        -- Dòng kho của một lần khách trả: đúng lô, đúng số lượng của lần trả.
        SELECT * INTO tra FROM public.drug_return
         WHERE id = NEW.ref_id AND clinic_id = NEW.clinic_id;
        IF tra.drug_batch_id IS DISTINCT FROM NEW.drug_batch_id
           OR tra.returned_qty IS DISTINCT FROM NEW.quantity THEN
            RAISE EXCEPTION 'RETURN_RECEIVED không khớp lần khách trả thuốc'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    -- CP6: DISPENSE luồng cũ (không phân lô) trỏ dòng đơn qua ref_id.
    IF NEW.txn_type = 'DISPENSE' AND NEW.allocation_id IS NULL
       AND NEW.ref_type = 'prescription' THEN
        SELECT removed_at INTO da_go FROM public.prescription
         WHERE id = NEW.ref_id AND clinic_id = NEW.clinic_id FOR SHARE;
        IF da_go IS NOT NULL THEN
            RAISE EXCEPTION 'Dòng đơn đã được bác sĩ đính chính (lịch sử) — không giao'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.txn_type NOT IN ('SALE', 'SALE_REVERSAL')
       AND NOT (NEW.txn_type = 'DISPENSE' AND NEW.allocation_id IS NOT NULL) THEN
        RETURN NEW;
    END IF;
    SELECT * INTO pl FROM public.prescription_allocation
     WHERE id = NEW.allocation_id AND clinic_id = NEW.clinic_id;
    SELECT status INTO trang_thai FROM public.payment_cycle
     WHERE payment_cycle_id = NEW.payment_cycle_id AND clinic_id = NEW.clinic_id;

    IF NEW.txn_type IN ('SALE', 'DISPENSE') THEN
        SELECT removed_at INTO da_go FROM public.prescription
         WHERE id = pl.prescription_id AND clinic_id = NEW.clinic_id FOR SHARE;
    END IF;
    IF NEW.txn_type IN ('SALE', 'DISPENSE') AND da_go IS NOT NULL THEN
        RAISE EXCEPTION 'Dòng đơn đã được bác sĩ đính chính (lịch sử) — không ghi bán / giao mới (đối soát: CP5)'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.txn_type = 'SALE' THEN
        -- Bán TRỌN phân lô, chỉ khi lần thu đã PAID và phân lô còn hiệu lực.
        IF trang_thai IS DISTINCT FROM 'PAID' OR pl.released_at IS NOT NULL
           OR NEW.quantity <> -pl.quantity THEN
            RAISE EXCEPTION 'SALE không khớp phân lô/lần thu đã thu'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.txn_type = 'SALE_REVERSAL' THEN
        -- CP5: đảo ĐÚNG phần chưa giao = bán − đã xuất (tính từ sổ), mỗi SALE
        -- một lần (uq_inventory_txn_dao_mot_lan), và phải có căn cứ tài chính:
        -- lần thu đã huỷ phiếu, HOẶC tổng đã đảo trên dòng đơn ≤ số đã hoàn
        -- xong (COMPLETED) của đúng dòng ảnh chụp hoá đơn ấy.
        PERFORM 1 FROM public.prescription_allocation
          WHERE id = NEW.allocation_id AND clinic_id = NEW.clinic_id FOR UPDATE;
        SELECT * INTO goc FROM public.inventory_txn WHERE id = NEW.reverses_txn_id;
        SELECT coalesce(-sum(d.quantity), 0) INTO da_xuat FROM public.inventory_txn d
         WHERE d.txn_type = 'DISPENSE' AND d.allocation_id = NEW.allocation_id
           AND d.clinic_id = NEW.clinic_id;
        IF goc.txn_type IS DISTINCT FROM 'SALE'
           OR goc.allocation_id IS DISTINCT FROM NEW.allocation_id
           OR goc.payment_cycle_id IS DISTINCT FROM NEW.payment_cycle_id
           OR goc.drug_batch_id IS DISTINCT FROM NEW.drug_batch_id
           OR goc.clinic_id IS DISTINCT FROM NEW.clinic_id
           OR NEW.quantity <> -goc.quantity - da_xuat THEN
            RAISE EXCEPTION 'SALE_REVERSAL không khớp phần chưa giao của dòng bán gốc'
                USING ERRCODE = 'check_violation';
        END IF;
        IF trang_thai IS DISTINCT FROM 'VOIDED' THEN
            SELECT coalesce(sum(l.quantity), 0) INTO da_hoan
              FROM public.payment_refund_line l
              JOIN public.payment_refund r
                ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
              JOIN public.payment_bill_line b
                ON b.id = l.payment_bill_line_id AND b.clinic_id = l.clinic_id
             WHERE l.clinic_id = NEW.clinic_id
               AND l.payment_cycle_id = NEW.payment_cycle_id
               AND r.status = 'COMPLETED'
               AND b.source_type = 'prescription'
               AND b.source_id = pl.prescription_id::text;
            SELECT coalesce(sum(t.quantity), 0) INTO da_dao
              FROM public.inventory_txn t
              JOIN public.prescription_allocation a
                ON a.id = t.allocation_id AND a.clinic_id = t.clinic_id
             WHERE t.txn_type = 'SALE_REVERSAL' AND t.clinic_id = NEW.clinic_id
               AND t.payment_cycle_id = NEW.payment_cycle_id
               AND a.prescription_id = pl.prescription_id;
            IF da_dao + NEW.quantity > da_hoan THEN
                RAISE EXCEPTION 'Huỷ phần chưa giao cần căn cứ: huỷ phiếu, hoặc đã hoàn tiền đủ (% đã hoàn, cần %)',
                    da_hoan, da_dao + NEW.quantity
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    ELSE
        -- DISPENSE theo phân lô (review CP3 P1-B): lưới cuối ở DB, không chỉ
        -- trong Python — lần thu đang PAID, có SALE chưa đảo, và TỔNG đã xuất
        -- của phân lô (tính từ chính sổ, không từ handed_over_qty) không vượt
        -- số đã phân. Khoá dòng phân lô để hai lệnh ghi thẳng cùng lúc cũng
        -- phải xếp hàng.
        PERFORM 1 FROM public.prescription_allocation
          WHERE id = NEW.allocation_id AND clinic_id = NEW.clinic_id FOR UPDATE;
        IF trang_thai IS DISTINCT FROM 'PAID'
           OR NOT EXISTS (SELECT 1 FROM public.inventory_txn s
                           WHERE s.txn_type = 'SALE'
                             AND s.allocation_id = NEW.allocation_id
                             AND s.payment_cycle_id = NEW.payment_cycle_id
                             AND NOT EXISTS (
                                 SELECT 1 FROM public.inventory_txn r
                                  WHERE r.txn_type = 'SALE_REVERSAL'
                                    AND r.reverses_txn_id = s.id)) THEN
            RAISE EXCEPTION 'DISPENSE theo phân lô: lần thu chưa PAID hoặc chưa bán (đã đảo bán)'
                USING ERRCODE = 'check_violation';
        END IF;
        IF coalesce((SELECT -sum(d.quantity) FROM public.inventory_txn d
                      WHERE d.txn_type = 'DISPENSE'
                        AND d.allocation_id = NEW.allocation_id
                        AND d.clinic_id = NEW.clinic_id), 0)
           - NEW.quantity > pl.quantity THEN
            RAISE EXCEPTION 'DISPENSE theo phân lô: vượt số đã phân (%)', pl.quantity
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $function$;

-- ── 9. Quyền ──────────────────────────────────────────────────────────────
ALTER TABLE public.prescription_correction ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS prescription_correction_select_own_clinic
    ON public.prescription_correction;
CREATE POLICY prescription_correction_select_own_clinic ON public.prescription_correction
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.prescription_correction TO authenticated;
GRANT SELECT, INSERT ON public.prescription_correction TO service_role;
