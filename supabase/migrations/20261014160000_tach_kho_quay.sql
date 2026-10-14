-- G7 — TÁCH KHO / QUẦY trong MỘT cơ sở (Tuyền 14/10/2026: "KHO chứa tất cả, nhập
-- vào đây; QUẦY bán thực tế"; Q8 BẮT BUỘC làm).
--
-- MÔ HÌNH: một lô vật lý ở một cơ sở có TỐI ĐA HAI hàng `drug_batch` — một hàng
-- KHO, một hàng QUẦY — cùng số lô / thuốc / hạn / đơn vị / mã tem. Tồn từng nơi
-- là `quantity_on_hand` của hàng ấy, nên mọi bất biến đã có (tồn = cộng dồn sổ,
-- tồn ≥ 0, khả dụng, FEFO, hết hạn) tự áp cho TỪNG nơi chứa mà không viết lại.
-- Chuyển kho = hai dòng sổ đối ứng trên hai hàng, một giao dịch → tổng KHO + QUẦY
-- của lô không đổi.
--
-- NẠP DỮ LIỆU AN TOÀN: KHÔNG đổi dòng dữ liệu nào. Cột mới mặc định 'QUAY' và công
-- tắc `clinic_location.tach_kho_quay` mặc định TẮT → mọi lô hiện có là hàng QUẦY,
-- quầy bán bằng đúng tồn đang có, sáng hôm sau không hết thuốc. Bật công tắc ở một
-- cơ sở thì từ đó NHẬP đi vào KHO; quầy nhận hàng bằng phiếu chuyển.
--
-- Bất biến ép Ở ĐÂY (SO-LUAT Phần 6):
--   * bán / giao / nhận trả CHỈ trên hàng QUẦY (trigger sổ kho);
--   * không chuyển lô hết hạn ra quầy (trigger sổ kho);
--   * hai hàng cùng số lô phải cùng thuốc / hạn / đơn vị / mã tem (trigger hoãn);
--   * phiếu chuyển CHỈ THÊM như mọi phiếu kho; mỗi phiếu chỉ bị hoàn tác MỘT lần.
--
-- Chạy lại nhiều lần được (ci-may áp hai lần); không BEGIN/COMMIT.

-- ── 1. Nơi chứa ────────────────────────────────────────────────────────
ALTER TABLE public.drug_batch ADD COLUMN IF NOT EXISTS noi_chua text NOT NULL DEFAULT 'QUAY';
ALTER TABLE public.drug_batch DROP CONSTRAINT IF EXISTS drug_batch_noi_chua_check;
ALTER TABLE public.drug_batch ADD CONSTRAINT drug_batch_noi_chua_check
    CHECK (noi_chua IN ('KHO', 'QUAY'));

-- Số lô duy nhất THEO (cơ sở, nơi chứa): cùng số lô được có một hàng KHO và một
-- hàng QUẦY. Giữ nguyên UNIQUE (id, clinic_id) và các khoá ngoại ghép trỏ vào nó.
ALTER TABLE public.drug_batch DROP CONSTRAINT IF EXISTS uq_drug_batch_clinic_location_code;
ALTER TABLE public.drug_batch ADD CONSTRAINT uq_drug_batch_clinic_location_code
    UNIQUE (clinic_id, location_id, noi_chua, batch_code);

-- Mã tem (G3b) thuộc về LÔ: hai hàng cùng lô dùng chung một mã tem.
DROP INDEX IF EXISTS public.uq_drug_batch_ma_tem;
CREATE UNIQUE INDEX IF NOT EXISTS uq_drug_batch_ma_tem_noi
    ON public.drug_batch (ma_tem, noi_chua);

COMMENT ON COLUMN public.drug_batch.noi_chua IS
    'KHO hoặc QUAY (G7, 14/10/2026). Mặc định QUAY = hành vi cũ (một kho). Bán/giao chỉ ở QUAY.';

-- Hai hàng cùng (cơ sở, số lô) phải là CÙNG một lô. Kiểm lúc chốt giao dịch để
-- sửa cả hai hàng trong một câu UPDATE không tự vướng chính nó.
CREATE OR REPLACE FUNCTION public.drug_batch_hang_khop() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.drug_batch x
         WHERE x.clinic_id = NEW.clinic_id AND x.location_id = NEW.location_id
           AND x.batch_code = NEW.batch_code AND x.id <> NEW.id
           AND (x.drug_catalog_id IS DISTINCT FROM NEW.drug_catalog_id
                OR x.expiry_date IS DISTINCT FROM NEW.expiry_date
                OR x.unit IS DISTINCT FROM NEW.unit
                OR x.ma_tem IS DISTINCT FROM NEW.ma_tem)
    ) THEN
        RAISE EXCEPTION 'Lô % có hai hàng KHO / QUẦY khác thuốc, hạn, đơn vị hoặc mã tem',
            NEW.batch_code USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END
