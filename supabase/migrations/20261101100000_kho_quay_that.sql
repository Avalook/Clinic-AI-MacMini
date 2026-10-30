-- KHO ↔ QUẦY THẬT · KIỂM CA SỐ THẬT · ĐỒNG BỘ HOÀN TÁC (Tuyền 31/10/2026).
--
-- 1. Sổ kho thêm `DISPENSE_REVERSAL` (dấu +): đảo ĐÚNG một lần giao, tồn cộng lại
--    qua `inventory_txn_apply` như mọi dòng vật lý. Sổ vẫn chỉ-thêm, mỗi lần giao
--    đảo tối đa một lần (ép ở Postgres). Khách đã trả bớt thì chỉ đảo phần còn lại.
-- 2. `thuoc_giao_chua_gan_lo`: dòng chờ gán lô huỷ được, có vết.
-- 3. Kiểm ca / kiểm kho: lý do từng dòng, tách phần "đã giao chưa gắn lô" khỏi số
--    lệch (lệch = đếm + N − sổ), hoàn tác phiếu kiểm kho.
-- 4. `kiem_ke_sua_so`: quản lý sửa số sau cùng, chỉ thêm, giữ lịch sử.
--
-- Chỉ THÊM, chạy lại được, không BEGIN/COMMIT.

-- ── 1. Sổ kho ─────────────────────────────────────────────────────────────
ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_type_check;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_type_check CHECK (
    txn_type IN ('RECEIVE', 'DISPENSE', 'DISPENSE_REVERSAL', 'ADJUST', 'DISCARD', 'SALE',
                 'SALE_REVERSAL', 'RETURN_RECEIVED', 'CHUYEN_RA', 'CHUYEN_VAO'));

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_qty_sign_check;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_qty_sign_check CHECK (
    (txn_type IN ('RECEIVE', 'SALE_REVERSAL', 'RETURN_RECEIVED', 'CHUYEN_VAO',
                  'DISPENSE_REVERSAL')
        AND quantity > 0)
    OR (txn_type IN ('DISPENSE', 'DISCARD', 'SALE', 'CHUYEN_RA') AND quantity < 0)
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
        WHEN txn_type = 'DISPENSE_REVERSAL' THEN
            (payment_cycle_id IS NULL) = (allocation_id IS NULL)
            AND reverses_txn_id IS NOT NULL
            AND ref_type = 'prescription' AND ref_id IS NOT NULL
        WHEN txn_type = 'RETURN_RECEIVED' THEN
            ref_type = 'drug_return' AND ref_id IS NOT NULL
            AND payment_cycle_id IS NULL AND allocation_id IS NULL
            AND reverses_txn_id IS NULL
        ELSE
            payment_cycle_id IS NULL AND allocation_id IS NULL
            AND reverses_txn_id IS NULL
    END);

CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_txn_dao_giao_mot_lan
    ON public.inventory_txn (reverses_txn_id)
    WHERE txn_type = 'DISPENSE_REVERSAL';

-- ── 2. Dòng chờ gán lô huỷ được, có vết ──────────────────────────────────
ALTER TABLE public.thuoc_giao_chua_gan_lo
    ADD COLUMN IF NOT EXISTS huy_luc timestamptz,
    ADD COLUMN IF NOT EXISTS huy_boi uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS huy_ly_do text;
ALTER TABLE public.thuoc_giao_chua_gan_lo DROP CONSTRAINT IF EXISTS thuoc_giao_chua_gan_lo_huy_du_bo;
ALTER TABLE public.thuoc_giao_chua_gan_lo ADD CONSTRAINT thuoc_giao_chua_gan_lo_huy_du_bo CHECK (
    huy_luc IS NULL
    OR (drug_batch_id IS NULL AND length(btrim(coalesce(huy_ly_do, ''))) > 0));

