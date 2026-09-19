-- Contract tiền–thuốc, CP3 (19/09/2026): BÁN thuốc lúc thu tiền thành công,
-- theo đúng lô dược sĩ đã chọn trước.
--
-- Thiết kế đã chốt với reviewer (không phải quyết định kho của Dr4Women):
--   * `drug_batch.quantity_on_hand` GIỮ NGHĨA VẬT LÝ — thuốc còn trên kệ. Chỉ
--     RECEIVE / DISPENSE / ADJUST / DISCARD làm nó đổi, như trước.
--   * `SALE` (âm) / `SALE_REVERSAL` (dương) là cam kết BÁN, không phải thuốc rời
--     quầy → KHÔNG đổi `quantity_on_hand`. Chúng chỉ trừ vào lượng khả dụng kỹ
--     thuật (`drug_batch_kha_dung`), dùng để chặn bán quá số có.
--   * `prescription_allocation` = dược sĩ chọn lô cho dòng đơn TRƯỚC khi thu.
--     Chưa gắn lần thu: không giữ chỗ. Gắn vào lần thu chờ xác minh: giữ kỹ
--     thuật (chống bán trùng khi khách đã chuyển tiền). Gắn vào lần thu PAID:
--     phân lô của lần bán đó.
--   * Giao thuốc vẫn ghi DISPENSE (vật lý giảm) kèm phân lô + lần thu → khả
--     dụng không giảm lần hai.
--
-- Chỉ THÊM. Không ghi lại dòng sổ cũ, không đoán lô cho giao dịch trước CP3.
-- Chạy lại nhiều lần được.

-- ── Neo khoá ngoại ghép (cùng phòng khám) ────────────────────────────────
DO $cp3_neo$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.prescription'::regclass
                      AND conname = 'uq_prescription_id_clinic') THEN
        ALTER TABLE public.prescription
            ADD CONSTRAINT uq_prescription_id_clinic UNIQUE (id, clinic_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.payment_cycle'::regclass
                      AND conname = 'uq_payment_cycle_id_clinic_visit') THEN
        ALTER TABLE public.payment_cycle
            ADD CONSTRAINT uq_payment_cycle_id_clinic_visit
            UNIQUE (payment_cycle_id, clinic_id, visit_id);
    END IF;
END
$cp3_neo$;