$$;
DROP TRIGGER IF EXISTS trg_drug_batch_hang_khop ON public.drug_batch;
CREATE CONSTRAINT TRIGGER trg_drug_batch_hang_khop
    AFTER INSERT OR UPDATE ON public.drug_batch
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.drug_batch_hang_khop();

-- ── 2. Công tắc theo cơ sở (mặc định TẮT) ──────────────────────────────
ALTER TABLE public.clinic_location
    ADD COLUMN IF NOT EXISTS tach_kho_quay boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN public.clinic_location.tach_kho_quay IS
    'Bật = nhập kho đi vào KHO, quầy nhận bằng phiếu chuyển (G7). Tắt = một kho như trước.';

-- ── 3. Sổ kho: hai loại chuyển kho ─────────────────────────────────────
-- CHUYEN_RA (−) trên hàng nguồn, CHUYEN_VAO (+) trên hàng đích; inventory_txn_apply
-- cộng cho mọi loại trừ SALE / SALE_REVERSAL nên tồn từng hàng tự đúng.
ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_type_check;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_type_check CHECK (
    txn_type IN ('RECEIVE', 'DISPENSE', 'ADJUST', 'DISCARD', 'SALE', 'SALE_REVERSAL',
                 'RETURN_RECEIVED', 'CHUYEN_RA', 'CHUYEN_VAO'));

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_qty_sign_check;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_qty_sign_check CHECK (
    (txn_type IN ('RECEIVE', 'SALE_REVERSAL', 'RETURN_RECEIVED', 'CHUYEN_VAO')
        AND quantity > 0)
    OR (txn_type IN ('DISPENSE', 'DISCARD', 'SALE', 'CHUYEN_RA') AND quantity < 0)
    OR (txn_type = 'ADJUST' AND quantity <> 0));