-- ── 3. Kiểm ca / kiểm kho ─────────────────────────────────────────────────
-- `giao_da_tach` = phần "đã giao chưa gắn lô" đã tính vào lệch lúc chốt. Rỗng ở
-- phiếu cũ, nên công thức cũ (lệch = đếm − sổ) vẫn đúng với chúng.
-- `dem_luc` = lúc đếm dòng này: bán / giao giữa lúc đếm và lúc chốt không phải lệch.
-- `chua_ap` = phần lệch không áp được vào lô (lệch − số đã ghi sổ), khác 0 thì
-- phiếu KHÔNG được báo là đã khớp; `chua_ap_ly_do` nói vì sao và phải làm gì.
ALTER TABLE public.kiem_ke_ca_dong
    ADD COLUMN IF NOT EXISTS ly_do text,
    ADD COLUMN IF NOT EXISTS giao_da_tach numeric(14, 3),
    ADD COLUMN IF NOT EXISTS dem_luc timestamptz,
    ADD COLUMN IF NOT EXISTS chua_ap numeric(14, 3),
    ADD COLUMN IF NOT EXISTS chua_ap_ly_do text;
ALTER TABLE public.kiem_ke_ca_dong DROP CONSTRAINT IF EXISTS kiem_ke_ca_dong_lech_dung;
ALTER TABLE public.kiem_ke_ca_dong ADD CONSTRAINT kiem_ke_ca_dong_lech_dung CHECK (
    (ton_may IS NULL) = (lech IS NULL)
    AND (lech IS NULL OR lech = dem + coalesce(giao_da_tach, 0) - ton_may));

ALTER TABLE public.phieu_kho_dong
    ADD COLUMN IF NOT EXISTS ly_do text,
    ADD COLUMN IF NOT EXISTS giao_da_tach numeric(12, 3);
ALTER TABLE public.phieu_kho_dong DROP CONSTRAINT IF EXISTS phieu_kho_dong_du_bo;
ALTER TABLE public.phieu_kho_dong ADD CONSTRAINT phieu_kho_dong_du_bo CHECK (
    CASE loai
        WHEN 'NHAP' THEN
            so_luong IS NOT NULL AND so_luong > 0
            AND ton_may IS NULL AND thuc_te IS NULL AND lech IS NULL
            AND inventory_txn_id IS NOT NULL
            AND drug_batch_nguon_id IS NULL AND inventory_txn_nguon_id IS NULL
        WHEN 'KIEM' THEN
            so_luong IS NULL AND gia_nhap IS NULL
            AND ton_may IS NOT NULL AND ton_may >= 0
            AND thuc_te IS NOT NULL
            AND lech IS NOT NULL
            AND lech = thuc_te + coalesce(giao_da_tach, 0) - ton_may
            AND (lech = 0) = (inventory_txn_id IS NULL)
            AND drug_batch_nguon_id IS NULL AND inventory_txn_nguon_id IS NULL
        WHEN 'CHUYEN' THEN
            so_luong IS NOT NULL AND so_luong > 0
            AND gia_nhap IS NULL AND ton_may IS NULL AND thuc_te IS NULL AND lech IS NULL
            AND inventory_txn_id IS NOT NULL AND inventory_txn_nguon_id IS NOT NULL
            AND drug_batch_nguon_id IS NOT NULL AND drug_batch_nguon_id <> drug_batch_id
        ELSE false
    END
);

-- Phiếu kiểm kho hoàn tác được: phiếu KIEM mới trỏ phiếu gốc, mỗi phiếu một lần
-- (`uq_phieu_kho_hoan_tac_cua`).
ALTER TABLE public.phieu_kho DROP CONSTRAINT IF EXISTS phieu_kho_chuyen_du_bo;
ALTER TABLE public.phieu_kho ADD CONSTRAINT phieu_kho_chuyen_du_bo CHECK (
    CASE loai
        WHEN 'CHUYEN' THEN huong IN ('KHO_QUAY', 'QUAY_KHO')
        WHEN 'KIEM' THEN huong IS NULL
        ELSE huong IS NULL AND ly_do IS NULL AND hoan_tac_cua IS NULL
    END);