-- Đơn vị so theo cách viết (khoảng trắng, hoa/thường, dạng Unicode) — cùng luật
-- với `_don_vi` trong pharmacy_service. Hộp, vỉ, viên luôn là đơn vị khác nhau.
CREATE OR REPLACE FUNCTION public.don_vi_chuan(p text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT lower(regexp_replace(btrim(normalize(coalesce(p, ''), NFC)), '\s+', ' ', 'g'))
$$;

-- ── Phân lô ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.prescription_allocation (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id         uuid NOT NULL,
    prescription_id  uuid NOT NULL,
    drug_catalog_id  uuid NOT NULL,
    drug_batch_id    uuid NOT NULL,
    quantity         numeric(12, 3) NOT NULL CHECK (quantity > 0),
    handed_over_qty  numeric(12, 3) NOT NULL DEFAULT 0,
    payment_cycle_id uuid,
    created_by       uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    created_at       timestamptz NOT NULL DEFAULT now(),
    released_at      timestamptz,
    released_by      uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    release_reason   text,
    CONSTRAINT prescription_allocation_giao_trong_so_phan CHECK (
        handed_over_qty >= 0 AND handed_over_qty <= quantity),
    CONSTRAINT prescription_allocation_go_co_dau_vet CHECK (
        (released_at IS NULL) = (released_by IS NULL)
        AND (released_at IS NULL) = (release_reason IS NULL)),
    CONSTRAINT prescription_allocation_visit_fkey FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE RESTRICT,
    CONSTRAINT prescription_allocation_rx_fkey FOREIGN KEY (prescription_id, clinic_id)
        REFERENCES public.prescription (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT prescription_allocation_drug_fkey FOREIGN KEY (drug_catalog_id, clinic_id)
        REFERENCES public.drug_catalog (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT prescription_allocation_batch_fkey FOREIGN KEY (drug_batch_id, clinic_id)
        REFERENCES public.drug_batch (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT prescription_allocation_cycle_fkey
        FOREIGN KEY (payment_cycle_id, clinic_id, visit_id)
        REFERENCES public.payment_cycle (payment_cycle_id, clinic_id, visit_id)
        ON DELETE RESTRICT,
    -- Neo cho sổ kho: dòng SALE/DISPENSE mới phải trỏ đúng phân lô, đúng lô,
    -- đúng lần thu, đúng phòng khám — ép bằng MỘT khoá ngoại ghép.
    CONSTRAINT uq_prescription_allocation_neo_so
        UNIQUE (id, clinic_id, drug_batch_id, payment_cycle_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_prescription_allocation_dong_lo_song
    ON public.prescription_allocation (prescription_id, drug_batch_id)
    WHERE released_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_prescription_allocation_cycle
    ON public.prescription_allocation (clinic_id, payment_cycle_id)
    WHERE payment_cycle_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prescription_allocation_lo
    ON public.prescription_allocation (clinic_id, drug_batch_id);
CREATE INDEX IF NOT EXISTS idx_prescription_allocation_rx
    ON public.prescription_allocation (clinic_id, prescription_id);

COMMENT ON TABLE public.prescription_allocation IS
    'Lô dược sĩ chọn cho dòng đơn trước khi thu (contract tiền–thuốc CP3). '
    'payment_cycle_id NULL = chưa giữ; gắn lần thu chờ = giữ kỹ thuật; gắn lần '
    'thu PAID = phân lô của lần bán. Không xoá — đổi lô = gỡ dòng cũ + dòng mới.';

-- ── Sổ kho: bán / đảo bán ────────────────────────────────────────────────
ALTER TABLE public.inventory_txn
    ADD COLUMN IF NOT EXISTS payment_cycle_id uuid,
    ADD COLUMN IF NOT EXISTS allocation_id uuid,
    ADD COLUMN IF NOT EXISTS reverses_txn_id uuid
        REFERENCES public.inventory_txn(id) ON DELETE RESTRICT;

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_type_check;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_type_check CHECK (
    txn_type IN ('RECEIVE', 'DISPENSE', 'ADJUST', 'DISCARD', 'SALE', 'SALE_REVERSAL'));

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_qty_sign_check;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_qty_sign_check CHECK (
    (txn_type IN ('RECEIVE', 'SALE_REVERSAL') AND quantity > 0)
    OR (txn_type IN ('DISPENSE', 'DISCARD', 'SALE') AND quantity < 0)
    OR (txn_type = 'ADJUST' AND quantity <> 0));

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_dong_ban_co_nguon;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_dong_ban_co_nguon CHECK (
    CASE
        WHEN txn_type IN ('SALE', 'SALE_REVERSAL') THEN
            payment_cycle_id IS NOT NULL AND allocation_id IS NOT NULL
            AND ref_type = 'payment_cycle' AND ref_id = payment_cycle_id
            AND (reverses_txn_id IS NOT NULL) = (txn_type = 'SALE_REVERSAL')
        WHEN txn_type = 'DISPENSE' THEN
            (payment_cycle_id IS NULL) = (allocation_id IS NULL)
            AND reverses_txn_id IS NULL
        ELSE
            payment_cycle_id IS NULL AND allocation_id IS NULL
            AND reverses_txn_id IS NULL
    END);

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_allocation_fkey;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_allocation_fkey
    FOREIGN KEY (allocation_id, clinic_id, drug_batch_id, payment_cycle_id)
    REFERENCES public.prescription_allocation (id, clinic_id, drug_batch_id, payment_cycle_id)
    ON DELETE RESTRICT;

-- ĐÚNG MỘT LẦN, ép ở DB: một phân lô chỉ bán một lần trong một lần thu, và một
-- dòng bán chỉ bị đảo một lần. Thu lại / xác minh lại / hai người cùng bấm
-- không trừ được lần hai.
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_txn_ban_mot_lan
    ON public.inventory_txn (payment_cycle_id, allocation_id)
    WHERE txn_type = 'SALE';
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_txn_dao_mot_lan
    ON public.inventory_txn (reverses_txn_id)
    WHERE txn_type = 'SALE_REVERSAL';
CREATE INDEX IF NOT EXISTS idx_inventory_txn_allocation
    ON public.inventory_txn (clinic_id, allocation_id)
    WHERE allocation_id IS NOT NULL;

-- Tồn vật lý chỉ đổi theo thuốc vật lý. SALE/SALE_REVERSAL là cam kết bán.
CREATE OR REPLACE FUNCTION public.inventory_txn_apply()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.txn_type IN ('SALE', 'SALE_REVERSAL') THEN
        RETURN NEW;
    END IF;

    UPDATE public.drug_batch
       SET quantity_on_hand = quantity_on_hand + NEW.quantity,
           updated_at = now()
     WHERE id = NEW.drug_batch_id
       AND clinic_id = NEW.clinic_id;

    -- Không tìm thấy thì DỪNG. Bỏ qua lặng lẽ còn tệ hơn cả trừ nhầm: dòng vẫn
    -- vào sổ, tồn kho không đổi, và sổ với số dư lệch nhau ngay từ dòng đầu.
    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Lô thuốc % không thuộc phòng khám % (hoặc không tồn tại) — '
            'không trừ kho chéo phòng khám.', NEW.drug_batch_id, NEW.clinic_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    RETURN NEW;
END
$$;

-- Dòng bán / đảo bán phải khớp phân lô và lần thu ở thời điểm ghi.
CREATE OR REPLACE FUNCTION public.inventory_txn_ban_hop_le()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    pl record;
    goc record;
    trang_thai text;
BEGIN
    IF NEW.txn_type NOT IN ('SALE', 'SALE_REVERSAL')
       AND NOT (NEW.txn_type = 'DISPENSE' AND NEW.allocation_id IS NOT NULL) THEN
        RETURN NEW;
    END IF;
    SELECT * INTO pl FROM public.prescription_allocation
     WHERE id = NEW.allocation_id AND clinic_id = NEW.clinic_id;
    SELECT status INTO trang_thai FROM public.payment_cycle
     WHERE payment_cycle_id = NEW.payment_cycle_id AND clinic_id = NEW.clinic_id;

    IF NEW.txn_type = 'SALE' THEN
        -- CP3 bán TRỌN phân lô, chỉ khi lần thu đã PAID và phân lô còn hiệu lực.
        IF trang_thai IS DISTINCT FROM 'PAID' OR pl.released_at IS NOT NULL
           OR NEW.quantity <> -pl.quantity THEN
            RAISE EXCEPTION 'SALE không khớp phân lô/lần thu đã thu'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.txn_type = 'SALE_REVERSAL' THEN
        -- CP3 chỉ đảo TRỌN một dòng bán của lần thu đã huỷ phiếu. Hoàn/trả một
        -- phần là CP5 — nới luật này ở đó, không ở đây.
        SELECT * INTO goc FROM public.inventory_txn WHERE id = NEW.reverses_txn_id;
        IF goc.txn_type IS DISTINCT FROM 'SALE'
           OR goc.allocation_id IS DISTINCT FROM NEW.allocation_id
           OR goc.payment_cycle_id IS DISTINCT FROM NEW.payment_cycle_id
           OR goc.drug_batch_id IS DISTINCT FROM NEW.drug_batch_id
           OR goc.clinic_id IS DISTINCT FROM NEW.clinic_id
           OR NEW.quantity <> -goc.quantity
           OR trang_thai IS DISTINCT FROM 'VOIDED'
           OR pl.handed_over_qty <> 0 THEN
            RAISE EXCEPTION 'SALE_REVERSAL không khớp dòng bán gốc'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        -- DISPENSE theo phân lô: chỉ giao phần đã bán, chưa đảo.
        IF NOT EXISTS (SELECT 1 FROM public.inventory_txn s
                        WHERE s.txn_type = 'SALE' AND s.allocation_id = NEW.allocation_id
                          AND s.payment_cycle_id = NEW.payment_cycle_id)
           OR EXISTS (SELECT 1 FROM public.inventory_txn r
                       WHERE r.txn_type = 'SALE_REVERSAL'
                         AND r.allocation_id = NEW.allocation_id) THEN
            RAISE EXCEPTION 'DISPENSE theo phân lô chưa bán (hoặc đã đảo bán)'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_inventory_txn_ban_hop_le ON public.inventory_txn;
CREATE TRIGGER trg_inventory_txn_ban_hop_le
    BEFORE INSERT ON public.inventory_txn
    FOR EACH ROW EXECUTE FUNCTION public.inventory_txn_ban_hop_le();

-- ── Luật của phân lô ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.prescription_allocation_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
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
        SELECT visit_id, drug_catalog_id, unit, quantity_num, purchased_qty, closed_at
          INTO rx FROM public.prescription
         WHERE id = NEW.prescription_id AND clinic_id = NEW.clinic_id;
        IF rx.visit_id IS DISTINCT FROM NEW.visit_id THEN
            RAISE EXCEPTION 'Phân lô: dòng đơn không thuộc lượt khám này'
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
END $$;
DROP TRIGGER IF EXISTS trg_prescription_allocation_guard ON public.prescription_allocation;
CREATE TRIGGER trg_prescription_allocation_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.prescription_allocation
    FOR EACH ROW EXECUTE FUNCTION public.prescription_allocation_guard();

-- Dòng đơn còn phân lô hiệu lực thì không đổi thuốc / đơn vị / hạ số mua xuống
-- dưới tổng đã phân: phải gỡ phân lô trước.
CREATE OR REPLACE FUNCTION public.prescription_giu_phan_lo()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    da_phan numeric;
BEGIN
    SELECT coalesce(sum(quantity), 0) INTO da_phan
      FROM public.prescription_allocation
     WHERE prescription_id = OLD.id AND clinic_id = OLD.clinic_id
       AND released_at IS NULL;
    IF da_phan > 0 AND (
           NEW.drug_catalog_id IS DISTINCT FROM OLD.drug_catalog_id
           OR public.don_vi_chuan(NEW.unit) <> public.don_vi_chuan(OLD.unit)
           OR coalesce(NEW.purchased_qty, NEW.quantity_num, 0) < da_phan) THEN
        RAISE EXCEPTION 'Dòng đơn đang có phân lô — gỡ phân lô trước khi đổi'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_prescription_giu_phan_lo ON public.prescription;
CREATE TRIGGER trg_prescription_giu_phan_lo
    BEFORE UPDATE OF drug_catalog_id, unit, purchased_qty, quantity_num
    ON public.prescription
    FOR EACH ROW EXECUTE FUNCTION public.prescription_giu_phan_lo();

-- ── Lượng khả dụng kỹ thuật của một lô ───────────────────────────────────
-- = vật lý − đang giữ cho lần chuyển khoản/QR chờ − đã bán chưa giao.
-- Chỉ để CHẶN BÁN QUÁ; chưa phải con số/nhãn nghiệp vụ hiển thị (HOLD J6).
CREATE OR REPLACE FUNCTION public.drug_batch_kha_dung(p_clinic uuid, p_batch uuid)
RETURNS numeric LANGUAGE sql STABLE AS $$
    SELECT b.quantity_on_hand
         - coalesce((
               SELECT sum(a.quantity)
                 FROM public.prescription_allocation a
                 JOIN public.payment_cycle c
                   ON c.payment_cycle_id = a.payment_cycle_id
                  AND c.clinic_id = a.clinic_id
                WHERE a.clinic_id = p_clinic AND a.drug_batch_id = p_batch
                  AND a.released_at IS NULL
                  AND c.status = 'PENDING_VERIFICATION'), 0)
         - coalesce((
               SELECT sum(greatest(ban.da_ban - a.handed_over_qty, 0))
                 FROM public.prescription_allocation a
                 CROSS JOIN LATERAL (
                     SELECT coalesce(-sum(t.quantity), 0) AS da_ban
                       FROM public.inventory_txn t
                      WHERE t.allocation_id = a.id AND t.clinic_id = a.clinic_id
                        AND t.txn_type IN ('SALE', 'SALE_REVERSAL')) ban
                WHERE a.clinic_id = p_clinic AND a.drug_batch_id = p_batch), 0)
      FROM public.drug_batch b
     WHERE b.id = p_batch AND b.clinic_id = p_clinic
$$;

-- ── Quyền ────────────────────────────────────────────────────────────────
ALTER TABLE public.prescription_allocation ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS prescription_allocation_select_own_clinic
    ON public.prescription_allocation;
CREATE POLICY prescription_allocation_select_own_clinic
    ON public.prescription_allocation
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.prescription_allocation TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.prescription_allocation TO service_role;
