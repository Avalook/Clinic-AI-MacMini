-- G3b — MÃ VẠCH (Tuyền 14/10/2026: "dán nhãn từng lô, chip mã vạch").
--
-- Hai thứ, KHÔNG đổi cách tồn được tính:
--   1. `drug_ma_vach` — nhiều mã vạch nhà sản xuất (EAN/GTIN in sẵn trên hộp)
--      → MỘT thuốc. Mã là duy nhất trong phòng khám: một mã không thể thuộc
--      hai thuốc (ép Ở ĐÂY, hai người gắn cùng lúc thì một người nhận 409).
--   2. `drug_batch.ma_tem` — mã tem RIÊNG từng lô (in dán lúc nhập). Sinh tự
--      động bằng dãy số, duy nhất toàn bảng, không đổi được sau khi cấp: tem đã
--      dán trên hộp phải quét ra đúng lô đó mãi mãi.
--
-- Chạy lại nhiều lần được (ci-may áp hai lần): mọi câu đều IF NOT EXISTS /
-- DROP … IF EXISTS; lô đã có mã tem thì không cấp lại.

-- ── 1. Mã tem từng lô ───────────────────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS public.drug_batch_tem_seq;

-- Cột có DEFAULT nên lô tạo bằng đường nào (nhập, phiếu nhập, nạp dữ liệu) cũng
-- có tem, không phải sửa từng chỗ INSERT. ADD COLUMN … DEFAULT volatile điền
-- luôn cho lô cũ; lần chạy thứ hai không làm gì.
ALTER TABLE public.drug_batch
    ADD COLUMN IF NOT EXISTS ma_tem text
    DEFAULT ('LT' || lpad(nextval('public.drug_batch_tem_seq')::text, 8, '0'));

-- Lô tạo từ bảng sao lưu cũ có thể còn NULL (cột có từ trước khi DEFAULT áp).
UPDATE public.drug_batch
   SET ma_tem = 'LT' || lpad(nextval('public.drug_batch_tem_seq')::text, 8, '0')
 WHERE ma_tem IS NULL;

ALTER TABLE public.drug_batch ALTER COLUMN ma_tem SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_drug_batch_ma_tem
    ON public.drug_batch (ma_tem);

CREATE OR REPLACE FUNCTION public.drug_batch_ma_tem_bat_doi()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.ma_tem IS DISTINCT FROM OLD.ma_tem THEN
        RAISE EXCEPTION 'Mã tem của lô đã dán lên hộp, không đổi được'
            USING ERRCODE = '23514', CONSTRAINT = 'drug_batch_ma_tem_bat_doi';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS drug_batch_ma_tem_bat_doi ON public.drug_batch;
CREATE TRIGGER drug_batch_ma_tem_bat_doi
    BEFORE UPDATE OF ma_tem ON public.drug_batch
    FOR EACH ROW EXECUTE FUNCTION public.drug_batch_ma_tem_bat_doi();

COMMENT ON COLUMN public.drug_batch.ma_tem IS
    'Mã tem riêng của lô (LT + 8 số), in dán lúc nhập; quét ra đúng lô này. Duy nhất, bất biến.';

-- ── 2. Mã vạch nhà sản xuất → thuốc ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.drug_ma_vach (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    drug_catalog_id  uuid NOT NULL,
    ma               text NOT NULL CHECK (length(ma) BETWEEN 4 AND 64 AND ma = btrim(ma)
                                       AND ma !~ '^LT[0-9]{8}$'),
    -- Dạng so khớp: EAN-8/UPC/EAN-13/GTIN-14 của cùng một hộp là CÙNG một mã
    -- (mã vuông GS1 chứa GTIN-14, mã vạch trên hộp là EAN-13) → đệm 0 đầu cho
    -- đủ 14 số. Trùng ở đây = một mã không thể thuộc hai thuốc.
    ma_chuan         text GENERATED ALWAYS AS (
                         CASE WHEN ma ~ '^[0-9]{8,14}$' THEN lpad(ma, 14, '0') ELSE ma END
                     ) STORED,
    -- tay = gõ/quét ở ô gắn mã · gs1 = lấy từ mã vuông (GTIN) · quet = quét hộp
    nguon            text NOT NULL DEFAULT 'quet' CHECK (nguon IN ('tay', 'quet', 'gs1')),
    tao_boi          uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    tao_luc          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_drug_ma_vach_ma UNIQUE (clinic_id, ma_chuan),
    CONSTRAINT drug_ma_vach_thuoc_fkey FOREIGN KEY (drug_catalog_id, clinic_id)
        REFERENCES public.drug_catalog (id, clinic_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS drug_ma_vach_theo_thuoc
    ON public.drug_ma_vach (clinic_id, drug_catalog_id);

COMMENT ON TABLE public.drug_ma_vach IS
    'Mã vạch in sẵn trên hộp (EAN/GTIN), nhiều mã → một thuốc, mã duy nhất trong phòng khám (G3b, 14/10/2026). Gỡ mã được (ghi nhật ký).';

-- ── 3. RLS — đọc trong phòng khám của mình, ghi qua FastAPI ─────────────
ALTER TABLE public.drug_ma_vach ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS drug_ma_vach_select_own_clinic ON public.drug_ma_vach;
CREATE POLICY drug_ma_vach_select_own_clinic
    ON public.drug_ma_vach FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT, INSERT, DELETE ON public.drug_ma_vach TO service_role;
GRANT SELECT ON public.drug_ma_vach TO authenticated;

NOTIFY pgrst, 'reload schema';