-- ── 4. Quản lý sửa số sau cùng ở Báo cáo kho ─────────────────────────────
CREATE TABLE IF NOT EXISTS public.kiem_ke_sua_so (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id     uuid NOT NULL REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    -- CA = dòng `kiem_ke_ca_dong`, KHO = dòng `phieu_kho_dong`.
    nguon           text NOT NULL CHECK (nguon IN ('CA', 'KHO')),
    dong_id         uuid NOT NULL,
    so_cu           numeric(14, 3) NOT NULL CHECK (so_cu >= 0),
    so_moi          numeric(14, 3) NOT NULL CHECK (so_moi >= 0),
    ly_do           text NOT NULL CHECK (length(btrim(ly_do)) BETWEEN 1 AND 1000),
    sua_boi         uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    sua_luc         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT kiem_ke_sua_so_co_doi CHECK (so_moi <> so_cu)
);
CREATE INDEX IF NOT EXISTS kiem_ke_sua_so_theo_dong
    ON public.kiem_ke_sua_so (clinic_id, nguon, dong_id, sua_luc);

COMMENT ON TABLE public.kiem_ke_sua_so IS
    'Quản lý sửa số đếm sau cùng ở Báo cáo kho (31/10/2026). Chỉ thêm: mỗi lần sửa một dòng + một/ vài dòng ADJUST ref_type kiem_ke_sua.';

CREATE OR REPLACE FUNCTION public.kiem_ke_sua_so_chi_them()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'kiem_ke_sua_so chỉ thêm — sửa tiếp bằng một dòng mới'
        USING ERRCODE = 'insufficient_privilege';
END
$$;
DROP TRIGGER IF EXISTS kiem_ke_sua_so_chi_them ON public.kiem_ke_sua_so;
CREATE TRIGGER kiem_ke_sua_so_chi_them
    BEFORE UPDATE OR DELETE ON public.kiem_ke_sua_so
    FOR EACH ROW EXECUTE FUNCTION public.kiem_ke_sua_so_chi_them();

-- Như các bảng sổ kho khác (20261019120000): đọc qua FastAPI, trình duyệt không đọc thẳng.
ALTER TABLE public.kiem_ke_sua_so ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT ON public.kiem_ke_sua_so TO service_role;

-- ── 5. Trigger đọc sổ ròng ────────────────────────────────────────────────

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
    da_tra numeric;