-- Bán / giao / nhận trả CHỈ trên hàng QUẦY; chuyển ra QUẦY không nhận lô hết hạn.
CREATE OR REPLACE FUNCTION public.gac_ban_tu_quay() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $$
DECLARE lo record;
BEGIN
    IF NEW.txn_type NOT IN ('SALE', 'DISPENSE', 'RETURN_RECEIVED', 'CHUYEN_VAO') THEN
        RETURN NEW;
    END IF;
    SELECT noi_chua, expiry_date INTO lo FROM public.drug_batch
     WHERE id = NEW.drug_batch_id AND clinic_id = NEW.clinic_id;
    IF NEW.txn_type = 'CHUYEN_VAO' THEN
        IF lo.noi_chua = 'QUAY'
           AND lo.expiry_date < (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date THEN
            RAISE EXCEPTION 'Lô đã hết hạn — không chuyển ra quầy.'
                USING ERRCODE = 'exclusion_violation', CONSTRAINT = 'lo_het_han_quay';
        END IF;
    ELSIF lo.noi_chua IS DISTINCT FROM 'QUAY' THEN
        RAISE EXCEPTION 'Lô này đang ở KHO — chuyển sang quầy rồi mới bán / giao.'
            USING ERRCODE = 'exclusion_violation', CONSTRAINT = 'lo_o_kho';
    END IF;
    RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS trg_gac_ban_tu_quay ON public.inventory_txn;
CREATE TRIGGER trg_gac_ban_tu_quay
    BEFORE INSERT ON public.inventory_txn
    FOR EACH ROW EXECUTE FUNCTION public.gac_ban_tu_quay();

-- ── 4. Phiếu chuyển kho ────────────────────────────────────────────────
ALTER TABLE public.phieu_kho DROP CONSTRAINT IF EXISTS phieu_kho_loai_check;
ALTER TABLE public.phieu_kho ADD CONSTRAINT phieu_kho_loai_check
    CHECK (loai IN ('NHAP', 'KIEM', 'CHUYEN'));
ALTER TABLE public.phieu_kho ADD COLUMN IF NOT EXISTS huong text;
ALTER TABLE public.phieu_kho ADD COLUMN IF NOT EXISTS ly_do text;
ALTER TABLE public.phieu_kho ADD COLUMN IF NOT EXISTS hoan_tac_cua uuid
    REFERENCES public.phieu_kho(id) ON DELETE RESTRICT;
ALTER TABLE public.phieu_kho DROP CONSTRAINT IF EXISTS phieu_kho_chuyen_du_bo;
ALTER TABLE public.phieu_kho ADD CONSTRAINT phieu_kho_chuyen_du_bo CHECK (
    CASE WHEN loai = 'CHUYEN'
         THEN huong IN ('KHO_QUAY', 'QUAY_KHO')
         ELSE huong IS NULL AND ly_do IS NULL AND hoan_tac_cua IS NULL END);
-- Mỗi phiếu chuyển bị hoàn tác nhiều nhất MỘT lần (ép ở đây, không ở Python).
CREATE UNIQUE INDEX IF NOT EXISTS uq_phieu_kho_hoan_tac_cua
    ON public.phieu_kho (hoan_tac_cua) WHERE hoan_tac_cua IS NOT NULL;

ALTER TABLE public.phieu_kho_dong ADD COLUMN IF NOT EXISTS drug_batch_nguon_id uuid;
ALTER TABLE public.phieu_kho_dong ADD COLUMN IF NOT EXISTS inventory_txn_nguon_id uuid
    REFERENCES public.inventory_txn(id) ON DELETE RESTRICT;
ALTER TABLE public.phieu_kho_dong DROP CONSTRAINT IF EXISTS phieu_kho_dong_nguon_fkey;
ALTER TABLE public.phieu_kho_dong ADD CONSTRAINT phieu_kho_dong_nguon_fkey
    FOREIGN KEY (drug_batch_nguon_id, clinic_id)
    REFERENCES public.drug_batch (id, clinic_id) ON DELETE RESTRICT;
ALTER TABLE public.phieu_kho_dong DROP CONSTRAINT IF EXISTS uq_phieu_kho_dong_txn_nguon;
ALTER TABLE public.phieu_kho_dong ADD CONSTRAINT uq_phieu_kho_dong_txn_nguon
    UNIQUE (inventory_txn_nguon_id);

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
            AND lech IS NOT NULL AND lech = thuc_te - ton_may
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

-- Dòng chuyển: hàng nguồn cũng phải cùng cơ sở với phiếu.
CREATE OR REPLACE FUNCTION public.phieu_kho_dong_nguon_dung_co_so() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF NEW.drug_batch_nguon_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.phieu_kho p
          JOIN public.drug_batch b
            ON b.id = NEW.drug_batch_nguon_id AND b.clinic_id = NEW.clinic_id
         WHERE p.id = NEW.phieu_kho_id AND p.clinic_id = NEW.clinic_id
           AND b.location_id IS DISTINCT FROM p.location_id
    ) THEN
        RAISE EXCEPTION 'Phiếu chuyển: hàng nguồn thuộc kho cơ sở khác với phiếu'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS trg_phieu_kho_dong_nguon_dung_co_so ON public.phieu_kho_dong;
CREATE TRIGGER trg_phieu_kho_dong_nguon_dung_co_so
    BEFORE INSERT ON public.phieu_kho_dong
    FOR EACH ROW EXECUTE FUNCTION public.phieu_kho_dong_nguon_dung_co_so();

NOTIFY pgrst, 'reload schema';