BEGIN
    -- Hoàn tác giao (31/10/2026): đảo ĐÚNG một lần giao, phần khách đã trả thì
    -- không đảo (thuốc ấy đã về quầy bằng RETURN_RECEIVED). Khoá dòng giao gốc
    -- để lần trả chạy song song phải xếp hàng (`drug_return_guard` khoá cùng dòng).
    IF NEW.txn_type = 'DISPENSE_REVERSAL' THEN
        SELECT * INTO goc FROM public.inventory_txn
         WHERE id = NEW.reverses_txn_id AND clinic_id = NEW.clinic_id FOR UPDATE;
        SELECT coalesce(sum(returned_qty), 0) INTO da_tra FROM public.drug_return
         WHERE original_dispense_txn_id = NEW.reverses_txn_id
           AND clinic_id = NEW.clinic_id;
        IF goc.txn_type IS DISTINCT FROM 'DISPENSE'
           OR goc.drug_batch_id IS DISTINCT FROM NEW.drug_batch_id
           OR goc.ref_id IS DISTINCT FROM NEW.ref_id
           OR goc.allocation_id IS DISTINCT FROM NEW.allocation_id
           OR goc.payment_cycle_id IS DISTINCT FROM NEW.payment_cycle_id
           OR NEW.quantity <> -goc.quantity - da_tra THEN
            RAISE EXCEPTION 'DISPENSE_REVERSAL không khớp lần giao gốc'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
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
        -- Đã xuất RÒNG: lần giao đã hoàn tác không còn là "đã xuất".
        SELECT coalesce(-sum(d.quantity), 0) INTO da_xuat FROM public.inventory_txn d
         WHERE d.txn_type IN ('DISPENSE', 'DISPENSE_REVERSAL')
           AND d.allocation_id = NEW.allocation_id
           AND d.clinic_id = NEW.clinic_id;
        -- Huỷ phiếu: phần khách đã trả cũng hết nghĩa vụ giao → đảo cả phần ấy.
        SELECT coalesce(sum(returned_qty), 0) INTO da_tra FROM public.drug_return
         WHERE allocation_id = NEW.allocation_id AND clinic_id = NEW.clinic_id;
        IF goc.txn_type IS DISTINCT FROM 'SALE'
           OR goc.allocation_id IS DISTINCT FROM NEW.allocation_id
           OR goc.payment_cycle_id IS DISTINCT FROM NEW.payment_cycle_id
           OR goc.drug_batch_id IS DISTINCT FROM NEW.drug_batch_id
           OR goc.clinic_id IS DISTINCT FROM NEW.clinic_id
           OR NOT (NEW.quantity = -goc.quantity - da_xuat
                   OR (trang_thai = 'VOIDED'
                       AND NEW.quantity = -goc.quantity - da_xuat + da_tra)) THEN
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
                      WHERE d.txn_type IN ('DISPENSE', 'DISPENSE_REVERSAL')
                        AND d.allocation_id = NEW.allocation_id
                        AND d.clinic_id = NEW.clinic_id), 0)
           - NEW.quantity > pl.quantity THEN
            RAISE EXCEPTION 'DISPENSE theo phân lô: vượt số đã phân (%)', pl.quantity
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $function$;

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
    da_xuat numeric;
    da_tra numeric;
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
               OR NEW.handed_over_qty <> OLD.handed_over_qty)) THEN
        RAISE EXCEPTION 'prescription_allocation: cột đã ghi không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;

    -- Hoàn tác giao (31/10/2026): số đã giao chỉ GIẢM theo sổ — không xuống dưới
    -- đã xuất ròng − khách đã trả (dòng DISPENSE_REVERSAL ghi TRƯỚC khi giảm).
    IF NEW.handed_over_qty < OLD.handed_over_qty THEN
        SELECT coalesce(-sum(quantity), 0) INTO da_xuat FROM public.inventory_txn
         WHERE allocation_id = OLD.id AND clinic_id = OLD.clinic_id
           AND txn_type IN ('DISPENSE', 'DISPENSE_REVERSAL');
        SELECT coalesce(sum(returned_qty), 0) INTO da_tra FROM public.drug_return
         WHERE allocation_id = OLD.id AND clinic_id = OLD.clinic_id;
        IF NEW.handed_over_qty < greatest(da_xuat - da_tra, 0) THEN
            RAISE EXCEPTION 'prescription_allocation: giảm số đã giao phải khớp sổ kho'
                USING ERRCODE = 'check_violation';
        END IF;
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
        -- Phiếu đã huỷ: dòng bán từng "Huỷ phần chưa giao" không đảo được lần hai
        -- (uq_inventory_txn_dao_mot_lan), nên phần đã giao còn treo — thuốc đã về
        -- quầy (handed_over_qty = 0 ở trên), gỡ được; khả dụng chỉ tính phân lô
        -- chưa gỡ.
        SELECT status INTO trang_thai FROM public.payment_cycle
         WHERE payment_cycle_id = OLD.payment_cycle_id AND clinic_id = OLD.clinic_id;
        IF da_ban <> 0 AND trang_thai IS DISTINCT FROM 'VOIDED' THEN
            RAISE EXCEPTION 'Phân lô đang bán (chưa đảo) — không gỡ được'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $function$;

CREATE OR REPLACE FUNCTION public.drug_return_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    xuat record;
    da_tra numeric;
    cot_xu_ly text[] := ARRAY['disposition', 'disposition_by', 'disposition_at',
                              'disposition_reason', 'disposition_txn_id'];
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'drug_return: không xoá lần khách trả thuốc'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        -- Quyết định xử lý: ĐÚNG MỘT lần, chuyển NULL → BAN_LAI | HUY, người quyết là
        -- nhân sự đang hoạt động của phòng khám. Mọi cột khác bất biến.
        IF OLD.disposition IS NOT NULL THEN
            RAISE EXCEPTION 'drug_return: lần trả này đã xử lý (%) — không sửa lại', OLD.disposition
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.disposition IS NULL OR NEW.disposition NOT IN ('BAN_LAI', 'HUY') THEN
            RAISE EXCEPTION 'drug_return: quyết định xử lý phải là BAN_LAI hoặc HUY'
                USING ERRCODE = 'check_violation';
        END IF;
        IF (to_jsonb(NEW) - cot_xu_ly) IS DISTINCT FROM (to_jsonb(OLD) - cot_xu_ly) THEN
            RAISE EXCEPTION 'drug_return: chỉ được đặt quyết định xử lý, không sửa cột khác'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM public.clinic_membership m
                        WHERE m.clinic_id = NEW.clinic_id AND m.staff_id = NEW.disposition_by
                          AND m.is_active) THEN
            RAISE EXCEPTION 'drug_return: người quyết không thuộc phòng khám'
                USING ERRCODE = 'check_violation';
        END IF;
        -- HUY phải trỏ đúng dòng DISCARD của chính lần trả này. FK bên dưới chỉ
        -- ghim clinic/lô; nếu thiếu kiểm này một RECEIVE cùng lô hoặc DISCARD −1
        -- có thể được dùng để quyết huỷ lần trả 3 viên mà không trừ đúng tồn.
        IF NEW.disposition = 'HUY' AND NOT EXISTS (
            SELECT 1 FROM public.inventory_txn t
             WHERE t.id = NEW.disposition_txn_id
               AND t.clinic_id = NEW.clinic_id
               AND t.drug_batch_id = NEW.drug_batch_id
               AND t.txn_type = 'DISCARD'
               AND t.quantity = -NEW.returned_qty
               AND t.ref_type = 'drug_return'
               AND t.ref_id = NEW.id
        ) THEN
            RAISE EXCEPTION 'drug_return: HUY phải trỏ đúng DISCARD đủ số lượng của lần trả'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    SELECT * INTO xuat FROM public.inventory_txn
     WHERE id = NEW.original_dispense_txn_id AND clinic_id = NEW.clinic_id
     FOR UPDATE;
    IF xuat.txn_type IS DISTINCT FROM 'DISPENSE'
       OR xuat.ref_id IS DISTINCT FROM NEW.prescription_id
       OR xuat.allocation_id IS DISTINCT FROM NEW.allocation_id
       OR NEW.disposition IS NOT NULL
       -- Dòng đơn phải thuộc ĐÚNG lượt khai trên lần trả (lineage/audit).
       OR NOT EXISTS (SELECT 1 FROM public.prescription r
                       WHERE r.id = NEW.prescription_id AND r.clinic_id = NEW.clinic_id
                         AND r.visit_id = NEW.visit_id) THEN
        RAISE EXCEPTION 'Khách trả thuốc phải trỏ đúng DISPENSE gốc của dòng đơn'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT coalesce(sum(returned_qty), 0) INTO da_tra FROM public.drug_return
     WHERE original_dispense_txn_id = NEW.original_dispense_txn_id
       AND clinic_id = NEW.clinic_id;
    -- Lần giao đã hoàn tác: thuốc đã về quầy, không còn gì để khách trả.
    IF EXISTS (SELECT 1 FROM public.inventory_txn x
                WHERE x.txn_type = 'DISPENSE_REVERSAL'
                  AND x.reverses_txn_id = NEW.original_dispense_txn_id) THEN
        RAISE EXCEPTION 'Lần giao này đã hoàn tác — không ghi khách trả được'
            USING ERRCODE = 'check_violation';
    END IF;
    IF da_tra + NEW.returned_qty > -xuat.quantity THEN
        RAISE EXCEPTION 'Trả vượt số đã xuất (% + % > %)',
            da_tra, NEW.returned_qty, -xuat.quantity
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

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
                  AND (c.status = 'PENDING_VERIFICATION'
                       OR (c.status = 'PAID' AND NOT EXISTS (
                               SELECT 1 FROM public.inventory_txn s
                                WHERE s.txn_type = 'SALE'
                                  AND s.allocation_id = a.id
                                  AND s.payment_cycle_id = a.payment_cycle_id)))), 0)
         - coalesce((
               SELECT sum(greatest(ban.da_ban - a.handed_over_qty, 0))
                 FROM public.prescription_allocation a
                 CROSS JOIN LATERAL (
                     SELECT coalesce(-sum(t.quantity), 0) AS da_ban
                       FROM public.inventory_txn t
                      WHERE t.allocation_id = a.id AND t.clinic_id = a.clinic_id
                        AND t.txn_type IN ('SALE', 'SALE_REVERSAL')) ban
                WHERE a.clinic_id = p_clinic AND a.drug_batch_id = p_batch
                  AND a.released_at IS NULL), 0)
         - coalesce((
               SELECT sum(r.returned_qty) FROM public.drug_return r
                WHERE r.clinic_id = p_clinic AND r.drug_batch_id = p_batch
                  AND r.disposition IS NULL), 0)
      FROM public.drug_batch b
     WHERE b.id = p_batch AND b.clinic_id = p_clinic
$$;

CREATE OR REPLACE FUNCTION public.gac_ban_tu_quay() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $$
DECLARE lo record;
BEGIN
    IF NEW.txn_type NOT IN ('SALE', 'DISPENSE', 'RETURN_RECEIVED', 'CHUYEN_VAO') THEN
        RETURN NEW;
    END IF;
    SELECT noi_chua, expiry_date, drug_catalog_id, unit, location_id INTO lo FROM public.drug_batch
     WHERE id = NEW.drug_batch_id AND clinic_id = NEW.clinic_id;
    -- Không thấy lô (sai phòng khám / không tồn tại): để khoá ngoại và
    -- `inventory_txn_apply` từ chối bằng đúng câu của chúng, không đè bằng câu này.
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;
    IF NEW.txn_type = 'CHUYEN_VAO' THEN
        IF lo.noi_chua = 'QUAY'
           AND lo.expiry_date < (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date THEN
            RAISE EXCEPTION 'Lô đã hết hạn — không chuyển ra quầy.'
                USING ERRCODE = 'exclusion_violation', CONSTRAINT = 'lo_het_han_quay';
        END IF;
    ELSIF NEW.txn_type = 'RETURN_RECEIVED' AND lo.noi_chua = 'KHO'
          AND NEW.ref_type = 'drug_return'
          AND EXISTS (
            SELECT 1 FROM public.drug_return r
              JOIN public.inventory_txn x
                ON x.id = r.original_dispense_txn_id AND x.clinic_id = r.clinic_id
              JOIN public.prescription p
                ON p.id = r.prescription_id AND p.clinic_id = r.clinic_id
             WHERE r.id = NEW.ref_id AND r.clinic_id = NEW.clinic_id
               AND r.drug_batch_id = NEW.drug_batch_id
               AND r.returned_qty = NEW.quantity
               AND r.returned_qty > 0
               AND x.txn_type = 'DISPENSE' AND x.ref_type = 'prescription'
               AND x.ref_id = p.id AND x.drug_batch_id = NEW.drug_batch_id
               AND -x.quantity >= r.returned_qty
               AND p.drug_catalog_id = lo.drug_catalog_id
               AND lower(trim(coalesce(p.unit, ''))) =
                   lower(trim(coalesce(lo.unit, '')))
               AND coalesce(public.co_so_cua_luot(r.clinic_id, p.visit_id),
                            lo.location_id) = lo.location_id) THEN
        -- Trả về đúng lô đã giao từ kho, vẫn cách ly qua drug_return.disposition.
        RETURN NEW;
    ELSIF lo.noi_chua IS DISTINCT FROM 'QUAY'
          AND NOT (NEW.txn_type = 'DISPENSE'
                   AND NEW.ref_type = 'prescription'
                   AND EXISTS (
                     SELECT 1 FROM public.thuoc_giao_chua_gan_lo g
                       JOIN public.prescription p
                         ON p.id = g.prescription_id AND p.clinic_id = g.clinic_id
                      WHERE g.clinic_id = NEW.clinic_id
                        AND g.prescription_id = NEW.ref_id
                        AND g.drug_batch_id IS NULL AND g.huy_luc IS NULL
                        AND g.so_luong = -NEW.quantity
                        AND g.drug_catalog_id = lo.drug_catalog_id
                        AND lower(trim(coalesce(p.unit, ''))) =
                            lower(trim(coalesce(lo.unit, '')))
                        AND coalesce(public.co_so_cua_luot(g.clinic_id, p.visit_id),
                                     lo.location_id) = lo.location_id)) THEN
        RAISE EXCEPTION 'Lô này đang ở KHO — chuyển sang quầy rồi mới bán / giao.'
            USING ERRCODE = 'exclusion_violation', CONSTRAINT = 'lo_o_kho';
    END IF;
    RETURN NEW;
END
$$;

CREATE OR REPLACE FUNCTION public.payment_refund_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    lan record;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'payment_refund không xoá — huỷ bằng trạng thái'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF TG_OP = 'INSERT' THEN
        SELECT kind, paid_at, status INTO lan FROM public.payment_cycle
         WHERE payment_cycle_id = NEW.payment_cycle_id AND clinic_id = NEW.clinic_id
         FOR UPDATE;
        IF lan.paid_at IS NULL OR lan.kind IS DISTINCT FROM NEW.kind THEN
            RAISE EXCEPTION 'Hoàn tiền chỉ trên lần thu đã từng thu, đúng loại khoản'
                USING ERRCODE = 'check_violation';
        END IF;
        -- Hoàn tác lần thu đã trả khách phần còn lại (đã thu − đã hoàn): hoàn thêm
        -- trên phiếu đã huỷ là trả tiền khách hai lần (31/10/2026).
        IF lan.status = 'VOIDED' THEN
            RAISE EXCEPTION 'Lần thu đã hoàn tác — tiền đã trả khách, không hoàn thêm'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.status NOT IN ('PENDING', 'COMPLETED') THEN
            RAISE EXCEPTION 'Khoản hoàn mới phải PENDING hoặc COMPLETED'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.refund_id <> OLD.refund_id OR NEW.clinic_id <> OLD.clinic_id
       OR NEW.visit_id <> OLD.visit_id OR NEW.kind <> OLD.kind
       OR NEW.payment_cycle_id <> OLD.payment_cycle_id OR NEW.amount <> OLD.amount
       OR NEW.method <> OLD.method OR NEW.reason <> OLD.reason
       OR NEW.created_by <> OLD.created_by OR NEW.created_at <> OLD.created_at
       OR NOT (OLD.status = 'PENDING'
               AND NEW.status IN ('COMPLETED', 'FAILED', 'CANCELLED')) THEN
        RAISE EXCEPTION 'payment_refund: chỉ PENDING → COMPLETED/FAILED/CANCELLED'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

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

    -- Dòng QUẦY thêm (nguon = 'QUAY') không thuộc đơn bác sĩ nên không thuộc hồ sơ
    -- đã ký (TT13): quầy bán thêm / sửa số lượng dòng của mình được ở lượt đã ký.
    -- Dấu vết thu / bán / giao (mức C) vẫn chặn như mọi dòng.
    ky := public.luot_da_ky(NEW.visit_id, NEW.clinic_id)
          AND NEW.nguon IS DISTINCT FROM 'QUAY';

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
        -- Hoàn tác lần thu: thuốc về quầy thì số đã giao giảm theo, cả ở dòng lịch
        -- sử (31/10/2026) — chỉ GIẢM, không cột nào khác.
        IF (to_jsonb(NEW) - bo_qua
              - ARRAY['dispensed_qty', 'dispensed_at', 'dispensed_by_staff_id',
                      'dispense_status'])
             IS DISTINCT FROM
           (to_jsonb(OLD) - bo_qua
              - ARRAY['dispensed_qty', 'dispensed_at', 'dispensed_by_staff_id',
                      'dispense_status'])
           OR NEW.dispensed_qty > OLD.dispensed_qty THEN
            RAISE EXCEPTION 'Dòng đơn đã được đính chính (lịch sử) — không sửa được'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- Gỡ khỏi đơn hiện hành: một thao tác thuần, không kèm đổi nội dung.
    IF NEW.removed_in_correction_id IS NOT NULL OR NEW.removed_at IS NOT NULL
       OR NEW.removed_by IS NOT NULL OR NEW.removal_reason IS NOT NULL THEN
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
        -- MỘT nguồn sự thật cho người / lúc / lý do gỡ (review 4a P2): lấy từ
        -- lần đính chính. Gửi kèm giá trị khác thì từ chối — không ghi đè lặng
        -- lẽ một đầu vào mâu thuẫn.
        IF (NEW.removed_by IS NOT NULL AND NEW.removed_by IS DISTINCT FROM lan.corrected_by)
           OR (NEW.removed_at IS NOT NULL AND NEW.removed_at IS DISTINCT FROM lan.corrected_at)
           OR (NEW.removal_reason IS NOT NULL
               AND NEW.removal_reason IS DISTINCT FROM lan.reason) THEN
            RAISE EXCEPTION 'Người / lúc / lý do gỡ phải khớp lần đính chính'
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.removed_by := lan.corrected_by;
        NEW.removed_at := lan.corrected_at;
        NEW.removal_reason := lan.reason;
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

    -- QUẦY ĐẶT SỐ LƯỢNG TUỲ Ý (C19, Tuyền 02/10/2026; C14 chỉ cho điền chỗ trống):
    -- thu ngân thuốc tăng / giảm số lượng dòng đơn thành BẤT KỲ số nào, bác sĩ đã
    -- ghi số hay chưa. Chỉ số lượng / đơn vị + dấu người, lúc (+ số bác sĩ kê gốc);
    -- thuốc, cách dùng, lưu ý đứng nguyên — không phải quyết định chuyên môn.
    -- Lượt đã ký cũng được. Chặn khi đã có việc THẬT của nhà thuốc: đã giao / chốt /
    -- khách không lấy / trả thuốc, hoặc tiền thuốc đang thu (PAID / chờ xác minh).
    -- Dấu vết cũ của lần thu ĐÃ HOÀN TÁC (phiếu VOIDED) không còn chặn.
    -- Lưới toàn vẹn, không phải token bảo mật: cột dấu do máy chủ đặt.
    IF NEW.so_luong_dien_boi IS NOT NULL
       AND NEW.so_luong_dien_luc IS DISTINCT FROM OLD.so_luong_dien_luc
       AND NEW.drug_name_raw IS NOT DISTINCT FROM OLD.drug_name_raw
       AND NEW.drug_catalog_id IS NOT DISTINCT FROM OLD.drug_catalog_id
       AND NEW.dosage_instructions IS NOT DISTINCT FROM OLD.dosage_instructions
       AND NEW.caution IS NOT DISTINCT FROM OLD.caution
       AND OLD.dispensed_qty = 0
       AND OLD.closed_at IS NULL
       AND OLD.refusal_reason IS NULL
       AND NOT EXISTS (SELECT 1 FROM public.drug_return d
                        WHERE d.prescription_id = OLD.id AND d.clinic_id = OLD.clinic_id)
       AND NOT EXISTS (SELECT 1 FROM public.payment_cycle c
                        WHERE c.clinic_id = OLD.clinic_id AND c.visit_id = OLD.visit_id
                          AND c.kind = 'thuoc'
                          AND c.status IN ('PENDING_VERIFICATION', 'PAID')) THEN
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

NOTIFY pgrst, 'reload schema';
